"""
Мок-сервер для User Content Service API.

Запускается отдельно от основного приложения и эмулирует работу
микросервиса избранного и комментариев без подключения к БД.

Совместим по основным эндпоинтам и структурам ответов со Swagger‑спецификацией
из `openapi/user-content-service.yaml`, чтобы можно было кликать Try out
и получать реалистичные заглушки данных.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict

from fastapi import FastAPI, Query, Path, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, HttpUrl
import uvicorn


class FavoriteArticle(BaseModel):
    id: int = Field(..., description="Уникальный идентификатор записи в избранном", example=42)
    user_id: int = Field(..., description="ID пользователя", example=123)
    url: HttpUrl = Field(
        ...,
        description="URL статьи",
        example="https://lenta.ru/news/2025/03/01/example/",
    )
    title: str = Field(..., description="Заголовок статьи", example="Заголовок новости")
    description: Optional[str] = Field(
        None,
        description="Описание/краткое содержание статьи",
        example="Описание новости",
    )
    url_to_image: Optional[HttpUrl] = Field(
        None,
        description="URL изображения статьи",
        example="https://example.com/image.jpg",
    )
    source_name: str = Field(
        ...,
        description="Название источника новости",
        example="Lenta.ru",
    )
    published_at: datetime = Field(
        ...,
        description="Дата публикации статьи (ISO 8601)",
        example="2025-03-01T18:00:00Z",
    )
    added_at: datetime = Field(
        ...,
        description="Дата добавления в избранное (ISO 8601)",
        example="2025-03-01T19:00:00Z",
    )
    note: Optional[str] = Field(
        None,
        description="Личная заметка пользователя",
        example="Важно прочитать позже",
    )


class FavoriteToggleRequest(BaseModel):
    user_id: int = Field(..., description="ID пользователя", example=123)
    url: HttpUrl = Field(
        ...,
        description="URL статьи (обязательно)",
        example="https://lenta.ru/news/2025/03/01/example/",
    )
    title: Optional[str] = Field(
        None,
        description="Заголовок статьи",
        example="Заголовок новости",
    )
    description: Optional[str] = Field(
        None,
        description="Описание статьи",
        example="Описание новости",
    )
    url_to_image: Optional[HttpUrl] = Field(
        None,
        description="URL изображения статьи",
        example="https://example.com/image.jpg",
    )
    source_name: Optional[str] = Field(
        "Lenta.ru",
        description="Название источника новости",
        example="Lenta.ru",
    )
    published_at: Optional[datetime] = Field(
        None,
        description="Дата публикации статьи (ISO 8601)",
        example="2025-03-01T18:00:00Z",
    )


class FavoriteToggleResponse(BaseModel):
    success: bool = Field(..., example=True)
    is_favorite: bool = Field(
        ...,
        description="Текущее состояние: true если статья в избранном, false если удалена",
        example=True,
    )
    action: str = Field(
        ...,
        description="Действие, которое было выполнено",
        example="added",
    )


class FavoriteCheckResponse(BaseModel):
    is_favorite: bool = Field(
        ...,
        description="true если статья в избранном, false если нет",
        example=True,
    )
    article_id: Optional[int] = Field(
        None,
        description="ID записи в избранном (если статья в избранном)",
        example=42,
    )


class FavoriteUrlsResponse(BaseModel):
    user_id: int = Field(..., description="ID пользователя", example=123)
    urls: List[HttpUrl] = Field(
        ...,
        description="Массив URL избранных статей",
        example=[
            "https://lenta.ru/news/2025/03/01/example1/",
            "https://lenta.ru/news/2025/03/01/example2/",
        ],
    )
    total: int = Field(..., description="Общее количество избранных статей", example=2)


class Comment(BaseModel):
    id: int = Field(..., description="Уникальный идентификатор комментария", example=15)
    article_id: int = Field(..., description="ID избранной статьи", example=42)
    user_id: int = Field(..., description="ID автора комментария", example=123)
    text: str = Field(..., description="Текст комментария", example="Это интересная статья!")
    created_at: datetime = Field(
        ...,
        description="Дата создания комментария (ISO 8601)",
        example="2025-03-01T20:00:00Z",
    )


class CommentCreate(BaseModel):
    user_id: int = Field(..., description="ID пользователя", example=123)
    text: str = Field(..., description="Текст комментария", example="Это интересная статья!")


class CommentUpdate(BaseModel):
    user_id: int = Field(..., description="ID пользователя", example=123)
    text: str = Field(
        ...,
        description="Новый текст комментария",
        example="Обновленный текст комментария",
    )


class CommentResponse(BaseModel):
    success: bool = Field(..., example=True)
    comment: Comment


class CommentList(BaseModel):
    items: List[Comment]
    total: int = Field(..., description="Общее количество комментариев", example=5)
    page: int = Field(..., description="Номер текущей страницы", example=1)
    size: int = Field(..., description="Размер страницы", example=10)


class FavoriteWithComments(FavoriteArticle):
    comments: List[Comment] = Field(
        default_factory=list,
        description="Комментарии к статье (если include_comments=true)",
    )


class FavoriteList(BaseModel):
    items: List[FavoriteWithComments]
    total: int = Field(..., description="Общее количество избранных статей", example=42)
    page: int = Field(..., description="Номер текущей страницы", example=1)
    size: int = Field(..., description="Размер страницы", example=10)


# Мок‑хранилище в памяти


_FAVORITES: Dict[int, FavoriteArticle] = {}
_COMMENTS: Dict[int, Comment] = {}
_NEXT_FAVORITE_ID: int = 1
_NEXT_COMMENT_ID: int = 1


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _init_mock_data() -> None:
    """
    Инициализируем несколько избранных статей и комментариев для пользователя 123,
    чтобы сразу были данные при открытии Swagger.
    """
    global _NEXT_FAVORITE_ID, _NEXT_COMMENT_ID

    if _FAVORITES:
        return

    base_published = datetime(2025, 3, 1, 18, 0, 0, tzinfo=timezone.utc)

    favorites = [
        FavoriteArticle(
            id=_NEXT_FAVORITE_ID,
            user_id=123,
            url="https://lenta.ru/news/2025/03/01/example1/",
            title="Новости дня: главное к вечеру",
            description="Краткий обзор главных событий дня.",
            url_to_image="https://example.com/image1.jpg",
            source_name="Lenta.ru",
            published_at=base_published,
            added_at=base_published + timedelta(hours=1),
            note="Прочитать вечером",
        ),
        FavoriteArticle(
            id=_NEXT_FAVORITE_ID + 1,
            user_id=123,
            url="https://lenta.ru/news/2025/03/01/example2/",
            title="Экономика: курс валют и рынки",
            description="Обзор ситуации на валютном рынке.",
            url_to_image="https://example.com/image2.jpg",
            source_name="Lenta.ru",
            published_at=base_published + timedelta(hours=2),
            added_at=base_published + timedelta(hours=3),
            note=None,
        ),
    ]

    for fav in favorites:
        _FAVORITES[fav.id] = fav
        _NEXT_FAVORITE_ID += 1

    comment = Comment(
        id=_NEXT_COMMENT_ID,
        article_id=1,
        user_id=123,
        text="Это интересная статья!",
        created_at=base_published + timedelta(hours=2),
    )
    _COMMENTS[comment.id] = comment
    _NEXT_COMMENT_ID += 1


def _find_favorite_by_user_and_url(user_id: int, url: str) -> Optional[FavoriteArticle]:
    for fav in _FAVORITES.values():
        if fav.user_id == user_id and str(fav.url) == url:
            return fav
    return None


def _get_comments_for_article_and_user(article_id: int, user_id: int) -> List[Comment]:
    return [
        c for c in _COMMENTS.values() if c.article_id == article_id and c.user_id == user_id
    ]


# FastAPI приложение


app = FastAPI(
    title="User Content Service Mock",
    description=(
        "Мок‑сервер для тестирования User Content Service API "
        "(избранное + комментарии) без подключения к БД."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_init_mock_data()


# Эндпоинты избранного


@app.post(
    "/favorites/toggle",
    response_model=FavoriteToggleResponse,
    tags=["favorites"],
    summary="Добавить или удалить статью из избранного (toggle)",
)
async def toggle_favorite(payload: FavoriteToggleRequest):
    """
    Переключает состояние статьи в избранном пользователя.

    - Если статьи ещё нет в избранном — добавляет запись.
    - Если статья уже есть — удаляет её.
    """
    global _NEXT_FAVORITE_ID

    if not payload.url:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "URL статьи не указан",
                "code": 400,
                "details": {"url": ["Обязательное поле"]},
            },
        )

    existing = _find_favorite_by_user_and_url(payload.user_id, str(payload.url))
    if existing:
        del _FAVORITES[existing.id]
        return FavoriteToggleResponse(success=True, is_favorite=False, action="removed")

    published_at = payload.published_at or _now_utc()

    favorite = FavoriteArticle(
        id=_NEXT_FAVORITE_ID,
        user_id=payload.user_id,
        url=payload.url,
        title=payload.title or "Заголовок новости",
        description=payload.description or "Описание новости",
        url_to_image=payload.url_to_image,
        source_name=payload.source_name or "Lenta.ru",
        published_at=published_at,
        added_at=_now_utc(),
        note=None,
    )
    _FAVORITES[favorite.id] = favorite
    _NEXT_FAVORITE_ID += 1

    return FavoriteToggleResponse(success=True, is_favorite=True, action="added")


@app.get(
    "/favorites",
    response_model=FavoriteList,
    tags=["favorites"],
    summary="Получить список избранных статей пользователя",
)
async def get_favorites(
    user_id: int = Query(..., description="ID пользователя", example=123),
    include_comments: bool = Query(
        False,
        description="Включить комментарии к статьям в ответ",
        example=True,
    ),
    page: int = Query(1, ge=1, description="Номер страницы (начиная с 1)", example=1),
    size: int = Query(
        10,
        ge=1,
        le=100,
        description="Количество элементов на странице",
        example=10,
    ),
):
    user_favorites = [fav for fav in _FAVORITES.values() if fav.user_id == user_id]
    total = len(user_favorites)

    start = (page - 1) * size
    end = start + size
    page_items = user_favorites[start:end]

    items_with_comments: List[FavoriteWithComments] = []
    for fav in page_items:
        comments: List[Comment] = []
        if include_comments:
            comments = _get_comments_for_article_and_user(fav.id, user_id)
        items_with_comments.append(FavoriteWithComments(**fav.dict(), comments=comments))

    return FavoriteList(items=items_with_comments, total=total, page=page, size=size)


@app.get(
    "/favorites/check/{url:path}",
    response_model=FavoriteCheckResponse,
    tags=["favorites"],
    summary="Проверить наличие статьи в избранном пользователя",
)
async def check_favorite(
    url: str = Path(..., description="URL статьи (URL-encoded при необходимости)"),
    user_id: int = Query(..., description="ID пользователя", example=123),
):
    favorite = _find_favorite_by_user_and_url(user_id, url)
    if favorite:
        return FavoriteCheckResponse(is_favorite=True, article_id=favorite.id)
    return FavoriteCheckResponse(is_favorite=False, article_id=None)


@app.get(
    "/favorites/urls",
    response_model=FavoriteUrlsResponse,
    tags=["favorites"],
    summary="Получить список URL избранных статей пользователя",
)
async def get_favorite_urls(
    user_id: int = Query(..., description="ID пользователя", example=123),
):
    urls: List[HttpUrl] = [
        fav.url for fav in _FAVORITES.values() if fav.user_id == user_id
    ]
    return FavoriteUrlsResponse(user_id=user_id, urls=urls, total=len(urls))


# Эндпоинты комментариев


@app.post(
    "/favorites/{articleId}/comments",
    response_model=CommentResponse,
    status_code=201,
    tags=["comments"],
    summary="Добавить комментарий к избранной статье",
)
async def add_comment(
    articleId: int = Path(..., description="ID избранной статьи", example=42),
    payload: CommentCreate = ...,
):
    global _NEXT_COMMENT_ID

    favorite = _FAVORITES.get(articleId)
    if not favorite or favorite.user_id != payload.user_id:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Статья не найдена в избранном пользователя",
                "code": 404,
            },
        )

    if not payload.text.strip():
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Текст комментария не может быть пустым",
                "code": 400,
                "details": {"text": ["Текст комментария не может быть пустым"]},
            },
        )

    comment = Comment(
        id=_NEXT_COMMENT_ID,
        article_id=articleId,
        user_id=payload.user_id,
        text=payload.text,
        created_at=_now_utc(),
    )
    _COMMENTS[comment.id] = comment
    _NEXT_COMMENT_ID += 1

    return CommentResponse(success=True, comment=comment)


@app.get(
    "/favorites/{articleId}/comments",
    response_model=CommentList,
    tags=["comments"],
    summary="Получить комментарии к избранной статье",
)
async def get_comments(
    articleId: int = Path(..., description="ID избранной статьи", example=42),
    user_id: int = Query(..., description="ID пользователя", example=123),
    page: int = Query(1, ge=1, description="Номер страницы (начиная с 1)", example=1),
    size: int = Query(
        10,
        ge=1,
        le=100,
        description="Количество элементов на странице",
        example=10,
    ),
):
    favorite = _FAVORITES.get(articleId)
    if not favorite or favorite.user_id != user_id:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Статья не найдена в избранном пользователя",
                "code": 404,
            },
        )

    all_comments = _get_comments_for_article_and_user(articleId, user_id)
    total = len(all_comments)
    start = (page - 1) * size
    end = start + size
    page_items = all_comments[start:end]

    return CommentList(items=page_items, total=total, page=page, size=size)


@app.put(
    "/comments/{commentId}",
    response_model=CommentResponse,
    tags=["comments"],
    summary="Редактировать комментарий",
)
async def edit_comment(
    commentId: int = Path(..., description="ID комментария", example=15),
    payload: CommentUpdate = ...,
):
    comment = _COMMENTS.get(commentId)
    if not comment:
        raise HTTPException(
            status_code=404,
            detail={"error": "Комментарий не найден", "code": 404},
        )

    if comment.user_id != payload.user_id:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Комментарий принадлежит другому пользователю",
                "code": 403,
            },
        )

    if not payload.text.strip():
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Текст комментария не может быть пустым",
                "code": 400,
                "details": {"text": ["Текст комментария не может быть пустым"]},
            },
        )

    # Обновляем текст комментария
    updated = comment.copy(update={"text": payload.text})
    _COMMENTS[commentId] = updated

    return CommentResponse(success=True, comment=updated)


@app.delete(
    "/comments/{commentId}",
    tags=["comments"],
    summary="Удалить комментарий",
)
async def delete_comment(
    commentId: int = Path(..., description="ID комментария", example=15),
    user_id: int = Query(..., description="ID пользователя", example=123),
):
    comment = _COMMENTS.get(commentId)
    if not comment:
        raise HTTPException(
            status_code=404,
            detail={"error": "Комментарий не найден", "code": 404},
        )

    if comment.user_id != user_id:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Комментарий принадлежит другому пользователю",
                "code": 403,
            },
        )

    del _COMMENTS[commentId]
    return {"success": True}


# Технические / внутренние эндпоинты (по желанию)

@app.get(
    "/internal/health",
    tags=["internal"],
    summary="Проверка здоровья мок‑сервера",
)
async def health_check():
    return {
        "status": "healthy",
        "timestamp": _now_utc().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "stats": {
            "favorites_count": len(_FAVORITES),
            "comments_count": len(_COMMENTS),
        },
    }


# Запуск


if __name__ == "__main__":
    print("=" * 60)
    print("User Content Service Mock Server")
    print("=" * 60)
    print("\n Публичные эндпоинты:")
    print("  POST http://localhost:8002/favorites/toggle")
    print("  GET  http://localhost:8002/favorites")
    print("  GET  http://localhost:8002/favorites/check/{url}")
    print("  GET  http://localhost:8002/favorites/urls")
    print("  POST http://localhost:8002/favorites/{articleId}/comments")
    print("  GET  http://localhost:8002/favorites/{articleId}/comments")
    print("  PUT  http://localhost:8002/comments/{commentId}")
    print("  DELETE http://localhost:8002/comments/{commentId}")
    print("\n Swagger UI:   http://localhost:8002/docs")
    print("   ReDoc:        http://localhost:8002/redoc")
    print("=" * 60)

    uvicorn.run(app, host="0.0.0.0", port=8002)

