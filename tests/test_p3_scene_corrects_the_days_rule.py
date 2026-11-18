"""P3 (pilot 17 Nov): the scene corrects what the day teaches.

Walk 17 Nov (B1, days 3–5; «b1-part2.md», «check2-day1-b1.md»): on the day the
subjunctive was the rule, «je voudrais que tu reviens», «que Lila vient», «avant que je
prends» got one tense flag; elisions were flagged while missing subjunctives passed, and
a note could be «La forme correcte est « je veux que quelqu'un me dise ».» — the
corrected form again, no rule. The tutor lane was asked for «the most structural» error
and never told the day's rule.

Pinned here, with fake tutor answers (no model):

* the tutor payload carries the day's rule and the week's, as the rule cards state them;
* an error against the day's rule is the one shown first, even when the tutor listed an
  elision before it;
* a note that only restates the corrected form is refused: the rule's own line replaces
  it when the app can see the correction is about that rule, otherwise it is not shown.
"""

from __future__ import annotations

import importlib
import time
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.db.models.grammar import GrammarConcept, UserGrammarProgress
from app.db.models.user import User
from app.services import correction_contract
from app.services import living_story as engine
from app.services import story_lanes as lanes
from tests.test_living_story import turn_fixture

TEXT = "Je voudrais que tu reviens demain, il fait froid dans le appartement."
SUBJ_ID = "FR2_B12_SUBJ_WILL"
SUBJ_RULE_EN = "When you want someone else to act: vouloir, préférer, aimer que + subjonctif. Same person: infinitive."
RESTATED = "La forme correcte est « que tu reviennes »."


def _rules() -> dict:
    """``day_rules.for_turn`` as it reads the subjunctive's own day (no database)."""

    from types import SimpleNamespace

    from app.services.grammar_units import regex_patterns, unit_detectors

    unit = SimpleNamespace(external_id=SUBJ_ID, id=1, level="B1", name="", description="", category="")
    return {
        "today": {
            "id": SUBJ_ID,
            "name": "Subjonctif après vouloir que",
            "rule": SUBJ_RULE_EN,
            "detectors": regex_patterns(unit_detectors(unit)),
        },
        "recent": [{"id": "FR2_A2_PASSE_COMPOSE_ETRE", "name": "Passé composé avec être", "rule": "x", "detectors": []}],
    }


def _payload(text: str = TEXT, *, level: str = "A2", rules: dict | None = None, language: str = "en") -> dict:
    return {
        "learner_text": text,
        "history": [],
        "scene": {},
        "story": {
            "learner": {"address": "neutral"},
            "level": level,
            "commitments": [],
            "control_language": language,
        },
        "targets": [],
        "turn_plan": {},
        **({"day_rules": rules} if rules else {}),
    }


ELISION = {
    "span_fr": "le appartement",
    "corrected_fr": "l'appartement",
    "note_native": "« le » drops its vowel before a vowel: « l'appartement ».",
    "rule_id": None,
}
SUBJ = {
    "span_fr": "que tu reviens",
    "corrected_fr": "que tu reviennes",
    "note_native": "After « je voudrais que » the verb takes the subjunctive.",
    "rule_id": SUBJ_ID,
}


def _verdict(*corrections: dict, quotes: tuple[str, ...] = ()) -> lanes.TutorVerdict:
    return lanes.TutorVerdict.model_validate(
        {"outcome": "partially_met", "evidence_quotes": list(quotes), "corrections": list(corrections)}
    )


# ---------------------------------------------------------------------------
# The tutor is told the day's rule
# ---------------------------------------------------------------------------


def test_the_tutor_payload_carries_the_days_rule_and_the_weeks():
    sent = lanes.tutor_payload(_payload(rules=_rules()))

    assert sent["rules"]["today"] == {"id": SUBJ_ID, "name": "Subjonctif après vouloir que", "rule": SUBJ_RULE_EN}
    assert [row["id"] for row in sent["rules"]["recent"]] == ["FR2_A2_PASSE_COMPOSE_ETRE"]
    # The app's own detectors never reach a model, the ending lane never gets the rules.
    assert "detectors" not in str(sent)
    assert "day_rules" not in lanes.story_payload(_payload(rules=_rules()), {})
    assert "rules.today" in lanes.TUTOR and "only «the correct form is" in lanes.TUTOR


