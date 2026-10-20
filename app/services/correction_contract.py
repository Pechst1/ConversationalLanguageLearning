"""One corrector contract for every free-text surface (root cause #250).

Scene replies, the Courrier and the Journal each asked a model for a correction
and showed whatever came back, or a dead-end line («the corrector was
unavailable», «the correction could not be made») when it failed. Nothing
compared the correction with the sentence the learner actually wrote, and nothing
found the learner's mistakes without a model.

The flaw was structural: the corrector's output was *trusted*, and a failure had
*no value of its own* (a dead-end line, not a result). This module is the
contract that replaces both:

* :func:`edit_is_grounded` — a model edit (span, replacement, note) is accepted
  only when it can be tied to the sentence: the quoted span is in it, a subject
  the note leans on («With « tu »…») is in it, and a single être/avoir/aller form
  that changes person is wrong for the subject in front of it and right for the
  replacement. The rule is one-sided: it rejects only what it can prove wrong, so
  a subject it cannot read never drops a real fix.
* :func:`deterministic_edits` — a model-free pass over the same sentence
  (person of être/avoir/aller, être-verbs with avoir, aller + participle,
  first-person -dre verbs, determiner/noun gender from the core lexicon, accents,
  a present-tense verb after a passé composé). Every edit's span is a substring
  of the input, by construction.
* :func:`merge_deterministic_errata` / :func:`first_valid_edit` — verified model
  edits plus deterministic edits that do not overlap them. A model that fails or
  is rejected leaves the deterministic edits, never an empty «unavailable» card.

The same three calls serve the scene reply, the Courrier and the Journal, so the
surfaces cannot drift into three correctors with three opinions about French.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from app.services.answer_acceptance import is_real_correction

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
        if before is not None and before.low in _CLITIC_CONTEXT:
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
    if strict_span and not places:
        return False
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
    position = changed[0]
    old, new = span_words[position], new_words[position]
    old_persons, new_persons = _FORM_PERSONS.get(old), _FORM_PERSONS.get(new)
    if old_persons is None or new_persons is None:
        return True
    if not places:
        # Near-quote: the swap is judged against the whole sentence.
        return all(_markers_present(p, present) or p in {"3sg", "3pl"} for p in new_persons)
    return any(_swap_holds(tokens, source, place + position, old_persons, new_persons, present) for place in places)


def _swap_holds(
    tokens: list[Tok],
    text: str,
    index: int,
    old_persons: frozenset[str],
    new_persons: frozenset[str],
    present: set[str],
) -> bool:
    person = _subject_person(tokens, text, index)
    if person is not None:
        return person not in old_persons and person in new_persons
    # Subject unreadable: a first/second-person replacement still needs its pronoun
    # somewhere in the sentence («est → es» with no «tu» was the #193 bug).
    if new_persons & {"3sg", "3pl"}:
        return True
    return any(_markers_present(p, present) for p in new_persons)


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
    key = str(language or "en")[:2].lower()
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
_AMBIGUOUS_PARTICIPLES = frozenset({"rentré", "sorti", "monté", "descendu", "retourné"})
_PLACE_WORDS = frozenset(
    {"dans", "à", "au", "aux", "chez", "en", "hier", "tard", "tôt", "tout", "ensuite", "enfin", "vers",
     "de", "du", "par", "sur", "avant", "après", "ce", "cette", "puis", "et", "mais", "parce"}
)
_AVOIR_TO_ETRE = {"a": "est", "as": "es", "ai": "suis", "avons": "sommes", "avez": "êtes", "ont": "sont"}
_PRESENT_MARKERS = frozenset(
    {"maintenant", "aujourd'hui", "toujours", "souvent", "chaque", "demain", "d'habitude", "habituellement",
     "généralement", "tous", "toutes"}
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
    "theatre": "théâtre", "gateau": "gâteau",
    "etudiant": "étudiant", "etudiante": "étudiante", "arrivee": "arrivée", "journee": "journée",
    "soiree": "soirée", "idee": "idée", "annee": "année", "equipe": "équipe", "eglise": "église",
}
_MASC_DET = {"le": "la", "un": "une", "ce": "cette", "mon": "ma", "ton": "ta", "son": "sa"}
_FEM_DET = {"la": "le", "une": "un", "cette": "ce", "ma": "mon", "ta": "ton", "sa": "son"}
#: «je la porte», «il le mange»: in front of a verb form that is also a noun, «le/la» is
#: a pronoun, not a determiner, and says nothing about the noun's gender.
_PRONOUN_CONTEXT = frozenset(
    {"je", "j", "tu", "il", "elle", "on", "nous", "vous", "ils", "elles", "me", "m", "te", "t", "se", "s",
     "ne", "n", "y", "en", "lui", "leur", "qui"}
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


def _noun_gender(word: str) -> str | None:
    entry = _lemma(word)
    if not entry or entry.get("pos") != "noun":
        return None
    gender = entry.get("gender")
    return gender if gender in {"m", "f"} else None


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
            "fr": "La phrase raconte au passé composé ; gardez le même temps : « {right} ».",
        },
    },
    "FR_ELISION": {
        "label": {"en": "Elision", "de": "Elision", "fr": "Élision"},
        "note": {
            "en": "« je » drops its vowel in front of a vowel: « {right} ».",
            "de": "« je » verliert vor einem Vokal den Vokal: « {right} ».",
            "fr": "« je » s’élide devant une voyelle : « {right} ».",
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
}
_GENDER_WORD = {
    "m": {"en": "masculine", "de": "maskulin", "fr": "masculin"},
    "f": {"en": "feminine", "de": "feminin", "fr": "féminin"},
}


def _edit(rule_id: str, text: str, start: int, end: int, replacement: str, **fields: str) -> Edit:
    spec = _RULE_TEXT[rule_id]
    span = text[start:end]
    base = {"subject": "", "right": replacement, "wrong": span, "noun": "", "part": "", **fields}
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
        "FR_ELISION": "orthography",
        "FR_GENDER_DET": "gender_agreement",
        "FR_PARTICIPLE_AGREE": "gender_agreement",
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
        severity=1 if rule_id == "FR_ACCENT" else 2,
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


def deterministic_edits(
    text: object,
    *,
    people: Mapping[str, str] | None = None,
) -> list[Edit]:
    """Mistakes found without a model, in reading order, non-overlapping.

    ``people`` maps a known cast first name (casefolded) to ``"f"``/``"m"``; the
    default is the cast registry. The learner's own gender is never read: a first
    or second person subject leaves the participle as written.
    """

    source = "" if text is None else str(text)
    if not source.strip():
        return []
    cast = known_people() if people is None else {k.casefold(): v for k, v in people.items()}
    tokens = _tokens(source)
    found: list[Edit] = []

    def add(edit: Edit | None) -> None:
        if edit is None:
            return
        if any(edit.start < other.end and other.start < edit.end for other in found):
            return
        found.append(edit)

    for i, tok in enumerate(tokens):
        nxt = tokens[i + 1] if i + 1 < len(tokens) else None
        prev = tokens[i - 1] if i > 0 else None
        joined_next = nxt is not None and _joined(source, tok, nxt)
        joined_prev = prev is not None and _joined(source, prev, tok)

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
                if participle in _AMBIGUOUS_PARTICIPLES and not (
                    after is not None and _same_sentence(source, nxt, after) and after.low in _PLACE_WORDS
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

        # --- determiner / noun gender --------------------------------------------------
        if joined_next and nxt is not None and tok.low in (_MASC_DET.keys() | _FEM_DET.keys()):
            if tok.low in {"le", "la"} and prev is not None and joined_prev and prev.low in _PRONOUN_CONTEXT:
                pass  # «je la porte», «il le mange»: a pronoun, not a determiner
            else:
                gender = _noun_gender(nxt.low)
                vowel = nxt.low[:1] in "aeiouhéèêâîôû"
                if gender == "f" and tok.low in _MASC_DET:
                    if not (tok.low in {"mon", "ton", "son"} and vowel):
                        right = _MASC_DET[tok.low]
                        add(_edit("FR_GENDER_DET", source, tok.start, tok.end, _case(source[tok.start:tok.end], right),
                                  noun=nxt.low, gender="f", right=f"{right} {nxt.low}", wrong=f"{tok.low} {nxt.low}"))
                        continue
                elif gender == "m" and tok.low in _FEM_DET:
                    right = _FEM_DET[tok.low]
                    add(_edit("FR_GENDER_DET", source, tok.start, tok.end, _case(source[tok.start:tok.end], right),
                              noun=nxt.low, gender="m", right=f"{right} {nxt.low}", wrong=f"{tok.low} {nxt.low}"))
                    continue

        # --- de le / à le ---------------------------------------------------------------
        if tok.low in {"de", "à"} and joined_next and nxt is not None and nxt.low == "le":
            after = tokens[i + 2] if i + 2 < len(tokens) else None
            if after is not None and _joined(source, nxt, after) and _noun_gender(after.low) == "m":
                right = "du" if tok.low == "de" else "au"
                add(_edit("FR_CONTRACTION", source, tok.start, nxt.end, _case(source[tok.start:tok.start+1], right) if source[tok.start].isupper() else right,
                          right=right, wrong=f"{tok.low} le"))
                continue

        # --- elision: «je ai» -> «j'ai» ------------------------------------------------
        if tok.low == "je" and nxt is not None and nxt.low[:1] in "aeiouéèêâîô" and _same_clause(source, tok, nxt):
            gap = source[tok.end : nxt.start]
            if gap and gap.strip(" \u00a0") == "":
                apostrophe = "’" if "’" in source else "'"
                glued = _case(source[tok.start:tok.end], "j") + apostrophe + source[nxt.start:nxt.end]
                add(_edit("FR_ELISION", source, tok.start, nxt.end, glued, right=glued))
                continue

        # --- missing accents -----------------------------------------------------------
        if tok.low in _ACCENTS:
            right = _ACCENTS[tok.low]
            add(_edit("FR_ACCENT", source, tok.start, tok.end, _case(source[tok.start:tok.end], right), right=right))
            continue

    _tense_edits(source, tokens, cast, add)
    found.sort(key=lambda e: e.start)
    return found


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
        # a passé composé earlier in the same sentence
        has_pc = False
        for j in range(len(sentence) - 1):
            a, b = sentence[j], sentence[j + 1]
            if not _joined(text, a, b):
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
        if not _is_verb(infinitive) or low in {"être", "mène"}:
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


def grounded_errata(
    text: object, errata: Iterable[Mapping[str, Any]], *, strict_span: bool = False
) -> list[dict[str, Any]]:
    """The errata whose (learner_text, corrected_target, why_wrong) pass
    :func:`edit_is_grounded`. Authored task/vocabulary notes pass untouched."""
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
        if edit_is_grounded(
            text,
            item.get("learner_text"),
            item.get("corrected_target"),
            item.get("why_wrong"),
            strict_span=strict_span,
        ):
            kept.append(dict(item))
            if quoted:
                seen.add(quoted)
    return kept


def merge_deterministic_errata(
    text: object,
    errata: Iterable[Mapping[str, Any]],
    *,
    language: str | None = None,
    people: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Grounded model errata plus the deterministic ones that do not overlap them."""
    kept = grounded_errata(text, errata)
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
    """The single correction a scene turn can show: the model's when it is
    grounded, else the first deterministic edit, else nothing."""
    if span and replacement and edit_is_grounded(text, span, replacement, note):
        return str(span), str(replacement), str(note) if note else None
    edits = deterministic_edits(text, people=people)
    if edits:
        return edits[0].span, edits[0].replacement, edits[0].note_for(language)
    return None, None, None


__all__ = [
    "Edit",
    "apply_edits",
    "deterministic_edits",
    "deterministic_errata",
    "edit_is_grounded",
    "first_valid_edit",
    "grounded_errata",
    "known_people",
    "merge_deterministic_errata",
    "to_erratum",
]
