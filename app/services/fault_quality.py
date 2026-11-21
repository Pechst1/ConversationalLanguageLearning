"""Round 3 (walk 2, 17 Nov 2026): a stored fault is the learner's own French, or nothing.

The drill around the scene («Avant la scène», «Rappel») builds «Écris correctement ce
que tu as dit» items from the learner's stored faults (``UserError``). The B1 walk's
days 4 and 6 dealt nine such cards, and five of them were La Forge's half-finished
edits, not French the learner meant:

* «Ta copine attend les billets ? Oui, je les les donne après le travail.» — a word
  doubled while the learner moved a pronoun, the item's own «lui les» still open;
* «L'autre jour, c'était a l'heure du déjeuner …» — the item's planted «a» left
  in place, one of its three wrong words fixed;
* «Je t'appelle sans de t'expliquer le problème.» — the item's planted «de» untouched;
* «Le propriétaire … ? Je le l'ai déjà donné.» — the item's planted «l'» untouched;
* a judgement («Correcte» over a wrong sentence) stored as if the learner had
  written that sentence.

A fault is kept only when it is the learner's: its wrong span is a whole run of
words of what the learner submitted, that submission doubles no word, and it no
longer carries the error the item planted (a find-the-error item the learner left
half-fixed is the item's error, not theirs). Its correct target must be a
well-formed stretch of French. The write side (``ErrorMemoryService.
record_atelier_attempt``) stores nothing else; the read side (the drill's two
readers of the queue) refuses rows that fail the same checks, so the rows already
stored are harmless.

«Recopie la correction» writes no fault: it is ``AtelierService.record_micro_repair``,
which changes the attempt's payload and never calls the error memory.

Pure; no database access.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from typing import Any

#: Characters stripped from the edges of a word before comparing.
_EDGE = ".,;:!?…«»\"“”()[]{}—–-"
#: A word written twice in a row that French does write: «nous nous levons».
_DOUBLED_OK = {"nous", "vous"}
#: An elided article or pronoun before a consonant («m'me», «l'ai» is fine).
_BAD_ELISION = re.compile(r"^(?:[a-z]{1,3})'(?:[^aeiouyhàâäéèêëîïôöûùü]|$)")


def tokens(text: Any) -> list[str]:
    """Lower-cased words of ``text``, punctuation at their edges dropped."""

    folded = unicodedata.normalize("NFC", str(text or "")).replace("’", "'").replace("‘", "'").lower()
    words = (word.strip(_EDGE) for word in folded.split())
    return [word for word in words if word]


def doubled_word(text: Any) -> bool:
    """A word written twice in a row (an edit that copied instead of moving)."""

    words = tokens(text)
    return any(a == b and a not in _DOUBLED_OK for a, b in zip(words, words[1:], strict=False))


def is_word_run(span: Any, text: Any) -> bool:
    """``span`` is a whole run of consecutive words of ``text`` (never a piece of one)."""

    needle, haystack = tokens(span), tokens(text)
    if not needle:
        return False
    width = len(needle)
    return any(haystack[index : index + width] == needle for index in range(len(haystack) - width + 1))


def keeps_planted_error(submitted: Any, source: Any, expected: Any) -> bool:
    """The learner's line still carries a word the item planted and its answer removes."""

    planted = Counter(tokens(source)) - Counter(tokens(expected))
    if not planted:
        return False
    have, want = Counter(tokens(submitted)), Counter(tokens(expected))
    return any(have[word] > want[word] for word in planted)


def well_formed(text: Any) -> bool:
    """A correct target a drill can be built on: words, none doubled, no elision before a consonant."""

    words = tokens(text)
    if not words:
        return False
    if doubled_word(text):
        return False
    return not any(_BAD_ELISION.match(word) for word in words)


