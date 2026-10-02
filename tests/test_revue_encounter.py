"""WP-119 phase 1: the encounter (``app/services/revue/encounter.py``) under the fake provider.

The central acceptance test (WP-119 §1) is scripted first: on an evergreen dossier the
learner asks a question the dossier cannot answer, Romy names the gap, they phrase the
reader question together, the close files it with the learner's words, and resuming
replays the same thread. Then the guarantees around it: the Knowledge check refuses a
forced reveal, the bouclage steer at 80 %, simplify after two incomprehension turns, a
headline exercise whose distractor nothing contradicts is dropped, one active Revue per
learner per week.
"""

from __future__ import annotations

import uuid
from collections.abc import Generator

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models.npc import NPC, NPCMemory
from app.db.models.revue_session import RevueSession
from app.db.models.story import Story
from app.db.models.user import User
from app.services.revue import encounter as enc
from app.services.revue.encounter import (
    FALLBACK_LINE,
    FINAL_LINE,
    KEPT_LINE,
    SIMPLIFY_LEAD,
    STEER_LINE,
    FakeRevueProvider,
    RevueEncounter,
    RevueError,
)
from app.services.revue.evergreen import evergreens_for_week
from app.services.revue.state import ConversationState

WEEK = "2026-W40"
MARCHE = "evergreen-marche-du-dimanche"
PRICE_QUESTION = "Est-ce que les prix au marché sont plus bas qu'au supermarché ?"
REVUE_TABLES = (Story.__table__, NPC.__table__, NPCMemory.__table__, RevueSession.__table__)


@pytest.fixture(scope="module")
def revue_tables(db_engine) -> Generator[None, None, None]:
    created = [table for table in REVUE_TABLES if not inspect(db_engine).has_table(table.name)]
    for table in created:
        table.create(bind=db_engine, checkfirst=True)
    try:
        yield
    finally:
        for table in reversed(created):
            table.drop(bind=db_engine, checkfirst=True)


@pytest.fixture(autouse=True)
def evergreens_only(monkeypatch) -> None:
    """The acceptance test is on an evergreen (WP-119 §4.3: the harnesses' only content)."""

    monkeypatch.setattr(enc, "available_dossiers", evergreens_for_week)


@pytest.fixture()
def db(db_session: Session, revue_tables) -> Session:
    return db_session


def make_user(db: Session, *, level: str = "A2.1", native: str = "de", interests: str = "") -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"revue-{uuid.uuid4().hex[:10]}@example.com",
        hashed_password="x",
        cefr_estimate=level,
        native_language=native,
        interests=interests,
    )
    db.add(user)
    db.commit()
    return user


def items_of(result, kind: str) -> list:
    return [item for item in result.items if item.kind == kind]


def state_of(row: RevueSession) -> ConversationState:
    return ConversationState.from_json(row.state)


# ---------------------------------------------------------------------------
# The acceptance test (WP-119 §1, §5.4)
# ---------------------------------------------------------------------------


