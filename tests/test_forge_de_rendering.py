"""FORGE-DE (2026-10-03) — La Forge's items carry a German meaning.

The learner base is mostly German-speaking. Every frame of the item bank has a
German rendering (``de``) built by rule from ``lexicon_de.json``; these tests are
the quality gate: 30 items per unit of every A1/A2/B1 file render German that
passes the checker, the checker itself catches the obvious errors, and the
correction note quotes the rule of the item's own unit.
"""
from __future__ import annotations

import pytest

from app.services import item_bank as ib
from app.services.item_bank_de import german_violations

UNITS = list(ib.template_units())


@pytest.fixture(scope="module")
def sample() -> dict[str, list[ib.BankItem]]:
    bank = ib.ItemBank()
    return {unit: bank.generate(unit, 30, seed=f"forge-de:{unit}", detector=ib.unit_detector(unit)) for unit in UNITS}


def test_every_frame_has_a_german_rendering():
    missing = [
        (unit, frame.frame_id)
        for unit in UNITS
        for frame in ib.default_bank().frames(unit)
        if not frame.de
    ]
    assert missing == []


def test_thirty_items_per_unit_render_clean_german(sample):
    total = sum(len(items) for items in sample.values())
    rendered = [item for items in sample.values() for item in items if item.de]
    assert len(rendered) >= 0.98 * total
    for unit, items in sample.items():
        assert sum(1 for item in items if item.de) >= len(items) - 2, unit
    problems = [(item.unit, item.sentence, item.de, ib.german_problems(item)) for item in rendered if ib.german_problems(item)]
    assert problems == []


def test_the_german_follows_the_french_meaning(sample):
    """Spot checks of the meaning-carrying forms (the gloss units)."""

    pairs = {(item.unit, item.frame_id.split("~")[0]): item for items in sample.values() for item in items}
    for (unit, frame), item in pairs.items():
        if unit == "FR2_A21_TIME_PREPOSITIONS" and frame == "depuis":
            assert " seit " in f" {item.de} "
        if unit == "FR2_A21_TIME_PREPOSITIONS" and frame == "il-y-a":
            assert " vor " in f" {item.de} "
        if unit == "FR2_A21_TIME_PREPOSITIONS" and frame == "pendant":
            assert " lang " in f" {item.de} "
        if unit == "FR2_A12_CONNECTORS" and frame.startswith("because"):
            assert ", weil " in item.de and item.de.rstrip(".").split()[-1] in {"bin", "bist", "ist", "sind", "seid", "mag", "magst", "mögen", "mögt"}
        if unit in {"FR2_A11_NUMBERS", "FR2_A12_NUMBERS_BIG"}:
            digits = next(entry for slot, entry in item.bindings if slot == "M")["digits"]
            assert digits in item.de


def test_the_checker_catches_obvious_german_errors():
    tisch = {"deu": "Tisch", "dg": "m", "dpl": "Tische"}
    lampe = {"deu": "Lampe", "dg": "f", "dpl": "Lampen"}
    gehen = {"inf": "gehen", "prt": "ging", "pp": "gegangen", "aux": "sein"}
    essen = {"inf": "essen", "pres2": "isst", "pres3": "isst", "prt": "aß", "pp": "gegessen"}
    verbs = [gehen, essen, {"inf": "bleiben", "prt": "blieb", "pp": "geblieben", "aux": "sein"}, {"inf": "wohnen"}]
    assert german_violations("Ich habe einen Tisch.", nouns=[tisch], verbs=verbs) == []
    assert german_violations("Ich habe eine Tisch.", nouns=[tisch], verbs=verbs)
    assert german_violations("Ich sehe den Lampe.", nouns=[lampe], verbs=verbs)
    assert german_violations("Ich habe einen großer Tisch.", nouns=[tisch], verbs=verbs)
    assert german_violations("Ich bleibe zu Hause, weil ich bin müde.", verbs=verbs)
    assert german_violations("Gestern ich bin gegangen.", verbs=verbs)
    assert german_violations("Ich habe nach Hause gegangen.", verbs=verbs)
    assert german_violations("Ich bin im Mistral gegessen.", verbs=verbs)
    assert german_violations("Ich geht zum Markt.", verbs=verbs)
    assert german_violations("I am at the station.", verbs=verbs)
    assert german_violations("Ich {S} gehe.", verbs=verbs)
    # …and leaves the right ones alone
    for fine in ("Da ich müde bin, bleibe ich zu Hause.", "Wo wohnst du, Lila?", "Als Kind ging ich zum Markt.",
                 "Ich bin gestern nach Hause gegangen.", "Wir haben im Mistral gegessen."):
        assert german_violations(fine, verbs=verbs) == [], fine


def test_the_clause_builder_orders_german_words():
    lex = ib.lexicon()
    filters = ib.Filters(lex)
    je = next(entry for entry in lex.pool("pron") if entry["id"] == "je_m")
    lila = next(entry for entry in lex.pool("cast") if entry["id"] == "lila")
    faire = lex.verbs["faire"]
    courses = next(comp for comp in faire["comps"] if comp["fr"] == "les courses")
    lever = lex.verbs["se_lever"]
    tot = next(comp for comp in lever["comps"] if comp["fr"] == "tôt")
    assert filters.g_cl(je, faire, courses) == "ich kaufe ein"
    assert filters.g_cl(je, faire, courses, t="perfekt") == "ich habe eingekauft"
    assert filters.g_cl(je, faire, courses, o="sub") == "ich einkaufe"
    assert filters.g_cl(lila, lever, tot, t="perfekt", o="inv") == "ist Lila früh aufgestanden"
    assert filters.g_cl(je, lever, tot, t="konj") == "ich würde früh aufstehen"
    reposer = lex.verbs["se_reposer"]
    assert filters.g_cl(lila, reposer, None, o="sub") == "Lila sich ausruht"
    acheter = lex.verbs["acheter"]
    pain = next(comp for comp in acheter["comps"] if comp["fr"] == "du pain")
    assert filters.g_cl(je, acheter, pain, neg="nicht") == "ich kaufe kein Brot"


def test_a_correction_quotes_the_rule_of_the_items_own_unit(db_session):
    """QA-FORGE saw the -er rule on «veux»: FR_A1_VERB_001 maps to seven units."""

    from app.services.atelier import AtelierCorrectionService

    item = ib.default_bank().generate("FR2_A12_MODALS", 1, seed="forge-de-rule")[0]
    payload = ib.fill_item(item) or ib.transform_item(item)
    assert payload["bank_unit"] == "FR2_A12_MODALS"
    service = AtelierCorrectionService(db_session)
    for language in ("de", "en", "fr"):
        service.explanation_language = language
        expected = ib.unit_row("FR2_A12_MODALS")["syllabus"]["rule_short"][language]
        assert service._why_for(None, payload) == expected
        assert "-er" not in service._why_for(None, payload)
    # an item stored before the key was added is recognised by its id
    legacy = {key: value for key, value in payload.items() if key != "bank_unit"}
    assert ib.item_unit(legacy) == "FR2_A12_MODALS"
