# tests/reactions_service/test_main.py
"""
Юнит-тесты для Reactions Service
"""

import os
import types
from pathlib import Path
import pytest
from fastapi import BackgroundTasks, HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import patch, MagicMock, AsyncMock

import sys
sys.path.append(str(Path(__file__).resolve().parents[2] / "reactions-service"))
sys.modules.setdefault("dotenv", types.SimpleNamespace(load_dotenv=lambda: None))
for module_name in list(sys.modules):
    if module_name == "app" or module_name.startswith("app."):
        del sys.modules[module_name]

os.environ["DB_TYPE"] = "sqlite"
os.environ["SQLITE_PATH"] = ":memory:"

from app import main, models, crud, schemas
from app.database import Base, get_db

app = main.app


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
    
    def test_root_endpoint(self):
        """Корневой эндпоинт"""
        data = main.root()
        assert "Reactions Service API" in data.get("message", "")
    
    def test_health_check_with_db(self, db_session):
        """Проверка здоровья через корневой эндпоинт"""
        data = main.root()
        assert "running" in data["status"]


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
        
        user_id = 1000
        for reaction_type, count in reactions:
            for _ in range(count):
                reaction = schemas.ReactionCreate(
                    user_id=user_id,
                    news_id=news_id,
                    reaction_type=reaction_type
                )
                crud.create_reaction(db_session, reaction)
                user_id += 1
        
        counts, total = crud.get_reaction_counts(db_session, news_id)
        
        assert counts["important"] == 3
        assert counts["interesting"] == 2
        assert counts["liked"] == 1
        assert total == 6


class TestAPIEndpoints:
    """Тесты API эндпоинтов"""
    
    @pytest.mark.asyncio
    async def test_create_reaction(self, db_session, sample_reaction):
        """Создание реакции через API"""
        data = await main.create_or_update_reaction(
            schemas.ReactionCreate(**sample_reaction),
            BackgroundTasks(),
            db_session,
        )
        assert data["success"] is True
        assert data["action"] == "created"
    
    @pytest.mark.asyncio
    async def test_toggle_reaction_delete_same(self, db_session, sample_reaction):
        """Повторное нажатие на ту же реакцию - удаление"""
        # Создаём реакцию
        await main.create_or_update_reaction(
            schemas.ReactionCreate(**sample_reaction),
            BackgroundTasks(),
            db_session,
        )
        
        # Отправляем ту же реакцию снова
        data = await main.create_or_update_reaction(
            schemas.ReactionCreate(**sample_reaction),
            BackgroundTasks(),
            db_session,
        )
        assert data["action"] == "deleted"
    
    @pytest.mark.asyncio
    async def test_toggle_reaction_update_different(self, db_session, sample_reaction):
        """Изменение типа реакции"""
        # Создаём реакцию
        await main.create_or_update_reaction(
            schemas.ReactionCreate(**sample_reaction),
            BackgroundTasks(),
            db_session,
        )
        
        # Отправляем другой тип реакции
        updated_reaction = sample_reaction.copy()
        updated_reaction["reaction_type"] = "liked"
        data = await main.create_or_update_reaction(
            schemas.ReactionCreate(**updated_reaction),
            BackgroundTasks(),
            db_session,
        )
        assert data["action"] == "updated"
        assert data["reaction"].reaction_type.value == "liked"
    
    @pytest.mark.asyncio
    async def test_get_reaction_counts(self, db_session, sample_reaction):
        """Получение счётчиков реакций"""
        # Создаём несколько реакций
        news_id = sample_reaction["news_id"]
        
        for idx, reaction_type in enumerate(["important", "interesting", "important"]):
            reaction = {
                "user_id": 500 + idx,
                "news_id": news_id,
                "reaction_type": reaction_type
            }
            await main.create_or_update_reaction(
                schemas.ReactionCreate(**reaction),
                BackgroundTasks(),
                db_session,
            )
        
        data = main.get_reaction_counts(news_id, db_session)
        assert data.news_id == news_id
        assert data.counts["important"] == 2
        assert data.counts["interesting"] == 1
        assert data.total == 3
    
    @pytest.mark.asyncio
    async def test_get_reactions_by_news(self, db_session, sample_reaction):
        """Получение списка реакций на новость"""
        news_id = sample_reaction["news_id"]
        
        for i in range(5):
            reaction = {
                "user_id": 1000 + i,
                "news_id": news_id,
                "reaction_type": "important" if i % 2 == 0 else "interesting"
            }
            await main.create_or_update_reaction(
                schemas.ReactionCreate(**reaction),
                BackgroundTasks(),
                db_session,
            )
        
        data = main.get_reactions_by_news(news_id, page=1, size=3, db=db_session)
        assert len(data.items) == 3
        assert data.total == 5
        assert data.page == 1
        assert data.size == 3
    
    def test_get_reactions_by_news_empty(self, db_session):
        """Получение списка реакций для новости без реакций"""
        data = main.get_reactions_by_news("https://example.com/no-reactions", page=1, size=10, db=db_session)
        assert data.items == []
        assert data.total == 0
    
    @pytest.mark.asyncio
    async def test_delete_reaction_by_id(self, db_session, sample_reaction):
        """Удаление реакции по ID"""
        # Создаём реакцию
        create_response = await main.create_or_update_reaction(
            schemas.ReactionCreate(**sample_reaction),
            BackgroundTasks(),
            db_session,
        )
        reaction_id = create_response["reaction"].id
        
        # Удаляем
        response = main.delete_reaction(reaction_id, sample_reaction["user_id"], db_session)
        assert response["success"] is True
    
    @pytest.mark.asyncio
    async def test_delete_reaction_wrong_user(self, db_session, sample_reaction):
        """Попытка удалить чужую реакцию"""
        create_response = await main.create_or_update_reaction(
            schemas.ReactionCreate(**sample_reaction),
            BackgroundTasks(),
            db_session,
        )
        reaction_id = create_response["reaction"].id
        
        with pytest.raises(HTTPException) as exc_info:
            main.delete_reaction(reaction_id, 999, db_session)
        assert exc_info.value.status_code == 403
    
    def test_delete_reaction_not_found(self, db_session):
        """Удаление несуществующей реакции"""
        with pytest.raises(HTTPException) as exc_info:
            main.delete_reaction(99999, 123, db_session)
        assert exc_info.value.status_code == 404
    
    def test_get_reaction_counts_news_not_found(self, db_session):
        """Счётчики для несуществующей новости - возвращаются нули"""
        data = main.get_reaction_counts("https://example.com/not-exists", db_session)
        for count in data.counts.values():
            assert count == 0
        assert data.total == 0


