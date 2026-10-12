"""WP-164 — what a learner sees twice: the repetition report.

Run on demand, never part of the test run. It reads two kinds of life:

* **walk lives** — the experience walk (``tests/test_experience_walk.py``) on the
  fake provider. ``--walk`` plays them (``LIFE_DAYS`` shortens a life) and reads the
  ``life-*.json`` records; ``--lives-dir`` reads records a walk already wrote;
* **paid evidence** — the owner's live reads under
  ``docs/implementation/atelier-v2/evidence/`` (WP-136, WP-149, …): the ``*.md``
  transcripts the season report writes, one per band. These days were written by the
  real model.

Per learner it counts the share of scenes per place (and how many showed a borrowed
plate), the longest run of days in one room, repeated (character, place) pairs,
repeated scene openings (the first narration sentence, normalised), repeated
complications and premises, and text seen twice. Across learners it measures the
share of day-N text two lives have in common, tentpole days and generated days apart
(tentpoles are the same on purpose; generated days should not be).

    PY=venv/bin/python
    $PY scripts/variety_report.py --walk --days 15                 # 3 lives × 15 days, ~1-2 min
    $PY scripts/variety_report.py --lives-dir <dir>                # re-read a walk's records
    $PY scripts/variety_report.py --evidence docs/implementation/atelier-v2/evidence/wp149-confirmation
    $PY scripts/variety_report.py --walk --json out.json --markdown out.md

**The walk lives use the fake provider.** Its director cycles seven places and opens
every generated page on «Il pleut sur le canal.»: what the walk measures there is
what the brief offers and the guards allow, not what a model writes. The evidence
records are the only real generated days.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unicodedata
from collections import Counter
from collections.abc import Iterable
from itertools import combinations
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
#: Three walk lives: two at the same band (day-N sameness across learners is only
#: visible between learners who read the same band's wording) and one B1.
DEFAULT_LIVES = ("a1-de-fresh-average", "a1-de-fresh-strong", "b1-en-struggling")
DEFAULT_DAYS = 15
#: A sentence shorter than this many words («Non.», «Un silence.») is not counted as
#: text seen twice: the same «Merci.» on two days is language, not repetition.
MIN_SENTENCE_WORDS = 4
MISTRAL = "le_mistral"
#: A life of fewer scenes than this (a one-day top-up read) is left out of the tables.
MIN_TABLE_SCENES = 3

# ---------------------------------------------------------------------------
# Normalising text
# ---------------------------------------------------------------------------

_QUOTES = str.maketrans(
    {"’": "'", "‘": "'", "`": "'", "«": " ", "»": " ", "“": " ", "”": " ", '"': " "}
)
_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")
_NOT_WORD = re.compile(r"[^\w' ]+")


def normalise(text: Any) -> str:
    """Casefolded, quotes folded, punctuation dropped, whitespace collapsed; accents kept."""

    value = unicodedata.normalize("NFC", str(text or "")).translate(_QUOTES).casefold()
    value = _NOT_WORD.sub(" ", value)
    return " ".join(value.split())


def sentences(text: Any) -> list[str]:
    """The sentences of a text, each normalised (empty ones dropped)."""

    parts = _SENTENCE_END.split(str(text or "").replace("\n", " ").strip())
    return [norm for norm in (normalise(part) for part in parts) if norm]


def first_sentence(text: Any) -> str:
    found = sentences(text)
    return found[0] if found else ""


# ---------------------------------------------------------------------------
# Metrics over one life (a list of day dicts)
#
# A day: {"day": int, "kind": "tentpole" | "generated" | "lost", "key": "g1.2",
#         "place": str | None, "character": str | None, "opening": str,
#         "premise": str, "premise_id": str | None, "complication": str,
#         "text": [str, ...]}
# ---------------------------------------------------------------------------


def _scenes(days: Iterable[dict]) -> list[dict]:
    return [day for day in days if day.get("kind") in ("tentpole", "generated")]


def place_shares(days: Iterable[dict]) -> dict[str, float]:
    places = [day.get("place") or "?" for day in _scenes(days)]
    if not places:
        return {}
    counts = Counter(places)
    return {place: round(count / len(places), 3) for place, count in counts.most_common()}


def longest_room_run(days: Iterable[dict]) -> tuple[str | None, int]:
    """The longest run of consecutive scene days in one place: ``(place, days)``."""

    best: tuple[str | None, int] = (None, 0)
    current, length = None, 0
    for day in _scenes(days):
        place = day.get("place")
        if place and place == current:
            length += 1
        else:
            current, length = place, (1 if place else 0)
        if length > best[1]:
            best = (current, length)
    return best


def repeated_pairs(days: Iterable[dict]) -> dict[str, int]:
    """(character, place) pairs met on more than one day, with how often."""

    counts = Counter(
        f"{day.get('character')}@{day.get('place')}"
        for day in _scenes(days)
        if day.get("character") and day.get("place")
    )
    return {pair: count for pair, count in counts.most_common() if count > 1}


def repeated_values(values: Iterable[Any]) -> dict[str, int]:
    """Normalised non-empty values seen more than once, with how often."""

    counts = Counter(norm for norm in (normalise(value) for value in values) if norm)
    return {value: count for value, count in counts.most_common() if count > 1}


def text_seen_twice(
    days: Iterable[dict], *, min_words: int = MIN_SENTENCE_WORDS
) -> dict[str, list[int]]:
    """Sentences (``min_words`` or longer) the learner read on two or more days."""

    seen: dict[str, list[int]] = {}
    for day in _scenes(days):
        for sentence in {s for text in day.get("text") or [] for s in sentences(text)}:
            if len(sentence.split()) >= min_words:
                seen.setdefault(sentence, []).append(int(day.get("day") or 0))
    return {sentence: sorted(found) for sentence, found in seen.items() if len(set(found)) > 1}


def borrowed_plate_scenes(days: Iterable[dict], own: dict[str, bool]) -> int:
    """Scenes whose place shows another place's plate (``world.py``'s ``own: False``)."""

    return sum(1 for day in _scenes(days) if day.get("place") in own and not own[day["place"]])


def mistral_windows(days: Iterable[dict], *, window: int = 5, cap: int = 2) -> dict[str, Any]:
    """WP-166's place spread: in how many 5-scene windows the Mistral took more than 2."""

    places = [day.get("place") for day in _scenes(days)]
    spans = [places[i : i + window] for i in range(0, max(0, len(places) - window + 1))]
    over = sum(1 for span in spans if span.count(MISTRAL) > cap)
    return {"windows": len(spans), "over_cap": over}


