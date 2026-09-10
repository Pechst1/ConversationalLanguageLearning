"""WP-29 — coverage-controlled generation.

Every scene this app generates is guessed at by CEFR band: the director is told
"write for an A1 learner" and nothing checks the result against the words *this*
learner actually has. The reading research is unusually specific about the cost
of that. Comprehension with support needs about **95 %** known-word coverage of
the running text, and unassisted reading about **98 %** (Laufer &
Ravenhorst-Kalovski 2010; Hu & Nation 2000). A scene at 88 % is not "a bit hard";
it is a scene the learner decodes rather than reads.

So unknown words become a **budget** rather than an accident:

* a word is *known* when the learner's own FSRS row says so (retrievability
  ≥ :data:`~app.services.vocabulary_coverage.NAILED_RETRIEVABILITY`, reused
  verbatim — a second nailed-rule is exactly how two rubrics start disagreeing),
  or when it is in the core list for a band at or below their CEFR estimate;
* unknown words split into **targets** — today's due vocabulary and errata, which
  are *supposed* to be new — and **accidental** unknowns, which are the model
  reaching for a word nobody chose;
* the guard rejects on coverage below the floor, or on more accidental unknowns
  than the band's budget, and its hint names the words to replace *and* the
  targets to keep.

Three deliberate constraints:

**The core list is an assumption, and says so.** A learner on day one has no FSRS
history at all. Counting only nailed words would put every scene at ~0 % coverage
and reject all of them — a guard that costs a learner their day is a defect this
codebase has already paid for twice (WP-17, and the sixteen hint-less guards of
2026-09-07). So the core list for bands up to the learner's estimate is granted,
and :attr:`KnownWordSet.estimate_source` carries whether that estimate was
``measured``, ``placement`` or merely ``declared``. Nothing here upgrades a
declaration into evidence; the payload lets a reader discount it.

**Coverage counts tokens; the budget counts types.** The 95 % figure is about
running words, so targets count against coverage like any other unknown. The
budget is about how many *different* new words a scene asks a learner to absorb,
so it counts distinct lemmas.

**Thin text is not assessed, and never rejected.** Under
:data:`MIN_ASSESSED_TOKENS` running words the percentage is noise. The verdict is
``not_assessed`` with a reason, never a rejection: an unmeasurable scene is not a
bad scene.

The guard is *not* registered here. ``living_story.py`` is leased to WP-28; the
exact registration line and the scene-metadata diff are written out in
``docs/implementation/atelier-v2/WP-29-COVERAGE.md`` under "Hooks owed".
"""
from __future__ import annotations

import json
import re
import unicodedata
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.db.models.graphic_novel import GraphicNovelPanel, GraphicNovelScene
from app.db.models.progress import UserVocabularyProgress
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services.vocabulary_coverage import NAILED_RETRIEVABILITY, is_vocab_nailed

COVERAGE_VERSION = "lexical-coverage-v1"

#: Laufer & Ravenhorst-Kalovski 2010 / Hu & Nation 2000. The scene is a
#: *supported* text — it ships a hint, a translation and a gloss resolver — so
#: the supported floor is the one the guard enforces. The unassisted figure is
#: kept because the report prints both and a future reading mode may want it.
SUPPORTED_COVERAGE_FLOOR = 0.95
UNASSISTED_COVERAGE_FLOOR = 0.98

#: Distinct accidental-unknown lemmas a scene may carry, by band. It scales
#: because the same absolute number is a different load at A1 and B2: an A1
#: scene is ~110 running words and a beginner has no strategies for guessing
#: from context, while a B2 reader does.
ACCIDENTAL_UNKNOWN_BUDGET: dict[str, int] = {"A1": 1, "A2": 2, "B1": 3, "B2": 4, "C1": 5}
DEFAULT_ACCIDENTAL_BUDGET = 2

#: Below this many running words a percentage is noise, not a measurement.
MIN_ASSESSED_TOKENS = 20
#: A known set this small means the lexicon failed to load, not that the learner
#: knows nothing. Refuse to assess rather than reject every scene.
MIN_KNOWN_LEMMAS = 50

#: How many unknown words the hint is allowed to list. A retry instruction that
#: names twenty words is one the model reads as "rewrite everything".
MAX_HINT_WORDS = 6

#: Accent-insensitive matching is a fallback for longer words only. Below this
#: length French minimal pairs (``a``/``à``, ``ou``/``où``, ``sur``/``sûr``) are
#: different words, and folding them together would mark one known because the
#: other is.
ACCENT_FALLBACK_MIN_LENGTH = 3

BAND_ORDER: tuple[str, ...] = ("A1", "A2", "B1", "B2", "C1", "C2")

LEXICON_PATH = Path(__file__).resolve().parents[1] / "data" / "lexical" / "fr_core_lexicon.json"

