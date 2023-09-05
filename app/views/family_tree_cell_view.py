import werkzeug.exceptions
from flask import jsonify, make_response, request
from flask_jwt_extended import JWTManager, jwt_required

from ..models import FamilyTree, FamilyTreeCell, Picture
from ..schemas import family_trees_cells_schema, family_tree_cell_schema, picture_schema
from .verify_user_authorized import VerifyUserAuthorized

from run import app
from app import db


jwt = JWTManager(app)


@app.route("/family_trees/<int:id_family_tree>/family_tree_cells", methods=["GET"], endpoint="get_family_tree_cells")
@jwt_required()
@VerifyUserAuthorized
def get_family_tree_cells(id_family_tree):
    all_family_tree_cells = FamilyTreeCell.query.filter_by(id_family_tree=id_family_tree).all()
    result = family_trees_cells_schema.dump(all_family_tree_cells)
    data = {
        "message": "All Family Tree Cells !",
        "status": 200,
        "data": result
    }
    return make_response(jsonify(data), data["status"])


@app.route("/family_trees/<int:id_family_tree>/family_tree_cells", methods=["POST"], endpoint="create_family_tree_cell")
@jwt_required()
@VerifyUserAuthorized
def create_family_tree_cell(id_family_tree):
    family_tree = FamilyTree.query.get(id_family_tree)
    new_family_tree_cell = FamilyTreeCell(
        name=request.json.get("name"),
        surnames=request.json.get("surnames"),
        birthday=request.json.get("birthday"),
        jobs=request.json.get("jobs"),
        comments=request.json.get("comments")
    )
    family_tree.family_tree_cells.append(new_family_tree_cell)
    db.session.commit()

    result = family_tree_cell_schema.dump(new_family_tree_cell)
    data = {
        "message": "Family Tree Cell Created !",
        "status": 201,
        "data": result
    }
    return make_response(jsonify(data), data["status"])


@app.route("/family_trees/<int:id_family_tree>/family_tree_cells/<int:id_family_tree_cell>",
           methods=["GET", "PUT", "DELETE"],
           endpoint="get_update_delete_family_tree_cell")
@jwt_required()
@VerifyUserAuthorized
def get_update_delete_family_tree_cell(id_family_tree, id_family_tree_cell):
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
        data = {
            "message": "Family Tree Cell Info !",
            "status": 200,
            "data": result
        }
        return make_response(jsonify(data), data["status"])

    if request.method == "PUT":
        for key, value in request.get_json().items():
            family_tree_cell.__setattr__(key, value)

        db.session.commit()
        result = family_tree_cell_schema.dump(family_tree_cell)
        data = {
            "message": "Family Tree Cell Modified !",
            "status": 204,
            "data": result
        }
        return make_response(jsonify(data), data["status"])

    if request.method == "DELETE":
        Picture.query.filter_by(id_family_tree_cell=id_family_tree_cell).delete()
        db.session.delete(family_tree_cell)
        db.session.commit()
        result = picture_schema.dump(family_tree_cell)
        data = {
            "message": "Family Tree Cell Deleted !",
            "status": 200,
            "data": result
        }
        return make_response(jsonify(data), data["status"])
