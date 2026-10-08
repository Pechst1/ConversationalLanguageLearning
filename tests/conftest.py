"""Pytest fixtures for API tests."""

import asyncio
import itertools
import os
import sqlite3
import threading
from collections.abc import AsyncGenerator, Generator
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - import only for static analysis
    import httpx

os.environ.setdefault("SECRET_KEY", "test-secret-key")
# Existing authored fixtures explicitly test the legacy compatibility path.
# Story-engine tests enable the new engine with an injected fake model.
os.environ.setdefault("ATELIER_STORY_ENGINE_ENABLED", "false")
os.environ.setdefault("ATELIER_LLM_ENABLED", "false")
# WP-87: the suite's scripted story providers answer the single-actor schemas
# (SemanticTurn + Review). They keep testing that path — the rollback path — and
# tests/test_wp87_* switch the three-lane turn on (the production default).
os.environ.setdefault("ATELIER_STORY_TURN_LANES_ENABLED", "false")
os.environ.setdefault("GRAPHIC_NOVEL_IMAGE_GENERATION_ENABLED", "false")
os.environ.setdefault("ATELIER_PANEL_ART_ENABLED", "false")
# WP-75: a learner's first day is authored (the café, the cast, two quick
# recall items). The suite's existing journey tests are about the day the
# rotation / story engine makes, so they keep that premise; tests/test_wp75_*
# switch the first day on explicitly.
os.environ.setdefault("ATELIER_JOURNEY_FIRST_DAY_AUTHORED_ENABLED", "false")
# WP-L2: the suite describes the live v1 grammar catalogue; tests/test_wp_l2_*
# switch the v2 syllabus on explicitly. Pinned so an owner's .env that flips
# the catalogue does not silently change what the suite tests.
os.environ.setdefault("ATELIER_GRAMMAR_CATALOG_VERSION", "v1")
# The unauthenticated local-demo fallback (`app/api/deps.get_current_user_or_demo`)
# is a developer convenience that the owner's `.env` switches on. Left to the
# environment, the suite inherited it: three tests passed on that machine and
# returned 401 in CI, which has no `.env`. Pinned to the production default here
# — an environment variable outranks the dotenv file — so a local run and CI
# agree. Assignment, not `setdefault`: inheriting this one is the bug. Tests that
# genuinely exercise the fallback take the `local_demo_auth` fixture below.
os.environ["AUTO_CREATE_USERS_ON_LOGIN"] = "false"

import pytest

try:  # pragma: no cover - optional dependency
    import pytest_asyncio
except ImportError:  # pragma: no cover
    pytest_asyncio = None  # type: ignore[assignment]
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.db import models  # noqa: F401  # Imported for side effects
from app.db.base import Base
from app.db.models import (
    RefreshToken,
    User,
    UserConjugationProgress,
    VerbConjugation,
    VocabularyWord,
)
from app.db.models.achievement import Achievement, UserAchievement
from app.db.models.analytics import AnalyticsSnapshot
from app.db.models.atelier import (
    AtelierAttempt,
    AtelierCollectible,
    AtelierConceptBlueprint,
    AtelierExerciseSet,
    AtelierGenerationEvent,
    AtelierLanguagePack,
    AtelierServedItem,
    AtelierSession,
)
from app.db.models.cefr import UserCanDoStamp, UserCEFRProgressHistory, UserLevelCheckpoint
from app.db.models.daily_journey import (
    DailyJourney,
    DailyJourneyMutation,
    DailyJourneyStep,
)
from app.db.models.episode_audio import EpisodeAudioClip
from app.db.models.error import UserError, UserErrorConcept
from app.db.models.feedback import UserFeedbackReport
from app.db.models.grammar import (
    GrammarConcept,
    GrammarConceptArchive,
    GrammarConceptLocalization,
    UserGrammarProgress,
)
from app.db.models.graphic_novel import (
    GraphicNovelAttempt,
    GraphicNovelPanel,
    GraphicNovelScene,
    PersonalInputItem,
)
from app.db.models.intake import LearnerArtefact
from app.db.models.library import BookEpisode, UserBook
from app.db.models.line_audio import LineAudioClip
from app.db.models.mission import RealWorldMission, RealWorldMissionAttempt, RealWorldMissionTurn
from app.db.models.password_reset_delivery import PasswordResetDelivery
from app.db.models.pilot_event import PilotEvent
from app.db.models.placement import PlacementSession
from app.db.models.progress import ReviewLog, UserVocabularyProgress
from app.db.models.push_subscription import PushSubscription
from app.db.models.rehearsal import Rehearsal
from app.db.models.serial import SerialEpisode, SerialThread
from app.db.models.session import (
    ConversationMessage,
    LearningSession,
    SessionLearningMoment,
    WordInteraction,
)
from app.db.models.streak_day import StreakDay
from app.db.models.vocabulary import UserDailyWordSlate
from app.main import create_app
from app.utils.cache import cache_backend


@compiles(PG_UUID, "sqlite")
def _pg_uuid_as_text_on_sqlite(type_, compiler, **kw):  # noqa: ARG001
    """Keep UUIDs as text on SQLite; leave PostgreSQL's UUID type unchanged."""

    return "CHAR(32)"


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:  # pragma: no cover - placeholder for async tests
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


