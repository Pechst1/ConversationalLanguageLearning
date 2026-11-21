"""P8 (fifth commit): the story never decides for the learner.

The second real-model walk of 17 Nov (integration branch) logged three ways a page or
an ending stated a decision the learner never made:

- **a season fact paraphrased as an intention.** The return ticket for Wednesday is a
  fact of the season from T1 («Ton billet de retour est pour mercredi.», true). «Tu pars
  mercredi» and «La valise part mercredi» are not: a ticket is not a decision to leave.
- **an authored beat that presupposes the learner's choice** (gap 1's ticket day: «Why
  are you changing the date?», «Mercredi 2 décembre. C'est confirmé.» before the
  learner chose). That is fixed where the brief is composed (``director.gap_brief``);
  here it is only *read* (:func:`page_decides`).
- **the ending writer turning a hedged reply into a decision.** A1 day 3: the learner
  wrote «Je ne sais pas.» and «Je reste peut-être jeudi.»; the ending said «Alors, tu
  pars mercredi.», the summary «Du fliegst am Mittwoch nach Hause», and the day's
  record «Le chat ne décide pas ; tu pars mercredi.», which «Précédemment» then carried
  for two days.

What a decision is, here: the learner leaving, staying, selling, keeping, signing, or
changing their date, said of the learner in the second person (French, German, English),
in the present, the future or with «aller / vouloir / devoir». It is the learner's only
when their own words in the scene say it in the first person without a hedge («peut-être»,
«je ne sais pas», «si …»), with the same polarity, or when they said «oui» to a line that
put it to them. Word-based like every guard here: it reads, it never calls a model.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from typing import Any

#: The decisions this reading knows, by concept: French stems of the verb (any person),
#: German second-person forms, English stems.
_FR_VERBS: dict[str, str] = {
    "leave": r"(?:par(?:s|t|tir|tira[s]?|tiras|tez|tons)|rentr\w*|quitt\w*|repar\w*)",
    "stay": r"(?:rest(?:e|es|er|era|eras|ez|ons))",
    "sell": r"(?:vend(?:s|re|ras?|ez|ons)?)",
    "keep": r"(?:gard(?:e|es|er|eras?|ez|ons))",
    "sign": r"(?:sign(?:e|es|er|eras?|ez|ons))",
    "change": r"(?:chang(?:e|es|er|eras?|ez|eons)|d[ée]plac\w*|d[ée]cal\w*)",
}
#: «changer» is a decision only about the learner's date, ticket or flight.
_CHANGE_OBJECT = r"(?:\s+(?:de\s+)?(?:la|ta|ton|sa|son|le|ma|mon)\s+(?:date|billet|vol|avion|jour))"
_DE_VERBS: dict[str, str] = {
    "leave": r"(?:fliegst|reist|fährst|faehrst|gehst\s+zurück|kehrst|verlässt|verlaesst|abreisen|abfliegen|zurückfliegen|nach\s+hause)",
    "stay": r"(?:bleibst|bleiben)",
    "sell": r"(?:verkaufst|verkaufen)",
    "keep": r"(?:behältst|behaeltst|behalten)",
    "sign": r"(?:unterschreibst|unterschreiben)",
    "change": r"(?:änderst|aenderst|verschiebst|buchst\s+um|umbuchen|ändern|verschieben)",
}
_EN_VERBS: dict[str, str] = {
    "leave": r"(?:leav\w*|fly\w*|flie\w*|go(?:ing)?\s+(?:home|back))",
    "stay": r"(?:stay\w*)",
    "sell": r"(?:sell\w*)",
    "keep": r"(?:keep\w*)",
    "sign": r"(?:sign\w*)",
    "change": r"(?:chang\w*|mov\w*)\s+(?:the|your)\s+(?:date|ticket|flight)",
}
_OBJ = r"(?:(?:ne|n|y|en|le|la|les|l|lui|leur|me|m|te|t|se|s)\s+)"
_ADV = r"(?:(?:pas|plus|jamais|déjà|deja|vraiment|bien|toujours)\s+)"
_MODAL = rf"(?:vas|veux|dois|comptes|préfères|preferes|pourras)\s+{_ADV}{{0,2}}"
#: A past decision said of the learner: «tu as signé», «tu n'as pas vendu», «tu es parti».
_PARTICIPLES: dict[str, str] = {
    "leave": r"(?:partie?s?|rentrée?s?|quittée?s?)",
    "stay": r"(?:restée?s?)",
    "sell": r"(?:vendue?s?)",
    "keep": r"(?:gardée?s?)",
    "sign": r"(?:signée?s?)",
    "change": r"(?:changée?s?|déplacée?s?|décalée?s?)",
}
#: «tu pars», «tu ne vends pas», «tu vas rester», «tu veux partir», «ta valise part»,
#: «vous partez». Folded text (lower case, punctuation as spaces, apostrophes kept as space).
_FR_CLAIM = {
    concept: re.compile(
        rf"\b(?:tu|vous|ta\s+valise|tes\s+valises|la\s+valise)\s+{_OBJ}{{0,3}}"
        rf"(?:(?:{_MODAL}{_OBJ}{{0,2}})?{verb}|(?:as|avez|es|êtes)\s+(?:{_ADV}|{_OBJ}){{0,4}}{_PARTICIPLES[concept]})"
        + (_CHANGE_OBJECT if concept == "change" else r"\b")
    )
    for concept, verb in _FR_VERBS.items()
}
#: «Du fliegst am Mittwoch nach Hause», «fliegst du», «du wirst bleiben», «du willst verkaufen».
_DE_CLAIM = {
    concept: re.compile(rf"\bdu\b[^.;:!?]{{0,40}}?\b{verb}\b|\b{verb}\s+du\b")
    for concept, verb in _DE_VERBS.items()
}
_EN_CLAIM = {
    concept: re.compile(
        rf"\byou(?:\s+will|ll|\s+are\s+going\s+to|re\s+going\s+to|\s+want\s+to|\s+are|re)?\s+{verb}\b"
    )
    for concept, verb in _EN_VERBS.items()
}
#: The learner's own first-person statement of the same decision («je pars», «je ne
#: vends pas», «je vais rester», «on reste»).
_FR_OWN_VERBS: dict[str, str] = {
    "leave": r"(?:pars|part|partir|partirai|partons|rentre|rentrer|rentrerai|rentrons|quitte|quitter|quitterai|repars)",
    "stay": r"(?:reste|rester|resterai|restons)",
    "sell": r"(?:vends|vend|vendre|vendrai|vendons)",
    "keep": r"(?:garde|garder|garderai|gardons)",
    "sign": r"(?:signe|signer|signerai|signons)",
    "change": r"(?:change|changer|changerai|changeons|déplace|déplacer|deplace|deplacer|décale|décaler|decale|decaler)",
}
_FR_OWN = {
    concept: re.compile(
        rf"\b(?:je|j|on|nous)\s+{_OBJ}{{0,3}}"
        rf"(?:(?:(?:vais|veux|dois|compte|préfère|prefere|voudrais|allons|voulons)\s+(?:{_ADV}|{_OBJ}){{0,4}})?{verb}"
        rf"|(?:ai|avons|suis|sommes)\s+(?:{_ADV}|{_OBJ}){{0,4}}{_PARTICIPLES[concept]}"
        rf"|(?:ai|avons)\s+{_ADV}{{0,2}}(?:décidé|decide|choisi|refusé|refuse)\s+de\s+(?:{_ADV}|{_OBJ}){{0,4}}{verb})"
        + (_CHANGE_OBJECT if concept == "change" else r"\b")
    )
    for concept, verb in _FR_OWN_VERBS.items()
}
#: A clause that keeps the decision open is not a claim: «ob du … bleiben kannst, ist
#: noch offen», «si tu pars», «tu ne sais pas encore».
_OPEN = re.compile(
    r"\b(?:ob|whether|if|si|noch\s+offen|still\s+open|pas\s+encore|weißt\s+nicht|weisst\s+nicht"
    r"|ne\s+sais\s+pas|don\s+t\s+know|not\s+yet|noch\s+nicht)\b"
)
_NEGATION = re.compile(r"\b(?:ne|n|pas|jamais|plus|nicht|kein\w*|nie|not|never|don t|won t|isn t|aren t)\b")
#: A first-person sentence that does not commit: «Je reste peut-être jeudi.», «Je ne sais pas».
_HEDGE = re.compile(
    r"\b(?:peut\s+être|peutetre|je\s+ne\s+sais\s+pas|je\s+sais\s+pas|pas\s+encore|je\s+crois|on\s+verra|si"
    r"|probablement|sans\s+doute|je\s+pense|je\s+réfléchis|je\s+reflechis|ou)\b"
)
_ACCEPT = re.compile(r"^(?:oui|ouais|d accord|ok|okay|bien sûr|bien sur|exactement|voilà|voila)\b")
_SENTENCES = re.compile(r"[^.!?…]+[.!?…]*")
#: A question that presupposes the decision: «Pourquoi tu changes la date ?»
_WHY = re.compile(r"^\s*(?:alors\s+|et\s+|mais\s+)?(?:pourquoi|why|warum|quelle\s+raison)\b")


def fold(text: Any) -> str:
    value = unicodedata.normalize("NFC", str(text or "")).casefold().replace("’", "'")
    return " ".join(re.sub(r"[^\w\s]", " ", value).split())


def _negated(folded: str) -> bool:
    return bool(_NEGATION.search(folded))


def claims(text: Any, *, questions: bool = False) -> list[tuple[str, bool, str]]:
    """``(concept, negated, sentence)`` for each decision a text states of the learner.
    A question is asked, not stated, unless ``questions`` is set and it asks *why* the
    learner did it («Pourquoi tu changes la date ?» presupposes the change)."""

    found: list[tuple[str, bool, str]] = []
    for sentence in _SENTENCES.findall(str(text or "")):
        raw = sentence.strip()
        if not raw:
            continue
        if raw.endswith("?") and not (questions and _WHY.search(fold(raw))):
            continue
        for clause in re.split(r"\s*[;:]\s*|\s+[—–]\s+", raw):
            folded = fold(clause)
            if not folded or _OPEN.search(folded):
                continue
            for table in (_FR_CLAIM, _DE_CLAIM, _EN_CLAIM):
                for concept, pattern in table.items():
                    if pattern.search(folded):
                        found.append((concept, _negated(folded), clause.strip()))
    return found


def learner_decided(concept: str, negated: bool, said: Iterable[str], put_to: Iterable[tuple[str, str]] = ()) -> bool:
    """Whether the learner's own words commit to ``concept`` with that polarity: a
    first-person sentence without a hedge, or «oui» to a line that put it to them."""

    for text in said:
        for sentence in _SENTENCES.findall(str(text or "")):
            folded = fold(sentence)
            if not folded or _HEDGE.search(folded):
                continue
            if _FR_OWN[concept].search(folded) and _negated(folded) == negated:
                return True
    for line, answer in put_to:
        if _ACCEPT.search(fold(answer)) and not _HEDGE.search(fold(answer)):
            if any(c == concept and n == negated for c, n, _ in claims(line, questions=False) + _asked(line)):
                return True
    return False


def _asked(line: str) -> list[tuple[str, bool, str]]:
    """The decisions a character's question put to the learner («Tu pars mercredi ?»)."""

    out: list[tuple[str, bool, str]] = []
    for sentence in _SENTENCES.findall(str(line or "")):
        if sentence.strip().endswith("?"):
            folded = fold(sentence)
            for concept, pattern in _FR_CLAIM.items():
                if pattern.search(folded):
                    out.append((concept, _negated(folded), sentence.strip()))
    return out