def _user(db_session) -> User:
    user = User(
        id=uuid4(),
        email=f"p3-{uuid4().hex[:8]}@example.com",
        hashed_password="x",
        native_language="de",
        target_language="fr",
        proficiency_level="B1",
        cefr_estimate="B1.1",
        daily_goal_minutes=20,
    )
    db_session.add(user)
    db_session.commit()
    return user


def _concept(db_session, external_id: str, level: str = "B1") -> GrammarConcept:
    concept = db_session.query(GrammarConcept).filter(GrammarConcept.external_id == external_id).one_or_none()
    if concept is None:
        concept = GrammarConcept(
            language="fr", level=level, name=external_id, external_id=external_id, category="Verb",
            description="", difficulty_order=10, active=True,
        )
        db_session.add(concept)
        db_session.flush()
    return concept


def test_the_days_rule_is_read_from_the_learners_introductions(db_session):
    user = _user(db_session)
    now = datetime(2026, 11, 18, 9, 0, tzinfo=UTC)
    week = _concept(db_session, "FR2_B12_SUBJ_FORM")
    today = _concept(db_session, SUBJ_ID)
    old = _concept(db_session, "FR2_B12_SUBJ_NECESSITY")
    for concept, introduced in ((week, now - timedelta(days=3)), (today, now - timedelta(hours=1)), (old, now - timedelta(days=10))):
        db_session.add(UserGrammarProgress(user_id=user.id, concept_id=concept.id, introduced_at=introduced))
    db_session.flush()

    day_rules = importlib.import_module("app.services.day_rules")
    rules = day_rules.for_turn(db_session, user, control_language="de", now=now)

    assert rules["today"]["id"] == SUBJ_ID
    assert rules["today"]["rule"].startswith("Wenn eine andere Person handeln soll")
    assert rules["today"]["name"]
    assert [row["id"] for row in rules["recent"]] == ["FR2_B12_SUBJ_FORM"]  # ten days ago is not this week
    # The page's own rule outranks the learner's latest introduction.
    focused = day_rules.for_turn(db_session, user, control_language="de", now=now, focus_unit_id=week.id)
    assert focused["today"]["id"] == "FR2_B12_SUBJ_FORM"
    assert SUBJ_ID in [row["id"] for row in focused["recent"]]


# ---------------------------------------------------------------------------
# The error against the day's rule is the one shown
# ---------------------------------------------------------------------------


def test_an_error_against_the_days_rule_is_corrected_before_an_elision():
    # The walk's order: the elision listed first, the subjunctive after it.
    verdict = _verdict(ELISION, SUBJ)
    lanes.validate_tutor(verdict, _payload(rules=_rules()))

    assert (verdict.correction_span_fr, verdict.correction_fr) == ("que tu reviens", "que tu reviennes")
    assert verdict.corrections[0].rule_id == SUBJ_ID


def test_a_rule_id_the_day_does_not_teach_ranks_nothing():
    claimed = {**ELISION, "rule_id": "INVENTED"}
    verdict = _verdict(claimed, {**SUBJ, "rule_id": None})
    lanes.validate_tutor(verdict, _payload(rules=_rules()))

    assert verdict.correction_span_fr == "le appartement"
    assert verdict.corrections[0].rule_id is None


def test_the_lane_shows_the_days_rule_first(monkeypatch):
    """The whole reply lane, with a fake tutor answering in the walk's order."""

    answers = {
        "TutorVerdict": _verdict(ELISION, SUBJ).model_dump(exclude={"correction_span_fr", "correction_fr", "correction_note_native"}),
        "VoiceReply": {
            "reply_fr": "D'accord, je reviens demain.",
            "understood_intent": "L'apprenant veut un retour demain.",
            "needs_clarification": False,
        },
    }

    def fake_call(system, request, schema, on_usage, **kwargs):
        return schema.model_validate(answers[schema.__name__]), {}

    monkeypatch.setattr(engine, "_json_call", fake_call)
    result = lanes.run_reply_lanes(_payload(rules=_rules()), deadline=time.monotonic() + 30)

    assert result.tutor.correction_span_fr == "que tu reviens"


