"""Root cause #145: the scene has no state of what was said and what is established.

The next line used to be generated (or scripted) from the beat plan and the last
message only. So a character asked again what the learner had just answered («Non, je
ne vend pas» → «Vous allez vendre, oui ou non ?»), redefined the antagonist («Solvel est
une collègue»), invented a parcel and asked for an address, or printed the engine's own
English recap as story text.

This module is the scene ledger and the checks that read it. Pure functions, no model
call, no database:

* :func:`learner_intent` / :func:`build_ledger` — what the learner's last turn *did*
  (yes / no / question / other), the questions the scene had asked and now has
  answered, and the facts the learner gave;
* the line checks — each returns a retry hint (or ``None``): a settled question
  asked again, an established fact redefined, a fact invented from nowhere
  (tracking number, order, a request for the learner's address), the engine's recap
  shown as story text, a bare appointment with no stated purpose.

``living_story._validate_turn`` and the Courrier reply
(``missions.MissionConversationService.respond``) call the same checks, so the
generator is held to one account of the scene whichever lane wrote the line.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Literal

Intent = Literal["yes", "no", "question", "other"]


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text or "").casefold().replace("’", "'"))
    return "".join(char for char in text if not unicodedata.combining(char))


_SENTENCES = re.compile(r"(?<=[.!?…])\s+")
_WORDS = re.compile(r"[a-z0-9']+")
_STOP = frozenset(
    "le la les un une des de du d l et ou mais donc je tu il elle on nous vous ils elles me te se "
    "ce c ca est es suis sont a as ai au aux en y ne n pas plus que qu qui quoi pour par sur dans "
    "avec mon ma mes ton ta tes son sa ses moi toi lui oui non si votre vos notre nos leur leurs".split()
)

# ---------------------------------------------------------------------------
# the learner's intent in their last turn
# ---------------------------------------------------------------------------

_NO = re.compile(
    r"\bnon\b|\bne\s+(?:\w+\s+){0,2}?(?:pas|plus|jamais|rien)\b|\bn'\s?\w+\s+(?:\w+\s+){0,2}?(?:pas|plus|jamais|rien)\b"
    r"|\bpas\s+(?:question|du tout|maintenant|encore)\b|\bjamais\b"
)
_YES = re.compile(
    r"\boui\b|\bd'accord\b|\bbien sur\b|\bvolontiers\b|\bok\b|\bavec plaisir\b|\bje veux bien\b"
)


def learner_intent(text: str) -> Intent:
    """What the learner's turn does with the question put to them.

    ``no`` / ``yes`` by the earliest clear marker (a «non» before a later «et qui est
    Solvel ?» is still a refusal); ``question`` when the turn only asks; ``other``
    otherwise. Never a grade: clumsy French («je ne vend pas») reads like a polished one."""

    folded = _fold(text).strip()
    if not folded:
        return "other"
    no, yes = _NO.search(folded), _YES.search(folded)
    if no and yes:
        return "no" if no.start() < yes.start() else "yes"
    if no:
        return "no"
    if yes:
        return "yes"
    if "?" in folded:
        return "question"
    return "other"


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in _SENTENCES.split(str(text or "")) if part.strip()]


def _content(text: str) -> set[str]:
    return {
        w.split("'")[-1] for w in _WORDS.findall(_fold(text)) if len(w.split("'")[-1]) > 2
    } - _STOP


def questions_in(lines: Iterable[str]) -> list[str]:
    """Every question sentence in ``lines`` (what the scene has asked)."""

    return [s for line in lines for s in _sentences(line) if s.endswith("?")]


@dataclass
class SceneLedger:
    """The small state a generated line is checked against."""

    intent: Intent = "other"
    #: Questions the scene asked that the learner's turn has now settled (yes / no).
    settled: list[str] = field(default_factory=list)
    #: Everything the learner said in this scene, in their words.
    said: list[str] = field(default_factory=list)
    #: Every line a character already spoke in this scene.
    spoken: list[str] = field(default_factory=list)

    @property
    def learner_text(self) -> str:
        return " ".join(self.said)


def build_ledger(
    learner_text: str,
    *,
    spoken: Iterable[str] = (),
    learner_before: Iterable[str] = (),
) -> SceneLedger:
    """The ledger for one learner turn: ``spoken`` are the character lines so far
    (the last ones matter most), ``learner_before`` the learner's earlier turns."""

    spoken_lines = [str(line) for line in spoken if str(line).strip()]
    intent = learner_intent(learner_text)
    asked = questions_in(spoken_lines[-3:])
    settled = asked[-1:] if intent in {"yes", "no"} and asked else []
    return SceneLedger(
        intent=intent,
        settled=settled,
        said=[*[str(t) for t in learner_before if str(t).strip()], str(learner_text)],
        spoken=spoken_lines,
    )


