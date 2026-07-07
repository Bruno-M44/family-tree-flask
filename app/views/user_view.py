import io
import json
import os
import uuid
import zipfile
from typing import Optional
import werkzeug.exceptions
from flask import jsonify, make_response, request, Blueprint, Response, send_from_directory
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from sqlalchemy import func, select, insert, delete, update
from sqlalchemy.exc import SQLAlchemyError

from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from .utils import allowed_file
from ..models import User, FamilyTree, FamilyTreeInvitation, TokenBlocklist, association_user_ft, FamilyTreeCell, Picture, Pet, PetPicture, association_parent_child, association_couple
from ..schemas import user_schema, family_tree_schema
from ..demo.creator import create_demo_family_tree
from datetime import datetime, timedelta, timezone
from ..email_service import send_verification_email, send_member_added_email, send_member_invitation_email
from app import db, limiter


user_app = Blueprint("user_app", __name__)


@user_app.route("/verify", methods=["GET"], endpoint="verify_email")
def verify_email():
    token = request.args.get("token", "")
    if not token:
        return make_response(jsonify({"message": "Missing token", "status": 400}), 400)
    user = User.query.filter_by(verification_token=token).first()
    if not user:
        return make_response(jsonify({"message": "Invalid or expired token", "status": 404}), 404)
    expiry_cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=7)
    if user.verification_token_created_at and user.verification_token_created_at < expiry_cutoff:
        return make_response(jsonify({"message": "Invalid or expired token", "status": 404}), 404)
    user.verified = True
    user.verification_token = None
    user.verification_token_created_at = None
    try:
        db.session.commit()
    except SQLAlchemyError as err:
        db.session.rollback()
        return make_response(jsonify({"message": f"Database error: {err}", "status": 500}), 500)
    return make_response(jsonify({"message": "Email verified !", "status": 200}), 200)


@user_app.route("/user/export", methods=["GET"], endpoint="export_user_data")
@jwt_required()
def export_user_data():
    current_user = int(get_jwt_identity())
    user = db.session.get(User, current_user)

    family_trees_data = []
    rows = db.session.query(FamilyTree, association_user_ft.c.role).join(
        association_user_ft,
        FamilyTree.id_family_tree == association_user_ft.c.id_family_tree
    ).filter(association_user_ft.c.id_user == current_user).all()

    for family_tree, role in rows:
        cells_data = []
        cells = FamilyTreeCell.query.filter_by(id_family_tree=family_tree.id_family_tree).all()
        for cell in cells:
            pictures_data = [
                {
                    "filename": p.filename,
                    "picture_date": p.picture_date.strftime("%d/%m/%Y") if p.picture_date else None,
                    "comments": p.comments,
                    "header_picture": p.header_picture,
                }
                for p in cell.pictures
            ]
            pets_data = []
            for pet in cell.pets:
                pet_pictures_data = [
                    {
                        "filename": pp.filename,
                        "picture_date": pp.picture_date.strftime("%d/%m/%Y") if pp.picture_date else None,
                        "comments": pp.comments,
                    }
                    for pp in pet.pets_pictures
                ]
                pets_data.append({
                    "name": pet.name,
                    "species": pet.species,
                    "birthday": pet.birthday.strftime("%d/%m/%Y") if pet.birthday else None,
                    "deathday": pet.deathday.strftime("%d/%m/%Y") if pet.deathday else None,
                    "comments": pet.comments,
                    "pictures": pet_pictures_data,
                })
            cells_data.append({
                "name": cell.name,
                "surnames": cell.surnames,
                "birthday": cell.birthday.strftime("%d/%m/%Y") if cell.birthday else None,
                "deathday": cell.deathday.strftime("%d/%m/%Y") if cell.deathday else None,
                "jobs": cell.jobs,
                "comments": cell.comments,
                "generation": cell.generation,
                "pictures": pictures_data,
                "pets": pets_data,
            })
        family_trees_data.append({
            "title": family_tree.title,
            "family_name": family_tree.family_name,
            "role": role,
            "members": cells_data,
        })

    export = {
        "account": {
            "name": user.name,
            "surname": user.surname,
            "email": user.email,
        },
        "family_trees": family_trees_data,
    }

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("data.json", json.dumps(export, ensure_ascii=False, indent=2))

        for family_tree, _ in rows:
            ft_id = family_tree.id_family_tree
            cells = FamilyTreeCell.query.filter_by(id_family_tree=ft_id).all()
            for cell in cells:
                for pic in cell.pictures:
                    src = f"/pictures/{ft_id}/{cell.id_family_tree_cell}/{pic.filename}"
                    if os.path.isfile(src):
                        zf.write(src, f"pictures/{ft_id}/{cell.id_family_tree_cell}/{pic.filename}")
                for pet in cell.pets:
                    for pet_pic in pet.pets_pictures:
                        src = f"/pet_pictures/{ft_id}/{cell.id_family_tree_cell}/{pet.id_pet}/{pet_pic.filename}"
                        if os.path.isfile(src):
                            zf.write(src, f"pet_pictures/{ft_id}/{cell.id_family_tree_cell}/{pet.id_pet}/{pet_pic.filename}")

    buf.seek(0)
    return Response(
        buf.getvalue(),
        status=200,
        mimetype="application/zip",
        headers={"Content-Disposition": "attachment; filename=my_data.zip"},
    )


