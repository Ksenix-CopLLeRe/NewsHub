# tests/user_content_service/test_main.py
"""
Юнит-тесты для User Content Service
"""

import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_user_content.db"

import user_content_service.main as main
from user_content_service import schemas


class ScalarResultStub:
    def __init__(self, value):
        self._value = value

    def scalar(self):
        return self._value

    def scalar_one_or_none(self):
        return self._value


class ScalarsStub:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class ExecuteResultStub:
    def __init__(self, scalar=None, scalars=None, rows=None):
        self._scalar = scalar
        self._scalars = scalars or []
        self._rows = rows or []

    def scalar(self):
        return self._scalar

    def scalar_one_or_none(self):
        return self._scalar

    def scalars(self):
        return ScalarsStub(self._scalars)

    def all(self):
        return self._rows


@pytest.fixture
def db():
    mock = AsyncMock()
    mock.add = MagicMock()
    mock.delete = AsyncMock()
    return mock


@pytest.fixture
def sample_article():
    return schemas.FavoriteToggleRequest(
        user_id=123,
        url="https://lenta.ru/news/2025/03/15/test/",
        title="Тестовая статья",
        description="Это тестовое описание статьи",
        url_to_image="https://example.com/image.jpg",
        source_name="Lenta.ru",
        published_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_comment():
    return schemas.CommentCreate(
        user_id=123,
        text="Это тестовый комментарий",
    )


class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_health_check(self, db):
        db.execute.side_effect = [ScalarResultStub(2), ScalarResultStub(1)]
        data = await main.health_check(db)
        assert data["status"] == "healthy"
        assert data["stats"]["favorites_count"] == 2
        assert data["stats"]["comments_count"] == 1


class TestFavoritesEndpoints:
    @pytest.mark.asyncio
    async def test_toggle_favorite_add(self, db, sample_article):
        db.execute.return_value = ExecuteResultStub(scalar=None)

        response = await main.toggle_favorite(sample_article, db)

        assert response.success is True
        assert response.is_favorite is True
        assert response.action == "added"
        db.add.assert_called_once()
        db.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_toggle_favorite_remove(self, db, sample_article):
        existing = main.FavoriteArticleModel(id=1, user_id=123, url=str(sample_article.url))
        db.execute.return_value = ExecuteResultStub(scalar=existing)

        response = await main.toggle_favorite(sample_article, db)

        assert response.success is True
        assert response.is_favorite is False
        assert response.action == "removed"
        db.delete.assert_called_once_with(existing)

    @pytest.mark.asyncio
    async def test_get_favorites_empty(self, db):
        db.execute.side_effect = [
            ExecuteResultStub(scalar=0),
            ExecuteResultStub(scalars=[]),
        ]

        response = await main.get_favorites(user_id=123, include_comments=False, page=1, size=10, db=db)

        assert response.items == []
        assert response.total == 0
        assert response.page == 1

    @pytest.mark.asyncio
    async def test_get_favorites_with_comments(self, db):
        article = main.FavoriteArticleModel(
            id=7,
            user_id=123,
            url="https://example.com/news",
            title="Статья",
            description="Описание",
            source_name="Lenta.ru",
            published_at=datetime.now(timezone.utc),
            added_at=datetime.now(timezone.utc),
        )
        comment = main.CommentModel(
            id=9,
            article_id=7,
            user_id=123,
            text="Комментарий",
            created_at=datetime.now(timezone.utc),
        )
        db.execute.side_effect = [
            ExecuteResultStub(scalar=1),
            ExecuteResultStub(scalars=[article]),
            ExecuteResultStub(scalars=[comment]),
        ]

        response = await main.get_favorites(user_id=123, include_comments=True, page=1, size=10, db=db)

        assert len(response.items) == 1
        assert response.items[0].comments[0].text == "Комментарий"

    @pytest.mark.asyncio
    async def test_check_favorite_true(self, db):
        article = main.FavoriteArticleModel(id=3, user_id=123, url="https://example.com/news")
        db.execute.return_value = ExecuteResultStub(scalar=article)

        response = await main.check_favorite("https://example.com/news", 123, db)

        assert response.is_favorite is True
        assert response.article_id == 3

    @pytest.mark.asyncio
    async def test_check_favorite_false(self, db):
        db.execute.return_value = ExecuteResultStub(scalar=None)

        response = await main.check_favorite("https://example.com/news", 123, db)

        assert response.is_favorite is False
        assert response.article_id is None

    @pytest.mark.asyncio
    async def test_get_favorite_urls(self, db):
        db.execute.return_value = ExecuteResultStub(rows=[("https://a",), ("https://b",)])

        response = await main.get_favorite_urls(123, db)

        assert response.user_id == 123
        assert response.urls == ["https://a", "https://b"]
        assert response.total == 2


class TestCommentsEndpoints:
    @pytest.mark.asyncio
    async def test_add_comment(self, db, sample_comment):
        article = main.FavoriteArticleModel(id=5, user_id=123, url="https://example.com/news")
        db.execute.return_value = ExecuteResultStub(scalar=article)

        async def refresh(obj):
            obj.id = 11

        db.refresh.side_effect = refresh

        response = await main.add_comment(5, sample_comment, db)

        assert response.success is True
        assert response.comment.id == 11
        assert response.comment.text == sample_comment.text

    @pytest.mark.asyncio
    async def test_add_comment_article_not_favorite(self, db, sample_comment):
        db.execute.return_value = ExecuteResultStub(scalar=None)

        with pytest.raises(main.HTTPException) as exc_info:
            await main.add_comment(999, sample_comment, db)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_add_comment_empty_text(self, db):
        article = main.FavoriteArticleModel(id=5, user_id=123, url="https://example.com/news")
        db.execute.return_value = ExecuteResultStub(scalar=article)

        with pytest.raises(main.HTTPException) as exc_info:
            await main.add_comment(5, schemas.CommentCreate(user_id=123, text=""), db)

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_get_comments(self, db):
        article = main.FavoriteArticleModel(id=7, user_id=123, url="https://example.com/news")
        comments = [
            main.CommentModel(id=1, article_id=7, user_id=123, text="A", created_at=datetime.now(timezone.utc)),
            main.CommentModel(id=2, article_id=7, user_id=123, text="B", created_at=datetime.now(timezone.utc)),
        ]
        db.execute.side_effect = [
            ExecuteResultStub(scalar=article),
            ExecuteResultStub(scalar=2),
            ExecuteResultStub(scalars=comments),
        ]

        response = await main.get_comments(7, 123, page=1, size=10, db=db)

        assert len(response.items) == 2
        assert response.total == 2

    @pytest.mark.asyncio
    async def test_edit_comment(self, db):
        comment = main.CommentModel(id=4, article_id=7, user_id=123, text="Старый", created_at=datetime.now(timezone.utc))
        db.execute.return_value = ExecuteResultStub(scalar=comment)
        db.refresh.side_effect = AsyncMock()

        response = await main.edit_comment(4, schemas.CommentUpdate(user_id=123, text="Новый"), db)

        assert response.comment.text == "Новый"

    @pytest.mark.asyncio
    async def test_edit_comment_wrong_user(self, db):
        comment = main.CommentModel(id=4, article_id=7, user_id=123, text="Старый", created_at=datetime.now(timezone.utc))
        db.execute.return_value = ExecuteResultStub(scalar=comment)

        with pytest.raises(main.HTTPException) as exc_info:
            await main.edit_comment(4, schemas.CommentUpdate(user_id=999, text="Новый"), db)

        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_comment(self, db):
        comment = main.CommentModel(id=4, article_id=7, user_id=123, text="Удалить", created_at=datetime.now(timezone.utc))
        db.execute.return_value = ExecuteResultStub(scalar=comment)

        response = await main.delete_comment(4, 123, db)

        assert response["success"] is True
        db.delete.assert_called_once_with(comment)

    @pytest.mark.asyncio
    async def test_delete_comment_wrong_user(self, db):
        comment = main.CommentModel(id=4, article_id=7, user_id=123, text="Удалить", created_at=datetime.now(timezone.utc))
        db.execute.return_value = ExecuteResultStub(scalar=comment)

        with pytest.raises(main.HTTPException) as exc_info:
            await main.delete_comment(4, 999, db)

        assert exc_info.value.status_code == 403


class TestDataValidation:
    def test_toggle_favorite_missing_url(self):
        with pytest.raises(ValidationError):
            schemas.FavoriteToggleRequest(user_id=123, title="Без URL")

    def test_add_comment_missing_text(self):
        with pytest.raises(ValidationError):
            schemas.CommentCreate(user_id=123)

    def test_comment_update_requires_user_and_text(self):
        payload = schemas.CommentUpdate(user_id=123, text="ok")
        assert payload.user_id == 123
        assert payload.text == "ok"


class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_toggle_favorite_without_source_name(self, db):
        db.execute.return_value = ExecuteResultStub(scalar=None)
        payload = schemas.FavoriteToggleRequest(
            user_id=123,
            url="https://example.com/news",
            title="Статья",
            published_at=datetime.now(timezone.utc),
        )

        response = await main.toggle_favorite(payload, db)

        assert response.is_favorite is True

    @pytest.mark.asyncio
    async def test_toggle_favorite_without_published_at(self, db):
        db.execute.return_value = ExecuteResultStub(scalar=None)
        payload = schemas.FavoriteToggleRequest(
            user_id=123,
            url="https://example.com/news",
            title="Статья",
            source_name="Lenta.ru",
        )

        response = await main.toggle_favorite(payload, db)

        assert response.is_favorite is True

    @pytest.mark.asyncio
    async def test_same_article_different_users(self, db):
        db.execute.side_effect = [
            ExecuteResultStub(scalar=None),
            ExecuteResultStub(scalar=None),
        ]
        first = schemas.FavoriteToggleRequest(user_id=123, url="https://example.com/news", title="Статья")
        second = schemas.FavoriteToggleRequest(user_id=456, url="https://example.com/news", title="Статья")

        response1 = await main.toggle_favorite(first, db)
        response2 = await main.toggle_favorite(second, db)

        assert response1.is_favorite is True
        assert response2.is_favorite is True
