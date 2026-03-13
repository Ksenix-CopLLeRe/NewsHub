from sqlalchemy.orm import Session
from app import models, schemas
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def save_news_to_db(db: Session, news_item: schemas.NewsCreate) -> models.NewsItem:
    """
    Сохраняет одну новость в БД, если её там ещё нет
    """
    # Проверяем, есть ли уже новость с таким URL
    existing = db.query(models.NewsItem).filter(
        models.NewsItem.url == news_item.url
    ).first()
    
    if existing:
        # Обновляем существующую запись
        for key, value in news_item.dict().items():
            setattr(existing, key, value)
        db.commit()
        db.refresh(existing)
        logger.debug(f"Обновлена новость: {news_item.title[:50]}...")
        return existing
    else:
        # Создаём новую запись
        db_news = models.NewsItem(**news_item.dict())
        db.add(db_news)
        db.commit()
        db.refresh(db_news)
        logger.debug(f"Добавлена новая новость: {news_item.title[:50]}...")
        return db_news

def save_category_news(db: Session, category: str, news_items: list) -> int:
    """
    Сохраняет список новостей категории в БД
    """
    saved_count = 0
    for item in news_items:
        try:
            # Создаем Pydantic модель из словаря
            news_create = schemas.NewsCreate(**item)
            save_news_to_db(db, news_create)
            saved_count += 1
        except Exception as e:
            logger.error(f"Ошибка сохранения новости: {e}")
            continue
    
    logger.info(f"Сохранено {saved_count} новостей для категории '{category}'")
    return saved_count

def get_old_news_count(db: Session, hours: int = 24) -> int:
    """
    Возвращает количество новостей старше указанного количества часов
    """
    from sqlalchemy import func
    from datetime import timedelta
    
    cutoff = datetime.now() - timedelta(hours=hours)
    count = db.query(models.NewsItem).filter(
        models.NewsItem.published_at < cutoff
    ).count()
    
    return count

def clean_old_news(db: Session, days: int = 7) -> int:
    """
    Удаляет новости старше указанного количества дней
    """
    from datetime import timedelta
    
    cutoff = datetime.now() - timedelta(days=days)
    deleted = db.query(models.NewsItem).filter(
        models.NewsItem.published_at < cutoff
    ).delete(synchronize_session=False)
    
    db.commit()
    logger.info(f"Удалено {deleted} старых новостей (старше {days} дней)")
    return deleted