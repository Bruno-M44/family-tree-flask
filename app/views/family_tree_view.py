import io
import json
import logging as lg
import os
import shutil
import time
import uuid
import zipfile
import werkzeug.exceptions
from collections import deque
from datetime import datetime
from flask import current_app, jsonify, make_response, request, Blueprint, Response
from flask_jwt_extended import jwt_required, get_jwt_identity

from sqlalchemy import delete, insert, or_, select, update
from sqlalchemy.exc import SQLAlchemyError
from ..models import (
    User, FamilyTree, FamilyTreeHiddenBranches, association_user_ft, FamilyTreeCell, Picture,
    Pet, PetPicture, association_parent_child, association_couple,
)
from ..schemas import family_trees_schema, family_tree_schema
from app import db
from .utils import detect_face

family_tree_app = Blueprint("family_tree_app", __name__)

# Guards against zip-bomb archives: caps the total uncompressed size read
# into memory/disk during import, independent of the (much smaller) compressed
# upload size already bounded by MAX_CONTENT_LENGTH.
MAX_IMPORT_UNCOMPRESSED_SIZE = 300 * 1024 * 1024  # 300 MB


@family_tree_app.route("/family_trees", methods=["GET"], endpoint="get_family_trees")
@jwt_required()
def get_family_trees():
    current_user = int(get_jwt_identity())
    all_family_trees = FamilyTree.query.join(association_user_ft).filter(
        association_user_ft.c.id_user == current_user).all()
    result = family_trees_schema.dump(all_family_trees)
    data = {
        "message": "All Family Trees !",
        "status": 200,
        "data": result
    }
    return make_response(jsonify(data), data["status"])


@family_tree_app.route("/family_tree", methods=["POST"], endpoint="create_family_tree")
@jwt_required()
def create_family_tree():
    current_user = int(get_jwt_identity())
    user = db.session.get(User, current_user)
    body = request.get_json() or {}
    required = ['title', 'family_name']
    missing = [f for f in required if not body.get(f)]
    if missing:
        return make_response(jsonify({"message": f"Missing fields: {', '.join(missing)}", "status": 400}), 400)

    new_family_tree = FamilyTree(title=body['title'], family_name=body['family_name'])
    db.session.add(new_family_tree)
    db.session.flush()
    db.session.execute(
        insert(association_user_ft).values(
            id_user=current_user, id_family_tree=new_family_tree.id_family_tree, role="editor"
        )
    )
    try:
        db.session.commit()
    except SQLAlchemyError as err:
        db.session.rollback()
        return make_response(jsonify({"message": f"Database error: {err}", "status": 500}), 500)

    result = family_tree_schema.dump(new_family_tree)
    data = {
        "message": "Family Tree Created !",
        "status": 201,
        "data": result
    }
    return make_response(jsonify(data), data["status"])


VALID_TYPE_UNION = ('mariage', 'pacs', 'union_libre', 'fiancailles', 'autre')


def _move_dir_contents(src: str, dst: str) -> None:
    """Move every file from src into dst (created if needed), then remove src.

    File-by-file rather than shutil.move(src, dst) as a whole, so this stays
    safe even if dst already exists (e.g. a retried merge).
    """
    os.makedirs(dst, exist_ok=True)
    for filename in os.listdir(src):
        shutil.move(os.path.join(src, filename), os.path.join(dst, filename))
    os.rmdir(src)


def _member_role(id_user: int, id_family_tree: int):
    return db.session.execute(
        select(association_user_ft.c.role).where(
            association_user_ft.c.id_user == id_user,
            association_user_ft.c.id_family_tree == id_family_tree,
        )
    ).scalar_one_or_none()


# ---------------------------------------------------------------------------
# Split (inverse of merge): pure graph helpers, no DB/Flask involved so they
# stay unit-testable in isolation. `parent_child_edges` and `couple_edges` are
# plain (id, id) tuple iterables — the endpoint (added separately) is responsible
# for pulling them out of association_parent_child / association_couple first.
# ---------------------------------------------------------------------------

def _compute_descendant_subtree(id_cell_root, parent_child_edges, couple_edges):
    """Return the set of cell ids to extract into the new tree: id_cell_root,
    every descendant reachable through parent_child_edges, and the direct
    spouse(s) of each of those cells (but NOT a spouse's own other spouses/
    children — those are left for _find_cross_links to flag as a conflict,
    since they don't descend from id_cell_root)."""
    children_of = {}
    for parent_id, child_id in parent_child_edges:
        children_of.setdefault(parent_id, set()).add(child_id)

    subtree = set()
    queue = deque([id_cell_root])
    while queue:
        cell_id = queue.popleft()
        if cell_id in subtree:
            continue
        subtree.add(cell_id)
        for child_id in children_of.get(cell_id, ()):
            if child_id not in subtree:
                queue.append(child_id)

    couple_of = {}
    for cell_1, cell_2 in couple_edges:
        couple_of.setdefault(cell_1, set()).add(cell_2)
        couple_of.setdefault(cell_2, set()).add(cell_1)
    spouses = set()
    for cell_id in subtree:
        spouses |= couple_of.get(cell_id, set())
    subtree |= spouses

    return subtree


