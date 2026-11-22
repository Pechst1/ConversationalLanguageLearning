"""«Papier · l'écho»: what the learner does at the paper comes back in the story and in tomorrow's words.

* ``REVUE_WORDS_IN_DECK_ENABLED``: a word kept in a Papier (``kept_from_revue``) is treated like a word
  kept from the story — it opens tomorrow's deck (``day_words.kept_waiting_ids``), the director may
  bring it back (``kept_words.director_vocabulary``) and it is a recent kept word for the planner.
* ``REVUE_ECHO_ENABLED``: ``revue.echo`` reads the last finished Papier of the last three days and the
  day scene's director gets it as one block (``living_story._add_papier_echo``); off, the scene context
  and prompt are byte-identical.
"""

from __future__ import annotations

import copy
import json
import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import inspect
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.config import settings
from app.db.models.graphic_novel import GraphicNovelScene
from app.db.models.npc import NPC, NPCMemory
from app.db.models.pilot_event import PilotEvent
from app.db.models.revue_session import RevueDossier, RevueSession
from app.db.models.revue_vignette import RevuePictogram, RevueVignette
from app.db.models.story import Story
from app.db.models.user import User
from app.schemas.revue import RvComptoirRequest
from app.services import day_words, living_story
from app.services.kept_words import director_vocabulary, keep_revue_word, recent_kept_words
from app.services.revue import comptoir, echo
from app.services.revue import encounter as enc
from app.services.revue.encounter import FakeRevueProvider, RevueEncounter
from app.services.revue.evergreen import evergreens_for_week
from app.services.revue.pictogram import FakePictogramProvider
from app.services.season import page_pool

WEEK = "2026-W43"
ROMY, MARGAUX, GUS = "romy_tremblay", "margaux_barman", "augustin_de_roncourt"
TABLES = (Story.__table__, NPC.__table__, NPCMemory.__table__, RevueSession.__table__, RevueDossier.__table__,
          RevuePictogram.__table__, RevueVignette.__table__, PilotEvent.__table__)


@pytest.fixture(scope="module")
def tables(db_engine) -> Generator[None, None, None]:
    created = [table for table in TABLES if not inspect(db_engine).has_table(table.name)]
    for table in created:
        table.create(bind=db_engine, checkfirst=True)
    try:
        yield
    finally:
        for table in reversed(created):
            table.drop(bind=db_engine, checkfirst=True)


@pytest.fixture()
def db(db_session: Session, tables) -> Session:
    return db_session


@pytest.fixture(autouse=True)
def switches(monkeypatch) -> None:
    monkeypatch.setattr(enc, "available_dossiers", evergreens_for_week)
    monkeypatch.setattr(settings, "REVUE_ENABLED", True)
    monkeypatch.setattr(settings, "REVUE_COMPTOIR_ENABLED", True)
    monkeypatch.setattr(settings, "REVUE_WORDS_IN_DECK_ENABLED", False)
    monkeypatch.setattr(settings, "REVUE_ECHO_ENABLED", False)
    comptoir.forget_cache()


def make_user(db: Session, *, level: str = "A1.1") -> User:
    user = User(id=uuid.uuid4(), email=f"echo-{uuid.uuid4().hex[:10]}@example.com", hashed_password="x",
                cefr_estimate=level, native_language="en", interests="")
    db.add(user)
    db.commit()
    return user


def played_counter(db: Session, user: User | None = None) -> tuple[User, RevueSession]:
    """An A1 «Au comptoir» session played to its page and closed (no model call)."""

    revue = RevueEncounter(db, FakeRevueProvider())
    revue.pictogram_provider = FakePictogramProvider()
    user = user or make_user(db)
    row = revue.start(user, week=WEEK)

    def act(**body):
        return revue.comptoir(row, RvComptoirRequest(**body))

    act(act="vote", value="pour")
    for guest, value in ((ROMY, "agree"), (MARGAUX, "disagree"), (GUS, "disagree")):
        act(act="react", guest_id=guest, value=value)
    act(act="intox_who", guest_id=GUS)
    view = act(act="intox_fix", value="six jours sur sept").session.comptoir
    assert view.step == "opinion"
    act(act="opinion", value="pour", reason_index=0)
    act(act="comeback", index=2)
    revue.close(row)
    db.refresh(row)
    assert row.status == "closed"
    return user, row


