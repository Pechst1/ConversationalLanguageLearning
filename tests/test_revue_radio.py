"""WP-122 A «La Radio» (``app/services/revue/radio.py``, ``/revue/radio/*``).

* the bulletin's shape — lede, three claims, the guest, the sign-off — and 45–60 s, with a
  fake TTS (no network), for every evergreen and the grève at every band;
* caching: a second bulletin makes no TTS call; a second learner gets a copy, no call;
* interpretations carry «d'après»; the dictée is the shortest spoken fact;
* the dictée goes through the journey's dictation grader (met / accents / not yet);
* the rotation skips heard dossiers, falls back to the evergreen, one a day;
* the routes 404 while either flag is off and answer when both are on.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.config import settings
from app.db.models.line_audio import LineAudioClip
from app.db.models.pilot_event import PilotEvent
from app.db.models.user import User
from app.main import create_app
from app.services.episode_audio import SpokenLine, spec_for
from app.services.line_audio import LINE_AUDIO_EVENT_TYPE
from app.services.revue import radio
from app.services.revue.evergreen import evergreens_for_week, load_evergreens

PASSWORD = "securepass123"
GREVE = "evergreen-greve-transports"
WEEK = "2026-W40"


class FakeTts:
    """``speak_text``'s signature; counts calls and returns a few bytes."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def __call__(self, provider, *, text, voice, character_id, band, model) -> SpokenLine:  # noqa: ANN001
        self.calls.append({"text": text, "voice": voice, "character_id": character_id, "band": band})
        return SpokenLine(audio=b"ID3fake" + text.encode()[:8], model=model, spec=spec_for(character_id, band, model=model))


def greve():
    return next(dossier for dossier in load_evergreens() if dossier.id == GREVE)


def make_user(db: Session) -> User:
    user = User(id=uuid.uuid4(), email=f"radio-{uuid.uuid4().hex[:10]}@example.com", hashed_password="x", cefr_estimate="A2.1")
    db.add(user)
    db.commit()
    return user


# ---------------------------------------------------------------------------
# The bulletin
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("band", ["A1", "A2", "B1", "B2"])
def test_every_evergreen_bulletin_is_45_to_60_seconds(band: str) -> None:
    for dossier in load_evergreens():
        bulletin = radio.bulletin_script(dossier, band, week=WEEK)
        assert radio.MIN_SECONDS <= bulletin.seconds <= radio.MAX_SECONDS, (dossier.id, band, bulletin.seconds)


def test_bulletin_shape_with_a_fake_tts(db_session: Session) -> None:
    user = make_user(db_session)
    tts = FakeTts()
    bulletin = radio.bulletin_for(db_session, greve(), "A2", tts=tts, owner_id=user.id, provider=object(), week=WEEK)
    roles = [line.role for line in bulletin.lines]
    assert roles[0] == "lede" and roles[-2:] == ["guest", "signoff"]
    assert roles.count("claim") == 3
    assert bulletin.lines[0].speaker == radio.ROMY_ID
    assert bulletin.lines[-1].text_fr == "C'était Le Papier, semaine 40."
    # The work topic's guest (Marin), with his authored line and his own voice.
    guest = next(line for line in bulletin.lines if line.role == "guest")
    assert guest.speaker == "marin_leveque"
    assert guest.voice == "onyx" and bulletin.lines[0].voice == "nova"
    # The lede: whole sentences, at most the band's reading target ÷ 2 (90 / 2 at A2).
    assert len(bulletin.lines[0].text_fr.split()) <= 45 and bulletin.lines[0].text_fr.endswith(".")
    assert 45 <= bulletin.seconds <= 60
    assert bulletin.audio == "ready"
    assert len(tts.calls) == len(bulletin.lines)
    assert all(line.clip_url and line.clip_url.startswith("/api/v1/daily-journeys/line-audio/") for line in bulletin.lines)
    assert {call["band"] for call in tts.calls} == {"A2"}
    # Every paid line is priced on the WP-91 ledger, surface revue_radio.
    rows = list(db_session.scalars(select(PilotEvent).where(PilotEvent.user_id == user.id, PilotEvent.event_type == LINE_AUDIO_EVENT_TYPE)))
    assert len(rows) == len(bulletin.lines) and {row.payload["surface"] for row in rows} == {"revue_radio"}