REJECT_LOW_COVERAGE = "lexical_coverage_low"
REJECT_UNKNOWN_BUDGET = "too_many_new_words"

_APOSTROPHES = "'’ʼ"
_WORD_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿŒœ]+(?:[" + _APOSTROPHES + r"\-][A-Za-zÀ-ÖØ-öø-ÿŒœ]+)*")
_ELISION_SPLIT = re.compile(r"[" + _APOSTROPHES + r"]")
#: Hyphenated clitics: "est-ce", "va-t-il", "dis-moi", "celui-ci".
_HYPHEN_CLITICS = frozenset(
    {"ce", "je", "tu", "il", "elle", "on", "nous", "vous", "ils", "elles", "moi", "toi",
     "lui", "eux", "le", "la", "les", "y", "en", "ci", "là", "t"}
)


def band_of(level: str | None) -> str:
    """``"A2.1"`` and ``"a2"`` are both the A2 band; anything unreadable is A1."""

    raw = str(level or "").strip().upper()
    for band in BAND_ORDER:
        if raw.startswith(band):
            return band
    return "A1"


def band_index(band: str) -> int:
    try:
        return BAND_ORDER.index(band_of(band))
    except ValueError:  # pragma: no cover - band_of already clamps
        return 0


def strip_accents(value: str) -> str:
    return unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")


def fold(value: str | None) -> str:
    """Lowercase, NFC-normalised, apostrophes unified. Accents are **kept**.

    French accents distinguish words a learner has to tell apart (``ou``/``où``,
    ``sur``/``sûr``, ``a``/``à``), so folding them away here would quietly mark
    ``où`` known because ``ou`` is. Accent-insensitive matching exists, but only
    as a *fallback* after the accented form has failed to match, and only above
    :data:`ACCENT_FALLBACK_MIN_LENGTH` — see :func:`text_coverage`.
    """

    raw = unicodedata.normalize("NFC", str(value or "").strip().lower())
    for mark in _APOSTROPHES[1:]:
        raw = raw.replace(mark, "'")
    return raw


# ---------------------------------------------------------------------------
# The vendored lexicon
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Lexicon:
    """The curated French core list, its irregular forms, and its elisions."""

    version: str
    lemmas: dict[str, dict[str, Any]]
    forms: dict[str, str]
    elisions: dict[str, str]
    atomic: frozenset[str]
    provenance: dict[str, str]

    def band(self, lemma: str) -> str | None:
        entry = self.lemmas.get(lemma)
        return str(entry["band"]) if entry else None

    def rank(self, lemma: str) -> int | None:
        entry = self.lemmas.get(lemma)
        return int(entry["rank"]) if entry else None

    def core_lemmas(self, band: str) -> frozenset[str]:
        """Every core lemma at or below ``band``."""

        ceiling = band_index(band)
        return frozenset(
            lemma
            for lemma, entry in self.lemmas.items()
            if band_index(str(entry["band"])) <= ceiling
        )


@lru_cache(maxsize=1)
def load_lexicon() -> Lexicon:
    """Read the vendored lexicon once.

    A missing or unreadable file is not fatal: it yields an empty lexicon, which
    trips :data:`MIN_KNOWN_LEMMAS` and makes the guard abstain rather than reject
    every scene in the product.
    """

    try:
        payload = json.loads(LEXICON_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):  # pragma: no cover - defensive
        payload = {}
    return Lexicon(
        version=str(payload.get("version") or "missing"),
        lemmas={fold(k): v for k, v in (payload.get("lemmas") or {}).items()},
        forms={fold(k): fold(v) for k, v in (payload.get("forms") or {}).items()},
        elisions={fold(k): fold(v) for k, v in (payload.get("elisions") or {}).items()},
        atomic=frozenset(
            fold(v)
            for key in ("atomic_apostrophe", "atomic_hyphen")
            for v in (payload.get(key) or [])
        ),
        provenance=dict(payload.get("provenance") or {}),
    )


# ---------------------------------------------------------------------------
# Tokenisation and lemma resolution
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Token:
    """One running word, already folded. Punctuation and digits never get here."""

    surface: str
    key: str


def tokenize(text: str) -> list[Token]:
    """Split French text into running words, resolving elision and clitics.

    ``L'addition`` is two tokens (``l'`` → ``le``, ``addition``), ``qu'est-ce``
    is ``que`` + ``est`` + ``ce``, and ``aujourd'hui`` stays one word. Getting
    this wrong is not cosmetic: an apostrophe every other sentence, each counted
    as an unknown word, drags a perfectly readable A1 scene under the floor.
    """

    lexicon = load_lexicon()
    tokens: list[Token] = []
    for match in _WORD_RE.finditer(unicodedata.normalize("NFC", text or "")):
        surface = match.group(0)
        folded = fold(surface)
        for piece in _split_word(folded, lexicon):
            if piece:
                tokens.append(Token(surface=surface, key=piece))
    return tokens


