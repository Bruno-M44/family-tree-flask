import werkzeug.exceptions
from flask import jsonify, make_response, request, Blueprint
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func, select

from werkzeug.security import generate_password_hash
from ..models import User, FamilyTree, association_user_ft, FamilyTreeCell, Picture
from ..schemas import user_schema, family_tree_schema
from ..demo.creator import create_demo_family_tree
from app import db


user_app = Blueprint("user_app", __name__)


@user_app.route("/user", methods=["GET"], endpoint="get_user")
@jwt_required()
def get_user():
    current_user = int(get_jwt_identity())
    user = db.session.get(User, current_user)
    result = user_schema.dump(user)

    rows = db.session.query(FamilyTree, association_user_ft.c.permission).join(
        association_user_ft,
        FamilyTree.id_family_tree == association_user_ft.c.id_family_tree
    ).filter(association_user_ft.c.id_user == current_user).all()

    family_trees_result = []
    for family_tree, permission in rows:
        ft = family_tree_schema.dump(family_tree)
        ft["permission"] = permission
        family_trees_result.append(ft)
    result["family_trees"] = family_trees_result

    data = {
        "message": "User Info !",
        "status": 200,
        "data": result
    }
    return make_response(jsonify(data), data["status"])


@user_app.route("/user", methods=["POST"], endpoint="create_user")
def create_user():
    body = request.get_json() or {}
    required = ['name', 'surname', 'email', 'password']
    missing = [f for f in required if not body.get(f)]
    if missing:
        return make_response(jsonify({"message": f"Missing fields: {', '.join(missing)}", "status": 400}), 400)

    email_ = body['email']
    try:
        User.query.filter_by(email=email_).first_or_404()
    except werkzeug.exceptions.NotFound:
        new_user = User(
            name=body['name'],
            surname=body['surname'],
            email=email_,
            password=body['password']
        )
        db.session.add(new_user)
        db.session.flush()
        create_demo_family_tree(new_user)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            return make_response(jsonify({"message": "Database error", "status": 500}), 500)
        result = user_schema.dump(new_user)
        data = {
            "message": "User Created !",
            "status": 201,
            "data": result
        }
        return make_response(jsonify(data), data["status"])
    else:
        data = {
            "message": "User already exists !",
            "status": 403,
        }
        return make_response(jsonify(data), data["status"])


@user_app.route("/user", methods=["PUT"], endpoint="update_user")
@jwt_required()
def update_user():
    current_user = int(get_jwt_identity())
    user = db.session.get(User, current_user)
    data = request.get_json() or {}
    if 'name' in data:
        user.name = data['name']
    if 'surname' in data:
        user.surname = data['surname']
    if 'email' in data:
        user.email = data['email']
    if 'password' in data:
        user.password = generate_password_hash(data['password'])

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return make_response(jsonify({"message": "Database error", "status": 500}), 500)
    result = user_schema.dump(user)
    data = {
        "message": "User Modified !",
        "status": 200,
        "data": result
    }
    return make_response(jsonify(data), data["status"])


@user_app.route("/user", methods=["DELETE"], endpoint="delete_user")
@jwt_required()
def delete_user():
    current_user = int(get_jwt_identity())
    user = db.session.get(User, current_user)

    # Fetch user count per family tree in one query
    user_ft_ids = select(association_user_ft.c.id_family_tree).where(
        association_user_ft.c.id_user == current_user
    )
    user_counts = dict(
        db.session.query(
            association_user_ft.c.id_family_tree,
            func.count(association_user_ft.c.id_user)
        ).filter(
            association_user_ft.c.id_family_tree.in_(user_ft_ids)
        ).group_by(association_user_ft.c.id_family_tree).all()
    )

    for id_family_tree, count in user_counts.items():
        if count == 1:
            Picture.query.filter(
                Picture.id_family_tree_cell.in_(
                    db.session.query(FamilyTreeCell.id_family_tree_cell).filter_by(id_family_tree=id_family_tree)
                )
            ).delete(synchronize_session=False)
            FamilyTreeCell.query.filter_by(id_family_tree=id_family_tree).delete()
            FamilyTree.query.filter_by(id_family_tree=id_family_tree).delete()

    db.session.delete(user)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return make_response(jsonify({"message": "Database error", "status": 500}), 500)

    result = user_schema.dump(user)
    data = {
        "message": "User Deleted !",
        "status": 200,
        "data": result
    }
    return make_response(jsonify(data), data["status"])