def test_acceptance_unexpected_question_becomes_the_reader_question(db: Session) -> None:
    user = make_user(db)
    fake = FakeRevueProvider()
    revue = RevueEncounter(db, fake)

    row = revue.start(user, WEEK, dossier_id=MARCHE)
    arrive = revue.view(row)
    assert arrive.dossier.evergreen is True
    assert arrive.beat == "arrive"
    assert [item.kind for item in arrive.thread][:2] == ["narration", "narration"]
    assert any(item.kind == "line" and item.role == "purpose" for item in arrive.thread)
    assert any(item.kind == "summary" for item in arrive.thread)

    facts = revue.turn(row, "D'accord, je t'aide.")
    assert items_of(facts, "claims"), "the facts beat puts claims on the table"

    turn = revue.turn(row, PRICE_QUESTION)
    reply = next(item for item in items_of(turn, "line") if item.role == "reply")
    uncertainty = items_of(turn, "uncertainty")
    dossier = next(d for d in evergreens_for_week(WEEK) if d.id == MARCHE)
    assert "ne le disent pas" in reply.text_fr or any(u in reply.text_fr for u in dossier.uncertainties)
    assert uncertainty and uncertainty[0].text_fr in dossier.uncertainties
    questions = state_of(row).questions
    assert questions[-1]["text"] == PRICE_QUESTION
    assert questions[-1]["answerable"] is False
    assert turn.quick_replies[0].send_fr == "On formule la question ensemble ?"

    offer = revue.make_options(row)
    assert offer.recommended == "reader_question"
    reader = next(option for option in offer.options if option.kind == "reader_question")
    assert reader.seed_fr == PRICE_QUESTION

    draft = revue.make(row, "reader_question", {"action": "propose"}).draft
    assert draft.learner_fr == PRICE_QUESTION
    assert draft.contribution, "the learner's own words are marked in Romy's proposal"
    made = revue.make(row, "reader_question", {"action": "send", "text_fr": draft.proposal_fr}).made
    assert made.kind == "reader_question"

    thread_before_close = [item.model_dump() for item in revue.view(row).thread]
    view, closing = revue.close(row)
    assert view.status == "closed"
    headline = closing.dispatch.headline_fr
    assert "prix" in headline and "supermarché" in headline
    start, end = closing.dispatch.contribution[0]
    assert "prix" in headline[start:end]
    assert closing.question_kept_fr == made.text_fr
    assert len(closing.dispatch.body_fr) == 3
    assert closing.kept.claims and closing.kept.words
    assert closing.colophon_fr == "La suite la semaine prochaine."

    memory = db.scalars(select(NPCMemory).where(NPCMemory.user_id == user.id)).all()
    assert len(memory) == 1
    assert memory[0].npc_id == "romy_tremblay"
    assert memory[0].memory_type == "interaction"
    assert memory[0].scene_id == str(row.id)
    assert "question" in memory[0].content

    # Resume replays the same thread: same ids, same order, nothing regenerated.
    calls = len(fake.calls)
    replay = revue.view(db.get(RevueSession, row.id))
    assert [item.model_dump() for item in replay.thread][: len(thread_before_close)] == thread_before_close
    assert replay.closing == closing
    assert len(fake.calls) == calls
    # A second close returns the stored one.
    _, again = revue.close(row)
    assert again == closing
    assert len(db.scalars(select(NPCMemory).where(NPCMemory.user_id == user.id)).all()) == 1


def test_resume_mid_session_replays_identically(db: Session) -> None:
    user = make_user(db)
    revue = RevueEncounter(db, FakeRevueProvider())
    row = revue.start(user, WEEK, dossier_id=MARCHE)
    revue.turn(row, "D'accord, je t'aide.")
    revue.turn(row, PRICE_QUESTION)
    first = revue.view(row).model_dump()
    db.expire_all()
    second = RevueEncounter(db, FakeRevueProvider()).view(db.get(RevueSession, row.id)).model_dump()
    assert first == second
    assert second["beat"] == "pursue"


# ---------------------------------------------------------------------------
# Romy's reply: knowledge, length, dates, citations
# ---------------------------------------------------------------------------


def _forced(text: str, **extra) -> dict:
    return {"reply_fr": text, "claims_cited": [], "uncertainty_cited": None, "proposes_question": None, "shift": None, **extra}


def test_knowledge_check_refuses_a_forced_reveal(db: Session) -> None:
    user = make_user(db)
    reveal = _forced("Le secret ? Le prix, c'est 310 000 euros.")
    fake = FakeRevueProvider(script=[reveal, reveal])
    revue = RevueEncounter(db, fake)
    row = revue.start(user, WEEK, dossier_id=MARCHE)
    result = revue.turn(row, "Tu sais combien coûte l'immeuble ?")
    line = items_of(result, "line")[0]
    assert line.role == "fallback"
    assert line.text_fr == FALLBACK_LINE
    assert "310" not in " ".join(item.model_dump_json() for item in result.items)
    assert len([call for call in fake.calls if call[0] == "reply"]) == 2, "one regeneration, then the authored line"
    romy = [e for e in state_of(row).events if e.kind == "turn_romy"][-1]
    assert "knowledge" in romy.payload["refused"]