class SavepointLedger:
    """Every transaction on the suite's one SQLite connection is a SAVEPOINT.

    E-2. The suite shares one in-memory database per process (one per xdist
    worker), and it used to keep every row any test committed: results depended on
    which files had run before on the same worker. Now the data of a test, and of a
    module-scoped fixture, is rolled back when it ends; the schema stays.

    How: the engine's own COMMIT and ROLLBACK are switched off, and each
    transaction SQLAlchemy begins — any session, any thread, any code path that
    commits — becomes a SAVEPOINT on a stack. A commit RELEASEs it into the level
    below; a rollback rolls back to it. Below every test sits a ``test`` level and
    below every module a ``module`` level, both rolled back at teardown. Nothing in
    the application changes: a session still commits, ``after_commit`` hooks
    (``panel_art``, ``coulisses``, the story lanes) still fire, and what one
    session committed is visible to the next, as on a real database.
    """

    def __init__(self, raw: sqlite3.Connection) -> None:
        self.raw = raw
        self.stack: list[str] = []
        self.owners: dict[int, str] = {}
        self.lock = threading.RLock()
        self.counter = itertools.count()

    def open(self, kind: str) -> str:
        with self.lock:
            name = f"e2_{kind}_{next(self.counter)}"
            self.raw.execute(f"SAVEPOINT {name}")
            self.stack.append(name)
            return name

    def _end(self, name: str, *, keep: bool) -> bool:
        with self.lock:
            if name not in self.stack:
                return False
            if not keep:
                self.raw.execute(f"ROLLBACK TO SAVEPOINT {name}")
            self.raw.execute(f"RELEASE SAVEPOINT {name}")
            del self.stack[self.stack.index(name):]
            return True

    def release(self, name: str) -> bool:
        return self._end(name, keep=True)

    def rollback(self, name: str) -> bool:
        return self._end(name, keep=False)

    def rollback_level(self, name: str) -> None:
        """End a test or module level; it must still be there."""

        if not self.rollback(name):
            raise AssertionError(
                f"E-2 isolation: the savepoint {name} was released under the test "
                f"(open levels: {self.stack}). Something ended a transaction that "
                "began before this level — a session left open across tests?"
            )

    def watch(self, engine) -> None:
        @event.listens_for(engine, "begin")
        def _begin(conn) -> None:
            self.owners[id(conn)] = self.open("tx")

        @event.listens_for(engine, "commit")
        def _commit(conn) -> None:
            name = self.owners.pop(id(conn), None)
            if name:
                self.release(name)

        @event.listens_for(engine, "rollback")
        def _rollback(conn) -> None:
            name = self.owners.pop(id(conn), None)
            if name:
                self.rollback(name)

        # The savepoints above are the transactions; the DB-API connection's own
        # commit/rollback (and the pool's reset-on-return) must not end them.
        engine.dialect.do_commit = lambda dbapi_connection: None
        engine.dialect.do_rollback = lambda dbapi_connection: None


