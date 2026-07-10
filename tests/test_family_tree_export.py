import io
import json
import zipfile
from io import BytesIO


def test_export_family_tree_unauthenticated(client):
    response = client.get('/family_trees/1/export')
    assert response.status_code == 401


def test_export_family_tree_not_found(client, auth_headers):
    response = client.get('/family_trees/99999/export', headers=auth_headers)
    assert response.status_code == 404


def test_export_family_tree_empty(client, auth_headers):
    ft = client.post('/family_tree', json={'title': 'Empty', 'family_name': 'Fam'}, headers=auth_headers).get_json()['data']
    response = client.get(f"/family_trees/{ft['id_family_tree']}/export", headers=auth_headers)
    assert response.status_code == 200
    assert response.content_type == 'application/zip'
    with zipfile.ZipFile(io.BytesIO(response.data)) as zf:
        tree_json = json.loads(zf.read('tree.json'))
    assert tree_json['title'] == 'Empty'
    assert tree_json['cells'] == []
    assert tree_json['relations']['parent_child'] == []
    assert tree_json['relations']['couples'] == []


def test_export_family_tree_with_cells_pictures_pets_and_relations(client, auth_headers):
    ft = client.post('/family_tree', json={'title': 'Full', 'family_name': 'Fam'}, headers=auth_headers).get_json()['data']
    ft_id = ft['id_family_tree']

    alice = client.post(
        f'/family_trees/{ft_id}/family_tree_cells',
        json={'name': 'Dupont', 'surnames': 'Alice', 'generation': 0},
        headers=auth_headers,
    ).get_json()['data']
    bruno = client.post(
        f'/family_trees/{ft_id}/family_tree_cells',
        json={'name': 'Martin', 'surnames': 'Bruno', 'generation': 0},
        headers=auth_headers,
    ).get_json()['data']
    celeste = client.post(
        f'/family_trees/{ft_id}/family_tree_cells',
        json={'name': 'Dupont', 'surnames': 'Celeste', 'generation': 1,
              'parents': [alice['id_family_tree_cell'], bruno['id_family_tree_cell']]},
        headers=auth_headers,
    ).get_json()['data']
    client.post(
        f"/family_trees/{ft_id}/family_tree_cells/{alice['id_family_tree_cell']}/couple",
        json={'partner_id': bruno['id_family_tree_cell'], 'start_union': '01/06/2000'},
        headers=auth_headers,
    )
    client.post(
        f"/family_trees/{ft_id}/family_tree_cells/{alice['id_family_tree_cell']}/pictures",
        data={'file': (BytesIO(b'fake image'), 'photo.jpg'), 'header_picture': 'true'},
        headers=auth_headers,
        content_type='multipart/form-data',
    )
    pet = client.post(
        f"/family_tree_cells/{alice['id_family_tree_cell']}/pets",
        json={'name': 'Rex', 'species': 'chien'},
        headers=auth_headers,
    ).get_json()['data']
    client.post(
        f"/pets/{pet['id_pet']}/pets_pictures",
        data={'file': (BytesIO(b'fake pet image'), 'pet.jpg'), 'is_main': 'true'},
        headers=auth_headers,
        content_type='multipart/form-data',
    )

    response = client.get(f'/family_trees/{ft_id}/export', headers=auth_headers)
    assert response.status_code == 200
    assert 'attachment' in response.headers['Content-Disposition']

    with zipfile.ZipFile(io.BytesIO(response.data)) as zf:
        tree_json = json.loads(zf.read('tree.json'))
        assert any(n.startswith('pictures/') for n in zf.namelist())
        assert any(n.startswith('pets/') for n in zf.namelist())

    assert len(tree_json['cells']) == 3
    alice_data = next(c for c in tree_json['cells'] if c['surnames'] == 'Alice')
    assert len(alice_data['pictures']) == 1
    assert len(alice_data['pets']) == 1
    assert alice_data['pets'][0]['name'] == 'Rex'
    assert len(alice_data['pets'][0]['pictures']) == 1

    assert len(tree_json['relations']['parent_child']) == 2
    assert len(tree_json['relations']['couples']) == 1
    couple = tree_json['relations']['couples'][0]
    assert couple['start_union'] == '01/06/2000'
