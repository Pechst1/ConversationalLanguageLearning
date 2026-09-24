"""WP-S1 (La Forge): grade locally, never block on the model.

Everything the séance can check against an answer key is checked here, in
microseconds, on the request path:

* the comparison folds what is typography, not French — apostrophe and quote
  variants (``journey_contracts.normalize_answer_text``), case, exotic spaces and
  the final punctuation mark — and keeps the accents, so an accent slip is
  *reported* even where the grader forgives it;
* a token-level diff says *what* is wrong in a rewrite or a word-bank line: the
  ending of one word, a missing word, a stray one, or only the order;
* a unit's regex detectors (WP-L2 v2 catalogue) or, for v1 units, the profile
  matcher tell whether a free sentence uses the rule at all.

Free production (a sentence, the paragraph, a spoken transcript, a
conversation turn) still gets the model's verdict, but asynchronously: the
request returns :func:`production_local_check` at once and the relecture amends
the stored correction when it lands (``AtelierCorrectionService``).
"""
from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any

from app.services.journey_contracts import normalize_answer_text
from app.services.learner_copy import learner_text as _copy

#: Rungs graded by the model — asynchronously — after an instant local verdict.
FREE_PRODUCTION_ROUNDS: frozenset[str] = frozenset({"sentence", "speak", "conversation", "produce"})

#: Rungs graded by an answer key; the model never decides these verdicts.
KEYED_ROUNDS: frozenset[str] = frozenset({"recognize", "transform"})

_FINAL_PUNCTUATION = " .!?;:,…"
#: An elided particle («l'», «j'», «qu'») is its own token; «aujourd'hui» stays whole.
_TOKEN = re.compile(
    r"\b(?:jusqu|lorsqu|puisqu|quoiqu|qu|[cdjlmnst])'|\w+(?:['-]\w+)*|[^\s\w]",
    re.UNICODE | re.IGNORECASE,
)


