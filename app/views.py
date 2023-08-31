import werkzeug.exceptions
from flask import render_template, jsonify, make_response, request
from flask_jwt_extended import JWTManager, create_access_token, jwt_required

from .models import User, FamilyTree, association_user_ft, FamilyTreeCell, Picture
from .schemas import (users_schema, user_schema, family_trees_schema, family_tree_schema, family_trees_cells_schema,
                      family_tree_cell_schema, pictures_schema, picture_schema)
from . import models
from run import app
from app import db


jwt = JWTManager(app)


@app.route("/login", methods=["POST"])
def login():
    email_ = request.json.get("email")
    password_ = request.json.get("password")
    try:
        User.query.filter_by(email=email_, password=password_).first_or_404()
    except werkzeug.exceptions.NotFound:
        data = {
            "message": "Bad username or password",
            "status": 404,
        }
        return make_response(jsonify(data), data["status"])
    else:
        result = create_access_token(identity=email_)
        data = {
            "message": "Token !",
            "status": 200,
            "data": result
        }
        response = make_response(jsonify(data), data["status"])
        return response


@app.route('/')
def index():
    users = User.query.all()
    return render_template("index.html",
                           user_name=users)


@app.route("/users", methods=["GET"])
@jwt_required()
def get_users():
    all_users = User.query.all()
    result = users_schema.dump(all_users)
    data = {
        "message": "All Users !",
        "status": 200,
        "data": result
    }
    return make_response(jsonify(data), data["status"])


@app.route("/users/<int:id_user>", methods=["GET"])
@jwt_required()
def get_user(id_user):
    user = User.query.get(id_user)
    result = user_schema.dump(user)
    family_trees = FamilyTree.query.join(association_user_ft).filter(association_user_ft.c.id_user == id_user).all()
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


@app.route("/users/<int:id_user>/family_trees", methods=["GET"])
@jwt_required()
def get_family_trees(id_user):
    all_family_trees = FamilyTree.query.join(association_user_ft).filter(association_user_ft.c.id_user == id_user).all()
    result = family_trees_schema.dump(all_family_trees)
    data = {
        "message": "All Family Trees !",
        "status": 200,
        "data": result
    }
    return make_response(jsonify(data), data["status"])


@app.route("/users/<int:id_user>/family_trees/<int:id_family_tree>", methods=["GET"])
@jwt_required()
def get_family_tree(id_user, id_family_tree):
    family_tree = FamilyTree.query.join(association_user_ft).filter(
        association_user_ft.c.id_user == id_user,
        FamilyTree.id_family_tree == id_family_tree).first()

    result = family_tree_schema.dump(family_tree)
    data = {
        "message": "Family Tree Info !",
        "status": 200,
        "data": result
    }
    return make_response(jsonify(data), data["status"])


@app.route("/family_trees/<int:id_family_tree>/family_tree_cells", methods=["GET"])
@jwt_required()
def get_family_tree_cells(id_family_tree):
    all_family_tree_cells = FamilyTreeCell.query.filter(id_family_tree == id_family_tree).all()
    result = family_trees_cells_schema.dump(all_family_tree_cells)
    data = {
        "message": "All Family Tree Cells !",
        "status": 200,
        "data": result
    }
    return make_response(jsonify(data), data["status"])


@app.route("/family_trees/<int:id_family_tree>/family_tree_cells/<int:id_family_tree_cell>", methods=["GET"])
@jwt_required()
def get_family_tree_cell(id_family_tree, id_family_tree_cell):
    family_tree_cell = FamilyTreeCell.query.filter(
        id_family_tree == id_family_tree,
        id_family_tree_cell == id_family_tree_cell).first()
    result = family_tree_cell_schema.dump(family_tree_cell)
    data = {
        "message": "Family Tree Cell Info !",
        "status": 200,
        "data": result
    }
    return make_response(jsonify(data), data["status"])


@app.route("/family_tree_cells/<int:id_family_tree_cell>/pictures", methods=["GET"])
@jwt_required()
def get_pictures(id_family_tree_cell):
    all_pictures = Picture.query.filter(id_family_tree_cell == id_family_tree_cell).all()
    result = pictures_schema.dump(all_pictures)
    data = {
        "message": "All Pictures !",
        "status": 200,
        "data": result
    }
    return make_response(jsonify(data), data["status"])


@app.route("/family_tree_cells/<int:id_family_tree_cell>/pictures/<int:id_picture>", methods=["GET"])
@jwt_required()
def get_picture(id_family_tree_cell, id_picture):
    picture = Picture.query.filter(
        id_family_tree_cell == id_family_tree_cell,
        id_picture == id_picture).first()
    result = picture_schema.dump(picture)
    data = {
        "message": "Picture Info !",
        "status": 200,
        "data": result
    }
    return make_response(jsonify(data), data["status"])


@app.cli.command()
def init_db():
    models.init_db()