def _split_word(folded: str, lexicon: Lexicon) -> list[str]:
    if folded in lexicon.atomic:
        return [folded]
    pieces = _ELISION_SPLIT.split(folded)
    if len(pieces) > 1:
        # Everything before an apostrophe is an elided clitic; unrecognised ones
        # ("aujourd" in a word the atomic list missed) are kept as written.
        head = [lexicon.elisions.get(piece, piece) for piece in pieces[:-1]]
        pieces = [*head, pieces[-1]]
    out: list[str] = []
    for piece in pieces:
        if piece in lexicon.atomic:
            out.append(piece)
            continue
        parts = piece.split("-")
        if len(parts) > 1 and all(part in _HYPHEN_CLITICS for part in parts[1:]):
            # "est-ce", "va-t-il", "celui-ci": the head is the word, the tail is
            # grammar. "t" is a euphonic consonant and carries no meaning.
            out.append(parts[0])
            out.extend(part for part in parts[1:] if part != "t")
        else:
            out.append(piece)
    return out


class LemmaResolver(Protocol):
    """``(token key) -> ordered lemma candidates, best first``."""

    name: str

    def candidates(self, key: str) -> tuple[str, ...]:  # pragma: no cover - protocol
        ...


_VERB_STEM_SUFFIXES = (
    "eraient", "erions", "eriez", "erais", "erait", "eront", "erons", "erez",
    "aient", "ions", "iez", "ais", "ait", "ant", "ons", "ez", "ent", "es",
    "era", "erai", "eras", "é", "ée", "és", "ées", "ai", "as", "a", "e", "s", "t",
)
_FEMININE_SUFFIXES = (
    ("euses", "eux"), ("euse", "eux"), ("trices", "teur"), ("trice", "teur"),
    ("elles", "eau"), ("elle", "eau"), ("ives", "if"), ("ive", "if"),
    ("ères", "er"), ("ère", "er"), ("nnes", "n"), ("nne", "n"),
    ("ttes", "t"), ("tte", "t"), ("lles", "l"), ("lle", "l"),
    ("ches", "c"), ("che", "c"), ("sses", "s"), ("sse", "s"),
)


@dataclass(frozen=True)
class CuratedResolver:
    """The always-available fallback: the vendored form table plus suffix rules.

    It is deliberately *generous* — it proposes candidates and lets the caller
    keep the first one the learner knows. A resolver that guessed one lemma and
    committed to it would turn every regular past participle into an unknown
    word, and the guard would spend a learner's retries on correct French.
    """

    name: str = "curated"

    def candidates(self, key: str) -> tuple[str, ...]:
        lexicon = load_lexicon()
        out: list[str] = [key]

        def push(value: str) -> None:
            if value and len(value) > 1 and value not in out:
                out.append(value)

        irregular = lexicon.forms.get(key)
        if irregular:
            push(irregular)
        if key.endswith("aux"):
            push(key[:-3] + "al")
        for suffix in ("s", "x"):
            if key.endswith(suffix) and len(key) > 2:
                push(key[:-1])
        for suffix, replacement in _FEMININE_SUFFIXES:
            if key.endswith(suffix) and len(key) > len(suffix) + 1:
                push(key[: -len(suffix)] + replacement)
        if key.endswith("e") and len(key) > 2:
            push(key[:-1])
        for suffix in _VERB_STEM_SUFFIXES:
            if key.endswith(suffix) and len(key) > len(suffix) + 1:
                stem = key[: -len(suffix)]
                for ending in ("er", "ir", "re", "oir"):
                    push(stem + ending)
        return tuple(out)


@dataclass(frozen=True)
class SpacyResolver:
    """The POS pipeline already loaded elsewhere in the app, used for lemmas.

    Its lemma is offered *first* and the curated candidates follow, so a spaCy
    miss degrades to the fallback instead of producing a false unknown.
    """

    nlp: Any
    name: str = "spacy"
    _curated: CuratedResolver = field(default_factory=CuratedResolver)

    def candidates(self, key: str) -> tuple[str, ...]:
        out: list[str] = [key]
        # A broken or half-loaded pipeline must never cost a learner their
        # scene: the curated candidates below are a complete answer on their
        # own, so spaCy failing is a quality loss, not an outage.
        with suppress(Exception):
            doc = self.nlp(key)
            for token in doc:
                lemma = fold(getattr(token, "lemma_", ""))
                if lemma and lemma not in out:
                    out.append(lemma)
        for candidate in self._curated.candidates(key):
            if candidate not in out:
                out.append(candidate)
        return tuple(out)