def unsaid(text: Any, said: Iterable[str], put_to: Iterable[tuple[str, str]] = (), *, questions: bool = False) -> list[str]:
    """The sentences (or clauses) of ``text`` that state a decision the learner's words
    do not hold."""

    said = list(said)
    put_to = list(put_to)
    return [
        clause
        for concept, negated, clause in claims(text, questions=questions)
        if not learner_decided(concept, negated, said, put_to)
    ]


def without_unsaid(text: Any, said: Iterable[str], put_to: Iterable[tuple[str, str]] = ()) -> str:
    """``text`` without its sentences, or ``;`` clauses, that decide for the learner.
    «Le chat ne décide pas ; tu pars mercredi.» → «Le chat ne décide pas.»"""

    said = list(said)
    put_to = list(put_to)
    kept: list[str] = []
    for sentence in _SENTENCES.findall(str(text or "")):
        raw = sentence.strip()
        if not raw:
            continue
        if not unsaid(raw, said, put_to):
            kept.append(raw)
            continue
        end = raw[-1] if raw[-1] in ".!?…" else "."
        parts = [part.strip(" .!?…") for part in re.split(r"\s*;\s*", raw)]
        parts = [part for part in parts if part and not unsaid(part + ".", said, put_to)]
        if parts and len(parts) < len(re.split(r"\s*;\s*", raw)):
            kept.append(" ; ".join(parts) + end)
    return " ".join(kept).strip()


