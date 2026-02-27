#! /usr/bin/env python
'''Endpoint restitution for pet picture'''
import os
import uuid
import logging
import werkzeug.exceptions
from flask import jsonify, make_response, request, Blueprint, send_from_directory
from flask_jwt_extended import jwt_required
from werkzeug.utils import secure_filename
from app import db
from ..models import Pet, PetPicture, FamilyTreeCell
from ..schemas import pet_picture_schema, pets_pictures_schema
from .verify_user_authorized import VerifyUserAuthorized



ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

pet_picture_app = Blueprint("pet_picture_app", __name__)
logger = logging.getLogger(__name__)


@pet_picture_app.route(
    "/pets/<int:id_pet>/pets_pictures",
    methods=["GET"],
    endpoint="get_pets_pictures"
    )
@jwt_required()
@VerifyUserAuthorized
def get_pets_pictures(id_pet: int):
    '''get_pets_pictures endpoint'''
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
def get_update_delete_pet(id_pet: int, id_pet_picture: int):
    '''get_update_delete_pet_picture endpoint'''
    try:
        pet_picture = PetPicture.query.filter_by(
            id_pet=id_pet,
            id_pet_picture=id_pet_picture).first_or_404()
    except werkzeug.exceptions.NotFound:
        data = {
            "message": "Bad pet or pet picture",
            "status": 404,
        }
        return make_response(jsonify(data), data["status"])

    if request.method == "GET":
        result = pet_picture_schema.dump(pet_picture)
        data = {
            "message": "Pet Picture Info !",
            "status": 200,
            "data": result
        }
        return make_response(jsonify(data), data["status"])

    if request.method == "PUT":
        for key, value in request.get_json().items():
            setattr(pet_picture, key, value)

        db.session.commit()
        result = pet_picture_schema.dump(pet_picture)
        data = {
            "message": "Pet Picture Modified !",
            "status": 204,
            "data": result
        }
        return make_response(jsonify(data), data["status"])

    if request.method == "DELETE":
        db.session.delete(pet_picture)
        db.session.commit()
        result = pet_picture_schema.dump(pet_picture)
        data = {
            "message": "Pet Picture Deleted !",
            "status": 200,
            "data": result
        }
        return make_response(jsonify(data), data["status"])

@pet_picture_app.route(
    (
        "/pets/<int:id_pet>/pets_pictures/<int:id_pet_picture>/download"
        ),
    methods=["GET"],
    endpoint="download_pet_picture"
)
@jwt_required()
@VerifyUserAuthorized
def download_pet_picture(
    id_pet: int,
    id_pet_picture: int
    ):
    '''download_pet_picture endpoint'''
    try:
        pet_picture = PetPicture.query.filter_by(
            id_pet=id_pet,
            id_pet_picture=id_pet_picture).first_or_404()
    except werkzeug.exceptions.NotFound:
        data = {
            "message": "Bad pet or pet picture",
            "status": 404,
        }
        return make_response(jsonify(data), data["status"])
    
    try:
        pet = Pet.query.filter_by(id_pet=id_pet).first_or_404()
        id_family_tree_cell = pet.id_family_tree_cell

    except werkzeug.exceptions.NotFound:
        data = {
            "message": "Bad pet",
            "status": 404,
        }
        return make_response(jsonify(data), data["status"])
    
    try:
        family_tree_cell = FamilyTreeCell.query.filter_by(id_family_tree_cell=id_family_tree_cell).first_or_404()
        id_family_tree = family_tree_cell.id_family_tree

    except werkzeug.exceptions.NotFound:
        data = {
            "message": "Bad pet",
            "status": 404,
        }
        return make_response(jsonify(data), data["status"])

    if request.method == "GET":
        result = pet_picture_schema.dump(pet_picture)

        return send_from_directory(
            directory=f"/pet_pictures/{id_family_tree}/{id_family_tree_cell}/{id_pet}",
            path=result["filename"],
            as_attachment=True
            )

