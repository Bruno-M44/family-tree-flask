import os
import werkzeug.exceptions
from flask import jsonify, make_response, request, Blueprint, send_from_directory
from flask_jwt_extended import jwt_required

from ..models import FamilyTreeCell, Picture
from ..schemas import pictures_schema, picture_schema
from .verify_user_authorized import VerifyUserAuthorized
from app import db
from werkzeug.utils import secure_filename
import uuid

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

picture_app = Blueprint("picture_app", __name__)


@picture_app.route("/family_tree_cells/<int:id_family_tree_cell>/pictures", methods=["GET"], endpoint="get_pictures")
@jwt_required()
@VerifyUserAuthorized
def get_pictures(id_family_tree_cell: int):
    all_pictures = Picture.query.filter_by(id_family_tree_cell=id_family_tree_cell).all()
    result = pictures_schema.dump(all_pictures)
    data = {
        "message": "All Pictures !",
        "status": 200,
        "data": result
    }
    return make_response(jsonify(data), data["status"])


# @picture_app.route("/family_tree_cells/<int:id_family_tree_cell>/pictures", methods=["POST"], endpoint="create_picture")
# @jwt_required()
# @VerifyUserAuthorized
# def create_picture(id_family_tree_cell: int):
#     family_tree_cell = FamilyTreeCell.query.get(id_family_tree_cell)
#     new_picture = Picture(
#         picture_date=request.json.get("picture_date"),
#         comments=request.json.get("comments")
#     )
#     family_tree_cell.pictures.append(new_picture)
#     db.session.commit()

#     result = picture_schema.dump(new_picture)
#     data = {
#         "message": "Picture Created !",
#         "status": 201,
#         "data": result
#     }
#     return make_response(jsonify(data), data["status"])


@picture_app.route(
    "/family_trees/<int:id_family_tree>/family_tree_cells/<int:id_family_tree_cell>/pictures/<int:id_picture>",
    methods=["GET", "PUT"],
    endpoint="get_update_picture"
)
@jwt_required()
@VerifyUserAuthorized
def get_update_delete_picture(id_family_tree: int, id_family_tree_cell: int, id_picture: int):
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
            setattr(picture, key, value)

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

@picture_app.route(
    "/family_trees/<int:id_family_tree>/family_tree_cells/<int:id_family_tree_cell>/pictures/<int:id_picture>/download",
    methods=["GET"],
    endpoint="download_picture"
)
@jwt_required()
@VerifyUserAuthorized
def download_picture(id_family_tree: int, id_family_tree_cell: int, id_picture: int):
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

        return send_from_directory(
            directory=f"/pictures/{id_family_tree}/{id_family_tree_cell}",
            path=result["filename"],
            as_attachment=True
            )

@picture_app.route(
    "/family_trees/<int:id_family_tree>/family_tree_cells/<int:id_family_tree_cell>/pictures/<int:id_picture>/delete",
    methods=["DELETE"],
    endpoint="delete_picture"
)
@jwt_required()
@VerifyUserAuthorized
def delete_picture(id_family_tree: int, id_family_tree_cell: int, id_picture: int):
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

    if request.method == "DELETE":
        os.remove(f"/pictures/{id_family_tree}/{id_family_tree_cell}/{picture.filename}")
        db.session.delete(picture)
        db.session.commit()
        result = picture_schema.dump(picture)
        data = {
            "message": "Picture Deleted !",
            "status": 200,
            "data": result
        }
        return make_response(jsonify(data), data["status"])

@picture_app.route("/family_trees/<int:id_family_tree>/family_tree_cells/<int:id_family_tree_cell>/pictures", methods=["POST"], endpoint="upload_picture")
@jwt_required()
@VerifyUserAuthorized
def upload_picture(id_family_tree: int, id_family_tree_cell: int):
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    # current_app.logger.info("---allowed_file(file.filename): %s", allowed_file(file.filename))
    if file and allowed_file(file.filename):
    # Générer un nom de fichier unique
        filename = str(uuid.uuid4()) + '.' + file.filename.rsplit('.', 1)[1].lower()
        filename = secure_filename(filename)
        
        os.makedirs(f"/pictures/{id_family_tree}/{id_family_tree_cell}", exist_ok=True)
        file.save(f"/pictures/{id_family_tree}/{id_family_tree_cell}/{filename}")
        
        family_tree_cell = FamilyTreeCell.query.get(id_family_tree_cell)     
        new_picture = Picture(
            filename=filename,
            picture_date=request.form["picture_date"],
            comments=request.form["comments"],
            header_picture=request.form["header_picture"]
        )
        family_tree_cell.pictures.append(new_picture)
        db.session.commit()
        result = picture_schema.dump(new_picture)
        
    else:
        return jsonify({"error": "File not allowed"}), 400
             
    data = {
    "message": "Picture Created !",
    "status": 201,
    "data": result
    }
    return make_response(jsonify(data), data["status"])

def allowed_file(filename: str):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS