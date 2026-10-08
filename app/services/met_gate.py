"""WP-149 §A.1 — the met-gate: «met» is earned in the learner's own words.

Under lanes (WP-87) the tutor's grade is shown before the story lane's critic reads
the turn. The WP-136 read logged five ``false_successful_grading`` refusals after
release: «met» for a learner who had not given what the task asked («dites pourquoi
vous restez» answered with «C'est gentil. Je suis un peu perdu ici.»). The learner
was told they did it, and the evidence ledger credited it.

The gate runs on the tutor's verdict before the response is returned. It is
deterministic and only ever lowers a grade:

* «met» needs at least one evidence quote that occurs in the learner's text (this
  turn or an earlier one of the scene), after typography and accent folding — the
  iOS ‘smart’ apostrophe is the learner's apostrophe;
* «met» needs every required slot of the objective evidenced in the learner's text.
  A slot is read off the task's own wording (``objective_native``, ``objective_
  semantics``, the rubric): «dites pourquoi», «why», «warum» need a reason clause;
  «une condition», «a condition», «Bedingung» need a condition clause. An objective
  that asks the learner to *ask* why («Ask Romy why…») needs a question, not a reason,
  and has no slot;
* ``demonstrated_target_ids`` keeps only targets whose French occurs in this turn
  (the rule the ledger already applies to the observations it credits).

Otherwise «met» becomes «partially_met», with the existing partial feedback.
"""

from __future__ import annotations

import re
from typing import Any

from app.services.answer_acceptance import fold_all

#: The grade the gate gives a «met» it cannot support.
DOWNGRADED = "partially_met"

# What asks for a reason / a condition, in the three control languages and in the
# English ``objective_semantics``. Folded text: no accents, apostrophes straight.
_ASKS_REASON = re.compile(
    r"\b(?:pourquoi|(?:une|la|ta|votre|des) raisons?|justifi\w*"
    r"|why|(?:a|one|the|your) reasons?|reasons? why|justify"
    r"|warum|weshalb|wieso|(?:einen|den|deinen|ihren) grund|begrund\w*)\b"
)
_ASKS_A_QUESTION = re.compile(
    r"\b(?:ask|asks|asking|demande\w*|pose\w* (?:la|une) question|frag\w*|erkundig\w*)\b"
    r"[^.;:]{0,50}\b(?:why|pourquoi|warum|weshalb|wieso)\b"
)
_ASKS_CONDITION = re.compile(
    r"\b(?:(?:une|la|ta|votre) condition|a condition|(?:a|one|the) condition"
    r"|on condition|(?:eine|die|deine|ihre) bedingung|unter der bedingung)\b"
)

# The learner's French. Reason: an explicit connector, a purpose («pour + infinitive»),
# a cause, or a preference stated as the reason at A1 («j'aime le quartier»). Condition:
# «si», «à condition», «seulement si», «sauf si», «tant que», «pourvu que».
_REASON_CLAUSE = re.compile(
    r"\b(?:parce que|parce qu'|car|puisque|puisqu'|vu que|etant donne|a cause d|grace a"
    r"|pour que|pour qu'|c'est pour ca|c'est pourquoi|comme ca|sinon|donc|alors"
    r"|j'aime|j'adore|je prefere|j'ai besoin|il faut|ici c'est"
    r"|pour (?:[a-z]+(?:er|ir|re|oir))\b)"
)
_CONDITION_CLAUSE = re.compile(
    r"\b(?:si|s'il|s'ils|a condition|seulement si|sauf si|tant qu|pourvu qu|au cas ou|uniquement si)\b"
)

#: ``slot -> (asks, evidence)``.
SLOTS: dict[str, tuple[re.Pattern, re.Pattern]] = {
    "reason": (_ASKS_REASON, _REASON_CLAUSE),
    "condition": (_ASKS_CONDITION, _CONDITION_CLAUSE),
}


def required_slots(task_texts: list[str]) -> list[str]:
    """The slots the task's own wording requires, in ``SLOTS`` order."""

    folded = " ".join(fold_all(text) for text in task_texts if text)
    slots = []
    for slot, (asks, _evidence) in SLOTS.items():
        if not asks.search(folded):
            continue
        if slot == "reason" and _ASKS_A_QUESTION.search(folded) and not re.search(
            r"\b(?:explain|explique\w*|erklar\w*|give|donne\w*|nenn\w*|say|dis|dites|sag\w*)\b[^.;:]{0,30}"
            r"\b(?:why|pourquoi|warum|reason|raison|grund)\b",
            folded,
        ):
            # «Ask Romy why she left»: the learner asks the question; no reason owed.
            continue
        slots.append(slot)
    return slots


def slot_evidenced(slot: str, learner_texts: list[str]) -> bool:
    _asks, evidence = SLOTS[slot]
    return any(evidence.search(f" {fold_all(text)} ") for text in learner_texts if text)


def _learner_texts(payload: dict) -> list[str]:
    return [
        str(payload.get("learner_text") or ""),
        *[str(h.get("learner") or "") for h in payload.get("history") or [] if isinstance(h, dict)],
    ]


def _task_texts(payload: dict) -> list[str]:
    scene = payload.get("scene") or {}
    return [
        str(scene.get("objective_native") or ""),
        str(scene.get("objective_semantics") or ""),
        str(payload.get("rubric") or ""),
    ]


def met_gate(verdict: Any, payload: dict) -> list[str]:
    """Apply the gate to a tutor verdict in place; return why it lowered the grade
    (empty when it did not). ``verdict`` has ``outcome``, ``evidence_quotes`` and
    ``demonstrated_target_ids`` (``story_lanes.TutorVerdict``)."""

    learner = _learner_texts(payload)
    folded_learner = [f" {fold_all(text)} " for text in learner if text]
    quotes = [
        quote
        for quote in verdict.evidence_quotes
        if fold_all(quote) and any(fold_all(quote) in text for text in folded_learner)
    ]
    verdict.evidence_quotes = quotes
    # The targets the ledger may credit: their French is in this turn — the rule
    # ``evaluate_turn_lanes`` applies to the observations, folded the same way.
    labels = {
        str(target.get("id")): fold_all(target.get("label_fr") or "")
        for target in payload.get("targets") or []
        if isinstance(target, dict)
    }
    turn = fold_all(payload.get("learner_text") or "")
    verdict.demonstrated_target_ids = [
        target_id
        for target_id in verdict.demonstrated_target_ids
        if labels.get(str(target_id)) and labels[str(target_id)] in turn
    ]
    if verdict.outcome != "met":
        return []
    reasons: list[str] = []
    if not quotes:
        reasons.append("met_without_evidence")
    for slot in required_slots(_task_texts(payload)):
        if not slot_evidenced(slot, learner):
            reasons.append(f"missing_{slot}")
    if reasons:
        verdict.outcome = DOWNGRADED
    return reasons