def _find_cross_links(id_cell_root, subtree_ids, parent_child_edges, couple_edges):
    """Detect any relationship that would cross the new tree boundary: a cell
    inside `subtree_ids` linked (parent/child or couple) to a cell outside it.
    The link(s) from id_cell_root to its own parent(s) are the intended cut
    point, not a conflict, and are excluded.

    Returns a list of {"inside": id, "outside": id, "relation": "parent_child"|"couple"}
    dicts — empty if the split is clean."""
    conflicts = []
    for parent_id, child_id in parent_child_edges:
        if child_id == id_cell_root:
            continue  # the intentional cut point
        parent_in, child_in = parent_id in subtree_ids, child_id in subtree_ids
        if parent_in != child_in:
            inside, outside = (parent_id, child_id) if parent_in else (child_id, parent_id)
            conflicts.append({"inside": inside, "outside": outside, "relation": "parent_child"})
    for cell_1, cell_2 in couple_edges:
        cell_1_in, cell_2_in = cell_1 in subtree_ids, cell_2 in subtree_ids
        if cell_1_in != cell_2_in:
            inside, outside = (cell_1, cell_2) if cell_1_in else (cell_2, cell_1)
            conflicts.append({"inside": inside, "outside": outside, "relation": "couple"})
    return conflicts


