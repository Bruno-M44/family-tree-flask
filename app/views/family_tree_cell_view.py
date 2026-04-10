from datetime import datetime
import werkzeug.exceptions
from flask import jsonify, make_response, request, Blueprint, current_app
from flask_jwt_extended import jwt_required

from ..models import FamilyTree, FamilyTreeCell, Picture, association_parent_child, association_couple
from ..schemas import family_tree_cell_schema
from .verify_user_authorized import VerifyUserAuthorized
from app import db
from sqlalchemy import select, or_


family_tree_cell_app = Blueprint("family_tree_cell_app", __name__)


@family_tree_cell_app.route(
    "/family_trees/<int:id_family_tree>/family_tree_cells",
    methods=["GET"],
    endpoint="get_family_tree_cells"
)
@jwt_required()
@VerifyUserAuthorized
def get_family_tree_cells(id_family_tree: int):
    cells = FamilyTreeCell.query.filter_by(id_family_tree=id_family_tree).all()
    if not cells:
        return make_response(jsonify({"message": "All Family Tree Cells !", "status": 200, "data": []}), 200)

    cell_ids = [c.id_family_tree_cell for c in cells]
    cell_map = {c.id_family_tree_cell: c for c in cells}

    # Batch load all parent-child relations touching these cells
    pc_rows = db.session.query(association_parent_child).filter(
        or_(
            association_parent_child.c.id_family_tree_cell_parent.in_(cell_ids),
            association_parent_child.c.id_family_tree_cell_child.in_(cell_ids)
        )
    ).all()

    children_by_parent = {}
    cells_with_parents = set()
    extra_cell_ids = set()
    for row in pc_rows:
        pid, cid = row.id_family_tree_cell_parent, row.id_family_tree_cell_child
        if pid in cell_map:
            children_by_parent.setdefault(pid, []).append(cid)
        if cid in cell_map:
            cells_with_parents.add(cid)
        if cid not in cell_map:
            extra_cell_ids.add(cid)

    # Batch load all couple relations touching these cells
    couple_rows = db.session.query(association_couple).filter(
        or_(
            association_couple.c.id_family_tree_cell_couple_1.in_(cell_ids),
            association_couple.c.id_family_tree_cell_couple_2.in_(cell_ids)
        )
    ).all()

    couples_by_cell = {}
    for row in couple_rows:
        id1 = row.id_family_tree_cell_couple_1
        id2 = row.id_family_tree_cell_couple_2
        info = {"start_union": row.start_union, "end_union": row.end_union}
        if id1 in cell_map:
            couples_by_cell.setdefault(id1, []).append({**info, "partner_id": id2})
        if id2 in cell_map:
            couples_by_cell.setdefault(id2, []).append({**info, "partner_id": id1})
        if id1 not in cell_map:
            extra_cell_ids.add(id1)
        if id2 not in cell_map:
            extra_cell_ids.add(id2)

    # Fetch any extra cells (partners or children from other trees) in one query
    if extra_cell_ids:
        extra_cells = FamilyTreeCell.query.filter(
            FamilyTreeCell.id_family_tree_cell.in_(extra_cell_ids)
        ).all()
        cell_map.update({c.id_family_tree_cell: c for c in extra_cells})

    result = []
    for cell in cells:
        cid = cell.id_family_tree_cell
        cell_result = family_tree_cell_schema.dump(cell)

        cell_result["children"] = [
            family_tree_cell_schema.dump(cell_map[child_id])
            for child_id in children_by_parent.get(cid, [])
            if child_id in cell_map
        ]
        cell_result["couples"] = [
            family_tree_cell_schema.dump(cell_map[c["partner_id"]]) | {
                "start_union": c["start_union"], "end_union": c["end_union"]
            }
            for c in couples_by_cell.get(cid, [])
            if c["partner_id"] in cell_map
        ]
        cell_result["orphan"] = cid not in cells_with_parents
        result.append(cell_result)

    data = {
        "message": "All Family Tree Cells !",
        "status": 200,
        "data": result
    }
    return make_response(jsonify(data), data["status"])


@family_tree_cell_app.route(
    "/family_trees/<int:id_family_tree>/family_tree_cells",
    methods=["POST"],
    endpoint="create_family_tree_cell"
)
@jwt_required()
@VerifyUserAuthorized
def create_family_tree_cell(id_family_tree: int):
    body = request.get_json() or {}
    required = ['name', 'surnames', 'birthday', 'jobs', 'comments', 'generation']
    missing = [f for f in required if body.get(f) is None]
    if missing:
        return make_response(jsonify({"message": f"Missing fields: {', '.join(missing)}", "status": 400}), 400)

    try:
        new_family_tree_cell = FamilyTreeCell(
            name=body['name'],
            surnames=body['surnames'],
            birthday=body['birthday'],
            deathday=body.get('deathday'),
            jobs=body['jobs'],
            comments=body['comments'],
            generation=body['generation']
        )
    except ValueError:
        return make_response(jsonify({"message": "Invalid date format, expected dd/mm/yyyy", "status": 400}), 400)

    family_tree = db.session.get(FamilyTree, id_family_tree)
    for child_id in body.get("children") or []:
        child = db.session.get(FamilyTreeCell, child_id)
        if child is None:
            return make_response(jsonify({"message": f"Child cell {child_id} not found", "status": 404}), 404)
        new_family_tree_cell.parent.append(child)

    for parent_id in body.get("parents") or []:
        parent = db.session.get(FamilyTreeCell, parent_id)
        if parent is None:
            return make_response(jsonify({"message": f"Parent cell {parent_id} not found", "status": 404}), 404)
        parent.parent.append(new_family_tree_cell)

    for couple_id in body.get("couples") or []:
        partner = db.session.get(FamilyTreeCell, couple_id)
        if partner is None:
            return make_response(jsonify({"message": f"Couple cell {couple_id} not found", "status": 404}), 404)
        new_family_tree_cell.couple.append(partner)

    family_tree.family_tree_cells.append(new_family_tree_cell)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return make_response(jsonify({"message": "Database error", "status": 500}), 500)

    result = family_tree_cell_schema.dump(new_family_tree_cell)
    data = {
        "message": "Family Tree Cell Created !",
        "status": 201,
        "data": result
    }
    return make_response(jsonify(data), data["status"])