def test_second_call_makes_no_tts_call_and_a_second_learner_gets_a_copy(db_session: Session) -> None:
    first, second = make_user(db_session), make_user(db_session)
    tts = FakeTts()
    one = radio.bulletin_for(db_session, greve(), "B1", tts=tts, owner_id=first.id, provider=object(), week=WEEK)
    spoken = len(tts.calls)
    again = radio.bulletin_for(db_session, greve(), "B1", tts=tts, owner_id=first.id, provider=object(), week=WEEK)
    assert len(tts.calls) == spoken, "a replay makes no call"
    assert again.cached_lines == len(again.lines) and again.synthesized_lines == 0 and again.cost_usd == 0
    assert [line.clip_url for line in again.lines] == [line.clip_url for line in one.lines]
    other = radio.bulletin_for(db_session, greve(), "B1", tts=tts, owner_id=second.id, provider=object(), week=WEEK)
    assert len(tts.calls) == spoken, "another learner gets a copy of the bytes"
    assert other.audio == "ready"
    owned = db_session.scalar(select(func.count()).select_from(LineAudioClip).where(LineAudioClip.user_id == second.id))
    assert owned == len(other.lines)


def test_a_silent_line_silences_the_bulletin(db_session: Session) -> None:
    user = make_user(db_session)

    def broken(provider, **kwargs):  # noqa: ANN001, ARG001
        raise RuntimeError("provider down")

    bulletin = radio.bulletin_for(db_session, greve(), "A2", tts=broken, owner_id=user.id, provider=object(), week=WEEK)
    assert bulletin.audio == "unavailable"
    assert all(line.clip_url is None for line in bulletin.lines)


def test_interpretations_carry_d_apres_and_facts_do_not() -> None:
    for dossier in load_evergreens():
        for claim in dossier.claims:
            spoken = radio.spoken_claim(claim)
            if claim.kind == "fact":
                assert spoken == " ".join(claim.fr.split())
            else:
                assert "d'après" in spoken.casefold(), spoken
                assert spoken.casefold().count("d'après") == 1, spoken
    view = next(claim for claim in greve().claims if claim.kind == "interpretation")
    assert radio.spoken_claim(view) == (
        "D'après les syndicats de salariés et les partis de gauche, le service minimum remet en cause le droit de grève."
    )
    # A2 hears two facts and the view; A1 facts only.
    a2 = radio.bulletin_script(greve(), "A2", week=WEEK)
    assert any(line.role == "claim" and "D'après" in line.text_fr for line in a2.lines)
    a1 = radio.bulletin_script(greve(), "A1", week=WEEK)
    assert all(line.claim_kind == "fact" for line in a1.lines if line.role == "claim")


def test_the_dictee_is_the_shortest_spoken_fact() -> None:
    for dossier in load_evergreens():
        for band in ("A1", "A2", "B1"):
            bulletin = radio.bulletin_script(dossier, band, week=WEEK)
            facts = [line for line in bulletin.lines if line.role == "claim" and line.claim_kind == "fact"]
            assert bulletin.dictee.role == "claim" and bulletin.dictee.claim_kind == "fact"
            assert len(bulletin.dictee.text_fr) == min(len(line.text_fr) for line in facts)


def test_the_dictee_is_graded_by_the_journey_dictation_grader() -> None:
    line = radio.bulletin_script(greve(), "A2", week=WEEK).dictee.text_fr
    assert radio.grade_dictee(line, line.lower().replace(",", ""), language="en").outcome == "met"
    unaccented = line.replace("é", "e").replace("è", "e").replace("ê", "e")
    partial = radio.grade_dictee(line, unaccented, language="de")
    assert partial.outcome == "partially_met" and partial.note == "Fast: nur die Akzente fehlen."
    wrong = radio.grade_dictee(line, "je ne sais pas", language="fr")
    assert wrong.outcome == "not_yet" and wrong.expected_fr == line


# ---------------------------------------------------------------------------
# The rotation
# ---------------------------------------------------------------------------


