import json
import re
import pytest
import responses as rsps

REACTIONS_URL = "http://reactions-service:8000"
USER_CONTENT_URL = "http://user-content-service:8002"

ARTICLE_PAYLOAD = {
    "url": "https://lenta.ru/news/test/",
    "title": "Тестовая новость",
    "description": "Тестовое описание",
    "source": {"name": "Lenta.ru"},
    "urlToImage": "https://example.com/image.jpg",
    "publishedAt": "2026-04-22T10:00:00Z",
}

TOGGLE_SUCCESS = {"success": True, "is_favorite": True, "action": "added"}
TOGGLE_REMOVED = {"success": True, "is_favorite": False, "action": "removed"}


def post_json(client, url, data):
    return client.post(url, data=json.dumps(data), content_type="application/json")


# ---------- POST /api/toggle-favorite/ ----------

@pytest.mark.django_db
class TestToggleFavorite:
    def test_anonymous_redirects_to_login(self, client):
        response = post_json(client, "/api/toggle-favorite/", ARTICLE_PAYLOAD)
        assert response.status_code == 302
        assert "login" in response.url

    def test_add_article_to_favorites(self, auth_client):
        with rsps.RequestsMock() as mock:
            mock.add(rsps.POST, f"{USER_CONTENT_URL}/favorites/toggle", json=TOGGLE_SUCCESS, status=200)
            response = post_json(auth_client, "/api/toggle-favorite/", ARTICLE_PAYLOAD)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["action"] == "added"

    def test_remove_article_from_favorites(self, auth_client):
        with rsps.RequestsMock() as mock:
            mock.add(rsps.POST, f"{USER_CONTENT_URL}/favorites/toggle", json=TOGGLE_REMOVED, status=200)
            response = post_json(auth_client, "/api/toggle-favorite/", ARTICLE_PAYLOAD)
        assert response.json()["action"] == "removed"

    def test_invalid_json_returns_400(self, auth_client):
        response = auth_client.post("/api/toggle-favorite/", data="not-json", content_type="application/json")
        assert response.status_code == 400

    def test_empty_source_name_defaults_to_lenta(self, auth_client):
        with rsps.RequestsMock() as mock:
            mock.add(rsps.POST, f"{USER_CONTENT_URL}/favorites/toggle", json=TOGGLE_SUCCESS, status=200)
            payload = {**ARTICLE_PAYLOAD, "source": {"name": ""}}
            post_json(auth_client, "/api/toggle-favorite/", payload)
            sent = json.loads(mock.calls[0].request.body)
        assert sent["source_name"] == "Lenta.ru"

    def test_empty_title_defaults_to_placeholder(self, auth_client):
        with rsps.RequestsMock() as mock:
            mock.add(rsps.POST, f"{USER_CONTENT_URL}/favorites/toggle", json=TOGGLE_SUCCESS, status=200)
            payload = {**ARTICLE_PAYLOAD, "title": ""}
            post_json(auth_client, "/api/toggle-favorite/", payload)
            sent = json.loads(mock.calls[0].request.body)
        assert sent["title"] == "Новость без заголовка"

    def test_empty_image_url_not_sent(self, auth_client):
        with rsps.RequestsMock() as mock:
            mock.add(rsps.POST, f"{USER_CONTENT_URL}/favorites/toggle", json=TOGGLE_SUCCESS, status=200)
            payload = {**ARTICLE_PAYLOAD, "urlToImage": ""}
            post_json(auth_client, "/api/toggle-favorite/", payload)
            sent = json.loads(mock.calls[0].request.body)
        assert "url_to_image" not in sent


# ---------- POST /api/add-reaction/ ----------

