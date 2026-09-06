"""WP-06 — bounded purposeful conversation.

These tests pin the *contract* of ``app.services.journey_conversation``'s
grading half: bounded turns, paraphrase recognition, material ambiguity,
semantic success with a form error, target bypass, provider failure, and the
guard that stops a model widening the outcome vocabulary or writing arbitrary
keys into character memory.

The default path is deterministic and provider-free (``ATELIER_LLM_ENABLED`` is
false in ``tests/conftest.py``), exactly like WP-03. Real model quality is not
asserted here.
"""
from __future__ import annotations

from dataclasses import replace
from uuid import uuid4

import pytest

from app.db.models.user import User
from app.services import journey_content as jc_content
from app.services import journey_conversation as jc
from app.services.journey_contracts import (
    AssistanceLevel,
    AttemptAnswer,
    CapabilityKey,
    InputMode,
    ScenarioBrief,
    TargetKind,
    TargetRef,
    TaskOutcome,
)
from app.services.llm_service import LLMResult


@pytest.fixture(autouse=True)
def _clear_content_cache():
    jc_content.reset_content_cache()
    yield
    jc_content.reset_content_cache()


def _user(db_session, *, cefr: str = "A1.1", native: str = "en") -> User:
    user = User(
        id=uuid4(),
        email=f"{uuid4()}@journey.test",
        hashed_password="x",
        native_language=native,
        target_language="fr",
        proficiency_level="beginner",
        cefr_estimate=cefr,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _brief(db_session, user, key: CapabilityKey, *, band: str | None = None) -> ScenarioBrief:
    brief = jc_content.resolve_scenario_brief(
        db_session, user=user, scenario_key=key, level_band=band
    )
    assert isinstance(brief, ScenarioBrief)
    return brief


def _answer(text: str, *, mode: InputMode = InputMode.TEXT) -> AttemptAnswer:
    return AttemptAnswer(mode=mode, text=text)


def _evaluate(db_session, user, brief, text, *, turn_index=0, mode=InputMode.TEXT, history=None,
              assistance=AssistanceLevel.NONE, task=None):
    return jc.evaluate_response(
        db_session,
        user=user,
        scenario=brief,
        task=task or brief.response_task,
        answer=_answer(text, mode=mode),
        turn_index=turn_index,
        assistance=assistance,
        history=history,
    )


# --------------------------------------------------------------------------
# Bounded participation
# --------------------------------------------------------------------------


def test_turn_budget_is_two_normal_turns_plus_one_repair(db_session):
    user = _user(db_session)
    brief = _brief(db_session, user, CapabilityKey.ORDER_AT_CAFE)
    task = brief.response_task

    assert jc.normal_turns(task) == 2
    assert task.repair_allowed is True
    assert jc.turn_budget(task) == 3
    assert [jc.remaining_turns(task, index) for index in range(4)] == [2, 1, 0, 0]
    assert jc.is_repair_turn(task, 0) is False
    assert jc.is_repair_turn(task, 2) is True

    no_repair = replace(task, repair_allowed=False)
    assert jc.turn_budget(no_repair) == 2
    assert jc.remaining_turns(no_repair, 1) == 0


def test_turn_budget_is_identical_for_voice_and_text(db_session):
    user = _user(db_session)
    brief = _brief(db_session, user, CapabilityKey.ORDER_AT_CAFE)
    text = _evaluate(db_session, user, brief, "Un café au comptoir, s'il vous plaît.")
    voice = _evaluate(
        db_session,
        user,
        brief,
        "Un café au comptoir, s'il vous plaît.",
        mode=InputMode.VOICE,
    )
    assert text.outcome is voice.outcome is TaskOutcome.MET
    assert text.consequence.outcome_key == voice.consequence.outcome_key
    assert text.character_reply_fr == voice.character_reply_fr
    assert text.turn_consumed is voice.turn_consumed is True


def test_a_turn_past_the_budget_is_not_consumed_and_asks_for_no_repair(db_session):
    """Repeated respond: a late resubmission never books another turn."""

    user = _user(db_session)
    brief = _brief(db_session, user, CapabilityKey.ORDER_AT_CAFE)

    exhausted = _evaluate(db_session, user, brief, "Euh.", turn_index=2)
    assert exhausted.outcome is TaskOutcome.NOT_YET
    assert exhausted.needs_repair is False
    assert exhausted.turn_consumed is False
    # A not-yet exchange resolves the scene, but never warms the story.
    assert exhausted.consequence is None
    assert jc.default_outcome_key(brief.response_task, "order_at_cafe") == "not_ordered"

    repeated = _evaluate(db_session, user, brief, "Euh.", turn_index=5)
    assert repeated.needs_repair is False
    assert repeated.turn_consumed is False


def test_a_partial_first_turn_asks_for_another_turn(db_session):
    user = _user(db_session)
    brief = _brief(db_session, user, CapabilityKey.ORDER_AT_CAFE)
    result = _evaluate(db_session, user, brief, "Un café, s'il vous plaît.")
    assert result.outcome is TaskOutcome.PARTIALLY_MET
    assert result.needs_repair is True
    assert result.consequence is None
    assert "comptoir" in result.character_reply_fr


def test_intents_accumulate_across_turns(db_session):
    user = _user(db_session)
    brief = _brief(db_session, user, CapabilityKey.ORDER_AT_CAFE)
    history = [
        {"role": "learner", "text": "Un café, s'il vous plaît."},
        {"role": "character", "text": "Vous vous installez ou c'est à emporter ?"},
    ]
    result = _evaluate(db_session, user, brief, "En terrasse.", turn_index=1, history=history)
    assert result.outcome is TaskOutcome.MET
    assert result.needs_repair is False
    assert result.consequence.outcome_key == "served_at_terrace"
    assert "café" in result.character_reply_fr


# --------------------------------------------------------------------------
# Communicative success vs linguistic polish
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "outcome_key"),
    [
        ("Je voudrais un café, s'il vous plaît. Au comptoir.", "served_at_counter"),
        ("Un café au comptoir.", "served_at_counter"),
        ("Bonjour ! Pour moi ce sera un chocolat chaud, en terrasse.", "served_at_terrace"),
        ("Un thé à emporter, merci.", "takeaway"),
        ("Je prends un express, je reste ici.", "served_at_counter"),
    ],
)
def test_paraphrases_are_recognised_without_exact_string_matching(
    db_session, text, outcome_key
):
    user = _user(db_session)
    brief = _brief(db_session, user, CapabilityKey.ORDER_AT_CAFE)
    result = _evaluate(db_session, user, brief, text)
    assert result.outcome is TaskOutcome.MET
    assert result.consequence is not None
    assert result.consequence.outcome_key == outcome_key


