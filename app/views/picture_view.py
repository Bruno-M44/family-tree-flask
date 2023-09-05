import werkzeug.exceptions
from flask import jsonify, make_response, request
from flask_jwt_extended import JWTManager, jwt_required

from ..models import FamilyTreeCell, Picture
from ..schemas import pictures_schema, picture_schema
from .verify_user_authorized import VerifyUserAuthorized

from run import app
from app import db


jwt = JWTManager(app)


@app.route("/family_tree_cells/<int:id_family_tree_cell>/pictures", methods=["GET"], endpoint="get_pictures")
@jwt_required()
@VerifyUserAuthorized
def get_pictures(id_family_tree_cell):
    all_pictures = Picture.query.filter_by(id_family_tree_cell=id_family_tree_cell).all()
    result = pictures_schema.dump(all_pictures)
    data = {
        "message": "All Pictures !",
        "status": 200,
        "data": result
    }
    return make_response(jsonify(data), data["status"])


@app.route("/family_tree_cells/<int:id_family_tree_cell>/pictures", methods=["POST"], endpoint="create_picture")
@jwt_required()
@VerifyUserAuthorized
def create_picture(id_family_tree_cell):
    family_tree_cell = FamilyTreeCell.query.get(id_family_tree_cell)
    new_picture = Picture(
        picture_date=request.json.get("picture_date"),
        comments=request.json.get("comments")
    )
    family_tree_cell.pictures.append(new_picture)
    db.session.commit()

    result = picture_schema.dump(new_picture)
    data = {
        "message": "Picture Created !",
        "status": 201,
        "data": result
    }
    return make_response(jsonify(data), data["status"])


@app.route("/family_tree_cells/<int:id_family_tree_cell>/pictures/<int:id_picture>",
           methods=["GET", "PUT", "DELETE"],
           endpoint="get_update_delete_picture")
@jwt_required()
@VerifyUserAuthorized
def get_update_delete_picture(id_family_tree_cell, id_picture):
    try:
        picture = Picture.query.filter_by(
            id_family_tree_cell=id_family_tree_cell,
            id_picture=id_picture).first_or_404()
    except werkzeug.exceptions.NotFound:
        data = {
            "message": "Bad family tree cell or picture",
            "status": 404,
        }
        return make_response(jsonify(data), data["status"])

    if request.method == "GET":
        result = picture_schema.dump(picture)
        data = {
            "message": "Picture Info !",
            "status": 200,
            "data": result
        }
        return make_response(jsonify(data), data["status"])

    if request.method == "PUT":
        for key, value in request.get_json().items():
            picture.__setattr__(key, value)

        db.session.commit()
        result = picture_schema.dump(picture)
        data = {
            "message": "Picture Modified !",
            "status": 204,
            "data": result
        }
        return make_response(jsonify(data), data["status"])

    if request.method == "DELETE":
        db.session.delete(picture)
        db.session.commit()
        result = picture_schema.dump(picture)
        data = {
            "message": "Picture Deleted !",
            "status": 200,
            "data": result
        }
        return make_response(jsonify(data), data["status"])
