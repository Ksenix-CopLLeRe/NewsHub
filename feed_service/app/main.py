# app/main.py
from fastapi import FastAPI, Depends, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional, List
from app.database import SessionLocal
from app import crud, models, schemas
import time
import logging
import threading

from app import models, schemas, crud, rss_parser
from app.database import engine, get_db

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создание таблиц (для разработки)
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Feed Service",
    description="Микросервис для управления новостями из RSS-лент",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def auto_clean_old_news():
    """Запускать очистку раз в сутки"""
    while True:
        time.sleep(24 * 3600)  # раз в день
        db = SessionLocal()
        crud.delete_old_news(db, days=30)
        db.close()

# Запустить при старте
thread = threading.Thread(target=auto_clean_old_news, daemon=True)
thread.start()

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
    """Проверка здоровья сервиса"""
    db_status = "unknown"
    total_news = 0
    
    try:
        # Проверяем подключение к БД
        db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {e}"
    
    # Получаем количество новостей
    try:
        total_news = db.query(models.NewsItem).count()
    except Exception as e:
        # Если ошибка, но БД уже unhealthy, добавляем детали
        if db_status == "healthy":
            db_status = f"unhealthy: {e}"
    
    # Определяем общий статус
    status = "healthy"
    if db_status != "healthy":
        status = "degraded"
    
    return {
        "status": status,
        "timestamp": time.time(),
        "services": {
            "database": db_status
        },
        "stats": {
            "total_news": total_news
        }
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

# ---------- GET /news/{id} ----------
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
@app.post("/rss/update/{category}", response_model=schemas.RSSUpdateResponse)
def update_category(
    category: str,
    db: Session = Depends(get_db)
):
    """
    Обновить новости из RSS для указанной категории
    """
    start_time = time.time()
    
    if category not in rss_parser.RSS_FEEDS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown category: {category}. Available: {list(rss_parser.RSS_FEEDS.keys())}"
        )
    
    # Парсим RSS
    news_items = rss_parser.parse_rss_feed(category)
    parsed_count = len(news_items)
    
    # Сохраняем в БД
    saved_count = 0
    error_count = 0
    
    for item in news_items:
        try:
            news_create = schemas.NewsCreate(**item)
            crud.create_or_update_news(db, news_create)
            saved_count += 1
        except Exception as e:
            logger.error(f"Ошибка сохранения: {e}")
            error_count += 1
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    return {
        "category": category,
        "parsed": parsed_count,
        "saved": saved_count,
        "errors": error_count,
        "duration_ms": duration_ms
    }

# ---------- POST /rss/update-all ----------
@app.post("/rss/update-all", response_model=schemas.BulkUpdateResponse)
def update_all_categories(
    db: Session = Depends(get_db)
):
    """
    Обновить все категории
    """
    start_time = time.time()
    results = {}
    total_parsed = 0
    total_saved = 0
    total_errors = 0
    
    for category in rss_parser.RSS_FEEDS.keys():
        try:
            # Парсим RSS
            news_items = rss_parser.parse_rss_feed(category)
            parsed = len(news_items)
            saved = 0
            errors = 0
            
            # Сохраняем
            for item in news_items:
                try:
                    news_create = schemas.NewsCreate(**item)
                    crud.create_or_update_news(db, news_create)
                    saved += 1
                except Exception as e:
                    logger.error(f"Ошибка сохранения в {category}: {e}")
                    errors += 1
            
            results[category] = {
                "parsed": parsed,
                "saved": saved,
                "errors": errors
            }
            total_parsed += parsed
            total_saved += saved
            total_errors += errors
            
            time.sleep(0.5)  # Пауза между запросами
            
        except Exception as e:
            logger.error(f"Ошибка обновления категории {category}: {e}")
            results[category] = {
                "parsed": 0,
                "saved": 0,
                "errors": 1,
                "error": str(e)
            }
            total_errors += 1
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    return {
        "status": "completed",
        "results": results,
        "total_parsed": total_parsed,
        "total_saved": total_saved,
        "total_errors": total_errors,
        "duration_ms": duration_ms
    }


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