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
    response = client.put(
        '/user',
        json={'password': new_password, 'current_password': USER_1['password']},
        headers=auth_headers,
    )
    assert response.status_code == 200
    # Verify new password works for login
    login_resp = client.post('/login', json={**USER_1, 'password': new_password})
    assert login_resp.status_code == 200


def test_update_user_password_requires_current_password(client, auth_headers):
    response = client.put('/user', json={'password': 'new_secure_password'}, headers=auth_headers)
    assert response.status_code == 401


def test_update_user_password_rejects_wrong_current_password(client, auth_headers):
    response = client.put(
        '/user',
        json={'password': 'new_secure_password', 'current_password': 'wrong'},
        headers=auth_headers,
    )
    assert response.status_code == 401
    # Old password must still work
    login_resp = client.post('/login', json=USER_1)
    assert login_resp.status_code == 200


def test_update_user_password_revokes_current_token(client, auth_headers):
    response = client.put(
        '/user',
        json={'password': 'new_secure_password', 'current_password': USER_1['password']},
        headers=auth_headers,
    )
    assert response.status_code == 200
    # The token used for this request must now be revoked
    stale_response = client.get('/user', headers=auth_headers)
    assert stale_response.status_code == 401


def test_delete_user(client, auth_headers):
    response = client.delete('/user', headers=auth_headers)
    assert response.status_code == 200
    assert response.get_json()['message'] == 'User Deleted !'


def test_delete_user_unauthenticated(client):
    response = client.delete('/user')
    assert response.status_code == 401


def test_verify_email_ok(client):
    from unittest.mock import patch
    with patch('app.views.user_view.create_demo_family_tree'):
        with patch('app.views.user_view.send_verification_email') as mock_send:
            client.post('/user', json=USER_1)
            token = mock_send.call_args[0][1]

    response = client.get(f'/verify?token={token}')
    assert response.status_code == 200
    assert response.get_json()['message'] == 'Email verified !'


def test_verify_email_invalid_token(client):
    response = client.get('/verify?token=invalid-token')
    assert response.status_code == 404


def test_verify_email_missing_token(client):
    response = client.get('/verify')
    assert response.status_code == 400


def test_verify_email_expired_token(client):
    from datetime import datetime, timedelta, timezone
    from unittest.mock import patch
    from app import db as _db
    from app.models import User

    with patch('app.views.user_view.create_demo_family_tree'):
        with patch('app.views.user_view.send_verification_email') as mock_send:
            client.post('/user', json=USER_1)
            token = mock_send.call_args[0][1]

    user = User.query.filter_by(email=USER_1['email']).first()
    user.verification_token_created_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=8)
    _db.session.commit()

    response = client.get(f'/verify?token={token}')
    assert response.status_code == 404


def test_create_user_has_verified_false(client):
    response = client.post('/user', json=USER_1)
    assert response.status_code == 201
    assert response.get_json()['data']['verified'] is False


def test_export_user_data(client, auth_headers):
    import io, zipfile, json
    response = client.get('/user/export', headers=auth_headers)
    assert response.status_code == 200
    assert response.content_type == 'application/zip'
    assert 'attachment' in response.headers.get('Content-Disposition', '')
    assert 'my_data.zip' in response.headers.get('Content-Disposition', '')

    with zipfile.ZipFile(io.BytesIO(response.data)) as zf:
        assert 'data.json' in zf.namelist()
        data = json.loads(zf.read('data.json'))

    assert 'account' in data
    assert 'family_trees' in data
    account = data['account']
    assert account['email'] == USER_1['email']
    assert account['name'] == USER_1['name']
    assert account['surname'] == USER_1['surname']
    assert 'password' not in account


def test_export_user_data_structure(client, auth_headers):
    import io, zipfile, json
    response = client.get('/user/export', headers=auth_headers)
    assert response.status_code == 200

    with zipfile.ZipFile(io.BytesIO(response.data)) as zf:
        data = json.loads(zf.read('data.json'))

    assert isinstance(data['family_trees'], list)
    for ft in data['family_trees']:
        assert 'title' in ft
        assert 'family_name' in ft
        assert 'role' in ft
        assert 'members' in ft
        assert isinstance(ft['members'], list)
        for member in ft['members']:
            assert 'name' in member
            assert 'surnames' in member
            assert 'pictures' in member
            assert 'pets' in member


def test_export_user_data_unauthenticated(client):
    response = client.get('/user/export')
    assert response.status_code == 401
