"""
User Content Service — микросервис избранного и комментариев.

Работает с SQLite. Запуск:

    uvicorn user_content_service.main:app --reload --port 8002

Через Docker: см. Dockerfile.user-content-service
"""

from datetime import datetime, timezone
from typing import List
from urllib.parse import unquote

from fastapi import Depends, FastAPI, HTTPException, Path, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func
from sqlalchemy.orm import Session

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
    description="Микросервис управления избранным и комментариями к статьям.",
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


@app.on_event("startup")
def on_startup():
    init_db()


# --- Эндпоинты избранного ---


@app.post("/favorites/toggle", response_model=FavoriteToggleResponse, tags=["favorites"])
async def toggle_favorite(payload: FavoriteToggleRequest, db: Session = Depends(get_db)):
    """Добавить или удалить статью из избранного (toggle)."""
    url_str = str(payload.url).strip()
    if not url_str:
        raise HTTPException(
            status_code=400,
            detail={"error": "URL статьи не указан", "code": 400, "details": {"url": ["Обязательное поле"]}},
        )

    existing = db.query(FavoriteArticleModel).filter(
        FavoriteArticleModel.user_id == payload.user_id,
        FavoriteArticleModel.url == url_str,
    ).first()

    if existing:
        db.delete(existing)
        db.commit()
        return FavoriteToggleResponse(success=True, is_favorite=False, action="removed")

    published_at = payload.published_at or _now_utc()
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
    db.commit()
    db.refresh(fav)
    return FavoriteToggleResponse(success=True, is_favorite=True, action="added")


@app.get("/favorites", response_model=FavoriteList, tags=["favorites"])
async def get_favorites(
    user_id: int = Query(..., description="ID пользователя"),
    include_comments: bool = Query(False, description="Включить комментарии к статьям"),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Получить список избранных статей пользователя."""
    query = db.query(FavoriteArticleModel).filter(FavoriteArticleModel.user_id == user_id)
    total = query.count()
    rows = query.order_by(FavoriteArticleModel.added_at.desc()).offset((page - 1) * size).limit(size).all()

    items: List[FavoriteWithComments] = []
    for row in rows:
        comments: List[Comment] = []
        if include_comments:
            comment_rows = db.query(CommentModel).filter(
                CommentModel.article_id == row.id,
                CommentModel.user_id == user_id,
            ).all()
            comments = [Comment.model_validate(c) for c in comment_rows]
        fav = FavoriteArticle.model_validate(row)
        items.append(FavoriteWithComments(**fav.model_dump(), comments=comments))

    return FavoriteList(items=items, total=total, page=page, size=size)


@app.get("/favorites/check/{url:path}", response_model=FavoriteCheckResponse, tags=["favorites"])
async def check_favorite(
    url: str = Path(...),
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """Проверить наличие статьи в избранном пользователя."""
    url_decoded = unquote(url)
    fav = db.query(FavoriteArticleModel).filter(
        FavoriteArticleModel.user_id == user_id,
        FavoriteArticleModel.url == url_decoded,
    ).first()
    if fav:
        return FavoriteCheckResponse(is_favorite=True, article_id=fav.id)
    return FavoriteCheckResponse(is_favorite=False, article_id=None)


@app.get("/favorites/urls", response_model=FavoriteUrlsResponse, tags=["favorites"])
async def get_favorite_urls(
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """Получить список URL избранных статей пользователя."""
    rows = db.query(FavoriteArticleModel.url).filter(FavoriteArticleModel.user_id == user_id).all()
    urls = [r[0] for r in rows]
    return FavoriteUrlsResponse(user_id=user_id, urls=urls, total=len(urls))


# --- Эндпоинты комментариев ---


@app.post("/favorites/{articleId}/comments", response_model=CommentResponse, status_code=201, tags=["comments"])
async def add_comment(
    articleId: int = Path(..., description="ID избранной статьи"),
    payload: CommentCreate = ...,
    db: Session = Depends(get_db),
):
    """Добавить комментарий к избранной статье."""
    fav = db.query(FavoriteArticleModel).filter(
        FavoriteArticleModel.id == articleId,
        FavoriteArticleModel.user_id == payload.user_id,
    ).first()
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
    db.commit()
    db.refresh(comment)
    return CommentResponse(success=True, comment=Comment.model_validate(comment))


@app.get("/favorites/{articleId}/comments", response_model=CommentList, tags=["comments"])
async def get_comments(
    articleId: int = Path(...),
    user_id: int = Query(...),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Получить комментарии к избранной статье."""
    fav = db.query(FavoriteArticleModel).filter(
        FavoriteArticleModel.id == articleId,
        FavoriteArticleModel.user_id == user_id,
    ).first()
    if not fav:
        raise HTTPException(
            status_code=404,
            detail={"error": "Статья не найдена в избранном пользователя", "code": 404},
        )

    query = db.query(CommentModel).filter(
        CommentModel.article_id == articleId,
        CommentModel.user_id == user_id,
    )
    total = query.count()
    rows = query.order_by(CommentModel.created_at.desc()).offset((page - 1) * size).limit(size).all()
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
    db: Session = Depends(get_db),
):
    """Редактировать комментарий."""
    comment = db.query(CommentModel).filter(CommentModel.id == commentId).first()
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
    db.commit()
    db.refresh(comment)
    return CommentResponse(success=True, comment=Comment.model_validate(comment))


@app.delete("/comments/{commentId}", tags=["comments"])
async def delete_comment(
    commentId: int = Path(...),
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """Удалить комментарий."""
    comment = db.query(CommentModel).filter(CommentModel.id == commentId).first()
    if not comment:
        raise HTTPException(status_code=404, detail={"error": "Комментарий не найден", "code": 404})
    if comment.user_id != user_id:
        raise HTTPException(
            status_code=403,
            detail={"error": "Комментарий принадлежит другому пользователю", "code": 403},
        )
    db.delete(comment)
    db.commit()
    return {"success": True}


@app.get("/internal/health", tags=["internal"])
async def health_check(db: Session = Depends(get_db)):
    """Проверка работоспособности сервиса и БД."""
    fav_count = db.query(func.count(FavoriteArticleModel.id)).scalar() or 0
    comment_count = db.query(func.count(CommentModel.id)).scalar() or 0
    return {
        "status": "healthy",
        "timestamp": _now_utc().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "database": "sqlite",
        "stats": {"favorites_count": fav_count, "comments_count": comment_count},
    }
