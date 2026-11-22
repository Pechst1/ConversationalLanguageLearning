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


_SOFT_C_ENDINGS = ("çons", "çais", "çait", "çaient", "çant", "ça", "ças", "çâmes", "çâtes")
_SPOKEN_ENDINGS = ("ons", "ez", "ions", "iez", "ais", "ait", "aient")


def _stem_change_verb(before: list[str], after: list[str], removed: list[int], written: list[int]) -> bool:
    """The spelling an -er verb's stem takes, in a verb (a subject before it):

    - a grave accent written before a silent ending: «j'achete → j'achète», «je la leve
      → je la lève»;
    - «ç» before «a» or «o»: «nous commencons → nous commençons»;
    - the grave accent taken away before a spoken ending: «nous achètons → nous
      achetons».

    «les eleves», «la regle», «est seche» are a noun or an adjective: no subject stands
    before them."""
    took_grave_away = any("è" in before[index] for index in removed)
    for index in written:
        word = after[index]
        if not _after_subject(after, index):
            continue
        if "è" in word or word.endswith(_SOFT_C_ENDINGS):
            return True
        if took_grave_away and "è" not in word and word.endswith(_SPOKEN_ENDINGS):
            return True
    return False


#: The forms a lent rule owns when the change is only an accent: the surface's rule is
#: kept for a slip in its own form, and only then.
_ACCENT_FORMS = {ER_SPELLING_UNIT: _stem_change_verb}


@dataclass(frozen=True)
class LentForm:
    """The lent unit's own form, as the catalogue writes it (review of #978).

    ``patterns`` are the unit's regex detectors (the ones La Forge and «Rayons X» read);
    ``traps`` its ✗/✓ pairs (``main_traps`` and the rule card's). A change that only
    touches accents, apostrophes, spaces or capitals keeps the lent rule when it is the
    rule's form:

    - the change is one of the unit's own traps, or the one word a trap swaps:
      «nous achètons → nous achetons», «la votre → la vôtre», «Lundi 3 Mars → lundi 3
      mars»;
    - or the detector recognises the rule's form on the changed characters of the
      corrected sentence *and not* on the same characters of the learner's: the change
      made the form («le bar ou on → le bar où on», «qu'il fut → qu'il fût», «nous
      commencons → nous commençons»). A word the detector reads either way is only
      inside the rule's span, not its form: «un cafe → un café» under «Un, une, des»,
      «mon frere → mon frère» under the possessives.

    An apostrophe written into a space or a gap is elision, never a rule's form here
    («c est → c'est»), unless a trap of the unit lists it. «cafe → café» or «a → à» in a
    passé composé letter touch no such form and stay no rule's.
    """

    patterns: tuple[str, ...] = ()
    traps: tuple[tuple[str, str], ...] = ()

    def owns(self, learner_text: object, corrected_text: object, context: object = None) -> bool:
        return self._is_trap(learner_text, corrected_text) or self._detector_on_change(
            learner_text, corrected_text, context
        )

    def _is_trap(self, learner_text: object, corrected_text: object) -> bool:
        for fold in (False, True):
            pair = (_cased_words(learner_text, fold), _cased_words(corrected_text, fold))
            swap = _one_word_swap(*pair) if fold else None
            for wrong, right in self.traps:
                trap = (_cased_words(wrong, fold), _cased_words(right, fold))
                if _replaces_in(trap, pair) or (swap is not None and _one_word_swap(*trap) == swap):
                    return True
        return False

    def _detector_on_change(self, learner_text: object, corrected_text: object, context: object) -> bool:
        if not self.patterns:
            return False
        from app.services.grammar_units import detector_spans

        before, after = _in_context(learner_text, corrected_text, context)
        changes = [change for change in _changes(before, after) if not _elision_only(before, after, change)]
        if not changes:
            return False
        patterns = list(self.patterns)
        corrected_spans = detector_spans(patterns, after)
        learner_spans = detector_spans(patterns, before)
        for i1, i2, j1, j2 in changes:
            if not _tells_words_apart(_touched_words(before, i1, i2), _touched_words(after, j1, j2)):
                continue  # «hotel → hôtel»: an accent on a word with no accent-free twin
            if not any(_touches(span, j1, j2) for span in corrected_spans):
                continue  # the change is outside every use of the rule's form
            if any(_touches(span, i1, i2) for span in learner_spans):
                continue  # the learner's word was read as the form already: «un cafe»
            if len(detector_spans(patterns, _without_changed_words(after, j1, j2))) >= len(corrected_spans):
                continue  # the form holds without the word: «suis très content», «très» is optional
            return True
        return False


def _cased_words(text: object, fold: bool) -> list[str]:
    found = _WORD.findall(unicodedata.normalize("NFC", str(text or "")))
    return [word.casefold() for word in found] if fold else found


