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


def test_export_user_data_includes_cell_picture_and_pet_data(client, auth_headers):
    """The shallow export tests above use an account with no family tree, so the
    per-cell/picture/pet loops never actually run. This exercises them."""
    import io, zipfile, json
    from io import BytesIO

    ft = client.post('/family_tree', json={'title': 'Export Tree', 'family_name': 'Export'}, headers=auth_headers).get_json()['data']
    cell = client.post(
        f"/family_trees/{ft['id_family_tree']}/family_tree_cells",
        json={'name': 'Dupont', 'surnames': 'Alice', 'generation': 0, 'birthday': '01/01/1980'},
        headers=auth_headers,
    ).get_json()['data']
    client.post(
        f"/family_trees/{ft['id_family_tree']}/family_tree_cells/{cell['id_family_tree_cell']}/pictures",
        data={'file': (BytesIO(b'fake image content'), 'photo.jpg'), 'header_picture': 'true'},
        headers=auth_headers,
        content_type='multipart/form-data',
    )
    pet = client.post(
        f"/family_tree_cells/{cell['id_family_tree_cell']}/pets",
        json={'name': 'Rex', 'species': 'chien', 'birthday': '01/01/2020'},
        headers=auth_headers,
    ).get_json()['data']
    client.post(
        f"/pets/{pet['id_pet']}/pets_pictures",
        data={'file': (BytesIO(b'fake pet image'), 'pet.jpg'), 'is_main': 'true'},
        headers=auth_headers,
        content_type='multipart/form-data',
    )

    response = client.get('/user/export', headers=auth_headers)
    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.data)) as zf:
        data = json.loads(zf.read('data.json'))
        # Picture files themselves should be bundled in the zip too
        assert any(n.startswith('pictures/') for n in zf.namelist())
        assert any(n.startswith('pet_pictures/') for n in zf.namelist())

    export_ft = next(f for f in data['family_trees'] if f['title'] == 'Export Tree')
    member = next(m for m in export_ft['members'] if m['surnames'] == 'Alice')
    assert member['birthday'] == '01/01/1980'
    assert len(member['pictures']) == 1
    assert len(member['pets']) == 1
    assert member['pets'][0]['name'] == 'Rex'
    assert len(member['pets'][0]['pictures']) == 1


def test_update_user_surname(client, auth_headers):
    response = client.put('/user', json={'surname': 'Nouveau'}, headers=auth_headers)
    assert response.status_code == 200
    assert response.get_json()['data']['surname'] == 'Nouveau'


def test_update_user_email(client, auth_headers):
    from unittest.mock import patch
    with patch('app.views.user_view.send_verification_email') as mock_send:
        response = client.put('/user', json={'email': 'new@test.com'}, headers=auth_headers)
    assert response.status_code == 200
    assert response.get_json()['data']['email'] == 'new@test.com'
    assert response.get_json()['data']['verified'] is False
    mock_send.assert_called_once()


def test_update_user_email_already_in_use(client, auth_headers):
    client.post('/user', json={
        'name': 'Other', 'surname': 'User', 'email': 'taken@test.com', 'password': 'pw',
    })
    response = client.put('/user', json={'email': 'taken@test.com'}, headers=auth_headers)
    assert response.status_code == 409


def test_delete_user_removes_sole_family_tree(client, auth_headers):
    from app import db as _db
    from app.models import FamilyTree
    ft = client.post('/family_tree', json={'title': 'Solo Tree', 'family_name': 'Solo'}, headers=auth_headers).get_json()['data']
    id_family_tree = ft['id_family_tree']

    response = client.delete('/user', headers=auth_headers)
    assert response.status_code == 200

    assert _db.session.get(FamilyTree, id_family_tree) is None


