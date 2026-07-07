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

import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration

db = SQLAlchemy()
jwt = JWTManager()
ma = Marshmallow()

if environ.get('GLITCHTIP_DSN'):
    sentry_sdk.init(
        dsn=environ['GLITCHTIP_DSN'],
        integrations=[FlaskIntegration()],
        traces_sample_rate=0,
        environment='development' if environ.get('FLASK_DEBUG') else 'production',
    )


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

    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(jwt_header, jwt_payload):
        from app.models import TokenBlocklist
        return TokenBlocklist.query.filter_by(jti=jwt_payload["jti"]).first() is not None

    from app.views.login_view import login_app
    from app.views.user_view import user_app
    from app.views.family_tree_view import family_tree_app
    from app.views.family_tree_cell_view import family_tree_cell_app
    from app.views.picture_view import picture_app
    from app.views.pet_view import pet_app
    from app.views.pet_picture_view import pet_picture_app
    from app.views.command import command_app
    from app.views.invitation_view import invitation_app
    from app.views.hidden_branches_view import hidden_branches_app
    from app.views.gedcom_view import gedcom_app

    app.register_blueprint(login_app)
    app.register_blueprint(user_app)
    app.register_blueprint(invitation_app)
    app.register_blueprint(hidden_branches_app)
    app.register_blueprint(gedcom_app)
    app.register_blueprint(family_tree_app)
    app.register_blueprint(family_tree_cell_app)
    app.register_blueprint(picture_app)
    app.register_blueprint(pet_app)
    app.register_blueprint(pet_picture_app)
    app.register_blueprint(command_app)

    from app.db_migrations import run_migrations
    with app.app_context():
        run_migrations(db)

    return app