def _replaces_in(trap: tuple[list[str], list[str]], pair: tuple[list[str], list[str]]) -> bool:
    """``pair`` is the trap, or the part of the trap's sentence the trap changes: the
    learner's words sit in the ✗ side where the corrected words sit in the ✓ side, and
    the rest of the two sides is the same («Lundi 3 Mars» → «lundi 3 mars» in «Le
    rendez-vous est Lundi 3 Mars.»)."""
    (wrong, right), (before, after) = trap, pair
    if not before or not after or before == after:
        return False
    for at in range(len(wrong) - len(before) + 1):
        if (
            wrong[at : at + len(before)] == before
            and right[at : at + len(after)] == after
            and wrong[:at] == right[:at]
            and wrong[at + len(before) :] == right[at + len(after) :]
        ):
            return True
    return False


def _one_word_swap(before: list[str], after: list[str]) -> tuple[str, str] | None:
    """The one word a pair changes («la votre» → «la vôtre»: votre → vôtre), else ``None``."""
    if len(before) != len(after):
        return None
    swaps = [(old, new) for old, new in zip(before, after, strict=True) if old != new]
    return swaps[0] if len(swaps) == 1 else None


def _in_context(learner_text: object, corrected_text: object, context: object) -> tuple[str, str]:
    """The learner's sentence and the same sentence corrected: a pair often quotes only
    «ou on», and the noun before it («le bar») is what makes it the relative «où»."""
    learner = unicodedata.normalize("NFC", str(learner_text or ""))
    corrected = unicodedata.normalize("NFC", str(corrected_text or ""))
    sentence = unicodedata.normalize("NFC", str(context or ""))
    if sentence and learner and len(sentence.lower()) == len(sentence):
        at = sentence.lower().find(learner.lower())
        if at >= 0:
            return sentence, sentence[:at] + corrected + sentence[at + len(learner) :]
    return learner, corrected


def _changes(before: str, after: str) -> list[tuple[int, int, int, int]]:
    """Each place ``after`` differs from ``before``: ``(i1, i2)`` in ``before`` and
    ``(j1, j2)`` in ``after`` (an empty range where a character was only added or taken
    away). Case counts: a capital is a change."""
    matcher = difflib.SequenceMatcher(a=before, b=after, autojunk=False)
    return [(i1, i2, j1, j2) for tag, i1, i2, j1, j2 in matcher.get_opcodes() if tag != "equal"]


_APOSTROPHES = frozenset("'’ʼ`´")


def _elision_only(before: str, after: str, change: tuple[int, int, int, int]) -> bool:
    i1, i2, j1, j2 = change
    written, removed = after[j1:j2], before[i1:i2]
    return bool(written) and set(written) <= _APOSTROPHES and set(removed) <= _APOSTROPHES | {" "}


def _touched_words(text: str, first: int, last: int) -> str:
    return " ".join(word.group(0) for word in _WORD.finditer(text) if _touches((word.start(), word.end()), first, last))


def _tells_words_apart(learner_words: str, corrected_words: str) -> bool:
    """A change of accent alone is a rule's form only when the accent tells two French
    words apart (ou/où, votre/vôtre, fut/fût); a capital or a space always may be
    («Lundi → lundi», «Quelque → Quel que»). «hotel → hôtel», «cafe → café» are spelling,
    even inside the rule's span («l'hôtel où», «un café»)."""
    from app.services.answer_acceptance import ACCENT_HOMOGRAPHS

    learner, corrected = learner_words.casefold(), corrected_words.casefold()
    if learner == corrected or _letters(learner) != _letters(corrected) or " " in learner + corrected:
        return True  # a capital, or a space/word boundary moved
    return learner in ACCENT_HOMOGRAPHS or corrected in ACCENT_HOMOGRAPHS


def _without_changed_words(text: str, first: int, last: int) -> str:
    """``text`` with the words the change touched taken out."""
    kept, at = [], 0
    for word in _WORD.finditer(text):
        if _touches((word.start(), word.end()), first, last):
            kept.append(text[at : word.start()])
            at = word.end()
    kept.append(text[at:])
    return "".join(kept)


def _touches(span: tuple[int, int], first: int, last: int) -> bool:
    start, end = span
    return start <= first <= end if first == last else first < end and start < last


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
    context: object = None,
    lent_form: LentForm | None = None,
) -> str | None:
    """The unit the change itself names (an external id), :data:`NO_RULE`, or ``None``.

    ``lent_unit`` is the external id of the rule the surface would file the slip under
    (the letter's, the step's, the séance's). It is kept only where the change is its
    form: a passé composé unit for a participle or an auxiliary, and for an accent, an
    apostrophe, a space or a capital, the form ``lent_form`` (the unit's detectors and
    traps) recognises on the changed characters, or a stem-change accent for «-er verbs
    that change spelling». ``context`` is the learner's text the pair was cut from,
    read for the words in front of the slip.
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
        if lent_unit and lent_form is not None and lent_form.owns(learner_text, corrected_text, context):
            return lent_unit
        return NO_RULE
    return None
