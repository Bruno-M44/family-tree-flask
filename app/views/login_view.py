import werkzeug.exceptions
from flask import jsonify, make_response, request, Blueprint
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required

from ..models import User


login_app = Blueprint("login_app", __name__)


@login_app.route("/login", methods=["POST"], endpoint="login")
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


@login_app.route("/refresh", methods=["POST"], endpoint="refresh")
@jwt_required()
def login():
    current_user = get_jwt_identity()

    result = create_access_token(identity=current_user)
    data = {
        "message": "Refresh Token !",
        "status": 200,
        "data": result
    }
    response = make_response(jsonify(data), data["status"])
    return response
