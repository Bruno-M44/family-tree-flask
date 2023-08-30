from flask_marshmallow import Marshmallow

from run import app


ma = Marshmallow(app)


class UserSchema(ma.Schema):
    class Meta:
        fields = ("id_user", "name", "surname", "email")


user_schema = UserSchema()
users_schema = UserSchema(many=True)
