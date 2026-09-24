"""WP-S2 — La Forge's item bank: variety without waiting.

Every A1–A2 unit of the v2 syllabus has *generative templates* in
``app/data/grammar_templates/`` (``units_*.json``), filled from a small
morphological lexicon (``lexicon.json``: nouns with gender and plural,
adjectives with their four forms and position, verbs with their conjugation
tables) and from the world bible's cast and places. A template is a French
frame with slots and exactly one *target* — the rule-carrying span — written
``[[right // wrong // wrong]]``::

    "fr": "{S} [[{S|v:être} // {S|v_x:être}]] {A|agree:S}."

Rendering a frame yields one :class:`BankItem`: the sentence, its target span,
the trap forms and the ✗ sentences they make, an English gloss and a scene for
production prompts. Every rung of the séance is posed from that one item,
in the payload shapes the frontend already renders (fill, classify — a ✓/✗
judgement or a minimal pair —, word bank with the trap as a spare chip,
transform «fix the ✗», and guided production), with the answer key alongside
(``correct_answer`` / ``expected_answer``, ``accepted_answers``,
``target_span``) so grading can stay local.

No LLM is involved: an item is rendered in microseconds, so a séance starts
without waiting. The variety guarantee (no sentence twice in a session, none
within seven days for the same learner, never the rule card's own example) is
kept by the caller through :func:`fingerprint` and the ``exclude`` set.

Template syntax, in full:

``{X}``            the slot's French surface (``entry["fr"]``)
``{X.key}``        a field of the slot's entry
``{X|filter:a:b}`` a morphological filter; an argument naming a bound slot is
                   passed as that slot's entry (``{A|agree:N}``)
``[[a // b // c]]`` the target: ``a`` is right, the others are traps (a filter
                   ending in ``_x`` returns a list of traps)

Slots are declared per unit (``"slots"``) and per frame, as
``pool[:tag,!tag][@SLOT]``: ``noun:food``, ``adj@N`` (an adjective that suits
N), ``comp@V`` (a complement of the bound verb V), ``pron:!1s``.
"""
from __future__ import annotations

import hashlib
import json
import random
import re
import unicodedata
from collections import Counter
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field, replace
from functools import cached_property, lru_cache
from pathlib import Path
from typing import Any

from app.services import item_semantics as semantics

TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "data" / "grammar_templates"
ITEM_BANK_VERSION = "forge-bank-1"

#: Days during which a learner never sees the same sentence twice.
VARIETY_WINDOW_DAYS = 7

# --------------------------------------------------------------------------- #
# Text helpers
# --------------------------------------------------------------------------- #

_H_ASPIRE = frozenset(
    {
        "haricot", "haricots", "hibou", "héros", "hall", "huit", "hache", "haut", "hauteur",
        "honte", "hamburger", "hockey", "handball", "hasard", "housse", "hangar", "homard",
    }
)
_VOWEL = re.compile(r"^[aeiouyàâäéèêëîïôöùûüœæh]", re.IGNORECASE)


def starts_with_vowel(text: str) -> bool:
    word = re.split(r"[\s'’-]", str(text or "").strip().lower(), maxsplit=1)[0]
    if not word or word in _H_ASPIRE:
        return False
    return bool(_VOWEL.match(word))


def elide(word: str, following: str) -> str:
    """``word`` + ``following`` with French elision (je aime → j'aime)."""

    following = following.strip()
    if " " in word.strip():
        head, _, last = word.strip().rpartition(" ")
        return f"{head} {elide(last, following)}"
    lowered = word.lower()
    if lowered in {"je", "me", "te", "se", "le", "la", "ne", "de", "que", "jusque", "lorsque", "puisque"} and starts_with_vowel(following):
        return f"{word[:-1]}'{following}"
    if lowered == "si" and re.match(r"^ils?\b", following, re.IGNORECASE):
        return f"{word[:-1]}'{following}"
    return f"{word} {following}"


_ELIDING = r"(je|me|te|se|le|la|ne|de|que|jusque|lorsque|puisque)"


def tidy_french(text: str) -> str:
    """Contractions and elisions over free text (never over a target).

    The target is replaced by a sentinel before this runs, so a trap such as
    «à le cinéma» survives and a frame author puts every joint the rule is
    about inside the target.
    """

    out = f" {text} "
    out = re.sub(r"\s+", " ", out)
    out = re.sub(r"(?i)(?<=[\s(])à les ", lambda m: "aux " if m.group(0)[0].islower() else "Aux ", out)
    out = re.sub(r"(?<=[\s(])à le ", "au ", out)
    out = re.sub(r"(?<=[\s(])À le ", "Au ", out)
    out = re.sub(r"(?<=[\s(])de les ", "des ", out)
    out = re.sub(r"(?<=[\s(])De les ", "Des ", out)
    out = re.sub(r"(?<=[\s(])de le ", "du ", out)
    out = re.sub(r"(?<=[\s(])De le ", "Du ", out)

    def _elide(match: re.Match[str]) -> str:
        word, following = match.group(1), match.group(2)
        if not starts_with_vowel(following):
            return match.group(0)
        return f"{word[:-1]}'{following}"

    out = re.sub(rf"(?i)(?<=[\s(]){_ELIDING} ([\wàâäéèêëîïôöùûüœæ]+)", _elide, out)
    out = re.sub(r"(?i)(?<=[\s(])(si) (ils?)\b", lambda m: f"{m.group(1)[0]}'{m.group(2)}", out)
    return out.strip()


