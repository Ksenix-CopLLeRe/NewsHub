import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from sqlalchemy.pool import NullPool

from user_content_service.database import Base, get_db
from user_content_service.main import app


@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg


@pytest.fixture(scope="session")
def sync_db_url(postgres_container):
    return postgres_container.get_connection_url()


@pytest.fixture(scope="session")
def async_db_url(sync_db_url):
    # testcontainers returns postgresql+psycopg2://..., replace driver with asyncpg
    return sync_db_url.replace("psycopg2", "asyncpg")


@pytest.fixture(scope="session")
def sync_engine(sync_db_url):
    engine = create_engine(sync_db_url)
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def test_async_engine(async_db_url, sync_engine):
    # NullPool: each request gets a fresh connection — avoids asyncpg event-loop binding issues
    engine = create_async_engine(async_db_url, poolclass=NullPool)
    yield engine
    engine.sync_engine.dispose()


@pytest.fixture(scope="session")
def AsyncTestSession(test_async_engine):
    return async_sessionmaker(
        test_async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


@pytest.fixture(autouse=True)
def clean_tables(sync_engine):
    yield
    with sync_engine.begin() as conn:
        conn.execute(text("DELETE FROM comments"))
        conn.execute(text("DELETE FROM favorite_articles"))


@pytest.fixture
def client(AsyncTestSession):
    async def override_get_db():
        async with AsyncTestSession() as session:
            yield session

    # Bypass startup (which inserts seed data into an empty DB)
    original_startup = app.router.on_startup.copy()
    app.router.on_startup.clear()
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.router.on_startup.clear()
        app.router.on_startup.extend(original_startup)
        app.dependency_overrides.clear()


# ---------- helpers ----------

@pytest.fixture
def make_favorite(client):
    def _make(
        user_id=1,
        url="https://example.com/news/1",
        title="Test Article",
        description="Test description",
        source_name="Test Source",
        published_at="2026-04-21T12:00:00Z",
    ):
        payload = {
            "user_id": user_id,
            "url": url,
            "title": title,
            "description": description,
            "source_name": source_name,
            "published_at": published_at,
        }
        client.post("/favorites/toggle", json=payload)
        check = client.get(f"/favorites/check/{url}?user_id={user_id}")
        return check.json()  # {"is_favorite": True, "article_id": N}

    return _make


@pytest.fixture
def make_comment(client):
    def _make(article_id, user_id=1, text="Test comment"):
        response = client.post(
            f"/favorites/{article_id}/comments",
            json={"user_id": user_id, "text": text},
        )
        assert response.status_code == 201
        return response.json()["comment"]

    return _make
