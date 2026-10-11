"""WP-31 — «Répétition»: rehearse a real upcoming situation, then debrief it.

What these tests hold down, in the order the package promises it:

1. the declaration is structured — goal, counterpart, register, date, facts —
   and an unusable field falls back to something honest rather than a guess;
2. **the no-canon rule**: nothing about a rehearsal reaches serial memory, and
   no world-bible character reaches a rehearsal (a source scan plus a live run);
3. the generated scene must pass the same guarantees an authored journey scene
   passes — band lengths, one register, typed endings, and the no-spoil gate;
4. the turn bound is 3–6 and it is this package that owns it, not the journey
   conversation module's own two-turn budget;
5. the debrief opens on the declared date, takes exactly three outcomes, and
   corrects one free line — or says in as many words that it did not;
6. every real provider call writes a priced pilot row, a replayed turn buys
   nothing, and a provider that never answers yields «non préparée» with the
   learner's declaration intact.

No live model call is made anywhere in this file: the provider is a fake.
"""
from __future__ import annotations

import ast
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.db.models.pilot_event import PilotEvent
from app.db.models.rehearsal import Rehearsal
from app.db.models.serial import SerialThread
from app.db.models.user import User
from app.services.journey_contracts import AssistanceLevel, TaskOutcome
from app.services.rehearsal import (
    DEBRIEF_EVENT_TYPE,
    MAX_TURNS,
    MIN_TURNS,
    PREPARE_EVENT_TYPE,
    TURN_EVENT_TYPE,
    RehearsalRefused,
    RehearsalService,
    cap_state,
    conversation_turn_index,
    covered_point_ids,
    debrief_available,
    ending_for,
    mentions_fiction,
    normalize_brief,
    normalize_declaration,
    normalize_scene,
    public_view,
    rehearsal_digest_line,
    rehearsal_outcome,
    resolve_event_date,
    sanitize_correction,
    scenario_brief_for,
    validate_rehearsal_scene,
)

