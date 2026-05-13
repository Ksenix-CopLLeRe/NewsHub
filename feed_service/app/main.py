# app/main.py
import uuid
import logging
import os
import time
import asyncio
from contextlib import asynccontextmanager
from typing import Optional, List

from fastapi import FastAPI, Depends, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy.orm import Session
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app import crud, models, schemas, rss_parser
from app.database import SessionLocal, engine, get_db
from app.logging_config import correlation_id_var, setup_json_logging
from app.rss_parser import update_category_async, update_all_categories_async

setup_json_logging("feed-service")
logger = logging.getLogger(__name__)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        cid = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        token = correlation_id_var.set(cid)
        try:
            response = await call_next(request)
        finally:
            correlation_id_var.reset(token)
        response.headers["X-Correlation-ID"] = cid
        return response

_sentry_dsn = os.getenv("SENTRY_DSN")
if _sentry_dsn:
    import sentry_sdk
    from sentry_sdk.integrations.starlette import StarletteIntegration
    from sentry_sdk.integrations.fastapi import FastApiIntegration

    sentry_sdk.init(
        dsn=_sentry_dsn,
        integrations=[
            StarletteIntegration(transaction_style="endpoint"),
            FastApiIntegration(transaction_style="endpoint"),
        ],
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.0")),
        environment=os.getenv("SENTRY_ENVIRONMENT", os.getenv("ENVIRONMENT", "development")),
    )


def _memory_rss_mb():
    try:
        import psutil

        return round(psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024, 2)
    except Exception:
        return None


def _sample_rss_dependency():
    if os.getenv("HEALTH_CHECK_SAMPLE_RSS", "true").lower() != "true":
        return {"skipped": True}
    try:
        import httpx

        first_list = next(iter(rss_parser.RSS_FEEDS.values()))
        url = first_list[0]
        r = httpx.get(url, timeout=3.0, follow_redirects=True)
        return {"ok": r.status_code < 500, "status_code": r.status_code}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:160]}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
        
    # Создание таблиц
    models.Base.metadata.create_all(bind=engine)
    logger.info("Database tables created/verified")
    
    # Запуск фоновой очистки старых новостей
    asyncio.create_task(auto_clean_old_news_async())
    logger.info("Auto-clean task started")
    
    logger.info("Starting initial RSS parsing...")
    db = SessionLocal()
    try:
        result = await update_all_categories_async(db)
        logger.info(f"Initial RSS parsing completed: {result}")
    except Exception as e:
        logger.error(f"Error during initial RSS parsing: {e}")
    finally:
        db.close()
    
    yield
    
    engine.dispose()

async def auto_clean_old_news_async():
    """Асинхронная очистка старых новостей раз в сутки"""
    while True:
        await asyncio.sleep(24 * 3600)  # раз в день
        db = SessionLocal()
        try:
            deleted = crud.delete_old_news(db, days=30)
            logger.info(f"Auto-cleaned {deleted} old news")
        except Exception as e:
            logger.error(f"Error during auto-clean: {e}")
        finally:
            db.close()

