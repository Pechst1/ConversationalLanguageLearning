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
from typing import Final

#: The answer for a change that only touches accents, apostrophes or spaces outside
#: the lent rule's own form: the slip is filed under no rule.
NO_RULE: Final = "no_rule"

POSSESSIVES_UNIT = "FR2_A11_POSSESSIVES"
DEMONSTRATIVES_UNIT = "FR2_A12_DEMONSTRATIVES"
DEFINITE_UNIT = "FR2_A11_LE_LA"
INDEFINITE_UNIT = "FR2_A11_UN_UNE"
PC_AVOIR_UNIT = "FR2_A21_PC_AVOIR"
PC_ETRE_UNIT = "FR2_A21_PC_ETRE"
ER_SPELLING_UNIT = "FR2_A12_ER_SPELLING"

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


def _stem_change_verb(before: list[str], after: list[str], removed: list[int], written: list[int]) -> bool:
    """«j'achete → j'achète», «je la leve → je la lève»: a grave accent written into the
    stem of a verb (a subject before it). «les eleves», «la regle», «est seche» are a
    noun or an adjective: no subject stands before them."""
    for index in written:
        word = after[index]
        if "è" in word and _after_subject(after, index):
            return True
    return False


#: The forms a lent rule owns when the change is only an accent: the surface's rule is
#: kept for a slip in its own form, and only then.
_ACCENT_FORMS = {ER_SPELLING_UNIT: _stem_change_verb}


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
    learner_text: object, corrected_text: object, *, lent_unit: str | None = None, context: object = None
) -> str | None:
    """The unit the change itself names (an external id), :data:`NO_RULE`, or ``None``.

    ``lent_unit`` is the external id of the rule the surface would file the slip under
    (the letter's, the step's, the séance's). It is kept only where the change is its
    form: a passé composé unit for a participle or an auxiliary, «-er verbs that change
    spelling» for an accent in a verb's stem. ``context`` is the learner's text the
    pair was cut from, read for the words in front of the slip.
    """

    before, after = _words(learner_text), _words(corrected_text)
    if not after or str(learner_text or "").strip() == str(corrected_text or "").strip():
        return None
    lead = _lead_in(before, context)
    before, after = lead + before, lead + after
    removed, written = _changed(before, after)
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
        own_form = _ACCENT_FORMS.get(lent_unit or "")
        if own_form is not None and own_form(before, after, removed, written):
            return lent_unit
        return NO_RULE
    return None
