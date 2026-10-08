"""EXPERIENCE-REVIEW 2026-10-04 — one regression per fix of the 30-day life walk.

Each test names the moment a learner met in the walk
(``docs/implementation/atelier-v2/EXPERIENCE-REVIEW-2026-10-04.md``).
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.db.models.error import UserError
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services import grammar_items, pragmatics
from app.services import journey_planner as planner
from app.services.answer_acceptance import judge
from app.services.journey_contracts import TargetKind, TargetRef
from app.services.journey_learning import attempted_answer
from app.services.vocabulary_credit import VocabularyCreditService
from tests import walk_checks
from tests.test_journey_planner import _brief

UNIT_JE_VOUDRAIS = "FR2_A11_JE_VOUDRAIS"

# ---------------------------------------------------------------------------
# Grading: «ca» for «ça»; a wish is not a blunt request
# ---------------------------------------------------------------------------


def test_ca_typed_for_ca_cedilla_is_a_named_slip_not_a_refusal() -> None:
    """C1 day 20: «Elles ont beau essayer, ca ne marche pas.» was refused."""

    verdict = judge("Elles ont beau essayer, ca ne marche pas.", ["Elles ont beau essayer, ça ne marche pas."])
    assert verdict.correct and verdict.accent_slip
    assert judge("ca va", ["ça va"]).correct


def test_the_literary_ca_grave_stays_strict() -> None:
    assert not judge("ça", ["çà"]).correct
    assert not judge("çà va", ["ça va"]).correct


@pytest.mark.parametrize(
    "wish",
    ["Je veux comprendre qui elle était.", "Je veux que tu restes.", "je veux partir demain", "Oui, je veux bien."],
)
def test_a_wish_is_never_corrected_to_je_voudrais(wish: str) -> None:
    """A1 days 4–5: «Je veux comprendre qui elle était» was corrected to «Je voudrais»
    and came back as the most frequent reply target of the month (45 times)."""

    assert pragmatics.bare_request_finding(wish, level_band="A1") is None


@pytest.mark.parametrize("asking", ["Je veux un café.", "je veux l'addition", "Je veux ça.", "je veux de l'eau"])
def test_a_request_for_something_is_still_blunt(asking: str) -> None:
    finding = pragmatics.bare_request_finding(asking, level_band="A1")
    assert finding is not None and finding.code == pragmatics.BLUNT_WANT
    assert finding.span.casefold() == "je veux"  # the span is the verb, never the object


# ---------------------------------------------------------------------------
# Repairs are of the learner's own French
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("give_up", ["euh je ne sais pas", "je sais pas", "?", "keine Ahnung", "Ich weiß nicht."])
def test_a_give_up_is_not_an_attempt(give_up: str) -> None:
    assert not attempted_answer(give_up, "appartement")


@pytest.mark.parametrize("attempt", ["appartment", "Je es français", "je veux un marteau", "cle"])
def test_wrong_french_is_an_attempt(attempt: str) -> None:
    assert attempted_answer(attempt, "x")


@pytest.mark.parametrize(
    ("wording", "answer"),
    [
        ("der Schlüssel", "quoi"),  # a tapped card, posed as «what you said»
        ("merci pour ta lettre. hier je suis alle au mistral et je parle avec lila", "clé"),  # a letter, and a word it lacked
        ("clé", "vendre"),
    ],
)
def test_a_repair_is_not_posed_when_the_answer_does_not_fix_the_wording(wording: str, answer: str) -> None:
    """A2 day 4: «Schreib richtig, was du gesagt hast: der Schlüssel» → «quoi»."""

    target = TargetRef(kind=TargetKind.ERROR, id="e", label_fr=answer, label_native="why")
    task = planner.build_recall_task(
        target=target, scenario=_brief(control_language="de"), affordances=[], optional=False, learner_text=wording
    )
    assert task is None


def test_a_real_repair_is_still_posed() -> None:
    target = TargetRef(kind=TargetKind.ERROR, id="e", label_fr="Je suis français.", label_native="why")
    task = planner.build_recall_task(
        target=target, scenario=_brief(control_language="de"), affordances=[], optional=False, learner_text="Je es français."
    )
    assert task is not None and task.prompt_fr == "Je es français."


def _user_and_word(db_session, *, native: str = "de") -> tuple[User, VocabularyWord]:
    user = User(email=f"review-{uuid.uuid4().hex}@example.com", hashed_password="x", target_language="fr", native_language=native)
    # An unusual word on purpose: the shared test database keeps it, and no scene uses it.
    word = VocabularyWord(language="fr", word="écuelle", normalized_word="écuelle", german_translation="Napf", english_translation="bowl")
    db_session.add_all([user, word])
    db_session.commit()
    return user, word


def test_a_missed_practice_item_lapses_the_word_but_opens_no_repair(db_session) -> None:
    """A1 day 2: the tapped wrong card came back as «The word clé needs another repair»."""

    user, word = _user_and_word(db_session)
    result = VocabularyCreditService(db_session).apply(
        user=user, word=word, event_type="produced_incorrect", source_type="atelier",
        learner_text="Napf", record_erratum=False,
    )
    assert result.erratum_id is None
    assert db_session.query(UserError).filter(UserError.user_id == user.id).count() == 0


def test_a_vocabulary_repair_is_written_in_the_learners_language(db_session) -> None:
    """C1 day 11 (German native): «The word autre needs another repair in context.»"""

    user, word = _user_and_word(db_session, native="de")
    VocabularyCreditService(db_session).apply(
        user=user, word=word, event_type="produced_incorrect", source_type="mission", learner_text="la ecuel"
    )
    erratum = db_session.query(UserError).filter(UserError.user_id == user.id).one()
    text = " ".join(str(value) for value in (erratum.display_label, erratum.why_wrong, erratum.repair_hint))
    assert "needs another repair" not in text and "Vocabulary:" not in text
    assert "„écuelle“" in text and "Wort" in text


# ---------------------------------------------------------------------------
# A Rappel never says «today's rule»; recognition asks which sentence *uses* it
# ---------------------------------------------------------------------------


def _unit(db_session, external_id: str, language: str = "de") -> dict:
    from tests.test_rule_step_regressions import _unit as unit

    return unit(db_session, external_id, language=language)


def test_a_review_of_an_earlier_rule_never_calls_it_todays(db_session) -> None:
    """A1 day 13: «Welcher Satz folgt der Regel von heute?» about the -er verbs,
    asked before the day's own rule (Ne…pas)."""

    brief = _unit(db_session, "FR_A1_NOUN_001")
    for stability in (1.0, 5.0):
        for day in ("2026-03-10", "2026-03-11", "2026-03-12"):
            task = grammar_items.review_item(
                {**brief, "stability": stability},
                sentences=["Je voudrais une petite table.", "Il pleut.", "Tu viens ?"],
                language="de",
                day_key=day,
            )
            if task is None:
                continue
            for text in (task.instruction_native, task.goal_native):
                assert "von heute" not in str(text or ""), text


