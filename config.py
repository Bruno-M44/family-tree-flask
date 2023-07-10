import os

basedir = os.path.abspath(os.path.dirname(__file__))
print('sqlite:///' + os.path.join(basedir, 'family-tree-flask.db'))
SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'family-tree-flask.db')
