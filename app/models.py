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
        backref=db.backref("user")
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
    family_tree_cells = db.relationship("FamilyTreeCell", backref=db.backref("family_tree"))

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
    deathday = db.Column(db.DateTime, nullable=True)
    generation = db.Column(db.Integer)
    id_family_tree = db.Column(db.ForeignKey("family_tree.id_family_tree", ondelete="CASCADE"))
    pictures = db.relationship("Picture", backref=db.backref("family_tree_cell"))
    parent = db.relationship(
        "FamilyTreeCell",
        secondary="association_parent_child",
        primaryjoin="association_parent_child.c.id_family_tree_cell_parent == FamilyTreeCell.id_family_tree_cell",
        secondaryjoin="association_parent_child.c.id_family_tree_cell_child == FamilyTreeCell.id_family_tree_cell",
        backref=db.backref("parents")
    )
    couple = db.relationship(
        "FamilyTreeCell",
        secondary="association_couple",
        primaryjoin="association_couple.c.id_family_tree_cell_couple_1 == FamilyTreeCell.id_family_tree_cell",
        secondaryjoin="association_couple.c.id_family_tree_cell_couple_2 == FamilyTreeCell.id_family_tree_cell",
        backref=db.backref("couples")
    )

    def __init__(self, name: str, surnames: str, birthday: str, jobs: str, comments: str, generation: int, deathday: str = None):
        self.name = name
        self.surnames = surnames
        self.birthday = datetime.strptime(birthday, "%d/%m/%Y")
        self.deathday = datetime.strptime(deathday, "%d/%m/%Y") if deathday else deathday
        self.jobs = jobs
        self.comments = comments
        self.generation = generation


class Picture(db.Model):
    # query: db.Query  # autocomplete
    id_picture = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String, nullable=False)
    picture_date = db.Column(db.DateTime, nullable=False)
    comments = db.Column(db.String, nullable=False)
    header_picture = db.Column(db.Boolean, default=False)
    id_family_tree_cell = db.Column(db.ForeignKey("family_tree_cell.id_family_tree_cell", ondelete="CASCADE"))

    def __init__(self, filename: str, picture_date: str, comments: str, header_picture: str):
        self.filename = filename
        self.picture_date = datetime.strptime(picture_date, "%d/%m/%Y")
        self.comments = comments
        self.header_picture = eval(header_picture)


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
    user_1.family_trees.append(family_tree_1)

    # determination of x and y
    # sort by birthday
    # Loop on family_tree_cells :
    # 1er enregistrement, on détermine x par rapport aux nombres d'enfants
    # Si enfant, x est relatif par rapport au x du parent
    # Si 2nd couple, x est relatif par rapport au 1er x du couple
    # Vérifier si logique fonctionne, ensuite prévoir un tableau de remplissage : si position, on décale



    db.session.add(user_1)

    user_2 = User(name="Dalton", surname="Joe", email="joe.dalton@posteo.net", password="password2")
    family_tree_2 = FamilyTree(title="Family Dalton", family_name="Dalton")
    user_2.family_trees.append(family_tree_2)
    db.session.add(user_2)

    db.session.commit()
    lg.warning('Database initialized!')