@lru_cache(maxsize=1)
def default_resolver() -> LemmaResolver:
    """spaCy when the model is installed, the curated table otherwise."""

    try:
        import spacy

        from app.config import settings

        return SpacyResolver(nlp=spacy.load(settings.FRENCH_NLP_MODEL))
    except Exception:
        return CuratedResolver()


# ---------------------------------------------------------------------------
# The learner's known-word set
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class KnownWordSet:
    """What this learner can be assumed to read, and on whose authority."""

    lemmas: frozenset[str]
    band: str
    estimate_level: str
    estimate_source: str
    nailed_count: int
    core_count: int
    version: str = COVERAGE_VERSION

    def __contains__(self, lemma: str) -> bool:
        return lemma in self.lemmas

    @property
    def is_assessable(self) -> bool:
        return len(self.lemmas) >= MIN_KNOWN_LEMMAS

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "band": self.band,
            "estimate_level": self.estimate_level,
            "estimate_source": self.estimate_source,
            "nailed_words": self.nailed_count,
            "core_words": self.core_count,
            "known_lemmas": len(self.lemmas),
            "nailed_rule": {"retrievability": NAILED_RETRIEVABILITY},
        }


def _cefr_estimate(db: Session, user: User) -> tuple[str, str]:
    """WP-25's estimate, read only — never recomputed, never persisted here."""

    try:
        from app.services.cefr_progress import CEFRProgressService

        payload = CEFRProgressService(db).current(user, recompute_if_missing=False) or {}
    except Exception:  # pragma: no cover - a level must never 500 a scene
        payload = {}
    level = str(payload.get("estimate") or getattr(user, "cefr_estimate", None) or "")
    source = str(payload.get("estimate_source") or "declared")
    if not level:
        level = str(getattr(user, "proficiency_level", None) or "A1")
        source = "declared"
    return level, source


def nailed_lemmas(db: Session, *, user: User, now: datetime | None = None) -> set[str]:
    """Every lemma this learner's own FSRS row says they have nailed.

    Reuses :func:`app.services.vocabulary_coverage.is_vocab_nailed` verbatim
    rather than re-deriving retrievability, so the coverage guard and the
    coverage map can never disagree about whether a word is known.
    """

    now = now or datetime.now(UTC)
    target_language = (getattr(user, "target_language", None) or "fr").strip() or "fr"
    rows = (
        db.query(UserVocabularyProgress, VocabularyWord)
        .join(VocabularyWord, UserVocabularyProgress.word_id == VocabularyWord.id)
        .filter(
            UserVocabularyProgress.user_id == user.id,
            VocabularyWord.language == target_language,
        )
        .filter(or_(VocabularyWord.direction == "fr_to_de", VocabularyWord.direction.is_(None)))
        .all()
    )
    known: set[str] = set()
    for progress, word in rows:
        if not is_vocab_nailed(progress, now=now):
            continue
        # Tokenised, not folded whole: a card can hold a phrase ("avoir soif",
        # "le chien"), and a known set keyed on the phrase would never match the
        # word as it appears in a scene.
        for surface in (word.normalized_word, word.word):
            known.update(token.key for token in tokenize(str(surface or "")))
    return known


def known_word_set(
    db: Session,
    *,
    user: User,
    now: datetime | None = None,
    level: str | None = None,
) -> KnownWordSet:
    """FSRS-nailed words ∪ the core list for every band up to the estimate."""

    estimate_level, estimate_source = _cefr_estimate(db, user)
    if level:
        estimate_level, estimate_source = level, "override"
    band = band_of(estimate_level)
    core = load_lexicon().core_lemmas(band)
    nailed = nailed_lemmas(db, user=user, now=now)
    return KnownWordSet(
        lemmas=frozenset(core | nailed),
        band=band,
        estimate_level=estimate_level or band,
        estimate_source=estimate_source,
        nailed_count=len(nailed),
        core_count=len(core),
    )


# ---------------------------------------------------------------------------
# Coverage of a text
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UnknownWord:
    """One unknown lemma, with the surface the learner would actually read."""

    lemma: str
    surface: str
    count: int
    rank: int | None
    band: str | None
    is_target: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "lemma": self.lemma,
            "surface": self.surface,
            "count": self.count,
            "rank": self.rank,
            "band": self.band,
            "is_target": self.is_target,
        }


