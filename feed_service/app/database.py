# app/database.py
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# Получаем URL из переменной окружения
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://feed_user:feed_password@localhost:5432/feed_db"
)

engine = create_engine(
    DATABASE_URL,
    echo=True,  # Логи SQL-запросов
    pool_size=5,  # Размер пула соединений
    max_overflow=10
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()