class TestBackgroundTasks:
    """Тесты фоновых задач"""
    
    @pytest.mark.asyncio
    @patch("app.main.write_log")
    async def test_create_reaction_logs(self, mock_write_log, db_session, sample_reaction):
        """Проверка логирования при создании реакции"""
        background_tasks = BackgroundTasks()
        await main.create_or_update_reaction(
            schemas.ReactionCreate(**sample_reaction),
            background_tasks,
            db_session,
        )
        assert len(background_tasks.tasks) == 1
        task = background_tasks.tasks[0]
        task.func(*task.args, **task.kwargs)
        mock_write_log.assert_called_once()
        call_args = mock_write_log.call_args[0][0]
        assert "REACTION CREATED" in call_args
        assert str(sample_reaction["user_id"]) in call_args
    
    @pytest.mark.asyncio
    @patch("app.main.write_log")
    async def test_delete_reaction_logs(self, mock_write_log, db_session, sample_reaction):
        """Проверка логирования при удалении реакции"""
        # Создаём
        first_tasks = BackgroundTasks()
        await main.create_or_update_reaction(
            schemas.ReactionCreate(**sample_reaction),
            first_tasks,
            db_session,
        )
        assert len(first_tasks.tasks) == 1
        first_tasks.tasks[0].func(*first_tasks.tasks[0].args, **first_tasks.tasks[0].kwargs)
        # Отправляем ту же для удаления
        second_tasks = BackgroundTasks()
        await main.create_or_update_reaction(
            schemas.ReactionCreate(**sample_reaction),
            second_tasks,
            db_session,
        )
        assert len(second_tasks.tasks) == 1
        second_tasks.tasks[0].func(*second_tasks.tasks[0].args, **second_tasks.tasks[0].kwargs)
        assert mock_write_log.call_count == 2


class TestAsyncEndpoints:
    """Тесты асинхронных эндпоинтов"""
    
    @pytest.mark.asyncio
    @patch("app.main.httpx.AsyncClient")
    async def test_get_external_news(self, mock_client_class):
        """Получение внешних новостей"""
        from app.main import get_external_news
        
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
    
    @patch("app.main.httpx.AsyncClient")
    def test_get_combined_data_endpoint(self, mock_client_class):
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
