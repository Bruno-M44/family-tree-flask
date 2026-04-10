import pytest

FAMILY_TREE = {'title': 'Family Smith', 'family_name': 'Smith'}


@pytest.fixture
def created_family_tree(client, auth_headers):
    response = client.post('/family_tree', json=FAMILY_TREE, headers=auth_headers)
    assert response.status_code == 201
    return response.get_json()['data']


def test_get_family_trees(client, auth_headers):
    response = client.get('/family_trees', headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.get_json()['data'], list)


def test_get_family_trees_unauthenticated(client):
    response = client.get('/family_trees')
    assert response.status_code == 401


def test_create_family_tree(client, auth_headers):
    response = client.post('/family_tree', json=FAMILY_TREE, headers=auth_headers)
    assert response.status_code == 201
    data = response.get_json()['data']
    assert data['title'] == FAMILY_TREE['title']
    assert data['family_name'] == FAMILY_TREE['family_name']
    assert 'id_family_tree' in data


def test_create_family_tree_missing_fields(client, auth_headers):
    response = client.post('/family_tree', json={'title': 'Only title'}, headers=auth_headers)
    assert response.status_code == 400


def test_create_family_tree_unauthenticated(client):
    response = client.post('/family_tree', json=FAMILY_TREE)
    assert response.status_code == 401


def test_get_family_tree(client, auth_headers, created_family_tree):
    ft_id = created_family_tree['id_family_tree']
    response = client.get(f'/family_trees/{ft_id}', headers=auth_headers)
    assert response.status_code == 200
    assert response.get_json()['data']['title'] == FAMILY_TREE['title']


def test_get_family_tree_not_found(client, auth_headers):
    response = client.get('/family_trees/99999', headers=auth_headers)
    assert response.status_code == 404


def test_update_family_tree(client, auth_headers, created_family_tree):
    ft_id = created_family_tree['id_family_tree']
    response = client.put(
        f'/family_trees/{ft_id}',
        json={'title': 'Updated Title'},
        headers=auth_headers
    )
    assert response.status_code == 200
    assert response.get_json()['data']['title'] == 'Updated Title'


def test_delete_family_tree(client, auth_headers, created_family_tree):
    ft_id = created_family_tree['id_family_tree']
    response = client.delete(f'/family_trees/{ft_id}', headers=auth_headers)
    assert response.status_code == 200
    # Verify it no longer exists
    response = client.get(f'/family_trees/{ft_id}', headers=auth_headers)
    assert response.status_code == 404
