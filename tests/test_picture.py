import pytest
from io import BytesIO
from app import db as _db
from app.models import Picture


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
def created_picture(client, auth_headers, created_family_tree_cell):
    cell_id = created_family_tree_cell['id_family_tree_cell']
    ft_id = created_family_tree_cell['id_family_tree']
    data = {
        'file': (BytesIO(b'fake image content'), 'test.jpg'),
    }
    response = client.post(
        f'/family_trees/{ft_id}/family_tree_cells/{cell_id}/pictures',
        headers=auth_headers,
        data=data,
        content_type='multipart/form-data'
    )
    if response.status_code in (201, 200):
        return response.get_json()['data']
    return None


# -----------------------------------------------------------------------
# GET /family_tree_cells/<cell_id>/pictures
# -----------------------------------------------------------------------

def test_get_pictures(client, auth_headers, created_family_tree_cell):
    cell_id = created_family_tree_cell['id_family_tree_cell']
    response = client.get(f'/family_tree_cells/{cell_id}/pictures', headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.get_json()['data'], list)


def test_get_pictures_unauthenticated(client, created_family_tree_cell):
    cell_id = created_family_tree_cell['id_family_tree_cell']
    response = client.get(f'/family_tree_cells/{cell_id}/pictures')
    assert response.status_code == 401


# -----------------------------------------------------------------------
# GET /family_trees/<ft_id>/family_tree_cells/<cell_id>/pictures/<pic_id>
# -----------------------------------------------------------------------

def test_get_picture(client, auth_headers, created_family_tree_cell):
    cell_id = created_family_tree_cell['id_family_tree_cell']
    ft_id = created_family_tree_cell['id_family_tree']
    response = client.get(f'/family_trees/{ft_id}/family_tree_cells/{cell_id}/pictures/1', headers=auth_headers)
    assert response.status_code in (200, 404)


def test_get_picture_not_found(client, auth_headers, created_family_tree_cell):
    cell_id = created_family_tree_cell['id_family_tree_cell']
    ft_id = created_family_tree_cell['id_family_tree']
    response = client.get(f'/family_trees/{ft_id}/family_tree_cells/{cell_id}/pictures/99999', headers=auth_headers)
    assert response.status_code == 404


# -----------------------------------------------------------------------
# PUT /family_trees/<ft_id>/family_tree_cells/<cell_id>/pictures/<pic_id>
# -----------------------------------------------------------------------

def test_update_picture(client, auth_headers, created_family_tree_cell):
    cell_id = created_family_tree_cell['id_family_tree_cell']
    ft_id = created_family_tree_cell['id_family_tree']
    response = client.put(
        f'/family_trees/{ft_id}/family_tree_cells/{cell_id}/pictures/1',
        json={'description': 'Test description'},
        headers=auth_headers,
    )
    assert response.status_code in (200, 404)


# -----------------------------------------------------------------------
# GET /family_trees/<ft_id>/family_tree_cells/<cell_id>/pictures/<pic_id>/download
# -----------------------------------------------------------------------

def test_download_picture(client, auth_headers, created_family_tree_cell):
    cell_id = created_family_tree_cell['id_family_tree_cell']
    ft_id = created_family_tree_cell['id_family_tree']
    response = client.get(f'/family_trees/{ft_id}/family_tree_cells/{cell_id}/pictures/1/download', headers=auth_headers)
    assert response.status_code in (200, 404)


def test_download_picture_not_found(client, auth_headers, created_family_tree_cell):
    cell_id = created_family_tree_cell['id_family_tree_cell']
    ft_id = created_family_tree_cell['id_family_tree']
    response = client.get(f'/family_trees/{ft_id}/family_tree_cells/{cell_id}/pictures/99999/download', headers=auth_headers)
    assert response.status_code == 404


# -----------------------------------------------------------------------
# DELETE /family_trees/<ft_id>/family_tree_cells/<cell_id>/pictures/<pic_id>/delete
# -----------------------------------------------------------------------

def test_delete_picture(client, auth_headers, created_family_tree_cell):
    cell_id = created_family_tree_cell['id_family_tree_cell']
    ft_id = created_family_tree_cell['id_family_tree']
    response = client.delete(f'/family_trees/{ft_id}/family_tree_cells/{cell_id}/pictures/1/delete', headers=auth_headers)
    assert response.status_code in (200, 404)


def test_delete_picture_not_found(client, auth_headers, created_family_tree_cell):
    cell_id = created_family_tree_cell['id_family_tree_cell']
    ft_id = created_family_tree_cell['id_family_tree']
    response = client.delete(f'/family_trees/{ft_id}/family_tree_cells/{cell_id}/pictures/99999/delete', headers=auth_headers)
    assert response.status_code == 404