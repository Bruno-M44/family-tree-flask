import io
import json
import os
import uuid
import zipfile
import werkzeug.exceptions
from datetime import datetime
from flask import jsonify, make_response, request, Blueprint, Response
from flask_jwt_extended import jwt_required, get_jwt_identity

from sqlalchemy import insert, select
from sqlalchemy.exc import SQLAlchemyError
from ..models import (
    User, FamilyTree, association_user_ft, FamilyTreeCell, Picture,
    Pet, PetPicture, association_parent_child, association_couple,
)
from ..schemas import family_trees_schema, family_tree_schema
from app import db
from .utils import detect_face

family_tree_app = Blueprint("family_tree_app", __name__)


@family_tree_app.route("/family_trees", methods=["GET"], endpoint="get_family_trees")
@jwt_required()
def get_family_trees():
    current_user = int(get_jwt_identity())
    all_family_trees = FamilyTree.query.join(association_user_ft).filter(
        association_user_ft.c.id_user == current_user).all()
    result = family_trees_schema.dump(all_family_trees)
    data = {
        "message": "All Family Trees !",
        "status": 200,
        "data": result
    }
    return make_response(jsonify(data), data["status"])


@family_tree_app.route("/family_tree", methods=["POST"], endpoint="create_family_tree")
@jwt_required()
def create_family_tree():
    current_user = int(get_jwt_identity())
    user = db.session.get(User, current_user)
    body = request.get_json() or {}
    required = ['title', 'family_name']
    missing = [f for f in required if not body.get(f)]
    if missing:
        return make_response(jsonify({"message": f"Missing fields: {', '.join(missing)}", "status": 400}), 400)

    new_family_tree = FamilyTree(title=body['title'], family_name=body['family_name'])
    db.session.add(new_family_tree)
    db.session.flush()
    db.session.execute(
        insert(association_user_ft).values(
            id_user=current_user, id_family_tree=new_family_tree.id_family_tree, role="editor"
        )
    )
    try:
        db.session.commit()
    except SQLAlchemyError as err:
        db.session.rollback()
        return make_response(jsonify({"message": f"Database error: {err}", "status": 500}), 500)

    result = family_tree_schema.dump(new_family_tree)
    data = {
        "message": "Family Tree Created !",
        "status": 201,
        "data": result
    }
    return make_response(jsonify(data), data["status"])


