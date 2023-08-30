from flask import Flask
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config.from_object("config")
app.config["JWT_SECRET_KEY"] = "F6*99s5*y*v6a45oyN#b$%ipWe"

db = SQLAlchemy(app)

# We need to make sure Flask knows about its views and models before we run
# the app, so we import them. We could do it earlier, but there's
# a risk that we may run into circular dependencies, so we do it at the
# last minute here.
from app import views, models