@user_app.route("/user", methods=["GET"], endpoint="get_user")
@jwt_required()
def get_user():
    current_user = int(get_jwt_identity())
    user = db.session.get(User, current_user)
    result = user_schema.dump(user)

    rows = db.session.query(FamilyTree, association_user_ft.c.role).join(
        association_user_ft,
        FamilyTree.id_family_tree == association_user_ft.c.id_family_tree
    ).filter(association_user_ft.c.id_user == current_user).all()

    family_trees_result = []
    for family_tree, role in rows:
        ft = family_tree_schema.dump(family_tree)
        ft["role"] = role
        family_trees_result.append(ft)
    result["family_trees"] = family_trees_result

    data = {
        "message": "User Info !",
        "status": 200,
        "data": result
    }
    return make_response(jsonify(data), data["status"])


def _consume_invitations(user: User) -> None:
    """Add the new user to every family tree for which a pending invitation exists, then delete them."""
    expiry_cutoff: datetime = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=7)
    invitations: list = FamilyTreeInvitation.query.filter_by(email=user.email).all()
    for inv in invitations:
        if inv.created_at >= expiry_cutoff:
            db.session.execute(
                insert(association_user_ft).values(
                    id_user=user.id_user,
                    id_family_tree=inv.id_family_tree,
                    role=inv.role,
                )
            )
        db.session.delete(inv)


