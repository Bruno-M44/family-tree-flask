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
        'header_picture': 'true',
    }
    response = client.post(
        f'/family_trees/{ft_id}/family_tree_cells/{cell_id}/pictures',
        headers=auth_headers,
        data=data,
        content_type='multipart/form-data'
    )
    assert response.status_code == 201
    return response.get_json()['data']


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


def test_get_pictures_includes_uploaded_picture(client, auth_headers, created_family_tree_cell, created_picture):
    cell_id = created_family_tree_cell['id_family_tree_cell']
    response = client.get(f'/family_tree_cells/{cell_id}/pictures', headers=auth_headers)
    assert response.status_code == 200
    ids = [p['id_picture'] for p in response.get_json()['data']]
    assert created_picture['id_picture'] in ids


# -----------------------------------------------------------------------
# POST /family_trees/<ft_id>/family_tree_cells/<cell_id>/pictures
# -----------------------------------------------------------------------

def test_upload_picture(client, auth_headers, created_family_tree_cell):
    cell_id = created_family_tree_cell['id_family_tree_cell']
    ft_id = created_family_tree_cell['id_family_tree']
    response = client.post(
        f'/family_trees/{ft_id}/family_tree_cells/{cell_id}/pictures',
        headers=auth_headers,
        data={'file': (BytesIO(b'fake image content'), 'test.jpg'), 'header_picture': 'true'},
        content_type='multipart/form-data',
    )
    assert response.status_code == 201
    assert response.get_json()['data']['header_picture'] is True


def test_upload_picture_no_file_part(client, auth_headers, created_family_tree_cell):
    cell_id = created_family_tree_cell['id_family_tree_cell']
    ft_id = created_family_tree_cell['id_family_tree']
    response = client.post(
        f'/family_trees/{ft_id}/family_tree_cells/{cell_id}/pictures',
        headers=auth_headers,
        data={'header_picture': 'true'},
        content_type='multipart/form-data',
    )
    assert response.status_code == 400
    assert 'No file part' in response.get_json()['message']


def test_upload_picture_no_selected_file(client, auth_headers, created_family_tree_cell):
    cell_id = created_family_tree_cell['id_family_tree_cell']
    ft_id = created_family_tree_cell['id_family_tree']
    response = client.post(
        f'/family_trees/{ft_id}/family_tree_cells/{cell_id}/pictures',
        headers=auth_headers,
        data={'file': (BytesIO(b''), ''), 'header_picture': 'true'},
        content_type='multipart/form-data',
    )
    assert response.status_code == 400
    assert 'No selected file' in response.get_json()['message']


def test_upload_picture_disallowed_extension(client, auth_headers, created_family_tree_cell):
    cell_id = created_family_tree_cell['id_family_tree_cell']
    ft_id = created_family_tree_cell['id_family_tree']
    response = client.post(
        f'/family_trees/{ft_id}/family_tree_cells/{cell_id}/pictures',
        headers=auth_headers,
        data={'file': (BytesIO(b'not an image'), 'malware.exe'), 'header_picture': 'true'},
        content_type='multipart/form-data',
    )
    assert response.status_code == 400
    assert 'File not allowed' in response.get_json()['message']


def test_upload_picture_missing_header_picture_field(client, auth_headers, created_family_tree_cell):
    cell_id = created_family_tree_cell['id_family_tree_cell']
    ft_id = created_family_tree_cell['id_family_tree']
    response = client.post(
        f'/family_trees/{ft_id}/family_tree_cells/{cell_id}/pictures',
        headers=auth_headers,
        data={'file': (BytesIO(b'fake image content'), 'test.jpg')},
        content_type='multipart/form-data',
    )
    assert response.status_code == 400
    assert 'header_picture' in response.get_json()['message']


def test_upload_picture_unauthenticated(client, created_family_tree_cell):
    cell_id = created_family_tree_cell['id_family_tree_cell']
    ft_id = created_family_tree_cell['id_family_tree']
    response = client.post(
        f'/family_trees/{ft_id}/family_tree_cells/{cell_id}/pictures',
        data={'file': (BytesIO(b'fake image content'), 'test.jpg'), 'header_picture': 'true'},
        content_type='multipart/form-data',
    )
    assert response.status_code == 401


# -----------------------------------------------------------------------
# GET /family_trees/<ft_id>/family_tree_cells/<cell_id>/pictures/<pic_id>
# -----------------------------------------------------------------------

