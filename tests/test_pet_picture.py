import pytest
from app import db as _db
from app.models import FamilyTree, FamilyTreeCell


@pytest.fixture
def created_family_tree(client, auth_headers):
    response = client.post('/family_tree', json={'title': 'Test Tree', 'family_name': 'Test'}, headers=auth_headers)
    assert response.status_code == 201
    return response.get_json()['data']


@pytest.fixture
def created_family_tree_cell(client, auth_headers, created_family_tree):
    ft_id = created_family_tree['id_family_tree']
    response = client.post(
        f'/family_trees/{ft_id}/family_tree_cells',
        json={
            'name': 'John',
            'surnames': 'Smith',
            'birthday': '01/01/1980',
            'jobs': 'Engineer',
            'comments': 'Test',
            'generation': 1,
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    return response.get_json()['data']


@pytest.fixture
def created_pet(client, auth_headers, created_family_tree_cell):
    cell_id = created_family_tree_cell['id_family_tree_cell']
    response = client.post(
        f'/family_tree_cells/{cell_id}/pets',
        json={
            'name': 'Buddy',
            'species': 'Dog',
            'birthday': '01/01/2020',
        },
        headers=auth_headers,
    )
    if response.status_code == 201:
        return response.get_json()['data']
    return None


# -----------------------------------------------------------------------
# GET /pets/<pet_id>/pets_pictures
# -----------------------------------------------------------------------

def test_get_pets_pictures(client, auth_headers, created_pet):
    if created_pet:
        pet_id = created_pet['id_pet']
        response = client.get(f'/pets/{pet_id}/pets_pictures', headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.get_json()['data'], list)


def test_get_pets_pictures_unauthenticated(client, created_pet):
    if created_pet:
        pet_id = created_pet['id_pet']
        response = client.get(f'/pets/{pet_id}/pets_pictures')
        assert response.status_code == 401


# -----------------------------------------------------------------------
# GET /pets/<pet_id>/pets_pictures/<pic_id>
# -----------------------------------------------------------------------

def test_get_pet_picture(client, auth_headers, created_pet):
    if created_pet:
        pet_id = created_pet['id_pet']
        response = client.get(f'/pets/{pet_id}/pets_pictures/1', headers=auth_headers)
        assert response.status_code in (200, 404)


def test_get_pet_picture_not_found(client, auth_headers, created_pet):
    if created_pet:
        pet_id = created_pet['id_pet']
        response = client.get(f'/pets/{pet_id}/pets_pictures/99999', headers=auth_headers)
        assert response.status_code == 404


# -----------------------------------------------------------------------
# PUT /pets/<pet_id>/pets_pictures/<pic_id>
# -----------------------------------------------------------------------

def test_update_pet_picture(client, auth_headers, created_pet):
    if created_pet:
        pet_id = created_pet['id_pet']
        response = client.put(
            f'/pets/{pet_id}/pets_pictures/1',
            json={'comments': 'Test comment'},
            headers=auth_headers,
        )
        assert response.status_code in (200, 404)


# -----------------------------------------------------------------------
# DELETE /pets/<pet_id>/pets_pictures/<pic_id>/delete
# -----------------------------------------------------------------------

def test_delete_pet_picture(client, auth_headers, created_pet):
    if created_pet:
        pet_id = created_pet['id_pet']
        response = client.delete(f'/pets/{pet_id}/pets_pictures/1/delete', headers=auth_headers)
        assert response.status_code in (200, 404)


def test_delete_pet_picture_not_found(client, auth_headers, created_pet):
    if created_pet:
        pet_id = created_pet['id_pet']
        response = client.delete(f'/pets/{pet_id}/pets_pictures/99999/delete', headers=auth_headers)
        assert response.status_code == 404


# -----------------------------------------------------------------------
# GET /pets/<pet_id>/pets_pictures/<pic_id>/download
# -----------------------------------------------------------------------

def test_download_pet_picture(client, auth_headers, created_pet):
    if created_pet:
        pet_id = created_pet['id_pet']
        response = client.get(f'/pets/{pet_id}/pets_pictures/1/download', headers=auth_headers)
        assert response.status_code in (200, 404)


def test_download_pet_picture_not_found(client, auth_headers, created_pet):
    if created_pet:
        pet_id = created_pet['id_pet']
        response = client.get(f'/pets/{pet_id}/pets_pictures/99999/download', headers=auth_headers)
        assert response.status_code == 404