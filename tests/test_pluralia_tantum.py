"""Codex review on #465: a noun used in the plural only took a singular article
(«le gens», «la vacances»). The catalogue carries no number, so the curated list
``app/data/lexical/fr_pluralia_tantum.json`` is the one place that says it; the
server sends it as the noun's ``number`` and the client's ``articleFor`` reads «les».
A final -s or -x is never read as a plural (le bras, le prix, le temps)."""
from __future__ import annotations

import json
from types import SimpleNamespace

from app.schemas.vocabulary import VocabularyWordRead
from app.services.lexical_coverage import LEXICON_PATH
from app.services.lexicon_grammar import pluralia_tantum, word_grammar, word_number


def _word(text: str, **fields: object) -> SimpleNamespace:
    return SimpleNamespace(**{"word": text, "normalized_word": text, "language": "fr", "part_of_speech": None, "gender": None, **fields})


def test_gens_and_vacances_are_plural_nouns() -> None:
    assert word_number(_word("gens")) == "pl"
    assert word_number(_word("vacances")) == "pl"
    assert word_number(_word("les vacances")) == "pl"
    # The schema every Lexique row and the word sheet read sends it.
    row = VocabularyWordRead(id=1, language="fr", word="vacances", normalized_word="vacances")
    assert (row.part_of_speech, row.gender, row.number) == ("noun", "f", "pl")


def test_a_final_s_or_x_is_not_a_plural() -> None:
    for text in ("bras", "prix", "temps", "pays", "fois", "voix", "corps"):
        assert word_number(_word(text)) is None, text
    # «frais» the adjective has no number; only a noun has.
    assert word_number(_word("frais")) is None
    assert word_number(_word("frais", part_of_speech="noun")) == "pl"


def test_every_lexicon_noun_in_the_list_and_no_other_is_plural() -> None:
    lemmas = json.loads(LEXICON_PATH.read_text(encoding="utf-8"))["lemmas"]
    plural = pluralia_tantum()
    nouns = [lemma for lemma, entry in lemmas.items() if entry.get("pos") == "noun"]
    assert {"gens", "vacances"} <= set(nouns)
    for lemma in nouns:
        word = _word(lemma)
        assert word_grammar(word)[0] == "noun", lemma
        assert (word_number(word) == "pl") == (lemma in plural), lemma