def synthetic(db: Session, user: User, *, days_ago: float, title: str = "Le marché ouvre le dimanche",
              status: str = "closed", dossier_id: str = "d-echo", mode: str = "titre") -> RevueSession:
    when = datetime.now(UTC) - timedelta(days=days_ago)
    snapshot = {"topic": "food", "title_fr": title, "summary_fr": "Un marché ouvre."}
    events = [{"seq": 1, "at": when.isoformat(), "kind": "choice",
               "payload": {"kind": "dossier", "dossier_id": dossier_id, "mode": mode, "snapshot": snapshot}}]
    if status == "closed":
        events += [
            {"seq": 2, "at": when.isoformat(), "kind": "artifact",
             "payload": {"kind": "titre", "text_fr": "Le marché ouvre aussi le dimanche", "proof": "clean"}},
            {"seq": 3, "at": when.isoformat(), "kind": "closed",
             "payload": {"closing": {"kept": {"words": [{"fr": "le marché"}, {"fr": "ouvrir"}]}}}},
        ]
    row = RevueSession(id=uuid.uuid4(), user_id=user.id, week="2026-W47", dossier_id=dossier_id, plan={},
                       state={"events": events}, status=status, started_at=when - timedelta(minutes=8),
                       closed_at=when if status == "closed" else None)
    db.add(row)
    db.commit()
    return row


# ---------------------------------------------------------------------------
# 1 · REVUE_WORDS_IN_DECK_ENABLED
# ---------------------------------------------------------------------------


def _kept_yesterday(db: Session, user: User) -> int:
    yesterday = datetime.now(UTC) - timedelta(days=1)
    kept = keep_revue_word(db, user=user, term="la récolte", gloss="harvest",
                           sentence="Au marché, la récolte arrive le matin.",
                           met={"session_id": str(uuid.uuid4()), "dossier_id": "d-1", "place_id": "marche_aligre",
                                "place_label_fr": "Le marché d'Aligre", "week": "2026-W47"}, now=yesterday)
    db.commit()
    assert kept is not None
    return kept.word_id


def test_a_papier_word_kept_yesterday_is_in_todays_priority_set_and_the_directors_vocabulary(db, monkeypatch):
    user = make_user(db)
    word_id = _kept_yesterday(db, user)

    monkeypatch.setattr(settings, "REVUE_WORDS_IN_DECK_ENABLED", True)
    assert word_id in day_words.kept_waiting_ids(db, user)
    assert word_id in recent_kept_words(db, user_id=user.id)
    kept = director_vocabulary(db, user_id=user.id)["kept_words"]
    assert {"word": "la récolte", "gloss": "harvest", "example_fr": "Au marché, la récolte arrive le matin."} in kept


def test_with_the_deck_switch_off_a_papier_word_is_not_a_kept_word(db):
    user = make_user(db)
    word_id = _kept_yesterday(db, user)
    assert word_id not in day_words.kept_waiting_ids(db, user)
    assert word_id not in recent_kept_words(db, user_id=user.id)
    assert director_vocabulary(db, user_id=user.id)["kept_words"] == []


def test_the_words_a_played_papier_kept_open_the_next_deck(db, monkeypatch):
    user, _row = played_counter(db)
    assert day_words.kept_waiting_ids(db, user) == []
    monkeypatch.setattr(settings, "REVUE_WORDS_IN_DECK_ENABLED", True)
    assert day_words.kept_waiting_ids(db, user), "the close's kept words wait for the next deck"


# ---------------------------------------------------------------------------
# 2 · REVUE_ECHO_ENABLED — the record
# ---------------------------------------------------------------------------


