from flask import jsonify, make_response, request, Blueprint
from flask_jwt_extended import create_access_token, get_jwt, get_jwt_identity, jwt_required
from werkzeug.security import check_password_hash, generate_password_hash

from .. import db, limiter
from ..models import TokenBlocklist, User


login_app = Blueprint("login_app", __name__)

# Precomputed so a lookup of a non-existent email takes as long as a real one
# (avoids leaking account existence via response timing).
_DUMMY_PASSWORD_HASH = generate_password_hash("not-a-real-password")


@login_app.route("/login", methods=["POST"], endpoint="login")
@limiter.limit("10 per minute")
def login():
    body = request.get_json() or {}
    email_ = body.get("email")
    password_ = body.get("password")
    if not email_ or not password_:
        return make_response(jsonify({"message": "email and password are required", "status": 400}), 400)
    user = User.query.filter_by(email=email_).first()
    password_valid = check_password_hash(user.password if user else _DUMMY_PASSWORD_HASH, password_)
    if not user or not password_valid:
        return make_response(jsonify({"message": "Bad username or password", "status": 401}), 401)
    if not user.verified:
        return make_response(jsonify({"message": "Email not verified", "status": 403}), 403)
    result = create_access_token(identity=str(user.id_user))
    data = {
        "message": "Token !",
        "status": 200,
        "data": result
    }
    return make_response(jsonify(data), data["status"])


@login_app.route("/logout", methods=["DELETE"], endpoint="logout")
@jwt_required()
def logout():
    jti = get_jwt()["jti"]
    db.session.add(TokenBlocklist(jti=jti))
    db.session.commit()
    return make_response(jsonify({"message": "Logged out", "status": 200}), 200)


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
