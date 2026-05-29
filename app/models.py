#! /usr/bin/env python
"""Module providing the application models."""

from datetime import datetime, timezone
import logging as lg

from sqlalchemy import insert
from werkzeug.security import generate_password_hash
from app import db
from app.encryption import EncryptedString, EncryptedDateTime

association_user_ft = db.Table(
    "association_user_ft",
    db.Column("id_user", db.Integer, db.ForeignKey(
        "user.id_user", ondelete="CASCADE"), primary_key=True),
    db.Column("id_family_tree", db.Integer, db.ForeignKey(
        "family_tree.id_family_tree", ondelete="CASCADE"), primary_key=True),
    db.Column("role", db.String, nullable=False, default="viewer")
)

association_parent_child = db.Table(
    "association_parent_child",
    db.Column(
        "id_family_tree_cell_parent",
        db.Integer,
        db.ForeignKey("family_tree_cell.id_family_tree_cell"), primary_key=True
    ),
    db.Column(
        "id_family_tree_cell_child",
        db.Integer,
        db.ForeignKey("family_tree_cell.id_family_tree_cell"), primary_key=True
    )
)

association_couple = db.Table(
    "association_couple",
    db.Column(
        "id_family_tree_cell_couple_1",
        db.Integer,
        db.ForeignKey("family_tree_cell.id_family_tree_cell"), primary_key=True
    ),
    db.Column(
        "id_family_tree_cell_couple_2",
        db.Integer,
        db.ForeignKey("family_tree_cell.id_family_tree_cell"), primary_key=True
    ),
    db.Column("start_union", db.DateTime, nullable=True),
    db.Column("end_union", db.DateTime, nullable=True)
)


class TokenBlocklist(db.Model):
    """Revoked JWT tokens (identified by jti)."""
    id = db.Column(db.Integer, primary_key=True)
    jti = db.Column(db.String(36), nullable=False, index=True, unique=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class FamilyTreeInvitation(db.Model):
    """Pending invitation to join a family tree for a non-registered email."""
    id_invitation = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String, nullable=False, index=True)
    id_family_tree = db.Column(
        db.Integer,
        db.ForeignKey("family_tree.id_family_tree", ondelete="CASCADE"),
        nullable=False,
    )
    role = db.Column(db.String, nullable=False, default="viewer")
    token = db.Column(db.String, nullable=False, unique=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class User(db.Model):
    """user model"""
    # query: db.Query  # autocomplete
    id_user = db.Column(db.Integer, primary_key=True)
    name = db.Column(EncryptedString, nullable=False)
    surname = db.Column(EncryptedString, nullable=False)
    email = db.Column(db.String, nullable=False, unique=True)
    password = db.Column(db.String, nullable=False)
    verified = db.Column(db.Boolean, nullable=False, default=False)
    verification_token = db.Column(db.String, nullable=True)
    avatar = db.Column(db.String, nullable=True)
    avatar_face_x = db.Column(db.Integer, nullable=True)
    avatar_face_y = db.Column(db.Integer, nullable=True)
    avatar_face_width = db.Column(db.Integer, nullable=True)
    avatar_face_height = db.Column(db.Integer, nullable=True)
    family_trees = db.relationship(
        "FamilyTree",
        secondary=association_user_ft,
        backref=db.backref("user")
    )

    def __init__(self, name, surname, email, password):
        self.name = name
        self.surname = surname
        self.email = email
        self.password = generate_password_hash(password)


class FamilyTree(db.Model):
    """family_tree model"""
    # query: db.Query  # autocomplete
    id_family_tree = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String, nullable=False)
    family_name = db.Column(db.String, nullable=False)
    is_example = db.Column(db.Boolean, nullable=False, default=False)
    family_tree_cells = db.relationship("FamilyTreeCell", backref=db.backref("family_tree"))

    def __init__(self, title, family_name, is_example=False):
        self.title = title
        self.family_name = family_name
        self.is_example = is_example


