"""WP-89 «Le fil» — the conversation is one conversation (backend half).

Replays the live walk of 2026-09-28 (W7/W8, the authored first-day café scene at
Le Mistral, an A1.1 learner) through the authored path with a fake provider
that returns the replies Margaux actually gave. Fake provider only; never a
paid call. Every test makes its own learner, so the order does not matter.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import replace
from typing import Any

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
    TaskOutcome,
)
from app.services.llm_service import LLMResult

W7_TURN = "Un cafe s'il vous plait"
W7_MODEL_LINE = (
    "Bien sûr, un café arrive tout de suite ; voulez-vous vous asseoir au comptoir, "
    "sur la terrasse couverte chauffée ou préférez-vous à emporter ?"
)
W8_TURN = "Bonjour ! Au comptoir, merci."
W8_MODEL_LINE = (
    "Bonjour ! Je vous apporte ça tout de suite au comptoir, voulez-vous quelque "
    "chose à boire en particulier ?"
)
GREETING_NUDGE = jc.PRAGMATIC_ELICITATION_FR[jc.pragmatics.MISSING_GREETING]["vous"]
A1_CAP = jc.REPLY_WORD_CAPS["A1"]


@pytest.fixture(autouse=True)
def _clear_content_cache():
    jc_content.reset_content_cache()
    yield
    jc_content.reset_content_cache()


def _user(db_session, *, cefr: str = "A1.1") -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"{uuid.uuid4()}@wp89.test",
        hashed_password="x",
        native_language="en",
        target_language="fr",
        proficiency_level="beginner",
        cefr_estimate=cefr,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _brief(db_session, user) -> ScenarioBrief:
    brief = jc_content.resolve_scenario_brief(
        db_session, user=user, scenario_key=CapabilityKey.ORDER_AT_CAFE
    )
    assert isinstance(brief, ScenarioBrief)
    assert jc._band(brief) == "A1"
    return brief


def _evaluate(db_session, user, brief, text, *, turn_index=0, history=None, task=None):
    return jc.evaluate_response(
        db_session,
        user=user,
        scenario=brief,
        task=task or brief.response_task,
        answer=AttemptAnswer(mode=InputMode.TEXT, text=text),
        turn_index=turn_index,
        assistance=AssistanceLevel.NONE,
        history=history,
    )


class _RoutingLLM:
    """Answers the grade prompt and the reply prompt separately, and records both."""

    def __init__(self, replies: list[str], grade: str | None = None) -> None:
        self.replies = list(replies)
        self.grade = grade or '{"outcome": "not_yet", "evidence_quotes": []}'
        self.reply_prompts: list[str] = []
        self.grade_calls = 0

    def generate_chat_completion(self, messages, **kwargs: Any) -> LLMResult:  # noqa: ANN001
        if kwargs.get("system_prompt") == jc._GRADE_SYSTEM_PROMPT:
            self.grade_calls += 1
            content = self.grade
        else:
            self.reply_prompts.append(messages[-1]["content"])
            content = self.replies.pop(0) if self.replies else "{}"
        return LLMResult(
            provider="fake",
            model="fake-1",
            content=content,
            prompt_tokens=1,
            completion_tokens=1,
            total_tokens=2,
            cost=0.0,
            raw_response={},
        )


@pytest.fixture()
def fake_llm(monkeypatch):
    def _install(replies: list[str], grade: str | None = None) -> _RoutingLLM:
        fake = _RoutingLLM(replies, grade)
        monkeypatch.setattr(jc, "_conversation_llm", lambda: fake)
        return fake

    return _install


def _reply(line: str) -> str:
    return json.dumps({"reply_fr": line}, ensure_ascii=False)


# ---------------------------------------------------------------------------
# The W7/W8 replay
# ---------------------------------------------------------------------------


def test_the_w7_w8_transcript_replays_at_level_and_never_forgets_the_coffee(
    db_session, fake_llm
):
    user = _user(db_session)
    brief = _brief(db_session, user)
    fake = fake_llm(
        [_reply(W8_MODEL_LINE), _reply(W8_MODEL_LINE)],
        grade='{"outcome": "partially_met", "evidence_quotes": ["Un cafe"]}',
    )

    first = _evaluate(db_session, user, brief, W7_TURN)
    # W7: no « bonjour » on the opening turn, and the scene goes on. The nudge
    # *is* the line — nothing is stacked after a line that moved the scene on,
    # and no model line is bought to be thrown away.
    assert first.character_reply_fr == GREETING_NUDGE
    assert not fake.reply_prompts
    assert jc.reply_source(first) == "authored"
    assert first.needs_repair is True
    assert jc.word_count(first.character_reply_fr) <= A1_CAP
    # W7's « Correct, with help »: the server says partially met, unassisted.
    # The label is the client mapping `partially_met` onto "supported".
    assert first.outcome is TaskOutcome.PARTIALLY_MET
    assert first.assistance is AssistanceLevel.NONE

    history = [{"learner": W7_TURN, "character": first.character_reply_fr}]
    second = _evaluate(db_session, user, brief, W8_TURN, turn_index=1, history=history)

    reply = second.character_reply_fr or ""
    assert jc.word_count(reply) <= A1_CAP, reply
    assert "boire" not in reply
    settled = jc.settled_facts(
        "order_at_cafe",
        jc._merge_signals(jc._signals(W8_TURN), [jc._signals(W7_TURN)]),
        jc._OutcomeChoice(key=None, categories=("counter",)),
    )
    assert {fact.slot for fact in settled} >= {"drink", "seat"}
    assert jc.reasked_fact(reply, settled) is None
    assert "café" in reply.lower() and "comptoir" in reply
    assert second.outcome is TaskOutcome.MET
    assert second.consequence is not None
    assert second.consequence.outcome_key == "served_at_counter"
    # Two refused attempts, then the authored line for that state.
    assert len(fake.reply_prompts) == jc.MAX_MODEL_ATTEMPTS
    assert jc.reply_source(second) == "authored"

    # Memory: the prompt carries the whole thread and the settled facts…
    prompt = fake.reply_prompts[0]
    assert f"Learner: {W7_TURN}" in prompt
    assert f"Margaux: {GREETING_NUDGE}" in prompt
    assert "the learner ordered un café" in prompt
    assert "the learner will have it au comptoir" in prompt
    # …and the level.
    assert f"at most {A1_CAP} words" in prompt
    # The retry is told why the first reply was refused.
    assert "Your previous reply was refused" in fake.reply_prompts[1]


def test_the_w7_line_is_refused_for_its_length_even_after_a_greeting(db_session, fake_llm):
    user = _user(db_session)
    brief = _brief(db_session, user)
    fake = fake_llm([_reply(W7_MODEL_LINE), _reply(W7_MODEL_LINE)])

    result = _evaluate(db_session, user, brief, "Bonjour, un café s'il vous plaît.")

    reply = result.character_reply_fr or ""
    assert len(fake.reply_prompts) == 2
    assert jc.reply_source(result) == "authored"
    assert jc.word_count(reply) <= A1_CAP, reply
    assert "bonjour d" not in reply.lower(), "no nudge: the learner greeted"
    assert "comptoir" in reply, "the authored line still asks where to sit"
    assert "?" in reply


def test_a_reply_that_reasks_the_drink_is_retried_and_a_good_retry_stands(
    db_session, fake_llm
):
    user = _user(db_session)
    brief = _brief(db_session, user)
    fake = fake_llm(
        [
            _reply("Au comptoir, parfait. Et vous buvez quoi ?"),
            _reply("Un café au comptoir, je vous le prépare."),
        ]
    )
    history = [{"learner": "Bonjour, un café.", "character": "Un café, très bien. Où ça ?"}]

    result = _evaluate(db_session, user, brief, "Au comptoir.", turn_index=1, history=history)

    assert len(fake.reply_prompts) == 2
    assert "already settled" in fake.reply_prompts[1]
    assert result.character_reply_fr == "Un café au comptoir, je vous le prépare."
    assert jc.reply_source(result) == "model"


def test_a_reply_full_of_words_the_learner_has_never_met_falls_back(db_session, fake_llm):
    user = _user(db_session)
    brief = _brief(db_session, user)
    rare = "Un café, parfait. Une viennoiserie artisanale saupoudrée, peut-être ?"
    fake = fake_llm([_reply(rare), _reply(rare)])

    result = _evaluate(db_session, user, brief, "Bonjour, un café, s'il vous plaît.")

    assert len(fake.reply_prompts) == 2
    assert "has not met" in fake.reply_prompts[1]
    assert jc.reply_source(result) == "authored"
    assert "viennoiserie" not in (result.character_reply_fr or "")


def test_the_level_and_reask_guards_as_units():
    assert jc.reply_level_issue(W7_MODEL_LINE, band="A1") is not None
    assert jc.reply_level_issue("Un café au comptoir, très bien.", band="A1") is None
    assert jc.reply_level_issue("Un café ; au comptoir.", band="A1") is not None
    assert jc.reply_level_issue("Un café ? Au comptoir ?", band="A1") is not None
    assert jc.reply_level_issue(W8_MODEL_LINE, band="B1") is None
    drink = [jc.SettledFact("drink", "un café", "the learner ordered un café")]
    assert jc.reasked_fact(W8_MODEL_LINE, drink) is not None
    assert jc.reasked_fact("Un café, très bien. Au comptoir ?", drink) is None
    assert jc.reasked_fact("Qu'est-ce que je vous sers ?", drink) is not None
    seat = [jc.SettledFact("seat", "au comptoir", "")]
    assert jc.reasked_fact("Vous vous installez où ?", seat) is not None
    assert jc.reasked_fact("Je vous le sers au comptoir.", seat) is None


# ---------------------------------------------------------------------------
# Nudges are never appended after a model line
# ---------------------------------------------------------------------------


def test_the_greeting_nudge_replaces_a_model_line_on_the_opening_turn(db_session, fake_llm):
    user = _user(db_session)
    brief = _brief(db_session, user)
    fake = fake_llm([_reply("Un café, très bien. Au comptoir ?")])

    result = _evaluate(db_session, user, brief, "Un café, s'il vous plaît.")

    assert result.character_reply_fr == GREETING_NUDGE
    assert not fake.reply_prompts
    assert result.consequence is None


def test_no_softener_nudge_is_appended_on_a_later_turn(db_session, fake_llm):
    user = _user(db_session)
    brief = _brief(db_session, user)
    fake_llm([_reply("Un thé, très bien. Au comptoir ou en terrasse ?")])
    history = [{"learner": "Bonjour !", "character": "Bonjour ! Qu'est-ce que je vous sers ?"}]

    result = _evaluate(
        db_session, user, brief, "Vous avez un thé ?", turn_index=1, history=history
    )

    reply = result.character_reply_fr or ""
    assert reply == "Un thé, très bien. Au comptoir ou en terrasse ?"
    assert "demandez ça comment" not in reply
    assert jc.reply_source(result) == "model"


# ---------------------------------------------------------------------------
# «Relance»
# ---------------------------------------------------------------------------


def test_a_minimal_correct_answer_earns_one_more_clause(db_session):
    user = _user(db_session)
    brief = _brief(db_session, user)
    assert brief.response_task.max_turns >= 2

    result = _evaluate(db_session, user, brief, "Café, terrasse.")

    assert result.outcome is TaskOutcome.MET
    assert result.needs_repair is True, "the planned second exchange is spent"
    assert result.character_reply_fr.endswith("Et avec ça ?")
    assert jc.word_count(result.character_reply_fr) <= A1_CAP
    assert result.consequence is not None, "the ending the learner earned stands"
    assert result.feedback_reason == jc.RELANCE_REASON

    # The next exchange is the last planned one: it closes, and asks nothing more.
    follow = _evaluate(
        db_session,
        user,
        brief,
        "Merci.",
        turn_index=1,
        history=[{"learner": "Café, terrasse.", "character": result.character_reply_fr}],
    )
    assert follow.needs_repair is False
    assert "Et avec ça ?" not in (follow.character_reply_fr or "")


def test_no_relance_without_a_planned_exchange_left(db_session):
    user = _user(db_session)
    brief = _brief(db_session, user)
    single = replace(brief.response_task, max_turns=1)

    result = _evaluate(db_session, user, brief, "Café, terrasse.", task=single)

    assert result.outcome is TaskOutcome.MET
    assert result.needs_repair is False
    assert "Et avec ça ?" not in (result.character_reply_fr or "")


def test_no_relance_for_a_full_answer_or_twice_in_one_scene(db_session):
    user = _user(db_session)
    brief = _brief(db_session, user)
    three = replace(brief.response_task, max_turns=3)

    full = _evaluate(
        db_session, user, brief, "Je voudrais un café au comptoir, s'il vous plaît.", task=three
    )
    assert full.needs_repair is False
    assert "Et avec ça ?" not in (full.character_reply_fr or "")

    again = _evaluate(
        db_session,
        user,
        brief,
        "Café, terrasse.",
        turn_index=1,
        task=three,
        history=[{"learner": "Thé.", "character": "Un thé, très bien. Et avec ça ?"}],
    )
    assert "Et avec ça ?" not in (again.character_reply_fr or "")


def test_the_minimal_answer_table():
    assert jc.is_minimal_answer("Bonjour ! Au comptoir, merci.", band="A1")
    assert not jc.is_minimal_answer("Un café au comptoir.", band="A1")
    assert jc.is_minimal_answer("Un café au comptoir.", band="A2")
    assert jc.is_minimal_answer("Je voudrais un café au comptoir, merci.", band="B1")


# ---------------------------------------------------------------------------
# The public thread (contract v1, additive)
# ---------------------------------------------------------------------------


def test_the_thread_is_on_the_next_turn_and_on_the_snapshot(db_session, monkeypatch):
    from app.schemas.daily_journey import JourneyAttemptRequest
    from app.services import daily_journey as journey_module
    from app.services.daily_journey import DailyJourneyService
    from app.services.daily_journey_adapters import build_default_adapters
    from tests.test_daily_journey_state import advance_to_respond, create_request, make_user

    monkeypatch.setattr(journey_module.settings, "ATELIER_DAILY_JOURNEY_ENABLED", True, raising=False)
    monkeypatch.setattr(journey_module.settings, "ATELIER_DAILY_JOURNEY_COHORT", "", raising=False)

    user = make_user(db_session, f"wp89-thread-{uuid.uuid4().hex[:8]}@example.com")
    service = DailyJourneyService(db_session, build_default_adapters())
    created, _ = service.create_journey(user, create_request())
    state, respond = advance_to_respond(service, user, created)
    assert respond.prompt.thread == [], "turn 0 has no thread"

    def attempt(text: str):
        return service.submit_attempt(
            user,
            uuid.UUID(created.id),
            uuid.UUID(respond.id),
            JourneyAttemptRequest.model_validate(
                {
                    "mutation_id": uuid.uuid4().hex,
                    "expected_revision": state.revision,
                    "input": {"mode": "text", "text": text},
                }
            ),
        )

    first = attempt("Je prend un café.")
    assert first.correction is not None
    assert first.next_turn is not None
    thread = first.next_turn.prompt.thread
    assert len(thread) == 1
    assert thread[0].learner_fr == "Je prend un café."
    assert thread[0].character_fr == first.character_reply_fr
    assert thread[0].correction is not None
    assert thread[0].correction.corrected_fr.lower().startswith("je prends")
    assert first.next_turn.prompt.character_line_fr == thread[-1].character_fr

    step = next(s for s in first.journey.steps if s.id == respond.id)
    assert [item.model_dump() for item in step.prompt.thread] == [
        item.model_dump() for item in thread
    ]
    wire = first.model_dump(mode="json")
    assert wire["next_turn"]["prompt"]["thread"][0]["correction"]["span_fr"] == "Je prend"
