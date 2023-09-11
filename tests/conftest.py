import pytest
import json

from run import create_app


@pytest.fixture
def client():
    app = create_app()
    with app.test_client() as client:
        yield client


class AccessToken:
    def __init__(self, user_credential):
        self.user_credential = user_credential

    def __call__(self, own_function):
        def internal_wrapper(client):
            response = client.post(
                "/login",
                headers={'Content-Type': 'application/json'},
                data=json.dumps(self.user_credential)
            )
            access_token = response.get_json()["data"]
            own_function(client, access_token)
        return internal_wrapper