def test_a_form_error_does_not_block_communicative_success_or_the_plot(db_session):
    """Semantic success with a form error: met objective, one correction, no punishment."""

    user = _user(db_session)
    brief = _brief(db_session, user, CapabilityKey.ORDER_AT_CAFE)
    result = _evaluate(
        db_session, user, brief, "Je prend un café, s'il vous plaît. En terrasse."
    )

    assert result.outcome is TaskOutcome.MET
    assert result.consequence.outcome_key == "served_at_terrace"
    assert result.correction is not None
    assert result.correction.span_fr == "Je prend"
    assert result.correction.corrected_fr == "Je prends"
    # The reply lands first and stays in character; it never mentions the slip.
    assert result.character_reply_fr.startswith("Un café en terrasse")
    assert "prends" not in result.character_reply_fr


def test_wrong_grammar_never_produces_an_unrelated_punitive_outcome(db_session):
    user = _user(db_session)
    brief = _brief(db_session, user, CapabilityKey.ARRANGE_MEETING)
    clean = _evaluate(db_session, user, brief, "Samedi, au marché.")
    messy = _evaluate(db_session, user, brief, "samedi au marche je peut venir")

    assert clean.consequence.outcome_key == "meeting_saturday_market"
    assert messy.consequence.outcome_key == "meeting_saturday_market"
    assert messy.outcome is TaskOutcome.MET
    assert messy.correction is not None
    assert messy.correction.span_fr == "je peut"


def test_a_correction_span_must_be_verbatim_from_the_learner_text(db_session):
    user = _user(db_session)
    brief = _brief(db_session, user, CapabilityKey.ORDER_AT_CAFE)
    result = _evaluate(db_session, user, brief, "Je prend un thé au comptoir.")
    assert result.correction is not None
    assert result.correction.is_valid_for("Je prend un thé au comptoir.")
    assert result.correction.span_fr in "Je prend un thé au comptoir."


def test_no_correction_is_manufactured_from_a_clean_answer(db_session):
    user = _user(db_session)
    brief = _brief(db_session, user, CapabilityKey.ORDER_AT_CAFE)
    result = _evaluate(db_session, user, brief, "Je voudrais un thé, en terrasse.")
    assert result.correction is None


def test_the_scene_register_is_enforced_in_the_correction_and_the_reply(db_session):
    """Same character, same register in both modalities and both directions."""

    user = _user(db_session)
    cafe = _brief(db_session, user, CapabilityKey.ORDER_AT_CAFE)
    result = _evaluate(db_session, user, cafe, "Tu peux me donner un café au comptoir ?")
    assert result.correction is not None
    assert result.correction.span_fr == "Tu peux"
    # The span is quoted verbatim, so its sentence-initial capital is preserved.
    assert result.correction.corrected_fr == "Vous pouvez"
    assert jc._register_ok(result.character_reply_fr, "vous")

    meeting = _brief(db_session, user, CapabilityKey.ARRANGE_MEETING)
    lila = _evaluate(db_session, user, meeting, "Samedi au marché, ça te va ?")
    assert jc._register_ok(lila.character_reply_fr, "tu")


