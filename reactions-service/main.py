"""
Микросервис для управления реакциями на новости.
Реализует API, описанное в openapi/reactions-service.yaml
"""

from fastapi import FastAPI, HTTPException, Query, Header
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime
from enum import Enum

# ----- Перечисление типов реакций (как в спецификации) -----
class ReactionType(str, Enum):
    important = "important"
    interesting = "interesting"
    shocking = "shocking"
    useful = "useful"
    liked = "liked"

# ----- Модели данных Pydantic (соответствуют OpenAPI schemas) -----
class ReactionBase(BaseModel):
    """Базовая модель реакции"""
    user_id: int
    news_id: str
    reaction_type: ReactionType

class ReactionCreate(ReactionBase):
    """Модель для создания реакции (без ID)"""
    pass

class Reaction(ReactionBase):
    """Полная модель реакции (с ID и датой)"""
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class ReactionCounts(BaseModel):
    """Агрегированные счетчики (как в спецификации)"""
    news_id: str
    counts: Dict[ReactionType, int]
    total: int

class ReactionList(BaseModel):
    """Список реакций с пагинацией"""
    items: List[Reaction]
    total: int
    page: int
    size: int

# ----- Создаем FastAPI приложение -----
app = FastAPI(
    title="Reactions & Counters Service API",
    description="Микросервис для управления эмоциональными реакциями пользователей на новости",
    version="1.0.0"
)

# ----- "База данных" в памяти (для заглушки) -----
# В реальном проекте здесь была бы PostgreSQL

# Хранилище реакций: {id: Reaction}
reactions_db = {}

# Индексы для быстрого поиска:
# news_index[news_id][user_id] = reaction_id
news_index = {}

# Счетчик для следующего ID
next_id = 1

# Заполняем тестовыми данными (как в примерах из спецификации)
test_reactions = [
    {"user_id": 123, "news_id": "https://lenta.ru/news/2025/03/01/example/", "reaction_type": "important"},
    {"user_id": 456, "news_id": "https://lenta.ru/news/2025/03/01/example/", "reaction_type": "interesting"},
    {"user_id": 789, "news_id": "https://lenta.ru/news/2025/03/01/example/", "reaction_type": "important"},
]

for test in test_reactions:
    reaction = Reaction(
        id=next_id,
        created_at=datetime.now(),
        **test
    )
    reactions_db[next_id] = reaction
    
    # Индексируем
    if reaction.news_id not in news_index:
        news_index[reaction.news_id] = {}
    news_index[reaction.news_id][reaction.user_id] = reaction.id
    
    next_id += 1

# ----- Эндпоинты API (соответствуют спецификации) -----

@app.get("/")
def root():
    """Корневой эндпоинт для проверки"""
    return {
        "message": "Reactions Service API",
        "status": "running",
        "docs": "/docs",
        "endpoints": [
            "POST /reactions",
            "DELETE /reactions/{reactionId}",
            "GET /reactions/news/{newsId}",
            "GET /reactions/counts/{newsId}"
        ]
    }


@app.post("/reactions", response_model=dict, status_code=201)
def create_or_update_reaction(reaction: ReactionCreate):
    """
    Добавить или обновить реакцию (toggle-логика)
    
    - Если реакции нет → создает (201)
    - Если есть и тип тот же → удаляет (200)
    - Если есть и тип другой → обновляет (200)
    """
    global next_id
    
    news_id = reaction.news_id
    user_id = reaction.user_id
    
    # Проверяем, есть ли уже реакция от этого пользователя на эту новость
    existing_reaction_id = None
    if news_id in news_index and user_id in news_index[news_id]:
        existing_reaction_id = news_index[news_id][user_id]
    
    # Случай 1: Реакции нет → создаем
    if existing_reaction_id is None:
        new_reaction = Reaction(
            id=next_id,
            created_at=datetime.now(),
            **reaction.dict()
        )
        
        reactions_db[next_id] = new_reaction
        
        # Индексируем
        if news_id not in news_index:
            news_index[news_id] = {}
        news_index[news_id][user_id] = next_id
        
        next_id += 1
        
        return {
            "success": True,
            "action": "created",
            "reaction": new_reaction.dict()
        }
    
    # Случай 2: Реакция есть
    existing = reactions_db[existing_reaction_id]
    
    # Если тот же тип → удаляем (toggle)
    if existing.reaction_type == reaction.reaction_type:
        del reactions_db[existing_reaction_id]
        del news_index[news_id][user_id]
        
        return {
            "success": True,
            "action": "deleted",
            "reaction": existing.dict()
        }
    
    # Если другой тип → обновляем
    existing.reaction_type = reaction.reaction_type
    # existing.created_at не меняем (дата первой реакции)
    
    return {
        "success": True,
        "action": "updated",
        "reaction": existing.dict()
    }


@app.delete("/reactions/{reaction_id}")
def delete_reaction(reaction_id: int, x_user_id: int = Header(...)):
    """
    Удалить реакцию по ID (только для владельца)
    """
    if reaction_id not in reactions_db:
        raise HTTPException(status_code=404, detail="Reaction not found")
    
    reaction = reactions_db[reaction_id]
    
    # Проверяем, что пользователь удаляет свою реакцию
    if reaction.user_id != x_user_id:
        raise HTTPException(status_code=403, detail="Cannot delete another user's reaction")
    
    # Удаляем из индексов
    if reaction.news_id in news_index and reaction.user_id in news_index[reaction.news_id]:
        del news_index[reaction.news_id][reaction.user_id]
    
    # Удаляем из базы
    del reactions_db[reaction_id]
    
    return {"success": True, "message": "Reaction deleted successfully"}


@app.get("/reactions/news/{news_id}", response_model=ReactionList)
def get_reactions_by_news(
    news_id: str,
    page: int = Query(1, ge=1, description="Номер страницы"),
    size: int = Query(10, ge=1, le=100, description="Элементов на странице")
):
    """
    Получить все реакции на конкретную новость (с пагинацией)
    """
    # Собираем все реакции для этой новости
    news_reactions = []
    if news_id in news_index:
        for user_id, reaction_id in news_index[news_id].items():
            news_reactions.append(reactions_db[reaction_id])
    
    total = len(news_reactions)
    
    # Пагинация
    start = (page - 1) * size
    end = start + size
    paginated = news_reactions[start:end]
    
    return ReactionList(
        items=paginated,
        total=total,
        page=page,
        size=size
    )


@app.get("/reactions/counts/{news_id}", response_model=ReactionCounts)
def get_reaction_counts(news_id: str):
    """
    Получить агрегированные счетчики реакций для новости
    """
    counts = {
        ReactionType.important: 0,
        ReactionType.interesting: 0,
        ReactionType.shocking: 0,
        ReactionType.useful: 0,
        ReactionType.liked: 0
    }
    
    total = 0
    
    if news_id in news_index:
        for user_id, reaction_id in news_index[news_id].items():
            reaction = reactions_db[reaction_id]
            counts[reaction.reaction_type] += 1
            total += 1
    
    return ReactionCounts(
        news_id=news_id,
        counts=counts,
        total=total
    )