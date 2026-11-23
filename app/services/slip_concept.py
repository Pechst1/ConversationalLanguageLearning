"""#973: which rule a slip belongs to, read off what the correction changed.

A slip used to get its rule from one of two guesses: a *family word* (any swap among
articles, possessives and demonstratives became «determiner», and that family's
first unit, «Un, une, des», won), or the *surface's rule* (a letter, a scene step or a
séance lent its own rule to every slip made in it, an accent on «café» included).
Everything downstream trusts that rule: the Cahier, the due list, the drill around
the scene, recall's «Rule: …» line and what a later right answer credits.

:func:`unit_for_change` looks at the change itself. It answers with a catalogue unit
(an external id), :data:`NO_RULE` (an accent, an apostrophe or a space: spelling, not
a grammar rule) or ``None`` (the change names no unit; the caller keeps the rule it
was lent, or infers one). ``ErrorMemoryService.concept_for_slip`` resolves it, and
every record path goes through it (``record_erratum``, the scene's inference, the
Courrier's normaliser).
"""
from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass
from typing import Final

from app.services.grammar_items import fold_apostrophes

#: The answer for a change that only touches accents, apostrophes or spaces outside
#: the lent rule's own form: the slip is filed under no rule.
NO_RULE: Final = "no_rule"

POSSESSIVES_UNIT = "FR2_A11_POSSESSIVES"
DEMONSTRATIVES_UNIT = "FR2_A12_DEMONSTRATIVES"
DEFINITE_UNIT = "FR2_A11_LE_LA"
INDEFINITE_UNIT = "FR2_A11_UN_UNE"
CONTRACTIONS_UNIT = "FR2_A11_CONTRACTIONS"
PC_AVOIR_UNIT = "FR2_A21_PC_AVOIR"
PC_ETRE_UNIT = "FR2_A21_PC_ETRE"

#: The passé composé units. A slip in a participle or an auxiliary is one of them; the
#: two that name the auxiliary are chosen by the auxiliary the correction wrote, the
#: others (chunks, negation, pronominal) keep the one the surface lent.
_PC_BY_AUXILIARY = frozenset({PC_AVOIR_UNIT, PC_ETRE_UNIT})
PC_UNITS = _PC_BY_AUXILIARY | {"FR2_A12_PC_CHUNKS", "FR2_A21_PC_NEGATION", "FR2_A21_PC_PRONOMINAL"}

#: One family per determiner word. «du», «de», «d'», «au», «aux» are left out: each is
#: a partitive, a contraction or a preposition depending on the sentence.
_DETERMINER_FAMILIES: dict[str, str] = {
    **dict.fromkeys(("mon", "ma", "mes", "ton", "ta", "tes", "son", "sa", "ses", "notre", "nos", "votre", "vos", "leur", "leurs"), POSSESSIVES_UNIT),
    **dict.fromkeys(("ce", "cet", "cette", "ces"), DEMONSTRATIVES_UNIT),
    **dict.fromkeys(("le", "la", "les", "l"), DEFINITE_UNIT),
    **dict.fromkeys(("un", "une", "des"), INDEFINITE_UNIT),
}
_DETERMINER_WORDS = frozenset(_DETERMINER_FAMILIES) | {"du", "de", "d", "au", "aux"}

_SUBJECTS = frozenset({"je", "j", "tu", "il", "elle", "on", "nous", "vous", "ils", "elles"})
#: Words that stand between a subject and its verb: «je ne les achète pas», «on se lève».
_CLITICS = frozenset({"ne", "n", "me", "m", "te", "t", "se", "s", "le", "la", "les", "l", "lui", "leur", "y", "en"})
_REFLEXIVES = frozenset({"me", "m", "te", "t", "se", "s", "nous", "vous"})
#: Words that may stand between an auxiliary and its participle: «j'ai pas mangé».
_BETWEEN_AUX_AND_PARTICIPLE = frozenset(
    {"pas", "jamais", "plus", "rien", "déjà", "bien", "mal", "encore", "toujours", "souvent", "beaucoup", "tout", "aussi", "vraiment"}
)
_AVOIR_FORMS = frozenset({"ai", "as", "a", "avons", "avez", "ont"})
_ETRE_FORMS = frozenset({"suis", "es", "est", "sommes", "êtes", "sont"})

