"""Phase 1, Maßstab: the detector — lines a reader hears at once as a machine.

The 30 generated days of the paid runs of 7 and 8 October read like a machine: a
caption narrates the learner's turn («Tout le monde attend ta réponse.»), a character
talks like a teacher («Dis une phrase avec «J'ai».») or like a contract («quelle
condition tu veux que je respecte»), «néanmoins» and «désormais» are forced into speech
below B2, a line comes twice on one page, and the task runs to 20–37 words. No guard
and no critic looked for any of it (stories plan, «Diagnose» 1–5).

This module finds those lines with string rules: deterministic, free and fast enough
to run on every generated day in production.

* :func:`page_hits` reads the page the director wrote. Its hits are ``blocking``: the
  page is written again with :func:`feedback`, never the day lost.
* :func:`reply_hits` reads what is written after the page (the character's reply, the
  ending). Its hits are counted only: a page rewrite cannot fix them.
* ``python -m app.services.season.prose_detector FILE.md …`` counts both over the
  live-read transcripts (:mod:`app.services.season.transcript`), one row per file.

The rules are narrow on purpose: every French line and caption of the authored season
passes them at every level (``tests/test_prose_detector.py``). A rule that trips an
authored line is narrowed, never the test. Pure functions: no model call, no database.
"""

from __future__ import annotations

import json
import re
import statistics
import sys
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

#: The longest task a reader takes in at a glance: the character's question, not a brief.
TASK_MAX_WORDS = 12

#: Below B2 the written-register connectors are a word list forced into speech: the
#: B1 test learner's mots_a_placer were exactly these five.
CONNECTOR_BANDS = frozenset({"A1", "A2", "B1"})

PAGE_KINDS = (
    "quiz_caption",
    "teacher_talk",
    "contract_words",
    "written_connector",
    "repeated_line",
    "long_task",
)
REPLY_KINDS = ("deferred_ending", "leaves_without_answer", "glued_self_repair")


@dataclass(frozen=True)
class Hit:
    """One machine line.

    ``where`` is ``premise``, ``caption:<i>``, ``line:<i>:<j>``, ``opening``, ``task``,
    ``answer`` (page side), or ``reply`` / ``resolution`` (reply side); ``text`` is the
    sentence that tripped the rule, verbatim, so a rewrite can find it."""

    kind: str
    where: str
    text: str
    blocking: bool


# ---------------------------------------------------------------------------
# Text: one apostrophe, one hyphen, one space; sentences; words
# ---------------------------------------------------------------------------

#: The model mixes typographic variants freely («Dis‑moi», «s’est»): the rules read one
#: of each. Every mapping is one character for one, so a folded sentence lines up with
#: the original.
_FOLD = str.maketrans(
    {
        "’": "'",
        "‘": "'",
        "ʼ": "'",
        "‐": "-",
        "‑": "-",
        " ": " ",
        " ": " ",
        " ": " ",
    }
)
_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")
#: A word: letters or digits, with the apostrophes and hyphens inside it («J'ai»,
#: «dis-moi» are one word each; «garder/partager/vendre» is three).
_WORD = re.compile(r"[^\W_]+(?:['\-][^\W_]+)*")


def _fold(text: str) -> str:
    return str(text or "").translate(_FOLD)


def _sentences(text: Any) -> list[str]:
    """The sentences of a text, verbatim: a hit quotes the sentence, not the paragraph."""

    return [part.strip() for part in _SENTENCE_END.split(str(text or "").strip()) if part.strip()]


def _normal(text: Any) -> str:
    """A line as a reader compares it: case, punctuation and spacing do not count."""

    return re.sub(r"[\W_]+", "", _fold(str(text or "")).casefold())


def task_words(text: str) -> int:
    """Words in a task line. Punctuation on its own («:» and «?» with French spacing) is
    not a word."""

    return len(_WORD.findall(_fold(text)))


def _band(level: Any) -> str:
    """«B1.1» → «B1»; an unknown level is ``""`` (no band rule applies)."""

    match = re.match(r"\s*([ABC][12])", str(level or "").upper())
    return match.group(1) if match else ""


def _rule(*patterns: str) -> re.Pattern[str]:
    return re.compile("|".join(f"(?:{pattern})" for pattern in patterns), re.IGNORECASE)


# ---------------------------------------------------------------------------
# Page-side rules
# ---------------------------------------------------------------------------

