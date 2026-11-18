"""#894 (walk 18 Nov, `a1-de-fresh`, day 1): the être rule drill.

«In welchem Satz steckt die Regel von heute?» under the rule card «Ich bin, du bist:
Subjektpronomen und être» offered «C'est qui, vous ?» (the key), «Vous allez vendre
l'appartement d'Odile ?» and «Il pleut.». A beginner picked the sentence with the
subject pronoun «Vous»: the rule's title promises subject pronouns. The miss said
only «Être heißt sein: je suis, tu es, …»; nothing named the «est» hidden in «C'est»,
or said that «allez» is *aller*.

* A «does not use the rule» distractor now also holds nothing the rule's *title*
  names (here: no subject pronoun), not only nothing its detector keys.
* A miss names the key's form («est» in «C'est», être) and, for the chosen
  sentence, why it does not use the rule («allez» comes from aller).
"""
from __future__ import annotations

import re
from dataclasses import replace
from types import SimpleNamespace

from sqlalchemy.orm import Session

from app.db.models.grammar import GrammarConcept
from app.services import concept_life, grammar_items, journey_learning
from app.services import journey_planner as planner
from app.services.grammar_catalog import FrenchCoreGrammarCatalog
from app.services.journey_contracts import (
    AssistanceLevel,
    AttemptAnswer,
    InputMode,
    RecallTask,
    TaskOutcome,
)

KEY = "C'est qui, vous ?"
VOUS_ALLEZ = "Vous allez vendre l'appartement d'Odile ?"
IL_PLEUT = "Il pleut."
#: Day 1 of season 1 at A1 (app/data/season/s1/levels_a.json), in scene order.
DAY_ONE = (
    "Il pleut. Tu as une valise, une lettre, une clé.",
    "Ah ! Vous voilà. Vous venez pour M. Marchand ?",
    "C'est qui ?",
    "La personne de la vente.",
    "Prenez une chaise.",
    "Vous allez vendre l'appartement d'Odile ? À Solvel ?",
    "Regarde ses chaussures, Marin. Ce n'est pas Solvel.",
    "Alors ? C'est qui, vous ? Et pourquoi ici ?",
    "Le café d'Odile. Toujours le même.",
    "Ah.",
    "Bravo, Gus. Belle gaffe.",
)
#: The subject pronouns the rule's title names («Subjektpronomen»).
SUBJECT_PRONOUN = re.compile(r"\b(?:j'|(?:je|tu|il|elle|on|nous|vous|ils|elles)\b)", re.IGNORECASE)
GERMAN = SimpleNamespace(native_language="de", cefr_estimate="A1", proficiency_level="A1")


def _etre(db: Session) -> tuple[dict, GrammarConcept]:
    FrenchCoreGrammarCatalog(db, "v2").ensure_catalog()
    concept = db.query(GrammarConcept).filter(GrammarConcept.external_id == "FR2_A11_ETRE").one()
    return concept_life.concept_brief(db, concept, control_language="de"), concept


def _miss(db: Session, task: RecallTask, option_id: str):
    return journey_learning.evaluate_recall(
        db,
        user=GERMAN,  # type: ignore[arg-type]
        task=task,
        answer=AttemptAnswer(mode=InputMode.TEXT, text="", option_id=option_id),
        assistance=AssistanceLevel.NONE,
    )


def _text(task: RecallTask, option_id: str | None) -> str:
    return next(option["text_fr"] for option in task.options if option["id"] == option_id)


def test_distractors(db_session: Session) -> None:
    """No «not this one» holds a subject pronoun: the rule's title names them."""

    brief, _ = _etre(db_session)
    assert "Subjektpronomen" in brief["title_native"]
    task = grammar_items.recognise_item(brief, sentences=planner.scene_sentences(*DAY_ONE), language="de")
    assert task is not None, "day 1 still has a «uses today's rule» item"
    distractors = [o["text_fr"] for o in task.options if o["id"] != task.correct_option_id]
    assert distractors
    for text in distractors:
        assert not SUBJECT_PRONOUN.search(text), (
            f"«{text}» has a subject pronoun, which the rule's title names: a beginner reads it as the rule"
        )
    # The walk's own three sentences: neither «Vous allez…» nor «Il pleut.» is a «not this one».
    walk = grammar_items.recognise_item(brief, sentences=[KEY, VOUS_ALLEZ, IL_PLEUT], language="de")
    assert walk is None or {o["text_fr"] for o in walk.options} == {KEY}, [o["text_fr"] for o in walk.options]


