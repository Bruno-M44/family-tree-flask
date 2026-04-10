from .conftest import USER_1


def test_login_success(client, created_user):
    response = client.post('/login', json=USER_1)
    assert response.status_code == 200
    assert response.get_json()['message'] == 'Token !'
    assert 'data' in response.get_json()


def test_login_wrong_password(client, created_user):
    response = client.post('/login', json={**USER_1, 'password': 'wrong'})
    assert response.status_code == 401


def test_login_unknown_email(client):
    response = client.post('/login', json=USER_1)
    assert response.status_code == 401


def test_login_missing_fields(client):
    response = client.post('/login', json={'email': USER_1['email']})
    assert response.status_code == 400


def test_login_empty_body(client):
    response = client.post('/login', json={})
    assert response.status_code == 400
