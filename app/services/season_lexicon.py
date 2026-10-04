"""WP-131 — a season's words, read off the lines a learner actually reads.

The bible's tentpole ``lexicon`` lists are written for A1–A2
(``season.runtime._lexicon`` serves them below B1 only). From B1 a tentpole page
is a level variant (``levels_*.json``), and the journey looked its new word up
in the scene's text with a difficulty floor — so a B1+ day often had no word to
practise at the learner's band at all (EXPERIENCE-REVIEW 2026-10-04 §7.1: B1+
vocabulary items fell from 259 to 123 once grammar words were excluded).

This module derives, offline, the words each tentpole day holds **at each
level**, from the rendered lines of that level (``Say.text(band)``), matched to
the core lexicon (A1 → C1). The result is a data file beside the bible,
``app/data/season/<id>/lexicon.json`` (``scripts/build_season_lexicon.py``); the
bible and level files are never written.

Per day and per advanced level (B1, B2, C1):

* **new anchors** — content words (noun, verb, adjective, adverb) whose core
  band is the learner's own or one below (the review's difficulty floor, fix
  12), never a closed-class word, a numeral or a cast name; the learner's own
  band first;
* **foundational words** — content words below that floor. They are never
  *introduced* at B1+; they are offered only to a learner who already holds the
  word and has it due (a genuine weakness, reviewed in the scene's sentence).

Per level, ``season_words`` lists every core content lemma the season's lines
use at that level: the word drill's «scene relevance» (:mod:`app.services.word_order`).

At run time :func:`scene_entries` keeps the anchors whose surface the day's
draft really prints, glosses them in the learner's language and admits a
foundational word only when it is due.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel

LEXICON_FILE = "lexicon.json"
FORMAT_VERSION = 1
#: The levels a tentpole page has its own variant for, from B1 (below B1 the
#: bible's own lexicon serves).
ADVANCED_LEVELS = ("b1", "b2", "c1")
ALL_LEVELS = ("a1", "a2", "b1", "b2", "c1")
CONTENT_POS = frozenset({"noun", "verb", "adjective", "adverb"})
#: Kept per day and level in the data file; the scene shows at most
#: :data:`SCENE_ANCHORS` of them.
MAX_NEW_PER_DAY = 10
MAX_FOUNDATIONAL_PER_DAY = 6
SCENE_ANCHORS = 5
#: Of those, at most this many are due foundational words.
MAX_DUE_FOUNDATIONAL = 2
_BAND_LEVEL = {"A1": 1, "A2": 2, "B1": 3, "B2": 4, "C1": 5, "C2": 6}


def _band_level(band: str | None) -> int:
    return _BAND_LEVEL.get(str(band or "").upper()[:2], 1)


def floor_level(level: int) -> int:
    """The lowest band a *new* word may have for a learner at ``level`` (review fix
    12: from B1, one level below the learner; below B1, no floor)."""

    return max(1, level - 1) if level >= 3 else 1


# ---------------------------------------------------------------------------
# Derivation (offline)
# ---------------------------------------------------------------------------


def _says(node: Any) -> Iterator[Any]:
    """Every :class:`~app.services.season.format.Say` inside a season model."""

    from app.services.season.format import Say

    if isinstance(node, Say):
        yield node
        return
    if isinstance(node, BaseModel):
        for value in node.__dict__.values():
            yield from _says(value)
    elif isinstance(node, dict):
        for value in node.values():
            yield from _says(value)
    elif isinstance(node, (list, tuple)):
        for value in node:
            yield from _says(value)


_TITLES = frozenset({"mme", "maître", "monsieur", "madame", "mademoiselle"})


def _cast_tokens(season: Any) -> frozenset[str]:
    from app.services.lexical_coverage import fold
    from app.services.season.world import season_cast_names

    tokens: set[str] = set()
    names = list(season_cast_names(season.id).values()) + [member.name for member in season.cast]
    for name in names:
        for piece in str(name or "").replace("-", " ").split():
            # Proper names only: «Augustin», «Roncourt» — not «le brocanteur»'s
            # article or the title «Mme».
            clean = piece.strip(".,«»")
            if len(clean) >= 3 and clean[:1].isupper() and clean.isalpha():
                tokens.add(fold(clean))
    return frozenset(token for token in tokens if token not in _TITLES)


#: Auxiliaries: grammar, not words to drill in a scene.
_AUXILIARIES = frozenset({"être", "avoir"})
_NOMINAL_SUFFIXES = (
    ("aux", "al"), ("euses", "eux"), ("euse", "eux"), ("trices", "teur"), ("trice", "teur"),
    ("ives", "if"), ("ive", "if"), ("ères", "er"), ("ère", "er"), ("nnes", "n"), ("nne", "n"),
    ("ttes", "t"), ("tte", "t"), ("lles", "l"), ("lle", "l"), ("es", ""), ("s", ""), ("x", ""), ("e", ""),
)


def lemma_of(key: str, *, capitalised: bool = False) -> str | None:
    """The core lemma a folded running word stands for, or ``None``.

    Precision over recall, so a gloss never lies about the sentence:

    * an irregular or conjugated form goes to its lemma («est» → «être», never
      the noun «est»); otherwise the word itself;
    * a plural or feminine form only to a noun or adjective («boulangère» →
      «boulanger»), and a verb-stem guess only to a verb («regarde» →
      «regarder», never the noun «regard»);
    * a capitalised word reached only by a guess is a name («Paris» is not
      «pari»).
    """

    from app.services.lexical_coverage import CuratedResolver, load_lexicon

    lexicon = load_lexicon()
    form = lexicon.forms.get(key)
    if form and form in lexicon.lemmas:
        return form
    if capitalised and key.endswith("e") and (lexicon.lemmas.get(key + "r") or {}).get("pos") == "verb":
        # «Signe ici.», «Marche !»: a sentence-opening imperative, not the noun.
        return key + "r"
    if key in lexicon.lemmas:
        return key
    if capitalised:
        return None
    # «refuse», «exposée»: a first-group verb's form before a look-alike noun.
    for suffix in ("ées", "ée", "és", "é", "ent", "es", "e"):
        if key.endswith(suffix) and len(key) > len(suffix) + 2:
            entry = lexicon.lemmas.get(key[: len(key) - len(suffix)] + "er")
            if entry and entry.get("pos") == "verb":
                return key[: len(key) - len(suffix)] + "er"
    for suffix, replacement in _NOMINAL_SUFFIXES:
        if key.endswith(suffix) and len(key) > len(suffix) + 2:
            candidate = key[: len(key) - len(suffix)] + replacement
            entry = lexicon.lemmas.get(candidate)
            if entry and entry.get("pos") in {"noun", "adjective"}:
                return candidate
    for candidate in CuratedResolver().candidates(key)[1:]:
        entry = lexicon.lemmas.get(candidate)
        if entry and entry.get("pos") == "verb" and candidate.endswith(("er", "ir", "re", "oir")):
            return candidate
    return None


def _sentence_with(text: str, surface: str) -> str:
    import re

    from app.services.scene_items import contains_surface

    for sentence in re.split(r"(?<=[.!?…])\s+", text):
        if contains_surface(sentence, surface):
            return sentence.strip()
    return text.strip()


def _words_in(texts: list[str], *, cast: frozenset[str]) -> dict[str, dict[str, Any]]:
    """``{lemma: {surface, sentence, order}}`` for the core content words of ``texts``."""

    from app.services.level_coverage import CLOSED_CLASS_WORDS
    from app.services.lexical_coverage import load_lexicon, tokenize

    lexicon = load_lexicon()
    found: dict[str, dict[str, Any]] = {}
    order = 0
    for text in texts:
        for token in tokenize(text):
            key = token.key
            if len(key) < 3 or key in cast or key in CLOSED_CLASS_WORDS:
                continue
            lemma = lemma_of(key, capitalised=token.surface[:1].isupper())
            if lemma is None or lemma in found or lemma in CLOSED_CLASS_WORDS or lemma in _AUXILIARIES:
                continue
            entry = lexicon.lemmas[lemma]
            if entry.get("numeral") or entry.get("pos") not in CONTENT_POS:
                continue
            surface = token.surface.split("'")[-1].split("’")[-1]
            found[lemma] = {"surface": surface, "sentence": _sentence_with(text, surface), "order": order}
            order += 1
    return found


def _entry(lemma: str, seen: dict[str, Any], role: str) -> dict[str, Any]:
    from app.services.lexical_coverage import load_lexicon

    entry = load_lexicon().lemmas[lemma]
    gloss = entry.get("gloss") if isinstance(entry.get("gloss"), dict) else {}
    return {
        "lemma": lemma,
        "surface_fr": seen["surface"],
        "band": entry.get("band"),
        "sub_band": entry.get("sub_band"),
        "part_of_speech": entry.get("pos"),
        "gender": entry.get("gender") if entry.get("gender") in {"m", "f"} else None,
        "gloss": {key: value for key, value in gloss.items() if key in {"en", "de"} and value},
        "sentence_fr": seen["sentence"][:400],
        "role": role,
    }


def day_anchors(texts: list[str], level: str, *, cast: frozenset[str] = frozenset()) -> list[dict[str, Any]]:
    """The anchors of one day's lines at ``level`` (``b1`` / ``b2`` / ``c1``)."""

    from app.services.lexical_coverage import load_lexicon

    lexicon = load_lexicon()
    learner = _band_level(level)
    floor = floor_level(learner)
    seen = _words_in(texts, cast=cast)
    new: list[tuple[tuple[int, int, int], str]] = []
    foundational: list[tuple[tuple[int, int], str]] = []
    for lemma, info in seen.items():
        band = _band_level(lexicon.lemmas[lemma].get("band"))
        if floor <= band <= learner:
            # The learner's own band first, then one below; in reading order.
            new.append(((learner - band, info["order"], 0), lemma))
        elif band < floor:
            foundational.append(((info["order"], 0), lemma))
    new.sort()
    foundational.sort()
    return [_entry(lemma, seen[lemma], "new") for _key, lemma in new[:MAX_NEW_PER_DAY]] + [
        _entry(lemma, seen[lemma], "foundational") for _key, lemma in foundational[:MAX_FOUNDATIONAL_PER_DAY]
    ]