def test_the_echo_of_a_counter_played_yesterday(db):
    user, row = played_counter(db)
    record = echo.echo_for(db, user.id, now=datetime.now(UTC) + timedelta(days=1))
    assert record is not None and record.session_id == str(row.id)
    assert record.desk == "comptoir" and record.desk_fr == "Au comptoir"
    assert record.headline_fr and record.rubric
    assert record.did == {"stance": "pour", "sentence_fr": "Je suis pour, parce que le marché est vivant."}
    assert [p["id"] for p in record.present] == [ROMY, MARGAUX, GUS]
    assert record.kept_words
    # The regulars' own memory (knowledge.remember), at most two, never Romy's.
    assert 1 <= len(record.regulars_remember) <= echo.MAX_REGULAR_FACTS
    assert all(r["id"] != ROMY and record.headline_fr in r["fr"] for r in record.regulars_remember)

    block = echo.director_block(record, now=datetime.now(UTC) + timedelta(days=1))
    assert block["when_fr"] == "hier" and block["instruction"] == echo.INSTRUCTION
    assert block["learner_did"]["stance"] == "pour"
    json.dumps(block, ensure_ascii=False)


def test_the_echo_of_a_headline(db):
    user = make_user(db)
    synthetic(db, user, days_ago=1)
    record = echo.echo_for(db, user.id)
    assert record is not None and record.desk == "titre"
    assert record.did == {"headline_fr": "Le marché ouvre aussi le dimanche"}
    assert record.kept_words == ["le marché", "ouvrir"]
    assert [p["id"] for p in record.present] == [ROMY]


def test_no_echo_older_than_three_days_unfinished_or_already_played(db):
    user = make_user(db)
    assert echo.echo_for(db, user.id) is None, "no Papier, no echo"
    synthetic(db, user, days_ago=4)
    assert echo.echo_for(db, user.id) is None, "older than three days"
    synthetic(db, user, days_ago=0.5, status="active")
    assert echo.echo_for(db, user.id) is None, "an unfinished Papier filed nothing"

    row = synthetic(db, user, days_ago=1)
    assert echo.echo_for(db, user.id) is not None
    scene = GraphicNovelScene(user_id=user.id, title="t", brief="b", cache_key="k", prompt_version="v",
                              image_model="m", image_quality="q", created_at=row.closed_at + timedelta(hours=1),
                              completed_at=row.closed_at + timedelta(hours=2))
    db.add(scene)
    db.commit()
    assert echo.echo_for(db, user.id) is None, "once: a scene written after it was played to its end"


def test_no_echo_of_a_sensitive_or_skipped_story(db):
    user = make_user(db)
    synthetic(db, user, days_ago=1, title="Un attentat à Lyon")
    assert echo.echo_for(db, user.id) is None, "a sensitive story"

    user = make_user(db)
    dossier_id = f"d-skip-{uuid.uuid4().hex[:6]}"
    db.add(RevueDossier(id=dossier_id, week="2026-W47", period="2026-W47", topic="politics", payload={},
                        source_hashes={}, checks={"comptoir": "skip"}, builder_version="t"))
    db.commit()
    synthetic(db, user, days_ago=1, title="Le budget 2027", dossier_id=dossier_id)
    assert echo.echo_for(db, user.id) is None, "the counter's desk skipped it"


def test_a_text_printed_unchecked_is_not_quoted(db):
    user = make_user(db)
    row = synthetic(db, user, days_ago=1)
    state = copy.deepcopy(row.state)
    state["events"][1]["payload"]["proof"] = "as_written"
    row.state = state
    flag_modified(row, "state")
    db.commit()
    record = echo.echo_for(db, user.id)
    assert record is not None and record.did == {}


# ---------------------------------------------------------------------------
# 2 · REVUE_ECHO_ENABLED — the scene's director
# ---------------------------------------------------------------------------


def _scene_context() -> dict:
    return {"learner": {"level": "A2"}, "kept_words": [], "consequences": [], "chapter": {"title_fr": "x"}}


