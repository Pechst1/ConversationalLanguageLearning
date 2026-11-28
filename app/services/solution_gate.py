"""The solution waits for the second chance (owner, 2026-11-13).

«The user should not see what is right when he then gets another chance to fix
it; only afterwards the solution.» A La Forge miss is followed by a chance to
fix it: the line repaired in place, «Try the line again», a word chosen again.
Until that chance is spent, the learner-facing payload says WHERE the answer is
wrong (the marked words of their own line) and WHY in terms of the rule (a hint),
never the corrected line, the corrected word, or a note that spells it.

The stored correction keeps everything; only what is served is withheld.

    correction["solution"] = {"state": "withheld" | "shown", "language": "de"}

``withheld`` is written when the answer is posed for the first time and a
second chance follows a miss (:func:`second_chance_for`); it turns ``shown``
when the chance is spent: a repair sent (``record_micro_repair``), «Show the
solution» (``POST /atelier/attempts/{id}/reveal``). A retry is a new attempt on
the same item, which never gets a chance of its own: its miss shows the
solution. Items with no second chance (a two-way choice, a burst, a rule check,
a re-test) are ``shown`` from the start.

An answer nobody read and nobody can be asked to read again (no model) is no miss
and never gets its chance: :func:`no_chance_follows` serves it whole, and a later
re-check reveals it first (#855).

:func:`learner_view` is the one place the withheld payload is made. The hints
are the model's or the rule's own ``hint`` when it has one, else its note; every
one goes through :func:`scrub_hint`, which drops each clause naming a word the
learner has not written and the correction has. The prompt asks the model for a
hint without the answer; the scrub is what guarantees it.

What names the answer is read where the answer can stand (#1086, #1109): the hint is
written in the learner's language, so one of its own words («es» in «Schau, wer es
tut») is the answer only where the hint quotes it as French; and the learner's own
line, quoted back («You wrote “ils ont écouté à”»), never names the answer, while the
key inside it said on its own («this item needs “ils ont écouté”») does.
"""
from __future__ import annotations

import copy
import re
import unicodedata
from typing import Any

STATE_KEY = "solution"
WITHHELD = "withheld"
SHOWN = "shown"

#: Answer keys an item carries (``prompt_payload`` on a stored attempt).
ITEM_ANSWER_KEYS = frozenset(
    {
        "answer",
        "answer_tokens",
        "expected_answer",
        "correct_answer",
        "correct_label",
        "example_answer",
        "accepted_answers",
        "accepted_fr",
        "corrected_fr",
        "model_answer",
    }
)

#: Correction keys served as they are while the solution is withheld: none of
#: them carries French the learner did not write.
_SAFE_KEYS = frozenset(
    {
        STATE_KEY,
        "assessment_status",
        "verdict",
        "score_0_4",
        "local_status",
        "local_verdict",
        "graded_by",
        "latency",
        "confidence",
        "calibration",
        "adaptive_lock",
        "retest",
        "retest_of",
        "evidence_deferred",
        "evidence_applied",
        "forge",
        "rule_reference",
        "memory_updates",
        "world_reply",
        "burst",
        "second_check",
        "explanation_language",
        "missing_targets",
    }
)

_WORD = re.compile(r"[0-9A-Za-zÀ-ÖØ-öø-ÿŒœ]+")
_APOSTROPHES = re.compile(r"[‘’‚‛′´`ʹʻʼ]")
#: A clause ends at a sentence stop, a semicolon, a colon or a line break.
_CLAUSE = re.compile(r"(\s*[;:]\s+|\s+:\s*|(?<=[.!?…])\s+|\n+)")


def _fold(value: Any) -> str:
    text = unicodedata.normalize("NFC", str(value or ""))
    return _APOSTROPHES.sub("'", text).lower()


def _tokens(value: Any) -> set[str]:
    return set(_WORD.findall(_fold(value)))


def _is_leak_token(token: str) -> bool:
    # One-letter words are elided articles and pronouns («l'», «j'»): they say
    # nothing on their own. An accented one («à») is a whole answer.
    return len(token) >= 2 or not token.isascii()


