import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import HTTPException

import sys
sys.path.append('.')

# ============ Устанавливаем переменные окружения ДО импорта ============
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["ENVIRONMENT"] = "test"
os.environ["DEBUG"] = "false"

# Импортируем после установки переменных
from feed_service.app import main
app = main.app

# ============ TEST ENGINE ============
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine
)

# ============ OVERRIDE DB ============
def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[main.get_db] = override_get_db

# ============ CREATE TABLES ============
@pytest.fixture(autouse=True)
def setup_database():
    main.models.Base.metadata.create_all(bind=test_engine)
    yield
    main.models.Base.metadata.drop_all(bind=test_engine)

@pytest.fixture
def db_session():
    session = TestingSessionLocal()
    yield session
    session.close()

@pytest.fixture
def sample_news():
    return {
        "url": "https://lenta.ru/news/2025/03/15/test/",
        "title": "Тестовая новость",
        "description": "Это тестовое описание новости",
        "image_url": "https://example.com/image.jpg",
        "source_name": "Lenta.ru",
        "published_at": datetime.now(timezone.utc),
        "category": "россия"
    }

# ============ TESTS ============

class TestHealthCheck:
    def test_root_endpoint(self):
        data = main.root()
        assert data["service"] == "Feed Service"
    
    def test_health_check_ok(self, db_session):
        data = main.health_check(db_session)
        assert "services" in data


class TestCRUD:
    def test_create_news(self, db_session, sample_news):
        news_create = main.schemas.NewsCreate(**sample_news)
        news = main.crud.create_news(db_session, news_create)
        
        assert news.id is not None
        assert news.url == sample_news["url"]
        assert news.title == sample_news["title"]
    
    def test_create_or_update_news_new(self, db_session, sample_news):
        news_create = main.schemas.NewsCreate(**sample_news)
        news, created = main.crud.create_or_update_news(db_session, news_create)
        
        assert created is True
        assert news.url == sample_news["url"]
    
    def test_create_or_update_news_existing(self, db_session, sample_news):
        news_create = main.schemas.NewsCreate(**sample_news)
        news1, _ = main.crud.create_or_update_news(db_session, news_create)
        
        updated_data = main.schemas.NewsCreate(**sample_news)
        updated_data.title = "Обновлённый заголовок"
        news2, created = main.crud.create_or_update_news(db_session, updated_data)
        
        assert created is False
        assert news2.id == news1.id
        assert news2.title == "Обновлённый заголовок"
    
    def test_get_news_by_id(self, db_session, sample_news):
        news_create = main.schemas.NewsCreate(**sample_news)
        news = main.crud.create_news(db_session, news_create)
        
        found = main.crud.get_news_by_id(db_session, news.id)
        assert found is not None
        assert found.id == news.id
    
    def test_get_news_by_url(self, db_session, sample_news):
        news_create = main.schemas.NewsCreate(**sample_news)
        main.crud.create_news(db_session, news_create)
        
        found = main.crud.get_news_by_url(db_session, sample_news["url"])
        assert found is not None
        assert found.url == sample_news["url"]
    
    def test_get_news_list_with_pagination(self, db_session):
        for i in range(25):
            news = main.schemas.NewsCreate(
                url=f"https://example.com/news/{i}",
                title=f"Новость {i}",
                description=f"Описание {i}",
                published_at=datetime.now(timezone.utc),
                category="россия"
            )
            main.crud.create_news(db_session, news)
        
        items, total = main.crud.get_news_list(db_session, skip=0, limit=10)
        assert len(items) == 10
        assert total == 25
    
    def test_get_news_list_with_category_filter(self, db_session):
        news1 = main.schemas.NewsCreate(
            url="https://example.com/news1",
            title="Новость 1",
            description="Описание",
            published_at=datetime.now(timezone.utc),
            category="россия"
        )
        news2 = main.schemas.NewsCreate(
            url="https://example.com/news2",
            title="Новость 2",
            description="Описание",
            published_at=datetime.now(timezone.utc),
            category="мир"
        )
        main.crud.create_news(db_session, news1)
        main.crud.create_news(db_session, news2)
        
        items, total = main.crud.get_news_list(db_session, category="россия")
        assert len(items) == 1
        assert items[0].category == "россия"
    
    def test_get_news_list_with_search(self, db_session):
        news = main.schemas.NewsCreate(
            url="https://example.com/news",
            title="Уникальный поисковый запрос",
            description="Описание с важными словами",
            published_at=datetime.now(timezone.utc),
            category="россия"
        )
        main.crud.create_news(db_session, news)
        
        items, total = main.crud.get_news_list(db_session, search="Уникальный")
        assert len(items) == 1
    
    def test_update_news(self, db_session, sample_news):
        news_create = main.schemas.NewsCreate(**sample_news)
        news = main.crud.create_news(db_session, news_create)
        
        update_data = main.schemas.NewsUpdate(title="Новый заголовок")
        updated = main.crud.update_news(db_session, news.id, update_data)
        
        assert updated is not None
        assert updated.title == "Новый заголовок"
    
    def test_delete_news(self, db_session, sample_news):
        news_create = main.schemas.NewsCreate(**sample_news)
        news = main.crud.create_news(db_session, news_create)
        
        result = main.crud.delete_news(db_session, news.id)
        assert result is True
        
        found = main.crud.get_news_by_id(db_session, news.id)
        assert found is None
    
    def test_delete_old_news(self, db_session):
        old_news = main.schemas.NewsCreate(
            url="https://example.com/old",
            title="Старая новость",
            description="Описание",
            published_at=datetime.now(timezone.utc) - timedelta(days=10),
            category="россия"
        )
        new_news = main.schemas.NewsCreate(
            url="https://example.com/new",
            title="Новая новость",
            description="Описание",
            published_at=datetime.now(timezone.utc),
            category="россия"
        )
        main.crud.create_news(db_session, old_news)
        main.crud.create_news(db_session, new_news)
        
        deleted = main.crud.delete_old_news(db_session, days=7)
        assert deleted == 1
    
    def test_get_categories_with_counts(self, db_session):
        for i in range(2):
            news = main.schemas.NewsCreate(
                url=f"https://example.com/russia/{i}",
                title=f"Россия {i}",
                description="Описание",
                published_at=datetime.now(timezone.utc),
                category="россия"
            )
            main.crud.create_news(db_session, news)
        
        news3 = main.schemas.NewsCreate(
            url="https://example.com/world/1",
            title="Мир",
            description="Описание",
            published_at=datetime.now(timezone.utc),
            category="мир"
        )
        main.crud.create_news(db_session, news3)
        
        categories = main.crud.get_categories_with_counts(db_session)
        categories_dict = dict(categories)
        
        assert categories_dict.get("россия") == 2
        assert categories_dict.get("мир") == 1


