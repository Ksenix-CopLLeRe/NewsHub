"""
Pydantic-схемы для запросов и ответов User Content Service.
Совместимы с openapi/user-content-service.yaml.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class FavoriteArticle(BaseModel):
    """Избранная статья пользователя."""

    id: int
    user_id: int
    url: str
    title: str
    description: Optional[str] = None
    url_to_image: Optional[str] = None
    source_name: str
    published_at: datetime
    added_at: datetime
    note: Optional[str] = None

    class Config:
        from_attributes = True


class FavoriteToggleRequest(BaseModel):
    """Запрос на toggle избранного."""

    user_id: int
    url: str
    title: Optional[str] = None
    description: Optional[str] = None
    url_to_image: Optional[str] = None
    source_name: Optional[str] = "Lenta.ru"
    published_at: Optional[datetime] = None


class FavoriteToggleResponse(BaseModel):
    """Результат toggle избранного."""

    success: bool = True
    is_favorite: bool
    action: str


class FavoriteCheckResponse(BaseModel):
    """Результат проверки наличия статьи в избранном."""

    is_favorite: bool
    article_id: Optional[int] = None


class FavoriteUrlsResponse(BaseModel):
    """Список URL избранных статей."""

    user_id: int
    urls: List[str]
    total: int


class Comment(BaseModel):
    """Комментарий к избранной статье."""

    id: int
    article_id: int
    user_id: int
    text: str
    created_at: datetime

    class Config:
        from_attributes = True


class CommentCreate(BaseModel):
    """Создание комментария."""

    user_id: int
    text: str


class CommentUpdate(BaseModel):
    """Обновление комментария."""

    user_id: int
    text: str


class CommentResponse(BaseModel):
    """Ответ с комментарием."""

    success: bool = True
    comment: Comment


class CommentList(BaseModel):
    """Список комментариев с пагинацией."""

    items: List[Comment]
    total: int
    page: int
    size: int


class FavoriteWithComments(FavoriteArticle):
    """Избранная статья с комментариями."""

    comments: List[Comment] = []


class FavoriteList(BaseModel):
    """Список избранных статей с пагинацией."""

    items: List[FavoriteWithComments]
    total: int
    page: int
    size: int
