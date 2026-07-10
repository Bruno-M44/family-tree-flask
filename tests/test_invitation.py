from unittest.mock import patch


def test_send_invitation(client, auth_headers):
    with patch('app.views.invitation_view.send_platform_invitation_email') as mock_send:
        response = client.post('/invitation', json={'email': 'newperson@test.com'}, headers=auth_headers)
    assert response.status_code == 200
    assert 'envoyée' in response.get_json()['message']
    mock_send.assert_called_once()
    call_kwargs = mock_send.call_args.kwargs
    assert call_kwargs['to_email'] == 'newperson@test.com'


def test_send_invitation_missing_email(client, auth_headers):
    response = client.post('/invitation', json={}, headers=auth_headers)
    assert response.status_code == 400
    assert 'Missing email' in response.get_json()['message']


def test_send_invitation_existing_account(client, auth_headers):
    client.post('/user', json={
        'name': 'Other', 'surname': 'User', 'email': 'existing@test.com', 'password': 'pw',
    })
    with patch('app.views.invitation_view.send_platform_invitation_email') as mock_send:
        response = client.post('/invitation', json={'email': 'existing@test.com'}, headers=auth_headers)
    assert response.status_code == 200
    assert 'existe déjà' in response.get_json()['message']
    mock_send.assert_not_called()


def test_send_invitation_unauthenticated(client):
    response = client.post('/invitation', json={'email': 'newperson@test.com'})
    assert response.status_code == 401
