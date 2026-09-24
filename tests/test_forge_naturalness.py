"""WP-S5 — La Forge's templated sentences are natural and live in the story.

* The naturalness checker (:mod:`app.services.item_semantics`) names the
  failures the 2026-09-24 review found (a carrot at the theatre, a croissant
  for 940 euros, «hier … le dimanche», «à côté de elle», «Romy et Margaux
  part», an English cue in the wrong tense, …).
* A seeded sample of every A1–A2 unit is clean, and the *source* constraints
  (lexicon annotations and slot specs) do the work: the checker, the bank's
  last line of defence, rejects almost nothing.
* ≥ 80 % of the items name a cast member, a world-bible place or a story
  object (WP-S5 «Done when»).
"""
from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

import pytest

from app.services import item_bank as ib
from app.services import item_semantics as sem

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_PER_UNIT = 40


def _a1_a2_units() -> list[str]:
    with (ROOT / "templates" / "french_core_grammar_v2.tsv").open(encoding="utf-8") as handle:
        return [row["external_id"] for row in csv.DictReader(handle, delimiter="\t") if row["cefr_level"] in {"A1", "A2"}]


def _noun(noun_id: str) -> dict:
    return next(entry for entry in ib.lexicon().pool("noun") if entry["id"] == noun_id)


def _number(value: int) -> dict:
    return next(entry for entry in ib.lexicon().pool("num") if entry["value"] == value)


def _item(sentence: str, en: str = "", bindings: tuple = (), links: tuple = ()) -> ib.BankItem:
    return ib.BankItem(
        unit="TEST", frame_id="t", sentence=sentence, target=sentence, traps=("x",), wrong_sentences=("x",),
        prefix="", suffix="", en=en, scene="", bindings=bindings, links=links,
    )


# --------------------------------------------------------------------------- #
# The checker names each kind of failure
# --------------------------------------------------------------------------- #


def test_a_thing_must_be_where_such_things_are() -> None:
    bad = _item("Il y a une carotte au théâtre.", bindings=(("N", _noun("carotte")), ("P", _noun("théâtre"))))
    good = _item("Il y a une carotte au marché.", bindings=(("N", _noun("carotte")), ("P", _noun("marché"))))
    assert [c.kind for c in sem.violations(bad)] == ["location"]
    assert sem.violations(good) == []


def test_prices_and_head_counts_fit_the_thing() -> None:
    croissant = _item("Le croissant coûte neuf cent quarante euros.",
                      bindings=(("N", _noun("croissant")), ("M", _number(940))))
    guitar = _item("La guitare coûte six cent trente euros.", bindings=(("N", _noun("guitare")), ("M", _number(630))))
    crowd = _item("Il y a cinq cent quatre-vingt-dix personnes au Mistral.",
                  bindings=(("P", _noun("mistral")), ("M", _number(590))))
    assert "price" in {c.kind for c in sem.violations(croissant)}
    assert sem.violations(guitar) == []
    assert "capacity" in {c.kind for c in sem.violations(crowd)}


@pytest.mark.parametrize(
    "sentence",
    [
        "Hier, vous avez nagé le dimanche.",
        "Aujourd'hui, nous partons demain matin.",
        "Il vient de dîner tard.",
        "Je rentre à minuit dans deux ans.",
        "Tu étudies le soir toutes les semaines.",
        "On s'est couché tard ce matin.",
        "Vous vous êtes levées tôt hier soir.",
    ],
)
def test_one_sentence_has_one_consistent_time(sentence: str) -> None:
    kinds = {clash.kind for clash in sem.sentence_violations(sentence)}
    assert kinds & {"time", "daypart"}, sentence


@pytest.mark.parametrize(
    ("sentence", "kind"),
    [
        ("Gus est à côté de elle au musée.", "elision"),
        ("J'achète quelque chose de original.", "elision"),
        ("Romy et Margaux part en vacances le quatre juin.", "pair_agreement"),
        ("Samedi dernier, il a dormi bien.", "adverb_position"),
        ("Tu veux dormir bien ?", "adverb_position"),
        ("Je voudrais préférer le métro.", "aspect"),
        ("On doit perdre les clés.", "aspect"),
        ("Il faut avoir un chat.", "aspect"),
        ("Je te rappelle : il est en train de préférer le thé.", "aspect"),
        ("Marin est plus lent que Marin.", "identity"),
        ("Nous parlions avec Margaux quand Romy est rentrée avec Romy.", "identity"),
    ],
)
def test_wrong_forms_and_odd_sentences_are_named(sentence: str, kind: str) -> None:
    assert kind in {clash.kind for clash in sem.sentence_violations(sentence)}, sentence


@pytest.mark.parametrize(
    "sentence",
    [
        "Gus est à côté d'elle au musée.",
        "Marin et Lila ne se lèvent plus à six heures.",
        "Lila et Romy se sont réveillées tard.",
        "Tu vas au marché ce week-end ? Oui, j'y vais ce week-end.",
        "Il est six heures moins dix maintenant.",
        "Ils viennent d'Angleterre.",
        "Avant, je travaillais le samedi.",
        "Nous nous sommes beaucoup amusés.",
    ],
)
def test_natural_sentences_pass(sentence: str) -> None:
    assert sem.sentence_violations(sentence) == [], sentence


