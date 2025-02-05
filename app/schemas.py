from app import ma


class UserSchema(ma.Schema):
    class Meta:
        fields = ("id_user", "name", "surname", "email")


user_schema = UserSchema()


class FamilyTreeSchema(ma.Schema):
    class Meta:
        fields = ("id_family_tree", "title", "family_name")


family_tree_schema = FamilyTreeSchema()
family_trees_schema = FamilyTreeSchema(many=True)


class FamilyTreeCellSchema(ma.Schema):
    class Meta:
        fields = ("id_family_tree_cell", "name", "surnames", "birthday", "deathday", "jobs", "comments", "generation", "id_family_tree")


family_tree_cell_schema = FamilyTreeCellSchema()


class PictureSchema(ma.Schema):
    class Meta:
        fields = ("id_picture", "filename", "picture_date", "comments", "header_picture", "id_family_tree_cell")


picture_schema = PictureSchema()
pictures_schema = PictureSchema(many=True)