app = FastAPI(
    title="Feed Service",
    description="Микросервис для управления новостями из RSS-лент",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Instrumentator().instrument(app).expose(app)

# ============ ЭНДПОИНТЫ ============

@app.get("/")
def root():
    """Корневой эндпоинт"""
    return {
        "service": "Feed Service",
        "version": "2.0.0",
        "status": "running",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    """Проверка здоровья сервиса: БД, память, зависимости (образец RSS)."""
    db_ok = True
    db_detail = "ok"
    total_news = 0

    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        db_ok = False
        db_detail = str(exc)[:200]

    try:
        total_news = db.query(models.NewsItem).count()
    except Exception as exc:
        if db_ok:
            db_ok = False
            db_detail = str(exc)[:200]

    rss_dep = _sample_rss_dependency()
    mem_mb = _memory_rss_mb()

    rss_ok = rss_dep.get("skipped") or rss_dep.get("ok") is True
    overall_ok = db_ok and rss_ok

    return {
        "status": "healthy" if overall_ok else "degraded",
        "service": "feed-service",
        "database": {"ok": db_ok, "detail": db_detail},
        "memory": {"rss_mb": mem_mb},
        "dependencies": {
            "postgresql": {"ok": db_ok},
            "sample_rss_source": rss_dep,
        },
        "stats": {"total_news": total_news},
        "timestamp": time.time(),
    }

# ---------- GET /feed ----------
@app.get("/feed", response_model=schemas.NewsListResponse)
def get_feed(
    category: Optional[str] = Query(None, description="Фильтр по категории"),
    q: Optional[str] = Query(None, description="Поисковый запрос"),
    page: int = Query(1, ge=1, description="Номер страницы"),
    size: int = Query(20, ge=1, le=100, description="Размер страницы"),
    db: Session = Depends(get_db)
):
    """
    Получить ленту новостей с пагинацией, фильтрацией и поиском
    """
    skip = (page - 1) * size
    items, total = crud.get_news_list(
        db=db,
        category=category,
        search=q,
        skip=skip,
        limit=size
    )
    
    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size
    }

# ---------- GET /news/id/{id} — must be declared before /news/{url:path} ----------
@app.get("/news/id/{news_id}", response_model=schemas.NewsResponse)
def get_news_by_id(
    news_id: int,
    db: Session = Depends(get_db)
):
    """
    Получить новость по ID
    """
    news = crud.get_news_by_id(db, news_id)
    if not news:
        raise HTTPException(status_code=404, detail="News not found")
    return news

# ---------- GET /news/{url} ----------
@app.get("/news/{url:path}", response_model=schemas.NewsResponse)
def get_news_by_url(
    url: str,
    db: Session = Depends(get_db)
):
    """
    Получить новость по URL
    """
    news = crud.get_news_by_url(db, url)
    if not news:
        raise HTTPException(
            status_code=404,
            detail=f"News with URL {url} not found"
        )
    return news

# ---------- GET /categories ----------
@app.get("/categories", response_model=schemas.CategoriesResponse)
def get_categories(db: Session = Depends(get_db)):
    """
    Получить список категорий с количеством новостей
    """
    categories = crud.get_categories_with_counts(db)
    
    # Добавляем категории, которых нет в БД
    all_categories = list(rss_parser.RSS_FEEDS.keys())
    existing_cats = {cat: cnt for cat, cnt in categories}
    
    result = []
    for cat in all_categories:
        result.append({
            "name": cat,
            "count": existing_cats.get(cat, 0)
        })
    
    return {
        "categories": result,
        "total": len(result)
    }

# ---------- POST /rss/update/{category} ----------
@app.post("/rss/update/{category}")
async def update_category(
    category: str,
    db: Session = Depends(get_db)
):
    """
    Асинхронное обновление новостей из RSS для указанной категории
    """
    if category not in rss_parser.RSS_FEEDS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown category: {category}. Available: {list(rss_parser.RSS_FEEDS.keys())}"
        )
    
    # Вызываем асинхронный парсер
    result = await update_category_async(db, category)
    return result


# ---------- POST /rss/update-all ----------
@app.post("/rss/update-all")
async def update_all_categories(
    db: Session = Depends(get_db)
):
    """
    Асинхронное обновление всех категорий
    """
    result = await update_all_categories_async(db)
    return result


# ---------- POST /news/clean ----------
@app.post("/news/clean")
def clean_old_news(
    days: int = Query(7, ge=1, le=90, description="Удалить новости старше N дней"),
    db: Session = Depends(get_db)
):
    """
    Очистить старые новости (административный эндпоинт)
    """
    deleted = crud.delete_old_news(db, days)
    return {
        "message": f"Deleted {deleted} news older than {days} days",
        "deleted_count": deleted
    }

# ---------- GET /stats ----------
@app.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    """
    Получить статистику по новостям
    """
    total = crud.get_news_list(db, skip=0, limit=1)[1]
    categories = crud.get_categories_with_counts(db)
    
    # Получить самую старую и самую новую новость
    oldest = db.query(models.NewsItem).order_by(
        models.NewsItem.published_at.asc()
    ).first()
    
    newest = db.query(models.NewsItem).order_by(
        models.NewsItem.published_at.desc()
    ).first()
    
    return {
        "total_news": total,
        "categories": dict(categories),
        "oldest_news": {
            "title": oldest.title if oldest else None,
            "date": oldest.published_at if oldest else None
        },
        "newest_news": {
            "title": newest.title if newest else None,
            "date": newest.published_at if newest else None
        }
    }