@user_app.route("/user", methods=["POST"], endpoint="create_user")
@limiter.limit("5 per hour")
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
        token = str(uuid.uuid4())
        new_user = User(
            name=body['name'],
            surname=body['surname'],
            email=email_,
            password=body['password']
        )
        new_user.verification_token = token
        new_user.verification_token_created_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.session.add(new_user)
        db.session.flush()
        create_demo_family_tree(new_user)
        _consume_invitations(new_user)
        try:
            db.session.commit()
        except SQLAlchemyError as err:
            db.session.rollback()
            return make_response(jsonify({"message": f"Database error: {err}", "status": 500}), 500)
        send_verification_email(email_, token)
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
@limiter.limit("10 per hour")
def update_user():
    current_user = int(get_jwt_identity())
    user = db.session.get(User, current_user)
    data = request.get_json() or {}
    if 'name' in data:
        user.name = data['name']
    if 'surname' in data:
        user.surname = data['surname']
    if 'email' in data and data['email'] != user.email:
        if User.query.filter_by(email=data['email']).first():
            return make_response(jsonify({"message": "Email already in use", "status": 409}), 409)
        user.email = data['email']
        user.verified = False
        user.verification_token = str(uuid.uuid4())
        user.verification_token_created_at = datetime.now(timezone.utc).replace(tzinfo=None)
        send_verification_email(user.email, user.verification_token)
    password_changed = False
    if 'password' in data:
        if not check_password_hash(user.password, data.get('current_password') or ''):
            return make_response(jsonify({"message": "Current password is incorrect", "status": 401}), 401)
        user.password = generate_password_hash(data['password'])
        password_changed = True

    try:
        db.session.commit()
    except SQLAlchemyError as err:
        db.session.rollback()
        return make_response(jsonify({"message": f"Database error: {err}", "status": 500}), 500)

    if password_changed:
        db.session.add(TokenBlocklist(jti=get_jwt()["jti"]))
        db.session.commit()

    result = user_schema.dump(user)
    data = {
        "message": "User Modified !",
        "status": 200,
        "data": result
    }
    return make_response(jsonify(data), data["status"])


@user_app.route(
    "/user/family-tree/<int:id_family_tree>/members",
    methods=["GET"],
    endpoint="get_family_tree_members",
)
@jwt_required()
def get_family_tree_members(id_family_tree: int) -> Response:
    """Return the list of members (id, name, surname, email, role) of a family tree."""
    current_user: int = int(get_jwt_identity())

    if _get_member_role(current_user, id_family_tree) is None:
        return make_response(jsonify({"message": "Not authorized", "status": 403}), 403)

    rows = db.session.query(User, association_user_ft.c.role).join(
        association_user_ft,
        User.id_user == association_user_ft.c.id_user,
    ).filter(
        association_user_ft.c.id_family_tree == id_family_tree
    ).all()

    members: list = [
        {
            "id_user": user.id_user,
            "name": user.name,
            "surname": user.surname,
            "email": user.email,
            "role": role,
        }
        for user, role in rows
    ]

    return make_response(jsonify({"message": "Members", "status": 200, "data": members}), 200)


VALID_ROLES: tuple = ("viewer", "editor")


def _get_member_role(id_user: int, id_family_tree: int) -> Optional[str]:
    """Return the role of a user in a family tree, or None if not a member."""
    row = db.session.execute(
        select(association_user_ft.c.role).where(
            association_user_ft.c.id_user == id_user,
            association_user_ft.c.id_family_tree == id_family_tree,
        )
    ).first()
    return row[0] if row else None


def _get_user_by_email(email: str) -> Optional[User]:
    """Return the User matching the given email, or None if not found."""
    return User.query.filter_by(email=email).first()