def day_key(tentpole_id: str, day: str, variant: str | None = None) -> str:
    return f"{tentpole_id}.{day}" + (f"@{variant}" if variant else "")


def source_digest(season_id: str) -> str:
    """sha256[:12] of the season files the derivation reads (bible, levels)."""

    from app.services.season.format import SEASON_ROOT

    folder = SEASON_ROOT / season_id
    digest = hashlib.sha256()
    for path in sorted(folder.glob("*.json")):
        if path.name == LEXICON_FILE:
            continue
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


def build(season_id: str = "s1") -> dict[str, Any]:
    """The season's lexicon file content (deterministic)."""

    from app.services.lexical_coverage import load_lexicon
    from app.services.season.format import load_season

    season = load_season(season_id)
    cast = _cast_tokens(season)
    days: dict[str, dict[str, list[dict[str, Any]]]] = {}
    season_words: dict[str, set[str]] = {level: set() for level in ALL_LEVELS}
    for tentpole_id in sorted(season.tentpoles):
        tentpole = season.tentpoles[tentpole_id]
        for day in tentpole.days:
            says = list(_says(day))
            by_level: dict[str, list[dict[str, Any]]] = {}
            for level in ALL_LEVELS:
                band = level.upper()
                texts = [say.text(band) for say in says]
                # Only words at or below the level: the drill must not reach above
                # the learner's band because the story happens to print a word.
                season_words[level] |= {
                    lemma
                    for lemma in _words_in(texts, cast=cast)
                    if _band_level(load_lexicon().lemmas[lemma].get("band")) <= _band_level(level)
                }
                if level in ADVANCED_LEVELS:
                    by_level[level] = day_anchors(texts, level, cast=cast)
            days[day_key(tentpole_id, day.day, day.variant)] = by_level
    return {
        "version": FORMAT_VERSION,
        "season_id": season_id,
        "source": source_digest(season_id),
        "note": "Derived by scripts/build_season_lexicon.py from the tentpoles and level files; never edited by hand.",
        "days": days,
        "season_words": {level: sorted(words) for level, words in season_words.items()},
    }