def _text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return " ".join(_text(item) for item in value)
    if isinstance(value, dict):
        return " ".join(_text(item) for item in value.values())
    return "" if value is None else str(value)


def _passes(correction: dict[str, Any], verdict: Any = None) -> bool:
    """The answer was right: nothing is withheld (mirrors ``seanceAssessment``)."""

    shown_verdict = verdict if verdict is not None else correction.get("verdict")
    if str(shown_verdict or correction.get("verdict") or "") not in {"correct", "accepted"}:
        return False
    return not (correction.get("errata") or correction.get("missing_targets") or correction.get("lexical_gaps"))


def is_withheld(correction: dict[str, Any] | None, verdict: Any = None) -> bool:
    """Is this correction served without its solution right now?"""

    if not isinstance(correction, dict):
        return False
    state = correction.get(STATE_KEY)
    if not isinstance(state, dict) or state.get("state") != WITHHELD:
        return False
    if no_chance_follows(correction, verdict):
        return False
    return not _passes(correction, verdict)


def no_chance_follows(correction: dict[str, Any] | None, verdict: Any = None) -> bool:
    """Nobody read this answer and nobody can be asked to read it again (#855, #333).

    ``withheld`` is written when the answer is posed, before anyone has read it: it says
    a chance follows a MISS. An unread answer is no miss, and when its check cannot run
    again (no model: the screen offers «Skip without a check», never «Check again») no
    miss can ever come, so there is no chance to wait for and the rules' fixes are the
    only help it gets: they are served whole. This is the reading the screen draws from
    (``check.outcome``, ``check.call``, ``check.retryable``: ``canAskAgain``), so the gate
    and the screen cannot disagree on whether a chance follows. While the check runs, or
    while it can be asked again (a timeout, a provider error), the answer stays withheld:
    a read miss then opens its chance with nothing given away.
    """

    if not isinstance(correction, dict):
        return False
    from app.core.verdict import Call, Outcome
    from app.services.verdicts import from_forge

    shown = verdict if verdict is not None else correction.get("verdict")
    read = from_forge(correction, verdict=str(shown) if shown is not None else None)
    return read.outcome is Outcome.NOT_CHECKED and read.call is not Call.PENDING and not read.retryable


def served_whole_unread(correction: dict[str, Any] | None, verdict: Any = None) -> bool:
    """Posed with a chance, but served whole because no chance could follow (#855).

    What was served stays served: a re-check of such an answer must :func:`reveal` it
    first, so a miss read later shows the solution instead of offering a chance.
    """

    if not isinstance(correction, dict):
        return False
    state = correction.get(STATE_KEY)
    return isinstance(state, dict) and state.get("state") == WITHHELD and no_chance_follows(correction, verdict)


def mark(correction: dict[str, Any], *, chance: bool, language: str | None = None) -> dict[str, Any]:
    """The correction with its solution state: withheld when a second chance follows a miss."""

    updated = dict(correction or {})
    updated[STATE_KEY] = {"state": WITHHELD if chance else SHOWN, "language": language or "en"}
    return updated


def reveal(correction: dict[str, Any], *, by: str) -> dict[str, Any]:
    """The chance is spent (``by``: «repair», «reveal»): the solution is served from now on."""

    updated = dict(correction or {})
    state = updated.get(STATE_KEY) if isinstance(updated.get(STATE_KEY), dict) else {}
    updated[STATE_KEY] = {**state, "state": SHOWN, "revealed_by": by}
    return updated


#: La Forge drills (``forge_drills``) that pose a fill without its options: the
#: learner types the form. The item keeps its ``choices`` for the classic way, so
#: the number of options it stores says nothing about what the learner saw.
TYPED_DRILLS = frozenset({"typed"})


def _option_counts(prompt_payload: Any, answers: Any) -> list[int]:
    """How many options each answered item offered, where the learner picked one of them.

    An answer that is none of the item's options was typed, not picked (a typed fill
    keeps the options it is posed without): it counts no options.
    """

    wanted = {str(key): value for key, value in answers.items()} if isinstance(answers, dict) else {}
    counts: list[int] = []

    def walk(node: Any) -> None:
        if isinstance(node, list):
            for child in node:
                walk(child)
            return
        if not isinstance(node, dict):
            return
        item_id = str(node.get("id") or "")
        if item_id in wanted:
            options = node.get("choices") or node.get("labels") or node.get("options")
            if isinstance(options, list) and options:
                given = _fold(_text(wanted[item_id])).strip()
                if any(_fold(_text(option)).strip() == given for option in options):
                    counts.append(len(options))
        for value in node.values():
            if isinstance(value, (dict, list)):
                walk(value)

    walk(prompt_payload)
    return counts


