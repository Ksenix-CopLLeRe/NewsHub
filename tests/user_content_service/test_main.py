# tests/user_content_service/test_main.py
"""
Юнит-тесты для User Content Service
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock, MagicMock

import sys
sys.path.append('.')

from user_content_service.main import app
from user_content_service import models, schemas
from user_content_service.database import Base, get_db


# Тестовая БД (SQLite in-memory асинхронная)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
AsyncTestingSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def override_get_db():
    async with AsyncTestingSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
async def setup_database():
    """Создаём таблицы перед каждым тестом"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
async def db_session():
    async with AsyncTestingSessionLocal() as session:
        yield session


@pytest.fixture
def sample_article():
    return {
        "user_id": 123,
        "url": "https://lenta.ru/news/2025/03/15/test/",
        "title": "Тестовая статья",
        "description": "Это тестовое описание статьи",
        "url_to_image": "https://example.com/image.jpg",
        "source_name": "Lenta.ru",
        "published_at": datetime.now(timezone.utc).isoformat()
    }


@pytest.fixture
def sample_comment():
    return {
        "user_id": 123,
        "text": "Это тестовый комментарий"
    }


class TestHealthCheck:
    """Тесты проверки здоровья"""
    
    def test_health_check(self, client):
        """Проверка эндпоинта здоровья"""
        response = client.get("/internal/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "database" in data
        assert "stats" in data


class TestFavoritesEndpoints:
    """Тесты эндпоинтов избранного"""
    
    def test_toggle_favorite_add(self, client, sample_article):
        """Добавление статьи в избранное"""
        response = client.post("/favorites/toggle", json=sample_article)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["is_favorite"] is True
        assert data["action"] == "added"
    
    def test_toggle_favorite_remove(self, client, sample_article):
        """Удаление статьи из избранного (toggle)"""
        # Добавляем
        client.post("/favorites/toggle", json=sample_article)
        
        # Удаляем
        response = client.post("/favorites/toggle", json=sample_article)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["is_favorite"] is False
        assert data["action"] == "removed"
    
    def test_get_favorites_empty(self, client):
        """Получение пустого списка избранного"""
        response = client.get("/favorites?user_id=123")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
    
    def test_get_favorites_with_data(self, client, sample_article):
        """Получение списка избранного с данными"""
        # Добавляем статью
        client.post("/favorites/toggle", json=sample_article)
        
        response = client.get("/favorites?user_id=123")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["total"] == 1
        assert data["items"][0]["url"] == sample_article["url"]
        assert data["items"][0]["title"] == sample_article["title"]
    
    def test_get_favorites_pagination(self, client):
        """Пагинация в списке избранного"""
        # Добавляем 15 статей
        for i in range(15):
            article = {
                "user_id": 123,
                "url": f"https://example.com/news/{i}",
                "title": f"Статья {i}",
                "description": f"Описание {i}",
                "source_name": "Lenta.ru",
                "published_at": datetime.now(timezone.utc).isoformat()
            }
            client.post("/favorites/toggle", json=article)
        
        response = client.get("/favorites?user_id=123&page=2&size=10")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 5  # 15 - 10 = 5
        assert data["total"] == 15
        assert data["page"] == 2
        assert data["size"] == 10
    
    def test_check_favorite_true(self, client, sample_article):
        """Проверка наличия статьи в избранном (есть)"""
        client.post("/favorites/toggle", json=sample_article)
        
        encoded_url = sample_article["url"].replace("/", "%2F")
        response = client.get(f"/favorites/check/{encoded_url}?user_id=123")
        assert response.status_code == 200
        data = response.json()
        assert data["is_favorite"] is True
        assert data["article_id"] is not None
    
    def test_check_favorite_false(self, client):
        """Проверка наличия статьи в избранном (нет)"""
        encoded_url = "https%3A%2F%2Fexample.com%2Fnot-favorite"
        response = client.get(f"/favorites/check/{encoded_url}?user_id=123")
        assert response.status_code == 200
        data = response.json()
        assert data["is_favorite"] is False
        assert data["article_id"] is None
    
    def test_get_favorite_urls(self, client, sample_article):
        """Получение списка URL избранных статей"""
        client.post("/favorites/toggle", json=sample_article)
        
        response = client.get("/favorites/urls?user_id=123")
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == 123
        assert sample_article["url"] in data["urls"]
        assert data["total"] == 1
    
    def test_get_favorites_with_comments(self, client, sample_article, sample_comment):
        """Получение избранных статей с комментариями"""
        # Добавляем статью
        add_response = client.post("/favorites/toggle", json=sample_article)
        article_id = add_response.json()["article_id"]
        
        # Добавляем комментарий
        client.post(f"/favorites/{article_id}/comments", json=sample_comment)
        
        # Получаем с комментариями
        response = client.get("/favorites?user_id=123&include_comments=true")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert len(data["items"][0]["comments"]) == 1
        assert data["items"][0]["comments"][0]["text"] == sample_comment["text"]


class TestCommentsEndpoints:
    """Тесты эндпоинтов комментариев"""
    
    def test_add_comment(self, client, sample_article, sample_comment):
        """Добавление комментария"""
        # Сначала добавляем статью в избранное
        add_response = client.post("/favorites/toggle", json=sample_article)
        article_id = add_response.json()["article_id"]
        
        response = client.post(f"/favorites/{article_id}/comments", json=sample_comment)
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["comment"]["text"] == sample_comment["text"]
        assert data["comment"]["user_id"] == sample_comment["user_id"]
    
    def test_add_comment_article_not_favorite(self, client, sample_comment):
        """Добавление комментария к не избранной статье"""
        response = client.post("/favorites/99999/comments", json=sample_comment)
        assert response.status_code == 404
    
    def test_add_comment_empty_text(self, client, sample_article):
        """Добавление пустого комментария"""
        add_response = client.post("/favorites/toggle", json=sample_article)
        article_id = add_response.json()["article_id"]
        
        response = client.post(
            f"/favorites/{article_id}/comments",
            json={"user_id": 123, "text": ""}
        )
        assert response.status_code == 400
    
    def test_get_comments(self, client, sample_article, sample_comment):
        """Получение списка комментариев"""
        # Добавляем статью
        add_response = client.post("/favorites/toggle", json=sample_article)
        article_id = add_response.json()["article_id"]
        
        # Добавляем несколько комментариев
        for i in range(3):
            comment = {"user_id": 123, "text": f"Комментарий {i}"}
            client.post(f"/favorites/{article_id}/comments", json=comment)
        
        response = client.get(f"/favorites/{article_id}/comments?user_id=123")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 3
        assert data["total"] == 3
    
    def test_get_comments_pagination(self, client, sample_article):
        """Пагинация комментариев"""
        add_response = client.post("/favorites/toggle", json=sample_article)
        article_id = add_response.json()["article_id"]
        
        for i in range(15):
            comment = {"user_id": 123, "text": f"Комментарий {i}"}
            client.post(f"/favorites/{article_id}/comments", json=comment)
        
        response = client.get(f"/favorites/{article_id}/comments?user_id=123&page=2&size=5")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 5
        assert data["total"] == 15
        assert data["page"] == 2
        assert data["size"] == 5
    
    def test_edit_comment(self, client, sample_article, sample_comment):
        """Редактирование комментария"""
        # Добавляем статью
        add_response = client.post("/favorites/toggle", json=sample_article)
        article_id = add_response.json()["article_id"]
        
        # Добавляем комментарий
        add_comment_response = client.post(f"/favorites/{article_id}/comments", json=sample_comment)
        comment_id = add_comment_response.json()["comment"]["id"]
        
        # Редактируем
        update_data = {"user_id": 123, "text": "Обновлённый комментарий"}
        response = client.put(f"/comments/{comment_id}", json=update_data)
        assert response.status_code == 200
        data = response.json()
        assert data["comment"]["text"] == "Обновлённый комментарий"
    
    def test_edit_comment_wrong_user(self, client, sample_article, sample_comment):
        """Редактирование чужого комментария"""
        add_response = client.post("/favorites/toggle", json=sample_article)
        article_id = add_response.json()["article_id"]
        
        add_comment_response = client.post(f"/favorites/{article_id}/comments", json=sample_comment)
        comment_id = add_comment_response.json()["comment"]["id"]
        
        # Пытается редактировать другой пользователь
        update_data = {"user_id": 999, "text": "Чужой комментарий"}
        response = client.put(f"/comments/{comment_id}", json=update_data)
        assert response.status_code == 403
    
    def test_delete_comment(self, client, sample_article, sample_comment):
        """Удаление комментария"""
        add_response = client.post("/favorites/toggle", json=sample_article)
        article_id = add_response.json()["article_id"]
        
        add_comment_response = client.post(f"/favorites/{article_id}/comments", json=sample_comment)
        comment_id = add_comment_response.json()["comment"]["id"]
        
        response = client.delete(f"/comments/{comment_id}?user_id=123")
        assert response.status_code == 200
        assert response.json()["success"] is True
        
        # Проверяем, что комментарий удалён
        get_response = client.get(f"/favorites/{article_id}/comments?user_id=123")
        assert len(get_response.json()["items"]) == 0
    
    def test_delete_comment_wrong_user(self, client, sample_article, sample_comment):
        """Удаление чужого комментария"""
        add_response = client.post("/favorites/toggle", json=sample_article)
        article_id = add_response.json()["article_id"]
        
        add_comment_response = client.post(f"/favorites/{article_id}/comments", json=sample_comment)
        comment_id = add_comment_response.json()["comment"]["id"]
        
        response = client.delete(f"/comments/{comment_id}?user_id=999")
        assert response.status_code == 403
    
    def test_delete_comment_not_found(self, client):
        """Удаление несуществующего комментария"""
        response = client.delete("/comments/99999?user_id=123")
        assert response.status_code == 404


class TestDataValidation:
    """Тесты валидации данных"""
    
    def test_toggle_favorite_missing_url(self, client):
        """Добавление в избранное без URL"""
        data = {
            "user_id": 123,
            "title": "Новость без URL"
        }
        response = client.post("/favorites/toggle", json=data)
        assert response.status_code == 400
    
    def test_add_comment_missing_text(self, client, sample_article):
        """Добавление комментария без текста"""
        add_response = client.post("/favorites/toggle", json=sample_article)
        article_id = add_response.json()["article_id"]
        
        response = client.post(
            f"/favorites/{article_id}/comments",
            json={"user_id": 123}
        )
        assert response.status_code == 422  # Pydantic validation error
    
    def test_invalid_page_negative(self, client):
        """Отрицательный номер страницы"""
        response = client.get("/favorites?user_id=123&page=-1")
        assert response.status_code == 422
    
    def test_invalid_size_too_large(self, client):
        """Слишком большой размер страницы"""
        response = client.get("/favorites?user_id=123&size=200")
        assert response.status_code == 422


class TestEdgeCases:
    """Тесты граничных случаев"""
    
    def test_toggle_favorite_without_source_name(self, client):
        """Добавление статьи без указания источника"""
        article = {
            "user_id": 123,
            "url": "https://example.com/news",
            "title": "Статья без источника",
            "published_at": datetime.now(timezone.utc).isoformat()
        }
        response = client.post("/favorites/toggle", json=article)
        assert response.status_code == 200
        # Должен использоваться источник по умолчанию
        assert response.json()["is_favorite"] is True
    
    def test_toggle_favorite_without_published_at(self, client):
        """Добавление статьи без даты публикации"""
        article = {
            "user_id": 123,
            "url": "https://example.com/news",
            "title": "Статья без даты",
            "source_name": "Lenta.ru"
        }
        response = client.post("/favorites/toggle", json=article)
        assert response.status_code == 200
        assert response.json()["is_favorite"] is True
    
    def test_same_article_different_users(self, client, sample_article):
        """Одна и та же статья в избранном у разных пользователей"""
        # Пользователь 1
        article1 = sample_article.copy()
        article1["user_id"] = 123
        client.post("/favorites/toggle", json=article1)
        
        # Пользователь 2
        article2 = sample_article.copy()
        article2["user_id"] = 456
        response = client.post("/favorites/toggle", json=article2)
        assert response.status_code == 200
        
        # Проверяем, что у каждого своя запись
        response1 = client.get("/favorites/urls?user_id=123")
        response2 = client.get("/favorites/urls?user_id=456")
        
        assert sample_article["url"] in response1.json()["urls"]
        assert sample_article["url"] in response2.json()["urls"]
    
    def test_multiple_comments_same_article(self, client, sample_article):
        """Несколько комментариев к одной статье"""
        add_response = client.post("/favorites/toggle", json=sample_article)
        article_id = add_response.json()["article_id"]
        
        comments = ["Первый комментарий", "Второй комментарий", "Третий комментарий"]
        for text in comments:
            response = client.post(
                f"/favorites/{article_id}/comments",
                json={"user_id": 123, "text": text}
            )
            assert response.status_code == 201
        
        get_response = client.get(f"/favorites/{article_id}/comments?user_id=123")
        assert len(get_response.json()["items"]) == 3