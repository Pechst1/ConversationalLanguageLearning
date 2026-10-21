"""The rules whose form *is* an order: pronoun order, ne … pas.

#271 / #146: a word-bank miss that only reorders the words is «word order» unless
the order is what the unit teaches. «Tu peux le me prêter» for «Tu peux me le
prêter» is the day's rule («me/te before le/la/les»), not a loose word order. The
decision used to live in one place (the bank items' ``target_span``), so every item
without that field, the fallback word banks among them, said «word order» about a
rule miss. It now comes from the rule's own elements, here, for both word-bank
paths: :func:`form_intact` says whether the elements the unit orders are still
together in the order the key has them.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any

#: Unit families that order their own elements, by external id.
_PRONOUN_CLUSTER_UNITS = re.compile(r"DOUBLE_PRONOUN")
_NEGATION_FRAME_UNITS = re.compile(r"(^|_)NEG(ATION|_|$)|_NEG_")

_CLITICS = frozenset(
    {"me", "m'", "te", "t'", "se", "s'", "nous", "vous", "le", "la", "les", "l'", "lui", "leur", "y", "en"}
)
_NEGATION_SECOND = frozenset({"pas", "plus", "jamais", "rien", "personne"})
_NEGATION_FIRST = frozenset({"ne", "n'"})


def _words(text: Any) -> list[str]:
    """Lower-case words with accents folded; an elided clitic is its own word
    («m'en» → «m'», «en»), punctuation is dropped."""

    value = re.sub(r"[‘’‚‛′`´ʹʻʼ]", "'", str(text or "")).lower()
    value = "".join(ch for ch in unicodedata.normalize("NFKD", value) if not unicodedata.combining(ch))
    return re.findall(r"[a-z]+'?", value)


def order_kind(external_id: Any) -> str | None:
    """``"pronouns"`` / ``"negation"`` when the unit teaches that order, else ``None``."""

    unit = str(external_id or "").upper()
    if _PRONOUN_CLUSTER_UNITS.search(unit):
        return "pronouns"
    if _NEGATION_FRAME_UNITS.search(unit):
        return "negation"
    return None


def _pronoun_runs(words: list[str]) -> list[list[str]]:
    runs: list[list[str]] = []
    current: list[str] = []
    for word in [*words, ""]:
        if word in _CLITICS:
            current.append(word)
            continue
        if len(current) >= 2:
            runs.append(current)
        current = []
    return runs


def _negation_frames(words: list[str]) -> list[list[str]]:
    frames: list[list[str]] = []
    for index, word in enumerate(words):
        if word not in _NEGATION_FIRST:
            continue
        for end in range(index + 1, min(index + 4, len(words))):
            if words[end] in _NEGATION_SECOND:
                frames.append(words[index : end + 1])
                break
    return frames


def rule_elements(external_id: Any, target: Any) -> list[list[str]]:
    """The stretches of ``target`` the unit's rule orders (empty for any other unit)."""

    kind = order_kind(external_id)
    words = _words(target)
    if kind == "pronouns":
        return _pronoun_runs(words)
    if kind == "negation":
        return _negation_frames(words)
    return []


def form_intact(external_id: Any, learner: Any, target: Any) -> bool | None:
    """Whether every stretch the rule orders is in ``learner`` as the key has it.

    ``None`` when the unit teaches no order, or ``target`` has no such stretch: the
    caller keeps its own reading of the miss.
    """

    elements = rule_elements(external_id, target)
    if not elements:
        return None
    said = f" {' '.join(_words(learner))} "
    return all(f" {' '.join(element)} " in said for element in elements)
