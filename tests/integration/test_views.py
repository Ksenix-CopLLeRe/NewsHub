import re
import pytest
import responses as rsps

FEED_URL = "http://feed-service:8000"
REACTIONS_URL = "http://reactions-service:8000"
USER_CONTENT_URL = "http://user-content-service:8002"

MOCK_ARTICLE = {
    "url": "https://lenta.ru/news/test/",
    "title": "Тестовая новость",
    "description": "Тестовое описание",
    "image_url": "https://example.com/image.jpg",
    "source_name": "Lenta.ru",
    "published_at": "2026-04-22T10:00:00Z",
    "category": "россия",
}

MOCK_ARTICLE_WITHOUT_IMAGE = {
    **MOCK_ARTICLE,
    "url": "https://lenta.ru/news/no-image/",
    "title": "Новость без картинки",
    "image_url": "   ",
}

MOCK_FEED = {"items": [MOCK_ARTICLE], "total": 1, "page": 1, "size": 20}
EMPTY_COUNTS = {"counts": {"important": 0, "interesting": 0, "shocking": 0, "useful": 0, "liked": 0}, "total": 0}
EMPTY_REACTIONS = {"items": [], "total": 0, "page": 1, "size": 100}


def _mock_authenticated_home(mock):
    mock.add(rsps.GET, f"{FEED_URL}/feed", json=MOCK_FEED)
    mock.add(rsps.GET, f"{USER_CONTENT_URL}/favorites/urls", json={"urls": []})
    mock.add(rsps.GET, re.compile(rf"{REACTIONS_URL}/reactions/counts/.*"), json=EMPTY_COUNTS)
    mock.add(rsps.GET, re.compile(rf"{REACTIONS_URL}/reactions/news/.*"), json=EMPTY_REACTIONS)


@pytest.mark.django_db
class TestHomeView:
    def test_anonymous_user_sees_feed(self, client):
        with rsps.RequestsMock() as mock:
            mock.add(rsps.GET, f"{FEED_URL}/feed", json=MOCK_FEED)
            response = client.get("/")
        assert response.status_code == 200

    def test_anonymous_user_articles_in_response(self, client):
        with rsps.RequestsMock() as mock:
            mock.add(rsps.GET, f"{FEED_URL}/feed", json=MOCK_FEED)
            response = client.get("/")
        assert "Тестовая новость" in response.content.decode("utf-8")

    def test_article_without_image_renders_without_placeholder(self, client):
        with rsps.RequestsMock() as mock:
            mock.add(
                rsps.GET,
                f"{FEED_URL}/feed",
                json={"items": [MOCK_ARTICLE_WITHOUT_IMAGE], "total": 1, "page": 1, "size": 20},
            )
            response = client.get("/")
        content = response.content.decode("utf-8")
        assert "Новость без картинки" in content
        assert "/static/images/no-image.png" not in content
        assert 'src="   "' not in content

    def test_authenticated_user_calls_reactions_and_favorites(self, auth_client):
        with rsps.RequestsMock() as mock:
            _mock_authenticated_home(mock)
            response = auth_client.get("/")
        assert response.status_code == 200

    def test_category_filter_is_passed_to_feed(self, client):
        with rsps.RequestsMock() as mock:
            mock.add(rsps.GET, f"{FEED_URL}/feed", json=MOCK_FEED)
            response = client.get("/?category=russia")
            assert "category=%D1%80%D0%BE%D1%81%D1%81%D0%B8%D1%8F" in mock.calls[0].request.url
        assert response.status_code == 200

    def test_search_query_is_passed_to_feed(self, client):
        with rsps.RequestsMock() as mock:
            mock.add(rsps.GET, f"{FEED_URL}/feed", json=MOCK_FEED)
            response = client.get("/?q=тест")
            assert "q=" in mock.calls[0].request.url
        assert response.status_code == 200

    def test_feed_service_error_shows_empty_page(self, client):
        import requests as req_lib
        with rsps.RequestsMock(assert_all_requests_are_fired=False) as mock:
            mock.add(rsps.GET, f"{FEED_URL}/feed", body=req_lib.exceptions.ConnectionError())
            response = client.get("/")
        assert response.status_code == 200

    def test_pagination_params_forwarded(self, client):
        with rsps.RequestsMock() as mock:
            mock.add(rsps.GET, f"{FEED_URL}/feed", json=MOCK_FEED)
            response = client.get("/?page=2&size=10")
            assert "page=2" in mock.calls[0].request.url
            assert "size=10" in mock.calls[0].request.url
        assert response.status_code == 200


@pytest.mark.django_db
class TestFavoritesView:
    def test_anonymous_redirects_to_login(self, client):
        response = client.get("/favorites/")
        assert response.status_code == 302
        assert "login" in response.url

    def test_authenticated_user_sees_favorites_page(self, auth_client):
        with rsps.RequestsMock() as mock:
            mock.add(rsps.GET, f"{USER_CONTENT_URL}/favorites", json={"items": [], "total": 0, "page": 1, "size": 20})
            response = auth_client.get("/favorites/")
        assert response.status_code == 200

    def test_favorites_service_error_shows_empty(self, auth_client):
        import requests as req_lib
        with rsps.RequestsMock() as mock:
            mock.add(rsps.GET, f"{USER_CONTENT_URL}/favorites", body=req_lib.exceptions.ConnectionError())
            response = auth_client.get("/favorites/")
        assert response.status_code == 200


@pytest.mark.django_db
class TestAdminStatsView:
    def test_regular_user_redirected_to_home(self, auth_client):
        response = auth_client.get("/management/stats/")
        assert response.status_code == 302
        assert response.url == "/"

    def test_anonymous_redirected_to_login(self, client):
        response = client.get("/management/stats/")
        assert response.status_code == 302
        assert "login" in response.url

    def test_superuser_sees_stats_page(self, superuser_client):
        with rsps.RequestsMock() as mock:
            mock.add(rsps.GET, f"{FEED_URL}/stats", json={"total": 100})
            mock.add(rsps.GET, f"{REACTIONS_URL}/", json={"status": "running"})
            mock.add(rsps.GET, f"{USER_CONTENT_URL}/internal/health", json={"status": "healthy"})
            response = superuser_client.get("/management/stats/")
        assert response.status_code == 200

    def test_superuser_sees_stats_when_services_unreachable(self, superuser_client):
        import requests as req_lib
        with rsps.RequestsMock(assert_all_requests_are_fired=False) as mock:
            mock.add(rsps.GET, f"{FEED_URL}/stats", body=req_lib.exceptions.ConnectionError())
            mock.add(rsps.GET, f"{REACTIONS_URL}/", body=req_lib.exceptions.ConnectionError())
            mock.add(rsps.GET, f"{USER_CONTENT_URL}/internal/health", body=req_lib.exceptions.ConnectionError())
            response = superuser_client.get("/management/stats/")
        assert response.status_code == 200
