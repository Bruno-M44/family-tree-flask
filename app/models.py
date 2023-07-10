from flask_sqlalchemy import SQLAlchemy
import logging as lg

from .views import app

# Create database connection object
db = SQLAlchemy(app)


association_user_ft = db.Table(
    "association_user_ft",
    db.Column("user_id", db.Integer, db.ForeignKey("user.id"), primary_key=True),
    db.Column("family_tree_id", db.Integer, db.ForeignKey("family_tree.id"), primary_key=True),
    db.Column("permission", db.String, nullable=False, default="view")
)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    surname = db.Column(db.String, nullable=False)
    email = db.Column(db.String, nullable=False)
    family_trees = db.relationship(
        "FamilyTree",
        secondary=association_user_ft
    )

    def __init__(self, name, surname, email):
        self.name = name
        self.surname = surname
        self.email = email


class FamilyTree(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String, nullable=False)
    family_name = db.Column(db.String, nullable=False)

    def __init__(self, title, family_name):
        self.title = title
        self.family_name = family_name


def init_db():
    db.drop_all()
    db.create_all()
    user_1 = User(name="Smith", surname="John", email="john.smith@gmail.com")
    family_tree_1 = FamilyTree(title="Family Smith", family_name="Smith")
    user_1.family_trees.append(family_tree_1)
    db.session.add(user_1)

    user_2 = User(name="Dalton", surname="Joe", email="joe.dalton@posteo.net")
    family_tree_2 = FamilyTree(title="Family Dalton", family_name="Dalton")
    user_2.family_trees.append(family_tree_2)
    db.session.add(user_2)

    db.session.commit()
    lg.warning('Database initialized!')
