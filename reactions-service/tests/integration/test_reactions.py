NEWS_ID = "https://ria.ru/20260421/test.html"


# ---------- POST /reactions (create / toggle / update) ----------

def test_create_reaction(client):
    payload = {"user_id": 1, "news_id": NEWS_ID, "reaction_type": "important"}
    response = client.post("/reactions", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert data["action"] == "created"
    assert data["reaction"]["user_id"] == 1
    assert data["reaction"]["news_id"] == NEWS_ID
    assert data["reaction"]["reaction_type"] == "important"
    assert "id" in data["reaction"]


def test_create_reaction_same_type_toggles_delete(client):
    payload = {"user_id": 1, "news_id": NEWS_ID, "reaction_type": "interesting"}

    client.post("/reactions", json=payload)
    response = client.post("/reactions", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["action"] == "deleted"
    assert data["reaction"]["reaction_type"] == "interesting"


def test_create_reaction_different_type_updates(client):
    client.post("/reactions", json={"user_id": 1, "news_id": NEWS_ID, "reaction_type": "important"})
    response = client.post("/reactions", json={"user_id": 1, "news_id": NEWS_ID, "reaction_type": "liked"})

    assert response.status_code == 201
    data = response.json()
    assert data["action"] == "updated"
    assert data["reaction"]["reaction_type"] == "liked"


def test_toggle_delete_then_recreate(client):
    payload = {"user_id": 1, "news_id": NEWS_ID, "reaction_type": "useful"}

    client.post("/reactions", json=payload)   # created
    client.post("/reactions", json=payload)   # deleted
    response = client.post("/reactions", json=payload)  # created again

    assert response.json()["action"] == "created"


def test_different_users_can_react_to_same_news(client):
    client.post("/reactions", json={"user_id": 1, "news_id": NEWS_ID, "reaction_type": "important"})
    response = client.post("/reactions", json={"user_id": 2, "news_id": NEWS_ID, "reaction_type": "important"})

    assert response.status_code == 201
    assert response.json()["action"] == "created"


def test_same_user_can_react_to_different_news(client):
    client.post("/reactions", json={"user_id": 1, "news_id": NEWS_ID, "reaction_type": "important"})
    response = client.post("/reactions", json={"user_id": 1, "news_id": "https://example.com/other", "reaction_type": "important"})

    assert response.status_code == 201
    assert response.json()["action"] == "created"


# ---------- DELETE /reactions/{id} ----------

def test_delete_reaction_by_owner(client, make_reaction):
    reaction = make_reaction(user_id=5)

    response = client.delete(f"/reactions/{reaction.id}", headers={"x-user-id": "5"})

    assert response.status_code == 200
    assert response.json()["success"] is True


def test_delete_reaction_by_non_owner_returns_403(client, make_reaction):
    reaction = make_reaction(user_id=10)

    response = client.delete(f"/reactions/{reaction.id}", headers={"x-user-id": "99"})

    assert response.status_code == 403


def test_delete_reaction_not_found_returns_404(client):
    response = client.delete("/reactions/99999", headers={"x-user-id": "1"})

    assert response.status_code == 404


def test_delete_requires_x_user_id_header(client, make_reaction):
    reaction = make_reaction()

    response = client.delete(f"/reactions/{reaction.id}")

    assert response.status_code == 422


# ---------- GET /reactions/news/{news_id} ----------

def test_get_reactions_by_news_empty(client):
    response = client.get(f"/reactions/news/{NEWS_ID}")

    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0


def test_get_reactions_by_news_returns_items(client, make_reaction):
    make_reaction(user_id=1, news_id=NEWS_ID, reaction_type="important")
    make_reaction(user_id=2, news_id=NEWS_ID, reaction_type="liked")

    response = client.get(f"/reactions/news/{NEWS_ID}")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


def test_get_reactions_by_news_pagination(client, make_reaction):
    for i in range(5):
        make_reaction(user_id=i + 1, news_id=NEWS_ID)

    response = client.get(f"/reactions/news/{NEWS_ID}?page=2&size=2")

    data = response.json()
    assert data["page"] == 2
    assert data["size"] == 2
    assert len(data["items"]) == 2
    assert data["total"] == 5


def test_get_reactions_only_returns_matching_news(client, make_reaction):
    make_reaction(user_id=1, news_id=NEWS_ID)
    make_reaction(user_id=1, news_id="https://other.com/news")

    response = client.get(f"/reactions/news/{NEWS_ID}")

    assert response.json()["total"] == 1


# ---------- GET /reactions/counts/{news_id} ----------

def test_get_counts_empty(client):
    response = client.get(f"/reactions/counts/{NEWS_ID}")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    for reaction_type in ["important", "interesting", "shocking", "useful", "liked"]:
        assert data["counts"][reaction_type] == 0


def test_get_counts_aggregates_by_type(client, make_reaction):
    make_reaction(user_id=1, news_id=NEWS_ID, reaction_type="important")
    make_reaction(user_id=2, news_id=NEWS_ID, reaction_type="important")
    make_reaction(user_id=3, news_id=NEWS_ID, reaction_type="interesting")

    response = client.get(f"/reactions/counts/{NEWS_ID}")

    data = response.json()
    assert data["total"] == 3
    assert data["counts"]["important"] == 2
    assert data["counts"]["interesting"] == 1
    assert data["counts"]["shocking"] == 0


def test_get_counts_only_for_target_news(client, make_reaction):
    make_reaction(user_id=1, news_id=NEWS_ID, reaction_type="liked")
    make_reaction(user_id=1, news_id="https://other.com/news", reaction_type="liked")

    response = client.get(f"/reactions/counts/{NEWS_ID}")

    assert response.json()["total"] == 1


def test_get_counts_all_reaction_types(client, make_reaction):
    types = ["important", "interesting", "shocking", "useful", "liked"]
    for i, rtype in enumerate(types):
        make_reaction(user_id=i + 1, news_id=NEWS_ID, reaction_type=rtype)

    response = client.get(f"/reactions/counts/{NEWS_ID}")

    data = response.json()
    assert data["total"] == 5
    for rtype in types:
        assert data["counts"][rtype] == 1
