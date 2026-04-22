# tests/conftest.py
"""
Общие фикстуры для всех тестов
"""

import pytest
from datetime import datetime, timezone
from typing import Dict, Any


@pytest.fixture
def test_user_id() -> int:
    """Фикстура с ID тестового пользователя"""
    return 12345


@pytest.fixture
def test_news_url() -> str:
    """Фикстура с URL тестовой новости"""
    return "https://lenta.ru/news/2025/03/15/test-article/"


@pytest.fixture
def test_article_data(test_user_id, test_news_url) -> Dict[str, Any]:
    """Фикстура с данными тестовой статьи"""
    return {
        "user_id": test_user_id,
        "url": test_news_url,
        "title": "Тестовая статья для юнит-тестов",
        "description": "Это описание тестовой статьи, используется в тестах",
        "url_to_image": "https://example.com/test-image.jpg",
        "source_name": "Lenta.ru",
        "published_at": datetime.now(timezone.utc).isoformat()
    }


@pytest.fixture
def test_reaction_data(test_user_id, test_news_url) -> Dict[str, Any]:
    """Фикстура с данными тестовой реакции"""
    return {
        "user_id": test_user_id,
        "news_id": test_news_url,
        "reaction_type": "important"
    }


@pytest.fixture
def test_comment_data(test_user_id) -> Dict[str, Any]:
    """Фикстура с данными тестового комментария"""
    return {
        "user_id": test_user_id,
        "text": "Это тестовый комментарий, созданный в рамках юнит-тестов"
    }


def pytest_configure(config):
    """Регистрируем пользовательские маркеры тестов."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )


@pytest.fixture(autouse=True)
def disable_network_requests(monkeypatch):
    """
    Отключаем реальные сетевые запросы во время тестов
    (для всех сервисов).
    """
    import requests

    def mock_request(*args, **kwargs):
        raise RuntimeError("Network requests are disabled during tests!")

    monkeypatch.setattr(requests, "get", mock_request)
    monkeypatch.setattr(requests, "post", mock_request)
    monkeypatch.setattr(requests, "put", mock_request)
    monkeypatch.setattr(requests, "delete", mock_request)