@family_tree_app.route("/family_trees/<int:id_family_tree>/export", methods=["GET"], endpoint="export_family_tree")
@jwt_required()
def export_family_tree(id_family_tree: int):
    current_user = int(get_jwt_identity())
    family_tree = FamilyTree.query.join(association_user_ft).filter(
        association_user_ft.c.id_user == current_user,
        FamilyTree.id_family_tree == id_family_tree,
    ).first()
    if family_tree is None:
        return make_response(jsonify({"message": "Family tree not found"}), 404)

    cells = FamilyTreeCell.query.filter_by(id_family_tree=id_family_tree).all()
    cell_ids = [c.id_family_tree_cell for c in cells]

    if cell_ids:
        pc_rows = db.session.execute(
            select(association_parent_child).where(
                association_parent_child.c.id_family_tree_cell_parent.in_(cell_ids)
            )
        ).fetchall()
        couple_rows = db.session.execute(
            select(association_couple).where(
                association_couple.c.id_family_tree_cell_couple_1.in_(cell_ids)
            )
        ).fetchall()
    else:
        pc_rows, couple_rows = [], []

    cells_data = []
    for cell in cells:
        pictures_data = []
        for pic in cell.pictures:
            pictures_data.append({
                "zip_path": f"pictures/{cell.id_family_tree_cell}_{pic.filename}",
                "picture_date": pic.picture_date.strftime("%d/%m/%Y") if pic.picture_date else None,
                "comments": pic.comments,
                "header_picture": pic.header_picture,
                "face_x": pic.face_x,
                "face_y": pic.face_y,
                "face_width": pic.face_width,
                "face_height": pic.face_height,
            })

        pets_data = []
        for pet in cell.pets:
            pet_pictures_data = []
            for pp in pet.pets_pictures:
                pet_pictures_data.append({
                    "zip_path": f"pets/{pet.id_pet}_{pp.filename}",
                    "picture_date": pp.picture_date.strftime("%d/%m/%Y") if pp.picture_date else None,
                    "comments": pp.comments,
                    "is_main": pp.is_main,
                    "face_x": pp.face_x,
                    "face_y": pp.face_y,
                    "face_width": pp.face_width,
                    "face_height": pp.face_height,
                })
            pets_data.append({
                "export_id": pet.id_pet,
                "name": pet.name,
                "species": pet.species,
                "birthday": pet.birthday.strftime("%d/%m/%Y") if pet.birthday else None,
                "deathday": pet.deathday.strftime("%d/%m/%Y") if pet.deathday else None,
                "comments": pet.comments,
                "pictures": pet_pictures_data,
            })

        cells_data.append({
            "export_id": cell.id_family_tree_cell,
            "name": cell.name,
            "maiden_name": cell.maiden_name,
            "surnames": cell.surnames,
            "birthday": cell.birthday.strftime("%d/%m/%Y") if cell.birthday else None,
            "deathday": cell.deathday.strftime("%d/%m/%Y") if cell.deathday else None,
            "jobs": cell.jobs,
            "comments": cell.comments,
            "generation": cell.generation,
            "pictures": pictures_data,
            "pets": pets_data,
        })

    tree_json = {
        "version": 1,
        "title": family_tree.title,
        "family_name": family_tree.family_name,
        "cells": cells_data,
        "relations": {
            "parent_child": [
                {"parent_id": row.id_family_tree_cell_parent, "child_id": row.id_family_tree_cell_child}
                for row in pc_rows
            ],
            "couples": [
                {
                    "cell_1_id": row.id_family_tree_cell_couple_1,
                    "cell_2_id": row.id_family_tree_cell_couple_2,
                    "start_union": row.start_union.strftime("%d/%m/%Y") if row.start_union else None,
                    "end_union": row.end_union.strftime("%d/%m/%Y") if row.end_union else None,
                }
                for row in couple_rows
            ],
        },
    }

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("tree.json", json.dumps(tree_json, ensure_ascii=False, indent=2))
        for cell in cells:
            for pic in cell.pictures:
                src = f"/pictures/{id_family_tree}/{cell.id_family_tree_cell}/{pic.filename}"
                if os.path.isfile(src):
                    zf.write(src, f"pictures/{cell.id_family_tree_cell}_{pic.filename}")
            for pet in cell.pets:
                for pp in pet.pets_pictures:
                    src = f"/pet_pictures/{id_family_tree}/{cell.id_family_tree_cell}/{pet.id_pet}/{pp.filename}"
                    if os.path.isfile(src):
                        zf.write(src, f"pets/{pet.id_pet}_{pp.filename}")

    buf.seek(0)
    safe_name = family_tree.family_name.replace(" ", "_")
    return Response(
        buf.getvalue(),
        status=200,
        mimetype="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.zip"'},
    )


