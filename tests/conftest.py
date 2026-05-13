import pytest
from unittest.mock import patch
from cryptography.fernet import Fernet

from app import create_app
from app import db as _db


TEST_CONFIG = {
    'TESTING': True,
    'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
    'JWT_SECRET_KEY': 'test-secret-key-long-enough-for-hmac-sha256',
    'ENCRYPTION_KEY': Fernet.generate_key(),
}

USER_1 = {
    'name': 'Dutronc',
    'surname': 'Thomas',
    'email': 'thomas.dutronc@gmail.com',
    'password': 'password1',
}


@pytest.fixture
def app():
    app = create_app(test_config=TEST_CONFIG)
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def no_demo_creation():
    """Disable demo family tree creation and email sending in tests."""
    with patch('app.views.user_view.create_demo_family_tree'):
        with patch('app.views.user_view.send_verification_email'):
            yield


@pytest.fixture
def created_user(client):
    response = client.post('/user', json=USER_1)
    assert response.status_code == 201
    # Bypass email flow: verify directly in DB
    from app.models import User
    user = User.query.filter_by(email=USER_1['email']).first()
    user.verified = True
    _db.session.commit()
    return response


@pytest.fixture
def auth_token(client, created_user):
    response = client.post('/login', json=USER_1)
    assert response.status_code == 200
    return response.get_json()['data']


@pytest.fixture
def auth_headers(auth_token):
    return {'Authorization': f'Bearer {auth_token}'}