# ---------------------------------------------------------------------------
# An explanation states a rule
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "note",
    [
        RESTATED,
        "The correct form is « que tu reviennes ».",
        "Die richtige Form ist „que tu reviennes“.",
        "On dit « que tu reviennes », pas « que tu reviens ».",
        "que tu reviennes",
    ],
)
def test_a_note_that_only_restates_the_form_says_nothing(note):
    assert not correction_contract.note_states_a_rule(note, "que tu reviens", "que tu reviennes")


@pytest.mark.parametrize(
    "note",
    [
        "After « je voudrais que » the verb takes the subjunctive.",
        "Nach „vouloir que“ steht der Subjonctif.",
        "Après « vouloir que », le verbe est au subjonctif.",
        "« je » drops its vowel before a vowel: « j'ai ».",
    ],
)
def test_a_note_that_names_a_rule_stands(note):
    assert correction_contract.note_states_a_rule(note, "que tu reviens", "que tu reviennes")


def test_a_restating_note_is_replaced_by_the_days_rule():
    verdict = _verdict({**SUBJ, "note_native": RESTATED})
    lanes.validate_tutor(verdict, _payload(rules=_rules()))

    assert verdict.correction_fr == "que tu reviennes"
    assert verdict.correction_note_native == SUBJ_RULE_EN


def test_a_restating_note_without_a_rule_the_app_can_see_is_not_shown():
    # No rule named: the correction goes, and the model-free edit stands in.
    verdict = _verdict({**SUBJ, "note_native": RESTATED, "rule_id": None})
    lanes.validate_tutor(verdict, _payload(rules=_rules()))
    assert verdict.correction_fr != "que tu reviennes"
    assert verdict.correction_span_fr == "le appartement"  # the rule pass's own elision
    # A rule named that the correction is not about (its detector does not see it): the same.
    wrong = _verdict({**ELISION, "note_native": "La forme correcte est « l'appartement ».", "rule_id": SUBJ_ID})
    lanes.validate_tutor(wrong, _payload("Il fait froid dans le appartement.", rules=_rules()))
    assert wrong.correction_note_native != SUBJ_RULE_EN
    assert correction_contract.note_states_a_rule(wrong.correction_note_native, "le appartement", "l'appartement")


def test_the_single_actor_path_refuses_a_restating_note_too():
    turn = engine.SemanticTurn.model_validate(
        {
            **turn_fixture(TEXT),
            "correction_span_fr": "que tu reviens",
            "correction_fr": "que tu reviennes",
            "correction_note_native": RESTATED,
        }
    )
    engine._validate_turn(turn, _payload(), reply_checks=False)
    assert turn.correction_fr != "que tu reviennes"


# ---------------------------------------------------------------------------
# Every guard before P3 still holds for each correction
# ---------------------------------------------------------------------------


def test_the_old_guards_hold_for_a_listed_correction():
    gender_only = {"span_fr": "perdu", "corrected_fr": "perdue", "note_native": "Agreement with the speaker.", "rule_id": None}
    verdict = _verdict(gender_only)
    lanes.validate_tutor(verdict, _payload("Je suis perdu."))
    assert verdict.correction_fr is None and verdict.corrections == []

    ungrounded = {"span_fr": "est", "corrected_fr": "es", "note_native": "After « tu » use « es ».", "rule_id": None}
    verdict = _verdict(ungrounded)
    lanes.validate_tutor(verdict, _payload("Ma grand-mère est malade."))
    assert verdict.correction_fr != "es"


def test_an_answer_in_the_shape_before_p3_is_still_read():
    verdict = lanes.TutorVerdict(
        outcome="met",
        evidence_quotes=["Tu est gentil."],
        correction_span_fr="est",
        correction_fr="es",
        correction_note_native="After « tu » the verb is « es ».",
    )
    lanes.validate_tutor(verdict, _payload("Tu est gentil."))
    assert (verdict.correction_span_fr, verdict.correction_fr) == ("est", "es")
    assert [c.corrected_fr for c in verdict.corrections] == ["es"]