def test_an_a1_recognition_asks_which_sentence_uses_the_rule(db_session) -> None:
    brief = _unit(db_session, "FR_A1_NOUN_001")
    task = grammar_items.recognise_item(
        brief, sentences=["Je pense partir.", "Tu viens ?"], language="de"
    )
    assert task is not None
    assert task.instruction_native == "In welchem Satz steckt die Regel von heute?"


# ---------------------------------------------------------------------------
# Season: the ask-again line names its speaker; hints are graded
# ---------------------------------------------------------------------------


def test_the_ask_again_line_names_its_speaker() -> None:
    """A1 day 27: «lila_bonnet : Pardon ? Je ne comprends pas… Et en français ?»"""

    from app.services.season.runtime import SEASON_CONTEXT_KEY, _named_turn

    scenario = SimpleNamespace(story_context={SEASON_CONTEXT_KEY: {"id": "s1"}})
    turn = _named_turn(scenario, {"id": "t2.b.key", "to": "lila_bonnet", "to_name": None})
    assert turn["to_name"] == "Lila Bonnet"


def test_a_season_hint_is_the_opening_of_the_example_not_the_whole_reply() -> None:
    """A1 day 8: the hint and the suggested reply were the same sentence."""

    from app.services.season.runtime import hint_for

    turn = {"replies": [{"examples": ["Je vends et je pars. Une semaine."], "clumsy": False}]}
    hint = hint_for(turn, "de")
    assert hint.startswith("Zum Beispiel:")
    assert "Une semaine" not in hint and hint.endswith("…»")
    short = {"replies": [{"examples": ["Les photos."], "clumsy": False}]}
    assert hint_for(short, "de") == "Zum Beispiel: «Les photos.»"


# ---------------------------------------------------------------------------
# Practice before the scene, and the B1+ day's new words
# ---------------------------------------------------------------------------


def test_a_word_not_met_yet_is_not_gender_quizzed_before_the_scene() -> None:
    """A1 day 1: the very first item was «Maskulin oder feminin? clé»."""

    formats = planner._slot_formats(
        "warmup", shape=planner.DayShape.STANDARD, dice=None, identity="w", used_today={},
        used_by_target=set(), new_word=True,
    )
    assert "classify" not in formats and formats
    met = planner._slot_formats(
        "warmup", shape=planner.DayShape.STANDARD, dice=None, identity="w", used_today={}, used_by_target=set(),
    )
    assert "classify" in met


