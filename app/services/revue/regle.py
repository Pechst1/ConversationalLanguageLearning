"""«Papier · La règle» (2026-11-22): Romy corrects like the scene's tutor and names the app's rules.

Romy's marks (``comptoir_loop.proof_marks``) were checked only by the Papier's own code. Every
desk that shows them (the counter, «Le fil», «Le titre», «La photo», «Le micro») now gets them
from :func:`marked`, which does, in order:

1. **Guards, always on** (wrong marks the first real run showed, tirage 2026-11-22):
   :func:`accept_what_stands` puts back, sentence by sentence, a question whose only change is
   its form — «Tu viens quand ?» rewritten to «Quand viens-tu ?», «De combien est la hausse … ?»
   reordered — so it is accepted as written: a question already in inversion at every level, a
   correct «est-ce que» or intonation question below B2 (:data:`SPOKEN_OK_BANDS`); a question
   word first then its subject without either («Quand la course commence ?») stays a slip, as
   ``micro.formation_slips`` says. :func:`drop_unchanged` drops a mark whose replacement is the
   learner's own words.
2. **The scene tutor's verification** (``REVUE_TUTOR_MARKS_ENABLED``): each mark, as the pair
   (the learner's words, the corrected words) in its own sentence, goes through
   ``story_lanes._accepted_correction`` — the very path a scene correction passes (grounding,
   preference swaps, gender-only changes, ``correction_contract.verified_model_edit``, unsupported
   tense changes). A mark that fails is dropped and its change taken out of Romy's corrected
   text (it is never shown, never printed); when none passes, the most serious model-free edit
   (``correction_contract.best_deterministic_edit``) stands in, as in the scene.
3. **The app's rule** (same switch): each mark is tied to a grammar concept
   (``GrammarConcept.external_id``, :func:`concept_for`) — the day's rule or a recent one when
   ``day_rules.rule_statement`` sees the correction is about it, else a catalogue unit of the
   mark's kind whose detector (``grammar_units.detector_spans``) finds the form at the corrected
   place — with its name in the learner's correction language (the scene's); ``is_day_rule`` /
   ``is_recent_rule`` say when it is one of the day's rules, and the full why («Le pourquoi»)
   is then the rule card's own line, not the model's paraphrase.

The day's rule used well is not booked as grammar practice here: the scene books it through
the journey's evaluation (``concept_evidence.with_concept_evidence`` on a ``ResponseTask``), and
no entry point takes free text alone.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable, Sequence
from typing import Any

from loguru import logger

from app.config import settings

#: Below B2 a correct spoken question stands as the learner wrote it (owner, 2026-11-22).
SPOKEN_OK_BANDS = frozenset({"A1", "A2", "B1"})
#: The concept fields a mark carries (and the views show) once tied to a rule.
VIEW_KEYS = ("concept_id", "concept_name", "is_day_rule", "is_recent_rule")


def enabled() -> bool:
    return bool(getattr(settings, "REVUE_TUTOR_MARKS_ENABLED", False))


# ---------------------------------------------------------------------------
# 1 · The guards: a question's form, a mark that changes nothing
# ---------------------------------------------------------------------------

_QWORDS = frozenset("""combien pourquoi comment quand où ou quel quelle quels quelles qui que quoi lequel laquelle
    lesquels lesquelles""".split())
_PRONOUNS = frozenset("je j tu il elle on nous vous ils elles".split())
_DETERMINERS = frozenset("""le la l les un une des du ce cet cette ces mon ma mes ton ta tes son sa ses notre nos
    votre vos leur leurs""".split())
_OPENERS = frozenset("et mais alors donc bon".split())
_PREPOSITIONS = frozenset("de d à a en pour depuis avec dans par sur chez".split())
_RAW = re.compile(r"[\w'’-]+")
_WORD = re.compile(r"[^\W\d_]+|\d+")
_INVERTED = re.compile(r"^[^\W\d_]+-(?:t-)?(?:je|tu|il|elle|on|nous|vous|ils|elles|ce)$")


def _raw(sentence: str) -> list[str]:
    return [t.replace("’", "'").lower().strip("-") for t in _RAW.findall(sentence or "")]


def learner_form(sentence: str) -> str:
    """How a question is built: ``est_ce_que``, ``inversion`` (a hyphened subject, or a
    question word then the verb: «De combien est la hausse ?»), ``fronted`` (a question word
    then its subject, neither: «Quand la course commence ?») or ``intonation`` (no question
    word in front: «Tu viens quand ?», «Et la course, elle dure combien ?»)."""

    tokens = _raw(sentence)
    if any(t.startswith(("est-ce", "qu'est-ce")) for t in tokens):
        return "est_ce_que"
    if any(_INVERTED.match(t) for t in tokens):
        return "inversion"
    i = 0
    while i < len(tokens) and tokens[i] in _OPENERS:
        i += 1
    if i < len(tokens) and tokens[i] in _PREPOSITIONS:
        i += 1
    if i >= len(tokens) or tokens[i] not in _QWORDS:
        return "intonation"
    word, i = tokens[i], i + 1
    if word == "combien" and i < len(tokens) and tokens[i].startswith("d'"):
        i += 1  # «combien d'argent»
    elif word == "combien" and i < len(tokens) and tokens[i] == "de":
        i += 2  # «combien de chevaux»
    elif word.startswith("quel"):
        i += 1  # «quel prix»
    following = tokens[i] if i < len(tokens) else ""
    head = following.split("'")[0] if "'" in following else following
    return "fronted" if following in _PRONOUNS | _DETERMINERS or head in {"j", "l"} else "inversion"


def _bag(sentence: str) -> tuple[Counter[str], set[str]]:
    """The question's words with its form taken out: «est-ce que» (and «qu'est-ce que» as
    «que»), the «-t-» of an inversion, «quoi» as «que»; the subject pronouns apart."""

    words = _WORD.findall((sentence or "").replace("’", "'").lower())
    out: list[str] = []
    i = 0
    while i < len(words):
        if words[i:i + 3] in (["est", "ce", "que"], ["est", "ce", "qu"]):
            i += 3
            continue
        out.append(words[i])
        i += 1
    out = ["que" if w in {"quoi", "qu"} else w for w in out if w != "t"]
    return Counter(w for w in out if w not in _PRONOUNS), {w for w in out if w in _PRONOUNS}


def question_form_only(learner: str, corrected: str) -> bool:
    """Both are questions with the same words; only the form differs (word order, «est-ce
    que», an inversion's pronoun copy: «la hausse est-elle»)."""

    if "?" not in learner or "?" not in corrected:
        return False
    mine, my_pronouns = _bag(learner)
    theirs, their_pronouns = _bag(corrected)
    return (mine == theirs and my_pronouns <= their_pronouns
            and their_pronouns - my_pronouns <= {"il", "elle", "ils", "elles"})


def stands_as_written(learner: str, corrected: str, band: str) -> bool:
    """A question the checks accept as the learner wrote it: the correction only moves it to
    another register (``answer_acceptance.is_preference_swap``) or changes its form alone, and
    the learner's form is right at their level."""

    from app.services.answer_acceptance import is_preference_swap

    if "?" not in learner:
        return False
    if not (is_preference_swap(learner, corrected) or question_form_only(learner, corrected)):
        return False
    form = learner_form(learner)
    return form == "inversion" or (form in {"est_ce_que", "intonation"} and band in SPOKEN_OK_BANDS)


def _pairs(learner_fr: str, target_fr: str) -> list[tuple[int, str, str]] | None:
    """The sentences side by side, ``(offset in learner_fr, learner's, Romy's)``, as
    ``proof_marks`` reads them; ``None`` when they do not line up."""

    from app.services.revue.comptoir_loop import _sentences_at

    mine, theirs = _sentences_at(learner_fr), _sentences_at(target_fr)
    if len(mine) != len(theirs) or not mine:
        return None
    return [(offset, a, b) for (offset, a), (_, b) in zip(mine, theirs, strict=True)]


def accept_what_stands(learner_fr: str, target_fr: str, band: str, shape: Callable[[str], str]) -> str:
    """Romy's text with each question that :func:`stands_as_written` put back as the learner
    wrote it (``shape``: how it prints). Unchanged when none does."""

    pairs = _pairs(learner_fr, target_fr)
    if not pairs or not any(stands_as_written(a, b, band) for _, a, b in pairs):
        return target_fr
    return shape("".join(a if stands_as_written(a, b, band) else b for _, a, b in pairs).strip())


def _same(a: str, b: str) -> bool:
    return " ".join(a.replace("’", "'").split()) == " ".join(b.replace("’", "'").split())


def drop_unchanged(marks: Sequence[dict[str, Any]], learner_fr: str, target_fr: str) -> list[dict[str, Any]]:
    """The marks without one whose replacement is the learner's own words (or with no change
    of Romy's at its place at all)."""

    from app.services.revue.pourquoi import mark_fixes

    fixes = mark_fixes(learner_fr, target_fr)
    out = []
    for mark in marks:
        fix = fixes.get(int(mark.get("start") or 0))
        if fix is None or (fix["fix"] and _same(fix["fix"], str(mark.get("span_fr") or ""))):
            continue  # nothing changes at its place: not a mark
        out.append(dict(mark))
    return out


# ---------------------------------------------------------------------------
# 2 · The scene tutor's verification
# ---------------------------------------------------------------------------


def _sentence_at(learner_fr: str, start: int) -> tuple[int, str]:
    from app.services.revue.comptoir_loop import _sentences_at

    for offset, sentence in _sentences_at(learner_fr):
        if offset <= start < offset + len(sentence):
            return offset, sentence
    return 0, learner_fr


def _apply(text: str, edits: Sequence[tuple[int, str, str]]) -> str:
    """``text`` with each ``(start, span, replacement)`` made, right to left."""

    out = text
    for start, span, new in sorted(edits, key=lambda e: e[0], reverse=True):
        if out[start:start + len(span)] == span:
            out = out[:start] + new + out[start + len(span):]
    return re.sub(r"\s+", " ", out).replace(" ,", ",").strip()


def _pair(sentence: str, at: int, span: str, fix: str) -> tuple[int, str, str]:
    """The mark as a correction the tutor reads: a dropped word takes the next word with it
    («les les écrivains» → «les écrivains»), so nothing is replaced by nothing."""

    if fix:
        return at, span, fix
    following = re.match(r"\s*([\w'’-]+)", sentence[at + len(span):])
    if following:
        return at, sentence[at:at + len(span) + following.end()], following.group(1)
    return at, span, fix


def _tutor_accepts(sentence: str, at: int, span: str, fix: str, *, rules: dict | None, language: str | None) -> bool:
    """``story_lanes._accepted_correction`` on the pair in its sentence, and what it settles
    on writes the same sentence (a tutor that would correct it otherwise does not stand by it)."""

    from app.services import day_rules
    from app.services.story_lanes import TutorCorrection, _accepted_correction

    today, recent = day_rules.rule_ids(rules)
    try:
        accepted = _accepted_correction(TutorCorrection(span_fr=span, corrected_fr=fix), sentence, rules=rules,
                                        known={rule for rule in (today, *recent) if rule}, language=language)
    except Exception as exc:  # noqa: BLE001 - a check that cannot run never lets a mark through
        logger.warning("revue regle: tutor check failed ({})", exc)
        return False
    if accepted is None:
        return False
    ours = _apply(sentence, [(at, span, fix)])
    where = sentence.find(accepted.span_fr, max(0, at - len(accepted.span_fr)))
    if where < 0:
        where = sentence.find(accepted.span_fr)
    theirs = _apply(sentence, [(where, accepted.span_fr, accepted.corrected_fr)]) if where >= 0 else ""
    return _same(ours.casefold(), theirs.casefold())


def vet(marks: Sequence[dict[str, Any]], *, learner_fr: str, target_fr: str, language: str | None,
        rules: dict | None, shape: Callable[[str], str]) -> tuple[str, list[dict[str, Any]]]:
    """``(target, marks)``: the marks the scene's tutor stands by, Romy's text without the
    changes of the others; none standing, the most serious model-free edit, or none."""

    from app.services.revue.pourquoi import mark_fixes

    fixes = mark_fixes(learner_fr, target_fr)
    kept: list[dict[str, Any]] = []
    for mark in marks:
        start, span = int(mark.get("start") or 0), str(mark.get("span_fr") or "")
        fix = (fixes.get(start) or {}).get("fix", "")
        offset, sentence = _sentence_at(learner_fr, start)
        at, wide, new = _pair(sentence, start - offset, span, fix)
        if wide and new and _tutor_accepts(sentence, at, wide, new, rules=rules, language=language):
            kept.append({**mark, "_edit": (offset + at, wide, new)})
    if len(kept) == len(marks):
        return target_fr, [_without_edit(m) for m in kept]
    if not kept:
        return _fallback(learner_fr, language=language, shape=shape)
    dropped = {int(m.get("start") or 0) for m in marks} - {int(m.get("start") or 0) for m in kept}
    pairs = _pairs(learner_fr, target_fr)
    if pairs:  # only the sentences a dropped mark was in are rebuilt; the others stay Romy's
        parts = []
        for offset, mine, theirs in pairs:
            if not any(offset <= start < offset + len(mine) for start in dropped):
                parts.append(theirs)
                continue
            edits = [(s - offset, a, b) for s, a, b in (m["_edit"] for m in kept) if offset <= s < offset + len(mine)]
            parts.append(" " + _apply(mine, edits))
        target = shape("".join(parts).strip())
    else:
        target = shape(_apply(learner_fr, [m["_edit"] for m in kept]))
    return target, [_without_edit(m) for m in kept]


def _without_edit(mark: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in mark.items() if key != "_edit"}


def _fallback(learner_fr: str, *, language: str | None, shape: Callable[[str], str]) -> tuple[str, list[dict[str, Any]]]:
    from app.services.correction_contract import best_deterministic_edit
    from app.services.revue.comptoir_loop import _mark_kind

    span, fixed, note = best_deterministic_edit(learner_fr, language=language)
    at = learner_fr.find(span) if span and fixed else -1
    if at < 0:
        return shape(learner_fr), []
    mark: dict[str, Any] = {"span_fr": span, "start": at,
                            "kind": _mark_kind(_WORD.findall(span or ""), _WORD.findall(fixed or ""))}
    if note:
        mark["why_full"] = note
    return shape(_apply(learner_fr, [(at, span, str(fixed))])), [mark]


# ---------------------------------------------------------------------------
# 3 · The app's rule: a grammar concept for each mark
# ---------------------------------------------------------------------------

#: The catalogue units each Papier rule (``correcteur.RULES``) may fall under, likeliest first.
RULE_CONCEPTS: dict[str, tuple[str, ...]] = {
    "pp_agreement": ("FR2_A21_PC_ETRE", "FR2_B11_PP_AGREEMENT_AVOIR", "FR2_A21_PC_PRONOMINAL"),
    "contraction": ("FR2_A11_CONTRACTIONS", "FR2_A11_PARTITIVE"),
    "accent": ("FR2_A12_ER_SPELLING",),
    "verb_ending": ("FR2_A11_ER_VERBS", "FR2_A12_IR_RE_VERBS", "FR2_A12_ER_SPELLING", "FR2_A21_PC_AVOIR",
                    "FR2_A12_FUTUR_PROCHE", "FR2_A12_MODALS"),
    "adj_gender": ("FR2_A11_ADJ_AGREEMENT", "FR2_A22_ADJ_SPECIAL"),
    "plural_s": ("FR2_A11_NOUN_PLURALS", "FR2_A11_ADJ_AGREEMENT"),
}
#: The units a mark's kind may fall under when no Papier rule names it.
KIND_CONCEPTS: dict[str, tuple[str, ...]] = {
    "accord": ("FR2_A11_ADJ_AGREEMENT", "FR2_A11_NOUN_PLURALS", "FR2_A21_PC_ETRE", "FR2_B11_PP_AGREEMENT_AVOIR",
               "FR2_A22_TOUT"),
    "genre": ("FR2_A11_UN_UNE", "FR2_A11_LE_LA", "FR2_A11_ADJ_AGREEMENT", "FR2_A11_POSSESSIVES",
              "FR2_A12_DEMONSTRATIVES", "FR2_A22_ADJ_SPECIAL"),
    "conjugaison": ("FR2_A11_ETRE", "FR2_A11_AVOIR", "FR2_A11_ER_VERBS", "FR2_A12_IR_RE_VERBS", "FR2_A11_ALLER_VENIR",
                    "FR2_A11_FAIRE_PRENDRE", "FR2_A12_MODALS", "FR2_A12_FUTUR_PROCHE", "FR2_A21_PC_AVOIR",
                    "FR2_A21_PC_ETRE", "FR2_A22_IMPARFAIT", "FR2_A22_FUTUR_SIMPLE", "FR2_A22_FUTUR_IRREGULAR",
                    "FR2_B11_CONDITIONAL", "FR2_B12_SUBJ_FORM", "FR2_B12_SUBJ_IRREGULAR", "FR2_B12_SUBJ_NECESSITY",
                    "FR2_B12_SUBJ_WILL", "FR2_B12_SUBJ_CONJUNCTIONS"),
    "ordre": ("FR2_A11_QUESTION_WORDS", "FR2_A11_QUESTIONS", "FR2_A21_INVERSION", "FR2_A11_NEGATION",
              "FR2_A22_PRONOUN_POSITION", "FR2_A21_COD", "FR2_A11_ADJ_AGREEMENT"),
    "manque": ("FR2_A11_NEGATION", "FR2_A21_PC_NEGATION", "FR2_A11_QUESTION_WORDS", "FR2_A11_QUESTIONS",
               "FR2_A21_PC_AVOIR", "FR2_A21_PC_ETRE", "FR2_A11_PARTITIVE", "FR2_A11_LE_LA", "FR2_A11_UN_UNE"),
    "mot": ("FR2_A11_AVOIR", "FR2_A12_CEST_IL_EST", "FR2_A21_VERB_PREPOSITIONS", "FR2_A11_PLACES",
            "FR2_A11_CONTRACTIONS", "FR2_A22_RELATIVE_QUI_QUE", "FR2_A22_MEILLEUR_MIEUX", "FR2_A21_SAVOIR_CONNAITRE"),
    "orthographe": ("FR2_A12_ER_SPELLING", "FR2_A11_LE_LA"),
}


def _hits(patterns: list[str], text: str, start: int, end: int) -> bool:
    from app.services.grammar_units import detector_spans

    return any(a < end and start < b for a, b in detector_spans(patterns, text))


def concept_for(sentence: str, span: str, fix: str, *, kind: str, rule: str | None, rules: dict | None,
                language: str) -> dict[str, Any] | None:
    """The grammar concept a mark falls under, or ``None``: ``concept_id`` (the concept's
    ``external_id``), ``concept_name`` in ``language``, ``is_day_rule`` / ``is_recent_rule``,
    and ``rule_statement`` (the day's or a recent rule's own line) when it is one of them.

    The day's and the recent rules first, when ``day_rules.rule_statement`` sees the
    correction is about one; then the catalogue units of the Papier's rule and of the mark's
    kind whose detector finds the form at the corrected place — one the correction brought in
    before one that was already there —, then another kind's unit whose form the correction
    brought in (a «mot» guessed from the diff is often a verb: «ont devenu» → «sont devenus»)."""

    from app.services import day_rules
    from app.services.grammar_units import _v2_rows_by_external_id, regex_patterns

    at = sentence.find(span) if span else -1
    if at < 0 or not fix:
        return None
    today, recent = day_rules.rule_ids(rules)
    entries = {str(e.get("id")): e for e in [(rules or {}).get("today"), *((rules or {}).get("recent") or [])]
               if isinstance(e, dict) and e.get("id")}

    def found(concept_id: str, name: str, statement: str | None) -> dict[str, Any]:
        out: dict[str, Any] = {"concept_id": concept_id, "concept_name": name,
                               "is_day_rule": concept_id == today, "is_recent_rule": concept_id in recent}
        if statement and (out["is_day_rule"] or out["is_recent_rule"]):
            out["rule_statement"] = statement
        return out

    for rule_id in [r for r in (today, *sorted(recent)) if r]:
        statement = day_rules.rule_statement(rules, rule_id, text=sentence, span=span, corrected=fix)
        if statement:
            return found(rule_id, str(entries[rule_id].get("name") or ""), statement)
    fixed = sentence[:at] + fix + sentence[at + len(span):]
    rows = _v2_rows_by_external_id()
    mine = list(dict.fromkeys([*RULE_CONCEPTS.get(rule or "", ()), *KIND_CONCEPTS.get(kind, ())]))
    others = [c for c in dict.fromkeys(c for ids in KIND_CONCEPTS.values() for c in ids) if c not in mine]
    brought: list[str] = []
    there: list[str] = []
    elsewhere: list[str] = []  # another kind's unit, only when the correction brought its form in
    for concept_id in [*mine, *others]:
        row = rows.get(concept_id)
        patterns = regex_patterns([(row or {}).get("syllabus", {}).get("detector") or {}])
        if not patterns or not _hits(patterns, fixed, at, at + len(fix)):
            continue
        new = not _hits(patterns, sentence, at, at + len(span))
        if concept_id in mine:
            (brought if new else there).append(concept_id)
        elif new:
            elsewhere.append(concept_id)
    for concept_id in [*brought, *there, *elsewhere]:
        names = rows[concept_id].get("syllabus", {}).get("names") or {}
        entry = entries.get(concept_id) or {}
        name = str(entry.get("name") or names.get(language) or names.get("en") or rows[concept_id].get("name") or "")
        return found(concept_id, name, str(entry.get("rule") or "") or None)
    return None


def name_rules(marks: Sequence[dict[str, Any]], *, learner_fr: str, target_fr: str, rules: dict | None,
               language: str) -> list[dict[str, Any]]:
    """Each mark with its concept (:func:`concept_for`) when one applies."""

    from app.services.revue.pourquoi import mark_fixes, rule_for

    fixes = mark_fixes(learner_fr, target_fr)
    out = []
    for mark in marks:
        mark = dict(mark)
        start, span = int(mark.get("start") or 0), str(mark.get("span_fr") or "")
        fix = (fixes.get(start) or {}).get("fix", "")
        offset, sentence = _sentence_at(learner_fr, start)
        at, wide, new = _pair(sentence, start - offset, span, fix)
        kind = str(mark.get("kind") or "")
        try:
            concept = concept_for(sentence, wide, new, kind=kind, rule=rule_for(kind, wide, new), rules=rules,
                                  language=language)
        except Exception as exc:  # noqa: BLE001 - a rule not named costs the name, never the mark
            logger.warning("revue regle: concept not found ({})", exc)
            concept = None
        if concept:
            mark.update(concept, fix_fr=fix)
        out.append(mark)
    return out


def state_rules(marks: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """A mark under the day's or a recent rule explains itself with that rule's own line:
    the full why always, the hint too unless the line shows the corrected words."""

    from app.services.revue.pourquoi import gives_away

    out = []
    for mark in marks:
        mark = dict(mark)
        statement = str(mark.get("rule_statement") or "")
        if statement:
            mark["why_full"] = statement
            if not gives_away(statement, str(mark.get("span_fr") or ""), str(mark.get("fix_fr") or "")):
                mark["why_hint"] = statement
        out.append(mark)
    return out


def view_fields(mark: dict[str, Any]) -> dict[str, Any]:
    """What a view shows of a mark's concept (nothing without one)."""

    if not enabled() or not mark.get("concept_id"):
        return {}
    return {key: mark.get(key) for key in VIEW_KEYS}


# ---------------------------------------------------------------------------
# The one entry every desk calls
# ---------------------------------------------------------------------------


def day_rules_for(encounter: Any, loaded: Any, language: str) -> dict | None:
    """The day's and the recent rules for the learner, as the scene reads them."""

    from app.db.models.user import User
    from app.services import day_rules

    try:
        user = encounter.db.get(User, loaded.row.user_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("revue regle: learner not read ({})", exc)
        return None
    return day_rules.for_turn(encounter.db, user, control_language=language) if user is not None else None


def marked(encounter: Any, loaded: Any, *, learner_fr: str, edited: str, hints: list[dict[str, Any]] | None,
           raw_marks: Any, band: str, language: str | None, takes: Any = None,
           shape: Callable[[str], str] | None = None) -> tuple[str, list[dict[str, Any]]]:
    """Romy's corrected text and her marks, as every desk shows them: the guards, then (switch
    on) the scene tutor's verification and the app's rules, then «Le pourquoi» when
    ``language`` is given (``pourquoi.explain_marks``)."""

    from app.services.revue import comptoir_loop, pourquoi, voice

    shape = shape or voice.french_typography
    target = accept_what_stands(learner_fr, edited, band, shape)
    marks = drop_unchanged(comptoir_loop.proof_marks(learner_fr, target, hints), learner_fr, target)
    rules: dict | None = None
    tutor_language = language
    if enabled():
        tutor_language = language or pourquoi.explain_language(encounter, loaded)
        rules = day_rules_for(encounter, loaded, tutor_language)
        if marks:
            target, marks = vet(marks, learner_fr=learner_fr, target_fr=target, language=tutor_language, rules=rules,
                                shape=shape)
            marks = name_rules(marks, learner_fr=learner_fr, target_fr=target, rules=rules, language=tutor_language)
    if language and marks:
        marks = pourquoi.explain_marks(marks, raw_marks, learner_fr=learner_fr, target_fr=target,
                                       dossier=loaded.dossier, takes=takes, band=band, language=language)
    if enabled():
        marks = state_rules(marks)
    return target, marks


__all__ = [
    "KIND_CONCEPTS",
    "RULE_CONCEPTS",
    "SPOKEN_OK_BANDS",
    "accept_what_stands",
    "concept_for",
    "drop_unchanged",
    "enabled",
    "learner_form",
    "marked",
    "name_rules",
    "question_form_only",
    "stands_as_written",
    "state_rules",
    "vet",
    "view_fields",
]