@dataclass(frozen=True)
class CoverageResult:
    """What share of this text the learner can read, and what the rest is."""

    coverage: float
    running_words: int
    known_words: int
    unknown_words: int
    unknown: tuple[UnknownWord, ...]
    band: str
    estimate_source: str
    resolver: str
    proper_noun_words: int
    version: str = COVERAGE_VERSION

    @property
    def targets(self) -> tuple[UnknownWord, ...]:
        return tuple(word for word in self.unknown if word.is_target)

    @property
    def accidental(self) -> tuple[UnknownWord, ...]:
        return tuple(word for word in self.unknown if not word.is_target)

    @property
    def is_assessable(self) -> bool:
        return self.running_words >= MIN_ASSESSED_TOKENS

    def as_metadata(self) -> dict[str, Any]:
        """The additive scene-metadata shape (spec §3.4).

        Read by telemetry, by ``scripts/coverage_report.py`` and by WP-35's
        learner model. Small on purpose: a scene payload is stored per learner
        per day, so the unknown lists are capped.
        """

        return {
            "version": self.version,
            "coverage": round(self.coverage, 4),
            "running_words": self.running_words,
            "known_words": self.known_words,
            "unknown_words": self.unknown_words,
            "unknown_lemmas": len(self.unknown),
            "target_unknowns": [word.as_dict() for word in self.targets[:MAX_HINT_WORDS]],
            "accidental_unknowns": [word.as_dict() for word in self.accidental[:MAX_HINT_WORDS]],
            "target_count": len(self.targets),
            "accidental_count": len(self.accidental),
            "band": self.band,
            "estimate_source": self.estimate_source,
            "resolver": self.resolver,
            "proper_noun_words": self.proper_noun_words,
            "floor": SUPPORTED_COVERAGE_FLOOR,
            "budget": ACCIDENTAL_UNKNOWN_BUDGET.get(self.band, DEFAULT_ACCIDENTAL_BUDGET),
            "assessable": self.is_assessable,
        }


def _target_keys(targets: Any) -> frozenset[str]:
    """Fold a list of words — or of multi-word names — into lookup keys.

    Multi-word entries matter: a location is called "Café des Arts", and a
    proper-noun exemption that only matched the whole string would leave "Café"
    counted as a word the learner failed to know.
    """

    keys: set[str] = set()
    for raw in targets or ():
        for token in tokenize(str(raw or "")):
            keys.add(token.key)
            keys.add(strip_accents(token.key))
    return frozenset(keys)


def text_coverage(
    text: str,
    known: KnownWordSet,
    *,
    targets: Any = (),
    proper_nouns: Any = (),
    resolver: LemmaResolver | None = None,
) -> CoverageResult:
    """Tokens → lemmas → share known, with the unknowns ranked and split.

    Proper nouns (this world's cast and locations) are counted as known and
    reported separately. Coverage research treats them that way, and it is the
    honest reading here too: "Romy" is a name the scene introduces, not a word
    the learner failed to learn.
    """

    resolver = resolver or default_resolver()
    lexicon = load_lexicon()
    target_keys = _target_keys(targets)
    proper_keys = _target_keys(proper_nouns)
    ascii_known = {
        strip_accents(lemma)
        for lemma in known.lemmas
        if len(lemma) > ACCENT_FALLBACK_MIN_LENGTH
    }

    running = 0
    known_count = 0
    proper_count = 0
    unknown_counts: dict[str, int] = {}
    unknown_surface: dict[str, str] = {}

    for token in tokenize(text):
        running += 1
        candidates = resolver.candidates(token.key)
        if any(candidate in proper_keys for candidate in candidates) or (
            strip_accents(token.key) in proper_keys
        ):
            proper_count += 1
            known_count += 1
            continue
        hit = next((candidate for candidate in candidates if candidate in known.lemmas), None)
        if hit is None:
            # Accent folding, last and only for longer words. An exact accented
            # match always wins first, and the length floor keeps the short
            # minimal pairs French actually distinguishes — a/à, ou/où, sur/sûr
            # — from vouching for one another.
            hit = next(
                (
                    candidate
                    for candidate in candidates
                    if len(candidate) > ACCENT_FALLBACK_MIN_LENGTH
                    and strip_accents(candidate) in ascii_known
                ),
                None,
            )
        if hit is not None:
            known_count += 1
            continue
        lemma = _best_lemma(candidates, lexicon)
        unknown_counts[lemma] = unknown_counts.get(lemma, 0) + 1
        unknown_surface.setdefault(lemma, token.surface)

    unknown = [
        UnknownWord(
            lemma=lemma,
            surface=unknown_surface.get(lemma, lemma),
            count=count,
            rank=lexicon.rank(lemma),
            band=lexicon.band(lemma),
            is_target=lemma in target_keys or strip_accents(lemma) in target_keys,
        )
        for lemma, count in unknown_counts.items()
    ]
    # Ranked by frequency: a lemma the core list knows is more frequent than one
    # it does not, and an unranked lemma sorts last rather than first.
    unknown.sort(key=lambda word: (word.rank is None, word.rank or 0, -word.count, word.lemma))

    unknown_tokens = sum(word.count for word in unknown)
    coverage = (known_count / running) if running else 0.0
    return CoverageResult(
        coverage=coverage,
        running_words=running,
        known_words=known_count,
        unknown_words=unknown_tokens,
        unknown=tuple(unknown),
        band=known.band,
        estimate_source=known.estimate_source,
        resolver=getattr(resolver, "name", "unknown"),
        proper_noun_words=proper_count,
    )