#: The learner's answer or turn, as something narration waits for. Not a turn in a
#: queue («Tu attends ton tour.»).
_YOUR_TURN = r"réponse|phrase|décision|suite|choix|voix|parole|verdict|commande"

#: After «une réponse», «la décision»: not someone else's («la réponse du médecin», «une
#: réponse claire de Berlin»), unless it is the learner's («de toi», «de ta part»).
_NOT_SOMEONE_ELSES = (
    r"(?!(?:\s+(?!(?:avant|après|pour|sans|depuis|dès)\b)\w+)?\s*"
    r"(?:du\b|des\b|d'|de\s+(?!toi\b|vous\b|ta\s+part\b|votre\s+part\b)))"
)

#: quiz_caption — narration (a caption or the premise) that tells the learner it is
#: their turn, that their answer decides, or that someone is waiting for it. The
#: authored captions narrate what happens: «En haut, l'appartement attend toujours.»
#: (no answer waited for), «Demain matin, c'est le tour de Lila.» (not the learner's
#: turn), «Maintenant, c'est toi que tout le monde regarde.» (a look, not a wait).
_QUIZ = _rule(
    # «Margaux attend ta réponse», «Romy attend ta décision écrite», «le comptoir
    # attend ta voix».
    r"\battend(?:s|ent|ait|aient|ra|ront|ant)?\s+(?:toujours\s+|encore\s+|maintenant\s+|juste\s+)?"
    rf"(?:ta|ton|tes|votre|vos)\s+(?:\w+\s+)?(?:{_YOUR_TURN})s?\b",
    # «Lila attend une réponse.», «Margaux attend la réponse comme on attend la saison.»
    r"\battend(?:s|ent|ait|aient|ra|ront|ant)?\s+(?:toujours\s+|encore\s+|maintenant\s+|juste\s+)?"
    rf"(?:une|la)\s+(?:\w+\s+)?(?:réponse|décision|verdict)\b{_NOT_SOMEONE_ELSES}",
    # «Tout le monde attend.», «tout le monde attend que quelqu'un fixe la suite», «tout
    # le monde attend un compromis concret» — not «Tout le monde attend le bus.»
    r"\b(?:tout\s+le\s+monde|le\s+groupe|toute\s+la\s+table|toute\s+la\s+salle)\s+(?:t'|vous\s+)?"
    r"attend(?:ent|ait)?(?=\s*(?:[.!?…;:,]|$)|\s+(?:que\s+(?:tu|vous|quelqu'un)\b|"
    r"(?:ta|ton|tes|votre|vos|toujours|encore|maintenant)\b|en\s+silence\b|de\s+toi\b|"
    r"(?:un|une|la|le)\s+(?:\w+\s+)?(?:réponse|décision|compromis|accord|proposition|plan|choix|"
    r"verdict|suite)\b))",
    r"\battend(?:ent|ait|ra)?\s+(?:toujours\s+|encore\s+)?que\s+(?:tu|vous)\b",
    # «C'est ton tour.», «C'est le moment.», «C'est le moment : choisis ta commande
    # habituelle en français.», «Maintenant, c'est à toi.», «C'est à toi de parler.» —
    # not «C'est le moment de fermer.», nor «C'est à toi ?» (whose it is).
    r"\bc'est\s+(?:ton|votre)\s+tour\b",
    r"\bc'est\s+le\s+moment\b(?!\s*(?:où\b|d'|de\s+(?!(?:(?:te|vous)\s+)?"
    r"(?:parler|répondre|décider|choisir|dire|jouer|lancer)\b)))",
    r"\bc'est\s+(?:maintenant\s+)?à\s+(?:toi|vous)\b(?=\s*(?:[.!…;:]|$|maintenant\b))",
    r"\bà\s+(?:toi|vous)\s+de\s+(?:jouer|parler|répondre|décider|choisir|dire)\b",
    # «Ta décision va décider du ton de l'article.», «Ta réponse peut décider de sa route.»
    # — not «Ta voix va trembler.»
    r"\b(?:ta|votre)\s+(?:réponse|décision|phrase|parole|choix)\s+"
    r"(?:\w+\s+)?(?:va|vont|peut|pourrait|décide|décidera|change|changera|compte|comptera|pèse|fera)\b",
    # «la décision repose maintenant sur toi», «la décision est à toi» — not «la décision
    # repose sur un malentendu».
    r"\bla\s+décision\s+(?:\w+\s+)?(?:repose(?:ra)?\s+(?:maintenant\s+|désormais\s+|entièrement\s+|donc\s+)?"
    r"sur\s+(?:toi|vous|tes|vos)\b|est\s+à\s+(?:toi|vous)\b|t'appartient|vous\s+appartient|"
    r"dépend\s+de\s+(?:toi|vous)\b|est\s+entre\s+(?:tes|vos)\s+mains|doit\s+tomber)",
    r"\bdécision\s+que\s+tu\s+(?:fais|prends|vas\s+prendre)\b",
    r"\btout\s+dépend\s+de\s+(?:toi|vous|ta\s+réponse|ce\s+que\s+tu)\b",
)

