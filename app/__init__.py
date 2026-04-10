#! /usr/bin/env python
import logging
from os import environ
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


def create_app(test_config=None):
    app = Flask(__name__)
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    app.config.from_object("config")
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=1)
    app.config["JWT_REFRESH_TOKEN_EXPIRES"] = timedelta(hours=1)

    if test_config:
        app.config.update(test_config)
        app.config.pop('SQLALCHEMY_ENGINE_OPTIONS', None)

    CORS(app,
         origins=environ.get('CORS_ORIGINS', '*'),
         allow_headers=['Authorization', 'Content-Type'])
    db.init_app(app)
    jwt.init_app(app)
    ma.init_app(app)

    from app.views.login_view import login_app
    from app.views.user_view import user_app
    from app.views.family_tree_view import family_tree_app
    from app.views.family_tree_cell_view import family_tree_cell_app
    from app.views.picture_view import picture_app
    from app.views.pet_view import pet_app
    from app.views.pet_picture_view import pet_picture_app
    from app.views.command import command_app

    app.register_blueprint(login_app)
    app.register_blueprint(user_app)
    app.register_blueprint(family_tree_app)
    app.register_blueprint(family_tree_cell_app)
    app.register_blueprint(picture_app)
    app.register_blueprint(pet_app)
    app.register_blueprint(pet_picture_app)
    app.register_blueprint(command_app)

    return app
