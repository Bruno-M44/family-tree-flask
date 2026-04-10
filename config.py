from os import environ
from dotenv import load_dotenv


load_dotenv()  # charge le .env dans l'environnement

SQLALCHEMY_DATABASE_URI = environ.get('DB_URL')
JWT_SECRET_KEY = environ.get('JWT_SECRET_KEY')
SQLALCHEMY_ENGINE_OPTIONS = {
    "pool_size": 5,
    "max_overflow": 5,
    "pool_pre_ping": True,
    "pool_recycle": 300,
}