def learner_report(days: list[dict], *, own: dict[str, bool] | None = None) -> dict[str, Any]:
    scenes = _scenes(days)
    generated = [day for day in scenes if day.get("kind") == "generated"]
    room, run = longest_room_run(days)
    openings = repeated_values(day.get("opening") for day in scenes)
    gen_openings = repeated_values(day.get("opening") for day in generated)
    seen_twice = text_seen_twice(days)
    return {
        "days": len(days),
        "scenes": len(scenes),
        "generated": len(generated),
        "lost": sum(1 for day in days if day.get("kind") == "lost"),
        "place_shares": place_shares(days),
        "distinct_places": len({day.get("place") for day in scenes if day.get("place")}),
        "mistral_share": place_shares(days).get(MISTRAL, 0.0),
        "generated_mistral_share": place_shares(generated).get(MISTRAL, 0.0),
        "generated_distinct_places": len(
            {day.get("place") for day in generated if day.get("place")}
        ),
        "mistral_windows": mistral_windows(days),
        "borrowed_plate_scenes": borrowed_plate_scenes(days, own or {}),
        "longest_room_run": {"place": room, "days": run},
        "repeated_pairs": repeated_pairs(days),
        "repeated_openings": openings,
        "repeated_generated_openings": gen_openings,
        "generated_openings_distinct": len(
            {normalise(day.get("opening")) for day in generated if day.get("opening")}
        ),
        "repeated_premises": repeated_values(
            day.get("premise_id") or day.get("premise") for day in generated
        ),
        "repeated_complications": repeated_values(day.get("complication") for day in generated),
        "text_seen_twice": len(seen_twice),
        "text_seen_twice_examples": sorted(seen_twice, key=lambda s: (-len(seen_twice[s]), s))[:5],
    }


# ---------------------------------------------------------------------------
# Across learners
# ---------------------------------------------------------------------------


def _day_text(day: dict) -> set[str]:
    return {
        s
        for text in day.get("text") or []
        for s in sentences(text)
        if len(s.split()) >= MIN_SENTENCE_WORDS
    }


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)


def _band(days: list[dict]) -> str:
    return next((str(day.get("band")) for day in days if day.get("band")), "")


