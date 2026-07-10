import pytest
from io import BytesIO
from app import db as _db
from app.models import PetPicture


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
    assert response.status_code == 201
    return response.get_json()['data']


@pytest.fixture
def created_pet_picture(client, auth_headers, created_pet):
    pet_id = created_pet['id_pet']
    response = client.post(
        f'/pets/{pet_id}/pets_pictures',
        headers=auth_headers,
        data={'file': (BytesIO(b'fake pet image content'), 'pet.jpg'), 'is_main': 'true'},
        content_type='multipart/form-data',
    )
    assert response.status_code == 201
    return response.get_json()['data']


# -----------------------------------------------------------------------
# GET /pets/<pet_id>/pets_pictures
# -----------------------------------------------------------------------

def test_get_pets_pictures(client, auth_headers, created_pet):
    pet_id = created_pet['id_pet']
    response = client.get(f'/pets/{pet_id}/pets_pictures', headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.get_json()['data'], list)


def test_get_pets_pictures_unauthenticated(client, created_pet):
    pet_id = created_pet['id_pet']
    response = client.get(f'/pets/{pet_id}/pets_pictures')
    assert response.status_code == 401


def test_get_pets_pictures_includes_uploaded_picture(client, auth_headers, created_pet, created_pet_picture):
    pet_id = created_pet['id_pet']
    response = client.get(f'/pets/{pet_id}/pets_pictures', headers=auth_headers)
    ids = [p['id_pet_picture'] for p in response.get_json()['data']]
    assert created_pet_picture['id_pet_picture'] in ids


# -----------------------------------------------------------------------
# POST /pets/<pet_id>/pets_pictures
# -----------------------------------------------------------------------

def test_upload_pet_picture(client, auth_headers, created_pet):
    pet_id = created_pet['id_pet']
    response = client.post(
        f'/pets/{pet_id}/pets_pictures',
        headers=auth_headers,
        data={'file': (BytesIO(b'fake pet image content'), 'pet.jpg'), 'is_main': 'true'},
        content_type='multipart/form-data',
    )
    assert response.status_code == 201
    assert response.get_json()['data']['is_main'] is True


def test_upload_pet_picture_no_file_part(client, auth_headers, created_pet):
    pet_id = created_pet['id_pet']
    response = client.post(
        f'/pets/{pet_id}/pets_pictures',
        headers=auth_headers,
        data={},
        content_type='multipart/form-data',
    )
    assert response.status_code == 400
    assert 'No file part' in response.get_json()['message']


def test_upload_pet_picture_no_selected_file(client, auth_headers, created_pet):
    pet_id = created_pet['id_pet']
    response = client.post(
        f'/pets/{pet_id}/pets_pictures',
        headers=auth_headers,
        data={'file': (BytesIO(b''), '')},
        content_type='multipart/form-data',
    )
    assert response.status_code == 400
    assert 'No selected file' in response.get_json()['message']


def test_upload_pet_picture_disallowed_extension(client, auth_headers, created_pet):
    pet_id = created_pet['id_pet']
    response = client.post(
        f'/pets/{pet_id}/pets_pictures',
        headers=auth_headers,
        data={'file': (BytesIO(b'not an image'), 'malware.exe')},
        content_type='multipart/form-data',
    )
    assert response.status_code == 400
    assert 'File not allowed' in response.get_json()['message']


def test_upload_pet_picture_second_main_unsets_previous(client, auth_headers, created_pet, created_pet_picture):
    pet_id = created_pet['id_pet']
    second = client.post(
        f'/pets/{pet_id}/pets_pictures',
        headers=auth_headers,
        data={'file': (BytesIO(b'second pet image'), 'pet2.jpg'), 'is_main': 'true'},
        content_type='multipart/form-data',
    ).get_json()['data']
    assert second['is_main'] is True

    first_refreshed = client.get(
        f"/pets/{pet_id}/pets_pictures/{created_pet_picture['id_pet_picture']}", headers=auth_headers,
    ).get_json()['data']
    assert first_refreshed['is_main'] is False