def test_rotation_skips_heard_dossiers_then_falls_back_to_the_evergreen(db_session: Session) -> None:
    user = make_user(db_session)
    day = datetime(2026, 10, 1, 9, tzinfo=UTC)
    first = radio.radio_week(db_session, user.id, week=WEEK, now=day)
    live = [dossier for dossier in first.queue if not dossier.evergreen]
    assert live, "W40 has authored dossiers"
    assert first.current.id == live[0].id and first.chip
    # Hear every live dossier, one per day.
    for offset, dossier in enumerate(live):
        radio.mark_heard(db_session, user.id, dossier, band="A2", week=WEEK, now=day + timedelta(days=offset))
    db_session.commit()
    later = day + timedelta(days=len(live))
    after = radio.radio_week(db_session, user.id, week=WEEK, now=later)
    assert all(dossier.id not in after.heard or dossier.evergreen for dossier in after.queue)
    assert after.current is not None and after.current.evergreen
    assert after.current.id == evergreens_for_week(WEEK)[0].id
    assert not after.heard_today and after.chip
    # One a day: heard today → no chip until tomorrow, the queue is still there.
    radio.mark_heard(db_session, user.id, after.current, band="A2", week=WEEK, now=later)
    db_session.commit()
    today = radio.radio_week(db_session, user.id, week=WEEK, now=later + timedelta(hours=1))
    assert today.heard_today and not today.chip


# ---------------------------------------------------------------------------
# The routes
# ---------------------------------------------------------------------------


@pytest.fixture()
def api(db_session: Session) -> Iterator[TestClient]:
    app = create_app()

    def override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client


def login(client: TestClient) -> dict[str, str]:
    email = f"radio-{uuid.uuid4().hex[:10]}@example.com"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD, "target_language": "fr", "native_language": "de"},
    )
    response = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_routes_404_while_either_flag_is_off(api: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "REVUE_ENABLED", True)
    monkeypatch.setattr(settings, "REVUE_RADIO_ENABLED", False)
    assert api.get("/api/v1/revue/radio/week").status_code == 404
    headers = login(api)
    assert api.get("/api/v1/revue/radio/week", headers=headers).status_code == 404
    assert api.get(f"/api/v1/revue/radio/{GREVE}", headers=headers).status_code == 404
    monkeypatch.setattr(settings, "REVUE_ENABLED", False)
    monkeypatch.setattr(settings, "REVUE_RADIO_ENABLED", True)
    assert api.get("/api/v1/revue/radio/week", headers=headers).status_code == 404


def test_routes_answer_when_on(api: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "REVUE_ENABLED", True)
    monkeypatch.setattr(settings, "REVUE_RADIO_ENABLED", True)
    tts = FakeTts()
    monkeypatch.setattr(radio, "_default_synthesizer", lambda: object())
    original = radio.bulletin_for

    def with_fake(*args, **kwargs):  # noqa: ANN002, ANN003
        kwargs["tts"] = tts
        return original(*args, **kwargs)

    monkeypatch.setattr(radio, "bulletin_for", with_fake)
    assert api.get("/api/v1/revue/radio/week").status_code == 401
    headers = login(api)
    week = api.get("/api/v1/revue/radio/week", headers=headers)
    assert week.status_code == 200, week.text
    body = week.json()
    assert body["chip"] is True and body["current"] and 45 <= body["seconds"] <= 60

    bulletin = api.get(f"/api/v1/revue/radio/{GREVE}?band=A2", headers=headers)
    assert bulletin.status_code == 200, bulletin.text
    view = bulletin.json()
    assert view["audio"] == "ready" and len(view["lines"]) == len(tts.calls)
    assert view["lines"][view["dictee"]["line_index"]]["role"] == "claim"
    clip = api.get(view["lines"][0]["clip_url"], headers=headers)
    assert clip.status_code == 200 and clip.content.startswith(b"ID3fake")

    dictee_line = view["lines"][view["dictee"]["line_index"]]["text_fr"]
    graded = api.post(f"/api/v1/revue/radio/{GREVE}/dictee", json={"text": dictee_line, "band": "A2"}, headers=headers)
    assert graded.status_code == 200 and graded.json()["outcome"] == "met"

    heard = api.post(f"/api/v1/revue/radio/{GREVE}/heard", json={"band": "A2", "dictee": "met"}, headers=headers)
    assert heard.status_code == 200, heard.text
    assert GREVE in heard.json()["heard"] and heard.json()["heard_today"] is True and heard.json()["chip"] is False
    assert api.get("/api/v1/revue/radio/nope", headers=headers).status_code == 404
