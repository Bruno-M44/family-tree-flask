from datetime import datetime
import logging as lg

from app import db


association_user_ft = db.Table(
    "association_user_ft",
    db.Column("id_user", db.Integer, db.ForeignKey("user.id_user", ondelete="CASCADE"), primary_key=True),
    db.Column("id_family_tree", db.Integer, db.ForeignKey(
        "family_tree.id_family_tree", ondelete="CASCADE"), primary_key=True),
    db.Column("permission", db.String, nullable=False, default="view")
)


class User(db.Model):
    # query: db.Query  # autocomplete
    id_user = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    surname = db.Column(db.String, nullable=False)
    email = db.Column(db.String, nullable=False)
    password = db.Column(db.String, nullable=False)
    family_trees = db.relationship(
        "FamilyTree",
        secondary=association_user_ft,
        backref=db.backref("user", cascade='delete')
    )

    def __init__(self, name, surname, email, password):
        self.name = name
        self.surname = surname
        self.email = email
        self.password = password


class FamilyTree(db.Model):
    # query: db.Query  # autocomplete
    id_family_tree = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String, nullable=False)
    family_name = db.Column(db.String, nullable=False)
    family_tree_cells = db.relationship("FamilyTreeCell", backref=db.backref("family_tree", cascade='delete'))

    def __init__(self, title, family_name):
        self.title = title
        self.family_name = family_name


class FamilyTreeCell(db.Model):
    # query: db.Query  # autocomplete
    id_family_tree_cell = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    surnames = db.Column(db.String, nullable=False)
    birthday = db.Column(db.DateTime, nullable=False)
    jobs = db.Column(db.String, nullable=False)
    comments = db.Column(db.String, nullable=False)
    id_family_tree = db.Column(db.ForeignKey("family_tree.id_family_tree", ondelete="CASCADE"))
    pictures = db.relationship("Picture", backref=db.backref("family_tree_cell", cascade='delete'))

    def __init__(self, name: str, surnames: str, birthday: str, jobs: str, comments: str):
        self.name = name
        self.surnames = surnames
        self.birthday = datetime.strptime(birthday, "%d/%m/%Y")
        self.jobs = jobs
        self.comments = comments

    # def __setattr__(self, key, value):
    #     print("---key :", key)
    #     if key == "birthday":
    #         print(key, value, type(value))
    #         super(FamilyTreeCell, self).__setattr__(key, datetime.strptime(value, "%d/%m/%Y"))
    #     else:
    #         super(FamilyTreeCell, self).__setattr__(key, value)


class Picture(db.Model):
    # query: db.Query  # autocomplete
    id_picture = db.Column(db.Integer, primary_key=True)
    picture_date = db.Column(db.DateTime, nullable=False)
    comments = db.Column(db.String, nullable=False)
    id_family_tree_cell = db.Column(db.ForeignKey("family_tree_cell.id_family_tree_cell", ondelete="CASCADE"))

    def __init__(self, picture_date, comments):
        self.picture_date = datetime.strptime(picture_date, "%d/%m/%Y")
        self.comments = comments

    # def __setattr__(self, key, value):
    #     if key == "picture_date":
    #         super(Picture, self).__setattr__(key, datetime.strptime(str(value), "%d/%m/%Y"))
    #     else:
    #         super(Picture, self).__setattr__(key, value)


def init_db():
    db.drop_all()
    db.create_all()
    user_1 = User(name="Smith", surname="John", email="john.smith@gmail.com", password="password1")
    family_tree_1 = FamilyTree(title="Family Smith", family_name="Smith")
    family_tree_cell_1 = FamilyTreeCell(
        name="Smith",
        surnames="John, Johnny",
        birthday="14/07/1983",
        jobs="engineer",
        comments="my father"
    )
    picture_1 = Picture(
        picture_date="04/10/1990",
        comments="7 years"
    )
    family_tree_cell_1.pictures.append(picture_1)
    family_tree_1.family_tree_cells.append(family_tree_cell_1)
    user_1.family_trees.append(family_tree_1)
    db.session.add(user_1)

    user_2 = User(name="Dalton", surname="Joe", email="joe.dalton@posteo.net", password="password2")
    family_tree_2 = FamilyTree(title="Family Dalton", family_name="Dalton")
    user_2.family_trees.append(family_tree_2)
    db.session.add(user_2)

    db.session.commit()
    lg.warning('Database initialized!')