#: «what was said», per control language, when a summary had nothing left but a decision
#: the learner never made.
_SAID_FALLBACK = {
    "de": "Du hast gesagt: „{quote}“",
    "en": "You said: “{quote}”",
    "fr": "Tu as dit : « {quote} »",
}


def said_fallback(language: str | None, quote: str) -> str:
    quote = " ".join(str(quote or "").split()).strip()
    if not quote:
        return ""
    from app.services.chrome_language import fold_language

    template = _SAID_FALLBACK[fold_language(language)]
    return template.format(quote=quote[:160])


#: A page line that says an open choice is made: «C'est confirmé.», «Mercredi, c'est fini.»
DONE = re.compile(
    r"\bc['’]est\s+(?:noté|décidé|réglé|fini|entendu|confirmé|fait)\b|\b(?:tu\s+as|vous\s+avez)\s+(?:décidé|choisi)\b"
    r"|\bta\s+décision\s+est\s+prise\b",
    re.IGNORECASE,
)


def page_decides(lines: Iterable[str], question: str = "", *, open_choices: Iterable[dict] = ()) -> bool:
    """Whether a page (written before the learner answers) decides for them: a line
    states a decision of theirs («La valise part mercredi.»), the question asks why they
    made one («Pourquoi tu changes la date ?»), or, while a choice is theirs today
    (``today.learner_decides``), a line says it is done or names the story's own value
    («Mercredi 2 décembre. C'est confirmé.»). A season fact said as a fact («Ton billet
    de retour est pour mercredi.») is not a decision."""

    lines = [str(line or "") for line in lines]
    if any(claims(line) for line in lines):
        return True
    if question and claims(question, questions=True):
        return True
    choices = [row for row in open_choices if isinstance(row, dict)]
    if choices:
        values = [fold(row.get("if_the_learner_decides_nothing")) for row in choices]
        for line in lines:
            if DONE.search(line):
                return True
            folded = fold(line)
            if any(value and value in folded for value in values):
                return True
    return False


__all__ = [
    "DONE",
    "claims",
    "fold",
    "learner_decided",
    "page_decides",
    "said_fallback",
    "unsaid",
    "without_unsaid",
]