# ---------------------------------------------------------------------------
# Reading (run time)
# ---------------------------------------------------------------------------


def lexicon_path(season_id: str) -> Path:
    from app.services.season.format import SEASON_ROOT

    return SEASON_ROOT / season_id / LEXICON_FILE


@lru_cache(maxsize=4)
def load(season_id: str = "s1") -> dict[str, Any]:
    """The derived lexicon file, or an empty one (a season without it has none)."""

    try:
        return json.loads(lexicon_path(season_id).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"days": {}, "season_words": {}}


def season_words(level: str | None, season_id: str = "s1") -> frozenset[str]:
    """Every core content lemma the season's lines use at ``level`` (``A1`` … ``C1``)."""

    key = str(level or "").lower()[:2]
    return _season_words(season_id, key)


@lru_cache(maxsize=16)
def _season_words(season_id: str, key: str) -> frozenset[str]:
    return frozenset(load(season_id).get("season_words", {}).get(key) or ())


def page_anchors(page: dict[str, Any] | None) -> list[dict[str, Any]]:
    """The derived anchors of a rendered season page at its band (``[]`` below B1)."""

    if not isinstance(page, dict):
        return []
    level = str(page.get("band") or "").lower()[:2]
    if level not in ADVANCED_LEVELS:
        return []
    season_id = str(page.get("season_id") or "s1")
    key = day_key(str(page.get("tentpole") or ""), str(page.get("day") or ""), page.get("variant"))
    return list((load(season_id).get("days", {}).get(key) or {}).get(level) or [])


@lru_cache(maxsize=4)
def _season_cast_tokens(season_id: str) -> frozenset[str]:
    from app.services.season.format import load_season

    try:
        return _cast_tokens(load_season(season_id))
    except Exception:  # noqa: BLE001 - no season, no names to avoid
        return frozenset()