def test_an_advanced_learners_new_scene_word_is_never_a_grammar_word(db_session) -> None:
    """B2 and C1 walks: the day's new word was «pas», «moi», «elle», «cinq»."""

    from app.services.journey_learning import _new_vocabulary_anchor

    user = User(email=f"review-{uuid.uuid4().hex}@example.com", hashed_password="x", target_language="fr", native_language="en")
    rows = [
        VocabularyWord(language="fr", word=word, normalized_word=word, english_translation=word, difficulty_level=level, frequency_rank=rank)
        for word, level, rank in (("pas", 1, 1), ("cinq", 1, 2), ("vendre", 1, 3), ("néanmoins", 4, 900))
    ]
    db_session.add_all([user, *rows])
    db_session.commit()
    try:
        scenario = _brief(level_band="B2", control_language="en")
        anchor = _new_vocabulary_anchor(
            db_session, user=user, scenario=scenario, terms={"pas", "cinq", "vendre", "néanmoins"}, exclude=set()
        )
        assert anchor is not None and anchor.target.label_fr == "néanmoins"
        a1 = _brief(level_band="A1", control_language="en")
        first = _new_vocabulary_anchor(
            db_session, user=user, scenario=a1, terms={"pas", "cinq", "vendre", "néanmoins"}, exclude=set()
        )
        assert first is not None and first.target.label_fr == "pas"  # a beginner still meets «pas»
    finally:
        # The shared test database keeps no catalogue words of ours: later suites
        # would meet «pas» as a scene's new word.
        for row in rows:
            db_session.delete(row)
        db_session.commit()


# ---------------------------------------------------------------------------
# The band check's light checks do not flood the drill
# ---------------------------------------------------------------------------


def test_words_credited_far_below_the_learners_band_are_trusted_longer() -> None:
    from app.services.band_check import credit_schedule

    near_stability, near = credit_schedule(1)
    far_stability, far = credit_schedule(5)
    assert near == (20, 90) and far[0] >= 90
    # The stability keeps the word «known» (R ≥ 0.85) until its check is due.
    for stability, window in ((near_stability, near), (far_stability, far)):
        retrievability = (1 + window[1] / (9 * stability)) ** -1
        assert retrievability >= 0.85


# ---------------------------------------------------------------------------
# The Courrier: no claim without an assessment, no English, the learner's level
# ---------------------------------------------------------------------------


def test_an_unassessed_letter_is_never_told_something_is_missing() -> None:
    """C1 day 1: a flawless letter got «il me manque encore ceci : Écrire un message
    qu'on pourrait vraiment envoyer»."""

    from app.services.missions import MissionConversationService

    mission = SimpleNamespace(
        turns=[SimpleNamespace(role="user")],
        prompt_payload={"messenger": {"opening_message": "Salut, c'est Romy.", "register": "tu / warm informal"}},
        title="Trois questions", brief="", mission_type="message",
    )
    unassessed = [{"id": "real_world_task", "label": "Écrire un message", "met": False, "assessed": False}]
    reply = MissionConversationService._fallback_response(None, mission, objective_progress=unassessed)
    assert "manque" not in reply and "ton message" in reply
    assessed = [{"id": "real_world_task", "label": "Écrire un message", "met": False, "assessed": True}]
    assert "manque" in MissionConversationService._fallback_response(None, mission, objective_progress=assessed)


def test_a_story_letter_objective_is_french_and_carries_its_translations() -> None:
    from app.services.story_correspondence import story_letter_context

    facts = story_letter_context({"character_name": "Marin", "register": "tu", "summary_fr": "La soupe."})
    assert facts["desired_outcome_i18n"]["de"].startswith("Marin weiß")
    assert facts["desired_outcome_i18n"]["fr"] == facts["desired_outcome"]


# ---------------------------------------------------------------------------
# The walk checks that hold these invariants actually catch them
# ---------------------------------------------------------------------------


def _transcript(events: list[dict]) -> dict:
    return {"persona": "p", "quality": "q", "day": 1, "native": "de", "cefr": "A1.1", "events": events}


def test_the_walk_flags_a_repair_of_a_give_up() -> None:
    event = {"step": {"kind": "recall", "prompt": {"target": {"kind": "error"}, "prompt_fr": "euh je ne sais pas"}}}
    assert walk_checks.check_repairs(_transcript([event]))


def test_the_walk_flags_todays_rule_on_a_rappel() -> None:
    event = {
        "step": {
            "kind": "recall",
            "prompt": {"target": {"kind": "grammar", "id": "7"}, "instruction_native": "Welcher Satz folgt der Regel von heute?"},
        }
    }
    assert walk_checks.check_rule_of_today(_transcript([event]))
    rule = {"step": {"kind": "rule", "prompt": {"concept_id": 7}}}
    assert not walk_checks.check_rule_of_today(_transcript([rule, event]))