def _best_lemma(candidates: tuple[str, ...], lexicon: Lexicon) -> str:
    """Report the candidate the lexicon recognises, else the surface form."""

    for candidate in candidates[1:]:
        if candidate in lexicon.lemmas:
            return candidate
    return candidates[0]


# ---------------------------------------------------------------------------
# The guard
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SceneText:
    """The learner-facing French of a scene, and the names in it."""

    text: str
    proper_nouns: frozenset[str] = frozenset()


@dataclass(frozen=True)
class LearnerLexicon:
    """The learner side of the guard: what they know and what is being taught."""

    known: KnownWordSet
    targets: frozenset[str] = frozenset()
    resolver: LemmaResolver | None = None

    @property
    def band(self) -> str:
        return self.known.band


@dataclass(frozen=True)
class CoverageVerdict:
    """``verdict + hint``, in the living-story guard style.

    ``reason`` is the machine token the reports record; ``hint`` is the
    instruction handed back to the retry. Every rejecting guard in this codebase
    owes the retry an instruction (STATUS 2026-09-07, defect 1) — this one names
    the accidental words to replace and the targets to keep.
    """

    status: str
    reason: str | None = None
    hint: str | None = None
    result: CoverageResult | None = None

    @property
    def rejected(self) -> bool:
        return self.status == "rejected"

    @property
    def accepted(self) -> bool:
        return self.status == "accepted"

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "reason": self.reason,
            "hint": self.hint,
            "coverage": self.result.as_metadata() if self.result else None,
        }


def accidental_budget(band: str) -> int:
    return ACCIDENTAL_UNKNOWN_BUDGET.get(band_of(band), DEFAULT_ACCIDENTAL_BUDGET)


def _article(band: str) -> str:
    return "an" if band[:1].upper() in {"A", "E", "I", "O"} else "a"


def _quote(words: tuple[UnknownWord, ...]) -> str:
    return ", ".join(f"« {word.surface} »" for word in words[:MAX_HINT_WORDS])


def _keep_clause(result: CoverageResult) -> str:
    targets = result.targets
    if not targets:
        return ""
    return (
        f" Keep {_quote(targets)} — {'those are' if len(targets) > 1 else 'that is'} "
        "today's target vocabulary and meant to be new."
    )


def check_scene_coverage(scene: SceneText, learner: LearnerLexicon) -> CoverageVerdict:
    """``(scene, learner) → verdict + hint``.

    Accepts at or above :data:`SUPPORTED_COVERAGE_FLOOR` with no more accidental
    unknown lemmas than the band's budget. Abstains — never rejects — when the
    text is too short to measure or the lexicon failed to load.
    """

    if not learner.known.is_assessable:
        return CoverageVerdict(status="not_assessed", reason="known_set_unavailable")
    result = text_coverage(
        scene.text,
        learner.known,
        targets=learner.targets,
        proper_nouns=scene.proper_nouns,
        resolver=learner.resolver,
    )
    if not result.is_assessable:
        return CoverageVerdict(status="not_assessed", reason="text_too_short", result=result)

    band = result.band
    budget = accidental_budget(band)
    accidental = result.accidental
    if result.coverage < SUPPORTED_COVERAGE_FLOOR:
        return CoverageVerdict(
            status="rejected",
            reason=REJECT_LOW_COVERAGE,
            hint=(
                f"This scene runs at {result.coverage * 100:.0f} % known-word coverage for "
                f"{_article(band)} {band} learner; {SUPPORTED_COVERAGE_FLOOR * 100:.0f} % is the floor for "
                "reading with support, so they would be decoding it rather than reading it. "
                f"Replace the words they have never met — {_quote(accidental) or 'the rarest words in the scene'} "
                "— with everyday equivalents, and shorten the sentences that carry them."
                + _keep_clause(result)
            ),
            result=result,
        )
    if len(accidental) > budget:
        return CoverageVerdict(
            status="rejected",
            reason=REJECT_UNKNOWN_BUDGET,
            hint=(
                f"{len(accidental)} new words nobody is teaching today: {_quote(accidental)}. "
                f"{_article(band).capitalize()} {band} scene may carry {budget}. Say the same "
                "thing with words this "
                "learner already has — the situation is what makes the scene, not the "
                "vocabulary." + _keep_clause(result)
            ),
            result=result,
        )
    return CoverageVerdict(status="accepted", result=result)


# ---------------------------------------------------------------------------
# Scene text extraction (duck-typed: this module never imports living_story)
# ---------------------------------------------------------------------------


