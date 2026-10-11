"""WP-121 A: Le Palais de mémoire — the kept words of a Papier, reviewed where they were met.

* A.0 ``encounter.close`` files every ``RvKept.words[]`` in the SRS (``keep_revue_word``)
  with ``met.source="revue"`` and the place; idempotent; a word used and judged correct
  starts one step ahead.
* A.1 ``words_due_by_place`` groups due cards by the Papier place, the most recent wins.
* A.2 the carte payload carries ``due_words`` per pin (the place's newest pin) and ``due_total``.
* A.3 ``GET /revue/carte/review/{place_id}`` returns the words with the line that carried
  them and the items (match_pairs from four words, a word bank / unscramble below); the
  grade is checked on the server and schedules through ``EnhancedSRSService``; when the
  place's words are graded, its dot is gone.
"""

from __future__ import annotations

import uuid
from collections.abc import Generator, Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.config import settings
from app.db.models.npc import NPC, NPCMemory
from app.db.models.progress import UserVocabularyProgress
from app.db.models.revue_session import RevueSession
from app.db.models.revue_vignette import RevuePictogram, RevueVignette
from app.db.models.story import Story
from app.db.models.user import User
from app.main import create_app
from app.services.kept_words import keep_revue_word, place_line_fr, words_due_by_place
from app.services.revue import carte
from app.services.revue import encounter as enc
from app.services.revue.carte import grade_review, pins_for, review_for
from app.services.revue.encounter import FakeRevueProvider, RevueEncounter
from app.services.revue.evergreen import evergreens_for_week

PASSWORD = "securepass123"
TABLES = (Story.__table__, NPC.__table__, NPCMemory.__table__, RevueSession.__table__,
          RevuePictogram.__table__, RevueVignette.__table__)
ALIGRE = {"lat": 48.849, "lon": 2.378, "precision": "exact", "label_fr": "Place d'Aligre et marché Beauvau, Paris 12e"}
NOW = datetime(2026, 10, 3, 9, tzinfo=UTC)


@pytest.fixture(scope="module")
def palais_tables(db_engine) -> Generator[None, None, None]:
    created = [table for table in TABLES if not inspect(db_engine).has_table(table.name)]
    for table in created:
        table.create(bind=db_engine, checkfirst=True)
    try:
        yield
    finally:
        for table in reversed(created):
            table.drop(bind=db_engine, checkfirst=True)


@pytest.fixture()
def db(db_session: Session, palais_tables) -> Session:
    return db_session


@pytest.fixture(autouse=True)
def evergreens_only(monkeypatch) -> None:
    monkeypatch.setattr(enc, "available_dossiers", evergreens_for_week)


def make_user(db: Session) -> User:
    user = User(id=uuid.uuid4(), email=f"palais-{uuid.uuid4().hex[:10]}@example.com", hashed_password="x",
                cefr_estimate="A2.1", native_language="de")
    db.add(user)
    db.commit()
    return user


def event(seq: int, event_kind: str, **payload) -> dict:
    return {"seq": seq, "at": datetime(2026, 10, 1, 9, tzinfo=UTC).isoformat(), "kind": event_kind, "payload": payload}


def papier(db: Session, user: User, *, place_id: str = "marche_aligre", closed_at: datetime | None = None,
           romy_line: str = "Au marché, la récolte arrive le matin.", vocabulary: list[dict] | None = None) -> RevueSession:
    place = {"id": place_id, "name_fr": "Le marché d'Aligre, un matin", "brief": "", "known": False, "geo": ALIGRE}
    snapshot = {"id": f"d-{uuid.uuid4().hex[:8]}", "topic": "food", "title_fr": "Les prix au marché", "places": [place]}
    events = [
        event(1, "choice", kind="dossier", dossier_id=snapshot["id"], snapshot=snapshot),
        event(2, "turn_romy", beat="facts", role="reply", text_fr=romy_line),
        event(3, "closed", closing={
            "romy_line_fr": "C'est noté.",
            "dispatch": {"headline_fr": "Les fruits coûtent plus cher", "contribution": [], "body_fr": [],
                         "kicker_fr": "", "byline_fr": "", "sources": []},
            "kept": {"words": [], "claims": []},
            "question_kept_fr": None,
        }),
    ]
    row = RevueSession(
        user_id=user.id, week="2026-W40", dossier_id=snapshot["id"],
        plan={"stage": {"place_id": place_id, "plate_url": "/assets/serial/locations/marche_canal.webp"},
              "vocabulary": vocabulary or [{"fr": "un étal", "claim_id": "c1"}, {"fr": "le prix", "claim_id": "c2"}]},
        state={"state_version": "revue-state-v1", "events": events},
        status="closed",
        closed_at=closed_at or datetime(2026, 10, 1, 10, tzinfo=UTC),
    )
    db.add(row)
    db.commit()
    return row


