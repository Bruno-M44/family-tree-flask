import json


from .conftest import client, AccessToken
from .credentials import UserCredential


def test_create_user_ok(client):
    response = client.post(
        "/user",
        headers={'Content-Type': 'application/json'},
        data=json.dumps(UserCredential.USER_1)
    )
    assert response.status_code == 201
    assert response.get_json()["message"] == "User Created !"


def test_create_user_already_exists(client):
    response = client.post(
        "/user",
        headers={'Content-Type': 'application/json'},
        data=json.dumps(UserCredential.USER_1)
    )
    assert response.status_code == 403
    assert response.get_json()["message"] == "User already exists !"


@AccessToken(user_credential=UserCredential.USER_1)
def test_get_user(client, access_token):
    response = client.get(
        "/user",
        headers={"Authorization": "Bearer {}".format(access_token)}
    )
    assert response.status_code == 200
    assert response.get_json()["message"] == "User Info !"
    for key, value in UserCredential.USER_1.items():
        if key != "password":
            assert value == response.get_json()["data"].get(key)


@AccessToken(user_credential=UserCredential.USER_1)
def test_delete_user(client, access_token):
    response = client.delete(
        "/user",
        headers={"Authorization": "Bearer {}".format(access_token)}
    )
    assert response.status_code == 200
    assert response.get_json()["message"] == "User Deleted !"