def scene_text_from_draft(draft: Any, *, proper_nouns: Any = ()) -> SceneText:
    """Collect the French a learner actually reads out of a scene draft.

    Duck-typed on purpose. ``living_story.SceneDraft`` is leased to WP-28 and
    importing it here would couple this module to a file it must not touch, and
    close an import cycle besides.
    """

    parts: list[str] = []
    for attribute in ("premise_fr", "opening_line_fr", "suggested_response_fr"):
        value = getattr(draft, attribute, None)
        if value:
            parts.append(str(value))
    for panel in getattr(draft, "panels", None) or ():
        narration = getattr(panel, "narration_fr", None)
        if narration:
            parts.append(str(narration))
        for line in getattr(panel, "dialogue", None) or ():
            text = getattr(line, "text_fr", None)
            if text:
                parts.append(str(text))
    return SceneText(text=" ".join(parts), proper_nouns=_target_keys(proper_nouns))


def world_proper_nouns(context: Any) -> frozenset[str]:
    """Cast and location names from a story context, as known-word exemptions."""

    world = (context or {}).get("world") if isinstance(context, dict) else None
    names: set[str] = set()
    for group in ("cast", "locations"):
        for entry in (world or {}).get(group, []) or ():
            for key in ("name", "id"):
                value = (entry or {}).get(key) if isinstance(entry, dict) else None
                if value:
                    names.add(str(value))
    return _target_keys(names)


# ---------------------------------------------------------------------------
# Reporting: stored scenes, the report script, and one digest line
# ---------------------------------------------------------------------------

#: Where the hook writes the metadata. Both keys are read so the report works
#: whether the diff landed on the draft payload or on the stored scene.
SCENE_METADATA_KEY = "lexical_coverage"


def stored_scene_coverage(scene: GraphicNovelScene) -> dict[str, Any] | None:
    """The metadata the hook stored, if it is there. ``None`` is not zero."""

    for payload in (scene.script_payload, scene.source_snapshot):
        entry = (payload or {}).get(SCENE_METADATA_KEY) if isinstance(payload, dict) else None
        if isinstance(entry, dict) and entry.get("coverage") is not None:
            return entry
    return None


def scene_reading_text(db: Session, scene: GraphicNovelScene) -> str:
    """Rebuild the learner-facing French of a stored scene from its panels."""

    parts: list[str] = [str(scene.brief or "")]
    panels = (
        db.query(GraphicNovelPanel)
        .filter(GraphicNovelPanel.scene_id == scene.id)
        .order_by(GraphicNovelPanel.panel_index.asc())
        .all()
    )
    for panel in panels:
        overlay = panel.overlay_payload if isinstance(panel.overlay_payload, dict) else {}
        narration = overlay.get("narration_fr") or panel.beat
        if narration:
            parts.append(str(narration))
        for line in overlay.get("dialogue") or ():
            text = (line or {}).get("text_fr") if isinstance(line, dict) else None
            if text:
                parts.append(str(text))
    return " ".join(part for part in parts if part)


@dataclass(frozen=True)
class SceneCoverageRow:
    """One row of the coverage report: stored, or honestly labelled recomputed."""

    scene_id: str
    created_at: datetime | None
    title: str
    coverage: float
    accidental_count: int
    target_count: int
    accidental: tuple[str, ...]
    origin: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "scene_id": self.scene_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "title": self.title,
            "coverage": round(self.coverage, 4),
            "accidental_count": self.accidental_count,
            "target_count": self.target_count,
            "accidental": list(self.accidental),
            "origin": self.origin,
        }


def recent_scene_coverage(
    db: Session,
    *,
    user: User,
    limit: int = 14,
    recompute: bool = True,
    resolver: LemmaResolver | None = None,
) -> list[SceneCoverageRow]:
    """Coverage over this learner's last ``limit`` generated scenes.

    A scene whose metadata the hook wrote is reported as ``stored``. Until that
    hook lands, coverage is recomputed from the stored panels and labelled
    ``recomputed`` — against *today's* known-word set, not the one the learner
    had on the day, which is why the label is on the row.
    """

    scenes = (
        db.query(GraphicNovelScene)
        .filter(GraphicNovelScene.user_id == user.id)
        .order_by(GraphicNovelScene.created_at.desc())
        .limit(max(1, limit))
        .all()
    )
    known = known_word_set(db, user=user) if recompute else None
    rows: list[SceneCoverageRow] = []
    for scene in scenes:
        stored = stored_scene_coverage(scene)
        if stored:
            accidental = tuple(
                str(item.get("surface") or item.get("lemma"))
                for item in stored.get("accidental_unknowns") or ()
            )
            rows.append(
                SceneCoverageRow(
                    scene_id=str(scene.id),
                    created_at=scene.created_at,
                    title=str(scene.title or ""),
                    coverage=float(stored.get("coverage") or 0.0),
                    accidental_count=int(stored.get("accidental_count") or len(accidental)),
                    target_count=int(stored.get("target_count") or 0),
                    accidental=accidental,
                    origin="stored",
                )
            )
            continue
        if not recompute or known is None:
            continue
        text = scene_reading_text(db, scene)
        result = text_coverage(text, known, resolver=resolver)
        if not result.is_assessable:
            continue
        rows.append(
            SceneCoverageRow(
                scene_id=str(scene.id),
                created_at=scene.created_at,
                title=str(scene.title or ""),
                coverage=result.coverage,
                accidental_count=len(result.accidental),
                target_count=len(result.targets),
                accidental=tuple(word.surface for word in result.accidental[:MAX_HINT_WORDS]),
                origin="recomputed",
            )
        )
    return rows