# --------------------------------------------------------------------------
# Material ambiguity
# --------------------------------------------------------------------------


def test_material_ambiguity_clarifies_and_withholds_the_consequence(db_session):
    user = _user(db_session)
    brief = _brief(db_session, user, CapabilityKey.ORDER_AT_CAFE)
    result = _evaluate(db_session, user, brief, "Un café au comptoir, ou plutôt à emporter ?")

    assert result.outcome is TaskOutcome.PARTIALLY_MET
    assert result.needs_repair is True
    assert result.consequence is None
    assert "ou" in result.character_reply_fr


def test_immaterial_variation_does_not_trigger_a_clarification(db_session):
    user = _user(db_session)
    brief = _brief(db_session, user, CapabilityKey.ORDER_AT_CAFE)
    result = _evaluate(
        db_session, user, brief, "Bonjour Margaux, un café au comptoir s'il vous plaît, merci !"
    )
    assert result.needs_repair is False
    assert result.consequence.outcome_key == "served_at_counter"


def test_ambiguity_on_the_last_turn_still_resolves_to_a_declared_outcome(db_session):
    user = _user(db_session)
    brief = _brief(db_session, user, CapabilityKey.ORDER_AT_CAFE)
    result = _evaluate(
        db_session, user, brief, "Un café au comptoir, ou plutôt à emporter ?", turn_index=2
    )
    assert result.needs_repair is False
    assert result.turn_consumed is False
    # The clarification can no longer be asked, so the declared default stands.
    assert result.consequence.outcome_key == "served_at_counter"


def test_a_scene_fact_conflict_is_corrected_rather_than_granted(db_session):
    """The Canal market only opens at the weekend (WP-03 required fact)."""

    user = _user(db_session, cefr="A2.1")
    brief = _brief(db_session, user, CapabilityKey.ARRANGE_MEETING, band="A2")
    result = _evaluate(db_session, user, brief, "Mardi au marché, vers dix heures.")

    # The plan contradicts a scene fact, so it is queried, not silently granted.
    assert result.needs_repair is True
    assert result.consequence is None
    assert result.correction is not None
    assert result.correction.span_fr == "Mardi"
    assert result.correction.corrected_fr == "Samedi"
    assert "week-end" in result.character_reply_fr

    final = _evaluate(
        db_session, user, brief, "Mardi au marché, vers dix heures.", turn_index=2
    )
    assert final.consequence.outcome_key == "meeting_postponed"


# --------------------------------------------------------------------------
# Typed consequences
# --------------------------------------------------------------------------


def test_every_proposed_outcome_key_is_declared_by_the_brief(db_session):
    user = _user(db_session)
    for key in CapabilityKey:
        brief = _brief(db_session, user, key)
        allowed = set(brief.response_task.allowed_outcomes)
        assert allowed
        assert allowed <= set(brief.resolution_lines)
        assert allowed <= set(brief.resolution_summaries)
        for text in ("Un café au comptoir.", "Samedi au marché.", "En retard, le métro."):
            result = _evaluate(db_session, user, brief, text, turn_index=2)
            if result.consequence is not None:
                assert result.consequence.outcome_key in allowed


def test_an_arbitrary_outcome_key_is_rejected_and_replaced_by_the_default(db_session):
    user = _user(db_session)
    brief = _brief(db_session, user, CapabilityKey.ORDER_AT_CAFE)
    task = brief.response_task

    assert jc.coerce_outcome_key("romy_pays_your_rent", task=task, scenario_key="order_at_cafe") == (
        "not_ordered"
    )
    assert jc.coerce_outcome_key(None, task=task, scenario_key="order_at_cafe") == (
        "not_ordered"
    )
    assert jc.coerce_outcome_key(
        "served_at_terrace", task=task, scenario_key="order_at_cafe"
    ) == "served_at_terrace"

    empty = replace(task, allowed_outcomes=[])
    assert jc.coerce_outcome_key("anything", task=empty, scenario_key="order_at_cafe") is None


def test_the_callback_fact_is_short_and_never_the_raw_answer(db_session):
    user = _user(db_session)
    brief = _brief(db_session, user, CapabilityKey.ORDER_AT_CAFE)
    result = _evaluate(
        db_session,
        user,
        brief,
        "Bonjour ! Alors je voudrais un thé en terrasse, s'il vous plaît, merci beaucoup.",
    )
    callback = result.consequence.callback_fr
    assert callback == "un thé en terrasse"
    assert len(callback.split()) <= jc.MAX_CALLBACK_WORDS
    assert "s'il vous plaît" not in callback


