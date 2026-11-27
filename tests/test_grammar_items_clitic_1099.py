"""#1099: a clitic «l'», «le», «la», «les» before a verb is never the article rule.

The day-7 walk (26 Nov 2026) was asked, on «Regel zum Wiederholen · Le, la, l', les»,
which sentence carries the rule, and «Romy allume sa caméra, puis l'éteint en te
regardant.» was the key: its «l'» is the pronoun «la» in front of a verb. The article
unit's regex finds «l'» before any vowel and «le/la/les» before any word; the
noun-phrase gate (:func:`grammar_items.rule_span`) only checked the shape of the
determiner, never whether the word after it is a noun or a verb.
"""
from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.db.models.grammar import GrammarConcept
from app.services import concept_life, grammar_items
from app.services.grammar_catalog import FrenchCoreGrammarCatalog

ROMY = "Romy allume sa caméra, puis l'éteint en te regardant."
WALK_SCENE = [ROMY, "Jonas, tu m'aides ?", "Alors, on fait quoi ?"]
ARTICLE_LINE = "Le café est prêt, la table est libre."


def _article_unit(db: Session) -> dict:
    FrenchCoreGrammarCatalog(db, "v2").ensure_catalog()
    concept = db.query(GrammarConcept).filter(GrammarConcept.external_id == "FR2_A11_LE_LA").one()
    brief = concept_life.concept_brief(db, concept, control_language="de")
    assert brief["noun_phrase"] is True
    return brief


def test_walk_line(db_session: Session) -> None:
    brief = _article_unit(db_session)
    assert grammar_items.rule_span(brief, ROMY) is None, "«l'éteint» is a pronoun before a verb"


@pytest.mark.parametrize(
    "line",
    [
        "Margaux la regarde sans rien dire.",
        "Lila les appelle demain.",
        "Puis le prend et sort.",
        "Il ouvre la boîte et l'écoute.",
        "Jonas l'aime beaucoup.",
    ],
    ids=["la", "les", "le", "et-l", "l"],
)
def test_clitic(db_session: Session, line: str) -> None:
    brief = _article_unit(db_session)
    bounds = grammar_items.rule_span(brief, line)
    marked = line[bounds[0] : bounds[1]] if bounds else None
    assert bounds is None or marked == "la boîte", (line, marked)


@pytest.mark.parametrize(
    ("line", "marked"),
    [
        (ARTICLE_LINE, "Le café"),
        ("L'école est fermée.", "L'école"),
        ("Je cherche l'hôtel.", "l'hôtel"),
        ("L'aide arrive enfin.", "L'aide"),
        ("Tu pousses la porte du Mistral.", "la porte"),
        ("J'aime les chats.", "les chats"),
    ],
    ids=["le", "l-ecole", "l-hotel", "l-aide", "la", "les"],
)
def test_article(db_session: Session, line: str, marked: str) -> None:
    brief = _article_unit(db_session)
    bounds = grammar_items.rule_span(brief, line)
    assert bounds is not None, line
    assert line[bounds[0] : bounds[1]] == marked


def test_no_item(db_session: Session) -> None:
    brief = {**_article_unit(db_session), "examples": []}
    task = grammar_items.recognise_item(brief, sentences=WALK_SCENE, language="de", review=True)
    assert task is None, f"built with the key {task.solution_fr if task else None!r}"


def test_romy_never_key(db_session: Session) -> None:
    brief = _article_unit(db_session)
    task = grammar_items.recognise_item(brief, sentences=WALK_SCENE, language="de", review=True)
    if task is not None:
        assert task.solution_fr != ROMY


def test_answer(db_session: Session) -> None:
    brief = {**_article_unit(db_session), "examples": []}
    task = grammar_items.recognise_item(
        brief, sentences=[*WALK_SCENE, ARTICLE_LINE], language="de", review=True
    )
    assert task is not None
    assert task.solution_fr == ARTICLE_LINE
    texts = [option["text_fr"] for option in task.options]
    assert ROMY not in texts, "«sa caméra» is a noun phrase: never a distractor"
