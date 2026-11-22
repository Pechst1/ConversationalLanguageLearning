"""«Papier · Le pourquoi» (owner 2026-11-20): Romy's marks that teach.

On «Ton avis» Romy marks the learner's slips (``comptoir_loop.proof_marks``) and the learner
fixes them. A mark said *that* something was wrong, never *why*, and nothing came back. With
``REVUE_POURQUOI_ENABLED`` a mark also carries:

* ``why_hint`` and ``why_full`` — one sentence each, ≤ 22 words, stating the RULE in the
  learner's mother tongue (``chrome_language.user_correction_language``: the app's rule for
  correction notes at every level; the interface stays French from B1), written by the same
  ``comptoir_edit`` call (:func:`edit_instructions`, prompt ``comptoir-edit-v4``). The hint shows
  while the learner fixes the sentence and must not contain the corrected form (no solution
  before a retry); the full why shows once the proof is settled. **Design: both from the model,
  and both checked** (:func:`check_why`): the hint is refused when it carries a word the
  correction adds or the corrected stretch itself, so a model that ignores the rule costs the
  hint, never the answer. Any failed check drops the why and keeps the mark and its kind.
* ``example_fr`` — the same pattern in today's story (:func:`story_example`), found by the app in
  the dossier's own lead, summary and honest takes, never written by the model; shown as
  «Dans l'article : …» only once settled.
* ``rule_id`` — the Correcteur's rule (``correcteur.RULES``: ``pp_agreement``, ``contraction``,
  ``accent``, ``verb_ending``, ``adj_gender``, ``plural_s``) when the wrong/right pair maps to
  one (``correcteur._diff_rule``) and the mark's kind agrees with it; absent otherwise.

Once settled, the slips the learner repaired or missed go to their error memory
(:func:`remember`, ``ErrorMemoryService.record_erratum``, ``source_type="revue"``), each one
first passed through ``fault_quality.learner_own_fault`` so no half-edited sentence is stored;
La Forge and the drill serve them on a later day with their usual scheduling.

Everything here is a function a second player can call («Le fil» reuses the edit and the fix
step): :func:`explain_marks` on the checked edit, :func:`hint_of` and :func:`notes_of` for the
view, :func:`remember` at settle.
"""

from __future__ import annotations

import difflib
import re
import unicodedata
from collections.abc import Sequence
from typing import Any

from loguru import logger

from app.config import settings

POURQUOI_PROMPT_VERSION = "comptoir-edit-v4"
#: The context key that turns the extended prompt on (absent: today's prompt and payload).
EXPLAIN_KEY = "explain_language"
WHY_MAX_WORDS = 22
#: A story sentence longer than this is not shown as an example.
EXAMPLE_MAX_WORDS = 35
#: How the error memory names the Papier.
SOURCE_TYPE = "revue"
#: A mark's kind, as the error memory files it when no rule maps.
KIND_TASK: dict[str, str] = {
    "accord": "agreement",
    "conjugaison": "verb_conjugation",
    "genre": "gender_agreement",
    "orthographe": "spelling",
    "mot": "word_choice",
    "ordre": "word_order",
    "manque": "missing_word",
}
#: The kinds each Correcteur rule may come under (a rule from a pair whose kind disagrees is dropped).
RULE_KINDS: dict[str, frozenset[str]] = {
    "accent": frozenset({"orthographe"}),
    "verb_ending": frozenset({"conjugaison", "orthographe"}),
    "adj_gender": frozenset({"accord", "genre"}),
    "plural_s": frozenset({"accord"}),
    "pp_agreement": frozenset({"accord"}),
    "contraction": frozenset({"mot", "orthographe", "accord"}),
}


def enabled() -> bool:
    return bool(getattr(settings, "REVUE_POURQUOI_ENABLED", False))


# ---------------------------------------------------------------------------
# The prompt: today's, extended only when the context asks for the why
# ---------------------------------------------------------------------------

_SCHEMA_V3 = '{"edited_fr": str, "marks": [{"span_fr": str, "kind": str}], "reply_fr": str, "reply_en": str, "reply_de": str}'
_SCHEMA_V4 = ('{"edited_fr": str, "marks": [{"span_fr": str, "kind": str, "why_hint": str, "why_full": str}], '
              '"reply_fr": str, "reply_en": str, "reply_de": str}')
