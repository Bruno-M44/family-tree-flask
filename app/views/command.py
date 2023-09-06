from flask import Blueprint
from .. import models


app = Blueprint("app", __name__)


@app.cli.command()
def init_db():
    models.init_db()
