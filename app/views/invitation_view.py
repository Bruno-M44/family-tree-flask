from typing import Optional

from flask import Blueprint, Response, jsonify, make_response, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy.exc import SQLAlchemyError

from app import db, limiter
from ..email_service import send_platform_invitation_email
from ..models import User

invitation_app = Blueprint("invitation_app", __name__)


@invitation_app.route("/invitation", methods=["POST"], endpoint="send_invitation")
@jwt_required()
@limiter.limit("20 per hour")
def send_invitation() -> Response:
    body: dict = request.get_json() or {}
    email: Optional[str] = body.get("email")

    if not email:
        return make_response(jsonify({"message": "Missing email", "status": 400}), 400)

    if User.query.filter_by(email=email).first():
        return make_response(jsonify({"message": "Ce compte existe déjà."}), 200)

    inviter: User = db.session.get(User, int(get_jwt_identity()))
    inviter_name: str = f"{inviter.name} {inviter.surname}"

    send_platform_invitation_email(to_email=email, inviter_name=inviter_name)
    return make_response(jsonify({"message": "Invitation envoyée."}), 200)
