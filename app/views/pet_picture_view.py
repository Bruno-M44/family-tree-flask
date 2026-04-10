#! /usr/bin/env python
'''Endpoint restitution for pet picture'''
import os
import uuid
import werkzeug.exceptions
from datetime import datetime
from flask import jsonify, make_response, request, Blueprint, send_from_directory
from flask_jwt_extended import jwt_required
from werkzeug.utils import secure_filename
from app import db
from ..models import Pet, PetPicture, FamilyTreeCell
from ..schemas import pet_picture_schema, pets_pictures_schema
from .verify_user_authorized import VerifyUserAuthorized
from .utils import allowed_file

pet_picture_app = Blueprint("pet_picture_app", __name__)


def _get_pet_path(id_pet: int):
    """Return (pet, id_family_tree_cell, id_family_tree) or a error response tuple."""
    pet = db.session.get(Pet, id_pet)
    if pet is None:
        return None, None, None, make_response(jsonify({"message": "Bad pet", "status": 404}), 404)
    family_tree_cell = db.session.get(FamilyTreeCell, pet.id_family_tree_cell)
    if family_tree_cell is None:
        return None, None, None, make_response(jsonify({"message": "Bad pet", "status": 404}), 404)
    return pet, pet.id_family_tree_cell, family_tree_cell.id_family_tree, None


@pet_picture_app.route(
    "/pets/<int:id_pet>/pets_pictures",
    methods=["GET"],
    endpoint="get_pets_pictures"
)
@jwt_required()
@VerifyUserAuthorized
def get_pets_pictures(id_pet: int):
    all_pets_pictures = PetPicture.query.filter_by(id_pet=id_pet).all()
    result = pets_pictures_schema.dump(all_pets_pictures)
    data = {
        "message": "All Pets Pictures !",
        "status": 200,
        "data": result
    }
    return make_response(jsonify(data), data["status"])


@pet_picture_app.route(
    "/pets/<int:id_pet>/pets_pictures/<int:id_pet_picture>",
    methods=["GET", "PUT", "DELETE"],
    endpoint="get_update_delete_pet_picture"
)
@jwt_required()
@VerifyUserAuthorized
def get_update_delete_pet_picture(id_pet: int, id_pet_picture: int):
    try:
        pet_picture = PetPicture.query.filter_by(
            id_pet=id_pet,
            id_pet_picture=id_pet_picture).first_or_404()
    except werkzeug.exceptions.NotFound:
        return make_response(jsonify({"message": "Bad pet or pet picture", "status": 404}), 404)

    if request.method == "GET":
        result = pet_picture_schema.dump(pet_picture)
        return make_response(jsonify({"message": "Pet Picture Info !", "status": 200, "data": result}), 200)

    if request.method == "PUT":
        data = request.get_json() or {}
        if 'comments' in data:
            pet_picture.comments = data['comments']
        try:
            if 'picture_date' in data:
                pet_picture.picture_date = datetime.strptime(data['picture_date'], "%d/%m/%Y") if data['picture_date'] else None
        except ValueError:
            return make_response(jsonify({"message": "Invalid date format, expected dd/mm/yyyy", "status": 400}), 400)

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            return make_response(jsonify({"message": "Database error", "status": 500}), 500)
        result = pet_picture_schema.dump(pet_picture)
        return make_response(jsonify({"message": "Pet Picture Modified !", "status": 200, "data": result}), 200)

    # DELETE
    db.session.delete(pet_picture)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return make_response(jsonify({"message": "Database error", "status": 500}), 500)
    result = pet_picture_schema.dump(pet_picture)
    return make_response(jsonify({"message": "Pet Picture Deleted !", "status": 200, "data": result}), 200)


@pet_picture_app.route(
    "/pets/<int:id_pet>/pets_pictures/<int:id_pet_picture>/download",
    methods=["GET"],
    endpoint="download_pet_picture"
)
@jwt_required()
@VerifyUserAuthorized
def download_pet_picture(id_pet: int, id_pet_picture: int):
    try:
        pet_picture = PetPicture.query.filter_by(
            id_pet=id_pet,
            id_pet_picture=id_pet_picture).first_or_404()
    except werkzeug.exceptions.NotFound:
        return make_response(jsonify({"message": "Bad pet or pet picture", "status": 404}), 404)

    _, id_family_tree_cell, id_family_tree, err = _get_pet_path(id_pet)
    if err:
        return err

    result = pet_picture_schema.dump(pet_picture)
    return send_from_directory(
        directory=f"/pet_pictures/{id_family_tree}/{id_family_tree_cell}/{id_pet}",
        path=result["filename"],
        as_attachment=True
    )


@pet_picture_app.route(
    "/pets/<int:id_pet>/pets_pictures/<int:id_pet_picture>/delete",
    methods=["DELETE"],
    endpoint="delete_pet_picture"
)
@jwt_required()
@VerifyUserAuthorized
def delete_pet_picture(id_pet: int, id_pet_picture: int):
    try:
        pet_picture = PetPicture.query.filter_by(
            id_pet=id_pet,
            id_pet_picture=id_pet_picture).first_or_404()
    except werkzeug.exceptions.NotFound:
        return make_response(jsonify({"message": "Bad pet or pet picture", "status": 404}), 404)

    _, id_family_tree_cell, id_family_tree, err = _get_pet_path(id_pet)
    if err:
        return err

    try:
        os.remove(f"/pet_pictures/{id_family_tree}/{id_family_tree_cell}/{id_pet}/{pet_picture.filename}")
    except FileNotFoundError:
        pass
    db.session.delete(pet_picture)
    db.session.commit()
    result = pet_picture_schema.dump(pet_picture)
    return make_response(jsonify({"message": "Pet Picture Deleted !", "status": 200, "data": result}), 200)


@pet_picture_app.route(
    "/pets/<int:id_pet>/pets_pictures",
    methods=["POST"],
    endpoint="upload_pet_picture"
)
@jwt_required()
@VerifyUserAuthorized
def upload_pet_picture(id_pet: int):
    if 'file' not in request.files:
        return make_response(jsonify({"message": "No file part", "status": 400}), 400)

    file = request.files['file']

    if file.filename == '':
        return make_response(jsonify({"message": "No selected file", "status": 400}), 400)

    if not allowed_file(file.filename):
        return make_response(jsonify({"message": "File not allowed", "status": 400}), 400)

    required_fields = ['picture_date', 'comments']
    missing = [f for f in required_fields if f not in request.form]
    if missing:
        return make_response(jsonify({"message": f"Missing fields: {', '.join(missing)}", "status": 400}), 400)

    pet, id_family_tree_cell, id_family_tree, err = _get_pet_path(id_pet)
    if err:
        return err

    filename = secure_filename(str(uuid.uuid4()) + '.' + file.filename.rsplit('.', 1)[1].lower())
    os.makedirs(f"/pet_pictures/{id_family_tree}/{id_family_tree_cell}/{id_pet}", exist_ok=True)
    file.save(f"/pet_pictures/{id_family_tree}/{id_family_tree_cell}/{id_pet}/{filename}")

    new_pet_picture = PetPicture(
        filename=filename,
        picture_date=request.form["picture_date"],
        comments=request.form["comments"]
    )
    pet.pets_pictures.append(new_pet_picture)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return make_response(jsonify({"message": "Database error", "status": 500}), 500)
    result = pet_picture_schema.dump(new_pet_picture)
    return make_response(jsonify({"message": "Pet Picture Created !", "status": 201, "data": result}), 201)
