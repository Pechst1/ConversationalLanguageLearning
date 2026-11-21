"""#174: the answer bank. Every right answer a teacher accepts, reviewed once, stored in the repo.

A keyed item used to be right for one stored string (and the few variants a rule could
derive). The bank lists, per authored item, every answer a French teacher accepts for that
exact prompt at its CEFR level (spelling variants such as «clé»/«clef», tu/vous or gender
where the prompt leaves them open, on/nous, contractions, word order) and the common wrong
answers that must stay wrong, each with a one-line reason.

It was written offline by ``scripts/build_answer_bank.py``: one model call proposes, a
second, independent call judges every proposed form blind; only forms both accept are
listed, only forms both refuse stay wrong. Nothing calls a model at answer time.

The bank lives in ``app/data/answer_bank/<source>.json``, one file per authored source,
keyed by the stable item id :func:`authored_items` gives. Each entry stores the hash of
the prompt and key it was written for (:func:`item_hash`): when an item's prompt or key
changes, ``tests/test_answer_bank_fresh.py`` fails until the entry is regenerated.

At answer time the judges ask :func:`bank_verdict` with the item's accepted answers. The
lookup is by the key itself (after :func:`answer_acceptance.fold_typography`), so every
surface that grades against that key reads the same entry. Two items with one key merge
strictly: a variant is accepted only when every item accepts it, and a wrong form is kept
only when no item accepts it.

Behind ``settings.ANSWER_BANK_ENABLED`` (off by default): off, the judges behave as before.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace
from typing import Any

__all__ = [
    "SOURCES",
    "AuthoredItem",
    "BankHit",
    "authored_items",
    "bank_verdict",
    "enabled",
    "entries",
    "item_hash",
    "load_bank",
    "variants_of",
    "why_for_learner",
]

_APP = Path(__file__).resolve().parents[1]
DATA = _APP / "data"
BANK_DIR = DATA / "answer_bank"

#: The authored sources, in the order the builder pays for them (La Forge and the
#: pre-scene drills first).
SOURCES = ("repair_pairs", "seance", "journey_phrases", "season_words")


def enabled() -> bool:
    from app.config import settings

    return bool(getattr(settings, "ANSWER_BANK_ENABLED", False))


# ---------------------------------------------------------------------------
# The authored items
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AuthoredItem:
    """One authored item judged against a stored key.

    ``prompt`` is everything the learner is shown (or told) that decides which answers
    are right; ``key`` is the stored answer; ``listed`` the variants the item lists itself.
    """

    id: str
    source: str
    kind: str
    cefr: str
    key: str
    prompt: Mapping[str, Any]
    listed: tuple[str, ...] = ()
    origin: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source": self.source,
            "kind": self.kind,
            "cefr": self.cefr,
            "key": self.key,
            "prompt": dict(self.prompt),
            "listed": list(self.listed),
            "origin": self.origin,
            "hash": item_hash(self),
        }


def _sha(value: str, n: int = 10) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:n]


def item_hash(item: AuthoredItem) -> str:
    """What the bank entry was written for: the kind, the level, the prompt, the key, the listed variants."""

    payload = json.dumps(
        {"kind": item.kind, "cefr": item.cefr, "prompt": item.prompt, "key": item.key, "listed": list(item.listed)},
        ensure_ascii=False,
        sort_keys=True,
    )
    return _sha(payload, 16)


def _band(value: Any) -> str:
    text = str(value or "").strip().upper()
    match = re.match(r"([ABC][12])", text)
    return match.group(1) if match else "A1"


def _repair_pairs() -> list[AuthoredItem]:
    """La Forge's ✗/✓ pairs (rule cards and reviewed units, :func:`grammar_units.contrast_pairs`).

    They are posed as «fix this sentence» (Essai, Forge transform, the fallback set) and
    as «right or wrong?» with the fix asked after a miss; the key is the ✓ sentence.
    """

    from app.services.grammar_units import contrast_pairs

    rows: dict[str, dict[str, Any]] = {}
    for path in sorted((DATA / "grammar_review").glob("units_*.json")):
        for unit in json.loads(path.read_text(encoding="utf-8")).get("units") or []:
            rows.setdefault(str(unit["external_id"]), dict(unit, _origin=path.relative_to(_APP).as_posix()))
    with (DATA / "grammar_catalog" / "french_core_grammar_v1.tsv").open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            rows.setdefault(str(row["external_id"]), dict(row, _origin="data/grammar_catalog/french_core_grammar_v1.tsv"))
    items: list[AuthoredItem] = []
    for external_id in sorted(rows):
        row = rows[external_id]
        concept = SimpleNamespace(**{k: v for k, v in row.items() if not k.startswith("_")})
        for pair in contrast_pairs(concept):
            wrong, right = str(pair["wrong"]), str(pair["right"])
            items.append(
                AuthoredItem(
                    id=f"{external_id}#{_sha(wrong + '|' + right)}",
                    source="repair_pairs",
                    kind="fix_the_mistake",
                    cefr=_band(row.get("cefr_level")),
                    key=right,
                    prompt={"wrong_sentence": wrong, "grammar_point": str(row.get("name_en") or external_id)},
                    origin=f"{row['_origin']}:{external_id} (+ rule card)",
                )
            )
    return items


def _seance() -> list[AuthoredItem]:
    """The séance challenges (``seance_challenges.txt``): the foil sentence, repaired to the focus."""

    from app.services.seance_curriculum import curriculum

    items: list[AuthoredItem] = []
    for external_id, lesson in sorted(curriculum().items()):
        if not lesson.get("sentence") or not lesson.get("source"):
            continue
        items.append(
            AuthoredItem(
                id=external_id,
                source="seance",
                kind="fix_the_mistake",
                cefr=_band(lesson.get("cefr_level")),
                key=str(lesson["sentence"]),
                prompt={
                    "wrong_sentence": str(lesson["source"]),
                    "scene": str(lesson.get("scene") or ""),
                    "grammar_point": str(lesson.get("name_en") or external_id),
                    "blanked": str(lesson.get("blank") or ""),
                },
                origin=f"data/seance_challenges.txt:{external_id}",
            )
        )
    return items


def _journey_phrases() -> list[AuthoredItem]:
    """The pre-scene recall phrases: each scenario's target affordances and the first day's recall words."""

    items: list[AuthoredItem] = []
    for path in sorted((DATA / "journey_scenarios" / "journey-content-v1").glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        scenario = str(data.get("scenario_key") or path.stem)
        seen: set[str] = set()
        for variant in data.get("variants") or []:
            band = _band(variant.get("level_band"))
            objective = (variant.get("objective_native") or {}).get("en") or ""
            for phrase in variant.get("target_affordances_fr") or []:
                phrase = str(phrase).strip()
                ident = f"{scenario}:{band}:{phrase}"
                if not phrase or ident in seen:
                    continue
                seen.add(ident)
                items.append(
                    AuthoredItem(
                        id=f"{scenario}:{band}#{_sha(phrase)}",
                        source="journey_phrases",
                        kind="recall_phrase",
                        cefr=band,
                        key=phrase,
                        prompt={
                            "scene": f"{data.get('location_name', '')}: {objective}",
                            "register": str(data.get("register") or ""),
                        },
                        origin=f"{path.relative_to(_APP).as_posix()}:variants[{band}].target_affordances_fr",
                    )
                )
    first_day = json.loads((DATA / "journey_scenarios" / "first_day_v1.json").read_text(encoding="utf-8"))
    for band, words in sorted((first_day.get("recall_words") or {}).items()):
        for row in words or []:
            word = str(row.get("word") or "").strip()
            if not word:
                continue
            gloss = row.get("gloss") or {}
            items.append(
                AuthoredItem(
                    id=f"first_day:{band}#{_sha(word)}",
                    source="journey_phrases",
                    kind="recall_word",
                    cefr=_band(band),
                    key=word,
                    prompt={"meaning_en": str(gloss.get("en") or ""), "meaning_de": str(gloss.get("de") or ""),
                            "part_of_speech": str(row.get("part_of_speech") or "")},
                    origin=f"data/journey_scenarios/first_day_v1.json:recall_words.{band}",
                )
            )
    return items


def _blank(sentence: str, surface: str) -> str:
    pattern = re.compile(rf"(?<![\w'’-]){re.escape(surface)}(?![\w-])", re.IGNORECASE)
    blanked, count = pattern.subn("___", sentence, count=1)
    return blanked if count else ""


def _season_words() -> list[AuthoredItem]:
    """The season's day words (``season/s1/lexicon.json``) as the scene cloze poses them.

    :mod:`app.services.scene_items` blanks ``surface_fr`` in a line of the day and grades
    the form that fits the line (:func:`answer_acceptance.judge_in_line`), with the gloss as
    the hint; so the prompt is the line with the blank and the gloss, the key the surface.
    """

    data = json.loads((DATA / "season" / "s1" / "lexicon.json").read_text(encoding="utf-8"))
    rows: dict[str, tuple[str, dict[str, Any]]] = {}
    for day, bands in (data.get("days") or {}).items():
        for rows_of_band in (bands or {}).values():
            for row in rows_of_band or []:
                surface = str(row.get("surface_fr") or "").strip()
                gloss = row.get("gloss") or {}
                if not surface:
                    continue
                ident = f"{surface.casefold()}|{gloss.get('en', '')}"
                rows.setdefault(ident, (day, row))
    items: list[AuthoredItem] = []
    for ident in sorted(rows):
        day, row = rows[ident]
        gloss = row.get("gloss") or {}
        surface = str(row["surface_fr"]).strip()
        items.append(
            AuthoredItem(
                id=f"{row.get('lemma') or surface}#{_sha(ident)}",
                source="season_words",
                kind="cloze_word",
                cefr=_band(row.get("band")),
                key=surface,
                prompt={
                    "line_with_blank": _blank(str(row.get("sentence_fr") or ""), surface),
                    "hint_en": str(gloss.get("en") or ""),
                    "hint_de": str(gloss.get("de") or ""),
                    "dictionary_form": str(row.get("lemma") or ""),
                    "part_of_speech": str(row.get("part_of_speech") or ""),
                },
                origin=f"data/season/s1/lexicon.json:days.{day}",
            )
        )
    return items


_BUILDERS = {
    "repair_pairs": _repair_pairs,
    "seance": _seance,
    "journey_phrases": _journey_phrases,
    "season_words": _season_words,
}


def authored_items(source: str | None = None) -> list[AuthoredItem]:
    """Every authored keyed item of one source, or of all of them, in a stable order."""

    names = [source] if source else list(SOURCES)
    out: list[AuthoredItem] = []
    for name in names:
        out.extend(_BUILDERS[name]())
    return out


# ---------------------------------------------------------------------------
# The stored bank
# ---------------------------------------------------------------------------


def bank_path(source: str) -> Path:
    return BANK_DIR / f"{source}.json"


@lru_cache(maxsize=8)
def load_bank(source: str) -> dict[str, Any]:
    path = bank_path(source)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def entries() -> dict[str, dict[str, Any]]:
    """Every stored entry of every source, by item id."""

    out: dict[str, dict[str, Any]] = {}
    for source in SOURCES:
        for item_id, entry in (load_bank(source).get("entries") or {}).items():
            out[f"{source}/{item_id}"] = entry
    return out


def freshness_problems(items: Iterable[AuthoredItem] | None = None) -> list[str]:
    """Why the stored bank no longer matches the authored items, one line each.

    A source with a bank file must have one entry per item, written for that item's
    current prompt and key (:func:`item_hash`), and no entry for an item that is gone.
    A source with no bank file yet is reported by :func:`coverage`, not here.
    """

    whole = items is None
    by_source: dict[str, list[AuthoredItem]] = {}
    for item in authored_items() if items is None else items:
        by_source.setdefault(item.source, []).append(item)
    problems: list[str] = []
    for source, rows in sorted(by_source.items()):
        bank = load_bank(source)
        if not bank:
            continue
        stored = dict(bank.get("entries") or {})
        for item in rows:
            entry = stored.pop(item.id, None)
            if entry is None:
                problems.append(f"{source}/{item.id}: no bank entry (key «{item.key}», from {item.origin})")
            elif entry.get("hash") != item_hash(item) or entry.get("key") != item.key:
                problems.append(f"{source}/{item.id}: prompt or key changed since the entry was written (key «{item.key}»)")
        if whole:
            problems.extend(f"{source}/{item_id}: entry for an item that no longer exists" for item_id in sorted(stored))
    return problems


def coverage() -> dict[str, tuple[int, int]]:
    """Per source: (items with a bank entry, authored items)."""

    out: dict[str, tuple[int, int]] = {}
    for source in SOURCES:
        items = authored_items(source)
        stored = (load_bank(source).get("entries") or {}).keys()
        out[source] = (sum(1 for item in items if item.id in stored), len(items))
    return out


@dataclass(slots=True)
class _Merged:
    key: str
    kinds: set[str] = field(default_factory=set)
    accepted: dict[str, str] = field(default_factory=dict)  # folded -> as written
    wrong: dict[str, dict[str, str]] = field(default_factory=dict)  # folded -> {form, why_en, why_de}


def _fold(value: object) -> str:
    from app.services.answer_acceptance import fold_typography

    return fold_typography(value)


def strip_accents(value: str) -> str:
    from app.services.answer_acceptance import strip_accents as strip

    return strip(value)


@lru_cache(maxsize=1)
def _index() -> dict[str, _Merged]:
    """Folded key -> merged entry. A key whose own item the judge refused is not indexed."""

    grouped: dict[str, list[dict[str, Any]]] = {}
    for entry in entries().values():
        if entry.get("key_rejected"):
            continue
        key = _fold(entry.get("key"))
        if key:
            grouped.setdefault(key, []).append(entry)
    index: dict[str, _Merged] = {}
    for key, rows in grouped.items():
        merged = _Merged(key=str(rows[0].get("key")), kinds={str(row.get("kind") or "") for row in rows})
        sets = []
        for row in rows:
            sets.append({_fold(form): str(form) for form in [row.get("key"), *(row.get("accepted") or [])] if _fold(form)})
        common = set(sets[0])
        for other in sets[1:]:
            common &= set(other)
        merged.accepted = {folded: sets[0][folded] for folded in sorted(common)}
        everything_accepted = set().union(*sets)
        # An accent the answer left out is the one accent rule's to judge (named, and
        # forgiven or refused by :func:`answer_acceptance.accent_policy`), never the bank's.
        accent_free = {strip_accents(form) for form in everything_accepted}
        for row in rows:
            for wrong in row.get("wrong") or []:
                folded = _fold(wrong.get("form"))
                if folded and folded not in everything_accepted and strip_accents(folded) not in accent_free:
                    merged.wrong.setdefault(folded, dict(wrong))
        index[key] = merged
    return index


def reset_cache() -> None:
    load_bank.cache_clear()
    _index.cache_clear()


_ARTICLE = re.compile(r"^(l'|les|le|la|une|un|des|du|de la|de l')(?:\s+|(?<='))(?=\S)")


def _split_article(folded: str) -> tuple[str | None, str]:
    match = _ARTICLE.match(folded)
    if not match:
        return None, folded
    return match.group(1), folded[match.end():].strip()


@dataclass(frozen=True, slots=True)
class BankHit:
    """What the bank says about one answer: right (a listed variant) or wrong (a listed trap)."""

    correct: bool
    expected: str
    form: str
    why: Mapping[str, str] | None = None
    #: The key is only ever a fix-the-mistake sentence: its words are the rule, so a
    #: listed wrong form is not a typo there.
    overrides_typo: bool = False


def _entries_for(candidates: Iterable[object], *, article_optional: bool) -> list[tuple[_Merged, str | None]]:
    index = _index()
    found: list[tuple[_Merged, str | None]] = []
    for candidate in candidates:
        folded = _fold(candidate)
        if not folded:
            continue
        if folded in index:
            found.append((index[folded], None))
            continue
        if article_optional:
            article, bare = _split_article(folded)
            if article is not None and bare in index:
                found.append((index[bare], article))
    return found


def bank_verdict(
    answer: object,
    candidates: Iterable[object],
    *,
    article_optional: bool = False,
) -> BankHit | None:
    """The bank's word on ``answer`` for an item keyed by ``candidates``, or ``None``.

    Equal (after the one fold) to an accepted variant: right. Equal to a listed wrong form:
    wrong, with its reason. Anything else: the bank says nothing and the judge goes on.
    An answer equal to one of ``candidates`` itself is never refused here.
    """

    if not enabled():
        return None
    learner = _fold(answer)
    candidates = [str(item) for item in candidates if item and str(item).strip()]
    if not learner or not candidates:
        return None
    if learner in {_fold(item) for item in candidates}:
        return None
    found = _entries_for(candidates, article_optional=article_optional)
    if not found:
        return None
    learner_article, learner_bare = _split_article(learner) if article_optional else (None, learner)
    for merged, key_article in found:
        if learner in merged.accepted:
            return BankHit(correct=True, expected=merged.key, form=merged.accepted[learner])
        if key_article is not None or (article_optional and learner_article is not None):
            # A card keyed «la clé»: «la clef» and «clef» are right; another article is not ours to decide.
            if learner_bare in merged.accepted and learner_article in {None, key_article}:
                return BankHit(correct=True, expected=merged.key, form=merged.accepted[learner_bare])
    for merged, _key_article in found:
        wrong = merged.wrong.get(learner)
        if wrong is not None:
            return BankHit(
                correct=False,
                expected=merged.key,
                form=str(wrong.get("form") or ""),
                why=_why(wrong),
                overrides_typo=merged.kinds == {"fix_the_mistake"},
            )
    return None


def variants_of(keys: Iterable[object]) -> list[str]:
    """The reviewed variants of these keys, as written (empty with the flag off)."""

    if not enabled():
        return []
    out: list[str] = []
    for merged, _article in _entries_for(keys, article_optional=False):
        out.extend(form for form in merged.accepted.values() if form not in out)
    return out


def _why(row: Mapping[str, Any]) -> dict[str, str]:
    return {lang: str(row.get(f"why_{lang}") or "") for lang in ("en", "de") if row.get(f"why_{lang}")}


def why_for_learner(hit: BankHit, accepted: Iterable[object], language: str | None) -> str | None:
    """The stored reason in the learner's language, unless it would show the answer.

    The owner's rule: no solution before a retry. A reason that contains an accepted
    answer, or the key's word the learner left out, is not shown.
    """

    if not hit.why:
        return None
    lang = "de" if str(language or "").lower().startswith("de") else "en"
    text = hit.why.get(lang) or hit.why.get("en")
    if not text:
        return None
    folded = _fold(text)
    learner_words = set(_fold(hit.form).split())
    for answer in [hit.expected, *accepted]:
        target = _fold(answer)
        if not target:
            continue
        if f" {target} " in f" {folded} ":
            return None
        for word in target.split():
            if word not in learner_words and len(word) > 2 and re.search(rf"(?<!\w){re.escape(word)}(?!\w)", folded):
                return None
    return text
