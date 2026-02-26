"""
Мок-сервер для Feed Service API.
Запускается отдельно от основного монолита для тестирования микросервисной архитектуры.
"""

from fastapi import FastAPI, Query, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
from datetime import datetime, timedelta
import uvicorn
import random
import secrets

# Секретный токен для внутренних эндпоинтов (в реальности хранится в .env)
INTERNAL_TOKEN = "mock-internal-token-123456"

# Создаем приложение
app = FastAPI(
    title="Feed Service Mock",
    description="Мок-сервер для тестирования Feed Service API",
    version="1.0.0"
)

# Настройка CORS для тестирования из браузера
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============ МОК-ДАННЫЕ ============

# Категории новостей
CATEGORIES = ["россия", "мир", "экономика", "наука", "спорт", "культура"]

# Функция для генерации мок-новостей
def generate_mock_news(category: str = None, count: int = 20) -> List[dict]:
    """Генерирует тестовые новости"""
    news_items = []
    
    # Шаблоны для генерации
    titles = {
        "россия": [
            "Путин подписал новый закон о развитии экономики",
            "В Москве открылся международный форум",
            "Госдума приняла важный законопроект",
            "Российские ученые совершили прорыв в физике",
            "Новые меры поддержки семей в России"
        ],
        "мир": [
            "Трамп объявил о новых выборах в США",
            "В Европе обсуждают климатические изменения",
            "Китай запустил новую космическую станцию",
            "Переговоры по Украине в Стамбуле",
            "Саммит G7 начался в Германии"
        ],
        "экономика": [
            "Курс доллара упал до минимума",
            "Нефть подорожала на 5% за день",
            "Инфляция в России замедлилась",
            "Новые санкции против России",
            "Биткоин обновил исторический максимум"
        ],
        "наука": [
            "Ученые нашли лекарство от старения",
            "NASA запустило миссию к Марсу",
            "Российские физики получили Нобелевскую премию",
            "Открыта новая планета в зоне обитаемости",
            "Создан первый квантовый компьютер"
        ],
        "спорт": [
            "Сборная России выиграла золото",
            "Олимпиада в Париже открылась",
            "Российский футболист перешел в Реал",
            "Чемпионат мира по хоккею стартовал",
            "Боксер Поветкин завершил карьеру"
        ],
        "культура": [
            "Новый фильм Бондарчука вышел в прокат",
            "Эрмитаж открыл выставку импрессионистов",
            "Умер известный актер театра и кино",
            "Концерт группы Руки Вверх! собрал стадион",
            "Книга Пелевина стала бестселлером"
        ]
    }
    
    descriptions = [
        "Эксперты отмечают, что это решение повлияет на...",
        "Подробности этого события обсуждаются в мировых СМИ...",
        "Аналитики прогнозируют дальнейшее развитие ситуации...",
        "Это событие может кардинально изменить...",
        "По словам очевидцев, происходящее вызывает..."
    ]
    
    # Генерируем новости
    for i in range(count):
        # Выбираем категорию
        news_category = category if category else random.choice(CATEGORIES)
        
        # Генерируем дату публикации (от текущей до 7 дней назад)
        days_ago = random.randint(0, 7)
        hours_ago = random.randint(0, 23)
        minutes_ago = random.randint(0, 59)
        published_at = datetime.now() - timedelta(
            days=days_ago, 
            hours=hours_ago, 
            minutes=minutes_ago
        )
        
        # Формируем новость
        news_item = {
            "url": f"https://lenta.ru/news/2025/03/{random.randint(1, 28):02d}/example{i}/",
            "title": random.choice(titles.get(news_category, titles["россия"])),
            "description": random.choice(descriptions),
            "image_url": f"https://icdn.lenta.ru/images/2025/03/0{random.randint(1, 9)}/{random.randint(100, 999)}.jpg",
            "source_name": "Lenta.ru",
            "published_at": published_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "category": news_category
        }
        news_items.append(news_item)
    
    # Сортируем по дате (сначала свежие)
    news_items.sort(key=lambda x: x["published_at"], reverse=True)
    return news_items

# Генерируем основную базу новостей (100 новостей)
MOCK_NEWS = generate_mock_news(count=100)

# ============ ПУБЛИЧНЫЕ ЭНДПОИНТЫ ============

@app.get("/feed", tags=["public"])
async def get_feed(
    category: Optional[str] = Query(None, description="Фильтр по категории"),
    q: Optional[str] = Query(None, description="Поисковый запрос"),
    page: int = Query(1, ge=1, description="Номер страницы"),
    size: int = Query(20, ge=1, le=100, description="Размер страницы")
):
    """
    Получить ленту новостей с поддержкой фильтрации, поиска и пагинации.
    
    - **category**: фильтр по категории
    - **q**: поиск по заголовку и описанию
    - **page**: номер страницы (начиная с 1)
    - **size**: количество элементов на странице (max 100)
    """
    # Фильтруем по категории
    filtered_news = MOCK_NEWS
    if category:
        filtered_news = [n for n in filtered_news if n["category"] == category]
    
    # Поиск по тексту
    if q:
        q_lower = q.lower()
        filtered_news = [
            n for n in filtered_news 
            if q_lower in n["title"].lower() or q_lower in n["description"].lower()
        ]
    
    # Пагинация
    total = len(filtered_news)
    start = (page - 1) * size
    end = start + size
    paginated_news = filtered_news[start:end]
    
    return {
        "items": paginated_news,
        "total": total,
        "page": page,
        "size": size
    }

