"""Owner decision 18 Nov 2026: a scene correction is explained in the mother tongue.

At B1 the interface is French (``user_chrome_language``), and on a season day the scene's
``control_language`` is that interface language (``season.runtime.today_for`` →
``Today.language``). The tutor lane read its note language, the day's rule card and the
model-free notes from that ``control_language``: a B1 learner whose mother tongue is
English or German was explained a correction in French, while the Courrier explains it in
the mother tongue (``missions.py``: ``day_rules.for_turn(..., user_mother_tongue(user))``).

Pinned here, with fakes (no model call):

* the language the tutor lane is handed for notes is the mother tongue (en, de) at B1.1,
  and the day's rule line that replaces a note stating no rule is in that language;
* an A1 learner is unchanged;
* the interface (the scene's ``control_language``, the chrome) stays French from B1;
* the app's own scene correction notes (explicit, margin) follow the same rule.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.db.models.grammar import UserGrammarProgress
from app.db.models.user import User
from app.services import journey_conversation as jc
from app.services import living_story as engine
from app.services import story_lanes as lanes
from app.services.chrome_language import user_chrome_language, user_mother_tongue
from tests.test_p3_scene_corrects_the_days_rule import RESTATED, SUBJ, SUBJ_ID, TEXT, _concept

RULE_START = {
    "en": "When you want someone else to act",
    "de": "Wenn eine andere Person handeln soll",
}


def _learner(db_session, *, native: str, level: str) -> User:
    user = User(
        id=uuid4(),
        email=f"mt-{uuid4().hex[:8]}@example.com",
        hashed_password="x",
        native_language=native,
        target_language="fr",
        proficiency_level=level[:2],
        cefr_estimate=level,
        daily_goal_minutes=20,
    )
    db_session.add(user)
    db_session.flush()
    concept = _concept(db_session, SUBJ_ID)
    db_session.add(
        UserGrammarProgress(
            user_id=user.id, concept_id=concept.id, introduced_at=datetime.now(UTC) - timedelta(hours=1)
        )
    )
    db_session.flush()
    return user


class _DB:
    """The test session, with the scene the turn is about."""

    def __init__(self, real, scene):
        self._real, self._scene = real, scene

    def get(self, model, key):
        return self._scene

    def __getattr__(self, name):
        return getattr(self._real, name)


def _season_turn_payload(db_session, monkeypatch, user: User) -> dict:
    """``living_story._turn_payload`` on a season day: the scene's control language is the
    interface language (``Today.language`` = ``user_chrome_language``)."""

    context = {
        "thread_id": "thread",
        "control_language": user_chrome_language(user),
        "level": user.cefr_estimate,
        "events": [],
        "commitments": [],
        "world": {"cast": [{"id": "lila", "name": "Lila"}]},
        "relationships": {},
        "moods": {},
        "agendas": [],
        "consequences": [],
        "secrets": {},
        "chapter": {},
    }
    monkeypatch.setattr(engine, "story_context", lambda db, u: dict(context))
    monkeypatch.setattr(engine, "_noticed_word", lambda *a, **k: None)
    monkeypatch.setattr(engine, "keeps_talking", lambda *a, **k: False)
    scene = SimpleNamespace(user_id=user.id, status="available", script_payload={})
    scenario = SimpleNamespace(
        serial_thread_id="thread",
        story_context={"scene_id": str(uuid4()), "draft": {}},
        character_id="lila",
        character_name="Lila",
    )
    task = SimpleNamespace(max_turns=3, opening_line_fr="Tu viens ?", rubric_native="Answer.", targets=[])
    answer = SimpleNamespace(text=TEXT)
    return engine._turn_payload(_DB(db_session, scene), user, scenario, task, answer, [], 1)


@pytest.mark.parametrize("native", ["en", "de"])
def test_a_b1_learner_is_explained_a_scene_correction_in_the_mother_tongue(db_session, monkeypatch, native):
    user = _learner(db_session, native=native, level="B1.1")
    payload = _season_turn_payload(db_session, monkeypatch, user)

    # The interface stays French from B1 (unchanged): the scene's own words.
    assert user_chrome_language(user) == "fr"
    assert payload["story"]["control_language"] == "fr"
    # The tutor is handed the mother tongue for its notes …
    assert lanes.tutor_payload(payload)["control_language"] == native
    # … and the day's rule card is read in it, for the tutor and for the fallback note.
    assert payload["day_rules"]["today"]["rule"].startswith(RULE_START[native])
    assert lanes.tutor_payload(payload)["rules"]["today"]["rule"].startswith(RULE_START[native])

    # A model note that states no rule: the day's rule line takes its place, in the
    # mother tongue, never in French.
    verdict = lanes.TutorVerdict.model_validate(
        {"outcome": "partially_met", "evidence_quotes": [], "corrections": [{**SUBJ, "note_native": RESTATED}]}
    )
    lanes.validate_tutor(verdict, payload)
    assert verdict.correction_span_fr == "que tu reviens"
    assert verdict.correction_note_native.startswith(RULE_START[native])


def test_the_correction_language_reaches_no_other_model_call(db_session, monkeypatch):
    user = _learner(db_session, native="en", level="B1.1")
    payload = _season_turn_payload(db_session, monkeypatch, user)

    assert engine.CORRECTION_LANGUAGE_KEY in payload
    assert engine.CORRECTION_LANGUAGE_KEY not in lanes.story_payload(payload, {})
    assert engine.CORRECTION_LANGUAGE_KEY not in lanes.voice_payload(payload)


@pytest.mark.parametrize("native", ["en", "de"])
def test_an_a1_learner_is_unchanged(db_session, monkeypatch, native):
    user = _learner(db_session, native=native, level="A1.1")
    payload = _season_turn_payload(db_session, monkeypatch, user)

    assert payload["story"]["control_language"] == native == user_chrome_language(user)
    assert lanes.tutor_payload(payload)["control_language"] == native
    assert payload["day_rules"]["today"]["rule"].startswith(RULE_START[native])


def test_a_recorded_payload_without_the_key_keeps_its_control_language():
    assert lanes.correction_language({"story": {"control_language": "de"}}) == "de"


@pytest.mark.parametrize(
    ("native", "level", "explicit", "margin"),
    [
        ("en", "A2.1", "That was the one you were just asked about", "It is “un café”"),
        ("en", "B1.1", "That was the one you were just asked about", "It is “un café”"),
        ("de", "B1.1", "Danach wurde eben gefragt", "„un café“"),
    ],
)
def test_the_apps_own_scene_notes_are_in_the_mother_tongue(native, level, explicit, margin):
    learner = SimpleNamespace(native_language=native, cefr_estimate=level, proficiency_level=level[:2])
    assert user_mother_tongue(learner) == native
    assert explicit in jc._explicit_note(user=learner, wrong="une café", correct="un café", why="")
    assert margin in jc._margin_note(user=learner, wrong="une café", correct="un café", why="")
