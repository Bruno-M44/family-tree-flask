#! /usr/bin/env python
'''Commands usable by the application'''
import click
from flask import Blueprint
from .. import models


command_app = Blueprint("command_app", __name__)


@command_app.cli.command()
def init_db():
    '''Drop and create DB with a few records'''
    models.init_db()


@command_app.cli.command()
def create_all():
    '''Create tables that do not exist'''
    models.create_all()

@command_app.cli.command()
@click.argument("table")
def drop_table(table: str):
    '''Drop specific table'''
    models.drop_table(table=table)
