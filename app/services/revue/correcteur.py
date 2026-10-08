"""Le Correcteur (WP-122 §4): Romy's draft, seeded with the learner's own mistakes.

Romy's three-line dispatch for a dossier arrives with errors in it; the learner marks
them before it goes to print. Noticing is the step most apps skip.

**The draft** (:func:`draft_for`). The base text is the dispatch the phase-1 close
writes when no session exists: the dossier's claims as lines, facts first, topped up
with the summary's sentences. The close's builder (``encounter.RevueEncounter.close``)
needs a session and a provider, so the small body builder is copied here
(:func:`dispatch_lines`) rather than imported.

**Seeding** is deterministic. :data:`RULES` is a small rule set, one per grammar point
that can be applied mechanically to a sentence: past-participle agreement, article
contraction, accents, verb endings (-é/-er, -ais/-ait), gender agreement of adjectives
and determiners, plural -s. Each rule finds *sites* in a sentence and makes the wrong
form. The candidates are, in order:

1. the learner's own errata (``journey_errata.errata_targets_for_user``), each tried
   first verbatim (the learner's own wrong wording where the correction occurs in the
   text), then through the rule its grammar point maps to (:func:`rule_for_target`);
2. the band's three «classiques» (:data:`CLASSIQUES`) when the learner has fewer
   errata on file than the quota (:data:`QUOTA`: 3 at A1–A2, 4 at B1+).

A candidate whose rule finds no free site is skipped and the next one is tried. Only
if the quota is still short is the provider asked to rewrite *one* sentence so that
it contains the first skipped point (one model call, never more); the rewrite must
keep every number and name, and the fact checks must give the same verdicts.

**Facts never change.** After seeding, the seeded text is unseeded span by span and
must equal the base text exactly (:func:`differs_only_in_spans`: the seeded text
differs from the base only inside the spans), and ``check_anchor`` and
``check_attribution`` are rerun on the dossier's claims as the unseeded text states
them: their verdicts must equal the verdicts on the dossier itself.

**Grading** (:func:`grade_marks`, §4.2): a mark overlapping a seeded span is
*noticed*; with a right fix it is *repaired* (``erratum_repair_evidence`` written to
the errata memory, so an error the learner now notices stops being seeded: its next
review moves into the future); an untouched seeded span is *missed* (revealed after
«Bon à tirer», nothing written); a mark on a correct span is a *false alarm* (shown
kindly, never penalised). Romy's one line is authored by outcome and band.
"""

from __future__ import annotations

import re
import unicodedata
import uuid
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.revue_correcteur import RevueCorrection
from app.db.models.user import User
from app.services.revue import policy
from app.services.revue.checks import CheckResult, check_anchor, check_attribution
from app.services.revue.dossier import EditorialDossier, fold, parse_week, week_bounds

PROMPT_VERSION = "correcteur-v1"
#: How many mistakes a draft carries, by band (§4.1).
QUOTA = {"A1": 3, "A2": 3, "B1": 4, "B2": 4}
#: The dispatch has three lines (as the close writes it).
DISPATCH_LINES = 3
RELEVE_HREF = "/notebook?mode=releve"

# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

_TOKEN = re.compile(r"\d+|[^\W\d_]+", re.UNICODE)
_SENTENCE = re.compile(r"[^.!?…]+[.!?…]*\s*")


def _sentences(text: str) -> list[str]:
    return [chunk.strip() for chunk in _SENTENCE.findall(text or "") if chunk.strip()]


def strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def _fold_answer(text: str | None) -> str:
    """Whitespace, quote marks and case folded; accents kept (they are the point)."""

    return fold(text).casefold().strip(" .,;:!?")


def _case_like(source: str, out: str) -> str:
    return out[:1].upper() + out[1:] if source[:1].isupper() else out


@dataclass(frozen=True, slots=True)
class Token:
    start: int
    end: int
    text: str

    @property
    def low(self) -> str:
        return self.text.casefold()


def tokens(sentence: str) -> list[Token]:
    return [Token(m.start(), m.end(), m.group(0)) for m in _TOKEN.finditer(sentence)]


@dataclass(frozen=True, slots=True)
class Site:
    """Where a rule can seed: ``sentence[start:end]`` is ``correct``; ``wrong`` replaces it."""

    start: int
    end: int
    correct: str
    wrong: str


# ---------------------------------------------------------------------------
# The rule set
# ---------------------------------------------------------------------------

#: Auxiliary forms after which a past participle stands (passé composé, passive).
AUX = frozenset(
    "a ai as avons avez ont avait avaient avoir aura auront ayant est es sommes êtes sont "
    "était étaient être été sera seront soit soient serait seraient étant".split()
)
#: Words a participle may sit behind an auxiliary with («a déjà payé», «est bien arrivé»).
_BETWEEN = frozenset("pas plus bien déjà jamais encore toujours souvent aussi tout été".split())
#: Words after which a verb is an infinitive.
INF_TRIGGERS = frozenset(
    "pour de d à sans avant doit doivent peut peuvent veut veulent faut va vont aller "
    "devoir pouvoir vouloir faire fait savoir sait laisser".split()
)
#: -er words that are not infinitives.
_ER_NOT_VERB = frozenset(
    "hier premier dernier cher fier mer hiver enfer léger entier super amer fer ver "
    "boucher boulanger étranger quartier métier dossier marcher janvier février".split()
) - {"marcher"}
PLURAL_DETS = frozenset(
    "les des ces mes tes ses nos vos leurs plusieurs quelques deux trois quatre cinq six sept "
    "huit neuf dix douze quinze vingt cent mille".split()
)
_NOT_NOUNS = frozenset("plus moins tous tout autres très".split())
#: Words that end in -s in the singular too: never a plural to drop.
_INVARIABLE_S_WORDS = frozenset(
    "préavis avis moins plus fois temps pays prix mois cours bras corps repas souris dos gros bas jus "
    "mais très après dès sans sous dans vers depuis alors puis parfois toujours jamais ailleurs plusieurs "
    "tous français anglais frais palais mauvais succès procès progrès accès".split()
)
#: The same, accents folded: a seeded «preavis» is still not a plural.
_INVARIABLE_S = frozenset(strip_accents(word) for word in _INVARIABLE_S_WORDS)
#: Irregular participles: masculine singular → feminine singular.
_PP_IRREGULAR = {
    "fait": "faite", "dit": "dite", "écrit": "écrite", "pris": "prise", "mis": "mise",
    "venu": "venue", "parti": "partie", "sorti": "sortie", "né": "née", "ouvert": "ouverte",
    "devenu": "devenue", "revenu": "revenue", "permis": "permise", "promis": "promise",
}
_PP_IRREGULAR_BACK = {fem: masc for masc, fem in _PP_IRREGULAR.items()}
#: Adjective pairs (masculine, feminine), singular; the plural adds -s (or -x → -x).
_ADJ_PAIRS = (
    ("grand", "grande"), ("petit", "petite"), ("important", "importante"), ("nouveau", "nouvelle"),
    ("vrai", "vraie"), ("public", "publique"), ("premier", "première"), ("dernier", "dernière"),
    ("prochain", "prochaine"), ("seul", "seule"), ("français", "française"), ("gratuit", "gratuite"),
    ("long", "longue"), ("bon", "bonne"), ("beau", "belle"), ("plein", "pleine"), ("social", "sociale"),
    ("local", "locale"), ("national", "nationale"), ("ouvert", "ouverte"), ("fermé", "fermée"),
    ("cher", "chère"), ("lourd", "lourde"), ("haut", "haute"), ("froid", "froide"), ("chaud", "chaude"),
    ("parisien", "parisienne"), ("européen", "européenne"), ("traditionnel", "traditionnelle"),
    ("constitutionnel", "constitutionnelle"), ("annuel", "annuelle"), ("officiel", "officielle"),
    ("mondial", "mondiale"), ("nombreux", "nombreuse"), ("heureux", "heureuse"), ("blanc", "blanche"),
    ("frais", "fraîche"), ("certain", "certaine"), ("municipal", "municipale"), ("régional", "régionale"),
    ("politique", "politique"), ("minimum", "minimum"),
)


