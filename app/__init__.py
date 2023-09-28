from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from flask_jwt_extended import JWTManager
from flask_marshmallow import Marshmallow

db = SQLAlchemy()
jwt = JWTManager()
ma = Marshmallow()


def create_app():
    app = Flask(__name__)
    app.config.from_object("config")
    app.config["JWT_SECRET_KEY"] = "F6*99s5*y*v6a45oyN#b$%ipWe"
    # app.config['APPLICATION_ROOT'] = '/views'

    db.init_app(app)
    jwt.init_app(app)
    ma.init_app(app)

    # Ensure FOREIGN KEY for sqlite3
    def _fk_pragma_on_connect(dbapi_con, con_record):  # noqa
        dbapi_con.execute('pragma foreign_keys=ON')

    with app.app_context():
        event.listen(db.engine, "connect", _fk_pragma_on_connect)

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