@pytest.fixture(scope="session")
def db_engine():
    # isolation_level=None: the sqlite3 module issues no implicit BEGIN; every
    # transaction is a savepoint the ledger opened.
    raw = sqlite3.connect(":memory:", check_same_thread=False, isolation_level=None)
    engine = create_engine("sqlite://", creator=lambda: raw, poolclass=StaticPool)
    engine.savepoints = SavepointLedger(raw)
    engine.savepoints.watch(engine)
    Base.metadata.create_all(
        bind=engine,
        tables=[
            User.__table__,
            PasswordResetDelivery.__table__,
            UserFeedbackReport.__table__,
            PushSubscription.__table__,
            RefreshToken.__table__,
            Achievement.__table__,
            UserAchievement.__table__,
            AnalyticsSnapshot.__table__,
            PilotEvent.__table__,
            PlacementSession.__table__,
            Rehearsal.__table__,
            VocabularyWord.__table__,
            VerbConjugation.__table__,
            UserConjugationProgress.__table__,
            GrammarConcept.__table__,
            GrammarConceptArchive.__table__,
            GrammarConceptLocalization.__table__,
            UserGrammarProgress.__table__,
            UserCEFRProgressHistory.__table__,
            UserLevelCheckpoint.__table__,
            UserCanDoStamp.__table__,
            AtelierLanguagePack.__table__,
            AtelierConceptBlueprint.__table__,
            AtelierSession.__table__,
            AtelierCollectible.__table__,
            AtelierExerciseSet.__table__,
            AtelierGenerationEvent.__table__,
            AtelierAttempt.__table__,
            AtelierServedItem.__table__,
            SerialThread.__table__,
            RealWorldMission.__table__,
            RealWorldMissionAttempt.__table__,
            RealWorldMissionTurn.__table__,
            LearnerArtefact.__table__,
            EpisodeAudioClip.__table__,
            LineAudioClip.__table__,
            UserBook.__table__,
            BookEpisode.__table__,
            PersonalInputItem.__table__,
            GraphicNovelScene.__table__,
            GraphicNovelPanel.__table__,
            GraphicNovelAttempt.__table__,
            SerialEpisode.__table__,
            UserError.__table__,
            UserErrorConcept.__table__,
            UserVocabularyProgress.__table__,
            UserDailyWordSlate.__table__,
            ReviewLog.__table__,
            LearningSession.__table__,
            ConversationMessage.__table__,
            SessionLearningMoment.__table__,
            WordInteraction.__table__,
            DailyJourney.__table__,
            DailyJourneyStep.__table__,
            DailyJourneyMutation.__table__,
            StreakDay.__table__,
        ],
    )
    try:
        yield engine
    finally:
        Base.metadata.drop_all(
            bind=engine,
            tables=[
                StreakDay.__table__,
                DailyJourneyMutation.__table__,
                DailyJourneyStep.__table__,
                DailyJourney.__table__,
                WordInteraction.__table__,
                SessionLearningMoment.__table__,
                ConversationMessage.__table__,
                LearningSession.__table__,
                ReviewLog.__table__,
                UserDailyWordSlate.__table__,
                UserVocabularyProgress.__table__,
                AnalyticsSnapshot.__table__,
                Rehearsal.__table__,
                PilotEvent.__table__,
                UserErrorConcept.__table__,
                UserError.__table__,
                SerialEpisode.__table__,
                LineAudioClip.__table__,
                EpisodeAudioClip.__table__,
                GraphicNovelAttempt.__table__,
                GraphicNovelPanel.__table__,
                GraphicNovelScene.__table__,
                PersonalInputItem.__table__,
                BookEpisode.__table__,
                UserBook.__table__,
                LearnerArtefact.__table__,
                RealWorldMissionTurn.__table__,
                RealWorldMissionAttempt.__table__,
                RealWorldMission.__table__,
                SerialThread.__table__,
                AtelierServedItem.__table__,
                AtelierAttempt.__table__,
                AtelierGenerationEvent.__table__,
                AtelierExerciseSet.__table__,
                AtelierCollectible.__table__,
                AtelierSession.__table__,
                AtelierConceptBlueprint.__table__,
                AtelierLanguagePack.__table__,
                UserGrammarProgress.__table__,
                UserCanDoStamp.__table__,
                UserLevelCheckpoint.__table__,
                UserCEFRProgressHistory.__table__,
                GrammarConceptLocalization.__table__,
                GrammarConceptArchive.__table__,
                GrammarConcept.__table__,
                VocabularyWord.__table__,
                UserConjugationProgress.__table__,
                VerbConjugation.__table__,
                UserAchievement.__table__,
                Achievement.__table__,
                RefreshToken.__table__,
                PushSubscription.__table__,
                UserFeedbackReport.__table__,
                User.__table__,
                PasswordResetDelivery.__table__,
            ],
        )


@pytest.fixture(scope="module", autouse=True)
def module_data_rolls_back(db_engine) -> Generator[None, None, None]:
    """What a module-scoped fixture committed (the 126-day harness) leaves with it."""

    level = db_engine.savepoints.open("module")
    try:
        yield
    finally:
        db_engine.savepoints.rollback_level(level)


@pytest.fixture(autouse=True)
def test_data_rolls_back(module_data_rolls_back, db_engine) -> Generator[None, None, None]:
    """What a test committed is gone before the next test starts."""

    level = db_engine.savepoints.open("test")
    try:
        yield
    finally:
        db_engine.savepoints.rollback_level(level)


@pytest.fixture()
def db_session(db_engine) -> Generator[Session, None, None]:
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


#: WP-78. Suites written before the practice day pin the classic envelope
#: (scene first, at most two recalls) and run with the practice day off; these
#: modules pin the practice day and run it on, as production does. A module-
#: scoped fixture (the 126-day harness) sees the production default either way.
PRACTICE_DAY_MODULE_PREFIXES = ("test_wp78_", "test_long_horizon_evidence", "test_wp_l4_", "test_wp_s4_", "test_forge_integration")


@pytest.fixture(autouse=True)
def classic_day_unless_practice_suite(request, monkeypatch) -> None:
    from app.config import settings

    module = getattr(request, "module", None)
    name = str(getattr(module, "__name__", "")).rsplit(".", 1)[-1]
    monkeypatch.setattr(
        settings,
        "ATELIER_JOURNEY_PRACTICE_DAY_ENABLED",
        name.startswith(PRACTICE_DAY_MODULE_PREFIXES),
    )


@pytest.fixture(autouse=True)
def clear_cache() -> Generator[None, None, None]:
    cache_backend.clear()
    try:
        yield
    finally:
        cache_backend.clear()


@pytest.fixture()
def local_demo_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    """Enable the unauthenticated local-demo user for one test.

    `get_current_user_or_demo` reads the flag on every call, so patching the
    settings object is enough. A test that calls an authenticated endpoint with
    no Authorization header must ask for this fixture: without it the endpoint
    answers 401, which is what production does.
    """

    from app.config import settings

    monkeypatch.setattr(settings, "AUTO_CREATE_USERS_ON_LOGIN", True)


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