def keep(db: Session, user: User, row: RevueSession, term: str, gloss: str, sentence: str, *,
         place_id: str = "marche_aligre", now: datetime = NOW, used: bool = False):
    result = keep_revue_word(db, user=user, term=term, gloss=gloss, sentence=sentence, used_correctly=used, now=now, met={
        "source": "revue", "session_id": str(row.id), "dossier_id": row.dossier_id, "place_id": place_id,
        "place_label_fr": ALIGRE["label_fr"], "place_name_fr": "Le marché d'Aligre, un matin", "week": "2026-W41",
    })
    db.commit()
    return result


def card(db: Session, user: User, word_id: int) -> UserVocabularyProgress:
    return db.scalar(select(UserVocabularyProgress).where(UserVocabularyProgress.user_id == user.id,
                                                           UserVocabularyProgress.word_id == word_id))


# ---------------------------------------------------------------------------
# A.0
# ---------------------------------------------------------------------------


def test_close_files_the_kept_words_and_a_used_correct_word_starts_one_step_ahead(db: Session) -> None:
    user = make_user(db)
    revue = RevueEncounter(db, FakeRevueProvider())
    row = revue.start(user, "2026-W40", dossier_id="evergreen-marche-du-dimanche")
    revue.turn(row, "D'accord, je t'aide.")
    revue.turn(row, "Il y a beaucoup de marchés à Paris.")
    _, closing = revue.close(row)
    used = {w.fr for w in closing.kept.words if w.used}
    assert used == {"marchés"}

    cards = db.scalars(select(UserVocabularyProgress).where(UserVocabularyProgress.user_id == user.id)).all()
    assert len(cards) == 5
    by_word = {c.word.word: c for c in cards}
    ahead = by_word["marchés"]
    assert ahead.reps == 1 and ahead.provenance == "kept_from_revue"
    assert enc_aware(ahead.due_at) > datetime.now(UTC)
    for word, other in by_word.items():
        place = other.context["places"][-1]
        assert place["source"] == "revue" and place["place_id"] == "marche_aligre"
        assert place["session_id"] == str(row.id) and place["week"] == "2026-W40"
        assert place["sentence_fr"], "the claim the word was kept with"
        if word != "marchés":
            assert other.reps == 0
    revue.close(row)
    assert len(db.scalars(select(UserVocabularyProgress).where(UserVocabularyProgress.user_id == user.id)).all()) == 5


def enc_aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def test_keeping_twice_in_one_session_is_a_no_op_and_an_existing_card_keeps_its_schedule(db: Session) -> None:
    user = make_user(db)
    row = papier(db, user)
    first = keep(db, user, row, "la récolte", "die Ernte", "La récolte est bonne.")
    again = keep(db, user, row, "la récolte", "die Ernte", "La récolte est bonne.", used=True)
    assert first.created and not again.created and again.already and not again.stepped_ahead
    progress = card(db, user, first.word_id)
    assert progress.reps == 0 and len(progress.context["places"]) == 1


# ---------------------------------------------------------------------------
# A.1
# ---------------------------------------------------------------------------


