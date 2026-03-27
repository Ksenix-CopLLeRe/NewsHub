from fastapi import FastAPI, Depends, HTTPException, Header, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional
from urllib.parse import unquote
from datetime import datetime
import httpx
import asyncio
import time
from app import schemas, models, crud
from app.database import engine, get_db
from app.schemas import ReactionType

# Создаем таблицы (только для разработки!)
# models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Reactions & Counters Service API",
    description="Микросервис для управления эмоциональными реакциями пользователей на новости",
    version="1.0.0"
)

# ========== Функция для фонового логирования ==========

def write_log(message: str):
    """
    Фоновая задача — запись в лог-файл.
    Выполняется после ответа клиенту.
    """
    time.sleep(0.3)  # Имитация работы с диском
    
    with open("reactions.log", "a", encoding="utf-8") as f:
        f.write(f"{datetime.now().isoformat()} - {message}\n")

# ========== АСИНХРОННЫЕ ЭНДПОИНТЫ ==========

# --- Задание 1: Асинхронный запрос к внешнему API ---
@app.get("/external/news")
async def get_external_news(limit: int = Query(5, ge=1, le=20)):
    """
    Асинхронно получает тестовые новости из внешнего API (JSONPlaceholder)
    """
    async with httpx.AsyncClient() as client:
        response = await client.get("https://jsonplaceholder.typicode.com/posts")
        posts = response.json()
        
        news = [
            {
                "id": post["id"],
                "title": post["title"],
                "body": post["body"],
                "source": "jsonplaceholder"
            }
            for post in posts[:limit]
        ]
        
    return {
        "news": news,
        "total": len(news),
        "source": "external API"
    }

# --- Задание 2: Параллельные запросы с asyncio.gather() ---
@app.get("/external/combined")
async def get_combined_data():
    """
    Параллельно получает данные из нескольких источников
    """
    async with httpx.AsyncClient() as client:
        posts_task = client.get("https://jsonplaceholder.typicode.com/posts")
        users_task = client.get("https://jsonplaceholder.typicode.com/users")
        comments_task = client.get("https://jsonplaceholder.typicode.com/comments")
        
        posts_resp, users_resp, comments_resp = await asyncio.gather(
            posts_task, users_task, comments_task
        )
        
        return {
            "posts": posts_resp.json()[:3],
            "users": users_resp.json()[:3],
            "comments": comments_resp.json()[:3],
            "message": "Данные получены параллельно!"
        }

