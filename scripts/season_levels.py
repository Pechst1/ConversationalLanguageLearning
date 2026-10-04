"""Check (and list the work left for) a season's level variants — T-2, 2026-10-03.

The bible lines stay in the tentpole files; the variants live in
``app/data/season/<id>/levels.json`` (see app/services/season/levels.py). This
script checks every variant against its band:

* **words** — share of running words inside the band's core lexicon (v3, A1 → C1),
  cast and place names counted as known. A line may carry at most the band's
  budget of words outside the list (A1: 1, A2: 2, B1: 3, B2: 4, C1: 6), and every
  level of every file must reach 95 % overall;
* **grammar** — no reviewed detector of a sub-band *above* the band fires on the
  variant (an A1 line with a subjonctif, a B1 line with a passé antérieur);
* **length** — an A1 line is at most 10 words, an A2 line 14 (letters and documents
  excepted: they get an easy-read version, not a short one);
* **coverage** — which lines still lack a1 / b2 / c1, and which turns lack
  level examples (``--todo``);
* **translations** (QA-STORY 2026-10-03) — an a1 variant that differs from the A2
  line carries ``a1_native`` {en, de}; every turn/solve has a plain task
  (``tasks.json``) and every turn an «ask again» line (or ``null``).

    venv/bin/python scripts/season_levels.py [--season s1] [--todo] [--file t3] [--strict]
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.grammar_catalog import detector_matches, parse_detector  # noqa: E402
from app.services.lexical_coverage import (  # noqa: E402
    KnownWordSet,
    default_resolver,
    load_lexicon,
    text_coverage,
)
from app.services.season.levels import (  # noqa: E402
    iter_example_slots,
    iter_says,
    iter_task_owners,
    level_key,
    read_levels,
    read_tasks,
)

ROOT = Path(__file__).resolve().parents[1]
SEASON_ROOT = ROOT / "app" / "data" / "season"
CATALOGUE = ROOT / "templates" / "french_core_grammar_v2.tsv"
SUB_BANDS = ("A1.1", "A1.2", "A2.1", "A2.2", "B1.1", "B1.2", "B2.1", "B2.2", "C1.1", "C1.2")
LEVEL_BAND = {"a1": "A1", "a2": "A2", "b1": "B1", "b2": "B2", "c1": "C1"}
BUDGET = {"A1": 1, "A2": 2, "B1": 3, "B2": 4, "C1": 6}
MAX_WORDS = {"A1": 10, "A2": 14}
FLOOR = 0.95
#: Long diegetic text (letters, documents) is read, not heard: no length cap.
LONG_TEXT_WORDS = 30
#: The languages an A1 line and an «ask again» line are translated into.
NATIVE_LANGUAGES = ("en", "de")
#: The languages a plain task is written in.
TASK_LANGUAGES = ("en", "de", "fr")


def _known(band: str, names: frozenset[str]) -> KnownWordSet:
    core = load_lexicon().core_lemmas(band)
    return KnownWordSet(lemmas=frozenset(core | names), band=band, estimate_level=band,
                        estimate_source="season_levels", nailed_count=0, core_count=len(core))


def _names(season_dir: Path) -> frozenset[str]:
    names: set[str] = set()
    lemmas = load_lexicon().lemmas
    for path in [season_dir / "season.json", season_dir / "world.json"]:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r'"name(?:_fr)?"\s*:\s*"([^"]+)"', text):
            # Capitalised words only: «L'arrière-salle du Mistral» names Mistral, not salle.
            for part in re.findall(r"[A-ZÀ-Ý][A-Za-zÀ-ÿ-]+", match.group(1)):
                # A cast member's name is a name («Marchand», «Marin»); in a place
                # name «Rue», «Gare», «Le» are words the band must earn.
                if path.name == "season.json" or part.lower() not in lemmas:
                    names.add(part.lower())
        for match in re.finditer(r'"id"\s*:\s*"[a-z_]+",\s*"name"\s*:\s*"([^"]+)"', text):
            names.update(part.lower() for part in re.findall(r"[A-ZÀ-Ý][A-Za-zÀ-ÿ-]+", match.group(1)))
        # Titles («M.», «Mme») and the season's own proper nouns no entry spells out.
        names.update({"m", "mme", "mlle"})
        for word in re.findall(r"\b(Solvel|Paris|Odile|Mistral|Valmy|Berlin|Lyon)\b", text):
            names.add(word.lower())
    return frozenset(names)


def _detectors_above(band: str) -> list[tuple[str, dict]]:
    top = max(i for i, sub in enumerate(SUB_BANDS) if sub.startswith(band))
    found = []
    with CATALOGUE.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            if row["sub_band"] in SUB_BANDS and SUB_BANDS.index(row["sub_band"]) > top:
                detector = parse_detector(row["detector"])
                if detector and detector.get("kind") == "regex":
                    found.append((row["external_id"], detector))
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--season", default="s1")
    parser.add_argument("--file", help="only this tentpole file (t1 … t8, season)")
    parser.add_argument("--todo", action="store_true", help="list lines still lacking variants")
    parser.add_argument("--strict", action="store_true", help="exit 1 on any problem")
    args = parser.parse_args()

    season_dir = SEASON_ROOT / args.season
    levels = read_levels(season_dir)
    lines = levels["lines"]
    tasks = read_tasks(season_dir)
    names = _names(season_dir)
    resolver = default_resolver()
    above = {band: _detectors_above(band) for band in ("A1", "A2", "B1", "B2")}

    files = ["season", *sorted(p.stem for p in season_dir.glob("t[0-9].json"))]
    if args.file:
        files = [args.file]
    problems: list[str] = []
    todo: dict[str, int] = defaultdict(int)
    totals: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])

    for file_id in files:
        raw = json.loads((season_dir / f"{file_id}.json").read_text(encoding="utf-8"))
        for say in iter_says(raw):
            key = level_key(say["a2"], say.get("b1"))
            variants = lines.get(key) or {}
            for field in ("a1", "b2", "c1"):
                if not variants.get(field):
                    todo[f"{file_id}:{field}"] += 1
            # QA-STORY 2026-10-03: an A1 variant that is not the A2 line carries its own
            # translations — an A1 learner must never read the A2 line's beside it.
            a1 = variants.get("a1")
            if isinstance(a1, str) and a1.strip() and " ".join(a1.split()) != " ".join(say["a2"].split()):
                native_a1 = variants.get("a1_native") or {}
                missing = [lang for lang in NATIVE_LANGUAGES if not str(native_a1.get(lang) or "").strip()]
                if missing:
                    problems.append(f"{file_id} a1_native {key}: no translation in {missing} — {a1}")
            for field, text in variants.items():
                band = LEVEL_BAND.get(field) if isinstance(text, str) else None
                if band is None or not isinstance(text, str) or not text.strip():
                    continue
                # «À suivre…» closes every episode: a formula met on day one, not vocabulary.
                measured = re.sub(r"[ÀA] suivre…?", "", text)
                result = text_coverage(measured, _known(band, names), resolver=resolver)
                totals[(file_id, field)][0] += result.known_words
                totals[(file_id, field)][1] += result.running_words
                unknown = [word.lemma for word in result.unknown]
                if len(unknown) > BUDGET[band]:
                    problems.append(f"{file_id} {field} {key}: outside {band} list: {unknown} — {text}")
                words = len(text.split())
                if band in MAX_WORDS and MAX_WORDS[band] < words < LONG_TEXT_WORDS:
                    problems.append(f"{file_id} {field} {key}: {words} words (≤ {MAX_WORDS[band]}) — {text}")
                for unit, detector in above.get(band, []):
                    if detector_matches(detector, text):
                        problems.append(f"{file_id} {field} {key}: {unit} is above {band} — {text}")
        for slot, _owner, _field in iter_example_slots(file_id, raw):
            if slot not in levels["examples"]:
                todo[f"{file_id}:examples"] += 1
        # QA-STORY: every turn and solve has a plain task (en/de/fr); every turn says
        # what its addressee asks when a reply expresses none of the routes (or null).
        for owner in iter_task_owners(raw):
            slot = f"{file_id}:{owner['id']}"
            plain = tasks["tasks"].get(slot) or {}
            missing = [lang for lang in TASK_LANGUAGES if not str(plain.get(lang) or "").strip()]
            if missing:
                problems.append(f"{slot}: plain task missing in {missing}")
            if owner.get("kind") != "turn":
                continue
            if slot not in tasks["ask_again"]:
                problems.append(f"{slot}: no ask_again (write one, or null for a catch-all turn)")
                continue
            ask = tasks["ask_again"][slot]
            if ask is None:
                continue
            for field in ("fr", "fr_named"):
                text = str(ask.get(field) or "")
                if not text:
                    if field == "fr":
                        problems.append(f"{slot}: ask_again has no fr")
                    continue
                measured = text.replace("{name}", "")
                result = text_coverage(measured, _known("A1", names), resolver=resolver)
                unknown = [word.lemma for word in result.unknown]
                if len(unknown) > BUDGET["A1"]:
                    problems.append(f"{slot} ask_again {field}: outside A1 list {unknown} — {text}")
                if len(measured.split()) > MAX_WORDS["A1"]:
                    problems.append(f"{slot} ask_again {field}: longer than {MAX_WORDS['A1']} words — {text}")
                for unit, detector in above["A1"]:
                    if detector_matches(detector, measured):
                        problems.append(f"{slot} ask_again {field}: {unit} is above A1 — {text}")
            if ask.get("fr"):
                missing = [lang for lang in NATIVE_LANGUAGES if not str(ask.get(lang) or "").strip()]
                if missing:
                    problems.append(f"{slot}: ask_again has no translation in {missing}")

    print("coverage by file and level (known running words):")
    for (file_id, field), (known, running) in sorted(totals.items()):
        share = known / running if running else 1.0
        flag = "" if share >= FLOOR else "  ✗ below 95 %"
        print(f"  {file_id:7} {field}: {share:6.1%} of {running}{flag}")
        if share < FLOOR:
            problems.append(f"{file_id} {field}: {share:.1%} known (floor 95 %)")
    if args.todo:
        print("still to write:")
        for slot, count in sorted(todo.items()):
            print(f"  {slot}: {count}")
    print(f"{len(problems)} problems")
    for problem in problems[:200]:
        print(f"  ✗ {problem}")
    return 1 if (problems and args.strict) else 0


if __name__ == "__main__":
    sys.exit(main())
