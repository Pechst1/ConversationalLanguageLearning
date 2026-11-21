"""#829 — an A1 place slot binds a place of the season, never one whose preposition is untaught.

Walk 16 Nov 2026 (fake provider, ``a1-de-fresh``, A1.1 day 2): a La Forge
review of être asked «Seid ihr diese Woche im Iran?». The answer needs
«en Iran», the country preposition of FR2_A11_PLACES (teaching order 130),
which no card had shown a learner on être (order 10). Walk 18 Nov: «Sie sind
diese Woche in Mexiko», «Bist du diese Woche in Brüssel / London?». The être
and numbers frames bind their place from the ``geo`` pool — the whole atlas,
17 cities and 27 countries — and nothing in ``_bind`` kept it to the places
the season is set in. Story places only weighed more (attempt 1, #867: 81 %
of être's «… cette semaine» items still went to Munich, Montréal, Rome…).

Every ``geo`` form («à Munich», «en Iran», «au Canada») belongs to the PLACES
rule («Ville : à ; pays féminin : en …»), and the lexicon now says so
(``"rule"``). The places of the season (Paris, where it is set; Marseille,
Lila's town) are story places instead (``"story": true``). The bank leaves an
entry out of every unit taught before its rule — the gate the CEFR band
already was — so before PLACES a place slot can only bind a season place.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from app.services import item_semantics as semantics
from app.services.item_bank import ItemBank, default_bank, lexicon, template_units, unit_row

PLACES = "FR2_A11_PLACES"
#: The places of season 1 the canon sets the story in (app/data/season/s1/world.json):
#: Paris, and Marseille, Lila's town. (Berlin is Lila's secret until T5; Montréal Romy's.)
SEASON_PLACES = {"Paris", "Marseille"}


def _order(unit: str) -> int:
    return int(unit_row(unit).get("difficulty_order") or 10_000)


def _early_a1() -> list[str]:
    """Today's rule and every review an A1.1 learner meets before FR2_A11_PLACES."""

    return [unit for unit in template_units() if unit.startswith("FR2_A1") and _order(unit) < _order(PLACES)]


def _forms(entry: dict) -> list[str]:
    return [entry["in"], entry["de"], *entry.get("x", [])]


def _mentions(entry: dict, text: str) -> bool:
    if any(re.search(rf"(?<!\w){re.escape(form)}(?!\w)", text, re.IGNORECASE) for form in _forms(entry)):
        return True
    # «Le billet pour Munich» binds the bare name; case-sensitive so «vienne» is not Vienne.
    return bool(re.search(rf"(?<!\w){re.escape(entry['fr'])}(?!\w)", text))


def _foreign_places(text: str) -> list[str]:
    """The ``geo`` places in ``text`` that are not places of the season."""

    return [entry["fr"] for entry in lexicon().pool("geo") if entry["fr"] not in SEASON_PLACES and _mentions(entry, text)]


def _countries_in(text: str) -> list[str]:
    countries = [entry for entry in lexicon().pool("geo") if "city" not in entry.get("tags", [])]
    return [entry["fr"] for entry in countries if any(re.search(rf"(?<!\w){re.escape(form)}(?!\w)", text, re.IGNORECASE) for form in _forms(entry))]


def _items(bank: ItemBank, unit: str, seeds: int = 6, count: int = 60) -> list:
    items = []
    for seed in range(seeds):
        items.extend(bank.generate(unit, count, seed=f"829:{unit}:{seed}"))
    return items


def test_early_a1_season_places() -> None:
    """The done-when: no early A1 item (rule or review) places anyone outside the season."""

    bank = default_bank()
    early = _early_a1()
    assert {"FR2_A11_ETRE", "FR2_A11_NUMBERS"} <= set(early)
    places: Counter[str] = Counter()
    examples: list[tuple[str, str]] = []
    for unit in early:
        for item in _items(bank, unit):
            found = {place for text in (item.sentence, *item.accepted) for place in _foreign_places(text)}
            places.update(found)
            if found and len(examples) < 4:
                examples.append((unit, item.sentence))
    assert not places, f"A1 items before {PLACES} bind places outside the season: {dict(places.most_common())} e.g. {examples}"


def test_etre_week_paris() -> None:
    """Attempt 1's review input: être «… cette semaine» lines stay in the season's places."""

    bank = default_bank()
    lines = [item.sentence for s in range(30) for item in bank.generate("FR2_A11_ETRE", 60, seed=f"y{s}") if "cette semaine" in item.sentence]
    assert lines, "être's «… cette semaine» frames still render"
    elsewhere = Counter(place for line in lines for place in _foreign_places(line))
    assert not elsewhere, f"{sum(elsewhere.values())}/{len(lines)} être lines away from the season: {dict(elsewhere.most_common(8))}"
    assert all(re.search(r"\bà (?:Paris|Marseille)\b", line) for line in lines), [line for line in lines if "à Paris" not in line][:5]


def test_geo_names_rule() -> None:
    """The gate works on what is marked: every ``geo`` place is a season place or names
    the PLACES rule; so does any entry whose words carry a country preposition
    («voyager en Italie»)."""

    for entry in lexicon().pool("geo"):
        season = entry["fr"] in SEASON_PLACES
        assert semantics.is_story_entry(entry) == season, f"{entry['fr']}: story place should be {season}"
        assert (entry.get("rule") == PLACES) != season, f"{entry['fr']}: should name rule {PLACES}: {not season}"

    raw = json.loads(Path("app/data/grammar_templates/lexicon.json").read_text(encoding="utf-8"))
    unmarked: list[str] = []

    def walk(node) -> None:
        if isinstance(node, dict):
            words = " ".join(str(node.get(key) or "") for key in ("fr", "in"))
            if _countries_in(words) and node.get("rule") != PLACES:
                unmarked.append(words.strip())
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(raw)
    assert not unmarked, f"entries with a country preposition but no «rule»: {unmarked[:10]}"


def test_places_drills_atlas() -> None:
    """From PLACES on, the whole atlas is back: countries and cities beyond the season."""

    bank = default_bank()
    for unit in (PLACES, "FR2_A11_ALLER_VENIR"):
        assert _order(unit) >= _order(PLACES)
        items = _items(bank, unit)
        assert any(_countries_in(item.sentence) for item in items), unit
    assert any(_foreign_places(item.sentence) for item in _items(bank, PLACES)), PLACES
