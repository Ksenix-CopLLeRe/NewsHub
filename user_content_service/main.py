"""
Точка входа микросервиса User Content Service.

Повторно использует FastAPI‑приложение из `mocks/user_content_service_mock.py`,
чтобы не дублировать логику и модели.

Команда для локального запуска (без Docker):

    uvicorn user_content_service.main:app --reload --port 8002
"""

from mocks.user_content_service_mock import app  # noqa: F401