def test_the_walk_flags_a_wish_corrected_to_je_voudrais() -> None:
    event = {
        "step": {"kind": "respond", "prompt": {}},
        "answer": {"input": {"text": "Je veux comprendre qui elle était."}},
        "result": {"correction": {"corrected_fr": "Je voudrais"}},
    }
    assert walk_checks.check_wishes_are_not_corrected(_transcript([event]))


def test_the_life_walk_flags_a_flooded_drill_and_a_dishonest_letter() -> None:
    record = {
        "persona": "b2-en", "quality": "strong", "true_level": "B2.1",
        "days": [
            {
                "day": 20,
                "journey": {"learner_level": "B2"},
                "drill": {"summary": {"due_total": 300}},
                "courrier": {"letters": [{"correction": {"verdict": "unassessed"}, "answer_back": "Il me manque encore ceci", "objectives": ["Placer une fois : Je suis, tu es : les pronoms et être"]}]},
            }
        ],
    }
    problems = walk_checks.check_life(record)
    assert any("backlog" in p for p in problems)
    assert any("unassessed" in p for p in problems)
    assert any("Placer une fois" in p for p in problems)


del datetime, timedelta, UTC


# ---------------------------------------------------------------------------
# The in-story recast offers two forms of one word, never two words
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("wrong", "right"),
    [("On commence quand ?", "On commence maintenant ?"), ("Je suis un peu perdu", "Je suis un peu perdu(e)")],
)
def test_a_forced_choice_is_never_between_two_different_words(wrong: str, right: str) -> None:
    """The paid A2 read: «Pardon, on commence maintenant ou quand ?» — a content
    change posed as a form; «perdu ou perdu(e)» — an agreement no one can judge."""

    from app.services.journey_conversation import self_repair_question

    line, kind = self_repair_question(wrong_fr=wrong, corrected_fr=right, register="tu")
    assert kind == "repetition" and " ou " not in line


def test_a_forced_choice_between_two_forms_is_kept() -> None:
    from app.services.journey_conversation import self_repair_question

    assert self_repair_question(wrong_fr="un homme", corrected_fr="une homme", register="tu") == ("Pardon, un ou une homme ?", "choice")


def test_the_a1_essai_never_asks_to_rewrite_what_the_item_before_printed(db_session) -> None:
    """A1 day 19: «Was ist richtig? … Je voudrais un café, s'il vous plaît.», then
    «Korrigiere: Je voudrais de un café.» → «Je voudrais un café.»."""

    from app.services.answer_acceptance import fold_all
    from app.services.grammar_catalog import FrenchCoreGrammarCatalog

    FrenchCoreGrammarCatalog(db_session, "v2").ensure_catalog()
    from app.db.models.grammar import GrammarConcept
    from app.services import concept_life

    concept = db_session.query(GrammarConcept).filter(GrammarConcept.external_id == UNIT_JE_VOUDRAIS).one()
    brief = concept_life.concept_brief(db_session, concept, control_language="de")
    items = grammar_items.guided_items(
        brief, sentences=["Bonjour, je voudrais un café et une tarte, s'il vous plaît.", "Tu en penses quoi ?"], language="de"
    )
    shown: list[str] = []
    for item in items:
        if item.task_type == "transform":
            assert not any(fold_all(item.solution_fr) in earlier for earlier in shown), item.solution_fr
        shown.append(fold_all(item.solution_fr))


def test_a_story_letter_keeps_its_objective_translations_into_the_courrier() -> None:
    """A2 day 3 (German): the letter day printed «Gus sait ce que vous en pensez…»
    as the learner's task — the translations were dropped on the way."""

    from app.services.missions import MissionGenerator, success_signal_i18n
    from app.services.story_correspondence import story_letter_context

    facts = story_letter_context({"character_name": "Gus", "register": "vous", "summary_fr": "La pétition."})
    generator = MissionGenerator.__new__(MissionGenerator)
    context = generator._custom_context({**facts, "summary_fr": "La pétition."})
    assert context["desired_outcome_i18n"]["de"].startswith("Gus weiß")
    _title, _brief, messenger, objectives = generator._story_born_mission(
        title="", brief="", messenger={}, custom_context=context
    )
    assert success_signal_i18n(messenger)["de"].startswith("Gus weiß")
    assert not objectives[0]["label"].startswith("Achieve")


def test_a_stem_accent_slip_on_a_participle_is_forgiven_and_named() -> None:
    """C1 day 27: «Une fois rentrée, Marie a diné.» was refused for «dîné» — the
    participle's «-é» was right; only the stem's circumflex was missing."""

    verdict = judge("Une fois rentrée, Marie a diné.", ["Une fois rentrée, Marie a dîné."])
    assert verdict.correct and verdict.accent_slip
    assert not judge("Il a mange.", ["Il a mangé."]).correct  # the ending still decides