def test_with_the_echo_switch_off_the_scene_prompt_is_byte_identical(db, monkeypatch):
    user, _row = played_counter(db)
    monkeypatch.setattr(echo, "echo_for", lambda *a, **k: pytest.fail("no read with the switch off"))
    context = _scene_context()
    before = json.dumps(living_story._prompt_payload(context), ensure_ascii=False, sort_keys=True)
    living_story._add_papier_echo(db, user, context, now=datetime.now(UTC) + timedelta(days=1))
    assert context == _scene_context()
    assert json.dumps(living_story._prompt_payload(context), ensure_ascii=False, sort_keys=True) == before


def test_with_the_echo_on_and_a_papier_yesterday_the_block_is_in_the_scene_prompt(db, monkeypatch):
    user, row = played_counter(db)
    monkeypatch.setattr(settings, "REVUE_ECHO_ENABLED", True)
    context = _scene_context()
    living_story._add_papier_echo(db, user, context, now=datetime.now(UTC) + timedelta(days=1))
    block = context[echo.CONTEXT_KEY]
    assert block["headline_fr"] and block["present"][0]["id"] == ROMY
    payload = json.dumps(living_story._prompt_payload(context), ensure_ascii=False)
    assert "papier_echo" in payload and "Je suis pour, parce que le marché est vivant." in payload
    # A shared page is written without the life: the echo is dropped, the day stays shareable.
    assert echo.CONTEXT_KEY in page_pool.DROPPED_KEYS
    assert echo.CONTEXT_KEY not in page_pool.shareable(context)

    later = _scene_context()
    living_story._add_papier_echo(db, user, later, now=datetime.now(UTC) + timedelta(days=4))
    assert echo.CONTEXT_KEY not in later, "older than three days: absent"


def test_with_the_echo_on_and_no_papier_the_context_is_unchanged(db, monkeypatch):
    user = make_user(db)
    monkeypatch.setattr(settings, "REVUE_ECHO_ENABLED", True)
    context = _scene_context()
    living_story._add_papier_echo(db, user, context)
    assert context == _scene_context()


# ---------------------------------------------------------------------------
# Integration 2026-11-22: a word kept by hand inside the Papier is a Papier word
# ---------------------------------------------------------------------------


def test_a_word_kept_by_hand_in_the_papier_is_kept_from_the_revue_with_the_sessions_reference(db):
    from sqlalchemy import select as sa_select

    from app.db.models.progress import UserVocabularyProgress
    from app.db.models.session import WordInteraction
    from app.services.revue import carte

    revue = RevueEncounter(db, FakeRevueProvider())
    revue.pictogram_provider = FakePictogramProvider()
    user = make_user(db, level="A2.1")
    user.native_language = "de"
    db.commit()
    row = revue.start(user, week=WEEK)
    item = (row.plan.get("vocabulary") or [])[0]
    term = f"{item['fr']}"
    lead = enc.load(row).dossier.lead_for("A2").fr
    kept = carte.keep_tapped_word(db, user=user, row=row, term=term, sentence=lead, surface=term)
    db.commit()
    assert kept is not None and kept["already_kept"] is False
    progress = db.scalars(sa_select(UserVocabularyProgress).where(
        UserVocabularyProgress.user_id == user.id, UserVocabularyProgress.word_id == kept["word_id"])).one()
    assert progress.provenance == "kept_from_revue"
    assert progress.provenance_ref == str(row.id)
    places = (progress.context or {}).get("places") or []
    assert places and places[0]["session_id"] == str(row.id) and places[0]["dossier_id"] == row.dossier_id
    interaction = db.scalars(sa_select(WordInteraction).where(
        WordInteraction.user_id == user.id, WordInteraction.word_id == kept["word_id"])).one()
    assert interaction.interaction_type == "kept_from_revue"
    again = carte.keep_tapped_word(db, user=user, row=row, term=term, sentence=lead, surface=term)
    assert again["already_kept"] is True