def finish_sentence(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([.,])", r"\1", text)
    text = re.sub(r"\s*([?!;:])", r" \1", text)
    text = re.sub(r"\s+", " ", text).strip()
    return capitalize_first(text)


def finish_english(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([.,?!:;])", r"\1", text)
    text = re.sub(r"([.?!]\s+)([a-z])", lambda match: match.group(1) + match.group(2).upper(), text)
    return capitalize_first(text)


def capitalize_first(text: str) -> str:
    for index, char in enumerate(text):
        if char.isalpha():
            return text[:index] + char.upper() + text[index + 1:]
    return text


def normalize(value: Any) -> str:
    """Accent- and case-folded comparison key (the séance grader's own fold)."""

    text = re.sub(r"[‘’‚‛′`´ʹʻʼ]", "'", "" if value is None else str(value)).strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"'\s+", "'", text)
    text = re.sub(r"[.!?;:,«»\"“”]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def fingerprint(sentence: str) -> str:
    """Stable id of a sentence for the variety guarantee (case/accents/punctuation folded)."""

    return hashlib.sha256(normalize(sentence).encode("utf-8")).hexdigest()[:24]


def contains_phrase(haystack: str, needle: str) -> bool:
    """Is ``needle`` a whole-word run inside ``haystack`` (both folded)?"""

    hay, pin = normalize(haystack), normalize(needle)
    if not pin:
        return False
    return re.search(rf"(?:^|[\s']){re.escape(pin)}(?:$|[\s'])", hay) is not None


# --------------------------------------------------------------------------- #
# Morphology
# --------------------------------------------------------------------------- #

PERSON_KEYS = ("1s", "2s", "3s", "1p", "2p", "3p")
_IMPARFAIT = ("ais", "ais", "ait", "ions", "iez", "aient")
_FUTUR = ("ai", "as", "a", "ons", "ez", "ont")
_REFLEXIVE = ("me", "te", "se", "nous", "vous", "se")
_TRAP_PERSONS = {0: (1, 2), 1: (2, 0), 2: (1, 5), 3: (4, 2), 4: (3, 2), 5: (2, 3)}
_ENGLISH_BE = {"1s": ("am", "was"), "2": ("are", "were"), "3s": ("is", "was"), "1p": ("are", "were"), "3p": ("are", "were")}


def _regular_er(inf: str) -> list[str]:
    stem = inf[:-2]
    nous_stem = stem + "e" if stem.endswith("g") else (stem[:-1] + "ç" if stem.endswith("c") else stem)
    return [stem + "e", stem + "es", stem + "e", nous_stem + "ons", stem + "ez", stem + "ent"]


class Morph:
    """Conjugation over the lexicon's verb entries."""

    def __init__(self, verbs: dict[str, dict[str, Any]]) -> None:
        self.verbs = verbs

    def verb(self, key: str | dict[str, Any]) -> dict[str, Any]:
        if isinstance(key, dict):
            return key
        return self.verbs[key]

    def present(self, verb: str | dict[str, Any], person: int) -> str:
        entry = self.verb(verb)
        table = entry.get("pres") or _regular_er(entry["inf"])
        return table[person]

    def imparfait(self, verb: str | dict[str, Any], person: int) -> str:
        entry = self.verb(verb)
        if entry["inf"] == "être":
            stem = "ét"
        else:
            stem = self.present(entry, 3)[:-3]
        ending = _IMPARFAIT[person]
        if ending.startswith("i") and stem.endswith("ge"):
            stem = stem[:-1]
        if ending.startswith("i") and stem.endswith("ç"):
            stem = stem[:-1] + "c"
        return stem + ending

    def future_stem(self, verb: str | dict[str, Any]) -> str:
        entry = self.verb(verb)
        if entry.get("fut"):
            return entry["fut"]
        inf = entry["inf"]
        return inf[:-1] if inf.endswith("re") else inf

    def futur(self, verb: str | dict[str, Any], person: int) -> str:
        return self.future_stem(verb) + _FUTUR[person]

    def conditionnel(self, verb: str | dict[str, Any], person: int) -> str:
        return self.future_stem(verb) + _IMPARFAIT[person]

    def participle(self, verb: str | dict[str, Any], gender: str = "m", plural: bool = False, agree: bool | None = None) -> str:
        entry = self.verb(verb)
        pp = entry["pp"]
        if agree is None:
            agree = self.aux(entry) == "être"
        if not agree:
            return pp
        suffix = ("e" if gender == "f" else "") + ("s" if plural and not pp.endswith("s") else "")
        if gender == "f" and plural and pp.endswith("s"):
            suffix = "es"
        return pp + suffix

    def aux(self, verb: str | dict[str, Any]) -> str:
        entry = self.verb(verb)
        return "être" if entry.get("pron") else entry.get("aux", "avoir")

    def form(self, verb: str | dict[str, Any], tense: str, person: int) -> str:
        if tense == "present":
            return self.present(verb, person)
        if tense == "imparfait":
            return self.imparfait(verb, person)
        if tense == "futur":
            return self.futur(verb, person)
        if tense == "conditionnel":
            return self.conditionnel(verb, person)
        raise KeyError(tense)


# --------------------------------------------------------------------------- #
# Lexicon and templates
# --------------------------------------------------------------------------- #


def _read_json(name: str) -> Any:
    with (TEMPLATE_DIR / name).open(encoding="utf-8") as handle:
        return json.load(handle)


def _number_words() -> dict[int, str]:
    units = ["zéro", "un", "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf", "dix", "onze", "douze",
             "treize", "quatorze", "quinze", "seize", "dix-sept", "dix-huit", "dix-neuf"]
    tens = {20: "vingt", 30: "trente", 40: "quarante", 50: "cinquante", 60: "soixante"}
    words: dict[int, str] = dict(enumerate(units))
    for ten, name in tens.items():
        words[ten] = name
        for unit in range(1, 10):
            words[ten + unit] = f"{name} et un" if unit == 1 else f"{name}-{units[unit]}"
    for n in range(70, 80):
        words[n] = "soixante et onze" if n == 71 else f"soixante-{words[n - 60]}"
    words[80] = "quatre-vingts"
    for n in range(81, 100):
        words[n] = f"quatre-vingt-{words[n - 80]}"
    for hundred in range(1, 10):
        base = "cent" if hundred == 1 else f"{units[hundred]} cents"
        words[hundred * 100] = base
        for rest in range(1, 100):
            head = "cent" if hundred == 1 else f"{units[hundred]} cent"
            words[hundred * 100 + rest] = f"{head} {words[rest]}"
    return words


NUMBER_WORDS = _number_words()


def _number_traps(n: int) -> list[str]:
    """Structural misspellings of a number (never a different number)."""

    word = NUMBER_WORDS[n]
    traps: list[str] = []
    if n < 100:
        tens, unit = divmod(n, 10)
        if 11 <= n <= 16:
            traps.append("dix-" + NUMBER_WORDS[n - 10])
        if 17 <= n <= 19:
            traps.append(word.replace("-", " "))
        if 20 <= n <= 69 and unit == 1:
            traps.extend([word.replace(" et un", "-un"), word.replace(" et un", " un")])
        elif 20 <= n <= 69 and unit > 1:
            base = NUMBER_WORDS[tens * 10]
            traps.extend([f"{base} et {NUMBER_WORDS[unit]}", f"{base} {NUMBER_WORDS[unit]}"])
        if n == 70:
            traps.extend(["septante", "soixante et dix"])
        if 71 <= n <= 79:
            rest = NUMBER_WORDS[n - 70]
            traps.extend(["soixante-dix-un" if n == 71 else f"soixante-dix-{rest}", "septante et un" if n == 71 else f"septante-{rest}"])
        if n == 80:
            traps.extend(["quatre-vingt", "huitante"])
        if 81 <= n <= 99:
            traps.append(word.replace("quatre-vingt-", "quatre-vingts-"))
            traps.append("nonante" + (f"-{NUMBER_WORDS[n - 90]}" if n > 90 else "") if n >= 90 else word.replace("quatre-vingt-", "quatre-vingt "))
    else:
        hundred, rest = divmod(n, 100)
        if hundred == 1:
            traps.append("un " + word)
        if rest == 0 and hundred > 1:
            traps.append(word[:-1])
        if rest and hundred > 1:
            traps.append(word.replace(" cent ", " cents ", 1))
        if rest:
            for rest_trap in _number_traps(rest)[:1]:
                traps.append(word[: len(word) - len(NUMBER_WORDS[rest])] + rest_trap)
    return [trap for trap in dict.fromkeys(traps) if trap and trap != word]


@dataclass
class Lexicon:
    pools: dict[str, list[dict[str, Any]]]
    verbs: dict[str, dict[str, Any]]
    morph: Morph

    def pool(self, name: str) -> list[dict[str, Any]]:
        if name not in self.pools:
            raise KeyError(f"unknown template pool {name!r}")
        return self.pools[name]


def _subject_entries(raw: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    pronouns = [dict(entry, kind="person", tags=list(entry.get("tags") or []) + ["pron"]) for entry in raw["pronouns"]]
    cast = [dict(entry, p=2, n="s", kind="person", tags=list(entry.get("tags") or []) + ["cast"]) for entry in raw["cast"]]
    pairs = [dict(entry, p=5, n="p", kind="person", tags=list(entry.get("tags") or []) + ["pair"]) for entry in raw["cast_pairs"]]
    return pronouns, cast, pairs


@lru_cache(maxsize=1)
def lexicon() -> Lexicon:
    raw = _read_json("lexicon.json")
    verbs = {entry["id"]: dict(entry) for entry in raw["verbs"]}
    for entry in verbs.values():
        entry.setdefault("fr", entry["inf"])
        entry.setdefault("tags", [])
        for comp in entry.get("comps") or []:
            tags = list(comp.get("tags") or [])
            # An indefinite or partitive object turns into «de» after a
            # negation (pas de, plus de): negation frames never take one.
            if re.match(r"^(?:un|une|des|du|de la|de l'|d')\b", comp.get("fr", "")) or re.match(r"^(?:de l'|d')", comp.get("fr", "")):
                tags.append("indef")
            comp["tags"] = tags
    pronouns, cast, pairs = _subject_entries(raw)
    nouns = [dict(entry) for entry in raw["nouns"]]
    for entry in nouns:
        entry.setdefault("tags", [])
        entry.setdefault("n", "s")
    pools: dict[str, list[dict[str, Any]]] = {
        "pron": pronouns,
        "cast": cast,
        "pair": pairs,
        "subj": pronouns + cast + pairs,
        "person3": cast + pairs,
        "noun": nouns,
        "adj": [dict(entry) for entry in raw["adjectives"]],
        "verb": list(verbs.values()),
        "num": [
            {"id": f"n{n}", "fr": NUMBER_WORDS[n], "digits": str(n), "value": n, "x": _number_traps(n),
             "tags": (["small"] if n < 70 else ["big"]) + (["age"] if 18 <= n <= 69 else [])}
            for n in [*range(2, 70), *range(70, 100), *range(100, 1000, 10)]
        ],
    }
    for name, entries in (raw.get("pools") or {}).items():
        pools[name] = [dict(entry) for entry in entries]
    for entries in pools.values():
        for index, entry in enumerate(entries):
            entry.setdefault("id", f"{entry.get('fr', index)}")
            entry.setdefault("tags", [])
    return Lexicon(pools=pools, verbs=verbs, morph=Morph(verbs))


@lru_cache(maxsize=1)
def unit_templates() -> dict[str, dict[str, Any]]:
    units: dict[str, dict[str, Any]] = {}
    for path in sorted(TEMPLATE_DIR.glob("units_*.json")):
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)
        for unit_id, spec in data.items():
            if unit_id.startswith("_"):
                continue
            units[unit_id] = spec
    return units


def template_units() -> list[str]:
    return sorted(unit_templates())


# --------------------------------------------------------------------------- #
# Filters
# --------------------------------------------------------------------------- #


class RenderError(ValueError):
    """A frame cannot be rendered with these bindings; the sampler skips it."""


def _person(entry: dict[str, Any]) -> int:
    if "p" not in entry:
        raise RenderError(f"slot {entry.get('id')} is not a subject")
    return int(entry["p"])


def _plural(entry: dict[str, Any]) -> bool:
    return entry.get("n") == "p"


def _gender(entry: dict[str, Any]) -> str:
    return "f" if entry.get("g") == "f" else "m"


def _en_person(entry: dict[str, Any]) -> str:
    if entry.get("en_p"):
        return entry["en_p"]
    return {0: "1s", 1: "2", 2: "3s", 3: "1p", 4: "2", 5: "3p"}[_person(entry)]


def _noun_plural(entry: dict[str, Any]) -> str:
    if entry.get("pl"):
        return entry["pl"]
    word = entry["fr"]
    if word.endswith(("s", "x", "z")):
        return word
    if word.endswith(("eau", "au", "eu")):
        return word + "x"
    if word.endswith("al"):
        return word[:-2] + "aux"
    head, sep, tail = word.partition(" ")
    return (head + "s" + sep + tail) if sep else word + "s"


def _en_article(noun_en: str) -> str:
    return ("an " if re.match(r"^[aeiou]", noun_en, re.IGNORECASE) and not noun_en.lower().startswith(("uni", "euro", "one")) else "a ") + noun_en


def _def(entry: dict[str, Any], plural: bool = False) -> str:
    if plural:
        return "les " + _noun_plural(entry)
    if entry.get("proper_article") is not None:
        article = entry["proper_article"]
        return (article + " " + entry["fr"]).strip()
    if starts_with_vowel(entry["fr"]):
        return "l'" + entry["fr"]
    return ("la " if _gender(entry) == "f" else "le ") + entry["fr"]


def _def_x(entry: dict[str, Any], plural: bool = False) -> list[str]:
    word = entry["fr"]
    if plural:
        return ["le " + _noun_plural(entry) if _gender(entry) == "m" else "la " + _noun_plural(entry), "les " + word]
    if starts_with_vowel(word):
        return ["le " + word if _gender(entry) == "m" else "la " + word, "la " + word if _gender(entry) == "m" else "le " + word]
    return ["le " + word if _gender(entry) == "f" else "la " + word, "les " + word]


def _indef(entry: dict[str, Any], plural: bool = False) -> str:
    if plural:
        return "des " + _noun_plural(entry)
    return ("une " if _gender(entry) == "f" else "un ") + entry["fr"]


def _indef_x(entry: dict[str, Any], plural: bool = False) -> list[str]:
    if plural:
        return [("une " if _gender(entry) == "f" else "un ") + _noun_plural(entry), "de " + _noun_plural(entry) if not starts_with_vowel(entry["fr"]) else "d'" + _noun_plural(entry)]
    return [("un " if _gender(entry) == "f" else "une ") + entry["fr"], "des " + entry["fr"]]


def _partitive(entry: dict[str, Any]) -> str:
    word = entry["fr"]
    if starts_with_vowel(word):
        return "de l'" + word
    return ("de la " if _gender(entry) == "f" else "du ") + word


def _partitive_x(entry: dict[str, Any]) -> list[str]:
    word = entry["fr"]
    if starts_with_vowel(word):
        return ["du " + word, "de la " + word if _gender(entry) == "f" else "de le " + word]
    if _gender(entry) == "f":
        return ["du " + word, "de " + word]
    return ["de le " + word, "de la " + word]


def _dem(entry: dict[str, Any], plural: bool = False) -> str:
    if plural:
        return "ces " + _noun_plural(entry)
    if _gender(entry) == "f":
        return "cette " + entry["fr"]
    return ("cet " if starts_with_vowel(entry["fr"]) else "ce ") + entry["fr"]


def _dem_x(entry: dict[str, Any], plural: bool = False) -> list[str]:
    word = entry["fr"]
    if plural:
        return ["cette " + _noun_plural(entry) if _gender(entry) == "f" else "ce " + _noun_plural(entry)]
    if _gender(entry) == "f":
        return ["ce " + word, "cet " + word if starts_with_vowel(word) else "ces " + word]
    if starts_with_vowel(word):
        return ["ce " + word, "cette " + word]
    return ["cette " + word, "cet " + word]


def _prep_de(entry: dict[str, Any], plural: bool = False) -> str:
    if plural:
        return "des " + _noun_plural(entry)
    if entry.get("proper_article") == "":
        return ("d'" if starts_with_vowel(entry["fr"]) else "de ") + entry["fr"]
    if starts_with_vowel(entry["fr"]) and entry.get("proper_article") is None:
        return "de l'" + entry["fr"]
    return ("de la " if _gender(entry) == "f" else "du ") + entry["fr"]


def _prep_de_x(entry: dict[str, Any], plural: bool = False) -> list[str]:
    word = entry["fr"]
    if plural:
        return ["de les " + _noun_plural(entry), "du " + _noun_plural(entry)]
    if starts_with_vowel(word):
        return ["du " + word, "de le " + word if _gender(entry) == "m" else "de la " + word]
    if _gender(entry) == "f":
        return ["du " + word, "de " + word]
    return ["de le " + word, "de la " + word]


def _prep_a(entry: dict[str, Any], plural: bool = False) -> str:
    if plural:
        return "aux " + _noun_plural(entry)
    if entry.get("proper_article") == "":
        return "à " + entry["fr"]
    if starts_with_vowel(entry["fr"]):
        return "à l'" + entry["fr"]
    return ("à la " if _gender(entry) == "f" else "au ") + entry["fr"]


def _prep_a_x(entry: dict[str, Any], plural: bool = False) -> list[str]:
    word = entry["fr"]
    if plural:
        return ["à les " + _noun_plural(entry), "au " + _noun_plural(entry)]
    if starts_with_vowel(word):
        return ["au " + word, "à le " + word if _gender(entry) == "m" else "à la " + word]
    if _gender(entry) == "f":
        return ["au " + word, "à le " + word]
    return ["à le " + word, "à la " + word]


_POSSESSIVES = {
    # person -> (masc/vowel, fem, plural)
    0: ("mon", "ma", "mes"),
    1: ("ton", "ta", "tes"),
    2: ("son", "sa", "ses"),
    3: ("notre", "notre", "nos"),
    4: ("votre", "votre", "vos"),
    5: ("leur", "leur", "leurs"),
}


def _poss(noun: dict[str, Any], owner: dict[str, Any], plural: bool = False) -> str:
    masc, fem, many = _POSSESSIVES[_person(owner)]
    if plural:
        return f"{many} {_noun_plural(noun)}"
    if _gender(noun) == "f" and not starts_with_vowel(noun["fr"]):
        return f"{fem} {noun['fr']}"
    return f"{masc} {noun['fr']}"


def _poss_x(noun: dict[str, Any], owner: dict[str, Any], plural: bool = False) -> list[str]:
    masc, fem, many = _POSSESSIVES[_person(owner)]
    word = noun["fr"]
    if plural:
        return [f"{fem if _gender(noun) == 'f' else masc} {_noun_plural(noun)}", f"{many} {word}" if many != "leurs" else f"leur {_noun_plural(noun)}"]
    if _gender(noun) == "f" and starts_with_vowel(word):
        return [f"{fem} {word}", f"{many} {word}"]
    if _gender(noun) == "f":
        return [f"{masc} {word}", f"{many} {word}"]
    return [f"{fem} {word}", f"{many} {word}"]


def _adj_form(adj: dict[str, Any], gender: str, plural: bool) -> str:
    key = ("fp" if gender == "f" else "mp") if plural else ("f" if gender == "f" else "m")
    if key == "m":
        return adj["m"]
    if key in adj:
        return adj[key]
    base = adj["m"]
    if key == "f":
        return base if base.endswith("e") else base + "e"
    if key == "mp":
        return base if base.endswith(("s", "x")) else base + "s"
    return _adj_form(adj, "f", False) + "s"


def _neg_word(word: Any) -> str:
    if isinstance(word, dict):
        word = word.get("fr", "pas")
    word = str(word or "pas")
    return "" if word == "_" else word


def _en_poss(owner: dict[str, Any]) -> str:
    if owner.get("en_poss"):
        return owner["en_poss"]
    person = _en_person(owner)
    if person == "3s":
        return "her" if _gender(owner) == "f" else "his"
    return {"1s": "my", "2": "your", "1p": "our", "3p": "their"}[person]


def _en_obj(entry: dict[str, Any]) -> str:
    if entry.get("en_obj"):
        return entry["en_obj"]
    person = _person(entry)
    if person == 2:
        return "her" if _gender(entry) == "f" else "him"
    return {0: "me", 1: "you", 3: "us", 4: "you", 5: "them"}[person]


_TONIC = {0: "moi", 1: "toi", 3: "nous", 4: "vous"}


def _tonic(entry: dict[str, Any]) -> str:
    person = _person(entry)
    if person in _TONIC:
        return _TONIC[person]
    if person == 2:
        return "elle" if _gender(entry) == "f" else "lui"
    return "elles" if _gender(entry) == "f" else "eux"


class Filters:
    """The template filters, bound to one lexicon."""

    def __init__(self, lex: Lexicon) -> None:
        self.lex = lex
        self.morph = lex.morph

    # -- verbs ----------------------------------------------------------------
    def _verb(self, ref: Any) -> dict[str, Any]:
        if isinstance(ref, dict):
            if "inf" in ref:
                return ref
            if ref.get("verb"):
                return self.lex.verbs[ref["verb"]]
            raise RenderError("slot is not a verb")
        try:
            return self.lex.verbs[str(ref)]
        except KeyError as exc:
            raise RenderError(f"unknown verb {ref}") from exc

    def conj(self, subject: dict[str, Any], verb: Any, tense: str = "present") -> str:
        """The finite verb chunk after the subject (reflexive included, no subject)."""

        entry = self._verb(verb)
        person = _person(subject)
        if tense in {"pc", "pc_avoir", "pc_etre", "pc_noagree"}:
            aux_key = {"pc_avoir": "avoir", "pc_etre": "être"}.get(tense, self.morph.aux(entry))
            aux = self.morph.present(aux_key, person)
            agree = aux_key == "être" and tense != "pc_noagree"
            pp = self.morph.participle(entry, _gender(subject), _plural(subject), agree=agree)
            chunk = f"{aux} {pp}"
        else:
            chunk = self.morph.form(entry, tense, person)
        if entry.get("pron"):
            chunk = elide(_REFLEXIVE[person], chunk)
        return chunk

    def v(self, subject: dict[str, Any], verb: Any, tense: str = "present") -> str:
        return self.conj(subject, verb, tense)

    def v_x(self, subject: dict[str, Any], verb: Any, tense: str = "present") -> list[str]:
        right = self.conj(subject, verb, tense)
        traps: list[str] = []
        person = _person(subject)
        entry = self._verb(verb)
        if tense == "present":
            for extra in (entry.get("pres_x") or {}).get(str(person), []):
                traps.append(elide(_REFLEXIVE[person], extra) if entry.get("pron") else extra)
        for other in _TRAP_PERSONS[person]:
            fake = dict(subject, p=other, n="p" if other >= 3 else "s")
            candidate = self.conj(fake, entry, tense)
            if normalize(candidate) != normalize(right):
                traps.append(candidate)
        if entry.get("pron"):
            wrong_reflexive = _REFLEXIVE[(person + 2) % 6] if _REFLEXIVE[(person + 2) % 6] != _REFLEXIVE[person] else "se"
            if wrong_reflexive == _REFLEXIVE[person]:
                wrong_reflexive = "me"
            bare = self.conj(dict(subject), dict(entry, pron=False), tense)
            traps.append(elide(wrong_reflexive, bare))
        return traps

    def sv(self, subject: dict[str, Any], verb: Any, tense: str = "present") -> str:
        """Subject + verb with elision: j'aime, je me lève, Marin arrive."""

        return elide(subject["fr"], self.conj(subject, verb, tense)) if subject["fr"].lower() == "je" else f"{subject['fr']} {self.conj(subject, verb, tense)}"

    def sv_x(self, subject: dict[str, Any], verb: Any, tense: str = "present") -> list[str]:
        traps = [
            elide(subject["fr"], chunk) if subject["fr"].lower() == "je" else f"{subject['fr']} {chunk}"
            for chunk in self.v_x(subject, verb, tense)
        ]
        right = self.conj(subject, verb, tense)
        if subject["fr"].lower() == "je" and starts_with_vowel(right):
            traps.append(f"je {right}")
        return traps

    def sv_etre(self, subject: dict[str, Any], verb: Any, tense: str = "present") -> list[str]:
        """Trap: the chunk with être (for avoir-uses such as age)."""

        forms = self.conj(subject, "être", tense)
        return [elide(subject["fr"], forms) if subject["fr"].lower() == "je" else f"{subject['fr']} {forms}"]

    def neg(self, subject: dict[str, Any], verb: Any, tense: str = "present", word: str = "pas") -> str:
        """ne + verb + pas (after the subject): «ne parle pas», «n'aime pas», «ne me lève pas».

        ``word`` is pas / plus / jamais / rien / personne (or a slot holding one);
        ``_`` means none at all (Personne ne vient).
        """

        word = _neg_word(word)
        entry = self._verb(verb)
        person = _person(subject)
        if tense in {"pc", "pc_avoir", "pc_etre"}:
            aux_key = {"pc_avoir": "avoir", "pc_etre": "être"}.get(tense, self.morph.aux(entry))
            aux = self.morph.present(aux_key, person)
            pp = self.morph.participle(entry, _gender(subject), _plural(subject), agree=aux_key == "être")
            head = elide(_REFLEXIVE[person], aux) if entry.get("pron") else aux
            if word == "personne":
                return f"{elide('ne', head)} {pp} personne"
            return re.sub(r"\s+", " ", f"{elide('ne', head)} {word} {pp}")
        form = self.morph.form(entry, tense, person)
        head = elide(_REFLEXIVE[person], form) if entry.get("pron") else form
        return f"{elide('ne', head)} {word}".strip()

    def neg_x(self, subject: dict[str, Any], verb: Any, tense: str = "present", word: str = "pas") -> list[str]:
        word = _neg_word(word)
        entry = self._verb(verb)
        person = _person(subject)
        if tense in {"pc", "pc_avoir", "pc_etre"}:
            aux_key = {"pc_avoir": "avoir", "pc_etre": "être"}.get(tense, self.morph.aux(entry))
            aux = self.morph.present(aux_key, person)
            pp = self.morph.participle(entry, _gender(subject), _plural(subject), agree=aux_key == "être")
            head = elide(_REFLEXIVE[person], aux) if entry.get("pron") else aux
            if word == "personne":
                return [f"{elide('ne', head)} personne {pp}", f"{elide('ne', head)} pas {pp} personne", f"{head} {pp} personne"]
            if not word:
                return [f"{head} {pp}", f"{elide('ne', head)} pas {pp}"]
            traps = [f"{elide('ne', head)} {pp} {word}", f"ne {word} {head} {pp}"]
            if starts_with_vowel(head):
                traps.append(f"ne {head} {word} {pp}")
            if word != "pas":
                traps.insert(0, f"{elide('ne', head)} pas {word} {pp}")
            return traps
        form = self.morph.form(entry, tense, person)
        head = elide(_REFLEXIVE[person], form) if entry.get("pron") else form
        if not word:
            return [head, f"{elide('ne', head)} pas"]
        traps = [f"ne {word} {head}", f"{head} {word}"]
        if starts_with_vowel(head):
            traps.insert(0, f"ne {head} {word}")
        if word != "pas":
            traps.insert(0, f"{elide('ne', head)} pas {word}")
        return traps

    def inf(self, verb: Any) -> str:
        entry = self._verb(verb)
        if entry.get("pron"):
            return elide("se", entry["inf"])
        return entry["inf"]

    def inf_refl(self, verb: Any, subject: dict[str, Any]) -> str:
        """An infinitive whose reflexive pronoun follows the subject (je vais me lever)."""

        entry = self._verb(verb)
        if entry.get("pron"):
            return elide(_REFLEXIVE[_person(subject)], entry["inf"])
        return entry["inf"]

    def pp(self, verb: Any, agree_with: dict[str, Any] | None = None) -> str:
        entry = self._verb(verb)
        if agree_with is None:
            return entry["pp"]
        return self.morph.participle(entry, _gender(agree_with), _plural(agree_with), agree=True)

    def pp_x(self, verb: Any, agree_with: dict[str, Any] | None = None) -> list[str]:
        entry = self._verb(verb)
        traps = list(entry.get("pp_x") or [])
        traps.append(entry["inf"])
        if agree_with is not None:
            traps.insert(0, entry["pp"])
        return traps

    def fut_x(self, subject: dict[str, Any], verb: Any) -> list[str]:
        entry = self._verb(verb)
        person = _person(subject)
        traps = [self.morph.conditionnel(entry, person)]
        stem_trap = entry.get("fut_x")
        if stem_trap:
            traps.insert(0, stem_trap + _FUTUR[person])
        for other in _TRAP_PERSONS[person][:1]:
            traps.append(self.morph.futur(entry, other))
        prefix = "" if not entry.get("pron") else _REFLEXIVE[person] + " "
        return [elide(prefix.strip(), trap) if prefix else trap for trap in traps]

    def sfut_x(self, subject: dict[str, Any], verb: Any) -> list[str]:
        return [elide(subject["fr"], trap) if subject["fr"].lower() == "je" else f"{subject['fr']} {trap}" for trap in self.fut_x(subject, verb)]

    def imp_x(self, subject: dict[str, Any], verb: Any) -> list[str]:
        entry = self._verb(verb)
        person = _person(subject)
        traps: list[str] = []
        for other in _TRAP_PERSONS[person]:
            candidate = self.morph.imparfait(entry, other)
            if normalize(candidate) != normalize(self.morph.imparfait(entry, person)):
                traps.append(candidate)
        if entry.get("imp_x"):
            traps.insert(0, entry["imp_x"] + _IMPARFAIT[person])
        return traps

    def simp_x(self, subject: dict[str, Any], verb: Any) -> list[str]:
        return [elide(subject["fr"], trap) if subject["fr"].lower() == "je" else f"{subject['fr']} {trap}" for trap in self.imp_x(subject, verb)]

    def imperative(self, verb: Any, person: str = "2s") -> str:
        entry = self._verb(verb)
        if person == "2p":
            return self.morph.present(entry, 4)
        if person == "1p":
            return self.morph.present(entry, 3)
        if entry.get("imp2"):
            return entry["imp2"]
        form = self.morph.present(entry, 1)
        if entry["inf"].endswith("er") and form.endswith("es"):
            return form[:-1]
        return form

    def imperative_x(self, verb: Any, person: str = "2s") -> list[str]:
        entry = self._verb(verb)
        right = self.imperative(entry, person)
        traps = []
        if person == "2s":
            tu_form = self.morph.present(entry, 1)
            if tu_form != right:
                traps.append(tu_form)
            elif right.endswith("s"):
                traps.append(right[:-1])
            traps.append("tu " + tu_form)
        else:
            traps.append(("vous " if person == "2p" else "nous ") + right)
            traps.append(entry["inf"])
        return [trap for trap in traps if normalize(trap) != normalize(right)]

    # -- English --------------------------------------------------------------
    def _en_forms(self, verb: Any) -> list[str]:
        entry = self._verb(verb)
        forms = entry.get("en")
        if not forms:
            raise RenderError(f"verb {entry['inf']} has no English")
        return forms

    def en_sv(self, subject: dict[str, Any], verb: Any, tense: str = "present") -> str:
        who = subject.get("en") or subject["fr"]
        return f"{who} {self.en_v(subject, verb, tense)}"

    def en_v(self, subject: dict[str, Any], verb: Any, tense: str = "present") -> str:
        if isinstance(tense, dict):
            tense = tense.get("en_mode") or "present"
        entry = self._verb(verb)
        person = _en_person(subject)
        third = person == "3s"
        be_now, be_past = _ENGLISH_BE[person]
        if entry["inf"] == "être" and tense in {"present", "neg", "q", "pc", "imparfait", "imp", "used"}:
            if tense == "present":
                return be_now
            if tense == "neg":
                return f"{be_now} not"
            if tense == "q":
                return be_now
            return be_past
        base, s3, past, pp, ing = self._en_forms(entry)
        have = "has" if third else "have"
        do = "does" if third else "do"
        if tense == "present":
            return s3 if third else base
        if tense == "neg":
            return f"{do} not {base}"
        if tense == "q":
            return base  # the frame writes «Do you …?» itself
        if tense == "pc":
            return past
        if tense == "pc_neg":
            return f"did not {base}"
        if tense in {"imparfait", "prog_past"}:
            return f"{be_past} {ing}"
        if tense == "used":
            return f"used to {base}"
        if tense == "futur":
            return f"will {base}"
        if tense == "futur_neg":
            return f"will not {base}"
        if tense == "near":
            return f"{be_now} going to {base}"
        if tense == "near_neg":
            return f"{be_now} not going to {base}"
        if tense == "perfect_prog":
            return f"{have} been {ing}"
        if tense == "cond":
            return f"would {base}"
        if tense == "recent":
            return f"{have} just {pp}"
        if tense == "prog":
            return f"{be_now} {ing}"
        if tense == "perfect":
            return f"{have} {pp}"
        if tense == "can":
            return f"can {base}"
        if tense == "cannot":
            return f"cannot {base}"
        if tense == "want":
            return f"{'wants' if third else 'want'} to {base}"
        if tense == "must":
            return f"{'has' if third else 'have'} to {base}"
        if tense == "should":
            return f"should {base}"
        if tense == "base":
            return base
        if tense == "ing":
            return ing
        if tense == "past_participle":
            return pp
        if tense == "never":
            return f"never {s3 if third else base}"
        if tense == "no_longer":
            return f"{do} not {base} anymore"
        raise RenderError(f"unknown English tense {tense}")

    def en_svc(self, subject: dict[str, Any], verb: Any, comp: Any, tense: str = "present") -> str:
        """Subject + verb + complement in English; a complement may bring its own verb («go cycling»)."""

        who = subject.get("en") or subject["fr"]
        return f"{who} {self.en_vc(subject, verb, comp, tense)}"

    def en_vc(self, subject: dict[str, Any], verb: Any, comp: Any, tense: str = "present") -> str:
        entry = self._verb(verb)
        if isinstance(comp, dict) and comp.get("en_forms"):
            entry = {"inf": "_", "en": comp["en_forms"]}
        obj = ""
        if isinstance(comp, dict):
            obj = comp.get("en_obj") if comp.get("en_obj") is not None else comp.get("en", "")
        mode = tense.get("en_mode") if isinstance(tense, dict) else tense
        if mode == "no_longer":
            return f"{self.en_v(subject, entry, 'neg')} {obj} anymore".replace("  ", " ").strip()
        return f"{self.en_v(subject, entry, tense)} {obj}".strip()

    def en_do(self, subject: dict[str, Any]) -> str:
        return "does" if _en_person(subject) == "3s" else "do"

    def en_be(self, subject: dict[str, Any], tense: str = "present") -> str:
        now, past = _ENGLISH_BE[_en_person(subject)]
        return past if tense == "past" else now

    def en_have(self, subject: dict[str, Any]) -> str:
        return "has" if _en_person(subject) == "3s" else "have"

    def en_poss(self, owner: dict[str, Any]) -> str:
        return _en_poss(owner)

    def en_obj(self, entry: dict[str, Any]) -> str:
        return _en_obj(entry)

    def en_it(self, noun: dict[str, Any]) -> str:
        if noun.get("kind") == "person":
            return "her" if _gender(noun) == "f" else "him"
        return "them" if _plural(noun) else "it"

    # -- nouns ----------------------------------------------------------------
    def def_(self, noun: dict[str, Any], number: str = "s") -> str:
        return _def(noun, number == "p")

    def def_x(self, noun: dict[str, Any], number: str = "s") -> list[str]:
        return _def_x(noun, number == "p")

    def indef(self, noun: dict[str, Any], number: str = "s") -> str:
        return _indef(noun, number == "p")

    def indef_x(self, noun: dict[str, Any], number: str = "s") -> list[str]:
        return _indef_x(noun, number == "p")

    def part(self, noun: dict[str, Any]) -> str:
        return _partitive(noun)

    def part_x(self, noun: dict[str, Any]) -> list[str]:
        return _partitive_x(noun)

    def dem(self, noun: dict[str, Any], number: str = "s") -> str:
        return _dem(noun, number == "p")

    def dem_x(self, noun: dict[str, Any], number: str = "s") -> list[str]:
        return _dem_x(noun, number == "p")

    def a(self, noun: dict[str, Any], number: str = "s") -> str:
        return _prep_a(noun, number == "p" or _plural(noun))

    def a_x(self, noun: dict[str, Any], number: str = "s") -> list[str]:
        return _prep_a_x(noun, number == "p" or _plural(noun))

    def de(self, noun: dict[str, Any], number: str = "s") -> str:
        return _prep_de(noun, number == "p" or _plural(noun))

    def de_x(self, noun: dict[str, Any], number: str = "s") -> list[str]:
        return _prep_de_x(noun, number == "p" or _plural(noun))

    def q(self, noun: dict[str, Any], number: str | None = None) -> str:
        """After a quantity or a negation: de/d' + noun (plural when countable)."""

        tags = noun.get("tags", [])
        word = _noun_plural(noun) if "count" in tags and "mass" not in tags and number != "s" else noun["fr"]
        return ("d'" if starts_with_vowel(word) else "de ") + word

    def q_x(self, noun: dict[str, Any]) -> list[str]:
        count = "count" in noun.get("tags", []) and "mass" not in noun.get("tags", [])
        word = _noun_plural(noun) if count else noun["fr"]
        if count:
            return ["des " + word, "de les " + word]
        return [_partitive(noun), "de " + word if starts_with_vowel(word) else ("de la " + word if _gender(noun) == "m" else "du " + word)]

    def pl(self, noun: dict[str, Any]) -> str:
        return _noun_plural(noun)

    def poss(self, noun: dict[str, Any], owner: dict[str, Any], number: str = "s") -> str:
        return _poss(noun, owner, number == "p")

    def poss_x(self, noun: dict[str, Any], owner: dict[str, Any], number: str = "s") -> list[str]:
        return _poss_x(noun, owner, number == "p")

    def cod(self, noun: dict[str, Any]) -> str:
        """The direct-object pronoun standing for the noun (before a consonant)."""

        if _plural(noun):
            return "les"
        return "la" if _gender(noun) == "f" else "le"

    def en_(self, noun: dict[str, Any], mode: str = "bare") -> str:
        word = noun.get("en") or noun["fr"]
        if mode == "the":
            return word if noun.get("en_proper") else f"the {word}"
        if mode == "a":
            return _en_article(word)
        if mode == "pl":
            return noun.get("en_pl") or (word + "s")
        if mode == "the_pl":
            return "the " + (noun.get("en_pl") or (word + "s"))
        if mode == "some":
            return f"some {word}"
        if mode == "any":
            return f"any {word}"
        if mode == "q":
            tags = noun.get("tags", [])
            return (noun.get("en_pl") or (word + "s")) if "count" in tags and "mass" not in tags else word
        if mode == "this":
            return f"this {word}"
        if mode == "these":
            return "these " + (noun.get("en_pl") or (word + "s"))
        return word

    # -- adjectives -----------------------------------------------------------
    def agree(self, adj: dict[str, Any], head: dict[str, Any], number: str | None = None) -> str:
        plural = _plural(head) if number is None else number == "p"
        return _adj_form(adj, _gender(head), plural)

    def agree_x(self, adj: dict[str, Any], head: dict[str, Any], number: str | None = None) -> list[str]:
        plural = _plural(head) if number is None else number == "p"
        right = _adj_form(adj, _gender(head), plural)
        order = [("m", False), ("f", False), ("m", True), ("f", True)]
        preferred = [
            ("m" if _gender(head) == "f" else "f", plural),
            (_gender(head), not plural),
        ] + order
        traps: list[str] = []
        for gender, many in preferred:
            candidate = _adj_form(adj, gender, many)
            if normalize(candidate) != normalize(right) and candidate not in traps:
                traps.append(candidate)
        return traps

    def agree_pre(self, adj: dict[str, Any], head: dict[str, Any], number: str | None = None) -> str:
        """Before the noun: bel / nouvel / vieil in front of a masculine vowel."""

        plural = _plural(head) if number is None else number == "p"
        if not plural and _gender(head) == "m" and adj.get("m_v") and starts_with_vowel(head.get("fr", "")):
            return adj["m_v"]
        return _adj_form(adj, _gender(head), plural)

    def agree_pre_x(self, adj: dict[str, Any], head: dict[str, Any], number: str | None = None) -> list[str]:
        right = self.agree_pre(adj, head, number)
        plural = _plural(head) if number is None else number == "p"
        traps = []
        if adj.get("m_v") and right == adj["m_v"]:
            traps.extend([adj["m"], _adj_form(adj, "f", False)])
        traps.extend(self.agree_x(adj, head, number))
        return [trap for trap in dict.fromkeys(traps) if normalize(trap) != normalize(right)] or [_adj_form(adj, "f" if _gender(head) == "m" else "m", plural)]

    def en_comp(self, adj: dict[str, Any]) -> str:
        return adj.get("en_comp") or f"more {adj.get('en')}"

    def en_sup(self, adj: dict[str, Any]) -> str:
        return adj.get("en_sup") or f"the most {adj.get('en')}"

    def gn(self, entry: dict[str, Any], head: dict[str, Any]) -> str:
        """A variant chosen by the head's gender/number (keys m, f, mp, fp; fr fallback)."""

        key = ("fp" if _gender(head) == "f" else "mp") if _plural(head) else ("f" if _gender(head) == "f" else "m")
        for candidate in (key, key[0], "m", "fr"):
            if entry.get(candidate):
                return entry[candidate]
        raise RenderError("no gendered variant")

    # -- people ---------------------------------------------------------------
    def tonic(self, entry: dict[str, Any]) -> str:
        return _tonic(entry)

    def ilelle(self, entry: dict[str, Any]) -> str:
        if _plural(entry):
            return "elles" if _gender(entry) == "f" else "ils"
        return "elle" if _gender(entry) == "f" else "il"

    def after(self, entry: dict[str, Any], word: str) -> str:
        """``word`` + the slot's French with elision: «qu'il», «que je», «s'il»."""

        return elide(word, entry["fr"])

    # -- clause builders ------------------------------------------------------
    def _subject_join(self, subject: dict[str, Any], chunk: str) -> str:
        if subject["fr"].lower() == "je":
            return elide("je", chunk)
        return f"{subject['fr']} {chunk}"

    def after_sv(self, subject: dict[str, Any], word: str, verb: Any, tense: str = "present") -> str:
        """``word`` + subject + verb with every elision: «parce qu'il aime», «parce que j'aime»."""

        return elide(word, self.sv(subject, verb, tense))

    def estceque(self, subject: dict[str, Any]) -> str:
        return elide("est-ce que", subject["fr"])

    def estceque_x(self, subject: dict[str, Any]) -> list[str]:
        traps = [f"est-ce qui {subject['fr']}"]
        if starts_with_vowel(subject["fr"]):
            traps.insert(0, f"est-ce que {subject['fr']}")
        else:
            traps.append(f"qu'est-ce que {subject['fr']}")
        return traps

    def inv(self, subject: dict[str, Any], verb: Any) -> str:
        form = self.morph.present(self._verb(verb), _person(subject))
        pronoun = subject["fr"]
        if _person(subject) == 2 and form[-1:] in {"e", "a"}:
            return f"{form}-t-{pronoun}"
        return f"{form}-{pronoun}"

    def inv_x(self, subject: dict[str, Any], verb: Any) -> list[str]:
        form = self.morph.present(self._verb(verb), _person(subject))
        pronoun = subject["fr"]
        traps = []
        if _person(subject) == 2 and form[-1:] in {"e", "a"}:
            traps.append(f"{form}-{pronoun}")
        traps.append(f"{pronoun} {form}-{pronoun}")
        traps.append(f"{form} {pronoun}")
        return traps

    def _cod(self, noun: dict[str, Any], number: str | None = None) -> str:
        plural = _plural(noun) if number is None else number == "p"
        if plural:
            return "les"
        return "la" if _gender(noun) == "f" else "le"

    def sv_cod(self, subject: dict[str, Any], verb: Any, noun: dict[str, Any], tense: str = "present") -> str:
        """Subject + direct-object pronoun + verb: «je la regarde», «je l'aime», «je l'ai achetée»."""

        entry = self._verb(verb)
        cod = self._cod(noun)
        person = _person(subject)
        if tense == "pc":
            aux = self.morph.present("avoir", person)
            pp = self.morph.participle(entry, _gender(noun), _plural(noun), agree=True)
            return self._subject_join(subject, f"{elide(cod, aux)} {pp}")
        return self._subject_join(subject, elide(cod, self.morph.present(entry, person)))

    def sv_cod_x(self, subject: dict[str, Any], verb: Any, noun: dict[str, Any], tense: str = "present") -> list[str]:
        entry = self._verb(verb)
        cod = self._cod(noun)
        person = _person(subject)
        if tense == "pc":
            aux = self.morph.present("avoir", person)
            agreed = self.morph.participle(entry, _gender(noun), _plural(noun), agree=True)
            traps = [
                self._subject_join(subject, f"{aux} {elide(cod, agreed)}"),
                self._subject_join(subject, f"{aux} {agreed} {cod}"),
            ]
            if agreed != entry["pp"]:
                traps.append(self._subject_join(subject, f"{elide(cod, aux)} {entry['pp']}"))
            return traps
        form = self.morph.present(entry, person)
        traps = [self._subject_join(subject, f"{form} {cod}"), self._subject_join(subject, f"lui {form}" if cod != "les" else f"leur {form}")]
        if cod in {"le", "la"}:
            other = "la" if cod == "le" else "le"
            traps.append(self._subject_join(subject, elide(other, form)))
        if starts_with_vowel(form):
            traps.insert(0, f"{subject['fr']} {cod} {form}")
        return traps

    def sv_coi(self, subject: dict[str, Any], verb: Any, target: dict[str, Any], number: str | None = None) -> str:
        plural = _plural(target) if number is None else number == "p"
        pronoun = "leur" if plural else "lui"
        return self._subject_join(subject, f"{pronoun} {self.morph.present(self._verb(verb), _person(subject))}")

    def sv_coi_x(self, subject: dict[str, Any], verb: Any, target: dict[str, Any], number: str | None = None) -> list[str]:
        plural = _plural(target) if number is None else number == "p"
        form = self.morph.present(self._verb(verb), _person(subject))
        if plural:
            return [self._subject_join(subject, f"leurs {form}"), self._subject_join(subject, f"les {form}"), self._subject_join(subject, f"{form} leur")]
        cod = "la" if _gender(target) == "f" else "le"
        return [self._subject_join(subject, elide(cod, form)), self._subject_join(subject, f"{form} lui"), self._subject_join(subject, f"leur {form}")]

    def sv_y(self, subject: dict[str, Any], verb: Any) -> str:
        return self._subject_join(subject, f"y {self.morph.present(self._verb(verb), _person(subject))}")

    def sv_y_x(self, subject: dict[str, Any], verb: Any) -> list[str]:
        form = self.morph.present(self._verb(verb), _person(subject))
        traps = [self._subject_join(subject, f"{form} y"), self._subject_join(subject, f"en {form}")]
        if subject["fr"].lower() == "je":
            traps.append(f"je y {form}")
        return traps

    def sv_en(self, subject: dict[str, Any], verb: Any) -> str:
        return self._subject_join(subject, f"en {self.morph.present(self._verb(verb), _person(subject))}")

    def de_inf(self, verb: Any, subject: dict[str, Any] | None = None) -> str:
        return elide("de", self.inf_refl(verb, subject) if subject else self.inf(verb))

    def de_conj(self, verb: Any, subject: dict[str, Any]) -> str:
        return f"de {self.conj(subject, verb)}"

    def cod_inf(self, noun: dict[str, Any], verb: Any) -> str:
        return elide(self._cod(noun), self.inf(verb))

    def imp_cod(self, verb: Any, noun: dict[str, Any], person: str = "2s") -> str:
        return f"{self.imperative(verb, person)}-{self._cod(noun)}"

    def imp_cod_x(self, verb: Any, noun: dict[str, Any], person: str = "2s") -> list[str]:
        form = self.imperative(verb, person)
        cod = self._cod(noun)
        return [f"{elide(cod, form)}", f"{form} {cod}"]

    def neg_imp(self, verb: Any, noun: dict[str, Any], person: str = "2s") -> str:
        return f"ne {elide(self._cod(noun), self.imperative(verb, person))} pas"

    def neg_imp_x(self, verb: Any, noun: dict[str, Any], person: str = "2s") -> list[str]:
        form = self.imperative(verb, person)
        cod = self._cod(noun)
        return [f"ne {form} pas {cod}", f"ne {form}-{cod} pas"]

    # -- determiners and pronouns --------------------------------------------
    def art_def(self, entry: dict[str, Any]) -> str:
        if _plural(entry):
            return "les"
        return "la" if _gender(entry) == "f" else "le"

    def art_def_x(self, entry: dict[str, Any]) -> list[str]:
        right = self.art_def(entry)
        return [item for item in ("le", "la", "les") if item != right]

    def art_indef(self, noun: dict[str, Any]) -> str:
        return "une" if _gender(noun) == "f" else "un"

    def quel(self, noun: dict[str, Any], number: str = "s") -> str:
        forms = {("m", False): "quel", ("f", False): "quelle", ("m", True): "quels", ("f", True): "quelles"}
        return forms[(_gender(noun), number == "p")]

    def quel_x(self, noun: dict[str, Any], number: str = "s") -> list[str]:
        right = self.quel(noun, number)
        return [form for form in ("quel", "quelle", "quels", "quelles") if form != right][:2]

    def with_prep(self, entry: dict[str, Any], prep: Any) -> str:
        word = prep.get("fr") if isinstance(prep, dict) else str(prep)
        return elide(str(word), _tonic(entry))

    def with_prep_x(self, entry: dict[str, Any], prep: Any) -> list[str]:
        word = prep.get("fr") if isinstance(prep, dict) else str(prep)
        return [f"{word} {trap}" for trap in self.tonic_x(entry)]

    def de_tonic(self, entry: dict[str, Any]) -> str:
        """«de» + the stressed pronoun, elided: «à côté d'elle», «près de moi»."""

        return elide("de", _tonic(entry))

    def de_tonic_x(self, entry: dict[str, Any]) -> list[str]:
        return [elide("de", trap) for trap in self.tonic_x(entry)]

    def en_qty(self, qty: dict[str, Any], noun: dict[str, Any]) -> str:
        """«too much» / «too many»: the quantity's English for a mass or a count noun."""

        tags = noun.get("tags", [])
        count = "count" in tags and "mass" not in tags
        return str((qty.get("en_count") if count else None) or qty.get("en") or "")

    def en_all(self, noun: dict[str, Any]) -> str:
        """«tout le projet» is the whole project; «toute la limonade» all the lemonade."""

        word = noun.get("en") or noun["fr"]
        tags = noun.get("tags", [])
        return f"the whole {word}" if "count" in tags and "mass" not in tags else f"all the {word}"

    def tonic_x(self, entry: dict[str, Any]) -> list[str]:
        person = _person(entry)
        if person == 0:
            return ["je", "me"]
        if person == 1:
            return ["tu", "te"]
        if person == 2:
            return ["la", "il"] if _gender(entry) == "f" else ["il", "le"]
        if person == 5:
            return ["les", "ils"] if _gender(entry) == "f" else ["ils", "les"]
        raise RenderError("no tonic trap for nous/vous")

    def tout(self, noun: dict[str, Any], number: str = "s") -> str:
        if number == "p":
            return ("toutes les " if _gender(noun) == "f" else "tous les ") + _noun_plural(noun)
        if starts_with_vowel(noun["fr"]):
            return ("toute l'" if _gender(noun) == "f" else "tout l'") + noun["fr"]
        return ("toute la " if _gender(noun) == "f" else "tout le ") + noun["fr"]

    def tout_x(self, noun: dict[str, Any], number: str = "s") -> list[str]:
        word = noun["fr"]
        if number == "p":
            plural = _noun_plural(noun)
            return [f"tout les {plural}", f"toutes les {plural}"] if _gender(noun) == "m" else [f"tous les {plural}", f"toute les {plural}"]
        if starts_with_vowel(word):
            return [f"toute l'{word}", f"tous l'{word}"] if _gender(noun) == "m" else [f"tout l'{word}", f"toutes l'{word}"]
        return [f"toute le {word}", f"tous le {word}"] if _gender(noun) == "m" else [f"tout la {word}", f"toutes la {word}"]

    def tous(self, entry: dict[str, Any]) -> str:
        return "toutes" if _gender(entry) == "f" else "tous"

    def tous_x(self, entry: dict[str, Any]) -> list[str]:
        return ["tous", "tout"] if _gender(entry) == "f" else ["tout", "toutes"]

    def celui(self, noun: dict[str, Any], number: str = "s") -> str:
        forms = {("m", False): "celui", ("f", False): "celle", ("m", True): "ceux", ("f", True): "celles"}
        return forms[(_gender(noun), number == "p")]

    def celui_x(self, noun: dict[str, Any], number: str = "s") -> list[str]:
        right = self.celui(noun, number)
        order = {"celui": ["celle", "ceux"], "celle": ["celui", "celles"], "ceux": ["celles", "celui"], "celles": ["ceux", "celle"]}
        return order[right]

    def meilleur(self, noun: dict[str, Any], number: str = "s") -> str:
        return "meilleur" + ("e" if _gender(noun) == "f" else "") + ("s" if number == "p" else "")

    def meilleur_x(self, noun: dict[str, Any], number: str = "s") -> list[str]:
        bon = "bonne" if _gender(noun) == "f" else "bon"
        return ["mieux", f"plus {bon}{'s' if number == 'p' else ''}"]

    def bon(self, noun: dict[str, Any]) -> str:
        return "bonne" if _gender(noun) == "f" else "bon"

    def un_gn(self, job: dict[str, Any], head: dict[str, Any]) -> str:
        form = job.get("f") if _gender(head) == "f" else job.get("m")
        return ("une " if _gender(head) == "f" else "un ") + str(form)

    # -- more English ---------------------------------------------------------
    def en_pron(self, entry: dict[str, Any]) -> str:
        if _plural(entry):
            return "they"
        return "she" if _gender(entry) == "f" else "he"

    def en_job(self, job: dict[str, Any], head: dict[str, Any]) -> str:
        word = job.get("en_f") if _gender(head) == "f" and job.get("en_f") else job.get("en")
        return _en_article(str(word))

    def en_with(self, prep: dict[str, Any], person: dict[str, Any]) -> str:
        return str(prep.get("en") or "").format(poss=_en_poss(person), obj=_en_obj(person))

    def en_aadj(self, noun: dict[str, Any], adj: dict[str, Any]) -> str:
        return _en_article(f"{adj.get('en')} {noun.get('en')}")

    def en_cmp(self, adj: dict[str, Any], cmp: dict[str, Any]) -> str:
        kind = cmp.get("id") if isinstance(cmp, dict) else str(cmp)
        if kind == "moins":
            return f"less {adj.get('en')} than"
        if kind == "aussi":
            return f"as {adj.get('en')} as"
        return f"{self.en_comp(adj)} than"

    def en_imp(self, verb: Any, comp: Any = None) -> str:
        you = {"p": 1, "en_p": "2", "fr": "tu"}
        return self.en_vc(you, verb, comp or {}, "present")

    def en_imp_it(self, verb: Any, noun: dict[str, Any]) -> str:
        you = {"p": 1, "en_p": "2", "fr": "tu"}
        return f"{self.en_v(you, verb, 'present')} {self.en_it(noun)}"

    def en_v3(self, verb: Any, comp: Any = None, tense: str = "present") -> str:
        third = {"p": 2, "en_p": "3s", "fr": "il"}
        return self.en_vc(third, verb, comp or {}, tense)

    # -- misc -----------------------------------------------------------------
    def cap(self, entry: dict[str, Any], key: str = "fr") -> str:
        return capitalize_first(str(entry.get(key) or ""))

    def x(self, entry: dict[str, Any], key: str = "x") -> list[str]:
        value = entry.get(key)
        if isinstance(value, list):
            return list(value)
        if value:
            return [str(value)]
        raise RenderError(f"slot has no traps under {key}")


_FILTER_ALIASES = {"def": "def_", "en": "en_"}


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #

_SLOT_RE = re.compile(r"\{([A-Z][A-Z0-9]*)(?:\.([a-z_0-9]+))?(?:\|([^{}]+))?\}")
_TARGET_RE = re.compile(r"\[\[(.+?)\]\]")
_SENTINEL = "§§"


@dataclass(frozen=True)
class BankItem:
    unit: str
    frame_id: str
    sentence: str
    target: str
    traps: tuple[str, ...]
    wrong_sentences: tuple[str, ...]
    prefix: str
    suffix: str
    en: str
    scene: str
    accepted: tuple[str, ...] = ()
    lemmas: tuple[str, ...] = ()
    #: The form is chosen by meaning (parce que / mais, depuis / il y a):
    #: every prompt then carries the English meaning.
    gloss: bool = False
    #: WP-S5: what filled the slots, ``(slot, entry)``; the declared
    #: dependencies ``(slot, head slot)``; the frame's own time words. The
    #: naturalness checker (:mod:`app.services.item_semantics`) reads them.
    bindings: tuple[tuple[str, dict[str, Any]], ...] = field(default=(), compare=False, hash=False, repr=False)
    links: tuple[tuple[str, str], ...] = field(default=(), compare=False, hash=False, repr=False)
    frame_times: tuple[str, ...] = field(default=(), compare=False, hash=False, repr=False)
    #: WP-S5: the frame's coach line, when the sentence answers one.
    ask: dict[str, str] | None = field(default=None, compare=False, hash=False, repr=False)

    @cached_property
    def fingerprint(self) -> str:
        return fingerprint(self.sentence)


@dataclass
class _Frame:
    unit: str
    frame_id: str
    fr: str
    en: str
    slots: dict[str, str]
    scene: str | None
    accepted: list[str] = field(default_factory=list)
    weight: float = 1.0
    gloss: bool = False
    #: WP-S5: the time categories the frame's literal words carry
    #: («ce soir», «le samedi», «en train de»), so a slot never adds a clash.
    times: tuple[str, ...] = ()
    #: WP-S5: an optional coach line (``{"fr", "en"}``, with slots) the
    #: sentence answers — the free-use rung's two-line scene.
    ask: dict[str, str] | None = None


#: WP-S5: how much likelier a story entry (a cast member, a bible place, a
#: recurring object, «avec Lila») is than a generic one; an entry the
#: learner's own story has lately been about counts twice more.
STORY_WEIGHT = 4.0
STORY_FOCUS_WEIGHT = 2.0


def _story_weight(entry: dict[str, Any], story: frozenset[str]) -> float:
    weight = STORY_WEIGHT if semantics.is_story_entry(entry) else 1.0
    if story and (str(entry.get("id") or "").lower() in story or semantics.members(entry) & story):
        weight *= STORY_FOCUS_WEIGHT
    return weight


#: WP-S5: the share of a frame's items said *to* a cast member («J'ai
#: faim, Lila.», «Tu viens au Mistral, Gus ?»), when the frame names nobody
#: of the story itself. A line addressed to someone is still the learner's
#: own sentence — the pronoun the rule is about stays the subject.
VOCATIVE_SHARE = 0.6
_CAST_POOLS = frozenset({"cast", "person3", "pair", "subj"})


def _with_vocative(frame: _Frame) -> list[_Frame]:
    fr, en = frame.fr.rstrip(), frame.en.rstrip()
    pools = {spec.split("@")[0].split(":")[0] for spec in frame.slots.values()}
    eligible = (
        fr[-1:] in {".", "?", "!"}
        and en[-1:] in {".", "?", "!"}
        and not pools & _CAST_POOLS
        and not semantics.members({"fr": _literal_text(fr)})
        and "s'il vous plaît" not in fr
        and "s'il te plaît" not in fr
        # «Voici Lila. C'est …»: two statements, the scene is already there
        and not re.search(r"[.!]\s", _literal_text(fr[:-1]))
    )
    if not eligible:
        return [frame]

    def address(text: str) -> str | None:
        # A question and its answer: the name goes with the question
        # («Tu veux des poires, Lila ? Oui, j'en veux deux.»).
        question = text.find("?")
        if 0 < question < len(text) - 1:
            if "[[" in text[:question] and "]]" not in text[:question]:
                return None
            return f"{text[:question].rstrip()}, {{VOC}} {text[question:]}"
        return f"{text[:-1].rstrip()}, {{VOC}}{text[-1]}"

    fr_voc, en_voc = address(fr), address(en)
    if fr_voc is None or en_voc is None or any(spec.startswith("num:age") for spec in frame.slots.values()):
        return [frame]
    # Said to Lila, «tu» is Lila: the vocative agrees with a «tu» subject.
    subject = next(
        (
            slot
            for slot, spec in frame.slots.items()
            if spec.split(":")[0].split("@")[0] in {"pron", "state_tu"} and re.search(r"\{" + slot + r"[|.}]", fr)
        ),
        None,
    )
    plain = replace(frame, weight=frame.weight * (1 - VOCATIVE_SHARE))
    said_to = replace(
        frame,
        frame_id=f"{frame.frame_id}~voc",
        fr=fr_voc,
        en=en_voc,
        slots={**frame.slots, "VOC": f"cast@{subject}" if subject else "cast"},
        weight=frame.weight * VOCATIVE_SHARE,
    )
    return [plain, said_to]


def _literal_text(fr: str) -> str:
    """A frame's own words: slots and the target removed."""

    return _SLOT_RE.sub(" ", _TARGET_RE.sub(" ", fr))


class ItemBank:
    """Render and sample items from the templates of one unit."""

    def __init__(self, lex: Lexicon | None = None, templates: dict[str, dict[str, Any]] | None = None) -> None:
        self.lex = lex or lexicon()
        self.templates = templates if templates is not None else unit_templates()
        self.filters = Filters(self.lex)
        self._frames: dict[str, list[_Frame]] = {}
        #: WP-S5: rendered items per unit, and those the naturalness checker
        #: had to reject (by kind) — the source constraints should leave
        #: almost nothing for it.
        self.stats: dict[str, Counter[str]] = {}

    # -- frames ---------------------------------------------------------------
    def supports(self, unit: str) -> bool:
        return unit in self.templates

    def frames(self, unit: str) -> list[_Frame]:
        if unit in self._frames:
            return self._frames[unit]
        spec = self.templates[unit]
        defaults = dict(spec.get("slots") or {})
        frames = []
        for index, raw in enumerate(spec.get("frames") or []):
            frames.append(
                _Frame(
                    unit=unit,
                    frame_id=str(raw.get("id") or f"{unit.lower()}-{index + 1}"),
                    fr=raw["fr"],
                    en=raw["en"],
                    slots={**defaults, **(raw.get("slots") or {})},
                    scene=raw.get("scene") or spec.get("scene"),
                    accepted=list(raw.get("accepted") or []),
                    weight=float(raw.get("weight") or 1.0),
                    gloss=bool(raw.get("gloss", spec.get("gloss", False))),
                    times=(*(raw.get("times") or ()), *semantics.time_marks(_literal_text(raw["fr"]))),
                    ask=raw.get("ask") if isinstance(raw.get("ask"), dict) else None,
                )
            )
        frames = [twin for frame in frames for twin in _with_vocative(frame)]
        self._frames[unit] = frames
        return frames

    # -- slot binding ---------------------------------------------------------
    def _candidates(self, spec: str, bindings: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        dependency = None
        if "@" in spec:
            spec, dependency = spec.split("@", 1)
        name, _, tag_text = spec.partition(":")
        tags = [tag.strip() for tag in tag_text.split(",") if tag.strip()]
        if name == "comp":
            if not dependency or dependency not in bindings:
                raise RenderError("comp needs a bound verb")
            entries = [dict(entry, id=entry.get("id") or entry["fr"]) for entry in bindings[dependency].get("comps") or []]
        elif name == "obj":
            verb = bindings.get(dependency or "")
            kinds = set((verb or {}).get("obj") or [])
            entries = [entry for entry in self.lex.pool("noun") if entry.get("kind") in kinds or set(entry.get("tags", [])) & kinds]
        else:
            entries = self.lex.pool(name)
            if dependency:
                head = bindings.get(dependency)
                if head is None:
                    raise RenderError(f"slot depends on unbound {dependency}")
                features = {head.get("kind") or "person", *head.get("tags", [])}
                entries = [entry for entry in entries if features & set(entry.get("kinds") or features)]
        for tag in tags:
            if tag.startswith("!"):
                entries = [entry for entry in entries if tag[1:] not in entry.get("tags", []) and entry.get("id") != tag[1:]]
            elif tag.startswith("="):
                wanted = set(tag[1:].split("|"))
                entries = [entry for entry in entries if entry.get("id") in wanted]
            else:
                options = tag.split("|")
                entries = [
                    entry
                    for entry in entries
                    if any(option in entry.get("tags", []) or entry.get("kind") == option or entry.get("g") == option for option in options)
                ]
        return entries

    @staticmethod
    def _slot_order(slots: dict[str, str]) -> list[tuple[str, str]]:
        """Slots in dependency order: ``X@V`` after ``V``."""

        ordered: list[tuple[str, str]] = []
        pending = dict(slots)
        while pending:
            progressed = False
            for slot, spec in list(pending.items()):
                dependency = spec.split("@", 1)[1] if "@" in spec else None
                if dependency is None or dependency not in pending:
                    ordered.append((slot, spec))
                    del pending[slot]
                    progressed = True
            if not progressed:
                raise RenderError("circular slot dependencies")
        return ordered

    def _bind(
        self,
        frame: _Frame,
        rng: random.Random,
        known: frozenset[str],
        story: frozenset[str] = frozenset(),
    ) -> dict[str, dict[str, Any]]:
        bindings: dict[str, dict[str, Any]] = {}
        used_ids: dict[str, set[str]] = {}
        needs_comps = {spec.split("@", 1)[1] for spec in frame.slots.values() if spec.startswith("comp@")}
        for slot, spec in self._slot_order(frame.slots):
            if slot not in frame.fr and slot not in frame.en and not any(slot in value for value in frame.slots.values() if value != spec):
                continue
            entries = self._candidates(spec, bindings)
            if slot in needs_comps:
                entries = [entry for entry in entries if entry.get("comps")]
            pool_key = spec.split("@")[0].split(":")[0]
            taken = used_ids.setdefault(pool_key, set())
            entries = [entry for entry in entries if str(entry.get("id")) not in taken]
            # WP-S5: only what makes sense next to what is already bound —
            # a carrot at the market, a price that fits, one time of day.
            head = bindings.get(spec.split("@", 1)[1]) if "@" in spec else None
            entries = [
                entry
                for entry in entries
                if not semantics.time_conflict(frame.times, semantics.entry_marks(entry))
                and (head is None or semantics.link_clash(head, entry) is None)
                and all(semantics.pair_clash(entry, other) is None for other in bindings.values())
            ]
            if not entries:
                raise RenderError(f"no candidates for {slot} ({spec})")
            weights = [
                (3.0 if known and str(entry.get("lemma") or entry.get("fr") or "").lower() in known else 1.0)
                * _story_weight(entry, story)
                for entry in entries
            ]
            choice = rng.choices(entries, weights=weights, k=1)[0]
            bindings[slot] = choice
            taken.add(str(choice.get("id")))
        return bindings

    # -- expression rendering ---------------------------------------------------
    def _eval(self, match: re.Match[str], bindings: dict[str, dict[str, Any]], english: bool = False) -> str | list[str]:
        slot, key, filter_text = match.group(1), match.group(2), match.group(3)
        if slot not in bindings:
            raise RenderError(f"unbound slot {slot}")
        entry = bindings[slot]
        if key:
            value = entry.get(key)
            if value is None:
                raise RenderError(f"{slot} has no {key}")
            return value if isinstance(value, list) else str(value)
        if not filter_text:
            if english and entry.get("en") is not None:
                return str(entry.get("en"))
            return str(entry.get("fr") or "")
        name, *raw_args = filter_text.split(":")
        method = getattr(self.filters, _FILTER_ALIASES.get(name, name), None)
        if method is None:
            raise RenderError(f"unknown filter {name}")
        args: list[Any] = [bindings.get(arg, arg) for arg in raw_args]
        return method(entry, *args)

    def _render_text(self, text: str, bindings: dict[str, dict[str, Any]], english: bool = False) -> str:
        def replace(match: re.Match[str]) -> str:
            value = self._eval(match, bindings, english)
            if isinstance(value, list):
                raise RenderError("a trap filter outside a target")
            return value

        return _SLOT_RE.sub(replace, text)

    def _render_alternatives(self, text: str, bindings: dict[str, dict[str, Any]]) -> list[str]:
        """One target alternative, which may expand to several traps."""

        results = [""]
        position = 0
        for match in _SLOT_RE.finditer(text):
            literal = text[position:match.start()]
            value = self._eval(match, bindings)
            values = value if isinstance(value, list) else [value]
            results = [result + literal + str(item) for result in results for item in values]
            position = match.end()
        tail = text[position:]
        return [re.sub(r"\s+", " ", result + tail).strip() for result in results]

    def render(self, frame: _Frame, bindings: dict[str, dict[str, Any]]) -> BankItem:
        target_match = _TARGET_RE.search(frame.fr)
        if not target_match:
            raise RenderError(f"frame {frame.frame_id} has no target")
        parts = [part.strip() for part in target_match.group(1).split("//")]
        right_values = self._render_alternatives(parts[0], bindings)
        if len(right_values) != 1:
            raise RenderError("the right answer must be one form")
        right = right_values[0]
        traps: list[str] = []
        for part in parts[1:]:
            for trap in self._render_alternatives(part, bindings):
                if trap and normalize(trap) != normalize(right) and normalize(trap) not in {normalize(t) for t in traps}:
                    traps.append(trap)
        if not traps:
            raise RenderError("no trap differs from the answer")
        context = frame.fr[: target_match.start()] + f" {_SENTINEL} " + frame.fr[target_match.end():]
        context = tidy_french(self._render_text(context, bindings))
        before, _, after = context.partition(_SENTINEL)
        if re.search(r"[.?!]\s*$", before):
            right = capitalize_first(right)
            traps = [capitalize_first(trap) for trap in traps]
        sentence = finish_sentence(f"{before} {right} {after}")
        # Locate the (possibly capitalised) target inside the finished sentence.
        start = len(finish_sentence(f"{before} X")) - 1 if before.strip() else 0
        target = sentence[start: start + len(right)]
        if normalize(target) != normalize(right):
            raise RenderError("target not found in the sentence")
        prefix, suffix = sentence[:start], sentence[start + len(target):]
        wrong_sentences = []
        kept_traps = []
        for trap in traps:
            shown = capitalize_first(trap) if start == 0 or target[:1].isupper() else trap
            wrong = finish_sentence(f"{prefix}{shown}{suffix}")
            if normalize(wrong) == normalize(sentence):
                continue
            kept_traps.append(shown)
            wrong_sentences.append(wrong)
        if not kept_traps:
            raise RenderError("every trap folds onto the answer")
        english = finish_english(self._render_text(frame.en, bindings, english=True))
        scene = finish_english(self._render_text(frame.scene, bindings, english=True)) if frame.scene else ""
        accepted = [finish_sentence(tidy_french(self._render_text(alt, bindings))) for alt in frame.accepted]
        lemmas = tuple(
            str(entry.get("lemma") or entry.get("fr") or "").lower()
            for entry in bindings.values()
            if entry.get("fr")
        )
        return BankItem(
            unit=frame.unit,
            frame_id=frame.frame_id,
            sentence=sentence,
            target=target,
            traps=tuple(kept_traps),
            wrong_sentences=tuple(wrong_sentences),
            prefix=prefix,
            suffix=suffix,
            en=english,
            scene=scene,
            accepted=tuple(dict.fromkeys([sentence, *accepted])),
            lemmas=lemmas,
            gloss=frame.gloss,
            bindings=tuple(bindings.items()),
            links=tuple(
                (slot, spec.split("@", 1)[1]) for slot, spec in frame.slots.items() if "@" in spec and slot in bindings
            ),
            frame_times=frame.times,
            ask=self._render_ask(frame, bindings),
        )

    def _render_ask(self, frame: _Frame, bindings: dict[str, dict[str, Any]]) -> dict[str, str] | None:
        if not frame.ask:
            return None
        try:
            fr = finish_sentence(tidy_french(self._render_text(str(frame.ask.get("fr") or ""), bindings)))
            en = finish_english(self._render_text(str(frame.ask.get("en") or ""), bindings, english=True))
        except (RenderError, KeyError, IndexError):
            return None
        return {"fr": fr, "en": en} if fr else None

    # -- sampling -------------------------------------------------------------
    def sample(
        self,
        unit: str,
        rng: random.Random,
        *,
        exclude: Iterable[str] = (),
        known: Iterable[str] = (),
        detector: Any = None,
        story: Iterable[str] = (),
    ) -> Iterator[BankItem]:
        """Endless distinct items (by fingerprint) of one unit, skipping ``exclude``.

        ``detector`` is a callable(sentence) -> bool; an item whose sentence it
        rejects is never yielded. ``story`` (WP-S5) names lexicon ids and cast
        members the learner's story has lately been about; they are preferred.
        Every item passes the naturalness checker
        (:func:`app.services.item_semantics.violations`).
        """

        frames = self.frames(unit)
        if not frames:
            return
        seen = set(exclude)
        known_set = frozenset(word.lower() for word in known if word)
        story_set = frozenset(str(value).lower() for value in story if value)
        weights = [frame.weight for frame in frames]
        stats = self.stats.setdefault(unit, Counter())
        misses = 0
        while misses < 400:
            frame = rng.choices(frames, weights=weights, k=1)[0]
            try:
                item = self.render(frame, self._bind(frame, rng, known_set, story_set))
            except (RenderError, KeyError, IndexError):
                misses += 1
                continue
            stats["rendered"] += 1
            clashes = semantics.violations(item)
            if clashes:
                stats["rejected"] += 1
                for clash in clashes:
                    stats[f"rejected:{clash.kind}"] += 1
                misses += 1
                continue
            key = item.fingerprint
            if key in seen or (detector is not None and not detector(item.sentence)):
                misses += 1
                continue
            misses = 0
            seen.add(key)
            yield item

    def generate(
        self,
        unit: str,
        count: int,
        *,
        seed: Any = 0,
        exclude: Iterable[str] = (),
        known: Iterable[str] = (),
        detector: Any = None,
        story: Iterable[str] = (),
    ) -> list[BankItem]:
        rng = random.Random(str(seed))  # noqa: S311 - reproducible variety, not security
        items: list[BankItem] = []
        for item in self.sample(unit, rng, exclude=exclude, known=known, detector=detector, story=story):
            items.append(item)
            if len(items) >= count:
                break
        return items


@lru_cache(maxsize=1)
def default_bank() -> ItemBank:
    return ItemBank()


# --------------------------------------------------------------------------- #
# Units, detectors, v1 → v2
# --------------------------------------------------------------------------- #


@lru_cache(maxsize=1)
def _v2_rows() -> dict[str, dict[str, Any]]:
    from app.services.grammar_catalog import FRENCH_CORE_CATALOG_V2_VERSION, catalog_rows

    return {row["external_id"]: row for row in catalog_rows(FRENCH_CORE_CATALOG_V2_VERSION)}


def units_for_external_id(external_id: str | None) -> list[str]:
    """The v2 units with templates that stand for a concept (v2 id, or a v1 id via the mapping)."""

    from app.services.grammar_catalog import load_v1_to_v2_mapping

    external_id = str(external_id or "")
    bank = default_bank()
    if bank.supports(external_id):
        return [external_id]
    return [unit for unit in load_v1_to_v2_mapping().get(external_id, []) if bank.supports(unit)]


def unit_detector(unit: str):
    """A callable(sentence) -> bool for the unit's regex detector (None for llm detectors)."""

    row = _v2_rows().get(unit) or {}
    detector = (row.get("syllabus") or {}).get("detector") or {}
    if detector.get("kind") != "regex":
        return None
    pattern = re.compile(detector["pattern"], re.IGNORECASE)

    def matches(sentence: str) -> bool:
        return pattern.search(re.sub(r"[’ʼ‘]", "'", sentence)) is not None

    return matches


def unit_row(unit: str) -> dict[str, Any]:
    return _v2_rows().get(unit) or {}


def unit_band(unit: str) -> str:
    return str(unit_row(unit).get("level") or "A1")


# --------------------------------------------------------------------------- #
# Rung items (the séance's payload shapes)
# --------------------------------------------------------------------------- #

RUNG_TYPES: tuple[str, ...] = ("fill", "classify", "pair", "word_bank", "transform", "production")

_INSTRUCTIONS = {
    "forge.word_bank": "Build the sentence. One chip is not needed.",
    "forge.word_bank_all": "Build the sentence with the chips.",
    "forge.transform": "Correct the sentence: fix the part that breaks today's rule. Keep the rest.",
    "forge.sentence": "Write the sentence in French.",
    "forge.speak": "Say it aloud in French, then check the transcript.",
    "forge.conversation": "Answer the message in French, with the rule of the day.",
    "forge.scene": "Answer in French, with the rule of the day.",
}


#: WP-S6: the cue templates around a bank item, in the three chrome languages
#: (the séance's own words, `lib/language-rule.ts`). Only the ask and the
#: situation move: the meaning is the frame's English gloss (the bank has no
#: German or French frames), and the French sentences stay French. The English
#: column is exactly the `prompt` / `instruction` the item already carries.
_CUES: dict[str, dict[str, str]] = {
    "pair": {
        "en": 'Which sentence says: "{meaning}"',
        "de": "Welcher Satz bedeutet: „{meaning}“",
        "fr": "Quelle phrase veut dire : « {meaning} »",
    },
    "transform_gloss": {
        "en": 'Correct the sentence so that it means: "{meaning}"',
        "de": "Korrigiere den Satz, sodass er bedeutet: „{meaning}“",
        "fr": "Corrigez la phrase pour qu’elle veuille dire : « {meaning} »",
    },
    "say": {
        "en": '{scene} Say in French: "{meaning}"',
        "de": "{scene} Sag auf Französisch: „{meaning}“",
        "fr": "{scene} Dites en français : « {meaning} »",
    },
    "message": {
        "en": (
            '{scene} Write a short message in French (two or three sentences). '
            'Include the idea "{meaning}" and add a reason or a detail of your own.'
        ),
        "de": (
            "{scene} Schreib eine kurze Nachricht auf Französisch (zwei oder drei Sätze). "
            "Bring den Gedanken „{meaning}“ unter und füge einen Grund oder ein eigenes Detail hinzu."
        ),
        "fr": (
            "{scene} Écrivez un court message en français (deux ou trois phrases). "
            "Reprenez l’idée « {meaning} » et ajoutez une raison ou un détail à vous."
        ),
    },
}

#: The default situations, as short native-language situations (WP-S6).
_SCENES_L10N: dict[str, dict[str, str]] = {
    "At Le Mistral, Margaux leans over the zinc counter and asks you something.": {
        "de": "Im Mistral beugt sich Margaux über den Tresen und fragt dich etwas.",
        "fr": "Au Mistral, Margaux se penche au-dessus du zinc et vous pose une question.",
    },
    "Romy texts you from the newsroom and wants a quick answer.": {
        "de": "Romy schreibt dir aus der Redaktion und will schnell eine Antwort.",
        "fr": "Romy vous écrit depuis la rédaction et veut une réponse rapide.",
    },
    "At the canal market, Marin turns to you with a question.": {
        "de": "Auf dem Markt am Kanal dreht sich Marin mit einer Frage zu dir um.",
        "fr": "Au marché du canal, Marin se tourne vers vous avec une question.",
    },
    "Lila calls you from her classroom during the break.": {
        "de": "Lila ruft dich in der Pause aus ihrem Klassenzimmer an.",
        "fr": "Lila vous appelle de sa classe pendant la récréation.",
    },
    "Gus sends you a message from his loft.": {
        "de": "Gus schickt dir eine Nachricht aus seinem Loft.",
        "fr": "Gus vous envoie un message depuis son loft.",
    },
}


def _cue_l10n(key: str, item: BankItem, *, scene: str | None = None) -> dict[str, str]:
    """``{en, de, fr}`` for one cue template (WP-S6). A situation with no
    authored translation is left out of that language rather than mixed in."""

    out: dict[str, str] = {}
    for language, template in _CUES[key].items():
        where = ""
        if scene is not None:
            where = scene if language == "en" else _SCENES_L10N.get(scene, {}).get(language, "")
        out[language] = template.format(meaning=item.en, scene=where).strip()
    return out


def _item_id(unit: str, item: BankItem, mode: str) -> str:
    return f"{unit.lower().replace('_', '-')}-{mode}-{item.fingerprint[:10]}"


def _answer_key(item: BankItem) -> dict[str, Any]:
    return {
        "target_span": item.target,
        "accepted_answers": list(item.accepted),
        "bank_frame": item.frame_id,
        "bank_fingerprint": item.fingerprint,
    }


def _scramble(values: list[str], key: str) -> list[str]:
    keyed = sorted(values, key=lambda value: hashlib.sha256(f"{key}:{value}".encode()).hexdigest())
    return keyed


def _item_errors(mode: str, payload: dict[str, Any]) -> list[str]:
    """The séance's own per-item validators (one implementation, never a copy)."""

    from app.services.atelier import (  # lazy: atelier imports this module
        AtelierExerciseGenerator,
        _contains_blank_marker,
        _join_french_tokens,
        _multiset_subset,
        _transform_noop_errors,
    )
    from app.services.atelier import _normalize as atelier_normalize

    if mode == "fill":
        return AtelierExerciseGenerator._fill_quality_errors(payload)
    if mode == "classify":
        errors = AtelierExerciseGenerator._classify_quality_errors(payload)
        if atelier_normalize(payload.get("correct_label")) not in {atelier_normalize(label) for label in payload.get("labels") or []}:
            errors.append("correct_label is not one of labels")
        return errors
    if mode == "word_bank":
        errors = AtelierExerciseGenerator._word_bank_quality_errors(payload)
        tokens, answer_tokens = payload.get("tokens") or [], payload.get("answer_tokens") or []
        if _contains_blank_marker(payload.get("prompt")) or any(_contains_blank_marker(token) for token in tokens):
            errors.append("blank marker")
        if not _multiset_subset(answer_tokens, tokens):
            errors.append("answer not buildable")
        if atelier_normalize(payload.get("correct_answer")) != atelier_normalize(_join_french_tokens(answer_tokens)):
            errors.append("answer does not match its tokens")
        return errors
    if mode == "transform":
        return _transform_noop_errors(payload)
    return []


def _checked(mode: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    return None if _item_errors(mode, payload) else payload


def fill_item(item: BankItem, *, lesson_external_id: str | None = None) -> dict[str, Any] | None:
    prompt = f"{item.prefix}___{item.suffix}".strip()
    if contains_phrase(prompt.replace("___", " "), item.target):
        return None
    if item.gloss:
        prompt = f"{prompt} ({item.en})"
    choices = [item.target, *item.traps[:2]]
    if len({normalize(choice) for choice in choices}) < 2:
        return None
    payload = {
        "id": _item_id(item.unit, item, "fill"),
        "prompt": prompt,
        "choices": _scramble(choices, item.fingerprint),
        "correct_answer": item.target,
        "meaning": item.en,
        **_answer_key(item),
    }
    payload["accepted_answers"] = [item.target]
    if lesson_external_id:
        payload["lesson_external_id"] = lesson_external_id
    return _checked("fill", payload)


def classify_item(item: BankItem, *, show_correct: bool, lesson_external_id: str | None = None) -> dict[str, Any] | None:
    prompt = item.sentence if show_correct else item.wrong_sentences[0]
    if item.gloss:
        prompt = f"{prompt} ({item.en})"
    label = "Correct" if show_correct else "À corriger"
    payload = {
        "id": _item_id(item.unit, item, "classify"),
        "prompt": prompt,
        "labels": ["Correct", "À corriger"],
        "correct_label": label,
        "correct_answer": label,
        "classify_kind": "judgement",
        **_answer_key(item),
    }
    payload["accepted_answers"] = [label]
    if lesson_external_id:
        payload["lesson_external_id"] = lesson_external_id
    return _checked("classify", payload)


def pair_item(item: BankItem, *, lesson_external_id: str | None = None) -> dict[str, Any] | None:
    """The minimal pair («discriminate»), as a classify variant: which one says …?"""

    wrong = item.wrong_sentences[0]
    if normalize(wrong) == normalize(item.sentence):
        return None
    prompt = f'Which sentence says: "{item.en}"'
    payload = {
        "id": _item_id(item.unit, item, "pair"),
        "prompt": prompt,
        "prompt_l10n": _cue_l10n("pair", item),
        "labels": _scramble([item.sentence, wrong], item.fingerprint),
        "correct_label": item.sentence,
        "correct_answer": item.sentence,
        "classify_kind": "minimal_pair",
        **_answer_key(item),
    }
    if lesson_external_id:
        payload["lesson_external_id"] = lesson_external_id
    return _checked("classify", payload)


_PUNCTUATION = frozenset(",.;:!?")


def _tokens(sentence: str) -> list[str]:
    sentence = re.sub(r"[‘’‚‛′`´ʹʻʼ]", "'", sentence)
    return [token for token in re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ]+(?:['-][A-Za-zÀ-ÖØ-öø-ÿ]+)*|[.,!?;:]", sentence) if token.strip()]


def _join(tokens: list[str]) -> str:
    text = " ".join(token.strip() for token in tokens if token.strip())
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"([cdjlmnst])'\s+", r"\1'", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


def word_bank_item(item: BankItem, *, lesson_external_id: str | None = None) -> dict[str, Any] | None:
    answer_tokens = _tokens(item.sentence)
    if normalize(_join(answer_tokens)) != normalize(item.sentence):
        return None
    counts: dict[str, int] = {}
    for token in answer_tokens:
        counts[normalize(token)] = counts.get(normalize(token), 0) + 1
    spares: list[str] = []
    for trap in item.traps:
        for token in _tokens(trap):
            key = normalize(token)
            if not key or token in _PUNCTUATION:
                continue
            if counts.get(key, 0) > 0:
                continue
            if key not in {normalize(spare) for spare in spares}:
                spares.append(token)
        if spares:
            break
    chips = _scramble([*answer_tokens, *spares[:2]], item.fingerprint)
    while chips and chips[0] in {",", ".", ";", ":", "!", "?"}:
        chips = chips[1:] + chips[:1]
    if normalize(_join(chips)) == normalize(item.sentence) and len(chips) > 2:
        chips = chips[1:] + chips[:1]
    payload = {
        "id": _item_id(item.unit, item, "build"),
        "prompt": _INSTRUCTIONS["forge.word_bank" if spares else "forge.word_bank_all"],
        "instruction_key": "forge.word_bank" if spares else "forge.word_bank_all",
        "meaning_cue": item.en,
        "answer_tokens": answer_tokens,
        "tokens": chips,
        "correct_answer": item.sentence,
        **_answer_key(item),
    }
    if lesson_external_id:
        payload["lesson_external_id"] = lesson_external_id
    return _checked("word_bank", payload)


def transform_item(item: BankItem) -> dict[str, Any] | None:
    # The ✗ sentence to repair: never one that still contains the whole
    # answer (a trap that only adds a word, «Vous venez …» for «Venez …»).
    choice = next(
        (
            (source, trap)
            for source, trap in zip(item.wrong_sentences, item.traps, strict=False)
            if normalize(source) != normalize(item.sentence) and not contains_phrase(source, item.sentence)
        ),
        None,
    )
    if choice is None:
        return None
    source, wrong_span = choice
    instruction: dict[str, Any] = {"instruction": _INSTRUCTIONS["forge.transform"], "instruction_key": "forge.transform"}
    if item.gloss:
        instruction = {
            "instruction": f'Correct the sentence so that it means: "{item.en}"',
            "instruction_l10n": _cue_l10n("transform_gloss", item),
        }
    return _checked(
        "transform",
        {
            "id": _item_id(item.unit, item, "repair"),
            "type": "rewrite",
            **instruction,
            "source": source,
            "wrong_span": wrong_span,
            "expected_answer": item.sentence,
            "meaning": item.en,
            **_answer_key(item),
        },
    )


_DEFAULT_SCENES = (
    "At Le Mistral, Margaux leans over the zinc counter and asks you something.",
    "Romy texts you from the newsroom and wants a quick answer.",
    "At the canal market, Marin turns to you with a question.",
    "Lila calls you from her classroom during the break.",
    "Gus sends you a message from his loft.",
)


def _scene_for(item: BankItem) -> str:
    if item.scene:
        return item.scene
    index = int(item.fingerprint[:4], 16) % len(_DEFAULT_SCENES)
    return _DEFAULT_SCENES[index]


def production_prompt(item: BankItem) -> str:
    return f'{_scene_for(item)} Say in French: "{item.en}"'


def output_item(
    item: BankItem,
    *,
    round_name: str,
    requirement: dict[str, Any],
    coach: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """A production item. With a ``coach`` the conversation rung is a two-line
    scene (WP-S5), or ``None`` when this item cannot be one with that coach."""

    if round_name == "conversation" and coach:
        return scene_item(item, coach=coach, requirement=requirement)
    kind = {"sentence": "short_sentence", "speak": "spoken_response", "conversation": "conversation_turn"}[round_name]
    words = len(item.sentence.split())
    return {
        "id": _item_id(item.unit, item, round_name),
        "type": kind,
        "instruction": _INSTRUCTIONS[f"forge.{round_name}"],
        "instruction_key": f"forge.{round_name}",
        "prompt": production_prompt(item),
        "prompt_l10n": _cue_l10n("say", item, scene=_scene_for(item)),
        "example_answer": item.sentence,
        "requirements": [dict(requirement)],
        "min_words": max(2, min(words - 2, 5)),
        "max_words": max(24, words + 12),
        **_answer_key(item),
    }


def scene_item(item: BankItem, *, coach: dict[str, Any], requirement: dict[str, Any]) -> dict[str, Any] | None:
    """WP-S5 — the free-use rung as a two-line scene with the rule's coach.

    The coach says a line; the learner replies, and the reply needs the rule.
    The payload is the conversation turn the séance page already renders
    (``character`` byline, ``prompt``) plus the scene itself (``scene.lines``)
    for the coach's portrait; it is graded like any production, locally and
    then by the relecture (WP-S1), against ``example_answer``.
    """

    from app.services.forge_coaches import mini_scene

    scene = mini_scene(item, coach)
    if scene is None:
        return None
    coach_line, reply = scene["lines"][0], scene["reply"]
    words = len(reply.split())
    return {
        "id": _item_id(item.unit, item, "scene"),
        "type": "conversation_turn",
        "instruction": _INSTRUCTIONS["forge.scene"],
        "instruction_key": "forge.scene",
        "prompt": f'{coach["name"]}: « {coach_line["fr"]} » ({coach_line["en"]}) Reply in French: "{scene["reply_en"]}"',
        "character": {"id": coach["id"], "name": coach["name"], "register": coach.get("register", "tu")},
        "coach": dict(coach),
        "scene": {"lines": scene["lines"]},
        "example_answer": reply,
        "requirements": [dict(requirement)],
        "min_words": max(2, min(words - 2, 5)),
        "max_words": max(24, words + 12),
        **_answer_key(item),
        "accepted_answers": [reply],
    }


def produce_block(item: BankItem, model: BankItem, *, requirement: dict[str, Any]) -> dict[str, Any]:
    """The session paragraph: a model line to vary, and a situation that needs the rule."""

    return {
        "source_fragment": model.sentence,
        "prompt": (
            f'{_scene_for(item)} Write a short message in French (two or three sentences). '
            f'Include the idea "{item.en}" and add a reason or a detail of your own.'
        ),
        "prompt_l10n": _cue_l10n("message", item, scene=_scene_for(item)),
        "requirements": [dict(requirement)],
        "min_words": 10,
        "max_words": 70,
        "example_answer": item.sentence,
        **_answer_key(item),
    }


def rung_item(rung: str, item: BankItem, *, index: int = 0, requirement: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """One rung's payload item from one bank item (used by tests and the session builder)."""

    if rung == "fill":
        return fill_item(item)
    if rung == "classify":
        return classify_item(item, show_correct=index % 2 == 0)
    if rung == "pair":
        return pair_item(item)
    if rung == "word_bank":
        return word_bank_item(item)
    if rung == "transform":
        return transform_item(item)
    if rung == "production":
        return output_item(item, round_name="sentence", requirement=requirement or {"label": item.unit, "target_count": 1})
    raise KeyError(rung)


def spoils(rung: str, payload_item: dict[str, Any]) -> bool:
    """Does the item's prompt show its own answer? (the no-spoil rule)."""

    if rung == "fill":
        return contains_phrase(str(payload_item["prompt"]).replace("___", " "), payload_item["correct_answer"])
    if rung in {"classify", "pair"}:
        return contains_phrase(str(payload_item["prompt"]), payload_item["correct_label"]) and rung == "pair"
    if rung == "word_bank":
        return contains_phrase(str(payload_item["prompt"]) + " " + str(payload_item["meaning_cue"]), payload_item["correct_answer"])
    if rung == "transform":
        shown = f"{payload_item['instruction']} {payload_item['source']}"
        return normalize(payload_item["expected_answer"]) == normalize(payload_item["source"]) or contains_phrase(shown, payload_item["expected_answer"])
    if rung == "production":
        return contains_phrase(str(payload_item["prompt"]), payload_item["example_answer"])
    return False


# --------------------------------------------------------------------------- #
# A séance's exercise payload from the bank
# --------------------------------------------------------------------------- #

#: Sentences one concept's set needs: 3 fill, 3 build, 3 classify, 3 repair,
#: sentence / speak / conversation, and the paragraph's model and idea.
ITEMS_PER_SET = 17
_SPARE_ITEMS = 6


@dataclass
class BankSet:
    payload: dict[str, Any]
    fingerprints: list[str]
    units: list[str]


def _rule_card_sentences(base: dict[str, Any], extra: Iterable[str] = ()) -> set[str]:
    sentences: set[str] = set()
    panel = base.get("rule_panel") or {}
    for example in panel.get("examples") or []:
        sentences.add(fingerprint(str(example)))
    xray = base.get("xray") or {}
    if xray.get("sentence"):
        sentences.add(fingerprint(str(xray["sentence"])))
    for sentence in extra:
        sentences.add(fingerprint(str(sentence)))
    return sentences


def build_bank_set(
    *,
    external_id: str,
    base: dict[str, Any],
    requirement: dict[str, Any],
    seed: Any,
    exclude: Iterable[str] = (),
    known: Iterable[str] = (),
    rule_examples: Iterable[str] = (),
    pool_outputs: dict[str, Any] | None = None,
    story: Iterable[str] = (),
) -> BankSet | None:
    """The whole exercise payload for one concept, from its units' templates.

    ``exclude`` holds fingerprints the learner must not see again (this
    session, the last seven days); the rule card's examples are always
    excluded. ``pool_outputs`` (``output_ladder`` + ``produce`` of a vetted
    shared LLM set) replaces the templated production prompts when given.
    """

    units = units_for_external_id(external_id)
    if not units:
        return None
    bank = default_bank()
    blocked = set(exclude) | _rule_card_sentences(base, rule_examples)
    rng = random.Random(str(seed))  # noqa: S311 - reproducible variety, not security
    streams = [
        bank.sample(
            unit,
            random.Random(f"{seed}:{unit}"),  # noqa: S311 - reproducible variety, not security
            exclude=blocked,
            known=known,
            detector=unit_detector(unit),
            story=story,
        )
        for unit in units
    ]
    items: list[BankItem] = []
    exhausted: set[int] = set()
    position = rng.randrange(len(streams))
    # A few spares: an item a rung cannot pose honestly (no trap left for a
    # word bank, say) is skipped for that rung and may serve another.
    wanted = ITEMS_PER_SET + _SPARE_ITEMS
    while len(items) < wanted and len(exhausted) < len(streams):
        index = position % len(streams)
        position += 1
        if index in exhausted:
            continue
        try:
            candidate = next(streams[index])
        except StopIteration:
            exhausted.add(index)
            continue
        if candidate.fingerprint in blocked:
            continue
        blocked.add(candidate.fingerprint)
        items.append(candidate)
    if len(items) < ITEMS_PER_SET:
        return None

    lesson = external_id
    fills, builds, sorts, repairs = [], [], [], []
    queue = list(items)
    served: list[str] = []

    def take(builder) -> dict[str, Any] | None:
        for position_in_queue, candidate in enumerate(queue):
            built = builder(candidate)
            if built is not None:
                queue.pop(position_in_queue)
                served.append(candidate.fingerprint)
                return built
        return None

    for index in range(3):
        fills.append(take(lambda item: fill_item(item, lesson_external_id=lesson)))
        builds.append(take(lambda item: word_bank_item(item, lesson_external_id=lesson)))
        # Alternate a ✓/✗ judgement with a minimal pair; the judgement's
        # right label alternates too, so a learner cannot learn a button.
        if index == 1:
            sorts.append(take(lambda item: pair_item(item, lesson_external_id=lesson)))
        else:
            show = (int(items[0].fingerprint[:2], 16) + index) % 2 == 0
            sorts.append(take(lambda item, show=show: classify_item(item, show_correct=show, lesson_external_id=lesson)))
        repairs.append(take(transform_item))
    if any(entry is None for entry in (*fills, *builds, *sorts, *repairs)) or len(queue) < 5:
        return None
    # WP-S5: the free-use rung is a two-line scene with the rule's coach —
    # seat the first remaining item that can be one in the conversation slot.
    from app.services.forge_coaches import coach_for_concept

    coach = coach_for_concept(external_id)
    scene_index = next(
        (index for index, candidate in enumerate(queue) if coach and scene_item(candidate, coach=coach, requirement=requirement)),
        None,
    )
    if scene_index is not None and scene_index != 2:
        queue.insert(2, queue.pop(scene_index))
    sentence_item, speak_item, conversation_item, produce_idea, produce_model = queue[:5]
    conversation = output_item(conversation_item, round_name="conversation", requirement=requirement, coach=coach)
    if conversation is None:
        conversation = output_item(conversation_item, round_name="conversation", requirement=requirement)
    payload = dict(base)
    if coach:
        payload["coach"] = dict(coach)
    payload["recognize"] = {
        "fill": {"items": fills},
        "word_bank": {"items": builds},
        "classify": {"items": sorts},
    }
    payload["transform"] = {"items": repairs}
    if pool_outputs and pool_outputs.get("output_ladder") and pool_outputs.get("produce"):
        payload["output_ladder"] = pool_outputs["output_ladder"]
        payload["produce"] = pool_outputs["produce"]
    else:
        served.extend(item.fingerprint for item in queue[:5])
        payload["output_ladder"] = {
            "sentence": {"items": [output_item(sentence_item, round_name="sentence", requirement=requirement)]},
            "speak": {"items": [output_item(speak_item, round_name="speak", requirement=requirement)]},
            "conversation": {"items": [conversation]},
        }
        payload["produce"] = produce_block(produce_idea, produce_model, requirement=requirement)
    payload["forge"] = {
        "source": "item_bank",
        "bank_version": ITEM_BANK_VERSION,
        "units": units,
        "fingerprints": served,
    }
    return BankSet(payload=payload, fingerprints=served, units=units)


__all__ = [
    "BankItem",
    "BankSet",
    "ITEMS_PER_SET",
    "ITEM_BANK_VERSION",
    "ItemBank",
    "RUNG_TYPES",
    "VARIETY_WINDOW_DAYS",
    "build_bank_set",
    "contains_phrase",
    "default_bank",
    "fingerprint",
    "lexicon",
    "normalize",
    "rung_item",
    "spoils",
    "template_units",
    "unit_band",
    "unit_detector",
    "units_for_external_id",
]
