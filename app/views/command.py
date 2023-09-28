from flask import Blueprint
from .. import models


command_app = Blueprint("command_app", __name__)


@command_app.cli.command()
def init_db():
    models.init_db()
