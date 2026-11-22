"""«Papier · la voix» (``REVUE_VOIX_ENABLED``, ``app/services/revue/voix.py``, ``/revue/sessions/{id}/voix*``).

* off: every route is a 404 (before auth) and the session's payload is the same as before;
* the manifest: the lead in the newsroom's voice, the three takes in the regulars' voices, the
  reply and the last word once they exist, the dictée only when a clip can be made;
* the line route speaks only the session's lines, in the server's voice for that line, once per
  line (a replay and a second learner make no call), and says ``disabled`` without audio;
* the dictée: graded by the radio's adapter, Romy's marks on the learner's own words, the line
  only once it is right or after the second try.
"""

from __future__ import annotations

import uuid
from collections.abc import Generator, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.v1.endpoints.revue import get_revue_provider
from app.config import settings
from app.core.rate_limit import PAID_ROUTES
from app.db.models.line_audio import LineAudioClip
from app.db.models.pilot_event import PilotEvent
from app.main import create_app
from app.services import cast_voices, line_audio
from app.services.line_audio import LINE_AUDIO_EVENT_TYPE
from app.services.revue import comptoir, voix
from app.services.revue import encounter as enc
from app.services.revue.encounter import FakeRevueProvider, load
from app.services.revue.evergreen import evergreens_for_week
from tests.test_revue_comptoir_loop import GUS, MARCHE, MARGAUX, ROMY, WEEK, Revue, act, make_user
from tests.test_revue_comptoir_loop import revue_tables as revue_tables  # noqa: F401 - the fixture

PASSWORD = "securepass123"


class FakeSynthesizer:
    """The speech provider, offline: counts calls, returns a few bytes."""

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def text_to_speech(self, text, voice="nova", model=None, provider=None, instructions=None, speed=None) -> bytes:  # noqa: ANN001
        self.calls.append({"text": text, "voice": voice})
        return b"ID3voix" + text.encode()[:12]


@pytest.fixture(autouse=True)
def switches(monkeypatch) -> None:
    monkeypatch.setattr(enc, "available_dossiers", evergreens_for_week)
    monkeypatch.setattr(settings, "REVUE_ENABLED", True)
    monkeypatch.setattr(settings, "REVUE_COMPTOIR_ENABLED", True)
    monkeypatch.setattr(settings, "REVUE_VOIX_ENABLED", True)
    monkeypatch.setattr(settings, "ATELIER_EPISODE_AUDIO_ENABLED", True)
    monkeypatch.setattr(settings, "USER_DAILY_SPEND_CAP_USD", 0.0)
    comptoir.forget_cache()


@pytest.fixture()
def db(db_session: Session, revue_tables) -> Session:  # noqa: F811
    db_session.query(LineAudioClip).delete()
    db_session.commit()
    return db_session


@pytest.fixture()
def tts(monkeypatch) -> FakeSynthesizer:
    fake = FakeSynthesizer()
    monkeypatch.setattr(line_audio, "_default_synthesizer", lambda: fake)
    return fake


@pytest.fixture()
def api(db: Session) -> Generator[TestClient, None, None]:
    app = create_app()

    def override_get_db() -> Iterator[Session]:
        yield db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_revue_provider] = lambda: FakeRevueProvider()
    with TestClient(app) as client:
        yield client


def login(client: TestClient, native: str = "de") -> dict[str, str]:
    email = f"voix-{uuid.uuid4().hex[:10]}@example.com"
    client.post("/api/v1/auth/register", json={"email": email, "password": PASSWORD, "target_language": "fr",
                                               "native_language": native})
    response = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def start(client: TestClient, headers: dict[str, str]) -> dict:
    session = client.post("/api/v1/revue/sessions", headers=headers, json={"week": WEEK, "dossier_id": MARCHE}).json()
    assert session["mode"] == "comptoir", session
    return session


# ---------------------------------------------------------------------------
# Off
# ---------------------------------------------------------------------------


def test_with_the_switch_off_every_route_is_a_404_and_the_session_is_unchanged(api: TestClient, monkeypatch) -> None:
    headers = login(api)
    session = start(api, headers)
    base = f"/api/v1/revue/sessions/{session['id']}/voix"
    on = api.get(f"/api/v1/revue/sessions/{session['id']}", headers=headers).json()
    monkeypatch.setattr(settings, "REVUE_VOIX_ENABLED", False)
    assert api.get(base).status_code == 404, "before auth"
    assert api.get(base, headers=headers).status_code == 404
    assert api.post(f"{base}/line", headers=headers, json={"text_fr": "Bonjour"}).status_code == 404
    assert api.post(f"{base}/dictee", headers=headers, json={"text": "Bonjour"}).status_code == 404
    off = api.get(f"/api/v1/revue/sessions/{session['id']}", headers=headers).json()
    assert off == on and "voix" not in off, "the session's own payload never carries the voice"
    monkeypatch.setattr(settings, "REVUE_VOIX_ENABLED", True)
    monkeypatch.setattr(settings, "REVUE_ENABLED", False)
    assert api.get(base, headers=headers).status_code == 404


