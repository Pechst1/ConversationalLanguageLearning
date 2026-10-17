"""Deterministic guards for what a Courrier character says: one address form, one band.

Root cause these guards exist for (#117): the Courrier had a lexical guard for the
letter (``letter_level_verdict``) and nothing else. A letter could mix «tu» and
«vous» between its opening and its P.S., and the character's *replies*
(``MissionConversationService.respond``) were never checked at all, so an A1.1
learner got the plus-que-parfait, the subjunctive and the future from a friend
whose letter was written in the present tense. Scenes already have these guards
(``living_story._check_scene_address_register``, ``_check_register``); the Courrier
had none. This module is the Courrier's equivalent, shared by the letter writer and
the reply writer so the two cannot drift apart again.

Pure functions, no model calls.
"""

from __future__ import annotations

import re

from app.services.pragmatics import address_markers

_PARTICIPLES = (
    r"(?:\w+é(?:e|s|es)?|eu|pris|fait|dit|vu|lu|su|pu|voulu|dû|mis|ouvert|parti|venu|reçu|prévu"
    r"|fini|compris|perdu|entendu|attendu|connu|bu|cru|écrit|offert|devenu)"
)
#: «j'avais prévu», «il avait oublié», «elle était partie».
_PLUS_QUE_PARFAIT = re.compile(
    rf"\b(?:avais|avait|avions|aviez|avaient|étais|était|étions|étiez|étaient)\s+(?:déjà\s+|pas\s+)?{_PARTICIPLES}\b",
    re.IGNORECASE,
)
_SUBJ_FORMS = (
    r"(?:sois|soit|soient|soyez|soyons|aies|ait|aient|aie|ayez|ayons|fasse|fasses|fassent|puisse|puisses|puissent"
    r"|aille|ailles|aillent|vienne|viennes|viennent|sache|saches|sachent|veuille|veuilles|prenne|prennes|prennent"
    r"|doive|doives|doivent|parte|partes|partent)"
)
#: «qu'il y ait eu», «que tu viennes», «il faut que», «bien que».
_SUBJUNCTIVE = re.compile(
    rf"\bqu['’]\s*(?:il|elle|on|ils|elles)\s+(?:y\s+)?{_SUBJ_FORMS}\b"
    rf"|\bque\s+(?:je|j['’]|tu|nous|vous|il|elle|on|ils|elles)\s*(?:y\s+)?{_SUBJ_FORMS}\b"
    r"|\b(?:bien que|il faut que|pour que|avant que|à moins que|jusqu['’]à ce que)\b",
    re.IGNORECASE,
)
_FUTURE = re.compile(
    r"\b(?:sera|serai|seras|serons|serez|seront|aura|auras|aurai|auront|ira|irai|iras|irons|iront"
    r"|fera|ferai|feras|feront|viendra|viendrai|prendra|prendrai|pourra|pourrai|pourront|devra|faudra"
    r"|voudra|verra|saura|enverra|attendra)\b"
    r"|\b\w{3,}(?:erai|eras|era|erons|erez|eront)\b",
    re.IGNORECASE,
)

#: Tenses each learner band has not met; A1 also gets no future.
_BAND_TENSES = {
    "A1": ("plus-que-parfait", "subjonctif", "futur simple"),
    "A2": ("plus-que-parfait", "subjonctif"),
}
_DETECTORS = {
    "plus-que-parfait": _PLUS_QUE_PARFAIT,
    "subjonctif": _SUBJUNCTIVE,
    "futur simple": _FUTURE,
}


def above_band_tenses(text: str | None, level: str | None) -> list[str]:
    """The tenses in ``text`` the learner's band has not met; empty from B1 up."""

    band = str(level or "").strip().upper()[:2]
    return [tense for tense in _BAND_TENSES.get(band, ()) if _DETECTORS[tense].search(text or "")]


def voice_problems(texts: list[str | None], *, register: str | None, level: str | None) -> list[str]:
    """Why a character's own words must be rewritten, as hints for the writer.

    ``register`` is ``"tu"`` or ``"vous"`` (or ``None`` when unknown: only a text
    that mixes both is then wrong). ``texts`` are everything one character says in
    one go (a letter's opening and its P.S.).
    """

    joined = " ".join(str(item) for item in texts if item and str(item).strip())
    problems: list[str] = []
    tu_seen, vous_seen = address_markers(joined)
    if tu_seen and vous_seen:
        problems.append(
            "The character addresses the learner with both «tu» and «vous» (and their "
            "possessives). Use exactly one form in every sentence, the P.S. included."
        )
    elif register == "tu" and vous_seen:
        problems.append("This character says «tu» to the learner: never «vous», «votre» or «vos».")
    elif register == "vous" and tu_seen:
        problems.append("This character says «vous» to the learner: never «tu», «toi», «ton» or «ta».")
    tenses = above_band_tenses(joined, level)
    if tenses:
        problems.append(
            f"The learner is {str(level).upper()[:2]}: no {', '.join(tenses)}. Use the present tense "
            "(and passé composé) in short sentences."
        )
    return problems


def register_word(value: object) -> str | None:
    """«tu» / «vous» from a stored register description, else ``None``."""

    text = str(value or "").strip().lower()
    if text.startswith("tu"):
        return "tu"
    if text.startswith("vous"):
        return "vous"
    return None