def _adj_lexicon() -> dict[str, tuple[str, str, bool]]:
    """form → (opposite gender, other number, is_plural)."""

    out: dict[str, tuple[str, str, bool]] = {}
    for masc, fem in _ADJ_PAIRS:
        if masc == fem:
            continue
        masc_pl = masc if masc.endswith(("s", "x")) else (masc[:-2] + "aux" if masc.endswith("al") else masc + "s")
        if masc.endswith("eau"):
            masc_pl = masc + "x"
        fem_pl = fem + "s"
        out.setdefault(masc, (fem, masc_pl, False))
        out.setdefault(fem, (masc, fem_pl, False))
        out.setdefault(masc_pl, (fem_pl, masc, True))
        out.setdefault(fem_pl, (masc_pl, fem, True))
    return out


ADJECTIVES = _adj_lexicon()
#: Determiners by gender and number, for the gender rule's options (never seeded on their own).
_DETERMINER_SWAPS = {
    "le": ["la", "les"], "la": ["le", "les"], "les": ["le", "la"], "un": ["une", "des"],
    "une": ["un", "des"], "ce": ["cette", "ces"], "cette": ["ce", "cet"], "cet": ["cette", "ce"],
    "mon": ["ma", "mes"], "ma": ["mon", "mes"], "son": ["sa", "ses"], "sa": ["son", "ses"],
}
CONTRACTIONS = {"du": "de le", "au": "à le", "aux": "à les", "des": "de les"}
UNCONTRACTED = {wrong: right for right, wrong in CONTRACTIONS.items()}
_CONTRACTION_OPTIONS = {
    "du": ["de le", "de la"], "au": ["à le", "à la"], "aux": ["à les", "au"], "des": ["de les", "du"],
    "de le": ["du", "de la"], "à le": ["au", "à la"], "à les": ["aux", "au"], "de les": ["des", "du"],
}


def _previous(toks: list[Token], index: int, *, skip: frozenset[str] = frozenset()) -> Token | None:
    j = index - 1
    while j >= 0 and toks[j].low in skip:
        j -= 1
    return toks[j] if j >= 0 else None


def _after_aux(toks: list[Token], index: int) -> bool:
    prev = _previous(toks, index, skip=_BETWEEN)
    if prev is None:
        return False
    if prev.low in AUX:
        return True
    # «a été payé»: «été» itself is in _BETWEEN, so look at what precedes it.
    return False


def _pp_toggle(word: str) -> list[str]:
    low = word.casefold()
    if low in _PP_IRREGULAR:
        fem = _PP_IRREGULAR[low]
        return [fem, (low if low.endswith("s") else low + "s")]
    if low in _PP_IRREGULAR_BACK:
        return [_PP_IRREGULAR_BACK[low], low + "s"]
    for ending, swaps in (("ées", ("és", "ée")), ("ée", ("é", "ées")), ("és", ("é", "ées")), ("é", ("ée", "és"))):
        if low.endswith(ending) and len(low) > len(ending) + 1:
            stem = word[: len(word) - len(ending)]
            return [stem + swap for swap in swaps]
    return []


def _is_participle(word: str) -> bool:
    low = word.casefold()
    return bool(_pp_toggle(word)) and (low.endswith(("é", "ée", "és", "ées")) or low in _PP_IRREGULAR or low in _PP_IRREGULAR_BACK)


@dataclass(frozen=True)
class Rule:
    """One mechanical grammar point: where it can be seeded, and the forms it makes."""

    id: str
    label_fr: str
    #: Catalogue subskills (v1 and v2) this rule stands for.
    subskills: tuple[str, ...]
    sites: Callable[[str], list[Site]]
    variants: Callable[[str], list[str]]


def _sites_pp(sentence: str) -> list[Site]:
    toks = tokens(sentence)
    out = []
    for i, tok in enumerate(toks):
        # «été» is the participle of être: invariable, never an agreement site.
        if tok.low != "été" and _is_participle(tok.text) and _after_aux(toks, i):
            out.append(Site(tok.start, tok.end, tok.text, _case_like(tok.text, _pp_toggle(tok.text)[0])))
    return out


def _sites_contraction(sentence: str) -> list[Site]:
    toks = tokens(sentence)
    first, last = [], []
    for tok in toks:
        if tok.low in CONTRACTIONS:
            site = Site(tok.start, tok.end, tok.text, _case_like(tok.text, CONTRACTIONS[tok.low]))
            # «des» is also the plural indefinite article: tried after du / au / aux.
            (last if tok.low == "des" else first).append(site)
    return first + last


def _strip_first_accent(word: str) -> str | None:
    for index, char in enumerate(word):
        if char.casefold() in "éèêàç":
            plain = strip_accents(char)
            return word[:index] + plain + word[index + 1 :]
    return None


def _sites_accent(sentence: str) -> list[Site]:
    toks = tokens(sentence)
    first, then = [], []
    for tok in toks:
        if tok.low == "à":
            first.append(Site(tok.start, tok.end, tok.text, _case_like(tok.text, "a")))
        elif len(tok.text) >= 4 and (wrong := _strip_first_accent(tok.text)):
            then.append(Site(tok.start, tok.end, tok.text, wrong))
    return first + then


def _variants_accent(word: str) -> list[str]:
    low = word.casefold()
    fixed = {"à": ["a"], "a": ["à"], "ou": ["où"], "où": ["ou"]}
    if low in fixed:
        return [_case_like(word, v) for v in fixed[low]]
    out = []
    if stripped := _strip_first_accent(word):
        out.append(stripped)
        swapped = word.replace("é", "è", 1) if "é" in word else None
        if swapped and swapped != word:
            out.append(swapped)
    return out


def _sites_verb_ending(sentence: str) -> list[Site]:
    toks = tokens(sentence)
    out = []
    for i, tok in enumerate(toks):
        low = tok.low
        prev = _previous(toks, i)
        if low.endswith("é") and len(low) >= 4 and _after_aux(toks, i):
            out.append(Site(tok.start, tok.end, tok.text, tok.text[:-1] + "er"))
        elif (
            low.endswith("er") and len(low) >= 5 and low not in _ER_NOT_VERB
            and prev is not None and prev.low in INF_TRIGGERS
        ):
            out.append(Site(tok.start, tok.end, tok.text, tok.text[:-2] + "é"))
        elif low.endswith("ait") and len(low) >= 4 and strip_accents(low) not in _INVARIABLE_S:
            out.append(Site(tok.start, tok.end, tok.text, tok.text[:-1] + "s"))
    return out


