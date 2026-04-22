"""
User Content Service — микросервис избранного и комментариев.

Полностью асинхронный (asyncpg + AsyncSession). Запуск:

    uvicorn user_content_service.main:app --reload --port 8002

Через Docker: см. Dockerfile.user-content-service
"""

from datetime import datetime, timezone
from typing import List, Optional
from urllib.parse import unquote

from fastapi import Depends, FastAPI, HTTPException, Path, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_db, init_db
from .models import Comment as CommentModel
from .models import FavoriteArticle as FavoriteArticleModel
from .schemas import (
    Comment,
    CommentCreate,
    CommentList,
    CommentResponse,
    CommentUpdate,
    FavoriteArticle,
    FavoriteCheckResponse,
    FavoriteList,
    FavoriteToggleRequest,
    FavoriteToggleResponse,
    FavoriteUrlsResponse,
    FavoriteWithComments,
)

app = FastAPI(
    title="User Content Service",
    description="Асинхронный микросервис управления избранным и комментариями к статьям.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _to_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Нормализует datetime в UTC (timezone-aware) для asyncpg."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@app.on_event("startup")
async def on_startup():
    await init_db()


# Эндпоинты избранного

@app.post("/favorites/toggle", response_model=FavoriteToggleResponse, tags=["favorites"])
async def toggle_favorite(payload: FavoriteToggleRequest, db: AsyncSession = Depends(get_db)):
    """Добавить или удалить статью из избранного (toggle)."""
    url_str = str(payload.url).strip()
    if not url_str:
        raise HTTPException(
            status_code=400,
            detail={"error": "URL статьи не указан", "code": 400, "details": {"url": ["Обязательное поле"]}},
        )

    result = await db.execute(
        select(FavoriteArticleModel).where(
            FavoriteArticleModel.user_id == payload.user_id,
            FavoriteArticleModel.url == url_str,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        await db.delete(existing)
        await db.commit()
        return FavoriteToggleResponse(success=True, is_favorite=False, action="removed")

    published_at = _to_utc(payload.published_at) or _now_utc()
    added_at = _now_utc()

    fav = FavoriteArticleModel(
        user_id=payload.user_id,
        url=url_str,
        title=payload.title or "Заголовок новости",
        description=payload.description or "Описание новости",
        url_to_image=payload.url_to_image,
        source_name=payload.source_name or "Lenta.ru",
        published_at=published_at,
        added_at=added_at,
        note=None,
    )
    db.add(fav)
    await db.commit()
    await db.refresh(fav)
    return FavoriteToggleResponse(success=True, is_favorite=True, action="added")


@app.get("/favorites", response_model=FavoriteList, tags=["favorites"])
async def get_favorites(
    user_id: int = Query(..., description="ID пользователя"),
    include_comments: bool = Query(False, description="Включить комментарии к статьям"),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Получить список избранных статей пользователя."""
    stmt = (
        select(FavoriteArticleModel)
        .where(FavoriteArticleModel.user_id == user_id)
        .order_by(FavoriteArticleModel.added_at.desc())
    )
    count_result = await db.execute(select(func.count()).select_from(FavoriteArticleModel).where(FavoriteArticleModel.user_id == user_id))
    total = count_result.scalar() or 0

    result = await db.execute(stmt.offset((page - 1) * size).limit(size))
    rows = result.scalars().all()

    items: List[FavoriteWithComments] = []
    for row in rows:
        comments: List[Comment] = []
        if include_comments:
            com_stmt = select(CommentModel).where(
                CommentModel.article_id == row.id,
                CommentModel.user_id == user_id,
            )
            com_result = await db.execute(com_stmt)
            comment_rows = com_result.scalars().all()
            comments = [Comment.model_validate(c) for c in comment_rows]
        fav = FavoriteArticle.model_validate(row)
        items.append(FavoriteWithComments(**fav.model_dump(), comments=comments))

    return FavoriteList(items=items, total=total, page=page, size=size)


@app.get("/favorites/check/{url:path}", response_model=FavoriteCheckResponse, tags=["favorites"])
async def check_favorite(
    url: str = Path(...),
    user_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Проверить наличие статьи в избранном пользователя."""
    url_decoded = unquote(url)
    result = await db.execute(
        select(FavoriteArticleModel).where(
            FavoriteArticleModel.user_id == user_id,
            FavoriteArticleModel.url == url_decoded,
        )
    )
    fav = result.scalar_one_or_none()
    if fav:
        return FavoriteCheckResponse(is_favorite=True, article_id=fav.id)
    return FavoriteCheckResponse(is_favorite=False, article_id=None)


@app.get("/favorites/urls", response_model=FavoriteUrlsResponse, tags=["favorites"])
async def get_favorite_urls(
    user_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Получить список URL избранных статей пользователя."""
    result = await db.execute(select(FavoriteArticleModel.url).where(FavoriteArticleModel.user_id == user_id))
    urls = [r[0] for r in result.all()]
    return FavoriteUrlsResponse(user_id=user_id, urls=urls, total=len(urls))


# Эндпоинты комментариев

@app.post("/favorites/{articleId}/comments", response_model=CommentResponse, status_code=201, tags=["comments"])
async def add_comment(
    articleId: int = Path(..., description="ID избранной статьи"),
    payload: CommentCreate = ...,
    db: AsyncSession = Depends(get_db),
):
    """Добавить комментарий к избранной статье."""
    result = await db.execute(
        select(FavoriteArticleModel).where(
            FavoriteArticleModel.id == articleId,
            FavoriteArticleModel.user_id == payload.user_id,
        )
    )
    fav = result.scalar_one_or_none()
    if not fav:
        raise HTTPException(
            status_code=404,
            detail={"error": "Статья не найдена в избранном пользователя", "code": 404},
        )
    if not (payload.text and payload.text.strip()):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Текст комментария не может быть пустым",
                "code": 400,
                "details": {"text": ["Текст комментария не может быть пустым"]},
            },
        )

    comment = CommentModel(
        article_id=articleId,
        user_id=payload.user_id,
        text=payload.text.strip(),
        created_at=_now_utc(),
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    return CommentResponse(success=True, comment=Comment.model_validate(comment))


@app.get("/favorites/{articleId}/comments", response_model=CommentList, tags=["comments"])
async def get_comments(
    articleId: int = Path(...),
    user_id: int = Query(...),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Получить комментарии к избранной статье."""
    result = await db.execute(
        select(FavoriteArticleModel).where(
            FavoriteArticleModel.id == articleId,
            FavoriteArticleModel.user_id == user_id,
        )
    )
    fav = result.scalar_one_or_none()
    if not fav:
        raise HTTPException(
            status_code=404,
            detail={"error": "Статья не найдена в избранном пользователя", "code": 404},
        )

    base_stmt = select(CommentModel).where(
        CommentModel.article_id == articleId,
        CommentModel.user_id == user_id,
    )
    count_result = await db.execute(select(func.count()).select_from(CommentModel).where(
        CommentModel.article_id == articleId,
        CommentModel.user_id == user_id,
    ))
    total = count_result.scalar() or 0

    stmt = base_stmt.order_by(CommentModel.created_at.desc()).offset((page - 1) * size).limit(size)
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return CommentList(
        items=[Comment.model_validate(r) for r in rows],
        total=total,
        page=page,
        size=size,
    )


@app.put("/comments/{commentId}", response_model=CommentResponse, tags=["comments"])
async def edit_comment(
    commentId: int = Path(...),
    payload: CommentUpdate = ...,
    db: AsyncSession = Depends(get_db),
):
    """Редактировать комментарий."""
    result = await db.execute(select(CommentModel).where(CommentModel.id == commentId))
    comment = result.scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=404, detail={"error": "Комментарий не найден", "code": 404})
    if comment.user_id != payload.user_id:
        raise HTTPException(
            status_code=403,
            detail={"error": "Комментарий принадлежит другому пользователю", "code": 403},
        )
    if not (payload.text and payload.text.strip()):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Текст комментария не может быть пустым",
                "code": 400,
                "details": {"text": ["Текст комментария не может быть пустым"]},
            },
        )

    comment.text = payload.text.strip()
    await db.commit()
    await db.refresh(comment)
    return CommentResponse(success=True, comment=Comment.model_validate(comment))


@app.delete("/comments/{commentId}", tags=["comments"])
async def delete_comment(
    commentId: int = Path(...),
    user_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Удалить комментарий."""
    result = await db.execute(select(CommentModel).where(CommentModel.id == commentId))
    comment = result.scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=404, detail={"error": "Комментарий не найден", "code": 404})
    if comment.user_id != user_id:
        raise HTTPException(
            status_code=403,
            detail={"error": "Комментарий принадлежит другому пользователю", "code": 403},
        )
    await db.delete(comment)
    await db.commit()
    return {"success": True}


@app.get("/internal/health", tags=["internal"])
async def health_check(db: AsyncSession = Depends(get_db)):
    """Проверка работоспособности сервиса и БД."""
    fav_result = await db.execute(select(func.count()).select_from(FavoriteArticleModel))
    comment_result = await db.execute(select(func.count()).select_from(CommentModel))
    fav_count = fav_result.scalar() or 0
    comment_count = comment_result.scalar() or 0
    return {
        "status": "healthy",
        "timestamp": _now_utc().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "database": "postgresql",
        "stats": {"favorites_count": fav_count, "comments_count": comment_count},
    }
