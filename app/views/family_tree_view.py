import werkzeug.exceptions
from flask import jsonify, make_response, request, Blueprint
from flask_jwt_extended import jwt_required, get_jwt_identity

from ..models import User, FamilyTree, association_user_ft, FamilyTreeCell, Picture
from ..schemas import family_trees_schema, family_tree_schema
from app import db

family_tree_app = Blueprint("family_tree_app", __name__)


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
    user.family_trees.append(new_family_tree)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return make_response(jsonify({"message": "Database error", "status": 500}), 500)

    result = family_tree_schema.dump(new_family_tree)
    data = {
        "message": "Family Tree Created !",
        "status": 201,
        "data": result
    }
    return make_response(jsonify(data), data["status"])


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
    if request.method == "PUT":
        family_tree = db.session.get(FamilyTree, id_family_tree)
        data = request.get_json() or {}
        if 'title' in data:
            family_tree.title = data['title']
        if 'family_name' in data:
            family_tree.family_name = data['family_name']

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            return make_response(jsonify({"message": "Database error", "status": 500}), 500)
        result = family_tree_schema.dump(family_tree)
        data = {
            "message": "Family Tree Modified !",
            "status": 200,
            "data": result
        }
        return make_response(jsonify(data), data["status"])

    if request.method == "DELETE":
        Picture.query.filter(
            Picture.id_family_tree_cell.in_(
                db.session.query(FamilyTreeCell.id_family_tree_cell).filter_by(id_family_tree=id_family_tree)
            )
        ).delete(synchronize_session=False)
        FamilyTreeCell.query.filter_by(id_family_tree=id_family_tree).delete()
        db.session.delete(family_tree)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            return make_response(jsonify({"message": "Database error", "status": 500}), 500)
        result = family_tree_schema.dump(family_tree)
        data = {
            "message": "Family Tree Deleted !",
            "status": 200,
            "data": result
        }
        
        return make_response(jsonify(data), data["status"])