def test_register_consumes_pending_invitation(client, auth_headers):
    """A user invited by email (before they have an account) should be
    auto-joined to the tree once they register with that same email."""
    from unittest.mock import patch
    ft = client.post('/family_tree', json={'title': 'Invite Tree', 'family_name': 'Invite'}, headers=auth_headers).get_json()['data']

    with patch('app.views.user_view.send_member_invitation_email'):
        add_resp = client.post(
            f"/user/family-tree/{ft['id_family_tree']}/member",
            json={'email': 'invitee@test.com', 'role': 'viewer'},
            headers=auth_headers,
        )
    assert add_resp.status_code == 200
    assert add_resp.get_json()['status'] == 'invitation_sent'

    with patch('app.views.user_view.create_demo_family_tree'):
        with patch('app.views.user_view.send_verification_email'):
            register_resp = client.post('/user', json={
                'name': 'Invitee', 'surname': 'Test', 'email': 'invitee@test.com', 'password': 'pw',
            })
    assert register_resp.status_code == 201

    from app.models import User
    invitee = User.query.filter_by(email='invitee@test.com').first()
    invitee.verified = True
    from app import db as _db
    _db.session.commit()
    login = client.post('/login', json={'email': 'invitee@test.com', 'password': 'pw'})
    invitee_headers = {'Authorization': f"Bearer {login.get_json()['data']}"}

    trees_resp = client.get('/family_trees', headers=invitee_headers)
    titles = [t['title'] for t in trees_resp.get_json()['data']]
    assert 'Invite Tree' in titles


# ---------------------------------------------------------------------------
# Avatar
# ---------------------------------------------------------------------------

def test_get_avatar_no_avatar(client, auth_headers):
    response = client.get('/user/avatar', headers=auth_headers)
    assert response.status_code == 404


def test_get_avatar_unauthenticated(client):
    response = client.get('/user/avatar')
    assert response.status_code == 401


def test_upload_avatar(client, auth_headers):
    from io import BytesIO
    response = client.post(
        '/user/avatar',
        data={'file': (BytesIO(b'fake image content'), 'avatar.jpg')},
        headers=auth_headers,
        content_type='multipart/form-data',
    )
    assert response.status_code == 200
    assert response.get_json()['avatar']

    get_response = client.get('/user/avatar', headers=auth_headers)
    assert get_response.status_code == 200


def test_upload_avatar_no_file(client, auth_headers):
    response = client.post('/user/avatar', headers=auth_headers, content_type='multipart/form-data')
    assert response.status_code == 400


def test_upload_avatar_disallowed_extension(client, auth_headers):
    from io import BytesIO
    response = client.post(
        '/user/avatar',
        data={'file': (BytesIO(b'not an image'), 'malware.exe')},
        headers=auth_headers,
        content_type='multipart/form-data',
    )
    assert response.status_code == 400


def test_upload_avatar_replaces_previous(client, auth_headers):
    from io import BytesIO
    first = client.post(
        '/user/avatar',
        data={'file': (BytesIO(b'first image'), 'first.jpg')},
        headers=auth_headers,
        content_type='multipart/form-data',
    ).get_json()['avatar']
    second = client.post(
        '/user/avatar',
        data={'file': (BytesIO(b'second image'), 'second.jpg')},
        headers=auth_headers,
        content_type='multipart/form-data',
    ).get_json()['avatar']
    assert first != second


def test_delete_avatar(client, auth_headers):
    from io import BytesIO
    client.post(
        '/user/avatar',
        data={'file': (BytesIO(b'fake image content'), 'avatar.jpg')},
        headers=auth_headers,
        content_type='multipart/form-data',
    )
    response = client.delete('/user/avatar', headers=auth_headers)
    assert response.status_code == 200

    get_response = client.get('/user/avatar', headers=auth_headers)
    assert get_response.status_code == 404


def test_delete_avatar_none_to_delete(client, auth_headers):
    response = client.delete('/user/avatar', headers=auth_headers)
    assert response.status_code == 404


def test_delete_avatar_unauthenticated(client):
    response = client.delete('/user/avatar')
    assert response.status_code == 401
