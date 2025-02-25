import werkzeug.exceptions
from flask import jsonify, make_response, request, Blueprint
from flask_jwt_extended import jwt_required

from ..models import FamilyTree, FamilyTreeCell, Picture, association_parent_child, association_couple
from ..schemas import family_tree_cell_schema, picture_schema
from .verify_user_authorized import VerifyUserAuthorized
from app import db
from sqlalchemy import or_


family_tree_cell_app = Blueprint("family_tree_cell_app", __name__)


@family_tree_cell_app.route(
    "/family_trees/<int:id_family_tree>/family_tree_cells",
    methods=["GET"],
    endpoint="get_family_tree_cells"
)
@jwt_required()
@VerifyUserAuthorized
def get_family_tree_cells(id_family_tree: int):
    family_tree_cells = FamilyTreeCell.query.filter_by(id_family_tree=id_family_tree).all()
    result = []

    for family_tree_cell in family_tree_cells:
        family_tree_cell_result = family_tree_cell_schema.dump(family_tree_cell)
        family_tree_cell_result["children"] = get_children(family_tree_cell=family_tree_cell)
        family_tree_cell_result["couples"] = get_couples(family_tree_cell=family_tree_cell)
        result.append(family_tree_cell_result)

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
    family_tree = FamilyTree.query.get(id_family_tree)
    new_family_tree_cell = FamilyTreeCell(
        name=request.json.get("name"),
        surnames=request.json.get("surnames"),
        birthday=request.json.get("birthday"),
        deathday=request.json.get("deathday"),
        jobs=request.json.get("jobs"),
        comments=request.json.get("comments"),
        generation=request.json.get("generation")
    )
    for child in request.json.get("children"):
        new_family_tree_cell.parent.append(FamilyTreeCell.query.get(child))

    for parent in request.json.get("parents"):
        family_tree_cell_parent = FamilyTreeCell.query.get(parent)
        family_tree_cell_parent.parent.append(new_family_tree_cell)

    family_tree.family_tree_cells.append(new_family_tree_cell)

    db.session.commit()

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


def get_children(family_tree_cell: FamilyTreeCell) -> list:
    children = db.session.query(
        association_parent_child).filter(
        association_parent_child.c.id_family_tree_cell_parent == family_tree_cell.id_family_tree_cell
    ).all()

    return [
        family_tree_cell_schema.dump(
            FamilyTreeCell.query.filter_by(id_family_tree_cell=child.id_family_tree_cell_child).first_or_404())
        for child in children
    ]


def get_couples(family_tree_cell: FamilyTreeCell) -> list:
    couples = db.session.query(association_couple).filter(or_(
        association_couple.c.id_family_tree_cell_couple_1 == family_tree_cell.id_family_tree_cell,
        association_couple.c.id_family_tree_cell_couple_2 == family_tree_cell.id_family_tree_cell
    )).all()
    print("couples :", couples)
    couples = [
        {
            "id_couple": couple[0],
            "start_union": couple[2],
            "end_union": couple[3]
        } if couple[0] != family_tree_cell.id_family_tree_cell else {
            "id_couple": couple[1],
            "start_union": couple[2],
            "end_union": couple[3]
        } for couple in couples
    ]
    return [
        family_tree_cell_schema.dump(
            FamilyTreeCell.query.filter_by(id_family_tree_cell=couple["id_couple"]).first_or_404()
        ) | {"start_union": couple["start_union"], "end_union": couple["end_union"]}

        for couple in couples
    ]
