"""
SQLAlchemy-модели для User Content Service.
"""

from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from .database import Base


class FavoriteArticle(Base):
    """Избранная статья пользователя."""

    __tablename__ = "favorite_articles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    url = Column(String(2048), nullable=False, index=True)
    title = Column(String(512), nullable=False)
    description = Column(Text, nullable=True)
    url_to_image = Column(String(2048), nullable=True)
    source_name = Column(String(256), nullable=False)
    published_at = Column(DateTime, nullable=False)
    added_at = Column(DateTime, nullable=False)
    note = Column(Text, nullable=True)

    # Один user_id + url — одна запись
    __table_args__ = (
        {"sqlite_autoincrement": True},
    )

    comments = relationship("Comment", back_populates="article", cascade="all, delete-orphan")


class Comment(Base):
    """Комментарий к избранной статье."""

    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    article_id = Column(Integer, ForeignKey("favorite_articles.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False)

    article = relationship("FavoriteArticle", back_populates="comments")
