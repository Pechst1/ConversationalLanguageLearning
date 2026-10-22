"""ROOT CAUSE #146 (Forge items, #267/#266) — one validator for what an item *means*.

A Forge item is assembled from parts that are written by different hands: the
model writes the situation («la vendeuse vous demande …»), the cast decides who
is on the badge (Lila · tu), the bank writes the coach's line, and after the
answer a second model call writes the character's reaction. Each part was
checked for its *shape* (a prompt is not empty, a blank is visible), and nothing
checked that the parts *agree*. So the live walk of 21-22 Oct found:

* a «tu» badge over a text in «vous» («Votre colocataire écrit … Répondez …»);
* a shop assistant who asks the customer the price the customer must give;
* «affichés à 21 euros» for «les deux livres» (per book, or both?);
* a reaction spoken by Lila after Margaux's prompt, in the plural for the
  learner's «Il …», about a Paul who is nowhere in the cast.

This module is the deterministic guard next to the existing ones
(:mod:`app.services.item_semantics` for the bank's sentences): pure functions on
text, no model call, each returning :class:`Problem` rows (empty: the item
agrees with itself). It is used where the parts meet:

* ``register_problems`` / ``situation_problems`` when the serial cast is put on
  a prompt (``_with_serial_conversation``) and when a generated set is
  validated (``AtelierExerciseGenerator._payload_validation_errors``);
* ``reaction_problems`` on the character's reaction
  (``MissionConversationService.respond_for_atelier``).
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Problem:
    kind: str
    detail: str


# --------------------------------------------------------------------------- #
# Text helpers
# --------------------------------------------------------------------------- #

_APOSTROPHES = re.compile(r"[’ʼ‘]")
#: The English side of a prompt: «( … )» glosses and the learner-language ask.
_GLOSS = re.compile(r"\([^()]*\)")
_ASK = re.compile(r"(?:Reply|Say|Write|Answer|Respond) in French\s*:?\s*[\"“][^\"”]*[\"”]?", re.IGNORECASE)


def _plain(text: object) -> str:
    return _APOSTROPHES.sub("'", str(text or ""))


def french_of(prompt: object) -> str:
    """The French part of a prompt: without the English gloss and the ask."""

    text = _ASK.sub(" ", _GLOSS.sub(" ", _plain(prompt)))
    return re.sub(r"\s+", " ", text).strip()


# --------------------------------------------------------------------------- #
# Register: the text and the badge say the same thing
# --------------------------------------------------------------------------- #

_VOUS_IMPERATIVES = (
    "répondez|dites|demandez|écrivez|expliquez|proposez|racontez|décrivez|refusez|invitez|"
    "excusez|remerciez|félicitez|rassurez|confirmez|indiquez|précisez|donnez|posez|mentionnez|"
    "commandez|saluez|présentez|acceptez|insistez|suggérez|annoncez|rappelez|parlez|prévenez"
)
_VOUS = re.compile(rf"\b(?:vous|votre|vos|{_VOUS_IMPERATIVES})\b|-vous\b", re.IGNORECASE)
_TU = re.compile(
    r"\b(?:tu|toi|ton|ta|tes|te|réponds)\b|\bdis-(?:lui|leur|moi)\b|\bt'|-(?:tu|toi)\b",
    re.IGNORECASE,
)


def prompt_register(prompt: object) -> str | None:
    """«tu», «vous», «mixed», or ``None`` when the text addresses nobody."""

    text = french_of(prompt)
    tu, vous = bool(_TU.search(text)), bool(_VOUS.search(text))
    if tu and vous:
        return "mixed"
    return "tu" if tu else "vous" if vous else None


def register_problems(prompt: object, register: object) -> list[Problem]:
    """The prompt addresses the learner in another register than its badge says.

    A «tu» speaker over a text that says «vous» (or the reverse) reads as two
    different people. A text with no address at all agrees with any badge.
    """

    badge = str(register or "").strip().lower()
    if badge not in {"tu", "vous"}:
        return []
    found = prompt_register(prompt)
    if found is None or found == badge:
        return []
    return [Problem("register", f"badge {badge}, text {found}: {french_of(prompt)}")]


# --------------------------------------------------------------------------- #
# Roles: who asks whom
# --------------------------------------------------------------------------- #

#: People behind a counter: they ask what the customer wants, never what it costs.
_SERVICE = (
    "vendeu(?:r|se)|serveu(?:r|se)|libraire|caissi(?:er|ère)|boulang(?:er|ère)|commerçant(?:e)?|"
    "marchand(?:e)?|réceptionniste|guichetier|guichetière|fleuriste|pharmacien(?:ne)?|"
    "boucher|bouchère|poissonni(?:er|ère)|épicier|épicière|patron(?:ne)?|gérant(?:e)?|barman|barmaid"
)
_PRICE_QUESTION = (
    r"(?:combien\s+(?:ça\s+|cela\s+|cela\s+)?(?:coûte|coûtent|font|fait|vaut|valent)|"
    r"(?:quel\s+est\s+)?le\s+prix|quel\s+prix|c'est\s+combien|ça\s+fait\s+combien|combien\s+je\s+(?:vous\s+)?dois)"
)
#: «la vendeuse vous demande combien coûtent …» / «La vendeuse : « Combien coûte … ? »».
_SELLER_ASKS_PRICE = re.compile(
    rf"\b(?:{_SERVICE})\b[^.?!«»\"]{{0,60}}?\bvous\s+(?:demande|interroge|dit)\b[^.?!«»\"]{{0,40}}?{_PRICE_QUESTION}"
    rf"|\b(?:{_SERVICE})\b\s*:?\s*[«\"“]\s*{_PRICE_QUESTION}",
    re.IGNORECASE,
)


def role_problems(prompt: object) -> list[Problem]:
    """Asker and answerer contradict the scene: the seller asks the price."""

    text = french_of(prompt)
    if _SELLER_ASKS_PRICE.search(text):
        return [Problem("roles", f"a shop assistant asks the customer the price: {text}")]
    return []


# --------------------------------------------------------------------------- #
# A price says what it is a price of
# --------------------------------------------------------------------------- #

_PRICE_TALK = re.compile(r"\b(?:coût\w*|prix|affich\w*|payer|paie\w*|vaut|valent|tarif|facture|addition)\b|[àa]\s+\d", re.IGNORECASE)
_AMOUNT = re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:€|euros?)|\b(?:un|deux|trois|quatre|cinq|six|sept|huit|neuf|dix|vingt\w*|trente|quarante|cinquante|soixante\w*|cent)\s+euros?\b", re.IGNORECASE)
_MANY = re.compile(
    r"\b(?:deux|trois|quatre|cinq|six|sept|huit|neuf|dix|douze|plusieurs|\d+)\s+(?!euros?\b|€|ans?\b|heures?\b|minutes?\b|jours?\b|fois\b|semaines?\b|mois\b|h\b)[a-zéèêàâîôûç]+",
    re.IGNORECASE,
)
_BASIS = re.compile(
    r"\b(?:pièce|chacun(?:e)?|l'un|l'une|le\s+kilo|le\s+litre|la\s+douzaine|la\s+paire|l'unité|unité|chaque|"
    r"par\s+\w+|au\s+total|en\s+tout|le\s+total|ensemble|à\s+eux\s+deux|à\s+elles\s+deux|pour\s+(?:les\s+\w+|tous|l'ensemble)|"
    r"kilo|litre|la\s+bouteille|le\s+paquet)\b",
    re.IGNORECASE,
)


def price_basis_problems(prompt: object) -> list[Problem]:
    """A price for several things must say per item or in total."""

    text = french_of(prompt)
    if _AMOUNT.search(text) and _PRICE_TALK.search(text) and _MANY.search(text) and not _BASIS.search(text):
        return [Problem("price_basis", f"price of several things, per item or in total?: {text}")]
    return []


# --------------------------------------------------------------------------- #
# Labels that belong to the screen, not to the scene
# --------------------------------------------------------------------------- #

_ROLE_LABEL = re.compile(
    r"\b(?:Colleague|Friend|Roommate|Flatmate|Neighbou?r|Shopkeeper|Shop assistant|Waiter|Waitress|"
    r"Customer|Seller|Boss|Teacher|Landlord|Stranger)\s*:\s*[«\"“]"
)
_ASK_TWICE = re.compile(r"(?:Reply|Say|Write|Answer) in French", re.IGNORECASE)


def label_problems(prompt: object) -> list[Problem]:
    text = _plain(prompt)
    found: list[Problem] = []
    if _ROLE_LABEL.search(text):
        found.append(Problem("role_label", f"an English role label speaks inside the scene: {text}"))
    if len(_ASK_TWICE.findall(text)) > 1:
        found.append(Problem("doubled_ask", f"the ask is given twice: {text}"))
    return found


_ADVICE = {
    "roles": "has the shop assistant who asks the customer the price the customer must give (who asks whom?)",
    "price_basis": "gives a price for several things without saying per item or in total",
    "role_label": "has an English role label speaking inside the scene",
    "doubled_ask": "gives the ask twice",
    "register": "addresses the learner in another register than the speaker's badge",
}


def advice(problem: Problem) -> str:
    """The problem in words a generator can be told (retry feedback, test output)."""

    return _ADVICE.get(problem.kind, problem.detail)


def situation_problems(prompt: object) -> list[Problem]:
    """Everything a situation prompt can get wrong on its own (no badge needed)."""

    return [*role_problems(prompt), *price_basis_problems(prompt), *label_problems(prompt)]


def item_problems(prompt: object, *, register: object = None) -> list[Problem]:
    """A prompt against the speaker it is put under (``register``: the badge's)."""

    return [*register_problems(prompt, register), *situation_problems(prompt)]


# --------------------------------------------------------------------------- #
# A reaction: the item's own speaker, the learner's person, the cast's names
# --------------------------------------------------------------------------- #

_NAME = re.compile(r"\b[A-ZÀÂÉÈÊËÎÏÔÛÙÇ][a-zàâéèêëîïôûùç'-]{2,}\b")
#: First names a model reaches for; at the start of a sentence a capital is no proof of a name.
_COMMON_FIRST_NAMES = frozenset(
    """paul julie pierre jacques jean marie sophie thomas nicolas pauline claire laura antoine
    julien camille lucas hugo louis emma léa manon chloé alice sarah anna david daniel michel
    philippe patrick isabelle catherine nathalie sylvie céline vincent alexandre maxime
    mathieu clément benoît bruno éric olivier stéphane françois christophe laurent
    sébastien fabrice guillaume romain théo jules adrien arthur victor émilie élodie
    amélie delphine valérie martine monique brigitte christine""".split()
)
_SINGULAR_SUBJECT = re.compile(r"(?:^|[.!?;,]\s*|\b(?:et|mais|que|qu'|puisque|parce que)\s+)(il|elle)\b(?!\s+(?:y\s+a|faut|fait|pleut|neige|s'agit))", re.IGNORECASE)
_PLURAL_SUBJECT = re.compile(r"(?:^|[.!?;,]\s*|\b(?:et|mais|que|qu'|puisque|parce que)\s+)(ils|elles)\b", re.IGNORECASE)


def _capitalised(text: str) -> list[tuple[str, bool]]:
    """``(token, sentence_initial)`` for every capitalised word."""

    found = []
    for match in _NAME.finditer(text):
        before = text[: match.start()].rstrip(" «\"“")
        found.append((match.group(0), not before or before[-1] in ".!?…:"))
    return found


def cast_names() -> frozenset[str]:
    """Every name the cast registry knows, as the learner reads it."""

    from app.services.cast_registry import all_members

    names: set[str] = set()
    for row in all_members().values():
        names.add(row.short_name)
        names.update(part for part in row.name.replace(".", " ").split() if len(part) > 2)
    return frozenset(names)


def reaction_problems(
    reply: object,
    *,
    learner_text: object = "",
    grounded: Iterable[object] = (),
) -> list[Problem]:
    """What a reaction must not do: invent a person, or change the learner's person.

    ``grounded`` is every text the reaction may take a capitalised word from
    (the scene, the opening line, the learner's own answer); the cast registry's
    names are always allowed. A name that is none of these is invented.
    """

    text = _plain(reply)
    learner = _plain(learner_text)
    known = {word.lower() for word in cast_names()}
    for source in grounded:
        known.update(token.lower() for token, _initial in _capitalised(_plain(source)))
    known.update(token.lower() for token, _initial in _capitalised(learner))
    found: list[Problem] = []
    for token, initial in _capitalised(text):
        if token.lower() in known:
            continue
        if initial and token.lower() not in _COMMON_FIRST_NAMES:
            continue  # a sentence opener: «Ah», «Alors», «Bien sûr»
        found.append(Problem("invented_name", f"{token} is not in the cast: {text}"))
        break
    learner_sg = bool(_SINGULAR_SUBJECT.search(learner)) and not _PLURAL_SUBJECT.search(learner)
    learner_pl = bool(_PLURAL_SUBJECT.search(learner)) and not _SINGULAR_SUBJECT.search(learner)
    reply_sg, reply_pl = bool(_SINGULAR_SUBJECT.search(text)), bool(_PLURAL_SUBJECT.search(text))
    if learner_sg and reply_pl and not reply_sg:
        found.append(Problem("number", f"the learner said one, the reaction says several: {text}"))
    elif learner_pl and reply_sg and not reply_pl:
        found.append(Problem("number", f"the learner said several, the reaction says one: {text}"))
    return found


__all__ = [
    "Problem",
    "advice",
    "cast_names",
    "french_of",
    "item_problems",
    "label_problems",
    "price_basis_problems",
    "prompt_register",
    "reaction_problems",
    "register_problems",
    "role_problems",
    "situation_problems",
]
