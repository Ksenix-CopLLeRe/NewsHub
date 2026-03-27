# app/crud.py
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_
from typing import Optional, List, Tuple
from datetime import datetime, timedelta

from app import models, schemas

# ============ CREATE ============
def create_news(db: Session, news: schemas.NewsCreate) -> models.NewsItem:
    """Создать новость"""
    db_news = models.NewsItem(**news.dict())
    db.add(db_news)
    db.commit()
    db.refresh(db_news)
    return db_news

def create_or_update_news(db: Session, news: schemas.NewsCreate) -> Tuple[models.NewsItem, bool]:
    """Создать или обновить новость (по url)"""
    existing = db.query(models.NewsItem).filter(
        models.NewsItem.url == news.url
    ).first()
    
    if existing:
        for key, value in news.dict().items():
            setattr(existing, key, value)
        existing.updated_at = datetime.now()
        db.commit()
        db.refresh(existing)
        return existing, False  # False = обновлено
    else:
        db_news = models.NewsItem(**news.dict())
        db.add(db_news)
        db.commit()
        db.refresh(db_news)
        return db_news, True  # True = создано

# ============ READ ============
def get_news_by_id(db: Session, news_id: int) -> Optional[models.NewsItem]:
    """Получить новость по ID"""
    return db.query(models.NewsItem).filter(models.NewsItem.id == news_id).first()

def get_news_by_url(db: Session, url: str) -> Optional[models.NewsItem]:
    """Получить новость по URL"""
    return db.query(models.NewsItem).filter(models.NewsItem.url == url).first()

def get_news_list(
    db: Session,
    category: Optional[str] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 20
) -> Tuple[List[models.NewsItem], int]:
    """
    Получить список новостей с фильтрацией
    Возвращает (список, общее количество)
    """
    query = db.query(models.NewsItem)
    
    # Фильтр по категории
    if category:
        query = query.filter(models.NewsItem.category == category)
    
    # Поиск по тексту
    if search:
        query = query.filter(
            or_(
                models.NewsItem.title.ilike(f"%{search}%"),
                models.NewsItem.description.ilike(f"%{search}%")
            )
        )
    
    # Общее количество
    total = query.count()
    
    # Пагинация и сортировка
    items = query.order_by(models.NewsItem.published_at.desc())\
                 .offset(skip).limit(limit).all()
    
    return items, total

def get_categories_with_counts(db: Session) -> List[Tuple[str, int]]:
    """Получить список категорий с количеством новостей"""
    results = db.query(
        models.NewsItem.category,
        func.count(models.NewsItem.id).label('count')
    ).group_by(models.NewsItem.category).all()
    
    return [(cat, cnt) for cat, cnt in results]

# ============ UPDATE ============
def update_news(
    db: Session,
    news_id: int,
    news_update: schemas.NewsUpdate
) -> Optional[models.NewsItem]:
    """Обновить новость"""
    db_news = get_news_by_id(db, news_id)
    if not db_news:
        return None
    
    update_data = news_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_news, field, value)
    
    db_news.updated_at = datetime.now()
    db.commit()
    db.refresh(db_news)
    return db_news

# ============ DELETE ============
def delete_news(db: Session, news_id: int) -> bool:
    """Удалить новость"""
    db_news = get_news_by_id(db, news_id)
    if not db_news:
        return False
    
    db.delete(db_news)
    db.commit()
    return True

def delete_old_news(db: Session, days: int = 7) -> int:
    """Удалить новости старше указанного количества дней"""
    cutoff = datetime.now() - timedelta(days=days)
    deleted = db.query(models.NewsItem).filter(
        models.NewsItem.published_at < cutoff
    ).delete()
    db.commit()
    return deleted