import respx
import httpx
from unittest.mock import patch

JSONPLACEHOLDER = "https://jsonplaceholder.typicode.com"

POSTS = [{"id": i, "title": f"title {i}", "body": f"body {i}", "userId": 1} for i in range(1, 101)]
USERS = [{"id": i, "name": f"User {i}"} for i in range(1, 11)]
COMMENTS = [{"id": i, "postId": 1, "body": f"comment {i}"} for i in range(1, 101)]


# ---------- GET /external/news ----------

def test_external_news_default_limit(client):
    with respx.mock:
        respx.get(f"{JSONPLACEHOLDER}/posts").mock(return_value=httpx.Response(200, json=POSTS))
        response = client.get("/external/news")

    assert response.status_code == 200
    data = response.json()
    assert len(data["news"]) == 5
    assert data["total"] == 5
    assert data["source"] == "external API"


def test_external_news_custom_limit(client):
    with respx.mock:
        respx.get(f"{JSONPLACEHOLDER}/posts").mock(return_value=httpx.Response(200, json=POSTS))
        response = client.get("/external/news?limit=3")

    data = response.json()
    assert len(data["news"]) == 3
    assert data["total"] == 3


def test_external_news_max_limit(client):
    with respx.mock:
        respx.get(f"{JSONPLACEHOLDER}/posts").mock(return_value=httpx.Response(200, json=POSTS))
        response = client.get("/external/news?limit=20")

    assert response.json()["total"] == 20


def test_external_news_limit_above_max_returns_422(client):
    response = client.get("/external/news?limit=21")
    assert response.status_code == 422


def test_external_news_limit_zero_returns_422(client):
    response = client.get("/external/news?limit=0")
    assert response.status_code == 422


def test_external_news_item_structure(client):
    with respx.mock:
        respx.get(f"{JSONPLACEHOLDER}/posts").mock(return_value=httpx.Response(200, json=POSTS))
        response = client.get("/external/news?limit=1")

    item = response.json()["news"][0]
    assert {"id", "title", "body", "source"} <= item.keys()
    assert item["source"] == "jsonplaceholder"


# ---------- GET /external/combined ----------

def test_external_combined_returns_data_from_all_sources(client):
    with respx.mock:
        respx.get(f"{JSONPLACEHOLDER}/posts").mock(return_value=httpx.Response(200, json=POSTS))
        respx.get(f"{JSONPLACEHOLDER}/users").mock(return_value=httpx.Response(200, json=USERS))
        respx.get(f"{JSONPLACEHOLDER}/comments").mock(return_value=httpx.Response(200, json=COMMENTS))
        response = client.get("/external/combined")

    assert response.status_code == 200
    data = response.json()
    assert "posts" in data and "users" in data and "comments" in data
    assert len(data["posts"]) == 3
    assert len(data["users"]) == 3
    assert len(data["comments"]) == 3


def test_external_combined_includes_message(client):
    with respx.mock:
        respx.get(f"{JSONPLACEHOLDER}/posts").mock(return_value=httpx.Response(200, json=POSTS))
        respx.get(f"{JSONPLACEHOLDER}/users").mock(return_value=httpx.Response(200, json=USERS))
        respx.get(f"{JSONPLACEHOLDER}/comments").mock(return_value=httpx.Response(200, json=COMMENTS))
        data = client.get("/external/combined").json()

    assert "message" in data


# ---------- POST /reports/generate + GET /reports/status ----------

def test_generate_report_returns_pending(client):
    with patch("time.sleep"):
        response = client.post("/reports/generate")

    assert response.status_code == 200
    data = response.json()
    assert "report_id" in data
    assert data["status"] == "pending"
    assert "message" in data


def test_generate_report_with_news_id(client):
    with patch("time.sleep"):
        response = client.post("/reports/generate?news_id=https://example.com/1")

    assert response.status_code == 200
    assert "report_id" in response.json()


def test_each_report_gets_unique_id(client):
    with patch("time.sleep"):
        id1 = client.post("/reports/generate").json()["report_id"]
        id2 = client.post("/reports/generate").json()["report_id"]

    assert id1 != id2


def test_report_status_accessible_after_generate(client):
    with patch("time.sleep"):
        report_id = client.post("/reports/generate").json()["report_id"]
        response = client.get(f"/reports/status/{report_id}")

    assert response.status_code == 200
    assert response.json()["status"] in {"pending", "completed"}


def test_report_status_completed_after_background_task(client):
    with patch("time.sleep"):
        report_id = client.post("/reports/generate").json()["report_id"]

    response = client.get(f"/reports/status/{report_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    result = response.json()["result"]
    assert result is not None
    assert "report_id" in result


def test_report_status_not_found(client):
    response = client.get("/reports/status/99999999")
    assert response.status_code == 404