def test_indoor_and_outdoor_and_cafe_and_tea_produce_different_replies(db_session):
    user = _user(db_session)
    brief = _brief(db_session, user, CapabilityKey.ORDER_AT_CAFE)
    variants = {
        "Un café au comptoir.": "served_at_counter",
        "Un café en terrasse.": "served_at_terrace",
        "Un thé au comptoir.": "served_at_counter",
        "Un thé en terrasse.": "served_at_terrace",
        "Un thé à emporter.": "takeaway",
    }
    replies = {}
    for text, outcome_key in variants.items():
        result = _evaluate(db_session, user, brief, text)
        assert result.consequence.outcome_key == outcome_key
        replies[text] = result.character_reply_fr
    assert len(set(replies.values())) == len(variants)
    assert "thé" in replies["Un thé en terrasse."]
    assert "café" in replies["Un café en terrasse."]
    assert "terrasse" in replies["Un thé en terrasse."]
    assert "comptoir" in replies["Un thé au comptoir."]


# --------------------------------------------------------------------------
# Targets and evidence
# --------------------------------------------------------------------------


def _target(label: str) -> TargetRef:
    return TargetRef(
        kind=TargetKind.VOCABULARY,
        id=f"vocab-{label}",
        label_fr=label,
        label_native=label,
    )


def test_a_target_bypassed_by_a_correct_answer_is_not_a_lapse(db_session):
    user = _user(db_session)
    brief = _brief(db_session, user, CapabilityKey.ORDER_AT_CAFE)
    task = replace(brief.response_task, targets=[_target("un chocolat chaud")])

    result = _evaluate(db_session, user, brief, "Un café au comptoir.", task=task)

    assert result.outcome is TaskOutcome.MET
    assert result.observations == []


def test_a_used_target_is_independent_production_and_records_the_answer(db_session):
    user = _user(db_session)
    brief = _brief(db_session, user, CapabilityKey.ORDER_AT_CAFE)
    task = replace(brief.response_task, targets=[_target("en terrasse")])

    result = _evaluate(db_session, user, brief, "Un café en terrasse, s'il vous plaît.", task=task)

    assert len(result.observations) == 1
    observation = result.observations[0]
    assert str(observation.evidence_kind) == "produced_independent"
    assert observation.modality is InputMode.TEXT
    assert observation.learner_text == "Un café en terrasse, s'il vous plaît."


def test_a_revealed_solution_downgrades_the_same_target_to_supported(db_session):
    user = _user(db_session)
    brief = _brief(db_session, user, CapabilityKey.ORDER_AT_CAFE)
    task = replace(brief.response_task, targets=[_target("en terrasse")])

    result = _evaluate(
        db_session,
        user,
        brief,
        "Un café en terrasse, s'il vous plaît.",
        task=task,
        assistance=AssistanceLevel.SOLUTION,
    )
    assert str(result.observations[0].evidence_kind) == "produced_supported"
    assert result.assistance is AssistanceLevel.SOLUTION


def test_a_target_the_learner_got_wrong_is_recorded_as_not_yet(db_session):
    user = _user(db_session)
    brief = _brief(db_session, user, CapabilityKey.ORDER_AT_CAFE)
    task = replace(brief.response_task, targets=[_target("je prends")])

    result = _evaluate(db_session, user, brief, "Je prend un café au comptoir.", task=task)

    assert result.correction is not None
    assert len(result.observations) == 1
    assert str(result.observations[0].evidence_kind) == "not_yet"
    assert result.observations[0].corrected_text == "Je prends"


# --------------------------------------------------------------------------
# Modalities and provider failure
# --------------------------------------------------------------------------


def test_a_failed_transcription_neither_consumes_a_turn_nor_books_a_lapse(db_session):
    user = _user(db_session)
    brief = _brief(db_session, user, CapabilityKey.ORDER_AT_CAFE)
    task = replace(brief.response_task, targets=[_target("un café")])

    result = jc.evaluate_response(
        db_session,
        user=user,
        scenario=brief,
        task=task,
        answer=AttemptAnswer(mode=InputMode.VOICE, text="   "),
        turn_index=0,
        assistance=AssistanceLevel.NONE,
    )

    assert result.outcome is TaskOutcome.UNSCORED
    assert result.pending is True
    assert result.turn_consumed is False
    assert result.needs_repair is False
    assert result.observations == []
    assert result.consequence is None
    assert result.character_reply_fr is None
    assert result.failure_reason == "voice_transcription_unavailable"


def test_a_mid_turn_timeout_is_an_unscored_response_not_a_mistake(db_session):
    result = jc.unscored_response_evaluation(
        assistance=AssistanceLevel.HINT, reason="grading_timeout"
    )
    assert result.outcome is TaskOutcome.UNSCORED
    assert result.pending is True
    assert result.turn_consumed is False
    assert result.observations == []
    assert result.failure_reason == "grading_timeout"


