"""QA-FORGE (2026-10-03) — the owner's «Vous sommes au bureau de l'ONG, Gus.»

Regression tests for the item-bank rules that came out of reading 30 items of
every A1, A2 and B1 unit: who a line may be said to (vocatives), the cast's
registers (the learner says «vous» to Gus), vocabulary above a unit's band, and
the template slips the read found.
"""
from __future__ import annotations

import re

import pytest

from app.services import item_bank as ib
from app.services import item_semantics as sem

UNITS = list(ib.template_units())
_VOC = re.compile(r",\s*(Margaux|Marin|Romy|Lila|Gus)\s*[.?!]")


@pytest.fixture(scope="module")
def sample() -> dict[str, list[ib.BankItem]]:
    bank = ib.ItemBank()
    return {unit: bank.generate(unit, 60, seed=f"qa-forge:{unit}", detector=ib.unit_detector(unit)) for unit in UNITS}


def test_the_owners_sentence_is_rejected_on_every_count():
    clashes = {clash.kind for clash in sem.address_violations("Vous êtes au bureau de l'ONG, Gus.")}
    assert clashes == {"told_to_self"}
    assert {c.kind for c in sem.address_violations("Tu es malade, Marin.")} == {"told_to_self"}
    assert {c.kind for c in sem.address_violations("Tu es au café, Gus ?")} == {"register"}
    assert {c.kind for c in sem.address_violations("Vous voulez une salade, Lila ?")} == {"register"}
    # A question to a «tu» friend, a statement about oneself, a plural imperative: fine.
    for fine in ("Tu es au café, Lila ?", "Je suis à la poste, Romy.", "Romy et Margaux, prenez-la !",
                 "J'ai rendez-vous au Mistral, Lila.", "Pourriez-vous partir avec Gus, Monsieur Marchand ?"):
        assert sem.address_violations(fine) == [], fine


def test_no_sampled_line_tells_its_addressee_about_themselves_or_breaks_a_register(sample):
    for unit, items in sample.items():
        for item in items:
            assert sem.address_violations(item.sentence) == [], (unit, item.sentence)


def test_a_vocative_never_follows_a_clause_break(sample):
    for unit, items in sample.items():
        for item in items:
            if item.frame_id.endswith("~voc"):
                body = item.sentence[: _VOC.search(item.sentence).start()] if _VOC.search(item.sentence) else item.sentence
                assert "," not in body.split("?")[0], (unit, item.sentence)
                assert not re.search(r"\b(?:parce que|parce qu'|donc|comme|car|mais)\b", body), (unit, item.sentence)


def test_tu_and_vous_are_asked_not_told_in_the_etre_unit(sample):
    for item in sample["FR2_A11_ETRE"]:
        if re.match(r"(?:Tu|Vous)\b", item.sentence):
            assert item.sentence.endswith("?"), item.sentence
    assert any(item.sentence.endswith("?") for item in sample["FR2_A11_ETRE"])


def test_a_word_above_the_units_band_stays_out(sample):
    for unit in UNITS:
        if ib._unit_level(unit) in {"A1", "A2"}:
            assert not any("ONG" in item.sentence for item in sample[unit]), unit


def test_gus_is_never_asked_with_tu(sample):
    """The learner says «vous» to Gus (season.json): never «Tu …, Gus ?», «Gus, prends-la !»."""

    for unit, items in sample.items():
        for item in items:
            if re.search(r", Gus\s*\?", item.sentence):
                assert not re.match(r"(?:Est-ce que )?(?:tu|t')", item.sentence, re.IGNORECASE), (unit, item.sentence)
            assert not re.search(r"(?:^|[.?!]\s)Gus, \w+-(?:le|la|les)\b", item.sentence), (unit, item.sentence)


def test_the_template_slips_the_read_found_are_gone(sample):
    every = [item.sentence for items in sample.values() for item in items]
    # «Si elles étaient libre» — the adjective agrees, so plural subjects are not offered.
    assert not any(re.search(r"\b(?:étions|étiez|étaient) libre\b", sentence) for sentence in every)
    # «Lundi prochain, nous aurons deux frères.» / «toute la guitare» / «Ce matin, tu as dîné»
    assert not any("aurons deux frères" in sentence or "aurez deux frères" in sentence for sentence in every)
    assert not any(re.search(r"\btoute la (?:guitare|photo)\b", sentence) for sentence in every)
    assert not any(re.search(r"Ce matin, \w+ \w+ dîné", sentence) for sentence in every)
    # «Je te rappelle : tu es en train de…» / «Désolé, tu viens de…»: the speaker is busy, not the listener.
    assert not any(re.search(r"Je te rappelle : (?:tu|vous|il|elle|ils|elles) ", sentence) for sentence in every)
    assert not any(re.search(r"Désolée?, (?:tu|vous|il|elle|ils|elles) ", sentence) for sentence in every)
    # «Rien n'est impossible à la gare ce week-end.»
    assert not any(re.search(r"Rien n'est \w+ (?:à|au|aux) ", sentence) for sentence in every)
