import json
import pytest

from .conftest import client
from .credentials import UserCredential


def test_login(credentials, client):
    response = client.post(
        "/login",
        headers={'Content-Type': 'application/json'},
        data=json.dumps(UserCredential.USER_1)
    )
    assert response.status_code == 200
    assert response.get_json()["message"] == "Token !"
