"""One corrector contract for every free-text surface (root cause #250).

Scene replies, the Courrier and the Journal each asked a model for a correction
and showed whatever came back, or a dead-end line («the corrector was
unavailable», «the correction could not be made») when it failed. Nothing
compared the correction with the sentence the learner actually wrote, and nothing
found the learner's mistakes without a model.

The flaw was structural: the corrector's output was *trusted*, and a failure had
*no value of its own* (a dead-end line, not a result). A first contract added a
grounding check and a model-free pass, but the two were still separate judges:
the check let «il est» -> «ils sont» through, and a rule could hand back French the
rules themselves would mark wrong (#318: «la appartement» -> «le appartement»).

This module now has **one checker for every edit**, whoever wrote it:

* :func:`verify_edit` — a proposed edit (span, replacement, note) is shown only
  when (1) it is about the sentence (the quoted span and any subject the note
  leans on are in it; a single swapped être/avoir/aller form is wrong for its
  subject), (2) it keeps the learner's subject, (3) every same-verb person swap
  inside it holds, and (4) the replacement *settles*: put back into the sentence,
  the rules find nothing left to fix, or they complete it («le appartement» ->
  «l'appartement»). The checks are one-sided: they reject only what they can
  prove wrong. :func:`edit_is_grounded` is its boolean view.
* :func:`deterministic_edits` — the model-free pass: person of être/avoir/aller,
  auxiliaries and agreement, elision, contraction, determiner gender and
  number, accents, apostrophes and spelling, negation order, «de» after modals, «à»,
  age with avoir, stressed pronouns, the feminine of a closed list of adjectives
  («une bon offre»). Every rule stands on closed evidence (a fixed trigger
  list, the core lexicon) and is silent when it cannot tell: «je voudrais de un
  café» could be «un café» or «d'un café», so it says nothing. Every edit is
  settled before it is returned, and its span is a substring of the input.
* :func:`merge_deterministic_errata` / :func:`first_valid_edit` /
  :func:`verify_erratum` / :func:`repair_text` — what the surfaces call: verified
  model edits plus the deterministic ones that do not overlap them, and the whole
  corrected sentence passed through the same rules. A model that fails or is
  rejected leaves the deterministic edits, never an empty «unavailable» card.

Precision is measured, not argued: ``tests/test_correction_corpus.py`` runs every
rule over all the French the app publishes (zero corrections allowed) and over
the rule cards' own mistakes (a recall floor; every fix must be part of the
card's right answer).
"""

from __future__ import annotations

import difflib
import re
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from functools import lru_cache
from typing import Any

from app.core.verdict import span_pattern
from app.services.answer_acceptance import (
    correction_is_grounded,
    is_real_correction,
    known_slip,
    person_swaps_hold,
)
from app.services.chrome_language import mother_tongue
from app.services.journey_contracts import normalize_answer_text
from app.services.spelling_variants import is_variant_edit

# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------

_WORD = re.compile(r"[^\W\d_]+(?:-[^\W\d_]+)*", re.UNICODE)
_APOSTROPHES = str.maketrans({"’": "'", "‘": "'", "ʼ": "'", "`": "'", "´": "'"})
_CLAUSE_BREAK = re.compile(r"[.!?…;:(),]")
_SENTENCE_BREAK = re.compile(r"[.!?…;]")


@dataclass(frozen=True, slots=True)
class Tok:
    low: str
    start: int
    end: int


def _norm(value: object) -> str:
    return unicodedata.normalize("NFC", "" if value is None else str(value)).translate(_APOSTROPHES)


def _tokens(text: str) -> list[Tok]:
    return [Tok(m.group(0).casefold(), m.start(), m.end()) for m in _WORD.finditer(text)]


def _joined(text: str, left: Tok, right: Tok) -> bool:
    """Whether ``right`` follows ``left`` with nothing but a space or an apostrophe."""
    return text[left.end : right.start].strip(" '’‘ʼ\u00a0") == ""


def _same_sentence(text: str, left: Tok, right: Tok) -> bool:
    return not _SENTENCE_BREAK.search(text[left.end : right.start])


def _same_clause(text: str, left: Tok, right: Tok) -> bool:
    return not _CLAUSE_BREAK.search(text[left.end : right.start])


def _starts_sentence(text: str, tok: Tok) -> bool:
    """Whether ``tok`` is the first word of the text, of a line or of a sentence."""
    before = text[: tok.start].rstrip("  «»\"“”„‘'(")
    return not before or before[-1] in ".!?…:;\n"


_QUOTE = re.compile(r"«[^»]*»|“[^”]*”|„[^“”]*[“”]|\"[^\"]*\"|‘[^’]*’|(?<!\w)'[^']*'(?!\w)")
#: A quote this short cites a word or two. A longer one is someone's speech, and is corrected.
_CITATION_WORDS = 6


def _cited_stretches(text: str) -> list[tuple[int, int]]:
    """The stretches of ``text`` where a learner cites words instead of using them: «On ne dit
    pas « ce est »», «le mot "hotel"». A line that is all one quote is the line itself."""
    stretches = []
    for match in _QUOTE.finditer(text):
        if len(_WORD.findall(match.group())) > _CITATION_WORDS or match.group() == text.strip():
            continue
        stretches.append(match.span())
    return stretches


#: Words no French sentence holds, and the phrases that say the next word isn't French.
_OTHER_LANGUAGE_WORDS = frozenset(
    {"the", "and", "is", "this", "that", "with", "you", "your", "my", "like", "ich", "ist", "das", "und", "nicht", "ein",
     "eine", "mit", "auf", "deutsch", "englisch", "english", "german", "heißt"}
)
_OTHER_LANGUAGE_PHRASES = frozenset({("en", "anglais"), ("en", "allemand"), ("mot", "anglais"), ("mot", "allemand")})


def _in_another_language(text: str, tokens: list[Tok], index: int) -> bool:
    """Whether the sentence around ``tokens[index]`` is not French, or says its word isn't."""
    start = index
    while start > 0 and _same_sentence(text, tokens[start - 1], tokens[start]):
        start -= 1
    end = index
    while end + 1 < len(tokens) and _same_sentence(text, tokens[end], tokens[end + 1]):
        end += 1
    words = [tok.low for tok in tokens[start : end + 1]]
    return bool(_OTHER_LANGUAGE_WORDS & set(words)) or bool(_OTHER_LANGUAGE_PHRASES & set(zip(words, words[1:], strict=False)))


# ---------------------------------------------------------------------------
# Persons
# ---------------------------------------------------------------------------

_PERSON_FORMS: dict[str, dict[str, str]] = {
    # lemma -> person -> form
    "être": {"1sg": "suis", "2sg": "es", "3sg": "est", "1pl": "sommes", "2pl": "êtes", "3pl": "sont"},
    "avoir": {"1sg": "ai", "2sg": "as", "3sg": "a", "1pl": "avons", "2pl": "avez", "3pl": "ont"},
    "aller": {"1sg": "vais", "2sg": "vas", "3sg": "va", "1pl": "allons", "2pl": "allez", "3pl": "vont"},
}
_FORM_LEMMA: dict[str, str] = {
    form: lemma for lemma, table in _PERSON_FORMS.items() for form in table.values()
}
_FORM_PERSONS: dict[str, frozenset[str]] = {}
for _lemma, _table in _PERSON_FORMS.items():
    for _person, _form in _table.items():
        _FORM_PERSONS[_form] = _FORM_PERSONS.get(_form, frozenset()) | {_person}

_SUBJECT_PRONOUNS: dict[str, str] = {
    "je": "1sg",
    "tu": "2sg",
    "il": "3sg",
    "elle": "3sg",
    "on": "3sg",
    "ils": "3pl",
    "elles": "3pl",
}
#: «nous» and «vous» are objects as often as subjects («je vous est…»). They read
#: as a subject only when no subject pronoun or object clitic stands in front.
_CLITIC_CONTEXT = frozenset(
    {"je", "j", "tu", "il", "elle", "on", "ils", "elles", "ne", "n", "me", "m", "te", "t", "se", "s",
     "lui", "leur", "le", "la", "l", "les", "y", "en", "qui", "nous", "vous"}
)
_PREPOSITIONS = frozenset(
    {"pour", "avec", "chez", "à", "de", "d", "sans", "sur", "sous", "par", "contre", "comme", "entre", "vers"}
)
_BETWEEN = frozenset({"ne", "n", "toujours", "déjà", "aussi", "vraiment", "bien", "jamais", "pas"})
_CONJUNCTIONS = frozenset({"et", "mais", "ou", "donc", "puis", "alors"})
#: A person's subject marker: a first/second-person form needs its pronoun somewhere.
_PERSON_MARKERS: dict[str, frozenset[str]] = {
    "1sg": frozenset({"je", "j", "moi"}),
    "2sg": frozenset({"tu", "toi", "t"}),
    "1pl": frozenset({"nous", "moi"}),
    "2pl": frozenset({"vous", "toi", "tu"}),
}
#: «after 'tu'», "with « vous »", «nach tu», «avec je»: a note hanging its rule on a subject.
_CITED_SUBJECT = re.compile(
    r"\b(?:after|with|following|nach|mit|avec|apr[eè]s|derri[eè]re)\s+[«'‘’\"“]?\s*"
    r"(je|j|tu|il|elle|on|nous|vous|ils|elles)\b",
    re.IGNORECASE,
)
_CITED_EQUIVALENTS: dict[str, frozenset[str]] = {
    "je": frozenset({"je", "j", "moi"}),
    "j": frozenset({"je", "j", "moi"}),
    "tu": frozenset({"tu", "toi", "t"}),
}


def _subject_person(tokens: list[Tok], text: str, index: int) -> str | None:
    """Who the subject right before ``tokens[index]`` is, or ``None`` when the
    sentence does not say. Only a subject read with confidence may prove a form
    right or wrong."""

    i = index - 1
    while i >= 0 and tokens[i].low in _BETWEEN and _same_clause(text, tokens[i], tokens[i + 1]):
        i -= 1
    if i < 0 or not _same_clause(text, tokens[i], tokens[i + 1]):
        return None
    word = tokens[i].low
    before = tokens[i - 1] if i > 0 and _same_clause(text, tokens[i - 1], tokens[i]) else None
    if word in {"nous", "vous"}:
        # «Marie nous a invités», «Le chef vous a appelé»: after a noun «nous/vous»
        # is an object. The model-free pass reads them as the subject only where
        # nothing else can be: at the start of the clause, or after a conjunction.
        if before is not None and before.low not in _CONJUNCTIONS:
            return None
        return "1pl" if word == "nous" else "2pl"
    person = _SUBJECT_PRONOUNS.get(word)
    if person is None:
        return None
    if before is not None and (before.low in {"et", "ni", "ou"} or before.low in _PREPOSITIONS):
        return None  # «Marie et elle sont», «pour elle est…»
    return person


def _markers_present(person: str, words: set[str]) -> bool:
    wanted = _PERSON_MARKERS.get(person)
    return True if wanted is None else bool(wanted & words)


# ---------------------------------------------------------------------------
# The contract: is a model edit about this sentence?
# ---------------------------------------------------------------------------


def _find_span(tokens: list[Tok], span_words: list[str]) -> list[int]:
    """Start indexes where ``span_words`` stand in ``tokens``."""
    if not span_words:
        return []
    low = [t.low for t in tokens]
    return [
        i for i in range(len(low) - len(span_words) + 1) if low[i : i + len(span_words)] == span_words
    ]


def _words_of(value: object) -> list[str]:
    return [m.group(0).casefold() for m in _WORD.finditer(_norm(value))]


def edit_is_grounded(
    text: object,
    span: object,
    replacement: object,
    note: object = None,
    *,
    strict_span: bool = True,
) -> bool:
    """Whether a proposed edit passes :func:`verify_edit` (the boolean view)."""
    return verify_edit(text, span, replacement, note, strict_span=strict_span).ok


@dataclass(frozen=True, slots=True)
class Verdict:
    """What :func:`verify_edit` decided about one proposed edit. ``replacement`` is
    the one to show: the proposal itself, or the proposal completed by the rules
    («le appartement» -> «l'appartement»). ``span`` is the learner's words it
    replaces: the quoted span, or a wider one when the rules folded a neighbouring
    word in (a model's «la» -> «le» before «appartement» is shown as «la
    appartement» -> «l'appartement», never «la» -> «l»)."""

    ok: bool
    replacement: str | None = None
    reason: str = ""
    span: str | None = None


#: Subject pronouns that may stand in for each other in a correction: the same person
#: and number (gender, register, elision). Anything else rewrites who acts.
_SUBJECT_WORDS = frozenset({"je", "j", "tu", "il", "elle", "on", "nous", "vous", "ils", "elles"})
_SAME_SUBJECT = (
    frozenset({"je", "j"}),
    frozenset({"tu", "vous"}),
    frozenset({"il", "elle"}),
    frozenset({"ils", "elles"}),
    frozenset({"on", "nous"}),
)


