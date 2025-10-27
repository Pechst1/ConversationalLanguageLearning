"""Pytest fixtures for API tests."""

import asyncio
import os
from collections.abc import AsyncGenerator, Generator

os.environ.setdefault("SECRET_KEY", "test-secret-key")

import pytest
try:  # pragma: no cover - optional dependency
    import pytest_asyncio
except ImportError:  # pragma: no cover
    pytest_asyncio = None  # type: ignore[assignment]
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.db import models  # noqa: F401  # Imported for side effects
from app.db.models.achievement import Achievement, UserAchievement
from app.db.base import Base
from app.db.models import User, VocabularyWord
from app.db.models.analytics import AnalyticsSnapshot
from app.db.models.progress import ReviewLog, UserVocabularyProgress
from app.db.models.session import ConversationMessage, LearningSession, WordInteraction
from app.main import create_app
from app.utils.cache import cache_backend


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:  # pragma: no cover - placeholder for async tests
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def db_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[
            User.__table__,
            Achievement.__table__,
            UserAchievement.__table__,
            AnalyticsSnapshot.__table__,
            VocabularyWord.__table__,
            UserVocabularyProgress.__table__,
            ReviewLog.__table__,
            LearningSession.__table__,
            ConversationMessage.__table__,
            WordInteraction.__table__,
        ],
    )
    try:
        yield engine
    finally:
        Base.metadata.drop_all(
            bind=engine,
            tables=[
                WordInteraction.__table__,
                ConversationMessage.__table__,
                LearningSession.__table__,
                ReviewLog.__table__,
                UserVocabularyProgress.__table__,
                AnalyticsSnapshot.__table__,
                VocabularyWord.__table__,
                UserAchievement.__table__,
                Achievement.__table__,
                User.__table__,
            ],
        )


@pytest.fixture()
def db_session(db_engine) -> Generator[Session, None, None]:
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def clear_cache() -> Generator[None, None, None]:
    cache_backend.clear()
    try:
        yield
    finally:
        cache_backend.clear()


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    app = create_app()

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client


if pytest_asyncio is not None:

    @pytest_asyncio.fixture()
    async def async_client(db_session: Session) -> AsyncGenerator["httpx.AsyncClient", None]:
        import httpx

        app = create_app()

        async def override_get_db() -> AsyncGenerator[Session, None]:
            yield db_session

        app.dependency_overrides[get_db] = override_get_db

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            yield client

else:

    @pytest.fixture()
    def async_client():  # pragma: no cover - skip when dependency missing
        pytest.skip("pytest-asyncio is not installed")


@pytest.fixture()
def french_vocabulary(db_session):
    words = [
        VocabularyWord(
            language="fr",
            word="baguette",
            normalized_word="baguette",
            part_of_speech="noun",
            frequency_rank=10,
            english_translation="baguette",
            difficulty_level=1,
        ),
        VocabularyWord(
            language="fr",
            word="fromage",
            normalized_word="fromage",
            part_of_speech="noun",
            frequency_rank=11,
            english_translation="cheese",
            difficulty_level=1,
        ),
        VocabularyWord(
            language="fr",
            word="bonjour",
            normalized_word="bonjour",
            part_of_speech="interjection",
            frequency_rank=5,
            english_translation="hello",
            difficulty_level=1,
        ),
    ]
    db_session.add_all(words)
    db_session.commit()
    try:
        yield words
    finally:
        db_session.query(VocabularyWord).delete()
        db_session.commit()
