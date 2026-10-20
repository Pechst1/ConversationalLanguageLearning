"""#236 / #146 (review of attempt 1, #244): the conjugation table must not leak its auxiliary.

``word_match`` takes the forms of an irregular verb from the conjugation table.
The table's compound tenses hold the auxiliary («j'ai vendu»), so every verb
"was used" by «J'ai faim», and «être» was "used" by the word «et».
"""
from __future__ import annotations

import pytest

from app.services.word_match import fold, target_occurs_in

_AVOIR_TEXTS = [
    "J'ai faim",
    "Il a froid",
    "Nous avons un chat",
    "Ils ont peur",
    "Vous avez raison",
    "Tu as soif",
]


@pytest.mark.parametrize("text", _AVOIR_TEXTS)
def test_the_auxiliary_of_the_passe_compose_does_not_stand_for_the_verb(text):
    assert target_occurs_in("vendre", text) is False


@pytest.mark.parametrize("text", ["Elle a vendu un tableau", "je vends", "Nous avons vendu la table"])
def test_the_participle_and_the_conjugated_forms_still_count(text):
    assert target_occurs_in("vendre", text) is True


def test_etre_is_not_the_word_et():
    assert target_occurs_in("être", "Pierre et Marie mangent.") is False
    assert target_occurs_in("être", "Je suis fatigué") is True
    assert target_occurs_in("avoir", "Il a froid") is True


@pytest.mark.parametrize("text", ["J'ai faim", "Il a froid"])
def test_the_courrier_counter_ignores_the_auxiliary(text):
    from app.services.missions import MissionCorrectionService, _normalize_phrase

    item = {"word": "vendre", "normalized_word": "vendre"}
    assert MissionCorrectionService._contains_vocabulary_form(None, _normalize_phrase(text), item) is False


def test_no_verb_of_the_core_lexicon_is_used_by_a_bare_auxiliary():
    """Sweep: a, ai, as, ont, avons, avez, et belong to avoir / être only."""
    from app.services.core_lexicon import _entries

    leaks = []
    checked = 0
    for lemma, _entry in _entries():
        folded = fold(lemma)
        if folded in {"avoir", "etre"} or not folded.endswith(("er", "ir", "re")) or " " in folded:
            continue
        checked += 1
        for word in ("a", "ai", "as", "ont", "avons", "avez", "et"):
            if target_occurs_in(lemma, word):
                leaks.append((lemma, word))
    assert checked > 50, "the sweep must cover the verb list"
    assert leaks == []