def typed_answer(prompt_payload: Any, answer_payload: Any, drill: str | None = None) -> bool:
    """Was this recognise answer typed rather than picked among options?

    Walk of 19 Nov: La Forge's «Tape la forme» is a fill posed without its options
    (``drill == "typed"``), and an answer that is none of the item's options was
    typed whatever the drill.
    """

    if drill in TYPED_DRILLS:
        return True
    answers = (answer_payload or {}).get("answers") if isinstance(answer_payload, dict) else None
    if not isinstance(answers, dict) or not answers:
        return False
    if not _has_options(prompt_payload, answers):
        return True
    return not _option_counts(prompt_payload, answers)


def _has_options(prompt_payload: Any, answers: dict[str, Any]) -> bool:
    found = False

    def walk(node: Any) -> None:
        nonlocal found
        if found:
            return
        if isinstance(node, list):
            for child in node:
                walk(child)
            return
        if not isinstance(node, dict):
            return
        if str(node.get("id") or "") in answers:
            options = node.get("choices") or node.get("labels") or node.get("options")
            if isinstance(options, list) and options:
                found = True
                return
        for value in node.values():
            if isinstance(value, (dict, list)):
                walk(value)

    walk(prompt_payload)
    return found


def second_chance_for(
    *,
    round_name: str,
    exercise_id: str,
    prompt_payload: Any,
    answer_payload: Any,
    first_submission: bool,
    retest: bool,
    rule_check: bool,
    drill: str | None = None,
) -> bool:
    """Does a miss on this answer get a second chance on the same screen?

    No for a resubmission (the retry IS the chance; a re-posed item is asked
    again later and its miss is final), a re-test, a rule check (an exam: one
    go per item) and La Forge's burst («rafale», four judgements in one go,
    shown together). No for a choice between two the learner picked from (the
    miss names the other one). Everything else does: a choice among three or
    more, a word bank, a typed form, a transform, a free line.

    Walk of 19 Nov: a typed fill (``drill`` «typed») keeps the two options of its
    classic form in the stored item; the learner never saw them, so the miss
    named nothing and still gets its retry. Only an answer picked among two
    options is exempt.
    """

    if not first_submission or retest or rule_check:
        return False
    if "+" in str(exercise_id or "").split(":")[-1]:
        return False
    if round_name == "recognize" and drill not in TYPED_DRILLS:
        answers = (answer_payload or {}).get("answers") if isinstance(answer_payload, dict) else None
        counts = _option_counts(prompt_payload, answers)
        if counts and min(counts) <= 2:
            return False
    return True


