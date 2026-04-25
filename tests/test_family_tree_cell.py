import pytest
from app import db as _db
from app.models import FamilyTree, FamilyTreeCell, association_parent_child, association_couple


USER_1 = {
    'name': 'Dutronc',
    'surname': 'Thomas',
    'email': 'thomas.dutronc@gmail.com',
    'password': 'password1',
}


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
            'comments': 'Test comment',
            'generation': 1,
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    return response.get_json()['data']


@pytest.fixture
def second_family_tree_cell(client, auth_headers, created_family_tree):
    ft_id = created_family_tree['id_family_tree']
    response = client.post(
        f'/family_trees/{ft_id}/family_tree_cells',
        json={
            'name': 'Jane',
            'surnames': 'Doe',
            'birthday': '01/01/1985',
            'jobs': 'Doctor',
            'comments': '',
            'generation': 1,
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    return response.get_json()['data']


@pytest.fixture
def child_family_tree_cell(client, auth_headers, created_family_tree, created_family_tree_cell):
    ft_id = created_family_tree['id_family_tree']
    parent_id = created_family_tree_cell['id_family_tree_cell']
    response = client.post(
        f'/family_trees/{ft_id}/family_tree_cells',
        json={
            'name': 'Child',
            'surnames': 'Smith',
            'birthday': '01/01/2010',
            'jobs': '',
            'comments': '',
            'generation': 2,
            'parents': [parent_id],
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    return response.get_json()['data']


# -----------------------------------------------------------------------
# GET /family_trees/<id>/family_tree_cells
# -----------------------------------------------------------------------

def test_get_family_tree_cells(client, auth_headers, created_family_tree):
    ft_id = created_family_tree['id_family_tree']
    response = client.get(f'/family_trees/{ft_id}/family_tree_cells', headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.get_json()['data'], list)


def test_get_family_tree_cells_unauthenticated(client, created_family_tree):
    ft_id = created_family_tree['id_family_tree']
    response = client.get(f'/family_trees/{ft_id}/family_tree_cells')
    assert response.status_code == 401


def test_get_family_tree_cells_not_member(client, auth_headers, created_family_tree):
    ft_id = created_family_tree['id_family_tree']
    response = client.get(f'/family_trees/{ft_id}/family_tree_cells')
    assert response.status_code == 401


# -----------------------------------------------------------------------
# POST /family_trees/<id>/family_tree_cells
# -----------------------------------------------------------------------

def test_create_family_tree_cell(client, auth_headers, created_family_tree):
    ft_id = created_family_tree['id_family_tree']
    response = client.post(
        f'/family_trees/{ft_id}/family_tree_cells',
        json={
            'name': 'John',
            'surnames': 'Smith',
            'birthday': '01/01/1980',
            'jobs': 'Engineer',
            'comments': 'Test comment',
            'generation': 1,
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.get_json()['data']
    assert data['name'] == 'John'
    assert data['surnames'] == 'Smith'
    assert data['generation'] == 1


def test_create_family_tree_cell_missing_fields(client, auth_headers, created_family_tree):
    ft_id = created_family_tree['id_family_tree']
    response = client.post(
        f'/family_trees/{ft_id}/family_tree_cells',
        json={'name': 'John'},
        headers=auth_headers,
    )
    assert response.status_code == 400


def test_create_family_tree_cell_invalid_date(client, auth_headers, created_family_tree):
    ft_id = created_family_tree['id_family_tree']
    response = client.post(
        f'/family_trees/{ft_id}/family_tree_cells',
        json={
            'name': 'John',
            'surnames': 'Smith',
            'birthday': 'invalid-date',
            'jobs': '',
            'comments': '',
            'generation': 1,
        },
        headers=auth_headers,
    )
    assert response.status_code == 400


def test_create_family_tree_cell_with_parents(client, auth_headers, created_family_tree, created_family_tree_cell):
    ft_id = created_family_tree['id_family_tree']
    parent_id = created_family_tree_cell['id_family_tree_cell']
    response = client.post(
        f'/family_trees/{ft_id}/family_tree_cells',
        json={
            'name': 'Child',
            'surnames': 'Smith',
            'birthday': '01/01/2010',
            'jobs': '',
            'comments': '',
            'generation': 2,
            'parents': [parent_id],
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.get_json()['data']
    assert data['generation'] == 2


def test_create_family_tree_cell_with_invalid_parent(client, auth_headers, created_family_tree):
    ft_id = created_family_tree['id_family_tree']
    response = client.post(
        f'/family_trees/{ft_id}/family_tree_cells',
        json={
            'name': 'Child',
            'surnames': 'Smith',
            'birthday': '01/01/2010',
            'jobs': '',
            'comments': '',
            'generation': 2,
            'parents': [99999],
        },
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_create_family_tree_cell_with_couples(client, auth_headers, created_family_tree, created_family_tree_cell):
    ft_id = created_family_tree['id_family_tree']
    person_id = created_family_tree_cell['id_family_tree_cell']
    response = client.post(
        f'/family_trees/{ft_id}/family_tree_cells',
        json={
            'name': 'Spouse',
            'surnames': 'Smith',
            'birthday': '01/01/1982',
            'jobs': '',
            'comments': '',
            'generation': 1,
            'couples': [person_id],
        },
        headers=auth_headers,
    )
    assert response.status_code == 201


# -----------------------------------------------------------------------
# GET /family_trees/<id>/family_tree_cells/<cell_id>
# -----------------------------------------------------------------------

def test_get_family_tree_cell(client, auth_headers, created_family_tree_cell):
    cell_id = created_family_tree_cell['id_family_tree_cell']
    ft_id = created_family_tree_cell['id_family_tree']
    response = client.get(f'/family_trees/{ft_id}/family_tree_cells/{cell_id}', headers=auth_headers)
    assert response.status_code == 200
    assert response.get_json()['data']['name'] == 'John'


def test_get_family_tree_cell_not_found(client, auth_headers, created_family_tree):
    ft_id = created_family_tree['id_family_tree']
    response = client.get(f'/family_trees/{ft_id}/family_tree_cells/99999', headers=auth_headers)
    assert response.status_code == 404


# -----------------------------------------------------------------------
# PUT /family_trees/<id>/family_tree_cells/<cell_id>
# -----------------------------------------------------------------------

def test_update_family_tree_cell(client, auth_headers, created_family_tree_cell):
    cell_id = created_family_tree_cell['id_family_tree_cell']
    ft_id = created_family_tree_cell['id_family_tree']
    response = client.put(
        f'/family_trees/{ft_id}/family_tree_cells/{cell_id}',
        json={'name': 'Updated Name'},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.get_json()['data']['name'] == 'Updated Name'


def test_update_family_tree_cell_maiden_name(client, auth_headers, created_family_tree_cell):
    cell_id = created_family_tree_cell['id_family_tree_cell']
    ft_id = created_family_tree_cell['id_family_tree']
    response = client.put(
        f'/family_trees/{ft_id}/family_tree_cells/{cell_id}',
        json={'maiden_name': 'Doe'},
        headers=auth_headers,
    )
    assert response.status_code == 200


# -----------------------------------------------------------------------
# DELETE /family_trees/<id>/family_tree_cells/<cell_id>
# -----------------------------------------------------------------------

def test_delete_family_tree_cell(client, auth_headers, created_family_tree_cell):
    cell_id = created_family_tree_cell['id_family_tree_cell']
    ft_id = created_family_tree_cell['id_family_tree']
    response = client.delete(f'/family_trees/{ft_id}/family_tree_cells/{cell_id}', headers=auth_headers)
    assert response.status_code == 200
    # Verify it no longer exists
    response = client.get(f'/family_trees/{ft_id}/family_tree_cells/{cell_id}', headers=auth_headers)
    assert response.status_code == 404


def test_delete_family_tree_cell_with_children(
    client, auth_headers, created_family_tree, created_family_tree_cell
):
    """Delete a parent cell that has children - should work."""
    ft_id = created_family_tree['id_family_tree']
    parent_id = created_family_tree_cell['id_family_tree_cell']
    child = client.post(
        f'/family_trees/{ft_id}/family_tree_cells',
        json={
            'name': 'Child',
            'surnames': 'Smith',
            'birthday': '01/01/2010',
            'jobs': '',
            'comments': '',
            'generation': 2,
            'parents': [parent_id],
        },
        headers=auth_headers,
    )
    assert child.status_code == 201
    response = client.delete(f'/family_trees/{ft_id}/family_tree_cells/{parent_id}', headers=auth_headers)
    assert response.status_code == 200


# -----------------------------------------------------------------------
# POST /family_trees/<id>/family_tree_cells/<cell_id>/parent
# -----------------------------------------------------------------------

def test_add_parent(client, auth_headers, created_family_tree, second_family_tree_cell, created_family_tree_cell):
    ft_id = created_family_tree['id_family_tree']
    cell_id = second_family_tree_cell['id_family_tree_cell']
    parent_id = created_family_tree_cell['id_family_tree_cell']
    response = client.post(
        f'/family_trees/{ft_id}/family_tree_cells/{cell_id}/parent',
        json={'parent_id': parent_id},
        headers=auth_headers,
    )
    assert response.status_code == 201


def test_add_parent_missing_field(client, auth_headers, created_family_tree_cell):
    cell_id = created_family_tree_cell['id_family_tree_cell']
    ft_id = created_family_tree_cell['id_family_tree']
    response = client.post(
        f'/family_trees/{ft_id}/family_tree_cells/{cell_id}/parent',
        json={},
        headers=auth_headers,
    )
    assert response.status_code == 400


def test_add_parent_already_exists(client, auth_headers, created_family_tree, created_family_tree_cell):
    ft_id = created_family_tree['id_family_tree']
    parent_id = created_family_tree_cell['id_family_tree_cell']
    child = client.post(
        f'/family_trees/{ft_id}/family_tree_cells',
        json={
            'name': 'Child',
            'surnames': 'Smith',
            'birthday': '01/01/2010',
            'jobs': '',
            'comments': '',
            'generation': 2,
            'parents': [parent_id],
        },
        headers=auth_headers,
    )
    assert child.status_code == 201
    child_id = child.get_json()['data']['id_family_tree_cell']
    response = client.post(
        f'/family_trees/{ft_id}/family_tree_cells/{child_id}/parent',
        json={'parent_id': parent_id},
        headers=auth_headers,
    )
    assert response.status_code == 409


def test_delete_parent(client, auth_headers, created_family_tree, created_family_tree_cell):
    ft_id = created_family_tree['id_family_tree']
    parent_id = created_family_tree_cell['id_family_tree_cell']
    child = client.post(
        f'/family_trees/{ft_id}/family_tree_cells',
        json={
            'name': 'Child',
            'surnames': 'Smith',
            'birthday': '01/01/2010',
            'jobs': '',
            'comments': '',
            'generation': 2,
            'parents': [parent_id],
        },
        headers=auth_headers,
    )
    assert child.status_code == 201
    child_id = child.get_json()['data']['id_family_tree_cell']
    response = client.delete(
        f'/family_trees/{ft_id}/family_tree_cells/{child_id}/parent/{parent_id}',
        headers=auth_headers,
    )
    assert response.status_code == 200


def test_delete_parent_not_found(client, auth_headers, created_family_tree_cell):
    cell_id = created_family_tree_cell['id_family_tree_cell']
    ft_id = created_family_tree_cell['id_family_tree']
    response = client.delete(
        f'/family_trees/{ft_id}/family_tree_cells/{cell_id}/parent/99999',
        headers=auth_headers,
    )
    assert response.status_code == 404


# -----------------------------------------------------------------------
# POST /family_trees/<id>/family_tree_cells/<cell_id>/couple
# -----------------------------------------------------------------------

def test_add_couple(client, auth_headers, created_family_tree, created_family_tree_cell, second_family_tree_cell):
    ft_id = created_family_tree['id_family_tree']
    cell_id = created_family_tree_cell['id_family_tree_cell']
    partner_id = second_family_tree_cell['id_family_tree_cell']
    response = client.post(
        f'/family_trees/{ft_id}/family_tree_cells/{cell_id}/couple',
        json={'partner_id': partner_id},
        headers=auth_headers,
    )
    assert response.status_code == 201


def test_add_couple_missing_field(client, auth_headers, created_family_tree_cell):
    cell_id = created_family_tree_cell['id_family_tree_cell']
    ft_id = created_family_tree_cell['id_family_tree']
    response = client.post(
        f'/family_trees/{ft_id}/family_tree_cells/{cell_id}/couple',
        json={},
        headers=auth_headers,
    )
    assert response.status_code == 400


def test_add_couple_already_exists(client, auth_headers, created_family_tree, created_family_tree_cell, second_family_tree_cell):
    ft_id = created_family_tree['id_family_tree']
    cell_id = created_family_tree_cell['id_family_tree_cell']
    partner_id = second_family_tree_cell['id_family_tree_cell']
    client.post(
        f'/family_trees/{ft_id}/family_tree_cells/{cell_id}/couple',
        json={'partner_id': partner_id},
        headers=auth_headers,
    )
    response = client.post(
        f'/family_trees/{ft_id}/family_tree_cells/{cell_id}/couple',
        json={'partner_id': partner_id},
        headers=auth_headers,
    )
    assert response.status_code == 409


# -----------------------------------------------------------------------
# DELETE /family_trees/<id>/family_tree_cells/<cell_id>/couple/<partner_id>
# -----------------------------------------------------------------------

def test_delete_couple(client, auth_headers, created_family_tree, created_family_tree_cell, second_family_tree_cell):
    ft_id = created_family_tree['id_family_tree']
    cell_id = created_family_tree_cell['id_family_tree_cell']
    partner_id = second_family_tree_cell['id_family_tree_cell']
    client.post(
        f'/family_trees/{ft_id}/family_tree_cells/{cell_id}/couple',
        json={'partner_id': partner_id},
        headers=auth_headers,
    )
    response = client.delete(
        f'/family_trees/{ft_id}/family_tree_cells/{cell_id}/couple/{partner_id}',
        headers=auth_headers,
    )
    assert response.status_code == 200


def test_delete_couple_not_found(client, auth_headers, created_family_tree_cell):
    cell_id = created_family_tree_cell['id_family_tree_cell']
    ft_id = created_family_tree_cell['id_family_tree']
    response = client.delete(
        f'/family_trees/{ft_id}/family_tree_cells/{cell_id}/couple/99999',
        headers=auth_headers,
    )
    assert response.status_code == 404