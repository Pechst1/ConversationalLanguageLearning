"""WP-30 — the journal API, driven the way the Cahier tab drives it.

Behavioural, not snapshot: the real router, the real service, a fake checker in
place of the paid provider.

The test this file exists for is
:func:`test_the_scene_text_is_not_in_the_response_until_the_learner_has_written`.
Everything else in the package is a design decision that could be revisited;
that one is the package. A free-recall prompt that ships the scene in the same
JSON is a copying exercise wearing a retrieval-practice label, and no amount of
front-end discipline can fix a payload that already carries the answer.
"""
from __future__ import annotations

import json
import uuid
from collections.abc import Generator, Iterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models.daily_journey import DailyJourney, DailyJourneyStep
from app.db.models.grammar import GrammarConcept
from app.db.models.journal import JournalEntry
from app.db.models.user import User
from app.main import create_app
from app.services import journal as journal_module

TEST_PASSWORD = "securepass123"

SETUP_FR = "Romy vous attend au Mistral avec un livre sous le bras."
CHARACTER_LINE_FR = "Vous me le rapportez mardi ?"
TITLE_FR = "Un café au Mistral"


@pytest.fixture(autouse=True)
def journal_table(db_engine):
    """This package owns its own table's DDL in its own tests (see test_journal)."""
    JournalEntry.__table__.create(bind=db_engine, checkfirst=True)


