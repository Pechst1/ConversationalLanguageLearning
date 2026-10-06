"""WP-30 — «Le journal de bord», one test per claim the package makes.

In the order the package promises them:

1. the offer schedule is +1 day and the follow-up +7, and neither is a guess;
2. the scene text is not readable while the learner writes it from memory;
3. the correction is the Séance's, one relevant error in the foreground and the
   rest behind it, and every grammar error becomes a WP-24 erratum;
4. vocabulary the recap used from the due set earns ordinary SRS credit, and a
   word the correction flagged does not;
5. content recall is scored against the scene's stored facts, separately from
   grammar, and a scene with no facts scores ``None`` rather than zero;
6. the character's line is about the content and never praises an empty recap;
7. the +7 follow-up produces the ``used_again_later`` signal;
8. one priced pilot row per real correction call, and a replay buys nothing;
9. a provider that does not answer yields an honest state, keeps the writing,
   and moves no schedule.
"""
from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.db.models.daily_journey import DailyJourney, DailyJourneyStep
from app.db.models.error import UserError
from app.db.models.grammar import GrammarConcept
from app.db.models.journal import JournalEntry
from app.db.models.pilot_event import PilotEvent
from app.db.models.progress import UserVocabularyProgress
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services.journal import (
    FOLLOWUP_OFFSET_DAYS,
    JOURNAL_EVENT_TYPE,
    JOURNAL_FOLLOWUP_EVENT_TYPE,
    RECALL_OFFSET_DAYS,
    RECALL_WINDOW_DAYS,
    JournalService,
    character_reaction,
    content_cues,
    followup_prompt,
    scene_cue,
    scene_facts_for,
    scene_reveal,
    score_content_recall,
)

TODAY = date(2026, 9, 10)
NOW = datetime(2026, 9, 10, 9, 0, tzinfo=UTC)


#: Words this module puts in the *global* vocabulary table, so it can take them
#: out again. The engine is session-scoped and `vocabulary_words` is shared, so
#: a French word left behind here becomes a planner candidate for every learner
#: in every later module — which is exactly how the living-story day drivers
#: started failing on a recall step they had nothing to do with.
_PLANTED_WORD_IDS: list[int] = []


@pytest.fixture(autouse=True)
def journal_table(db_engine, db_session):
    """Create ``journal_entries``, and leave the shared tables as they were.

    The table is declared here rather than in the shared ``conftest`` list:
    several innovation packages are adding tables against the same checkout this
    week, and a package that owns its own DDL in its own test module cannot
    collide with any of them. ``checkfirst`` makes it idempotent across modules.
    """
    JournalEntry.__table__.create(bind=db_engine, checkfirst=True)
    _PLANTED_WORD_IDS.clear()
    try:
        yield
    finally:
        if _PLANTED_WORD_IDS:
            db_session.query(UserVocabularyProgress).filter(
                UserVocabularyProgress.word_id.in_(_PLANTED_WORD_IDS)
            ).delete(synchronize_session=False)
            db_session.query(VocabularyWord).filter(
                VocabularyWord.id.in_(_PLANTED_WORD_IDS)
            ).delete(synchronize_session=False)
            db_session.commit()
            _PLANTED_WORD_IDS.clear()


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


class _FakeCorrector:
    """A checker that answers with whatever the test told it to answer.

    ``fail`` makes the call raise the way a real provider fails, which is the
    only honest way to test the ``unavailable`` state: the correction service's
    own fallback rule is what has to fire, not a flag the test set by hand.
    """

    def __init__(self, content: dict | None = None, *, fail: bool = False) -> None:
        self.content = content or {}
        self.fail = fail
        self.calls = 0

    def generate_error_detection(self, messages, **kwargs):
        self.calls += 1
        if self.fail:
            from app.services.llm_service import LLMProviderError

            raise LLMProviderError("journal checker unavailable")
        payload = json.loads(messages[0]["content"])
        content = dict(self.content)
        content.setdefault("verdict", "accepted")
        content.setdefault("score_0_4", 4)
        content.setdefault("errata", [])
        content.setdefault("corrected_answer", (payload.get("answer") or {}).get("text", ""))
        content.setdefault("concept_hits", [])
        content.setdefault("missing_targets", [])
        return SimpleNamespace(
            provider="openai",
            model="test-model",
            content=json.dumps(content, ensure_ascii=False),
            prompt_tokens=120,
            completion_tokens=60,
            total_tokens=180,
            cost=0.0004,
            raw_response={},
        )


