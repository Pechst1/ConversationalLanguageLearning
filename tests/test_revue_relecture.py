"""WP-121 B: La Relecture — re-answer your own Papier's question six weeks later.

* eligibility (clock shim): five weeks after close no, six weeks yes; a Papier without a
  kept question or a written headline never; once re-read, never again;
* the offer is the oldest eligible Papier;
* the answer is stored once in ``revue_relectures`` and answered with the pair: the old
  answer and the new one, the rubric's register/grammar spans, Romy's one line, no score;
* La Carte's pins carry «eligible» / «read»; the routes hide behind the Revue flag.
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
from app.api.v1.endpoints.revue_relecture import get_relecture_scorer
from app.config import settings
from app.db.models.revue_relecture import RevueRelecture
from app.db.models.revue_session import RevueSession
from app.db.models.revue_vignette import RevuePictogram, RevueVignette
from app.db.models.user import User
from app.main import create_app
from app.services.revue import carte, grading, relecture
from app.services.revue.relecture import RelectureError

PASSWORD = "securepass123"
TABLES = (RevueSession.__table__, RevuePictogram.__table__, RevueVignette.__table__, RevueRelecture.__table__)
CLOSED = datetime(2026, 8, 20, 10, tzinfo=UTC)
QUESTION = "Est-ce que les prix au marché sont plus bas qu'au supermarché ?"
ALIGRE = {"lat": 48.849, "lon": 2.378, "precision": "exact", "label_fr": "Place d'Aligre et marché Beauvau, Paris 12e"}


@pytest.fixture(scope="module")
def relecture_tables(db_engine) -> Generator[None, None, None]:
    created = [table for table in TABLES if not inspect(db_engine).has_table(table.name)]
    for table in created:
        table.create(bind=db_engine, checkfirst=True)
    try:
        yield
    finally:
        for table in reversed(created):
            table.drop(bind=db_engine, checkfirst=True)


@pytest.fixture()
def db(db_session: Session, relecture_tables) -> Session:
    return db_session


def make_user(db: Session) -> User:
    user = User(id=uuid.uuid4(), email=f"relue-{uuid.uuid4().hex[:10]}@example.com", hashed_password="x")
    db.add(user)
    db.commit()
    return user


def event(seq: int, event_kind: str, **payload) -> dict:
    return {"seq": seq, "at": CLOSED.isoformat(), "kind": event_kind, "payload": payload}


def papier(db: Session, user: User, *, closed_at: datetime = CLOSED, question: str | None = QUESTION,
           artifact: dict | None = None, week: str = "2026-W34") -> RevueSession:
    place = {"id": "marche_aligre", "name_fr": "Le marché d'Aligre, un matin", "brief": "", "known": False, "geo": ALIGRE}
    snapshot = {"id": f"d-{uuid.uuid4().hex[:8]}", "topic": "food", "title_fr": "Les prix au marché",
                "summary_fr": "Les prix des fruits montent.", "places": [place]}
    if artifact is None and question:
        artifact = {"kind": "reader_question", "text_fr": question, "learner_fr": "les prix au marché plus bas ?",
                    "contribution": []}
    events = [event(1, "choice", kind="dossier", dossier_id=snapshot["id"], snapshot=snapshot),
              event(2, "turn_learner", text_fr="Les prix au marché sont plus bas ?")]
    if artifact:
        events.append(event(3, "artifact", **artifact))
    events.append(event(4, "closed", closing={
        "romy_line_fr": "C'est noté.",
        "dispatch": {"headline_fr": "Les prix au marché", "contribution": [], "body_fr": [], "kicker_fr": "",
                     "byline_fr": "", "sources": []},
        "kept": {"words": [], "claims": [{"id": "c1", "kind": "fact", "fr": "Les fruits coûtent 8 % plus cher qu'en 2025."}]},
        "question_kept_fr": question,
    }))
    row = RevueSession(
        user_id=user.id, week=week, dossier_id=snapshot["id"],
        plan={"stage": {"place_id": "marche_aligre", "plate_url": "/assets/serial/locations/marche_canal.webp"},
              "learner": {"band": "A2"},
              "vocabulary": [{"fr": "la récolte", "claim_id": "c1"}, {"fr": "le prix", "claim_id": "c1"}]},
        state={"state_version": "revue-state-v1", "events": events},
        status="closed",
        closed_at=closed_at,
    )
    db.add(row)
    db.commit()
    return row


def test_eligible_six_weeks_after_close_not_five(db: Session) -> None:
    user = make_user(db)
    row = papier(db, user)
    assert relecture.eligible(row, now=CLOSED + timedelta(weeks=5)) is False
    assert relecture.eligible(row, now=CLOSED + timedelta(weeks=6)) is True
    assert relecture.offer(db, user, now=CLOSED + timedelta(weeks=5)) is None
    offer = relecture.offer(db, user, now=CLOSED + timedelta(weeks=6))
    assert offer is not None and offer.session_id == str(row.id)
    assert offer.kind == "question" and offer.prompt_fr == QUESTION and offer.week == "2026-W34"


def test_a_papier_without_a_question_or_a_written_headline_is_never_eligible(db: Session) -> None:
    user = make_user(db)
    plain = papier(db, user, question=None, artifact={"kind": "headline_choice", "text_fr": "Les prix montent"})
    assert relecture.eligible(plain, now=CLOSED + timedelta(weeks=12)) is False
    written = papier(db, user, question=None,
                     artifact={"kind": "headline_write", "text_fr": "Les fruits plus chers", "learner_fr": "Les fruits plus chers"})
    assert relecture.eligible(written, now=CLOSED + timedelta(weeks=6)) is True
    offer = relecture.offer(db, user, now=CLOSED + timedelta(weeks=6))
    assert offer.kind == "headline" and offer.session_id == str(written.id)


def test_the_offer_is_the_oldest_eligible_and_never_twice(db: Session) -> None:
    user = make_user(db)
    old = papier(db, user, closed_at=CLOSED - timedelta(weeks=2))
    new = papier(db, user)
    now = CLOSED + timedelta(weeks=7)
    assert relecture.offer(db, user, now=now).session_id == str(old.id)
    relecture.answer(db, user, str(old.id), answer_fr="Non, au marché c'est plus cher.", now=now)
    db.commit()
    assert relecture.offer(db, user, now=now).session_id == str(new.id)
    with pytest.raises(RelectureError) as twice:
        relecture.answer(db, user, str(old.id), answer_fr="Encore une fois.", now=now)
    assert twice.value.code == "relecture_done"
    with pytest.raises(RelectureError) as early:
        relecture.answer(db, user, str(new.id), answer_fr="Trop tôt.", now=CLOSED + timedelta(weeks=5))
    assert early.value.code == "relecture_not_yet"
    assert db.scalar(select(RevueRelecture).where(RevueRelecture.session_id == old.id)).mode == "text"


def test_the_pair_shows_both_answers_the_flags_and_one_line_without_a_score(db: Session) -> None:
    user = make_user(db)
    row = papier(db, user)
    pair = relecture.answer(db, user, str(row.id), answer_fr="Vous savez, le récolte est petite, donc les prix montent.",
                            now=CLOSED + timedelta(weeks=6), scorer=grading.FakeRubricScorer())
    db.commit()
    assert pair.then.label_fr == "Semaine 34" and pair.then.text_fr == "les prix au marché plus bas ?"
    assert pair.now.label_fr == "Aujourd'hui"
    flagged = {(pair.now.text_fr[s.start:s.end], s.flag) for s in pair.now.spans}
    assert ("Vous", "register") in flagged and ("savez", "register") in flagged
    assert ("le récolte", "grammar") in flagged
    assert pair.romy_line_fr == relecture.ROMY_LINES["register"]["A"]
    dumped = pair.model_dump()
    assert "score" not in str(dumped) and "outcome" not in str(dumped)
    assert relecture.read(db, user, str(row.id)) == pair


def test_romy_notices_one_thing_by_flag_then_by_change() -> None:
    span = relecture.RelectureSpan(start=0, end=3, flag="grammar")
    line = relecture.romy_line(band="B1", week="2026-W41", then_spans=[span], now_spans=[], then_fr="a", now_fr="b")
    assert line == "Ce que j'avais souligné en semaine 41, tu ne le fais plus."
    longer = relecture.romy_line(band="A1", week="2026-W41", then_spans=[], now_spans=[], then_fr="oui",
                                 now_fr="oui, parce que les fruits viennent de loin")
    assert longer == "Tu en dis plus qu'en semaine 41."


def test_carte_pins_carry_the_relecture_marks(db: Session, monkeypatch) -> None:
    user = make_user(db)
    waiting = papier(db, user, closed_at=datetime.now(UTC) - timedelta(weeks=1))
    ready = papier(db, user, closed_at=datetime.now(UTC) - timedelta(weeks=7))
    read = papier(db, user, closed_at=datetime.now(UTC) - timedelta(weeks=8))
    relecture.answer(db, user, str(read.id), answer_fr="Je crois que non.")
    db.commit()
    marks = {pin.session_id: pin.relecture for pin in carte.pins_for(db, user).pins}
    assert marks[str(waiting.id)] is None
    assert marks[str(ready.id)].state == "eligible"
    assert marks[str(read.id)].state == "read" and marks[str(read.id)].read_at


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@pytest.fixture()
def api(db_session: Session, relecture_tables) -> Generator[TestClient, None, None]:
    app = create_app()

    def override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_relecture_scorer] = lambda: grading.FakeRubricScorer()
    with TestClient(app) as client:
        yield client


def login(client: TestClient) -> tuple[dict[str, str], str]:
    email = f"relue-{uuid.uuid4().hex[:10]}@example.com"
    client.post("/api/v1/auth/register",
                json={"email": email, "password": PASSWORD, "target_language": "fr", "native_language": "de"})
    response = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}, email


def test_routes_offer_answer_and_read_the_pair(api: TestClient, db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "REVUE_ENABLED", False)
    assert api.get("/api/v1/revue/relecture/offer").status_code == 404
    monkeypatch.setattr(settings, "REVUE_ENABLED", True)
    headers, email = login(api)
    assert api.get("/api/v1/revue/relecture/offer", headers=headers).json() == {"offer": None}
    user = db_session.scalar(select(User).where(User.email == email))
    row = papier(db_session, user)
    monkeypatch.setattr(relecture, "_now", lambda: CLOSED + timedelta(weeks=5))
    assert api.get("/api/v1/revue/relecture/offer", headers=headers).json() == {"offer": None}
    early = api.post(f"/api/v1/revue/relecture/{row.id}", headers=headers, json={"answer_fr": "Oui."})
    assert early.status_code == 409 and early.json()["detail"] == "relecture_not_yet"

    monkeypatch.setattr(relecture, "_now", lambda: CLOSED + timedelta(weeks=6, days=1))
    offer = api.get("/api/v1/revue/relecture/offer", headers=headers).json()["offer"]
    assert offer["session_id"] == str(row.id) and offer["prompt_fr"] == QUESTION
    posted = api.post(f"/api/v1/revue/relecture/{row.id}", headers=headers,
                      json={"answer_fr": "Non, au marché les fruits sont plus chers.", "mode": "voice"})
    assert posted.status_code == 200, posted.text
    body = posted.json()
    assert set(body) == {"session_id", "offer", "then", "now", "romy_line_fr", "asked_at"}
    assert body["now"]["text_fr"] == "Non, au marché les fruits sont plus chers."
    assert api.get(f"/api/v1/revue/relecture/{row.id}", headers=headers).json() == body
    twice = api.post(f"/api/v1/revue/relecture/{row.id}", headers=headers, json={"answer_fr": "Encore."})
    assert twice.status_code == 409 and twice.json()["detail"] == "relecture_done"
    assert api.get("/api/v1/revue/relecture/offer", headers=headers).json() == {"offer": None}
