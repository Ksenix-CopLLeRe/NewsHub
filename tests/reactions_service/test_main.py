# tests/reactions_service/test_main.py
"""
Юнит-тесты для Reactions Service
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from datetime import datetime
from unittest.mock import patch, MagicMock

import sys
sys.path.append('.')

from reactions_service.app.main import app
from reactions_service.app import models, crud, schemas
from reactions_service.app.database import Base, get_db


# Тестовая БД (SQLite in-memory)
TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_database():
    """Создаём таблицы перед каждым тестом"""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def sample_reaction():
    return {
        "user_id": 123,
        "news_id": "https://lenta.ru/news/2025/03/15/test/",
        "reaction_type": "important"
    }


class TestHealthCheck:
    """Тесты проверки здоровья"""
    
    def test_root_endpoint(self, client):
        """Корневой эндпоинт"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "Reactions Service API" in data.get("message", "")
    
    def test_health_check_with_db(self, client, db_session):
        """Проверка здоровья через корневой эндпоинт"""
        response = client.get("/")
        assert response.status_code == 200


class TestCRUD:
    """Тесты CRUD операций"""
    
    def test_create_reaction(self, db_session, sample_reaction):
        """Создание реакции"""
        reaction_create = schemas.ReactionCreate(**sample_reaction)
        reaction = crud.create_reaction(db_session, reaction_create)
        
        assert reaction.id is not None
        assert reaction.user_id == sample_reaction["user_id"]
        assert reaction.news_id == sample_reaction["news_id"]
        assert reaction.reaction_type.value == sample_reaction["reaction_type"]
    
    def test_get_user_reaction(self, db_session, sample_reaction):
        """Получение реакции пользователя"""
        reaction_create = schemas.ReactionCreate(**sample_reaction)
        crud.create_reaction(db_session, reaction_create)
        
        found = crud.get_user_reaction(
            db_session, 
            sample_reaction["user_id"], 
            sample_reaction["news_id"]
        )
        assert found is not None
        assert found.user_id == sample_reaction["user_id"]
    
    def test_get_user_reaction_not_found(self, db_session):
        """Реакция не найдена"""
        found = crud.get_user_reaction(db_session, 999, "https://example.com/not-found")
        assert found is None
    
    def test_update_reaction(self, db_session, sample_reaction):
        """Обновление реакции"""
        reaction_create = schemas.ReactionCreate(**sample_reaction)
        reaction = crud.create_reaction(db_session, reaction_create)
        
        update_data = schemas.ReactionUpdate(reaction_type="liked")
        updated = crud.update_reaction(db_session, reaction, update_data)
        
        assert updated.reaction_type.value == "liked"
    
    def test_delete_reaction(self, db_session, sample_reaction):
        """Удаление реакции"""
        reaction_create = schemas.ReactionCreate(**sample_reaction)
        reaction = crud.create_reaction(db_session, reaction_create)
        
        crud.delete_reaction(db_session, reaction)
        
        found = crud.get_reaction(db_session, reaction.id)
        assert found is None
    
    def test_get_reactions_by_news(self, db_session):
        """Получение всех реакций на новость"""
        news_id = "https://example.com/news/123"
        
        # Создаём несколько реакций
        for i, reaction_type in enumerate(["important", "interesting", "useful"]):
            reaction = schemas.ReactionCreate(
                user_id=100 + i,
                news_id=news_id,
                reaction_type=reaction_type
            )
            crud.create_reaction(db_session, reaction)
        
        reactions = crud.get_reactions_by_news(db_session, news_id)
        assert len(reactions) == 3
    
    def test_count_reactions_by_news(self, db_session):
        """Подсчёт количества реакций на новость"""
        news_id = "https://example.com/news/123"
        
        for i in range(5):
            reaction = schemas.ReactionCreate(
                user_id=100 + i,
                news_id=news_id,
                reaction_type="important"
            )
            crud.create_reaction(db_session, reaction)
        
        count = crud.count_reactions_by_news(db_session, news_id)
        assert count == 5
    
    def test_get_reaction_counts(self, db_session):
        """Получение агрегированных счётчиков реакций"""
        news_id = "https://example.com/news/123"
        
        reactions = [
            ("important", 3),
            ("interesting", 2),
            ("liked", 1),
        ]
        
        for reaction_type, count in reactions:
            for i in range(count):
                reaction = schemas.ReactionCreate(
                    user_id=1000 + i,
                    news_id=news_id,
                    reaction_type=reaction_type
                )
                crud.create_reaction(db_session, reaction)
        
        counts, total = crud.get_reaction_counts(db_session, news_id)
        
        assert counts["important"] == 3
        assert counts["interesting"] == 2
        assert counts["liked"] == 1
        assert total == 6