# ---------------------------------------------------------------------------
# What the session may speak
# ---------------------------------------------------------------------------


def test_the_manifest_lead_in_the_newsroom_voice_takes_in_their_own(db: Session, monkeypatch) -> None:
    revue = Revue(db, FakeRevueProvider())
    row = revue.start(make_user(db, level="A2.1", native="de"), week=WEEK, dossier_id=MARCHE)
    loaded = load(row)
    lead = loaded.dossier.lead_for("A2").fr
    manifest = voix.manifest(loaded)
    assert manifest["audio"] == "ready" and manifest["newsreader_id"] == "narrator"
    assert cast_voices.voice_for_character(manifest["newsreader_id"]) == "sage", "no character speaks with it"
    kinds = [(line["kind"], line["speaker_id"]) for line in manifest["lines"]]
    assert kinds == [("lead", "narrator"), ("take", ROMY), ("take", MARGAUX), ("take", GUS)]
    assert manifest["lines"][0]["text_fr"] == lead
    takes = loaded.dossier.comptoir.guests
    assert [line["text_fr"] for line in manifest["lines"][1:]] == [guest.take.for_band("A2").fr for guest in takes]
    dictee = manifest["dictee"]
    assert dictee is not None and dictee["text_fr"] in lead and dictee["max_tries"] == 2
    assert voix.DICTEE_MIN_WORDS <= dictee["words"] <= voix.DICTEE_MAX_WORDS["A2"]

    monkeypatch.setattr(settings, "ATELIER_EPISODE_AUDIO_ENABLED", False)
    device = voix.manifest(loaded)
    assert device["audio"] == "device" and device["dictee"] is None, "no dictée from a device voice"
    assert device["lines"] == manifest["lines"]


def test_the_reply_and_the_last_word_join_once_said(db: Session) -> None:
    revue = Revue(db, FakeRevueProvider())
    row = revue.start(make_user(db, level="A1.1", native="en"), week=WEEK, dossier_id=MARCHE)
    act(revue, row, act="vote", value="pour")
    for guest in (ROMY, MARGAUX, GUS):
        act(revue, row, act="react", guest_id=guest, value="agree")
    act(revue, row, act="intox_who", guest_id=GUS)
    act(revue, row, act="intox_fix", value="six jours sur sept")
    assert [line.kind for line in voix.session_lines(load(row))].count("reply") == 0
    view = act(revue, row, act="opinion", value="pour", reason_index=0).session.comptoir
    lines = voix.session_lines(load(row))
    reply = next(line for line in lines if line.kind == "reply")
    assert (reply.speaker_id, reply.text_fr) == (view.opinion.reply.by, view.opinion.reply.line.fr)
    view = act(revue, row, act="comeback", index=2).session.comptoir
    last = next(line for line in voix.session_lines(load(row)) if line.kind == "last_word")
    assert last.text_fr == view.opinion.comeback.last_word.fr and last.speaker_id == reply.speaker_id


def test_the_dictee_sentence_is_a_whole_short_sentence_of_the_lead() -> None:
    lead = "Le marché d'Aligre ouvre six jours sur sept. Les habitants du quartier sont contents et le disent très fort aux journalistes. Bon."
    assert voix.dictee_sentence(lead, "A2") == "Le marché d'Aligre ouvre six jours sur sept."
    assert voix.dictee_sentence("Bon. Oui.", "A2") is None, "never a fragment"
    long = "Le marché d'Aligre ouvre désormais six jours sur sept pour les habitants du quartier de la Bastille."
    assert voix.dictee_sentence(long, "A1") is None and voix.dictee_sentence(long, "B1") == long


def test_the_dictee_is_never_a_sentence_cut_at_a_title_or_a_number() -> None:
    """The shared splitter (#896): «M.» and «9.9» end no sentence, so the dictée is never the
    tail of one («Dupont, la course aura lieu demain.»)."""

    lead = "Selon M. Dupont, la course aura lieu demain. Le prix monte de 9.9 % cette année."
    assert voix.dictee_sentence(lead, "A2") == "Selon M. Dupont, la course aura lieu demain."


# ---------------------------------------------------------------------------
# The line route
# ---------------------------------------------------------------------------