# --- Задание 3: POST /reactions с фоновой задачей ---
@app.post("/reactions", status_code=201)
async def create_or_update_reaction(
    reaction: schemas.ReactionCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Добавить или обновить реакцию (toggle-логика)
    + фоновое логирование
    """
    # Ищем существующую реакцию
    existing = crud.get_user_reaction(db, reaction.user_id, reaction.news_id)
    
    # Если реакции нет - создаем
    if not existing:
        new_reaction = crud.create_reaction(db, reaction)
        
        background_tasks.add_task(
            write_log,
            f"REACTION CREATED: user_id={reaction.user_id}, news_id={reaction.news_id}, type={reaction.reaction_type}"
        )
        
        return {
            "success": True,
            "action": "created",
            "reaction": schemas.ReactionResponse.model_validate(new_reaction)
        }
    
    # Если есть и тип тот же - удаляем
    if existing.reaction_type.value == reaction.reaction_type:
        crud.delete_reaction(db, existing)
        
        background_tasks.add_task(
            write_log,
            f"REACTION DELETED: user_id={reaction.user_id}, news_id={reaction.news_id}, type={reaction.reaction_type}"
        )
        
        return {
            "success": True,
            "action": "deleted",
            "reaction": schemas.ReactionResponse.model_validate(existing)
        }
    
    # Если тип другой - обновляем
    update_data = schemas.ReactionUpdate(reaction_type=reaction.reaction_type)
    updated = crud.update_reaction(db, existing, update_data)
    
    background_tasks.add_task(
        write_log,
        f"REACTION UPDATED: user_id={reaction.user_id}, news_id={reaction.news_id}, old_type={existing.reaction_type.value}, new_type={reaction.reaction_type}"
    )
    
    return {
        "success": True,
        "action": "updated",
        "reaction": schemas.ReactionResponse.model_validate(updated)
    }

# --- Задание 4: Эндпоинт с фоновой задачей + асинхронный запрос ---
@app.get("/external/combined")
async def get_combined_data():
    """
    Параллельно получает данные из нескольких источников
    """
    # Можно увеличить время ожидания, чтобы реже ловить таймаут
    timeout = httpx.Timeout(10.0)  # или 20.0, под себя

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            posts_task = client.get("https://jsonplaceholder.typicode.com/posts")
            users_task = client.get("https://jsonplaceholder.typicode.com/users")
            comments_task = client.get("https://jsonplaceholder.typicode.com/comments")

            posts_resp, users_resp, comments_resp = await asyncio.gather(
                posts_task, users_task, comments_task
            )

            posts_resp.raise_for_status()
            users_resp.raise_for_status()
            comments_resp.raise_for_status()

        except httpx.TimeoutException as e:
            # Внешний сервис тупит — отдаём 502, а не 500
            raise HTTPException(status_code=502, detail=f"External API timeout: {e}")
        except httpx.HTTPError as e:
            # Любая другая сетевая ошибка
            raise HTTPException(status_code=502, detail=f"External API error: {e}")

    return {
        "posts": posts_resp.json()[:3],
        "users": users_resp.json()[:3],
        "comments": comments_resp.json()[:3],
        "message": "Данные получены параллельно!"
    }

# --- Задание 5: Генерация отчёта с отслеживанием статуса ---
reports_status = {}

@app.post("/reports/generate")
async def generate_report(
    background_tasks: BackgroundTasks,
    news_id: Optional[str] = None
):
    """Запускает фоновую генерацию отчёта"""
    report_id = int(time.time() * 1000)
    reports_status[report_id] = {
        "status": "pending",
        "result": None,
        "created_at": datetime.now().isoformat()
    }
    
    background_tasks.add_task(
        generate_report_background,
        report_id=report_id,
        news_id=news_id
    )
    
    return {
        "report_id": report_id,
        "status": "pending",
        "message": "Отчёт генерируется. Проверьте статус по /reports/status/{report_id}"
    }

def generate_report_background(report_id: int, news_id: Optional[str] = None):
    """Фоновая задача генерации отчёта"""
    try:
        time.sleep(3)
        
        reports_status[report_id]["status"] = "completed"
        reports_status[report_id]["result"] = {
            "report_id": report_id,
            "news_id": news_id if news_id else "all",
            "message": "Отчёт сгенерирован успешно",
            "data": "Здесь могли быть ваши данные"
        }
        reports_status[report_id]["completed_at"] = datetime.now().isoformat()
        
    except Exception as e:
        reports_status[report_id]["status"] = "failed"
        reports_status[report_id]["error"] = str(e)

@app.get("/reports/status/{report_id}")
async def get_report_status(report_id: int):
    """Проверить статус генерации отчёта"""
    if report_id not in reports_status:
        raise HTTPException(status_code=404, detail="Report not found")
    
    return reports_status[report_id]

# ========== СИНХРОННЫЕ ЭНДПОИНТЫ ==========

@app.get("/")
def root():
    return {
        "message": "Reactions Service API",
        "status": "running with PostgreSQL",
        "docs": "/docs"
    }

@app.delete("/reactions/{reaction_id}")
def delete_reaction(
    reaction_id: int,
    x_user_id: int = Header(...),
    db: Session = Depends(get_db)
):
    """Удалить реакцию по ID (только для владельца)"""
    reaction = crud.get_reaction(db, reaction_id)
    
    if not reaction:
        raise HTTPException(status_code=404, detail="Reaction not found")
    
    if reaction.user_id != x_user_id:
        raise HTTPException(status_code=403, detail="Cannot delete another user's reaction")
    
    crud.delete_reaction(db, reaction)
    return {"success": True, "message": "Reaction deleted successfully"}

@app.get("/reactions/news/{news_id:path}", response_model=schemas.ReactionListResponse)
def get_reactions_by_news(
    news_id: str,
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Получить список реакций на новость с пагинацией"""
    skip = (page - 1) * size
    reactions = crud.get_reactions_by_news(db, news_id, skip=skip, limit=size)
    total = crud.count_reactions_by_news(db, news_id)
    
    return schemas.ReactionListResponse(
        items=[schemas.ReactionResponse.model_validate(r) for r in reactions],
        total=total,
        page=page,
        size=size
    )

@app.get("/reactions/counts/{news_id:path}", response_model=schemas.ReactionCountsResponse)
def get_reaction_counts(
    news_id: str,
    db: Session = Depends(get_db)
):
    """Получить агрегированные счетчики реакций по новости"""
    counts, total = crud.get_reaction_counts(db, news_id)
    
    return schemas.ReactionCountsResponse(
        news_id=news_id,
        counts=counts,
        total=total
    )