def test_knowledge_check_accepts_the_regeneration(db: Session) -> None:
    user = make_user(db)
    fake = FakeRevueProvider(script=[_forced("C'est 310 000 euros."), _forced("Je ne sais pas, hein.")])
    revue = RevueEncounter(db, fake)
    row = revue.start(user, WEEK, dossier_id=MARCHE)
    line = items_of(revue.turn(row, "Et l'immeuble ?"), "line")[0]
    assert (line.role, line.text_fr) == ("reply", "Je ne sais pas, hein.")
    retry_context = [call for call in fake.calls if call[0] == "reply"][1][1]
    assert "knowledge" in retry_context["retry_feedback"]["problems"]


def test_reply_is_cut_to_the_word_target_and_loses_relative_dates(db: Session) -> None:
    user = make_user(db)  # A2: reading target 90 → at most 45 words
    long = " ".join(["Le marché d'Aligre ouvre tôt."] * 20)
    fake = FakeRevueProvider(script=[_forced(long), _forced(long)])
    revue = RevueEncounter(db, fake)
    row = revue.start(user, WEEK, dossier_id=MARCHE)
    line = items_of(revue.turn(row, "Il ouvre quand ?"), "line")[0]
    assert enc.word_count(line.text_fr) <= 45
    assert line.text_fr.startswith("Le marché d'Aligre ouvre tôt.")

    dated = _forced("Demain, le marché sera plein. Paris compte 91 marchés.", claims_cited=["c1", "c99"])
    fake.script = [dated, dated]
    result = revue.turn(row, "Et les autres marchés ?")
    line = items_of(result, "line")[0]
    assert "emain" not in line.text_fr
    assert line.text_fr == "Paris compte 91 marchés."
    romy = [e for e in state_of(row).events if e.kind == "turn_romy"][-1]
    assert romy.payload["claims_cited"] == ["c1"], "an unknown claim id is dropped"


def test_evidence_is_unscored_and_never_mastery(db: Session) -> None:
    user = make_user(db)
    revue = RevueEncounter(db, FakeRevueProvider())
    row = revue.start(user, WEEK, dossier_id=MARCHE)
    result = revue.turn(row, "Le marché est ouvert le matin ?")
    assert result.evidence.outcome == "unscored"
    assert result.evidence.capability_known is False
    evidence = [e for e in state_of(row).events if e.kind == "evidence"][-1].payload
    assert evidence["rubric_version"] == enc.GRADER_ID
    assert evidence["correct"] is None
    assert state_of(row).words_used_correctly == set()


def test_a_retried_turn_is_not_played_twice(db: Session) -> None:
    user = make_user(db)
    fake = FakeRevueProvider()
    revue = RevueEncounter(db, fake)
    row = revue.start(user, WEEK, dossier_id=MARCHE)
    first = revue.turn(row, "D'accord, je t'aide.", client_turn_id="t-1")
    calls = len(fake.calls)
    again = revue.turn(row, "D'accord, je t'aide.", client_turn_id="t-1")
    assert again == first
    assert len(fake.calls) == calls
    assert state_of(row).turns_used == 1


def test_angle_shift_is_recorded_and_shown(db: Session) -> None:
    user = make_user(db)
    fake = FakeRevueProvider(script=[_forced("Bonne idée, on compare avec le supermarché.", shift="angle")])
    revue = RevueEncounter(db, fake)
    row = revue.start(user, WEEK, dossier_id=MARCHE)
    result = revue.turn(row, "Moi, je veux comparer avec le supermarché.")
    shift = items_of(result, "shift")
    assert shift and shift[0].reason == "angle" and shift[0].angle.id == "a2"
    assert revue.view(row).plan.angle.id == "a2"


# ---------------------------------------------------------------------------
# Budget, simplify
# ---------------------------------------------------------------------------


