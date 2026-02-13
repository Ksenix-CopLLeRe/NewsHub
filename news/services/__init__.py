"""
Сервисный слой (BFF) для интеграции с внутренними микросервисами.

Сейчас все реализации *локальные* и используют Django-модели и rss_parser.
Позже их можно заменить на HTTP‑клиентов к FastAPI‑сервисам, не меняя Django views.
"""

from django.conf import settings

from .feed_client import LocalFeedClient
from .user_content_client import LocalUserContentClient
from .reactions_client import LocalReactionsClient


def get_feed_client():
    """
    Фабрика клиента ленты новостей.

    Пока всегда возвращает локальную реализацию.
    В будущем здесь можно добавить выбор между Local/HTTP клиентом по настройкам.
    """
    return LocalFeedClient()


def get_user_content_client():
    """
    Фабрика клиента пользовательского контента (избранное + комментарии).
    """
    return LocalUserContentClient()


def get_reactions_client():
    """
    Фабрика клиента реакций.
    """
    return LocalReactionsClient()

