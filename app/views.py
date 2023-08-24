from flask import render_template
from .models import User
from . import models
from run import app


@app.route('/')
def index():
    users = User.query.all()
    return render_template("index.html",
                           user_name=users)


@app.cli.command()
def init_db():
    models.init_db()