_WORD = re.compile(r"[^\W\d_]+")


def _words(text: object) -> list[str]:
    return _WORD.findall(unicodedata.normalize("NFC", str(text or "")).casefold())


def _letters(text: object) -> str:
    """The text's letters with every accent, apostrophe, space and stop taken away."""
    decomposed = unicodedata.normalize("NFD", str(text or "").casefold())
    return "".join(char for char in decomposed if char.isalpha())


def _changed(before: list[str], after: list[str]) -> tuple[list[int], list[int]]:
    """The indices of the words the correction removed (``before``) and wrote (``after``)."""
    removed: list[int] = []
    written: list[int] = []
    matcher = difflib.SequenceMatcher(a=before, b=after, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        removed.extend(range(i1, i2))
        written.extend(range(j1, j2))
    return removed, written


def _after_subject(words: list[str], index: int) -> bool:
    """A subject pronoun stands before ``words[index]``, with only clitics between."""
    position = index - 1
    while position >= 0 and words[position] in _CLITICS and words[position] not in _SUBJECTS:
        position -= 1
    return position >= 0 and words[position] in _SUBJECTS


def _pronoun_reading(words: list[str], index: int) -> bool:
    """«le», «la», «les», «l'», «leur» right after a subject (or its clitics) are object
    pronouns: «je le vois», «je leur parle» swap no determiner."""
    return words[index] in {"le", "la", "les", "l", "leur"} and _after_subject(words, index)


def _determiner_unit(before: list[str], after: list[str], removed: list[int], written: list[int]) -> str | None:
    changed = [before[i] for i in removed] + [after[j] for j in written]
    if not changed or not set(changed) <= _DETERMINER_WORDS:
        return None
    if any(_pronoun_reading(before, i) for i in removed) or any(_pronoun_reading(after, j) for j in written):
        return None
    for words, indices in ((after, written), (before, removed)):
        if not indices:
            continue  # nothing written: the word the learner should not have used says which family
        families = {_DETERMINER_FAMILIES.get(words[i]) for i in indices}
        if len(families) == 1 and None not in families:
            return families.pop()
        return None
    return None


#: #1027: «à» (written «a» by a keyboard without accents) melts with «le»/«les» into
#: «au»/«aux», and never with «la»/«l'» («au école → à l'école»).
_A_FORMS = frozenset({"à", "a"})
_A_CONTRACTED = frozenset({"au", "aux"})
_ARTICLES = frozenset({"le", "la", "les", "l"})


def _contraction_unit(before: list[str], after: list[str], removed: list[int], written: list[int]) -> str | None:
    """The change melts a preposition into its article, or splits a melted form:
    «a le → au», «à les → aux», «de le → du», «de les → des», «au école → à l'école».

    «du → de la» and «des → de» are left out: a partitive or a negation reads the same
    («du pain», «pas de pain»), and only the sentence tells them from a contraction."""

    gone, new = [before[i] for i in removed], [after[j] for j in written]
    if not gone or not new:
        return None
    for one, other in ((gone, new), (new, gone)):
        if (
            set(one) <= _A_CONTRACTED
            and set(other) <= _A_FORMS | _ARTICLES
            and set(other) & _A_FORMS
            and set(other) & _ARTICLES
        ):
            return CONTRACTIONS_UNIT
    # «de» + «le»/«les» the learner wrote apart, melted by the correction.
    if set(new) <= {"du", "des"} and set(gone) <= {"de", "le", "les"} and "de" in gone and set(gone) & {"le", "les"}:
        return CONTRACTIONS_UNIT
    return None


def change_identity(learner_text: object, corrected_text: object) -> str:
    """#1027: what a slip changed, as its identity: the learner's words and the
    corrected words, case, spacing and apostrophe forms aside. Two slips are the same
    slip only when they change the same words the same way («cafe → café» twice), never
    because they share a label («Spelling») or a letter."""

    def fold(text: object) -> str:
        return " ".join(fold_apostrophes(unicodedata.normalize("NFC", str(text or ""))).casefold().split())

    return f"{fold(learner_text)}→{fold(corrected_text)}"


def spelling_only(learner_text: object, corrected_text: object) -> bool:
    """The correction touches only accents, apostrophes, spaces or capitals: «cafe →
    café», «c est → c'est». Such a slip names no pattern a label could stand for, so
    nothing but its own change says which slip it is (#1027)."""

    return bool(_letters(corrected_text)) and _letters(learner_text) == _letters(corrected_text)


def _participle(word: str) -> bool:
    """A past participle, agreed or not: «mangé», «arrivée», «partis», «pris»."""
    from app.services import correction_contract

    for ending in ("es", "s", "e", ""):
        if ending and not word.endswith(ending):
            continue
        base = word[: len(word) - len(ending)] if ending else word
        if base and correction_contract._participle(base):
            return True
    return False


def _etre_participle(word: str) -> bool:
    from app.services.correction_contract import _ETRE_PARTICIPLES

    for ending in ("es", "s", "e", ""):
        if word.endswith(ending) and (word[: len(word) - len(ending)] if ending else word) in _ETRE_PARTICIPLES:
            return True
    return False


def _compound_past(words: list[str], aux_index: int, participle_index: int) -> str | None:
    """The passé composé unit an auxiliary and its participle make, or ``None``."""
    aux, participle = words[aux_index], words[participle_index]
    if aux in _AVOIR_FORMS and _participle(participle):
        return PC_AVOIR_UNIT
    if aux in _ETRE_FORMS and _participle(participle):
        # After «être» a participle is told from an adjective («je suis fatiguée») by
        # the verb: a verb of movement, or a pronominal verb («elle s'est levée»).
        if _etre_participle(participle) or (aux_index > 0 and words[aux_index - 1] in _REFLEXIVES):
            return PC_ETRE_UNIT
    return None


def _passe_compose_unit(after: list[str], written: list[int]) -> str | None:
    """The correction wrote a participle after an auxiliary, or the auxiliary of a
    participle: «ai mange → ai mangé», «est arrive → est arrivée», «a parti → est parti»."""
    for index in written:
        back = index - 1
        while back >= 0 and after[back] in _BETWEEN_AUX_AND_PARTICIPLE | {"ne", "n"}:
            back -= 1
        if back >= 0 and (unit := _compound_past(after, back, index)):
            return unit
        ahead = index + 1
        while ahead < len(after) and after[ahead] in _BETWEEN_AUX_AND_PARTICIPLE:
            ahead += 1
        if ahead < len(after) and (unit := _compound_past(after, index, ahead)):
            return unit
    return None


@dataclass(frozen=True)
class LentForm:
    """What the lent rule's own form looks like, from its catalogue entry: its regex
    detectors (``pattern`` strings) and its ✗/✓ pairs (``main_traps``, the rule card's
    traps). An accent-only slip stays the lent rule's only when one of them says the
    changed word is that form."""

    patterns: tuple[str, ...] = ()
    traps: tuple[tuple[str, str], ...] = ()


def _spliced(learner_text: object, corrected_text: object, context: object) -> tuple[str, str]:
    """The learner's sentence and the corrected sentence: ``context`` with the span
    replaced when the span sits in it (a detector needs «le bar où», not «où»)."""

    span, fixed = fold_apostrophes(learner_text), fold_apostrophes(corrected_text)
    sentence = fold_apostrophes(context)
    at = sentence.casefold().find(span.casefold()) if span.strip() else -1
    if at < 0 or len(sentence.casefold()) != len(sentence):
        return span, fixed
    return sentence, sentence[:at] + fixed + sentence[at + len(span) :]


def _hits(patterns: tuple[str, ...], text: str, flags: int) -> int:
    count = 0
    for pattern in patterns:
        try:
            count += sum(1 for _ in re.finditer(pattern, text, flags))
        except re.error:
            continue
    return count


def _detector_owns(patterns: tuple[str, ...], learner_text: object, corrected_text: object, context: object) -> bool:
    """A lent rule's detector recognises its form where the correction wrote it, and
    the learner's sentence lacked it there: «le bar où», «nous commençons», «qu'il
    fût», «Quel que soit», «lundi 3 mars». «j ai vu → j'ai vu» touches a passé composé
    the learner had already written: the apostrophe is not that rule's form."""

    from app.services.grammar_units import detector_spans

    if not patterns:
        return False
    before, after = _spliced(learner_text, corrected_text, context)
    matcher = difflib.SequenceMatcher(a=before, b=after, autojunk=False)
    edits = [(j1, j2) for tag, _i1, _i2, j1, j2 in matcher.get_opcodes() if tag != "equal"]
    at_change = any(
        # a written character inside the match, or a character removed from it
        (j1 < end and j2 > start) if j1 < j2 else (start <= j1 <= end)
        for start, end in detector_spans(list(patterns), after)
        for j1, j2 in edits
    )
    if not at_change:
        return False
    if _hits(patterns, after, re.IGNORECASE) > _hits(patterns, before, re.IGNORECASE):
        return True
    # A capital only: the detectors read case-blind, so ask them case by case
    # («Lundi 3 Mars → lundi 3 mars»).
    return before.casefold() == after.casefold() and _hits(patterns, after, 0) > _hits(patterns, before, 0)


def _swap(learner_text: object, corrected_text: object) -> tuple[tuple[str, ...], tuple[str, ...]]:
    before, after = _words(learner_text), _words(corrected_text)
    removed, written = _changed(before, after)
    return tuple(before[i] for i in removed), tuple(after[j] for j in written)


def _trap_owns(traps: tuple[tuple[str, str], ...], learner_text: object, corrected_text: object) -> bool:
    """The slip swaps the very words one of the rule's own ✗/✓ pairs swaps:
    «nous achètons → nous achetons» is a listed trap of the -er spelling verbs."""

    swap = _swap(learner_text, corrected_text)
    if not any(swap):
        return False
    return any(_swap(wrong, right) == swap for wrong, right in traps)


def owns_form(lent: LentForm | None, learner_text: object, corrected_text: object, context: object = None) -> bool:
    """The changed word is the lent rule's own form (its detector, or one of its traps)."""

    if lent is None:
        return False
    return _detector_owns(lent.patterns, learner_text, corrected_text, context) or _trap_owns(
        lent.traps, learner_text, corrected_text
    )


def _lead_in(span: list[str], context: object) -> list[str]:
    """The words of ``context`` (the learner's whole text) before the slip: a pair
    often quotes only «le aime», and «je» in front of it says it is a pronoun."""
    words = _words(context)
    if not span:
        return []
    for start in range(len(words) - len(span) + 1):
        if words[start : start + len(span)] == span:
            return words[max(0, start - 4) : start]
    return []


def unit_for_change(
    learner_text: object,
    corrected_text: object,
    *,
    lent_unit: str | None = None,
    lent_form: LentForm | None = None,
    context: object = None,
) -> str | None:
    """The unit the change itself names (an external id), :data:`NO_RULE`, or ``None``.

    ``lent_unit`` is the external id of the rule the surface would file the slip under
    (the letter's, the step's, the séance's). It is kept only where the change is its
    form: a passé composé unit for a participle or an auxiliary; for an accent, an
    apostrophe, a space or a capital, a change ``lent_form`` (the unit's detectors and
    traps) recognises as the unit's own («le bar où», «nous commençons», «la vôtre»).
    ``context`` is the learner's text the pair was cut from, read for the words in
    front of the slip and by the detectors.
    """

    before, after = _words(learner_text), _words(corrected_text)
    if not after or str(learner_text or "").strip() == str(corrected_text or "").strip():
        return None
    lead = _lead_in(before, context)
    before, after = lead + before, lead + after
    removed, written = _changed(before, after)
    contraction = _contraction_unit(before, after, removed, written)
    if contraction is not None:
        return contraction
    determiner = _determiner_unit(before, after, removed, written)
    if determiner is not None:
        return determiner
    accent_only = _letters(learner_text) == _letters(corrected_text)
    if lent_unit is None or lent_unit in PC_UNITS or accent_only:
        compound = _passe_compose_unit(after, written)
        if compound is not None:
            if lent_unit in PC_UNITS and lent_unit not in _PC_BY_AUXILIARY:
                return lent_unit
            return compound
    if accent_only:
        if lent_unit is not None and owns_form(lent_form, learner_text, corrected_text, context):
            return lent_unit
        return NO_RULE
    return None