def _due_held_word_ids(db: Any, user: Any, word_ids: list[int], now: datetime) -> set[int]:
    """The words among ``word_ids`` the learner holds a card for that is due now."""

    if not word_ids:
        return set()
    from sqlalchemy import select

    from app.db.models.progress import UserVocabularyProgress
    from app.services.progress import vocabulary_progress_is_due

    rows = db.scalars(
        select(UserVocabularyProgress).where(
            UserVocabularyProgress.user_id == user.id,
            UserVocabularyProgress.word_id.in_(word_ids),
        )
    ).all()
    return {int(row.word_id) for row in rows if vocabulary_progress_is_due(row, now)}


def scene_entries(
    db: Any,
    *,
    user: Any,
    scenario: Any,
    now: datetime | None = None,
    limit: int = SCENE_ANCHORS,
) -> list[dict[str, Any]]:
    """A B1+ tentpole day's lexicon, in the shape ``SceneDraft.lexicon`` has.

    Only anchors whose surface the day's draft really prints (so the scene's own
    sentence rides along); glossed in the learner's language (en/de, else en);
    a foundational word only when the learner holds it and it is due. ``[]`` for
    anything that is not a B1+ season tentpole.
    """

    from app.services.lexical_coverage import fold, tokenize
    from app.services.scene_items import contains_surface, draft_of, scene_texts
    from app.services.season.runtime import SEASON_CONTEXT_KEY

    story = getattr(scenario, "story_context", None)
    season_ctx = story.get(SEASON_CONTEXT_KEY) if isinstance(story, dict) else None
    if not isinstance(season_ctx, dict) or season_ctx.get("kind") != "tentpole":
        return []
    anchors = page_anchors(season_ctx.get("page"))
    if not anchors:
        return []
    texts = scene_texts(draft_of(scenario))
    names = _season_cast_tokens(str((season_ctx.get("page") or {}).get("season_id") or "s1"))

    def practisable(text: str, surface: str) -> bool:
        # The practice item is cut from this sentence: it must print the word and
        # must not name a character (the learner may not have met them yet).
        if not contains_surface(text, surface):
            return False
        sentence = _sentence_with(text, surface)
        return not any(token.key in names for token in tokenize(sentence))

    printed = [
        (anchor, ref)
        for anchor in anchors
        for ref in [next((ref for ref, text in texts.items() if practisable(text, anchor.get("surface_fr") or "")), None)]
        if ref is not None
    ]
    if not printed:
        return []
    native = str(getattr(user, "native_language", None) or "en").lower()[:2]
    foundational = [anchor for anchor, _ref in printed if anchor.get("role") == "foundational"]
    due: set[str] = set()
    if foundational:
        from sqlalchemy import select

        from app.db.models.vocabulary import VocabularyWord

        # Any catalogue row of the lemma: the learner's card may be an imported
        # deck's or the story's, not the core list's.
        lemmas = {fold(anchor["lemma"]) for anchor in foundational}
        language = (getattr(user, "target_language", None) or "fr").strip() or "fr"
        rows = db.execute(
            select(VocabularyWord.id, VocabularyWord.normalized_word).where(
                VocabularyWord.language == language,
                VocabularyWord.normalized_word.in_(sorted(lemmas)),
            )
        ).all()
        by_id = {int(row[0]): str(row[1]) for row in rows}
        held = _due_held_word_ids(db, user, list(by_id), now or datetime.now(UTC))
        due = {by_id[word_id] for word_id in held}
    # A due foundational weakness first (at most :data:`MAX_DUE_FOUNDATIONAL`),
    # then the new anchors at the learner's band.
    admitted = [
        (anchor, ref)
        for anchor, ref in printed
        if anchor.get("role") == "foundational" and fold(anchor["lemma"]) in due
    ][:MAX_DUE_FOUNDATIONAL] + [(anchor, ref) for anchor, ref in printed if anchor.get("role") != "foundational"]
    entries: list[dict[str, Any]] = []
    for anchor, ref in admitted:
        gloss = anchor.get("gloss") or {}
        entries.append(
            {
                "surface_fr": anchor["surface_fr"],
                "lemma": anchor["lemma"],
                "gloss_native": gloss.get(native) or gloss.get("en") or "",
                "part_of_speech": anchor.get("part_of_speech"),
                "gender": anchor.get("gender"),
                "line_ref": ref,
                "anchor_role": anchor.get("role"),
                "band": anchor.get("band"),
            }
        )
        if len(entries) >= limit:
            break
    return entries


__all__ = [
    "ADVANCED_LEVELS",
    "LEXICON_FILE",
    "build",
    "day_anchors",
    "day_key",
    "floor_level",
    "lemma_of",
    "load",
    "page_anchors",
    "scene_entries",
    "season_words",
    "source_digest",
]
