from datetime import datetime, timezone
from flask import jsonify, make_response, request, Blueprint
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import SQLAlchemyError

from ..models import FamilyTree, FamilyTreeCell, FamilyTreeHiddenBranches, association_user_ft
from app import db

hidden_branches_app = Blueprint("hidden_branches_app", __name__)


def _is_member(id_user: int, id_family_tree: int) -> bool:
    return FamilyTree.query.join(association_user_ft).filter(
        association_user_ft.c.id_user == id_user,
        FamilyTree.id_family_tree == id_family_tree,
    ).first() is not None


@hidden_branches_app.route(
    "/family_trees/<int:id_family_tree>/hidden_branches",
    methods=["GET", "PUT"],
    endpoint="hidden_branches",
)
@jwt_required()
def hidden_branches(id_family_tree: int):
    current_user = int(get_jwt_identity())

    if not _is_member(current_user, id_family_tree):
        return make_response(jsonify({"message": "Access denied"}), 403)

    if request.method == "GET":
        row = FamilyTreeHiddenBranches.query.filter_by(
            id_user=current_user, id_family_tree=id_family_tree
        ).first()
        data = {
            "hidden_above": row.hidden_above if row else [],
            "hidden_below": row.hidden_below if row else [],
        }
        return make_response(jsonify({"data": data}), 200)

    body = request.get_json() or {}
    try:
        hidden_above = [int(x) for x in (body.get("hidden_above") or [])]
        hidden_below = [int(x) for x in (body.get("hidden_below") or [])]
    except (TypeError, ValueError):
        return make_response(jsonify({"message": "hidden_above and hidden_below must be lists of integers"}), 400)

    all_ids = set(hidden_above) | set(hidden_below)
    if all_ids:
        valid_ids = {
            row.id_family_tree_cell
            for row in FamilyTreeCell.query
            .filter_by(id_family_tree=id_family_tree)
            .with_entities(FamilyTreeCell.id_family_tree_cell)
            .all()
        }
        invalid = all_ids - valid_ids
        if invalid:
            return make_response(jsonify({"message": f"Unknown cell IDs for this tree: {sorted(invalid)}"}), 400)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    row = FamilyTreeHiddenBranches.query.filter_by(
        id_user=current_user, id_family_tree=id_family_tree
    ).first()
    if row:
        row.hidden_above = hidden_above
        row.hidden_below = hidden_below
        row.updated_at = now
    else:
        row = FamilyTreeHiddenBranches(
            id_user=current_user,
            id_family_tree=id_family_tree,
            hidden_above=hidden_above,
            hidden_below=hidden_below,
            updated_at=now,
        )
        db.session.add(row)

    try:
        db.session.commit()
    except SQLAlchemyError as e:
        db.session.rollback()
        return make_response(jsonify({"message": f"Database error: {e}"}), 500)

    return make_response(jsonify({"data": {"hidden_above": hidden_above, "hidden_below": hidden_below}}), 200)
