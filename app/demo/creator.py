"""Lie le nouvel utilisateur à l'arbre démo partagé (celui de demo@demo.com)."""

from app import db
from app.models import User, association_user_ft
from sqlalchemy import insert, select


def create_demo_family_tree(user):
    """Relie le nouvel utilisateur à l'arbre démo existant en mode viewer."""
    demo_user = User.query.filter_by(email='demo@demo.com').first()
    if not demo_user:
        return

    row = db.session.execute(
        select(association_user_ft.c.id_family_tree).where(
            association_user_ft.c.id_user == demo_user.id_user
        )
    ).first()

    if not row:
        return

    db.session.execute(
        insert(association_user_ft).values(
            id_user=user.id_user,
            id_family_tree=row[0],
            role='viewer',
        )
    )
    db.session.flush()