class TestAPIEndpoints:
    def test_get_feed_empty(self, db_session):
        data = main.get_feed(category=None, q=None, page=1, size=20, db=db_session)
        assert data["items"] == []
        assert data["total"] == 0
    
    def test_get_news_by_url_not_found(self, db_session):
        with pytest.raises(HTTPException) as exc_info:
            main.get_news_by_url("https://example.com/not-found", db_session)
        assert exc_info.value.status_code == 404
    
    def test_get_news_by_id_not_found(self, db_session):
        with pytest.raises(HTTPException) as exc_info:
            main.get_news_by_id(99999, db_session)
        assert exc_info.value.status_code == 404


class TestRSSParser:
    @patch("feed_service.app.rss_parser.feedparser.parse")
    def test_parse_rss_content(self, mock_parse):
        from feed_service.app.rss_parser import parse_rss_content
        
        mock_feed = MagicMock()
        mock_entry = MagicMock()
        mock_entry.link = "https://example.com/article"
        mock_entry.title = "Тестовая статья"
        mock_entry.summary = "Краткое описание"
        mock_entry.published_parsed = (2025, 3, 15, 12, 0, 0, 0, 0, 0)
        mock_entry.media_content = []
        mock_entry.media_thumbnail = []
        mock_entry.links = []
        mock_entry.enclosures = []
        
        mock_feed.entries = [mock_entry]
        mock_parse.return_value = mock_feed
        
        items = parse_rss_content("<rss></rss>", "https://lenta.ru", "россия")
        
        assert len(items) == 1
        assert items[0]["url"] == "https://example.com/article"
        assert items[0]["title"] == "Тестовая статья"
    
    def test_extract_source_name(self):
        from feed_service.app.rss_parser import extract_source_name
        
        test_cases = [
            ("https://ria.ru/news/123", "РИА Новости"),
            ("https://tass.ru/some/article", "ТАСС"),
            ("https://www.interfax.ru/news", "Интерфакс"),
            ("https://www.kommersant.ru/doc", "Коммерсантъ"),
            ("https://lenta.ru/news", "Lenta.ru"),
            ("https://unknown-domain.com", "Unknown-domain"),
        ]
        
        for url, expected in test_cases:
            assert extract_source_name(url) == expected
    
    def test_extract_image_url_from_media_content(self):
        from feed_service.app.rss_parser import _extract_image_url
        
        mock_entry = MagicMock()
        mock_entry.media_content = [{"url": "https://example.com/image.jpg"}]
        mock_entry.media_thumbnail = []
        mock_entry.links = []
        mock_entry.enclosures = []
        
        result = _extract_image_url(mock_entry)
        assert result == "https://example.com/image.jpg"
    
    def test_extract_image_url_from_enclosure(self):
        from feed_service.app.rss_parser import _extract_image_url
        
        mock_entry = MagicMock()
        mock_entry.media_content = []
        mock_entry.media_thumbnail = []
        mock_entry.links = []
        mock_entry.enclosures = [{"href": "https://example.com/photo.jpg", "type": "image/jpeg"}]
        
        result = _extract_image_url(mock_entry)
        assert result == "https://example.com/photo.jpg"
    
    @pytest.mark.asyncio
    @patch("feed_service.app.rss_parser.httpx.AsyncClient")
    async def test_fetch_rss_feed(self, mock_client_class):
        from feed_service.app.rss_parser import fetch_rss_feed
        
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.text = "<rss>content</rss>"
        mock_response.raise_for_status = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
        result = await fetch_rss_feed(mock_client, "https://example.com/rss")
        
        mock_client.get.assert_called_once()
        assert result == "<rss>content</rss>"