@user_app.route(
    "/user/family-tree/<int:id_family_tree>/member",
    methods=["POST"],
    endpoint="add_member",
)
@jwt_required()
def add_member(id_family_tree: int) -> Response:
    """Add a user (identified by email) as a member of a family tree."""
    current_user: int = int(get_jwt_identity())
    if _get_member_role(current_user, id_family_tree) != "editor":
        return make_response(jsonify({"message": "Not authorized", "status": 403}), 403)

    body: dict = request.get_json() or {}
    email: Optional[str] = body.get("email")
    role: str = body.get("role", "viewer")

    if not email:
        return make_response(jsonify({"message": "Missing email", "status": 400}), 400)
    if role not in VALID_ROLES:
        return make_response(
            jsonify({"message": "role must be 'viewer' or 'editor'", "status": 400}), 400
        )

    inviter: User = db.session.get(User, current_user)
    family_tree: Optional[FamilyTree] = db.session.get(FamilyTree, id_family_tree)

    target_user: Optional[User] = _get_user_by_email(email)
    if target_user is None:
        invitation_token: str = str(uuid.uuid4())
        invitation: FamilyTreeInvitation = FamilyTreeInvitation(
            email=email,
            id_family_tree=id_family_tree,
            role=role,
            token=invitation_token,
        )
        db.session.add(invitation)
        try:
            db.session.commit()
        except SQLAlchemyError as err:
            db.session.rollback()
            return make_response(jsonify({"message": f"Database error: {err}", "status": 500}), 500)
        send_member_invitation_email(
            to_email=email,
            tree_title=family_tree.title,
            family_name=family_tree.family_name,
            inviter_name=f"{inviter.name} {inviter.surname}",
            invitation_token=invitation_token,
        )
        return make_response(jsonify({"status": "invitation_sent", "message": "Invitation sent"}), 200)

    if _get_member_role(target_user.id_user, id_family_tree) is not None:
        return make_response(
            jsonify({"message": "User already member of this tree", "status": 409}), 409
        )

    db.session.execute(
        insert(association_user_ft).values(
            id_user=target_user.id_user, id_family_tree=id_family_tree, role=role
        )
    )
    try:
        db.session.commit()
    except SQLAlchemyError as err:
        db.session.rollback()
        return make_response(jsonify({"message": f"Database error: {err}", "status": 500}), 500)

    send_member_added_email(
        to_email=email,
        tree_title=family_tree.title,
        family_name=family_tree.family_name,
        inviter_name=f"{inviter.name} {inviter.surname}",
    )
    return make_response(jsonify({"message": "Member added", "status": 201}), 201)


@user_app.route(
    "/user/family-tree/<int:id_family_tree>/leave",
    methods=["DELETE"],
    endpoint="leave_family_tree",
)
@jwt_required()
def leave_family_tree(id_family_tree: int) -> Response:
    """Allow the authenticated user to leave a family tree they are a member of."""
    current_user: int = int(get_jwt_identity())

    if _get_member_role(current_user, id_family_tree) is None:
        return make_response(jsonify({"message": "You are not a member of this tree", "status": 404}), 404)

    count: int = db.session.execute(
        select(func.count()).select_from(association_user_ft).where(
            association_user_ft.c.id_family_tree == id_family_tree
        )
    ).scalar()
    if count <= 1:
        return make_response(
            jsonify({"message": "Cannot leave a tree you are the last member of", "status": 409}), 409
        )

    editor_count: int = db.session.execute(
        select(func.count()).select_from(association_user_ft).where(
            association_user_ft.c.id_family_tree == id_family_tree,
            association_user_ft.c.role == "editor",
            association_user_ft.c.id_user != current_user,
        )
    ).scalar()
    if _get_member_role(current_user, id_family_tree) == "editor" and editor_count == 0:
        return make_response(
            jsonify({"message": "Cannot leave: you are the last editor of this tree", "status": 409}), 409
        )

    db.session.execute(
        delete(association_user_ft).where(
            association_user_ft.c.id_user == current_user,
            association_user_ft.c.id_family_tree == id_family_tree,
        )
    )
    try:
        db.session.commit()
    except SQLAlchemyError as err:
        db.session.rollback()
        return make_response(jsonify({"message": f"Database error: {err}", "status": 500}), 500)
    return make_response(jsonify({"message": "You have left the tree", "status": 200}), 200)


