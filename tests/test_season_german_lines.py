"""#598: the German under an authored French line is checked, not just written.

The «Avant le 8 janvier.» line shipped as «Bis vor dem 8. Januar.» in one place while
the same French sentence read «Vor dem 8. Januar.» in two others: nothing looked for
stacked prepositions, and nothing compared the renditions of one French sentence.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

SEASON_DIR = Path(__file__).resolve().parents[1] / "app" / "data" / "season" / "s1"

# Two prepositions piled up the way French «avant» invites: «bis vor dem», «bis nach der».
_STACKED = re.compile(r"\bbis (?:vor|nach|zu|in|auf|an|bei|mit|von) (?:dem|der|den|des|einem|einer)\b", re.I)


def _pairs(node, found):
    """Collect (french, german) from the shapes the season files use."""
    if isinstance(node, dict):
        native = node.get("native")
        if isinstance(node.get("a2"), str) and isinstance(native, dict) and isinstance(native.get("de"), str):
            found.append((node["a2"], native["de"]))
        for level in ("a1", "b2", "c1"):
            alt = node.get(f"{level}_native")
            if isinstance(node.get(level), str) and isinstance(alt, dict) and isinstance(alt.get("de"), str):
                found.append((node[level], alt["de"]))
        for value in node.values():
            _pairs(value, found)
    elif isinstance(node, list):
        for value in node:
            _pairs(value, found)


def _all_pairs():
    found: list[tuple[str, str]] = []
    for path in sorted(SEASON_DIR.glob("*.json")):
        _pairs(json.loads(path.read_text(encoding="utf-8")), found)
    return found


def test_598_the_scan_finds_the_authored_lines() -> None:
    assert len(_all_pairs()) > 100


def test_598_no_authored_german_line_stacks_prepositions() -> None:
    bad = [de for _, de in _all_pairs() if _STACKED.search(de)]
    assert not bad, f"not German: {bad}"


def test_598_the_date_line_has_one_german_rendition() -> None:
    dated = [(fr, de) for fr, de in _all_pairs() if fr.endswith("Avant le 8 janvier.")]
    assert len(dated) >= 3, "the date line is authored in several places"
    for fr, de in dated:
        assert de.endswith("Vor dem 8. Januar."), (fr, de)