@pytest.mark.parametrize(
    ("english", "kind"),
    [
        ("You go to the shop this summer.", "english_tense"),
        ("He cycles tonight.", "english_tense"),
        ("I buy too much carrots.", "english_quantity"),
        ("Romy and Margaux goes on holiday on June 4.", "english_agreement"),
    ],
)
def test_english_cue_mismatches_are_named(english: str, kind: str) -> None:
    assert kind in {clash.kind for clash in sem.sentence_violations("Phrase.", english)}


def test_english_cues_that_are_fine_pass() -> None:
    for english in (
        "You are going to the shop this summer.",
        "We go home at midnight because we have an exam tomorrow.",
        "I go to the market after work.",
        "He leaves for Portugal next Monday.",
    ):
        assert sem.sentence_violations("Phrase.", english) == [], english


def test_linked_slots_must_fit_their_head() -> None:
    lex = ib.lexicon()
    rouge = next(a for a in lex.pool("adj") if a["id"] == "rouge")
    table, stylo = _noun("table"), _noun("stylo")
    assert sem.link_clash(_noun("photo"), rouge) is not None  # «une photo rouge»: colour is for things one paints
    assert sem.link_clash(table, rouge) is None
    assert sem.link_clash(table, stylo).kind == "comparison"  # «la table est aussi jolie que le stylo»
    assert sem.link_clash(_noun("parc"), _noun("marche_canal")).kind == "containment"  # «le meilleur parc du marché du canal»
    marin = next(c for c in lex.pool("cast") if c["id"] == "marin")
    assert sem.link_clash(marin, _number(66)).kind == "cast_fact"
    tu_f = next(p for p in lex.pool("pron") if p["id"] == "tu_f")
    assert sem.link_clash(tu_f, marin).kind == "address"  # «Tu es contente, Marin»


def test_cast_keep_their_world_bible_jobs() -> None:
    lex = ib.lexicon()
    romy = next(c for c in lex.pool("cast") if c["id"] == "romy")
    jobs = {job["id"]: job for job in lex.pool("job")}
    assert sem.pair_clash(romy, jobs["job_infirmier"]).kind == "cast_fact"
    assert sem.pair_clash(romy, jobs["job_journaliste"]) is None


def test_a_cup_holds_coffee_not_wine() -> None:
    lex = ib.lexicon()
    cup = next(q for q in lex.pool("qty_drink") if q["fr"] == "une tasse")
    assert sem.pair_clash(cup, _noun("vin")).kind == "container"
    assert sem.pair_clash(cup, _noun("thé")) is None


# --------------------------------------------------------------------------- #
# A seeded sample of every A1–A2 unit is clean — at the source
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def sample() -> tuple[dict[str, list[ib.BankItem]], dict[str, Counter]]:
    bank = ib.ItemBank()
    items = {
        unit: bank.generate(unit, SAMPLE_PER_UNIT, seed=f"naturalness:{unit}", detector=ib.unit_detector(unit))
        for unit in _a1_a2_units()
    }
    return items, bank.stats


def test_every_unit_yields_a_full_clean_sample(sample) -> None:
    items, _stats = sample
    for unit, unit_items in items.items():
        assert len(unit_items) == SAMPLE_PER_UNIT, unit
        for item in unit_items:
            assert sem.violations(item) == [], (unit, item.sentence, item.en, sem.violations(item))


def test_the_source_constraints_do_the_work(sample) -> None:
    """The checker is a last line of defence: it rejects < 5 % in every unit."""

    _items, stats = sample
    for unit in _a1_a2_units():
        counts = stats[unit]
        assert counts["rendered"] >= SAMPLE_PER_UNIT
        assert counts["rejected"] / counts["rendered"] < 0.05, (unit, dict(counts))


def test_at_least_80_percent_of_items_live_in_the_story(sample) -> None:
    items, _stats = sample
    every = [item for unit_items in items.values() for item in unit_items]
    linked = sum(sem.is_story_linked(item.sentence) for item in every)
    assert linked / len(every) >= 0.80, linked / len(every)
    for unit, unit_items in items.items():
        rate = sum(sem.is_story_linked(item.sentence) for item in unit_items) / len(unit_items)
        assert rate >= 0.5, (unit, rate)


def test_story_links_name_cast_places_and_objects() -> None:
    links = sem.story_links("Hier, Marin a cherché sa bague au Mistral.")
    assert links == {"cast": ["marin"], "places": ["mistral"], "objects": ["bague"]}
    assert not sem.is_story_linked("Il est six heures.")


def test_the_learners_own_story_is_preferred() -> None:
    """Entries the chronicle names (``story``) come up more often."""

    bank = ib.ItemBank()
    plain = bank.generate("FR2_A11_ETRE", 60, seed="focus")
    focused = bank.generate("FR2_A11_ETRE", 60, seed="focus", story=["brocante"])
    count = lambda items: sum("brocante" in item.sentence for item in items)  # noqa: E731
    assert count(focused) > count(plain)