@user_app.route(
    "/user/family-tree/<int:id_family_tree>/member/<string:email>",
    methods=["DELETE"],
    endpoint="remove_member",
)
@jwt_required()
def remove_member(id_family_tree: int, email: str) -> Response:
    """Remove a user (identified by email) from a family tree."""
    current_user: int = int(get_jwt_identity())
    if _get_member_role(current_user, id_family_tree) != "editor":
        return make_response(jsonify({"message": "Not authorized", "status": 403}), 403)

    target_user: Optional[User] = _get_user_by_email(email)
    if target_user is None:
        return make_response(jsonify({"message": "User not found", "status": 404}), 404)
    if _get_member_role(target_user.id_user, id_family_tree) is None:
        return make_response(
            jsonify({"message": "User not member of this tree", "status": 404}), 404
        )

    count: int = db.session.execute(
        select(func.count()).select_from(association_user_ft).where(
            association_user_ft.c.id_family_tree == id_family_tree
        )
    ).scalar()
    if count <= 1:
        return make_response(
            jsonify({"message": "Cannot remove the last member of a tree", "status": 409}), 409
        )

    db.session.execute(
        delete(association_user_ft).where(
            association_user_ft.c.id_user == target_user.id_user,
            association_user_ft.c.id_family_tree == id_family_tree,
        )
    )
    try:
        db.session.commit()
    except SQLAlchemyError as err:
        db.session.rollback()
        return make_response(jsonify({"message": f"Database error: {err}", "status": 500}), 500)
    return make_response(jsonify({"message": "Member removed", "status": 200}), 200)


@user_app.route(
    "/user/family-tree/<int:id_family_tree>/member/<string:email>",
    methods=["PATCH"],
    endpoint="update_member_role",
)
@jwt_required()
def update_member_role(id_family_tree: int, email: str) -> Response:
    """Update the role of a user (identified by email) in a family tree."""
    current_user: int = int(get_jwt_identity())
    if _get_member_role(current_user, id_family_tree) != "editor":
        return make_response(jsonify({"message": "Not authorized", "status": 403}), 403)

    body: dict = request.get_json() or {}
    new_role: Optional[str] = body.get("role")
    if new_role not in VALID_ROLES:
        return make_response(
            jsonify({"message": "role must be 'viewer' or 'editor'", "status": 400}), 400
        )

    target_user: Optional[User] = _get_user_by_email(email)
    if target_user is None:
        return make_response(jsonify({"message": "User not found", "status": 404}), 404)
    if _get_member_role(target_user.id_user, id_family_tree) is None:
        return make_response(
            jsonify({"message": "User not member of this tree", "status": 404}), 404
        )

    db.session.execute(
        update(association_user_ft).where(
            association_user_ft.c.id_user == target_user.id_user,
            association_user_ft.c.id_family_tree == id_family_tree,
        ).values(role=new_role)
    )
    try:
        db.session.commit()
    except SQLAlchemyError as err:
        db.session.rollback()
        return make_response(jsonify({"message": f"Database error: {err}", "status": 500}), 500)
    return make_response(jsonify({"message": "Role updated", "status": 200}), 200)


@user_app.route("/user/avatar", methods=["GET"], endpoint="get_avatar")
@jwt_required()
def get_avatar() -> Response:
    """Serve the avatar file of the authenticated user."""
    current_user: int = int(get_jwt_identity())
    user: User = db.session.get(User, current_user)

    if not user.avatar:
        return make_response(jsonify({"message": "No avatar", "status": 404}), 404)

    return send_from_directory(f"/avatars/{current_user}", user.avatar)


@user_app.route("/user/avatar", methods=["POST"], endpoint="upload_avatar")
@jwt_required()
def upload_avatar() -> Response:
    """Upload or replace the avatar of the authenticated user."""
    from .utils import allowed_file
    current_user: int = int(get_jwt_identity())
    user: User = db.session.get(User, current_user)

    if "file" not in request.files:
        return make_response(jsonify({"message": "No file part", "status": 400}), 400)

    file = request.files["file"]
    if file.filename == "":
        return make_response(jsonify({"message": "No selected file", "status": 400}), 400)
    if not allowed_file(file.filename):
        return make_response(jsonify({"message": "File not allowed", "status": 400}), 400)

    if user.avatar:
        old_path: str = f"/avatars/{current_user}/{user.avatar}"
        try:
            os.remove(old_path)
        except FileNotFoundError:
            pass

    filename: str = secure_filename(str(uuid.uuid4()) + "." + file.filename.rsplit(".", 1)[1].lower())
    filepath: str = f"/avatars/{current_user}/{filename}"
    os.makedirs(f"/avatars/{current_user}", exist_ok=True)
    file.save(filepath)

    from .utils import detect_face
    try:
        face = detect_face(filepath)
    except Exception:
        face = None
    user.avatar = filename
    user.avatar_face_x, user.avatar_face_y, user.avatar_face_width, user.avatar_face_height = face if face else (None, None, None, None)
    try:
        db.session.commit()
    except SQLAlchemyError as err:
        db.session.rollback()
        return make_response(jsonify({"message": f"Database error: {err}", "status": 500}), 500)

    return make_response(jsonify({"message": "Avatar uploaded", "status": 200, "avatar": filename}), 200)


