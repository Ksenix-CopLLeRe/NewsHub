NEWS_URL = "https://ria.ru/20260421/test.html"
NEWS_URL_2 = "https://tass.ru/20260421/other.html"

TOGGLE_PAYLOAD = {
    "user_id": 1,
    "url": NEWS_URL,
    "title": "Test Article",
    "description": "Test description",
    "source_name": "РИА Новости",
    "published_at": "2026-04-21T10:00:00Z",
}


# ---------- GET /internal/health ----------

def test_health_returns_healthy(client):
    response = client.get("/internal/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "favorites_count" in data["stats"]
    assert "comments_count" in data["stats"]


# ---------- POST /favorites/toggle ----------

def test_toggle_adds_favorite(client):
    response = client.post("/favorites/toggle", json=TOGGLE_PAYLOAD)

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["is_favorite"] is True
    assert data["action"] == "added"


def test_toggle_removes_favorite(client):
    client.post("/favorites/toggle", json=TOGGLE_PAYLOAD)
    response = client.post("/favorites/toggle", json=TOGGLE_PAYLOAD)

    assert response.status_code == 200
    data = response.json()
    assert data["is_favorite"] is False
    assert data["action"] == "removed"


def test_toggle_add_after_remove(client):
    client.post("/favorites/toggle", json=TOGGLE_PAYLOAD)  # add
    client.post("/favorites/toggle", json=TOGGLE_PAYLOAD)  # remove
    response = client.post("/favorites/toggle", json=TOGGLE_PAYLOAD)  # add again

    assert response.json()["is_favorite"] is True
    assert response.json()["action"] == "added"


def test_toggle_isolated_per_user(client):
    # User 1 adds
    client.post("/favorites/toggle", json={**TOGGLE_PAYLOAD, "user_id": 1})
    # User 2 toggle on same URL — should add (independent)
    response = client.post("/favorites/toggle", json={**TOGGLE_PAYLOAD, "user_id": 2})

    assert response.json()["action"] == "added"


# ---------- GET /favorites/check/{url} ----------

def test_check_favorite_true(client):
    client.post("/favorites/toggle", json=TOGGLE_PAYLOAD)

    response = client.get(f"/favorites/check/{NEWS_URL}?user_id=1")

    assert response.status_code == 200
    data = response.json()
    assert data["is_favorite"] is True
    assert data["article_id"] is not None


def test_check_favorite_false_when_not_added(client):
    response = client.get(f"/favorites/check/{NEWS_URL}?user_id=1")

    data = response.json()
    assert data["is_favorite"] is False
    assert data["article_id"] is None


def test_check_favorite_false_after_removal(client):
    client.post("/favorites/toggle", json=TOGGLE_PAYLOAD)
    client.post("/favorites/toggle", json=TOGGLE_PAYLOAD)  # remove

    response = client.get(f"/favorites/check/{NEWS_URL}?user_id=1")

    assert response.json()["is_favorite"] is False


def test_check_favorite_user_isolated(client):
    client.post("/favorites/toggle", json={**TOGGLE_PAYLOAD, "user_id": 1})

    response = client.get(f"/favorites/check/{NEWS_URL}?user_id=2")

    assert response.json()["is_favorite"] is False


# ---------- GET /favorites ----------

def test_get_favorites_empty(client):
    response = client.get("/favorites?user_id=1")

    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0


def test_get_favorites_returns_items(client):
    client.post("/favorites/toggle", json={**TOGGLE_PAYLOAD, "url": NEWS_URL})
    client.post("/favorites/toggle", json={**TOGGLE_PAYLOAD, "url": NEWS_URL_2})

    response = client.get("/favorites?user_id=1")

    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


def test_get_favorites_only_for_requesting_user(client):
    client.post("/favorites/toggle", json={**TOGGLE_PAYLOAD, "user_id": 1})
    client.post("/favorites/toggle", json={**TOGGLE_PAYLOAD, "user_id": 2, "url": NEWS_URL_2})

    response = client.get("/favorites?user_id=1")

    assert response.json()["total"] == 1


def test_get_favorites_pagination(client):
    for i in range(5):
        client.post("/favorites/toggle", json={**TOGGLE_PAYLOAD, "url": f"https://example.com/{i}"})

    response = client.get("/favorites?user_id=1&page=2&size=2")

    data = response.json()
    assert data["page"] == 2
    assert data["size"] == 2
    assert len(data["items"]) == 2
    assert data["total"] == 5


def test_get_favorites_includes_comments(client, make_favorite, make_comment):
    fav = make_favorite(user_id=1, url=NEWS_URL)
    make_comment(article_id=fav["article_id"], user_id=1, text="My comment")

    response = client.get("/favorites?user_id=1&include_comments=true")

    item = response.json()["items"][0]
    assert len(item["comments"]) == 1
    assert item["comments"][0]["text"] == "My comment"


def test_get_favorites_excludes_comments_by_default(client, make_favorite, make_comment):
    fav = make_favorite()
    make_comment(article_id=fav["article_id"])

    response = client.get("/favorites?user_id=1")

    assert response.json()["items"][0]["comments"] == []


# ---------- GET /favorites/urls ----------

def test_get_favorite_urls_empty(client):
    response = client.get("/favorites/urls?user_id=1")

    assert response.status_code == 200
    data = response.json()
    assert data["urls"] == []
    assert data["total"] == 0


def test_get_favorite_urls_returns_list(client):
    client.post("/favorites/toggle", json={**TOGGLE_PAYLOAD, "url": NEWS_URL})
    client.post("/favorites/toggle", json={**TOGGLE_PAYLOAD, "url": NEWS_URL_2})

    response = client.get("/favorites/urls?user_id=1")

    data = response.json()
    assert data["total"] == 2
    assert NEWS_URL in data["urls"]
    assert NEWS_URL_2 in data["urls"]


def test_get_favorite_urls_user_isolated(client):
    client.post("/favorites/toggle", json={**TOGGLE_PAYLOAD, "user_id": 1})
    client.post("/favorites/toggle", json={**TOGGLE_PAYLOAD, "user_id": 2, "url": NEWS_URL_2})

    response = client.get("/favorites/urls?user_id=1")

    data = response.json()
    assert data["total"] == 1
    assert NEWS_URL in data["urls"]