@family_tree_app.route("/family_trees/import", methods=["POST"], endpoint="import_family_tree")
@jwt_required()
def import_family_tree():
    current_user = int(get_jwt_identity())

    if "file" not in request.files:
        return make_response(jsonify({"message": "No file provided"}), 400)
    file = request.files["file"]
    if not file.filename.lower().endswith(".zip"):
        return make_response(jsonify({"message": "File must be a ZIP archive"}), 400)

    try:
        with zipfile.ZipFile(io.BytesIO(file.read())) as zf:
            if "tree.json" not in zf.namelist():
                return make_response(jsonify({"message": "Invalid archive: missing tree.json"}), 400)

            tree_data = json.loads(zf.read("tree.json"))
            for field in ("title", "family_name", "cells", "relations"):
                if field not in tree_data:
                    return make_response(jsonify({"message": f"Invalid tree.json: missing field '{field}'"}), 400)

            new_tree = FamilyTree(title=tree_data["title"], family_name=tree_data["family_name"])
            db.session.add(new_tree)
            db.session.flush()
            db.session.execute(
                insert(association_user_ft).values(
                    id_user=current_user, id_family_tree=new_tree.id_family_tree, role="editor"
                )
            )

            cell_map = {}
            pet_map = {}

            for cell_data in tree_data["cells"]:
                new_cell = FamilyTreeCell(
                    name=cell_data["name"],
                    surnames=cell_data["surnames"],
                    generation=cell_data["generation"],
                    birthday=cell_data.get("birthday"),
                    deathday=cell_data.get("deathday"),
                    maiden_name=cell_data.get("maiden_name"),
                    jobs=cell_data.get("jobs"),
                    comments=cell_data.get("comments"),
                )
                new_cell.id_family_tree = new_tree.id_family_tree
                db.session.add(new_cell)
                db.session.flush()
                cell_map[cell_data["export_id"]] = new_cell

                for pic_data in cell_data.get("pictures", []):
                    ext = os.path.splitext(pic_data["zip_path"])[1]
                    new_filename = f"{uuid.uuid4()}{ext}"
                    pic_dir = f"/pictures/{new_tree.id_family_tree}/{new_cell.id_family_tree_cell}"
                    os.makedirs(pic_dir, exist_ok=True)
                    filepath = f"{pic_dir}/{new_filename}"
                    if pic_data["zip_path"] in zf.namelist():
                        with zf.open(pic_data["zip_path"]) as src, open(filepath, "wb") as dst:
                            dst.write(src.read())
                    new_pic = Picture(
                        filename=new_filename,
                        picture_date=pic_data.get("picture_date"),
                        comments=pic_data.get("comments") or "",
                        header_picture=pic_data.get("header_picture", False),
                    )
                    # Prioritise face coords from ZIP; run detection if absent
                    face_x = pic_data.get("face_x")
                    if face_x is None and os.path.exists(filepath):
                        try:
                            detected = detect_face(filepath)
                        except Exception:
                            detected = None
                        if detected:
                            face_x, face_y, face_w, face_h = detected
                            new_pic.face_x, new_pic.face_y = face_x, face_y
                            new_pic.face_width, new_pic.face_height = face_w, face_h
                    else:
                        new_pic.face_x = face_x
                        new_pic.face_y = pic_data.get("face_y")
                        new_pic.face_width = pic_data.get("face_width")
                        new_pic.face_height = pic_data.get("face_height")
                    new_pic.id_family_tree_cell = new_cell.id_family_tree_cell
                    db.session.add(new_pic)

                for pet_data in cell_data.get("pets", []):
                    new_pet = Pet(
                        name=pet_data["name"],
                        species=pet_data.get("species"),
                        birthday=pet_data.get("birthday"),
                        deathday=pet_data.get("deathday"),
                        comments=pet_data.get("comments") or "",
                    )
                    new_pet.id_family_tree_cell = new_cell.id_family_tree_cell
                    db.session.add(new_pet)
                    db.session.flush()
                    pet_map[pet_data["export_id"]] = new_pet

                    for pp_data in pet_data.get("pictures", []):
                        ext = os.path.splitext(pp_data["zip_path"])[1]
                        new_filename = f"{uuid.uuid4()}{ext}"
                        pp_dir = f"/pet_pictures/{new_tree.id_family_tree}/{new_cell.id_family_tree_cell}/{new_pet.id_pet}"
                        os.makedirs(pp_dir, exist_ok=True)
                        pp_filepath = f"{pp_dir}/{new_filename}"
                        if pp_data["zip_path"] in zf.namelist():
                            with zf.open(pp_data["zip_path"]) as src, open(pp_filepath, "wb") as dst:
                                dst.write(src.read())
                        new_pp = PetPicture(
                            filename=new_filename,
                            picture_date=pp_data.get("picture_date"),
                            comments=pp_data.get("comments") or "",
                            is_main=pp_data.get("is_main", False),
                        )
                        pp_face_x = pp_data.get("face_x")
                        if pp_face_x is None and os.path.exists(pp_filepath):
                            try:
                                pp_detected = detect_face(pp_filepath)
                            except Exception:
                                pp_detected = None
                            if pp_detected:
                                new_pp.face_x, new_pp.face_y, new_pp.face_width, new_pp.face_height = pp_detected
                        else:
                            new_pp.face_x = pp_face_x
                            new_pp.face_y = pp_data.get("face_y")
                            new_pp.face_width = pp_data.get("face_width")
                            new_pp.face_height = pp_data.get("face_height")
                        new_pp.id_pet = new_pet.id_pet
                        db.session.add(new_pp)

            for pc in tree_data["relations"].get("parent_child", []):
                parent_cell = cell_map.get(pc["parent_id"])
                child_cell = cell_map.get(pc["child_id"])
                if parent_cell and child_cell:
                    db.session.execute(
                        insert(association_parent_child).values(
                            id_family_tree_cell_parent=parent_cell.id_family_tree_cell,
                            id_family_tree_cell_child=child_cell.id_family_tree_cell,
                        )
                    )

            for cp in tree_data["relations"].get("couples", []):
                cell_1 = cell_map.get(cp["cell_1_id"])
                cell_2 = cell_map.get(cp["cell_2_id"])
                if cell_1 and cell_2:
                    start = datetime.strptime(cp["start_union"], "%d/%m/%Y") if cp.get("start_union") else None
                    end = datetime.strptime(cp["end_union"], "%d/%m/%Y") if cp.get("end_union") else None
                    db.session.execute(
                        insert(association_couple).values(
                            id_family_tree_cell_couple_1=cell_1.id_family_tree_cell,
                            id_family_tree_cell_couple_2=cell_2.id_family_tree_cell,
                            start_union=start,
                            end_union=end,
                        )
                    )

            db.session.commit()

    except zipfile.BadZipFile:
        return make_response(jsonify({"message": "Invalid ZIP file"}), 400)
    except (KeyError, json.JSONDecodeError) as e:
        db.session.rollback()
        return make_response(jsonify({"message": f"Invalid tree.json format: {e}"}), 400)
    except SQLAlchemyError as e:
        db.session.rollback()
        return make_response(jsonify({"message": f"Database error: {e}"}), 500)
    except Exception as e:
        db.session.rollback()
        return make_response(jsonify({"message": f"Import failed: {e}"}), 500)

    return make_response(jsonify({"message": "Family tree imported successfully"}), 201)