_WHY_RULES = """- why_hint and why_full (every mark): one sentence each, 22 words at most, written in the language named by
  INPUT.explain_language (en English, de German, fr French), stating the grammar RULE behind the mark (what agrees
  with what, which tense or form a word takes and why, where the accent goes), never just «wrong word». why_hint is
  read BEFORE the learner fixes the sentence: it must NOT contain the corrected form nor any word you added or
  changed; it may quote the learner's own words in «». why_full is read after the fix: it may quote the corrected
  form in «». Never name the app, a field name or an id."""


def edit_instructions(context: dict[str, Any] | None) -> str:
    """The ``comptoir_edit`` instructions for ``context``: today's (``comptoir-edit-v3``) unless
    the context carries :data:`EXPLAIN_KEY`, then v4 (the marks' ``why_hint`` and ``why_full``)."""

    from app.services.revue.comptoir_loop import COMPTOIR_EDIT_INSTRUCTIONS

    if not (context or {}).get(EXPLAIN_KEY):
        return COMPTOIR_EDIT_INSTRUCTIONS
    extended = COMPTOIR_EDIT_INSTRUCTIONS.replace(_SCHEMA_V3, _SCHEMA_V4, 1)
    return extended.replace("\n- reply_fr:", f"\n{_WHY_RULES}\n- reply_fr:", 1)


def explain_language(encounter: Any, loaded: Any) -> str:
    """The learner's correction language (mother tongue folded onto en / de / fr), from their
    user row; the plan's gloss language when the row cannot be read."""

    from app.services.chrome_language import fold_language, user_correction_language

    try:
        from app.db.models.user import User

        user = encounter.db.get(User, loaded.row.user_id)
        if user is not None:
            return user_correction_language(user)
    except Exception as exc:  # noqa: BLE001 - the plan's language stands in
        logger.warning("revue pourquoi: learner not read ({})", exc)
    from app.services.revue.encounter import _gloss_language_of

    return fold_language(_gloss_language_of(loaded.plan))


# ---------------------------------------------------------------------------
# The checks
# ---------------------------------------------------------------------------

_WORD = re.compile(r"[^\W\d_]+(?:['’-][^\W\d_]+)*")
_PIECE = re.compile(r"[^\W\d_]+")
_QUOTED = re.compile(r"«[^»]*»|“[^”]*”|„[^“”]*[“”]|\"[^\"]*\"|‹[^›]*›")
_SNAKE = re.compile(r"\b[a-z]+_[a-z_]+\b", re.IGNORECASE)
_MACHINE = re.compile(r"\b(json|span|prompt|learner|app|api|null|kind|input|output)\b", re.IGNORECASE)
_LANGUAGE_MARKERS: dict[str, frozenset[str]] = {
    "en": frozenset("""the a an is are be with of and to after before when its it use uses must needs takes this that
        noun verb not for by on here word words because so has have their which""".split()),
    "de": frozenset("""der die das den dem des ein eine einen einem ist sind mit und nach vor wenn im zu nicht wird
        muss braucht hier bei auf für von sich man wort verb nomen weil also hat haben steht""".split()),
    "fr": frozenset("""le la les un une des est sont avec et après avant quand se il elle on dans du au aux pour par
        pas ne qui que doit verbe nom mot parce donc a ont""".split()),
}


def _norm(text: Any) -> str:
    return unicodedata.normalize("NFC", str(text or "")).replace("’", "'").replace("‘", "'")


def _pieces(text: Any) -> list[str]:
    """Lower-cased letter runs (accents kept: an accent can be the slip)."""

    return [piece.casefold() for piece in _PIECE.findall(_norm(text))]


def reads_as(text: str, language: str) -> bool:
    """``text`` (its quoted French aside) reads as ``language``: at least two of its small
    words, and more than any other language's."""

    words = [word.casefold() for word in _WORD.findall(_QUOTED.sub(" ", _norm(text)))]
    counts = {lang: sum(word in markers for word in words) for lang, markers in _LANGUAGE_MARKERS.items()}
    mine = counts.get(language, 0)
    return mine >= 2 and all(mine > count for lang, count in counts.items() if lang != language)


def gives_away(text: str, span: str, fix: str) -> bool:
    """``text`` shows the answer: the corrected stretch, or a word the correction adds or changes."""

    fix_pieces = _pieces(fix)
    if not fix_pieces:
        return False
    learner = set(_pieces(span))
    added = {piece for piece in fix_pieces if piece not in learner}
    said = _pieces(text)
    if added & set(said):
        return True
    width = len(fix_pieces)
    return any(said[i:i + width] == fix_pieces for i in range(len(said) - width + 1))