def fix_stands_in(line: Any, wrong: Any, correct: Any) -> bool:
    """The correction is French in the line the learner will be shown.

    Walk 14 (21 Nov 2026, B1 days 3–13): a letter's correction «il faut que je vends
    → je vende» was stored as the bare pair «je vends» → «je vende». Out of the clause
    that asks for the subjunctive, the «fix» turns right French («je vends», I sell)
    into wrong French, and La Forge and the warm-up taught it three times; the
    learner's answer to that card then became a second fault («je avais vendu» →
    «je vende»). A fix that turns a verb into a form the lexicon's conjugation
    tables (:func:`tense_change.changed_tenses`) read as a subjunctive and nothing
    else, with no «que» in front of it in ``line``, is not French: the fault is
    dropped, not posed. A fix between two indicative tenses («a déjà réservé» →
    «avait déjà réservé») stays: both are French, the line only lacks its context.
    """

    from app.services.tense_change import SUBJONCTIF, changed_tenses

    try:
        changes = changed_tenses(wrong, correct)
    except Exception:  # noqa: BLE001 - a table that cannot be read proves nothing
        return True
    if not any(becomes == frozenset({SUBJONCTIF}) for _was, becomes in changes):
        return True
    text = unicodedata.normalize("NFC", str(line or wrong or "")).replace("’", "'")
    fixed = text.replace(str(wrong or ""), str(correct or ""), 1) if str(wrong or "") in text else str(correct or "")
    words = tokens(fixed.replace("'", "' "))
    verb_at = max((i for i, word in enumerate(words) if word in set(tokens(correct)) - set(tokens(wrong))), default=len(words))
    return any(word in ("que", "qu'", "qu") for word in words[:verb_at])


def rules_correct_the_fix(correct: Any) -> bool:
    """The model-free rule pass corrects the stored «fix» itself: it is not right French.

    Walk 14 (A1 day 13): «Lila a une valise dans la chambre.» was stored as wrong with
    «Lila a un valise dans la chambre.» as its correction (a key that kept another slip of
    the line), and posed for days. A target the rules would correct (a grammar edit,
    severity 2; a lone accent or apostrophe is left to the accent policy) is dropped.
    """

    from app.services import correction_contract

    try:
        return any(edit.severity >= 2 for edit in correction_contract.deterministic_edits(str(correct or "")))
    except Exception:  # noqa: BLE001 - the rules are a check, never a crash
        return False


def planted_item(item: dict[str, Any] | None) -> tuple[str, str] | None:
    """``(source, expected)`` of a find-the-error / rewrite item, else ``None``."""

    if not isinstance(item, dict):
        return None
    # Only an item that planted an error to find: «Touche le mot faux» (its wrong
    # span) or «Ta phrase» (a saved mistake). A directed rewrite («Quand …» into
    # «Si …») plants nothing: its source is right French.
    if not (item.get("wrong_span") or item.get("fix_words") or str(item.get("id") or "").startswith("mine-")):
        return None
    source = str(item.get("source_fr") or item.get("source") or "").strip()
    expected = str(item.get("expected_answer") or "").strip()
    if not source or not expected or "___" in source:
        return None
    if tokens(source) == tokens(expected):
        return None
    return source, expected


def submitted_text(answer_payload: Any, item_id: Any) -> str | None:
    """What the learner submitted for one item, as one line (``None`` when unknown)."""

    if not isinstance(answer_payload, dict):
        return None
    answers = answer_payload.get("answers")
    if isinstance(answers, dict) and item_id is not None and item_id in answers:
        value = answers[item_id]
    elif isinstance(answer_payload.get("text"), str):
        value = answer_payload["text"]
    elif isinstance(answers, dict) and len(answers) == 1:
        value = next(iter(answers.values()))
    else:
        return None
    if isinstance(value, list):
        value = " ".join(str(part) for part in value)
    if isinstance(value, dict):
        value = " ".join(str(part) for part in value.values())
    return str(value) if value is not None else None


