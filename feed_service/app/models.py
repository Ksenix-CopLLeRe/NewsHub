# app/models.py
from sqlalchemy import Column, Integer, String, DateTime, Text, Index
from sqlalchemy.sql import func
from app.database import Base

class NewsItem(Base):
    __tablename__ = "news"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String(500), unique=True, nullable=False, index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    image_url = Column(String(500), nullable=True)
    source_name = Column(String(100), nullable=False, default="Lenta.ru")
    published_at = Column(DateTime(timezone=True), nullable=False)
    category = Column(String(50), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Составной индекс для поиска
    __table_args__ = (
        Index('ix_news_category_published', 'category', 'published_at'),
    )