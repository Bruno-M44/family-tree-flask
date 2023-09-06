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
    current_user = get_jwt_identity()
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
    current_user = get_jwt_identity()
    user = User.query.get(current_user)
    new_family_tree = FamilyTree(
        title=request.json.get("title"),
        family_name=request.json.get("family_name")
    )
    user.family_trees.append(new_family_tree)
    db.session.commit()

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
def get_update_delete_family_tree(id_family_tree):
    current_user = get_jwt_identity()
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
        family_tree = FamilyTree.query.get(id_family_tree)
        for key, value in request.get_json().items():
            family_tree.__setattr__(key, value)

        db.session.commit()
        result = family_tree_schema.dump(family_tree)
        data = {
            "message": "Family Tree Modified !",
            "status": 204,
            "data": result
        }
        return make_response(jsonify(data), data["status"])

    if request.method == "DELETE":
        pictures_to_delete = Picture.query.join(FamilyTreeCell).filter(
            Picture.id_family_tree_cell == FamilyTreeCell.id_family_tree_cell,
            FamilyTreeCell.id_family_tree == id_family_tree
        ).all()
        for picture in pictures_to_delete:
            db.session.delete(picture)
        FamilyTreeCell.query.filter_by(id_family_tree=id_family_tree).delete()
        db.session.delete(family_tree)
        db.session.commit()
        result = family_tree_schema.dump(family_tree)
        data = {
            "message": "Family Tree Deleted !",
            "status": 200,
            "data": result
        }
        return make_response(jsonify(data), data["status"])
