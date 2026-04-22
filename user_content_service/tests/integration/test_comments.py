NEWS_URL = "https://ria.ru/20260421/test.html"


# ---------- POST /favorites/{articleId}/comments ----------

def test_add_comment(client, make_favorite):
    fav = make_favorite()

    response = client.post(
        f"/favorites/{fav['article_id']}/comments",
        json={"user_id": 1, "text": "Great article!"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert data["comment"]["text"] == "Great article!"
    assert data["comment"]["user_id"] == 1
    assert "id" in data["comment"]


def test_add_comment_to_nonexistent_article_returns_404(client):
    response = client.post(
        "/favorites/99999/comments",
        json={"user_id": 1, "text": "Comment"},
    )

    assert response.status_code == 404


def test_add_comment_to_another_users_article_returns_404(client, make_favorite):
    fav = make_favorite(user_id=1)

    # User 2 cannot comment on user 1's favorite
    response = client.post(
        f"/favorites/{fav['article_id']}/comments",
        json={"user_id": 2, "text": "Trying to comment"},
    )

    assert response.status_code == 404


def test_add_comment_empty_text_returns_400(client, make_favorite):
    fav = make_favorite()

    response = client.post(
        f"/favorites/{fav['article_id']}/comments",
        json={"user_id": 1, "text": "   "},
    )

    assert response.status_code == 400


def test_add_multiple_comments(client, make_favorite):
    fav = make_favorite()

    client.post(f"/favorites/{fav['article_id']}/comments", json={"user_id": 1, "text": "First"})
    client.post(f"/favorites/{fav['article_id']}/comments", json={"user_id": 1, "text": "Second"})

    response = client.get(f"/favorites/{fav['article_id']}/comments?user_id=1")
    assert response.json()["total"] == 2


# ---------- GET /favorites/{articleId}/comments ----------

def test_get_comments_empty(client, make_favorite):
    fav = make_favorite()

    response = client.get(f"/favorites/{fav['article_id']}/comments?user_id=1")

    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0


def test_get_comments_returns_items(client, make_favorite, make_comment):
    fav = make_favorite()
    make_comment(article_id=fav["article_id"], text="Comment one")
    make_comment(article_id=fav["article_id"], text="Comment two")

    response = client.get(f"/favorites/{fav['article_id']}/comments?user_id=1")

    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


def test_get_comments_pagination(client, make_favorite, make_comment):
    fav = make_favorite()
    for i in range(5):
        make_comment(article_id=fav["article_id"], text=f"Comment {i}")

    response = client.get(f"/favorites/{fav['article_id']}/comments?user_id=1&page=2&size=2")

    data = response.json()
    assert data["page"] == 2
    assert data["size"] == 2
    assert len(data["items"]) == 2
    assert data["total"] == 5


def test_get_comments_for_nonexistent_article_returns_404(client):
    response = client.get("/favorites/99999/comments?user_id=1")

    assert response.status_code == 404


# ---------- PUT /comments/{commentId} ----------

def test_edit_comment(client, make_favorite, make_comment):
    fav = make_favorite()
    comment = make_comment(article_id=fav["article_id"], text="Original text")

    response = client.put(
        f"/comments/{comment['id']}",
        json={"user_id": 1, "text": "Updated text"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["comment"]["text"] == "Updated text"


def test_edit_comment_strips_whitespace(client, make_favorite, make_comment):
    fav = make_favorite()
    comment = make_comment(article_id=fav["article_id"])

    response = client.put(
        f"/comments/{comment['id']}",
        json={"user_id": 1, "text": "  Trimmed  "},
    )

    assert response.json()["comment"]["text"] == "Trimmed"


def test_edit_comment_by_non_owner_returns_403(client, make_favorite, make_comment):
    fav = make_favorite(user_id=1)
    comment = make_comment(article_id=fav["article_id"], user_id=1)

    response = client.put(
        f"/comments/{comment['id']}",
        json={"user_id": 2, "text": "Hacker text"},
    )

    assert response.status_code == 403


def test_edit_comment_not_found_returns_404(client):
    response = client.put(
        "/comments/99999",
        json={"user_id": 1, "text": "New text"},
    )

    assert response.status_code == 404


def test_edit_comment_empty_text_returns_400(client, make_favorite, make_comment):
    fav = make_favorite()
    comment = make_comment(article_id=fav["article_id"])

    response = client.put(
        f"/comments/{comment['id']}",
        json={"user_id": 1, "text": ""},
    )

    assert response.status_code == 400


# ---------- DELETE /comments/{commentId} ----------

def test_delete_comment(client, make_favorite, make_comment):
    fav = make_favorite()
    comment = make_comment(article_id=fav["article_id"])

    response = client.delete(f"/comments/{comment['id']}?user_id=1")

    assert response.status_code == 200
    assert response.json()["success"] is True


def test_delete_comment_actually_removes_it(client, make_favorite, make_comment):
    fav = make_favorite()
    comment = make_comment(article_id=fav["article_id"])

    client.delete(f"/comments/{comment['id']}?user_id=1")

    response = client.get(f"/favorites/{fav['article_id']}/comments?user_id=1")
    assert response.json()["total"] == 0


def test_delete_comment_by_non_owner_returns_403(client, make_favorite, make_comment):
    fav = make_favorite(user_id=1)
    comment = make_comment(article_id=fav["article_id"], user_id=1)

    response = client.delete(f"/comments/{comment['id']}?user_id=2")

    assert response.status_code == 403


def test_delete_comment_not_found_returns_404(client):
    response = client.delete("/comments/99999?user_id=1")

    assert response.status_code == 404


def test_delete_favorite_cascades_comments(client, make_favorite, make_comment):
    fav = make_favorite(user_id=1, url=NEWS_URL)
    make_comment(article_id=fav["article_id"], text="Will be deleted")
    make_comment(article_id=fav["article_id"], text="Also deleted")

    # Remove from favorites (toggle removes it)
    client.post(
        "/favorites/toggle",
        json={"user_id": 1, "url": NEWS_URL, "title": "T", "source_name": "S"},
    )

    # Article is gone, so 404 on its comments
    response = client.get(f"/favorites/{fav['article_id']}/comments?user_id=1")
    assert response.status_code == 404
