from flask_marshmallow import Marshmallow

from run import app


ma = Marshmallow(app)


class UsersSchema(ma.Schema):
    class Meta:
        fields = ("id_user", "name", "surname", "email")


users_schema = UsersSchema(many=True)