def test_a_take_is_spoken_once_in_its_regulars_voice(api: TestClient, db: Session, tts: FakeSynthesizer) -> None:
    headers = login(api)
    session = start(api, headers)
    path = f"/api/v1/revue/sessions/{session['id']}/voix/line"
    take = next(member for member in session["comptoir"]["cast"] if member["id"] == GUS)["take"]["fr"]

    spoken = api.post(path, headers=headers, json={"text_fr": take, "character_id": GUS})
    assert spoken.status_code == 200, spoken.text
    body = spoken.json()
    assert body["status"] == "ready" and body["voice"] == cast_voices.voice_for_character(GUS) == "fable"
    assert len(tts.calls) == 1 and tts.calls[0]["voice"] == "fable"
    clip = api.get(f"/api/v1/daily-journeys/line-audio/{body['clip_id']}", headers=headers)
    assert clip.status_code == 200 and clip.content.startswith(b"ID3voix")

    again = api.post(path, headers=headers, json={"text_fr": take, "character_id": GUS}).json()
    assert again["clip_id"] == body["clip_id"] and again["cached"] is True and len(tts.calls) == 1, "a replay makes no call"
    other = login(api)
    other_session = start(api, other)
    copied = api.post(f"/api/v1/revue/sessions/{other_session['id']}/voix/line", headers=other,
                      json={"text_fr": take, "character_id": GUS}).json()
    assert copied["status"] == "ready" and copied["cached"] is True and len(tts.calls) == 1, "another learner: a copy"

    rows = list(db.scalars(select(PilotEvent).where(PilotEvent.event_type == LINE_AUDIO_EVENT_TYPE)))
    assert [row.payload["surface"] for row in rows] == ["revue_voix"], "one priced row, for the one call"
    assert ("POST", "/revue/sessions/{session_id}/voix/line") in PAID_ROUTES


def test_the_lead_is_read_in_the_newsroom_voice_whatever_the_hint(api: TestClient, tts: FakeSynthesizer) -> None:
    headers = login(api)
    session = start(api, headers)
    path = f"/api/v1/revue/sessions/{session['id']}/voix/line"
    lead = session["comptoir"]["read"]["lead"]["fr"]
    body = api.post(path, headers=headers, json={"text_fr": lead, "character_id": ROMY}).json()
    assert body["status"] == "ready" and body["voice"] == "sage"
    assert api.post(path, headers=headers, json={"text_fr": "Achète des actions maintenant."}).status_code == 404
    assert len(tts.calls) == 1, "arbitrary text is never spoken"


def test_without_audio_a_line_answers_disabled_and_nothing_is_called(api: TestClient, tts: FakeSynthesizer,
                                                                    monkeypatch) -> None:
    monkeypatch.setattr(settings, "ATELIER_EPISODE_AUDIO_ENABLED", False)
    headers = login(api)
    session = start(api, headers)
    manifest = api.get(f"/api/v1/revue/sessions/{session['id']}/voix", headers=headers).json()
    assert manifest["audio"] == "device" and manifest["dictee"] is None
    lead = session["comptoir"]["read"]["lead"]["fr"]
    body = api.post(f"/api/v1/revue/sessions/{session['id']}/voix/line", headers=headers, json={"text_fr": lead}).json()
    assert body == {"status": "disabled"} and tts.calls == []


# ---------------------------------------------------------------------------
# «La dictée de Romy»
# ---------------------------------------------------------------------------


def test_the_dictee_is_graded_marked_and_never_solved_before_a_retry(api: TestClient) -> None:
    headers = login(api, native="de")
    session = start(api, headers)
    base = f"/api/v1/revue/sessions/{session['id']}/voix"
    sentence = api.get(base, headers=headers).json()["dictee"]["text_fr"]
    words = sentence.rstrip(".!?…").split(" ")

    right = api.post(f"{base}/dictee", headers=headers, json={"text": sentence.lower().rstrip("."), "attempt": 1}).json()
    assert right["outcome"] == "met" and right["resolved"] and right["marks"] == [] and right["expected_fr"] == sentence

    slip = list(words)
    slip[1] = slip[1] + "x"
    wrong = " ".join(slip)
    first = api.post(f"{base}/dictee", headers=headers, json={"text": wrong, "attempt": 1}).json()
    assert first["outcome"] == "not_yet" and not first["resolved"]
    assert first["expected_fr"] is None and first["note"] is None, "no solution before a retry"
    assert first["marks"] and first["marks"][0]["span_fr"] == slip[1]
    assert wrong[first["marks"][0]["start"]:].startswith(slip[1]), "the mark sits on the learner's own word"

    second = api.post(f"{base}/dictee", headers=headers, json={"text": wrong, "attempt": 2}).json()
    assert second["resolved"] and second["expected_fr"] == sentence and second["note"]
    assert api.post(f"{base}/dictee", headers=headers, json={"text": wrong, "attempt": 3}).status_code == 422