def leak_terms(correction: dict[str, Any], learner: Any, context: Any = "") -> tuple[list[str], set[str]]:
    """``(phrases, tokens)`` that would give the answer away.

    Phrases: the corrected line and every corrected stretch the learner did not
    write. Tokens: their words the learner did not write. A word of the corrected
    line that the task itself shows (``context``) is not a leak; a word of a
    corrected stretch always is, even when the task shows it.
    """

    from app.services.atelier import narrow_repair

    learner_text = _text(learner)
    learner_tokens = _tokens(learner_text)
    errata = [item for item in (correction.get("errata") or []) if isinstance(item, dict)]
    for erratum in errata:
        learner_tokens |= _tokens(erratum.get("learner_text"))
    context_tokens = _tokens(_text(context))

    phrases: list[str] = []
    fix_tokens: set[str] = set()
    for erratum in errata:
        target = str(erratum.get("corrected_target") or "").strip()
        wrong = str(erratum.get("learner_text") or "").strip()
        if not target or _fold(target) == _fold(wrong):
            continue
        phrases.append(target)
        fix_tokens |= _tokens(target)
        if wrong:
            try:
                fix = narrow_repair(wrong, target)[2]
            except (IndexError, ValueError):
                fix = ""
            if fix:
                phrases.append(fix)
                fix_tokens |= _tokens(fix)
    # Walk of 19 Nov: «Il manque « d' ».» An elided word of one letter says nothing in a
    # sentence, but quoted alone it is the whole fix.
    phrases.extend(f"{token}'" for token in sorted(fix_tokens - learner_tokens) if len(token) == 1 and token.isalpha())
    line_tokens: set[str] = set()
    corrected = _text(correction.get("corrected_answer")).strip()
    if corrected and _fold(corrected).strip() != _fold(learner_text).strip():
        phrases.append(corrected)
        line_tokens = _tokens(corrected) - context_tokens
    tokens = {
        token
        for token in (fix_tokens | line_tokens) - learner_tokens
        if _is_leak_token(token)
    }
    # #1109: a key that is the learner's line minus a word they added («ils ont écouté»
    # for «ils ont écouté à») is in their line and still the whole answer. A whole key
    # stays a phrase unless it IS the learner's line; a narrow fix the learner's line
    # already holds says nothing. Where the line is quoted back, :func:`_leaks` reads
    # it as the learner's (``own``), not as the key.
    keys = {_fold(key).strip(" .!?") for key in (corrected, *(str(item.get("corrected_target") or "") for item in errata))}
    line = _fold(learner_text).strip(" .!?")

    def kept(phrase: str) -> bool:
        folded = _fold(phrase).strip()
        if not folded:
            return False
        if folded.strip(" .!?") in keys:
            return folded.strip(" .!?") != line
        return folded not in _fold(learner_text)

    return [phrase for phrase in phrases if kept(phrase)], tokens


#: #1086: words of the learner's own language that may also be French forms («es»:
#: German «es», French «tu es»; «as»: English «as», French «tu as»; «du», «des», «on»,
#: «an»). In a hint written in that language such a word is the learner's language, not
#: the answer, unless the hint quotes it as French («es»). Closed-class words only: an
#: unquoted French form that is no word of the language («sommes») leaks as before.
_LEARNER_WORDS: dict[str, frozenset[str]] = {
    "de": frozenset(
        {
            "es", "er", "sie", "wir", "ihr", "du", "ich", "man", "der", "die", "das", "den", "dem", "des",
            "ein", "eine", "einen", "einem", "einer", "und", "oder", "aber", "an", "am", "in", "im", "um",
            "auf", "aus", "bei", "mit", "von", "vor", "zu", "für", "nach", "ist", "sind", "bin", "bist",
            "hat", "hast", "habe", "haben", "wer", "wie", "was", "wo", "so", "nur", "auch", "noch", "nicht",
        }
    ),
    "en": frozenset(
        {
            "as", "on", "or", "me", "an", "a", "the", "and", "but", "for", "to", "of", "in", "at", "it", "is",
            "are", "was", "he", "she", "we", "you", "they", "his", "her", "its", "with", "not", "who", "what",
            "so", "only", "also", "here", "that", "this",
        }
    ),
}

_LETTER = "0-9a-zà-öø-ÿœ"
#: A stretch quoted as French: «…», “…”, „…“, "…", ‹…›, and (after :func:`_fold`, which
#: makes ‘ ’ ‚ a straight one) '…'. A double or angle quote left open runs to the clause's
#: end (the strict reading). A single quote opens and closes only at a word's edge, so
#: the apostrophe of «l'hôtel» or «j'ai» is no quote, and it must close.
_QUOTED = re.compile(
    r'«[^»]*(?:»|$)|“[^”]*(?:”|$)|„[^“”]*(?:[“”]|$)|"[^"]*(?:"|$)|‹[^›]*(?:›|$)'
    rf"|(?<![{_LETTER}'])'(?=[^\s']).*?(?<=[^\s'])'(?![{_LETTER}])"
)


def _learner_words(language: str | None) -> frozenset[str]:
    return _LEARNER_WORDS.get(str(language or "").strip().lower()[:2], frozenset())


def _inside(start: int, end: int, spans: list[tuple[int, int]]) -> bool:
    return any(left <= start and end <= right for left, right in spans)


