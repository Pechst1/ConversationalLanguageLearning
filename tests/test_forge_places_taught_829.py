"""#829 — an A1 item never needs a preposition rule the learner has not been taught.

Walk 16 Nov 2026 (fake provider, ``a1-de-fresh``, A1.1 day 2): a La Forge
review of être asked «Seid ihr diese Woche im Iran?». The answer needs
«en Iran», the country preposition of FR2_A11_PLACES (teaching order 130),
which no card had shown a learner on être (order 10). The être frames bind
their place from the ``geo`` pool, and nothing kept that pool's countries
(«en Iran», «au Canada», «aux États-Unis») out of a unit taught before the
rule their preposition belongs to.

Countries now say which rule their form needs (``"rule"`` in the lexicon), and
the bank leaves such an entry out of every unit taught before that rule — the
same gate the CEFR band already was, one step finer. «à + city» stays: être's
own rule card says «Nous sommes à Lyon.», and Paris, where the season is set,
is a story place.
"""
from __future__ import annotations

import re

from app.services.item_bank import ItemBank, default_bank, lexicon, template_units, unit_row

PLACES = "FR2_A11_PLACES"


def _order(unit: str) -> int:
    return int(unit_row(unit).get("difficulty_order") or 10_000)


def _countries() -> list[dict]:
    return [entry for entry in lexicon().pool("geo") if "city" not in entry.get("tags", [])]


def _country_phrases(sentence: str) -> list[str]:
    found = []
    for entry in _countries():
        for form in (entry["in"], entry["de"], *entry.get("x", [])):
            if re.search(rf"(?<!\w){re.escape(form)}(?!\w)", sentence, re.IGNORECASE):
                found.append(form)
    return found


def _items(bank: ItemBank, unit: str, seeds: int = 6, count: int = 60) -> list:
    items = []
    for seed in range(seeds):
        items.extend(bank.generate(unit, count, seed=f"829:{unit}:{seed}"))
    return items


def test_early_a1_no_country() -> None:
    """Today's rule and every review an A1.1 learner meets before FR2_A11_PLACES."""

    bank = default_bank()
    early = [unit for unit in template_units() if unit.startswith("FR2_A1") and _order(unit) < _order(PLACES)]
    assert "FR2_A11_ETRE" in early
    offending: list[tuple[str, str, list[str]]] = []
    for unit in early:
        for item in _items(bank, unit):
            for text in (item.sentence, *item.accepted):
                phrases = _country_phrases(text)
                if phrases:
                    offending.append((unit, text, phrases))
    assert not offending, (
        f"{len(offending)} items taught before {PLACES} need its country preposition, e.g. {offending[:5]}"
    )


def test_lexicon_names_rule() -> None:
    """The gate only works on what is marked: a geo country, a verb complement
    («voyager en Italie»), any entry whose words carry a country preposition."""

    import json
    from pathlib import Path

    raw = json.loads(Path("app/data/grammar_templates/lexicon.json").read_text(encoding="utf-8"))
    unmarked: list[str] = []

    def walk(node) -> None:
        if isinstance(node, dict):
            words = " ".join(str(node.get(key) or "") for key in ("fr", "in"))
            if _country_phrases(words) and node.get("rule") != PLACES:
                unmarked.append(words.strip())
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(raw)
    assert not unmarked, f"entries with a country preposition but no «rule»: {unmarked[:10]}"


def test_etre_in_cities() -> None:
    items = _items(default_bank(), "FR2_A11_ETRE")
    city_lines = [item.sentence for item in items if "cette semaine" in item.sentence]
    assert city_lines, "être's «… cette semaine» frames still render"
    assert all(re.search(r"\bà [A-ZÉ]", line) for line in city_lines), city_lines[:5]
    assert any("à Paris" in line for line in city_lines)


def test_places_has_countries() -> None:
    bank = default_bank()
    for unit in (PLACES, "FR2_A11_ALLER_VENIR"):
        assert _order(unit) >= _order(PLACES)
        assert any(_country_phrases(item.sentence) for item in _items(bank, unit)), unit
