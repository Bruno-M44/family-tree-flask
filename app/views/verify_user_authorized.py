import werkzeug.exceptions
from flask import jsonify, make_response
from flask_jwt_extended import get_jwt_identity

from ..models import association_user_ft, FamilyTreeCell, Pet
from app import db


class VerifyUserAuthorized:
    def __init__(self, own_function):
        self.func = own_function

    def __call__(self, *args, **kwargs):
        current_user = get_jwt_identity()
        try:
            if not kwargs.get("id_family_tree"):
                if not kwargs.get("id_family_tree_cell"):
                    id_family_tree_cell = Pet.query.filter_by(
                        id_pet=kwargs["id_pet"]
                    ).first_or_404().id_family_tree_cell
                    id_family_tree = FamilyTreeCell.query.filter_by(
                        id_family_tree_cell=id_family_tree_cell
                    ).first_or_404().id_family_tree
                else:
                    id_family_tree = FamilyTreeCell.query.filter_by(
                        id_family_tree_cell=kwargs["id_family_tree_cell"]
                    ).first_or_404().id_family_tree
            else:
                id_family_tree = kwargs["id_family_tree"]

            db.session.query(
                association_user_ft).filter(
                association_user_ft.c.id_user == current_user,
                association_user_ft.c.id_family_tree == id_family_tree
            ).first_or_404()
        except werkzeug.exceptions.NotFound:
            data = {
                "message": "User not authorized !",
                "status": 404,
            }
            return make_response(jsonify(data), data["status"])
        return self.func(*args, **kwargs)
