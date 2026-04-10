#! /usr/bin/env python
from app import ma
from app.models import User, FamilyTree, FamilyTreeCell, Picture, Pet, PetPicture


class UserSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = User
        fields = ("id_user", "name", "surname", "email")


user_schema = UserSchema()


class FamilyTreeSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = FamilyTree
        fields = ("id_family_tree", "title", "family_name")


family_tree_schema = FamilyTreeSchema()
family_trees_schema = FamilyTreeSchema(many=True)


class FamilyTreeCellSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = FamilyTreeCell
        include_fk = True
        fields = ("id_family_tree_cell", "name", "surnames", "birthday", "deathday", "jobs", "comments", "generation", "id_family_tree")


family_tree_cell_schema = FamilyTreeCellSchema()


class PictureSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Picture
        include_fk = True
        fields = ("id_picture", "filename", "picture_date", "comments", "header_picture", "id_family_tree_cell")


picture_schema = PictureSchema()
pictures_schema = PictureSchema(many=True)


class PetSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Pet
        include_fk = True
        fields = ("id_pet", "name", "species", "birthday", "deathday", "comments", "id_family_tree_cell")


pet_schema = PetSchema()
pets_schema = PetSchema(many=True)


class PetPictureSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = PetPicture
        include_fk = True
        fields = ("id_pet_picture", "filename", "picture_date", "comments", "id_pet")


pet_picture_schema = PetPictureSchema()
pets_pictures_schema = PetPictureSchema(many=True)