def _variants_verb_ending(word: str) -> list[str]:
    low = word.casefold()
    if low.endswith("er") and len(low) >= 5 and low not in _ER_NOT_VERB:
        return [word[:-2] + "é", word[:-2] + "ez"]
    if low.endswith("é") and len(low) >= 4:
        return [word[:-1] + "er", word[:-1] + "ez"]
    if low.endswith("ez") and len(low) >= 4:
        return [word[:-2] + "er", word[:-2] + "é"]
    if strip_accents(low) in _INVARIABLE_S:
        return []
    if low.endswith("ait") and len(low) >= 4:
        return [word[:-1] + "s", word[:-1] + "ent"]
    if low.endswith("ais") and len(low) >= 4:
        return [word[:-1] + "t"]
    return []


def _sites_adj_gender(sentence: str) -> list[Site]:
    out = []
    for tok in tokens(sentence):
        entry = ADJECTIVES.get(tok.low)
        if entry:
            out.append(Site(tok.start, tok.end, tok.text, _case_like(tok.text, entry[0])))
    return out


def _variants_adj_gender(word: str) -> list[str]:
    low = word.casefold()
    if low in ADJECTIVES:
        opposite, other_number, _ = ADJECTIVES[low]
        return [_case_like(word, opposite), _case_like(word, other_number)]
    if low in _DETERMINER_SWAPS:
        return [_case_like(word, v) for v in _DETERMINER_SWAPS[low]]
    return []


def _is_plural_det(tok: Token) -> bool:
    return tok.low in PLURAL_DETS or (tok.text.isdigit() and int(tok.text) > 1)


def _sites_plural(sentence: str) -> list[Site]:
    toks = tokens(sentence)
    out = []
    for i, tok in enumerate(toks):
        if i == 0 or not _is_plural_det(toks[i - 1]) or tok.text.isdigit():
            continue
        low = tok.low
        if low in _NOT_NOUNS or low in PLURAL_DETS:
            continue
        # The words must touch: «48 heures», not «48, heures».
        if sentence[toks[i - 1].end : tok.start].strip():
            continue
        if strip_accents(low) in _INVARIABLE_S:
            continue
        if low.endswith("eaux") or (low.endswith("s") and not low.endswith("ss") and len(low) >= 4):
            out.append(Site(tok.start, tok.end, tok.text, tok.text[:-1]))
    return out


def _variants_plural(word: str) -> list[str]:
    low = word.casefold()
    if strip_accents(low) in _INVARIABLE_S:
        return []
    if low.endswith("s") and not low.endswith("ss") and len(low) >= 3:
        return [word[:-1]]
    if low.endswith("x") and len(low) >= 4:
        return [word[:-1]]
    if len(low) >= 3 and low[-1].isalpha():
        return [word + "s"]
    return []


RULES: dict[str, Rule] = {
    rule.id: rule
    for rule in (
        Rule(
            "pp_agreement", "l'accord du participe passé",
            ("past_participle_agreement", "past_participle_agreement_avoir", "passe_compose_etre",
             "pp_agreement_pronominal", "passive_intro"),
            _sites_pp, _pp_toggle,
        ),
        Rule(
            "contraction", "la contraction de l'article (du, au, aux)",
            ("contractions_au_du", "partitive_articles", "definite_articles"),
            _sites_contraction, lambda w: list(_CONTRACTION_OPTIONS.get(w.casefold(), [])),
        ),
        Rule("accent", "les accents (é, è, à)", (), _sites_accent, _variants_accent),
        Rule(
            "verb_ending", "la terminaison du verbe (-é / -er, -ais / -ait)",
            ("passe_compose_avoir", "passe_compose_chunks", "modals_infinitive", "imparfait", "imparfait_basics",
             "futur_proche", "pour_sans_avant_de", "verb_a_de_infinitive", "present_core"),
            _sites_verb_ending, _variants_verb_ending,
        ),
        Rule(
            "adj_gender", "l'accord de l'adjectif en genre",
            ("adjective_agreement", "gender_number"),
            _sites_adj_gender, _variants_adj_gender,
        ),
        Rule("plural_s", "le pluriel (-s)", ("plural",), _sites_plural, _variants_plural),
    )
}
RULE_ORDER = tuple(RULES)

#: The band's three «classiques» (§5 decision 5): the mistakes every learner of the band makes.
CLASSIQUES: dict[str, tuple[str, str, str]] = {
    "A1": ("accent", "contraction", "plural_s"),
    "A2": ("contraction", "pp_agreement", "accent"),
    "B1": ("pp_agreement", "contraction", "accent"),
    "B2": ("pp_agreement", "contraction", "accent"),
}

# ---------------------------------------------------------------------------
# Errata → rule
# ---------------------------------------------------------------------------

_MARKERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("pp_agreement", ("particip", "pp_agree", "past_participle", "accord du participe", "partizip")),
    ("contraction", ("contraction", "du/de le", "au/a le", "article_contract")),
    ("accent", ("accent", "spelling", "orthograph", "akzent")),
    ("verb_ending", ("ending", "terminaison", "infinitiv", "conjug", "endung")),
    ("plural_s", ("plural", "pluriel")),
    ("adj_gender", ("gender", "genre", "adjecti", "adjektiv", "agreement", "accord")),
)


def _diff_rule(learner: str | None, correct: str | None) -> str | None:
    """The rule a wrong/right pair shows, from the words that differ."""

    wrong = _fold_answer(learner)
    right = _fold_answer(correct)
    if not wrong or not right or wrong == right:
        return None
    if re.search(r"\b(de|à|a) les?\b", wrong) and re.search(r"\b(du|au|aux|des)\b", right):
        return "contraction"
    if strip_accents(wrong) == strip_accents(right):
        return "accent"
    w_words, r_words = wrong.split(), right.split()
    if len(w_words) != len(r_words):
        return None
    pairs = [(a, b) for a, b in zip(w_words, r_words, strict=True) if a != b]
    if len(pairs) != 1:
        return None
    a, b = pairs[0]
    if (a.endswith("er") and b.endswith("é")) or (a.endswith("é") and b.endswith("er")):
        return "verb_ending"
    if {a[-3:], b[-3:]} <= {"ais", "ait"} and a[:-1] == b[:-1]:
        return "verb_ending"
    if a in ADJECTIVES and b in ADJECTIVES:
        return "adj_gender"
    if b in _pp_toggle(a) or a in _pp_toggle(b):
        return "pp_agreement"
    if a.rstrip("s") == b.rstrip("s"):
        return "plural_s"
    if a.rstrip("e") == b.rstrip("e"):
        return "adj_gender"
    return None