def _user(db_session) -> User:
    user = User(
        id=uuid4(),
        email=f"journal-{uuid4().hex[:8]}@example.com",
        hashed_password="x",
        native_language="en",
        target_language="fr",
        proficiency_level="A1",
        cefr_estimate="A1.2",
        daily_goal_minutes=20,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _concept(db_session) -> GrammarConcept:
    concept = GrammarConcept(
        language="fr",
        level="A1",
        name="Articles définis",
        external_id=f"FR_A1_ART_{uuid4().hex[:6]}",
        category="Nomen",
        description="le / la / les",
        difficulty_order=10,
        active=True,
    )
    db_session.add(concept)
    db_session.commit()
    db_session.refresh(concept)
    return concept


def _journey(
    db_session,
    user: User,
    *,
    local_date: date,
    callback: str | None = "Vous avez promis de rapporter le livre mardi.",
    concept: GrammarConcept | None = None,
    status: str = "completed",
) -> DailyJourney:
    journey = DailyJourney(
        user_id=user.id,
        local_date=local_date,
        timezone="UTC",
        content_version="journey-content-v1",
        level_band="A1",
        status=status,
        serial_episode_id="ep-7",
        scenario_snapshot={
            "scenario_key": "order_at_cafe",
            "title_fr": "Un café au Mistral",
            "character_name": "Romy",
            "location_name": "Le Mistral",
            "objective_native": "Order one coffee and ask the price.",
        },
        recap_snapshot=(
            {"story_outcome": {"outcome_key": "met", "callback_fr": callback}}
            if callback
            else {}
        ),
    )
    db_session.add(journey)
    db_session.flush()
    db_session.add(
        DailyJourneyStep(
            journey_id=journey.id,
            ordinal=0,
            kind="scene",
            status="completed",
            public_prompt={
                "setup_fr": "Romy vous attend au Mistral avec un livre sous le bras.",
                "setup_native": "Romy is waiting for you.",
                "objective_native": "Order one coffee.",
                "character_line_fr": "Vous me le rapportez mardi ?",
            },
            private_task={"rubric": "NEVER PUBLIC", "accepted": ["oui"]},
        )
    )
    db_session.add(
        DailyJourneyStep(
            journey_id=journey.id,
            ordinal=1,
            kind="respond",
            status="completed",
            target_kind="grammar" if concept else None,
            target_id=str(concept.id) if concept else None,
            public_prompt={},
            private_task={},
        )
    )
    db_session.commit()
    db_session.refresh(journey)
    return journey


def _due_word(db_session, user: User, *, word: str = "livre") -> VocabularyWord:
    row = VocabularyWord(
        language="fr",
        word=word,
        normalized_word=word,
        frequency_rank=300,
        english_translation="book",
        german_translation="Buch",
        direction="fr_to_de",
    )
    db_session.add(row)
    db_session.flush()
    db_session.add(
        UserVocabularyProgress(
            user_id=user.id,
            word_id=row.id,
            due_at=datetime(2026, 9, 1, tzinfo=UTC),
            stability=1.0,
            difficulty=5.0,
        )
    )
    db_session.commit()
    db_session.refresh(row)
    _PLANTED_WORD_IDS.append(row.id)
    return row


def _service(db_session, corrector: _FakeCorrector | None = None) -> JournalService:
    return JournalService(db_session, llm_service=corrector)


# ---------------------------------------------------------------------------
# 1. the offer schedule
# ---------------------------------------------------------------------------


def test_yesterdays_scene_is_offered_and_todays_is_not(db_session):
    user = _user(db_session)
    _journey(db_session, user, local_date=TODAY)
    assert _service(db_session).offer(user, now=NOW) is None

    _journey(db_session, user, local_date=TODAY - timedelta(days=RECALL_OFFSET_DAYS))
    entry = _service(db_session).offer(user, now=NOW)
    assert entry is not None
    assert entry.scene_date == TODAY - timedelta(days=1)
    assert entry.offered_on == TODAY
    assert entry.followup_due_on == entry.scene_date + timedelta(days=FOLLOWUP_OFFSET_DAYS)


def test_a_scene_older_than_the_window_is_never_offered(db_session):
    user = _user(db_session)
    _journey(db_session, user, local_date=TODAY - timedelta(days=RECALL_WINDOW_DAYS + 1))
    assert _service(db_session).offer(user, now=NOW) is None


def test_an_unfinished_journey_is_not_recallable(db_session):
    user = _user(db_session)
    _journey(db_session, user, local_date=TODAY - timedelta(days=1), status="active")
    assert _service(db_session).offer(user, now=NOW) is None


def test_the_offer_is_idempotent_and_never_forks_one_evening_into_two_rows(db_session):
    user = _user(db_session)
    _journey(db_session, user, local_date=TODAY - timedelta(days=1))
    first = _service(db_session).offer(user, now=NOW)
    second = _service(db_session).offer(user, now=NOW)
    assert first.id == second.id
    assert db_session.query(JournalEntry).filter(JournalEntry.user_id == user.id).count() == 1


def test_a_declined_scene_is_not_offered_again(db_session):
    user = _user(db_session)
    _journey(db_session, user, local_date=TODAY - timedelta(days=1))
    service = _service(db_session)
    entry = service.offer(user, now=NOW)
    service.skip(entry)
    assert service.offer(user, now=NOW) is None


# ---------------------------------------------------------------------------
# 2. the scene is not on screen while they write
# ---------------------------------------------------------------------------


def test_the_cue_carries_who_and_where_and_no_authored_scene_text(db_session):
    user = _user(db_session)
    journey = _journey(db_session, user, local_date=TODAY - timedelta(days=1))
    cue = scene_cue(journey, today=TODAY)
    assert cue["character_name"] == "Romy"
    assert cue["location_name"] == "Le Mistral"
    assert cue["days_ago"] == 1
    rendered = json.dumps(cue, ensure_ascii=False)
    assert "Romy vous attend" not in rendered
    assert "rapportez" not in rendered
    assert "Un café au Mistral" not in rendered


def test_the_offered_row_holds_no_scene_text_outside_the_sealed_reveal(db_session):
    user = _user(db_session)
    _journey(db_session, user, local_date=TODAY - timedelta(days=1))
    entry = _service(db_session).offer(user, now=NOW)
    visible = json.dumps(
        {"cue": entry.cue, "facts": entry.scene_facts, "text": entry.entry_text},
        ensure_ascii=False,
    )
    assert "Romy vous attend au Mistral" not in visible
    assert "Vous me le rapportez mardi" not in visible
    # And the reveal itself does hold it, so the "after" half of the flow works.
    assert "Romy vous attend au Mistral" in json.dumps(entry.scene_reveal, ensure_ascii=False)


def test_the_journal_never_reads_the_private_task(db_session):
    """Source scan: evaluator material is not what a recap is scored against."""
    from pathlib import Path

    source = Path("app/services/journal.py").read_text(encoding="utf-8")
    assert "private_task" in source, "the rule is stated in the module docstring"
    assert "step.private_task" not in source
    assert ".private_task" not in source.replace("``private_task``", "")

    journey_source = Path("app/api/v1/endpoints/journal.py").read_text(encoding="utf-8")
    assert "private_task" not in journey_source


def test_the_reveal_is_the_scene_and_the_facts_are_its_commitments(db_session):
    user = _user(db_session)
    journey = _journey(db_session, user, local_date=TODAY - timedelta(days=1))
    reveal = scene_reveal(journey)
    assert reveal["setup_fr"].startswith("Romy vous attend")
    assert reveal["character_line_fr"] == "Vous me le rapportez mardi ?"

    facts = scene_facts_for(journey, story_context={})
    assert [fact.kind for fact in facts] == ["outcome"]
    assert "livre" in facts[0].cues
    # "Romy" was on the prompt, so writing it back proves nothing.
    assert "romy" not in facts[0].cues


def test_a_commitment_from_another_episode_is_not_this_scenes_fact(db_session):
    user = _user(db_session)
    journey = _journey(db_session, user, local_date=TODAY - timedelta(days=1), callback=None)
    facts = scene_facts_for(
        journey,
        story_context={
            "commitments": [
                {"id": "c1", "episode_id": "ep-7", "summary_fr": "Rapporter le parapluie jeudi."},
                {"id": "c2", "episode_id": "ep-2", "summary_fr": "Payer la note du dimanche."},
            ]
        },
    )
    assert [fact.key for fact in facts] == ["commitment:c1"]


# ---------------------------------------------------------------------------
# 3. correction and errata
# ---------------------------------------------------------------------------


def _write(db_session, user, corrector, text: str) -> JournalEntry:
    service = _service(db_session, corrector)
    entry = service.offer(user, now=NOW)
    return service.write(user, entry, text=text)


def test_one_correction_is_foregrounded_and_the_rest_stay_available(db_session):
    user = _user(db_session)
    concept = _concept(db_session)
    _journey(db_session, user, local_date=TODAY - timedelta(days=1), concept=concept)
    corrector = _FakeCorrector(
        {
            "verdict": "partial",
            "score_0_4": 2,
            "corrected_answer": "J’ai vu le livre au Mistral et j’ai promis de le rapporter mardi.",
            "errata": [
                {
                    "item_id": "a",
                    "display_label": "Article",
                    "learner_text": "la livre",
                    "corrected_target": "le livre",
                    "why_wrong": "«livre» is masculine here.",
                    "repair_hint": "Say le livre.",
                    "severity": 2,
                    "recurring": True,
                    "task_error_type": "gender_agreement",
                },
                {
                    "item_id": "b",
                    "display_label": "Verbe",
                    "learner_text": "j’ai promet",
                    "corrected_target": "j’ai promis",
                    "why_wrong": "Past participle of promettre.",
                    "repair_hint": "promis",
                    "severity": 2,
                    "recurring": True,
                    "task_error_type": "verb_form",
                },
            ],
        }
    )
    entry = _write(
        db_session,
        user,
        corrector,
        "J’ai vu la livre au Mistral et j’ai promet de le rapporter mardi.",
    )
    assert entry.assessment_status == "checked"
    assert entry.correction["foreground"] is not None
    assert len(entry.correction["errata"]) == 2
    # The foreground is one of the two, and the full list still holds both.
    spans = {item["span_fr"] for item in entry.correction["errata"]}
    assert entry.correction["foreground"]["span_fr"] in spans


def test_every_grammar_error_becomes_a_wp24_erratum(db_session):
    user = _user(db_session)
    concept = _concept(db_session)
    _journey(db_session, user, local_date=TODAY - timedelta(days=1), concept=concept)
    corrector = _FakeCorrector(
        {
            "verdict": "partial",
            "score_0_4": 2,
            "corrected_answer": "J’ai vu le livre.",
            "errata": [
                {
                    "item_id": "a",
                    "display_label": "Article",
                    "learner_text": "la livre",
                    "corrected_target": "le livre",
                    "why_wrong": "masculine",
                    "repair_hint": "le livre",
                    "severity": 2,
                    "recurring": True,
                    "task_error_type": "gender_agreement",
                }
            ],
        }
    )
    entry = _write(db_session, user, corrector, "J’ai vu la livre.")
    assert len(entry.errata_ids) == 1
    stored = db_session.query(UserError).filter(UserError.user_id == user.id).all()
    assert len(stored) == 1
    assert stored[0].original_text == "la livre"
    assert stored[0].correction == "le livre"


def test_task_compliance_notes_are_not_mistakes(db_session):
    user = _user(db_session)
    concept = _concept(db_session)
    _journey(db_session, user, local_date=TODAY - timedelta(days=1), concept=concept)
    corrector = _FakeCorrector(
        {
            "verdict": "accepted",
            "score_0_4": 4,
            "corrected_answer": "J’ai vu le livre.",
            "errata": [
                {
                    "item_id": "a",
                    "display_label": "Missing writing target",
                    "learner_text": "J’ai vu le livre.",
                    "corrected_target": "le passé composé",
                    "why_wrong": "target used once",
                    "severity": 1,
                    "recurring": False,
                    "task_error_type": "task_compliance",
                }
            ],
        }
    )
    entry = _write(db_session, user, corrector, "J’ai vu le livre.")
    assert entry.correction["errata"] == []
    assert entry.errata_ids == []


# ---------------------------------------------------------------------------
# 4. vocabulary credit
# ---------------------------------------------------------------------------


def test_a_due_word_used_in_the_recap_earns_credit(db_session):
    user = _user(db_session)
    concept = _concept(db_session)
    _journey(db_session, user, local_date=TODAY - timedelta(days=1), concept=concept)
    word = _due_word(db_session, user, word="livre")
    before = (
        db_session.query(UserVocabularyProgress)
        .filter(UserVocabularyProgress.user_id == user.id, UserVocabularyProgress.word_id == word.id)
        .one()
    )
    before_due = before.due_at

    corrector = _FakeCorrector({"verdict": "accepted", "score_0_4": 4, "errata": []})
    entry = _write(db_session, user, corrector, "J’ai rapporté le livre à Romy au Mistral.")

    assert entry.vocabulary_credit["status"] == "applied"
    assert "livre" in entry.vocabulary_credit["credited"]
    db_session.refresh(before)
    assert before.due_at != before_due


def test_a_word_the_correction_flagged_is_not_credited(db_session):
    user = _user(db_session)
    concept = _concept(db_session)
    _journey(db_session, user, local_date=TODAY - timedelta(days=1), concept=concept)
    _due_word(db_session, user, word="livre")
    corrector = _FakeCorrector(
        {
            "verdict": "partial",
            "score_0_4": 2,
            "corrected_answer": "J’ai rapporté le livre.",
            "errata": [
                {
                    "item_id": "a",
                    "display_label": "Article",
                    "learner_text": "la livre",
                    "corrected_target": "le livre",
                    "why_wrong": "masculine",
                    "severity": 2,
                    "recurring": True,
                    "task_error_type": "gender_agreement",
                }
            ],
        }
    )
    entry = _write(db_session, user, corrector, "J’ai rapporté la livre à Romy.")
    assert entry.vocabulary_credit["credited"] == []
    assert "livre" in entry.vocabulary_credit["skipped_flagged"]


# ---------------------------------------------------------------------------
# 5. content recall, separate from grammar
# ---------------------------------------------------------------------------


def test_content_recall_is_scored_against_the_stored_facts(db_session):
    facts = [
        {"key": "outcome", "kind": "outcome", "text_fr": "rapporter le livre mardi",
         "cues": ["rapporter", "livre", "mardi"]},
        {"key": "c1", "kind": "commitment", "text_fr": "payer la note",
         "cues": ["payer", "note"]},
    ]
    recall = score_content_recall("J’ai promis de rapporter le livre mardi.", facts)
    assert recall["status"] == "scored"
    assert recall["score"] == 0.5
    assert [item["key"] for item in recall["matched"]] == ["outcome"]
    assert [item["key"] for item in recall["missed"]] == ["c1"]


def test_a_single_common_word_does_not_prove_a_wide_fact(db_session):
    facts = [
        {"key": "outcome", "kind": "outcome", "text_fr": "rapporter le livre mardi",
         "cues": ["rapporter", "livre", "mardi"]}
    ]
    assert score_content_recall("J’ai vu un livre.", facts)["score"] == 0.0
    assert score_content_recall("J’ai rapporté le livre.", facts)["score"] == 1.0


def test_a_scene_with_no_stored_facts_scores_none_and_never_zero(db_session):
    recall = score_content_recall("J’ai parlé avec Romy.", [])
    assert recall["status"] == "no_facts"
    assert recall["score"] is None


def test_recall_folds_accents_and_ios_smart_quotes(db_session):
    facts = [{"key": "c1", "kind": "commitment", "text_fr": "j’ai réglé la note",
              "cues": ["regle", "note"]}]
    assert score_content_recall("J’ai reglé la note.", facts)["score"] == 1.0


def test_grammar_and_content_are_two_columns_not_one_score(db_session):
    """Flawless French about the wrong evening is not a recalled evening."""
    user = _user(db_session)
    concept = _concept(db_session)
    _journey(db_session, user, local_date=TODAY - timedelta(days=1), concept=concept)
    corrector = _FakeCorrector({"verdict": "accepted", "score_0_4": 4, "errata": []})
    entry = _write(db_session, user, corrector, "Il faisait beau et je suis rentré tôt.")
    assert entry.correction["verdict"] == "accepted"
    assert entry.content_recall["score"] == 0.0
    assert entry.recall_score == 0.0


# ---------------------------------------------------------------------------
# 6. the character's line
# ---------------------------------------------------------------------------


def test_the_character_names_the_commitment_the_learner_remembered():
    recall = {
        "status": "scored",
        "matched": [{"kind": "commitment", "text_fr": "rapporter le livre mardi"}],
        "missed": [],
    }
    line = character_reaction(character_name="Romy", recall=recall)
    assert line.startswith("Romy")
    assert "rapporter le livre mardi" in line
    assert line.count("»") == 1


def test_the_character_says_what_is_missing_rather_than_praising_nothing():
    recall = {
        "status": "scored",
        "matched": [],
        "missed": [{"kind": "outcome", "text_fr": "rapporter le livre mardi"}],
    }
    line = character_reaction(character_name="Romy", recall=recall)
    assert "manque" in line


def test_the_character_stays_silent_when_there_is_nothing_honest_to_say():
    assert character_reaction(character_name="Romy", recall={"status": "no_facts"}) is None
    assert character_reaction(character_name=None, recall={"status": "scored", "matched": []}) is None


def test_the_followup_line_is_one_question_naming_the_character():
    assert followup_prompt("Romy") == "Et la semaine dernière, avec Romy ?"
    assert followup_prompt(None).endswith("?")


# ---------------------------------------------------------------------------
# 7. the +7-day follow-up and its signal
# ---------------------------------------------------------------------------


def _written_entry(db_session, user, concept) -> JournalEntry:
    corrector = _FakeCorrector({"verdict": "accepted", "score_0_4": 4, "errata": []})
    return _write(db_session, user, corrector, "J’ai rapporté le livre à Romy mardi.")


def test_the_followup_is_due_at_seven_days_and_not_at_six(db_session):
    user = _user(db_session)
    concept = _concept(db_session)
    _journey(db_session, user, local_date=TODAY - timedelta(days=1), concept=concept)
    entry = _written_entry(db_session, user, concept)

    six = datetime.combine(entry.scene_date + timedelta(days=6), datetime.min.time(), tzinfo=UTC)
    seven = datetime.combine(entry.scene_date + timedelta(days=7), datetime.min.time(), tzinfo=UTC)
    service = _service(db_session)
    assert service.followup_due(user, now=six) is None
    assert service.followup_due(user, now=seven).id == entry.id


def test_answering_the_followup_produces_the_used_again_later_signal(db_session):
    user = _user(db_session)
    concept = _concept(db_session)
    _journey(db_session, user, local_date=TODAY - timedelta(days=1), concept=concept)
    entry = _written_entry(db_session, user, concept)

    service = _service(db_session)
    service.answer_followup(user, entry, text="J’ai rapporté le livre, comme promis.")
    db_session.refresh(entry)
    assert entry.followup_signal == "used_again_later"
    assert entry.followup_answered_at is not None

    event = (
        db_session.query(PilotEvent)
        .filter(
            PilotEvent.event_type == JOURNAL_FOLLOWUP_EVENT_TYPE,
            PilotEvent.user_id == user.id,
        )
        .one()
    )
    assert event.payload["signal"] == "used_again_later"
    assert event.payload["days_later"] == FOLLOWUP_OFFSET_DAYS


def test_a_followup_that_recalls_nothing_says_so_rather_than_nothing(db_session):
    user = _user(db_session)
    concept = _concept(db_session)
    _journey(db_session, user, local_date=TODAY - timedelta(days=1), concept=concept)
    entry = _written_entry(db_session, user, concept)
    _service(db_session).answer_followup(user, entry, text="Je ne sais plus du tout.")
    db_session.refresh(entry)
    assert entry.followup_signal == "not_recalled"


def test_the_followup_is_answered_once(db_session):
    user = _user(db_session)
    concept = _concept(db_session)
    _journey(db_session, user, local_date=TODAY - timedelta(days=1), concept=concept)
    entry = _written_entry(db_session, user, concept)
    service = _service(db_session)
    service.answer_followup(user, entry, text="J’ai rapporté le livre.")
    service.answer_followup(user, entry, text="En fait je ne sais plus.")
    db_session.refresh(entry)
    assert entry.followup_text == "J’ai rapporté le livre."
    assert (
        db_session.query(PilotEvent)
        .filter(
            PilotEvent.event_type == JOURNAL_FOLLOWUP_EVENT_TYPE,
            PilotEvent.user_id == user.id,
        )
        .count()
        == 1
    )


# ---------------------------------------------------------------------------
# 8. cost
# ---------------------------------------------------------------------------


def test_one_priced_pilot_row_per_real_correction_call(db_session):
    user = _user(db_session)
    concept = _concept(db_session)
    _journey(db_session, user, local_date=TODAY - timedelta(days=1), concept=concept)
    corrector = _FakeCorrector({"verdict": "accepted", "score_0_4": 4, "errata": []})
    entry = _write(db_session, user, corrector, "J’ai rapporté le livre à Romy.")

    rows = (
        db_session.query(PilotEvent)
        .filter(
            PilotEvent.event_type == JOURNAL_EVENT_TYPE,
            PilotEvent.user_id == user.id,
        )
        .all()
    )
    assert len(rows) == 1
    assert rows[0].user_id == user.id
    assert rows[0].entity_type == "journal_entry"
    assert rows[0].entity_id == str(entry.id)
    assert rows[0].cost_usd == pytest.approx(0.0004)
    assert rows[0].payload["total_tokens"] == 180
    assert corrector.calls == 1


def test_a_replayed_write_buys_no_second_correction(db_session):
    user = _user(db_session)
    concept = _concept(db_session)
    _journey(db_session, user, local_date=TODAY - timedelta(days=1), concept=concept)
    corrector = _FakeCorrector({"verdict": "accepted", "score_0_4": 4, "errata": []})
    service = _service(db_session, corrector)
    entry = service.offer(user, now=NOW)
    service.write(user, entry, text="J’ai rapporté le livre.")
    service.write(user, entry, text="Autre chose entièrement.")
    db_session.refresh(entry)
    assert entry.entry_text == "J’ai rapporté le livre."
    assert corrector.calls == 1
    assert (
        db_session.query(PilotEvent)
        .filter(
            PilotEvent.event_type == JOURNAL_EVENT_TYPE,
            PilotEvent.user_id == user.id,
        )
        .count()
        == 1
    )


# ---------------------------------------------------------------------------
# 9. honest failure
# ---------------------------------------------------------------------------


def test_a_provider_that_does_not_answer_keeps_the_writing_and_invents_nothing(db_session):
    user = _user(db_session)
    concept = _concept(db_session)
    _journey(db_session, user, local_date=TODAY - timedelta(days=1), concept=concept)
    _due_word(db_session, user, word="livre")
    corrector = _FakeCorrector(fail=True)
    entry = _write(db_session, user, corrector, "J’ai rapporté le livre à Romy mardi.")

    assert entry.status == "unavailable"
    assert entry.assessment_status == "unavailable"
    assert entry.entry_text == "J’ai rapporté le livre à Romy mardi."
    assert entry.correction["errata"] == []
    assert entry.correction["foreground"] is None
    assert entry.errata_ids == []
    assert entry.vocabulary_credit["reason"] == "assessment_unavailable"
    assert db_session.query(UserError).filter(UserError.user_id == user.id).count() == 0
    # The content half does not depend on a provider and still answers.
    assert entry.content_recall["status"] == "scored"


def test_a_scene_with_no_concept_to_check_against_is_unavailable_not_a_pass(db_session):
    """No anchor for the paid checker is a missing measurement, not a good one."""
    user = _user(db_session)
    _journey(db_session, user, local_date=TODAY - timedelta(days=1), concept=None)
    corrector = _FakeCorrector({"verdict": "accepted", "score_0_4": 4, "errata": []})
    entry = _write(db_session, user, corrector, "J’ai rapporté le livre à Romy.")
    assert entry.assessment_status == "unavailable"
    assert corrector.calls == 0


def test_an_empty_entry_is_not_a_submission(db_session):
    user = _user(db_session)
    _journey(db_session, user, local_date=TODAY - timedelta(days=1))
    service = _service(db_session)
    entry = service.offer(user, now=NOW)
    service.write(user, entry, text="   ")
    db_session.refresh(entry)
    assert entry.status == "offered"
    assert entry.entry_text is None


def test_content_cues_drop_function_words_and_what_the_prompt_gave_away():
    cues = content_cues("Vous avez promis de rapporter le livre à Romy mardi.", given={"romy"})
    assert "promis" in cues and "rapporter" in cues and "livre" in cues and "mardi" in cues
    assert "romy" not in cues
    assert "vous" not in cues and "avez" not in cues