class FamilyTreeCell(db.Model):
    """family_tree_cell model"""
    # query: db.Query  # autocomplete
    id_family_tree_cell = db.Column(db.Integer, primary_key=True)
    name = db.Column(EncryptedString, nullable=False)
    maiden_name = db.Column(EncryptedString, nullable=True)
    surnames = db.Column(EncryptedString, nullable=False)
    birthday = db.Column(EncryptedDateTime, nullable=True)
    jobs = db.Column(EncryptedString, nullable=True)
    comments = db.Column(EncryptedString, nullable=True)
    deathday = db.Column(EncryptedDateTime, nullable=True)
    generation = db.Column(db.Integer)
    id_family_tree = db.Column(db.ForeignKey("family_tree.id_family_tree", ondelete="CASCADE"))
    pictures = db.relationship("Picture", backref=db.backref("family_tree_cell"))
    pets = db.relationship("Pet", backref=db.backref("family_tree_cell"))
    parent = db.relationship(
        "FamilyTreeCell",
        secondary="association_parent_child",
        primaryjoin=(
            "association_parent_child.c.id_family_tree_cell_parent == "
            "FamilyTreeCell.id_family_tree_cell"),
        secondaryjoin=(
            "association_parent_child.c.id_family_tree_cell_child == "
            "FamilyTreeCell.id_family_tree_cell"
        ),
        backref=db.backref("parents")
    )
    couple = db.relationship(
        "FamilyTreeCell",
        secondary="association_couple",
        primaryjoin=(
            "association_couple.c.id_family_tree_cell_couple_1 == "
            "FamilyTreeCell.id_family_tree_cell"
        ),
        secondaryjoin=(
            "association_couple.c.id_family_tree_cell_couple_2 == "
            "FamilyTreeCell.id_family_tree_cell"
        ),
        backref=db.backref("couples")
    )

    def __init__(
        self,
        name: str,
        surnames: str,
        generation: int,
        birthday: str = None,
        deathday: str = None,
        maiden_name: str = None,
        jobs: str = None,
        comments: str = None
        ):
        self.name = name
        self.maiden_name = maiden_name
        self.surnames = surnames
        self.birthday = datetime.strptime(birthday, "%d/%m/%Y") if birthday and birthday != 'null' else None
        self.deathday = datetime.strptime(deathday, "%d/%m/%Y") if deathday and deathday != 'null' else None
        self.jobs = jobs
        self.comments = comments
        self.generation = generation


class Picture(db.Model):
    """picture model"""
    # query: db.Query  # autocomplete
    id_picture = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String, nullable=False)
    picture_date = db.Column(db.DateTime, nullable=False)
    comments = db.Column(db.String, nullable=False)
    header_picture = db.Column(db.Boolean, default=False)
    face_x = db.Column(db.Integer, nullable=True)
    face_y = db.Column(db.Integer, nullable=True)
    face_width = db.Column(db.Integer, nullable=True)
    face_height = db.Column(db.Integer, nullable=True)
    id_family_tree_cell = db.Column(
        db.ForeignKey("family_tree_cell.id_family_tree_cell", ondelete="CASCADE"))

    def __init__(self, filename: str, picture_date: str, comments: str, header_picture: str):
        self.filename = filename
        self.picture_date = datetime.strptime(picture_date, "%d/%m/%Y") if picture_date else None
        self.comments = comments
        self.header_picture = str(header_picture).strip().lower() == 'true'


class Pet(db.Model):
    """pet model"""
    # query: db.Query  # autocomplete
    id_pet = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    species = db.Column(db.String, nullable=True)
    birthday = db.Column(db.DateTime, nullable=True)
    deathday = db.Column(db.DateTime, nullable=True)
    comments = db.Column(db.String, nullable=True)
    id_family_tree_cell = db.Column(
        db.ForeignKey("family_tree_cell.id_family_tree_cell", ondelete="CASCADE"))
    pets_pictures = db.relationship("PetPicture", backref=db.backref("pet"))

    def __init__(self, name: str, species: str | None, birthday: str, deathday: str, comments: str):
        self.name = name
        self.species = species
        self.birthday = datetime.strptime(birthday, "%d/%m/%Y") if birthday and birthday != 'null' else None
        self.deathday = datetime.strptime(deathday, "%d/%m/%Y") if deathday and deathday != 'null' else None
        self.comments = comments


class PetPicture(db.Model):
    """pet_picture model"""
    # query: db.Query  # autocomplete
    id_pet_picture = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String, nullable=False)
    picture_date = db.Column(db.DateTime, nullable=True)
    comments = db.Column(db.String, nullable=True)
    is_main = db.Column(db.Boolean, nullable=False, default=False)
    face_x = db.Column(db.Integer, nullable=True)
    face_y = db.Column(db.Integer, nullable=True)
    face_width = db.Column(db.Integer, nullable=True)
    face_height = db.Column(db.Integer, nullable=True)
    id_pet = db.Column(
        db.ForeignKey("pet.id_pet", ondelete="CASCADE"))

    def __init__(self, filename: str, picture_date: str, comments: str, is_main: bool = False):
        self.filename = filename
        self.picture_date = datetime.strptime(picture_date, "%d/%m/%Y") if picture_date else None
        self.comments = comments
        self.is_main = is_main


class FamilyTreeHiddenBranches(db.Model):
    """Branches masquées par utilisateur et par arbre généalogique."""
    __tablename__ = "family_tree_hidden_branches"
    id_user = db.Column(
        db.Integer,
        db.ForeignKey("user.id_user", ondelete="CASCADE"),
        primary_key=True,
    )
    id_family_tree = db.Column(
        db.Integer,
        db.ForeignKey("family_tree.id_family_tree", ondelete="CASCADE"),
        primary_key=True,
    )
    hidden_above = db.Column(db.JSON, nullable=False, default=list)
    hidden_below = db.Column(db.JSON, nullable=False, default=list)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
    )


def create_all():
    '''Create tables that do not exist'''
    db.create_all()


