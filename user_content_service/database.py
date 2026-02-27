"""
Подключение к SQLite и фабрика сессий для User Content Service.
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# По умолчанию: sqlite в текущей директории
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./user_content.db",
)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    echo=os.getenv("SQL_ECHO", "").lower() in ("1", "true", "yes"),
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Зависимость FastAPI для получения сессии БД."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Создаёт таблицы в БД."""
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
