import werkzeug.exceptions
from flask import render_template, jsonify, make_response, request
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity

from .models import User
from .schemas import users_schema, user_schema
from . import models
from run import app


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
    data = {
        "message": "User Info !",
        "status": 200,
        "data": result
    }
    return make_response(jsonify(data), data["status"])


@app.cli.command()
def init_db():
    models.init_db()
