from fastapi import FastAPI, Query, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime, timedelta
from app import models, schemas, rss_parser, crud
from app.database import SessionLocal, engine
from app.rss_parser import RSS_FEEDS
import threading
import time
import uvicorn
import random

# Секретный токен для внутренних эндпоинтов (в реальности хранится в .env)
INTERNAL_TOKEN = "mock-internal-token-123456"

models.Base.metadata.create_all(bind=engine)

# Создаем приложение
app = FastAPI(
    title="Feed Service",
    description="Мок-сервер для тестирования Feed Service API",
    version="1.0.0"
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Настройка CORS для тестирования из браузера
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============ ПУБЛИЧНЫЕ ЭНДПОИНТЫ ============

# @app.get("/feed", tags=["public"])
# def get_feed(
#     category: Optional[str] = Query(None, description="Фильтр по категории"),
#     q: Optional[str] = Query(None, description="Поисковый запрос"),
#     page: int = Query(1, ge=1, description="Номер страницы"),
#     size: int = Query(20, ge=1, le=100, description="Размер страницы")
# ):
#     """
#     Получить ленту новостей с поддержкой фильтрации, поиска и пагинации.
    
#     - **category**: фильтр по категории
#     - **q**: поиск по заголовку и описанию
#     - **page**: номер страницы (начиная с 1)
#     - **size**: количество элементов на странице (max 100)
#     """
#     # Фильтруем по категории
#     filtered_news = MOCK_NEWS
#     if category:
#         filtered_news = [n for n in filtered_news if n["category"] == category]
    
#     # Поиск по тексту
#     if q:
#         q_lower = q.lower()
#         filtered_news = [
#             n for n in filtered_news 
#             if q_lower in n["title"].lower() or q_lower in n["description"].lower()
#         ]
    
#     # Пагинация
#     total = len(filtered_news)
#     start = (page - 1) * size
#     end = start + size
#     paginated_news = filtered_news[start:end]
    
#     return {
#         "items": paginated_news,
#         "total": total,
#         "page": page,
#         "size": size
#     }

# @app.get("/news/{url:path}", tags=["public"])
# def get_news_by_url(url: str):
#     """
#     Получить конкретную новость по URL.
    
#     - **url**: URL статьи (URL-encoded)
#     """
#     # Ищем новость по URL
#     for news in MOCK_NEWS:
#         if news["url"] == url:
#             return news
    
#     raise HTTPException(
#         status_code=404,
#         detail={
#             "error": f"Новость с URL {url} не найдена",
#             "code": 404
#         }
#     )

# @app.get("/categories", tags=["public"])
# def get_categories(db: Session = Depends(get_db)):
#     """
#     Получить список всех доступных категорий новостей.
#     """
#     from sqlalchemy import func

#     categories_list = list(RSS_FEEDS.keys())

#     results = db.query(
#         models.NewsItem.category,
#         func.count(models.NewsItem.id).label('count')
#     ).group_by(models.NewsItem.category).all()
    
#     counts = {cat: 0 for cat in categories_list}
#     for cat, count in results:
#         counts[cat] = count
    
#     return {
#         "categories": categories_list,
#         "counts": counts,
#         "total": len(categories_list)
#     }

# @app.get("/feed/latest", tags=["public"])
# def get_latest_news(
#     limit: int = Query(10, ge=1, le=50, description="Количество новостей")
# ):
#     """
#     Получить самые свежие новости (без пагинации).
    
#     - **limit**: количество новостей (max 50)
#     """
#     return MOCK_NEWS[:limit]

# ============ ВНУТРЕННИЕ ЭНДПОИНТЫ ============

@app.post("/rss/update/{category}")
def update_category(category: str, db: Session = Depends(get_db)):
    """
    Обновить новости из RSS для конкретной категории
    """
    if category not in rss_parser.RSS_FEEDS:
        raise HTTPException(
            status_code=400,
            detail={"error": f"Неизвестная категория: {category}", "code": 400}
        )
    
    # Парсим RSS
    news_items = rss_parser.parse_rss_feed(category)
    
    if not news_items:
        return {
            "category": category,
            "status": "no news found",
            "saved": 0
        }
    
    # Сохраняем в БД
    saved = crud.save_category_news(db, category, news_items)
    
    return {
        "category": category,
        "status": "success",
        "parsed": len(news_items),
        "saved": saved
    }

@app.post("/rss/update-all")
def update_all_categories(db: Session = Depends(get_db)):
    """
    Обновить все категории (может занять некоторое время)
    """
    results = {}
    total_parsed = 0
    total_saved = 0
    
    for category in rss_parser.RSS_FEEDS.keys():
        news_items = rss_parser.parse_rss_feed(category)
        total_parsed += len(news_items)
        
        saved = crud.save_category_news(db, category, news_items)
        total_saved += saved
        
        results[category] = {
            "parsed": len(news_items),
            "saved": saved
        }
        
        time.sleep(1)
    
    return {
        "status": "success",
        "total_parsed": total_parsed,
        "total_saved": total_saved,
        "results": results
    }

# @app.get("/internal/health", tags=["internal"])
# def health_check():
#     """
#     [ВНУТРЕННИЙ] Проверка здоровья сервиса.
    
#     Используется для мониторинга и оркестрации.
#     """
#     return {
#         "status": "healthy",
#         "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
#         "services": {
#             "database": "ok",
#             "rss_fetcher": "ok"
#         },
#         "stats": {
#             "total_news_items": len(MOCK_NEWS),
#             "last_update": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
#         }
#     }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)