def _walks_item(brief: dict) -> RecallTask:
    """The item as the walk saw it (stored in journeys before this fix)."""

    target = grammar_items.grammar_target(brief)
    return RecallTask(
        task_type="choice",
        instruction_native=grammar_items._RECOGNISE_USE["de"],
        prompt_fr=None,
        options=[
            {"id": "o1", "text_fr": KEY},
            {"id": "o2", "text_fr": VOUS_ALLEZ},
            {"id": "o3", "text_fr": IL_PLEUT},
        ],
        target=target,
        optional=False,
        correct_option_id="o1",
        accepted_answers=[KEY],
        hint_native=brief["rule_short_native"],
        solution_fr=KEY,
        options_kind="sentences",
    )


def test_miss_note(db_session: Session) -> None:
    """The walk's item: a miss names «est» in «C'est» (être) and the picked verb («allez»: aller)."""

    brief, _ = _etre(db_session)
    task = _walks_item(brief)

    result = _miss(db_session, task, "o2")
    assert result.outcome is TaskOutcome.NOT_YET
    assert result.correction is not None
    note = result.correction.note_native
    assert "„est“" in note and "„C'est“" in note and "(être)" in note, f"the key's form is not named: {note!r}"
    assert "„allez“" in note and "aller" in note.replace("„allez“", ""), f"«allez» is not said to be aller: {note!r}"

    note = _miss(db_session, task, "o3").correction.note_native
    assert "„est“" in note and "„C'est“" in note, f"the key's form is not named: {note!r}"
    assert "„pleut“" in note and "pleuvoir" in note, f"«pleut» is not said to be pleuvoir: {note!r}"
    # The rule's one-line summary still closes the note.
    assert note.endswith(brief["rule_short_native"]), note


def test_day_one(db_session: Session) -> None:
    """Day 1's item as built today: a miss on any option names the key's marked form."""

    brief, _ = _etre(db_session)
    task = grammar_items.recognise_item(brief, sentences=planner.scene_sentences(*DAY_ONE), language="de")
    assert task is not None
    key = _text(task, task.correct_option_id)
    span = grammar_items.rule_span(brief, key)
    assert span is not None
    marked = grammar_items.fold_apostrophes(key)[span[0]:span[1]]
    for option in task.options:
        if option["id"] == task.correct_option_id:
            continue
        note = _miss(db_session, task, option["id"]).correction.note_native
        assert f"„{marked}“" in note, f"miss on «{option['text_fr']}» does not name «{marked}» in «{key}»: {note!r}"
        assert "être" in note.split(brief["rule_short_native"])[0], note


def test_er_guard(db_session: Session) -> None:
    """«„pleut“ kommt von pleuvoir, nicht von regarder» would be false for the -er rule:
    the chosen sentence is set against the key's verb only when the rule's title names it."""

    FrenchCoreGrammarCatalog(db_session, "v2").ensure_catalog()
    concept = db_session.query(GrammarConcept).filter(GrammarConcept.external_id == "FR2_A11_ER_VERBS").one()
    brief = concept_life.concept_brief(db_session, concept, control_language="de")
    key = next(text for text in ("Tu regardes la mer.", "Nous parlons français.", "Elle aime le café.")
               if grammar_items.rule_span(brief, text) is not None)
    task = replace(
        _walks_item(brief),
        options=[{"id": "o1", "text_fr": key}, {"id": "o3", "text_fr": IL_PLEUT}],
        accepted_answers=[key],
        solution_fr=key,
    )
    note = _miss(db_session, task, "o3").correction.note_native
    assert "nicht von" not in note and "keine Form von" not in note, note
