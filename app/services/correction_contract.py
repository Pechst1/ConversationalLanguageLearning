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
  number, accents and spelling, negation order, «de» after modals, «à», age with
  avoir, stressed pronouns. Every rule stands on closed evidence (a fixed trigger
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

from app.services.answer_acceptance import (
    correction_is_grounded,
    is_real_correction,
    known_slip,
    person_swaps_hold,
)

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
        # a near-quote (the Courrier's «une photo» for «un photo»): the replacement is
        # checked on its own
        return quoted, repair_text(proposed, people=cast) or proposed
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
    "theatre": "théâtre", "gateau": "gâteau",
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
        "FR_ELISION": "orthography",
        "FR_SPELLING": "orthography",
        "FR_CONTRACTION": "articles",
        "FR_GENDER_DET": "gender_agreement",
        "FR_CET": "gender_agreement",
        "FR_MON_VOWEL": "gender_agreement",
        "FR_PARTICIPLE_AGREE": "gender_agreement",
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
        severity=1 if rule_id in {"FR_ACCENT", "FR_SPELLING", "FR_A_GRAVE"} else 2,
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
}
#: Spelled like a participle after avoir: «j'ai reve» is «rêvé», not «rêve».
_PARTICIPLE_LOOKALIKES = frozenset({"reve", "prete", "telephone"})
#: «grand mère» -> «grand-mère»: the hyphen of the family words.
_HYPHENATED = {
    ("grand", "mère"): "grand-mère", ("grand", "mere"): "grand-mère", ("grand", "père"): "grand-père",
    ("grand", "pere"): "grand-père", ("grands", "parents"): "grands-parents",
    ("grand", "parents"): "grands-parents",
}


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


def _space(source: str, left: Tok, right: Tok) -> bool:
    return source[left.end : right.start] in {" ", " "}


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
        if final is None:
            continue
        if any(final.start < other.end and other.start < final.end for other in settled):
            continue
        settled.append(final)
    settled.sort(key=lambda e: e.start)
    return settled


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


_QUOTED = "«“\"‘'"
_UNQUOTED = "»”\"’'"


def _requote(note: str, old: str, new: str) -> str:
    """``note`` quoting ``new`` where it quoted ``old`` («« le appartement »» ->
    «« l'appartement »»). Only quoted words change: a short fix like «de» or «à» is
    never replaced inside the rest of the explanation."""
    if not note or not old or old == new:
        return note
    pattern = re.compile(f"([{_QUOTED}]\\s*){re.escape(old)}(\\s*[{_UNQUOTED}])")
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
            and tok.low in _PLURAL_DETS
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
        if tok.low in _ACCENTS and not acronym:
            right = _ACCENTS[tok.low]
            add(_edit("FR_ACCENT", source, tok.start, tok.end, _case(source[tok.start:tok.end], right), right=right))
            continue
        if (
            tok.low in _MISSPELLINGS
            and not acronym
            and not glued_before
            and _lemma(tok.low) is None
            and _forms().get(tok.low) is None
            and not (nxt is not None and source[tok.end : nxt.start] in {"'", "’", "-"})
            and not (tok.low in _PARTICIPLE_LOOKALIKES and prev is not None and prev.low in _AVOIR_FORMS)
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
        verified = verify_erratum(text, item, strict_span=strict_span)
        if verified is not None:
            kept.append(verified)
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
    """The single correction a scene turn can show: the model's when it passes
    :func:`verify_edit` (as settled there), else the most serious model-free edit
    (grammar before spelling, then reading order), else nothing."""
    if span and replacement:
        verdict = verify_edit(text, span, replacement, note, people=people)
        if verdict.ok and verdict.replacement:
            shown = _requote(str(note), str(replacement), verdict.replacement) if note else None
            return verdict.span or str(span), verdict.replacement, shown
    edits = deterministic_edits(text, people=people)
    if edits:
        best = min(edits, key=lambda e: (-e.severity, e.start))
        return best.span, best.replacement, best.note_for(language)
    return None, None, None


__all__ = [
    "Edit",
    "Verdict",
    "apply_edits",
    "changes_subject",
    "deterministic_edits",
    "deterministic_errata",
    "edit_is_grounded",
    "first_valid_edit",
    "grounded_errata",
    "known_people",
    "merge_deterministic_errata",
    "repair_text",
    "to_erratum",
    "verify_edit",
    "verify_erratum",
]