@family_tree_app.route(
    "/family_trees/<int:id_family_tree_a>/merge", methods=["POST"], endpoint="merge_family_trees"
)
@jwt_required()
def merge_family_trees(id_family_tree_a: int):
    """Merge family tree B into family tree A: reassign B's cells to A and link
    id_cell_a/id_cell_b. Tree B is deleted once merged.

    `link_type` picks the junction:
      - "couple" (default): id_cell_a and id_cell_b become spouses;
      - "child_of": id_cell_a is the child of id_cell_b (e.g. re-merging a split);
      - "parent_of": id_cell_a is the parent of id_cell_b.
    For the parent/child types, `id_second_parent` (optional) must be a spouse of
    the parent cell, in the parent's tree; the child is linked to it as well."""
    current_user = int(get_jwt_identity())
    body = request.get_json() or {}
    id_family_tree_b = body.get("id_family_tree_b")
    id_cell_a = body.get("id_cell_a")
    id_cell_b = body.get("id_cell_b")
    link_type = body.get("link_type") or "couple"
    id_second_parent = body.get("id_second_parent") or None

    if not id_family_tree_b or not id_cell_a or not id_cell_b:
        return make_response(
            jsonify({"message": "Missing fields: id_family_tree_b, id_cell_a, id_cell_b", "status": 400}), 400
        )
    if link_type not in ("couple", "child_of", "parent_of"):
        return make_response(
            jsonify({"message": "Invalid link_type, expected couple, child_of or parent_of", "status": 400}), 400
        )
    if link_type == "couple" and id_second_parent:
        return make_response(
            jsonify({"message": "id_second_parent only applies to child_of/parent_of", "status": 400}), 400
        )
    if id_family_tree_a == id_family_tree_b:
        return make_response(jsonify({"message": "Cannot merge a family tree with itself", "status": 400}), 400)

    family_tree_a = db.session.get(FamilyTree, id_family_tree_a)
    family_tree_b = db.session.get(FamilyTree, id_family_tree_b)
    if family_tree_a is None or family_tree_b is None:
        return make_response(jsonify({"message": "Family tree not found", "status": 404}), 404)
    if family_tree_a.is_example or family_tree_b.is_example:
        return make_response(jsonify({"message": "Cannot merge the demo family tree", "status": 400}), 400)

    if _member_role(current_user, id_family_tree_a) != "editor" or \
            _member_role(current_user, id_family_tree_b) != "editor":
        return make_response(
            jsonify({"message": "You must be editor of both family trees", "status": 403}), 403
        )

    cell_a = FamilyTreeCell.query.filter_by(
        id_family_tree_cell=id_cell_a, id_family_tree=id_family_tree_a).first()
    cell_b = FamilyTreeCell.query.filter_by(
        id_family_tree_cell=id_cell_b, id_family_tree=id_family_tree_b).first()
    if cell_a is None or cell_b is None:
        return make_response(
            jsonify({"message": "Cell not found in the corresponding family tree", "status": 404}), 404
        )

    parent_ids = []
    if link_type != "couple":
        parent_cell, child_cell = (cell_b, cell_a) if link_type == "child_of" else (cell_a, cell_b)
        # Le futur enfant ne doit pas déjà avoir de parents : on ne greffe pas un 3e parent.
        has_parents = db.session.execute(
            select(association_parent_child).where(
                association_parent_child.c.id_family_tree_cell_child == child_cell.id_family_tree_cell
            )
        ).first()
        if has_parents:
            return make_response(
                jsonify({"message": "The child cell already has parents", "status": 400}), 400
            )
        parent_ids = [parent_cell.id_family_tree_cell]
        if id_second_parent:
            spouse_ids = {
                other
                for c1, c2 in db.session.execute(
                    select(
                        association_couple.c.id_family_tree_cell_couple_1,
                        association_couple.c.id_family_tree_cell_couple_2,
                    ).where(or_(
                        association_couple.c.id_family_tree_cell_couple_1 == parent_cell.id_family_tree_cell,
                        association_couple.c.id_family_tree_cell_couple_2 == parent_cell.id_family_tree_cell,
                    ))
                )
                for other in (c1, c2) if other != parent_cell.id_family_tree_cell
            }
            if id_second_parent not in spouse_ids:
                return make_response(
                    jsonify({"message": "id_second_parent must be a spouse of the parent cell", "status": 400}), 400
                )
            parent_ids.append(id_second_parent)

    start_union = end_union = None
    try:
        if body.get("start_union"):
            start_union = datetime.strptime(body["start_union"], "%d/%m/%Y")
        if body.get("end_union"):
            end_union = datetime.strptime(body["end_union"], "%d/%m/%Y")
    except ValueError:
        return make_response(jsonify({"message": "Invalid date format, expected dd/mm/yyyy", "status": 400}), 400)

    type_union = body.get("type_union") if body.get("type_union") in VALID_TYPE_UNION else None
    place_union = body.get("place_union") or None

    # 1. Safety net: dump both trees to ZIP exports before mutating anything.
    #    Stored under /pictures, which is already a persistent, writable volume
    #    in every environment (prod and CI) — avoids provisioning a new one.
    try:
        backup_dir = (
            f"{current_app.config['PICTURES_ROOT']}/_merge_backups/"
            f"{int(time.time())}_{id_family_tree_a}_{id_family_tree_b}"
        )
        os.makedirs(backup_dir, exist_ok=True)
        for tree_id in (id_family_tree_a, id_family_tree_b):
            with open(f"{backup_dir}/tree_{tree_id}.zip", "wb") as backup_file:
                backup_file.write(_build_export_zip(tree_id))
    except OSError as err:
        lg.warning(
            "Merge safety backup failed for trees %s/%s: %s", id_family_tree_a, id_family_tree_b, err
        )

    try:
        # 2. Move picture/pet-picture files on disk from tree B's folders to tree A's
        #    (file paths are keyed by id_family_tree, see picture_view.py).
        cell_ids_b = [
            c.id_family_tree_cell
            for c in FamilyTreeCell.query.filter_by(id_family_tree=id_family_tree_b).all()
        ]
        pictures_root = current_app.config['PICTURES_ROOT']
        pet_pictures_root = current_app.config['PET_PICTURES_ROOT']
        for cid in cell_ids_b:
            src = f"{pictures_root}/{id_family_tree_b}/{cid}"
            if os.path.isdir(src):
                _move_dir_contents(src, f"{pictures_root}/{id_family_tree_a}/{cid}")
            for pet in Pet.query.filter_by(id_family_tree_cell=cid).all():
                src_pet = f"{pet_pictures_root}/{id_family_tree_b}/{cid}/{pet.id_pet}"
                if os.path.isdir(src_pet):
                    _move_dir_contents(src_pet, f"{pet_pictures_root}/{id_family_tree_a}/{cid}/{pet.id_pet}")

        # 3. Reassign B's cells to A, realigning generations onto the join point:
        #    same generation for a couple, one apart for a parent/child link.
        target_generation_b = cell_a.generation + {"couple": 0, "child_of": -1, "parent_of": 1}[link_type]
        offset = target_generation_b - cell_b.generation
        FamilyTreeCell.query.filter_by(id_family_tree=id_family_tree_b).update(
            {
                FamilyTreeCell.id_family_tree: id_family_tree_a,
                FamilyTreeCell.generation: FamilyTreeCell.generation + offset,
            },
            synchronize_session=False,
        )

        # 4. Create the junction link(s).
        if link_type == "couple":
            db.session.execute(
                insert(association_couple).values(
                    id_family_tree_cell_couple_1=id_cell_a,
                    id_family_tree_cell_couple_2=id_cell_b,
                    start_union=start_union,
                    end_union=end_union,
                    type_union=type_union,
                    place_union=place_union,
                )
            )
        else:
            for parent_id in parent_ids:
                db.session.execute(
                    insert(association_parent_child).values(
                        id_family_tree_cell_parent=parent_id,
                        id_family_tree_cell_child=child_cell.id_family_tree_cell,
                    )
                )

        # 5. Merge memberships onto A (editor beats viewer), then let B's own
        #    membership rows cascade-delete when B is deleted below.
        members_a = {
            row.id_user: row.role
            for row in db.session.execute(
                select(association_user_ft.c.id_user, association_user_ft.c.role).where(
                    association_user_ft.c.id_family_tree == id_family_tree_a
                )
            )
        }
        members_b = db.session.execute(
            select(association_user_ft.c.id_user, association_user_ft.c.role).where(
                association_user_ft.c.id_family_tree == id_family_tree_b
            )
        ).all()
        for row in members_b:
            if row.id_user in members_a:
                if members_a[row.id_user] != "editor" and row.role == "editor":
                    db.session.execute(
                        update(association_user_ft)
                        .where(
                            association_user_ft.c.id_user == row.id_user,
                            association_user_ft.c.id_family_tree == id_family_tree_a,
                        )
                        .values(role="editor")
                    )
            else:
                db.session.execute(
                    insert(association_user_ft).values(
                        id_user=row.id_user, id_family_tree=id_family_tree_a, role=row.role
                    )
                )

        # 6. Tree B's hidden-branches state is no longer meaningful; drop it,
        #    then delete B itself.
        db.session.execute(
            delete(FamilyTreeHiddenBranches).where(
                FamilyTreeHiddenBranches.id_family_tree == id_family_tree_b
            )
        )
        db.session.delete(family_tree_b)
        db.session.commit()
    except SQLAlchemyError as err:
        db.session.rollback()
        return make_response(jsonify({"message": f"Database error: {err}", "status": 500}), 500)

    return make_response(
        jsonify({
            "message": "Family trees merged",
            "status": 200,
            "data": {"id_family_tree": id_family_tree_a},
        }),
        200,
    )


