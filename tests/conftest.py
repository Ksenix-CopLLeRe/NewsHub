import pytest


@pytest.fixture
def user(db):
    from django.contrib.auth.models import User
    return User.objects.create_user(
        username="testuser", password="testpass123", email="test@example.com"
    )


@pytest.fixture
def superuser(db):
    from django.contrib.auth.models import User
    return User.objects.create_superuser(
        username="admin", password="adminpass123", email="admin@example.com"
    )


@pytest.fixture
def auth_client(client, user):
    client.login(username="testuser", password="testpass123")
    return client


@pytest.fixture
def superuser_client(client, superuser):
    client.login(username="admin", password="adminpass123")
    return client