def learner_own_fault(
    *,
    wrong: Any,
    correct: Any,
    submitted: Any = None,
    item: dict[str, Any] | None = None,
) -> bool:
    """Is this fault French the learner produced, with a target a drill can use?

    ``submitted`` and ``item`` are known for a La Forge fault (its attempt); a fault
    from the scene, a letter or the journal has neither and is judged on its own words.
    """

    if not tokens(wrong) or not well_formed(correct):
        return False
    if doubled_word(wrong):
        return False
    if not fix_stands_in(submitted if submitted is not None and is_word_run(wrong, submitted) else wrong, wrong, correct):
        return False
    if rules_correct_the_fix(correct):
        return False
    if submitted is not None:
        if not is_word_run(wrong, submitted):
            # «m'me»: not a word the learner wrote; a judgement («Correcte») over
            # the item's sentence: not French the learner wrote at all.
            return False
        if doubled_word(submitted):
            return False
        planted = planted_item(item)
        if planted is not None and keeps_planted_error(submitted, *planted):
            return False
    return True


def attempt_fault_is_own(attempt: Any, erratum: dict[str, Any]) -> bool:
    """The write side's check for one erratum of a La Forge attempt."""

    item_id = erratum.get("item_id")
    items = [entry for entry in ((getattr(attempt, "prompt_payload", None) or {}).get("items") or []) if isinstance(entry, dict)]
    item = next((entry for entry in items if item_id and entry.get("id") == item_id), None)
    if item is None and len(items) == 1:
        item = items[0]
    return learner_own_fault(
        wrong=erratum.get("learner_text"),
        correct=erratum.get("corrected_target"),
        submitted=submitted_text(getattr(attempt, "answer_payload", None), item_id),
        item=item,
    )


def stored_fault_is_own(row: Any, attempt: Any = None) -> bool:
    """The read side's check for one stored ``UserError`` (its attempt when it has one)."""

    if attempt is None or getattr(row, "source_type", None) != "atelier":
        # Only La Forge's faults are read against an attempt (a letter's row can carry
        # a ``source_attempt_id`` that is not its own).
        return learner_own_fault(wrong=getattr(row, "original_text", None), correct=getattr(row, "correction", None))
    payload = (getattr(row, "error_metadata", None) or {}) if isinstance(getattr(row, "error_metadata", None), dict) else {}
    index = (payload.get("source_payload") or {}).get("erratum_index") if isinstance(payload.get("source_payload"), dict) else None
    errata = list(((getattr(attempt, "correction_payload", None) or {}).get("errata")) or [])
    erratum = errata[index] if isinstance(index, int) and 0 <= index < len(errata) and isinstance(errata[index], dict) else {}
    return attempt_fault_is_own(
        attempt,
        {
            "item_id": erratum.get("item_id"),
            "learner_text": getattr(row, "original_text", None),
            "corrected_target": getattr(row, "correction", None),
        },
    )


def drillable_errors(db: Any, rows: list[Any]) -> list[Any]:
    """``rows`` without the faults that are not the learner's own (one query for their attempts)."""

    from app.db.models.atelier import AtelierAttempt

    ids = {
        row.source_attempt_id
        for row in rows
        if getattr(row, "source_attempt_id", None) and getattr(row, "source_type", None) == "atelier"
    }
    attempts: dict[Any, Any] = {}
    if ids:
        try:
            attempts = {attempt.id: attempt for attempt in db.query(AtelierAttempt).filter(AtelierAttempt.id.in_(ids)).all()}
        except Exception:  # noqa: BLE001 - unread attempts: each row is judged on its own words
            attempts = {}
    return [row for row in rows if stored_fault_is_own(row, attempts.get(getattr(row, "source_attempt_id", None)))]


__all__ = [
    "attempt_fault_is_own",
    "doubled_word",
    "drillable_errors",
    "fix_stands_in",
    "is_word_run",
    "keeps_planted_error",
    "learner_own_fault",
    "planted_item",
    "rules_correct_the_fix",
    "stored_fault_is_own",
    "submitted_text",
    "tokens",
    "well_formed",
]
