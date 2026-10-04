"""«Vérification du lexique» — skip the words a learner already knows (2026-10-03).

The owner's goal is progress substantially faster than Duolingo. The level gate
asks for 80 % of each sub-band's core words on a known card; a learner placed at
B1 who already reads A1/A2 French would otherwise spend months re-carding words
they know. After placement, each sub-band *below* the learner's own can be
checked in about two minutes:

* :data:`ITEMS` core words of the sub-band (no grammar words, numerals or
  colloquial words), each a four-way meaning choice in the learner's language,
  plus «je ne sais pas»;
* the sample is seeded by learner, sub-band and day, so a retry the same day
  gets the same questions;
* :data:`PASS_SHARE` correct or better credits the sub-band: every core word of
  it the learner has no card for gets a settled card (``provenance="band_check"``)
  that counts as known now and comes back for a light check over the next weeks
  (:data:`VERIFY_WITHIN_DAYS`). A word missed in the check is not credited — it
  stays in the ordinary new-word supply.

Pure apart from the database reads and the credit write; no model call.
"""

from __future__ import annotations

import hashlib
import random
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.progress import UserVocabularyProgress
from app.db.models.vocabulary import VocabularyWord
from app.services.core_lexicon import CORE_DECK, ensure_core_lexicon
from app.services.lexical_coverage import load_lexicon

ITEMS = 24
OPTIONS = 4
PASS_SHARE = 0.9
PROVENANCE = "band_check"
#: The credited card: settled, known now, first light check within these days.
CREDIT_STABILITY_DAYS = 30.0
VERIFY_WITHIN_DAYS = (10, 45)
#: EXPERIENCE-REVIEW 2026-10-04: the light check's window by how far below the
#: learner's own sub-band the credited one lies. A B2 learner credits about 2,800
#: words; all of them checked within 10–45 days came back at ~80 a day, filled the
#: drill (its 30 due a session) for weeks, and the throttle halved new words to 4.
#: Words a learner proved in a band far below their own are trusted longer.
VERIFY_WINDOWS: dict[int, tuple[int, int]] = {1: (20, 90), 2: (40, 180), 3: (90, 365)}


def credit_schedule(distance: int) -> tuple[float, tuple[int, int]]:
    """``(stability, (first, last) day of the light check)`` for a credited sub-band
    ``distance`` sub-bands below the learner's own. The stability keeps the word
    known (retrievability ≥ 0.85) until its check is due."""

    window = VERIFY_WINDOWS.get(max(1, distance)) or VERIFY_WINDOWS[max(VERIFY_WINDOWS)]
    return max(CREDIT_STABILITY_DAYS, window[1] / 1.5), window
SUB_BANDS = ("A1.1", "A1.2", "A2.1", "A2.2", "B1.1", "B1.2", "B2.1", "B2.2", "C1.1", "C1.2")


def _language(user: Any) -> str:
    native = str(getattr(user, "native_language", "") or "").lower()[:2]
    return native if native in {"en", "de"} else "en"


def _sub_band(level: str | None) -> str:
    """«A2.1» stays itself; a coarse «A2» (a declaration) is its first half."""

    raw = str(level or "").strip().upper()
    if raw in SUB_BANDS:
        return raw
    if raw.startswith("C2"):
        return SUB_BANDS[-1]
    coarse = raw[:2] if raw[:2] in {"A1", "A2", "B1", "B2", "C1"} else "A1"
    return f"{coarse}.1"


def _pool(sub_band: str) -> list[tuple[str, dict[str, Any]]]:
    """The sub-band's checkable core words, in list order."""

    return sorted(
        (
            (lemma, entry)
            for lemma, entry in load_lexicon().lemmas.items()
            if entry.get("sub_band") == sub_band
            and not entry.get("numeral")
            and entry.get("pos") not in {"function", "number"}
            and entry.get("register") != "familier"
            and isinstance(entry.get("gloss"), dict)
        ),
        key=lambda item: int(item[1].get("rank") or 0),
    )


def _seed(user: Any, sub_band: str, day: str) -> int:
    digest = hashlib.sha256(f"{getattr(user, 'id', '')}:{sub_band}:{day}".encode()).hexdigest()
    return int(digest[:12], 16)


#: EXERCISE-QA: nouns with an aspirated h take «le/la», never «l'» («le haricot»,
#: «la honte», «le héros»). The lexicon does not mark them.
H_ASPIRE: frozenset[str] = frozenset(
    {
        "hache", "haie", "haillon", "haine", "hall", "halle", "halte", "hamac", "hameau", "hamburger",
        "hamster", "hanche", "handball", "handicap", "hangar", "hareng", "haricot", "harnais", "harpe",
        "hasard", "hâte", "hausse", "haut", "hauteur", "havre", "hérisson", "hernie", "héros", "hêtre",
        "hibou", "hiérarchie", "hockey", "homard", "honte", "hoquet", "hotte", "housse", "houx", "hublot",
        "huit", "hurlement", "hutte", "hachis", "haddock", "hachette", "hamecon", "hameçon", "harcèlement",
        "hardiesse", "harem", "hargne", "hennissement", "héron", "hérault", "hollande", "hongrie", "huée",
        "huguenot", "hune", "huppe",
    }
)


def _shown(lemma: str, entry: dict[str, Any]) -> str:
    """A noun with its article, so the gender is part of what is recognised."""

    if entry.get("pos") != "noun":
        return lemma
    gender = entry.get("gender")
    if lemma[:1].lower() in "aeéèêiîoôuûh" and lemma.lower() not in H_ASPIRE:
        return f"l'{lemma}"
    return f"{'la' if gender == 'f' else 'le'} {lemma}"