def fold_typography(value: Any) -> str:
    """Quotes, case, spacing and the final punctuation folded; accents kept."""

    text = normalize_answer_text("" if value is None else str(value))
    text = unicodedata.normalize("NFC", text).casefold()
    text = re.sub(r"[«»\"]", " ", text)
    text = re.sub(r"'\s+", "'", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    return " ".join(text.split()).strip(_FINAL_PUNCTUATION)


def strip_accents(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def tokens(value: Any) -> list[str]:
    """Words (an elided «l'», «j'» stays one token) — punctuation is dropped."""

    return [token for token in _TOKEN.findall(fold_typography(value)) if token[0].isalnum()]


def same_answer(learner: Any, target: Any) -> tuple[bool, bool]:
    """``(matches, accent_slip)``: does it match, and only once accents are folded?"""

    left, right = fold_typography(learner), fold_typography(target)
    if not right:
        return False, False
    if left == right:
        return True, False
    folded_match = strip_accents(left) == strip_accents(right)
    return folded_match, folded_match


def _ending(learner: str, target: str) -> tuple[str, str] | None:
    """Same stem, different ending: ``("arrive", "arrivera")`` -> the two words."""

    prefix = 0
    for left, right in zip(strip_accents(learner), strip_accents(target), strict=False):
        if left != right:
            break
        prefix += 1
    stem = min(len(learner), len(target))
    if prefix >= 3 or (stem and prefix >= stem - 1 and prefix >= 2):
        return learner, target
    return None


def token_diff(learner: Any, target: Any) -> list[dict[str, str]]:
    """What separates the learner's line from the key, one operation per difference.

    Kinds: ``ending`` (same stem), ``accent``, ``word`` (a different word),
    ``missing``, ``extra`` and ``order`` (same words, other order — reported alone).
    """

    left, right = tokens(learner), tokens(target)
    if left == right:
        return []
    if sorted(strip_accents(token) for token in left) == sorted(strip_accents(token) for token in right) and [
        strip_accents(token) for token in left
    ] != [strip_accents(token) for token in right]:
        return [{"kind": "order", "learner": " ".join(left), "target": " ".join(right)}]
    ops: list[dict[str, str]] = []
    matcher = SequenceMatcher(a=[strip_accents(token) for token in left], b=[strip_accents(token) for token in right], autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for offset in range(i2 - i1):
                if left[i1 + offset] != right[j1 + offset]:
                    ops.append({"kind": "accent", "learner": left[i1 + offset], "target": right[j1 + offset]})
            continue
        if tag == "delete":
            ops.extend({"kind": "extra", "learner": token, "target": ""} for token in left[i1:i2])
            continue
        if tag == "insert":
            ops.extend({"kind": "missing", "learner": "", "target": token} for token in right[j1:j2])
            continue
        # replace: pair the words up in order; any surplus is missing / extra.
        pairs = list(zip(left[i1:i2], right[j1:j2], strict=False))
        for learner_word, target_word in pairs:
            kind = "ending" if _ending(learner_word, target_word) else "word"
            ops.append({"kind": kind, "learner": learner_word, "target": target_word})
        ops.extend({"kind": "extra", "learner": token, "target": ""} for token in left[i1 + len(pairs):i2])
        ops.extend({"kind": "missing", "learner": "", "target": token} for token in right[j1 + len(pairs):j2])
    return ops


def describe_diff(ops: list[dict[str, str]], language: Any) -> str:
    """One or two short sentences, in the learner's language, naming the difference."""

    sentences: list[str] = []
    for op in ops:
        kind = op.get("kind")
        if kind == "accent":
            continue
        if kind == "order":
            sentences.append(_copy("forge.diff.order", language))
        elif kind == "ending":
            sentences.append(_copy("forge.diff.ending", language, learner=op["learner"], target=op["target"]))
        elif kind == "word":
            sentences.append(_copy("forge.diff.word", language, learner=op["learner"], target=op["target"]))
        elif kind == "missing":
            sentences.append(_copy("forge.diff.missing", language, target=op["target"]))
        elif kind == "extra":
            sentences.append(_copy("forge.diff.extra", language, learner=op["learner"]))
        if len(sentences) == 2:
            break
    return " ".join(sentences)


def similarity(learner: Any, target: Any) -> float:
    """0–1 token similarity to a model answer (accent-insensitive)."""

    left = [strip_accents(token) for token in tokens(learner)]
    right = [strip_accents(token) for token in tokens(target)]
    if not left or not right:
        return 0.0
    return round(SequenceMatcher(a=left, b=right, autojunk=False).ratio(), 3)


def detector_check(concept: Any, text: str) -> dict[str, Any]:
    """Does ``text`` use the unit? ``{"status": hit|miss|unknown, "span", "source"}``.

    The v2 unit's own regex detectors decide when it has them (fixed expressions
    such as «un peu» never count); v1 units fall back to the profile matcher.
    """

    if concept is None or not str(text or "").strip():
        return {"status": "unknown", "span": None, "source": None}
    try:
        from app.services.grammar_items import detector_span
        from app.services.grammar_units import regex_patterns, unit_detectors

        patterns = regex_patterns(unit_detectors(concept))
    except Exception:  # pragma: no cover - a catalogue read must never fail a grade
        patterns = []
    if patterns:
        span = detector_span(patterns, text)
        return {"status": "hit" if span else "miss", "span": span, "source": "detector"}
    from app.services.grammar_feedback import count_concept_hits

    hits = count_concept_hits(concept, text)
    return {"status": "hit" if hits else "miss", "span": None, "source": "profile"}


def production_local_check(concept: Any, text: str, model_answer: Any = None) -> dict[str, Any]:
    """The instant verdict for free production: the rule's detector, and closeness to a model answer."""

    check = detector_check(concept, text)
    result: dict[str, Any] = {"detector": check["status"], "span": check["span"], "source": check["source"]}
    if model_answer:
        result["model_similarity"] = similarity(text, model_answer)
    return result


__all__ = [
    "FREE_PRODUCTION_ROUNDS",
    "KEYED_ROUNDS",
    "describe_diff",
    "detector_check",
    "fold_typography",
    "production_local_check",
    "same_answer",
    "similarity",
    "strip_accents",
    "token_diff",
    "tokens",
]
