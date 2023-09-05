import werkzeug.exceptions
from flask import jsonify, make_response, request
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity

from ..models import User, FamilyTree, association_user_ft, FamilyTreeCell, Picture
from ..schemas import user_schema, family_tree_schema

from run import app
from app import db


jwt = JWTManager(app)


@app.route("/login", methods=["POST"], endpoint="login")
def login():
    email_ = request.json.get("email")
    password_ = request.json.get("password")
    try:
        id_user = User.query.filter_by(email=email_, password=password_).first_or_404().id_user
    except werkzeug.exceptions.NotFound:
        data = {
            "message": "Bad username or password",
            "status": 404,
        }
        return make_response(jsonify(data), data["status"])
    else:
        result = create_access_token(identity=id_user)
        data = {
            "message": "Token !",
            "status": 200,
            "data": result
        }
        response = make_response(jsonify(data), data["status"])
        return response


@app.route("/user", methods=["GET"], endpoint="get_user")
@jwt_required()
def get_user():
    current_user = get_jwt_identity()
    user = User.query.get(current_user)
    result = user_schema.dump(user)
    family_trees = FamilyTree.query.join(association_user_ft).filter(
        association_user_ft.c.id_user == current_user).all()
    family_trees_result = []
    for family_tree in family_trees:
        family_tree = family_tree_schema.dump(family_tree)
        family_tree["permission"] = db.session.query(
            association_user_ft).filter(
            association_user_ft.c.id_family_tree == family_tree["id_family_tree"]
        ).first().permission
        family_trees_result.append(family_tree)
    result["family_trees"] = family_trees_result

    data = {
        "message": "User Info !",
        "status": 200,
        "data": result
    }
    return make_response(jsonify(data), data["status"])


@app.route("/user", methods=["POST"], endpoint="create_user")
def create_user():
    email_ = request.json.get("email")
    try:
        User.query.filter_by(email=email_).first_or_404()
    except werkzeug.exceptions.NotFound:
        new_user = User(
            name=request.json.get("name"),
            surname=request.json.get("surname"),
            email=email_,
            password=request.json.get("password")
        )
        db.session.add(new_user)
        db.session.commit()
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


@app.route("/user", methods=["PUT"], endpoint="update_user")
@jwt_required()
def update_user():
    current_user = get_jwt_identity()
    user = User.query.get(current_user)
    for key, value in request.get_json().items():
        user.__setattr__(key, value)

    db.session.commit()
    result = user_schema.dump(user)
    data = {
        "message": "User Modified !",
        "status": 204,
        "data": result
    }
    return make_response(jsonify(data), data["status"])


@app.route("/user", methods=["DELETE"], endpoint="delete_user")
@jwt_required()
def delete_user():
    current_user = get_jwt_identity()
    user = User.query.get(current_user)
    links_users_family_trees = db.session.query(association_user_ft).filter(
        association_user_ft.c.id_user == current_user).all()
    for id_family_tree in [link.id_family_tree for link in links_users_family_trees]:
        if len(db.session.query(association_user_ft).filter(
                association_user_ft.c.id_family_tree == id_family_tree).all()) == 1:

            pictures_to_delete = Picture.query.join(FamilyTreeCell).filter(
                Picture.id_family_tree_cell == FamilyTreeCell.id_family_tree_cell,
                FamilyTreeCell.id_family_tree == id_family_tree
            ).all()
            for picture in pictures_to_delete:
                db.session.delete(picture)
            FamilyTreeCell.query.filter_by(id_family_tree=id_family_tree).delete()
            FamilyTree.query.filter_by(id_family_tree=id_family_tree).delete()

    db.session.delete(user)
    db.session.commit()

    result = user_schema.dump(user)
    data = {
        "message": "User Deleted !",
        "status": 200,
        "data": result
    }
    return make_response(jsonify(data), data["status"])
