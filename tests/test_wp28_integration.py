"""WP-28 — the hooks four packages left for their integration owner.

Each package landed with a lease that stopped at someone else's file, and each
wrote down what it could not wire. This pins the wiring itself, not the parts
that already have owners' tests:

1. **The because-line reaches the learner.** WP-24 could rank a learner's due
   errata and stamp the plan with them, but nothing read them at journey
   creation and nothing put the answer on ``GET /atelier/today``. Home's line
   was dark by construction.
2. **A prefetched scene cannot outlive the mistakes it was drafted for.** WP-26
   keys the cache on "learner context"; the errata are learner context now that
   the director is told about them, so a changed target set must change the key.
3. **The envelope says whether the draft is warm** rather than leaving the
   client to infer it from how fast the answer came back.
"""
from __future__ import annotations

import pathlib
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.db.models.error import UserError
from app.db.models.user import User
from app.schemas.daily_journey import JourneyCreateRequest
from app.services import journey_latency
from app.services.error_memory import ERROR_STATE_OPEN, ErrorMemoryService
from app.services.journey_contracts import InputMode
from app.services.journey_errata import errata_targets_for_user, reason_for
from app.services.journey_latency import scene_cache_key

NOW = datetime(2026, 9, 10, 9, 0, tzinfo=UTC)
LABEL = "Accord du participe passé"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def make_user(db: Session, email: str) -> User:
    user = User(
        id=uuid.uuid4(),
        email=email,
        hashed_password="test",
        native_language="en",
        target_language="fr",
        proficiency_level="beginner",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def record_erratum(db: Session, user: User, *, label: str = LABEL) -> UserError:
    """Record a mistake the way the product records one, then make it due."""

    ErrorMemoryService(db).record_erratum(
        user=user,
        erratum={
            "display_label": label,
            "learner_text": "une homme",
            "corrected_target": "un homme",
            "why_wrong": "homme is masculine",
            "repair_hint": "un homme",
            "task_error_type": label,
            "severity": 2,
        },
        source_type="daily_journey",
    )
    db.commit()
    error = (
        db.query(UserError)
        .filter(UserError.user_id == user.id, UserError.display_label == label)
        .order_by(UserError.created_at.desc())
        .first()
    )
    assert error is not None
    error.state = ERROR_STATE_OPEN
    error.next_review_date = datetime.now(UTC) - timedelta(days=1)
    db.commit()
    return error


@pytest.fixture()
def journey_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.services.daily_journey as journey_module

    monkeypatch.setattr(
        journey_module.settings, "ATELIER_DAILY_JOURNEY_ENABLED", True, raising=False
    )
    monkeypatch.setattr(
        journey_module.settings, "ATELIER_DAILY_JOURNEY_COHORT", "", raising=False
    )


@pytest.fixture()
def cache_enabled(monkeypatch: pytest.MonkeyPatch):
    """The prefetch's preconditions, plus a settable story revision."""

    monkeypatch.setattr(
        journey_latency.settings, "ATELIER_STORY_ENGINE_ENABLED", True, raising=False
    )
    monkeypatch.setattr(
        journey_latency.settings, "ATELIER_JOURNEY_PREFETCH_ENABLED", True, raising=False
    )
    import app.services.living_story as living_story

    monkeypatch.setattr(
        living_story, "story_revision", lambda db, user: "rev-1", raising=False
    )


# ---------------------------------------------------------------------------
# 1. WP-24 §5 — the because-line, end to end
# ---------------------------------------------------------------------------


def test_a_due_erratum_reaches_the_today_envelope_as_a_because_line(
    db_session: Session, journey_enabled: None
) -> None:
    """The whole chain: a recorded mistake → the plan → ``GET /today``.

    Nothing here is stubbed on the WP-24 side: the erratum is recorded through
    the service that owns the dedupe key, ranked by ``journey_errata``, merged
    by the real planner, and read back off the persisted plan by the state
    machine. If any link is missing the line is dark, which is exactly the
    state this package inherited.
    """

    from app.services.daily_journey import DailyJourneyService
    from tests.test_daily_journey_state import build_adapters

    user = make_user(db_session, "because-e2e@example.com")
    error = record_erratum(db_session, user)

    service = DailyJourneyService(db_session, build_adapters())
    _snapshot, code = service.create_journey(
        user,
        JourneyCreateRequest(
            mutation_id=uuid.uuid4().hex,
            timezone="Europe/Paris",
            budget_seconds=300,
            preferred_input_mode=InputMode.TEXT,
        ),
    )
    assert code == 201

    envelope = service.get_today(user)
    assert envelope.because is not None, "the because-line is still dark"
    assert envelope.because.kind == "erratum"
    assert envelope.because.reason == reason_for(error.id)
    assert envelope.because.label == LABEL
    # The «faux → juste» half is what turns "you got something wrong" into
    # something a learner can act on.
    assert envelope.because.example == "une homme → un homme"


def test_a_learner_with_no_due_mistake_is_told_nothing(
    db_session: Session, journey_enabled: None
) -> None:
    """No erratum, no line — and no invented explanation for today's scene."""

    from app.services.daily_journey import DailyJourneyService
    from tests.test_daily_journey_state import build_adapters

    user = make_user(db_session, "because-none@example.com")
    service = DailyJourneyService(db_session, build_adapters())
    service.create_journey(
        user,
        JourneyCreateRequest(
            mutation_id=uuid.uuid4().hex,
            timezone="Europe/Paris",
            budget_seconds=300,
            preferred_input_mode=InputMode.TEXT,
        ),
    )
    assert service.get_today(user).because is None


def test_the_because_line_is_read_from_the_plan_not_recomputed_from_the_queue(
    db_session: Session, journey_enabled: None
) -> None:
    """The claim is about the scene the learner HAS.

    Recomputing the line on every read would let a mistake recorded after the
    scene was planned claim credit for it — a scene that never targeted that
    erratum, announcing that it does.
    """

    from app.services.daily_journey import DailyJourneyService
    from tests.test_daily_journey_state import build_adapters

    user = make_user(db_session, "because-after@example.com")
    service = DailyJourneyService(db_session, build_adapters())
    service.create_journey(
        user,
        JourneyCreateRequest(
            mutation_id=uuid.uuid4().hex,
            timezone="Europe/Paris",
            budget_seconds=300,
            preferred_input_mode=InputMode.TEXT,
        ),
    )
    record_erratum(db_session, user, label="Le passé composé")
    assert errata_targets_for_user(db_session, user)
    assert service.get_today(user).because is None


def test_the_story_director_is_told_what_the_learner_gets_wrong(
    db_session: Session
) -> None:
    """WP-24 §5's quality half: the erratum shapes the situation.

    Label, «faux → juste» and the stored explanation — the three fields the
    handover named. The prompt must ask for a situation that *needs* the
    repaired form; a scene that merely mentions the rule is a drill wearing a
    story's clothes.
    """

    import app.services.living_story as living_story

    user = make_user(db_session, "director-errata@example.com")
    assert living_story.errata_context(db_session, user) == []

    record_erratum(db_session, user)
    context = living_story.errata_context(db_session, user)
    assert context and context[0]["label"] == LABEL
    assert context[0]["example"] == "une homme → un homme"
    assert context[0]["why"]

    assert "errata lists mistakes this learner has actually made" in living_story.DIRECTOR
    assert "NEEDS the repaired form" in living_story.DIRECTOR
    # The actor grades what was said. Telling it what to expect would bias the
    # correction it is asked to produce.
    assert "errata" not in living_story.ACTOR


# ---------------------------------------------------------------------------
# 2. WP-26 — the cache key carries the errata
# ---------------------------------------------------------------------------


def test_the_prefetch_key_changes_when_the_errata_targets_change(
    db_session: Session, cache_enabled: None
) -> None:
    """A scene drafted for one set of mistakes is not the scene for another.

    Without this, a learner who repaired a mistake overnight would be served the
    morning scene that was generated to make them repeat it.
    """

    user = make_user(db_session, "key-errata@example.com")
    empty = scene_cache_key(db_session, user, input_mode=InputMode.TEXT)
    assert empty

    record_erratum(db_session, user)
    with_one = scene_cache_key(db_session, user, input_mode=InputMode.TEXT)
    assert with_one and with_one != empty

    record_erratum(db_session, user, label="Le passé composé")
    with_two = scene_cache_key(db_session, user, input_mode=InputMode.TEXT)
    assert with_two and with_two not in {empty, with_one}

    # Stable while the set is: the key must not churn on every read, or nothing
    # would ever be servable.
    assert scene_cache_key(db_session, user, input_mode=InputMode.TEXT) == with_two


def test_a_repaired_erratum_puts_the_key_back(
    db_session: Session, cache_enabled: None
) -> None:
    """Membership, not the ranking's clock-dependent order, is what keys it."""

    user = make_user(db_session, "key-repaired@example.com")
    empty = scene_cache_key(db_session, user, input_mode=InputMode.TEXT)
    error = record_erratum(db_session, user)
    assert scene_cache_key(db_session, user, input_mode=InputMode.TEXT) != empty

    error.next_review_date = datetime.now(UTC) + timedelta(days=7)
    db_session.commit()
    assert scene_cache_key(db_session, user, input_mode=InputMode.TEXT) == empty


# ---------------------------------------------------------------------------
# 3. WP-26 — the envelope says whether the draft is warm
# ---------------------------------------------------------------------------


def test_today_says_whether_the_draft_is_warm(
    db_session: Session, journey_enabled: None, cache_enabled: None, monkeypatch
) -> None:
    import app.services.living_story as living_story
    from app.services.daily_journey import DailyJourneyService
    from tests.test_daily_journey_state import build_adapters
    from tests.test_journey_latency import make_brief

    user = make_user(db_session, "warm-envelope@example.com")
    service = DailyJourneyService(db_session, build_adapters())
    assert service.get_today(user).is_warm is False

    monkeypatch.setattr(
        living_story, "generate_scene", lambda db, *, user, input_mode: make_brief()
    )
    assert journey_latency.prefetch_scene_for(db_session, user) == "prefetched"
    assert service.get_today(user).is_warm is True


def test_warmth_is_false_once_the_day_has_a_journey(
    db_session: Session, journey_enabled: None, cache_enabled: None
) -> None:
    """The field describes the draft the learner is about to ask for.

    With today's journey already on the envelope there is no draft to be warm,
    and claiming otherwise would make the client hold back its honest wait copy
    for a request that has to be generated.
    """

    from app.services.daily_journey import DailyJourneyService
    from tests.test_daily_journey_state import build_adapters

    user = make_user(db_session, "warm-after@example.com")
    service = DailyJourneyService(db_session, build_adapters())
    service.create_journey(
        user,
        JourneyCreateRequest(
            mutation_id=uuid.uuid4().hex,
            timezone="Europe/Paris",
            budget_seconds=300,
            preferred_input_mode=InputMode.TEXT,
        ),
    )
    envelope = service.get_today(user)
    assert envelope.journey is not None
    assert envelope.is_warm is False


# ---------------------------------------------------------------------------
# 4. The surfaces — source scans
# ---------------------------------------------------------------------------

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
WEB = REPO_ROOT / "web-frontend"


def read(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def test_the_because_line_is_wired_from_the_envelope_to_home() -> None:
    """The line was dark because nothing carried it, not because nothing said it.

    WP-24 wrote the French and the payload; the three links between them —
    the envelope field, the page's read of it, and the prop — are this
    package's, and each one alone is enough to keep the line dark.
    """

    helper = read(WEB / "lib" / "atelier-next.ts")
    page = read(WEB / "pages" / "atelier.tsx")
    home = read(WEB / "components" / "atelier-v2" / "home" / "HomeScreen.tsx")
    types = read(WEB / "types" / "daily-journey.ts")

    assert "export function journeyBecause(" in helper
    # An unknown kind prints nothing rather than guessing at French for it.
    assert "because.kind !== 'erratum'" in helper
    assert "journeyBecause(journey.envelope)" in page
    assert "becauseLine={becauseLine}" in page
    assert "because={becauseLine}" in page
    assert "<BecauseLine because={because} />" in home
    assert "because: JourneyBecause | null;" in types


def test_the_client_is_told_the_draft_is_warm_instead_of_timing_it() -> None:
    controller = read(WEB / "components" / "atelier-v2" / "journey" / "useDailyJourney.ts")
    requests = read(WEB / "components" / "atelier-v2" / "journey" / "journey-requests.ts")

    assert "envelope?.is_warm === true" in controller
    assert "delayMs: warm ? WARM_WAIT_HINT_DELAY_MS : WAIT_HINT_DELAY_MS" in controller
    assert "export const WARM_WAIT_HINT_DELAY_MS" in requests
    # Delayed, never suppressed: a warm scene whose preconditions changed is
    # generated like any other, and that learner still gets told.
    assert "never suppressed" in requests


def test_the_controller_no_longer_carries_the_dead_voice_capture() -> None:
    """WP-27 moved the microphone into `useVoiceAnswer` and left the old fields.

    Two capture paths in one screen is how a transcript ends up submitted by
    something nobody is looking at — the exact defect WP-27 removed.
    """

    controller = read(WEB / "components" / "atelier-v2" / "journey" / "useDailyJourney.ts")
    index = read(WEB / "components" / "atelier-v2" / "journey" / "index.ts")
    voice_hook = read(WEB / "components" / "atelier-v2" / "journey" / "useVoiceAnswer.ts")

    for dead in ("VoiceState", "startRecording", "stopRecording", "resetVoice", "MediaRecorder"):
        assert dead not in controller, f"{dead} is still in the journey controller"
    assert "VoiceState" not in index
    # The one surviving capture path is the respond step's own hook.
    assert "MediaRecorder" in voice_hook


def test_le_releve_names_a_placement_as_a_placement() -> None:
    """A measured prior must not wear the words of a self-declaration.

    `estimate_source === 'placement'` outranks `declared` and is still
    unverified, so the gauges and the forecast stay away — but the sentence
    under the level has to say which of the two it is.
    """

    releve = read(WEB / "components" / "releve" / "Releve.tsx")

    assert "cefr?.estimate_source === 'placement'" in releve
    assert "Niveau estimé (placement)" in releve
    assert "const unverified = declared || placement;" in releve
    # The declared sentence survives untouched: it is still the honest line for
    # a learner who only ever told us.
    assert "Niveau que vous avez indiqué." in releve
    # Neither branch may print a gauge against a level nothing has tested.
    assert "{!unverified && (coursWords[1] > 0 || coursRules[1] > 0) && (" in releve
