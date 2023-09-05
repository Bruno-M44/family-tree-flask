from .. import models
from run import app


@app.cli.command()
def init_db():
    models.init_db()