def rule_for_target(target: Any, *, subskill: str | None = None) -> str | None:
    """The rule an erratum's grammar point maps to, or None (then only its verbatim form can seed).

    The wrong/right pair decides first; then the concept's catalogue subskill; then the
    words in its label and memory key.
    """

    by_diff = _diff_rule(getattr(target, "example_learner", None), getattr(target, "example_correct", None))
    if by_diff:
        return by_diff
    if subskill:
        for rule in RULES.values():
            if subskill in rule.subskills:
                return rule.id
    marker = " ".join(
        str(part or "")
        for part in (
            getattr(target, "label", None),
            getattr(target, "memory_key", None),
            (getattr(target, "payload", None) or {}).get("task_error_type"),
            subskill,
        )
    ).casefold()
    marker = strip_accents(marker).replace("-", "_")
    for rule_id, words in _MARKERS:
        if any(strip_accents(word) in marker for word in words):
            return rule_id
    return None


def _verbatim_sites(sentence: str, learner: str | None, correct: str | None) -> list[Site]:
    """The learner's own wrong wording, where its correction occurs in the sentence."""

    wrong, right = (learner or "").strip(), (correct or "").strip()
    if not wrong or not right or _fold_answer(wrong) == _fold_answer(right) or len(right) < 2:
        return []
    if len(right.split()) > 4 or len(wrong.split()) > 5:  # a phrase, not a whole sentence
        return []
    pattern = re.compile(r"(?<![\w])" + re.escape(right) + r"(?![\w])", re.IGNORECASE)
    return [Site(m.start(), m.end(), m.group(0), _case_like(m.group(0), wrong)) for m in pattern.finditer(sentence)]


# ---------------------------------------------------------------------------
# The draft
# ---------------------------------------------------------------------------


@dataclass
class Seed:
    sentence_index: int
    #: ``[start, end)`` in the *seeded* sentence.
    span: tuple[int, int]
    wrong_fr: str
    correct_fr: str
    error_id: str | None
    grammar_point: str
    source: str  # "errata" | "classique"
    rule: str
    #: ``[start, end)`` of the correct form in the *base* sentence.
    base_span: tuple[int, int] = (0, 0)


@dataclass
class Unit:
    sentence_index: int
    span: tuple[int, int]
    text: str
    options: list[str] | None = None


@dataclass
class Draft:
    dossier_id: str
    band: str
    title_fr: str
    kicker_fr: str
    byline_fr: str
    #: The seeded sentences, as the learner reads them.
    sentences: list[str]
    #: The unseeded sentences (after a rewrite, if one was made): the private key's other half.
    base_sentences: list[str]
    #: Which claim each line states (None for a summary sentence).
    claim_ids: list[str | None]
    seeded: list[Seed]
    units: list[Unit]
    checks: dict[str, Any] = field(default_factory=dict)
    rewrite: dict[str, Any] | None = None
    short_by: int = 0
    prompt_version: str = PROMPT_VERSION

    @property
    def text_fr(self) -> str:
        return " ".join(self.sentences)

    def to_json(self) -> dict[str, Any]:
        data = asdict(self)
        data["text_fr"] = self.text_fr
        for seed in data["seeded"]:
            seed["span"] = list(seed["span"])
            seed["base_span"] = list(seed["base_span"])
        for unit in data["units"]:
            unit["span"] = list(unit["span"])
        return data

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Draft:
        payload = {k: v for k, v in data.items() if k != "text_fr"}
        payload["seeded"] = [
            Seed(**{**s, "span": tuple(s["span"]), "base_span": tuple(s.get("base_span") or (0, 0))})
            for s in data.get("seeded") or []
        ]
        payload["units"] = [Unit(**{**u, "span": tuple(u["span"])}) for u in data.get("units") or []]
        return cls(**payload)


def dispatch_lines(dossier: EditorialDossier, count: int = DISPATCH_LINES) -> list[tuple[str, str | None]]:
    """Romy's dispatch without a session: the claims as lines (facts first), then the summary.

    Copied in spirit from ``encounter.RevueEncounter.close`` (which needs a session and a
    provider): there the body is the claims shown, topped up from the summary. Here every
    line that can be a claim is one, so the fact checks can be rerun on each.
    """

    claims = dossier.facts() + dossier.interpretations() + dossier.forecasts()
    lines: list[tuple[str, str | None]] = [(re.sub(r"\s+", " ", c.fr).strip(), c.id) for c in claims[:count]]
    for sentence in _sentences(dossier.summary_fr):
        if len(lines) >= count:
            break
        if all(sentence != line for line, _ in lines):
            lines.append((sentence, None))
    return lines[:count]


def _source_names(dossier: EditorialDossier, claim_ids: Sequence[str | None]) -> list[str]:
    by_id = dossier.claims_by_id()
    names = []
    for claim_id in claim_ids:
        if claim_id and claim_id in by_id:
            source = dossier.source_by_id(by_id[claim_id].source_id)
            if source and source.name not in names:
                names.append(source.name)
    return names


@dataclass
class _Candidate:
    rule: str | None
    source: str
    error_id: str | None = None
    grammar_point: str = ""
    learner: str | None = None
    correct: str | None = None


