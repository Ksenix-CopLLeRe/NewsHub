import pytest
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from testcontainers.postgres import PostgresContainer

from app.main import app
from app.database import Base, get_db
from app import crud, schemas


@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg


@pytest.fixture(scope="session")
def test_engine(postgres_container):
    engine = create_engine(postgres_container.get_connection_url())
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def TestSession(test_engine):
    return sessionmaker(bind=test_engine)


@pytest.fixture
def db_session(TestSession):
    session = TestSession()
    yield session
    session.close()


@pytest.fixture(autouse=True)
def clean_tables(test_engine):
    yield
    with test_engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE news RESTART IDENTITY CASCADE"))


@pytest.fixture
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    @asynccontextmanager
    async def noop_lifespan(app):
        yield

    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = noop_lifespan

    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.router.lifespan_context = original_lifespan
        app.dependency_overrides.clear()


@pytest.fixture
def make_news(db_session):
    def _make(
        url="https://example.com/news/1",
        title="Test Title",
        description="Test description",
        category="россия",
        published_at=None,
        source_name="Test Source",
        image_url=None,
    ):
        if published_at is None:
            published_at = datetime.now(timezone.utc)
        news = schemas.NewsCreate(
            url=url,
            title=title,
            description=description,
            category=category,
            published_at=published_at,
            source_name=source_name,
            image_url=image_url,
        )
        item, _ = crud.create_or_update_news(db_session, news)
        db_session.refresh(item)
        return item

    return _make
