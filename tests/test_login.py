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


def test_login_unverified(client):
    """User created but email not yet verified cannot log in."""
    from unittest.mock import patch
    with patch('app.views.user_view.create_demo_family_tree'):
        with patch('app.views.user_view.send_verification_email'):
            client.post('/user', json=USER_1)
    response = client.post('/login', json=USER_1)
    assert response.status_code == 403
    assert response.get_json()['message'] == 'Email not verified'


def test_logout_success(client, auth_headers):
    response = client.delete('/logout', headers=auth_headers)
    assert response.status_code == 200
    assert response.get_json()['message'] == 'Logged out'


def test_logout_token_revoked(client, auth_headers):
    client.delete('/logout', headers=auth_headers)
    response = client.delete('/logout', headers=auth_headers)
    assert response.status_code == 401


def test_logout_requires_auth(client):
    response = client.delete('/logout')
    assert response.status_code == 401


def test_token_rejected_after_logout(client, auth_headers):
    client.delete('/logout', headers=auth_headers)
    response = client.get('/user', headers=auth_headers)
    assert response.status_code == 401