def cross_learner_overlap(
    lives: dict[str, list[dict]], *, same_band: bool = False
) -> dict[str, Any]:
    """The share of day-N text two lives have in common (Jaccard of their sentence
    sets), averaged over every pair of lives, for tentpole and generated days apart.
    ``same_band`` keeps only pairs of learners at the same band (the season's pages
    are worded per band, so two bands never share a tentpole's sentences)."""

    by_kind: dict[str, list[float]] = {"tentpole": [], "generated": []}
    per_day: dict[int, float] = {}
    for one, two in combinations(sorted(lives), 2):
        if same_band and _band(lives[one]) != _band(lives[two]):
            continue
        first = {int(day.get("day") or 0): day for day in lives[one]}
        second = {int(day.get("day") or 0): day for day in lives[two]}
        for number in sorted(set(first) & set(second)):
            a, b = first[number], second[number]
            if a.get("kind") not in by_kind or a.get("kind") != b.get("kind"):
                continue
            share = jaccard(_day_text(a), _day_text(b))
            by_kind[a["kind"]].append(share)
            per_day.setdefault(number, 0.0)
            per_day[number] = max(per_day[number], share)
    return {
        kind: {
            "pairs": len(values),
            "mean": round(sum(values) / len(values), 3) if values else None,
        }
        for kind, values in by_kind.items()
    } | {"max_per_day": {str(day): round(value, 3) for day, value in sorted(per_day.items())}}


def identical_openings_across(
    lives: dict[str, list[dict]], *, kind: str, same_band: bool = False, field: str = "opening"
) -> float | None:
    """The share of pairs of lives (of one band, with ``same_band``) that opened day N
    on the same sentence — or, with ``field="premise_id"``, staged the same season
    premise — over every day number both lives played as ``kind``."""

    same = pairs = 0
    for one, two in combinations(sorted(lives), 2):
        if same_band and _band(lives[one]) != _band(lives[two]):
            continue
        first = {
            int(d["day"]): normalise(d.get(field))
            for d in lives[one]
            if d.get("kind") == kind and d.get(field)
        }
        second = {
            int(d["day"]): normalise(d.get(field))
            for d in lives[two]
            if d.get("kind") == kind and d.get(field)
        }
        for number in set(first) & set(second):
            pairs += 1
            same += first[number] == second[number]
    return round(same / pairs, 3) if pairs else None


def report(lives: dict[str, list[dict]], *, own: dict[str, bool] | None = None) -> dict[str, Any]:
    first_days = {
        name: [day for day in days if day.get("day") == 1] for name, days in lives.items()
    }
    return {
        "learners": {name: learner_report(days, own=own) for name, days in sorted(lives.items())},
        "across": {
            **cross_learner_overlap(lives),
            "same_band": cross_learner_overlap(lives, same_band=True),
            "same_first_day_opening": identical_openings_across(
                first_days, kind="tentpole", same_band=True
            ),
            "same_generated_opening_on_day_n": identical_openings_across(
                lives, kind="generated", same_band=True
            ),
            "same_premise_on_day_n": identical_openings_across(
                lives, kind="generated", field="premise_id"
            ),
        },
    }


# ---------------------------------------------------------------------------
# Reading walk lives
# ---------------------------------------------------------------------------


def days_from_life(record: dict[str, Any]) -> list[dict]:
    """A walk life (``EXPERIENCE_OUT``'s ``life-*.json``) as report days."""

    out = []
    for today in record.get("days") or []:
        scene = today.get("scene") or {}
        key = str((today.get("season") or {}).get("last") or "")
        journey = today.get("journey") or {}
        if not scene:
            kind = "lost"
        elif scene.get("kind") == "tentpole" or key.startswith("t"):
            kind = "tentpole"
        else:
            kind = "generated"
        page_text = [
            text
            for event in journey.get("events") or []
            for panel in event.get("page") or []
            for text in [
                panel.get("narration_fr"),
                *[line.get("text_fr") for line in panel.get("dialogue") or []],
            ]
            if text
        ]
        out.append(
            {
                "day": int(today.get("day") or 0),
                "kind": kind,
                "key": key,
                "band": str(record.get("true_level") or "")[:2].upper(),
                "place": scene.get("location_id"),
                "character": scene.get("character_id"),
                "opening": first_sentence(scene.get("opening_fr") or scene.get("premise_fr")),
                "premise": scene.get("premise_fr") or "",
                "premise_id": scene.get("premise_id"),
                "complication": scene.get("complication") or "",
                "text": list(scene.get("text_fr") or []) or page_text,
            }
        )
    return out