def changes_subject(span: object, replacement: object) -> bool:
    """Whether the edit swaps the learner's subject for another person or number
    («il est» -> «ils sont»). The learner chose who acts: a fix agrees the verb with
    that subject, it never picks a new one (like the learner's own gender, #93)."""

    old, new = _words_of(span), _words_of(replacement)
    matcher = difflib.SequenceMatcher(a=old, b=new, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag != "replace":
            continue
        olds = [w for w in old[i1:i2] if w in _SUBJECT_WORDS]
        news = [w for w in new[j1:j2] if w in _SUBJECT_WORDS]
        for a, b in zip(olds, news, strict=False):
            if a != b and not any(a in group and b in group for group in _SAME_SUBJECT):
                return True
    return False


def verify_edit(
    text: object,
    span: object,
    replacement: object,
    note: object = None,
    *,
    strict_span: bool = True,
    people: Mapping[str, str] | None = None,
) -> Verdict:
    """The one check every proposed correction passes before a learner sees it,
    whether a model or a rule wrote it (#250).

    1. it is about the sentence (:func:`_grounded`: span, cited subject, a single
       être/avoir/aller swap);
    2. it keeps the learner's subject (:func:`changes_subject`);
    3. every same-verb person swap inside it holds for its subject
       (``answer_acceptance.person_swaps_hold``: «il est vielle» -> «sont vieilles»
       does not);
    4. the corrected sentence is French the rules accept: the replacement is put
       back and settled, so «le appartement» reaches the learner as
       «l'appartement», and a fix that does not settle is dropped.
    """

    if is_variant_edit(span, replacement):
        return Verdict(False, reason="valid_variant")
    if not _grounded(text, span, replacement, note, strict_span=strict_span):
        return Verdict(False, reason="not_grounded")
    if changes_subject(span, replacement):
        return Verdict(False, reason="changes_subject")
    if not person_swaps_hold(text, span, replacement):
        return Verdict(False, reason="person_swap")
    settled = _settled(text, span, replacement, people)
    if settled is None:
        return Verdict(False, reason="does_not_settle")
    shown_span, shown = settled
    if is_variant_edit(shown_span, shown):
        return Verdict(False, reason="valid_variant")
    return Verdict(True, replacement=shown, span=shown_span)


def _locate(source: str, span: str) -> tuple[int, int] | None:
    at = source.find(span)
    if at >= 0:
        return at, at + len(span)
    folded_source, folded_span = _norm(source).casefold(), _norm(span).casefold()
    at = folded_source.find(folded_span)
    if at >= 0 and len(folded_source) == len(source):
        return at, at + len(span)
    return None


def _anchor(source: str, quoted: str) -> tuple[int, int] | None:
    """Where the learner wrote the words a near-quote stands for, or ``None``.

    The stretch has as many words as the quote, each the same word or a form of it
    (``_same_word``) or both grammar words (an article, a pronoun), and at least one
    word written exactly as quoted. The stretch with the most exact words wins, then
    the first. A quote that matches no stretch is about words the learner did not
    write, and has nothing to correct.
    """

    tokens = _tokens(source)
    wanted = _words_of(quoted)
    n = len(wanted)
    if not n or n > len(tokens):
        return None
    best: tuple[int, int] | None = None
    best_exact = 0
    for i in range(len(tokens) - n + 1):
        window = tokens[i : i + n]
        exact = 0
        for tok, word in zip(window, wanted, strict=True):
            if tok.low == word:
                exact += 1
            elif not (
                _same_word(tok.low, word)
                or (_strip_marks(tok.low) in _GRAMMAR_WORDS and _strip_marks(word) in _GRAMMAR_WORDS)
            ):
                break
        else:
            if (exact or n == 1) and (best is None or exact > best_exact):
                best, best_exact = (window[0].start, window[-1].end), exact
    return best


def _settled(
    text: object, span: object, replacement: object, people: Mapping[str, str] | None
) -> tuple[str, str] | None:
    """``(span, replacement)`` once the proposal settles in the sentence, or ``None``.
    The span is the learner's words the replacement stands for: the quoted span, or
    the wider one the rules folded a neighbouring word into («la» + «appartement»)."""
    source = "" if text is None else str(text)
    quoted = "" if span is None else str(span)
    proposed = "" if replacement is None else str(replacement)
    cast = known_people() if people is None else {k.casefold(): v for k, v in people.items()}
    where = _locate(source, quoted)
    if where is None:
        # A near-quote (the Courrier's «un photo» for the learner's «une photo», the
        # Forge's «un grand réunion» for «une grand réunion», #772): the span shown is
        # always the learner's own stretch, never the model's paraphrase of it (#250).
        where = _anchor(source, quoted)
        if where is None:
            return None
    start, end = where
    probe = Edit(span=source[start:end], replacement=proposed, rule_id="MODEL", label={}, note={}, start=start, end=end)
    final = _settle(source, probe, cast)
    if final is None:
        return None
    return final.span, final.replacement


def _grounded(
    text: object,
    span: object,
    replacement: object,
    note: object = None,
    *,
    strict_span: bool = True,
) -> bool:
    """Whether a proposed edit is about the sentence the learner wrote.

    ``strict_span=False`` skips the «span is in the sentence» test for surfaces
    that already match near-quotes (the Courrier accepts «une photo» for «un
    photo»); every other test still applies.
    """

    source = "" if text is None else str(text)
    tokens = _tokens(source)
    span_words = _words_of(span)
    new_words = _words_of(replacement)
    if _norm(span).split() == _norm(replacement).split() and span_words:
        return False  # a «correction» that reprints the learner's words
    if not is_real_correction(span, replacement):
        # #93/#174: a right sentence re-punctuated, or one right form swapped for
        # another («Vous êtes … ?» -> «Êtes-vous … ?»), is not an error.
        return False
    places = _find_span(tokens, span_words)
    if places:
        # #193 / #248: the one grounding every surface shares (span, cited subject,
        # and a swapped être/avoir/aller form checked against the subject in front
        # of it, object pronouns included: «Je lui a» -> «ai» stays a fix).
        return correction_is_grounded(source, span, replacement, note)
    if strict_span:
        return False
    # Near-quote (the Courrier accepts «une photo» for «un photo»): the cited subject
    # and a person swap are judged against the whole sentence.
    present = {t.low for t in tokens}
    for match in _CITED_SUBJECT.finditer(_norm(note)):
        cited = match.group(1).casefold()
        if not (_CITED_EQUIVALENTS.get(cited, frozenset({cited})) & present):
            return False
    if len(span_words) != len(new_words):
        return True
    changed = [i for i, (a, b) in enumerate(zip(span_words, new_words, strict=True)) if a != b]
    if len(changed) != 1:
        return True
    old, new = span_words[changed[0]], new_words[changed[0]]
    if _FORM_PERSONS.get(old) is None or (new_persons := _FORM_PERSONS.get(new)) is None:
        return True
    return all(_markers_present(p, present) or p in {"3sg", "3pl"} for p in new_persons)


# ---------------------------------------------------------------------------
# The note is checked against the form it explains (#369)
# ---------------------------------------------------------------------------
#
# Why this was possible: the model writes two things, the corrected form and a
# sentence about it, and only the form was ever checked. «aujourdhui» ->
# «aujourd'hui» was shown with «an accent on « hui »»: the form was right, the
# explanation named a character the form does not have. A note is a *claim about
# characters*; the characters are right there in the (span, replacement) pair, so
# the claim can be checked without a model. A note whose claim the pair does not
# bear out is replaced by one derived from the pair itself.

_ACCENT_CLAIM = re.compile(
    r"accent|aigu|circonflex|tr[ée]ma|c[ée]dill|diacrit|umlaut|di(?:a)?eresis|"
    r"akzent|zirkumflex",
    re.IGNORECASE,
)
_APOSTROPHE_CLAIM = re.compile(r"apostroph", re.IGNORECASE)
_QUOTED = re.compile(r"«\s*([^»]+?)\s*»|“\s*([^”]+?)\s*”|\"([^\"]+)\"")

_MARK_NAMES: dict[str, dict[str, str]] = {
    "́": {"en": "acute accent", "fr": "accent aigu", "de": "Akut"},
    "̀": {"en": "grave accent", "fr": "accent grave", "de": "Gravis"},
    "̂": {"en": "circumflex", "fr": "accent circonflexe", "de": "Zirkumflex"},
    "̈": {"en": "diaeresis", "fr": "tréma", "de": "Trema"},
    "̧": {"en": "cedilla", "fr": "cédille", "de": "Cedille"},
}


def _marked_letters(value: object) -> list[str]:
    """The letters of ``value`` that carry a diacritic (NFC form, reading order)."""
    out: list[str] = []
    for char in _norm(value):
        decomposed = unicodedata.normalize("NFD", char)
        if len(decomposed) > 1 and any(unicodedata.combining(c) for c in decomposed[1:]):
            out.append(char.casefold())
    return out


def _strip_marks(value: object) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", _norm(value)) if not unicodedata.combining(c))


def _base_letters(value: object) -> set[str]:
    return {c.casefold() for c in _strip_marks(value) if c.isalpha()}


def _quoted_fragments(note: str) -> list[str]:
    return [next(g for g in m.groups() if g) for m in _QUOTED.finditer(note)]


def _changed_marked_letters(span: str, replacement: str) -> list[str]:
    """Diacritic letters the replacement has more of than the span."""
    old = _marked_letters(span)
    out: list[str] = []
    for letter in _marked_letters(replacement):
        if letter in old:
            old.remove(letter)
        else:
            out.append(letter)
    return out


def note_matches_form(span: object, replacement: object, note: object) -> bool:
    """Whether a note's claims about characters are true of the (span, replacement) pair.

    One-sided, like :func:`edit_is_grounded`: it rejects only a claim it can prove
    false (an accent where no diacritic changes, an apostrophe where none changes,
    a quoted accented letter in neither form, an accent «on « hui »» when the
    letters it names have no diacritic in the corrected form). A note that makes no
    claim about characters always passes.
    """
    text = _norm(note).strip()
    old, new = _norm(span), _norm(replacement)
    if not text or not new:
        return True
    quoted = _quoted_fragments(text)
    # A quoted accented letter («ç») must be in one of the two forms.
    for fragment in quoted:
        fragment_marks = _marked_letters(fragment)
        if len(fragment.strip()) == 1 and fragment_marks:
            if fragment_marks[0] not in _marked_letters(new) + _marked_letters(old):
                return False
    if _ACCENT_CLAIM.search(text):
        added = _changed_marked_letters(old, new)
        removed = _changed_marked_letters(new, old)
        changed = added or removed
        if not changed:
            return False  # no diacritic is added, removed or swapped
        # «an accent on « hui »»: the words the note points at must contain a letter
        # that really changed. A quoted fragment is a pointer, never a new fact.
        pointed = [f for f in quoted if _base_letters(f)]
        if pointed:
            needed = {b for letter in changed for b in _base_letters(letter)} | set(changed)
            if not any((_base_letters(f) & needed) or (set(f.casefold()) & set(changed)) for f in pointed):
                return False
    if _APOSTROPHE_CLAIM.search(text) and old.count("'") == new.count("'"):
        return False
    return True


_FORM_NOTES: dict[str, dict[str, str]] = {
    "apostrophe_added": {
        "en": "An apostrophe is missing: « {new} ».",
        "fr": "Il manque une apostrophe : « {new} ».",
        "de": "Es fehlt ein Apostroph: « {new} ».",
    },
    "apostrophe_removed": {
        "en": "No apostrophe here: « {new} ».",
        "fr": "Pas d'apostrophe ici : « {new} ».",
        "de": "Hier steht kein Apostroph: « {new} ».",
    },
    "accent": {
        "en": "Spelling: the {mark} on « {letter} » — « {new} ».",
        "fr": "Orthographe : {mark} sur « {letter} » — « {new} ».",
        "de": "Schreibung: {mark} auf « {letter} » — « {new} ».",
    },
    "hyphen": {
        "en": "Hyphen: « {new} ».",
        "fr": "Trait d'union : « {new} ».",
        "de": "Bindestrich: « {new} ».",
    },
    "form": {
        "en": "The correct form is « {new} ».",
        "fr": "La forme correcte est « {new} ».",
        "de": "Die richtige Form ist « {new} ».",
    },
}


def _mark_of(letter: str) -> str | None:
    for part in unicodedata.normalize("NFD", letter)[1:]:
        if part in _MARK_NAMES:
            return part
    return None


def note_from_form(span: object, replacement: object, *, language: str | None = None) -> str:
    """A note written from the (span, replacement) pair alone, true by construction."""
    old, new = _norm(span).strip(), _norm(replacement).strip()
    fills = {"new": new, "old": old}
    if old.replace("'", "").casefold() == new.replace("'", "").casefold() and old.count("'") != new.count("'"):
        kind = "apostrophe_added" if new.count("'") > old.count("'") else "apostrophe_removed"
        return _pick(_FORM_NOTES[kind], language).format(**fills)
    added = _changed_marked_letters(old, new)
    if added and _strip_marks(old).casefold() == _strip_marks(new).casefold():
        letter = added[0]
        mark = _mark_of(letter)
        if mark is not None:
            return _pick(_FORM_NOTES["accent"], language).format(
                mark=_pick(_MARK_NAMES[mark], language), letter=letter, **fills
            )
    if old.count("-") != new.count("-") and old.replace("-", " ").casefold() == new.replace("-", " ").casefold():
        return _pick(_FORM_NOTES["hyphen"], language).format(**fills)
    return _pick(_FORM_NOTES["form"], language).format(**fills)


def _folded(value: object) -> str:
    """Text as a quote is compared: NFC, one apostrophe, case and spacing folded."""
    return " ".join(_norm(value).casefold().split())


_GUILLEMETS = re.compile(r"«\s*([^»]+?)\s*»")
_DOUBLE_QUOTED = re.compile(r"“\s*([^”]+?)\s*”|\"([^\"]+)\"")


def _quote_body(fragment: str) -> str:
    return _folded(fragment).strip(_EDGE_MARKS + " ")


def note_quotes_hold(note: object, span: object, replacement: object, context: object) -> bool:
    """Whether every French stretch a note quotes is one the learner wrote or the fix writes (#250, #772).

    A note quotes to point: «You wrote « un grand réunion »» must point at words in
    ``context`` (the learner's text), in that text once the fix is made, or in the
    fix itself. A quoted ending («-x», «-e») or a single word that is a form of a word
    there («être» for «est») is a pointer too. Anything else is the model describing
    a sentence the learner did not write («With « tu », …» when nobody is «tu», #193).
    Without ``context`` nothing is claimed false.
    """

    text = _norm(note)
    if not text.strip() or context is None or not str(context).strip():
        return True
    source = _norm(context)
    old, new = _norm(span), _norm(replacement)
    fixed = source.replace(old, new, 1) if old and old in source else source
    places = [_words_of(place) for place in (source, fixed, new, old)]
    words = {w for place in places for w in place}
    fragments = [(match.group(1), True) for match in _GUILLEMETS.finditer(text)]
    fragments += [(match.group(1) or match.group(2), False) for match in _DOUBLE_QUOTED.finditer(text)]
    for fragment, french in fragments:
        body = _quote_body(fragment)
        quoted = _words_of(body)
        if not quoted or body.startswith("-"):
            continue  # a mark, a number or an ending («-x»)
        if not french and not all(_is_grammar_word(w) or _verb_lemma(w) for w in quoted):
            continue  # a double-quoted English gloss («means "meeting"»), not French
        n = len(quoted)
        if any(place[i : i + n] == quoted for place in places for i in range(len(place) - n + 1)):
            continue
        if n == 1 and any((_lemmas(quoted[0]) | {quoted[0]}) & (_lemmas(w) | {w}) for w in words):
            continue  # «être» for «est»: the word's own family
        return False
    return True


#: A note that says a noun stays singular, or takes no plural ending.
_NO_PLURAL_CLAIM = re.compile(
    r"\bsingular\b|\bno plural\b|\btakes? no (?:plural )?-?s\b|\bsingulier\b|\bpas de pluriel\b|"
    r"\bsans -?s\b|\bSingular\b|\bkein(?:e|en)? Plural\b|\bohne -?s\b",
    re.IGNORECASE,
)


def _adds_plural(span: str, replacement: str) -> bool:
    """Whether the fix turns a word of the span into its plural («serviette» -> «serviettes»)."""

    old = set(_words_of(span))
    return any(w[-1:] in {"s", "x"} and w[:-1] in old and w not in old for w in _words_of(replacement))


def note_for_form(
    span: object, replacement: object, note: object, *, language: str | None = None, context: object = None
) -> str:
    """``note`` when the pair (and the learner's ``context``) bear out what it says,
    else a note written from the pair."""
    text = "" if note is None else str(note)
    if not text.strip():
        return text
    holds = note_matches_form(span, replacement, text) and note_quotes_hold(text, span, replacement, context)
    if holds and _NO_PLURAL_CLAIM.search(text) and _adds_plural(_norm(span), _norm(replacement)):
        holds = False  # #662: «singular nouns take no plural -s» over a fix that adds one
    if holds:
        return text
    return note_from_form(span, replacement, language=language)


def reconcile_notes(
    erratum: Mapping[str, Any], *, language: str | None = None, context: object = None
) -> dict[str, Any]:
    """The erratum with every explanation held to its own (learner_text, corrected_target),
    and, given the learner's ``context``, quoting only words that are there or in the fix.

    When the explanation is rewritten the hint is dropped: both came from the same
    reading of the sentence, and that reading was wrong (#772: «Change the article»
    for an article the learner wrote right)."""
    out = dict(erratum)
    why = out.get("why_wrong")
    if why:
        out["why_wrong"] = note_for_form(
            out.get("learner_text"), out.get("corrected_target"), why, language=language, context=context
        )
    hint = out.get("repair_hint")
    if hint:
        if why and out["why_wrong"] != why:
            out["repair_hint"] = ""
        else:
            out["repair_hint"] = note_for_form(
                out.get("learner_text"), out.get("corrected_target"), hint, language=language, context=context
            )
    return out


# ---------------------------------------------------------------------------
# Deterministic edits
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Edit:
    """One correction: ``span`` is a substring of the learner's text."""

    span: str
    replacement: str
    rule_id: str
    label: dict[str, str]
    note: dict[str, str]
    start: int = 0
    end: int = 0
    task_error_type: str = "grammar_target"
    severity: int = 2

    def note_for(self, language: str | None) -> str:
        return _pick(self.note, language)

    def label_for(self, language: str | None) -> str:
        return _pick(self.label, language)


def _pick(table: Mapping[str, str], language: str | None) -> str:
    key = mother_tongue(language)
    return table.get(key) or table.get("en") or next(iter(table.values()), "")


def _case(original: str, replacement: str) -> str:
    if original.isupper() and len(original) > 1:
        return replacement.upper()
    if original[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


_ETRE_PARTICIPLES = frozenset(
    {"allé", "venu", "arrivé", "parti", "entré", "resté", "tombé", "devenu", "revenu", "né", "mort",
     "rentré", "sorti", "monté", "descendu", "retourné"}
)
#: These take «avoir» with a direct object («a rentré la voiture», «a sorti son
#: téléphone»). They are flagged only when a place or time word follows.
#: «entré» too: «J'ai entré mon mot de passe» is French.
_AMBIGUOUS_PARTICIPLES = frozenset({"rentré", "sorti", "monté", "descendu", "retourné", "entré"})
#: A direct object before the auxiliary makes those verbs transitive: «Je l'ai sorti.»
_OBJECT_CLITICS = frozenset({"l", "le", "la", "les", "en", "m", "me", "t", "te"})
#: Night-shift review of #259: only a word after which no direct object can stand.
#: Determiners («ce», «tout», «du», «de»), «en», «par», «sur» and conjunctions start
#: objects («Elle a sorti cette lettre», «Il a sorti du pain») and are not here.
_PLACE_WORDS = frozenset({"dans", "à", "au", "aux", "chez", "vers", "hier", "tard", "tôt", "enfin"})
_AVOIR_TO_ETRE = {"a": "est", "as": "es", "ai": "suis", "avons": "sommes", "avez": "êtes", "ont": "sont"}
_PRESENT_MARKERS = frozenset(
    {"maintenant", "aujourd'hui", "aujourd", "toujours", "souvent", "chaque", "demain", "d'habitude",
     "habituellement", "généralement", "tous", "toutes", "encore", "actuellement", "désormais", "depuis",
     "moment"}
)
_PAST_MARKERS = frozenset({"hier", "avant-hier", "dernier", "dernière", "veille", "autrefois"})
_SUBORDINATORS = frozenset({"que", "qu", "qui", "si", "quand", "lorsque", "lorsqu", "parce", "comme", "où"})
#: A state or a habit holds now as well («… et elle aime le café», «… et il habite à
#: Lyon»): never a tense slip.
_STATE_VERBS = frozenset(
    {"aimer", "adorer", "détester", "préférer", "penser", "trouver", "sembler", "espérer", "habiter",
     "travailler", "parler", "porter", "ressembler", "coûter", "peser", "mesurer", "compter", "rêver",
     "exister", "durer", "posséder", "désirer", "souhaiter", "apprécier", "ignorer", "manquer",
     "étudier", "jouer", "chanter", "danser", "cuisiner", "garder", "rester", "continuer"}
)
_PC_PARTICIPLES = frozenset(
    {"eu", "fait", "dit", "pris", "mis", "vu", "su", "pu", "voulu", "dû", "bu", "lu", "écrit", "ouvert",
     "offert", "reçu", "vécu", "connu", "cru", "perdu", "vendu", "rendu", "attendu", "entendu", "répondu",
     "appris", "compris", "été"}
)

_DRE_FIRST_PERSON = {
    "vend": "vends", "rend": "rends", "attend": "attends", "entend": "entends", "descend": "descends",
    "perd": "perds", "répond": "réponds", "prend": "prends", "apprend": "apprends",
    "comprend": "comprends", "surprend": "surprends", "défend": "défends", "étend": "étends",
    "dépend": "dépends", "confond": "confonds", "mord": "mords",
}
_ACCENTS = {
    "apres": "après", "deja": "déjà", "tres": "très", "ecole": "école", "cafe": "café", "ete": "été",
    "etre": "être", "francais": "français", "meme": "même", "pere": "père", "mere": "mère",
    "frere": "frère", "voila": "voilà", "ca": "ça", "etait": "était", "hopital": "hôpital",
    "theatre": "théâtre", "gateau": "gâteau", "plait": "plaît", "etes": "êtes", "cheminee": "cheminée",
    "etudiant": "étudiant", "etudiante": "étudiante", "arrivee": "arrivée", "journee": "journée",
    "soiree": "soirée", "idee": "idée", "annee": "année", "equipe": "équipe", "eglise": "église",
}
#: Night-shift review of #259: a noun that is right with either gender, so its
#: determiner is never «corrected». Homographs whose meaning sets the gender («le
#: tour / la tour», «le poste / la poste»), and person nouns French uses for a woman
#: too while the core lexicon stores one gender («une enfant», «la ministre»).
_TWO_GENDER_NOUNS = frozenset(
    {
        # homographs
        "tour", "poste", "livre", "mode", "page", "voile", "manche", "critique", "vase", "mémoire",
        "moule", "somme", "solde", "aide", "physique", "pendule", "office", "œuvre", "espace", "gens",
        "mousse", "manœuvre", "parallèle", "finale", "geste", "mort", "après-midi", "foudre", "hymne",
        "crêpe", "garde", "merci", "pupille", "enseigne", "greffe", "radio", "relâche", "orge", "période",
        "faux", "physionomie", "interligne", "chose", "personne", "crème", "porte-parole",
        # person nouns used for women and men
        "enfant", "propriétaire", "ministre", "juge", "membre", "stagiaire", "guide", "médecin",
        "professeur", "prof", "peintre", "poète", "auteur", "écrivain", "chef", "témoin", "maire",
        "docteur", "ingénieur", "pompier", "auteure", "élève", "artiste", "journaliste", "collègue",
        "touriste", "camarade", "secrétaire", "libraire", "concierge", "dentiste", "adulte", "malade",
        "architecte", "pianiste", "photographe", "interprète", "pilote", "bibliothécaire", "locataire",
        "fonctionnaire", "responsable", "célibataire", "partenaire", "astronaute", "comptable", "fleuriste",
        "bénévole", "complice", "convive", "cadre", "mannequin", "bébé", "star", "vedette",
    }
)
_MASC_DET = {"le": "la", "un": "une", "ce": "cette", "mon": "ma", "ton": "ta", "son": "sa", "quel": "quelle"}
_FEM_DET = {"la": "le", "une": "un", "cette": "ce", "ma": "mon", "ta": "ton", "sa": "son", "quelle": "quel"}
#: «je la porte», «il le mange»: in front of a verb form that is also a noun, «le/la» is
#: a pronoun, not a determiner, and says nothing about the noun's gender.
_PRONOUN_CONTEXT = frozenset(
    {"je", "j", "tu", "il", "elle", "on", "nous", "vous", "ils", "elles", "me", "m", "te", "t", "se", "s",
     "ne", "n", "y", "en", "lui", "leur", "qui",
     # «sans que personne le remarque», «rien la arrête», «ça le fait rire»
     "personne", "rien", "chacun", "chacune", "ça", "cela", "ceci"}
)


@lru_cache(maxsize=1)
def _lexicon():  # pragma: no cover - thin cache
    from app.services.lexical_coverage import load_lexicon

    return load_lexicon()


@lru_cache(maxsize=4096)
def _lemma(word: str) -> dict[str, Any] | None:
    try:
        return _lexicon().lemmas.get(word)
    except Exception:  # pragma: no cover - the lexicon is optional context
        return None


def _is_verb(infinitive: str) -> bool:
    entry = _lemma(infinitive)
    return bool(entry and entry.get("pos") == "verb")


def _names_a_subject(text: str, tok: Tok) -> bool:
    """A name or a noun right before «le/la» is the subject of a verb that follows
    («Lila le porte», «le chat la regarde»), so the «le/la» is a pronoun."""
    original = text[tok.start : tok.end]
    starts_sentence = not text[: tok.start].strip() or bool(_SENTENCE_BREAK.search(text[: tok.start].rstrip()[-1:]))
    if original[:1].isupper() and (not starts_sentence or tok.low in _cast_first_names() or _lemma(tok.low) is None):
        return True  # a name (mid-sentence, a cast member, or no French word)
    return _noun_gender(tok.low) is not None


def _noun_gender(word: str) -> str | None:
    entry = _lemma(word)
    if not entry or entry.get("pos") != "noun":
        return None
    gender = entry.get("gender")
    return gender if gender in {"m", "f"} else None


@lru_cache(maxsize=1)
def _cast_first_names() -> frozenset[str]:
    return frozenset(known_people())


def known_people() -> dict[str, str]:
    """First names of the cast -> ``"f"`` / ``"m"``. A person whose gender the
    learner picks («x») is left out: nothing is imposed on them."""
    try:
        from app.services import cast_registry

        out: dict[str, str] = {}
        for member in cast_registry.all_members().values():
            gender = getattr(member, "gender", "x")
            first = str(getattr(member, "name", "") or "").split(" ")[0].strip().casefold()
            if first and gender in {"f", "m"}:
                out[first] = gender
        return out
    except Exception:  # pragma: no cover - the cast is optional context
        return {}


_RULE_TEXT: dict[str, dict[str, dict[str, str]]] = {
    "FR_PERSON_AUX": {
        "label": {"en": "Verb form", "de": "Verbform", "fr": "Forme du verbe"},
        "note": {
            "en": "After « {subject} » the verb is « {right} », not « {wrong} ».",
            "de": "Nach « {subject} » heißt es « {right} », nicht « {wrong} ».",
            "fr": "Après « {subject} », on écrit « {right} » et non « {wrong} ».",
        },
    },
    "FR_AUX_ETRE": {
        "label": {"en": "Auxiliary", "de": "Hilfsverb", "fr": "Auxiliaire"},
        "note": {
            "en": "« {part} » forms its passé composé with être: « {right} », not « {wrong} ».",
            "de": "« {part} » bildet das Perfekt mit être: « {right} », nicht « {wrong} ».",
            "fr": "« {part} » se conjugue avec être au passé composé : « {right} » et non « {wrong} ».",
        },
    },
    "FR_PARTICIPLE_AGREE": {
        "label": {"en": "Agreement", "de": "Angleichung", "fr": "Accord"},
        "note": {
            "en": "With être the participle agrees with the subject: « {right} ».",
            "de": "Mit être richtet sich das Partizip nach dem Subjekt: « {right} ».",
            "fr": "Avec être, le participe s’accorde avec le sujet : « {right} ».",
        },
    },
    "FR_ADJ_AGREE": {
        "label": {"en": "Agreement", "de": "Angleichung", "fr": "Accord"},
        "note": {
            "en": "« {noun} » is feminine, so the adjective is too: « {right} », not « {wrong} ».",
            "de": "« {noun} » ist feminin, also auch das Adjektiv: « {right} », nicht « {wrong} ».",
            "fr": "« {noun} » est féminin, l’adjectif aussi : « {right} » et non « {wrong} ».",
        },
    },
    "FR_ALLER_INF": {
        "label": {"en": "Verb form", "de": "Verbform", "fr": "Forme du verbe"},
        "note": {
            "en": "After aller (near future) the verb stays in the infinitive: « {right} », not « {wrong} ».",
            "de": "Nach aller (nahe Zukunft) steht der Infinitiv: « {right} », nicht « {wrong} ».",
            "fr": "Après aller (futur proche), le verbe reste à l’infinitif : « {right} » et non « {wrong} ».",
        },
    },
    "FR_VERB_DRE_S": {
        "label": {"en": "Verb ending", "de": "Verbendung", "fr": "Terminaison du verbe"},
        "note": {
            "en": "With « {subject} » this verb ends in -s: « {right} », not « {wrong} ».",
            "de": "Mit « {subject} » endet dieses Verb auf -s: « {right} », nicht « {wrong} ».",
            "fr": "Avec « {subject} », ce verbe se termine par -s : « {right} » et non « {wrong} ».",
        },
    },
    "FR_GENDER_DET": {
        "label": {"en": "Gender", "de": "Genus", "fr": "Genre"},
        "note": {
            "en": "« {noun} » is {gender_en}: « {right} », not « {wrong} ».",
            "de": "« {noun} » ist {gender_de}: « {right} », nicht « {wrong} ».",
            "fr": "« {noun} » est {gender_fr} : « {right} » et non « {wrong} ».",
        },
    },
    "FR_APOSTROPHE": {
        "label": {"en": "Spelling", "de": "Schreibweise", "fr": "Orthographe"},
        "note": {
            "en": "An apostrophe is missing: « {right} ».",
            "de": "Es fehlt ein Apostroph: « {right} ».",
            "fr": "Il manque une apostrophe : « {right} ».",
        },
    },
    "FR_ACCENT": {
        "label": {"en": "Spelling", "de": "Schreibweise", "fr": "Orthographe"},
        "note": {
            "en": "The accent is missing: « {right} ».",
            "de": "Der Akzent fehlt: « {right} ».",
            "fr": "Il manque l’accent : « {right} ».",
        },
    },
    "FR_TENSE_PC": {
        "label": {"en": "Tense", "de": "Zeitform", "fr": "Temps"},
        "note": {
            "en": "The sentence tells the story in the passé composé; keep the same tense: « {right} ».",
            "de": "Der Satz erzählt im passé composé; bleib bei derselben Zeit: « {right} ».",
            "fr": "La phrase raconte au passé composé ; garde le même temps : « {right} ».",
        },
    },
    "FR_ELISION": {
        "label": {"en": "Elision", "de": "Elision", "fr": "Élision"},
        "note": {
            "en": "« {word} » drops its vowel in front of a vowel or a silent h: « {right} ».",
            "de": "« {word} » verliert vor einem Vokal oder stummen h seinen Vokal: « {right} ».",
            "fr": "« {word} » s’élide devant une voyelle ou un h muet : « {right} ».",
        },
    },
    "FR_CET": {
        "label": {"en": "Determiner", "de": "Begleiter", "fr": "Déterminant"},
        "note": {
            "en": "In front of a vowel or a silent h, « ce » becomes « cet »: « {right} ».",
            "de": "Vor einem Vokal oder stummen h wird « ce » zu « cet »: « {right} ».",
            "fr": "Devant une voyelle ou un h muet, « ce » devient « cet » : « {right} ».",
        },
    },
    "FR_MON_VOWEL": {
        "label": {"en": "Determiner", "de": "Begleiter", "fr": "Déterminant"},
        "note": {
            "en": "In front of a vowel, « {wrong} » becomes « {det} », even for a feminine word: « {right} ».",
            "de": "Vor einem Vokal wird « {wrong} » zu « {det} », auch bei einem femininen Wort: « {right} ».",
            "fr": "Devant une voyelle, « {wrong} » devient « {det} », même au féminin : « {right} ».",
        },
    },
    "FR_PLURAL_NOUN": {
        "label": {"en": "Plural", "de": "Plural", "fr": "Pluriel"},
        "note": {
            "en": "After « {det} » the noun is plural: « {right} ».",
            "de": "Nach « {det} » steht das Nomen im Plural: « {right} ».",
            "fr": "Après « {det} », le nom se met au pluriel : « {right} ».",
        },
    },
    "FR_SPELLING": {
        "label": {"en": "Spelling", "de": "Schreibweise", "fr": "Orthographe"},
        "note": {
            "en": "This is written « {right} ».",
            "de": "Das schreibt man « {right} ».",
            "fr": "Cela s’écrit « {right} ».",
        },
    },
    "FR_CONTRACTION": {
        "label": {"en": "Contraction", "de": "Verschmelzung", "fr": "Contraction"},
        "note": {
            "en": "« {wrong} » contracts to « {right} ».",
            "de": "« {wrong} » verschmilzt zu « {right} ».",
            "fr": "« {wrong} » se contracte en « {right} ».",
        },
    },
    "FR_BARE_INFINITIVE": {
        "label": {"en": "Infinitive", "de": "Infinitiv", "fr": "Infinitif"},
        "note": {
            "en": "After « {word} » the infinitive follows directly, without « de »: « {right} ».",
            "de": "Nach « {word} » folgt der Infinitiv direkt, ohne « de »: « {right} ».",
            "fr": "Après « {word} », l’infinitif suit directement, sans « de » : « {right} ».",
        },
    },
    "FR_DOUBLE_NEGATION": {
        "label": {"en": "Negation", "de": "Verneinung", "fr": "Négation"},
        "note": {
            "en": "« {word} » already makes the sentence negative, so « pas » goes: « {right} ».",
            "de": "« {word} » verneint schon, « pas » fällt weg: « {right} ».",
            "fr": "« {word} » porte déjà la négation, « pas » disparaît : « {right} ».",
        },
    },
    "FR_NEGATION_ORDER": {
        "label": {"en": "Word order", "de": "Wortstellung", "fr": "Ordre des mots"},
        "note": {
            "en": "« ne … {word} » goes around the conjugated verb: « {right} ».",
            "de": "« ne … {word} » umschließt das konjugierte Verb: « {right} ».",
            "fr": "« ne … {word} » encadre le verbe conjugué : « {right} ».",
        },
    },
    "FR_NEGATION_AUX": {
        "label": {"en": "Word order", "de": "Wortstellung", "fr": "Ordre des mots"},
        "note": {
            "en": "In a compound tense « ne … {word} » goes around the auxiliary: « {right} ».",
            "de": "In zusammengesetzten Zeiten umschließt « ne … {word} » das Hilfsverb: « {right} ».",
            "fr": "Aux temps composés, « ne … {word} » encadre l’auxiliaire : « {right} ».",
        },
    },
    "FR_PARTITIVE_NEG": {
        "label": {"en": "Article", "de": "Artikel", "fr": "Article"},
        "note": {
            "en": "After a negation, « {wrong} » becomes « de »: « {right} ».",
            "de": "Nach einer Verneinung wird « {wrong} » zu « de »: « {right} ».",
            "fr": "Après une négation, « {wrong} » devient « de » : « {right} ».",
        },
    },
    "FR_MISSING_DE": {
        "label": {"en": "Preposition", "de": "Präposition", "fr": "Préposition"},
        "note": {
            "en": "« {word} » is followed by « de »: « {right} ».",
            "de": "Auf « {word} » folgt « de »: « {right} ».",
            "fr": "« {word} » se construit avec « de » : « {right} ».",
        },
    },
    "FR_A_GRAVE": {
        "label": {"en": "Spelling", "de": "Schreibweise", "fr": "Orthographe"},
        "note": {
            "en": "The preposition takes a grave accent (« a » without it is the verb avoir): « {right} ».",
            "de": "Die Präposition trägt einen Gravis (« a » ohne ihn ist das Verb avoir): « {right} ».",
            "fr": "La préposition prend un accent grave (sans lui, « a » est le verbe avoir) : « {right} ».",
        },
    },
    "FR_ETRE_AGE": {
        "label": {"en": "Verb", "de": "Verb", "fr": "Verbe"},
        "note": {
            "en": "Age is said with avoir: « {right} ».",
            "de": "Das Alter sagt man mit avoir: « {right} ».",
            "fr": "L’âge se dit avec avoir : « {right} ».",
        },
    },
    "FR_STRESSED_PRONOUN": {
        "label": {"en": "Pronoun", "de": "Pronomen", "fr": "Pronom"},
        "note": {
            "en": "After « {word} » the pronoun takes its stressed form: « {right} ».",
            "de": "Nach « {word} » steht das betonte Pronomen: « {right} ».",
            "fr": "Après « {word} », on emploie le pronom tonique : « {right} ».",
        },
    },
    "FR_OBJECT_PRONOUN": {
        "label": {"en": "Pronoun", "de": "Pronomen", "fr": "Pronom"},
        "note": {
            "en": "« à {word} » after this verb becomes « {clitic} » in front of it: « {right} ».",
            "de": "« à {word} » wird bei diesem Verb zu « {clitic} » vor dem Verb: « {right} ».",
            "fr": "Avec ce verbe, « à {word} » devient « {clitic} », placé devant le verbe : « {right} ».",
        },
    },
    "FR_PLURAL_FORM": {
        "label": {"en": "Plural", "de": "Plural", "fr": "Pluriel"},
        "note": {
            "en": "The plural of « {noun} » is « {right} ».",
            "de": "Der Plural von « {noun} » ist « {right} ».",
            "fr": "Le pluriel de « {noun} » est « {right} ».",
        },
    },
}
_GENDER_WORD = {
    "m": {"en": "masculine", "de": "maskulin", "fr": "masculin"},
    "f": {"en": "feminine", "de": "feminin", "fr": "féminin"},
}


def _edit(rule_id: str, text: str, start: int, end: int, replacement: str, **fields: str) -> Edit:
    spec = _RULE_TEXT[rule_id]
    span = text[start:end]
    base = {"subject": "", "right": replacement, "wrong": span, "noun": "", "part": "", "word": "", "det": "", **fields}
    gender = fields.get("gender", "")
    note = {}
    for lang, template in spec["note"].items():
        extra = {
            "gender_en": _GENDER_WORD.get(gender, {}).get("en", ""),
            "gender_de": _GENDER_WORD.get(gender, {}).get("de", ""),
            "gender_fr": _GENDER_WORD.get(gender, {}).get("fr", ""),
        }
        note[lang] = template.format(**{**base, **extra})
    task_type = {
        "FR_ACCENT": "orthography",
        "FR_APOSTROPHE": "orthography",
        "FR_ELISION": "orthography",
        "FR_SPELLING": "orthography",
        "FR_CONTRACTION": "articles",
        "FR_GENDER_DET": "gender_agreement",
        "FR_CET": "gender_agreement",
        "FR_MON_VOWEL": "gender_agreement",
        "FR_PARTICIPLE_AGREE": "gender_agreement",
        "FR_ADJ_AGREE": "gender_agreement",
        "FR_PLURAL_NOUN": "number_agreement",
        "FR_PLURAL_FORM": "number_agreement",
        "FR_A_GRAVE": "orthography",
        "FR_BARE_INFINITIVE": "prepositions",
        "FR_MISSING_DE": "prepositions",
        "FR_DOUBLE_NEGATION": "negation",
        "FR_NEGATION_ORDER": "word_order",
        "FR_NEGATION_AUX": "word_order",
        "FR_PARTITIVE_NEG": "negation",
        "FR_STRESSED_PRONOUN": "pronouns",
        "FR_OBJECT_PRONOUN": "pronouns",
    }.get(rule_id, "verb_conjugation")
    return Edit(
        span=span,
        replacement=replacement,
        rule_id=rule_id,
        label=spec["label"],
        note=note,
        start=start,
        end=end,
        task_error_type=task_type,
        severity=1 if rule_id in {"FR_ACCENT", "FR_APOSTROPHE", "FR_SPELLING", "FR_A_GRAVE"} else 2,
    )


def _subject_gender(tokens: list[Tok], text: str, index: int, people: Mapping[str, str]) -> tuple[str | None, bool]:
    """``(gender, plural)`` of the third-person subject before ``tokens[index]``
    (the auxiliary), or ``(None, False)``. Never reads a gender for the learner."""

    if index <= 0 or not _joined(text, tokens[index - 1], tokens[index]):
        return None, False
    word = tokens[index - 1].low
    original = text[tokens[index - 1].start : tokens[index - 1].end]
    if word == "elle":
        return "f", False
    if word == "elles":
        return "f", True
    if word == "il":
        return "m", False
    if word == "ils":
        return "m", True
    if original[:1].isupper() and word in people:
        return people[word], False
    return None, False


def _agree(participle: str, gender: str | None, plural: bool) -> str:
    out = participle
    if gender == "f" and not out.endswith("e"):
        out += "e"
    if plural and not out.endswith("s"):
        out += "s"
    return out


# ---------------------------------------------------------------------------
# What a word can be: the closed evidence the new rules stand on
# ---------------------------------------------------------------------------
#
# Every rule below fires only on a closed trigger set and stays silent when the
# lexicon cannot say what the next word is. The three night attempts at #250 were
# each rejected for one more correct sentence the pass marked wrong; the corpus guard
# (tests/test_correction_corpus.py) now runs every rule over the app's own French.


def _pos(word: str) -> str | None:
    entry = _lemma(word)
    return str(entry.get("pos")) if entry and entry.get("pos") else None


@lru_cache(maxsize=1)
def _forms() -> Mapping[str, str]:  # pragma: no cover - thin cache
    try:
        return _lexicon().forms
    except Exception:
        return {}


def _verb_lemma(word: str) -> str | None:
    """The infinitive ``word`` can be a form of, or ``None``. The vendored forms list
    misses most regular present forms («livre», «porte»), so the -er endings are read
    too: a word that *could* be a verb is treated as one, which keeps the rules that
    need a noun silent."""

    if _is_verb(word):
        return word
    lemma = _forms().get(word)
    if lemma and _is_verb(lemma):
        return lemma
    stems = []
    if word.endswith("ent"):
        stems.append(word[:-3])
    if word.endswith(("es", "ez")):
        stems.append(word[:-2])
    if word.endswith("ons"):
        stems.append(word[:-3])
    if word.endswith("e"):
        stems.append(word[:-1])
    for ending in ("ées", "és", "ée", "é"):
        if word.endswith(ending):
            stems.append(word[: -len(ending)])
            break
    for stem in stems:
        if stem and _is_verb(stem + "er"):
            return stem + "er"
    return None


def _could_be_verb(word: str) -> bool:
    return _verb_lemma(word) is not None


def _is_noun(word: str) -> bool:
    return _pos(word) == "noun"


def _noun_lemma(word: str) -> str | None:
    """The lexicon noun ``word`` is, singular or plural («enfants» -> «enfant»,
    «gâteaux» -> «gâteau», «yeux» -> «œil»), or ``None``."""
    if _is_noun(word):
        return word
    for candidate in (word[:-1] if word.endswith(("s", "x")) else None, _forms().get(word)):
        if candidate and _is_noun(candidate):
            return candidate
    if word.endswith("aux") and _is_noun(word[:-3] + "al"):
        return word[:-3] + "al"
    return None


def _rank(word: str) -> int:
    entry = _lemma(word) or {}
    rank = entry.get("rank")
    return int(rank) if isinstance(rank, int) else 10**6


def _reads_as_noun(word: str) -> bool:
    """A lexicon noun that is not more likely a verb form here: «livre» (rank 349)
    over «livrer» (2294) reads as the book; «garde» under «garder» does not."""

    if not _is_noun(word):
        return False
    lemma = _verb_lemma(word)
    return lemma is None or _rank(word) < _rank(lemma)


_VOWEL_LETTERS = frozenset("aeiouàâäéèêëîïôöûùüœæ")
#: h muet: the words that elide («l'homme», «j'habite»). Any other h-word is left
#: alone, aspirated or not («le héros», «la hache», «le heurt»): unsure means silent.
_MUTE_H_WORDS = frozenset(
    {
        "homme", "hommes", "heure", "heures", "hôtel", "hôtels", "hôpital", "hôpitaux", "hiver", "hivers",
        "histoire", "histoires", "habitude", "habitudes", "herbe", "herbes", "huile", "huiles", "horloge",
        "horaire", "horaires", "horizon", "horreur", "hôte", "hôtes", "hôtesse", "hommage", "honneur",
        "honnête", "humour", "humeur", "humain", "humains", "humaine", "humanité", "humide", "hélicoptère",
        "hippopotame", "hirondelle", "hypothèse", "hygiène", "harmonie", "héritage", "héroïne", "haleine",
        "hectare", "hémisphère", "huître", "huîtres", "hymne", "hôtelier", "hôtelière", "habitant",
        "habitants", "habitante", "habitantes", "habitation", "heureux", "heureuse", "heureusement",
        "horrible", "horribles", "humble", "hésitation", "hospitalité", "hypermarché", "habit", "habits",
    }
)
#: Verbs with a silent h, read by stem: «j'habite», «je m'habille», «j'hésite».
_MUTE_H_VERB_STEMS = ("habit", "habill", "hésit", "héberg", "humili", "honor")
#: Words with a vowel that never take an elided word in front («le onze», «le oui»).
_NO_ELISION = frozenset(
    {"onze", "onzième", "onzièmes", "oui", "ouate", "uhlan", "ululement", "yacht", "yaourt", "yaourts",
     "yoga", "yéti", "yen", "yeux", "yo-yo"}
)


def _vowel_sound(word: str) -> bool:
    """Whether ``word`` (casefolded) starts with a sound that takes elision."""
    if word == "y":
        return True  # the pronoun: «j'y vais», «il n'y a»
    if not word or word in _NO_ELISION:
        return False
    if word[0] in _VOWEL_LETTERS:
        return True
    if word[0] == "h":
        return word in _MUTE_H_WORDS or word.startswith(_MUTE_H_VERB_STEMS)
    return False


#: elided spelling of each word that drops its vowel.
_ELIDES = {
    "le": "l", "la": "l", "je": "j", "me": "m", "te": "t", "se": "s", "ne": "n", "de": "d",
    "que": "qu", "ce": "c", "si": "s", "jusque": "jusqu", "lorsque": "lorsqu", "puisque": "puisqu",
}
_SUBJECTS_AND_ARTICLES = frozenset({"il", "ils", "elle", "elles", "on", "un", "une", "en"})
#: The closed next words for the elisions that only happen in a few places.
_ELIDE_ONLY_BEFORE: dict[str, frozenset[str]] = {
    "ce": frozenset({"est", "était", "étaient"}),
    "si": frozenset({"il", "ils"}),
    "jusque": frozenset({"à", "au", "aux", "ici", "où", "alors", "en"}),
    "lorsque": _SUBJECTS_AND_ARTICLES,
    "puisque": _SUBJECTS_AND_ARTICLES,
    "que": _SUBJECTS_AND_ARTICLES | {"y", "est-ce", "au", "aux", "à"},
}
#: «ne» elides only in a real negation: its partner follows in the clause («je ne aime
#: pas»). Without one the «ne» is a word quoted, not used («ne est possible»).
_NEGATION_PARTNERS = frozenset(
    {"pas", "plus", "jamais", "rien", "personne", "guère", "point", "que", "qu", "aucun", "aucune", "ni", "nulle"}
)
#: Forms of être and avoir, and the pronouns: after a subject and «ne» these can only elide.
_ALWAYS_ELIDE_NE = frozenset(
    {"ai", "as", "a", "avons", "avez", "ont", "avais", "avait", "avions", "aviez", "avaient", "es", "est", "êtes", "étais",
     "était", "étions", "étiez", "étaient", "y", "en"}
)
_SUBJECTS_BEFORE_NE = frozenset({"je", "tu", "il", "elle", "on", "nous", "vous", "ils", "elles", "ce", "ça", "cela", "qui"})
#: «d'abord», «d'accord», «d'ici», «d'où», «d'autres», «d'un»: the function words «de»
#: elides in front of; any other word after «de» must be a noun, adjective or verb.
_DE_FUNCTION_WORDS = frozenset(
    {"un", "une", "abord", "accord", "ailleurs", "ici", "où", "autre", "autres", "elle", "elles", "eux",
     "en", "habitude", "avance", "aujourd"}
)


def _elision(source: str, tokens: list[Tok], i: int) -> tuple[int, str] | None:
    """``(end, replacement)`` when ``tokens[i]`` must elide in front of the next word
    («la appartement» -> «l'appartement», «de Odile» -> «d'Odile», «si il» -> «s'il»),
    else ``None``."""

    tok = tokens[i]
    elided = _ELIDES.get(tok.low)
    if elided is None or i + 1 >= len(tokens):
        return None
    nxt = tokens[i + 1]
    gap = source[tok.end : nxt.start]
    if not gap or gap.strip("  ") != "":
        return None  # only a plain space: a comma, a quote or a dash is a boundary
    if i > 0 and source[tokens[i - 1].end : tok.start] in {"'", "’", "-"}:
        return None  # part of a longer word («aujourd'hui», «peut-être»)
    word = nxt.low
    written = source[nxt.start : nxt.end]
    if len(written) == 1 and written.isupper():
        return None  # a letter used as a name or a variable («que Y», «ligne A»)
    if source[nxt.end : nxt.end + 2].lstrip(" ")[:1] == "/":
        return None  # «si il / elle»: words listed as words, not used
    capital_name = written[:1].isupper() and _lemma(word) is None and word[:1] in _VOWEL_LETTERS
    only = _ELIDE_ONLY_BEFORE.get(tok.low)
    if only is not None:
        ok = word in only or (tok.low == "que" and capital_name)
    elif not _vowel_sound(word):
        return None
    elif tok.low in {"le", "la"}:
        # determiner or object pronoun: a noun, an adjective or a verb follows, never a
        # function word («la une», «le un», «Donne le à Marie», «Il est la avec elle»)
        ok = not written[:1].isupper() and (_pos(word) in {"noun", "adjective"} or _could_be_verb(word))
    elif tok.low in {"je", "me", "te", "se", "ne"}:
        ok = word in {"y", "en"} or _could_be_verb(word)
        if ok and tok.low == "ne":
            rest = tokens[i + 2 :]
            ok = any(
                t.low in _NEGATION_PARTNERS and _same_clause(source, nxt, t) for t in rest[:6]
            ) or (
                # «je ne était», «Je ne ai»: a subject in front closes it, the «pas» may be missing
                word in _ALWAYS_ELIDE_NE
                and i > 0
                and _same_clause(source, tokens[i - 1], tok)
                and tokens[i - 1].low in _SUBJECTS_BEFORE_NE
            )
    elif word in {"un", "une"} and i > 0 and _could_be_verb(tokens[i - 1].low) and not _is_noun(tokens[i - 1].low):
        # «je voudrais de un café» is «un café», «je parle de un ami» is «d'un ami»:
        # after a verb the pass cannot tell which, so it says nothing
        return None
    else:  # de: a noun, an adjective, an infinitive, a name, or a closed few
        ok = (
            word in _DE_FUNCTION_WORDS
            or capital_name
            or (
                not written[:1].isupper()
                and (
                    _pos(word) in {"noun", "adjective"}
                    or _noun_lemma(word) is not None
                    or (word.endswith("s") and _pos(word[:-1]) == "adjective")
                    or _is_verb(word)
                )
            )
        )
    if not ok or not _vowel_sound(word):
        return None
    if word == "y" and tok.low not in {"je", "me", "te", "se", "ne", "que"}:
        return None
    apostrophe = "’" if "’" in source else "'"
    return nxt.end, _case(source[tok.start : tok.end], elided) + apostrophe + written


_PLURAL_DETS = frozenset(
    # «leurs» is left out: «leurs voiture» is as often «leur voiture» (one car each)
    {"les", "des", "mes", "tes", "ses", "ces", "nos", "vos", "plusieurs", "quelques", "deux",
     "trois", "quatre", "cinq", "six", "sept", "huit", "neuf", "dix", "douze", "quinze", "vingt", "trente",
     "quarante", "cinquante", "cent", "mille"}
)
#: «le deux mai», «le quinze avril»: a date, not a plural.
_CALENDAR = frozenset(
    {"janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
     "novembre", "décembre", "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"}
)
#: «des» in front of these is usually «du / de la» meant, not a plural: left alone.
_MASS_NOUNS = frozenset(
    {"eau", "pain", "lait", "café", "thé", "vin", "bière", "fromage", "viande", "riz", "sucre", "sel",
     "poivre", "beurre", "argent", "temps", "courage", "chance", "patience", "musique", "soupe", "chocolat",
     "jus", "huile", "farine", "confiture", "crème", "poisson", "poulet", "travail", "monde", "bruit", "sport"}
)
_IRREGULAR_PLURALS = {
    "œil": "yeux", "oeil": "yeux", "ciel": "cieux", "travail": "travaux", "bail": "baux", "corail": "coraux",
    "émail": "émaux", "vitrail": "vitraux", "bijou": "bijoux", "caillou": "cailloux", "chou": "choux",
    "genou": "genoux", "hibou": "hiboux", "joujou": "joujoux", "pou": "poux", "monsieur": "messieurs",
    "madame": "mesdames", "mademoiselle": "mesdemoiselles",
}
_AL_PLURAL_S = frozenset(
    {"bal", "carnaval", "chacal", "festival", "récital", "régal", "cal", "val", "étal", "narval", "choral", "pal",
     "santal", "cérémonial", "idéal", "final"}
)
_X_PLURAL_S = frozenset({"pneu", "bleu", "émeu", "landau", "sarrau"})


def _plural(noun: str) -> str | None:
    """The plural of a lexicon noun, or ``None`` when it is already plural-shaped or
    its plural is not one the pass can be sure of."""
    if noun in _IRREGULAR_PLURALS:
        return _IRREGULAR_PLURALS[noun]
    if noun.endswith(("s", "x", "z")) or "-" in noun:
        return None
    if noun.endswith("al"):
        return noun + "s" if noun in _AL_PLURAL_S else noun[:-2] + "aux"
    if noun.endswith(("eau", "au", "eu")):
        return noun + "s" if noun in _X_PLURAL_S else noun + "x"
    return noun + "s"


#: Misspellings that are no French word at all, each with its one spelling. A word
#: the lexicon knows is never on this list («marche», «cote», «foret» are words).
_MISSPELLINGS = {
    "parceque": "parce que", "aujourdhui": "aujourd’hui", "quelqun": "quelqu’un", "beacoup": "beaucoup",
    "bocoup": "beaucoup", "beaucoups": "beaucoup", "probleme": "problème", "problemes": "problèmes",
    "telephone": "téléphone", "metro": "métro", "numero": "numéro", "bientot": "bientôt",
    "plutot": "plutôt", "premiere": "première", "deuxieme": "deuxième", "troisieme": "troisième",
    "derniere": "dernière", "etage": "étage", "fenetre": "fenêtre",
    "tete": "tête", "hotel": "hôtel", "interessant": "intéressant", "interessante": "intéressante",
    "medecin": "médecin", "cinema": "cinéma", "francaise": "française", "garcon": "garçon",
    "lecon": "leçon", "recu": "reçu", "decu": "déçu", "noel": "Noël", "reve": "rêve", "pret": "prêt",
    "prete": "prête", "general": "général", "generalement": "généralement", "etranger": "étranger",
    "etrangere": "étrangère", "evidemment": "évidemment",
    # the apostrophe dropped and the words run together (#250, #333: «cest», «jai», «dabord»)
    "cest": "c’est", "cetait": "c’était", "jai": "j’ai", "jaime": "j’aime", "daccord": "d’accord",
    "dabord": "d’abord", "quil": "qu’il", "quils": "qu’ils", "quelquun": "quelqu’un", "jusqua": "jusqu’à",
    "nest": "n’est", "nai": "n’ai", "sil": "s’il",
}
#: The elided words a misspelled word may lean on: «l'hotel», «d'etage».
_ELIDED_BEFORE_A_WORD = frozenset({"l", "d", "j", "n", "s", "t", "m", "c", "qu"})
#: Glued only with a negation after it: «nest» is also a word of English and of German.
_GLUED_NEGATIONS = frozenset({"nest", "nai"})
#: «sil te plaît», «sil y a». Anything else after «sil» may be a name.
_AFTER_GLUED_SIL = frozenset({"te", "vous", "y", "ne", "est", "a", "fait"})
#: Spelled like a participle after avoir: «j'ai reve» is «rêvé», not «rêve».
_PARTICIPLE_LOOKALIKES = frozenset({"reve", "prete", "telephone"})
#: «grand mère» -> «grand-mère»: the hyphen of the family words.
_HYPHENATED = {
    ("grand", "mère"): "grand-mère", ("grand", "mere"): "grand-mère", ("grand", "père"): "grand-père",
    ("grand", "pere"): "grand-père", ("grands", "parents"): "grands-parents",
    ("grand", "parents"): "grands-parents",
}


# ---------------------------------------------------------------------------
# The missing accent: the one lexicon word this spelling can be (#250)
# ---------------------------------------------------------------------------

#: Common words only: the rarer a word, the likelier the learner meant another.
_ACCENT_FOLD_RANK = 3000
_ACCENT_FOLD_POS = frozenset({"noun", "adjective", "adverb", "function", "number"})
#: The lexicon doesn't hold them, but these are French as written, or read as another word: «il
#: boite», «une aine», «un foret», «un desert» typed for «un dessert», «metre» for «mettre», «pate»
#: for «pâté», «dela» for «de la». «the» and «these» are English first.
_BARE_READS_OTHERWISE = frozenset(
    {"the", "these", "aine", "boite", "foret", "media", "mures", "sures", "desert", "metre", "pate", "dela", "pecheur"}
)
#: A word ending in «é» that no verb form («il enerve», «ça m'enerve») can be typed for. Words in
#: «-té» with no such verb in the lexicon qualify by their ending.
_ACUTE_ENDING_WORDS = frozenset(
    {"clé", "bébé", "canapé", "télé", "comité", "degré", "congé", "malgré", "moitié", "pitié", "amitié", "supermarché",
     "député"}
)
_ACUTE_ENDING_LENGTH = 5


@lru_cache(maxsize=1)
def _accent_folds() -> Mapping[str, str]:  # pragma: no cover - thin cache
    """Unaccented spelling -> the one lexicon word it can be. The spelling itself is no lexicon
    word and no verb form, and only one lexicon word folds to it. Conjugations stay out: «fuites»
    is a noun the lexicon doesn't hold, and folds to the verb form «fuîtes»."""

    lemmas, forms = _lexicon().lemmas, _forms()
    surfaces = set(lemmas) | set(forms)
    by_fold: dict[str, set[str]] = {}
    for surface in surfaces:
        by_fold.setdefault(_strip_marks(surface), set()).add(surface)
    verbs = {_strip_marks(word) for word, entry in lemmas.items() if entry.get("pos") == "verb"}

    def rank_and_pos(word: str) -> tuple[int, str] | None:
        entry = lemmas.get(word) or lemmas.get(forms.get(word) or "")
        if not entry or not isinstance(entry.get("rank"), int):
            return None
        return entry["rank"], str(entry.get("pos"))

    folds: dict[str, str] = {}
    for bare, found in by_fold.items():
        if bare in surfaces or len(found) != 1 or bare in _BARE_READS_OTHERWISE or len(bare) < 3:
            continue
        form = next(iter(found))
        known = rank_and_pos(form)
        if known is None or known[0] > _ACCENT_FOLD_RANK or known[1] not in _ACCENT_FOLD_POS:
            continue
        if _could_be_verb(bare):
            continue
        # «ecoute» is «écoute» or «écouté», «complete» «complète» or «complété»: the verb says both
        if bare.endswith("e") and bare[:-1] + "er" in verbs:
            continue
        if form.endswith("é") and form not in _ACUTE_ENDING_WORDS and not (form.endswith("té") and len(form) > _ACUTE_ENDING_LENGTH):
            continue
        folds[bare] = form
    return folds


def _accent_fold(word: str) -> str | None:
    """The accented word ``word`` must be, its plural too («cles» -> «clés»), or ``None``."""

    folds = _accent_folds()
    if word in folds:
        return folds[word]
    if word.endswith("s") and word not in _lexicon().lemmas and word not in _forms():
        singular = folds.get(word[:-1])
        if singular is not None and _pos(singular) in {"noun", "adjective"} and _plural(singular) == singular + "s":
            return singular + "s"
    return None


# ---------------------------------------------------------------------------
# The dropped apostrophe: a closed list on both sides (#133, #250, the review of #310)
# ---------------------------------------------------------------------------

#: Pieces that are no word on their own, and the words they join.
_ELIDED_PIECES: dict[str, frozenset[str]] = {
    "qu": frozenset({"est-ce", "il", "ils", "elle", "elles", "on", "un", "une"}),
    "aujourd": frozenset({"hui"}),
    "quelqu": frozenset({"un", "une"}),
    "jusqu": frozenset({"à", "au", "aux", "ici", "où"}),
    "lorsqu": frozenset({"il", "ils", "elle", "elles", "on"}),
    "puisqu": frozenset({"il", "ils", "elle", "elles", "on"}),
}
#: The words each lone letter elides in front of. Never «et», «à», «ou» (the review of #310).
_ELIDED_LETTERS: dict[str, frozenset[str]] = {
    "c": frozenset({"est", "était", "etait", "étaient"}),
    "j": frozenset({"ai", "avais", "aurai", "aurais", "aime", "aimais", "adore", "arrive", "appelle", "étais", "habite",
                    "habitais", "espère", "irai", "irais", "y", "en", "écris", "écoute", "entends", "attends", "oublie", "ouvre"}),
    "s": frozenset({"il", "ils", "est", "était", "appelle", "appellent", "en", "y"}),
    "n": frozenset({"est", "es", "êtes", "ai", "as", "a", "avons", "avez", "ont", "y", "en", "était", "étais", "avait", "avais",
                    "aime", "aimes"}),
    "m": frozenset({"appelle", "appelles", "appelait", "appelais", "a", "as", "avez", "ont", "avait", "en", "y", "aime", "aimes",
                    "écoute", "attend", "attends"}),
    "t": frozenset({"ai", "a", "ont", "avait", "avais", "aime", "aimes", "appelle", "appelles", "écoute", "attend", "attends",
                    "en", "y"}),
    "l": frozenset({"ai", "as", "a", "avons", "avez", "ont", "avais", "avait", "aime", "aimes", "aiment", "appelle", "attends",
                    "attend", "écoute"}),
    "d": frozenset({"accord", "abord", "ailleurs", "habitude", "ici"}),
}
#: Who may stand in front of a clitic letter: only a subject makes «n est», «l a» French
#: («si n est pair» is about a number).
_PRONOUN_PERSONS = {**_SUBJECT_PRONOUNS, "nous": "1pl", "vous": "2pl", "ce": "3sg", "ça": "3sg", "cela": "3sg", "qui": "3sg"}
#: What may stand in front of «c est»: the start of a clause or one of these.
_BEFORE_C_EST = frozenset(
    {"que", "qu", "et", "mais", "ou", "car", "donc", "alors", "oui", "non", "parce", "puisque", "comme", "quand", "puis",
     "lorsque", "aussi", "bon", "ah", "oh", "eh", "bonjour", "salut", "merci", "voilà", "pense", "crois", "trouve", "sais",
     "dit"}
)
#: What may stand in front of «l» and a noun, besides the start of a clause or a verb.
_BEFORE_L_NOUN = frozenset(
    {"à", "a", "de", "dans", "sur", "sous", "pour", "avec", "par", "vers", "devant", "derrière", "sans", "après", "avant",
     "chez", "et", "ou", "mais", "que", "tout", "toute", "voici", "voilà", "est"}
)
#: A letter after these names itself: «la ligne C», «le plan B», «la vitamine D».
_NAMES_A_LETTER = frozenset(
    {"ligne", "plan", "vitamine", "bus", "quai", "bâtiment", "batiment", "lettre", "groupe", "option", "catégorie",
     "categorie", "point", "étage", "etage", "porte", "salle", "voie", "hall", "zone", "terminal", "tome", "annexe", "partie",
     "chapitre", "modèle", "modele", "type", "classe", "rang", "niveau", "section", "sortie", "entrée", "entree", "escalier",
     "métro", "metro", "tram", "tramway", "rer", "série", "serie", "variante", "réponse", "reponse", "case", "colonne",
     "taille", "note", "version", "équipe", "equipe", "jour"}
)
_NUMBER_NAMES = frozenset({"deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf", "dix", "double", "plusieurs", "quelques"})
_NOT_A_NAMED_LETTER = frozenset({"a", "à", "y"})


def _apostrophe(source: str) -> str:
    return "’" if "’" in source else "'"


def _letter_names_itself(source: str, tokens: list[Tok], index: int) -> bool:
    """Whether the lone letter at ``index`` is a letter or a unit, not an elided word: «le c
    est muet», «la ligne C», «200 m», «J U L I E», «A est ici. C est là-bas.»."""

    tok = tokens[index]
    written = source[tok.start : tok.end]
    if written.isupper() and not _starts_sentence(source, tok):
        return True
    if source[: tok.start].rstrip()[-1:].isdigit():
        return True
    if written.isupper() and any(
        other is not tok
        and len(other.low) == 1
        and source[other.start : other.end].isupper()
        and source[other.end : other.end + 1] not in {"'", "’"}
        for other in tokens
    ):
        return True
    if index == 0 or not _same_clause(source, tokens[index - 1], tok):
        return False
    prev = tokens[index - 1].low
    return (
        (prev in _DETERMINERS and prev != "ce")  # «ce n est pas» is the subject «ce»
        or prev in _NAMES_A_LETTER
        or prev in _NUMBER_NAMES
        or prev == "des"
        or (len(prev) == 1 and prev not in _NOT_A_NAMED_LETTER)
    )


def _spelled(word: str) -> str:
    """``word`` as the accent and spelling tables write it: «hotel» -> «hôtel»."""
    return _ACCENTS.get(word) or _MISSPELLINGS.get(word) or _accent_fold(word) or word


def _subject_fits(subject: str | None, verb: str) -> bool:
    """A subject in front of a clitic letter, and no être/avoir/aller form wrong for it."""
    person = _PRONOUN_PERSONS.get(subject or "")
    if person is None:
        return False
    persons = _FORM_PERSONS.get(verb)
    return persons is None or subject in {"qui"} or person in persons


def _dropped_apostrophe(source: str, tokens: list[Tok], index: int) -> tuple[int, int, str] | None:
    """``(start, end, replacement)`` when a space stands where an apostrophe belongs, else
    ``None``. Closed on both sides: the piece, the word after it and what stands in front."""

    tok = tokens[index]
    nxt = tokens[index + 1] if index + 1 < len(tokens) else None
    if nxt is None or not _space(source, tok, nxt):
        return None
    if index > 0 and source[tokens[index - 1].end : tok.start] in {"'", "’", "-"}:
        return None  # part of a longer word
    mark = _apostrophe(source)
    written, word, word_written = source[tok.start : tok.end], nxt.low, source[nxt.start : nxt.end]
    prev = tokens[index - 1] if index > 0 else None
    opens_clause = prev is None or not _same_clause(source, prev, tok)
    prev_low = None if opens_clause or prev is None else prev.low

    # «a l hotel» -> «à l'hôtel»: with nothing at all in front, this «a» has no subject to be a
    # verb of. After a stop it may have one: «Augustin de… Créteil… a l'honneur de signer».
    if tok.low == "a" and written == "a" and index == 0 and word == "l" and len(tokens) > 2:
        noun = tokens[index + 2]
        gap = source[nxt.end : noun.start]
        spelled = _spelled(noun.low)
        if gap in {" ", "'", "’"} and _vowel_sound(spelled) and _reads_as_noun(spelled):
            return tok.start, noun.end, f"à l{mark}{source[noun.start : noun.end]}"
        return None

    pieces = _ELIDED_PIECES.get(tok.low)
    if pieces is not None:
        if word in pieces:
            return tok.start, nxt.end, f"{written}{mark}{word_written}"
        # «Qu est ce que» -> «Qu'est-ce que»
        after = tokens[index + 2] if index + 2 < len(tokens) else None
        if tok.low == "qu" and word == "est" and after is not None and after.low == "ce" and _space(source, nxt, after):
            return tok.start, after.end, f"{written}{mark}{word_written}-{source[after.start : after.end]}"
        return None

    allowed = _ELIDED_LETTERS.get(tok.low)
    if allowed is None or _letter_names_itself(source, tokens, index):
        return None
    if tok.low == "d" and word_written[:1].isupper() and _lemma(word) is None and word[:1] in _VOWEL_LETTERS:
        # «la clé d Odile»: a noun in front of it, a name after it, a small «d»
        if written != "d" or prev_low is None or not _is_noun(_spelled(prev_low)):
            return None
    elif word not in allowed:
        # «l hotel», «l immeuble»: a noun that takes elision, after a word that can stand before one
        spelled = _spelled(word)
        if tok.low != "l" or not (_vowel_sound(spelled) and _reads_as_noun(spelled)):
            return None
        if not (prev_low is None or prev_low in _BEFORE_L_NOUN or _could_be_verb(prev_low)):
            return None
    elif tok.low == "c" and not (opens_clause or prev_low in _BEFORE_C_EST):
        return None
    elif tok.low == "s" and word not in {"il", "ils"} and not _subject_fits(_clitic_subject(tokens, index), word):
        if prev_low != "comment":
            return None
    elif tok.low in {"n", "m", "t", "l"} and not _subject_fits(_clitic_subject(tokens, index), word):
        # #754: «Gus m a demandé»: a name in front is a subject like «il», for a form of «il».
        if tok.low != "n" and _names_a_subject_in_front(source, prev, opens_clause) and (
            _FORM_PERSONS.get(word) is None or "3sg" in _FORM_PERSONS[word]
        ):
            return tok.start, nxt.end, f"{written}{mark}{word_written}"
        # «Lila n est pas là»: a name in front holds too, with its negation after the verb
        if not (
            tok.low == "n"
            and prev is not None
            and not opens_clause
            and source[prev.start : prev.end][:1].isupper()
            and _lemma(prev.low) is None
            and any(t.low in _NEGATION_PARTNERS and _same_clause(source, nxt, t) for t in tokens[index + 2 : index + 6])
        ):
            return None
    return tok.start, nxt.end, f"{written}{mark}{word_written}"


def _names_a_subject_in_front(source: str, prev: Tok | None, opens_clause: bool) -> bool:
    """Whether the word in front is a person's name: a cast first name («Marin», also a noun)
    or a capitalised word French does not know («Gus», «Margaux»). «Puis m a» has none."""
    if prev is None or opens_clause or not source[prev.start : prev.end][:1].isupper():
        return False
    return prev.low in _cast_first_names() or _lemma(prev.low) is None


def _clitic_subject(tokens: list[Tok], index: int) -> str | None:
    """The word in front of the clitic letter at ``index``, past a «ne»: «il ne m a pas»."""
    at = index - 1
    if at >= 0 and tokens[at].low in {"ne", "n"}:
        at -= 1
    return tokens[at].low if at >= 0 else None


# ---------------------------------------------------------------------------
# Phrase rules: word order and the small words around a verb
# ---------------------------------------------------------------------------

#: Finite forms of the verbs that take a bare infinitive («je peux venir», never «je
#: peux de venir»). The infinitives stay out: «le pouvoir de décider» is a noun.
_BARE_INFINITIVE_VERBS = frozenset(
    {"peux", "peut", "pouvons", "pouvez", "peuvent", "pourrais", "pourrait", "pourrions", "pourriez",
     "pourraient", "veux", "veut", "voulons", "voulez", "veulent", "voudrais", "voudrait", "voudrions",
     "voudriez", "voudraient", "dois", "doit", "devons", "devez", "doivent", "devrais", "devrait",
     "devrions", "devriez", "devraient", "faut", "faudrait", "faudra", "fallait", "sais", "sait", "savons",
     "savez", "savent", "aime", "aimes", "aimons", "aimez", "aiment", "aimerais", "aimerait", "adore",
     "adores", "adorons", "adorez", "adorent", "déteste", "détestes", "détestons", "détestez", "détestent"}
)
#: «je me dois de le dire»: a reflexive in front makes «de» right.
_REFLEXIVES = frozenset({"me", "m", "te", "t", "se", "s", "nous", "vous"})
_CLITICS_BEFORE_INFINITIVE = frozenset(
    {"me", "m", "te", "t", "se", "s", "le", "la", "l", "les", "lui", "leur", "y", "en", "nous", "vous"}
)
#: «pas» next to a word that already makes the sentence negative. «pas rien» is left
#: out: «ce n'est pas rien» is French.
_FULL_NEGATIONS = frozenset({"jamais", "aucun", "aucune", "guère", "personne"})
_NEGATION_WORDS = frozenset({"pas", "plus", "jamais", "rien"})
_AVOIR_FORMS = frozenset({"ai", "as", "a", "avons", "avez", "ont", "avais", "avait", "avions", "aviez", "avaient"})
#: «en face la gare» -> «en face de la gare»: the locutions that need «de» before a noun.
_NEEDS_DE = {("en", "face"), ("à", "côté"), ("au", "milieu"), ("au", "bord"), ("à", "cause"), ("au", "lieu")}
_EN_FACE_ADVERB_VERBS = frozenset({"regarder", "voir", "dire", "affronter", "fixer", "envisager", "accepter", "assumer"})
_DETERMINERS = frozenset(
    {"le", "la", "l", "les", "un", "une", "mon", "ma", "mes", "ton", "ta", "tes", "son", "sa", "ses", "notre",
     "votre", "nos", "vos", "leur", "leurs", "ce", "cet", "cette", "ces"}
)
_SUBJECT_PRONOUN_WORDS = frozenset({"je", "j", "tu", "il", "elle", "on", "nous", "vous", "ils", "elles"})
_STRESSED = {"je": "moi", "tu": "toi", "il": "lui", "ils": "eux"}
_STRESSED_PREPOSITIONS = frozenset({"chez", "avec", "pour", "sans", "contre", "derrière", "devant"})
_RELATIVES = frozenset(
    {"qui", "que", "qu", "dont", "où", "lequel", "laquelle", "lesquels", "lesquelles", "duquel", "desquels",
     "desquelles", "auquel", "auxquels", "auxquelles"}
)
_ETRE_TO_AVOIR = {"suis": "ai", "es": "as", "est": "a", "sommes": "avons", "êtes": "avez", "sont": "ont"}
_NUMBER_GAP = re.compile(r"\s+\d+\s+")


#: #749: «à moi / à toi» after these verbs is the object pronoun in front of the verb
#: («il m'a dit», «elle te parle»). Verbs that keep the stressed pronoun after «à»
#: («penser à moi», «tenir à toi», «venir à moi», «être à moi») are not here.
_INDIRECT_OBJECT_VERBS = frozenset(
    {"dire", "donner", "parler", "faire", "montrer", "demander", "répondre", "écrire", "envoyer", "apporter",
     "offrir", "expliquer", "raconter", "sourire", "téléphoner", "prêter", "rendre", "poser", "proposer",
     "présenter", "annoncer", "souhaiter", "passer", "acheter", "servir", "laisser", "conseiller", "apprendre",
     "lancer", "promettre", "rapporter", "vendre", "confier", "plaire", "mentir", "obéir"}
)
#: «faire attention à moi», «faire appel à toi»: these keep «à» and the stressed pronoun.
_FAIRE_KEEPS_A = frozenset({"attention", "appel", "allusion", "face", "honneur"})
#: «un ami à moi» is «a friend of mine»: after a person's relation «à moi» is the
#: possessive, and «Elle a présenté un ami à moi» means something else than «Elle m'a
#: présenté un ami». The floor only claims what is sure, so it leaves these alone.
_POSSESSIVE_A_NOUNS = frozenset(
    {"ami", "amie", "amis", "amies", "copain", "copine", "copains", "copines", "cousin", "cousine", "cousins",
     "cousines", "frère", "frères", "sœur", "sœurs", "soeur", "soeurs", "collègue", "collègues", "voisin",
     "voisine", "voisins", "voisines", "fils", "fille", "filles", "enfant", "enfants", "oncle", "tante", "père",
     "mère", "parents", "neveu", "nièce", "camarade", "camarades", "connaissance", "client", "cliente", "patron",
     "patronne", "chien", "chat", "idée", "idées"}
)
#: «Il a donné tout à moi» -> «Il m'a tout donné»: «tout» and «rien» move in front of the
#: participle, which a span edit cannot say; the floor leaves the sentence to the model.
_MOVES_BEFORE_PARTICIPLE = frozenset({"tout", "rien"})
#: The stressed pronoun -> the object pronoun before a consonant and before a vowel.
_OBJECT_CLITIC_OF = {"moi": ("me", "m"), "toi": ("te", "t")}
#: What may stand between the verb and «à moi»: a short noun group, nothing that opens
#: another phrase or negates the verb.
_NOT_IN_OBJECT = frozenset(
    {"à", "au", "aux", "que", "qu", "qui", "ne", "n", "pas", "plus", "jamais", "rien", "y", "en", "lui", "leur",
     "le", "la", "les", "l", "se", "s", "me", "m", "te", "t", "et", "ou", "pour", "avec", "sans", "chez", "dans"}
)
_OBJECT_DETERMINERS = frozenset(
    {"un", "une", "des", "du", "de", "d", "le", "la", "l", "les", "mon", "ma", "mes", "ton", "ta", "tes", "son", "sa",
     "ses", "notre", "votre", "nos", "vos", "leur", "leurs", "ce", "cet", "cette", "ces"}
)


def _object_pronoun_edit(source: str, tokens: list[Tok], index: int) -> Edit | None:
    """«à moi / à toi» closing a clause whose verb takes the object pronoun in front of it.

    Closed on every side: the clause ends after the pronoun (no «, pas à toi», no «et à
    Lila»), a subject stands right in front of the verb with nothing between (no «ne»,
    no clitic), and between the verb and «à» stands at most a short noun group."""

    at, pronoun = tokens[index], tokens[index + 1]
    if source[at.start : at.end] != "à" or not _space(source, at, pronoun):
        return None
    after = tokens[index + 2] if index + 2 < len(tokens) else None
    if after is not None and (
        _same_clause(source, pronoun, after) or after.low in {"pas", "non", "mais", "et", "ou", "ni", "aussi", "seul"}
    ):
        return None
    # The verb group: «a fait» (avoir + participle) or a finite verb, with its subject in front.
    for k in range(index - 1, max(index - 7, 0), -1):
        if not _same_clause(source, tokens[k], at):
            return None
        verb, first = tokens[k], tokens[k]
        last = k
        if verb.low in _AVOIR_FORMS and k + 1 < index and _participle(tokens[k + 1].low):
            lemma, last = _verb_lemma(tokens[k + 1].low), k + 1
        elif _finite_verb(verb.low) and not _participle(verb.low):
            lemma = _verb_lemma(verb.low)
        else:
            continue
        subject = tokens[k - 1] if k >= 1 else None
        if subject is None or not _joined(source, subject, first) or not _same_clause(source, subject, first):
            return None
        if subject.low not in _SUBJECT_PRONOUN_WORDS and not _names_a_subject_in_front(source, subject, False):
            return None
        if lemma not in _INDIRECT_OBJECT_VERBS:
            return None
        between = tokens[last + 1 : index]
        if len(between) > 4 or any(t.low in _NOT_IN_OBJECT - _OBJECT_DETERMINERS for t in between):
            return None
        if any(_is_verb(t.low) for t in between):
            return None
        if lemma == "faire" and any(t.low in _FAIRE_KEEPS_A for t in between):
            return None
        if any(t.low in _POSSESSIVE_A_NOUNS for t in between):
            return None  # «un ami (proche) à moi»: a friend of mine, whatever follows the noun
        if any(t.low in _MOVES_BEFORE_PARTICIPLE for t in between):
            return None  # «donné tout à moi»: «m'a tout donné» moves a word
        person ={"moi": {"je", "j"}, "toi": {"tu"}}[pronoun.low]
        if subject.low in person:
            return None  # «je … à moi» is no object pronoun
        full, elided = _OBJECT_CLITIC_OF[pronoun.low]
        verb_word = source[first.start : first.end]
        clitic = f"{elided}{_apostrophe(source)}" if _vowel_sound(verb_word.casefold()) else f"{full} "
        kept = source[first.start : tokens[index - 1].end]
        start, prefix = first.start, ""
        if subject.low == "j":
            # «J'ai écrit une lettre à toi» -> «Je t'ai écrit une lettre»
            start, prefix = subject.start, _case(source[subject.start : subject.end], "je") + " "
        right = f"{prefix}{clitic}{kept}"
        return _edit("FR_OBJECT_PRONOUN", source, start, pronoun.end, right,
                     word=pronoun.low, clitic=f"{full} / {elided}{_apostrophe(source)}", right=right)
    return None


def _finite_verb(word: str) -> bool:
    """A conjugated verb form, not an infinitive, a participle, a noun or a pronoun."""
    if word in _FORM_LEMMA:
        return True
    if word in _CLITIC_CONTEXT or _is_verb(word) or word.endswith(("é", "ée", "és", "ées")):
        return False
    return _verb_lemma(word) is not None and _pos(word) is None


_PARTICIPLE_ENDINGS = ("é", "ée", "és", "ées", "i", "ie", "is", "ies", "u", "ue", "us", "ues", "it", "ite",
                       "ert", "erte", "eint", "aint", "ait")


def _participle(word: str) -> bool:
    """A past participle the pass can vouch for: «vu», «mangé», «fini», «pris», «fait»."""
    if word in _PC_PARTICIPLES or word in _ETRE_PARTICIPLES:
        return True
    if word in _FORM_LEMMA or _is_verb(word) or not word.endswith(_PARTICIPLE_ENDINGS):
        return False
    if word.endswith("é") and _is_verb(word[:-1] + "er"):
        return True
    lemma = _forms().get(word)
    return bool(lemma and _is_verb(lemma) and _pos(word) is None)


_AUXILIARY_FORMS = frozenset(
    {"ai", "as", "a", "avons", "avez", "ont", "suis", "es", "est", "sommes", "êtes", "sont"}
)


def _verb_after_subject(word: str) -> bool:
    """A noun / verb form like «reste» or «porte», read as the verb it must be once a
    subject pronoun stands in front of it."""
    return (
        word not in _CLITIC_CONTEXT
        and not _is_verb(word)
        and not word.endswith(("é", "ée", "és", "ées"))
        and _verb_lemma(word) is not None
    )


def _is_number_word(word: str) -> bool:
    return all(_pos(part) == "number" for part in word.split("-")) if word else False


def _is_compound_number(word: str) -> bool:
    """#724: «trente-deux», «dix-sept», «quatre-vingt-dix»: a hyphenated number is one
    token, and always more than one, so the noun after it is plural («trente-deux ans»)."""
    return "-" in word and _is_number_word(word)


def _space(source: str, left: Tok, right: Tok) -> bool:
    return source[left.end : right.start] in {" ", " "}


#: A day or a time of day: what «à dix-huit heures» can follow where «a» is no verb.
_BEFORE_THE_CLOCK = frozenset(
    {"lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche", "demain", "hier", "hui", "matin", "soir",
     "après-midi"}
)
#: What may follow the hour. Not «de»: «jeudi a dix-huit heures de cours» has them, and not an
#: adjective: «lundi a trois heures libres». The review of #310 found both shapes.
_AFTER_THE_CLOCK = frozenset(
    {"du", "et", "ou", "mais", "à", "au", "aux", "chez", "dans", "avec", "pour", "sur", "en", "pile", "précises", "trente",
     "quinze", "moins", "je", "tu", "il", "elle", "on", "nous", "vous", "ils", "elles", "ce", "si", "car", "donc", "alors",
     "parce", "quand", "comme"}
)
#: «Le lundi a vingt-quatre heures, comme les autres jours.», «L'examen de lundi a trois heures
#: pour finir.»: after one of these the day is, or belongs to, the subject of the verb. «ce» stays
#: out: «ce soir a huit heures» is always the time.
_A_DAY_THAT_CAN_HAVE_HOURS = frozenset(
    {"le", "un", "chaque", "tout", "mon", "ton", "son", "notre", "votre", "leur", "de", "du"}
)
_CLOCK_IN_DIGITS = re.compile(r"\s+\d{1,2}(?:\s*h(?:\d{2})?(?!\w)|\s+heures?(?!\w))")
_DIGITS_OF_THE_HOUR = re.compile(r"\s+\d{1,2}(?:h\d{0,2})?")


def _clock_after_a(source: str, tokens: list[Tok], index: int) -> int | None:
    """Where the words to fix end when the «a» at ``index`` is «à» in front of a clock time, else
    ``None``. A span is found by its words, so it runs on to the number: the line may hold a right
    «a» earlier. Closed on both sides: a day or time word in front, the hour and its end after."""

    tok = tokens[index]
    if tok.low != "a" or source[tok.start : tok.end] != "a" or index == 0:
        return None
    prev = tokens[index - 1]
    digits = _CLOCK_IN_DIGITS.match(source, tok.end)
    # «Rendez-vous a 18 heures.»: after this word only a time in digits is sure
    if not _space(source, prev, tok) or not (prev.low in _BEFORE_THE_CLOCK or (digits and prev.low == "rendez-vous")):
        return None
    if index > 1 and tokens[index - 2].low in _A_DAY_THAT_CAN_HAVE_HOURS and prev.low != "rendez-vous":
        return None
    following = tokens[index + 1 :]
    if digits:
        hour_end = digits.end()
        fix_end = _DIGITS_OF_THE_HOUR.match(source, tok.end).end()  # type: ignore[union-attr]
    else:
        if len(following) < 2 or not _space(source, tok, following[0]) or not _space(source, following[0], following[1]):
            return None
        if not _is_number_word(following[0].low) or following[1].low not in {"heures", "h"}:
            return None
        hour_end, fix_end = following[1].end, following[0].end
    after = next((other for other in following if other.start >= hour_end), None)
    if after is not None and not _CLAUSE_BREAK.search(source[hour_end : after.start]) and after.low not in _AFTER_THE_CLOCK:
        return None
    return fix_end


#: The adjectives that go in front of a noun, masculine form -> feminine. Closed on purpose: these
#: forms are never a noun or a verb in the lexicon, so a feminine article in front of one is an
#: article and the mistake can only be the adjective.
_FEMININE_OF_ADJECTIVE = {
    "bon": "bonne", "petit": "petite", "grand": "grande", "beau": "belle", "nouveau": "nouvelle", "vieux": "vieille",
    "gros": "grosse", "long": "longue", "mauvais": "mauvaise", "joli": "jolie", "premier": "première",
    "dernier": "dernière",
}  # fmt: skip
_FEMININE_ARTICLES = frozenset({"une", "la", "cette", "ma", "ta", "sa"})
#: «ma grand mère» is «grand-mère» without its hyphen, and no «grande mère» is meant.
_AFTER_THE_OLD_GRAND = frozenset({"mère", "mere", "tante", "messe", "rue", "route", "place", "peine", "chose", "voile"})


def _phrase_edits(source: str, tokens: list[Tok], add) -> None:
    """Rules over a few words at once: a negation around the verb, «de» after a modal,
    a doubled negation, «de» after a negated avoir, the locutions that need «de»,
    «à» after a verb, age with avoir, and the stressed pronoun after a preposition."""

    n = len(tokens)
    for i, tok in enumerate(tokens):
        prev = tokens[i - 1] if i > 0 else None
        nxt = tokens[i + 1] if i + 1 < n else None
        after = tokens[i + 2] if i + 2 < n else None
        written = source[tok.start : tok.end]

        # «je peux de venir» -> «je peux venir»
        if (
            tok.low in _BARE_INFINITIVE_VERBS
            and nxt is not None
            and nxt.low in {"de", "d"}
            and _joined(source, tok, nxt)
            and not (prev is not None and _joined(source, prev, tok) and prev.low in _REFLEXIVES)
        ):
            j = i + 2
            while j < n and j < i + 4 and tokens[j].low in _CLITICS_BEFORE_INFINITIVE and _joined(source, tokens[j - 1], tokens[j]):
                j += 1
            if (
                j < n
                and j > i + 1
                and _joined(source, tokens[j - 1], tokens[j])
                and _is_verb(tokens[j].low)
                and not source[tokens[j].start : tokens[j].end][:1].isupper()
            ):
                kept = source[tokens[i + 2].start : tokens[j].end]
                add(_edit("FR_BARE_INFINITIVE", source, nxt.start, tokens[j].end, kept,
                          word=tok.low, right=f"{tok.low} {kept}"))
                continue

        # «je ne mange pas jamais» -> «je ne mange jamais»; «Mais pas jamais.» (no «ne»)
        # answers «never?» and stays
        if (
            tok.low == "pas"
            and nxt is not None
            and nxt.low in _FULL_NEGATIONS
            and _space(source, tok, nxt)
            and any(t.low in {"ne", "n"} and _same_clause(source, t, tok) for t in tokens[max(0, i - 6) : i])
        ):
            right = _case(written, source[nxt.start : nxt.end])
            add(_edit("FR_DOUBLE_NEGATION", source, tok.start, nxt.end, right, word=nxt.low, right=right))
            continue

        # «je ne pas parle» -> «je ne parle pas» (an infinitive keeps «ne pas parler»)
        if (
            tok.low == "ne"
            and nxt is not None
            and after is not None
            and nxt.low in _NEGATION_WORDS
            and _space(source, tok, nxt)
            and _space(source, nxt, after)
            and _finite_verb(after.low)
            and not source[after.start : after.end][:1].isupper()
        ):
            right = f"{written} {source[after.start:after.end]} {source[nxt.start:nxt.end]}"
            add(_edit("FR_NEGATION_ORDER", source, tok.start, after.end, right, word=nxt.low, right=right))
            continue

        # «Je pas ai beaucoup bagages» -> «Je n'ai pas beaucoup bagages»: a subject pronoun, then
        # «pas», then a finite verb. «nous» and «vous» may be objects unless they open the clause.
        if (
            tok.low in _SUBJECT_PRONOUN_WORDS - {"j"}
            and nxt is not None
            and after is not None
            and nxt.low == "pas"
            and _space(source, tok, nxt)
            and _space(source, nxt, after)
            and (_finite_verb(after.low) or _verb_after_subject(after.low))
            and not source[after.start : after.end][:1].isupper()
            and not (prev is not None and _same_clause(source, prev, tok) and prev.low in _PREPOSITIONS)
            and not (tok.low in {"nous", "vous"} and prev is not None and _same_clause(source, prev, tok))
        ):
            verb = source[after.start : after.end]
            ne = f"n{_apostrophe(source)}{verb}" if _vowel_sound(after.low) else f"ne {verb}"
            right = f"{written} {ne} {source[nxt.start : nxt.end]}"
            add(_edit("FR_NEGATION_ORDER", source, tok.start, after.end, right, word="pas", right=right))
            continue

        # «je n'ai vu pas le film» -> «je n'ai pas vu le film» («personne» does go after
        # the participle: «je n'ai vu personne»)
        if (
            tok.low in _AVOIR_FORMS | {"suis", "es", "est", "sommes", "êtes", "sont"}
            and nxt is not None
            and after is not None
            and after.low in {"pas", "plus", "jamais", "rien"}
            and _space(source, tok, nxt)
            and _space(source, nxt, after)
            and _participle(nxt.low)
            and any(t.low in {"ne", "n"} for t in tokens[max(0, i - 3) : i])
        ):
            right = f"{written} {source[after.start:after.end]} {source[nxt.start:nxt.end]}"
            add(_edit("FR_NEGATION_AUX", source, tok.start, after.end, right, word=after.low, right=right))
            continue

        # «il n'y a pas du pain» -> «il n'y a pas de pain»
        if (
            tok.low in {"pas", "plus", "jamais"}
            and prev is not None
            and prev.low in _AVOIR_FORMS
            and _space(source, prev, tok)
            and any(t.low in {"ne", "n"} for t in tokens[max(0, i - 4) : i - 1])
            and nxt is not None
            and _space(source, tok, nxt)
        ):
            head_at = None
            if nxt.low in {"du", "des"}:
                head_at = i + 2
            elif nxt.low == "de" and after is not None and after.low == "la" and _space(source, nxt, after):
                head_at = i + 3
            head = tokens[head_at] if head_at is not None and head_at < n else None
            if (
                head is not None
                and _space(source, tokens[head_at - 1], head)
                and head.low not in {"tout", "moins", "moindre", "moindres"}
                and not source[head.start : head.end][:1].isupper()
                and (lemma := _noun_lemma(head.low)) is not None
                and _reads_as_noun(lemma)
                # «je n'ai pas du pain mais du riz»: a contrast keeps the article
                and not any(
                    t.low in {"mais", "plutôt", "sinon"} and _same_sentence(source, head, t)
                    for t in tokens[head_at + 1 :]
                )
            ):
                right = "de " + source[head.start : head.end]
                add(_edit("FR_PARTITIVE_NEG", source, nxt.start, head.end, right,
                          wrong=source[nxt.start : tokens[head_at - 1].end], right=right))
                continue

        # «en face la gare» -> «en face de la gare»; «avant partir» -> «avant de partir».
        # «regarder en face la réalité» stays: there «en face» says how, and «la
        # réalité» is the verb's object.
        if (
            prev is not None
            and (prev.low, tok.low) in _NEEDS_DE
            and not (i >= 2 and _verb_lemma(tokens[i - 2].low) in _EN_FACE_ADVERB_VERBS)
            and _space(source, prev, tok)
            and nxt is not None
            and _space(source, tok, nxt)
            and nxt.low in _DETERMINERS
            and not (after is not None and after.low in {"plus", "moins", "mieux", "meilleur", "pire"})
        ):  # «au lieu le plus proche» is a place
            right = f"{source[prev.start:tok.end]} de"
            add(_edit("FR_MISSING_DE", source, prev.start, tok.end, right,
                      word=source[prev.start:tok.end].casefold(), right=right))
            continue
        if (
            tok.low == "avant"
            and nxt is not None
            and _space(source, tok, nxt)
            and _is_verb(nxt.low)
            and not _is_noun(nxt.low)
            and not source[nxt.start : nxt.end][:1].isupper()
        ):
            right = f"{written} de"
            add(_edit("FR_MISSING_DE", source, tok.start, tok.end, right, word="avant", right=right))
            continue

        # «je vais a Paris» -> «je vais à Paris»: right after a subject and its verb (or an
        # auxiliary and its participle: «je suis allé a Lyon»), «a» cannot be avoir
        if (
            tok.low == "a"
            and written == "a"
            and prev is not None
            and i >= 2
            and _joined(source, tokens[i - 2], prev)
            and _space(source, prev, tok)
            and (
                (
                    (tokens[i - 2].low in _SUBJECT_PRONOUN_WORDS or tokens[i - 2].low == "c")
                    # after a subject pronoun «reste», «porte» are the verbs
                    and (_finite_verb(prev.low) or _verb_after_subject(prev.low))
                )
                or (tokens[i - 2].low in _AUXILIARY_FORMS and _participle(prev.low))
            )
            and nxt is not None
            and _same_clause(source, tok, nxt)
            # «le projet auquel je croyais a échoué»: that «a» belongs to the main clause
            and not _participle(nxt.low)
            and not any(t.low in _RELATIVES and _same_sentence(source, t, tok) for t in tokens[max(0, i - 8) : i - 2])
        ):
            add(_edit("FR_A_GRAVE", source, tok.start, tok.end, "à", right="à"))
            continue

        # «une bon offre» -> «une bonne offre». Silent when the noun's gender isn't known, or a
        # masculine noun says the article is the mistake («une bon gâteau»).
        if (
            tok.low in _FEMININE_ARTICLES
            and nxt is not None
            and after is not None
            and source[nxt.start : nxt.end] in _FEMININE_OF_ADJECTIVE
            and _space(source, tok, nxt)
            and _space(source, nxt, after)
            and source[after.start : after.end] == after.low
            and after.low not in _TWO_GENDER_NOUNS
            and _noun_gender(after.low) == "f"
            and not (nxt.low == "grand" and after.low in _AFTER_THE_OLD_GRAND)
        ):
            right = f"{written} {_FEMININE_OF_ADJECTIVE[nxt.low]}"
            add(_edit("FR_ADJ_AGREE", source, tok.start, nxt.end, right, noun=after.low,
                      right=f"{_FEMININE_OF_ADJECTIVE[nxt.low]} {after.low}", wrong=f"{nxt.low} {after.low}"))
            continue

        # «jeudi a dix-huit heures» -> «jeudi à dix-huit heures»
        clock_end = _clock_after_a(source, tokens, i)
        if clock_end is not None:
            right = "à" + source[tok.end : clock_end]
            add(_edit("FR_A_GRAVE", source, tok.start, clock_end, right, right=right))
            continue

        # «je suis vingt ans» -> «j'ai vingt ans»
        if tok.low in _ETRE_TO_AVOIR and prev is not None and prev.low in _SUBJECT_PRONOUN_WORDS - {"j"} and _space(source, prev, tok):
            ans = None
            if nxt is not None and _space(source, tok, nxt) and _is_number_word(nxt.low) and after is not None and _space(source, nxt, after):
                ans = after
            elif nxt is not None and _NUMBER_GAP.fullmatch(source[tok.end : nxt.start] or ""):
                ans = nxt
            if ans is not None and ans.low in {"an", "ans"}:
                k = tokens.index(ans)
                follow = tokens[k + 1] if k + 1 < n else None
                if follow is None or not _same_clause(source, ans, follow) or follow.low not in {
                    "plus", "moins", "de", "d", "après", "avant", "que", "qu", "trop"
                }:
                    avoir = _ETRE_TO_AVOIR[tok.low]
                    pronoun = source[prev.start : prev.end]
                    age = " ".join(source[tok.end : ans.end].split())
                    if prev.low == "je":
                        apostrophe = "’" if "’" in source else "'"
                        right = _case(pronoun, "j") + apostrophe + avoir
                        add(_edit("FR_ETRE_AGE", source, prev.start, tok.end, right, right=f"{right} {age}"))
                    else:
                        right = _case(written, avoir)
                        add(_edit("FR_ETRE_AGE", source, tok.start, tok.end, right, right=f"{pronoun} {right} {age}"))
                    continue

        # #749: «Elle a fait un signe à moi» -> «Elle m'a fait un signe»
        if tok.low == "à" and nxt is not None and nxt.low in _OBJECT_CLITIC_OF:
            object_edit = _object_pronoun_edit(source, tokens, i)
            if object_edit is not None:
                add(object_edit)
                continue

        # «c'est je» -> «c'est moi»; «chez il» -> «chez lui»
        if tok.low in _STRESSED and prev is not None and _space(source, prev, tok):
            stressed_slot = False
            if prev.low == "est" and i >= 2 and tokens[i - 2].low == "c" and source[tokens[i - 2].end : prev.start] in {"'", "’"}:
                stressed_slot = nxt is None or not _same_clause(source, tok, nxt) or nxt.low == "qui"
            elif prev.low in _STRESSED_PREPOSITIONS:
                stressed_slot = nxt is None or not _same_clause(source, tok, nxt) or not (
                    nxt.low in _CLITIC_CONTEXT or nxt.low in _FORM_LEMMA or _could_be_verb(nxt.low)
                )
            if stressed_slot:
                right = _case(written, _STRESSED[tok.low])
                add(_edit("FR_STRESSED_PRONOUN", source, tok.start, tok.end, right,
                          word=prev.low if prev.low != "est" else "c’est", right=right))
                continue

        # «des journals» -> «des journaux»; «des gâteaus» -> «des gâteaux»
        if tok.low.endswith(("als", "eaus", "eus", "aus")) and _lemma(tok.low) is None and _forms().get(tok.low) is None:
            singular = tok.low[:-1]
            if _is_noun(singular) and singular not in _AL_PLURAL_S and singular not in _X_PLURAL_S:
                plural = _plural(singular)
                if plural and plural != tok.low:
                    right = _case(written, plural)
                    add(_edit("FR_PLURAL_FORM", source, tok.start, tok.end, right, noun=singular, right=right))
                    continue

        # «tout la semaine» -> «toute la semaine»; «toute le jour» -> «tout le jour»;
        # «tout les jours» -> «tous les jours». «tous / toutes les» stay: «elles ont
        # toutes les cheveux longs» agrees with «elles», not with the noun.
        if (
            tok.low in {"tout", "toute"}
            and nxt is not None
            and after is not None
            and _space(source, tok, nxt)
            and _joined(source, nxt, after)
            and nxt.low in {"le", "la", "l", "un", "une", "les"}
            and not source[after.start : after.end][:1].isupper()
        ):
            want = None
            if nxt.low == "les":
                lemma = _noun_lemma(after.low)
                gender = _noun_gender(lemma) if lemma and lemma not in _TWO_GENDER_NOUNS else None
                if tok.low == "tout" and gender in {"m", "f"}:
                    want = "tous" if gender == "m" else "toutes"
            elif after.low not in _TWO_GENDER_NOUNS:
                gender = _noun_gender(after.low)
                article_fits = (gender == "f" and nxt.low in {"la", "l", "une"}) or (
                    gender == "m" and nxt.low in {"le", "l", "un"}
                )
                if article_fits:
                    want = "toute" if gender == "f" else "tout"
            if want and want != tok.low:
                right = _case(written, want)
                phrase = f"{want} {source[nxt.start:after.end]}"
                add(_edit("FR_GENDER_DET", source, tok.start, tok.end, right, noun=after.low,
                          gender=_noun_gender(_noun_lemma(after.low) or after.low) or "", right=phrase,
                          wrong=source[tok.start:after.end]))
                continue


def deterministic_edits(
    text: object,
    *,
    people: Mapping[str, str] | None = None,
) -> list[Edit]:
    """Mistakes found without a model, in reading order, non-overlapping.

    ``people`` maps a known cast first name (casefolded) to ``"f"``/``"m"``; the
    default is the cast registry. The learner's own gender is never read: a first
    or second person subject leaves the participle as written.

    Every edit is *settled* before it is returned: its replacement is put back into
    the sentence and checked by the same rules, so a fix never teaches a new mistake
    (#318: «la appartement» became «le appartement», which the pass itself would flag
    as a missing elision). A replacement the rules flag again is completed by them
    («d'ecole» -> «d'école»), or dropped when it does not settle.
    """

    source = "" if text is None else str(text)
    if not source.strip():
        return []
    cast = known_people() if people is None else {k.casefold(): v for k, v in people.items()}
    settled: list[Edit] = []
    for edit in _raw_edits(source, cast):
        final = _settle(source, edit, cast)
        if final is None or is_variant_edit(final.span, final.replacement):
            continue  # package V: a fix between two accepted spellings corrects nothing
        if any(final.start < other.end and other.start < final.end for other in settled):
            continue
        settled.append(final)
    settled.sort(key=lambda e: e.start)
    return _found_by_their_words(source, settled)


def _found_by_their_words(source: str, edits: list[Edit]) -> list[Edit]:
    """Each edit with a neighbouring word when its words are also somewhere earlier in the line.

    An erratum keeps no offsets and a span is found by its words, so «a» -> «à» in «Camille a une
    clé et je vais a Paris» lands on the first «a», which is right. The word in front is taken
    when it is free, else the word after it. An edit no free word can tell apart is dropped: a
    fix that lands on a right word is worse than none."""

    words = _line_words(source)
    named: list[Edit] = []
    for index, edit in enumerate(edits):
        floor = named[-1].end if named else 0
        ceiling = edits[index + 1].start if index + 1 < len(edits) else len(source)
        start, end = edit.start, edit.end
        while (first := span_pattern(source[start:end]).search(source)) is not None and first.start() != start:
            before = [word for word in words if floor <= word[0] and word[1] <= start]
            following = [word for word in words if end <= word[0] and word[1] <= ceiling]
            if before:
                start = before[-1][0]
            elif following:
                end = following[0][1]
            else:
                start = -1
                break
        if start < 0:
            continue
        if (start, end) != (edit.start, edit.end):
            right = source[start : edit.start] + edit.replacement + source[edit.end : end]
            edit = replace(edit, span=source[start:end], replacement=right, start=start, end=end)
        named.append(edit)
    return named


def _settle(source: str, edit: Edit, cast: Mapping[str, str], depth: int = 0) -> Edit | None:
    """``edit`` once its replacement passes the rules in place, or ``None``.

    The replacement is spliced into the sentence and the raw rules run again; an edit
    they find inside (or across the edge of) the replaced region is folded into this
    one. Two rounds at most: a fix that still does not settle is not shown."""

    region_start, region_end = edit.start, edit.start + len(edit.replacement)
    context = source[: edit.start] + edit.replacement + source[edit.end :]
    inner = [e for e in _raw_edits(context, cast) if e.start < region_end and region_start < e.end]
    if not inner:
        return edit
    if depth >= 2:
        return None
    low = min([region_start, *(e.start for e in inner)])
    high = max([region_end, *(e.end for e in inner)])
    fixed = apply_edits(context, inner)
    delta = sum(len(e.replacement) - (e.end - e.start) for e in inner)
    replacement = fixed[low : high + delta]
    end = high - region_end + edit.end
    span = source[low:end]
    if _norm(span) == _norm(replacement):
        return None
    note = {lang: _requote(text, edit.replacement, replacement) for lang, text in edit.note.items()}
    composed = replace(edit, span=span, replacement=replacement, start=low, end=end, note=note)
    return _settle(source, composed, cast, depth + 1)


_OPEN_QUOTES = "«“\"‘'"
_UNQUOTED = "»”\"’'"


def _requote(note: str, old: str, new: str) -> str:
    """``note`` quoting ``new`` where it quoted ``old`` («« le appartement »» ->
    «« l'appartement »»). Only quoted words change: a short fix like «de» or «à» is
    never replaced inside the rest of the explanation."""
    if not note or not old or old == new:
        return note
    pattern = re.compile(f"([{_OPEN_QUOTES}]\\s*){re.escape(old)}(\\s*[{_UNQUOTED}])")
    out, count = pattern.subn(lambda m: m.group(1) + new + m.group(2), note)
    if count or len(old) < 4:
        return out
    return re.sub(rf"(?<!\w){re.escape(old)}(?!\w)", new, note)


def repair_text(text: object, *, people: Mapping[str, str] | None = None) -> str:
    """``text`` with every model-free correction applied: the check a model's whole
    corrected sentence goes through before the learner copies it (#318)."""
    source = "" if text is None else str(text)
    return apply_edits(source, deterministic_edits(source, people=people))


def _raw_edits(source: str, cast: Mapping[str, str]) -> list[Edit]:
    """One pass of the rules over ``source``, before any edit is settled."""

    tokens = _tokens(source)
    found: list[Edit] = []
    cited = _cited_stretches(source)

    def add(edit: Edit | None) -> None:
        if edit is None:
            return
        if any(edit.start < end and start < edit.end for start, end in cited):
            return
        if any(edit.start < other.end and other.start < edit.end for other in found):
            return
        found.append(edit)

    for i, tok in enumerate(tokens):
        nxt = tokens[i + 1] if i + 1 < len(tokens) else None
        prev = tokens[i - 1] if i > 0 else None
        joined_next = nxt is not None and _joined(source, tok, nxt)
        joined_prev = prev is not None and _joined(source, prev, tok)

        # --- the dropped apostrophe: «c est», «Qu est-ce», «s il te plaît», «d Odile» ---
        dropped = _dropped_apostrophe(source, tokens, i)
        if dropped is not None:
            start, end, glued = dropped
            add(_edit("FR_APOSTROPHE", source, start, end, glued, right=glued))
            continue

        # --- person of être / avoir / aller after a plain subject pronoun -------------
        if tok.low in _FORM_PERSONS and prev is not None and joined_prev:
            person = _subject_person(tokens, source, i)
            persons = _FORM_PERSONS[tok.low]
            if person is not None and person not in persons:
                lemma = _FORM_LEMMA[tok.low]
                right = _PERSON_FORMS[lemma][person]
                pronoun = source[prev.start : prev.end]
                if prev.low == "je" and right[0] in "aeiouhéèê":
                    apostrophe = "’" if "’" in source else "'"
                    glued = _case(pronoun, "j") + apostrophe + right
                    add(_edit("FR_PERSON_AUX", source, prev.start, tok.end, glued,
                              subject=pronoun.casefold(), right=glued))
                else:
                    add(_edit("FR_PERSON_AUX", source, tok.start, tok.end,
                              _case(source[tok.start:tok.end], right), subject=pronoun.casefold(), right=right))
                continue

        # --- être-verbs conjugated with avoir; agreement after être ------------------
        if joined_next and nxt is not None:
            aux_is_avoir = tok.low in _AVOIR_TO_ETRE
            participle = nxt.low
            if aux_is_avoir and participle in _ETRE_PARTICIPLES and _same_clause(source, tok, nxt):
                after = tokens[i + 2] if i + 2 < len(tokens) else None
                clause_ends = after is None or not _same_clause(source, nxt, after)
                if participle in _AMBIGUOUS_PARTICIPLES and (
                    not (clause_ends or (_joined(source, nxt, after) and after.low in _PLACE_WORDS))
                    or (prev is not None and joined_prev and prev.low in _OBJECT_CLITICS)
                ):
                    continue
                gender, plural = _subject_gender(tokens, source, i, cast)
                plural = plural or tok.low in {"ont", "avons"}
                start = tok.start
                prefix = ""
                if prev is not None and joined_prev and prev.low == "j":
                    start, prefix = prev.start, _case(source[prev.start : prev.end], "je") + " "
                right_aux = _AVOIR_TO_ETRE[tok.low]
                right_part = _agree(participle, gender, plural) if tok.low != "avez" else participle
                original_part = source[nxt.start : nxt.end]
                right_part = _case(original_part, right_part) if original_part[:1].isupper() else right_part
                replacement = prefix + _case(source[tok.start:tok.end], right_aux) + " " + right_part
                add(_edit("FR_AUX_ETRE", source, start, nxt.end, replacement, part=participle,
                          right=replacement, wrong=source[start:nxt.end]))
                continue
            if tok.low in {"est", "sont", "suis", "es", "sommes", "êtes"} and participle in _ETRE_PARTICIPLES:
                gender, plural = _subject_gender(tokens, source, i, cast)
                if gender == "f" or plural:
                    agreed = _agree(participle, gender, plural)
                    if agreed != participle:
                        add(_edit("FR_PARTICIPLE_AGREE", source, nxt.start, nxt.end, agreed, right=agreed))
                continue

        # --- aller + participle (near future wants the infinitive) --------------------
        if tok.low in _PERSON_FORMS["aller"].values() and joined_next and nxt is not None:
            w = nxt.low
            if len(w) >= 4 and w.endswith("é") and w not in {"été"} and _is_verb(w[:-1] + "er"):
                add(_edit("FR_ALLER_INF", source, nxt.start, nxt.end, _case(source[nxt.start:nxt.end], w[:-1] + "er"), right=w[:-1] + "er"))
                continue

        # --- first person -dre verbs: «je vend» -> «je vends» ------------------------
        if tok.low in _DRE_FIRST_PERSON and prev is not None and joined_prev and prev.low in {"je", "j", "tu"}:
            fixed = _DRE_FIRST_PERSON[tok.low]
            add(_edit("FR_VERB_DRE_S", source, tok.start, tok.end, _case(source[tok.start:tok.end], fixed),
                      subject="j’" if prev.low == "j" else prev.low, right=fixed))
            continue

        glued_before = prev is not None and source[prev.end : tok.start] in {"'", "’"}

        # --- elision: «la appartement», «de Odile», «je ai», «si il», «ce est» ----------
        # First: an article that elides says nothing about the noun's gender («la
        # appartement» is «l'appartement», never «le appartement», #318).
        if not glued_before and not (
            tok.low == "je" and nxt is not None and nxt.low in _FORM_PERSONS and "1sg" not in _FORM_PERSONS[nxt.low]
        ):  # «je a» is the person rule's «j'ai», not «j'a»
            elided = _elision(source, tokens, i)
            if elided is not None:
                end, glued = elided
                add(_edit("FR_ELISION", source, tok.start, end, glued, right=glued,
                          word=source[tok.start:tok.end].casefold()))
                continue

        # --- determiner / noun gender --------------------------------------------------
        if joined_next and nxt is not None and tok.low in (_MASC_DET.keys() | _FEM_DET.keys()):
            vowel = _vowel_sound(nxt.low)
            if glued_before:
                pass  # «quelqu'un veille»: the «un» belongs to the word before it
            elif tok.low in {"le", "la"} and vowel:
                pass  # elided above, or a pronoun in front of a verb: never a gender
            elif tok.low in {"le", "la"} and prev is not None and joined_prev and (
                prev.low in _PRONOUN_CONTEXT or _names_a_subject(source, prev)
            ):
                pass  # «je la porte», «Lila le porte»: a pronoun, not a determiner
            elif _is_verb(nxt.low) or nxt.low in _TWO_GENDER_NOUNS:
                pass  # «la manger» (a pronoun); «la tour» / «le tour», «une enfant»
            else:
                gender = _noun_gender(nxt.low)
                if gender == "f" and tok.low in _MASC_DET:
                    if not (tok.low in {"mon", "ton", "son"} and vowel):
                        right = _MASC_DET[tok.low]
                        add(_edit("FR_GENDER_DET", source, tok.start, tok.end, _case(source[tok.start:tok.end], right),
                                  noun=nxt.low, gender="f", right=f"{right} {nxt.low}", wrong=f"{tok.low} {nxt.low}"))
                        continue
                elif gender == "m" and tok.low in _FEM_DET:
                    # «cette appartement» -> «cet appartement»; «ma ami» -> «mon ami»
                    right = "cet" if tok.low == "cette" and vowel else _FEM_DET[tok.low]
                    add(_edit("FR_GENDER_DET", source, tok.start, tok.end, _case(source[tok.start:tok.end], right),
                              noun=nxt.low, gender="m", right=f"{right} {nxt.low}", wrong=f"{tok.low} {nxt.low}"))
                    continue

        # --- «ce ami» -> «cet ami»; «ma amie» -> «mon amie» ---------------------------
        if (
            joined_next
            and nxt is not None
            and not glued_before
            and tok.low in {"ce", "ma", "ta", "sa"}
            and _vowel_sound(nxt.low)
            and not source[nxt.start : nxt.end][:1].isupper()
            and _pos(nxt.low) in {"noun", "adjective"}
        ):
            if tok.low == "ce" and _noun_gender(nxt.low) != "f":
                add(_edit("FR_CET", source, tok.start, tok.end, _case(source[tok.start:tok.end], "cet"),
                          right=f"cet {nxt.low}", wrong=f"ce {nxt.low}"))
                continue
            if tok.low in {"ma", "ta", "sa"}:
                det = {"ma": "mon", "ta": "ton", "sa": "son"}[tok.low]
                add(_edit("FR_MON_VOWEL", source, tok.start, tok.end, _case(source[tok.start:tok.end], det),
                          det=det, right=f"{det} {nxt.low}", wrong=tok.low))
                continue

        # --- de le / à le; de les / à les ---------------------------------------------
        if tok.low in {"de", "à"} and joined_next and nxt is not None and nxt.low in {"le", "les"}:
            after = tokens[i + 2] if i + 2 < len(tokens) else None
            if nxt.low == "le":
                fires = (
                    after is not None
                    and _joined(source, nxt, after)
                    and not _is_verb(after.low)  # «de le vendre»: «le» is a pronoun
                    and not _vowel_sound(after.low)  # «à le hôtel» is «à l'hôtel», elided
                    and after.low not in _TWO_GENDER_NOUNS
                    and _noun_gender(after.low) == "m"
                )
                right = "du" if tok.low == "de" else "au"
            else:
                head = _noun_lemma(after.low) if after is not None else None
                fires = (
                    after is not None
                    and _joined(source, nxt, after)
                    and not source[after.start : after.end][:1].isupper()
                    and (
                        (head is not None and _reads_as_noun(head))
                        or (_pos(after.low) == "adjective" and not _could_be_verb(after.low))
                    )
                )  # «de les voir», «à les aider»: «les» is a pronoun there
                right = "des" if tok.low == "de" else "aux"
            if fires:
                add(_edit("FR_CONTRACTION", source, tok.start, nxt.end, _case(source[tok.start:tok.end], right),
                          right=right, wrong=f"{tok.low} {nxt.low}"))
                continue

        # --- plural determiner + singular noun: «les livre» -> «les livres» ----------
        if (
            joined_next
            and nxt is not None
            and not glued_before
            and (tok.low in _PLURAL_DETS or _is_compound_number(tok.low))
            and _same_clause(source, tok, nxt)
        ):
            written_noun = source[nxt.start : nxt.end]
            # «je les livre», «Marin les porte», «je veux les garder»: «les» is a pronoun
            pronoun_les = tok.low == "les" and prev is not None and joined_prev and (
                prev.low in _PRONOUN_CONTEXT
                or _names_a_subject(source, prev)
                or (
                    _could_be_verb(prev.low)
                    and _could_be_verb(nxt.low)
                    # «j'ai les livre»: «les» after être / avoir / aller is an article
                    # unless an infinitive follows («je vais les livrer»)
                    and (prev.low not in _FORM_LEMMA or _is_verb(nxt.low))
                )
            )
            plural = _plural(nxt.low)
            if (
                not pronoun_les
                and not written_noun[:1].isupper()
                and plural is not None
                and plural != nxt.low
                and _reads_as_noun(nxt.low)
                and not (tok.low == "des" and nxt.low in _MASS_NOUNS)
                and nxt.low not in _CALENDAR
            ):
                add(_edit("FR_PLURAL_NOUN", source, nxt.start, nxt.end, _case(written_noun, plural),
                          det=tok.low, right=f"{tok.low} {plural}", wrong=f"{tok.low} {nxt.low}"))
                continue

        # --- missing accents, misspellings, the family hyphen --------------------------
        # A word in capitals inside a sentence that is not is an acronym («Le CA se
        # réunit»), not «ça» typed without its cedilla.
        written = source[tok.start:tok.end]
        acronym = written.isupper() and len(written) > 1 and not source.isupper()
        # «le Grand Hotel», «son ami Andre»: a capital inside a sentence is a name. «En anglais,
        # hotel s'écrit sans accent», «Das Hotel ist schön»: this word isn't French.
        not_french = (tok.low in _ACCENTS or tok.low in _MISSPELLINGS) and (
            (written[:1].isupper() and not source.isupper() and not _starts_sentence(source, tok))
            or _in_another_language(source, tokens, i)
        )
        if tok.low in _ACCENTS and not acronym and not not_french:
            right = _ACCENTS[tok.low]
            add(_edit("FR_ACCENT", source, tok.start, tok.end, _case(source[tok.start:tok.end], right), right=right))
            continue
        if (
            tok.low in _MISSPELLINGS
            and not acronym
            and not not_french
            and (not glued_before or (prev is not None and prev.low in _ELIDED_BEFORE_A_WORD))
            and _lemma(tok.low) is None
            and _forms().get(tok.low) is None
            and not (nxt is not None and source[tok.end : nxt.start] in {"'", "’", "-"})
            and not (tok.low in _PARTICIPLE_LOOKALIKES and prev is not None and prev.low in _AVOIR_FORMS)
            # «Jai Paul»: a capital, then a capital, is somebody's name
            and not (written[:1].isupper() and nxt is not None and source[nxt.start : nxt.start + 1].isupper())
            and not (
                tok.low in _GLUED_NEGATIONS
                and not any(t.low in _NEGATION_PARTNERS and _same_clause(source, tok, t) for t in tokens[i + 1 : i + 6])
            )
            and not (tok.low == "sil" and (written != "sil" or nxt is None or nxt.low not in _AFTER_GLUED_SIL))
        ):
            right = _MISSPELLINGS[tok.low]
            if right[:1].islower():
                right = _case(written, right)
            if "’" not in source:
                right = right.replace("’", "'")
            add(_edit("FR_SPELLING", source, tok.start, tok.end, right, right=right))
            continue
        if (
            joined_next
            and nxt is not None
            and (tok.low, nxt.low) in _HYPHENATED
            and source[tok.end : nxt.start] == " "
        ):
            right = _case(written, _HYPHENATED[(tok.low, nxt.low)])
            add(_edit("FR_SPELLING", source, tok.start, nxt.end, right, right=right))
            continue
        # «cle» -> «clé», «decembre» -> «décembre»: the one word this spelling can be
        fold = _accent_fold(tok.low)
        if (
            fold is not None
            and not acronym
            and not (written[:1].isupper() and not source.isupper() and not _starts_sentence(source, tok))
            and not (written[:1].isupper() and nxt is not None and source[nxt.start : nxt.start + 1].isupper())
            and not (glued_before and (prev is None or prev.low not in _ELIDED_BEFORE_A_WORD))
            and not (nxt is not None and source[tok.end : nxt.start] in {"'", "’"})
            and not _in_another_language(source, tokens, i)
        ):
            add(_edit("FR_ACCENT", source, tok.start, tok.end, _case(written, fold), right=fold))
            continue

    _phrase_edits(source, tokens, add)
    _tense_edits(source, tokens, cast, add)
    _known_slip_edit(source, add)
    found.sort(key=lambda e: e.start)
    return found


def _known_slip_edit(text: str, add) -> None:
    """#193: «Je suis froid / faim / soif / peur / sommeil» -> «J'ai …», on every
    surface (``answer_acceptance.known_slip`` holds the unambiguous cases)."""

    notes = {lang: known_slip(text, lang) for lang in ("en", "de", "fr")}
    first = notes["en"]
    if first is None:
        return
    span, fix, _ = first
    match = re.search(r"\s+".join(re.escape(part) for part in span.split()), text.translate(_APOSTROPHES), re.IGNORECASE)
    if match is None:
        return
    original = text[match.start() : match.end()]
    replacement = fix if original[:1].isupper() else fix[:1].lower() + fix[1:]
    add(
        Edit(
            span=original,
            replacement=replacement,
            rule_id="FR_AVOIR_STATE",
            label=_RULE_TEXT["FR_PERSON_AUX"]["label"],
            note={lang: slip[2] for lang, slip in notes.items() if slip},
            start=match.start(),
            end=match.end(),
            task_error_type="verb_conjugation",
            severity=2,
        )
    )


def _first_sentence_end(text: str, tokens: list[Tok]) -> int:
    for i in range(1, len(tokens)):
        if not _same_sentence(text, tokens[i - 1], tokens[i]):
            return i
    return len(tokens)


def _tense_edits(text: str, tokens: list[Tok], cast: Mapping[str, str], add) -> None:
    """A present-tense verb coordinated onto a passé composé: «Lila a rentré … et
    elle mange» -> «et elle a mangé». Lexicon-gated: the infinitive must exist."""

    n = len(tokens)
    sentence_start = 0
    for i, tok in enumerate(tokens):
        if i > 0 and not _same_sentence(text, tokens[i - 1], tok):
            sentence_start = i
        if i < 2 or i + 1 >= n:
            continue
        if tok.low not in {"et", "puis"} and not (tok.low == "mais"):
            continue
        pron = tokens[i + 1]
        verb = tokens[i + 2] if i + 2 < n else None
        if verb is None or pron.low not in {"il", "elle", "on", "ils", "elles"}:
            continue
        if not (_joined(text, tok, pron) and _joined(text, pron, verb) and _same_sentence(text, tok, verb)):
            continue
        sentence = tokens[sentence_start:i]
        words = {t.low for t in tokens[sentence_start:]}
        if words & _PRESENT_MARKERS:
            continue
        # A present after a passé composé is very often right («J'ai fini et elle
        # regarde la télé»). It is a slip only when the story is told in the past:
        # «puis» (a next event), or a past time word in the sentence or opening the
        # text («Hier, …» — the Journal's retelling).
        anchored = tok.low == "puis" or bool(
            ({t.low for t in sentence} | {t.low for t in tokens[: _first_sentence_end(text, tokens)]}) & _PAST_MARKERS
        )
        if not anchored:
            continue
        # a passé composé earlier in the same sentence, in its main clause: «on montre
        # qu'on a entendu l'objection, puis on explique» narrates nothing
        has_pc = False
        for j in range(len(sentence) - 1):
            a, b = sentence[j], sentence[j + 1]
            if not _joined(text, a, b):
                continue
            if any(t.low in _SUBORDINATORS for t in sentence[max(0, j - 3) : j]):
                continue
            if a.low in _AVOIR_TO_ETRE and (
                b.low in _PC_PARTICIPLES or b.low in _ETRE_PARTICIPLES
                or (len(b.low) >= 4 and b.low.endswith("é") and _is_verb(b.low[:-1] + "er"))
            ):
                has_pc = True
                break
            if a.low in {"est", "sont", "suis", "es", "sommes", "êtes"} and b.low in _ETRE_PARTICIPLES:
                has_pc = True
                break
        if not has_pc:
            continue
        plural = pron.low in {"ils", "elles"}
        low = verb.low
        if plural:
            if not low.endswith("ent") or len(low) < 6:
                continue
            stem = low[:-3]
        else:
            if not low.endswith("e") or len(low) < 4:
                continue
            stem = low[:-1]
        infinitive = stem + "er"
        if not _is_verb(infinitive) or low in {"être", "mène"} or infinitive in _STATE_VERBS:
            continue
        participle = stem + "é"
        gender = "f" if pron.low in {"elle", "elles"} else None
        if participle in _ETRE_PARTICIPLES:
            aux = "sont" if plural else "est"
            participle = _agree(participle, gender, plural)
        else:
            aux = "ont" if plural else "a"
        right = f"{aux} {participle}"
        add(_edit("FR_TENSE_PC", text, verb.start, verb.end, right, right=f"{text[pron.start:pron.end]} {right}"))


# ---------------------------------------------------------------------------
# Reconciling the model with the deterministic pass
# ---------------------------------------------------------------------------


def to_erratum(edit: Edit, *, language: str | None = None) -> dict[str, Any]:
    """The erratum dict the Courrier, the Journal and the error memory share."""
    return {
        "display_label": edit.label_for(language),
        "learner_text": edit.span,
        "corrected_target": edit.replacement,
        "why_wrong": edit.note_for(language),
        "repair_hint": edit.note_for(language),
        "severity": edit.severity,
        "recurring": False,
        "task_error_type": edit.task_error_type,
        "external_id": edit.rule_id,
        "source": "deterministic",
    }


def apply_edits(text: str, edits: Iterable[Edit]) -> str:
    """``text`` with the edits applied (reading order, non-overlapping)."""
    out = "" if text is None else str(text)
    for edit in sorted(edits, key=lambda e: e.start, reverse=True):
        if out[edit.start : edit.end] == edit.span:
            out = out[: edit.start] + edit.replacement + out[edit.end :]
    return out


def deterministic_errata(
    text: object, *, language: str | None = None, people: Mapping[str, str] | None = None
) -> list[dict[str, Any]]:
    return [to_erratum(edit, language=language) for edit in deterministic_edits(text, people=people)]


#: #119: the unit that teaches «l'» and «d'» in front of a vowel («Le, la, l', les»).
ARTICLE_ELISION_UNIT = "FR2_A11_LE_LA"


def elides_an_article(learner_text: object, corrected_text: object, context: object = None) -> bool:
    """#119: whether a correction elides an article or «de»: «la appartement» →
    «l'appartement», «le hôtel» → «l'hôtel», «de Odile» → «d'Odile».

    Read off the pair, whoever wrote it (this contract or a model): the learner wrote
    «le», «la» or «de», a space and a word, and the correction glues «l'» or «d'» to
    that same word. «le» / «la» are the article only in front of a noun the lexicon
    knows, and not after a subject or another pronoun: «je le aime» → «je l'aime» is
    an object pronoun, not the article rule's. The contract's own errata quote only
    «le aime», so ``context`` (the learner's whole text) supplies the word before it.
    """

    wrong, right = _norm(learner_text), _norm(corrected_text)
    tokens = _tokens(wrong)
    for i, tok in enumerate(tokens[:-1]):
        if tok.low not in {"le", "la", "de"}:
            continue
        nxt = tokens[i + 1]
        if wrong[tok.end : nxt.start].strip(" \u00a0") != "" or wrong[tok.end : nxt.start] == "":
            continue  # only a plain space: «l'», «de-», a comma are not this slip
        if i > 0 and wrong[tokens[i - 1].end : tok.start] in {"'", "-"}:
            continue  # part of a longer word («aujourd'hui»)
        if tok.low != "de" and not _an_article_before(wrong, tokens, i, context):
            continue
        glued = "d" if tok.low == "de" else "l"
        if re.search(rf"(?<![^\W\d_]){glued}'\s?{re.escape(wrong[nxt.start : nxt.end])}(?![^\W\d_])", right, re.IGNORECASE):
            return True
    return False


#: The three contractions that always merge a preposition with a definite article:
#: «au» = à + le, «aux» = à + les, «du» = de + le. («des» is left out on purpose: it is
#: also the indefinite plural, «des livres», where no «de + les» is meant.)
_CONTRACTIONS: dict[str, tuple[str, str]] = {"au": ("à", "le"), "aux": ("à", "les"), "du": ("de", "le")}
_CONTRACTION_REASON = {
    "en": "« {right} » is {pre} + {art} joined into one word.",
    "de": "« {right} » verschmilzt aus {pre} + {art} zu einem Wort.",
    "fr": "« {right} » : {pre} + {art} se contracte en un seul mot.",
}


def _fold_accents(word: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", word) if not unicodedata.combining(c))


def contraction_reason(learner_text: object, expected_text: object, *, language: str | None = None) -> str | None:
    """#501: the one-line reason when a miss is a contraction: the learner wrote
    «a» (or «de») where the line has «au» / «aux» / «du».

    Read off the pair, in the learner's language, so a feedback line can say *why*
    («à + le» -> «au») and not only *what* («a Mistral» -> «au Mistral»). ``None``
    when the miss is anything else: the caller keeps its own note.
    """

    learner = [t.low for t in _tokens(_norm(learner_text))]
    expected = [t.low for t in _tokens(_norm(expected_text))]
    folded = [_fold_accents(word) for word in learner]
    matcher = difflib.SequenceMatcher(a=folded, b=[_fold_accents(word) for word in expected], autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag != "replace":
            continue
        for word in expected[j1:j2]:
            pair = _CONTRACTIONS.get(word)
            if pair is None or _fold_accents(pair[0]) not in folded[i1:i2]:
                continue
            return _pick(_CONTRACTION_REASON, language).format(right=word, pre=pair[0], art=pair[1])
    return None


def _an_article_before(wrong: str, tokens: list[Tok], index: int, context: object) -> bool:
    """Is ``tokens[index]`` («le» / «la») the article of the word after it?

    Not after a subject or another pronoun («je le aime», «il me la a donnée»), read
    from the pair or, when the pair starts with it, from ``context``; and only in
    front of a noun the lexicon knows: «je vais le acheter» is a pronoun before a
    verb, and a word the lexicon does not know is left to the corrector's own label.
    """

    from app.services.lexicon_grammar import lexicon_pos

    before = tokens[index - 1].low if index > 0 else _word_before(context, wrong[tokens[index].start :])
    if before in _PRONOUN_CONTEXT:
        return False
    return lexicon_pos(tokens[index + 1].low) == "noun"


def _word_before(context: object, quoted: str) -> str | None:
    """The word right in front of ``quoted`` where the learner wrote it in ``context``."""

    text = _norm(context)
    if not text.strip() or not quoted.strip():
        return None
    found = re.search(rf"(?<![^\W\d_]){re.escape(quoted.strip())}(?![^\W\d_])", text, re.IGNORECASE)
    if found is None:
        return None
    ahead = _tokens(text[: found.start()])
    return ahead[-1].low if ahead else None


def grounded_errata(
    text: object,
    errata: Iterable[Mapping[str, Any]],
    *,
    strict_span: bool = False,
    language: str | None = None,
) -> list[dict[str, Any]]:
    """The errata whose (learner_text, corrected_target, why_wrong) pass
    :func:`edit_is_grounded`, each with its notes held to its own corrected form
    (:func:`reconcile_notes`, #369). Authored task/vocabulary notes pass untouched."""
    kept: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in errata:
        if not isinstance(item, Mapping):
            continue
        if str(item.get("task_error_type") or "") in {"task_compliance", "length_compliance"}:
            kept.append(dict(item))
            continue
        quoted = " ".join(_words_of(item.get("learner_text")))
        if quoted and quoted in seen:
            continue  # one note per issue, not two near-duplicates (#93)
        verified = verify_erratum(text, item, strict_span=strict_span)
        if verified is not None:
            kept.append(reconcile_notes(verified, language=language, context=text))
            if quoted:
                seen.add(quoted)
    return kept


def verify_erratum(
    text: object, item: Mapping[str, Any], *, strict_span: bool = False
) -> dict[str, Any] | None:
    """``item`` (an erratum) as the learner should see it, its fix settled and its
    notes quoting that fix, or ``None`` when :func:`verify_edit` rejects it."""
    verdict = verify_edit(
        text,
        item.get("learner_text"),
        item.get("corrected_target"),
        item.get("why_wrong"),
        strict_span=strict_span,
    )
    if not verdict.ok:
        return None
    return _with_replacement(item, verdict.replacement, verdict.span)


def _with_replacement(item: Mapping[str, Any], replacement: str | None, span: str | None = None) -> dict[str, Any]:
    """``item`` showing the verified replacement (for ``span`` when the rules widened
    it), its notes quoting the same words."""
    out = dict(item)
    if span and _norm(span).casefold() != _norm(item.get("learner_text")).casefold():
        out["learner_text"] = span
    old = str(item.get("corrected_target") or "")
    if replacement and replacement != old:
        out["corrected_target"] = replacement
        for key in ("why_wrong", "repair_hint"):
            if isinstance(out.get(key), str) and old:
                out[key] = _requote(out[key], old, replacement)
    return out


def merge_deterministic_errata(
    text: object,
    errata: Iterable[Mapping[str, Any]],
    *,
    language: str | None = None,
    people: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Grounded model errata plus the deterministic ones that do not overlap them."""
    kept = grounded_errata(text, errata, language=language)
    source = ("" if text is None else str(text)).casefold()
    taken: list[tuple[int, int]] = []
    for item in kept:
        span = str(item.get("learner_text") or "").casefold()
        at = source.find(span) if span else -1
        if at >= 0:
            taken.append((at, at + len(span)))
    for edit in deterministic_edits(text, people=people):
        if any(edit.start < b and a < edit.end for a, b in taken):
            continue
        kept.append(to_erratum(edit, language=language))
    return kept


def first_valid_edit(
    text: object,
    span: object,
    replacement: object,
    note: object = None,
    *,
    language: str | None = None,
    people: Mapping[str, str] | None = None,
) -> tuple[str | None, str | None, str | None]:
    """The single correction a scene turn can show: the model's when it passes
    :func:`verify_edit` (as settled there), else the most serious model-free edit
    (grammar before spelling, then reading order), else nothing."""
    if span and replacement and changes_what_was_said(
        span, replacement, listed=True, question=in_a_question(text, span)
    ) is None:
        verdict = verify_edit(text, span, replacement, note, people=people)
        if verdict.ok and verdict.replacement:
            shown = _requote(str(note), str(replacement), verdict.replacement) if note else None
            if shown:
                # #93: a note naming an accent the corrected form lacks is rewritten.
                shown = (
                    note_for_form(verdict.span or span, verdict.replacement, shown, language=language, context=text)
                    or None
                )
            return verdict.span or str(span), verdict.replacement, shown
    edits = deterministic_edits(text, people=people)
    if edits:
        best = min(edits, key=lambda e: (-e.severity, e.start))
        return best.span, best.replacement, best.note_for(language)
    return None, None, None


# ---------------------------------------------------------------------------
# One corrected line (#133, #250)
# ---------------------------------------------------------------------------

#: Words a correction may add, drop or swap without changing what the learner said.
_GRAMMAR_WORDS = frozenset(
    """
    le la les l un une des du de d au aux ce cet cette ces c mon ton son ma ta sa mes tes ses notre votre nos vos
    leur leurs a dans en sur sous avec sans pour par chez vers entre contre avant apres pendant depuis et ou mais
    donc car parce puisque comme quand lorsque ni que qu si oui non je j tu il elle on nous vous ils elles me m te t
    se s lui y eux moi toi soi ne n pas plus jamais rien qui dont ca cela ceci tout toute tous toutes quel quelle
    quels quelles est-ce
    """.split()
)
_AUXILIARY_LEMMAS = frozenset({"être", "avoir", "aller"})
#: What a question asks, accents folded so «ou» -> «où» is no change. «Est-ce que» on its own
#: only marks it as a question; «qu'est-ce que» asks «what».
_ASKING_WORDS = {
    "quoi": "quoi", "ou": "ou", "quand": "quand", "comment": "comment", "pourquoi": "pourquoi", "combien": "combien",
    "quel": "quel", "quelle": "quel", "quels": "quel", "quelles": "quel", "lequel": "lequel", "laquelle": "lequel",
    "lesquels": "lequel", "lesquelles": "lequel",
}
#: Notes about the task or the words asked for. They change nothing in the learner's line.
_NOT_ABOUT_THE_LINE = frozenset({"task_compliance", "length_compliance", "lexical_gap"})
_LOCAL_REORDER_WORDS = 4
_MOVED_WORD_GAP = 2
_SAME_WORD_SPELLING = 0.7
_SAME_STEM_SPELLING = 0.6
_EDGE_MARKS = "«»\"“”,.;:!?…"
_ANY_WORD = re.compile(r"\S+")


def is_about_the_line(erratum: Mapping[str, Any]) -> bool:
    """Whether this erratum proposes a change to what the learner wrote."""

    kind = str(erratum.get("task_error_type") or "")
    return kind not in _NOT_ABOUT_THE_LINE and not kind.startswith("vocabulary")


def _lemmas(word: str) -> set[str]:
    found = {_verb_lemma(word), _noun_lemma(word), _forms().get(word), word if _lemma(word) else None}
    return {lemma for lemma in found if lemma}


def _is_grammar_word(word: str) -> bool:
    return _strip_marks(word) in _GRAMMAR_WORDS or _verb_lemma(word) in _AUXILIARY_LEMMAS


def _same_word(left: str, right: str) -> bool:
    """Two forms of one word, or one word and its misspelling."""

    a, b = _strip_marks(left), _strip_marks(right)
    if a == b or _lemmas(left) & _lemmas(right):
        return True
    close = difflib.SequenceMatcher(None, a, b).ratio()
    if a[:3] == b[:3] and close >= _SAME_STEM_SPELLING:
        return True  # one grows out of the other: «content», «contente», «lentement», «jouais»
    # Two real words that look alike are two words: «maison», «raison».
    return not (_lemmas(left) and _lemmas(right)) and close >= _SAME_WORD_SPELLING


def _what_it_asks(words: list[str]) -> list[str]:
    """The asking words, folded to one per family, in sorted order."""

    folded = [_strip_marks(word) for word in words]
    asks = [_ASKING_WORDS[word] for word in folded if word in _ASKING_WORDS]
    asks += ["qu'est-ce"] * sum(1 for one, two in zip(folded, folded[1:], strict=False) if (one, two) == ("qu", "est-ce"))
    return sorted(asks)


def in_a_question(line: object, span: object) -> bool:
    """Whether ``span`` sits in a sentence of ``line`` that ends with a question mark."""

    source, where = _norm(line), _locate(_norm(line), _norm(span))
    if where is None:
        return "?" in _norm(span)
    end = re.compile(r"[.!?…]+").search(source, where[1] - 1 if source[where[1] - 1 : where[1]] in ".!?…" else where[1])
    return bool(end and "?" in end.group())


def changes_what_was_said(
    span: object, replacement: object, *, listed: bool = False, question: bool | None = None
) -> str | None:
    """Why this change is a rewrite and not a correction, or ``None`` when it is a correction.

    ``the_question``: in a question, it changes what is being asked. ``words``: it brings in
    or takes out words of meaning. ``order``: it moves the sentence around. A word the
    learner wrote that isn't French may become the French word. ``listed`` is a change the
    corrector names and explains, which may also change one word («librairie» ->
    «bibliothèque») or swap one question word for another. A difference nobody listed may
    not. ``question`` says whether the span is in a question; by default, if it holds a «?».
    """

    old_text, new_text = _norm(span).casefold(), _norm(replacement).casefold()
    old, new = _WORD.findall(old_text), _WORD.findall(new_text)
    if old_text.count("?") != new_text.count("?"):
        return "the_question"
    asked, asks = _what_it_asks(old), _what_it_asks(new)
    if (question or (question is None and "?" in old_text) or "qu'est-ce" in asked) and asked != asks:
        if not (listed and len(asked) == len(asks)):
            return "the_question"

    def without(words: list[str], others: list[str]) -> list[str]:
        spare = [_strip_marks(word) for word in others]
        left: list[str] = []
        for word in words:
            if _strip_marks(word) in spare:
                spare.remove(_strip_marks(word))
            else:
                left.append(word)
        return left

    added = without(new, old)
    gone = [word for word in without(old, new) if not _is_grammar_word(word)]
    came = [word for word in added if not _is_grammar_word(word)]
    for word in list(gone):
        partner = next((other for other in came if _same_word(word, other)), None)
        if partner is not None:
            gone.remove(word)
            came.remove(partner)
    for word in list(gone):
        if added and not _lemmas(word):
            gone.remove(word)
            if came:
                came.pop(0)
    # A word said twice may lose its repeat.
    gone = [word for word in gone if _strip_marks(word) not in {_strip_marks(other) for other in new}]
    if gone or came:
        return None if listed and len(gone) <= 1 and len(came) <= 1 else "words"
    meaning = [[_strip_marks(word) for word in words if not _is_grammar_word(word)] for words in (old, new)]
    if meaning[0] != meaning[1] and sorted(meaning[0]) == sorted(meaning[1]) and len(old) > _LOCAL_REORDER_WORDS:
        return "order"
    return None


@dataclass(frozen=True, slots=True)
class SentenceGap:
    """One word-level difference between a line and a sentence: ``wrong`` at ``start`` becomes ``fix``."""

    start: int
    wrong: str
    fix: str

    @property
    def end(self) -> int:
        return self.start + len(self.wrong)


def _line_words(text: str) -> list[tuple[int, int, str]]:
    """``(start, end, key)`` per word: the key folds case, typography and edge marks."""

    words: list[tuple[int, int, str]] = []
    for match in _ANY_WORD.finditer(text):
        key = unicodedata.normalize("NFC", normalize_answer_text(match.group())).casefold().strip(_EDGE_MARKS)
        if key:
            words.append((match.start(), match.end(), key))
    return words


def line_differences(line: object, sentence: object) -> list[tuple[str, int, int, int, int]]:
    """The word-level differences between two lines (case, spacing and edge marks aside)."""

    left, right = _line_words(str(line or "")), _line_words(str(sentence or ""))
    matcher = difflib.SequenceMatcher(a=[word[2] for word in left], b=[word[2] for word in right], autojunk=False)
    return [op for op in matcher.get_opcodes() if op[0] != "equal"]


def _trim_shared_marks(wrong: str, fix: str) -> tuple[str, str]:
    """Drop the final mark both sides end with: «agreable,» -> «agréable,» is «agreable» -> «agréable»."""

    while len(wrong) > 1 and len(fix) > 1 and wrong[-1] == fix[-1] and wrong[-1] in _EDGE_MARKS:
        wrong, fix = wrong[:-1], fix[:-1]
    return wrong, fix


def sentence_gaps(line: str, sentence: str, *, fixed: Iterable[tuple[int, int]] = ()) -> list[SentenceGap] | None:
    """What it takes to turn ``line`` into ``sentence``, one gap per difference, or ``None``
    when a difference has no word in the line to stand next to. ``fixed`` holds stretches of
    the line that are already a correction, so a missing word isn't attached to one of them."""

    left, right = _line_words(line), _line_words(sentence)
    if not left or not right:
        return []
    fixed = list(fixed)

    def is_fixed(word: tuple[int, int, str]) -> bool:
        return any(word[0] < end and start < word[1] for start, end in fixed)

    def words_of(ids: range, side: list[tuple[int, int, str]]) -> set[str]:
        return {side[index][2] for index in ids}

    # A word moved shows as two differences, dropped here and added there. It is one change.
    differences: list[tuple[str, int, int, int, int]] = []
    for op in line_differences(line, sentence):
        if differences:
            _tag, i1, i2, j1, j2 = differences[-1]
            moved = (words_of(range(i1, i2), left) & words_of(range(op[3], op[4]), right)) | (
                words_of(range(op[1], op[2]), left) & words_of(range(j1, j2), right)
            )
            if op[1] - i2 <= _MOVED_WORD_GAP and moved:
                differences[-1] = ("replace", i1, op[2], j1, op[4])
                continue
        differences.append(op)

    gaps: list[SentenceGap] = []
    for tag, i1, i2, j1, j2 in differences:
        want = sentence[right[j1][0] : right[j2 - 1][1]] if j2 > j1 else ""
        if tag == "replace":
            start, wrong, fix = left[i1][0], line[left[i1][0] : left[i2 - 1][1]], want
        elif tag == "delete":
            # Words too many: the gap is the word next to them, without them.
            if i1 > 0:
                start, fix = left[i1 - 1][0], line[left[i1 - 1][0] : left[i1 - 1][1]]
                wrong = line[start : left[i2 - 1][1]]
            elif i2 < len(left):
                start, fix = left[i1][0], line[left[i2][0] : left[i2][1]]
                wrong = line[start : left[i2][1]]
            else:
                return None
        elif i1 > 0 and (i1 == len(left) or not is_fixed(left[i1 - 1])):
            # Words missing: the gap is the word next to them plus what is missing.
            start, anchor = left[i1 - 1][0], line[left[i1 - 1][0] : left[i1 - 1][1]]
            core = anchor.rstrip(_EDGE_MARKS)
            marks = anchor[len(core) :]
            fix, wrong = f"{core} {want}", anchor
            if marks and not fix.endswith(marks):
                fix += marks
        else:
            start, wrong = left[i1][0], line[left[i1][0] : left[i1][1]]
            fix = f"{want} {wrong}"
        wrong, fix = _trim_shared_marks(wrong, fix)
        if wrong.strip() and fix.strip() and wrong.strip() != fix.strip():
            gaps.append(_only_there(line, left, SentenceGap(start, wrong, fix)))
    return gaps


def _only_there(line: str, words: list[tuple[int, int, str]], gap: SentenceGap) -> SentenceGap:
    """The gap, with the word before it (or after it) when its words are also somewhere earlier
    in the line. A span is found by its words, so «a» -> «à» in «Camille a une clé, jeudi a dix
    heures» would land on the first «a», which is right."""

    while True:
        first = next(span_pattern(gap.wrong).finditer(line), None)
        if first is None or first.start() == gap.start:
            return gap
        before = [word for word in words if word[1] <= gap.start]
        if not before:
            return gap
        start = before[-1][0]
        between = line[start : gap.start]
        gap = SentenceGap(start, between + gap.wrong, between + gap.fix)


def _place_fix(line: str, span: str, fix: str, taken: list[tuple[int, int, str]], sentence: object) -> tuple[int, int] | None:
    """Where a listed fix goes: the free place its words are in, and when there are several, the
    one that brings the line closest to the model's sentence."""

    spots = [
        match.span()
        for match in span_pattern(span).finditer(line)
        if all(match.end() <= start or match.start() >= end for start, end, _fix in taken)
    ]
    if not spots:
        where = _locate(line, span)
        return where if where and all(where[1] <= start or where[0] >= end for start, end, _fix in taken) else None
    if len(spots) == 1 or not isinstance(sentence, str) or not sentence.strip():
        return spots[0]
    target = [word[2] for word in _line_words(sentence)]

    def closeness(spot: tuple[int, int]) -> float:
        made = line[: spot[0]] + fix + line[spot[1] :]
        return difflib.SequenceMatcher(None, [word[2] for word in _line_words(made)], target, autojunk=False).ratio()

    return max(spots, key=closeness)


def _refused_change(line: str, gap: SentenceGap) -> dict[str, Any] | None:
    """Why a change only the model's sentence holds may not be made, or ``None``."""

    reason = changes_what_was_said(gap.wrong, gap.fix, question=in_a_question(line, gap.wrong))
    if reason is None and not verify_edit(line, gap.wrong, gap.fix).ok:
        reason = "not_verified"
    return {"learner_text": gap.wrong, "corrected_target": gap.fix, "reason": reason} if reason else None


def held_gaps(line: str, sentence: object) -> tuple[list[SentenceGap], list[dict[str, Any]]] | None:
    """``(allowed, refused)``: the differences of the model's sentence, each through the one
    check. ``None`` when a difference has no word in the line to stand next to."""

    gaps = sentence_gaps(line, str(sentence or ""))
    if gaps is None:
        return None
    allowed, refused = [], []
    for gap in gaps:
        why = _refused_change(line, gap)
        if why:
            refused.append(why)
        else:
            allowed.append(gap)
    return allowed, refused


def apply_gaps(line: str, gaps: Iterable[SentenceGap]) -> str:
    """``line`` with ``gaps`` made, and nothing else changed."""

    out = line
    for gap in sorted(gaps, key=lambda item: item.start, reverse=True):
        out = out[: gap.start] + gap.fix + out[gap.end :]
    return out


@dataclass(frozen=True, slots=True)
class CheckedCorrection:
    """A correction a screen may print: ``corrected`` is the line with the listed fixes in it."""

    corrected: str
    errata: list[dict[str, Any]]
    refused: list[dict[str, Any]]


def verify_correction(
    text: object,
    sentence: object,
    errata: Iterable[Mapping[str, Any]],
    *,
    language: str | None = None,
    people: Mapping[str, str] | None = None,
) -> CheckedCorrection:
    """The learner's line with every verified fix in it, and every change in it listed (#133).

    A model returns a sentence and a list as two pieces of text, and the sentence was printed
    as it came: «Qu est-ce que c est, jeudi a dix-huit heures ?» came back as «C'est jeudi à
    dix-huit heures ?», a different question, with two listed fixes. Now the line is built
    from the learner's own words. Each listed fix passes :func:`verify_erratum` and
    :func:`changes_what_was_said`; each difference only the model's sentence holds becomes a
    fix of its own if it passes both, and is dropped if it doesn't. ``sentence`` may be
    ``None``: the listed fixes are then all there is.
    """

    line = "" if text is None else str(text)
    kept: list[dict[str, Any]] = []
    refused: list[dict[str, Any]] = []
    fixes: list[tuple[int, int, str]] = []
    for raw in errata:
        item = dict(raw)
        if not is_about_the_line(item):
            kept.append(item)
            continue
        verified = verify_erratum(line, item, strict_span=False)
        reason = "not_verified" if verified is None else changes_what_was_said(
            verified.get("learner_text"),
            verified.get("corrected_target"),
            listed=True,
            question=in_a_question(line, verified.get("learner_text")),
        )
        if reason or verified is None:
            refused.append(
                {"learner_text": item.get("learner_text"), "corrected_target": item.get("corrected_target"), "reason": reason}
            )
            continue
        span, fix = str(verified.get("learner_text") or ""), str(verified.get("corrected_target") or "")
        where = _place_fix(line, span, fix, fixes, sentence)
        if where:
            fixes.append((where[0], where[1], fix))
            placed = _only_there(line, _line_words(line), SentenceGap(where[0], line[where[0] : where[1]], fix))
            verified = {**verified, "learner_text": placed.wrong, "corrected_target": placed.fix}
        kept.append(verified)
    base = line
    fixed: list[tuple[int, int]] = []
    shift = 0
    for start, end, fix in sorted(fixes):
        base = base[: start + shift] + fix + base[end + shift :]
        fixed.append((start + shift, start + shift + len(fix)))
        shift += len(fix) - (end - start)

    def derive(source: str, target: str, *, by_rules: bool) -> str:
        nonlocal fixed
        out, shift_ = source, 0
        placed: list[SentenceGap] = []
        for gap in sentence_gaps(source, target, fixed=fixed) or []:
            # A listed fix stands: a sentence that disagrees with it doesn't undo it.
            if not by_rules and any(gap.start < end and start < gap.end for start, end in fixed):
                refused.append({"learner_text": gap.wrong, "corrected_target": gap.fix, "reason": "overlaps_a_fix"})
                continue
            if is_variant_edit(gap.wrong, gap.fix):
                refused.append({"learner_text": gap.wrong, "corrected_target": gap.fix, "reason": "valid_variant"})
                continue
            why = None if by_rules else _refused_change(source, gap)
            if why:
                refused.append(why)
                continue
            placed.append(gap)
            note = note_from_form(gap.wrong, gap.fix, language=language)
            kept.append(
                {
                    "display_label": "",
                    "learner_text": gap.wrong,
                    "corrected_target": gap.fix,
                    "why_wrong": note,
                    "repair_hint": "",
                    "severity": 1,
                    "recurring": False,
                    "task_error_type": "grammar",
                    "derived_from_sentence": True,
                }
            )
        for gap in sorted(placed, key=lambda item: item.start):
            out = out[: gap.start + shift_] + gap.fix + out[gap.end + shift_ :]
            shift_ += len(gap.fix) - len(gap.wrong)
        return out

    built = derive(base, str(sentence), by_rules=False) if isinstance(sentence, str) and sentence.strip() else base
    # The rules read the line once more: a fix can open another («à le» after a fixed word).
    settled = repair_text(built, people=people)
    if settled != built:
        built = derive(built, settled, by_rules=True)
    return CheckedCorrection(corrected=built, errata=kept, refused=refused)


__all__ = [
    "CheckedCorrection",
    "Edit",
    "SentenceGap",
    "Verdict",
    "apply_edits",
    "apply_gaps",
    "changes_what_was_said",
    "held_gaps",
    "in_a_question",
    "is_about_the_line",
    "line_differences",
    "sentence_gaps",
    "verify_correction",
    "changes_subject",
    "deterministic_edits",
    "deterministic_errata",
    "edit_is_grounded",
    "first_valid_edit",
    "grounded_errata",
    "known_people",
    "merge_deterministic_errata",
    "repair_text",
    "note_for_form",
    "note_from_form",
    "note_matches_form",
    "reconcile_notes",
    "to_erratum",
    "verify_edit",
    "verify_erratum",
]