def test_words_due_by_place_groups_and_a_word_belongs_to_its_most_recent_place(db: Session) -> None:
    user = make_user(db)
    aligre, canal = papier(db, user), papier(db, user, place_id="canal")
    kept = keep(db, user, aligre, "la récolte", "die Ernte", "La récolte est bonne.", now=NOW - timedelta(days=9))
    keep(db, user, aligre, "un étal", "ein Stand", "Chaque étal ouvre à huit heures.", now=NOW - timedelta(days=9))
    keep(db, user, canal, "la récolte", "die Ernte", "Au canal, on parle de la récolte.", place_id="canal",
         now=NOW - timedelta(days=2))
    grouped = words_due_by_place(db, user_id=user.id, now=NOW)
    assert [w.word for w in grouped["marche_aligre"]] == ["un étal"]
    assert [w.word for w in grouped["canal"]] == ["la récolte"]
    assert grouped["canal"][0].sentence_fr == "Au canal, on parle de la récolte."
    assert place_line_fr(card(db, user, kept.word_id).context) == "vu au marché d'Aligre, semaine 41"
    # Not due yet → not on the map.
    progress = card(db, user, kept.word_id)
    progress.due_at = NOW + timedelta(days=3)
    db.commit()
    assert "canal" not in words_due_by_place(db, user_id=user.id, now=NOW)


# ---------------------------------------------------------------------------
# A.2
# ---------------------------------------------------------------------------


def test_the_carte_payload_counts_due_words_on_the_places_newest_pin(db: Session) -> None:
    user = make_user(db)
    older = papier(db, user, closed_at=datetime(2026, 9, 1, tzinfo=UTC))
    newer = papier(db, user)
    keep(db, user, older, "la récolte", "die Ernte", "La récolte est bonne.", now=datetime.now(UTC) - timedelta(hours=1))
    keep(db, user, newer, "un étal", "ein Stand", "Chaque étal ouvre tôt.", now=datetime.now(UTC) - timedelta(hours=1))
    view = pins_for(db, user)
    counts = {pin.session_id: pin.due_words for pin in view.pins}
    assert counts == {str(newer.id): 2, str(older.id): 0}
    assert view.due_total == 2
    assert all(pin.place_id == "marche_aligre" for pin in view.pins)


# ---------------------------------------------------------------------------
# A.3
# ---------------------------------------------------------------------------


def test_two_due_words_at_aligre_are_reviewed_and_the_dot_goes(db: Session) -> None:
    user = make_user(db)
    row = papier(db, user)
    before = datetime.now(UTC) - timedelta(hours=1)
    keep(db, user, row, "la récolte", "die Ernte", "Cette année, la récolte des pommes est petite.", now=before)
    keep(db, user, row, "un étal", "ein Stand", "Chaque étal du marché ouvre à huit heures.", now=before)

    review = review_for(db, user, "marche_aligre")
    assert review.plate_url == "/assets/serial/locations/marche_canal.webp"
    assert review.headline_fr == "Les fruits coûtent plus cher"
    assert {w.word for w in review.words} == {"la récolte", "un étal"}
    recolte = next(w for w in review.words if w.word == "la récolte")
    assert recolte.speaker_id == "romy_tremblay" and "récolte" in recolte.line_fr
    assert recolte.sentence_fr == "Cette année, la récolte des pommes est petite."
    etal = next(w for w in review.words if w.word == "un étal")
    assert etal.line_fr == etal.sentence_fr, "no thread line carried it: the claim stands in"
    assert [item.task_type for item in review.items] == ["word_bank", "word_bank"]
    item = review.items[0]
    assert item.answer_key and item.answer_key["digests"]
    assert len(item.options) == len(carte._chunk(review.words[0].sentence_fr, review.words[0].word)) + 1

    for index, item in enumerate(review.items):
        word = next(w for w in review.words if w.progress_id == item.progress_ids[0])
        chunk = carte._chunk(word.sentence_fr, word.word)
        by_text = {}
        for option in item.options:
            by_text.setdefault(option.text_fr, []).append(option.id)
        tiles = [by_text[text].pop(0) for text in chunk]
        graded = grade_review(db, user, "marche_aligre", item_id=item.id, tile_ids=tiles)
        db.commit()
        [result] = graded.results
        assert result.correct and result.rating == 2
        assert graded.remaining == 1 - index
    progress = db.scalars(select(UserVocabularyProgress).where(UserVocabularyProgress.user_id == user.id)).all()
    assert all(p.reps == 1 and enc_aware(p.due_at) > datetime.now(UTC) for p in progress)
    view = pins_for(db, user)
    assert view.due_total == 0 and view.pins[0].due_words == 0