def test_an_empty_text_answer_is_unscored_rather_than_a_failed_attempt(db_session):
    user = _user(db_session)
    brief = _brief(db_session, user, CapabilityKey.ORDER_AT_CAFE)
    result = _evaluate(db_session, user, brief, "   ")
    assert result.outcome is TaskOutcome.UNSCORED
    assert result.turn_consumed is False
    assert result.failure_reason == "empty_answer"


def test_text_stays_available_when_the_brief_was_built_for_voice(db_session):
    user = _user(db_session)
    voice_brief = jc_content.resolve_scenario_brief(
        db_session,
        user=user,
        scenario_key=CapabilityKey.ORDER_AT_CAFE,
        input_mode=InputMode.VOICE,
    )
    assert isinstance(voice_brief, ScenarioBrief)
    result = _evaluate(db_session, user, voice_brief, "Un café au comptoir.")
    assert result.outcome is TaskOutcome.MET
    assert result.turn_consumed is True


def test_an_authored_reply_is_marked_as_authored(db_session):
    user = _user(db_session)
    brief = _brief(db_session, user, CapabilityKey.ORDER_AT_CAFE)
    result = _evaluate(db_session, user, brief, "Un café au comptoir.")
    assert jc.reply_source(result) == "authored"
    assert result.failure_reason == jc.REPLY_SOURCE_AUTHORED
    assert jc.reply_source(
        jc.unscored_response_evaluation(assistance=AssistanceLevel.NONE, reason="boom")
    ) == "none"


# --------------------------------------------------------------------------
# The optional model layer may never widen the vocabulary
# --------------------------------------------------------------------------


class _StubLLM:
    def __init__(self, payloads: list[str]) -> None:
        self.payloads = list(payloads)
        self.calls = 0

    def generate_chat_completion(self, *args, **kwargs):  # noqa: ANN002, ANN003
        self.calls += 1
        content = self.payloads.pop(0) if self.payloads else "{}"
        if isinstance(content, Exception):
            raise content
        return LLMResult(
            provider="stub",
            model="stub-1",
            content=content,
            prompt_tokens=1,
            completion_tokens=1,
            total_tokens=2,
            cost=0.0,
            raw_response={},
        )


@pytest.fixture()
def _model_enabled(monkeypatch):
    """Inject a stub provider into the conversation layer only.

    ``ATELIER_LLM_ENABLED`` is deliberately left false. Flipping the real flag
    would also switch on WP-03's scenario generator, which would reach a live
    provider with the key in ``.env`` — these tests must stay hermetic.
    """

    def _install(payloads):
        stub = _StubLLM(payloads)
        monkeypatch.setattr(jc, "_conversation_llm", lambda: stub)
        return stub

    return _install