def sample(user: Any, sub_band: str, *, now: datetime | None = None) -> list[dict[str, Any]]:
    """The day's check items for a sub-band: ``{id, fr, options[]}`` (no answer key)."""

    return [{k: v for k, v in item.items() if k != "answer"} for item in _items(user, sub_band, now=now)]


def _items(user: Any, sub_band: str, *, now: datetime | None = None) -> list[dict[str, Any]]:
    now = now or datetime.now(UTC)
    language = _language(user)
    pool = _pool(sub_band)
    if len(pool) < ITEMS:
        return []
    rng = random.Random(_seed(user, sub_band, now.date().isoformat()))  # noqa: S311 - a seeded sample, not a secret
    picked = rng.sample(pool, ITEMS)
    items: list[dict[str, Any]] = []
    for lemma, entry in picked:
        right = str(entry["gloss"].get(language) or entry["gloss"].get("en") or "")
        same_pos = [
            str(other["gloss"].get(language) or "")
            for other_lemma, other in pool
            if other_lemma != lemma and other.get("pos") == entry.get("pos")
        ]
        distractors = [gloss for gloss in dict.fromkeys(same_pos) if gloss and gloss != right]
        options = [right, *rng.sample(distractors, min(OPTIONS - 1, len(distractors)))]
        rng.shuffle(options)
        items.append({"id": lemma, "fr": _shown(lemma, entry), "options": options, "answer": options.index(right)})
    return items


def checkable(db: Session, user: Any) -> list[dict[str, Any]]:
    """Sub-bands below the learner's own, each with its word count and whether credited."""

    from app.services.lexical_coverage import _cefr_estimate

    level, _source = _cefr_estimate(db, user)
    current = SUB_BANDS.index(_sub_band(level))
    credited = credited_sub_bands(db, user)
    return [
        {"sub_band": band, "words": len(_pool(band)), "credited": band in credited}
        for band in SUB_BANDS[:current]
        if len(_pool(band)) >= ITEMS
    ]


def credited_sub_bands(db: Session, user: Any) -> set[str]:
    rows = db.scalars(
        select(UserVocabularyProgress.provenance_ref).where(
            UserVocabularyProgress.user_id == user.id,
            UserVocabularyProgress.provenance == PROVENANCE,
        ).distinct()
    )
    return {str(ref) for ref in rows if ref}


def submit(
    db: Session, user: Any, sub_band: str, answers: dict[str, int | None], *, now: datetime | None = None
) -> dict[str, Any]:
    """Grade the day's items; on a pass credit the sub-band. Flushes, never commits."""

    now = now or datetime.now(UTC)
    items = _items(user, sub_band, now=now)
    if not items:
        raise ValueError(f"no check for {sub_band}")
    missed = {item["id"] for item in items if answers.get(item["id"]) != item["answer"]}
    correct = len(items) - len(missed)
    passed = correct >= PASS_SHARE * len(items)
    credited = credit(db, user, sub_band, exclude=missed, now=now) if passed else 0
    return {
        "sub_band": sub_band,
        "correct": correct,
        "total": len(items),
        "passed": passed,
        "credited_words": credited,
        "missed": sorted(missed),
    }


def credit(db: Session, user: Any, sub_band: str, *, exclude: set[str] = frozenset(), now: datetime) -> int:
    """Settled, known cards for the sub-band's core words the learner has no card for."""

    ensure_core_lexicon(db)
    lemmas = {lemma for lemma, _entry in _pool(sub_band)} - set(exclude)
    rows = db.scalars(
        select(VocabularyWord).where(
            VocabularyWord.deck_name == CORE_DECK, VocabularyWord.normalized_word.in_(lemmas)
        )
    ).all()
    have = set(
        db.scalars(
            select(VocabularyWord.normalized_word)
            .join(UserVocabularyProgress, UserVocabularyProgress.word_id == VocabularyWord.id)
            .where(UserVocabularyProgress.user_id == user.id)
        )
    )
    from app.services.lexical_coverage import _cefr_estimate

    level, _source = _cefr_estimate(db, user)
    distance = SUB_BANDS.index(_sub_band(level)) - SUB_BANDS.index(sub_band) if sub_band in SUB_BANDS else 1
    stability, window = credit_schedule(distance)
    written = 0
    for word in rows:
        if word.normalized_word in have:
            continue
        rng = random.Random(f"{getattr(user, 'id', '')}:{word.id}")  # noqa: S311 - a seeded spread
        due = now + timedelta(days=rng.randint(*window))
        db.add(
            UserVocabularyProgress(
                user_id=user.id,
                word_id=word.id,
                stability=stability,
                difficulty=4.0,
                reps=2,
                lapses=0,
                state="review",
                phase="review",
                scheduler="fsrs",
                scheduled_days=(due - now).days,
                interval_days=(due - now).days,
                last_review_date=now,
                next_review_date=due,
                due_at=due,
                due_date=due.date(),
                proficiency_score=80,
                times_seen=1,
                provenance=PROVENANCE,
                provenance_ref=sub_band,
            )
        )
        written += 1
    db.flush()
    return written


__all__ = ["ITEMS", "PASS_SHARE", "PROVENANCE", "checkable", "credit", "credit_schedule", "credited_sub_bands", "sample", "submit"]