def _machine_words(text: str) -> bool:
    from app.services.revue import voice

    return bool(voice.app_words(text) or voice.meta_words(text) or voice.id_leaks(text)
                or _SNAKE.search(text) or _MACHINE.search(text))


def check_why(hint: Any, full: Any, *, span: str, fix: str, learner_fr: str, language: str) -> tuple[dict[str, str], str | None]:
    """The two whys of one mark, checked: both a sentence in ``language`` of at most
    :data:`WHY_MAX_WORDS` words that states a rule (``correction_contract.note_states_a_rule``),
    quotes only words the learner wrote or the fix writes (``note_quotes_hold``) and names no
    app word or id; the hint never gives the answer away (:func:`gives_away`). Both or neither:
    ``({}, problem)`` on any failure."""

    from app.services.correction_contract import note_quotes_hold, note_states_a_rule

    texts = {"why_hint": re.sub(r"\s+", " ", str(hint or "")).strip(),
             "why_full": re.sub(r"\s+", " ", str(full or "")).strip()}
    for key, text in texts.items():
        if not text:
            return {}, f"{key}:empty"
        if len(_WORD.findall(text)) > WHY_MAX_WORDS:
            return {}, f"{key}:too_long"
        if not reads_as(text, language):
            return {}, f"{key}:language"
        if _machine_words(text):
            return {}, f"{key}:app_words"
        if not note_states_a_rule(text, span, fix):
            return {}, f"{key}:no_rule"
    if gives_away(texts["why_hint"], span, fix):
        return {}, "why_hint:gives_away"
    if not note_quotes_hold(texts["why_hint"], span, span, learner_fr):
        return {}, "why_hint:quotes"
    if not note_quotes_hold(texts["why_full"], span, fix, learner_fr):
        return {}, "why_full:quotes"
    return texts, None


# ---------------------------------------------------------------------------
# Each mark's corrected stretch, its rule, the story's example
# ---------------------------------------------------------------------------


def mark_fixes(learner_fr: str, target_fr: str) -> dict[int, dict[str, str]]:
    """For each place :func:`comptoir_loop.proof_marks` would mark (by its ``start``): the
    corrected stretch (``fix``) and the target's words around it (``before``, ``after``).
    Server-side only: never in a view before the proof is settled."""

    from app.services.revue.comptoir_loop import _TOKEN, _token_key

    mine = list(_TOKEN.finditer(learner_fr))
    theirs = list(_TOKEN.finditer(target_fr))
    keys_a = [_token_key(m.group(0), i) for i, m in enumerate(mine)]
    keys_b = [_token_key(m.group(0), i) for i, m in enumerate(theirs)]
    out: dict[int, dict[str, str]] = {}
    if not mine:
        return out
    for op, i1, _i2, j1, j2 in difflib.SequenceMatcher(None, keys_a, keys_b, autojunk=False).get_opcodes():
        if op == "equal":
            continue
        if op == "insert":
            start = mine[max(i1 - 1, 0)].start()
            lo, hi = (j1 - 1, j2 - 1) if i1 > 0 and j1 > 0 else (j1, min(j2, len(theirs) - 1))
        elif op == "delete":
            out.setdefault(mine[i1].start(), {"fix": "", "before": "", "after": ""})
            continue
        else:
            start = mine[i1].start()
            lo, hi = j1, j2 - 1
        if not 0 <= lo <= hi < len(theirs):
            continue
        out.setdefault(start, {
            "fix": target_fr[theirs[lo].start():theirs[hi].end()],
            "before": theirs[lo - 1].group(0) if lo > 0 else "",
            "after": theirs[hi + 1].group(0) if hi + 1 < len(theirs) else "",
        })
    return out


def rule_for(kind: str, span: str, fix: str) -> str | None:
    """The Correcteur's rule for this wrong/right pair, when the mark's kind agrees with it."""

    if not span or not fix:
        return None
    from app.services.revue.correcteur import _diff_rule

    rule = _diff_rule(span, fix)
    return rule if rule and kind in RULE_KINDS.get(rule, frozenset()) else None


_GRAMMAR = frozenset("""le la les l un une des du de d au aux ce cet cette ces mon ton son ma ta sa mes tes ses
    notre votre nos vos leur leurs à a en et ou mais je j tu il elle on nous vous ils elles me m te t se s y ne n pas
    que qu qui est sont""".split())
_SENTENCE = re.compile(r"[^.!?…]+[.!?…]*")


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in _SENTENCE.findall(str(text or "")) if part.strip()]