@user_app.route("/user/avatar", methods=["DELETE"], endpoint="delete_avatar")
@jwt_required()
def delete_avatar() -> Response:
    """Delete the avatar of the authenticated user and remove the file from disk."""
    current_user: int = int(get_jwt_identity())
    user: User = db.session.get(User, current_user)

    if not user.avatar:
        return make_response(jsonify({"message": "No avatar to delete", "status": 404}), 404)

    try:
        os.remove(f"/avatars/{current_user}/{user.avatar}")
    except FileNotFoundError:
        pass

    user.avatar = None
    user.avatar_face_x = None
    user.avatar_face_y = None
    user.avatar_face_width = None
    user.avatar_face_height = None
    try:
        db.session.commit()
    except SQLAlchemyError as err:
        db.session.rollback()
        return make_response(jsonify({"message": f"Database error: {err}", "status": 500}), 500)

    return make_response(jsonify({"message": "Avatar deleted", "status": 200}), 200)


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

    files_to_delete = []

    for id_family_tree, count in user_counts.items():
        if count == 1:
            cell_ids = [
                row[0] for row in
                db.session.query(FamilyTreeCell.id_family_tree_cell)
                .filter_by(id_family_tree=id_family_tree).all()
            ]

            # Collect picture file paths before deletion
            pictures = Picture.query.filter(
                Picture.id_family_tree_cell.in_(cell_ids)
            ).all()
            for pic in pictures:
                files_to_delete.append(
                    f"/pictures/{id_family_tree}/{pic.id_family_tree_cell}/{pic.filename}"
                )

            # Collect pet picture file paths before deletion (CASCADE will remove DB rows)
            pets = Pet.query.filter(Pet.id_family_tree_cell.in_(cell_ids)).all()
            for pet in pets:
                for pet_pic in pet.pets_pictures:
                    files_to_delete.append(
                        f"/pet_pictures/{id_family_tree}/{pet.id_family_tree_cell}"
                        f"/{pet.id_pet}/{pet_pic.filename}"
                    )

            if cell_ids:
                db.session.execute(
                    association_parent_child.delete().where(
                        association_parent_child.c.id_family_tree_cell_parent.in_(cell_ids) |
                        association_parent_child.c.id_family_tree_cell_child.in_(cell_ids)
                    )
                )
                db.session.execute(
                    association_couple.delete().where(
                        association_couple.c.id_family_tree_cell_couple_1.in_(cell_ids) |
                        association_couple.c.id_family_tree_cell_couple_2.in_(cell_ids)
                    )
                )
            Picture.query.filter(
                Picture.id_family_tree_cell.in_(cell_ids)
            ).delete(synchronize_session=False)
            FamilyTreeCell.query.filter_by(id_family_tree=id_family_tree).delete()
            FamilyTree.query.filter_by(id_family_tree=id_family_tree).delete()

    db.session.delete(user)
    try:
        db.session.commit()
    except SQLAlchemyError as err:
        db.session.rollback()
        return make_response(jsonify({"message": f"Database error: {err}", "status": 500}), 500)

    for path in files_to_delete:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass

    result = user_schema.dump(user)
    data = {
        "message": "User Deleted !",
        "status": 200,
        "data": result
    }
    return make_response(jsonify(data), data["status"])