@pet_picture_app.route(
    (
        "/pets/<int:id_pet>/pets_pictures/<int:id_pet_picture>/delete"
        ),
    methods=["DELETE"],
    endpoint="delete_pet_picture"
)
@jwt_required()
@VerifyUserAuthorized
def delete_pet_picture(id_pet: int, id_pet_picture: int):
    '''delete_pet_picture endpoint'''
    try:
        pet_picture = PetPicture.query.filter_by(
            id_pet=id_pet,
            id_pet_picture=id_pet_picture).first_or_404()
    except werkzeug.exceptions.NotFound:
        data = {
            "message": "Bad pet or pet picture",
            "status": 404,
        }
        return make_response(jsonify(data), data["status"])

    try:
        pet = Pet.query.filter_by(id_pet=id_pet).first_or_404()
        id_family_tree_cell = pet.id_family_tree_cell

    except werkzeug.exceptions.NotFound:
        data = {
            "message": "Bad pet",
            "status": 404,
        }
        return make_response(jsonify(data), data["status"])
    
    try:
        family_tree_cell = FamilyTreeCell.query.filter_by(id_family_tree_cell=id_family_tree_cell).first_or_404()
        id_family_tree = family_tree_cell.id_family_tree

    except werkzeug.exceptions.NotFound:
        data = {
            "message": "Bad pet",
            "status": 404,
        }
        return make_response(jsonify(data), data["status"])

    if request.method == "DELETE":
        os.remove(
            f"/pet_pictures/{id_family_tree}/{id_family_tree_cell}/{id_pet}/{pet_picture.filename}"
            )
        db.session.delete(pet_picture)
        db.session.commit()
        result = pet_picture_schema.dump(pet_picture)
        data = {
            "message": "Pet Picture Deleted !",
            "status": 200,
            "data": result
        }
        return make_response(jsonify(data), data["status"])

@pet_picture_app.route(
    ("/pets/<int:id_pet>/pets_pictures"),
    methods=["POST"],
    endpoint="upload_pet_picture"
    )
@jwt_required()
@VerifyUserAuthorized
def upload_pet_picture(id_pet: int):
    '''upload_pet_picture endpoint'''
    logger.debug("---request:")
    logger.debug(request)
    logger.debug("---request.files:")
    logger.debug(request.files)
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    try:
        pet = Pet.query.filter_by(id_pet=id_pet).first_or_404()
        id_family_tree_cell = pet.id_family_tree_cell

    except werkzeug.exceptions.NotFound:
        data = {
            "message": "Bad pet",
            "status": 404,
        }
        return make_response(jsonify(data), data["status"])
    
    try:
        family_tree_cell = FamilyTreeCell.query.filter_by(id_family_tree_cell=id_family_tree_cell).first_or_404()
        id_family_tree = family_tree_cell.id_family_tree

    except werkzeug.exceptions.NotFound:
        data = {
            "message": "Bad pet",
            "status": 404,
        }
        return make_response(jsonify(data), data["status"])

    if file and allowed_file(file.filename):
    # Générer un nom de fichier unique
        filename = str(uuid.uuid4()) + '.' + file.filename.rsplit('.', 1)[1].lower()
        filename = secure_filename(filename)
        os.makedirs(f"/pet_pictures/{id_family_tree}/{id_family_tree_cell}/{id_pet}", exist_ok=True)
        file.save(f"/pet_pictures/{id_family_tree}/{id_family_tree_cell}/{id_pet}/{filename}")

        pet = Pet.query.get(id_pet)
        new_pet_picture = PetPicture(
            filename=filename,
            picture_date=request.form["picture_date"],
            comments=request.form["comments"]
        )
        pet.pets_pictures.append(new_pet_picture)
        db.session.commit()
        result = pet_picture_schema.dump(new_pet_picture)

    else:
        return jsonify({"error": "File not allowed"}), 400

    data = {
    "message": "Pet Picture Created !",
    "status": 201,
    "data": result
    }
    return make_response(jsonify(data), data["status"])

def allowed_file(filename: str):
    '''Check if filename extensions are allowed'''
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