def _leaks(
    clause: str,
    phrases: list[str],
    tokens: set[str],
    language: str | None = None,
    own: tuple[str, ...] | list[str] = (),
) -> bool:
    """Whether ``clause`` names the answer: one of its ``tokens`` or ``phrases``.

    #1086: a hint is written in the learner's ``language``, and only its French names
    the answer. A word of that language («es» in «Schau, wer es tut») is the answer only
    where the hint quotes it as French («Mit «tu» heißt «être» «es»», 'es'). Without a
    ``language`` (or in French) every word is read as French, as before.

    #1109: ``own`` are the learner's own lines. A phrase found inside one of them, quoted
    back («You wrote “ils ont écouté à”»), is the learner's text, not the answer."""

    folded = _fold(clause)
    words = _learner_words(language)
    quoted = [match.span() for match in _QUOTED.finditer(folded)] if words else []
    mine: list[tuple[int, int]] = []
    for line in {_fold(line).strip(" .!?") for line in own}:
        if line:
            mine.extend(match.span() for match in re.finditer(re.escape(line), folded))

    def names(start: int, end: int, said: list[str]) -> bool:
        if _inside(start, end, mine):
            return False
        if not said or not set(said) <= words:
            return True
        return _inside(start, end, quoted)

    for match in _WORD.finditer(folded):
        if match.group() in tokens and names(match.start(), match.end(), [match.group()]):
            return True
    for phrase in phrases:
        needle = _fold(phrase).strip(" .!?")
        if not needle:
            continue
        for match in re.finditer(rf"(?<![{_LETTER}]){re.escape(needle)}(?![{_LETTER}])", folded):
            if names(match.start(), match.end(), _WORD.findall(needle)):
                return True
    return False


def scrub_hint(
    text: Any,
    phrases: list[str],
    tokens: set[str],
    language: str | None = None,
    own: tuple[str, ...] | list[str] = (),
) -> str:
    """``text`` without every clause that names the answer. May return ``""``.

    ``language`` is the language the hint is written in and ``own`` the learner's own
    lines (:func:`_leaks`): a word of that language that is also a French form counts
    only where the hint quotes it as French, and the learner's line quoted back is theirs."""

    raw = str(text or "").strip()
    if not raw:
        return ""
    pieces = _CLAUSE.split(raw)
    kept: list[tuple[str, str]] = []
    dropped = False
    for index in range(0, len(pieces), 2):
        clause = pieces[index]
        separator = pieces[index + 1] if index + 1 < len(pieces) else ""
        if not clause.strip() or _leaks(clause, phrases, tokens, language, own):
            dropped = dropped or bool(clause.strip())
            continue
        clause = clause.strip()
        if dropped and kept and kept[-1][1].strip() in {";", ":"}:
            # Walk of 19 Nov: «Du hast „Ils a“ gewählt; Die Regel ist hier nicht der
            # Unterschied.» The clause a «;» or «:» led into is gone, so the sentence
            # before it ends there and the next one starts as a sentence.
            kept[-1] = (kept[-1][0], ". ")
            clause = clause[0].upper() + clause[1:]
        dropped = False
        kept.append((clause, separator))
    if not kept:
        return ""
    out = ""
    for index, (clause, separator) in enumerate(kept):
        out += clause
        if index < len(kept) - 1:
            out += separator if separator.strip() else " "
    out = out.strip().rstrip(",;:—–- ")
    if not out:
        return ""
    if out[-1] not in ".!?…»“\"”":
        out += "."
    return out[0].upper() + out[1:]


def _fallback(key: str, language: str | None) -> str:
    from app.services.learner_copy import learner_text

    return learner_text(key, language)


