"""
Асинхронное подключение к PostgreSQL для User Content Service.
"""

import os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

# asyncpg: postgresql+asyncpg://
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://usercontent:usercontent@localhost:5432/usercontent",
)
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(
    DATABASE_URL,
    echo=os.getenv("SQL_ECHO", "").lower() in ("1", "true", "yes"),
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()


async def get_db():
    """Зависимость FastAPI для получения асинхронной сессии БД."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Создаёт таблицы в БД и добавляет минимальные тестовые данные при первом запуске."""
    from datetime import datetime, timezone

    from . import models  # noqa: F401
    from .models import Comment, FavoriteArticle

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Минимальные тестовые данные, если БД пуста
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select, func

        result = await session.execute(select(func.count()).select_from(FavoriteArticle))
        if (result.scalar() or 0) == 0:
            now = datetime.now(timezone.utc)
            base = datetime(2025, 3, 1, 18, 0, 0, tzinfo=timezone.utc)
            fav1 = FavoriteArticle(
                user_id=123,
                url="https://lenta.ru/news/2025/03/01/example1/",
                title="Новости дня: главное",
                description="Краткий обзор событий.",
                url_to_image="https://example.com/img1.jpg",
                source_name="Lenta.ru",
                published_at=base,
                added_at=base,
                note="Прочитать позже",
            )
            fav2 = FavoriteArticle(
                user_id=123,
                url="https://lenta.ru/news/2025/03/01/example2/",
                title="Экономика: курс валют",
                description="Обзор валютного рынка.",
                url_to_image="https://example.com/img2.jpg",
                source_name="Lenta.ru",
                published_at=base,
                added_at=base,
                note=None,
            )
            session.add_all([fav1, fav2])
            await session.flush()
            com = Comment(article_id=fav1.id, user_id=123, text="Интересная статья!", created_at=now)
            session.add(com)
            await session.commit()
