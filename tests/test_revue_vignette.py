"""WP-120 phase B: minting the vignette and reading it back (``revue/vignette.py``, ``GET /revue/vignettes``).

The ring follows what the learner made; minting is idempotent per session; the read
composes week, place, ring, kept mark, the dossier's shared pictogram (or its topic
fallback) and the filed headline from the session's own state; the route hides behind
the Revue flag like every other Revue route.
"""

from __future__ import annotations

import uuid
from collections.abc import Generator, Iterator
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.config import settings
from app.db.models.revue_session import RevueSession
from app.db.models.revue_vignette import RevuePictogram, RevueVignette
from app.db.models.user import User
from app.main import create_app
from app.services.revue.pictogram import FakePictogramProvider, fallback_svg, validate_pictogram
from app.services.revue.vignette import mint, mint_for_close, ring_for, vignettes_for

PASSWORD = "securepass123"
TABLES = (RevueSession.__table__, RevuePictogram.__table__, RevueVignette.__table__)


@pytest.fixture(scope="module")
def vignette_tables(db_engine) -> Generator[None, None, None]:
    created = [table for table in TABLES if not inspect(db_engine).has_table(table.name)]
    for table in created:
        table.create(bind=db_engine, checkfirst=True)
    try:
        yield
    finally:
        for table in reversed(created):
            table.drop(bind=db_engine, checkfirst=True)


@pytest.fixture()
def db(db_session: Session, vignette_tables) -> Session:
    return db_session


def make_user(db: Session) -> User:
    user = User(id=uuid.uuid4(), email=f"vignette-{uuid.uuid4().hex[:10]}@example.com", hashed_password="x")
    db.add(user)
    db.commit()
    return user


def event(seq: int, event_kind: str, **payload) -> dict:
    return {"seq": seq, "at": datetime(2026, 10, 1, 9, tzinfo=UTC).isoformat(), "kind": event_kind, "payload": payload}


def closed_session(db: Session, user: User, *, dossier_id: str, topic: str = "food", headline: str | None = "Les prix au marché",
                   week: str = "2026-W40") -> RevueSession:
    events = [event(1, "choice", kind="dossier", snapshot={"id": dossier_id, "topic": topic, "title_fr": "Le marché du dimanche"})]
    if headline is not None:
        events.append(event(2, "closed", closing={"dispatch": {"headline_fr": headline, "contribution": [[0, 8]]}}))
    row = RevueSession(user_id=user.id, week=week, dossier_id=dossier_id, plan={},
                       state={"state_version": "revue-state-v1", "events": events}, status="closed")
    db.add(row)
    db.commit()
    return row


@pytest.mark.parametrize(
    ("make", "ring"),
    [("headline_choice", "headline"), ("headline_write", "headline"), ("reader_question", "question"),
     ("short_report", "report"), (None, "headline")],
)
def test_ring_follows_the_make_option(make: str | None, ring: str) -> None:
    assert ring_for(make) == ring


def test_mint_is_idempotent_per_session(db: Session) -> None:
    user = make_user(db)
    row = closed_session(db, user, dossier_id=f"d-{uuid.uuid4().hex[:8]}")
    kwargs = {"user_id": user.id, "session_id": row.id, "dossier_id": row.dossier_id, "week": row.week,
              "place_label_fr": "Le marché d'Aligre"}
    first = mint(db, ring="question", kept_contribution=True, **kwargs)
    db.commit()
    again = mint(db, ring="report", kept_contribution=False, **kwargs)
    assert again.id == first.id and again.ring == "question" and again.kept_contribution is True
    assert len(db.scalars(select(RevueVignette).where(RevueVignette.session_id == row.id)).all()) == 1
    with pytest.raises(ValueError):
        mint(db, ring="trophy", kept_contribution=False, **{**kwargs, "session_id": uuid.uuid4()})  # type: ignore[arg-type]


def test_mint_for_close_draws_the_pictogram_and_mints(db: Session) -> None:
    user = make_user(db)
    dossier = SimpleNamespace(id=f"d-{uuid.uuid4().hex[:8]}", topic="politics", vignette_object_fr="une urne")
    row = closed_session(db, user, dossier_id=dossier.id, topic="politics")
    provider = FakePictogramProvider()
    vignette = mint_for_close(db, row=row, dossier=dossier, make_option="reader_question", kept_contribution=True,
                              place_label_fr="L'hémicycle", provider=provider)
    db.commit()
    assert vignette is not None and vignette.ring == "question" and vignette.week == "2026-W40"
    assert len(provider.calls) == 1 and db.get(RevuePictogram, dossier.id) is not None
    # A second close (a retried request) neither draws nor mints again.
    assert mint_for_close(db, row=row, dossier=dossier, make_option="short_report", kept_contribution=False,
                          place_label_fr="ailleurs", provider=provider).id == vignette.id
    assert len(provider.calls) == 1


