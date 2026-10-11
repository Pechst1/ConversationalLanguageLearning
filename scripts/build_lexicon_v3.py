"""L-1 (content program 2026-10-03) — build ``fr-core-lexicon-v3``.

Writes ``app/data/lexical/fr_core_lexicon.json``: the French core lexicon
A1.1 → C1.2 plus a multiword ``expressions`` map. Deterministic: the same
inputs always give the same file.

Inputs
------
* **The v2 lexicon** (A1–B1, curated, WP-29/WP-L2/WP-S2), read from git by its
  blob id :data:`BASE_V2_BLOB` so the build can be re-run after the output has
  replaced it (``--base`` reads a file instead).
* ``app/data/lexical/fr_core_pos.json`` — POS/gender of the v2 lemmas (WP-84).
* ``Anki_cards___2025-11-01T13-09-36.csv`` — the owner's «Französisch 5000»
  export. Per decision D1 only the **rank, lemma, part of speech, gender (from
  the article) and IPA** are read. Its German glosses and example sentences are
  never parsed into the output.
* ``app/data/lexical/authored_b2_c1.json`` — our curation: re-banding, deck
  overrides, register labels, headwords, and the authored B2/C1 lemmas beyond
  the deck's 5,000.
* ``app/data/lexical/expressions_src.json`` — the authored multiword expressions.
* ``app/data/lexical/glosses_src.json`` — the authored learner glosses (en, de) of
  every lemma and expression (package L-2), merged in as ``gloss: {en, de}``.

Inflected forms for new lemmas are generated (verbs from the Verbiste templates
shipped with ``mlconjug3``, a declared dependency; regular noun/adjective
plurals and feminines by rule) and stored only when the suffix rules of
``app/services/lexical_coverage.py`` cannot resolve them — the v2 convention.

Run: ``venv/bin/python scripts/build_lexicon_v3.py`` (``--check`` builds and
prints the report without writing).
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LEX_DIR = ROOT / "app" / "data" / "lexical"
OUT = LEX_DIR / "fr_core_lexicon.json"
POS_PATH = LEX_DIR / "fr_core_pos.json"
AUTHORED_PATH = LEX_DIR / "authored_b2_c1.json"
EXPRESSIONS_PATH = LEX_DIR / "expressions_src.json"
GLOSSES_PATH = LEX_DIR / "glosses_src.json"
DECK_PATH = ROOT / "Anki_cards___2025-11-01T13-09-36.csv"
CAN_DOS_PATH = ROOT / "app" / "data" / "syllabus" / "fr_core_can_dos_v2.json"

#: ``git rev-parse HEAD:app/data/lexical/fr_core_lexicon.json`` at fbc7472 —
#: fr-core-lexicon-v2, 2,682 lemmas.
BASE_V2_BLOB = "e3c68b8bd6971f07d908259b73275165f830bb04"

VERSION = "fr-core-lexicon-v3"
BANDS = ("A1", "A2", "B1", "B2", "C1")
SUB_BANDS = ("A1.1", "A1.2", "A2.1", "A2.2", "B1.1", "B1.2", "B2.1", "B2.2", "C1.1", "C1.2")
POS_VALUES = ("noun", "verb", "adjective", "adverb", "function", "number", "interjection")
EXPRESSION_KINDS = ("chunk", "idiom", "collocation", "connector", "discourse")
REGISTERS = (None, "familier", "soutenu")

#: Cumulative receptive targets (non-numeral lemmas) the deck thresholds aim at.
CUMULATIVE_TARGET = {"B1": 2700, "B2": 4500}
#: Deck lemmas missing from v2 with a rank up to this are B1. The deck's corpus
#: is formal (parliament, press), so past ~600 its «frequent» words are
#: sénateur, motion, fédéral: B2, while everyday words it ranks low are
#: pulled down by the curated ``deck_band_overrides``.
B1_MAX_RANK = 600

sys.path.insert(0, str(ROOT))


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def fold(value: str) -> str:
    raw = unicodedata.normalize("NFC", str(value or "").strip().lower())
    for mark in "’ʼ":
        raw = raw.replace(mark, "'")
    return raw


def words(block: str) -> list[str]:
    return [fold(word) for word in str(block or "").split()]


def band_of(sub_band: str) -> str:
    return sub_band[:2]


def sub_band_index(sub_band: str) -> int:
    return SUB_BANDS.index(sub_band)


# ---------------------------------------------------------------------------
# inputs
# ---------------------------------------------------------------------------


def load_base(path: Path | None) -> dict[str, Any]:
    if path is not None:
        payload = json.loads(path.read_text(encoding="utf-8"))
    else:
        # A fixed argv with a pinned blob id: no untrusted input reaches git.
        raw = subprocess.run(  # noqa: S603
            ["git", "cat-file", "-p", BASE_V2_BLOB],  # noqa: S607
            cwd=ROOT, check=True, capture_output=True,
        ).stdout
        payload = json.loads(raw.decode("utf-8"))
    if payload.get("version") != "fr-core-lexicon-v2":
        raise SystemExit(f"base is {payload.get('version')!r}, expected fr-core-lexicon-v2")
    return payload


#: «1101 76 procéder \pʁɔ.se.de\ [anki:play:a:0] vi …» — rank, score, lemma,
#: IPA, POS tags. The rest of the field (gloss, examples) is not captured.
_DECK_HEAD = re.compile(
    r"^(\d+) (\d+) (.+?) \\([^\\]*)\\ \[anki:play[^\]]*\] "
    r"((?:[a-z]+(?:\([a-z]+\))?)(?:, [a-z]+(?:\([a-z]+\))?)*) "
)
_ARTICLES = (("le/la ", "mf"), ("le ", "m"), ("la ", "f"), ("les ", None), ("un ", "m"),
             ("une ", "f"), ("l'", None))
_DECK_NOUN_TAGS = {"nm": "m", "nf": "f", "nmf": "mf", "nmi": "m", "nmpl": "m", "nfpl": "f", "npl": None}
_DECK_POS = {
    "adj": "adjective", "nadj": "adjective", "nadjpl": "adjective",
    "adv": "adverb",
    "v": "verb", "vi": "verb", "vt": "verb", "vr": "verb", "vaux": "verb",
    "prep": "function", "art": "function", "pro": "function", "det": "function", "conj": "function",
    "num": "number", "intj": "interjection",
}


def parse_deck(path: Path) -> list[dict[str, Any]]:
    """The FR → DE notes of the export: rank, lemma, article gender, POS, IPA."""

    csv.field_size_limit(10**9)
    entries: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        reader = csv.reader(handle, delimiter="\t")
        next(reader)
        next(reader)
        for row in reader:
            if len(row) < 14 or row[13] != "FR -> DE":
                continue
            answer = row[1].split("　")[-1].strip().lstrip('"')
            match = _DECK_HEAD.match(answer)
            if not match:
                raise SystemExit(f"unparsed deck row: {answer[:80]!r}")
            rank, _score, raw, ipa, tags = match.groups()
            raw = fold(re.sub(r"\s*\\.*$", "", raw))
            article_gender: str | None = None
            article = ""
            for prefix, gender in _ARTICLES:
                if raw.startswith(prefix):
                    article, article_gender, raw = prefix, gender, raw[len(prefix):]
                    break
            headword = None
            for prefix in ("se ", "s'"):
                if raw.startswith(prefix) and not article:
                    headword, raw = raw, raw[len(prefix):]
                    break
            raw = re.split(r" (?:le|la|les) ", raw)[0]  # «plateforme la plate-forme»
            tag_list = [tag.split("(")[0] for tag in tags.split(", ") if tag != "app"]
            entries.append(
                {
                    "rank": int(rank),
                    "lemma": raw,
                    "article": article,
                    "article_gender": article_gender,
                    "tags": tag_list,
                    "ipa": ipa.strip() or None,
                    "headword": headword,
                }
            )
    entries.sort(key=lambda entry: entry["rank"])
    if len(entries) != 5000 or len({entry["rank"] for entry in entries}) != 5000:
        raise SystemExit(f"deck: expected 5000 ranked notes, got {len(entries)}")
    return entries


def deck_pos_gender(entry: dict[str, Any], gender_overrides: dict[str, str]) -> tuple[str, str | None]:
    tags = entry["tags"]
    noun_tags = [tag for tag in tags if tag in _DECK_NOUN_TAGS]
    if entry["article"]:
        pos = "noun"
    else:
        pos = next((_DECK_POS[tag] for tag in tags if tag in _DECK_POS), "noun" if noun_tags else "adjective")
    if pos != "noun":
        return pos, None
    gender = gender_overrides.get(entry["lemma"])
    if gender is None:
        tag_genders = {_DECK_NOUN_TAGS[tag] for tag in noun_tags if _DECK_NOUN_TAGS[tag]}
        if "mf" in tag_genders and not ({"m", "f"} & tag_genders):
            gender = "mf"
        elif entry["article_gender"]:
            gender = entry["article_gender"]
        elif len(tag_genders) == 1:
            gender = tag_genders.pop()
        elif {"m", "f"} <= tag_genders:
            gender = "mf"
    if gender is None:
        raise SystemExit(f"deck noun without gender: {entry['lemma']!r} (add it to gender_overrides)")
    return pos, gender


# ---------------------------------------------------------------------------
# numerals
# ---------------------------------------------------------------------------

_NUMBER_PARTS = frozenset(
    "un une deux trois quatre cinq six sept huit neuf dix onze douze treize quatorze quinze seize "
    "vingt vingts trente quarante cinquante soixante cent cents mille et".split()
)


def is_compound_numeral(lemma: str) -> bool:
    parts = lemma.split("-")
    if len(parts) < 2:
        return False
    head, last = parts[:-1], parts[-1]
    if last.endswith("ième"):
        stem = last[:-4]
        last_ok = any(stem.startswith(part.rstrip("e")) for part in _NUMBER_PARTS if len(part) > 2) or stem in {"un", "deux"}
    else:
        last_ok = last in _NUMBER_PARTS
    return last_ok and all(part in _NUMBER_PARTS for part in head)


# ---------------------------------------------------------------------------
# inflection
# ---------------------------------------------------------------------------


class Resolver:
    """The suffix rules of ``app.services.lexical_coverage.CuratedResolver``,
    without its file read: a generated form is stored only when these rules
    cannot reach its lemma."""

    def __init__(self) -> None:
        from app.services.lexical_coverage import _FEMININE_SUFFIXES, _VERB_STEM_SUFFIXES

        self.verb_suffixes = _VERB_STEM_SUFFIXES
        self.feminine_suffixes = _FEMININE_SUFFIXES

    def candidates(self, key: str) -> list[str]:
        out = [key]

        def push(value: str) -> None:
            if value and len(value) > 1 and value not in out:
                out.append(value)

        if key.endswith("aux"):
            push(key[:-3] + "al")
        for suffix in ("s", "x"):
            if key.endswith(suffix) and len(key) > 2:
                push(key[:-1])
        for suffix, replacement in self.feminine_suffixes:
            if key.endswith(suffix) and len(key) > len(suffix) + 1:
                push(key[: -len(suffix)] + replacement)
        if key.endswith("e") and len(key) > 2:
            push(key[:-1])
        for suffix in self.verb_suffixes:
            if key.endswith(suffix) and len(key) > len(suffix) + 1:
                stem = key[: -len(suffix)]
                for ending in ("er", "ir", "re", "oir"):
                    push(stem + ending)
        return out


class Verbiste:
    """Verb paradigms from the Verbiste templates bundled with mlconjug3."""

    def __init__(self) -> None:
        try:
            from mlconjug3.conjug_manager import ConjugManager

            manager = ConjugManager(language="fr")
            self.verbs: dict[str, dict[str, str]] = manager.verbs
            self.templates: dict[str, Any] = manager.conjugations
        except Exception as exc:  # pragma: no cover - the dependency is declared
            raise SystemExit(f"mlconjug3 Verbiste data unavailable: {exc}") from exc

    def forms(self, lemma: str) -> list[str] | None:
        info = self.verbs.get(lemma)
        if not info:
            return None
        root = info["root"]
        template = self.templates.get(info["template"])
        if not template:
            return None
        out: list[str] = []

        def walk(node: Any) -> None:
            if isinstance(node, str):
                out.append(root + node)
            elif isinstance(node, dict):
                for key in sorted(node):
                    walk(node[key])
            elif isinstance(node, (list, tuple)):
                if len(node) == 2 and isinstance(node[0], int):
                    walk(node[1])
                else:
                    for item in node:
                        walk(item)

        walk(template)
        return sorted({fold(form) for form in out if form and " " not in form})


#: Verbiste agrees participles that never agree (pouvoir, plaire, …).
_BAD_GENERATED_FORMS = frozenset("pue pues plue plues nuie nuies suffie suffies".split())


def regular_verb_forms(lemma: str) -> list[str]:
    """The regular paradigm when Verbiste does not list the verb."""

    if lemma.endswith("er"):
        stem = lemma[:-2]
        endings = ("e es ons ez ent ais ait ions iez aient erai eras era erons erez eront "
                   "erais erait erions eriez eraient ai as a âmes âtes èrent é ée és ées ant")
        return [stem + ending for ending in endings.split()]
    if lemma.endswith("ir"):
        stem = lemma[:-2]
        endings = ("is it issons issez issent issais issait issions issiez issaient irai iras ira "
                   "irons irez iront irais irait irions iriez iraient îmes îtes irent i ie ies "
                   "issant isse isses")
        return [stem + ending for ending in endings.split()]
    if lemma.endswith("re"):
        stem = lemma[:-2]
        endings = ("s ons ez ent ais ait ions iez aient rai ras ra rons rez ront rais rait rions "
                   "riez raient is it îmes îtes irent u ue us ues ant e es")
        return [stem + ending for ending in endings.split()]
    return []


def noun_forms(lemma: str) -> list[str]:
    if lemma.endswith(("s", "x", "z")) or "-" in lemma:
        return []
    if lemma.endswith("al"):
        return [lemma[:-2] + "aux"]
    if lemma.endswith(("eau", "au", "eu")):
        return [lemma + "x"]
    return [lemma + "s"]


#: Feminine endings, most specific first.
_FEMININE_RULES = (
    ("ieur", "ieure"), ("ateur", "atrice"), ("cteur", "ctrice"), ("eur", "euse"), ("eux", "euse"),
    ("cret", "crète"), ("plet", "plète"), ("quiet", "quiète"), ("et", "ette"),
    ("eil", "eille"), ("el", "elle"), ("ien", "ienne"), ("éen", "éenne"), ("on", "onne"),
    ("eau", "elle"), ("ef", "ève"), ("f", "ve"), ("er", "ère"), ("anc", "anche"), ("c", "que"),
    ("gu", "guë"),
)
#: -al adjectives whose plural is -als.
_AL_PLURAL_S = frozenset("fatal naval banal natal final glacial bancal tonal".split())


def adjective_forms(lemma: str) -> list[str]:
    if "-" in lemma:
        return []
    feminine = lemma
    if not lemma.endswith("e"):
        feminine = lemma + "e"
        for suffix, replacement in _FEMININE_RULES:
            if lemma.endswith(suffix):
                feminine = lemma[: -len(suffix)] + replacement
                break
    if lemma.endswith(("s", "x")):
        plural = lemma
    elif lemma.endswith("al") and lemma not in _AL_PLURAL_S:
        plural = lemma[:-2] + "aux"
    elif lemma.endswith("eau"):
        plural = lemma + "x"
    else:
        plural = lemma + "s"
    return sorted({feminine, plural, feminine + "s"} - {lemma})


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------


def build(base: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    pos_file = json.loads(POS_PATH.read_text(encoding="utf-8"))["lemmas"]
    authored = json.loads(AUTHORED_PATH.read_text(encoding="utf-8"))
    expressions_src = json.loads(EXPRESSIONS_PATH.read_text(encoding="utf-8"))
    deck = parse_deck(DECK_PATH)
    report: dict[str, Any] = {"warnings": []}
    warn = report["warnings"].append

    gender_overrides = {fold(k): v for k, v in authored["gender_overrides"].items()}
    spelling = {fold(k): fold(v) for k, v in authored["deck_spelling"].items()}
    variants = {fold(k): fold(v) for k, v in authored["variant_forms"].items()}
    removed = {fold(k): fold(v) for k, v in authored["remove_lemmas"].items()}
    reband = {fold(k): v for k, v in authored["reband"].items()}
    deck_skip = set(words(authored["deck_skip"]))
    forms_as_lemmas = set(words(authored["deck_forms_as_lemmas"]))
    deck_overrides = {
        lemma: sub_band for sub_band, block in authored["deck_band_overrides"].items() for lemma in words(block)
    }
    deck_to_c1 = set(words(authored["deck_to_c1"]))
    registers = {
        lemma: register for register, block in authored["register"].items() for lemma in words(block)
    }
    headwords = {fold(k): fold(v) for k, v in authored["headwords"].items()}
    pos_overrides = {fold(k): v for k, v in authored.get("pos_overrides", {}).items()}
    ipa_overrides = {fold(k): v for k, v in authored.get("ipa_overrides", {}).items()}

    base_lemmas: dict[str, dict[str, Any]] = base["lemmas"]
    base_forms: dict[str, str] = dict(base["forms"])

    # --- 1. the v2 lemmas -------------------------------------------------
    lemmas: dict[str, dict[str, Any]] = {}
    order: dict[str, tuple[int, int]] = {}
    for lemma, entry in base_lemmas.items():
        if lemma in removed:
            continue
        pos_entry = entry if entry.get("pos") else pos_file.get(lemma, {})
        pos = pos_overrides.get(lemma, pos_entry.get("pos"))
        if pos not in POS_VALUES:
            raise SystemExit(f"v2 lemma without pos: {lemma!r}")
        row: dict[str, Any] = {
            "band": entry["band"],
            "sub_band": entry["sub_band"],
            "pos": pos,
            "source": "v2",
        }
        if pos == "noun":
            row["gender"] = gender_overrides.get(lemma) or pos_entry.get("gender")
        lemmas[lemma] = row
        order[lemma] = (0, int(entry["rank"]))

    # Compound numerals: «X-cent» / «X-cents» and «quatre-vingt(s)» are one
    # lemma each; the -s spelling is the headword, the other a form.
    numeral_forms: dict[str, str] = {}
    for lemma in sorted(lemmas):
        if is_compound_numeral(lemma) and (lemma.endswith("-cent") or lemma == "quatre-vingt"):
            plural = lemma + "s"
            if plural in lemmas:
                numeral_forms[lemma] = plural
                del lemmas[lemma]
    report["numeral_variants_merged"] = sorted(numeral_forms)

    # --- 2. the deck ------------------------------------------------------
    deck_by_lemma: dict[str, dict[str, Any]] = {}
    expression_like: list[str] = []
    for entry in deck:
        lemma = spelling.get(entry["lemma"], entry["lemma"])
        entry = {**entry, "lemma": lemma}
        if " " in lemma or lemma in removed or (lemma.startswith("d'") and lemma not in lemmas):
            expression_like.append(lemma)
            continue
        deck_by_lemma.setdefault(lemma, entry)

    new_deck: list[dict[str, Any]] = []
    for lemma, entry in sorted(deck_by_lemma.items(), key=lambda item: item[1]["rank"]):
        if lemma in variants:
            continue
        if lemma in lemmas:
            row = lemmas[lemma]
            row["freq_rank"] = entry["rank"]
            if entry["ipa"]:
                row["ipa"] = entry["ipa"]
            if entry["headword"]:
                row.setdefault("headword", entry["headword"])
            continue
        if lemma in deck_skip:
            continue
        if lemma in base_forms and lemma not in forms_as_lemmas:
            warn(f"deck lemma {lemma!r} is a v2 form of {base_forms[lemma]!r}; listed in neither deck_skip nor deck_forms_as_lemmas")
            continue
        if lemma in numeral_forms:
            continue
        new_deck.append(entry)

    # Band the new deck lemmas: curated overrides first, then rank thresholds
    # sized to the cumulative targets.
    def non_numeral(band_set: set[str]) -> int:
        return sum(
            1 for lemma, row in lemmas.items() if row.get("band") in band_set and not is_compound_numeral(lemma)
        )

    unbanded: list[dict[str, Any]] = []
    for entry in new_deck:
        lemma = entry["lemma"]
        pos, gender = deck_pos_gender(entry, gender_overrides)
        pos = pos_overrides.get(lemma, pos)
        gender = (gender or gender_overrides.get(lemma)) if pos == "noun" else None
        row = {"pos": pos, "source": "anki_rank", "freq_rank": entry["rank"]}
        if gender:
            row["gender"] = gender
        if entry["ipa"]:
            row["ipa"] = entry["ipa"]
        if entry["headword"]:
            row["headword"] = entry["headword"]
        lemmas[lemma] = row
        order[lemma] = (1, entry["rank"])
        if lemma in deck_overrides:
            row["sub_band"] = deck_overrides[lemma]
            row["band"] = band_of(row["sub_band"])
        elif lemma in deck_to_c1:
            row["band"] = "C1"
        else:
            unbanded.append(entry)

    unused = sorted(set(deck_overrides) - {entry["lemma"] for entry in new_deck})
    if unused:
        warn(f"deck_band_overrides not applied (v2 lemma or not in the deck): {unused}")

    # Re-banding happens before the thresholds so the counts are final.
    for lemma, sub_band in reband.items():
        if lemma not in lemmas:
            raise SystemExit(f"reband: unknown lemma {lemma!r}")
        lemmas[lemma]["band"], lemmas[lemma]["sub_band"] = band_of(sub_band), sub_band

    authored_rows = authored_lemmas(authored, lemmas, warn)
    authored_b2 = sum(1 for row in authored_rows.values() if row["band"] == "B2")

    # B1 takes every remaining deck lemma up to B1_MAX_RANK: a word that
    # frequent is B1 vocabulary whatever the v2 count says (agir, exister,
    # mener). B2 is then sized to the cumulative target; the rest is C1.
    b1_cut = [entry for entry in unbanded if entry["rank"] <= B1_MAX_RANK]
    rest = [entry for entry in unbanded if entry["rank"] > B1_MAX_RANK]
    current_b2 = sum(1 for row in lemmas.values() if row.get("band") == "B2")
    b1_total = non_numeral({"A1", "A2", "B1"}) + len(b1_cut)
    b2_room = max(0, CUMULATIVE_TARGET["B2"] - b1_total - current_b2 - authored_b2)
    b2_cut = rest[:b2_room]
    c1_cut = rest[b2_room:]
    for group, band in ((b1_cut, "B1"), (b2_cut, "B2"), (c1_cut, "C1")):
        for entry in group:
            lemmas[entry["lemma"]]["band"] = band
    report["deck_thresholds"] = {
        "B1_last_rank": b1_cut[-1]["rank"] if b1_cut else None,
        "B2_last_rank": b2_cut[-1]["rank"] if b2_cut else None,
    }

    # Sub-bands for deck lemmas without one: the band's deck words in rank
    # order, first half .1, second half .2.
    for band in BANDS:
        pending = sorted(
            (lemma for lemma, row in lemmas.items() if row["band"] == band and "sub_band" not in row),
            key=lambda lemma: order[lemma],
        )
        half = (len(pending) + 1) // 2
        for index, lemma in enumerate(pending):
            lemmas[lemma]["sub_band"] = f"{band}.{1 if index < half else 2}"

    # --- 3. authored lemmas -----------------------------------------------
    for index, (lemma, row) in enumerate(authored_rows.items()):
        lemmas[lemma] = row
        order[lemma] = (2, index)

    # --- 4. per-lemma fields ----------------------------------------------
    for lemma, row in lemmas.items():
        row.setdefault("freq_rank", None)
        row["numeral"] = is_compound_numeral(lemma)
        if row["numeral"]:
            row["pos"] = "number"
        row["register"] = registers.get(lemma, row.get("register"))
        if lemma in headwords:
            row["headword"] = headwords[lemma]
        if lemma in ipa_overrides:  # the deck truncates a few transcriptions
            row["ipa"] = ipa_overrides[lemma]
    unknown_register = sorted(set(registers) - set(lemmas))
    if unknown_register:
        warn(f"register labels for unknown lemmas: {unknown_register}")
    unknown_headwords = sorted(set(headwords) - set(lemmas))
    if unknown_headwords:
        raise SystemExit(f"headwords for unknown lemmas: {unknown_headwords}")

    # Global list order: band, then v2 order / deck rank / authoring order.
    ranked = sorted(lemmas, key=lambda lemma: (BANDS.index(lemmas[lemma]["band"]), order[lemma], lemma))
    final: dict[str, dict[str, Any]] = {}
    for rank, lemma in enumerate(ranked, start=1):
        row = lemmas[lemma]
        out = {"band": row["band"], "sub_band": row["sub_band"], "rank": rank, "pos": row["pos"]}
        if row["pos"] == "noun":
            if row.get("gender") not in {"m", "f", "mf"}:
                raise SystemExit(f"noun without gender: {lemma!r}")
            out["gender"] = row["gender"]
        out["freq_rank"] = row["freq_rank"]
        out["numeral"] = row["numeral"]
        out["register"] = row["register"]
        out["source"] = row["source"]
        if row.get("ipa"):
            out["ipa"] = row["ipa"]
        if row.get("headword"):
            out["headword"] = row["headword"]
        if not out["sub_band"].startswith(out["band"]):
            raise SystemExit(f"sub_band/band mismatch: {lemma!r}")
        final[lemma] = out

    # --- 5. forms -----------------------------------------------------------
    forms = {key: value for key, value in base_forms.items() if value in final}
    dropped_forms = sorted(key for key, value in base_forms.items() if value not in final)
    if dropped_forms:
        report["dropped_forms"] = dropped_forms
    for variant, lemma in sorted({**numeral_forms, **variants}.items()):
        if lemma not in final:
            raise SystemExit(f"variant of unknown lemma: {variant!r} -> {lemma!r}")
        forms[variant] = lemma
    for key, lemma in sorted(authored.get("extra_forms", {}).items()):
        forms[fold(key)] = fold(lemma)
    resolver = Resolver()
    verbiste = Verbiste()
    generated = 0
    for lemma in ranked:
        row = final[lemma]
        if row["numeral"]:
            continue
        if row["pos"] == "verb":
            candidates = verbiste.forms(lemma) or regular_verb_forms(lemma)
        elif row["pos"] == "noun":
            candidates = noun_forms(lemma)
        elif row["pos"] == "adjective":
            candidates = adjective_forms(lemma)
        else:
            candidates = []
        for form in candidates:
            if form == lemma or form in final or form in forms:
                continue
            if form in _BAD_GENERATED_FORMS:
                continue
            if form[-1:] in {"s", "x"} and form[:-1] in final and form[:-1] != lemma:
                continue  # «vins» is the plural of vin before it is venir
            candidates_of_form = resolver.candidates(form)
            if lemma in candidates_of_form:
                continue
            # A more frequent lemma the suffix rules already reach owns the
            # surface («tue» is tuer, not taire; «fous» is fou, not foutre).
            if any(final[c]["rank"] < row["rank"] for c in candidates_of_form[1:] if c in final):
                continue
            forms[form] = lemma
            generated += 1
    report["generated_forms"] = generated
    for key, value in forms.items():
        if value not in final:
            raise SystemExit(f"form {key!r} points at unknown lemma {value!r}")

    atomic_apostrophe = sorted(set(base["atomic_apostrophe"]) | set(words(authored["atomic_apostrophe"])))
    atomic_hyphen = sorted(set(base["atomic_hyphen"]) | set(words(authored.get("atomic_hyphen", ""))))

    # --- 6. expressions -----------------------------------------------------
    expressions = build_expressions(expressions_src, final, forms, base["elisions"], set(atomic_apostrophe), resolver, warn)
    for lemma in expression_like:
        if not any(key == lemma or key.startswith(lemma + " ") for key in expressions):
            warn(f"deck multiword item {lemma!r} has no entry in expressions_src.json")

    # --- 6b. glosses (L-2) ----------------------------------------------------
    apply_glosses(final, expressions, warn)

    # --- 7. can-do check ----------------------------------------------------
    can_dos = json.loads(CAN_DOS_PATH.read_text(encoding="utf-8"))
    for sub_band, tasks in can_dos["sub_bands"].items():
        for task in tasks:
            for word in task["words"]:
                entry = final.get(word) or expressions.get(word)
                if entry is None:
                    warn(f"can-do {task['id']}: {word!r} is neither a lemma nor an expression")
                elif sub_band in SUB_BANDS and sub_band_index(entry["sub_band"]) > sub_band_index(sub_band):
                    warn(f"can-do {task['id']} ({sub_band}): {word!r} is banded {entry['sub_band']}")

    payload = {
        "version": VERSION,
        "language": "fr",
        "provenance": provenance(base["provenance"]),
        "bands": list(BANDS),
        "sub_bands": list(SUB_BANDS),
        "lemmas": final,
        "forms": dict(sorted(forms.items())),
        "elisions": base["elisions"],
        "atomic_apostrophe": atomic_apostrophe,
        "atomic_hyphen": atomic_hyphen,
        "expressions": expressions,
    }
    report.update(stats(final, expressions))
    return payload, report


def authored_lemmas(
    authored: dict[str, Any], existing: dict[str, dict[str, Any]], warn: Any
) -> dict[str, dict[str, Any]]:
    """``add_lemmas``: ``{sub_band: {pos_key: "word word …"}}``.

    ``pos_key`` is ``noun_m`` / ``noun_f`` / ``noun_mf`` / ``verb`` /
    ``adjective`` / ``adverb`` / ``function`` / ``interjection``. A pronominal
    verb is written «s'insurger»: the lemma is «insurger», the headword keeps
    the pronoun. A lemma the v2 list or the deck already has is skipped.
    """

    rows: dict[str, dict[str, Any]] = {}
    duplicates: list[str] = []
    for sub_band, groups in authored["add_lemmas"].items():
        if sub_band not in SUB_BANDS:
            raise SystemExit(f"add_lemmas: bad sub_band {sub_band!r}")
        for pos_key, block in groups.items():
            pos, _, gender = pos_key.partition("_")
            if pos not in POS_VALUES:
                raise SystemExit(f"add_lemmas: bad pos key {pos_key!r}")
            for word in words(block):
                headword = None
                if pos == "verb" and (word.startswith("s'") or word.startswith("se_")):
                    headword = word.replace("se_", "se ")
                    word = word[2:] if word.startswith("s'") else word[3:]
                if word in existing or word in rows:
                    duplicates.append(word)
                    continue
                row: dict[str, Any] = {
                    "band": band_of(sub_band),
                    "sub_band": sub_band,
                    "pos": pos,
                    "source": "authored",
                    "freq_rank": None,
                }
                if pos == "noun":
                    row["gender"] = gender or None
                if headword:
                    row["headword"] = headword
                rows[word] = row
    if duplicates:
        warn(f"{len(duplicates)} authored lemmas already listed (skipped): {' '.join(sorted(duplicates))}")
    return rows


def _expression_lemmas(
    surface: str,
    lemmas: dict[str, Any],
    forms: dict[str, str],
    elisions: dict[str, str],
    atomic: set[str],
    resolver: Resolver,
) -> tuple[list[str], list[str], int]:
    from app.services.lexical_coverage import Lexicon, _split_word

    lexicon = Lexicon(
        version=VERSION, lemmas={}, forms={}, elisions=elisions, atomic=frozenset(atomic), provenance={}
    )
    out: list[str] = []
    missing: list[str] = []
    tokens = 0
    for chunk in re.findall(r"[a-zà-öø-ÿœ]+(?:['\-][a-zà-öø-ÿœ]+)*", surface):
        for piece in _split_word(chunk, lexicon):
            tokens += 1
            if piece in lemmas:
                hit = piece
            elif piece in forms:
                hit = forms[piece]
            else:
                hit = next((c for c in resolver.candidates(piece)[1:] if c in lemmas), None)
            if hit is None:
                missing.append(piece)
                hit = piece
            if hit not in out:
                out.append(hit)
    return out, missing, tokens


def build_expressions(
    source: dict[str, Any],
    lemmas: dict[str, Any],
    forms: dict[str, str],
    elisions: dict[str, str],
    atomic: set[str],
    resolver: Resolver,
    warn: Any,
) -> dict[str, dict[str, Any]]:
    """``{sub_band: {kind: ["surface", "surface …", "surface [fam]"]}}``.

    ``…`` marks a variable slot (``variable: true``): dropped from the key at
    either edge, kept as `` … `` inside it;
    ``[fam]`` / ``[sout]`` set the register.
    """

    out: dict[str, dict[str, Any]] = {}
    missing_all: Counter[str] = Counter()
    duplicates: list[str] = []
    single: list[str] = []
    for sub_band in SUB_BANDS:
        groups = source["expressions"].get(sub_band) or {}
        for kind in EXPRESSION_KINDS:
            for raw in groups.get(kind) or []:
                text = fold(raw)
                register = None
                if text.endswith("[fam]"):
                    register, text = "familier", text[:-5]
                elif text.endswith("[sout]"):
                    register, text = "soutenu", text[:-6]
                text = re.sub(r"\s*[?!,]\s*", " ", text)
                variable = "…" in text
                # An edge slot is dropped from the key («avoir besoin de …» →
                # «avoir besoin de»); an inner one stays («avoir … ans»).
                key = " ".join(text.replace("…", " … ").split()).strip("… ").strip()
                if not key:
                    continue
                if key in out:
                    duplicates.append(key)
                    continue
                components, missing, tokens = _expression_lemmas(key, lemmas, forms, elisions, atomic, resolver)
                if tokens < 2:
                    single.append(key)
                    continue
                missing_all.update(missing)
                out[key] = {
                    "band": band_of(sub_band),
                    "sub_band": sub_band,
                    "kind": kind,
                    "register": register,
                    "lemmas": components,
                    "variable": variable,
                }
        for kind in groups:
            if kind not in EXPRESSION_KINDS:
                raise SystemExit(f"expressions: bad kind {kind!r} in {sub_band}")
    if duplicates:
        warn(f"duplicate expressions (first kept): {duplicates}")
    if single:
        warn(f"one-word expressions skipped (they are lemmas): {single}")
    if missing_all:
        warn(f"expression components not in the lexicon: {dict(sorted(missing_all.items()))}")
    return out


def apply_glosses(lemmas: dict[str, Any], expressions: dict[str, Any], warn: Any) -> None:
    """Merge ``glosses_src.json`` into each lemma and expression as ``gloss: {en, de}``.

    A missing gloss is a warning, not an error, so the lexicon still builds while
    new entries wait for their gloss. Glosses for keys no longer in the lexicon
    are reported too."""
    if not GLOSSES_PATH.exists():
        warn("glosses_src.json not found: no `gloss` fields written")
        return
    source = json.loads(GLOSSES_PATH.read_text(encoding="utf-8"))
    for section, rows in (("lemmas", lemmas), ("expressions", expressions)):
        glosses = source.get(section) or {}
        missing = []
        for key, row in rows.items():
            gloss = glosses.get(key)
            if not gloss or not str(gloss.get("en") or "").strip() or not str(gloss.get("de") or "").strip():
                missing.append(key)
                continue
            row["gloss"] = {"en": gloss["en"].strip(), "de": gloss["de"].strip()}
        if missing:
            warn(f"{section} without a gloss ({len(missing)}): {missing[:20]}")
        unused = sorted(set(glosses) - set(rows))
        if unused:
            warn(f"glosses_src.json {section} not in the lexicon ({len(unused)}): {unused[:20]}")


def provenance(base: dict[str, str]) -> dict[str, str]:
    out = dict(base)
    out["summary"] = (
        "Curated French core lexicon A1.1 → C1.2. `rank` is global list order (A1 first, C1 last) and is "
        "a coarse frequency proxy only; `freq_rank` is the corpus rank from the owner's frequency deck "
        "where the lemma is in its 5,000 words."
    )
    out["v3"] = (
        "Built 2026-10-03 (content program L-1) by scripts/build_lexicon_v3.py: v2 kept as the A1–B1 "
        "base with defects fixed (compound numerals flagged `numeral`, X-cent/X-cents merged, hyphenated "
        "pseudo-phrases and d'accord/d'ailleurs moved to `expressions`, re-banding); every word of the "
        "owner's «Französisch 5000» Anki export (rank 1-5000) banded by rank blended with curricular "
        "overrides; B2/C1 lemmas beyond the deck and the `expressions` map authored for this repository."
    )
    out["deck"] = (
        "Anki_cards___2025-11-01T13-09-36.csv («Französisch 5000»). Per decision D1 only factual data is "
        "used: frequency rank (`freq_rank`), lemma, part of speech, gender read from the article, and IPA "
        "(`ipa`). The deck's German glosses and example sentences are third-party text of unknown licence "
        "and are not copied."
    )
    out["forms_v3"] = (
        "Forms of new lemmas generated from conjugation templates (Verbiste data via mlconjug3, MIT) and "
        "regular noun/adjective rules, then filtered so only forms the suffix rules in "
        "app/services/lexical_coverage.py cannot resolve are stored (the v2 convention)."
    )
    out["expressions"] = (
        "Authored multiword expressions keyed by canonical lowercase surface; `lemmas` are the component "
        "lemmas resolved against this lexicon; `variable` marks an open slot."
    )
    out["glosses"] = (
        "`gloss: {en, de}` on every lemma and expression: short learner glosses authored for this "
        "repository (content program L-2, app/data/lexical/glosses_src.json). Nothing is copied from the "
        "deck or any third-party dictionary (D1)."
    )
    out["licence"] = (
        "Curated for this repository; free to redistribute with it. Deck-derived fields are rank order, "
        "part of speech, gender and IPA only (D1)."
    )
    return out


def stats(lemmas: dict[str, Any], expressions: dict[str, Any]) -> dict[str, Any]:
    per_sub = Counter(row["sub_band"] for row in lemmas.values() if not row["numeral"])
    numerals = Counter(row["sub_band"] for row in lemmas.values() if row["numeral"])
    cumulative: dict[str, int] = {}
    running = 0
    for band in BANDS:
        running += sum(count for sub, count in per_sub.items() if sub.startswith(band))
        cumulative[band] = running
    return {
        "lemmas": len(lemmas),
        "per_sub_band": {sub: per_sub[sub] for sub in SUB_BANDS},
        "numerals": dict(numerals),
        "cumulative_non_numeral": cumulative,
        "source": dict(Counter(row["source"] for row in lemmas.values())),
        "pos": dict(Counter(row["pos"] for row in lemmas.values())),
        "register": dict(Counter(row["register"] for row in lemmas.values() if row["register"])),
        "expressions": len(expressions),
        "expressions_per_band": dict(Counter(row["band"] for row in expressions.values())),
        "expressions_per_kind": dict(Counter(row["kind"] for row in expressions.values())),
        "glossed": {
            "lemmas": sum(1 for row in lemmas.values() if row.get("gloss")),
            "expressions": sum(1 for row in expressions.values() if row.get("gloss")),
        },
    }


def dump(payload: dict[str, Any]) -> str:
    """Indented at the top, one line per lemma / form / expression: a 7,000-word
    file stays diffable without running to 80,000 lines."""

    def line(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(", ", ": "))

    parts = ["{"]
    keys = list(payload)
    for index, key in enumerate(keys):
        value = payload[key]
        comma = "," if index < len(keys) - 1 else ""
        if isinstance(value, dict) and key in {"lemmas", "forms", "expressions", "provenance", "elisions"}:
            parts.append(f" {line(key)}: {{")
            items = list(value.items())
            for inner, (name, entry) in enumerate(items):
                inner_comma = "," if inner < len(items) - 1 else ""
                parts.append(f"  {line(name)}: {line(entry)}{inner_comma}")
            parts.append(f" }}{comma}")
        else:
            parts.append(f" {line(key)}: {line(value)}{comma}")
    parts.append("}")
    return "\n".join(parts) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", type=Path, default=None, help="read the v2 lexicon from this file")
    parser.add_argument("--check", action="store_true", help="build and report, do not write")
    args = parser.parse_args()
    payload, report = build(load_base(args.base))
    for line in report.pop("warnings"):
        print("warning:", line)
    print(json.dumps(report, ensure_ascii=False, indent=1))
    if not args.check:
        OUT.write_text(dump(payload), encoding="utf-8")
        print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
