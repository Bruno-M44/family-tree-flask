import io
import json
import os
import uuid
import zipfile
import werkzeug.exceptions
from flask import jsonify, make_response, request, Blueprint, Response
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func, select

from werkzeug.security import generate_password_hash
from ..models import User, FamilyTree, association_user_ft, FamilyTreeCell, Picture, Pet, PetPicture
from ..schemas import user_schema, family_tree_schema
from ..demo.creator import create_demo_family_tree
from ..email_service import send_verification_email
from app import db


user_app = Blueprint("user_app", __name__)


@user_app.route("/verify", methods=["GET"], endpoint="verify_email")
def verify_email():
    token = request.args.get("token", "")
    if not token:
        return make_response(jsonify({"message": "Missing token", "status": 400}), 400)
    user = User.query.filter_by(verification_token=token).first()
    if not user:
        return make_response(jsonify({"message": "Invalid or expired token", "status": 404}), 404)
    user.verified = True
    user.verification_token = None
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return make_response(jsonify({"message": "Database error", "status": 500}), 500)
    return make_response(jsonify({"message": "Email verified !", "status": 200}), 200)


@user_app.route("/user/export", methods=["GET"], endpoint="export_user_data")
@jwt_required()
def export_user_data():
    current_user = int(get_jwt_identity())
    user = db.session.get(User, current_user)

    family_trees_data = []
    rows = db.session.query(FamilyTree, association_user_ft.c.permission).join(
        association_user_ft,
        FamilyTree.id_family_tree == association_user_ft.c.id_family_tree
    ).filter(association_user_ft.c.id_user == current_user).all()

    for family_tree, permission in rows:
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
            "permission": permission,
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

    rows = db.session.query(FamilyTree, association_user_ft.c.permission).join(
        association_user_ft,
        FamilyTree.id_family_tree == association_user_ft.c.id_family_tree
    ).filter(association_user_ft.c.id_user == current_user).all()

    family_trees_result = []
    for family_tree, permission in rows:
        ft = family_tree_schema.dump(family_tree)
        ft["permission"] = permission
        family_trees_result.append(ft)
    result["family_trees"] = family_trees_result

    data = {
        "message": "User Info !",
        "status": 200,
        "data": result
    }
    return make_response(jsonify(data), data["status"])


@user_app.route("/user", methods=["POST"], endpoint="create_user")
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
        db.session.add(new_user)
        db.session.flush()
        create_demo_family_tree(new_user)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            return make_response(jsonify({"message": "Database error", "status": 500}), 500)
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
def update_user():
    current_user = int(get_jwt_identity())
    user = db.session.get(User, current_user)
    data = request.get_json() or {}
    if 'name' in data:
        user.name = data['name']
    if 'surname' in data:
        user.surname = data['surname']
    if 'email' in data:
        user.email = data['email']
    if 'password' in data:
        user.password = generate_password_hash(data['password'])

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return make_response(jsonify({"message": "Database error", "status": 500}), 500)
    result = user_schema.dump(user)
    data = {
        "message": "User Modified !",
        "status": 200,
        "data": result
    }
    return make_response(jsonify(data), data["status"])


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

            Picture.query.filter(
                Picture.id_family_tree_cell.in_(cell_ids)
            ).delete(synchronize_session=False)
            FamilyTreeCell.query.filter_by(id_family_tree=id_family_tree).delete()
            FamilyTree.query.filter_by(id_family_tree=id_family_tree).delete()

    db.session.delete(user)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return make_response(jsonify({"message": "Database error", "status": 500}), 500)

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