def test_mint_for_close_never_raises(db: Session) -> None:
    row = SimpleNamespace(id="not-a-uuid", user_id="nope", week="2026-W40")
    dossier = SimpleNamespace(id="x", topic="food", vignette_object_fr=None)
    assert mint_for_close(db, row=row, dossier=dossier, make_option=None, kept_contribution=False,  # type: ignore[arg-type]
                          place_label_fr="") is None
    db.rollback()


def test_vignettes_for_composes_each_stamp(db: Session) -> None:
    user, other = make_user(db), make_user(db)
    drawn_id, bare_id = f"d-{uuid.uuid4().hex[:8]}", f"d-{uuid.uuid4().hex[:8]}"
    drawn = closed_session(db, user, dossier_id=drawn_id, headline="Les prix au marché", week="2026-W40")
    bare = closed_session(db, user, dossier_id=bare_id, topic="sport", headline=None, week="2026-W41")
    closed_session(db, other, dossier_id=drawn_id)
    svg = validate_pictogram(FakePictogramProvider().draw(object_fr="un cageot", topic="food")).svg_normalised
    db.add(RevuePictogram(dossier_id=drawn_id, object_fr="un cageot", svg=svg, prompt_version="pictogram-v1"))
    mint(db, user_id=user.id, session_id=drawn.id, dossier_id=drawn_id, ring="question", kept_contribution=True,
         week="2026-W40", place_label_fr="Le marché d'Aligre")
    mint(db, user_id=user.id, session_id=bare.id, dossier_id=bare_id, ring="report", kept_contribution=False,
         week="2026-W41", place_label_fr="Un col des Alpes")
    db.commit()

    views = {view.dossier_id: view for view in vignettes_for(db, user.id)}
    assert set(views) == {drawn_id, bare_id}
    first = views[drawn_id]
    assert (first.week, first.place_label_fr, first.ring, first.kept_contribution) == (
        "2026-W40", "Le marché d'Aligre", "question", True)
    assert first.pictogram_svg == svg and first.headline_fr == "Les prix au marché"
    assert first.session_id == str(drawn.id)
    second = views[bare_id]
    assert second.pictogram_svg == fallback_svg("sport"), "no stored pictogram: the topic fallback, no provider call"
    assert second.headline_fr == "Le marché du dimanche", "no closing in the state: the dossier's title"
    assert vignettes_for(db, other.id) == []


# -- the route ------------------------------------------------------------------


@pytest.fixture()
def api(db_session: Session, vignette_tables) -> Generator[TestClient, None, None]:
    app = create_app()

    def override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client


def login(client: TestClient) -> tuple[dict[str, str], str]:
    email = f"vignette-{uuid.uuid4().hex[:10]}@example.com"
    client.post("/api/v1/auth/register",
                json={"email": email, "password": PASSWORD, "target_language": "fr", "native_language": "de"})
    response = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}, email


def test_route_is_404_while_the_flag_is_off(api: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "REVUE_ENABLED", False)
    assert api.get("/api/v1/revue/vignettes").status_code == 404
    headers, _ = login(api)
    assert api.get("/api/v1/revue/vignettes", headers=headers).status_code == 404


def test_route_lists_the_learners_vignettes_when_on(api: TestClient, db_session: Session, vignette_tables, monkeypatch) -> None:
    monkeypatch.setattr(settings, "REVUE_ENABLED", True)
    assert api.get("/api/v1/revue/vignettes").status_code == 401
    headers, email = login(api)
    empty = api.get("/api/v1/revue/vignettes", headers=headers)
    assert empty.status_code == 200 and empty.json() == {"vignettes": []}

    user = db_session.scalar(select(User).where(User.email == email))
    row = closed_session(db_session, user, dossier_id=f"d-{uuid.uuid4().hex[:8]}", topic="nature")
    mint(db_session, user_id=user.id, session_id=row.id, dossier_id=row.dossier_id, ring="headline",
         kept_contribution=True, week=row.week, place_label_fr="Les vignes du Beaujolais")
    db_session.commit()

    response = api.get("/api/v1/revue/vignettes", headers=headers)
    assert response.status_code == 200, response.text
    [vignette] = response.json()["vignettes"]
    assert set(vignette) == {"id", "session_id", "dossier_id", "week", "place_label_fr", "ring", "kept_contribution",
                             "pictogram_svg", "headline_fr", "minted_at"}
    assert vignette["ring"] == "headline" and vignette["kept_contribution"] is True
    assert vignette["pictogram_svg"] == fallback_svg("nature")
    assert vignette["headline_fr"] == "Les prix au marché"