def _needles(fix: str, before: str, after: str) -> list[str]:
    """What a story sentence must carry to show the pattern: the corrected stretch with the
    word after it, or before it; alone only when it holds a word of four letters or more that
    is not a small grammar word."""

    needles = []
    if after:
        needles.append(f"{fix} {after}")
    if before:
        needles.append(f"{before} {fix}")
    if any(len(piece) >= 4 and piece not in _GRAMMAR for piece in _pieces(fix)):
        needles.append(fix)
    return needles


def story_example(dossier: Any, takes: Any, band: str, *, fix: str, before: str = "", after: str = "") -> str | None:
    """A sentence of today's story — the lead for ``band``, the summary, then the regulars'
    honest takes (never the intox) — that carries the corrected pattern; ``None`` when none does."""

    if not fix or not _pieces(fix):
        return None
    planted = takes.intox.wrong_fr if getattr(takes, "intox", None) is not None else None
    liar = takes.intox.by if getattr(takes, "intox", None) is not None else None
    texts = [dossier.lead_for(band).fr, dossier.summary_fr]
    texts += [guest.take.for_band(band).fr for guest in getattr(takes, "guests", []) if guest.id != liar]
    candidates = [s for text in texts for s in _sentences(text)]
    for needle in _needles(fix, before, after):
        pattern = r"(?<![\w'])" + r"\s+".join(re.escape(_norm(w).casefold()) for w in needle.split()) + r"(?![\w'])"
        for sentence in candidates:
            if planted and _norm(planted).casefold() in _norm(sentence).casefold():
                continue
            if len(_WORD.findall(sentence)) > EXAMPLE_MAX_WORDS:
                continue
            if re.search(pattern, _norm(sentence).casefold()):
                return sentence
    return None


def explain_marks(marks: Sequence[dict[str, Any]], raw_marks: Any, *, learner_fr: str, target_fr: str,
                  dossier: Any, takes: Any, band: str, language: str) -> list[dict[str, Any]]:
    """Romy's marks (``proof_marks``) with their pourquoi: the model's whys for the one model
    mark over each (checked by :func:`check_why`), the corrected stretch (``fix_fr``, kept
    server-side), ``example_fr`` and ``rule_id``. A mark the checks refuse keeps its kind."""

    lowered = learner_fr.lower()
    rows = []
    for row in raw_marks if isinstance(raw_marks, list) else []:
        if not isinstance(row, dict):
            continue
        span = re.sub(r"\s+", " ", str(row.get("span_fr") or "")).strip(" .,!?").lower()
        at = lowered.find(span) if span else -1
        if at >= 0:
            rows.append((at, at + len(span), row))
    fixes = mark_fixes(learner_fr, target_fr)
    out = []
    for mark in marks:
        mark = dict(mark)
        start, end = int(mark.get("start") or 0), int(mark.get("start") or 0) + len(str(mark.get("span_fr") or ""))
        place = fixes.get(start, {"fix": "", "before": "", "after": ""})
        fix = place["fix"]
        mark["fix_fr"] = fix
        over = [row for a, b, row in rows if a < end and start < b]
        if len(over) == 1 and fix:
            whys, problem = check_why(over[0].get("why_hint"), over[0].get("why_full"), span=str(mark["span_fr"]),
                                      fix=fix, learner_fr=learner_fr, language=language)
            mark.update(whys)
            if problem:
                mark["why_refused"] = problem
        if example := story_example(dossier, takes, band, fix=fix, before=place["before"], after=place["after"]):
            mark["example_fr"] = example
        if rule := rule_for(str(mark.get("kind")), str(mark.get("span_fr")), fix):
            mark["rule_id"] = rule
        out.append(mark)
    return out


# ---------------------------------------------------------------------------
# The view
# ---------------------------------------------------------------------------


def hint_of(mark: dict[str, Any]) -> str | None:
    """The why shown on the fix step: the hint (never the corrected form), switch on only."""

    return (str(mark.get("why_hint") or "") or None) if enabled() else None


def rounds_of(opinion: dict[str, Any] | None, fixes: Sequence[dict[str, Any]]) -> list[tuple[str, list[dict[str, Any]]]]:
    """Each round the learner was shown marks in: the sentence they were on, and the marks."""

    rows = ([(str(opinion.get("learner_fr") or ""), opinion)] if opinion else [])
    rows += [(str(fix.get("text_fr") or ""), fix) for fix in fixes]
    return [(draft, [m for m in row.get("marks") or [] if isinstance(m, dict)])
            for draft, row in rows if row.get("proof") == "marked" and row.get("marks")]


