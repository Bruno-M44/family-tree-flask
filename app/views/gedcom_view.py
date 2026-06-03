"""GEDCOM 5.5.1 export and import endpoints."""
from collections import Counter
from datetime import datetime

from flask import Blueprint, Response, jsonify, make_response, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy import insert, select
from sqlalchemy.exc import SQLAlchemyError

from ..models import (
    FamilyTree, FamilyTreeCell,
    association_couple, association_parent_child, association_user_ft,
)
from app import db

gedcom_app = Blueprint("gedcom_app", __name__)

_GED_MONTHS = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN',
               'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']
_GED_MONTH_IDX = {m: i + 1 for i, m in enumerate(_GED_MONTHS)}

_TYPE_UNION_EXPORT = {
    'mariage': 'Mariage', 'pacs': 'PACS', 'union_libre': 'Union libre',
    'fiancailles': 'Fiançailles', 'autre': 'Autre',
}
_TYPE_UNION_IMPORT = {
    'mariage': 'mariage', 'marriage': 'mariage',
    'pacs': 'pacs', 'civil partnership': 'pacs', 'civil union': 'pacs',
    'union libre': 'union_libre', 'common law': 'union_libre',
    'fiançailles': 'fiancailles', 'fiancailles': 'fiancailles', 'engagement': 'fiancailles',
    'autre': 'autre', 'other': 'autre',
}


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _ged_date(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return f"{dt.day:02d} {_GED_MONTHS[dt.month - 1]} {dt.year}"


def _parse_ged_date(s: str) -> datetime | None:
    if not s:
        return None
    parts = s.strip().upper().split()
    try:
        if len(parts) == 3:
            return datetime(int(parts[2]), _GED_MONTH_IDX.get(parts[1], 1), int(parts[0]))
        if len(parts) == 2:
            return datetime(int(parts[1]), _GED_MONTH_IDX.get(parts[0], 1), 1)
        if len(parts) == 1:
            return datetime(int(parts[0]), 1, 1)
    except (ValueError, KeyError):
        pass
    return None


def _dt_str(dt: datetime | None) -> str | None:
    """Convert datetime back to the dd/mm/yyyy string expected by FamilyTreeCell.__init__."""
    return dt.strftime("%d/%m/%Y") if dt else None


# ── GEDCOM parser ──────────────────────────────────────────────────────────────

def _parse_gedcom(text: str) -> list:
    """Parse GEDCOM text into a list of level-0 records, each a nested dict."""
    roots: list = []
    stack: list = []

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = line.split(' ', 2)
        if len(parts) < 2:
            continue
        try:
            level = int(parts[0])
        except ValueError:
            continue

        rest = parts[1:]
        if rest[0].startswith('@') and rest[0].endswith('@') and len(rest) >= 2:
            xref, tag = rest[0], rest[1]
            value = rest[2] if len(rest) > 2 else ''
        else:
            xref, tag = None, rest[0]
            value = rest[1] if len(rest) > 1 else ''

        node = {'tag': tag, 'xref': xref, 'value': value, 'children': []}

        del stack[level:]          # keep only ancestors
        if stack:
            stack[-1]['children'].append(node)
        else:
            roots.append(node)
        stack.append(node)

    return roots


def _child_value(node: dict, tag: str) -> str | None:
    for c in node['children']:
        if c['tag'] == tag:
            return c['value'] or None
    return None


def _child_values(node: dict, tag: str) -> list:
    return [c['value'] for c in node['children'] if c['tag'] == tag and c['value']]


def _child_node(node: dict, tag: str) -> dict | None:
    for c in node['children']:
        if c['tag'] == tag:
            return c
    return None


def _child_nodes(node: dict, tag: str) -> list:
    return [c for c in node['children'] if c['tag'] == tag]


def _extract_note_text(node: dict) -> str | None:
    parts = [node['value'] or '']
    for c in node['children']:
        if c['tag'] == 'CONT':
            parts.append('\n' + (c['value'] or ''))
        elif c['tag'] == 'CONC':
            parts.append(c['value'] or '')
    result = ''.join(parts).strip()
    return result or None


# ── Export ─────────────────────────────────────────────────────────────────────

@gedcom_app.route(
    "/family_trees/<int:id_family_tree>/export/gedcom",
    methods=["GET"],
    endpoint="export_gedcom",
)
@jwt_required()
def export_gedcom(id_family_tree: int):
    current_user = int(get_jwt_identity())
    family_tree = FamilyTree.query.join(association_user_ft).filter(
        association_user_ft.c.id_user == current_user,
        FamilyTree.id_family_tree == id_family_tree,
    ).first()
    if family_tree is None:
        return make_response(jsonify({"message": "Family tree not found"}), 404)

    cells = FamilyTreeCell.query.filter_by(id_family_tree=id_family_tree).all()
    cell_ids = [c.id_family_tree_cell for c in cells]
    indi_tag = {cid: f"I{cid}" for cid in cell_ids}

    couple_rows, pc_rows = [], []
    if cell_ids:
        couple_rows = db.session.execute(
            select(association_couple).where(
                association_couple.c.id_family_tree_cell_couple_1.in_(cell_ids)
            )
        ).fetchall()
        pc_rows = db.session.execute(
            select(association_parent_child).where(
                association_parent_child.c.id_family_tree_cell_parent.in_(cell_ids)
            )
        ).fetchall()

    children_by_parent: dict = {}
    for row in pc_rows:
        children_by_parent.setdefault(row.id_family_tree_cell_parent, []).append(
            row.id_family_tree_cell_child
        )

    out = [
        "0 HEAD",
        "1 SOUR FamilyTree",
        "2 NAME Votre App",
        "1 GEDC",
        "2 VERS 5.5.1",
        "1 CHAR UTF-8",
        "1 LANG French",
    ]

    for cell in cells:
        iid = indi_tag[cell.id_family_tree_cell]
        out.append(f"0 @{iid}@ INDI")

        surnames = cell.surnames or ''
        name = cell.name or ''
        out.append(f"1 NAME {surnames} /{name}/")
        if surnames:
            out.append(f"2 GIVN {surnames}")
        if name:
            out.append(f"2 SURN {name}")
        if cell.alias:
            out.append(f"2 NICK {cell.alias}")
        if cell.maiden_name:
            out.append(f"2 _MARNM {cell.maiden_name}")

        sex_out = {'M': 'M', 'F': 'F'}.get(cell.sexe or '', 'U')
        out.append(f"1 SEX {sex_out}")

        if cell.birthday or cell.birth_place:
            out.append("1 BIRT")
            if cell.birthday:
                out.append(f"2 DATE {_ged_date(cell.birthday)}")
            if cell.birth_place:
                out.append(f"2 PLAC {cell.birth_place}")

        if cell.deathday or cell.death_place:
            out.append("1 DEAT Y")
            if cell.deathday:
                out.append(f"2 DATE {_ged_date(cell.deathday)}")
            if cell.death_place:
                out.append(f"2 PLAC {cell.death_place}")

        if cell.baptism_date or cell.baptism_place:
            out.append("1 BAPM")
            if cell.baptism_date:
                out.append(f"2 DATE {_ged_date(cell.baptism_date)}")
            if cell.baptism_place:
                out.append(f"2 PLAC {cell.baptism_place}")

        if cell.burial_date or cell.burial_place or cell.burial_type:
            burial_tag = "CREM" if cell.burial_type == 'cremation' else "BURI"
            out.append(f"1 {burial_tag}")
            if cell.burial_date:
                out.append(f"2 DATE {_ged_date(cell.burial_date)}")
            if cell.burial_place:
                out.append(f"2 PLAC {cell.burial_place}")

        if cell.nationality:
            out.append(f"1 NATI {cell.nationality}")
        if cell.jobs:
            out.append(f"1 OCCU {cell.jobs}")
        if cell.education:
            out.append(f"1 EDUC {cell.education}")
        if cell.military_service:
            out.append(f"1 _MILT {cell.military_service}")

        note_parts = [p for p in (cell.biography, cell.comments) if p]
        if note_parts:
            note = "\n---\n".join(note_parts)
            note_lines = note.split('\n')
            out.append(f"1 NOTE {note_lines[0]}")
            for nl in note_lines[1:]:
                out.append(f"2 CONT {nl}")

    fam_num = 0
    coupled_cell_ids: set = set()
    for row in couple_rows:
        fam_num += 1
        fid = f"F{fam_num}"
        id1 = row.id_family_tree_cell_couple_1
        id2 = row.id_family_tree_cell_couple_2
        coupled_cell_ids.add(id1)
        if id2:
            coupled_cell_ids.add(id2)
        out.append(f"0 @{fid}@ FAM")
        if id1 in indi_tag:
            out.append(f"1 HUSB @{indi_tag[id1]}@")
        if id2 and id2 in indi_tag:
            out.append(f"1 WIFE @{indi_tag[id2]}@")

        children_1 = set(children_by_parent.get(id1, []))
        children_2 = set(children_by_parent.get(id2, [])) if id2 else set()
        shared = children_1 & children_2 if id2 else children_1
        for child_id in shared:
            if child_id in indi_tag:
                out.append(f"1 CHIL @{indi_tag[child_id]}@")

        if row.start_union or row.place_union or row.type_union or row.end_union:
            out.append("1 MARR")
            if row.start_union:
                out.append(f"2 DATE {_ged_date(row.start_union)}")
            if row.place_union:
                out.append(f"2 PLAC {row.place_union}")
            if row.type_union:
                out.append(f"2 TYPE {_TYPE_UNION_EXPORT.get(row.type_union, row.type_union)}")
            if row.end_union:
                out.append(f"2 _ENDDATE {_ged_date(row.end_union)}")

    # Export parents who have children but no couple entry (single parents)
    cell_by_id = {c.id_family_tree_cell: c for c in cells}
    solo_parent_children: dict = {}
    for pc_row in pc_rows:
        pid = pc_row.id_family_tree_cell_parent
        cid = pc_row.id_family_tree_cell_child
        if pid not in coupled_cell_ids and pid in indi_tag:
            solo_parent_children.setdefault(pid, []).append(cid)

    for parent_id, child_ids in solo_parent_children.items():
        fam_num += 1
        fid = f"F{fam_num}"
        out.append(f"0 @{fid}@ FAM")
        parent_cell = cell_by_id.get(parent_id)
        role = "WIFE" if parent_cell and parent_cell.sexe == 'F' else "HUSB"
        out.append(f"1 {role} @{indi_tag[parent_id]}@")
        for child_id in child_ids:
            if child_id in indi_tag:
                out.append(f"1 CHIL @{indi_tag[child_id]}@")

    out.append("0 TRLR")

    filename = f"{family_tree.title}.ged".replace(" ", "_")
    return Response(
        "\n".join(out),
        mimetype="text/plain; charset=UTF-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Import helpers ─────────────────────────────────────────────────────────────

def _extract_indi(node: dict) -> dict:
    data: dict = {}

    name_node = _child_node(node, 'NAME')
    if name_node:
        givn = _child_value(name_node, 'GIVN')
        surn = _child_value(name_node, 'SURN')
        raw = name_node['value'] or ''
        if givn:
            data['surnames'] = givn
        elif '/' in raw:
            data['surnames'] = raw.split('/')[0].strip()
        else:
            data['surnames'] = raw.strip()
        if surn:
            data['name'] = surn
        elif '/' in raw and raw.count('/') >= 2:
            data['name'] = raw.split('/')[1].strip()
        nick = _child_value(name_node, 'NICK')
        if nick:
            data['alias'] = nick
        marnm = _child_value(name_node, '_MARNM')
        if marnm:
            data['maiden_name'] = marnm

    sex = _child_value(node, 'SEX')
    data['sexe'] = {'M': 'M', 'F': 'F'}.get(sex or '', 'ND')

    for ev_tag, date_k, place_k, btype in [
        ('BIRT', 'birthday',     'birth_place',  None),
        ('DEAT', 'deathday',     'death_place',  None),
        ('BAPM', 'baptism_date', 'baptism_place', None),
        ('BURI', 'burial_date',  'burial_place', 'inhumation'),
        ('CREM', 'burial_date',  'burial_place', 'cremation'),
    ]:
        ev = _child_node(node, ev_tag)
        if ev:
            d = _parse_ged_date(_child_value(ev, 'DATE') or '')
            if d:
                data[date_k] = d
            p = _child_value(ev, 'PLAC')
            if p:
                data[place_k] = p
            if btype:
                data['burial_type'] = btype

    for tag, key in [
        ('NATI', 'nationality'), ('OCCU', 'jobs'),
        ('EDUC', 'education'), ('_MILT', 'military_service'),
    ]:
        v = _child_value(node, tag)
        if v:
            data[key] = v

    notes = [_extract_note_text(n) for n in _child_nodes(node, 'NOTE')]
    notes = [n for n in notes if n]
    if notes:
        combined = notes[0]
        if '---' in combined:
            bio, comm = combined.split('---', 1)
            data['biography'] = bio.strip() or None
            data['comments'] = comm.strip() or None
        else:
            data['biography'] = combined
        if len(notes) > 1:
            data.setdefault('comments', '\n'.join(notes[1:]))

    return data


def _extract_fam(node: dict) -> dict:
    data = {
        'husb': _child_value(node, 'HUSB'),
        'wife': _child_value(node, 'WIFE'),
        'chil': _child_values(node, 'CHIL'),
    }
    marr = _child_node(node, 'MARR')
    if marr:
        data['marr_date'] = _parse_ged_date(_child_value(marr, 'DATE') or '')
        data['marr_plac'] = _child_value(marr, 'PLAC')
        t = _child_value(marr, 'TYPE')
        data['marr_type'] = _TYPE_UNION_IMPORT.get((t or '').lower().strip()) if t else None
        end_node = _child_node(marr, '_ENDDATE')
        if end_node:
            data['end_union'] = _parse_ged_date(end_node['value'] or '')
    # Standard GEDCOM divorce record
    div = _child_node(node, 'DIV')
    if div:
        d = _parse_ged_date(_child_value(div, 'DATE') or '')
        if d:
            data['end_union'] = d
    return data


def _compute_generations(xrefs: set, families: list) -> dict:
    """Assign generation numbers using DFS with max-parent-depth.

    Children receive max(parent_depths) + 1 so a child of parents at
    different depths is placed below the deepest parent.
    The result is then shifted so that the deepest parent (HUSB or WIFE)
    sits at generation 0; their ancestors get negative values and
    descendants get positive values.
    """
    parents_of: dict = {}
    parent_xrefs: set = set()

    for fam in families:
        husb = fam.get('husb')
        wife = fam.get('wife')
        parents = [p for p in (husb, wife) if p and p in xrefs]
        for p in parents:
            parent_xrefs.add(p)
        for chil in fam.get('chil', []):
            if chil not in xrefs:
                continue
            parents_of.setdefault(chil, []).extend(parents)

    depths: dict = {}

    def _depth(xref: str, visiting: frozenset = frozenset()) -> int:
        if xref in depths:
            return depths[xref]
        if xref in visiting:
            return 0  # cycle guard
        pars = parents_of.get(xref, [])
        d = max((_depth(p, visiting | {xref}) for p in pars), default=-1) + 1
        depths[xref] = d
        return d

    for xref in xrefs:
        _depth(xref)

    # Shift so the deepest HUSB/WIFE individual lands at generation 0.
    if parent_xrefs:
        max_depth = max(depths.get(x, 0) for x in parent_xrefs)
    elif depths:
        max_depth = max(depths.values())
    else:
        max_depth = 0

    return {xref: d - max_depth for xref, d in depths.items()}


# ── Import ─────────────────────────────────────────────────────────────────────

@gedcom_app.route(
    "/family_trees/import/gedcom",
    methods=["POST"],
    endpoint="import_gedcom",
)
@jwt_required()
def import_gedcom():
    current_user = int(get_jwt_identity())
    if 'file' not in request.files:
        return make_response(jsonify({"message": "Missing file"}), 400)

    raw = request.files['file'].read()
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError:
        text = raw.decode('latin-1')

    records = _parse_gedcom(text)

    indi_nodes = {r['xref']: r for r in records if r['tag'] == 'INDI' and r['xref']}
    fam_nodes  = [r for r in records if r['tag'] == 'FAM']

    individuals = {xref: _extract_indi(node) for xref, node in indi_nodes.items()}
    families    = [_extract_fam(node) for node in fam_nodes]
    generations = _compute_generations(set(individuals), families)

    surnames = [v.get('name') for v in individuals.values() if v.get('name')]
    if surnames:
        family_name = Counter(surnames).most_common(1)[0][0]
        title = f"Famille {family_name}"
    else:
        family_name, title = "Importé", "Arbre importé"

    family_tree = FamilyTree(title=title, family_name=family_name)
    db.session.add(family_tree)
    db.session.flush()
    db.session.execute(
        insert(association_user_ft).values(
            id_user=current_user,
            id_family_tree=family_tree.id_family_tree,
            role="editor",
        )
    )

    xref_to_id: dict = {}
    xref_to_cell: dict = {}
    for xref, data in individuals.items():
        cell = FamilyTreeCell(
            name=data.get('name') or '',
            surnames=data.get('surnames') or '',
            generation=generations.get(xref, 0),
            maiden_name=data.get('maiden_name'),
            birthday=_dt_str(data.get('birthday')),
            deathday=_dt_str(data.get('deathday')),
            birth_place=data.get('birth_place'),
            death_place=data.get('death_place'),
            baptism_date=_dt_str(data.get('baptism_date')),
            baptism_place=data.get('baptism_place'),
            burial_date=_dt_str(data.get('burial_date')),
            burial_place=data.get('burial_place'),
            burial_type=data.get('burial_type'),
            nationality=data.get('nationality'),
            jobs=data.get('jobs'),
            education=data.get('education'),
            military_service=data.get('military_service'),
            alias=data.get('alias'),
            sexe=data.get('sexe', 'ND'),
            biography=data.get('biography'),
            comments=data.get('comments'),
        )
        family_tree.family_tree_cells.append(cell)
        db.session.flush()
        xref_to_id[xref] = cell.id_family_tree_cell
        xref_to_cell[xref] = cell

    # Fix A: individuals with no parents (GEDCOM roots) get gen=gen_min, which is
    # often far below their partner's generation. Align them to their partner's level.
    has_parents_xref = {chil for fam in families for chil in fam.get('chil', [])}
    root_xrefs = {x for x in individuals if x not in has_parents_xref}
    for fam in families:
        husb_xref = fam.get('husb')
        wife_xref = fam.get('wife')
        if not husb_xref or not wife_xref:
            continue
        if husb_xref not in xref_to_cell or wife_xref not in xref_to_cell:
            continue
        gen_h = generations.get(husb_xref, 0)
        gen_w = generations.get(wife_xref, 0)
        if gen_h == gen_w:
            continue
        partner_gen = max(gen_h, gen_w)
        if husb_xref in root_xrefs and gen_h < gen_w:
            xref_to_cell[husb_xref].generation = partner_gen
        if wife_xref in root_xrefs and gen_w < gen_h:
            xref_to_cell[wife_xref].generation = partner_gen

    for fam in families:
        husb_id = xref_to_id.get(fam.get('husb') or '')
        wife_id = xref_to_id.get(fam.get('wife') or '')
        if husb_id and wife_id:
            db.session.execute(
                insert(association_couple).values(
                    id_family_tree_cell_couple_1=husb_id,
                    id_family_tree_cell_couple_2=wife_id,
                    start_union=fam.get('marr_date'),
                    place_union=fam.get('marr_plac'),
                    type_union=fam.get('marr_type'),
                    end_union=fam.get('end_union'),
                )
            )
        parent_ids = [p for p in (husb_id, wife_id) if p]
        for chil_xref in fam.get('chil', []):
            child_id = xref_to_id.get(chil_xref)
            if not child_id:
                continue
            for parent_id in parent_ids:
                db.session.execute(
                    insert(association_parent_child).values(
                        id_family_tree_cell_parent=parent_id,
                        id_family_tree_cell_child=child_id,
                    )
                )

    try:
        db.session.commit()
    except SQLAlchemyError as e:
        db.session.rollback()
        return make_response(jsonify({"message": f"Database error: {e}"}), 500)

    return make_response(jsonify({"id_family_tree": family_tree.id_family_tree}), 201)