@pytest.mark.django_db
class TestAddReaction:
    def test_anonymous_redirects_to_login(self, client):
        response = post_json(client, "/api/add-reaction/", {"url": "https://example.com", "reaction_type": "liked"})
        assert response.status_code == 302
        assert "login" in response.url

    def test_missing_url_returns_400(self, auth_client):
        response = post_json(auth_client, "/api/add-reaction/", {"reaction_type": "liked"})
        assert response.status_code == 400

    def test_missing_reaction_type_returns_400(self, auth_client):
        response = post_json(auth_client, "/api/add-reaction/", {"url": "https://example.com"})
        assert response.status_code == 400

    def test_invalid_json_returns_400(self, auth_client):
        response = auth_client.post("/api/add-reaction/", data="bad", content_type="application/json")
        assert response.status_code == 400

    def test_valid_reaction_returns_success_with_counts(self, auth_client):
        reaction_resp = {"success": True, "action": "created", "reaction": {"reaction_type": "liked"}}
        counts_resp = {"counts": {"liked": 1, "important": 0, "interesting": 0, "shocking": 0, "useful": 0}, "total": 1}
        with rsps.RequestsMock() as mock:
            mock.add(rsps.POST, f"{REACTIONS_URL}/reactions", json=reaction_resp, status=200)
            mock.add(rsps.GET, re.compile(rf"{REACTIONS_URL}/reactions/counts/.*"), json=counts_resp)
            response = post_json(auth_client, "/api/add-reaction/",
                                 {"url": "https://example.com", "reaction_type": "liked"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "reactions_count" in data

    def test_toggle_delete_reaction(self, auth_client):
        reaction_resp = {"success": True, "action": "deleted", "reaction": {"reaction_type": "liked"}}
        counts_resp = {"counts": {"liked": 0, "important": 0, "interesting": 0, "shocking": 0, "useful": 0}, "total": 0}
        with rsps.RequestsMock() as mock:
            mock.add(rsps.POST, f"{REACTIONS_URL}/reactions", json=reaction_resp, status=200)
            mock.add(rsps.GET, re.compile(rf"{REACTIONS_URL}/reactions/counts/.*"), json=counts_resp)
            response = post_json(auth_client, "/api/add-reaction/",
                                 {"url": "https://example.com", "reaction_type": "liked"})
        assert response.json()["action"] == "deleted"


# ---------- POST /api/add-comment/ ----------

@pytest.mark.django_db
class TestAddComment:
    def test_anonymous_redirects_to_login(self, client):
        response = post_json(client, "/api/add-comment/", {"article_id": 1, "text": "Привет"})
        assert response.status_code == 302
        assert "login" in response.url

    def test_missing_article_id_returns_400(self, auth_client):
        response = post_json(auth_client, "/api/add-comment/", {"text": "Комментарий"})
        assert response.status_code == 400

    def test_empty_text_returns_400(self, auth_client):
        response = post_json(auth_client, "/api/add-comment/", {"article_id": 1, "text": ""})
        assert response.status_code == 400

    def test_whitespace_text_returns_400(self, auth_client):
        response = post_json(auth_client, "/api/add-comment/", {"article_id": 1, "text": "   "})
        assert response.status_code == 400

    def test_invalid_json_returns_400(self, auth_client):
        response = auth_client.post("/api/add-comment/", data="bad", content_type="application/json")
        assert response.status_code == 400

    def test_valid_comment_returns_success(self, auth_client):
        comment_data = {"success": True, "comment": {"id": 1, "text": "Привет", "created_at": "2026-04-22T10:00:00Z"}}
        with rsps.RequestsMock() as mock:
            mock.add(rsps.POST, f"{USER_CONTENT_URL}/favorites/1/comments", json=comment_data, status=200)
            response = post_json(auth_client, "/api/add-comment/", {"article_id": 1, "text": "Привет"})
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_comment_date_formatted_as_dd_mm_yyyy(self, auth_client):
        comment_data = {"success": True, "comment": {"id": 1, "text": "Тест", "created_at": "2026-04-22T10:30:00Z"}}
        with rsps.RequestsMock() as mock:
            mock.add(rsps.POST, f"{USER_CONTENT_URL}/favorites/1/comments", json=comment_data, status=200)
            response = post_json(auth_client, "/api/add-comment/", {"article_id": 1, "text": "Тест"})
        assert response.json()["comment"]["created_at"] == "22.04.2026 10:30"


# ---------- POST /api/edit-comment/<id>/ ----------

@pytest.mark.django_db
class TestEditComment:
    def test_anonymous_redirects_to_login(self, client):
        response = post_json(client, "/api/edit-comment/1/", {"text": "Новый текст"})
        assert response.status_code == 302
        assert "login" in response.url

    def test_empty_text_returns_400(self, auth_client):
        response = post_json(auth_client, "/api/edit-comment/1/", {"text": ""})
        assert response.status_code == 400

    def test_whitespace_text_returns_400(self, auth_client):
        response = post_json(auth_client, "/api/edit-comment/1/", {"text": "   "})
        assert response.status_code == 400

    def test_invalid_json_returns_400(self, auth_client):
        response = auth_client.post("/api/edit-comment/1/", data="bad", content_type="application/json")
        assert response.status_code == 400

    def test_valid_edit_returns_success(self, auth_client):
        comment_data = {"success": True, "comment": {"id": 1, "text": "Новый текст", "created_at": "2026-04-22T10:00:00Z"}}
        with rsps.RequestsMock() as mock:
            mock.add(rsps.PUT, f"{USER_CONTENT_URL}/comments/1", json=comment_data, status=200)
            response = post_json(auth_client, "/api/edit-comment/1/", {"text": "Новый текст"})
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_edit_formats_date_in_response(self, auth_client):
        comment_data = {"success": True, "comment": {"id": 1, "text": "Текст", "created_at": "2026-04-22T15:45:00Z"}}
        with rsps.RequestsMock() as mock:
            mock.add(rsps.PUT, f"{USER_CONTENT_URL}/comments/1", json=comment_data, status=200)
            response = post_json(auth_client, "/api/edit-comment/1/", {"text": "Текст"})
        assert response.json()["comment"]["created_at"] == "22.04.2026 15:45"


# ---------- POST /api/delete-comment/<id>/ ----------

@pytest.mark.django_db
class TestDeleteComment:
    def test_anonymous_redirects_to_login(self, client):
        response = client.post("/api/delete-comment/1/")
        assert response.status_code == 302
        assert "login" in response.url

    def test_valid_delete_returns_success(self, auth_client):
        with rsps.RequestsMock() as mock:
            mock.add(rsps.DELETE, f"{USER_CONTENT_URL}/comments/1", json={"success": True}, status=200)
            response = auth_client.post("/api/delete-comment/1/")
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_service_error_returns_500(self, auth_client):
        import requests as req_lib
        with rsps.RequestsMock() as mock:
            mock.add(rsps.DELETE, f"{USER_CONTENT_URL}/comments/1", body=req_lib.exceptions.ConnectionError())
            response = auth_client.post("/api/delete-comment/1/")
        assert response.status_code == 500