#: Where an imperative stands. In speech and the task: at the head of any clause («…,
#: explique brièvement pourquoi, et propose une condition claire», «Décide maintenant si
#: Lila peut partir et propose un accord précis»). In narration only at the head of the
#: sentence or after a colon («Un espace vide t'attend : écris la condition.»): anywhere
#: else «propose», «explique», «donne» are a character's act («Marin pose la louche,
#: propose un plan.»). Never after a subject: «Je te propose un plan.», «J'écris une
#: phrase pour Odile.», «Marin explique pourquoi la soupe est salée.»
_CLAUSE_HEAD = (
    r"(?:^|(?<=[,:;(—–]\s)|(?<=[,:;(—–])|(?<=\bet\s)|(?<=\bou\s)|(?<=\bpuis\s)|(?<=\balors\s))"
)
_SENTENCE_HEAD = r"(?:^|(?<=:\s)|(?<=:))"


def _teacher(head: str) -> re.Pattern[str]:
    """teacher_talk in French — the exercise, not the fiction — with its imperatives at
    ``head``. Authored lines that must pass: «Dis un mot !», «Dis-moi quelque chose de
    vrai.», «C'est la phrase la plus faible de la langue française.», «C'est exactement
    ma phrase.», «Chez toi, on parle français.»"""

    return _rule(
        # «Dis une phrase avec «J'ai».», «Écris une phrase sur la carte.», «Réponds en une
        # phrase.», «Répète ta phrase.», «Dis quelque chose de simple, s'il te plaît.» —
        # not «Je te le dis en une phrase : je reste.», «Marin résume tout en une phrase.»
        rf"{head}dis(?:-moi|-nous|-lui)?\s+une\s+(?:\w+\s+)?phrase\b",
        rf"{head}(?:écris|écrivez)\s+(?:une|deux|trois|ta|votre)\s+(?:\w+\s+)?phrases?\b",
        rf"{head}(?:dis|dites|réponds|répondez|écris|écrivez|explique|expliquez|résume|résumez|"
        r"raconte|racontez)(?:-le|-la|-moi|-nous|-lui|-leur)?\s+(?:\w+\s+){0,2}?"
        r"en\s+une\s+(?:seule\s+)?phrase\b",
        rf"{head}(?:dis|donne|écris|répète)(?:-moi|-nous|-lui)?\s+(?:\w+\s+)?ta\s+phrase\b",
        rf"{head}dis\s+quelque\s+chose\s+de\s+simple\b",
        # «Lila attend ta phrase.», «Ta phrase, s'il te plaît ?» — not «Finis ta phrase.»,
        # «Ta phrase d'hier m'a touchée.»
        r"\battend\w*\s+(?:\w+\s+)?ta\s+phrase\b",
        r"\bta\s+phrase\s*(?:,\s*s'il\b|\?|avec\b|en\s+français\b)",
        # «Juste une phrase courte, d'accord ?», «une phrase avec «J'ai»» — not «C'est une
        # phrase simple mais vraie.»
        r"\b(?:une|ta|votre|cette|la)\s+phrase\s+(?:courte|complète|entière|en\s+français)\b",
        r"\b(?:une|ta|votre)\s+phrase\s+(?:avec|qui\s+commence)\b",
        # «Dis-le en français.», «Lila te chuchote des phrases utiles.»
        r"\ben\s+français\b",
        r"\b(?:phrases?|mots?|expressions?)\s+utiles?\b",
    )


_TEACHER_SAID = _teacher(_CLAUSE_HEAD)
_TEACHER_NARRATED = _teacher(_SENTENCE_HEAD)

