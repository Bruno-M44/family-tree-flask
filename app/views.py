import werkzeug.exceptions
from flask import jsonify, make_response, request
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity

from .models import User, FamilyTree, association_user_ft, FamilyTreeCell, Picture
from .schemas import (user_schema, family_trees_schema, family_tree_schema, family_trees_cells_schema,
                      family_tree_cell_schema, pictures_schema, picture_schema)
from . import models
from run import app
from app import db


jwt = JWTManager(app)


class VerifyUserAuthorized:
    def __init__(self, own_function):
        self.func = own_function

    def __call__(self, *args, **kwargs):
        current_user = get_jwt_identity()
        try:
            if not kwargs.get("id_family_tree"):
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
        else:
            return self.func(*args, **kwargs)


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


@app.route("/family_trees", methods=["GET"], endpoint="get_family_trees")
@jwt_required()
def get_family_trees():
    current_user = get_jwt_identity()
    all_family_trees = FamilyTree.query.join(association_user_ft).filter(
        association_user_ft.c.id_user == current_user).all()
    result = family_trees_schema.dump(all_family_trees)
    data = {
        "message": "All Family Trees !",
        "status": 200,
        "data": result
    }
    return make_response(jsonify(data), data["status"])


@app.route("/family_tree", methods=["POST"], endpoint="create_family_tree")
@jwt_required()
def create_family_tree():
    current_user = get_jwt_identity()
    user = User.query.get(current_user)
    new_family_tree = FamilyTree(
        title=request.json.get("title"),
        family_name=request.json.get("family_name")
    )
    user.family_trees.append(new_family_tree)
    db.session.commit()

    result = family_tree_schema.dump(new_family_tree)
    data = {
        "message": "Family Tree Created !",
        "status": 201,
        "data": result
    }
    return make_response(jsonify(data), data["status"])


@app.route("/family_trees/<int:id_family_tree>", methods=["GET", "PUT"], endpoint="get_update_family_tree")
@jwt_required()
def get_update_family_tree(id_family_tree):
    current_user = get_jwt_identity()
    try:
        family_tree = FamilyTree.query.join(association_user_ft).filter(
            association_user_ft.c.id_user == current_user,
            FamilyTree.id_family_tree == id_family_tree).first_or_404()
    except werkzeug.exceptions.NotFound:
        data = {
            "message": "Bad user or family tree",
            "status": 404,
        }
        return make_response(jsonify(data), data["status"])
    if request.method == "GET":
        result = family_tree_schema.dump(family_tree)
        data = {
            "message": "Family Tree Info !",
            "status": 200,
            "data": result
        }
        return make_response(jsonify(data), data["status"])
    if request.method == "PUT":
        family_tree = FamilyTree.query.get(id_family_tree)
        for key, value in request.get_json().items():
            family_tree.__setattr__(key, value)

        db.session.commit()
        result = family_tree_schema.dump(family_tree)
        data = {
            "message": "Family Tree Modified !",
            "status": 204,
            "data": result
        }
        return make_response(jsonify(data), data["status"])


@app.route("/family_trees/<int:id_family_tree>/family_tree_cells", methods=["GET"], endpoint="get_family_tree_cells")
@jwt_required()
@VerifyUserAuthorized
def get_family_tree_cells(id_family_tree):
    all_family_tree_cells = FamilyTreeCell.query.filter_by(id_family_tree=id_family_tree).all()
    result = family_trees_cells_schema.dump(all_family_tree_cells)
    data = {
        "message": "All Family Tree Cells !",
        "status": 200,
        "data": result
    }
    return make_response(jsonify(data), data["status"])


@app.route("/family_trees/<int:id_family_tree>/family_tree_cells", methods=["POST"], endpoint="create_family_tree_cell")
@jwt_required()
@VerifyUserAuthorized
def create_family_tree_cell(id_family_tree):
    family_tree = FamilyTree.query.get(id_family_tree)
    new_family_tree_cell = FamilyTreeCell(
        name=request.json.get("name"),
        surnames=request.json.get("surnames"),
        birthday=request.json.get("birthday"),
        jobs=request.json.get("jobs"),
        comments=request.json.get("comments")
    )
    family_tree.family_tree_cells.append(new_family_tree_cell)
    db.session.commit()

    result = family_tree_cell_schema.dump(new_family_tree_cell)
    data = {
        "message": "Family Tree Cell Created !",
        "status": 201,
        "data": result
    }
    return make_response(jsonify(data), data["status"])


@app.route("/family_trees/<int:id_family_tree>/family_tree_cells/<int:id_family_tree_cell>",
           methods=["GET", "PUT"],
           endpoint="get_update_family_tree_cell")
@jwt_required()
@VerifyUserAuthorized
def get_update_family_tree_cell(id_family_tree, id_family_tree_cell):
    try:
        family_tree_cell = FamilyTreeCell.query.filter_by(
            id_family_tree=id_family_tree,
            id_family_tree_cell=id_family_tree_cell).first_or_404()
    except werkzeug.exceptions.NotFound:
        data = {
            "message": "Bad family tree or family tree cell",
            "status": 404,
        }
        return make_response(jsonify(data), data["status"])

    if request.method == "GET":
        result = family_tree_cell_schema.dump(family_tree_cell)
        data = {
            "message": "Family Tree Cell Info !",
            "status": 200,
            "data": result
        }
        return make_response(jsonify(data), data["status"])

    if request.method == "PUT":
        family_tree_cell = FamilyTreeCell.query.get(id_family_tree_cell)
        for key, value in request.get_json().items():
            family_tree_cell.__setattr__(key, value)

        db.session.commit()
        result = family_tree_cell_schema.dump(family_tree_cell)
        data = {
            "message": "Family Tree Cell Modified !",
            "status": 204,
            "data": result
        }
        return make_response(jsonify(data), data["status"])


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
           methods=["GET", "PUT"],
           endpoint="get_update_picture")
@jwt_required()
@VerifyUserAuthorized
def get_update_picture(id_family_tree_cell, id_picture):
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
        picture = Picture.query.get(id_family_tree_cell)
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


@app.cli.command()
def init_db():
    models.init_db()
