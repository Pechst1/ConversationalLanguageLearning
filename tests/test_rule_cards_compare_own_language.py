"""R5 (check walk of 19 Nov, B1.1, English): an explanation compares with the reader's language only.

The English «Pourquoi ?» of «Pour, sans, avant de + infinitif» read «English says 'without
saying, before leaving'; German 'ohne zu sagen, bevor ich gehe'». A rule card's English text
is read by an English speaker and its German text by a German speaker (the mother tongue at
every level), so the English text never leans on German and the German text never on English.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

DATA = Path(__file__).resolve().parents[1] / "app" / "data"
FILES = sorted((DATA / "rule_cards").glob("fr2_*.json")) + [DATA / "grammar_rule_cards.json"]

#: The other language named in a text written for ``language``'s readers.
FOREIGN = {
    "en": re.compile(r"\bGerman\b|\bDeutsch", re.IGNORECASE),
    "de": re.compile(r"englisch|\bEnglish\b", re.IGNORECASE),
}

#: (file, path) → why the mention is not a comparison.
WHITELIST: dict[tuple[str, str], str] = {
    ("fr2_A1.json", "cards/FR2_A11_NEGATION/examples[0]/tr/en"): "a translation of «Je ne parle pas allemand.»",
    ("fr2_B2.json", "cards/FR2_B22_SI_MIXED/examples[1]/tr/en"): "a translation of a sentence about speaking German",
}


def _texts(node: Any, path: str = "") -> Iterator[tuple[str, str, str]]:
    if isinstance(node, dict):
        for key, value in node.items():
            here = f"{path}/{key}" if path else str(key)
            if isinstance(value, str) and key in FOREIGN:
                yield here, key, value
            else:
                yield from _texts(value, here)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _texts(value, f"{path}[{index}]")


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_a_rule_card_text_compares_with_its_readers_language_only(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    offenders = [
        f"{where} [{language}]: {text[:120]}"
        for where, language, text in _texts(data)
        if FOREIGN[language].search(text) and (path.name, where) not in WHITELIST
    ]
    assert not offenders, "\n".join(offenders)


def test_the_whitelist_names_real_texts() -> None:
    for (name, where), _reason in WHITELIST.items():
        data = json.loads((DATA / "rule_cards" / name).read_text(encoding="utf-8"))
        assert any(here == where for here, _lang, _text in _texts(data)), where


def test_the_walks_card_explains_in_english_only() -> None:
    cards = json.loads((DATA / "rule_cards" / "fr2_B1.json").read_text(encoding="utf-8"))["cards"]
    more = cards["FR2_B11_PREP_INFINITIVE"]["more"]
    assert "ohne zu sagen" not in more["en"]
    assert "sans dire, avant de partir" in more["en"]