def test_four_words_are_matched_and_a_wrong_first_pairing_counts_against_its_word(db: Session) -> None:
    user = make_user(db)
    row = papier(db, user)
    before = datetime.now(UTC) - timedelta(hours=1)
    for term, gloss in [("la récolte", "die Ernte"), ("un étal", "ein Stand"), ("le prix", "der Preis"), ("augmenter", "steigen")]:
        keep(db, user, row, term, gloss, f"On parle de {term} au marché.", now=before)
    review = review_for(db, user, "marche_aligre")
    [item] = review.items
    assert item.task_type == "match_pairs" and len(item.options) == 8
    pairs = carte._items_for(user.id, [w.model_dump() | {"audio_url": None} for w in review.words], {})[0]["_order"]
    first, second = pairs[0:2], pairs[2:4]
    attempts = [first[0], second[1], *first, *second, *pairs[4:]]  # the first word's first pairing is wrong
    graded = grade_review(db, user, "marche_aligre", item_id=item.id, tile_ids=attempts)
    outcomes = {r.progress_id: (r.correct, r.rating) for r in graded.results}
    assert outcomes[item.progress_ids[0]] == (False, 1)
    assert all(outcomes[pid] == (True, 2) for pid in item.progress_ids[1:])
    assert graded.remaining == 0


def test_a_wrong_order_is_graded_on_the_server_and_an_unknown_item_is_refused(db: Session) -> None:
    user = make_user(db)
    row = papier(db, user)
    keep(db, user, row, "la récolte", "die Ernte", "Cette année, la récolte des pommes est petite.",
         now=datetime.now(UTC) - timedelta(hours=1))
    [item] = review_for(db, user, "marche_aligre").items
    graded = grade_review(db, user, "marche_aligre", item_id=item.id, tile_ids=[o.id for o in item.options])
    assert graded.results[0].correct is False and graded.results[0].rating == 1
    with pytest.raises(carte.ReviewError):
        grade_review(db, user, "marche_aligre", item_id=f"w:{uuid.uuid4()}", tile_ids=[])


# ---------------------------------------------------------------------------
# The routes
# ---------------------------------------------------------------------------


@pytest.fixture()
def api(db_session: Session, palais_tables) -> Generator[TestClient, None, None]:
    app = create_app()

    def override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client


def login(client: TestClient) -> tuple[dict[str, str], str]:
    email = f"palais-{uuid.uuid4().hex[:10]}@example.com"
    client.post("/api/v1/auth/register",
                json={"email": email, "password": PASSWORD, "target_language": "fr", "native_language": "de"})
    response = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}, email


def test_review_routes_answer_the_words_and_grade_them(api: TestClient, db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "REVUE_ENABLED", False)
    assert api.get("/api/v1/revue/carte/review/marche_aligre").status_code == 404
    monkeypatch.setattr(settings, "REVUE_ENABLED", True)
    headers, email = login(api)
    user = db_session.scalar(select(User).where(User.email == email))
    row = papier(db_session, user)
    keep(db_session, user, row, "la récolte", "die Ernte", "Cette année, la récolte des pommes est petite.",
         now=datetime.now(UTC) - timedelta(hours=1))
    carte.invalidate(user.id)
    body = api.get("/api/v1/revue/carte", headers=headers).json()
    assert body["due_total"] == 1 and body["pins"][0]["due_words"] == 1

    review = api.get("/api/v1/revue/carte/review/marche_aligre", headers=headers)
    assert review.status_code == 200, review.text
    payload = review.json()
    assert payload["words"][0]["line_fr"] == "Au marché, la récolte arrive le matin."
    item = payload["items"][0]
    by_text = {o["text_fr"]: o["id"] for o in item["options"]}
    tiles = [by_text[t] for t in carte._chunk(payload["words"][0]["sentence_fr"], "la récolte")]
    graded = api.post("/api/v1/revue/carte/review/marche_aligre/grade", headers=headers,
                      json={"item_id": item["id"], "tile_ids": tiles})
    assert graded.status_code == 200, graded.text
    assert graded.json()["remaining"] == 0 and graded.json()["results"][0]["correct"] is True
    again = api.post("/api/v1/revue/carte/review/marche_aligre/grade", headers=headers,
                     json={"item_id": item["id"], "tile_ids": tiles})
    assert again.status_code == 409
    assert api.get("/api/v1/revue/carte", headers=headers).json()["due_total"] == 0
