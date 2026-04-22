from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch


def test_health_returns_healthy(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["services"]["database"] == "healthy"


def test_health_reports_news_count(client, make_news):
    make_news(url="https://example.com/1")
    make_news(url="https://example.com/2")

    response = client.get("/health")
    assert response.json()["stats"]["total_news"] == 2


# ---------- GET /feed ----------

def test_get_feed_empty(client):
    response = client.get("/feed")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["size"] == 20


def test_get_feed_returns_news(client, make_news):
    make_news(url="https://example.com/1", title="Article One")
    make_news(url="https://example.com/2", title="Article Two")
    make_news(url="https://example.com/3", title="Article Three")

    response = client.get("/feed")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3


def test_get_feed_filter_by_category(client, make_news):
    make_news(url="https://example.com/1", category="россия")
    make_news(url="https://example.com/2", category="россия")
    make_news(url="https://example.com/3", category="мир")

    response = client.get("/feed?category=россия")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert all(item["category"] == "россия" for item in data["items"])


def test_get_feed_filter_excludes_other_categories(client, make_news):
    make_news(url="https://example.com/1", category="спорт")
    make_news(url="https://example.com/2", category="наука")

    response = client.get("/feed?category=спорт")
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["category"] == "спорт"


def test_get_feed_search_by_title(client, make_news):
    make_news(url="https://example.com/1", title="Санкции против России")
    make_news(url="https://example.com/2", title="Новости спорта")
    make_news(url="https://example.com/3", title="Санкционная политика")

    response = client.get("/feed?q=санкц")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2


def test_get_feed_search_by_description(client, make_news):
    make_news(url="https://example.com/1", title="Новость", description="Важные события в мире")
    make_news(url="https://example.com/2", title="Спорт", description="Спортивные достижения")

    response = client.get("/feed?q=мире")
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["url"] == "https://example.com/1"


def test_get_feed_search_case_insensitive(client, make_news):
    make_news(url="https://example.com/1", title="Россия сегодня")

    response = client.get("/feed?q=РОССИЯ")
    data = response.json()
    assert data["total"] == 1


def test_get_feed_pagination(client, make_news):
    for i in range(5):
        make_news(url=f"https://example.com/{i}", title=f"Article {i}")

    response = client.get("/feed?page=2&size=2")
    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 2
    assert data["size"] == 2
    assert len(data["items"]) == 2
    assert data["total"] == 5


def test_get_feed_pagination_last_page(client, make_news):
    for i in range(5):
        make_news(url=f"https://example.com/{i}", title=f"Article {i}")

    response = client.get("/feed?page=3&size=2")
    data = response.json()
    assert len(data["items"]) == 1
    assert data["total"] == 5


def test_get_feed_sorted_by_date_desc(client, make_news):
    older = datetime.now(timezone.utc) - timedelta(days=2)
    newer = datetime.now(timezone.utc) - timedelta(days=1)

    make_news(url="https://example.com/old", title="Old", published_at=older)
    make_news(url="https://example.com/new", title="New", published_at=newer)

    response = client.get("/feed")
    items = response.json()["items"]
    assert items[0]["url"] == "https://example.com/new"
    assert items[1]["url"] == "https://example.com/old"


# ---------- GET /news/{url} ----------

def test_get_news_by_url(client, make_news):
    make_news(url="https://ria.ru/news/test.html", title="Test News")

    response = client.get("/news/https://ria.ru/news/test.html")
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Test News"
    assert data["url"] == "https://ria.ru/news/test.html"


def test_get_news_by_url_not_found(client):
    response = client.get("/news/https://example.com/nonexistent")
    assert response.status_code == 404


# ---------- GET /news/id/{id} ----------

def test_get_news_by_id(client, make_news):
    item = make_news(url="https://example.com/1", title="By ID")

    response = client.get(f"/news/id/{item.id}")
    assert response.status_code == 200
    assert response.json()["id"] == item.id
    assert response.json()["title"] == "By ID"


def test_get_news_by_id_not_found(client):
    response = client.get("/news/id/99999")
    assert response.status_code == 404


# ---------- GET /categories ----------

def test_get_categories_shows_all_rss_categories(client):
    response = client.get("/categories")
    assert response.status_code == 200
    data = response.json()
    names = [c["name"] for c in data["categories"]]
    for expected in ["россия", "мир", "экономика", "наука", "спорт", "культура"]:
        assert expected in names


def test_get_categories_counts(client, make_news):
    make_news(url="https://example.com/1", category="россия")
    make_news(url="https://example.com/2", category="россия")
    make_news(url="https://example.com/3", category="мир")

    response = client.get("/categories")
    data = response.json()
    counts = {c["name"]: c["count"] for c in data["categories"]}
    assert counts["россия"] == 2
    assert counts["мир"] == 1
    assert counts["наука"] == 0


# ---------- POST /news/clean ----------

def test_clean_old_news_deletes_old_items(client, make_news):
    old_date = datetime.now(timezone.utc) - timedelta(days=40)
    make_news(url="https://example.com/old", published_at=old_date)
    make_news(url="https://example.com/recent")

    response = client.post("/news/clean?days=30")
    assert response.status_code == 200
    data = response.json()
    assert data["deleted_count"] == 1


def test_clean_old_news_keeps_recent(client, make_news):
    make_news(url="https://example.com/recent1")
    make_news(url="https://example.com/recent2")

    response = client.post("/news/clean?days=7")
    assert response.json()["deleted_count"] == 0


# ---------- GET /stats ----------

def test_get_stats(client, make_news):
    make_news(url="https://example.com/1", category="россия")
    make_news(url="https://example.com/2", category="мир")

    response = client.get("/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["total_news"] == 2
    assert data["newest_news"]["title"] is not None


def test_get_stats_empty_db(client):
    response = client.get("/stats")
    data = response.json()
    assert data["total_news"] == 0
    assert data["newest_news"]["title"] is None


# ---------- POST /rss/update/{category} ----------

def test_update_rss_unknown_category_returns_400(client):
    response = client.post("/rss/update/неизвестная_категория")
    assert response.status_code == 400


def test_update_rss_valid_category(client):
    with patch("app.main.update_category_async", new_callable=AsyncMock) as mock:
        mock.return_value = {
            "category": "россия",
            "parsed": 5,
            "saved": 5,
            "errors": 0,
            "duration_ms": 100,
        }
        response = client.post("/rss/update/россия")

    assert response.status_code == 200
    data = response.json()
    assert data["category"] == "россия"
    assert data["saved"] == 5