class _FakeChecker:
    def __init__(self) -> None:
        self.calls = 0

    def generate_error_detection(self, messages, **kwargs):
        self.calls += 1
        payload = json.loads(messages[0]["content"])
        return SimpleNamespace(
            provider="openai",
            model="test-model",
            content=json.dumps(
                {
                    "verdict": "partial",
                    "score_0_4": 2,
                    "corrected_answer": "J’ai rapporté le livre à Romy.",
                    "concept_hits": [],
                    "missing_targets": [],
                    "errata": [
                        {
                            "item_id": "a",
                            "display_label": "Article",
                            "learner_text": "la livre",
                            "corrected_target": "le livre",
                            "why_wrong": "«livre» is masculine.",
                            "repair_hint": "le livre",
                            "severity": 2,
                            "recurring": True,
                            "task_error_type": "gender_agreement",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            prompt_tokens=100,
            completion_tokens=40,
            total_tokens=140,
            cost=0.0002,
            raw_response={"answer": payload.get("answer")},
        )


@pytest.fixture()
def fake_checker(monkeypatch: pytest.MonkeyPatch) -> _FakeChecker:
    """Every corrector built inside a request gets this checker."""
    checker = _FakeChecker()
    monkeypatch.setattr(
        journal_module._JournalCorrector, "_get_llm_service", lambda self: checker
    )
    return checker


@pytest.fixture()
def journal_client(db_session: Session) -> Generator[TestClient, None, None]:
    app = create_app()

    def override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client


def login(client: TestClient, email: str) -> dict[str, str]:
    client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": TEST_PASSWORD,
            "target_language": "fr",
            "native_language": "en",
            "proficiency_level": "A1",
        },
    )
    response = client.post(
        "/api/v1/auth/login", json={"email": email, "password": TEST_PASSWORD}
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _email() -> str:
    return f"journal-api-{uuid.uuid4().hex[:8]}@example.com"


def _seed_scene(db_session: Session, email: str, *, days_ago: int = 1) -> DailyJourney:
    user = db_session.query(User).filter(User.email == email).one()
    concept = GrammarConcept(
        language="fr",
        level="A1",
        name="Articles définis",
        external_id=f"FR_A1_ART_{uuid.uuid4().hex[:6]}",
        difficulty_order=10,
        active=True,
    )
    db_session.add(concept)
    db_session.flush()
    journey = DailyJourney(
        user_id=user.id,
        local_date=datetime.now(UTC).date() - timedelta(days=days_ago),
        timezone="UTC",
        content_version="journey-content-v1",
        level_band="A1",
        status="completed",
        serial_episode_id="ep-3",
        scenario_snapshot={
            "scenario_key": "order_at_cafe",
            "title_fr": TITLE_FR,
            "character_name": "Romy",
            "location_name": "Le Mistral",
            "objective_native": "Order one coffee.",
        },
        recap_snapshot={
            "story_outcome": {
                "outcome_key": "met",
                "callback_fr": "Vous avez promis de rapporter le livre mardi.",
            }
        },
    )
    db_session.add(journey)
    db_session.flush()
    db_session.add(
        DailyJourneyStep(
            journey_id=journey.id,
            ordinal=0,
            kind="scene",
            status="completed",
            public_prompt={
                "setup_fr": SETUP_FR,
                "setup_native": "Romy is waiting.",
                "objective_native": "Order one coffee.",
                "character_line_fr": CHARACTER_LINE_FR,
            },
            private_task={"rubric": "NEVER PUBLIC"},
        )
    )
    db_session.add(
        DailyJourneyStep(
            journey_id=journey.id,
            ordinal=1,
            kind="respond",
            status="completed",
            target_kind="grammar",
            target_id=str(concept.id),
            public_prompt={},
            private_task={},
        )
    )
    db_session.commit()
    return journey


# ---------------------------------------------------------------------------


def test_every_journal_route_needs_a_signed_in_learner(journal_client):
    entry_id = str(uuid.uuid4())
    assert journal_client.get("/api/v1/journal/state").status_code == 401
    assert journal_client.get("/api/v1/journal/entries").status_code == 401
    assert journal_client.post(f"/api/v1/journal/{entry_id}/write", json={"text": "x"}).status_code == 401
    assert journal_client.post(f"/api/v1/journal/{entry_id}/skip").status_code == 401
    assert journal_client.post(f"/api/v1/journal/{entry_id}/followup", json={"text": "x"}).status_code == 401


def test_a_learner_with_no_finished_scene_sees_an_empty_journal(journal_client):
    headers = login(journal_client, _email())
    state = journal_client.get("/api/v1/journal/state", headers=headers).json()
    assert state["status"] == "none"
    assert state["entry"] is None
    assert state["recall_offset_days"] == journal_module.RECALL_OFFSET_DAYS
    assert state["followup_offset_days"] == journal_module.FOLLOWUP_OFFSET_DAYS


def test_the_scene_text_is_not_in_the_response_until_the_learner_has_written(
    journal_client, db_session, fake_checker
):
    """The whole package, in one assertion pair.

    Before: the payload carries the cue and nothing a learner could copy.
    After: the reveal is there, because reading it back is the second half of
    retrieval practice.
    """
    email = _email()
    headers = login(journal_client, email)
    _seed_scene(db_session, email)

    before = journal_client.get("/api/v1/journal/state", headers=headers)
    body = before.text
    assert before.status_code == 200
    assert before.json()["status"] == "offered"
    for secret in (SETUP_FR, CHARACTER_LINE_FR, TITLE_FR):
        assert secret not in body, f"the offer leaked scene text: {secret!r}"
    # The cue that *is* there is only who / where / when.
    cue = before.json()["entry"]["cue"]
    assert cue["character_name"] == "Romy"
    assert cue["location_name"] == "Le Mistral"
    assert cue["days_ago"] == 1
    assert before.json()["entry"]["reveal"] is None

    entry_id = before.json()["entry"]["id"]
    after = journal_client.post(
        f"/api/v1/journal/{entry_id}/write",
        headers=headers,
        json={"text": "J’ai vu la livre au Mistral et j’ai promis de le rapporter mardi."},
    )
    assert after.status_code == 200
    assert SETUP_FR in after.text
    assert CHARACTER_LINE_FR in after.text


def test_the_prompt_model_has_no_field_that_could_hold_scene_text(journal_client):
    """Source scan, alongside the behavioural test above.

    Two different failures: the behavioural test catches a *value* leaking, this
    one catches the *shape* changing — a `setup_fr` added to the cue model would
    pass every runtime assertion until someone populated it.
    """
    from app.api.v1.endpoints.journal import JournalCueView, JournalRevealView

    cue_fields = set(JournalCueView.model_fields)
    assert cue_fields == {"character_name", "location_name", "scene_date", "days_ago"}
    assert not (cue_fields & set(JournalRevealView.model_fields))

    source = Path("app/api/v1/endpoints/journal.py").read_text(encoding="utf-8")
    # The reveal is attached on the written branch only, and once.
    assert source.count("JournalRevealView(**dict(entry.scene_reveal or {}))") == 1
    assert "if written else None" in source

    tab = Path("web-frontend/components/cahiers/JournalTab.tsx").read_text(encoding="utf-8")
    # The component reads the reveal only through `entry.reveal`, which the API
    # does not send before submission — there is no second path to the scene.
    assert "entry.cue" in tab
    assert "setup_fr" not in tab.split("entry.reveal &&")[0]


def test_the_correction_arrives_with_one_foreground_and_the_full_list(
    journal_client, db_session, fake_checker
):
    email = _email()
    headers = login(journal_client, email)
    _seed_scene(db_session, email)
    entry_id = journal_client.get("/api/v1/journal/state", headers=headers).json()["entry"]["id"]

    written = journal_client.post(
        f"/api/v1/journal/{entry_id}/write",
        headers=headers,
        json={"text": "J’ai vu la livre au Mistral et j’ai promis de le rapporter mardi."},
    ).json()

    entry = written["entry"]
    assert entry["status"] == "written"
    assert entry["correction"]["assessment_status"] == "checked"
    assert entry["correction"]["foreground"]["corrected_fr"] == "le livre"
    assert len(entry["correction"]["errata"]) == 1
    assert entry["errata_recorded"] == 1
    # Content recall is its own object, never folded into the verdict.
    assert entry["content_recall"]["status"] == "scored"
    assert "score" in entry["content_recall"]
    assert fake_checker.calls == 1


def test_an_empty_entry_is_refused_rather_than_stored(journal_client, db_session, fake_checker):
    email = _email()
    headers = login(journal_client, email)
    _seed_scene(db_session, email)
    entry_id = journal_client.get("/api/v1/journal/state", headers=headers).json()["entry"]["id"]

    response = journal_client.post(
        f"/api/v1/journal/{entry_id}/write", headers=headers, json={"text": "   "}
    )
    assert response.status_code == 422
    assert fake_checker.calls == 0


def test_a_replayed_write_makes_no_second_paid_call(journal_client, db_session, fake_checker):
    email = _email()
    headers = login(journal_client, email)
    _seed_scene(db_session, email)
    entry_id = journal_client.get("/api/v1/journal/state", headers=headers).json()["entry"]["id"]

    body = {"text": "J’ai rapporté la livre à Romy mardi comme promis."}
    first = journal_client.post(f"/api/v1/journal/{entry_id}/write", headers=headers, json=body)
    second = journal_client.post(f"/api/v1/journal/{entry_id}/write", headers=headers, json=body)
    assert first.status_code == second.status_code == 200
    assert first.json()["entry"]["entry_text"] == second.json()["entry"]["entry_text"]
    assert fake_checker.calls == 1


def test_a_learner_cannot_open_another_learners_entry(journal_client, db_session, fake_checker):
    mine = _email()
    theirs = _email()
    my_headers = login(journal_client, mine)
    _seed_scene(db_session, mine)
    entry_id = journal_client.get("/api/v1/journal/state", headers=my_headers).json()["entry"]["id"]

    their_headers = login(journal_client, theirs)
    response = journal_client.post(
        f"/api/v1/journal/{entry_id}/write", headers=their_headers, json={"text": "Bonjour."}
    )
    assert response.status_code == 404


def test_skipping_closes_the_entry_and_does_not_re_offer_it(journal_client, db_session):
    email = _email()
    headers = login(journal_client, email)
    _seed_scene(db_session, email)
    entry_id = journal_client.get("/api/v1/journal/state", headers=headers).json()["entry"]["id"]

    skipped = journal_client.post(f"/api/v1/journal/{entry_id}/skip", headers=headers).json()
    assert skipped["status"] == "skipped"
    again = journal_client.get("/api/v1/journal/state", headers=headers).json()
    assert again["status"] == "none"


def test_the_followup_line_appears_a_week_later_and_records_its_signal(
    journal_client, db_session, fake_checker
):
    email = _email()
    headers = login(journal_client, email)
    _seed_scene(db_session, email, days_ago=journal_module.FOLLOWUP_OFFSET_DAYS)
    entry_id = journal_client.get("/api/v1/journal/state", headers=headers).json()["entry"]["id"]
    journal_client.post(
        f"/api/v1/journal/{entry_id}/write",
        headers=headers,
        json={"text": "J’ai promis de rapporter le livre mardi à Romy."},
    )

    state = journal_client.get("/api/v1/journal/state", headers=headers).json()
    assert state["followup"] is not None
    assert state["followup"]["prompt_fr"] == "Et la semaine dernière, avec Romy ?"
    assert state["followup"]["answered"] is False

    answered = journal_client.post(
        f"/api/v1/journal/{state['followup']['entry_id']}/followup",
        headers=headers,
        json={"text": "J’ai rapporté le livre, comme promis."},
    ).json()
    assert answered["followup"] is None  # nothing else is due

    entry = db_session.query(JournalEntry).filter(JournalEntry.id == uuid.UUID(entry_id)).one()
    db_session.refresh(entry)
    assert entry.followup_signal == "used_again_later"


def test_the_entries_list_is_the_learners_own_writing(journal_client, db_session, fake_checker):
    email = _email()
    headers = login(journal_client, email)
    _seed_scene(db_session, email)
    assert journal_client.get("/api/v1/journal/entries", headers=headers).json() == []

    entry_id = journal_client.get("/api/v1/journal/state", headers=headers).json()["entry"]["id"]
    journal_client.post(
        f"/api/v1/journal/{entry_id}/write",
        headers=headers,
        json={"text": "J’ai rapporté le livre à Romy mardi."},
    )
    rows = journal_client.get("/api/v1/journal/entries", headers=headers).json()
    assert len(rows) == 1
    assert rows[0]["entry_text"] == "J’ai rapporté le livre à Romy mardi."
    assert rows[0]["scene_date"] == (date.today() - timedelta(days=1)).isoformat()