def test_no_provider_is_reached_while_the_flag_is_off(db_session, monkeypatch):
    """The default grading path is deterministic and provider-free."""

    from app.config import settings
    from app.services.llm_service import LLMService

    assert settings.ATELIER_LLM_ENABLED is False

    def _boom(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("the conversation layer must not call a provider")

    monkeypatch.setattr(LLMService, "generate_chat_completion", _boom, raising=False)
    monkeypatch.setattr(LLMService, "text_to_speech", _boom, raising=False)
    monkeypatch.setattr(LLMService, "transcribe_audio", _boom, raising=False)

    user = _user(db_session)
    brief = _brief(db_session, user, CapabilityKey.ORDER_AT_CAFE)
    result = _evaluate(db_session, user, brief, "Un thé en terrasse, s'il vous plaît.")

    assert jc.reply_source(result) == "authored"
    assert result.consequence.outcome_key == "served_at_terrace"


def test_a_valid_model_reply_is_used_and_marked_as_a_model_reply(db_session, _model_enabled):
    user = _user(db_session)
    brief = _brief(db_session, user, CapabilityKey.ORDER_AT_CAFE)
    stub = _model_enabled(
        ['{"reply_fr": "Un thé en terrasse, tout de suite.", "outcome_key": "served_at_terrace"}']
    )

    result = _evaluate(db_session, user, brief, "Un thé en terrasse.")

    assert stub.calls == 1
    assert result.character_reply_fr == "Un thé en terrasse, tout de suite."
    assert jc.reply_source(result) == "model"
    assert result.consequence.outcome_key == "served_at_terrace"


def test_a_model_outcome_key_outside_the_brief_is_rejected(db_session, _model_enabled):
    user = _user(db_session)
    brief = _brief(db_session, user, CapabilityKey.ORDER_AT_CAFE)
    _model_enabled(
        [
            '{"reply_fr": "Voilà.", "outcome_key": "margaux_lends_you_money"}',
            '{"reply_fr": "Voilà.", "outcome_key": "margaux_lends_you_money"}',
        ]
    )

    result = _evaluate(db_session, user, brief, "Un thé en terrasse.")

    assert result.consequence.outcome_key == "served_at_terrace"
    assert jc.reply_source(result) == "authored"
    assert "terrasse" in result.character_reply_fr


def test_a_model_that_invents_a_memory_field_is_discarded_whole(db_session, _model_enabled):
    """An unsupported arbitrary memory field must never reach character memory."""

    user = _user(db_session)
    brief = _brief(db_session, user, CapabilityKey.ORDER_AT_CAFE)
    payload = (
        '{"reply_fr": "Voilà.", "outcome_key": "served_at_terrace", '
        '"character_memory": {"margaux_owes_you": true}, "closeness_delta": 5}'
    )
    _model_enabled([payload, payload])

    result = _evaluate(db_session, user, brief, "Un thé en terrasse.")

    assert jc.reply_source(result) == "authored"
    assert result.consequence.outcome_key == "served_at_terrace"
    assert result.consequence.character_id == brief.character_id
    parsed = jc._parse_model_reply(
        payload, task=brief.response_task, scenario_key="order_at_cafe", register="vous"
    )
    assert parsed is None


def test_a_model_reply_in_the_wrong_register_is_discarded(db_session, _model_enabled):
    user = _user(db_session)
    brief = _brief(db_session, user, CapabilityKey.ORDER_AT_CAFE)
    payload = '{"reply_fr": "Tiens, tu veux ton café où ?", "outcome_key": "served_at_counter"}'
    _model_enabled([payload, payload])

    result = _evaluate(db_session, user, brief, "Un café au comptoir.")

    assert jc.reply_source(result) == "authored"
    assert jc._register_ok(result.character_reply_fr, "vous")


def test_a_provider_failure_falls_back_to_the_authored_reply(db_session, _model_enabled):
    user = _user(db_session)
    brief = _brief(db_session, user, CapabilityKey.ORDER_AT_CAFE)
    stub = _model_enabled([RuntimeError("provider down"), RuntimeError("provider down")])

    result = _evaluate(db_session, user, brief, "Un café au comptoir.")

    assert stub.calls == 2
    assert jc.reply_source(result) == "authored"
    assert result.outcome is TaskOutcome.MET
    assert result.consequence.outcome_key == "served_at_counter"


# --------------------------------------------------------------------------
# The other two scenarios
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "outcome_key"),
    [
        ("Samedi, au marché.", "meeting_saturday_market"),
        ("On se voit mardi au Mistral ?", "meeting_weekday_cafe"),
        ("Pas cette semaine, on remet ça.", "meeting_postponed"),
    ],
)
def test_meeting_choices_map_to_declared_outcomes(db_session, text, outcome_key):
    user = _user(db_session)
    brief = _brief(db_session, user, CapabilityKey.ARRANGE_MEETING)
    result = _evaluate(db_session, user, brief, text, turn_index=2)
    assert result.consequence.outcome_key == outcome_key


@pytest.mark.parametrize(
    ("text", "outcome_key"),
    [
        ("Je suis en retard, le métro est bloqué.", "romy_waits_at_bar"),
        ("Désolé, je suis en retard, viens à la station.", "romy_meets_at_station"),
        ("Le métro est bloqué, on remet ça à demain.", "romy_reschedules"),
    ],
)
def test_delay_choices_map_to_declared_outcomes(db_session, text, outcome_key):
    user = _user(db_session)
    brief = _brief(db_session, user, CapabilityKey.EXPLAIN_DELAY)
    result = _evaluate(db_session, user, brief, text, turn_index=2)
    assert result.consequence.outcome_key == outcome_key


def test_the_a2_delay_scene_asks_for_the_missing_arrival_time(db_session):
    user = _user(db_session, cefr="A2.1")
    brief = _brief(db_session, user, CapabilityKey.EXPLAIN_DELAY, band="A2")
    partial = _evaluate(db_session, user, brief, "Je suis en retard, le métro est bloqué.")
    assert partial.outcome is TaskOutcome.PARTIALLY_MET
    assert partial.needs_repair is True
    assert "heure" in partial.character_reply_fr

    full = _evaluate(
        db_session,
        user,
        brief,
        "J'arrive vers dix-neuf heures trente.",
        turn_index=1,
        history=[{"role": "learner", "text": "Je suis en retard, le métro est bloqué."}],
    )
    assert full.outcome is TaskOutcome.MET
    assert full.consequence.outcome_key == "romy_waits_at_bar"
    assert "dix-neuf heures trente" in full.character_reply_fr


# --------------------------------------------------------------------------
# The WP-05 handshake
# --------------------------------------------------------------------------


