from flask import jsonify, make_response, request, Blueprint
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required
from werkzeug.security import check_password_hash

from ..models import User


login_app = Blueprint("login_app", __name__)


@login_app.route("/login", methods=["POST"], endpoint="login")
def login():
    body = request.get_json() or {}
    email_ = body.get("email")
    password_ = body.get("password")
    if not email_ or not password_:
        return make_response(jsonify({"message": "email and password are required", "status": 400}), 400)
    user = User.query.filter_by(email=email_).first()
    if not user or not check_password_hash(user.password, password_):
        data = {
            "message": "Bad username or password",
            "status": 401,
        }
        return make_response(jsonify(data), data["status"])
    result = create_access_token(identity=str(user.id_user))
    data = {
        "message": "Token !",
        "status": 200,
        "data": result
    }
    return make_response(jsonify(data), data["status"])


@login_app.route("/refresh", methods=["POST"], endpoint="refresh")
@jwt_required()
def refresh():
    current_user = get_jwt_identity()
    result = create_access_token(identity=current_user)
    data = {
        "message": "Refresh Token !",
        "status": 200,
        "data": result
    }
    return make_response(jsonify(data), data["status"])
