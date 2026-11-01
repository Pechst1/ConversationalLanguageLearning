"""#129: an authored line that sets a time must say what happens then.

Day 2 «La lettre» had Camille close the turn with «Jeudi prochain, dix-huit
heures.» — a day and a clock time, and nothing else. The bible note said she
"sets the visit", but the note is for writers; the learner only reads the line,
and the letter's own deadline (le 8 janvier) made Thursday read as anything.

Nothing in the season checks looked at what a line *means*, so a bare
appointment could sit in any tentpole, bridge or level variant. This test reads
every spoken line of every season (a ``say`` under a ``who``: the A2/B1 text
and every level variant from the ``levels*.json`` overlays) and refuses one that
is only a date or a time once the time words are taken away. Labels and props
(«14 mars. 23 h.» on a Polaroid) are not someone setting a meeting.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from app.services.season.levels import iter_says, level_key, read_levels

SEASON_ROOT = Path(__file__).resolve().parents[1] / "app" / "data" / "season"
LEVEL_FIELDS = ("a2", "b1", "a1", "b2", "c1")

# Words that only place a moment in time (or stress its precision). A line made
# of nothing else names a time and no event.
TIME_WORDS = {
    "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche",
    "prochain", "prochaine", "dernier", "dernière", "demain", "aujourd'hui", "ce", "cette",
    "soir", "matin", "midi", "minuit", "après-midi", "semaine", "heure", "heures", "h",
    "et", "demie", "quart", "le", "la", "à", "vers", "précises", "précise", "pile",
    "sans", "faute", "janvier", "février", "mars", "avril", "mai", "juin", "juillet",
    "août", "septembre", "octobre", "novembre", "décembre",
    "un", "une", "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf", "dix",
    "onze", "douze", "treize", "quatorze", "quinze", "seize", "vingt", "trente",
    "dix-sept", "dix-huit", "dix-neuf",
}
DAY_OR_CLOCK = re.compile(
    r"\b(lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche|heures?|\d{1,2}\s*h)\b",
    re.IGNORECASE,
)


def is_bare_appointment(text: str) -> bool:
    """True when the line names a day or a clock time and nothing else."""

    if not DAY_OR_CLOCK.search(text):
        return False
    words = re.findall(r"[a-zàâçéèêëîïôûùüÿœ'\-]+|\d+", text.lower())
    rest = [word for word in words if word not in TIME_WORDS and not word.isdigit()]
    return not rest


def _spoken_says(node):
    """Every ``say`` a character speaks (depth first)."""

    if isinstance(node, dict):
        if node.get("who") and isinstance(node.get("say"), dict):
            yield node["say"]
        for value in node.values():
            yield from _spoken_says(value)
    elif isinstance(node, list):
        for value in node:
            yield from _spoken_says(value)


def _authored_lines() -> list[tuple[str, str]]:
    lines: list[tuple[str, str]] = []
    for folder in sorted(path for path in SEASON_ROOT.iterdir() if path.is_dir()):
        spoken_keys: set[str] = set()
        for path in sorted(folder.glob("*.json")):
            if path.name.startswith("levels") or path.name == "lexicon.json":
                continue
            raw = json.loads(path.read_text(encoding="utf-8"))
            for say in _spoken_says(raw):
                if not isinstance(say.get("a2"), str):
                    continue
                spoken_keys.add(level_key(say["a2"], say.get("b1")))
                for field in ("a2", "b1"):
                    if isinstance(say.get(field), str):
                        lines.append((f"{folder.name}/{path.name} {field}", say[field]))
        for key, variants in read_levels(folder).get("lines", {}).items():
            if key not in spoken_keys:
                continue
            for field in LEVEL_FIELDS:
                if isinstance(variants.get(field), str):
                    lines.append((f"{folder.name}/levels {key} {field}", variants[field]))
    return lines


def test_the_detector_reads_the_walk_line_as_bare():
    # The exact text of the walk (#129) and its old level variants.
    assert is_bare_appointment("Jeudi prochain, dix-huit heures.")
    assert is_bare_appointment("Jeudi prochain, dix-huit heures précises.")
    assert is_bare_appointment("Jeudi prochain, dix-huit heures. Sans faute.")
    # A line that says what happens then is not bare.
    assert not is_bare_appointment("Jeudi prochain, dix-huit heures. Je viens visiter l'appartement.")
    assert not is_bare_appointment("Jeudi. Gus a besoin de toi. Il ne dit pas pourquoi.")
    # A line with no day and no clock time is not an appointment at all.
    assert not is_bare_appointment("Pas ce soir.")


def test_no_authored_season_line_sets_a_time_without_saying_what_happens():
    lines = _authored_lines()
    assert len(lines) > 1000, "the season content was not found"
    bare = [f"{where}: «{text}»" for where, text in lines if is_bare_appointment(text)]
    assert not bare, "a line names a day/time and no event:\n" + "\n".join(bare)


def test_day_two_camille_says_thursday_is_the_visit():
    raw = json.loads((SEASON_ROOT / "s1" / "t1.json").read_text(encoding="utf-8"))
    texts = [say["a2"] for say in iter_says(raw) if say["a2"].startswith("Jeudi prochain, dix-huit heures")]
    assert texts == ["Jeudi prochain, dix-huit heures. Je viens visiter l'appartement."]
