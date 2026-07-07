"""Regression tests: a 'viewer' must never be able to write, only read.

These lock in the fix to VerifyUserAuthorized (app/views/verify_user_authorized.py)
and to get_update_delete_family_tree (app/views/family_tree_view.py), which
previously only checked tree membership, not role, for write methods.
"""
import pytest
from sqlalchemy import insert

from app import db as _db
from app.models import User, association_user_ft


@pytest.fixture
def family_tree_id(client, auth_headers):
    response = client.post('/family_tree', json={'title': 'Test Tree', 'family_name': 'Test'}, headers=auth_headers)
    assert response.status_code == 201
    return response.get_json()['data']['id_family_tree']


@pytest.fixture
def cell_id(client, auth_headers, family_tree_id):
    response = client.post(
        f'/family_trees/{family_tree_id}/family_tree_cells',
        json={'name': 'Alice', 'surnames': 'Dupont', 'generation': 1},
        headers=auth_headers,
    )
    assert response.status_code == 201
    return response.get_json()['data']['id_family_tree_cell']


@pytest.fixture
def viewer_headers(client, family_tree_id):
    client.post('/user', json={
        'name': 'Viewer', 'surname': 'User',
        'email': 'viewer_perm@test.com', 'password': 'pw',
    })
    viewer = User.query.filter_by(email='viewer_perm@test.com').first()
    viewer.verified = True
    _db.session.commit()
    _db.session.execute(
        insert(association_user_ft).values(
            id_user=viewer.id_user,
            id_family_tree=family_tree_id,
            role='viewer',
        )
    )
    _db.session.commit()
    login = client.post('/login', json={'email': 'viewer_perm@test.com', 'password': 'pw'})
    return {'Authorization': f"Bearer {login.get_json()['data']}"}


def test_viewer_cannot_create_cell(client, viewer_headers, family_tree_id):
    response = client.post(
        f'/family_trees/{family_tree_id}/family_tree_cells',
        json={'name': 'Bob', 'surnames': 'Martin', 'generation': 1},
        headers=viewer_headers,
    )
    assert response.status_code == 403


def test_viewer_cannot_update_cell(client, viewer_headers, family_tree_id, cell_id):
    response = client.put(
        f'/family_trees/{family_tree_id}/family_tree_cells/{cell_id}',
        json={'name': 'Hacked'},
        headers=viewer_headers,
    )
    assert response.status_code == 403


def test_viewer_cannot_delete_cell(client, viewer_headers, family_tree_id, cell_id):
    response = client.delete(
        f'/family_trees/{family_tree_id}/family_tree_cells/{cell_id}',
        headers=viewer_headers,
    )
    assert response.status_code == 403


def test_viewer_can_still_read_cells(client, viewer_headers, family_tree_id, cell_id):
    response = client.get(
        f'/family_trees/{family_tree_id}/family_tree_cells',
        headers=viewer_headers,
    )
    assert response.status_code == 200


def test_viewer_cannot_rename_family_tree(client, viewer_headers, family_tree_id):
    response = client.put(
        f'/family_trees/{family_tree_id}',
        json={'title': 'Hacked title'},
        headers=viewer_headers,
    )
    assert response.status_code == 403


def test_viewer_cannot_delete_family_tree(client, viewer_headers, family_tree_id):
    response = client.delete(
        f'/family_trees/{family_tree_id}',
        headers=viewer_headers,
    )
    assert response.status_code == 403


def test_viewer_can_still_read_family_tree(client, viewer_headers, family_tree_id):
    response = client.get(
        f'/family_trees/{family_tree_id}',
        headers=viewer_headers,
    )
    assert response.status_code == 200
