"""#827: a chapter's question is a whole question, never the tail of a chain of alternatives.

Walk 2026-11-16 (persona ``a1-de-fresh``, day 2): «Fin du chapitre» printed
«Ou tu dis au revoir à tout ça ?», the last of the A1 season question's alternatives
(«… Tu prends l'appartement pour toi ? Pour toi et les autres ? Ou tu dis au revoir à
tout ça ?»). ``question_line`` kept the last sentence ending in «?», so a question asked
over several sentences was filed under its last fragment, in the recap and in the
Feuilleton's archive alike.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.services import living_story as engine
from app.services.season.levels import VARIANT_FIELDS, level_key, read_levels
from app.services.sentence_line import question_line, sentences

SEASON = Path("app/data/season/s1")
#: A sentence opening on one of these continues the one before it.
FRAGMENT_OPENING = re.compile(r"^[«\"“(]?\s*(?:ou|et|mais|pour)\b", re.IGNORECASE)


def _season_questions() -> dict[str, str]:
    import json

    question = json.loads((SEASON / "season.json").read_text(encoding="utf-8"))["question"]
    by_level = {"a2": question["a2"]}
    if question.get("b1"):
        by_level["b1"] = question["b1"]
    variants = read_levels(SEASON)["lines"].get(level_key(question["a2"], question.get("b1"))) or {}
    for field in VARIANT_FIELDS:
        if isinstance(variants.get(field), str) and variants[field].strip():
            by_level[field] = variants[field]
    return by_level


def test_every_level_of_the_season_question_has_a_variant():
    # The A1 one is the walk's: if it went missing, the next test would pass on nothing.
    assert {"a1", "a2", "b2", "c1"} <= set(_season_questions())


@pytest.mark.parametrize("level", sorted(_season_questions()))
def test_each_level_of_the_season_question_files_a_whole_question(level):
    text = _season_questions()[level]
    line = question_line(text, engine.DIGEST_PART_CHARS)

    assert line, f"{level}: no question at all"
    assert len(line) <= engine.DIGEST_PART_CHARS * 2
    assert line.endswith("?"), f"{level}: {line!r} is not a question"
    assert not FRAGMENT_OPENING.match(line), f"{level}: {line!r} opens on the tail of a chain of alternatives"
    # Whole sentences of the text, in order, never a piece of one.
    assert line in " ".join(sentences(text)), f"{level}: {line!r} is not cut from the text"


def test_the_a1_chain_is_filed_from_its_first_question():
    a1 = _season_questions()["a1"]
    line = question_line(a1, engine.DIGEST_PART_CHARS)

    assert line.startswith("Alors, qu'est-ce que tu fais ?"), line
    assert line.endswith("Ou tu dis au revoir à tout ça ?"), line


def test_the_archive_line_of_a_chapter_with_no_resolution_is_the_whole_question():
    a1 = _season_questions()["a1"]
    digest = engine.chapter_digest_line({"question": a1, "resolved_fr": "", "development": ""})

    assert digest and not FRAGMENT_OPENING.match(digest), digest
    assert digest.startswith("Alors, qu'est-ce que tu fais ?"), digest


def test_a_chain_too_long_to_fit_keeps_its_opening_questions_not_its_tail():
    text = (
        "Le café brûle encore dans les mémoires du quartier, et personne ne veut en parler franchement. "
        "Qu'est-ce que tu fais de l'appartement que ta grand-mère t'a laissé au-dessus du Mistral ? "
        "Tu le gardes pour toi seul ? Pour toi et pour tous ceux qui vivent ici depuis des années ? "
        "Ou tu rends la clé au notaire ?"
    )
    line = question_line(text, 160)

    assert line.startswith("Qu'est-ce que tu fais"), line
    assert line.endswith("?") and len(line) <= 160, line


def test_a_question_that_continues_a_statement_brings_the_statement_or_nothing():
    text = (
        "Ta grand-mère t'a laissé l'étage au-dessus du Mistral, et avec lui le feu qui a pris en dessous, "
        "il y a quarante ans. Ou tu préfères ne rien savoir de tout ça, et partir demain ?"
    )
    line = question_line(text, 100)

    assert not FRAGMENT_OPENING.match(line), line


def test_a_single_question_is_still_the_last_one_asked():
    text = (
        "Odile ferme le café à minuit, comme chaque soir depuis l'incendie, et Marin range les chaises. "
        "Personne ne parle. Qui a gardé la deuxième clé ?"
    )

    assert question_line(text, 80) == "Qui a gardé la deuxième clé ?"


def test_a_row_filed_under_the_tail_alone_is_read_back_without_it():
    # Rows written before the fix carry «Ou tu dis au revoir à tout ça ?» as their question.
    from app.services import story_archive

    tail = "Ou tu dis au revoir à tout ça ?"
    assert engine.chapter_digest_line({"question": tail, "resolved_fr": ""}) is None
    assert engine.chapter_digest_line({"question": tail, "resolved_fr": "Marin garde la clé."}) == "Marin garde la clé."
    assert story_archive.clean_digest(f"{tail} → Marin garde la clé.") == "Marin garde la clé."
    assert story_archive.clean_digest(tail) is None
    # A resolution that opens on «Et» is no question, and stays.
    assert story_archive.clean_digest("Et Marin garde la clé.") == "Et Marin garde la clé."