def marks_for(learner: str, errata: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Where each erratum stands in the learner's line: the words that differ, by offset.

    The same placing as the repair in place (``repair_parts``), without the fixes.
    """

    from app.services.atelier import repair_parts

    parts = repair_parts(learner, errata) or []
    if not parts:
        # A one-word answer, or a stretch the repair cannot place: the learner's own words
        # are marked where they stand, once, or not at all.
        marks_found: list[dict[str, Any]] = []
        folded = learner.lower()
        for index, erratum in enumerate(errata):
            wrong = str(erratum.get("learner_text") or "").strip()
            if not wrong or erratum.get("task_error_type") in {"task_compliance", "length_compliance"}:
                continue
            start = folded.find(wrong.lower())
            if start >= 0 and folded.find(wrong.lower(), start + 1) < 0 and len(wrong) == len(wrong.lower()):
                marks_found.append({"start": start, "end": start + len(wrong), "text": learner[start : start + len(wrong)], "erratum": index})
        return sorted(marks_found, key=lambda mark: mark["start"])
    marks: list[dict[str, Any]] = []
    cursor = 0
    for part in parts:
        if "text" in part:
            cursor += len(str(part["text"]))
            continue
        wrong = str(part.get("wrong") or "")
        marks.append({"start": cursor, "end": cursor + len(wrong), "text": wrong, "erratum": part.get("erratum")})
        cursor += len(wrong)
    return marks


def learner_line(answer_payload: Any, item_id: str | None = None) -> str:
    """What the learner typed or said, as one line (an item's, or every item's)."""

    return _learner_line(answer_payload, item_id)


def _learner_line(answer_payload: Any, item_id: str | None = None) -> str:
    if not isinstance(answer_payload, dict):
        return _text(answer_payload)
    answers = answer_payload.get("answers")
    if isinstance(answers, dict):
        if item_id and item_id in answers:
            value = answers[item_id]
            return _join(value) if isinstance(value, list) else str(value or "")
        return " ".join(_join(value) if isinstance(value, list) else str(value or "") for value in answers.values())
    return str(answer_payload.get("text") or "")


def _join(tokens: list[Any]) -> str:
    from app.services.atelier import _join_french_tokens

    return _join_french_tokens(tokens)


def learner_view(
    correction: dict[str, Any] | None,
    *,
    verdict: Any = None,
    answer_payload: Any = None,
    context: Any = "",
) -> dict[str, Any]:
    """The correction as the learner may see it now (unchanged unless withheld)."""

    if served_whole_unread(correction, verdict):
        # #855: the solution IS on this payload, so it says so (``solution.state`` is what
        # the screen reads as «nothing right may be drawn», lib/solution-gate.ts).
        return {**correction, STATE_KEY: {**correction[STATE_KEY], "state": SHOWN, "served": "unread"}}  # type: ignore[index]
    if not isinstance(correction, dict) or not is_withheld(correction, verdict):
        return correction or {}
    state = correction.get(STATE_KEY) or {}
    language = state.get("language") if isinstance(state, dict) else None
    learner = _learner_line(answer_payload)
    phrases, tokens = leak_terms(correction, learner, context)

    view: dict[str, Any] = {key: copy.deepcopy(value) for key, value in correction.items() if key in _SAFE_KEYS}
    corrected = correction.get("corrected_answer")
    view["corrected_answer"] = {} if isinstance(corrected, dict) else ""
    ai_review = correction.get("ai_review")
    if isinstance(ai_review, dict):
        view["ai_review"] = {key: value for key, value in ai_review.items() if isinstance(value, (bool, int, float)) or key in {"status", "auto_started", "reason", "requested_at", "completed_at"}}

    local_check = correction.get("local_check")
    if isinstance(local_check, dict):
        # How the key read it, never what the key holds (a «trap» names the right form).
        view["local_check"] = {
            key: value
            for key, value in local_check.items()
            if isinstance(value, (bool, int, float)) or key in {"detector", "local_status", "status"}
        }
    gaps = correction.get("lexical_gaps")
    if isinstance(gaps, list):
        # The word the learner reached for is theirs; the French for it is the answer.
        view["lexical_gaps"] = [
            {"learner_fragment": gap.get("learner_fragment"), "language": gap.get("language")}
            for gap in gaps
            if isinstance(gap, dict)
        ]

    errata_in = [item for item in (correction.get("errata") or []) if isinstance(item, dict)]
    errata_out: list[dict[str, Any]] = []
    for index, erratum in enumerate(errata_in):
        task = erratum.get("task_error_type") in {"task_compliance", "length_compliance"}
        line = _learner_line(answer_payload, str(erratum.get("item_id") or "") or None)
        mark = marks_for(line, [erratum]) if line and not task else []
        hint = ""
        for source in (erratum.get("hint"), erratum.get("why_wrong"), erratum.get("repair_hint")):
            hint = scrub_hint(source, phrases, tokens, language, (learner, line))
            if hint:
                break
        if not hint and task and str(erratum.get("display_label") or "").strip() and not _leaks(
            str(erratum.get("display_label")), phrases, tokens, language
        ):
            # R2 (walk of 17 Nov): «Relis la consigne : qu'est-ce qu'elle te demande
            # d'utiliser ?» said nothing; what is missing is the card's rule, by name and in words.
            from app.services.learner_copy import learner_text

            hint = learner_text("forge.second_chance.task_rule_hint", language, rule=str(erratum.get("display_label")).strip())
        if not hint:
            key = "forge.second_chance.task_hint" if task else "forge.second_chance.hint" if mark else "forge.second_chance.choice_hint"
            hint = _fallback(key, language)
        label = str(erratum.get("display_label") or "")
        if label and _leaks(label, phrases, tokens, language):
            label = ""
        errata_out.append(
            {
                "item_id": erratum.get("item_id") or "",
                "display_label": label,
                "learner_text": "" if _leaks(str(erratum.get("learner_text") or ""), phrases, set(), own=(learner, line)) else str(erratum.get("learner_text") or ""),
                "corrected_target": "",
                "why_wrong": hint,
                "repair_hint": "",
                "hint": hint,
                "severity": erratum.get("severity"),
                "recurring": erratum.get("recurring"),
                "task_error_type": erratum.get("task_error_type"),
                "concept_id": erratum.get("concept_id"),
                "external_id": erratum.get("external_id"),
                "erratum_index": index,
                "mark": mark[0] if mark else None,
                "withheld": True,
            }
        )
    view["errata"] = errata_out
    view["notes_native"] = [item["hint"] for item in errata_out]
    view["marks"] = marks_for(learner, errata_in) if learner else []
    # The line the marks are offsets into, as the server joined it (a word bank's tiles).
    view["marked_line"] = learner
    view[STATE_KEY] = {**(state if isinstance(state, dict) else {}), "state": WITHHELD}
    return view


def withhold_check(check: dict[str, Any], correction: dict[str, Any] | None, verdict: Any = None) -> dict[str, Any]:
    """The verdict view (``check``) without its replacements while the solution is withheld."""

    if not is_withheld(correction, verdict):
        return check
    edits = [
        {**edit, "replacement": "", "note": ""}
        for edit in (check.get("edits") or [])
        if isinstance(edit, dict)
    ]
    return {**check, "edits": edits, "corrected": None}


#: What of an item the learner reads as the task (a word there is no news).
_TASK_KEYS = frozenset({"prompt", "instruction", "source", "source_fr", "situation"})


def task_text(payload: Any) -> str:
    """The task's own words, as shown: the prompt, the instruction, the sentence to transform."""

    found: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, list):
            for child in node:
                walk(child)
        elif isinstance(node, dict):
            for key, value in node.items():
                if key in _TASK_KEYS and isinstance(value, str):
                    found.append(value)
                elif isinstance(value, (dict, list)) and key not in ITEM_ANSWER_KEYS and key != "rule_panel":
                    walk(value)

    walk(payload)
    return " ".join(found)


def withhold_item(payload: Any) -> Any:
    """An item payload without its answer keys (a stored attempt's ``prompt_payload``)."""

    if isinstance(payload, list):
        return [withhold_item(item) for item in payload]
    if not isinstance(payload, dict):
        return payload
    return {key: withhold_item(value) for key, value in payload.items() if key not in ITEM_ANSWER_KEYS}


__all__ = [
    "ITEM_ANSWER_KEYS",
    "SHOWN",
    "STATE_KEY",
    "TYPED_DRILLS",
    "WITHHELD",
    "is_withheld",
    "leak_terms",
    "learner_line",
    "learner_view",
    "mark",
    "marks_for",
    "reveal",
    "scrub_hint",
    "second_chance_for",
    "withhold_check",
    "task_text",
    "typed_answer",
    "withhold_item",
]
