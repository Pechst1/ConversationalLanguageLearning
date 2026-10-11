"""WP-84 (b) — le / la on every Lexique noun and in the word sheet; the POS fix.

* every noun of the core lexicon carries a gender (m / f, or mf for the
  epicene ones), and every lemma a part of speech;
* a card without a stored gender reads it from the lexicon (Lexique rows,
  the word sheet's ``VocabularyWordRead``), a stored value always wins;
* «frère», «hiver», «notre» are no longer verbs.
"""
from __future__ import annotations

import json

import pytest

from app.db.models.vocabulary import VocabularyWord
from app.schemas.vocabulary import VocabularyWordRead
from app.services.lexical_coverage import LEXICON_PATH
from app.services.lexicon_grammar import (
    POS_PATH,
    lemma_key,
    lexicon_gender,
    lexicon_grammar_table,
    word_grammar,
)
from app.services.vocabulary_coverage import inferred_part_of_speech


def _card(word: str, **fields) -> VocabularyWord:
    return VocabularyWord(id=1, language="fr", word=word, normalized_word=word, topic_tags=[], **fields)


def test_every_lexicon_lemma_has_a_part_of_speech_and_every_noun_a_gender() -> None:
    lemmas = json.loads(LEXICON_PATH.read_text(encoding="utf-8"))["lemmas"]
    table = lexicon_grammar_table()
    missing = [lemma for lemma in lemmas if lemma not in table]
    assert missing == []
    nouns = {lemma: entry for lemma, entry in table.items() if entry["pos"] == "noun"}
    assert len(nouns) > 1200
    assert all(entry.get("gender") in {"m", "f", "mf"} for entry in nouns.values())
    assert json.loads(POS_PATH.read_text(encoding="utf-8"))["version"] == "fr-core-pos-v1"


@pytest.mark.parametrize(
    ("word", "pos"),
    [("frère", "noun"), ("hiver", "noun"), ("notre", "function"), ("plaisir", "noun"), ("manger", "verb")],
)
def test_the_pos_fix(word: str, pos: str) -> None:
    assert inferred_part_of_speech(_card(word)) == pos


@pytest.mark.parametrize(
    ("surface", "gender"),
    [("frère", "m"), ("le frère", "m"), ("hiver", "m"), ("l'hiver", "m"), ("la clé", "f"),
     ("maison", "f"), ("semaine", "f"), ("élève", None), ("manger", None)],
)
def test_lexicon_gender(surface: str, gender: str | None) -> None:
    assert lexicon_gender(surface) == gender


def test_lemma_key_strips_the_article() -> None:
    assert lemma_key("La Maison") == "maison"
    assert lemma_key("l’heure") == "heure"


def test_the_word_sheet_reads_le_la_from_the_lexicon() -> None:
    read = VocabularyWordRead.model_validate(_card("frère"))
    assert (read.part_of_speech, read.gender) == ("noun", "m")
    read = VocabularyWordRead.model_validate(_card("la maison"))
    assert read.gender == "f"
    # A stored value wins; a non-French card is left alone.
    assert word_grammar(_card("frère", gender="f", part_of_speech="noun")) == ("noun", "f")
    assert word_grammar(VocabularyWord(language="de", word="Bruder")) == (None, None)
    # A verb gets no gender.
    assert word_grammar(_card("manger")) == ("verb", None)