def coverage_distribution(rows: list[SceneCoverageRow]) -> dict[str, Any]:
    """Median, p10 and the share at or above the floor. Denominators included."""

    if not rows:
        return {"scenes": 0, "status": "insufficient_data"}
    values = sorted(row.coverage for row in rows)
    at_floor = sum(1 for value in values if value >= SUPPORTED_COVERAGE_FLOOR)
    unassisted = sum(1 for value in values if value >= UNASSISTED_COVERAGE_FLOOR)
    return {
        "scenes": len(values),
        "status": "ok",
        "median": values[len(values) // 2],
        "p10": values[max(0, int(len(values) * 0.1) - 1)] if len(values) >= 10 else values[0],
        "min": values[0],
        "max": values[-1],
        "at_supported_floor": at_floor,
        "at_unassisted_floor": unassisted,
        "stored": sum(1 for row in rows if row.origin == "stored"),
        "recomputed": sum(1 for row in rows if row.origin == "recomputed"),
        "floor": SUPPORTED_COVERAGE_FLOOR,
    }


def format_coverage_line(db: Session, day: date, user_id: str | None = None) -> str:
    """One digest line for the day's generated scenes (spec §3.5).

    Reads only what the generator stored. If the WP-29 hook has not landed in
    ``living_story.py`` yet, that is said in as many words — a coverage number
    nobody measured is not zero, and not 100 %.
    """

    query = db.query(GraphicNovelScene).filter(func.date(GraphicNovelScene.created_at) == day)
    if user_id:
        query = query.filter(GraphicNovelScene.user_id == UUID(str(user_id)))
    scenes = query.all()
    if not scenes:
        return "Lexical coverage: no scenes"
    rows = [
        SceneCoverageRow(
            scene_id=str(scene.id),
            created_at=scene.created_at,
            title=str(scene.title or ""),
            coverage=float(stored.get("coverage") or 0.0),
            accidental_count=int(stored.get("accidental_count") or 0),
            target_count=int(stored.get("target_count") or 0),
            accidental=(),
            origin="stored",
        )
        for scene in scenes
        if (stored := stored_scene_coverage(scene))
    ]
    if not rows:
        return (
            f"Lexical coverage: {len(scenes)} scene(s), none measured "
            "(WP-29 hook not applied in living_story.py)"
        )
    stats = coverage_distribution(rows)
    accidental = sum(row.accidental_count for row in rows)
    return (
        f"Lexical coverage: {stats['scenes']}/{len(scenes)} scene(s) measured · "
        f"median {stats['median'] * 100:.1f}% · min {stats['min'] * 100:.1f}% · "
        f"{stats['at_supported_floor']}/{stats['scenes']} at the "
        f"{SUPPORTED_COVERAGE_FLOOR * 100:.0f}% floor · "
        f"{accidental} accidental unknown(s)"
    )


__all__ = [
    "ACCENT_FALLBACK_MIN_LENGTH",
    "ACCIDENTAL_UNKNOWN_BUDGET",
    "COVERAGE_VERSION",
    "MAX_HINT_WORDS",
    "MIN_ASSESSED_TOKENS",
    "MIN_KNOWN_LEMMAS",
    "REJECT_LOW_COVERAGE",
    "REJECT_UNKNOWN_BUDGET",
    "SCENE_METADATA_KEY",
    "SUPPORTED_COVERAGE_FLOOR",
    "UNASSISTED_COVERAGE_FLOOR",
    "CoverageResult",
    "CoverageVerdict",
    "CuratedResolver",
    "KnownWordSet",
    "LearnerLexicon",
    "Lexicon",
    "SceneCoverageRow",
    "SceneText",
    "SpacyResolver",
    "Token",
    "UnknownWord",
    "accidental_budget",
    "band_of",
    "check_scene_coverage",
    "coverage_distribution",
    "default_resolver",
    "fold",
    "format_coverage_line",
    "known_word_set",
    "load_lexicon",
    "nailed_lemmas",
    "recent_scene_coverage",
    "scene_reading_text",
    "scene_text_from_draft",
    "stored_scene_coverage",
    "text_coverage",
    "tokenize",
    "world_proper_nouns",
]
