#! /usr/bin/env python
'''Endpoint restitution for pet'''
import werkzeug.exceptions
from datetime import datetime
from flask import jsonify, make_response, request, Blueprint
from flask_jwt_extended import jwt_required
from app import db
from ..models import FamilyTreeCell, Pet
from ..schemas import pets_schema, pet_schema
from .verify_user_authorized import VerifyUserAuthorized

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
    body = request.get_json() or {}
    required = ['name', 'species']
    missing = [f for f in required if not body.get(f)]
    if missing:
        return make_response(jsonify({"message": f"Missing fields: {', '.join(missing)}", "status": 400}), 400)

    try:
        new_pet = Pet(
            name=body['name'],
            species=body['species'],
            birthday=body.get('birthday'),
            deathday=body.get('deathday'),
            comments=body.get('comments')
        )
    except ValueError:
        return make_response(jsonify({"message": "Invalid date format, expected dd/mm/yyyy", "status": 400}), 400)

    family_tree_cell = db.session.get(FamilyTreeCell, id_family_tree_cell)
    family_tree_cell.pets.append(new_pet)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return make_response(jsonify({"message": "Database error", "status": 500}), 500)

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
        data = request.get_json() or {}
        if 'name' in data:
            pet.name = data['name']
        if 'species' in data:
            pet.species = data['species']
        if 'comments' in data:
            pet.comments = data['comments']
        try:
            if 'birthday' in data:
                pet.birthday = datetime.strptime(data['birthday'], "%d/%m/%Y") if data['birthday'] else None
            if 'deathday' in data:
                pet.deathday = datetime.strptime(data['deathday'], "%d/%m/%Y") if data['deathday'] else None
        except ValueError:
            return make_response(jsonify({"message": "Invalid date format, expected dd/mm/yyyy", "status": 400}), 400)

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            return make_response(jsonify({"message": "Database error", "status": 500}), 500)
        result = pet_schema.dump(pet)
        data = {
            "message": "Pet Modified !",
            "status": 200,
            "data": result
        }
        return make_response(jsonify(data), data["status"])

    if request.method == "DELETE":
        db.session.delete(pet)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            return make_response(jsonify({"message": "Database error", "status": 500}), 500)
        result = pet_schema.dump(pet)
        data = {
            "message": "Pet Deleted !",
            "status": 200,
            "data": result
        }
        return make_response(jsonify(data), data["status"])

    return None