@family_tree_app.route(
    "/family_trees/<int:id_family_tree>",
    methods=["GET", "PUT", "DELETE"],
    endpoint="get_update_delete_family_tree"
)
@jwt_required()
def get_update_delete_family_tree(id_family_tree: int):
    current_user = int(get_jwt_identity())
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

    if request.method in ("PUT", "DELETE"):
        role = db.session.execute(
            select(association_user_ft.c.role).where(
                association_user_ft.c.id_user == current_user,
                association_user_ft.c.id_family_tree == id_family_tree,
            )
        ).scalar_one_or_none()
        if role != "editor":
            data = {
                "message": "Viewers cannot modify or delete this family tree",
                "status": 403,
            }
            return make_response(jsonify(data), data["status"])

    if request.method == "PUT":
        family_tree = db.session.get(FamilyTree, id_family_tree)
        data = request.get_json() or {}
        if 'title' in data:
            family_tree.title = data['title']
        if 'family_name' in data:
            family_tree.family_name = data['family_name']

        try:
            db.session.commit()
        except SQLAlchemyError as err:
            db.session.rollback()
            return make_response(jsonify({"message": f"Database error: {err}", "status": 500}), 500)
        result = family_tree_schema.dump(family_tree)
        data = {
            "message": "Family Tree Modified !",
            "status": 200,
            "data": result
        }
        return make_response(jsonify(data), data["status"])

    if request.method == "DELETE":
        cell_ids = db.session.query(FamilyTreeCell.id_family_tree_cell).filter_by(id_family_tree=id_family_tree).all()
        cell_ids_list = [c[0] for c in cell_ids]
        if cell_ids_list:
            from app.models import association_parent_child, association_couple
            db.session.execute(
                association_parent_child.delete().where(
                    association_parent_child.c.id_family_tree_cell_parent.in_(cell_ids_list) |
                    association_parent_child.c.id_family_tree_cell_child.in_(cell_ids_list)
                )
            )
            db.session.execute(
                association_couple.delete().where(
                    association_couple.c.id_family_tree_cell_couple_1.in_(cell_ids_list) |
                    association_couple.c.id_family_tree_cell_couple_2.in_(cell_ids_list)
                )
            )
        Picture.query.filter(
            Picture.id_family_tree_cell.in_(
                db.session.query(FamilyTreeCell.id_family_tree_cell).filter_by(id_family_tree=id_family_tree)
            )
        ).delete(synchronize_session=False)
        FamilyTreeCell.query.filter_by(id_family_tree=id_family_tree).delete()
        db.session.delete(family_tree)
        try:
            db.session.commit()
        except SQLAlchemyError as err:
            db.session.rollback()
            return make_response(jsonify({"message": f"Database error: {err}", "status": 500}), 500)
        result = family_tree_schema.dump(family_tree)
        data = {
            "message": "Family Tree Deleted !",
            "status": 200,
            "data": result
        }

        return make_response(jsonify(data), data["status"])
