"""R2 (walk of 17 Nov 2026): La Forge never deals a free card the learner cannot solve.

A free card («Lila : « La fête des voisins ? » Réponds en français, avec cette règle.»)
refused five grammatical answers on the B1 walk, each for an intent the card never
stated: the stored item carried the English reply it wanted («Reply in French: "Yes,
I'm suggesting it to them."»), the French screen did not show it, and the grader read
it. Three rules hold every free card (``sentence``, ``speak``, ``conversation``):

* **It states what it is judged on.** A meaning the screen did not quote is not the
  task: the grader is told the card as the learner read it (``own_sentence``), and a
  task note it still writes about content is dropped once the card's rule is in the
  answer (:func:`only_what_the_card_asked`). The rule and correct French remain.
* **Two refusals end in the solution.** Once the solution is on screen (the retry
  refused, or «Voir la solution»), a refused free answer is served one acceptable model
  answer (:func:`model_answer`), said to nobody, and the card can end as seen.
* **Its floor fits its own answer.** A card's minimum word count never exceeds its
  shortest accepted answer (:func:`word_floor`): «J'ai trente ans.» against «5–24 words».
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

#: Task notes about the card, not about a span of French.
TASK_ERRATA = frozenset({"task_compliance", "length_compliance"})

#: A quoted meaning in any of the three chrome languages: "…", “…”, „…“.
_QUOTED = re.compile(r"\"([^\"]+)\"|“([^”]+)”|„([^“”]+)[“”]")


def quoted_meanings(raw_item: dict[str, Any]) -> list[str]:
    """The meanings an item quotes in its goals and its stored prompt, in every
    language (``goal_l10n``, ``goal_native``, ``prompt``, ``prompt_l10n``). A coach
    scene keeps its reply's meaning only there (``item_bank.scene_item``)."""

    texts: list[Any] = [raw_item.get("goal_native"), raw_item.get("prompt")]
    for key in ("goal_l10n", "prompt_l10n"):
        table = raw_item.get(key)
        if isinstance(table, dict):
            texts.extend(table.values())
    found: list[str] = []
    for text in texts:
        if not isinstance(text, str):
            continue
        for match in _QUOTED.finditer(text):
            value = next((group for group in match.groups() if group), "").strip()
            if value and value not in found:
                found.append(value)
    return found


def only_what_the_card_asked(correction: dict[str, Any] | None, *, rule_used: bool) -> dict[str, Any] | None:
    """The model's reading of an answer to a card that asked for a sentence of the
    learner's own with the rule (``own_sentence``): a task note about content the card
    never stated is dropped once the rule is in the answer. With nothing else left to
    fix, the answer is accepted. ``rule_used`` is the rule's detector on the answer."""

    if not isinstance(correction, dict) or not rule_used:
        return correction
    errata = [item for item in correction.get("errata") or [] if isinstance(item, dict)]
    kept = [item for item in errata if item.get("task_error_type") != "task_compliance"]
    if len(kept) == len(errata):
        return correction
    out = dict(correction)
    out["errata"] = kept
    out["dropped_errata"] = [
        *(out.get("dropped_errata") or []),
        *(
            {"learner_text": item.get("learner_text"), "reason": "content_the_card_never_asked"}
            for item in errata
            if item.get("task_error_type") == "task_compliance"
        ),
    ]
    if not kept and not out.get("lexical_gaps") and str(out.get("verdict") or "") not in {"correct", "accepted"}:
        out["verdict"] = "accepted"
        out["score_0_4"] = max(float(out.get("score_0_4") or 0), 3.0)
        out["missing_targets"] = []
    return out


def _words(text: Any) -> int:
    return len(str(text or "").split())


def word_floor(current: Any, answers: Iterable[Any]) -> int | None:
    """``current`` (a card's ``min_words``) lowered to fit the card's shortest answer:
    never more words than that answer has, never below one. An answer of several
    sentences counts each of them («Marin demande ton âge. J'ai trente ans.»: the card
    may quote only the last one)."""

    lengths: list[int] = []
    for answer in answers:
        if not isinstance(answer, str) or not answer.strip():
            continue
        lengths.append(_words(answer))
        parts = [part for part in re.split(r"(?<=[.!?…])\s+", answer.strip()) if part.strip()]
        if len(parts) > 1:
            lengths.extend(_words(part) for part in parts)
    try:
        floor = int(current) if current is not None else None
    except (TypeError, ValueError):
        return None
    if floor is None or not lengths:
        return floor
    return max(1, min(floor, min(lengths)))


FREE_ROUNDS = frozenset({"sentence", "speak", "conversation"})


def model_answer(prompt_payload: Any) -> str:
    """One acceptable model answer of a free card: its example, else its first
    accepted answer, said to nobody. ``""`` when the card has none."""

    items = prompt_payload.get("items") if isinstance(prompt_payload, dict) else None
    item = items[0] if isinstance(items, list) and items and isinstance(items[0], dict) else {}
    candidates = [item.get("example_answer"), *(item.get("accepted_answers") or []), item.get("expected_answer")]
    from app.services.answer_acceptance import addressed_names, strip_vocative

    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            names = addressed_names(candidate)
            return strip_vocative(candidate, names) if names else candidate.strip()
    return ""


def with_model_answer(correction: dict[str, Any], *, round_name: Any, prompt_payload: Any) -> dict[str, Any]:
    """The served correction of a refused free answer whose solution is on screen, with
    the card's model answer (``model_answer``) so the card can end as seen."""

    from app.services import solution_gate

    if str(round_name or "") not in FREE_ROUNDS or not isinstance(correction, dict):
        return correction
    if solution_gate.is_withheld(correction):
        return correction
    verdict = str(correction.get("verdict") or "")
    if verdict in {"correct", "accepted"} and not correction.get("errata"):
        return correction
    if str(correction.get("assessment_status") or "") in {"provisional", "unavailable"}:
        return correction
    answer = model_answer(prompt_payload)
    if not answer:
        return correction
    return {**correction, "model_answer": answer}


__all__ = [
    "FREE_ROUNDS",
    "TASK_ERRATA",
    "model_answer",
    "only_what_the_card_asked",
    "quoted_meanings",
    "with_model_answer",
    "word_floor",
]