@family_tree_app.route(
    "/family_trees/<int:id_family_tree>/split", methods=["POST"], endpoint="split_family_tree"
)
@jwt_required()
def split_family_tree(id_family_tree: int):
    """Split a cell and all its descendants (inverse of merge) off into a brand
    new family tree. Rejected if any relationship would end up crossing the
    two trees (blended families) — see _find_cross_links."""
    current_user = int(get_jwt_identity())
    body = request.get_json() or {}
    id_cell_root = body.get("id_cell_root")
    title = body.get("title")
    family_name = body.get("family_name")

    if not id_cell_root or not title or not family_name:
        return make_response(
            jsonify({"message": "Missing fields: id_cell_root, title, family_name", "status": 400}), 400
        )

    family_tree = db.session.get(FamilyTree, id_family_tree)
    if family_tree is None:
        return make_response(jsonify({"message": "Family tree not found", "status": 404}), 404)
    if family_tree.is_example:
        return make_response(jsonify({"message": "Cannot split the demo family tree", "status": 400}), 400)

    if _member_role(current_user, id_family_tree) != "editor":
        return make_response(jsonify({"message": "You must be editor of this family tree", "status": 403}), 403)

    cell_root = FamilyTreeCell.query.filter_by(
        id_family_tree_cell=id_cell_root, id_family_tree=id_family_tree).first()
    if cell_root is None:
        return make_response(jsonify({"message": "Cell not found in this family tree", "status": 404}), 404)

    # 1. Compute the subtree to extract, reject if any relationship would
    #    cross back into the tree being split (blended-family edge case).
    all_cell_ids = [
        c.id_family_tree_cell
        for c in FamilyTreeCell.query.filter_by(id_family_tree=id_family_tree).all()
    ]
    pc_edges = [
        (row.id_family_tree_cell_parent, row.id_family_tree_cell_child)
        for row in db.session.execute(
            select(association_parent_child).where(
                association_parent_child.c.id_family_tree_cell_parent.in_(all_cell_ids)
            )
        )
    ]
    couple_edges = [
        (row.id_family_tree_cell_couple_1, row.id_family_tree_cell_couple_2)
        for row in db.session.execute(
            select(association_couple).where(
                association_couple.c.id_family_tree_cell_couple_1.in_(all_cell_ids)
            )
        )
    ]

    subtree_ids = _compute_descendant_subtree(id_cell_root, pc_edges, couple_edges)
    conflicts = _find_cross_links(id_cell_root, subtree_ids, pc_edges, couple_edges)
    if conflicts:
        cells_by_id = {
            c.id_family_tree_cell: c
            for c in FamilyTreeCell.query.filter(
                FamilyTreeCell.id_family_tree_cell.in_(
                    {conflict["inside"] for conflict in conflicts} | {conflict["outside"] for conflict in conflicts}
                )
            ).all()
        }

        def _cell_label(cid):
            cell = cells_by_id.get(cid)
            return f"{cell.surnames} {cell.name}".strip() if cell else str(cid)

        return make_response(
            jsonify({
                "message": "Cannot split: some relationships would cross the two trees",
                "status": 400,
                "data": {
                    "conflicts": [
                        {
                            "inside": conflict["inside"],
                            "inside_name": _cell_label(conflict["inside"]),
                            "outside": conflict["outside"],
                            "outside_name": _cell_label(conflict["outside"]),
                            "relation": conflict["relation"],
                        }
                        for conflict in conflicts
                    ]
                },
            }),
            400,
        )

    # 2. Safety net: dump the tree to a ZIP export before mutating anything.
    try:
        backup_dir = (
            f"{current_app.config['PICTURES_ROOT']}/_split_backups/{int(time.time())}_{id_family_tree}"
        )
        os.makedirs(backup_dir, exist_ok=True)
        with open(f"{backup_dir}/tree_{id_family_tree}.zip", "wb") as backup_file:
            backup_file.write(_build_export_zip(id_family_tree))
    except OSError as err:
        lg.warning("Split safety backup failed for tree %s: %s", id_family_tree, err)

    try:
        # 3. Create the new tree, initially shared with the same members/roles
        #    as the tree being split.
        new_tree = FamilyTree(title=title, family_name=family_name)
        db.session.add(new_tree)
        db.session.flush()

        members = db.session.execute(
            select(association_user_ft.c.id_user, association_user_ft.c.role).where(
                association_user_ft.c.id_family_tree == id_family_tree
            )
        ).all()
        for row in members:
            db.session.execute(
                insert(association_user_ft).values(
                    id_user=row.id_user, id_family_tree=new_tree.id_family_tree, role=row.role
                )
            )

        # 4. Cut the link between the root cell and its own parent(s) — the
        #    intended cut point, never carried over.
        db.session.execute(
            delete(association_parent_child).where(
                association_parent_child.c.id_family_tree_cell_child == id_cell_root
            )
        )

        # 5. Move picture/pet-picture files on disk to the new tree's folders
        #    (file paths are keyed by id_family_tree, see picture_view.py).
        pictures_root = current_app.config['PICTURES_ROOT']
        pet_pictures_root = current_app.config['PET_PICTURES_ROOT']
        for cid in subtree_ids:
            src = f"{pictures_root}/{id_family_tree}/{cid}"
            if os.path.isdir(src):
                _move_dir_contents(src, f"{pictures_root}/{new_tree.id_family_tree}/{cid}")
            for pet in Pet.query.filter_by(id_family_tree_cell=cid).all():
                src_pet = f"{pet_pictures_root}/{id_family_tree}/{cid}/{pet.id_pet}"
                if os.path.isdir(src_pet):
                    _move_dir_contents(
                        src_pet, f"{pet_pictures_root}/{new_tree.id_family_tree}/{cid}/{pet.id_pet}"
                    )

        # 6. Reassign the subtree's cells to the new tree, realigning
        #    generations so the root cell becomes generation 0 there.
        offset = -cell_root.generation
        FamilyTreeCell.query.filter(
            FamilyTreeCell.id_family_tree_cell.in_(subtree_ids)
        ).update(
            {
                FamilyTreeCell.id_family_tree: new_tree.id_family_tree,
                FamilyTreeCell.generation: FamilyTreeCell.generation + offset,
            },
            synchronize_session=False,
        )

        # 7. Drop the moved cells from the source tree's per-user hidden-branches
        #    state — it must not go on referencing cells that just left.
        #    (hidden_above/hidden_below are stored as plain ints, see hidden_branches_view.py)
        for row in FamilyTreeHiddenBranches.query.filter_by(id_family_tree=id_family_tree).all():
            row.hidden_above = [cid for cid in (row.hidden_above or []) if cid not in subtree_ids]
            row.hidden_below = [cid for cid in (row.hidden_below or []) if cid not in subtree_ids]

        db.session.commit()
    except SQLAlchemyError as err:
        db.session.rollback()
        return make_response(jsonify({"message": f"Database error: {err}", "status": 500}), 500)

    return make_response(
        jsonify({
            "message": "Family tree split",
            "status": 201,
            "data": {"id_family_tree": new_tree.id_family_tree},
        }),
        201,
    )


