import os
import uuid
import werkzeug.exceptions
from datetime import datetime
from flask import jsonify, make_response, request, Blueprint, send_from_directory, send_file
from flask_jwt_extended import jwt_required
from werkzeug.utils import secure_filename

from ..models import FamilyTreeCell, Picture
from ..schemas import pictures_schema, picture_schema
from .verify_user_authorized import VerifyUserAuthorized
from .utils import allowed_file
from app import db


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


@picture_app.route(
    "/family_trees/<int:id_family_tree>/family_tree_cells/<int:id_family_tree_cell>/pictures/<int:id_picture>",
    methods=["GET", "PUT"],
    endpoint="get_update_picture"
)
@jwt_required()
@VerifyUserAuthorized
def get_update_picture(id_family_tree: int, id_family_tree_cell: int, id_picture: int):
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
        data = request.get_json() or {}
        if 'comments' in data:
            picture.comments = data['comments']
        if 'header_picture' in data:
            picture.header_picture = bool(data['header_picture'])
        try:
            if 'picture_date' in data:
                picture.picture_date = datetime.strptime(data['picture_date'], "%d/%m/%Y") if data['picture_date'] else None
        except ValueError:
            return make_response(jsonify({"message": "Invalid date format, expected dd/mm/yyyy", "status": 400}), 400)

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            return make_response(jsonify({"message": "Database error", "status": 500}), 500)
        result = picture_schema.dump(picture)
        data = {
            "message": "Picture Modified !",
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

    result = picture_schema.dump(picture)
    return send_from_directory(
        directory=f"/pictures/{id_family_tree}/{id_family_tree_cell}",
        path=result["filename"],
        as_attachment=False
    )


@picture_app.route(
    "/family_trees/<int:id_family_tree>/family_tree_cells/<int:id_family_tree_cell>/pictures/<int:id_picture>/secure",
    methods=["GET"]
)
@jwt_required()
@VerifyUserAuthorized
def secure_picture(id_family_tree, id_family_tree_cell, id_picture):
    picture = Picture.query.filter_by(
        id_family_tree_cell=id_family_tree_cell,
        id_picture=id_picture
    ).first_or_404()

    filepath = f"/pictures/{id_family_tree}/{id_family_tree_cell}/{picture.filename}"
    return send_file(filepath, mimetype="image/jpeg")


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

    try:
        os.remove(f"/pictures/{id_family_tree}/{id_family_tree_cell}/{picture.filename}")
    except FileNotFoundError:
        pass
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
    "/family_trees/<int:id_family_tree>/family_tree_cells/<int:id_family_tree_cell>/pictures",
    methods=["POST"],
    endpoint="upload_picture"
)
@jwt_required()
@VerifyUserAuthorized
def upload_picture(id_family_tree: int, id_family_tree_cell: int):
    if 'file' not in request.files:
        return make_response(jsonify({"message": "No file part", "status": 400}), 400)

    file = request.files['file']

    if file.filename == '':
        return make_response(jsonify({"message": "No selected file", "status": 400}), 400)

    if not (file and allowed_file(file.filename)):
        return make_response(jsonify({"message": "File not allowed", "status": 400}), 400)

    required_fields = ['picture_date', 'comments', 'header_picture']
    missing = [f for f in required_fields if f not in request.form]
    if missing:
        return make_response(jsonify({"message": f"Missing fields: {', '.join(missing)}", "status": 400}), 400)

    filename = secure_filename(str(uuid.uuid4()) + '.' + file.filename.rsplit('.', 1)[1].lower())
    os.makedirs(f"/pictures/{id_family_tree}/{id_family_tree_cell}", exist_ok=True)
    file.save(f"/pictures/{id_family_tree}/{id_family_tree_cell}/{filename}")

    family_tree_cell = db.session.get(FamilyTreeCell, id_family_tree_cell)
    new_picture = Picture(
        filename=filename,
        picture_date=request.form["picture_date"],
        comments=request.form["comments"],
        header_picture=request.form["header_picture"]
    )
    family_tree_cell.pictures.append(new_picture)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return make_response(jsonify({"message": "Database error", "status": 500}), 500)
    result = picture_schema.dump(new_picture)

    data = {
        "message": "Picture Created !",
        "status": 201,
        "data": result
    }
    return make_response(jsonify(data), data["status"])