#: teacher_talk in a task written in the learner's own language (A1/A2 tasks are
#: English or German): «with a sentence that starts 'J'ai...'», «in French».
_TEACHER_TASK = _rule(
    r"\bin\s+French\b",
    r"\bsentences?\b",
    r"\b(?:starts?|starting|begins?|beginning)\s+with\s+['\"«‘“]",
    r"\b(?:use|using)\s+the\s+(?:word|verb|phrase|expression|form|tense)\b",
    r"\bauf\s+Französisch\b",
    r"\b(?:Satz|Sätze|Sätzen)\b",
    r"\b(?:benutze|verwende|nutze)\s+(?:das|die|den)\s+(?:Wort|Verb|Ausdruck|Form|Zeit)\b",
)

#: What a brief asks the learner to hand over.
_DEAL = r"conditions?|plans?|accords?|engagements?|compromis"

#: «condition(s)», not the conjunction or a state: «à condition de/que» (the bible: «Ici,
#: on s'aime à condition de se retenir.»), «sans condition», «dans ces conditions», «en
#: bonne condition», «les conditions de travail», «la condition humaine».
_CONDITION = (
    r"(?<!\bà\s)(?<!\bà\sla\s)(?<!\bsans\s)(?<!dans\sces\s)(?<!bonne\s)(?<!bonnes\s)(?<!mauvaise\s)"
    r"(?<!mauvaises\s)\bconditions?\b(?!\s+(?:de\s+(?:vie|travail|santé)|physiques?|humaines?|météo\w*)\b)"
)


def _contract(head: str, *, said: bool) -> re.Pattern[str]:
    """contract_words — brief and contract vocabulary: the agency contract's
    «conditions», the MOVE's «reason», asked of the learner as if they were filling in a
    form. Plain French passes: «Pour quelle raison ?», «Sans ton accord, je ne publie
    rien.», «Je propose qu'on mange.», a character's own offer («Je te propose un plan.»)
    or plea («Donne-moi une raison de rester.», «Explique-moi pourquoi.»). ``said``:
    speech and the task, where «en expliquant brièvement pourquoi» and «Tu peux me
    proposer un plan ?» are the brief; in narration they are what a character does."""

    patterns = [
        _CONDITION,
        r"\bengagements?\s+(?:concrets?|précis|clairs?|écrits?)\b",
        r"\b(?:accords?|engagements?)\s+écrits?\b",
        # «Donne une raison.», «…, explique brièvement pourquoi, et propose une condition»
        rf"{head}donn(?:e|ez|er)\s+(?:une|ta|votre|deux|trois)\s+(?:\w+\s+)?raisons?\b(?!\s*(?:de\b|d'))",
        rf"{head}expli(?:que|quez|quer)\s+(?:brièvement|pourquoi|en\s+quelques\s+mots)\b",
        rf"{head}propos(?:e|ez|er)\s+(?:une|un|des|les|tes|ta|ton|votre|vos)\s+(?:\w+\s+)?(?:{_DEAL})\b",
        r"\bdéfends?\s+ta\s+(?:décision|position)\b",
        r"\bjustifiez?\s+(?:ta|votre)\s+(?:réponse|décision|choix|position|avis)\b",
    ]
    if said:
        patterns += [
            r"\ben\s+donnant\s+(?:une|ta|votre|deux|trois)\s+(?:\w+\s+)?raisons?\b",
            r"\ben\s+expliquant\s+(?:brièvement|pourquoi)\b",
            r"\bexpliquer\s+brièvement\b",
            rf"\ben\s+proposant\s+(?:une|un|des)\s+(?:\w+\s+)?(?:{_DEAL})\b",
            rf"\b(?:me|nous)\s+proposer\s+(?:une|un|des)\s+(?:\w+\s+)?(?:{_DEAL})\b",
            r"\ben\s+justifiant\b",
        ]
    return _rule(*patterns)


_CONTRACT_SAID = _contract(_CLAUSE_HEAD, said=True)
_CONTRACT_NARRATED = _contract(_SENTENCE_HEAD, said=False)

#: contract_words in a task written in English or German.
_CONTRACT_TASK = _rule(
    _CONDITION,
    r"\bgive\s+(?:a|one|your|two)\s+(?:\w+\s+)?reasons?\b",
    r"\bexplain\s+(?:briefly|why|in\s+a\s+few\s+words)\b",
    r"\bpropose\s+(?:a|an)\s+(?:\w+\s+)?(?:condition|plan|deal|agreement|compromise|commitment)\b",
    r"\bjustif(?:y|ication)\b",
    r"\bBedingung(?:en)?\b",
    r"\bbegründe\b",
    r"\b(?:nenne|gib)\s+(?:einen|deinen|zwei)\s+Gr(?:u|ü)nde?\b",
)

