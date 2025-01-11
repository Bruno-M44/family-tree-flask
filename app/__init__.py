from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from flask_jwt_extended import JWTManager
from flask_marshmallow import Marshmallow
from flask_cors import CORS
from datetime import timedelta

db = SQLAlchemy()
jwt = JWTManager()
ma = Marshmallow()


def create_app():
    app = Flask(__name__)
    app.config.from_object("config")
    app.config["JWT_SECRET_KEY"] = "F6*99s5*y*v6a45oyN#b$%ipWe"
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=1) # TODO : to review
    app.config["JWT_REFRESH_TOKEN_EXPIRES"] = timedelta(hours=1)
    # app.config['APPLICATION_ROOT'] = '/views'

    CORS(app)
    db.init_app(app)
    jwt.init_app(app)
    ma.init_app(app)

    from app.views.login_view import login_app
    from app.views.user_view import user_app
    from app.views.family_tree_view import family_tree_app
    from app.views.family_tree_cell_view import family_tree_cell_app
    from app.views.picture_view import picture_app
    from app.views.command import command_app

    app.register_blueprint(login_app)
    app.register_blueprint(user_app)
    app.register_blueprint(family_tree_app)
    app.register_blueprint(family_tree_cell_app)
    app.register_blueprint(picture_app)
    app.register_blueprint(command_app)

    return app