@family_tree_cell_app.route(
    "/family_trees/<int:id_family_tree>/family_tree_cells/<int:id_family_tree_cell>",
    methods=["GET", "PUT", "DELETE"],
    endpoint="get_update_delete_family_tree_cell")
@jwt_required()
@VerifyUserAuthorized
def get_update_delete_family_tree_cell(id_family_tree: int, id_family_tree_cell: int):
    try:
        family_tree_cell = FamilyTreeCell.query.filter_by(
            id_family_tree=id_family_tree,
            id_family_tree_cell=id_family_tree_cell).first_or_404()
    except werkzeug.exceptions.NotFound:
        data = {
            "message": "Bad family tree or family tree cell",
            "status": 404,
        }
        return make_response(jsonify(data), data["status"])

    if request.method == "GET":
        result = family_tree_cell_schema.dump(family_tree_cell)
        result["children"] = get_children(family_tree_cell=family_tree_cell)
        result["couples"] = get_couples(family_tree_cell=family_tree_cell)
        result["orphan"] = identify_orphan(family_tree_cell=family_tree_cell)

        data = {
            "message": "Family Tree Cell Info !",
            "status": 200,
            "data": result
        }
        return make_response(jsonify(data), data["status"])

    if request.method == "PUT":
        data = request.get_json() or {}
        if 'name' in data:
            family_tree_cell.name = data['name']
        if 'surnames' in data:
            family_tree_cell.surnames = data['surnames']
        if 'jobs' in data:
            family_tree_cell.jobs = data['jobs']
        if 'comments' in data:
            family_tree_cell.comments = data['comments']
        if 'generation' in data:
            family_tree_cell.generation = data['generation']
        try:
            if 'birthday' in data:
                family_tree_cell.birthday = datetime.strptime(data['birthday'], "%d/%m/%Y")
            if 'deathday' in data:
                family_tree_cell.deathday = datetime.strptime(data['deathday'], "%d/%m/%Y") if data['deathday'] else None
        except ValueError:
            return make_response(jsonify({"message": "Invalid date format, expected dd/mm/yyyy", "status": 400}), 400)

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            return make_response(jsonify({"message": "Database error", "status": 500}), 500)
        result = family_tree_cell_schema.dump(family_tree_cell)

        data = {
            "message": "Family Tree Cell Modified !",
            "status": 200,
            "data": result
        }
        return make_response(jsonify(data), data["status"])

    if request.method == "DELETE":
        Picture.query.filter_by(id_family_tree_cell=id_family_tree_cell).delete()
        db.session.delete(family_tree_cell)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            return make_response(jsonify({"message": "Database error", "status": 500}), 500)
        result = family_tree_cell_schema.dump(family_tree_cell)
        data = {
            "message": "Family Tree Cell Deleted !",
            "status": 200,
            "data": result
        }
        return make_response(jsonify(data), data["status"])


def get_children(family_tree_cell: FamilyTreeCell) -> list:
    rows = db.session.query(association_parent_child).filter(
        association_parent_child.c.id_family_tree_cell_parent == family_tree_cell.id_family_tree_cell
    ).all()
    child_ids = [row.id_family_tree_cell_child for row in rows]
    if not child_ids:
        return []
    children = FamilyTreeCell.query.filter(
        FamilyTreeCell.id_family_tree_cell.in_(child_ids)
    ).all()
    return [family_tree_cell_schema.dump(child) for child in children]


def get_couples(family_tree_cell: FamilyTreeCell) -> list:
    rows = db.session.query(association_couple).filter(or_(
        association_couple.c.id_family_tree_cell_couple_1 == family_tree_cell.id_family_tree_cell,
        association_couple.c.id_family_tree_cell_couple_2 == family_tree_cell.id_family_tree_cell
    )).all()
    if not rows:
        return []
    partner_data = [
        {
            "partner_id": row.id_family_tree_cell_couple_2
                if row.id_family_tree_cell_couple_1 == family_tree_cell.id_family_tree_cell
                else row.id_family_tree_cell_couple_1,
            "start_union": row.start_union,
            "end_union": row.end_union
        }
        for row in rows
    ]
    partner_ids = [p["partner_id"] for p in partner_data]
    partners = FamilyTreeCell.query.filter(
        FamilyTreeCell.id_family_tree_cell.in_(partner_ids)
    ).all()
    partner_map = {p.id_family_tree_cell: p for p in partners}
    return [
        family_tree_cell_schema.dump(partner_map[p["partner_id"]]) | {
            "start_union": p["start_union"], "end_union": p["end_union"]
        }
        for p in partner_data if p["partner_id"] in partner_map
    ]


def identify_orphan(family_tree_cell: FamilyTreeCell) -> bool:
    return not db.session.query(association_parent_child).filter(
        association_parent_child.c.id_family_tree_cell_child == family_tree_cell.id_family_tree_cell
    ).first()