def _overlaps(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def _finders(candidate: _Candidate) -> list[Callable[[str], list[Site]]]:
    finders: list[Callable[[str], list[Site]]] = []
    if candidate.learner and candidate.correct:
        finders.append(lambda s: _verbatim_sites(s, candidate.learner, candidate.correct))
    if candidate.rule:
        finders.append(RULES[candidate.rule].sites)
    return finders


def _all_sites(candidate: _Candidate, sentences: list[str]) -> list[tuple[int, Site]]:
    return [(index, site) for finder in _finders(candidate) for index, s in enumerate(sentences) for site in finder(s)]


def _free(index: int, site: Site, taken: dict[int, list[tuple[int, int]]]) -> bool:
    # A margin of two characters keeps two seeds from touching: at least a word between.
    widened = (site.start - 2, site.end + 2)
    return not any(_overlaps(widened, span) for span in taken.get(index, []))


def _place(
    candidate: _Candidate,
    sentences: list[str],
    taken: dict[int, list[tuple[int, int]]],
    *,
    later: Sequence[tuple[int, Site]] = (),
) -> tuple[int, Site] | None:
    """A free site for a candidate: its verbatim form before its rule; among the free sites,
    the one that blocks the fewest sites the later candidates could use, then the sentence
    with the fewest seeds so far, then reading order."""

    for finder in _finders(candidate):
        free = [
            (index, site)
            for index, sentence in enumerate(sentences)
            for site in finder(sentence)
            if _free(index, site, taken)
        ]
        if not free:
            continue

        def cost(pair: tuple[int, Site]) -> tuple[int, int, int, int]:
            index, site = pair
            widened = (site.start - 2, site.end + 2)
            blocks = sum(1 for i, other in later if i == index and _overlaps(widened, (other.start, other.end)))
            return (blocks, len(taken.get(index, [])), index, site.start)

        return min(free, key=cost)
    return None


def _place_all(
    candidates: Sequence[_Candidate], lines: list[str], quota: int
) -> tuple[list[tuple[int, Site, _Candidate]], list[_Candidate]]:
    """Place candidates in priority order until the quota; the ones with no free site are skipped."""

    taken: dict[int, list[tuple[int, int]]] = {}
    placed: list[tuple[int, Site, _Candidate]] = []
    skipped: list[_Candidate] = []
    for position, candidate in enumerate(candidates):
        if len(placed) >= quota:
            break
        later = [pair for other in candidates[position + 1 :] for pair in _all_sites(other, lines)]
        spot = _place(candidate, lines, taken, later=later)
        if spot is None:
            skipped.append(candidate)
            continue
        index, site = spot
        taken.setdefault(index, []).append((site.start, site.end))
        placed.append((index, site, candidate))
    return placed, skipped


def apply_sites(sentence: str, sites: list[tuple[Site, int]]) -> tuple[str, list[tuple[int, tuple[int, int]]]]:
    """``sentence`` with each site's wrong form; returns the new spans by the caller's tag."""

    out, cursor, spans = [], 0, []
    offset = 0
    for site, tag in sorted(sites, key=lambda pair: pair[0].start):
        out.append(sentence[cursor : site.start])
        start = site.start + offset
        out.append(site.wrong)
        spans.append((tag, (start, start + len(site.wrong))))
        offset += len(site.wrong) - (site.end - site.start)
        cursor = site.end
    out.append(sentence[cursor:])
    return "".join(out), spans


def unseed(sentences: Sequence[str], seeds: Sequence[Seed]) -> list[str]:
    """The seeded sentences with every span put back to its correct form."""

    restored = []
    for index, sentence in enumerate(sentences):
        own = sorted((s for s in seeds if s.sentence_index == index), key=lambda s: s.span[0])
        out, cursor = [], 0
        for seed in own:
            out.append(sentence[cursor : seed.span[0]])
            out.append(seed.correct_fr)
            cursor = seed.span[1]
        out.append(sentence[cursor:])
        restored.append("".join(out))
    return restored


def differs_only_in_spans(base: Sequence[str], seeded: Sequence[str], seeds: Sequence[Seed]) -> bool:
    """The stronger check: outside the spans, seeded and base text are identical, character
    for character; inside, the seeded text holds ``wrong_fr`` and the base ``correct_fr``."""

    if len(base) != len(seeded):
        return False
    for seed in seeds:
        start, end = seed.span
        if seeded[seed.sentence_index][start:end] != seed.wrong_fr or seed.wrong_fr == seed.correct_fr:
            return False
        b0, b1 = seed.base_span
        if base[seed.sentence_index][b0:b1] != seed.correct_fr:
            return False
    return list(unseed(seeded, seeds)) == list(base)


def _verdicts(results: Sequence[CheckResult]) -> list[tuple[bool, str, str | None, Any]]:
    return [(r.ok, r.check, r.reason, r.detail.get("claim_id")) for r in results]


def fact_checks(
    dossier: EditorialDossier,
    lines: Sequence[str],
    claim_ids: Sequence[str | None],
    source_texts: dict[str, str],
) -> dict[str, Any]:
    """Anchor and Attribution on the dossier, and again on the claims as ``lines`` state them.

    ``unchanged`` is True when every verdict is the same: the draft states no fact the
    dossier does not.
    """

    original = check_anchor(dossier, source_texts) + check_attribution(dossier)
    restated = dossier.model_copy(deep=True)
    by_id = {claim.id: claim for claim in restated.claims}
    for line, claim_id in zip(lines, claim_ids, strict=True):
        if claim_id and claim_id in by_id:
            by_id[claim_id].fr = line
    rerun = check_anchor(restated, source_texts) + check_attribution(restated)
    return {
        "unchanged": _verdicts(original) == _verdicts(rerun),
        "anchor": [{"claim_id": r.detail.get("claim_id"), "ok": r.ok, "reason": r.reason} for r in rerun if r.check == "anchor"],
        "attribution": [
            {"claim_id": r.detail.get("claim_id"), "ok": r.ok, "reason": r.reason} for r in rerun if r.check == "attribution"
        ],
    }


def source_texts_for(dossier: EditorialDossier) -> dict[str, str]:
    from app.services.revue.evergreen import evergreen_source_texts

    try:
        from app.services.revue.weekly import source_texts_for_week

        return source_texts_for_week(dossier.week)
    except Exception as exc:  # noqa: BLE001 - the evergreens' excerpts at least
        logger.bind(dossier=dossier.id).warning("correcteur: week source texts unavailable ({})", exc)
        return evergreen_source_texts()


# ---------------------------------------------------------------------------
# The provider (one rewrite, only when the rules cannot place the quota)
# ---------------------------------------------------------------------------


class CorrecteurProvider(Protocol):
    name: str

    def rewrite(self, context: dict[str, Any]) -> dict[str, Any]: ...


_REWRITE_TASK = (
    "Rewrite this one French sentence from a news dispatch so that it naturally contains a CORRECT use of "
    "the grammar point «{point}» (for example: {example}). Keep every fact, number, date and name exactly; "
    "do not add opinions; keep it at CEFR {band} and under 30 words. The sentence must stay correct French. "
    'Return JSON: {{"sentence_fr": str}}'
)
_POINT_EXAMPLES = {
    "pp_agreement": "«la grève a été annoncée», «elles sont arrivées»",
    "contraction": "«le début du mois», «au moins»",
    "accent": "«à», «déposé», «grève»",
    "verb_ending": "«ils ont annoncé», «pour réorganiser»",
    "adj_gender": "«une grande ville», «des lignes importantes»",
    "plural_s": "«les voyageurs», «deux jours»",
}


@dataclass
class FakeCorrecteurProvider:
    """Answers from ``script`` (one dict per call), else returns the sentence unchanged."""

    name: str = "fake-correcteur"
    script: list[dict[str, Any]] = field(default_factory=list)
    calls: list[dict[str, Any]] = field(default_factory=list)
    spent_usd: float = 0.0

    def rewrite(self, context: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(context)
        if self.script:
            return dict(self.script.pop(0))
        return {"sentence_fr": context.get("sentence_fr")}


@dataclass
class LLMCorrecteurProvider:
    """The Revue's JSON plumbing (``encounter.OpenAIRevueProvider.ask_json``), one call."""

    name: str = "llm-correcteur"
    _inner: Any = None

    @property
    def spent_usd(self) -> float:
        return float(getattr(self._inner, "spent_usd", 0.0) or 0.0)

    def rewrite(self, context: dict[str, Any]) -> dict[str, Any]:
        if self._inner is None:
            from app.services.revue.encounter import OpenAIRevueProvider

            self._inner = OpenAIRevueProvider(max_tokens=1200)
        instructions = _REWRITE_TASK.format(
            point=context["point_fr"], example=context["example"], band=context["band"]
        )
        return self._inner.ask_json(
            instructions, {"sentence_fr": context["sentence_fr"]}, temperature=0.3, label="correcteur_rewrite"
        )


def default_provider() -> CorrecteurProvider | None:
    from app.config import settings

    if getattr(settings, "OPENAI_API_KEY", None) or getattr(settings, "ANTHROPIC_API_KEY", None):
        return LLMCorrecteurProvider()
    return None


_NUMBER = re.compile(r"\d+")
_NAME = re.compile(r"(?<=\s)[A-ZÀ-Ý][\w-]+")


def _keeps_facts(before: str, after: str) -> bool:
    """A rewrite keeps every number and every capitalised name (not the sentence's first word)."""

    if sorted(_NUMBER.findall(before)) != sorted(_NUMBER.findall(after)):
        return False
    return set(_NAME.findall(" " + before.split(" ", 1)[-1])) <= set(_NAME.findall(" " + after))


def _try_rewrite(
    provider: CorrecteurProvider,
    candidate: _Candidate,
    *,
    dossier: EditorialDossier,
    lines: list[str],
    claim_ids: list[str | None],
    placed: Sequence[tuple[int, Site, _Candidate]],
    band: str,
    source_texts: dict[str, str],
) -> tuple[dict[str, Any], str | None]:
    """Ask for one line rewritten to contain ``candidate``'s point. The new line is accepted
    only when it keeps every number and name, the fact checks give the same verdicts, and
    the rule then finds a site in it. Returns the record (kept in the draft) and the line."""

    rule = RULES[candidate.rule]  # type: ignore[index]
    seeds_on = {index: sum(1 for i, _, _ in placed if i == index) for index in range(len(lines))}
    errata_on = {index: sum(1 for i, _, c in placed if i == index and c.source == "errata") for index in range(len(lines))}
    # The line with the fewest seeds and the fewest of the learner's own (a rewrite may
    # move them), a claim line (fact-checked) before a summary one.
    index = min(range(len(lines)), key=lambda i: (seeds_on[i], errata_on[i], claim_ids[i] is None, i))
    record: dict[str, Any] = {
        "sentence_index": index, "before": lines[index], "after": None, "point": rule.id,
        "provider": getattr(provider, "name", "provider"), "accepted": False, "reason": None,
    }
    context = {
        "sentence_fr": lines[index],
        "point": rule.id,
        "point_fr": rule.label_fr,
        "example": _POINT_EXAMPLES.get(rule.id, ""),
        "band": band,
    }
    try:
        raw = provider.rewrite(context)
    except Exception as exc:  # noqa: BLE001 - a short draft is fine; a broken one is not
        logger.warning("correcteur: rewrite failed ({}); the draft goes out short", exc)
        record["reason"] = "provider_failed"
        return record, None
    sentence = re.sub(r"\s+", " ", str((raw or {}).get("sentence_fr") or "")).strip()
    record["after"] = sentence
    if not sentence or sentence == lines[index]:
        record["reason"] = "unchanged"
        return record, None
    if not _keeps_facts(lines[index], sentence):
        record["reason"] = "numbers_or_names_moved"
        return record, None
    trial = list(lines)
    trial[index] = sentence
    checks = fact_checks(dossier, trial, claim_ids, source_texts)
    record["checks_unchanged"] = checks["unchanged"]
    if not checks["unchanged"]:
        record["reason"] = "fact_checks_changed"
        return record, None
    if not rule.sites(sentence):
        record["reason"] = "no_site_after_rewrite"
        return record, None
    record["accepted"] = True
    return record, sentence


# ---------------------------------------------------------------------------
# Units and options
# ---------------------------------------------------------------------------

_PAIR = re.compile(r"\b(de|à|a) (les?)\b", re.IGNORECASE)


def units_for(sentence_index: int, sentence: str) -> list[Unit]:
    """The sentence's tappable units: words, with «de le» / «à les» kept as one."""

    toks = tokens(sentence)
    merged: list[tuple[int, int]] = []
    skip = set()
    for i, tok in enumerate(toks):
        if i in skip:
            continue
        if i + 1 < len(toks):
            pair = sentence[tok.start : toks[i + 1].end]
            if _PAIR.fullmatch(pair) and pair.split(" ")[0].casefold() in {"de", "à"}:
                merged.append((tok.start, toks[i + 1].end))
                skip.add(i + 1)
                continue
        merged.append((tok.start, tok.end))
    return [Unit(sentence_index, span, sentence[span[0] : span[1]]) for span in merged]


#: Words after which a noun's number is in play (the plural rule's options need one).
_NOUN_CUES = PLURAL_DETS | frozenset("le la l un une ce cet cette mon ma ton ta son sa notre votre leur chaque".split())


def variants_for(text: str, *, prev: str | None = None) -> list[str]:
    """Every form the rules make from ``text``, in rule order, without ``text`` itself.

    ``prev`` is the word before: the plural rule only offers a form after a determiner
    or a number (otherwise it would offer «Dan» for «Dans»).
    """

    seen = {text.casefold()}
    out = []
    low_prev = (prev or "").casefold()
    plural_ok = low_prev in _NOUN_CUES or low_prev.isdigit()
    for rule_id in ("contraction", "pp_agreement", "verb_ending", "adj_gender", "accent", "plural_s"):
        if rule_id == "plural_s" and not plural_ok:
            continue
        if len(text) < 3 and rule_id not in {"contraction", "adj_gender", "accent"}:
            continue
        for form in RULES[rule_id].variants(text):
            if form and form.casefold() not in seen:
                seen.add(form.casefold())
                out.append(form)
    return out


def options_for(text: str, *, correct: str | None = None, prev: str | None = None) -> list[str] | None:
    """Three forms (the unit's own and two others; the correct one always among them), sorted."""

    variants = variants_for(text, prev=prev)
    picked = [text]
    if correct and correct.casefold() != text.casefold():
        picked.append(correct)
    for form in variants:
        if len(picked) >= 3:
            break
        if form.casefold() not in {p.casefold() for p in picked}:
            picked.append(form)
    if len(picked) < 2:
        return None
    return sorted(picked, key=lambda form: (strip_accents(form).casefold(), form))


# ---------------------------------------------------------------------------
# draft_for
# ---------------------------------------------------------------------------


def band_for(user: User) -> str:
    from app.services.chrome_language import level_band

    return policy.normalize_band(level_band(getattr(user, "cefr_estimate", None)) or "A1")


def _subskills(db: Session, concept_ids: set[int]) -> dict[int, str]:
    if not concept_ids:
        return {}
    from app.db.models.grammar import GrammarConcept

    rows = db.execute(select(GrammarConcept.id, GrammarConcept.subskill).where(GrammarConcept.id.in_(concept_ids))).all()
    return {row[0]: row[1] for row in rows if row[1]}


def _errata_candidates(db: Session, user: User) -> list[_Candidate]:
    from app.services.journey_errata import errata_targets_for_user

    targets = errata_targets_for_user(db, user, limit=8)
    subskills = _subskills(db, {t.concept_id for t in targets if t.concept_id})
    out = []
    for target in targets:
        rule = rule_for_target(target, subskill=subskills.get(target.concept_id or -1))
        point = RULES[rule].label_fr if rule else (target.label or "")
        out.append(
            _Candidate(
                rule=rule,
                source="errata",
                error_id=target.error_id,
                grammar_point=point,
                learner=target.example_learner,
                correct=target.example_correct,
            )
        )
    return out


def draft_for(
    db: Session,
    user: User,
    dossier: EditorialDossier,
    band: str,
    *,
    provider: CorrecteurProvider | None = None,
    source_texts: dict[str, str] | None = None,
    week_number: int | None = None,
) -> Draft:
    """Romy's dispatch for ``dossier``, seeded for this learner (see the module docstring)."""

    band = policy.normalize_band(band)
    quota = QUOTA[band]
    pairs = dispatch_lines(dossier)
    lines = [line for line, _ in pairs]
    claim_ids = [claim_id for _, claim_id in pairs]
    source_texts = source_texts if source_texts is not None else source_texts_for(dossier)

    # The learner's own errata first; the band's classiques fill what they cannot.
    candidates = _errata_candidates(db, user) + [
        _Candidate(rule=rule_id, source="classique", grammar_point=RULES[rule_id].label_fr)
        for rule_id in CLASSIQUES[band]
    ]

    placed, skipped = _place_all(candidates, lines, quota)

    rewrite_record: dict[str, Any] | None = None
    first = next((c for c in skipped if c.rule), None)
    if len(placed) < quota and provider is not None and first is not None:
        rewrite_record, new_line = _try_rewrite(
            provider, first, dossier=dossier, lines=lines, claim_ids=claim_ids, placed=placed,
            band=band, source_texts=source_texts,
        )
        if new_line is not None:
            trial = list(lines)
            trial[rewrite_record["sentence_index"]] = new_line
            replaced, _ = _place_all(candidates, trial, quota)
            if len(replaced) > len(placed):
                lines, placed = trial, replaced
            else:
                rewrite_record.update(accepted=False, reason="no_gain")

    # Build the seeded sentences.
    seeds: list[Seed] = []
    seeded_lines = list(lines)
    for index in range(len(lines)):
        own = [(site, n) for n, (i, site, _) in enumerate(placed) if i == index]
        if not own:
            continue
        seeded_lines[index], spans = apply_sites(lines[index], own)
        for tag, span in spans:
            _, site, candidate = placed[tag]
            seeds.append(
                Seed(
                    sentence_index=index,
                    span=span,
                    wrong_fr=site.wrong,
                    correct_fr=site.correct,
                    error_id=candidate.error_id,
                    grammar_point=candidate.grammar_point or (RULES[candidate.rule].label_fr if candidate.rule else ""),
                    source=candidate.source,
                    rule=candidate.rule or "verbatim",
                    base_span=(site.start, site.end),
                )
            )
    seeds.sort(key=lambda s: (s.sentence_index, s.span[0]))

    spans_only = differs_only_in_spans(lines, seeded_lines, seeds)
    if not spans_only:  # pragma: no cover - a bug in apply_sites, never a learner's problem
        raise RuntimeError("correcteur: the seeded text differs outside its spans")
    checks = fact_checks(dossier, unseed(seeded_lines, seeds), claim_ids, source_texts)
    checks["spans_only"] = spans_only

    options = band in {"A1", "A2"}
    by_span = {(s.sentence_index, s.span): s for s in seeds}
    units: list[Unit] = []
    for index, sentence in enumerate(seeded_lines):
        previous: str | None = None
        for unit in units_for(index, sentence):
            if options:
                seed = by_span.get((index, unit.span))
                unit.options = options_for(unit.text, correct=seed.correct_fr if seed else None, prev=previous)
            previous = unit.text.split(" ")[-1]
            units.append(unit)

    names = _source_names(dossier, claim_ids)
    number = week_number
    if number is None:
        try:
            number = parse_week(dossier.week)[1]
        except ValueError:
            number = None
    return Draft(
        dossier_id=dossier.id,
        band=band,
        title_fr=dossier.title_fr,
        kicker_fr="Le brouillon de Romy" + (f" · semaine {number}" if number else ""),
        byline_fr="Romy Tremblay · d'après " + " et ".join(names) if names else "Romy Tremblay",
        sentences=seeded_lines,
        base_sentences=lines,
        claim_ids=claim_ids,
        seeded=seeds,
        units=units,
        checks=checks,
        rewrite=rewrite_record,
        short_by=max(0, quota - len(seeds)),
    )


# ---------------------------------------------------------------------------
# Grading (§4.2)
# ---------------------------------------------------------------------------

#: Romy's one line at the end, by outcome and band group (authored, French).
ROMY_LINES: dict[str, dict[str, str]] = {
    "A": {
        "all_repaired": "Parfait ! Le papier est propre. Merci, correcteur !",
        "all_noticed": "Tu as tout vu ! Je corrige les formes, et le papier part.",
        "most": "Bien vu ! Il restait une ou deux fautes. Regarde en rouge.",
        "few": "Merci ! Il restait des fautes. Regarde-les en rouge.",
        "none": "Pas grave ! Regarde les fautes en rouge. La prochaine fois, tu les vois.",
    },
    "B": {
        "all_repaired": "Rien ne t'a échappé : le papier part tel quel à l'imprimerie. Merci !",
        "all_noticed": "Tu as tout repéré ; il ne restait qu'à trouver la bonne forme. Je m'en charge.",
        "most": "Bon œil ! Quelques fautes sont passées ; je te les montre en rouge.",
        "few": "Merci pour la relecture. Plusieurs fautes sont passées : regarde-les avant l'impression.",
        "none": "Celles-là t'ont échappé, ça arrive à tout le monde. Regarde-les : elles reviendront.",
    },
}


def romy_line(band: str, counts: dict[str, int]) -> str:
    group = "A" if policy.normalize_band(band) in {"A1", "A2"} else "B"
    seeded = counts["seeded"]
    noticed = counts["repaired"] + counts["noticed"]
    if seeded and counts["repaired"] == seeded:
        key = "all_repaired"
    elif seeded and noticed == seeded:
        key = "all_noticed"
    elif noticed == 0:
        key = "none"
    elif noticed * 2 >= seeded:
        key = "most"
    else:
        key = "few"
    return ROMY_LINES[group][key]


def _repairs(sentence: str, seed: Seed, mark: dict[str, Any]) -> bool:
    fix = mark.get("fix_fr")
    if fix is None or not str(fix).strip():
        return False
    if _fold_answer(fix) == _fold_answer(seed.correct_fr):
        return True
    m0, m1 = mark["span"]
    s0, s1 = seed.span
    u0, u1 = min(m0, s0), max(m1, s1)
    learner = sentence[u0:m0] + str(fix) + sentence[m1:u1]
    expected = sentence[u0:s0] + seed.correct_fr + sentence[s1:u1]
    return _fold_answer(learner) == _fold_answer(expected)


def grade(draft: Draft, marks: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """The four outcomes for a draft and the learner's marks (pure; no writes)."""

    clean = []
    for mark in marks:
        index = int(mark["sentence_index"])
        if index >= len(draft.sentences):
            continue
        length = len(draft.sentences[index])
        start, end = max(0, int(mark["span"][0])), min(length, int(mark["span"][1]))
        if end <= start:
            continue
        clean.append({**mark, "sentence_index": index, "span": [start, end]})

    outcomes, used = [], set()
    for seed in draft.seeded:
        touching = [
            (n, m) for n, m in enumerate(clean)
            if m["sentence_index"] == seed.sentence_index and _overlaps(tuple(m["span"]), seed.span)
        ]
        used.update(n for n, _ in touching)
        sentence = draft.sentences[seed.sentence_index]
        repairing = next((m for _, m in touching if _repairs(sentence, seed, m)), None)
        if repairing is not None:
            outcome, fix, picked = "repaired", repairing.get("fix_fr"), bool(repairing.get("picked"))
        elif touching:
            outcome, fix, picked = "noticed", touching[0][1].get("fix_fr"), False
        else:
            outcome, fix, picked = "missed", None, False
        outcomes.append(
            {
                "sentence_index": seed.sentence_index,
                "span": list(seed.span),
                "wrong_fr": seed.wrong_fr,
                "correct_fr": seed.correct_fr,
                "grammar_point": seed.grammar_point,
                "source": seed.source,
                "outcome": outcome,
                "fix_fr": fix,
                "picked": picked,
                "error_id": seed.error_id,
            }
        )
    false_alarms = [
        {
            "sentence_index": m["sentence_index"],
            "span": m["span"],
            "text_fr": draft.sentences[m["sentence_index"]][m["span"][0] : m["span"][1]],
            "fix_fr": m.get("fix_fr"),
        }
        for n, m in enumerate(clean)
        if n not in used
    ]
    counts = {
        "seeded": len(outcomes),
        "repaired": sum(o["outcome"] == "repaired" for o in outcomes),
        "noticed": sum(o["outcome"] == "noticed" for o in outcomes),
        "missed": sum(o["outcome"] == "missed" for o in outcomes),
        "false_alarms": len(false_alarms),
    }
    return {
        "dossier_id": draft.dossier_id,
        "sentences": draft.sentences,
        "outcomes": outcomes,
        "false_alarms": false_alarms,
        "counts": counts,
        "romy_line_fr": romy_line(draft.band, counts),
        "releve_href": RELEVE_HREF,
    }


def write_evidence(db: Session, user: User, outcomes: Sequence[dict[str, Any]], *, now: datetime | None = None) -> list[str]:
    """Errata memory: a repair is transform evidence (assisted when picked), a notice is
    recognition; both move the erratum's next review into the future, so it stops being
    seeded. A missed erratum is left due. Classiques write nothing. Returns the ids written."""

    from app.services.error_memory import ErrorMemoryService, erratum_repair_evidence

    service = ErrorMemoryService(db)
    written = []
    for outcome in outcomes:
        error_id = outcome.get("error_id")
        if not error_id or outcome["outcome"] == "missed":
            continue
        repaired = outcome["outcome"] == "repaired"
        rating = (3 if outcome.get("picked") else 4) if repaired else 3
        try:
            key = uuid.UUID(str(error_id))
        except ValueError:
            continue
        row = service.review_error(
            user=user,
            error_id=key,
            rating=rating,
            repaired=repaired,
            now=now,
            evidence=erratum_repair_evidence(rating=rating, repaired=repaired),
        )
        if row is not None:
            written.append(str(error_id))
    return written


# ---------------------------------------------------------------------------
# Rows, views, the week
# ---------------------------------------------------------------------------


def public_view(row: RevueCorrection) -> dict[str, Any]:
    """What the learner's client sees: no spans, no base text, no checks."""

    draft = Draft.from_json(row.draft)
    return {
        "id": str(row.id),
        "dossier_id": draft.dossier_id,
        "band": draft.band,
        "kicker_fr": draft.kicker_fr,
        "title_fr": draft.title_fr,
        "byline_fr": draft.byline_fr,
        "sentences": draft.sentences,
        "units": [
            {"sentence_index": u.sentence_index, "span": list(u.span), "text": u.text, "options": u.options}
            for u in draft.units
        ],
        "errors_count": len(draft.seeded),
        "options_enabled": draft.band in {"A1", "A2"},
        "result": result_view(row) if row.result else None,
    }


def result_view(row: RevueCorrection) -> dict[str, Any]:
    result = dict(row.result or {})
    result["outcomes"] = [{k: v for k, v in o.items() if k not in {"error_id", "picked"}} for o in result.get("outcomes") or []]
    result.pop("evidence", None)
    return {"id": str(row.id), **result}


def create_correction(
    db: Session,
    user: User,
    dossier: EditorialDossier,
    *,
    provider: CorrecteurProvider | None = None,
    band: str | None = None,
    week_number: int | None = None,
) -> RevueCorrection:
    draft = draft_for(db, user, dossier, band or band_for(user), provider=provider, week_number=week_number)
    row = RevueCorrection(user_id=user.id, dossier_id=dossier.id, draft=draft.to_json())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def grade_marks(db: Session, user: User, row: RevueCorrection, marks: Sequence[dict[str, Any]]) -> RevueCorrection:
    """Grade once; a second «Bon à tirer» returns the stored result."""

    if row.result:
        return row
    draft = Draft.from_json(row.draft)
    result = grade(draft, marks)
    result["evidence"] = write_evidence(db, user, result["outcomes"])
    row.result = result
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def owned_correction(db: Session, user: User, correction_id: str) -> RevueCorrection | None:
    try:
        key = uuid.UUID(str(correction_id))
    except ValueError:
        return None
    return db.scalar(select(RevueCorrection).where(RevueCorrection.id == key, RevueCorrection.user_id == user.id))


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def corrected_this_week(db: Session, user: User, week: str) -> list[str]:
    from app.services.revue.encounter import PARIS

    monday, _ = week_bounds(week)
    start = datetime(monday.year, monday.month, monday.day, tzinfo=PARIS)
    rows = db.scalars(select(RevueCorrection).where(RevueCorrection.user_id == user.id)).all()
    return sorted({row.dossier_id for row in rows if row.result and _aware(row.created_at) >= start})


def week_for(db: Session, user: User, week: str) -> dict[str, Any]:
    from app.services.revue.encounter import available_dossiers, week_view

    done = set(corrected_this_week(db, user, week))
    view = week_view(week)
    return {
        "week": week,
        "label": view.label,
        "dossiers": [
            {"id": d.id, "title_fr": d.title_fr, "topic": d.topic, "evergreen": d.evergreen}
            for d in available_dossiers(week)
            if d.id not in done
        ],
        "corrected": sorted(done),
    }


def find_any_dossier(dossier_id: str, week: str) -> EditorialDossier | None:
    """The week's dossier with that id, or any evergreen (they are evergreen)."""

    from app.services.revue.encounter import find_dossier
    from app.services.revue.evergreen import load_evergreens

    found = find_dossier(dossier_id, week)
    if found is not None:
        return found
    return next((d for d in load_evergreens() if d.id == dossier_id), None)


__all__ = [
    "CLASSIQUES",
    "QUOTA",
    "RULES",
    "CorrecteurProvider",
    "Draft",
    "FakeCorrecteurProvider",
    "LLMCorrecteurProvider",
    "Seed",
    "Site",
    "apply_sites",
    "band_for",
    "create_correction",
    "differs_only_in_spans",
    "dispatch_lines",
    "draft_for",
    "fact_checks",
    "find_any_dossier",
    "grade",
    "grade_marks",
    "options_for",
    "owned_correction",
    "public_view",
    "romy_line",
    "rule_for_target",
    "unseed",
    "units_for",
    "variants_for",
    "week_for",
    "write_evidence",
]
