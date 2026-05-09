#! /usr/bin/env python
'''Commands usable by the application'''
import click
from flask import Blueprint
from .. import models
from ..models import Picture, PetPicture, FamilyTreeCell, Pet
from ..views.utils import detect_face
from app import db


command_app = Blueprint("command_app", __name__)


@command_app.cli.command()
def init_db():
    '''Drop and create DB with a few records'''
    models.init_db()


@command_app.cli.command()
def create_all():
    '''Create tables that do not exist'''
    models.create_all()


@command_app.cli.command()
@click.argument("table")
def drop_table(table: str):
    '''Drop specific table'''
    models.drop_table(table=table)


@command_app.cli.command()
def detect_faces():
    '''Run face detection on all pictures missing face data'''
    pictures = Picture.query.filter(Picture.face_x.is_(None)).all()
    click.echo(f"Pictures to process: {len(pictures)}")
    updated = 0
    for picture in pictures:
        cell = db.session.get(FamilyTreeCell, picture.id_family_tree_cell)
        if cell is None:
            continue
        path = f"/pictures/{cell.id_family_tree}/{cell.id_family_tree_cell}/{picture.filename}"
        face = detect_face(path)
        if face:
            picture.face_x, picture.face_y, picture.face_width, picture.face_height = face
            updated += 1
    db.session.commit()
    click.echo(f"Pictures updated: {updated}")

    pet_pictures = PetPicture.query.filter(PetPicture.face_x.is_(None)).all()
    click.echo(f"Pet pictures to process: {len(pet_pictures)}")
    updated = 0
    for pet_picture in pet_pictures:
        pet = db.session.get(Pet, pet_picture.id_pet)
        if pet is None:
            continue
        cell = db.session.get(FamilyTreeCell, pet.id_family_tree_cell)
        if cell is None:
            continue
        path = f"/pet_pictures/{cell.id_family_tree}/{cell.id_family_tree_cell}/{pet.id_pet}/{pet_picture.filename}"
        face = detect_face(path)
        if face:
            pet_picture.face_x, pet_picture.face_y, pet_picture.face_width, pet_picture.face_height = face
            updated += 1
    db.session.commit()
    click.echo(f"Pet pictures updated: {updated}")
