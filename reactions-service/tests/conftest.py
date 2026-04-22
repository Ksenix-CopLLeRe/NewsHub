import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from testcontainers.postgres import PostgresContainer

# Import app after setting up fixtures — engine is lazy so import won't fail
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
        conn.execute(text("TRUNCATE TABLE reactions RESTART IDENTITY"))


@pytest.fixture
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def make_reaction(db_session):
    def _make(user_id=1, news_id="https://example.com/news/1", reaction_type="important"):
        data = schemas.ReactionCreate(
            user_id=user_id,
            news_id=news_id,
            reaction_type=reaction_type,
        )
        return crud.create_reaction(db_session, data)

    return _make