def test_get_picture(client, auth_headers, created_family_tree_cell, created_picture):
    cell_id = created_family_tree_cell['id_family_tree_cell']
    ft_id = created_family_tree_cell['id_family_tree']
    response = client.get(
        f"/family_trees/{ft_id}/family_tree_cells/{cell_id}/pictures/{created_picture['id_picture']}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.get_json()['data']['id_picture'] == created_picture['id_picture']


def test_get_picture_not_found(client, auth_headers, created_family_tree_cell):
    cell_id = created_family_tree_cell['id_family_tree_cell']
    ft_id = created_family_tree_cell['id_family_tree']
    response = client.get(f'/family_trees/{ft_id}/family_tree_cells/{cell_id}/pictures/99999', headers=auth_headers)
    assert response.status_code == 404


# -----------------------------------------------------------------------
# PUT /family_trees/<ft_id>/family_tree_cells/<cell_id>/pictures/<pic_id>
# -----------------------------------------------------------------------

def test_update_picture(client, auth_headers, created_family_tree_cell, created_picture):
    cell_id = created_family_tree_cell['id_family_tree_cell']
    ft_id = created_family_tree_cell['id_family_tree']
    response = client.put(
        f"/family_trees/{ft_id}/family_tree_cells/{cell_id}/pictures/{created_picture['id_picture']}",
        json={'comments': 'Updated comment', 'header_picture': False},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.get_json()['data']['comments'] == 'Updated comment'
    assert response.get_json()['data']['header_picture'] is False


def test_update_picture_date(client, auth_headers, created_family_tree_cell, created_picture):
    cell_id = created_family_tree_cell['id_family_tree_cell']
    ft_id = created_family_tree_cell['id_family_tree']
    response = client.put(
        f"/family_trees/{ft_id}/family_tree_cells/{cell_id}/pictures/{created_picture['id_picture']}",
        json={'picture_date': '15/06/2010'},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.get_json()['data']['picture_date'].startswith('2010-06-15')


def test_update_picture_invalid_date(client, auth_headers, created_family_tree_cell, created_picture):
    cell_id = created_family_tree_cell['id_family_tree_cell']
    ft_id = created_family_tree_cell['id_family_tree']
    response = client.put(
        f"/family_trees/{ft_id}/family_tree_cells/{cell_id}/pictures/{created_picture['id_picture']}",
        json={'picture_date': 'not-a-date'},
        headers=auth_headers,
    )
    assert response.status_code == 400


# -----------------------------------------------------------------------
# GET /family_trees/<ft_id>/family_tree_cells/<cell_id>/pictures/<pic_id>/download
# -----------------------------------------------------------------------

def test_download_picture(client, auth_headers, created_family_tree_cell, created_picture):
    cell_id = created_family_tree_cell['id_family_tree_cell']
    ft_id = created_family_tree_cell['id_family_tree']
    response = client.get(
        f"/family_trees/{ft_id}/family_tree_cells/{cell_id}/pictures/{created_picture['id_picture']}/download",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.data == b'fake image content'


def test_download_picture_not_found(client, auth_headers, created_family_tree_cell):
    cell_id = created_family_tree_cell['id_family_tree_cell']
    ft_id = created_family_tree_cell['id_family_tree']
    response = client.get(f'/family_trees/{ft_id}/family_tree_cells/{cell_id}/pictures/99999/download', headers=auth_headers)
    assert response.status_code == 404


# -----------------------------------------------------------------------
# GET /family_trees/<ft_id>/family_tree_cells/<cell_id>/pictures/<pic_id>/secure
# -----------------------------------------------------------------------

def test_secure_picture(client, auth_headers, created_family_tree_cell, created_picture):
    cell_id = created_family_tree_cell['id_family_tree_cell']
    ft_id = created_family_tree_cell['id_family_tree']
    response = client.get(
        f"/family_trees/{ft_id}/family_tree_cells/{cell_id}/pictures/{created_picture['id_picture']}/secure",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.data == b'fake image content'


# -----------------------------------------------------------------------
# DELETE /family_trees/<ft_id>/family_tree_cells/<cell_id>/pictures/<pic_id>/delete
# -----------------------------------------------------------------------

def test_delete_picture(client, auth_headers, created_family_tree_cell, created_picture):
    cell_id = created_family_tree_cell['id_family_tree_cell']
    ft_id = created_family_tree_cell['id_family_tree']
    response = client.delete(
        f"/family_trees/{ft_id}/family_tree_cells/{cell_id}/pictures/{created_picture['id_picture']}/delete",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert _db.session.get(Picture, created_picture['id_picture']) is None


def test_delete_picture_not_found(client, auth_headers, created_family_tree_cell):
    cell_id = created_family_tree_cell['id_family_tree_cell']
    ft_id = created_family_tree_cell['id_family_tree']
    response = client.delete(f'/family_trees/{ft_id}/family_tree_cells/{cell_id}/pictures/99999/delete', headers=auth_headers)
    assert response.status_code == 404
