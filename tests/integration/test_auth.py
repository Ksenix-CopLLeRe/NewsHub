import pytest


@pytest.mark.django_db
class TestRegister:
    def test_register_page_loads(self, client):
        response = client.get("/register/")
        assert response.status_code == 200

    def test_register_valid_user_redirects_to_home(self, client):
        response = client.post("/register/", {
            "username": "newuser",
            "password1": "TestPass1234!",
            "password2": "TestPass1234!",
        })
        assert response.status_code == 302
        assert response.url == "/"

    def test_register_password_mismatch_stays_on_page(self, client):
        response = client.post("/register/", {
            "username": "newuser",
            "password1": "TestPass1234!",
            "password2": "DifferentPass!",
        })
        assert response.status_code == 200

    def test_register_duplicate_username_stays_on_page(self, client, user):
        response = client.post("/register/", {
            "username": "testuser",
            "password1": "TestPass1234!",
            "password2": "TestPass1234!",
        })
        assert response.status_code == 200


@pytest.mark.django_db
class TestLogin:
    def test_login_page_loads(self, client):
        response = client.get("/login/")
        assert response.status_code == 200

    def test_login_valid_credentials_redirects_to_home(self, client, user):
        response = client.post("/login/", {
            "username": "testuser",
            "password": "testpass123",
        })
        assert response.status_code == 302
        assert response.url == "/"

    def test_login_wrong_password_stays_on_page(self, client, user):
        response = client.post("/login/", {
            "username": "testuser",
            "password": "wrongpassword",
        })
        assert response.status_code == 200

    def test_login_unknown_user_stays_on_page(self, client, db):
        response = client.post("/login/", {
            "username": "nobody",
            "password": "whatever",
        })
        assert response.status_code == 200


@pytest.mark.django_db
class TestLogout:
    def test_logout_redirects_to_home(self, auth_client):
        response = auth_client.get("/logout/")
        assert response.status_code == 302
        assert response.url == "/"

    def test_logout_works_for_anonymous(self, client):
        response = client.get("/logout/")
        assert response.status_code == 302
        assert response.url == "/"
