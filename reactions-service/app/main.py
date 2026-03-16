from fastapi import FastAPI, Depends, HTTPException, Header, Query
from sqlalchemy.orm import Session
from typing import Optional
from urllib.parse import unquote

from app import schemas, models, crud
from app.database import engine, get_db

# Создаем таблицы (только для разработки!)
# models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Reactions & Counters Service API",
    description="Микросервис для управления эмоциональными реакциями пользователей на новости",
    version="1.0.0"
)

@app.get("/")
def root():
    return {
        "message": "Reactions Service API",
        "status": "running with PostgreSQL",
        "docs": "/docs"
    }

@app.post("/reactions", status_code=201)
def create_or_update_reaction(
    reaction: schemas.ReactionCreate,
    db: Session = Depends(get_db)
):
    """
    Добавить или обновить реакцию (toggle-логика)
    """
    # Ищем существующую реакцию
    existing = crud.get_user_reaction(db, reaction.user_id, reaction.news_id)
    
    # Если реакции нет - создаем
    if not existing:
        new_reaction = crud.create_reaction(db, reaction)
        return {
            "success": True,
            "action": "created",
            "reaction": schemas.ReactionResponse.model_validate(new_reaction)
        }
    
    # Если есть и тип тот же - удаляем
    if existing.reaction_type.value == reaction.reaction_type:
        crud.delete_reaction(db, existing)
        return {
            "success": True,
            "action": "deleted",
            "reaction": schemas.ReactionResponse.model_validate(existing)
        }
    
    # Если тип другой - обновляем
    update_data = schemas.ReactionUpdate(reaction_type=reaction.reaction_type)
    updated = crud.update_reaction(db, existing, update_data)
    return {
        "success": True,
        "action": "updated",
        "reaction": schemas.ReactionResponse.model_validate(updated)
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