# ---------------------------------------------------------------------------
# line checks
# ---------------------------------------------------------------------------

#: A question that demands the yes/no the learner just gave.
_DEMANDS_ANSWER = re.compile(
    r"\boui\s+ou\s+non\b|\bou\s+(?:pas|non)\s*\?|\bor not\b", re.IGNORECASE
)


def _overlap(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / min(len(left), len(right))


def reasks_settled_question(reply: str, ledger: SceneLedger) -> str | None:
    """#132 / #171: the learner answered yes or no; the reply asks the same thing again.

    A reply that «Pardon ? … oui ou non ?» after a clear «Non, je ne vend pas» tells
    the learner their French did not work. Caught by the literal demand for a yes/no
    and by a question that repeats the settled one (most of its content words)."""

    if ledger.intent not in {"yes", "no"}:
        return None
    for sentence in _sentences(reply):
        if not sentence.endswith("?") and not _DEMANDS_ANSWER.search(sentence):
            continue
        again = bool(_DEMANDS_ANSWER.search(sentence))
        for old in ledger.settled:
            old_words, new_words = _content(old), _content(sentence)
            if (
                old_words
                and _overlap(new_words, old_words) >= 0.75
                and len(new_words) <= len(old_words) + 2
            ):
                again = True
        if again:
            return (
                f"«{sentence}» asks again what the learner just answered "
                f"({'no' if ledger.intent == 'no' else 'yes'}). Take the answer as given: "
                "react to it and move on; ask something new, never the same question."
            )
    return None


#: Facts the world bible fixes: what an organisation or person is *not*. A line that
#: says «<name> est un·e <noun>» with one of these nouns redefines the cast or the
#: antagonist (#132: «Solvel est une collègue qui aide pour les visites»; Solvel is the
#: buyer that wants the building).
ESTABLISHED_NOT: dict[str, frozenset[str]] = {
    "solvel": frozenset(
        "collegue ami amie voisin voisine employe employee cousin cousine copain copine "
        "locataire client cliente notaire proche famille serveur serveuse guide".split()
    ),
}


def redefines_established(reply: str, never: dict[str, frozenset[str]] | None = None) -> str | None:
    """#132: «X est <un·e> <noun>» where the world bible fixed what X is not."""

    for name, banned in (never if never is not None else ESTABLISHED_NOT).items():
        pattern = re.compile(
            rf"\b{re.escape(name)}(?:\s+immobilier)?\s+(?:est|etait|serait)\s+(?:une|un|le|la|l')\s*([a-z]+)"
        )
        for sentence in _sentences(reply):
            match = pattern.search(_fold(sentence))
            if match and match.group(1) in banned:
                return (
                    f"«{sentence}» redefines {name.title()}, whom the story has already "
                    "established (the real-estate buyer that wants the building). Keep what "
                    "the story says; answer the learner's question with what is already known."
                )
    return None


_TRACKING = re.compile(
    r"\bnum[eé]ro\s+de\s+(?:suivi|commande|colis|r[eé]f[eé]rence|dossier)\b|\btracking\b|\bsuivi\s+(?:du|de la)\s+(?:colis|commande)\b"
    r"|\b(?:ma|ta|votre|la)\s+commande\b|\bcolis\b|\br[eé]f[eé]rence\s*(?:n°|:|\d)",
    re.IGNORECASE,
)
_ADDRESS_REQUEST = re.compile(
    r"\b(?:ton|votre|ta|tes|vos)\s+(?:adresse|num[eé]ro de t[eé]l[eé]phone|iban|mot de passe|code postal|pi[eè]ce d['’]identit[eé])\b"
    r"|\b(?:confirme[rz]?|donne[rz]?|envoie[rz]?|indique[rz]?)\s+(?:moi\s+)?(?:ton|votre|ta|vos|tes)\s+(?:adresse|iban|mot de passe)\b",
    re.IGNORECASE,
)
_LONG_NUMBER = re.compile(r"\b\d[\d ]{5,}\d\b")


def invents_logistics(reply: str, learner_text: str, context: str = "") -> str | None:
    """#114: an order, a tracking or reference number, or a request for the learner's
    address that nobody in the scene mentioned. ``context`` is the scene's own text
    (a parcel the story really has is allowed through)."""

    known = _fold(f"{learner_text} {context}")
    for sentence in _sentences(reply):
        hit = _TRACKING.search(sentence)
        if hit and _fold(hit.group(0)) not in known:
            return (
                f"«{sentence}» brings in an order, parcel or reference number that nobody "
                "in the story mentioned. Answer what the learner wrote; invent no object, "
                "number or errand."
            )
        number = _LONG_NUMBER.search(sentence)
        if number and number.group(0) not in known:
            return f"«{sentence}» invents a number. Use only numbers the story or the learner gave."
        if _ADDRESS_REQUEST.search(sentence) and not _ADDRESS_REQUEST.search(_fold(known)):
            return (
                f"«{sentence}» asks the learner for personal data (an address, a number, a "
                "password). A character in this story never does; answer what was written."
            )
    return None


# The engine's own recap («the learner says…») and its UI-language cousins.
_RECAP = re.compile(
    r"\bthe\s+learner\b|\bder\s+lernende\b|\bdie\s+lernende\b|\ble\s+(?:learner|apprenant)\b|\bla\s+apprenante\b"
    r"|\bl['’]apprenant(?:e)?\b|\bel\s+(?:alumno|estudiante)\b|\blearner\s+(?:says|wrote|will)\b",
    re.IGNORECASE,
)
_ENGLISH_NARRATOR = re.compile(r"\b(?:the|will|says|have|papers|shared|then)\b", re.IGNORECASE)


def internal_recap_text(text: str) -> str | None:
    """#168: the engine's scene recap («The learner says they will have coffee…») is
    internal state. It must never be shown as story text, whatever the UI language."""

    match = _RECAP.search(str(text or ""))
    return match.group(0) if match else None


def is_english_recap(text: str, *, story_language: str = "fr") -> bool:
    """A narrator note in English inside a French story's panel text."""

    if story_language != "fr":
        return False
    sample = str(text or "")
    return len(_ENGLISH_NARRATOR.findall(sample)) >= 3 and not re.search(
        r"[àâçéèêëîïôùûœ]", sample.casefold()
    )


def bare_appointment(line: str) -> bool:
    """#129: a line that is only a day and an hour («Jeudi prochain, dix-huit heures.»)
    names no purpose. True when the whole sentence is a time with nothing it is for."""

    text = str(line or "").strip()
    if not text:
        return False
    folded = _fold(text)
    day = r"(?:lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche|demain)(?:\s+(?:prochain|matin|soir))?"
    hour = r"(?:\d{1,2}\s?(?:h|heures?)(?:\s?\d{2})?|[a-z-]+\s+heures?)"
    return bool(re.fullmatch(rf"\W*{day}[ ,]*(?:a\s+)?{hour}\W*", folded))


def line_problems(reply: str, ledger: SceneLedger, *, context: str = "") -> list[str]:
    """Every ledger problem with one generated line (empty when it is clean)."""

    checks = (
        reasks_settled_question(reply, ledger),
        redefines_established(reply),
        invents_logistics(reply, ledger.learner_text, context),
    )
    return [hint for hint in checks if hint]