def read_lives_dir(folder: Path) -> dict[str, list[dict]]:
    lives = {}
    for path in sorted(folder.glob("life-*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        lives[path.stem.removeprefix("life-")] = days_from_life(record)
    return lives


def play_walk(lives: Iterable[str], days: int, out: Path) -> float:
    """Play the walk's lives on the fake provider; the records land in ``out``."""

    selector = " or ".join(lives)
    env = {**os.environ, "WALK": "1", "LIFE_DAYS": str(days), "EXPERIENCE_OUT": str(out)}
    command = [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_experience_walk.py",
        "-m",
        "walk",
        "-k",
        selector,
        "-p",
        "no:randomly",
        "-q",
        "--no-header",
        "-p",
        "no:cacheprovider",
    ]
    started = time.monotonic()
    # The walk's own checks may fail (a known flake, a check this package is not
    # about): the records are written before the assertion, and the report reads them.
    subprocess.run(command, cwd=ROOT, env=env, check=False)  # noqa: S603 - our own pytest, fixed argv
    return time.monotonic() - started


# ---------------------------------------------------------------------------
# Reading paid evidence (the season report's markdown)
# ---------------------------------------------------------------------------

_DAY_HEAD = re.compile(r"^## Jour (\d+) — (.*)$")
_TENTPOLE = re.compile(r"T(\d+) · .* · jour ([AB])", re.IGNORECASE)
_GENERATED = re.compile(r"(g\d+\.\d+) \(jour généré\)")
#: A lost day the season served by re-reading a tentpole page (WP-124b).
_REREAD = re.compile(r"relecture de «t(\d+)\.([ab])»", re.IGNORECASE)
_QUOTED = re.compile(r"«(.*?)»")
_CAPTION = re.compile(r"^> \*(.*)\*$")
_PANEL = re.compile(r"^\*\*(P\d+|[a-z]\.[\w.]+)\*\*.*?— \*(.*)\*$")
_TURNS_TO = re.compile(r"^\*\*(.+?)\*\* \(se tourne vers toi\)")
_CHECKLIST = re.compile(r"^\*Checklist du réalisateur : ([^ ·]+)")

#: Where a generated page is, read from its first panel and premise (the season
#: report does not print ``location_id``): the earliest of these words wins. A
#: heuristic, marked as such in every table it feeds.
PLACE_WORDS: dict[str, tuple[str, ...]] = {
    "boulangerie": ("boulangerie", "bakery", "diallo"),
    "marche_canal": ("marché", "market"),
    "toit": ("toit", "roof", "skylight"),
    "stairwell": ("escalier", "stairs", "stairwell", "landing", "palier"),
    "odile_flat": (
        "appartement d'odile",
        "odile's flat",
        "odile's kitchen",
        "chez odile",
        "upstairs flat",
    ),
    "user_apartment": ("studio", "radiateur", "radiator", "sofa", "blanket"),
    "notaire": ("notaire", "notary", "vasseur"),
    "mairie": ("mairie", "town hall"),
    "marchand_office": ("gérance", "marchand's office"),
    "gare_de_lest": ("gare", "station", "train"),
    "metro_platform": ("métro", "metro"),
    "ecole": ("école", "classroom", "school", "classe"),
    "ngo_office": ("ong", "ngo"),
    "marin_lila_flat": ("marin and lila's", "chez marin"),
    "gus_loft": ("château", "gus's loft", "loft"),
    "newsroom": ("rédaction", "newsroom"),
    "buttes_chaumont": ("buttes",),
    "brocante": ("brocante", "flea market"),
    "rue_de_lancry": ("lancry",),
    "mistral_back_room": ("arrière-salle", "back room"),
    MISTRAL: (
        "mistral",
        "zinc",
        "café",
        "cafe",
        "booth",
        "comptoir",
        "counter",
        "banquette",
        "bar",
    ),
    "quai_de_valmy": ("quai", "canal"),
}


def infer_place(text: str) -> str | None:
    folded = str(text or "").casefold()
    best: tuple[int, str] | None = None
    for place, words in PLACE_WORDS.items():
        for word in words:
            match = re.search(rf"(?<!\w){re.escape(word)}(?!\w)", folded)
            if match and (best is None or match.start() < best[0]):
                best = (match.start(), place)
    return best[1] if best else None


def _tentpole_place(number: int, day: str) -> str | None:
    path = ROOT / "app" / "data" / "season" / "s1" / f"t{number}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    row = next(
        (row for row in data.get("days") or [] if str(row.get("day")).lower() == day.lower()), None
    )
    return (row or {}).get("location_id")


def days_from_evidence_md(text: str, *, band: str = "") -> list[dict]:
    """The season report's markdown (``SEASON_REPORT``) as report days."""

    blocks: list[tuple[int, str, list[str]]] = []
    for line in text.splitlines():
        head = _DAY_HEAD.match(line)
        if head:
            blocks.append((int(head.group(1)), head.group(2), []))
        elif blocks:
            blocks[-1][2].append(line)
    out = []
    for number, title, lines in blocks:
        tentpole = _TENTPOLE.search(title) or _REREAD.search(title)
        generated = _GENERATED.search(title)
        kind = "tentpole" if tentpole else "generated" if generated else "lost"
        texts: list[str] = []
        opening = premise = ""
        first_visual = ""
        character = premise_id = None
        for line in lines:
            caption = _CAPTION.match(line)
            panel = _PANEL.match(line)
            if panel and not first_visual:
                first_visual = panel.group(2)
            if caption:
                body = caption.group(1)
                texts.append(body)
                if kind == "generated" and not premise and not first_visual:
                    premise = body
                elif not opening and first_visual:
                    opening = body
            for quoted in _QUOTED.findall(line):
                if not line.startswith("**Toi**"):
                    texts.append(quoted)
            turned = _TURNS_TO.match(line)
            if turned:
                character = turned.group(1)
            checklist = _CHECKLIST.match(line)
            if checklist and checklist.group(1) != "—":
                premise_id = checklist.group(1)
        if kind == "tentpole":
            place = _tentpole_place(int(tentpole.group(1)), tentpole.group(2))
            key = f"t{tentpole.group(1)}.{tentpole.group(2).lower()}"
        else:
            place = infer_place(f"{first_visual} {premise}") if kind == "generated" else None
            key = generated.group(1) if generated else ""
        out.append(
            {
                "day": number,
                "kind": kind,
                "key": key,
                "band": band,
                "place": place,
                "character": character,
                "opening": first_sentence(opening or premise),
                "premise": premise,
                "premise_id": premise_id,
                "complication": "",
                "text": texts,
            }
        )
    return out


def read_evidence(folders: Iterable[Path], *, include_dry: bool = False) -> dict[str, list[dict]]:
    """Every season transcript under ``folders``. The free ``dry*`` runs (the fake
    director, before each paid run) are left out unless ``include_dry``."""

    lives = {}
    for folder in folders:
        for path in sorted(folder.rglob("*.md")):
            if path.name.upper() == "README.MD":
                continue
            if not include_dry and any(
                part.startswith("dry") for part in path.relative_to(folder).parts
            ):
                continue
            band = (
                path.stem[:2].upper() if re.match(r"^[ABC][12]", path.stem, re.IGNORECASE) else ""
            )
            days = days_from_evidence_md(path.read_text(encoding="utf-8"), band=band)
            if days:
                lives[str(path.relative_to(folder.parent))] = days
    return lives


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def plates_own() -> dict[str, bool]:
    try:
        sys.path.insert(0, str(ROOT))
        from app.services.season.world import SEASON_ONE_LOCATIONS

        return {place: bool(row.get("own")) for place, row in SEASON_ONE_LOCATIONS.items()}
    except Exception:  # noqa: BLE001 - the plate count is optional
        return {}


def markdown(result: dict[str, Any], *, title: str) -> str:
    rows = [
        f"### {title}",
        "",
        "| Learner | scenes (gen.) | Mistral share (gen.) | 5-day windows over the Mistral cap | "
        "places (gen.) | longest room run | repeated pairs | repeated openings (gen.) | "
        "repeated premises | repeated complications | text seen twice | borrowed plate |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    short = [name for name, row in result["learners"].items() if row["scenes"] < MIN_TABLE_SCENES]
    for name, row in result["learners"].items():
        if name in short:
            continue
        run = row["longest_room_run"]
        windows = row["mistral_windows"]
        rows.append(
            f"| {name} | {row['scenes']} ({row['generated']}) | {row['mistral_share']:.0%} "
            f"({row['generated_mistral_share']:.0%}) | {windows['over_cap']} of {windows['windows']} | {row['distinct_places']} "
            f"({row['generated_distinct_places']}) | {run['days']} × {run['place']} | "
            f"{sum(row['repeated_pairs'].values()) - len(row['repeated_pairs'])} over {len(row['repeated_pairs'])} pairs | "
            f"{sum(row['repeated_openings'].values()) - len(row['repeated_openings'])} "
            f"({sum(row['repeated_generated_openings'].values()) - len(row['repeated_generated_openings'])}) | "
            f"{sum(row['repeated_premises'].values()) - len(row['repeated_premises'])} | "
            f"{sum(row['repeated_complications'].values()) - len(row['repeated_complications'])} | "
            f"{row['text_seen_twice']} | {row['borrowed_plate_scenes']} |"
        )
    across = result["across"]
    band = across["same_band"]
    if short:
        rows += [
            "",
            f"Not tabled (fewer than {MIN_TABLE_SCENES} scenes, still in the across-learner numbers): {', '.join(short)}.",
        ]
    rows += [
        "",
        f"Across learners (mean Jaccard of day-N sentences): every pair of lives — tentpole days "
        f"{_fmt(across['tentpole']['mean'])} ({across['tentpole']['pairs']} pairs), generated days "
        f"{_fmt(across['generated']['mean'])} ({across['generated']['pairs']} pairs); same-band pairs — "
        f"tentpole days {_fmt(band['tentpole']['mean'])} ({band['tentpole']['pairs']}), generated days "
        f"{_fmt(band['generated']['mean'])} ({band['generated']['pairs']}). "
        f"Same-band pairs opening day 1 on the same sentence: {_fmt(across['same_first_day_opening'])}; "
        f"opening a generated day N on the same sentence: {_fmt(across['same_generated_opening_on_day_n'])}. "
        f"Pairs of lives staging the same season premise on a generated day N: "
        f"{_fmt(across['same_premise_on_day_n'])}.",
        "",
    ]
    return "\n".join(rows)


def _fmt(value: Any) -> str:
    return "—" if value is None else f"{value:.0%}" if isinstance(value, float) else str(value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--walk", action="store_true", help="play the walk lives first (fake provider)"
    )
    parser.add_argument(
        "--lives",
        default=",".join(DEFAULT_LIVES),
        help="walk lives, comma separated (persona-quality)",
    )
    parser.add_argument(
        "--days", type=int, default=DEFAULT_DAYS, help="days per walk life (LIFE_DAYS)"
    )
    parser.add_argument(
        "--lives-dir",
        type=Path,
        help="read the walk's life-*.json from here (or write them here with --walk)",
    )
    parser.add_argument(
        "--evidence",
        type=Path,
        action="append",
        default=[],
        help="a paid evidence folder (repeatable)",
    )
    parser.add_argument(
        "--include-dry",
        action="store_true",
        help="also read the free dry runs in the evidence folders",
    )
    parser.add_argument("--json", type=Path, help="write the full report as JSON")
    parser.add_argument("--markdown", type=Path, help="write the tables as markdown")
    args = parser.parse_args(argv)

    own = plates_own()
    parts: list[str] = []
    full: dict[str, Any] = {}
    if args.walk or args.lives_dir:
        folder = args.lives_dir or Path(tempfile.mkdtemp(prefix="variety-walk-"))
        if args.walk:
            folder.mkdir(parents=True, exist_ok=True)
            seconds = play_walk(
                [life.strip() for life in args.lives.split(",") if life.strip()], args.days, folder
            )
            print(
                f"walk: {args.lives} × {args.days} days in {seconds:.0f} s → {folder}",
                file=sys.stderr,
            )
        lives = read_lives_dir(folder)
        full["walk"] = report(lives, own=own)
        parts.append(
            markdown(full["walk"], title=f"Walk lives (fake provider), {len(lives)} lives")
        )
    if args.evidence:
        lives = read_evidence(args.evidence, include_dry=args.include_dry)
        full["evidence"] = report(lives, own=own)
        parts.append(
            markdown(
                full["evidence"],
                title=f"Paid evidence (real model), {len(lives)} reads; generated places inferred from the text",
            )
        )
    if not parts:
        parser.error("nothing to read: --walk, --lives-dir or --evidence")
    text = "\n".join(parts)
    print(text)
    if args.json:
        args.json.write_text(json.dumps(full, ensure_ascii=False, indent=1), encoding="utf-8")
    if args.markdown:
        args.markdown.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