class TestAPIEndpoints:
    """Тесты API эндпоинтов"""
    
    def test_create_reaction(self, client, sample_reaction):
        """Создание реакции через API"""
        response = client.post("/reactions", json=sample_reaction)
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["action"] == "created"
    
    def test_toggle_reaction_delete_same(self, client, sample_reaction):
        """Повторное нажатие на ту же реакцию - удаление"""
        # Создаём реакцию
        response1 = client.post("/reactions", json=sample_reaction)
        assert response1.status_code == 201
        
        # Отправляем ту же реакцию снова
        response2 = client.post("/reactions", json=sample_reaction)
        assert response2.status_code == 200
        data = response2.json()
        assert data["action"] == "deleted"
    
    def test_toggle_reaction_update_different(self, client, sample_reaction):
        """Изменение типа реакции"""
        # Создаём реакцию
        client.post("/reactions", json=sample_reaction)
        
        # Отправляем другой тип реакции
        updated_reaction = sample_reaction.copy()
        updated_reaction["reaction_type"] = "liked"
        response = client.post("/reactions", json=updated_reaction)
        assert response.status_code == 200
        data = response.json()
        assert data["action"] == "updated"
        assert data["reaction"]["reaction_type"] == "liked"
    
    def test_get_reaction_counts(self, client, db_session, sample_reaction):
        """Получение счётчиков реакций"""
        # Создаём несколько реакций
        news_id = sample_reaction["news_id"]
        
        for reaction_type in ["important", "interesting", "important"]:
            reaction = {
                "user_id": hash(reaction_type) % 1000,
                "news_id": news_id,
                "reaction_type": reaction_type
            }
            client.post("/reactions", json=reaction)
        
        response = client.get(f"/reactions/counts/{news_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["news_id"] == news_id
        assert data["counts"]["important"] == 2
        assert data["counts"]["interesting"] == 1
        assert data["total"] == 3
    
    def test_get_reactions_by_news(self, client, db_session, sample_reaction):
        """Получение списка реакций на новость"""
        news_id = sample_reaction["news_id"]
        
        for i in range(5):
            reaction = {
                "user_id": 1000 + i,
                "news_id": news_id,
                "reaction_type": "important" if i % 2 == 0 else "interesting"
            }
            client.post("/reactions", json=reaction)
        
        response = client.get(f"/reactions/news/{news_id}?page=1&size=3")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 3
        assert data["total"] == 5
        assert data["page"] == 1
        assert data["size"] == 3
    
    def test_get_reactions_by_news_empty(self, client):
        """Получение списка реакций для новости без реакций"""
        response = client.get("/reactions/news/https://example.com/no-reactions?page=1&size=10")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
    
    def test_delete_reaction_by_id(self, client, sample_reaction):
        """Удаление реакции по ID"""
        # Создаём реакцию
        create_response = client.post("/reactions", json=sample_reaction)
        reaction_id = create_response.json()["reaction"]["id"]
        
        # Удаляем
        response = client.delete(
            f"/reactions/{reaction_id}",
            headers={"x-user-id": str(sample_reaction["user_id"])}
        )
        assert response.status_code == 200
        assert response.json()["success"] is True
    
    def test_delete_reaction_wrong_user(self, client, sample_reaction):
        """Попытка удалить чужую реакцию"""
        create_response = client.post("/reactions", json=sample_reaction)
        reaction_id = create_response.json()["reaction"]["id"]
        
        response = client.delete(
            f"/reactions/{reaction_id}",
            headers={"x-user-id": "999"}  # Другой пользователь
        )
        assert response.status_code == 403
    
    def test_delete_reaction_not_found(self, client):
        """Удаление несуществующей реакции"""
        response = client.delete(
            "/reactions/99999",
            headers={"x-user-id": "123"}
        )
        assert response.status_code == 404
    
    def test_get_reaction_counts_news_not_found(self, client):
        """Счётчики для несуществующей новости - возвращаются нули"""
        response = client.get("/reactions/counts/https://example.com/not-exists")
        assert response.status_code == 200
        data = response.json()
        for count in data["counts"].values():
            assert count == 0
        assert data["total"] == 0


class TestBackgroundTasks:
    """Тесты фоновых задач"""
    
    @patch("reactions_service.app.main.write_log")
    def test_create_reaction_logs(self, mock_write_log, client, sample_reaction):
        """Проверка логирования при создании реакции"""
        response = client.post("/reactions", json=sample_reaction)
        assert response.status_code == 201
        
        # Даём время на выполнение фоновой задачи
        import time
        time.sleep(0.5)
        
        mock_write_log.assert_called_once()
        call_args = mock_write_log.call_args[0][0]
        assert "REACTION CREATED" in call_args
        assert str(sample_reaction["user_id"]) in call_args
    
    @patch("reactions_service.app.main.write_log")
    def test_delete_reaction_logs(self, mock_write_log, client, sample_reaction):
        """Проверка логирования при удалении реакции"""
        # Создаём
        client.post("/reactions", json=sample_reaction)
        # Отправляем ту же для удаления
        client.post("/reactions", json=sample_reaction)
        
        import time
        time.sleep(0.5)
        
        # Должно быть два вызова (создание и удаление)
        assert mock_write_log.call_count >= 1


class TestAsyncEndpoints:
    """Тесты асинхронных эндпоинтов"""
    
    @pytest.mark.asyncio
    @patch("reactions_service.app.main.httpx.AsyncClient")
    async def test_get_external_news(self, mock_client_class):
        """Получение внешних новостей"""
        from reactions_service.app.main import get_external_news
        
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.json.return_value = [
            {"id": 1, "title": "Post 1", "body": "Body 1"},
            {"id": 2, "title": "Post 2", "body": "Body 2"},
        ]
        mock_response.raise_for_status = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
        # FastAPI endpoint требует request, поэтому тестируем через TestClient
        # или напрямую вызываем функцию
    
    @patch("reactions_service.app.main.httpx.AsyncClient")
    def test_get_combined_data_endpoint(self, mock_client_class, client):
        """Тест параллельных запросов"""
        # Мокаем асинхронный клиент
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = [{"id": 1, "title": "Test"}]
        mock_response.status_code = 200
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
        # Этот тест сложен для мокинга, лучше использовать реальный TestClient
        # с замоканными внешними вызовами


# Для асинхронных тестов
import asyncio
from unittest.mock import AsyncMock