TODAY = date(2026, 9, 10)  # a Thursday
NOW = datetime(2026, 9, 10, 9, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _user(db_session, *, declared: str = "A2") -> User:
    user = User(
        id=uuid4(),
        email=f"rehearsal-{uuid4().hex[:8]}@example.com",
        hashed_password="x",
        native_language="en",
        target_language="fr",
        proficiency_level=declared,
        cefr_estimate="A2.1",
        daily_goal_minutes=20,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


GOOD_BRIEF = {
    "goal_fr": "Demander une réparation du chauffage",
    "goal_native": "Ask for the heating to be repaired",
    "counterpart": "le propriétaire",
    "register": "vous",
    "date_text": "mardi",
    "date_iso": "2026-09-15",
    "facts": ["le chauffage ne marche plus depuis samedi"],
}

GOOD_SCENE = {
    "title_fr": "Le chauffage",
    "place_fr": "au téléphone",
    "setup_fr": "Vous appelez pour le chauffage. Il ne marche plus depuis samedi.",
    "setup_native": "You call about the heating. It has not worked since Saturday.",
    "objective_fr": "Expliquez le problème et demandez une date.",
    "objective_native": "Explain the problem and ask for a date.",
    "opening_line_fr": "Allô ? Vous m’entendez bien ?",
    "rubric_native": "Met when the learner names the broken heating and asks for a date.",
    "points": [
        {"id": "probleme", "label_fr": "Dire ce qui ne marche pas", "cues_fr": ["chauffage", "panne"]},
        {"id": "date", "label_fr": "Demander une date", "cues_fr": ["quand", "date", "jeudi"]},
    ],
    "phrases": [
        {"fr": "Le chauffage est en panne.", "native": "The heating is broken."},
        {"fr": "Quand pouvez-vous passer ?", "native": "When can you come?"},
    ],
    "endings": {
        "date_obtenue": {
            "line_fr": "D’accord, je passe jeudi matin.",
            "summary_fr": "Le propriétaire passe jeudi matin.",
        },
        "rappel_plus_tard": {
            "line_fr": "Je vous rappelle demain, d’accord ?",
            "summary_fr": "Il doit vous rappeler demain.",
        },
    },
    "turns": 4,
}


class _FakeLLM:
    """A provider that answers with whatever the test told it to answer."""

    def __init__(self, *, scene=None, brief=None, raise_on_prepare=False, correction=None):
        self.prepare_calls = 0
        self.correction_calls = 0
        self._scene = GOOD_SCENE if scene is None else scene
        self._brief = GOOD_BRIEF if brief is None else brief
        self._raise = raise_on_prepare
        self._correction = correction

    def generate_chat_completion(self, messages, **kwargs):
        self.prepare_calls += 1
        if self._raise:
            raise ValueError("provider is down")
        return SimpleNamespace(
            content=json.dumps({"brief": self._brief, "scene": self._scene}, ensure_ascii=False),
            model="test-model",
            provider="test",
            prompt_tokens=400,
            completion_tokens=300,
            total_tokens=700,
            cost=0.004,
        )

    def generate_error_detection(self, messages, **kwargs):
        self.correction_calls += 1
        if self._correction is None:
            raise ValueError("no corrector")
        return SimpleNamespace(
            content=json.dumps(self._correction, ensure_ascii=False),
            model="test-model",
            provider="test",
            prompt_tokens=80,
            completion_tokens=40,
            total_tokens=120,
            cost=0.0002,
        )


def _service(db_session, llm=None) -> RehearsalService:
    return RehearsalService(db_session, llm_service=llm or _FakeLLM())


def _events(db_session, event_type: str, user: User) -> list[PilotEvent]:
    """This learner's rows only: the suite shares one database across tests."""

    return (
        db_session.query(PilotEvent)
        .filter(PilotEvent.event_type == event_type, PilotEvent.user_id == user.id)
        .all()
    )


# ---------------------------------------------------------------------------
# 1. The declaration, structured
# ---------------------------------------------------------------------------


def test_declaration_is_bounded_and_squeezed():
    assert normalize_declaration("  call   the landlord  ") == "call the landlord"
    assert len(normalize_declaration("x" * 5000)) == 600
    assert normalize_declaration(None) == ""


def test_structuring_keeps_goal_counterpart_register_date_and_facts():
    brief = normalize_brief(GOOD_BRIEF, declaration="call the landlord", today=TODAY)
    assert brief["goal_fr"] == "Demander une réparation du chauffage"
    assert brief["counterpart"] == "le propriétaire"
    assert brief["register"] == "vous"
    assert brief["date_iso"] == "2026-09-15"
    assert brief["facts"] == ["le chauffage ne marche plus depuis samedi"]
    # The learner's own words survive the structuring, always.
    assert brief["declaration"] == "call the landlord"


def test_an_unusable_register_becomes_vous_not_a_guess():
    brief = normalize_brief({**GOOD_BRIEF, "register": "formal-ish"}, declaration="x", today=TODAY)
    assert brief["register"] == "vous"


def test_a_structure_with_no_goal_or_counterpart_is_refused():
    from app.services.rehearsal import brief_is_usable

    assert brief_is_usable(normalize_brief(GOOD_BRIEF, declaration="x", today=TODAY))
    assert not brief_is_usable(
        normalize_brief({**GOOD_BRIEF, "goal_fr": ""}, declaration="x", today=TODAY)
    )
    assert not brief_is_usable(
        normalize_brief({**GOOD_BRIEF, "counterpart": ""}, declaration="x", today=TODAY)
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2026-09-15", date(2026, 9, 15)),
        ("mardi", date(2026, 9, 15)),
        ("Tuesday", date(2026, 9, 15)),
        ("Dienstag", date(2026, 9, 15)),
        ("demain", date(2026, 9, 11)),
        # Said on a Thursday, "jeudi" means the next one: a rehearsal is for
        # something that has not happened yet.
        ("jeudi", date(2026, 9, 17)),
        ("", None),
        ("un jour", None),
        ("2027-09-15", None),  # past the horizon: no date is claimed
        ("2026-09-01", None),  # already gone
    ],
)
def test_event_dates_are_resolved_or_honestly_absent(raw, expected):
    assert resolve_event_date(raw, today=TODAY) == expected


def test_a_date_the_structurer_could_not_resolve_keeps_the_learners_words():
    brief = normalize_brief(
        {**GOOD_BRIEF, "date_iso": None, "date_text": "quand il aura le temps"},
        declaration="x",
        today=TODAY,
    )
    assert brief["date_iso"] is None
    assert brief["date_text"] == "quand il aura le temps"


# ---------------------------------------------------------------------------
# 2. The no-canon rule
# ---------------------------------------------------------------------------


def test_rehearsal_never_writes_serial_memory():
    """A source scan over the *code*, not the prose.

    The module docstring names the story tables on purpose — to say it does not
    touch them — so the scan walks the AST instead of the text: every name this
    module imports or refers to, checked against the story-writing surface.
    """

    source = Path("app/services/rehearsal.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    imported: set[str] = set()
    referenced: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Name):
            referenced.add(node.id)
        elif isinstance(node, ast.Attribute):
            referenced.add(node.attr)

    forbidden_modules = {
        "app.services.living_story",
        "app.services.serial_arc_planner",
        "app.db.models.serial",
    }
    assert not (imported & forbidden_modules), imported & forbidden_modules

    forbidden_names = {
        "SerialThread",
        "SerialEpisode",
        "SerialThreadService",
        "apply_story_outcome",
        "apply_journey_story_outcome",
        "generate_scene",
        "evaluate_turn",
    }
    assert not (referenced & forbidden_names), referenced & forbidden_names

    # The one serial import allowed is the read-only path to the world bible,
    # and it exists precisely to keep the story *out* of the rehearsal.
    assert "from app.services.serial import WORLD_BIBLE_PATH" in source


def test_a_rehearsal_scenario_brief_carries_no_story_context(db_session):
    user = _user(db_session)
    service = _service(db_session)
    rehearsal = service.declare(user, declaration="call the landlord", now=NOW)
    db_session.commit()

    brief = scenario_brief_for(rehearsal)
    assert brief.story_context == {}
    assert brief.serial_thread_id is None
    assert brief.serial_episode_id is None


def test_a_whole_rehearsal_leaves_the_serial_untouched(db_session):
    user = _user(db_session)
    service = _service(db_session)
    before = db_session.query(SerialThread).count()

    rehearsal = service.declare(user, declaration="call the landlord, tuesday", now=NOW)
    service.respond(
        user, rehearsal, text="Bonjour, le chauffage est en panne.", turn_index=0, now=NOW
    )
    service.respond(
        user, rehearsal, text="Quand pouvez-vous passer ?", turn_index=1, now=NOW
    )
    db_session.commit()

    assert db_session.query(SerialThread).count() == before
    assert rehearsal.status == "rehearsed"


def test_a_scene_that_names_a_story_character_is_rejected(db_session):
    scene = dict(GOOD_SCENE)
    scene["opening_line_fr"] = "Allô ? Ici Margaux, vous m’entendez ?"
    normalized = normalize_scene(scene, brief=GOOD_BRIEF, level_band="A2")
    problems = validate_rehearsal_scene(normalized, register="vous")
    assert any("story" in problem for problem in problems)


def test_the_fiction_guard_finds_a_cast_name_anywhere():
    assert mentions_fiction("Je rappelle Margaux demain") is not None
    assert mentions_fiction("Je rappelle le propriétaire demain") is None


def test_a_provider_that_names_a_character_leaves_the_rehearsal_unprepared(db_session):
    user = _user(db_session)
    scene = {**GOOD_SCENE, "opening_line_fr": "Allô, ici Lila. Vous m’entendez ?"}
    service = _service(db_session, _FakeLLM(scene=scene))
    rehearsal = service.declare(user, declaration="call the landlord", now=NOW)
    db_session.commit()

    assert rehearsal.status == "not_prepared"
    assert rehearsal.scene == {}
    assert rehearsal.declaration == "call the landlord"


# ---------------------------------------------------------------------------
# 3. The scene contract
# ---------------------------------------------------------------------------


def test_a_good_scene_validates():
    scene = normalize_scene(GOOD_SCENE, brief=GOOD_BRIEF, level_band="A2")
    assert validate_rehearsal_scene(scene, register="vous") == []


def test_a_scene_over_the_band_length_is_rejected():
    scene = normalize_scene(
        {**GOOD_SCENE, "setup_fr": " ".join(["mot"] * 60)},
        brief=GOOD_BRIEF,
        level_band="A1",
    )
    problems = validate_rehearsal_scene(scene, register="vous")
    assert any("setup_fr is" in problem for problem in problems)


def test_a_register_break_in_a_spoken_line_is_rejected():
    scene = normalize_scene(
        {**GOOD_SCENE, "opening_line_fr": "Allô ? Tu m’entends bien ?"},
        brief=GOOD_BRIEF,
        level_band="A2",
    )
    problems = validate_rehearsal_scene(scene, register="vous")
    assert any("register break" in problem for problem in problems)


def test_a_scene_with_no_line_in_the_declared_register_is_rejected():
    scene = normalize_scene(
        {
            **GOOD_SCENE,
            "opening_line_fr": "Allô ? Oui, j’écoute.",
            "endings": {
                "date_obtenue": {"line_fr": "D’accord, jeudi matin.", "summary_fr": "Jeudi matin."},
                "rappel_plus_tard": {"line_fr": "Je rappelle demain.", "summary_fr": "Demain."},
            },
        },
        brief=GOOD_BRIEF,
        level_band="A2",
    )
    problems = validate_rehearsal_scene(scene, register="vous")
    assert any("carries the declared" in problem for problem in problems)


def test_a_useful_phrase_printed_in_the_setup_is_rejected():
    """The no-spoil gate: help that is already on screen was never held back."""

    scene = normalize_scene(
        {**GOOD_SCENE, "setup_fr": "Vous appelez. Le chauffage est en panne."},
        brief=GOOD_BRIEF,
        level_band="A2",
    )
    problems = validate_rehearsal_scene(scene, register="vous")
    assert any("leaks into a pre-answer field" in problem for problem in problems)


def test_an_untyped_ending_key_is_rejected():
    scene = normalize_scene(
        {
            **GOOD_SCENE,
            "endings": {
                "Date Obtenue!": {"line_fr": "Jeudi, vous êtes là ?", "summary_fr": "Jeudi."},
                "rappel": {"line_fr": "Je vous rappelle.", "summary_fr": "Demain."},
            },
        },
        brief=GOOD_BRIEF,
        level_band="A2",
    )
    problems = validate_rehearsal_scene(scene, register="vous")
    assert any("snake_case" in problem for problem in problems)


def test_a_point_with_no_cue_cannot_be_recognised_and_is_rejected():
    scene = normalize_scene(
        {
            **GOOD_SCENE,
            "points": [
                {"id": "probleme", "label_fr": "Dire le problème", "cues_fr": []},
                {"id": "date", "label_fr": "Demander une date", "cues_fr": ["quand"]},
            ],
        },
        brief=GOOD_BRIEF,
        level_band="A2",
    )
    problems = validate_rehearsal_scene(scene, register="vous")
    assert any("no cue" in problem for problem in problems)


def test_an_empty_field_is_rejected_rather_than_shown():
    scene = normalize_scene({**GOOD_SCENE, "rubric_native": ""}, brief=GOOD_BRIEF, level_band="A2")
    assert "rubric_native is empty" in validate_rehearsal_scene(scene, register="vous")


# ---------------------------------------------------------------------------
# 4. The turn bound
# ---------------------------------------------------------------------------


def test_the_turn_count_is_clamped_into_three_to_six():
    for asked, expected in ((0, MIN_TURNS), (1, MIN_TURNS), (4, 4), (9, MAX_TURNS)):
        scene = normalize_scene({**GOOD_SCENE, "turns": asked}, brief=GOOD_BRIEF, level_band="A2")
        assert scene["turns"] == expected


def test_this_package_owns_the_bound_and_the_conversation_module_only_hears_last_or_not():
    # Four rehearsal turns; the conversation module is told "a follow-up
    # remains" three times and "this is the last one" once.
    assert [conversation_turn_index(index, 4) for index in range(4)] == [0, 0, 0, 1]
    assert conversation_turn_index(0, 1) == 1


def test_a_turn_past_the_bound_is_refused(db_session):
    user = _user(db_session)
    scene = {**GOOD_SCENE, "turns": 3}
    service = _service(db_session, _FakeLLM(scene=scene))
    rehearsal = service.declare(user, declaration="call the landlord", now=NOW)
    for index in range(3):
        service.respond(user, rehearsal, text=f"Bonjour {index}", turn_index=index, now=NOW)
    db_session.commit()

    assert rehearsal.status == "rehearsed"
    with pytest.raises(RehearsalRefused) as caught:
        service.respond(user, rehearsal, text="encore", turn_index=3, now=NOW)
    assert caught.value.code == "rehearsal_not_live"


def test_a_replayed_turn_index_is_a_no_op(db_session):
    user = _user(db_session)
    service = _service(db_session)
    rehearsal = service.declare(user, declaration="call the landlord", now=NOW)
    service.respond(user, rehearsal, text="Bonjour", turn_index=0, now=NOW)
    stored = list(rehearsal.turns)

    service.respond(user, rehearsal, text="Bonjour encore", turn_index=0, now=NOW)
    assert rehearsal.turns == stored


def test_an_out_of_order_turn_is_refused(db_session):
    user = _user(db_session)
    service = _service(db_session)
    rehearsal = service.declare(user, declaration="call the landlord", now=NOW)
    with pytest.raises(RehearsalRefused) as caught:
        service.respond(user, rehearsal, text="Bonjour", turn_index=2, now=NOW)
    assert caught.value.code == "turn_out_of_order"


# ---------------------------------------------------------------------------
# 5. Grading with the evidence rubric
# ---------------------------------------------------------------------------


def test_points_are_recognised_cumulatively_across_turns():
    scene = normalize_scene(GOOD_SCENE, brief=GOOD_BRIEF, level_band="A2")
    assert covered_point_ids(scene, ["Le chauffage ne marche plus."]) == ["probleme"]
    assert covered_point_ids(
        scene, ["Le chauffage ne marche plus.", "Vous venez quand ?"]
    ) == ["probleme", "date"]
    assert rehearsal_outcome(scene, ["probleme"]) is TaskOutcome.PARTIALLY_MET
    assert rehearsal_outcome(scene, ["probleme", "date"]) is TaskOutcome.MET
    assert rehearsal_outcome(scene, []) is TaskOutcome.NOT_YET


def test_the_successful_ending_is_the_first_key_and_a_miss_never_takes_it():
    scene = normalize_scene(GOOD_SCENE, brief=GOOD_BRIEF, level_band="A2")
    assert ending_for(scene, TaskOutcome.MET) == "date_obtenue"
    assert ending_for(scene, TaskOutcome.NOT_YET) == "rappel_plus_tard"


def test_asking_for_the_phrases_costs_independence(db_session):
    user = _user(db_session)
    service = _service(db_session)
    rehearsal = service.declare(user, declaration="call the landlord", now=NOW)

    service.respond(
        user, rehearsal, text="Le chauffage est en panne.", turn_index=0, now=NOW
    )
    assert rehearsal.turns[0]["assistance"] == str(AssistanceLevel.NONE)
    assert rehearsal.turns[0]["evidence_kind"] in {"produced_independent", "not_yet"}

    service.reveal_phrases(rehearsal)
    service.respond(user, rehearsal, text="Quand pouvez-vous passer ?", turn_index=1, now=NOW)
    db_session.commit()

    assert rehearsal.turns[1]["assistance"] == str(AssistanceLevel.SUGGESTED_RESPONSE)
    # Both points are covered by now, so the turn is correct — and still only
    # *supported*, because the phrases were on screen.
    assert rehearsal.turns[1]["evidence_kind"] == "produced_supported"


def test_a_register_correction_from_the_shared_module_is_dropped_for_a_tu_rehearsal():
    from app.services.journey_contracts import Correction

    vous_rule = Correction(
        span_fr="tu peux",
        corrected_fr="vous pouvez",
        note_native="Margaux still uses vous with you here, so use vous pouvez.",
    )
    assert sanitize_correction(vous_rule, register="tu") is None
    # Even on a vous rehearsal, a note that names a character never ships.
    assert sanitize_correction(vous_rule, register="vous") is None

    plain = Correction(
        span_fr="je prend",
        corrected_fr="je prends",
        note_native="With je, prendre ends in -s: je prends.",
    )
    assert sanitize_correction(plain, register="tu") is plain
    assert sanitize_correction(None, register="vous") is None


# ---------------------------------------------------------------------------
# 6. The debrief
# ---------------------------------------------------------------------------


def _rehearse(db_session, user, service) -> Rehearsal:
    rehearsal = service.declare(user, declaration="call the landlord, tuesday", now=NOW)
    service.respond(
        user, rehearsal, text="Bonjour, le chauffage est en panne.", turn_index=0, now=NOW
    )
    service.respond(user, rehearsal, text="Vous venez quand ?", turn_index=1, now=NOW)
    db_session.commit()
    return rehearsal


def test_the_debrief_opens_on_the_declared_date_and_not_before(db_session):
    user = _user(db_session)
    service = _service(db_session)
    rehearsal = _rehearse(db_session, user, service)

    assert rehearsal.event_date == date(2026, 9, 15)
    assert not debrief_available(rehearsal, today=TODAY)
    assert debrief_available(rehearsal, today=date(2026, 9, 15))
    assert debrief_available(rehearsal, today=date(2026, 9, 20))

    with pytest.raises(RehearsalRefused) as caught:
        service.debrief(user, rehearsal, outcome="done", free_line="", now=NOW)
    assert caught.value.code == "debrief_not_due"


def test_with_no_date_the_debrief_is_offered_as_soon_as_the_rehearsal_is_done(db_session):
    user = _user(db_session)
    brief = {**GOOD_BRIEF, "date_iso": None, "date_text": "un de ces jours"}
    service = _service(db_session, _FakeLLM(brief=brief))
    rehearsal = _rehearse(db_session, user, service)

    assert rehearsal.event_date is None
    assert debrief_available(rehearsal, today=TODAY)


@pytest.mark.parametrize("outcome", ["done", "partly", "not_yet"])
def test_the_three_outcomes_are_recorded_as_the_success_metric(db_session, outcome):
    user = _user(db_session)
    service = _service(db_session)
    rehearsal = _rehearse(db_session, user, service)
    later = datetime(2026, 9, 16, 9, 0, tzinfo=UTC)

    service.debrief(user, rehearsal, outcome=outcome, free_line="", now=later)
    db_session.commit()

    assert rehearsal.status == "debriefed"
    assert rehearsal.outcome == outcome
    assert rehearsal.debrief["outcome"] == outcome
    # SQLite drops the offset; the instant is what matters.
    assert rehearsal.debriefed_at.replace(tzinfo=UTC) == later


def test_an_unknown_outcome_is_refused(db_session):
    user = _user(db_session)
    service = _service(db_session)
    rehearsal = _rehearse(db_session, user, service)
    with pytest.raises(RehearsalRefused) as caught:
        service.debrief(
            user,
            rehearsal,
            outcome="brilliant",
            free_line="",
            now=datetime(2026, 9, 16, tzinfo=UTC),
        )
    assert caught.value.code == "unknown_outcome"


def test_the_free_line_is_corrected(db_session):
    user = _user(db_session)
    llm = _FakeLLM(
        correction={
            "corrected_fr": "J’ai appelé et il vient jeudi.",
            "note_fr": "« appelé » prend un accent.",
            "already_correct": False,
        }
    )
    service = _service(db_session, llm)
    rehearsal = _rehearse(db_session, user, service)

    service.debrief(
        user,
        rehearsal,
        outcome="done",
        free_line="J'ai appele et il vient jeudi.",
        now=datetime(2026, 9, 16, tzinfo=UTC),
    )
    db_session.commit()

    assert llm.correction_calls == 1
    assert rehearsal.debrief["corrected_fr"] == "J’ai appelé et il vient jeudi."
    assert rehearsal.debrief["correction_available"] is True


def test_an_uncorrected_line_says_so_rather_than_passing_as_correct(db_session):
    user = _user(db_session)
    service = _service(db_session, _FakeLLM(correction=None))  # the corrector raises
    rehearsal = _rehearse(db_session, user, service)

    service.debrief(
        user,
        rehearsal,
        outcome="partly",
        free_line="J'ai appele.",
        now=datetime(2026, 9, 16, tzinfo=UTC),
    )
    db_session.commit()

    assert rehearsal.debrief["correction_available"] is False
    assert rehearsal.debrief["corrected_fr"] is None
    assert rehearsal.outcome == "partly"


# ---------------------------------------------------------------------------
# 7. Cost, cap and honest failure
# ---------------------------------------------------------------------------


def test_every_real_call_writes_a_priced_pilot_row(db_session):
    user = _user(db_session)
    llm = _FakeLLM(
        correction={"corrected_fr": "J’ai appelé.", "note_fr": "accent", "already_correct": False}
    )
    service = _service(db_session, llm)
    rehearsal = _rehearse(db_session, user, service)
    service.debrief(
        user,
        rehearsal,
        outcome="done",
        free_line="J'ai appele.",
        now=datetime(2026, 9, 16, tzinfo=UTC),
    )
    db_session.commit()

    prepared = _events(db_session, PREPARE_EVENT_TYPE, user)
    assert len(prepared) == 1
    assert prepared[0].cost_usd == pytest.approx(0.004)
    assert prepared[0].payload["cost_known"] is True

    turns = _events(db_session, TURN_EVENT_TYPE, user)
    assert len(turns) == 2
    # No live model reply in the test provider-isolated path, so the turn's own
    # cost is known to be nothing rather than merely assumed.
    assert all(row.payload["cost_known"] is True for row in turns)

    debriefs = _events(db_session, DEBRIEF_EVENT_TYPE, user)
    assert len(debriefs) == 1
    assert debriefs[0].payload["outcome"] == "done"
    corrections = _events(db_session, DEBRIEF_EVENT_TYPE + "_correction", user)
    assert len(corrections) == 1
    assert corrections[0].cost_usd == pytest.approx(0.0002)


def test_the_weekly_cap_is_hard_and_counts_abandoned_rehearsals(db_session, monkeypatch):
    from app.services import rehearsal as module

    monkeypatch.setattr(module.settings, "ATELIER_REHEARSAL_WEEKLY_CAP", 2, raising=False)
    user = _user(db_session)
    service = _service(db_session)

    first = service.declare(user, declaration="call the landlord", now=NOW)
    service.abandon(first)
    db_session.commit()
    second = service.declare(user, declaration="ask about the parcel", now=NOW)
    service.abandon(second)
    db_session.commit()

    # WP-37 re-pin. `Rehearsal.created_at` is a server default — real wall-clock
    # — while the window arithmetic below is driven from the frozen `NOW`. The
    # test therefore passed only on the day it was written: from the next
    # morning, rows stamped "today" still sat inside `NOW + 8 days`' window and
    # the slot never freed. Stamping the rows with the same clock the assertion
    # uses is what makes this a test of the seven-day window rather than of the
    # date it is run on.
    for row in (first, second):
        row.created_at = NOW
    db_session.commit()

    state = cap_state(db_session, user, now=NOW)
    assert state["limit"] == 2
    assert state["used"] == 2
    assert state["remaining"] == 0
    # The row's own clock decides when the slot frees, so the assertion is that
    # a date exists and is a week out — never a hard-coded instant.
    assert state["next_slot_at"] is not None
    with pytest.raises(RehearsalRefused) as caught:
        service.declare(user, declaration="one more", now=NOW)
    assert caught.value.code == "weekly_cap_reached"

    # Eight days later the oldest has rolled out of the window.
    assert cap_state(db_session, user, now=NOW + timedelta(days=8))["remaining"] == 2


def test_a_cap_of_zero_switches_the_feature_off(db_session, monkeypatch):
    from app.services import rehearsal as module

    monkeypatch.setattr(module.settings, "ATELIER_REHEARSAL_WEEKLY_CAP", 0, raising=False)
    user = _user(db_session)
    with pytest.raises(RehearsalRefused) as caught:
        _service(db_session).declare(user, declaration="call the landlord", now=NOW)
    assert caught.value.code == "rehearsal_disabled"


def test_one_open_rehearsal_at_a_time(db_session):
    user = _user(db_session)
    service = _service(db_session)
    service.declare(user, declaration="call the landlord", now=NOW)
    db_session.commit()
    with pytest.raises(RehearsalRefused) as caught:
        service.declare(user, declaration="something else", now=NOW)
    assert caught.value.code == "rehearsal_already_open"


def test_a_provider_failure_yields_non_preparee_and_keeps_the_declaration(db_session):
    user = _user(db_session)
    llm = _FakeLLM(raise_on_prepare=True)
    service = _service(db_session, llm)
    rehearsal = service.declare(user, declaration="call the landlord, tuesday", now=NOW)
    db_session.commit()

    assert rehearsal.status == "not_prepared"
    assert rehearsal.scene == {}
    assert rehearsal.failure_reason == "provider_failed"
    assert rehearsal.declaration == "call the landlord, tuesday"
    assert llm.prepare_calls == 2  # both attempts spent, then it stopped
    # Nothing was billed for a call that produced nothing usable.
    assert _events(db_session, PREPARE_EVENT_TYPE, user) == []

    view = public_view(rehearsal, today=TODAY)
    assert view["status"] == "not_prepared"
    assert view["scene"] is None


def test_no_provider_at_all_is_the_same_honest_state(db_session):
    user = _user(db_session)
    service = RehearsalService(db_session, llm_service=None)
    rehearsal = service.declare(user, declaration="call the landlord", now=NOW)
    db_session.commit()

    assert rehearsal.status == "not_prepared"
    assert rehearsal.failure_reason == "provider_unavailable"


def test_a_second_preparation_attempt_can_succeed(db_session):
    user = _user(db_session)
    service = _service(db_session, _FakeLLM(raise_on_prepare=True))
    rehearsal = service.declare(user, declaration="call the landlord", now=NOW)
    assert rehearsal.status == "not_prepared"

    RehearsalService(db_session, llm_service=_FakeLLM()).prepare(user, rehearsal, now=NOW)
    db_session.commit()
    assert rehearsal.status == "ready"
    assert rehearsal.failure_reason is None


# ---------------------------------------------------------------------------
# 8. What the client may see
# ---------------------------------------------------------------------------


def test_the_private_rubric_and_the_cues_never_leave_while_the_rehearsal_is_live(db_session):
    user = _user(db_session)
    service = _service(db_session)
    rehearsal = service.declare(user, declaration="call the landlord", now=NOW)
    db_session.commit()

    view = public_view(rehearsal, today=TODAY)
    assert view["scene"]["rubric_native"] is None
    assert view["scene"]["phrases"] == []
    serialized = json.dumps(view, ensure_ascii=False)
    assert "cues" not in serialized
    assert "chauffage" not in serialized or "Le chauffage est en panne." not in serialized
    assert GOOD_SCENE["rubric_native"] not in serialized


def test_the_rubric_is_released_once_it_can_no_longer_be_the_answer(db_session):
    user = _user(db_session)
    service = _service(db_session)
    rehearsal = _rehearse(db_session, user, service)

    view = public_view(rehearsal, today=TODAY)
    assert view["scene"]["rubric_native"] == GOOD_SCENE["rubric_native"]
    assert view["result"]["outcome"] == str(TaskOutcome.MET)
    assert view["result"]["points_covered"] == 2


def test_the_phrases_appear_only_after_they_are_asked_for(db_session):
    user = _user(db_session)
    service = _service(db_session)
    rehearsal = service.declare(user, declaration="call the landlord", now=NOW)
    assert public_view(rehearsal, today=TODAY)["scene"]["phrases_revealed"] is False

    service.reveal_phrases(rehearsal)
    db_session.commit()
    view = public_view(rehearsal, today=TODAY)
    assert view["scene"]["phrases_revealed"] is True
    assert len(view["scene"]["phrases"]) == 2


# ---------------------------------------------------------------------------
# 9. The digest line
# ---------------------------------------------------------------------------


def test_the_digest_reports_the_real_outcome_and_never_an_empty_percentage(db_session):
    user = _user(db_session)
    service = _service(db_session)
    assert "nothing to report" in rehearsal_digest_line(db_session, since=TODAY)

    rehearsal = _rehearse(db_session, user, service)
    # A window no other test in this module debriefs into.
    later = datetime(2026, 10, 2, 9, 0, tzinfo=UTC)
    service.debrief(user, rehearsal, outcome="done", free_line="", now=later)
    db_session.commit()

    line = rehearsal_digest_line(db_session, since=date(2026, 10, 2))
    assert "done:1" in line
    assert "carried out for real: 1/1 (100%)" in line