#: written_connector — written register forced into speech below B2. «Aussitôt dit,
#: aussitôt fait» is spoken French and passes.
_CONNECTOR = re.compile(
    r"\b(néanmoins|toutefois|notamment|désormais|aussitôt)\b(?!\s+(?:dit|fait)\b)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Reply-side rules: written after the page, counted only
# ---------------------------------------------------------------------------

#: deferred_ending — the day ends on «tomorrow» or «later» instead of the character's
#: own conclusion: «On reprendra la question demain au Mistral.», «Elle reviendra
#: demain pour une phrase claire.», «on verra demain», «la question reste ouverte».
#: A plan for tomorrow is a conclusion and passes («On commence demain après-midi.»).
_DEFERRED = _rule(
    r"\b(?:reviendr|repasser)(?:a|ai|as|ons|ez|ont)\s+(?:\w+\s+){0,2}?demain\b",
    r"\breprendr(?:a|ai|as|ons|ez|ont)\s+(?:la|cette)\s+(?:question|discussion)\b",
    r"\b(?:on|nous)\s+(?:en\s+)?(?:verra|verrons|reparle(?:ra|rons)?|rediscute(?:ra|rons)?)\s+demain\b",
    # «Le départ reste en suspens.», «en attente d'une réponse précise plus tard»
    r"\breste(?:nt|ra)?\s+(?:encore\s+|toujours\s+)?en\s+(?:suspens|attente)\b",
    r"\ben\s+attente\s+d",
    # «la question reste ouverte», «la décision reste à prendre» — not «La porte reste
    # ouverte.»
    r"\b(?:question|sujet|décision|discussion|conversation|situation|réponse|parole|choix|débat)s?\b"
    r"[^.;:!?]{0,40}?\breste(?:nt|ra)?\s+(?:encore\s+|toujours\s+)?"
    r"(?:ouverte?s?|à\s+venir|à\s+prendre|à\s+trancher)\b",
    r"\battendra\s+si\s+un\s+jour\b",
    r"\b(?:décision|question)(?:\s+\w+)?\s+n'est\s+pas\s+(?:encore\s+)?(?:\w+\s+)?"
    r"(?:prise|tranchée|réglée|bouclée)\b",
    r"\bla\s+conversation\s+reprendra\b",
)

#: deferred_ending, in the day's ending only: the ending waits for the learner's answer
#: («elle attend ta réponse écrite avant d'agir», «en attendant que tu reviennes avec une
#: idée concrète»). In a reply the same words are the conversation going on.
_WAITING_ENDING = _rule(
    r"\battend(?:s|ent|ait|ant|ra)?\s+(?:toujours\s+|encore\s+)?(?:ta|ton|tes|votre|vos)\s+(?:\w+\s+)?"
    r"(?:réponse|décision|proposition|accord|choix|suite)s?\b",
    r"\battend(?:s|ent|ait|ant|ra)?\s+(?:toujours\s+|encore\s+)?(?:une|un|la)\s+(?:\w+\s+)?"
    rf"(?:réponse|décision|proposition|accord)\b{_NOT_SOMEONE_ELSES}",
    r"\battendant\s+que\s+(?:tu|vous)\b",
)

#: leaves_without_answer — the authored fallback ending (``living_story.fallback_turn``):
#: the character leaves before answering. Not «Elle hésite avant de répondre.»
_LEAVES = _rule(
    r"\b(?:doi(?:t|s|vent)\s+partir|(?:a|ont)\s+dû\s+partir|part|partent|s'en\s+va|s'en\s+vont|"
    r"est\s+partie?|sont\s+parti(?:e)?s|appelée?s?\s+ailleurs)\s+avant\s+de\s+répondre\b"
)

#: glued_self_repair — «Pardon ? Tu peux le redire autrement ?» appended by code to a
#: reply that already said something (``journey_conversation.SELF_REPAIR_REPETITION_FR``):
#: a correction in the plot, not in the margin.
_GLUED_REPAIR = re.compile(
    r"\S.*?(?P<repair>Pardon\s*\?\s*(?:Tu\s+peux|Vous\s+pouvez)\s+le\s+redire\s+autrement\s*\?)\s*$",
    re.IGNORECASE | re.DOTALL,
)


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------


def _as_page(draft: Any) -> dict[str, Any]:
    if hasattr(draft, "model_dump"):
        return draft.model_dump(mode="json")
    if isinstance(draft, Mapping):
        return dict(draft)
    raise TypeError(f"a SceneDraft or a dict of the same shape, not {type(draft).__name__}")


def _field_hit(
    kind: str, where: str, text: Any, rule: re.Pattern[str], *, blocking: bool
) -> Hit | None:
    """One hit per text and kind, quoting the sentences that tripped the rule."""

    found = [sentence for sentence in _sentences(text) if rule.search(_fold(sentence))]
    return Hit(kind, where, " ".join(found), blocking) if found else None


def _places(page: Mapping[str, Any]) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """``(narration, speech)``: the premise and captions; the dialogue lines and the
    character's question to the learner, in page order, each with its ``where``."""

    narration = [("premise", str(page.get("premise_fr") or ""))]
    speech: list[tuple[str, str]] = []
    for index, panel in enumerate(page.get("panels") or []):
        if not isinstance(panel, Mapping):
            continue
        narration.append((f"caption:{index}", str(panel.get("narration_fr") or "")))
        for number, line in enumerate(panel.get("dialogue") or []):
            if isinstance(line, Mapping):
                speech.append((f"line:{index}:{number}", str(line.get("text_fr") or "")))
    speech.append(("opening", str(page.get("opening_line_fr") or "")))
    keep = [(where, text) for where, text in narration if text.strip()]
    return keep, [(where, text) for where, text in speech if text.strip()]


def page_hits(draft: Any, *, level: str, signature_phrases: Iterable[str] = ()) -> list[Hit]:
    """Every machine line on a page the director wrote (``SceneDraft`` or its dict).

    Blocking: a page with a hit is written again with :func:`feedback`. ``level`` is the
    learner's band («B1» or «B1.1»); ``signature_phrases`` are the cast's own refrains
    («J'ai rien entendu.»), which may come back on one page."""

    page = _as_page(draft)
    narration, speech = _places(page)
    task = str(page.get("objective_native") or "").strip()
    answer = str(page.get("suggested_response_fr") or "").strip()
    hits: list[Hit] = []

    def add(hit: Hit | None) -> None:
        if hit is not None:
            hits.append(hit)

    for where, text in narration:
        add(_field_hit("quiz_caption", where, text, _QUIZ, blocking=True))
    for kind, narrated, said, in_task in (
        ("teacher_talk", _TEACHER_NARRATED, _TEACHER_SAID, _TEACHER_TASK),
        ("contract_words", _CONTRACT_NARRATED, _CONTRACT_SAID, _CONTRACT_TASK),
    ):
        for where, text in narration:
            add(_field_hit(kind, where, text, narrated, blocking=True))
        for where, text in speech:
            add(_field_hit(kind, where, text, said, blocking=True))
        # The task is the learner's brief: French at B1 and up, English or German below.
        found = [
            sentence
            for sentence in _sentences(task)
            if said.search(_fold(sentence)) or in_task.search(_fold(sentence))
        ]
        if found:
            hits.append(Hit(kind, "task", " ".join(found), True))
    if _band(level) in CONNECTOR_BANDS:
        spoken = [*speech, *([("answer", answer)] if answer else [])]
        for where, text in spoken:
            for sentence in _sentences(text):
                for _match in _CONNECTOR.finditer(_fold(sentence)):
                    hits.append(Hit("written_connector", where, sentence, True))
    exempt = {_normal(phrase) for phrase in signature_phrases} - {""}
    said: set[str] = set()
    for where, text in speech:
        key = _normal(text)
        if not key or key in exempt:
            continue
        if key in said:
            hits.append(Hit("repeated_line", where, text.strip(), True))
        said.add(key)
    if task and task_words(task) > TASK_MAX_WORDS:
        hits.append(Hit("long_task", "task", task, True))
    return hits


def reply_hits(text: str, *, where: str = "reply") -> list[Hit]:
    """Machine endings in a text written after the page: the character's reply
    (``where="reply"``) or the day's ending (``where="resolution"``). Counted only."""

    hits: list[Hit] = []
    leaves = _field_hit("leaves_without_answer", where, text, _LEAVES, blocking=False)
    if leaves is not None:
        # The fallback's «la conversation reprendra» is the same ending, not a second one.
        hits.append(leaves)
    else:
        found = [
            sentence
            for sentence in _sentences(text)
            if _DEFERRED.search(_fold(sentence))
            or (where == "resolution" and _WAITING_ENDING.search(_fold(sentence)))
        ]
        if found:
            hits.append(Hit("deferred_ending", where, " ".join(found), False))
    match = _GLUED_REPAIR.match(_fold(str(text or "")).strip())
    if match:
        before = _sentences(str(text).strip()[: match.start("repair")])
        quote = " ".join(
            [*before[-1:], str(text).strip()[match.start("repair") : match.end("repair")]]
        )
        hits.append(Hit("glued_self_repair", where, quote, False))
    return hits


# ---------------------------------------------------------------------------
# Feedback for a rewrite
# ---------------------------------------------------------------------------

_ADVICE = {
    "quiz_caption": (
        "caption narrates the learner's turn",
        "captions show what happens, never the answer, a decision or anyone waiting",
    ),
    "teacher_talk": (
        "exercise talk inside the story",
        "nobody asks for a sentence, a word or French; the character asks what they want to know",
    ),
    "contract_words": (
        "brief or contract words",
        "people ask in their own words, never for conditions, a reason to give or a plan to propose",
    ),
    "written_connector": (
        "written-register connector in speech",
        "below B2 people speak plainly: no «néanmoins», «toutefois», «notamment», «désormais», «aussitôt»",
    ),
    "repeated_line": (
        "the same line twice on the page",
        "each line is said once; the question to the learner does not repeat a panel",
    ),
    "long_task": (
        "task too long",
        f"the task is the character's question in at most {TASK_MAX_WORDS} words",
    ),
    "deferred_ending": (
        "ending put off until later",
        "the character draws their own conclusion from what the learner said, today",
    ),
    "leaves_without_answer": (
        "character leaves without answering",
        "the character answers before the day ends",
    ),
    "glued_self_repair": (
        "self-repair glued to the reply",
        "a correction goes in the margin, never into the character's line",
    ),
}


def feedback(hits: Iterable[Hit]) -> list[str]:
    """One short instruction per kind for the rewrite, quoting the offending text."""

    quotes: dict[str, list[str]] = {}
    for hit in hits:
        texts = quotes.setdefault(hit.kind, [])
        if hit.text not in texts:
            texts.append(hit.text)
    out = []
    for kind, texts in quotes.items():
        label, advice = _ADVICE.get(kind, (kind.replace("_", " "), "rewrite it"))
        if kind == "long_task":
            label = f"task of {task_words(texts[0])} words"
        quoted = ", ".join(f"'{text}'" for text in texts[:3])
        more = f" and {len(texts) - 3} more" if len(texts) > 3 else ""
        out.append(f"{label} ({quoted}{more}): {advice}")
    return out


def signature_phrases(world: Mapping[str, Any]) -> list[str]:
    """The cast's refrains from a world bible (``cast[].signature_phrases``)."""

    phrases: list[str] = []
    for member in world.get("cast") or []:
        if isinstance(member, Mapping):
            phrases.extend(
                str(phrase)
                for phrase in member.get("signature_phrases") or []
                if str(phrase).strip()
            )
    return phrases


# ---------------------------------------------------------------------------
# Live-read transcripts (app.services.season.transcript.render_generated_day)
# ---------------------------------------------------------------------------

_LEVEL = re.compile(r"\bniveau\s+([ABC][12](?:\.\d)?)", re.IGNORECASE)
_PANEL = re.compile(r"^\*\*P\d+\*\*")
_CAPTION = re.compile(r"^> \*(?P<text>.*)\*\s*$")
_SPOKEN = re.compile(r"^\*\*(?P<who>[^*]+)\*\*(?P<aside>[^«]*)— «(?P<text>.*)»\s*$")
_TASK = re.compile(r"^\*Ta tâche\s*:\s*(?P<text>.*?)\*?\s*$")


@dataclass
class TranscriptDay:
    """One generated day of a transcript: the page as a draft dict, then what was
    written after it."""

    heading: str
    page: dict[str, Any]
    replies: list[str]
    resolution: str


def read_transcript(text: str) -> tuple[str, list[TranscriptDay]]:
    """``(level, generated days)`` of a live-read transcript. Tentpole days and lost
    days are the bible's or the fallback's, not the director's: they are skipped."""

    level = _LEVEL.search(text)
    days = [
        _read_day(section.splitlines())
        for section in re.split(r"^## ", text, flags=re.MULTILINE)[1:]
        if "(jour généré)" in section.split("\n", 1)[0]
    ]
    return (level.group(1) if level else ""), days


def _read_day(lines: list[str]) -> TranscriptDay:
    page: dict[str, Any] = {
        "premise_fr": "",
        "panels": [],
        "opening_line_fr": "",
        "objective_native": "",
    }
    replies: list[str] = []
    resolution = ""
    after_page = False
    for line in lines[1:]:
        if _PANEL.match(line):
            page["panels"].append({"narration_fr": "", "dialogue": []})
        elif task := _TASK.match(line):
            page["objective_native"] = task.group("text").strip()
            after_page = True
        elif caption := _CAPTION.match(line):
            if after_page:
                resolution = caption.group("text")
            elif page["panels"]:
                page["panels"][-1]["narration_fr"] = caption.group("text")
            else:
                page["premise_fr"] = caption.group("text")
        elif spoken := _SPOKEN.match(line):
            who, text = spoken.group("who").strip(), spoken.group("text")
            if who == "Toi":
                after_page = True
            elif after_page:
                replies.append(text)
            elif "se tourne vers toi" in spoken.group("aside"):
                page["opening_line_fr"], page["character_id"] = text, who
            elif page["panels"]:
                page["panels"][-1]["dialogue"].append({"character_id": who, "text_fr": text})
    return TranscriptDay(lines[0].strip(), page, replies, resolution)


def transcript_counts(text: str, *, signature_phrases: Iterable[str] = ()) -> dict[str, Any]:
    """Hits per kind over a transcript's generated days, and its task lengths."""

    level, days = read_transcript(text)
    phrases = list(signature_phrases)
    counts: Counter[str] = Counter()
    tasks: list[int] = []
    for day in days:
        for hit in page_hits(day.page, level=level, signature_phrases=phrases):
            counts[hit.kind] += 1
        for reply in day.replies:
            counts.update(hit.kind for hit in reply_hits(reply, where="reply"))
        if day.resolution:
            counts.update(hit.kind for hit in reply_hits(day.resolution, where="resolution"))
        if day.page.get("objective_native"):
            tasks.append(task_words(day.page["objective_native"]))
    return {"level": level, "days": len(days), "counts": counts, "tasks": tasks}


_COLUMNS = (
    ("quiz", "quiz_caption"),
    ("teacher", "teacher_talk"),
    ("contract", "contract_words"),
    ("connector", "written_connector"),
    ("repeated", "repeated_line"),
    ("deferred", "deferred_ending"),
    ("leaves", "leaves_without_answer"),
    ("glued", "glued_self_repair"),
)


def _row(name: str, level: str, days: int, counts: Mapping[str, int], tasks: Sequence[int]) -> str:
    median = statistics.median(tasks) if tasks else 0
    cells = [
        name,
        level,
        str(days),
        *(str(counts.get(kind, 0)) for _label, kind in _COLUMNS),
        f"{median:g} / {max(tasks, default=0)}",
        f"{sum(1 for words in tasks if words > TASK_MAX_WORDS)} of {len(tasks)}",
    ]
    return "| " + " | ".join(cells) + " |"


def _season_phrases() -> list[str]:
    world = Path(__file__).resolve().parents[2] / "data" / "season" / "s1" / "world.json"
    try:
        return signature_phrases(json.loads(world.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return []


def main(argv: Sequence[str] | None = None) -> int:
    """``python -m app.services.season.prose_detector FILE.md [FILE.md ...]``: one row
    per transcript, and the total."""

    paths = list(sys.argv[1:] if argv is None else argv)
    if not paths:
        print(main.__doc__)
        return 2
    phrases = _season_phrases()
    header = [
        "file",
        "level",
        "days",
        *(label for label, _kind in _COLUMNS),
        "task median / longest",
        f"tasks > {TASK_MAX_WORDS} words",
    ]
    print("| " + " | ".join(header) + " |")
    print("|" + "---|" * len(header))
    total: Counter[str] = Counter()
    all_tasks: list[int] = []
    all_days = 0
    for path in paths:
        result = transcript_counts(
            Path(path).read_text(encoding="utf-8"), signature_phrases=phrases
        )
        print(_row(path, result["level"], result["days"], result["counts"], result["tasks"]))
        total.update(result["counts"])
        all_tasks += result["tasks"]
        all_days += result["days"]
    print(_row("total", "", all_days, total, all_tasks))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
