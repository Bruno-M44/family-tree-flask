"""Crée un family tree exemple pour un nouvel utilisateur."""

import os
import shutil
from datetime import datetime

from app import db
from app.models import FamilyTree, FamilyTreeCell, Picture, Pet, PetPicture, association_user_ft
from sqlalchemy import insert

from .demo_data import (
    DEMO_FAMILY_TREE,
    DEMO_CELLS,
    DEMO_PARENT_CHILD,
    DEMO_COUPLES,
    DEMO_PETS,
)

DEMO_PICTURES_DIR = os.path.join(os.path.dirname(__file__), "pictures")
DEMO_PET_PICTURES_DIR = os.path.join(os.path.dirname(__file__), "pet_pictures")


def create_demo_family_tree(user):
    """Crée le family tree exemple et le lie à l'utilisateur."""

    # 1. Family tree
    ft = FamilyTree(
        title=DEMO_FAMILY_TREE["title"],
        family_name=DEMO_FAMILY_TREE["family_name"],
    )
    db.session.add(ft)
    db.session.flush()

    # 2. Cells + pictures
    ref_to_cell = {}  # ref -> FamilyTreeCell instance

    for cell_data in DEMO_CELLS:
        cell = FamilyTreeCell(
            name=cell_data["name"],
            surnames=cell_data["surnames"],
            birthday=cell_data["birthday"],
            jobs=cell_data["jobs"],
            comments=cell_data["comments"],
            generation=cell_data["generation"],
            deathday=cell_data["deathday"],
        )
        cell.id_family_tree = ft.id_family_tree
        db.session.add(cell)
        db.session.flush()

        ref_to_cell[cell_data["ref"]] = cell

        for pic_data in cell_data["pictures"]:
            pic = Picture(
                filename=pic_data["filename"],
                picture_date="01/01/1970",
                comments="",
                header_picture=str(pic_data["header_picture"]),
            )
            pic.id_family_tree_cell = cell.id_family_tree_cell
            db.session.add(pic)

            _copy_picture(pic_data["filename"], ft.id_family_tree, cell.id_family_tree_cell)

    # 3. Pets + pet pictures
    for pet_data in DEMO_PETS:
        cell = ref_to_cell[pet_data["cell_ref"]]
        pet = Pet(
            name=pet_data["name"],
            species=pet_data["species"],
            birthday=pet_data["birthday"],
            deathday=pet_data["deathday"],
            comments=pet_data["comments"],
        )
        pet.id_family_tree_cell = cell.id_family_tree_cell
        db.session.add(pet)
        db.session.flush()

        if pet_data.get("picture"):
            pet_pic = PetPicture(
                filename=pet_data["picture"],
                picture_date=None,
                comments="",
            )
            pet_pic.id_pet = pet.id_pet
            db.session.add(pet_pic)

            _copy_pet_picture(
                pet_data["picture"],
                ft.id_family_tree,
                cell.id_family_tree_cell,
                pet.id_pet,
            )

    # 4. Associations parent/enfant
    for parent_ref, child_ref in DEMO_PARENT_CHILD:
        parent_cell = ref_to_cell[parent_ref]
        child_cell = ref_to_cell[child_ref]
        parent_cell.parent.append(child_cell)

    # 5. Couples
    seen = set()
    for ref1, ref2 in DEMO_COUPLES:
        pair = tuple(sorted([ref1, ref2]))
        if pair not in seen:
            seen.add(pair)
            ref_to_cell[ref1].couple.append(ref_to_cell[ref2])

    # 6. Lier à l'utilisateur
    db.session.execute(
        insert(association_user_ft).values(
            id_user=user.id_user,
            id_family_tree=ft.id_family_tree,
            permission="edit",
        )
    )

    db.session.flush()


def _copy_picture(filename, id_family_tree, id_family_tree_cell):
    src = os.path.join(DEMO_PICTURES_DIR, filename)
    if not os.path.exists(src):
        return
    dest_dir = f"/pictures/{id_family_tree}/{id_family_tree_cell}"
    os.makedirs(dest_dir, exist_ok=True)
    shutil.copy2(src, os.path.join(dest_dir, filename))


def _copy_pet_picture(filename, id_family_tree, id_family_tree_cell, id_pet):
    src = os.path.join(DEMO_PET_PICTURES_DIR, filename)
    if not os.path.exists(src):
        return
    dest_dir = f"/pet_pictures/{id_family_tree}/{id_family_tree_cell}/{id_pet}"
    os.makedirs(dest_dir, exist_ok=True)
    shutil.copy2(src, os.path.join(dest_dir, filename))