def _build_export_zip(id_family_tree: int) -> bytes:
    """Build the ZIP export (tree.json + pictures + pet pictures) of a family tree.

    Shared by the export endpoint and the merge safety-net backup.
    """
    family_tree = db.session.get(FamilyTree, id_family_tree)
    cells = FamilyTreeCell.query.filter_by(id_family_tree=id_family_tree).all()
    cell_ids = [c.id_family_tree_cell for c in cells]

    if cell_ids:
        pc_rows = db.session.execute(
            select(association_parent_child).where(
                association_parent_child.c.id_family_tree_cell_parent.in_(cell_ids)
            )
        ).fetchall()
        couple_rows = db.session.execute(
            select(association_couple).where(
                association_couple.c.id_family_tree_cell_couple_1.in_(cell_ids)
            )
        ).fetchall()
    else:
        pc_rows, couple_rows = [], []

    cells_data = []
    for cell in cells:
        pictures_data = []
        for pic in cell.pictures:
            pictures_data.append({
                "zip_path": f"pictures/{cell.id_family_tree_cell}_{pic.filename}",
                "picture_date": pic.picture_date.strftime("%d/%m/%Y") if pic.picture_date else None,
                "comments": pic.comments,
                "header_picture": pic.header_picture,
                "face_x": pic.face_x,
                "face_y": pic.face_y,
                "face_width": pic.face_width,
                "face_height": pic.face_height,
            })

        pets_data = []
        for pet in cell.pets:
            pet_pictures_data = []
            for pp in pet.pets_pictures:
                pet_pictures_data.append({
                    "zip_path": f"pets/{pet.id_pet}_{pp.filename}",
                    "picture_date": pp.picture_date.strftime("%d/%m/%Y") if pp.picture_date else None,
                    "comments": pp.comments,
                    "is_main": pp.is_main,
                    "face_x": pp.face_x,
                    "face_y": pp.face_y,
                    "face_width": pp.face_width,
                    "face_height": pp.face_height,
                })
            pets_data.append({
                "export_id": pet.id_pet,
                "name": pet.name,
                "species": pet.species,
                "birthday": pet.birthday.strftime("%d/%m/%Y") if pet.birthday else None,
                "deathday": pet.deathday.strftime("%d/%m/%Y") if pet.deathday else None,
                "comments": pet.comments,
                "pictures": pet_pictures_data,
            })

        cells_data.append({
            "export_id": cell.id_family_tree_cell,
            "name": cell.name,
            "maiden_name": cell.maiden_name,
            "surnames": cell.surnames,
            "birthday": cell.birthday.strftime("%d/%m/%Y") if cell.birthday else None,
            "deathday": cell.deathday.strftime("%d/%m/%Y") if cell.deathday else None,
            "jobs": cell.jobs,
            "comments": cell.comments,
            "generation": cell.generation,
            "pictures": pictures_data,
            "pets": pets_data,
        })

    tree_json = {
        "version": 1,
        "title": family_tree.title,
        "family_name": family_tree.family_name,
        "cells": cells_data,
        "relations": {
            "parent_child": [
                {"parent_id": row.id_family_tree_cell_parent, "child_id": row.id_family_tree_cell_child}
                for row in pc_rows
            ],
            "couples": [
                {
                    "cell_1_id": row.id_family_tree_cell_couple_1,
                    "cell_2_id": row.id_family_tree_cell_couple_2,
                    "start_union": row.start_union.strftime("%d/%m/%Y") if row.start_union else None,
                    "end_union": row.end_union.strftime("%d/%m/%Y") if row.end_union else None,
                }
                for row in couple_rows
            ],
        },
    }

    pictures_root = current_app.config['PICTURES_ROOT']
    pet_pictures_root = current_app.config['PET_PICTURES_ROOT']
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("tree.json", json.dumps(tree_json, ensure_ascii=False, indent=2))
        for cell in cells:
            for pic in cell.pictures:
                src = f"{pictures_root}/{id_family_tree}/{cell.id_family_tree_cell}/{pic.filename}"
                if os.path.isfile(src):
                    zf.write(src, f"pictures/{cell.id_family_tree_cell}_{pic.filename}")
            for pet in cell.pets:
                for pp in pet.pets_pictures:
                    src = f"{pet_pictures_root}/{id_family_tree}/{cell.id_family_tree_cell}/{pet.id_pet}/{pp.filename}"
                    if os.path.isfile(src):
                        zf.write(src, f"pets/{pet.id_pet}_{pp.filename}")

    return buf.getvalue()


