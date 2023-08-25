from flask import render_template, jsonify, make_response

from .models import User
from .schemas import users_schema
from . import models
from run import app


@app.route('/')
def index():
    users = User.query.all()
    return render_template("index.html",
                           user_name=users)


@app.route("/users", methods=["GET"])
def get_users():
    all_users = User.query.all()
    result = users_schema.dump(all_users)
    data = {
        "message": "All Users !",
        "status": 200,
        "data": result
    }
    return make_response(jsonify(data))


@app.cli.command()
def init_db():
    models.init_db()