def test_the_evaluation_feeds_canonical_learning_evidence(db_session):
    from app.services import journey_learning as jl

    user = _user(db_session)
    brief = _brief(db_session, user, CapabilityKey.ORDER_AT_CAFE)
    task = replace(brief.response_task, targets=[_target("en terrasse")])
    journey_id, step_id = uuid4(), uuid4()
    session = jl.ensure_journey_learning_session(
        db_session, user=user, journey_id=journey_id, scenario_key=str(brief.scenario_key)
    )

    result = _evaluate(db_session, user, brief, "Je prend un café en terrasse.", task=task)
    assert result.outcome is TaskOutcome.MET
    assert result.correction is not None

    applied = jl.apply_learning_evidence(
        db_session,
        user=user,
        journey_id=journey_id,
        step_id=step_id,
        session=session,
        evaluation=result,
        modality=InputMode.TEXT,
    )
    db_session.commit()

    assert applied.applied_target_ids == [task.targets[0].id]
    # One target observation plus the single foreground correction.
    assert len(applied.source_keys) == 2

    replay = jl.apply_learning_evidence(
        db_session,
        user=user,
        journey_id=journey_id,
        step_id=step_id,
        session=session,
        evaluation=result,
        modality=InputMode.TEXT,
    )
    db_session.commit()
    assert set(replay.deduplicated_source_keys) == set(applied.source_keys)


def test_an_unscored_voice_failure_books_no_learning_evidence(db_session):
    from app.services import journey_learning as jl

    user = _user(db_session)
    brief = _brief(db_session, user, CapabilityKey.ORDER_AT_CAFE)
    task = replace(brief.response_task, targets=[_target("en terrasse")])
    journey_id, step_id = uuid4(), uuid4()
    session = jl.ensure_journey_learning_session(
        db_session, user=user, journey_id=journey_id, scenario_key=str(brief.scenario_key)
    )

    result = jc.evaluate_response(
        db_session,
        user=user,
        scenario=brief,
        task=task,
        answer=AttemptAnswer(mode=InputMode.VOICE, text=""),
        turn_index=0,
        assistance=AssistanceLevel.NONE,
    )
    applied = jl.apply_learning_evidence(
        db_session,
        user=user,
        journey_id=journey_id,
        step_id=step_id,
        session=session,
        evaluation=result,
        modality=InputMode.VOICE,
    )
    db_session.commit()

    assert result.turn_consumed is False
    assert applied.source_keys == []
    assert applied.applied_target_ids == []
    assert applied.learning_moment_id is None


def test_a_broken_tts_provider_never_blocks_the_turn(db_session, monkeypatch):
    """Audio is presentation. Grading and the reply never depend on it."""

    from app.services.llm_service import LLMService

    def _boom(*args, **kwargs):  # noqa: ANN002, ANN003
        raise RuntimeError("tts down")

    monkeypatch.setattr(LLMService, "text_to_speech", _boom, raising=False)
    monkeypatch.setattr(LLMService, "transcribe_audio", _boom, raising=False)

    user = _user(db_session)
    brief = _brief(db_session, user, CapabilityKey.ORDER_AT_CAFE)
    result = _evaluate(
        db_session, user, brief, "Un café au comptoir.", mode=InputMode.VOICE
    )

    assert result.outcome is TaskOutcome.MET
    assert result.character_reply_fr
    assert result.consequence.outcome_key == "served_at_counter"


def test_the_history_shape_the_state_machine_persists_is_understood(db_session):
    """WP-02 stores turn pairs as {"learner": ..., "character": ...}."""

    user = _user(db_session)
    brief = _brief(db_session, user, CapabilityKey.ORDER_AT_CAFE)
    history = [{"learner": "Un café, s'il vous plaît.", "character": "Où ça ?"}]

    result = _evaluate(db_session, user, brief, "En terrasse.", turn_index=1, history=history)

    assert result.outcome is TaskOutcome.MET
    assert result.consequence.outcome_key == "served_at_terrace"
    assert result.consequence.callback_fr == "un café en terrasse"


# ---------------------------------------------------------------------------
# The app's own advice must pass the app's own test (WP-12 defect D-3)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("scenario_key", list(CapabilityKey))
@pytest.mark.parametrize("band", ["A1", "A2"])
def test_every_authored_suggested_response_satisfies_its_own_objective(
    db_session, scenario_key: CapabilityKey, band: str
) -> None:
    """A learner who copies the app's model answer verbatim must be graded ``met``.

    ``help_kind: "suggested_response"`` charges the learner
    ``AssistanceLevel.SUGGESTED_RESPONSE`` for a revealed model answer. If that
    answer does not satisfy the step's own ``required_intents``, the learner is
    graded ``partially_met`` or ``not_yet``, earns no capability evidence and no
    keepsake, and is shown the failure ending — after doing exactly what the app
    told them to do (WP-12 defect D-3). This is the guard that keeps every
    authored variant honest, not just the one that was found broken.
    """

    user = _user(db_session)
    brief = _brief(db_session, user, scenario_key, band=band)
    assert brief.level_band == band
    suggested = brief.response_task.suggested_response_fr
    assert suggested, f"{scenario_key}/{band} offers suggested_response help with no text"

    evaluation = _evaluate(db_session, user, brief, suggested)
    assert evaluation.outcome is TaskOutcome.MET, (
        f"{scenario_key}/{band} suggests {suggested!r} but grades it "
        f"{evaluation.outcome.value} against {brief.response_task.required_intents}"
    )
    # The advice must also earn the day's consequence, not just the grade.
    assert evaluation.consequence is not None
    assert evaluation.consequence.outcome_key in brief.response_task.allowed_outcomes