@family_tree_app.route("/family_trees/<int:id_family_tree>/export", methods=["GET"], endpoint="export_family_tree")
@jwt_required()
def export_family_tree(id_family_tree: int):
    current_user = int(get_jwt_identity())
    family_tree = FamilyTree.query.join(association_user_ft).filter(
        association_user_ft.c.id_user == current_user,
        FamilyTree.id_family_tree == id_family_tree,
    ).first()
    if family_tree is None:
        return make_response(jsonify({"message": "Family tree not found"}), 404)

    zip_bytes = _build_export_zip(id_family_tree)
    safe_name = family_tree.family_name.replace(" ", "_")
    return Response(
        zip_bytes,
        status=200,
        mimetype="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.zip"'},
    )


@family_tree_app.route("/family_trees/import", methods=["POST"], endpoint="import_family_tree")
@jwt_required()
def import_family_tree():
    current_user = int(get_jwt_identity())

    if "file" not in request.files:
        return make_response(jsonify({"message": "No file provided"}), 400)
    file = request.files["file"]
    if not file.filename.lower().endswith(".zip"):
        return make_response(jsonify({"message": "File must be a ZIP archive"}), 400)

    try:
        with zipfile.ZipFile(io.BytesIO(file.read())) as zf:
            if "tree.json" not in zf.namelist():
                return make_response(jsonify({"message": "Invalid archive: missing tree.json"}), 400)

            total_uncompressed = sum(info.file_size for info in zf.infolist())
            if total_uncompressed > MAX_IMPORT_UNCOMPRESSED_SIZE:
                return make_response(jsonify({"message": "Archive too large once uncompressed"}), 400)

            tree_data = json.loads(zf.read("tree.json"))
            for field in ("title", "family_name", "cells", "relations"):
                if field not in tree_data:
                    return make_response(jsonify({"message": f"Invalid tree.json: missing field '{field}'"}), 400)

            new_tree = FamilyTree(title=tree_data["title"], family_name=tree_data["family_name"])
            db.session.add(new_tree)
            db.session.flush()
            db.session.execute(
                insert(association_user_ft).values(
                    id_user=current_user, id_family_tree=new_tree.id_family_tree, role="editor"
                )
            )

            cell_map = {}
            pet_map = {}

            for cell_data in tree_data["cells"]:
                new_cell = FamilyTreeCell(
                    name=cell_data["name"],
                    surnames=cell_data["surnames"],
                    generation=cell_data["generation"],
                    birthday=cell_data.get("birthday"),
                    deathday=cell_data.get("deathday"),
                    maiden_name=cell_data.get("maiden_name"),
                    jobs=cell_data.get("jobs"),
                    comments=cell_data.get("comments"),
                )
                new_cell.id_family_tree = new_tree.id_family_tree
                db.session.add(new_cell)
                db.session.flush()
                cell_map[cell_data["export_id"]] = new_cell

                for pic_data in cell_data.get("pictures", []):
                    ext = os.path.splitext(pic_data["zip_path"])[1]
                    new_filename = f"{uuid.uuid4()}{ext}"
                    pic_dir = f"{current_app.config['PICTURES_ROOT']}/{new_tree.id_family_tree}/{new_cell.id_family_tree_cell}"
                    os.makedirs(pic_dir, exist_ok=True)
                    filepath = f"{pic_dir}/{new_filename}"
                    if pic_data["zip_path"] in zf.namelist():
                        with zf.open(pic_data["zip_path"]) as src, open(filepath, "wb") as dst:
                            dst.write(src.read())
                    new_pic = Picture(
                        filename=new_filename,
                        picture_date=pic_data.get("picture_date"),
                        comments=pic_data.get("comments") or "",
                        header_picture=pic_data.get("header_picture", False),
                    )
                    # Prioritise face coords from ZIP; run detection if absent
                    face_x = pic_data.get("face_x")
                    if face_x is None and os.path.exists(filepath):
                        try:
                            detected = detect_face(filepath)
                        except Exception:
                            detected = None
                        if detected:
                            face_x, face_y, face_w, face_h = detected
                            new_pic.face_x, new_pic.face_y = face_x, face_y
                            new_pic.face_width, new_pic.face_height = face_w, face_h
                    else:
                        new_pic.face_x = face_x
                        new_pic.face_y = pic_data.get("face_y")
                        new_pic.face_width = pic_data.get("face_width")
                        new_pic.face_height = pic_data.get("face_height")
                    new_pic.id_family_tree_cell = new_cell.id_family_tree_cell
                    db.session.add(new_pic)

                for pet_data in cell_data.get("pets", []):
                    new_pet = Pet(
                        name=pet_data["name"],
                        species=pet_data.get("species"),
                        birthday=pet_data.get("birthday"),
                        deathday=pet_data.get("deathday"),
                        comments=pet_data.get("comments") or "",
                    )
                    new_pet.id_family_tree_cell = new_cell.id_family_tree_cell
                    db.session.add(new_pet)
                    db.session.flush()
                    pet_map[pet_data["export_id"]] = new_pet

                    for pp_data in pet_data.get("pictures", []):
                        ext = os.path.splitext(pp_data["zip_path"])[1]
                        new_filename = f"{uuid.uuid4()}{ext}"
                        pp_dir = f"{current_app.config['PET_PICTURES_ROOT']}/{new_tree.id_family_tree}/{new_cell.id_family_tree_cell}/{new_pet.id_pet}"
                        os.makedirs(pp_dir, exist_ok=True)
                        pp_filepath = f"{pp_dir}/{new_filename}"
                        if pp_data["zip_path"] in zf.namelist():
                            with zf.open(pp_data["zip_path"]) as src, open(pp_filepath, "wb") as dst:
                                dst.write(src.read())
                        new_pp = PetPicture(
                            filename=new_filename,
                            picture_date=pp_data.get("picture_date"),
                            comments=pp_data.get("comments") or "",
                            is_main=pp_data.get("is_main", False),
                        )
                        pp_face_x = pp_data.get("face_x")
                        if pp_face_x is None and os.path.exists(pp_filepath):
                            try:
                                pp_detected = detect_face(pp_filepath)
                            except Exception:
                                pp_detected = None
                            if pp_detected:
                                new_pp.face_x, new_pp.face_y, new_pp.face_width, new_pp.face_height = pp_detected
                        else:
                            new_pp.face_x = pp_face_x
                            new_pp.face_y = pp_data.get("face_y")
                            new_pp.face_width = pp_data.get("face_width")
                            new_pp.face_height = pp_data.get("face_height")
                        new_pp.id_pet = new_pet.id_pet
                        db.session.add(new_pp)

            for pc in tree_data["relations"].get("parent_child", []):
                parent_cell = cell_map.get(pc["parent_id"])
                child_cell = cell_map.get(pc["child_id"])
                if parent_cell and child_cell:
                    db.session.execute(
                        insert(association_parent_child).values(
                            id_family_tree_cell_parent=parent_cell.id_family_tree_cell,
                            id_family_tree_cell_child=child_cell.id_family_tree_cell,
                        )
                    )

            for cp in tree_data["relations"].get("couples", []):
                cell_1 = cell_map.get(cp["cell_1_id"])
                cell_2 = cell_map.get(cp["cell_2_id"])
                if cell_1 and cell_2:
                    start = datetime.strptime(cp["start_union"], "%d/%m/%Y") if cp.get("start_union") else None
                    end = datetime.strptime(cp["end_union"], "%d/%m/%Y") if cp.get("end_union") else None
                    db.session.execute(
                        insert(association_couple).values(
                            id_family_tree_cell_couple_1=cell_1.id_family_tree_cell,
                            id_family_tree_cell_couple_2=cell_2.id_family_tree_cell,
                            start_union=start,
                            end_union=end,
                        )
                    )

            db.session.commit()

    except zipfile.BadZipFile:
        return make_response(jsonify({"message": "Invalid ZIP file"}), 400)
    except (KeyError, json.JSONDecodeError) as e:
        db.session.rollback()
        return make_response(jsonify({"message": f"Invalid tree.json format: {e}"}), 400)
    except SQLAlchemyError as e:
        db.session.rollback()
        return make_response(jsonify({"message": f"Database error: {e}"}), 500)
    except Exception as e:
        db.session.rollback()
        return make_response(jsonify({"message": f"Import failed: {e}"}), 500)

    return make_response(jsonify({"message": "Family tree imported successfully"}), 201)


