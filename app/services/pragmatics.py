"""WP-33 — register and pragmatics, detected deterministically and explained.

The research this package answers (INNOVATION-WORK-PACKAGES-2026-09-10 §1):
instruction beats exposure, and **explicit meta-pragmatic** instruction has the
larger effect. So a register slip must be *named and explained* — "ici on dit
vous : c'est votre propriétaire" — not merely reacted to in character.

What this module is
-------------------

A pure, provider-free detector bank plus one narrow model call:

* :func:`address_register` — which register a French text addresses its reader
  in, or ``None`` when the text says nothing either way (or says both).
* :func:`politeness_markers` — greeting, thanks, please, conditional softener,
  apology, closing.
* :func:`bare_request_finding` — an imperative or a blunt ``je veux`` used as a
  request at A1/A2, with no softener anywhere in the utterance.
* :func:`assess_register` — the three of them combined into one verdict.
* :func:`model_register_gap` — an optional model opinion on the one thing the
  detectors genuinely cannot see (over-familiarity, bluntness, over-formality in
  a text that carries no address marker at all).

Three rules the rest of the codebase relies on
----------------------------------------------

1. **Honest "non évalué".** A turn that never addresses the counterpart, a scene
   whose expected register is unknown, and a model call that fails all produce
   :data:`RegisterVerdict.NOT_EVALUATED`. Nothing here guesses a verdict, and a
   missing verdict is never silently a pass.
2. **The model never overrules a detector.** :func:`model_register_gap` is only
   consulted when :func:`assess_register` returned ``NOT_EVALUATED``; a
   deterministic tu/vous verdict is final.
3. **No pronunciation or accent judgement, ever** (owner WON'T-DO, STATUS
   2026-09-10 WP-27). Speech becomes text and is judged as text. The system
   prompt below says so to the model, and
   ``tests/test_pragmatics_register.py`` scans this package's sources for the
   vocabulary that would betray it.

Spans are located in the learner's **raw** text, never the folded form, because
``Correction.is_valid_for`` requires the span to survive verbatim in what the
learner actually typed — including the U+2019 apostrophe iOS inserts.
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import UUID

from loguru import logger

from app.config import settings
from app.services.journey_contracts import normalize_answer_text

PRAGMATICS_POLICY_VERSION = "journey-pragmatics-v1"

#: Bands at which a bare imperative is a pragmatic finding rather than a style
#: preference. Above them the learner is expected to choose deliberately.
IMPERATIVE_SENSITIVE_BANDS = frozenset({"A1", "A2"})

#: One model call, one attempt, a tiny budget. This is an opinion on a sentence,
#: not a generation.
MODEL_MAX_TOKENS = 200


class Register(StrEnum):
    TU = "tu"
    VOUS = "vous"


class RegisterVerdict(StrEnum):
    #: The learner addressed the counterpart the way the counterpart addresses
    #: them, and asked rather than ordered.
    RESPECTED = "respected"
    #: A real, nameable slip: the wrong address register, or a bare command.
    SLIPPED = "slipped"
    #: Nothing observable. Never a pass and never a failure.
    NOT_EVALUATED = "not_evaluated"


# --------------------------------------------------------------------------
# Finding codes. Each one maps to exactly one `pragmatics.*` key in
# app/services/learner_copy.py, in en/de/fr.
# --------------------------------------------------------------------------

SLIP_TU_FOR_VOUS = "register_slip_tu_for_vous"
SLIP_VOUS_FOR_TU = "register_slip_vous_for_tu"
MIXED_REGISTER = "register_mixed"
BARE_IMPERATIVE = "bare_imperative"
BLUNT_WANT = "blunt_want"
MISSING_GREETING = "missing_greeting"
MISSING_POLITENESS = "missing_politeness"
MISSING_CLOSING = "missing_closing"

#: Findings that make the turn a slip. The rest are advisory: a mid-scene turn
#: with no "bonjour" is normal French, not a mistake.
SLIP_CODES = frozenset({SLIP_TU_FOR_VOUS, SLIP_VOUS_FOR_TU, MIXED_REGISTER, BARE_IMPERATIVE, BLUNT_WANT})

_COPY_KEYS: dict[str, str] = {
    SLIP_TU_FOR_VOUS: "pragmatics.register_use_vous",
    SLIP_VOUS_FOR_TU: "pragmatics.register_use_tu",
    MIXED_REGISTER: "pragmatics.register_mixed",
    BARE_IMPERATIVE: "pragmatics.bare_imperative",
    BLUNT_WANT: "pragmatics.blunt_want",
    MISSING_GREETING: "pragmatics.missing_greeting",
    MISSING_POLITENESS: "pragmatics.missing_politeness",
    MISSING_CLOSING: "pragmatics.missing_closing",
}


@dataclass(frozen=True, slots=True)
class RegisterFinding:
    """One nameable pragmatic observation about one learner turn.

    ``span``/``replacement`` are present only when a single-word repair is
    unambiguous. A ``vous`` that should be ``tu`` also moves the verb
    (« vous pouvez » → « tu peux »), so those cases carry the explanation and no
    fabricated one-word fix.
    """

    code: str
    span: str | None = None
    replacement: str | None = None

    @property
    def copy_key(self) -> str:
        return _COPY_KEYS.get(self.code, "pragmatics.register_not_evaluated")

    @property
    def is_slip(self) -> bool:
        return self.code in SLIP_CODES


@dataclass(frozen=True, slots=True)
class RegisterAssessment:
    """What one turn showed about register and politeness."""

    verdict: RegisterVerdict
    expected: str | None = None
    observed: str | None = None
    findings: tuple[RegisterFinding, ...] = ()
    #: ``"detector"``, ``"model"`` or ``"none"`` — never inferred by a reader.
    source: str = "detector"

    @property
    def evaluated(self) -> bool:
        return self.verdict is not RegisterVerdict.NOT_EVALUATED

    @property
    def respected(self) -> bool:
        return self.verdict is RegisterVerdict.RESPECTED

    @property
    def slip(self) -> RegisterFinding | None:
        """The one finding worth foregrounding, or ``None``."""

        for finding in self.findings:
            if finding.is_slip:
                return finding
        return None


NOT_EVALUATED = RegisterAssessment(verdict=RegisterVerdict.NOT_EVALUATED, source="none")


# --------------------------------------------------------------------------
# Folding
# --------------------------------------------------------------------------

def fold(value: str | None) -> str:
    """Lower-cased, accent-free, punctuation-free — one space between tokens.

    Mirrors ``journey_learning.fold_for_comparison`` deliberately (iOS smart
    quotes first) but is kept local so this module stays importable without the
    ORM: a detector must be usable from a test with no database.
    """

    text = normalize_answer_text(value).lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^0-9a-z\s]+", " ", text)
    return " ".join(text.split())


def _padded(value: str | None) -> str:
    return f" {fold(value)} "


# --------------------------------------------------------------------------
# 1. Address register
# --------------------------------------------------------------------------

#: Folded, space-padded markers. ``t es`` is what ``t'es`` folds to.
_TU_MARKERS: tuple[str, ...] = (
    " tu ", " toi ", " ton ", " ta ", " tes ", " te ", " t es ", " t as ", " tien ",
    " tienne ", " tutoie ", " tutoyer ",
)
_VOUS_MARKERS: tuple[str, ...] = (
    " vous ", " votre ", " vos ", " votres ", " vouvoie ", " vouvoyer ",
)

#: Word-for-word swaps that are safe on their own: the verb does not move with
#: them and no gender has to be guessed. « votre » is absent on purpose — it
#: becomes *ton* or *ta* depending on a noun this module does not analyse, and
#: a correction that changes the gender of the learner's noun is worse than none.
#: ``(pattern, group, replacement)`` — the group is the part actually swapped,
#: so a pattern may look at its context without correcting it.
_SAFE_SWAPS: dict[str, tuple[tuple[re.Pattern[str], int, str], ...]] = {
    "vous": (
        (re.compile(r"\b(tes)\b", re.IGNORECASE), 1, "vos"),
        (re.compile(r"\b(ton)\b", re.IGNORECASE), 1, "votre"),
        (re.compile(r"\b(ta)\b(?=\s)", re.IGNORECASE), 1, "votre"),
        (re.compile(r"\b(toi)\b", re.IGNORECASE), 1, "vous"),
        (re.compile(r"\b(te)\b", re.IGNORECASE), 1, "vous"),
    ),
    "tu": (
        (re.compile(r"\b(vos)\b", re.IGNORECASE), 1, "tes"),
        # « vous » as an object pronoun: « je vous remercie » → « je te
        # remercie ». Recognised by the subject in front of it, which is what
        # separates it from the subject « vous » whose verb moves too.
        (re.compile(r"\b(?:je|j|il|elle|on|nous)\s+(vous)\b", re.IGNORECASE), 1, "te"),
    ),
}

#: Subject pronoun + verb, corrected together. A bare « tu » → « vous » would
#: leave « vous peux », which is a worse sentence than the one the learner
#: wrote, so the pronoun is only ever swapped with its verb.
_TU_TO_VOUS_VERBS: dict[str, str] = {
    "es": "êtes", "as": "avez", "vas": "allez", "fais": "faites", "dis": "dites",
    "peux": "pouvez", "veux": "voulez", "sais": "savez", "prends": "prenez",
    "comprends": "comprenez", "apprends": "apprenez", "attends": "attendez",
    "entends": "entendez", "viens": "venez", "tiens": "tenez", "mets": "mettez",
    "bois": "buvez", "dois": "devez", "vois": "voyez", "crois": "croyez",
    "connais": "connaissez", "écris": "écrivez", "lis": "lisez", "pars": "partez",
    "sors": "sortez", "sers": "servez", "dors": "dormez", "reçois": "recevez",
    "finis": "finissez", "choisis": "choisissez", "réfléchis": "réfléchissez",
    # -er verbs whose stem changes between tu and vous. Without these the
    # regular ``-es`` → ``-ez`` rule below writes « vous appellez » and
    # « vous envoiez », which is a worse sentence than the learner's own.
    "appelles": "appelez", "rappelles": "rappelez", "épelles": "épelez",
    "jettes": "jetez", "projettes": "projetez",
    "paies": "payez", "payes": "payez", "essaies": "essayez", "essayes": "essayez",
    "envoies": "envoyez", "nettoies": "nettoyez",
    "préfères": "préférez", "espères": "espérez", "répètes": "répétez",
    "achètes": "achetez", "lèves": "levez", "amènes": "amenez", "emmènes": "emmenez",
}
#: Inverted, so the same table answers both directions and cannot drift.
_VOUS_TO_TU_VERBS: dict[str, str] = {
    **{value: key for key, value in _TU_TO_VOUS_VERBS.items()},
    "etes": "es",
}


def _has_any(folded_padded: str, markers: tuple[str, ...]) -> bool:
    return any(marker in folded_padded for marker in markers)


def address_register(text: str | None) -> str | None:
    """``"tu"``, ``"vous"``, or ``None`` when the text settles nothing.

    ``None`` covers both silences: a text with no address marker at all (« un
    café »), and a text carrying both (which is a *mixed* register — the caller
    distinguishes the two with :func:`address_markers`).
    """

    tu_seen, vous_seen = address_markers(text)
    if tu_seen == vous_seen:
        return None
    return str(Register.VOUS) if vous_seen else str(Register.TU)


def address_markers(text: str | None) -> tuple[bool, bool]:
    """``(tu_seen, vous_seen)`` for one text."""

    padded = _padded(text)
    return _has_any(padded, _TU_MARKERS), _has_any(padded, _VOUS_MARKERS)


_TU_SUBJECT = re.compile(r"\btu\s+([A-Za-zÀ-ÿ’'-]+)", re.IGNORECASE)
_VOUS_SUBJECT = re.compile(r"\bvous\s+([A-Za-zÀ-ÿ’'-]+)", re.IGNORECASE)


def _regular_swap(verb: str, *, to_vous: bool) -> str | None:
    lowered = verb.lower()
    table = _TU_TO_VOUS_VERBS if to_vous else _VOUS_TO_TU_VERBS
    if lowered in table:
        return table[lowered]
    if to_vous:
        if not lowered.endswith("es"):
            return None
        return f"{lowered[:-2]}ez"
    if not lowered.endswith("ez"):
        return None
    return f"{lowered[:-2]}es"


def slip_span(text: str | None, *, expected: str) -> tuple[str | None, str | None]:
    """``(span, replacement)`` for one register slip, in the learner's raw text.

    Safe word-for-word swaps are preferred; only when none is present does the
    subject pronoun get corrected, and then always together with its verb. When
    nothing can be repaired honestly both halves are ``None`` — the slip is still
    a slip, it simply arrives as an explanation instead of a diff.
    """

    raw = text or ""
    for pattern, group, replacement in _SAFE_SWAPS.get(expected, ()):
        match = pattern.search(raw)
        if match:
            return match.group(group), replacement
    to_vous = expected == str(Register.VOUS)
    subject = (_TU_SUBJECT if to_vous else _VOUS_SUBJECT).search(raw)
    if subject is None:
        return None, None
    swapped = _regular_swap(subject.group(1), to_vous=to_vous)
    if swapped is None:
        return None, None
    pronoun = "vous" if to_vous else "tu"
    return subject.group(0), f"{pronoun} {swapped}"


def counterpart_register(texts: list[str] | None) -> str | None:
    """The register the *counterpart* uses toward the learner, from their lines.

    For a generated scene there is no authored declaration to read, so the only
    honest source is what the character actually says. Lines that disagree —
    which the living-story ``mixed_address_register`` guard already rejects at
    generation time — yield ``None`` rather than a majority vote.
    """

    seen: set[str] = set()
    for text in texts or []:
        register = address_register(text)
        if register is not None:
            seen.add(register)
    if len(seen) != 1:
        return None
    return seen.pop()


# --------------------------------------------------------------------------
# 2. Politeness markers
# --------------------------------------------------------------------------

GREETING = "greeting"
THANKS = "thanks"
PLEASE = "please"
SOFTENER = "softener"
APOLOGY = "apology"
CLOSING = "closing"

_MARKER_CUES: dict[str, tuple[str, ...]] = {
    GREETING: ("bonjour", "bonsoir", "salut", "coucou", "re bonjour"),
    THANKS: ("merci", "je vous remercie", "je te remercie"),
    PLEASE: ("s il vous plait", "s il te plait", "svp", "stp"),
    SOFTENER: (
        "voudrais", "pourrais", "pourriez", "aimerais", "souhaiterais",
        "auriez", "seriez", "serait", "est ce que je peux", "est ce que je pourrais",
        "est ce possible", "j aimerais", "je voudrais",
    ),
    APOLOGY: ("pardon", "excusez moi", "excuse moi", "desole", "desolee", "je suis desole"),
    CLOSING: (
        "au revoir", "bonne journee", "bonne soiree", "a bientot", "a demain",
        "a tout a l heure", "bonne fin de journee",
    ),
}


def politeness_markers(text: str | None) -> frozenset[str]:
    """Which politeness moves the utterance makes. Never a score."""

    padded = _padded(text)
    return frozenset(
        name
        for name, cues in _MARKER_CUES.items()
        if any(f" {cue} " in padded for cue in cues)
    )


# --------------------------------------------------------------------------
# 3. Imperative versus request (A1/A2)
# --------------------------------------------------------------------------

#: Second-person imperatives a beginner reaches for when they mean "please may
#: I". Both the tu and the vous form, because the slip is the *bareness*, not
#: the register — « donne-moi un café » to Lila is still a command.
_IMPERATIVE_HEADS: tuple[str, ...] = (
    "donnez", "donne", "apportez", "apporte", "faites", "fais", "venez", "viens",
    "attendez", "attends", "dites", "dis", "mettez", "mets", "passez", "passe",
    "servez", "sers", "repondez", "reponds", "envoyez", "envoie", "appelez", "appelle",
)
#: The imperatives whose « …-moi » form has an exact polite counterpart.
_GIVE_VERBS: frozenset[str] = frozenset(
    {"donnez", "donne", "apportez", "apporte", "passez", "passe", "servez", "sers"}
)
#: Interjections that may legitimately precede the verb without softening it.
_LEADING_FILLERS: tuple[str, ...] = (
    "bonjour", "bonsoir", "salut", "coucou", "alors", "bon", "ok", "eh", "hein",
    "excusez", "excuse", "pardon", "et",
)
_BLUNT_WANT = re.compile(r"\bje\s+veux\b", re.IGNORECASE)
#: « je veux bien » is an acceptance, not a demand.
_WANT_ACCEPTS = (" je veux bien ",)


def _leading_verb(folded_tokens: list[str]) -> str | None:
    for token in folded_tokens:
        if token in _LEADING_FILLERS:
            continue
        return token
    return None


def bare_request_finding(
    text: str | None, *, level_band: str | None
) -> RegisterFinding | None:
    """A command where a beginner meant a request, or ``None``.

    Only at A1/A2 (:data:`IMPERATIVE_SENSITIVE_BANDS`): above that band the
    learner may be choosing bluntness, and a graded dimension that cannot tell
    the difference has no business calling it a mistake.
    """

    if str(level_band or "") not in IMPERATIVE_SENSITIVE_BANDS:
        return None
    padded = _padded(text)
    softened = bool(politeness_markers(text) & {PLEASE, SOFTENER})
    if not softened and not any(cue in padded for cue in _WANT_ACCEPTS):
        match = _BLUNT_WANT.search(text or "")
        if match:
            return RegisterFinding(code=BLUNT_WANT, span=match.group(0), replacement="je voudrais")
    if softened:
        return None
    head = _leading_verb(padded.split())
    if head is None or head not in _IMPERATIVE_HEADS:
        return None
    # The span has to survive verbatim in the raw text to be shown as a
    # correction; an accented head folds away, so a miss means no span, not a
    # fabricated one.
    raw = re.search(rf"\b{re.escape(head)}((?:-|\s)moi)?\b", text or "", re.IGNORECASE)
    if raw is None:
        return RegisterFinding(code=BARE_IMPERATIVE)
    # « Donnez-moi un café » → « Je voudrais un café » is a real French
    # sentence, so that one gets a diff. « Attendez ! » does not; it gets the
    # explanation and no invented rewrite.
    if raw.group(1) and head in _GIVE_VERBS:
        return RegisterFinding(
            code=BARE_IMPERATIVE, span=raw.group(0), replacement="je voudrais"
        )
    return RegisterFinding(code=BARE_IMPERATIVE, span=raw.group(0))


# --------------------------------------------------------------------------
# 4. The combined verdict
# --------------------------------------------------------------------------

def assess_register(
    text: str | None,
    *,
    expected_register: str | None,
    level_band: str | None = None,
    is_opening_turn: bool = False,
    is_closing_turn: bool = False,
) -> RegisterAssessment:
    """One turn's register and politeness, deterministically.

    The verdict answers only what was observed:

    ``SLIPPED``
        the learner addressed the counterpart in the register the counterpart
        does not use, mixed both in one turn, or issued a bare command at A1/A2.
    ``RESPECTED``
        the learner used the counterpart's own register and did not command.
    ``NOT_EVALUATED``
        the scene declares no expected register, or the turn addresses nobody
        (« un café, merci ») and commands nobody. This is the honest state; it
        is never rendered as a pass.
    """

    expected = str(expected_register) if expected_register else None
    if expected not in {str(Register.TU), str(Register.VOUS)}:
        expected = None

    tu_seen, vous_seen = address_markers(text)
    observed = address_register(text)
    findings: list[RegisterFinding] = []

    if tu_seen and vous_seen:
        findings.append(RegisterFinding(code=MIXED_REGISTER))
    elif expected is not None and observed is not None and observed != expected:
        span, replacement = slip_span(text, expected=expected)
        code = SLIP_TU_FOR_VOUS if expected == str(Register.VOUS) else SLIP_VOUS_FOR_TU
        findings.append(RegisterFinding(code=code, span=span, replacement=replacement))

    command = bare_request_finding(text, level_band=level_band)
    if command is not None:
        findings.append(command)

    markers = politeness_markers(text)
    if is_opening_turn and GREETING not in markers:
        findings.append(RegisterFinding(code=MISSING_GREETING))
    if is_closing_turn and not (markers & {CLOSING, THANKS}):
        findings.append(RegisterFinding(code=MISSING_CLOSING))
    if not (markers & {PLEASE, SOFTENER, THANKS, APOLOGY}):
        findings.append(RegisterFinding(code=MISSING_POLITENESS))

    ordered = tuple(sorted(findings, key=lambda item: (not item.is_slip,)))
    if any(item.is_slip for item in ordered):
        verdict = RegisterVerdict.SLIPPED
    elif expected is not None and observed == expected:
        verdict = RegisterVerdict.RESPECTED
    else:
        # Nothing addressed the counterpart and nothing commanded them: this
        # turn simply did not exercise register.
        return RegisterAssessment(
            verdict=RegisterVerdict.NOT_EVALUATED,
            expected=expected,
            observed=observed,
            findings=ordered,
            source="none",
        )

    return RegisterAssessment(
        verdict=verdict,
        expected=expected,
        observed=observed,
        findings=ordered,
        source="detector",
    )


# --------------------------------------------------------------------------
# 5. The counterpart's declared register (authored scenarios)
# --------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class CounterpartRegister:
    """What an authored scene declares about how its counterpart is addressed."""

    expected: str
    counterpart: str
    reason_fr: str = ""
    reason_native: dict[str, str] = field(default_factory=dict)

    def reason(self, language: str | None) -> str:
        code = str(language or "en").lower()[:2]
        return self.reason_native.get(code) or self.reason_native.get("en") or ""


@lru_cache(maxsize=64)
def _scenario_spec(scenario_key: str, content_version: str) -> dict[str, Any] | None:
    from app.services.journey_content import SCENARIO_DATA_ROOT

    path = Path(SCENARIO_DATA_ROOT) / content_version / f"{scenario_key}.json"
    if not path.is_file():
        return None
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:  # pragma: no cover - unreadable file
        logger.warning("pragmatics: scenario {} unreadable: {}", path, exc)
        return None
    return loaded if isinstance(loaded, dict) else None


def declared_counterpart_register(
    scenario_key: str | None, *, content_version: str | None = None
) -> CounterpartRegister | None:
    """The authored declaration, or ``None`` for a generated scene.

    Read straight from ``app/data/journey_scenarios/**`` rather than through
    ``ContentRules``, because the rules object carries the *scene's* register and
    this dimension grades the learner against the **counterpart's**. The two
    agree in every authored scenario today, and a test pins that they do — but
    they are different claims and are stored as such.
    """

    from app.services.journey_content import CURRENT_CONTENT_VERSION

    if not scenario_key:
        return None
    spec = _scenario_spec(str(scenario_key), str(content_version or CURRENT_CONTENT_VERSION))
    if spec is None:
        return None
    block = spec.get("counterpart_register")
    if not isinstance(block, dict):
        return None
    expected = str(block.get("expected") or "")
    if expected not in {str(Register.TU), str(Register.VOUS)}:
        return None
    native = block.get("reason_native")
    return CounterpartRegister(
        expected=expected,
        counterpart=str(block.get("counterpart") or spec.get("character_name") or ""),
        reason_fr=str(block.get("reason_fr") or ""),
        reason_native={
            str(key): str(value)
            for key, value in (native or {}).items()
            if isinstance(value, str) and value.strip()
        },
    )


# --------------------------------------------------------------------------
# 6. The one thing the detectors cannot see
# --------------------------------------------------------------------------

_MODEL_SYSTEM_PROMPT = (
    "You judge one thing about one French sentence written by a learner: whether "
    "its social register fits the person it is addressed to. Judge the words only. "
    "You are reading text; never comment on pronunciation, accent or delivery — "
    "the product does not score them. Do not correct grammar or spelling. "
    "Return only JSON."
)

_MODEL_USER_TEMPLATE = """The learner is speaking to {counterpart}{relation}.
That person addresses the learner with "{expected}".
Learner's sentence: {learner_text}

Is the sentence's register appropriate to that person?
Return JSON: {{"verdict": "appropriate" | "too_familiar" | "too_blunt" | "too_formal" | "unclear"}}
Use "unclear" whenever the sentence gives you nothing to judge. Add no other field."""

_MODEL_VERDICTS = {
    "appropriate": RegisterVerdict.RESPECTED,
    "too_familiar": RegisterVerdict.SLIPPED,
    "too_blunt": RegisterVerdict.SLIPPED,
    "too_formal": RegisterVerdict.SLIPPED,
    "unclear": RegisterVerdict.NOT_EVALUATED,
}
_MODEL_FINDING_CODES = {
    "too_familiar": SLIP_TU_FOR_VOUS,
    "too_blunt": BARE_IMPERATIVE,
    "too_formal": SLIP_VOUS_FOR_TU,
}


def _pragmatics_llm():
    if not settings.ATELIER_LLM_ENABLED:
        return None
    try:
        from app.services.llm_service import LLMService

        return LLMService()
    except ValueError:
        return None


def model_register_gap(
    db: Any,
    *,
    user_id: UUID | None,
    scenario_key: str,
    learner_text: str,
    counterpart: str,
    expected_register: str | None,
    relation_native: str = "",
) -> RegisterAssessment | None:
    """One bounded model opinion, or ``None`` — which stays "non évalué".

    Called **only** when :func:`assess_register` produced ``NOT_EVALUATED``, so
    this can never contradict a deterministic verdict. Any failure — provider
    down, unparseable JSON, an unknown verdict word, an extra field — returns
    ``None``. One priced pilot row per call, with the provider's own cost.
    """

    if not expected_register or not (learner_text or "").strip():
        return None
    llm = _pragmatics_llm()
    if llm is None:
        return None
    prompt = _MODEL_USER_TEMPLATE.format(
        counterpart=counterpart or "the other person",
        relation=f" ({relation_native})" if relation_native else "",
        expected=expected_register,
        learner_text=learner_text,
    )
    cost = 0.0
    try:
        result = llm.generate_chat_completion(
            [{"role": "user", "content": prompt}],
            system_prompt=_MODEL_SYSTEM_PROMPT,
            temperature=0.0,
            max_tokens=MODEL_MAX_TOKENS,
        )
        cost = float(getattr(result, "cost", 0.0) or 0.0)
        payload = json.loads(_strip_fence(result.content))
    except Exception as exc:  # noqa: BLE001 - never break a turn over an opinion
        logger.warning("pragmatics: register gap unavailable ({})", exc.__class__.__name__)
        _record(db, user_id=user_id, scenario_key=scenario_key, payload={"ok": False}, cost=0.0)
        return None

    verdict_word = payload.get("verdict") if isinstance(payload, dict) else None
    extras = set(payload) - {"verdict"} if isinstance(payload, dict) else {"?"}
    _record(
        db,
        user_id=user_id,
        scenario_key=scenario_key,
        payload={"ok": not extras, "verdict": str(verdict_word or "")},
        cost=cost,
    )
    if extras or not isinstance(verdict_word, str):
        return None
    verdict = _MODEL_VERDICTS.get(verdict_word)
    if verdict is None or verdict is RegisterVerdict.NOT_EVALUATED:
        return None
    code = _MODEL_FINDING_CODES.get(verdict_word)
    return RegisterAssessment(
        verdict=verdict,
        expected=expected_register,
        observed=None,
        findings=(RegisterFinding(code=code),) if code and verdict is RegisterVerdict.SLIPPED else (),
        source="model",
    )


def _strip_fence(content: str) -> str:
    text = (content or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"```\s*$", "", text).strip()
    return text


def _record(
    db: Any, *, user_id: UUID | None, scenario_key: str, payload: dict[str, Any], cost: float
) -> None:
    if db is None:
        return
    try:
        from app.services.pilot_events import PilotEventService

        PilotEventService(db).record(
            "journey_register_assessment",
            user_id=user_id,
            entity_type="daily_journey_pragmatics",
            entity_id=str(scenario_key),
            payload={**payload, "policy_version": PRAGMATICS_POLICY_VERSION},
            cost_usd=cost,
        )
    except Exception as exc:  # pragma: no cover - instrumentation never breaks a turn
        logger.warning("pragmatics: event not recorded ({})", exc.__class__.__name__)


__all__ = [
    "BARE_IMPERATIVE",
    "BLUNT_WANT",
    "IMPERATIVE_SENSITIVE_BANDS",
    "MISSING_CLOSING",
    "MISSING_GREETING",
    "MISSING_POLITENESS",
    "MIXED_REGISTER",
    "NOT_EVALUATED",
    "PRAGMATICS_POLICY_VERSION",
    "SLIP_CODES",
    "SLIP_TU_FOR_VOUS",
    "SLIP_VOUS_FOR_TU",
    "CounterpartRegister",
    "Register",
    "RegisterAssessment",
    "RegisterFinding",
    "RegisterVerdict",
    "address_markers",
    "address_register",
    "assess_register",
    "bare_request_finding",
    "counterpart_register",
    "declared_counterpart_register",
    "fold",
    "model_register_gap",
    "politeness_markers",
    "slip_span",
]
