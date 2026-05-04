import pytest
from app import db as _db
from app.models import Pet


@pytest.fixture
def created_pet(client, auth_headers, created_family_tree_cell):
    cell_id = created_family_tree_cell['id_family_tree_cell']
    response = client.post(
        f'/family_tree_cells/{cell_id}/pets',
        json={
            'name': 'Buddy',
            'species': 'Dog',
            'birthday': '01/01/2020',
            'comments': 'Loyal dog',
        },
        headers=auth_headers,
    )
    if response.status_code == 201:
        return response.get_json()['data']
    return None


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


# -----------------------------------------------------------------------
# GET /family_tree_cells/<cell_id>/pets
# -----------------------------------------------------------------------

def test_get_pets(client, auth_headers, created_family_tree_cell):
    cell_id = created_family_tree_cell['id_family_tree_cell']
    response = client.get(f'/family_tree_cells/{cell_id}/pets', headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.get_json()['data'], list)


def test_get_pets_unauthenticated(client, created_family_tree_cell):
    cell_id = created_family_tree_cell['id_family_tree_cell']
    response = client.get(f'/family_tree_cells/{cell_id}/pets')
    assert response.status_code == 401


# -----------------------------------------------------------------------
# POST /family_tree_cells/<cell_id>/pets
# -----------------------------------------------------------------------

def test_create_pet(client, auth_headers, created_family_tree_cell):
    cell_id = created_family_tree_cell['id_family_tree_cell']
    response = client.post(
        f'/family_tree_cells/{cell_id}/pets',
        json={
            'name': 'Buddy',
            'species': 'Dog',
            'birthday': '01/01/2020',
            'comments': 'Loyal dog',
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.get_json()['data']
    assert data['name'] == 'Buddy'
    assert data['species'] == 'Dog'


def test_create_pet_missing_fields(client, auth_headers, created_family_tree_cell):
    cell_id = created_family_tree_cell['id_family_tree_cell']
    response = client.post(
        f'/family_tree_cells/{cell_id}/pets',
        json={},
        headers=auth_headers,
    )
    assert response.status_code == 400


def test_create_pet_invalid_date(client, auth_headers, created_family_tree_cell):
    cell_id = created_family_tree_cell['id_family_tree_cell']
    response = client.post(
        f'/family_tree_cells/{cell_id}/pets',
        json={
            'name': 'Buddy',
            'species': 'Dog',
            'birthday': 'invalid-date',
        },
        headers=auth_headers,
    )
    assert response.status_code == 400


# -----------------------------------------------------------------------
# GET /family_tree_cells/<cell_id>/pets/<pet_id>
# -----------------------------------------------------------------------

def test_get_pet(client, auth_headers, created_pet):
    if created_pet:
        cell_id = created_pet['id_family_tree_cell']
        pet_id = created_pet['id_pet']
        response = client.get(f'/family_tree_cells/{cell_id}/pets/{pet_id}', headers=auth_headers)
        assert response.status_code == 200
        assert response.get_json()['data']['name'] == 'Buddy'


def test_get_pet_not_found(client, auth_headers, created_family_tree_cell):
    cell_id = created_family_tree_cell['id_family_tree_cell']
    response = client.get(f'/family_tree_cells/{cell_id}/pets/99999', headers=auth_headers)
    assert response.status_code == 404


# -----------------------------------------------------------------------
# PUT /family_tree_cells/<cell_id>/pets/<pet_id>
# -----------------------------------------------------------------------

def test_update_pet(client, auth_headers, created_pet):
    if created_pet:
        cell_id = created_pet['id_family_tree_cell']
        pet_id = created_pet['id_pet']
        response = client.put(
            f'/family_tree_cells/{cell_id}/pets/{pet_id}',
            json={'name': 'Max'},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.get_json()['data']['name'] == 'Max'


# -----------------------------------------------------------------------
# DELETE /family_tree_cells/<cell_id>/pets/<pet_id>
# -----------------------------------------------------------------------

def test_delete_pet(client, auth_headers, created_pet):
    if created_pet:
        cell_id = created_pet['id_family_tree_cell']
        pet_id = created_pet['id_pet']
        response = client.delete(f'/family_tree_cells/{cell_id}/pets/{pet_id}', headers=auth_headers)
        assert response.status_code == 200
        # Verify it no longer exists
        response = client.get(f'/family_tree_cells/{cell_id}/pets/{pet_id}', headers=auth_headers)
        assert response.status_code == 404


def test_delete_pet_not_found(client, auth_headers, created_family_tree_cell):
    cell_id = created_family_tree_cell['id_family_tree_cell']
    response = client.delete(f'/family_tree_cells/{cell_id}/pets/99999', headers=auth_headers)
    assert response.status_code == 404