@app.get("/news/{url:path}", tags=["public"])
async def get_news_by_url(url: str):
    """
    Получить конкретную новость по URL.
    
    - **url**: URL статьи (URL-encoded)
    """
    # Ищем новость по URL
    for news in MOCK_NEWS:
        if news["url"] == url:
            return news
    
    raise HTTPException(
        status_code=404,
        detail={
            "error": f"Новость с URL {url} не найдена",
            "code": 404
        }
    )

@app.get("/categories", tags=["public"])
async def get_categories():
    """
    Получить список всех доступных категорий новостей.
    """
    return {
        "categories": CATEGORIES,
        "total": len(CATEGORIES)
    }

@app.get("/feed/latest", tags=["public"])
async def get_latest_news(
    limit: int = Query(10, ge=1, le=50, description="Количество новостей")
):
    """
    Получить самые свежие новости (без пагинации).
    
    - **limit**: количество новостей (max 50)
    """
    return MOCK_NEWS[:limit]

# ============ ВНУТРЕННИЕ ЭНДПОИНТЫ ============

@app.post("/internal/feed/update-category", tags=["internal"])
async def update_category(
    request: dict,
    x_internal_token: str = Header(..., description="Внутренний токен для аутентификации")
):
    """
    [ВНУТРЕННИЙ] Обновить новости в конкретной категории.
    
    Вызывается только другими сервисами или по расписанию.
    Требует внутренний токен аутентификации.
    """
    # Проверка токена
    if x_internal_token != INTERNAL_TOKEN:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "Неверный внутренний токен",
                "code": 401
            }
        )
    
    category = request.get("category")
    force = request.get("force", False)
    
    if category not in CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail={
                "error": f"Категория '{category}' не найдена",
                "code": 400,
                "details": {
                    "category": [f"Допустимые значения: {', '.join(CATEGORIES)}"]
                }
            }
        )
    
    # Симулируем обновление RSS
    new_count = random.randint(5, 20)
    updated_count = random.randint(0, 10)
    
    return {
        "category": category,
        "articles_fetched": new_count + updated_count,
        "new_articles": new_count,
        "updated_articles": updated_count,
        "duration_ms": random.randint(1000, 5000)
    }

@app.post("/internal/feed/update-all", tags=["internal"])
async def update_all_categories(
    request: dict = None,
    x_internal_token: str = Header(..., description="Внутренний токен для аутентификации")
):
    """
    [ВНУТРЕННИЙ] Обновить все категории новостей.
    
    Вызывается по расписанию (например, каждые 5 минут).
    Требует внутренний токен аутентификации.
    """
    # Проверка токена
    if x_internal_token != INTERNAL_TOKEN:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "Неверный внутренний токен",
                "code": 401
            }
        )
    
    force = request.get("force", False) if request else False
    
    # Симулируем обновление всех категорий
    results = {}
    total_duration = 0
    
    for category in CATEGORIES:
        new = random.randint(5, 15)
        updated = random.randint(0, 8)
        total_in_category = random.randint(50, 200)
        duration = random.randint(500, 3000)
        
        results[category] = {
            "new": new,
            "updated": updated,
            "total": total_in_category
        }
        total_duration += duration
    
    return {
        "results": results,
        "total_duration_ms": total_duration
    }

@app.get("/internal/health", tags=["internal"])
async def health_check():
    """
    [ВНУТРЕННИЙ] Проверка здоровья сервиса.
    
    Используется для мониторинга и оркестрации.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "services": {
            "database": "ok",
            "rss_fetcher": "ok"
        },
        "stats": {
            "total_news_items": len(MOCK_NEWS),
            "last_update": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        }
    }

# ============ ЗАПУСК ============

if __name__ == "__main__":
    print("=" * 50)
    print("🚀 Feed Service Mock Server")
    print("=" * 50)
    print(f"\n📡 Публичные эндпоинты:")
    print(f"  GET  http://localhost:8000/feed")
    print(f"  GET  http://localhost:8000/news/{'{url}'}")
    print(f"  GET  http://localhost:8000/categories")
    print(f"  GET  http://localhost:8000/feed/latest")
    print(f"\n🔒 Внутренние эндпоинты (требуют токен):")
    print(f"  POST http://localhost:8000/internal/feed/update-category")
    print(f"  POST http://localhost:8000/internal/feed/update-all")
    print(f"  GET  http://localhost:8000/internal/health")
    print(f"\n🔑 Internal Token: {INTERNAL_TOKEN}")
    print(f"\n📊 Мок-данных: {len(MOCK_NEWS)} новостей")
    print(f"\n🚀 Запуск сервера на http://localhost:8000")
    print(f"📚 Документация: http://localhost:8000/docs")
    print("=" * 50)
    
    uvicorn.run(app, host="0.0.0.0", port=8000)