# ---------------------------------------------------------------------------
# Endings name what the learner chose (WP-12 defect D-2)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("answer", "drink", "gloss"),
    [
        ("Je voudrais un thé, s'il vous plaît. Au comptoir.", "un thé", "tea"),
        ("Un chocolat chaud en terrasse, s'il vous plaît.", "un chocolat chaud", "hot chocolate"),
        ("Un thé à emporter, s'il vous plaît.", "un thé", "tea"),
        ("Je voudrais un café au comptoir, s'il vous plaît.", "un café", "coffee"),
    ],
)
@pytest.mark.parametrize("band", ["A1", "A2"])
def test_the_ending_serves_the_drink_that_was_ordered(
    db_session, band: str, answer: str, drink: str, gloss: str
) -> None:
    user = _user(db_session)
    brief = _brief(db_session, user, CapabilityKey.ORDER_AT_CAFE, band=band)
    if band == "A2":
        # A2 also requires one extra request before the day can resolve.
        answer = f"{answer[:-1]}, et un verre d'eau."
    evaluation = _evaluate(db_session, user, brief, answer)
    assert evaluation.consequence is not None, answer
    key = evaluation.consequence.outcome_key

    line = jc.resolution_line(brief, key, learner_texts=[answer])
    summary = jc.resolution_summary(brief, key, learner_texts=[answer])
    assert drink in line.lower(), line
    assert gloss in summary.lower(), summary
    for other, other_gloss in (
        ("un café", "coffee"),
        ("un thé", "tea"),
        ("un chocolat chaud", "hot chocolate"),
    ):
        if other == drink:
            continue
        assert other not in line.lower(), line
        assert other_gloss not in summary.lower(), summary


def test_an_ending_with_no_identifiable_choice_names_none(db_session) -> None:
    """No learner text, no invented detail — and never a raw template."""

    user = _user(db_session)
    for key in CapabilityKey:
        brief = _brief(db_session, user, key)
        for outcome in brief.response_task.allowed_outcomes:
            for text in (
                jc.resolution_line(brief, outcome),
                jc.resolution_summary(brief, outcome),
                jc.resolution_line(brief, outcome, learner_texts=["euh je sais pas"]),
            ):
                assert text, f"{key}/{outcome} has no ending"
                assert "{" not in text and "}" not in text, text
        if key is CapabilityKey.ORDER_AT_CAFE:
            for outcome in brief.response_task.allowed_outcomes:
                line = jc.resolution_line(brief, outcome)
                summary = jc.resolution_summary(brief, outcome)
                for word in ("café", "thé", "chocolat"):
                    assert word not in line.lower(), line
                for word in ("coffee", "tea", "chocolate"):
                    assert word not in summary.lower(), summary


def test_the_meeting_ending_names_the_day_that_was_proposed(db_session) -> None:
    """The same defect shape as D-2, audited in the other family that names a choice."""

    user = _user(db_session)
    brief = _brief(db_session, user, CapabilityKey.ARRANGE_MEETING)
    answer = "On se voit dimanche au marché ?"
    evaluation = _evaluate(db_session, user, brief, answer)
    assert evaluation.consequence is not None
    key = evaluation.consequence.outcome_key
    line = jc.resolution_line(brief, key, learner_texts=[answer])
    summary = jc.resolution_summary(brief, key, learner_texts=[answer])
    assert "dimanche" in line.lower(), line
    assert "samedi" not in line.lower(), line
    assert "sunday" in summary.lower(), summary
    assert "saturday" not in summary.lower(), summary


def test_the_ending_remembers_a_drink_named_in_an_earlier_turn(db_session) -> None:
    """A two-turn order ("un thé", then "au comptoir") still ends with the tea."""

    user = _user(db_session)
    brief = _brief(db_session, user, CapabilityKey.ORDER_AT_CAFE)
    first, second = "Je voudrais un thé.", "Au comptoir, s'il vous plaît."
    evaluation = _evaluate(
        db_session,
        user,
        brief,
        second,
        turn_index=1,
        history=[{"learner": first, "character": "Et vous vous installez où ?"}],
    )
    assert evaluation.outcome is TaskOutcome.MET
    assert evaluation.consequence is not None
    line = jc.resolution_line(
        brief, evaluation.consequence.outcome_key, learner_texts=[first, second]
    )
    summary = jc.resolution_summary(
        brief, evaluation.consequence.outcome_key, learner_texts=[first, second]
    )
    assert "un thé" in line.lower(), line
    assert "café" not in line.lower(), line
    assert "tea" in summary.lower() and "coffee" not in summary.lower(), summary