def test_upload_pet_picture_unauthenticated(client, created_pet):
    pet_id = created_pet['id_pet']
    response = client.post(
        f'/pets/{pet_id}/pets_pictures',
        data={'file': (BytesIO(b'fake pet image content'), 'pet.jpg')},
        content_type='multipart/form-data',
    )
    assert response.status_code == 401


# -----------------------------------------------------------------------
# GET /pets/<pet_id>/pets_pictures/<pic_id>
# -----------------------------------------------------------------------

def test_get_pet_picture(client, auth_headers, created_pet, created_pet_picture):
    pet_id = created_pet['id_pet']
    response = client.get(
        f"/pets/{pet_id}/pets_pictures/{created_pet_picture['id_pet_picture']}", headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.get_json()['data']['id_pet_picture'] == created_pet_picture['id_pet_picture']


def test_get_pet_picture_not_found(client, auth_headers, created_pet):
    pet_id = created_pet['id_pet']
    response = client.get(f'/pets/{pet_id}/pets_pictures/99999', headers=auth_headers)
    assert response.status_code == 404


# -----------------------------------------------------------------------
# PUT /pets/<pet_id>/pets_pictures/<pic_id>
# -----------------------------------------------------------------------

def test_update_pet_picture(client, auth_headers, created_pet, created_pet_picture):
    pet_id = created_pet['id_pet']
    response = client.put(
        f"/pets/{pet_id}/pets_pictures/{created_pet_picture['id_pet_picture']}",
        json={'comments': 'Test comment'},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.get_json()['data']['comments'] == 'Test comment'


def test_update_pet_picture_date(client, auth_headers, created_pet, created_pet_picture):
    pet_id = created_pet['id_pet']
    response = client.put(
        f"/pets/{pet_id}/pets_pictures/{created_pet_picture['id_pet_picture']}",
        json={'picture_date': '15/06/2010'},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.get_json()['data']['picture_date'].startswith('2010-06-15')


def test_update_pet_picture_invalid_date(client, auth_headers, created_pet, created_pet_picture):
    pet_id = created_pet['id_pet']
    response = client.put(
        f"/pets/{pet_id}/pets_pictures/{created_pet_picture['id_pet_picture']}",
        json={'picture_date': 'not-a-date'},
        headers=auth_headers,
    )
    assert response.status_code == 400


def test_update_pet_picture_set_is_main(client, auth_headers, created_pet, created_pet_picture):
    pet_id = created_pet['id_pet']
    response = client.put(
        f"/pets/{pet_id}/pets_pictures/{created_pet_picture['id_pet_picture']}",
        json={'is_main': True},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.get_json()['data']['is_main'] is True


# -----------------------------------------------------------------------
# GET /pets/<pet_id>/pets_pictures/<pic_id>/download
# -----------------------------------------------------------------------

def test_download_pet_picture(client, auth_headers, created_pet, created_pet_picture):
    pet_id = created_pet['id_pet']
    response = client.get(
        f"/pets/{pet_id}/pets_pictures/{created_pet_picture['id_pet_picture']}/download", headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.data == b'fake pet image content'


def test_download_pet_picture_not_found(client, auth_headers, created_pet):
    pet_id = created_pet['id_pet']
    response = client.get(f'/pets/{pet_id}/pets_pictures/99999/download', headers=auth_headers)
    assert response.status_code == 404


# -----------------------------------------------------------------------
# DELETE /pets/<pet_id>/pets_pictures/<pic_id>/delete
# -----------------------------------------------------------------------

def test_delete_pet_picture(client, auth_headers, created_pet, created_pet_picture):
    pet_id = created_pet['id_pet']
    response = client.delete(
        f"/pets/{pet_id}/pets_pictures/{created_pet_picture['id_pet_picture']}/delete", headers=auth_headers,
    )
    assert response.status_code == 200
    assert _db.session.get(PetPicture, created_pet_picture['id_pet_picture']) is None


def test_delete_pet_picture_not_found(client, auth_headers, created_pet):
    pet_id = created_pet['id_pet']
    response = client.delete(f'/pets/{pet_id}/pets_pictures/99999/delete', headers=auth_headers)
    assert response.status_code == 404