def settled(rounds: list[tuple[str, list[dict[str, Any]]]], proof: str) -> list[dict[str, Any]]:
    """The marks the learner saw, once the proof is ``fixed`` or ``corrected``: each once (its
    latest round), with the sentence it was on (``draft_fr``) and ``outcome`` — ``missed`` when
    it was still marked when Romy corrected it, else ``repaired``. Empty for any other proof
    (a failed check: when in doubt, nothing)."""

    if proof not in {"fixed", "corrected"} or not rounds:
        return []
    last = len(rounds) - 1
    seen: dict[tuple[str, str], dict[str, Any]] = {}
    for index, (draft, marks) in enumerate(rounds):
        for mark in marks:
            key = (str(mark.get("span_fr") or "").casefold(), str(mark.get("kind") or ""))
            missed = proof == "corrected" and index == last
            seen.pop(key, None)
            seen[key] = {**mark, "draft_fr": draft, "outcome": "missed" if missed else "repaired"}
    return list(seen.values())


def notes_of(rounds: list[tuple[str, list[dict[str, Any]]]], proof: str) -> list[dict[str, Any]]:
    """What the settled screen explains (switch on only): the marks with a full why, an
    example or a rule."""

    if not enabled():
        return []
    return [
        {"span_fr": str(m.get("span_fr")), "kind": str(m.get("kind")), "why": m.get("why_full") or None,
         "example_fr": m.get("example_fr") or None, "rule_id": m.get("rule_id") or None}
        for m in settled(rounds, proof)
        if m.get("why_full") or m.get("example_fr") or m.get("rule_id")
    ]


# ---------------------------------------------------------------------------
# The mark comes back: the error memory
# ---------------------------------------------------------------------------


def remember(db: Any, user_id: Any, rounds: list[tuple[str, list[dict[str, Any]]]], proof: str, *,
             session_id: str, dossier_id: str) -> list[dict[str, Any]]:
    """The settled slips into the learner's error memory (``source_type="revue"``), each
    once, only when it is the learner's own French (``fault_quality.learner_own_fault``: a
    whole run of words of the sentence they wrote, no doubled word, a well-formed fix) and a
    real correction (``record_erratum`` refuses the rest). Never raises: a failed write costs
    the memory, not the session. Returns what was done, per slip."""

    if not enabled():
        return []
    from app.db.models.user import User
    from app.services.error_memory import ErrorMemoryService
    from app.services.fault_quality import learner_own_fault

    done: list[dict[str, Any]] = []
    try:
        user = db.get(User, user_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("revue pourquoi: learner not read ({})", exc)
        return done
    if user is None:
        return done
    service = ErrorMemoryService(db)
    for mark in settled(rounds, proof):
        span, fix, draft = str(mark.get("span_fr") or ""), str(mark.get("fix_fr") or ""), str(mark.get("draft_fr") or "")
        entry = {"span_fr": span, "outcome": mark["outcome"], "action": None}
        done.append(entry)
        if not fix or not learner_own_fault(wrong=span, correct=fix, submitted=draft):
            entry["action"] = "refused"
            continue
        kind = str(mark.get("kind") or "")
        erratum = {
            "learner_text": span,
            "corrected_target": fix,
            "context_fr": draft,
            "why_wrong": mark.get("why_full") or None,
            "task_error_type": mark.get("rule_id") or KIND_TASK.get(kind, "grammar_target"),
            "severity": 2,
            "recurring": True,
        }
        try:
            with db.begin_nested():
                update = service.record_erratum(
                    user=user, erratum=erratum, source_type=SOURCE_TYPE,
                    source_payload={"surface": "papier", "session_id": session_id, "dossier_id": dossier_id,
                                    "kind": kind, "rule_id": mark.get("rule_id"), "outcome": mark["outcome"]},
                )
            entry["action"] = (update or {}).get("action") or "refused"
        except Exception as exc:  # noqa: BLE001
            logger.warning("revue pourquoi: fault not kept ({})", exc)
            entry["action"] = "failed"
    return done


__all__ = [
    "EXPLAIN_KEY",
    "POURQUOI_PROMPT_VERSION",
    "SOURCE_TYPE",
    "check_why",
    "edit_instructions",
    "enabled",
    "explain_language",
    "explain_marks",
    "gives_away",
    "hint_of",
    "mark_fixes",
    "notes_of",
    "reads_as",
    "remember",
    "rounds_of",
    "rule_for",
    "settled",
    "story_example",
]