def test_bouclage_steer_at_eighty_percent_then_the_column_closes(db: Session) -> None:
    user = make_user(db)
    fake = FakeRevueProvider()
    revue = RevueEncounter(db, fake)
    row = revue.start(user, WEEK, dossier_id=MARCHE)
    budget = revue.view(row).plan.budget.turns
    threshold = -(-budget * 8 // 10)  # the first turn at ≥ 80 %
    result = None
    for index in range(threshold):
        result = revue.turn(row, f"Le marché ouvre le matin, numéro {index} ?")
        if index < threshold - 1:
            assert result.room.phase == "open"
            assert not any(item.kind == "line" and item.role == "steer" for item in result.items)
    assert result.room.phase == "bouclage"
    assert result.steer_to_make is True
    assert result.items[-1].kind == "line" and result.items[-1].role == "steer"
    assert result.items[-1].text_fr == STEER_LINE
    assert any(item.kind == "shift" and item.reason == "bouclage" for item in result.items)

    for index in range(threshold, budget):
        result = revue.turn(row, f"Encore une chose, numéro {index} ?")
    assert result.room.phase == "boucle"
    assert result.room.used == 7
    assert result.items[-1].text_fr == FINAL_LINE

    calls = len([c for c in fake.calls if c[0] == "reply"])
    after = revue.turn(row, "Et les horaires pendant les fêtes ?")
    assert items_of(after, "line")[0].text_fr == KEPT_LINE
    assert len([c for c in fake.calls if c[0] == "reply"]) == calls, "no model call once the column is full"
    assert state_of(row).questions[-1]["kept"] is True


def test_simplify_after_two_incomprehension_turns(db: Session) -> None:
    user = make_user(db)
    revue = RevueEncounter(db, FakeRevueProvider())
    row = revue.start(user, WEEK, dossier_id=MARCHE)
    before = revue.view(row).plan.support
    revue.turn(row, "D'accord, je t'aide.")
    first = revue.turn(row, "Je ne comprends pas.")
    assert not items_of(first, "shift")
    assert first.support.level == 0
    second = revue.turn(row, "Je ne comprends pas...")
    shift = items_of(second, "shift")
    assert shift and shift[0].reason == "simplify"
    assert second.support.level == 1
    assert second.support.glosses == "shown" and before.glosses == "tap"
    assert second.support.reading_target_words < before.reading_target_words
    line = items_of(second, "line")[0]
    assert line.text_fr.startswith(SIMPLIFY_LEAD)
    assert [reply.label for reply in second.quick_replies] == ["Ah, d'accord", "Encore plus simple"]
    # A third breakdown does not simplify again at once: two in a row are needed.
    third = revue.turn(row, "Je ne comprends pas.")
    assert third.support.level == 1


# ---------------------------------------------------------------------------
# Make
# ---------------------------------------------------------------------------


def test_headline_choice_picks_and_files(db: Session) -> None:
    user = make_user(db)
    revue = RevueEncounter(db, FakeRevueProvider())
    row = revue.start(user, WEEK, dossier_id=MARCHE)
    revue.turn(row, "D'accord, je t'aide.")
    offer = revue.make_options(row)
    headline = next(option for option in offer.options if option.kind == "headline_choice")
    assert len(headline.options) == 3
    assert "answer" not in headline.model_dump_json() and "contradicted_by" not in headline.model_dump_json()
    exercise = [e for e in state_of(row).events if e.payload.get("kind") == "headline_exercise"][-1].payload["exercise"]
    wrong = next(o["id"] for o in exercise["options"] if o["id"] != exercise["answer"])
    result = revue.make(row, "headline_choice", {"action": "pick", "option_id": wrong})
    assert result.correct is False
    assert result.answer_id == exercise["answer"]
    assert result.evidence.quote
    assert result.made.contribution == []
    # The exercise is built once: a second GET reuses it.
    assert revue.make_options(row).options[0] == headline


def test_headline_choice_dropped_when_a_distractor_is_not_contradicted(db: Session) -> None:
    user = make_user(db)
    uncontradicted = {
        "answer": {"text_fr": "Le marché d'Aligre ouvre six matins sur sept", "supported_by": "c2"},
        "distractors": [
            {"text_fr": "Paris compte 183 marchés", "contradicted_by": "c1"},
            {"text_fr": "Le marché d'Aligre est le plus cher de Paris"},
        ],
    }
    fake = FakeRevueProvider(headline_script=[uncontradicted, uncontradicted])
    revue = RevueEncounter(db, fake)
    row = revue.start(user, WEEK, dossier_id=MARCHE)
    revue.turn(row, "D'accord, je t'aide.")
    offer = revue.make_options(row)
    assert [option.kind for option in offer.options] == ["reader_question"]
    assert offer.recommended == "reader_question"
    assert len([c for c in fake.calls if c[0] == "headline"]) == 2, "regenerated once, then dropped"
    with pytest.raises(RevueError) as raised:
        revue.make(row, "headline_choice", {"action": "pick", "option_id": "h1"})
    assert (raised.value.status, raised.value.code) == (409, "revue_make_unavailable")


def test_closed_session_is_read_only(db: Session) -> None:
    user = make_user(db)
    revue = RevueEncounter(db, FakeRevueProvider())
    row = revue.start(user, WEEK, dossier_id=MARCHE)
    _, closing = revue.close(row)
    assert closing.question_kept_fr is None
    assert closing.dispatch.headline_fr  # an authored close with whatever exists
    for call in (lambda: revue.turn(row, "Encore ?"), lambda: revue.make_options(row)):
        with pytest.raises(RevueError) as raised:
            call()
        assert raised.value.code == "revue_session_closed"


# ---------------------------------------------------------------------------
# Entry: one active per week, the offer, a free request
# ---------------------------------------------------------------------------


def test_one_active_session_per_user_per_week(db: Session) -> None:
    user = make_user(db)
    revue = RevueEncounter(db, FakeRevueProvider())
    row = revue.start(user, WEEK, dossier_id=MARCHE)
    with pytest.raises(RevueError) as raised:
        revue.start(user, WEEK)
    assert (raised.value.code, raised.value.extra["session_id"]) == ("revue_session_active", str(row.id))

    # The partial unique index holds even past the service check.
    db.add(RevueSession(user_id=user.id, week=WEEK, dossier_id=MARCHE, plan={}, state={}, status="active"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    revue.close(db.get(RevueSession, row.id))
    with pytest.raises(RevueError) as raised:
        revue.start(user, WEEK)
    assert raised.value.code == "revue_week_filed"
    # Another week is free.
    assert revue.start(user, "2026-W41").week == "2026-W41"


def test_week_offer_recommends_the_least_recent_topic_then_interests(db: Session) -> None:
    user = make_user(db, interests="cuisine, voyage")
    revue = RevueEncounter(db, FakeRevueProvider())
    offer = revue.week_offer(user, WEEK)
    assert offer.recommended.dossier_id == MARCHE
    assert offer.recommended_reason == "interests"
    assert offer.evergreen_only is True and offer.recommended.evergreen is True
    assert [card.dossier_id for card in offer.alternatives] == ["evergreen-greve-transports"]
    assert offer.week.label == "Semaine 40" and offer.week.range == "du 28 sept. au 4 oct."
    assert offer.recommended.stage.plate_url and offer.recommended.stage.place_is_real is False

    previous = revue.start(user, "2026-W39", dossier_id=MARCHE)
    revue.close(previous)
    offer = revue.week_offer(user, WEEK)
    assert offer.recommended.dossier_id == "evergreen-greve-transports"
    assert offer.recommended_reason == "topic_least_recent"

    row = revue.start(user, WEEK)
    offer = revue.week_offer(user, WEEK)
    assert offer.resume is not None and offer.resume.session_id == str(row.id)
    revue.close(row)
    offer = revue.week_offer(user, WEEK)
    assert offer.resume is None and offer.filed is not None and offer.filed.dispatch is not None


def test_free_request_match_and_miss(db: Session) -> None:
    user = make_user(db)
    revue = RevueEncounter(db, FakeRevueProvider())
    assert revue.match(user, "la grève des trains", WEEK).match == "evergreen-greve-transports"
    miss = revue.match(user, "le football féminin", WEEK)
    assert miss.match is None and miss.romy_line_fr.startswith("Je n'ai que ça cette semaine")

    row = revue.start(user, WEEK, free_request="le football féminin")
    view = revue.view(row)
    assert view.plan.chosen_by == "recommended"
    assert any(item.kind == "line" and item.role == "fallback" and "Je n'ai que ça" in item.text_fr for item in view.thread)
    revue.close(row)

    other = make_user(db)
    row = revue.start(other, WEEK, free_request="Parle-moi de la grève des transports")
    assert row.dossier_id == "evergreen-greve-transports"
    assert revue.view(row).plan.chosen_by == "learner"


def test_plan_vocabulary_and_stage(db: Session) -> None:
    a2 = make_user(db, level="A2.1", native="de")
    b1 = make_user(db, level="B1.2", native="en")
    revue = RevueEncounter(db, FakeRevueProvider())
    view_a2 = revue.view(revue.start(a2, WEEK, dossier_id=MARCHE))
    view_b1 = revue.view(revue.start(b1, WEEK, dossier_id=MARCHE))
    assert len(view_a2.plan.vocabulary) == 5 and len(view_b1.plan.vocabulary) == 7
    assert view_a2.plan.gloss_language == "de" and view_b1.plan.gloss_language == "en"
    assert all(word.gloss for word in view_a2.plan.vocabulary)
    assert view_a2.plan.make_options == ["headline_choice", "reader_question"]
    assert view_b1.plan.make_options == ["headline_choice", "reader_question"]
    assert view_a2.stage.dress == "coat"  # §12.5: a market visit alone does not dress Toi
    assert view_a2.stage.cast[0].id == "romy_tremblay" and view_a2.stage.cast[0].hold == "notebook"
    assert any(item.kind == "line" and item.role == "place_note" for item in view_a2.thread)


def test_season_position_without_a_thread_uses_the_season_global_list(db: Session) -> None:
    user = make_user(db)
    position = enc.season_position(db, user)
    assert position is not None
    assert position.gap_id == ""
    assert enc.knowledge_hits(["C'est 310 000 euros."], position)
    assert not enc.knowledge_hits(["Paris compte 91 marchés."], position)


# ---------------------------------------------------------------------------
# The real provider's plumbing (no network: a stub LLM service)
# ---------------------------------------------------------------------------


class _StubLLM:
    def __init__(self, content: str | None = None, error: Exception | None = None) -> None:
        self.content, self.error, self.calls = content, error, []

    def generate_chat_completion(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        if self.error is not None:
            raise self.error
        from types import SimpleNamespace

        return SimpleNamespace(content=self.content, cost=0.002)


def test_openai_provider_asks_for_json_and_parses_it() -> None:
    stub = _StubLLM('{"reply_fr": "Bonjour.", "claims_cited": ["c1"], "uncertainty_cited": null, '
                    '"proposes_question": null, "shift": null, "translation": null}')
    provider = enc.OpenAIRevueProvider(_service=stub)
    for task, call in (
        ("reply", lambda: provider.reply({"max_words": 30, "band": "A2", "translation_language": "de"})),
        ("headline", lambda: provider.headline({"claims_shown": []})),
        ("question", lambda: provider.question({"band": "A2", "language": "de"})),
        ("close", lambda: provider.close({})),
        ("vocabulary", lambda: provider.vocabulary(claims=[], count=5, language="de")),
    ):
        call()
        messages, kwargs = stub.calls[-1]
        assert kwargs["response_format"] == {"type": "json_object"}, task
        assert kwargs["reasoning_effort"] == "low"
        assert "JSON" in messages[0]["content"]
    assert provider.reply({"max_words": 30, "band": "A2", "translation_language": None})["reply_fr"] == "Bonjour."
    assert provider.spent_usd > 0
    with pytest.raises(enc.RevueProviderError):
        enc.OpenAIRevueProvider(_service=_StubLLM("not json")).reply({})


def test_model_down_gives_the_authored_line(db: Session) -> None:
    user = make_user(db)
    down = enc.OpenAIRevueProvider(_service=_StubLLM(error=RuntimeError("provider down")))
    revue = RevueEncounter(db, down)
    row = revue.start(user, WEEK, dossier_id=MARCHE)  # vocabulary falls back to the authored extraction
    assert len(revue.view(row).plan.vocabulary) == 5
    result = revue.turn(row, "D'accord, je t'aide.")
    line = items_of(result, "line")[0]
    assert (line.role, line.text_fr) == ("fallback", FALLBACK_LINE)
    offer = revue.make_options(row)  # the authored headline when the model is down
    assert items_of(result, "claims"), "the facts need no generation"
    assert [option.kind for option in offer.options] == ["headline_choice", "reader_question"]
    _, closing = revue.close(row)
    assert closing.romy_line_fr and len(closing.dispatch.body_fr) >= 1
