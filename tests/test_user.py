from .conftest import USER_1


def test_create_user_ok(client):
    response = client.post('/user', json=USER_1)
    assert response.status_code == 201
    assert response.get_json()['message'] == 'User Created !'
    data = response.get_json()['data']
    assert data['email'] == USER_1['email']
    assert 'password' not in data


def test_create_user_missing_fields(client):
    response = client.post('/user', json={'email': USER_1['email']})
    assert response.status_code == 400


def test_create_user_already_exists(client, created_user):
    response = client.post('/user', json=USER_1)
    assert response.status_code == 403
    assert response.get_json()['message'] == 'User already exists !'


def test_get_user(client, auth_headers):
    response = client.get('/user', headers=auth_headers)
    assert response.status_code == 200
    data = response.get_json()['data']
    assert data['email'] == USER_1['email']
    assert data['name'] == USER_1['name']
    assert data['surname'] == USER_1['surname']
    assert 'password' not in data


def test_get_user_unauthenticated(client):
    response = client.get('/user')
    assert response.status_code == 401


def test_update_user_name(client, auth_headers):
    response = client.put('/user', json={'name': 'Updated'}, headers=auth_headers)
    assert response.status_code == 200
    assert response.get_json()['data']['name'] == 'Updated'


def test_update_user_password(client, auth_headers):
    new_password = 'new_secure_password'
    response = client.put('/user', json={'password': new_password}, headers=auth_headers)
    assert response.status_code == 200
    # Verify new password works for login
    login_resp = client.post('/login', json={**USER_1, 'password': new_password})
    assert login_resp.status_code == 200


def test_delete_user(client, auth_headers):
    response = client.delete('/user', headers=auth_headers)
    assert response.status_code == 200
    assert response.get_json()['message'] == 'User Deleted !'


def test_delete_user_unauthenticated(client):
    response = client.delete('/user')
    assert response.status_code == 401
