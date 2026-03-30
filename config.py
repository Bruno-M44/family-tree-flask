from os import environ

SQLALCHEMY_DATABASE_URI = environ.get('DB_URL')
SQLALCHEMY_ENGINE_OPTIONS = {
    "pool_size": 5,
    "max_overflow": 5,
    "pool_pre_ping": True,
    "pool_recycle": 300,
}
