#! /usr/bin/env python
'''Endpoint restitution for pet'''
import werkzeug.exceptions
from flask import jsonify, make_response, request, Blueprint
from flask_jwt_extended import jwt_required
from app import db
from ..models import FamilyTreeCell, Pet
from ..schemas import pets_schema, pet_schema
from .verify_user_authorized import VerifyUserAuthorized

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

pet_app = Blueprint("pet_app", __name__)


@pet_app.route(
    "/family_tree_cells/<int:id_family_tree_cell>/pets",
    methods=["GET"],
    endpoint="get_pets"
    )
@jwt_required()
@VerifyUserAuthorized
def get_pets(id_family_tree_cell: int):
    '''get_pets endpoint'''
    all_pets = Pet.query.filter_by(id_family_tree_cell=id_family_tree_cell).all()
    result = pets_schema.dump(all_pets)
    data = {
        "message": "All Pets !",
        "status": 200,
        "data": result
    }
    return make_response(jsonify(data), data["status"])


@pet_app.route(
    "/family_tree_cells/<int:id_family_tree_cell>/pets",
    methods=["POST"],
    endpoint="create_pet"
    )
@jwt_required()
@VerifyUserAuthorized
def create_pet(id_family_tree_cell: int):
    '''create_pet endpoint'''
    family_tree_cell = FamilyTreeCell.query.get(id_family_tree_cell)
    new_pet = Pet(
        name=request.json.get("name"),
        species=request.json.get("species"),
        birthday=request.json.get("birthday"),
        deathday=request.json.get("deathday"),
        comments=request.json.get("comments")
    )
    family_tree_cell.pets.append(new_pet)
    db.session.commit()

    result = pet_schema.dump(new_pet)
    data = {
        "message": "Pet Created !",
        "status": 201,
        "data": result
    }
    return make_response(jsonify(data), data["status"])


@pet_app.route(
    "/family_tree_cells/<int:id_family_tree_cell>/pets/<int:id_pet>",
    methods=["GET", "PUT", "DELETE"],
    endpoint="get_update_delete_pet"
)
@jwt_required()
@VerifyUserAuthorized
def get_update_delete_pet(id_family_tree_cell: int, id_pet: int):
    '''get_update_delete_pet endpoint'''
    try:
        pet = Pet.query.filter_by(
            id_family_tree_cell=id_family_tree_cell,
            id_pet=id_pet).first_or_404()
    except werkzeug.exceptions.NotFound:
        data = {
            "message": "Bad family tree cell cell or pet",
            "status": 404,
        }
        return make_response(jsonify(data), data["status"])

    if request.method == "GET":
        result = pet_schema.dump(pet)
        data = {
            "message": "Pet Info !",
            "status": 200,
            "data": result
        }

        return make_response(jsonify(data), data["status"])

    if request.method == "PUT":
        for key, value in request.get_json().items():
            setattr(pet, key, value)

        db.session.commit()
        result = pet_schema.dump(pet)
        data = {
            "message": "Pet Modified !",
            "status": 204,
            "data": result
        }
        return make_response(jsonify(data), data["status"])

    if request.method == "DELETE":
        db.session.delete(pet)
        db.session.commit()
        result = pet_schema.dump(pet)
        data = {
            "message": "Pet Deleted !",
            "status": 200,
            "data": result
        }
        return make_response(jsonify(data), data["status"])

    return None
