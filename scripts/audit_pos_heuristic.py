"""Report how often the suffix part-of-speech heuristic disagrees with spaCy.

`app/services/vocabulary_coverage.inferred_part_of_speech` used to guess a word's
part of speech from its ending alone: anything longer than four letters ending in
-er/-ir/-re/-oir was a verb. That is right for most of the deck and confidently
wrong for a visible minority — `plaisir`, `avenir`, `exemplaire` and `dernier`
are a noun, a noun, a noun and an adjective, and the review card printed them to
the learner as verbs.

This script measures the damage and produces the curated override list that fixes
the known-wrong set. It reads only: nothing is written to the database.

    .venv/bin/python scripts/audit_pos_heuristic.py
    .venv/bin/python scripts/audit_pos_heuristic.py --limit 2000 --show 40
    .venv/bin/python scripts/audit_pos_heuristic.py --emit-overrides app/data/pos_overrides.json

spaCy is optional. Without `FRENCH_NLP_MODEL` installed the script says so and
exits 0, so it can sit in CI without pinning a model download.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select  # noqa: E402

from app.config import settings  # noqa: E402
from app.db.models.vocabulary import VocabularyWord  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.services.vocabulary_coverage import (  # noqa: E402
    POS_OVERRIDES_PATH,
    heuristic_part_of_speech,
    normalize_pos_tag,
)

#: spaCy's universal tags, folded to the vocabulary vocabulary we store.
SPACY_TO_POS: dict[str, str] = {
    "VERB": "verb",
    "AUX": "verb",
    "NOUN": "noun",
    "PROPN": "noun",
    "ADJ": "adjective",
    "ADV": "adverb",
    "PRON": "function",
    "DET": "function",
    "ADP": "function",
    "CCONJ": "function",
    "SCONJ": "function",
    "PART": "function",
    "NUM": "function",
    "INTJ": "function",
}


def load_nlp() -> Any | None:
    """The French pipeline, or None when it is not installed here."""
    try:
        import spacy
    except Exception:
        return None
    try:
        return spacy.load(settings.FRENCH_NLP_MODEL)
    except Exception:
        return None


def spacy_pos(nlp: Any, word: VocabularyWord) -> tuple[str, str]:
    """spaCy's tag for one deck row, read twice: in context and on its own.

    A bare French infinitive is genuinely ambiguous to a tagger — `souvenir`
    alone comes back VERB, `diminuer` inside a sentence can come back ADV — so
    neither reading is trusted alone. The example sentence is how the learner
    actually meets the word, which makes it the primary reading; the isolated
    reading is the second opinion that decides whether an answer is confident
    enough to be written into the override file.

    Returns `(context_tag, isolated_tag)`; either half may be "".
    """
    surface = str(word.word or word.normalized_word or "").strip()
    if not surface:
        return "", ""

    context_tag = ""
    example = str(word.example_sentence or "").strip()
    if example:
        folded = surface.casefold()
        for token in nlp(example):
            if token.text.casefold() == folded or (token.lemma_ or "").casefold() == folded:
                context_tag = SPACY_TO_POS.get(token.pos_, "")
                break

    isolated_tag = ""
    doc = nlp(surface)
    for token in doc:
        # A multi-word surface ("avoir besoin") is headed by its first content token.
        if token.pos_ not in {"DET", "PUNCT", "SPACE"}:
            isolated_tag = SPACY_TO_POS.get(token.pos_, "")
            break
    return context_tag, isolated_tag


#: What the tagger is allowed to say about a surface the heuristic read as a verb.
#: French infinitives are the tagger's own weak spot — inside a sentence it will
#: happily call `diminuer` an adverb and `prier` an adjective — so a verb→noun or
#: verb→function correction (`foyer`, `métier`, `guère`) is accepted and a
#: verb→adjective/adverb one is refused rather than frozen into the deck.
VERB_LOOKING_SUFFIXES = ("er", "ir", "re", "oir")
VERB_CORRECTIONS_ACCEPTED = {"noun", "function"}


#: The hand-checked layer on top of the tagger. Two kinds of entry:
#:
#: * a surface the tagger got wrong in *both* readings, so the confidence gate
#:   above let it through — `pratiquement` is an adverb, `analyste` and `poète`
#:   are nouns, `été` here is the season;
#: * a surface the tagger and the heuristic happen to agree on and both get
#:   wrong — the -ir/-aire nouns and the -ier adjectives that started this work
#:   (`exemplaire` printed on the review card as a verb).
#:
#: Everything here was read by a person. Nothing is inferred.
CURATED_CORRECTIONS: dict[str, str] = {
    # Adverbs the tagger called verbs.
    "carrément": "adverb",
    "durement": "adverb",
    "politiquement": "adverb",
    "pratiquement": "adverb",
    "sincèrement": "adverb",
    "sûrement": "adverb",
    # Nouns the tagger called verbs or adjectives.
    "analyste": "noun",
    "consentement": "noun",
    "difficulté": "noun",
    "enceinte": "noun",
    "honte": "noun",
    "hâte": "noun",
    "islamiste": "noun",
    "nouveauté": "noun",
    "poète": "noun",
    "progressiste": "noun",
    "prophète": "noun",
    "socialiste": "noun",
    "séparatiste": "noun",
    "terroriste": "noun",
    "variété": "noun",
    "équipement": "noun",
    "été": "noun",
    # The -ir / -aire nouns and -ier adjectives the suffix rule reads as verbs.
    "avenir": "noun",
    "désir": "noun",
    "exemplaire": "noun",
    "loisir": "noun",
    "plaisir": "noun",
    "souvenir": "noun",
    "dernier": "adjective",
    "premier": "adjective",
}


def is_trustworthy(surface: str, heuristic: str, tagged: str) -> bool:
    if heuristic == "verb" and surface.lower().endswith(VERB_LOOKING_SUFFIXES):
        return tagged in VERB_CORRECTIONS_ACCEPTED
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit the suffix part-of-speech heuristic")
    parser.add_argument("--limit", type=int, default=None, help="Only the N most frequent rows")
    parser.add_argument("--show", type=int, default=25, help="How many mismatches to print")
    parser.add_argument(
        "--emit-overrides",
        type=Path,
        default=None,
        help=(
            "Write the confidently-mismatching surfaces as an override file "
            "(both spaCy readings agree and the heuristic disagrees)"
        ),
    )
    args = parser.parse_args()

    nlp = load_nlp()
    if nlp is None:
        print(
            f"spaCy model {settings.FRENCH_NLP_MODEL!r} is not available here; "
            f"skipping the audit. The curated list in {POS_OVERRIDES_PATH.relative_to(ROOT)} "
            "still applies at runtime."
        )
        return 0

    db = SessionLocal()
    try:
        query = select(VocabularyWord).where(VocabularyWord.language == "fr")
        query = query.order_by(VocabularyWord.frequency_rank.is_(None), VocabularyWord.frequency_rank)
        if args.limit:
            query = query.limit(args.limit)
        rows = list(db.scalars(query))
    finally:
        db.close()

    compared = 0
    mismatches: list[tuple[str, str, str]] = []
    confident_compared = 0
    confident_mismatches: list[tuple[str, str, str]] = []
    by_suffix: Counter[str] = Counter()
    for row in rows:
        heuristic = normalize_pos_tag(heuristic_part_of_speech(row))
        context_tag, isolated_tag = spacy_pos(nlp, row)
        tagged = normalize_pos_tag(context_tag or isolated_tag)
        if not heuristic or not tagged:
            continue
        compared += 1
        surface = str(row.word or row.normalized_word or "").strip()
        # Confident: both readings exist and agree. That is the only evidence
        # strong enough to be frozen into a file the review card prints from.
        confident = (
            bool(context_tag)
            and context_tag == isolated_tag
            and is_trustworthy(surface, heuristic, tagged)
        )
        if confident:
            confident_compared += 1
        if heuristic != tagged:
            mismatches.append((surface, heuristic, tagged))
            by_suffix[surface[-3:].lower()] += 1
            if confident:
                confident_mismatches.append((surface, heuristic, tagged))

    rate = (len(mismatches) / compared * 100) if compared else 0.0
    unresolved = len(mismatches) - len(confident_mismatches)
    residual = (unresolved / compared * 100) if compared else 0.0
    print(f"rows read                 : {len(rows)}")
    print(f"rows compared             : {compared}")
    print(f"heuristic mismatches      : {len(mismatches)}")
    print(f"heuristic mismatch rate   : {rate:.2f}%")
    print(f"confident comparisons     : {confident_compared}")
    print(f"confident mismatches      : {len(confident_mismatches)}  (these become overrides)")
    print(f"residual after overrides  : {unresolved} ({residual:.2f}%)")
    if by_suffix:
        top = ", ".join(f"-{suffix}:{count}" for suffix, count in by_suffix.most_common(8))
        print(f"worst endings             : {top}")
    for surface, heuristic, tagged in confident_mismatches[: args.show]:
        print(f"  {surface:<24} heuristic={heuristic:<10} spacy={tagged}")
    if len(confident_mismatches) > args.show:
        print(f"  … {len(confident_mismatches) - args.show} more")

    if args.emit_overrides:
        overrides = {
            surface.lower(): tagged for surface, _heuristic, tagged in sorted(confident_mismatches)
        }
        corrected = sum(1 for key in CURATED_CORRECTIONS if overrides.get(key) != CURATED_CORRECTIONS[key])
        overrides.update(CURATED_CORRECTIONS)
        overrides = dict(sorted(overrides.items()))
        print(f"curated corrections applied: {corrected}")
        payload = {
            "version": "pos-overrides-v1",
            "source": f"scripts/audit_pos_heuristic.py against {settings.FRENCH_NLP_MODEL}",
            "note": (
                "Surfaces where the suffix heuristic disagrees with the tagger and both "
                "of the tagger's readings — in the word's example sentence and on the bare "
                "word — agree with each other, plus the hand-checked corrections in "
                "CURATED_CORRECTIONS. The resolver reads this file first."
            ),
            "overrides": overrides,
        }
        args.emit_overrides.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
            encoding="utf-8",
        )
        print(f"wrote {len(payload['overrides'])} overrides to {args.emit_overrides}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