def drop_table(table: str):
    '''Drop specific table'''
    db.metadata.tables[table].drop(db.engine, checkfirst=True)


def init_db():
    '''Drop and create DB with a few records'''
    db.drop_all()
    db.create_all()
    user_1 = User(name="Smith", surname="John", email="john.smith@gmail.com", password="password1")
    user_1.verified = True
    family_tree_1 = FamilyTree(title="Family Smith", family_name="Smith")
    family_tree_cell_1 = FamilyTreeCell(
        name="Smith",
        surnames="John, Johnny",
        birthday="14/07/1983",
        jobs="engineer",
        comments="my father",
        generation=1
    )
    family_tree_cell_2 = FamilyTreeCell(
        name="Smith",
        surnames="Jimmy",
        birthday="17/09/1999",
        jobs="fireman",
        comments="son",
        generation=2
    )
    family_tree_cell_3 = FamilyTreeCell(
        name="Smith",
        surnames="Sarah",
        birthday="12/02/2002",
        jobs="director",
        comments="daughter",
        generation=2
    )
    family_tree_cell_4 = FamilyTreeCell(
        name="Jackson",
        surnames="Bob",
        birthday="05/10/1945",
        deathday="15/06/2012",
        jobs="factory worker",
        comments="grand father",
        generation=0
    )
    family_tree_cell_5 = FamilyTreeCell(
        name="Smith",
        surnames="Franklin",
        birthday="30/09/1940",
        deathday="15/06/2003",
        jobs="soldier",
        comments="grand father",
        generation=0
    )
    family_tree_cell_6 = FamilyTreeCell(
        name="Roosvelt",
        surnames="Amanda",
        birthday="25/12/1950",
        jobs="secretary",
        comments="grand mother",
        generation=0
    )
    family_tree_cell_7 = FamilyTreeCell(
        name="Gallagher",
        surnames="Shannon",
        birthday="04/02/1942",
        deathday="12/03/2015",
        jobs="housewife",
        comments="grand mother",
        generation=0
    )
    family_tree_cell_8 = FamilyTreeCell(
        name="Lockler",
        surnames="Roseanne",
        birthday="05/05/1980",
        jobs="hairdresser",
        comments="mother",
        generation=1
    )
    family_tree_cell_1.parent.append(family_tree_cell_2)
    family_tree_cell_1.parent.append(family_tree_cell_3)
    family_tree_cell_8.parent.append(family_tree_cell_2)
    family_tree_cell_8.parent.append(family_tree_cell_3)
    family_tree_cell_4.parent.append(family_tree_cell_1)
    family_tree_cell_5.parent.append(family_tree_cell_8)
    family_tree_cell_6.parent.append(family_tree_cell_1)
    family_tree_cell_7.parent.append(family_tree_cell_8)
    family_tree_cell_1.couple.append(family_tree_cell_8)
    family_tree_cell_5.couple.append(family_tree_cell_7)
    family_tree_cell_6.couple.append(family_tree_cell_4)
    family_tree_1.family_tree_cells.append(family_tree_cell_1)
    family_tree_1.family_tree_cells.append(family_tree_cell_2)
    family_tree_1.family_tree_cells.append(family_tree_cell_3)
    family_tree_1.family_tree_cells.append(family_tree_cell_4)
    family_tree_1.family_tree_cells.append(family_tree_cell_5)
    family_tree_1.family_tree_cells.append(family_tree_cell_6)
    family_tree_1.family_tree_cells.append(family_tree_cell_7)
    family_tree_1.family_tree_cells.append(family_tree_cell_8)
    db.session.flush()
    db.session.add(user_1)
    db.session.add(family_tree_1)
    db.session.flush()
    db.session.execute(
        insert(association_user_ft).values(
            id_user=user_1.id_user, id_family_tree=family_tree_1.id_family_tree, role="editor"
        )
    )

    # determination of x and y
    # sort by birthday
    # Loop on family_tree_cells :
    # 1er enregistrement, on détermine x par rapport aux nombres d'enfants
    # Si enfant, x est relatif par rapport au x du parent
    # Si 2nd couple, x est relatif par rapport au 1er x du couple
    # Vérifier si logique fonctionne, ensuite prévoir un tableau de remplissage :
    #  si position, on décale



    user_2 = User(name="Dalton", surname="Joe", email="joe.dalton@posteo.net", password="password2")
    user_2.verified = True
    family_tree_2 = FamilyTree(title="Family Dalton", family_name="Dalton")
    db.session.add(user_2)
    db.session.add(family_tree_2)
    db.session.flush()
    db.session.execute(
        insert(association_user_ft).values(
            id_user=user_2.id_user, id_family_tree=family_tree_2.id_family_tree, role="editor"
        )
    )

    user_demo = User(name="Demo", surname="User", email="demo@demo.com", password="demo")
    user_demo.verified = True
    db.session.add(user_demo)

    db.session.commit()
    lg.warning('Database initialized!')