@family_tree_app.route(
    "/family_trees/<int:id_family_tree>",
    methods=["GET", "PUT", "DELETE"],
    endpoint="get_update_delete_family_tree"
)
@jwt_required()
def get_update_delete_family_tree(id_family_tree: int):
    current_user = int(get_jwt_identity())
    try:
        family_tree = FamilyTree.query.join(association_user_ft).filter(
            association_user_ft.c.id_user == current_user,
            FamilyTree.id_family_tree == id_family_tree).first_or_404()
    except werkzeug.exceptions.NotFound:
        data = {
            "message": "Bad user or family tree",
            "status": 404,
        }
        return make_response(jsonify(data), data["status"])
    if request.method == "GET":
        result = family_tree_schema.dump(family_tree)
        data = {
            "message": "Family Tree Info !",
            "status": 200,
            "data": result
        }
        return make_response(jsonify(data), data["status"])

    if request.method in ("PUT", "DELETE"):
        role = db.session.execute(
            select(association_user_ft.c.role).where(
                association_user_ft.c.id_user == current_user,
                association_user_ft.c.id_family_tree == id_family_tree,
            )
        ).scalar_one_or_none()
        if role != "editor":
            data = {
                "message": "Viewers cannot modify or delete this family tree",
                "status": 403,
            }
            return make_response(jsonify(data), data["status"])

    if request.method == "PUT":
        family_tree = db.session.get(FamilyTree, id_family_tree)
        data = request.get_json() or {}
        if 'title' in data:
            family_tree.title = data['title']
        if 'family_name' in data:
            family_tree.family_name = data['family_name']

        try:
            db.session.commit()
        except SQLAlchemyError as err:
            db.session.rollback()
            return make_response(jsonify({"message": f"Database error: {err}", "status": 500}), 500)
        result = family_tree_schema.dump(family_tree)
        data = {
            "message": "Family Tree Modified !",
            "status": 200,
            "data": result
        }
        return make_response(jsonify(data), data["status"])

    if request.method == "DELETE":
        cell_ids = db.session.query(FamilyTreeCell.id_family_tree_cell).filter_by(id_family_tree=id_family_tree).all()
        cell_ids_list = [c[0] for c in cell_ids]
        if cell_ids_list:
            from app.models import association_parent_child, association_couple
            db.session.execute(
                association_parent_child.delete().where(
                    association_parent_child.c.id_family_tree_cell_parent.in_(cell_ids_list) |
                    association_parent_child.c.id_family_tree_cell_child.in_(cell_ids_list)
                )
            )
            db.session.execute(
                association_couple.delete().where(
                    association_couple.c.id_family_tree_cell_couple_1.in_(cell_ids_list) |
                    association_couple.c.id_family_tree_cell_couple_2.in_(cell_ids_list)
                )
            )
        Picture.query.filter(
            Picture.id_family_tree_cell.in_(
                db.session.query(FamilyTreeCell.id_family_tree_cell).filter_by(id_family_tree=id_family_tree)
            )
        ).delete(synchronize_session=False)
        FamilyTreeCell.query.filter_by(id_family_tree=id_family_tree).delete()
        db.session.delete(family_tree)
        try:
            db.session.commit()
        except SQLAlchemyError as err:
            db.session.rollback()
            return make_response(jsonify({"message": f"Database error: {err}", "status": 500}), 500)
        result = family_tree_schema.dump(family_tree)
        data = {
            "message": "Family Tree Deleted !",
            "status": 200,
            "data": result
        }

        return make_response(jsonify(data), data["status"])
