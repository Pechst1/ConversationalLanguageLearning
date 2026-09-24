"""WP-25 — an honest placement in the first five minutes.

Until this existed, a learner's CEFR level was **self-declared** for their first
forty in-app attempts (``DECLARED_LEVEL_EVIDENCE_ATTEMPTS``), because the
threshold walk in :mod:`app.services.cefr_progress` measures what the app has
verified and an empty database verifies nothing. The declaration is a decent
guess and a terrible measurement: the learners most likely to churn are exactly
the ones whose first week is served at the wrong band.

This module asks instead. Four to six short prompts in French, each drawn from a
CEFR band chosen by how the previous answer went, graded by the same paid
checker the Séance correction uses, and turned into an estimate that carries its
own confidence, its per-dimension breakdown and the evidence it was built from.

Three properties are load-bearing and every one of them has a test:

* **Resumable.** The conversation lives in ``placement_sessions``; a learner who
  closes the app comes back to the same open session with the same graded turns.
* **Idempotent.** Grading is a paid call. Replaying a response for a turn that is
  already graded returns the stored grading and pays nothing.
* **Honest under failure.** If the provider does not answer, the session is
  ``unassessed`` and carries **no level**. A placement that could not be measured
  says so; it never invents a band, and it never silently falls back to the
  declaration while wearing the word "placement".

What this module deliberately does not do: it does not grade French itself. The
verdict comes from :meth:`LLMService.generate_error_detection`, the same call
site policy as ``atelier_correction_cost`` — bounded request, one priced pilot
event per real call, telemetry failures swallowed.
"""
from __future__ import annotations

import hashlib
import json
import statistics
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from loguru import logger
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models.placement import PlacementSession
from app.db.models.user import User
from app.services.atelier_correction_cost import bound_learner_answer
from app.services.cefr_progress import CEFR_LEVELS, declared_level_floor, level_index
from app.services.journey_contracts import normalize_control_language
from app.services.llm_service import LLMProviderError, LLMService
from app.services.pilot_events import PilotEventService

PLACEMENT_VERSION = "placement-v1"

#: The pilot-ledger event type for one placement grading call. Read by name in
#: ``scripts/pilot_digest.py``, exactly as ``atelier_correction`` is.
PLACEMENT_EVENT_TYPE = "placement_grading"

#: The ladder the placement walks. It stops at B2.1: nothing in the prompt bank
#: can tell B2.1 from B2.2 in one paragraph, and claiming otherwise would be the
#: same dishonesty this package exists to remove.
PLACEMENT_BANDS: tuple[str, ...] = ("A1.1", "A1.2", "A2.1", "A2.2", "B1.1", "B1.2", "B2.1")

#: Four turns is the floor for an estimate, six the ceiling for the five-minute
#: promise (≈40 s of reading and writing per turn).
MIN_TURNS = 4
MAX_TURNS = 6

#: Stop early once the estimate has stopped moving: above this, more turns buy
#: precision the product cannot use and spend the learner's five minutes.
CONFIDENCE_TO_STOP = 0.7

#: Below this, the placement is reported but is **not** allowed to outrank the
#: learner's own declaration — a wobbly measurement is not better than a guess.
MIN_PRIOR_CONFIDENCE = 0.45

#: Ceiling on the learner text sent to the paid grader, shared with the Séance
#: correction so one pasted document cannot size a paid request.
ANSWER_MAX_CHARS = 1200

#: The dimensions a placement reports. They are the ones a single written turn
#: can actually evidence; fluency and pronunciation are not among them.
DIMENSIONS: tuple[str, ...] = ("range", "accuracy", "coherence", "task")

DIMENSION_LABELS_FR: dict[str, str] = {
    "range": "Richesse du lexique",
    "accuracy": "Correction grammaticale",
    "coherence": "Cohérence du propos",
    "task": "Réponse à la consigne",
}


@dataclass(frozen=True)
class PlacementPrompt:
    """One rung of the ladder."""

    band: str
    #: What the learner reads. French, second person, one speech act.
    prompt_fr: str
    #: The one-line brief the grader is told the prompt was asking for.
    intent: str
    #: A gentle nudge, shown under the field. Never an answer.
    hint_fr: str
    #: WP-69. Stable id, stored on the turn: the grader is told this prompt's
    #: own intent, and a session never shows the same id twice.
    prompt_id: str = ""


def _rung(band: str, suffix: str, prompt_fr: str, intent: str, hint_fr: str) -> PlacementPrompt:
    return PlacementPrompt(
        band=band,
        prompt_fr=prompt_fr,
        intent=intent,
        hint_fr=hint_fr,
        prompt_id=f"{band}-{suffix}",
    )


#: WP-69 (L3). Six prompts per band. The ladder *holds* a band on a middle score
#: and gives a second chance on a first low one, so one learner can meet the same
#: band on every turn of a session — and on 2026-09-22 did, three times, with the
#: same question. Six per band is :data:`MAX_TURNS`, so a session can never run
#: out of fresh prompts at any band. Every prompt in a band keeps that band's one
#: intent family and one speech act; each asks for a *production*, never a
#: recognition, because a placement that can be passed by picking an option
#: measures nothing. The first entry of each band is the original WP-25 prompt.
PROMPT_VARIANTS: dict[str, tuple[PlacementPrompt, ...]] = {
    # Introduce oneself — present tense, personal facts.
    "A1.1": (
        _rung("A1.1", "a", "Bonjour ! Présentez-vous en une ou deux phrases : votre prénom et d’où vous venez.",
              "introduce oneself: name and origin, present tense", "Une ou deux phrases suffisent."),
        _rung("A1.1", "b", "Vous rencontrez une nouvelle voisine. Dites-lui votre prénom et dans quelle ville vous habitez.",
              "introduce oneself: name and city of residence, present tense", "Deux phrases courtes suffisent."),
        _rung("A1.1", "c", "C’est votre premier cours de français. Dites votre prénom, votre âge et votre nationalité.",
              "introduce oneself: name, age and nationality, present tense", "Trois informations, en phrases courtes."),
        _rung("A1.1", "d", "Présentez-vous à votre nouveau professeur : votre prénom et votre travail ou vos études.",
              "introduce oneself: name and job or studies, present tense", "Une ou deux phrases suffisent."),
        _rung("A1.1", "e", "Un collègue français vous demande : « Vous parlez quelles langues ? » Répondez en une ou deux phrases.",
              "say which languages one speaks, present tense", "Une ou deux phrases suffisent."),
        _rung("A1.1", "f", "Écrivez deux phrases sur votre famille : combien vous êtes, et le prénom d’une personne.",
              "introduce one's family simply: how many and one name, present tense", "Deux phrases simples."),
    ),
    # A simple polite request in a shop, café or street — present tense.
    "A1.2": (
        _rung("A1.2", "a", "Vous êtes au café. Commandez une boisson et demandez le prix.",
              "order a drink and ask the price, polite present tense", "Deux phrases, à voix haute dans votre tête d’abord."),
        _rung("A1.2", "b", "Vous êtes à la boulangerie. Demandez poliment deux croissants et une baguette.",
              "order items in a bakery politely, present tense", "Pensez à la politesse."),
        _rung("A1.2", "c", "Au marché, vous voulez des pommes. Demandez un kilo et demandez combien ça coûte.",
              "ask for a quantity and the price at a market, polite present tense", "Deux phrases suffisent."),
        _rung("A1.2", "d", "Dans la rue, vous cherchez la gare. Demandez poliment le chemin à un passant.",
              "politely ask a passer-by for directions, present tense", "Commencez par saluer."),
        _rung("A1.2", "e", "À la réception d’un hôtel, demandez une chambre pour deux nuits.",
              "request a hotel room for two nights, polite present tense", "Une ou deux phrases polies."),
        _rung("A1.2", "f", "Au restaurant, demandez la carte au serveur, puis commandez un plat.",
              "ask for the menu and order a dish, polite present tense", "Deux phrases, une pour chaque demande."),
    ),
    # Narrate a recent past event — past tense required.
    "A2.1": (
        _rung("A2.1", "a", "Racontez ce que vous avez fait le week-end dernier, en trois phrases.",
              "narrate a past weekend in three sentences, past tense required", "Le temps du passé est attendu ici."),
        _rung("A2.1", "b", "Racontez ce que vous avez fait hier soir, en trois phrases.",
              "narrate the previous evening in three sentences, past tense required", "Le temps du passé est attendu ici."),
        _rung("A2.1", "c", "Racontez votre dernière journée de vacances, en trois phrases.",
              "narrate a recent holiday day in three sentences, past tense required", "Trois phrases au passé."),
        _rung("A2.1", "d", "Racontez votre dernier anniversaire : où vous étiez, avec qui, et ce que vous avez fait.",
              "narrate a past birthday: place, people, activities; past tenses required", "Le temps du passé est attendu ici."),
        _rung("A2.1", "e", "Racontez un bon repas que vous avez pris récemment, en trois phrases.",
              "narrate a recent meal: where, what, with whom; past tense required", "Trois phrases au passé."),
        _rung("A2.1", "f", "Racontez votre dernier voyage en train ou en avion, en trois phrases.",
              "narrate a recent journey in three sentences, past tense required", "Le temps du passé est attendu ici."),
    ),
    # A short practical message: apologise and rearrange — register-appropriate.
    "A2.2": (
        _rung("A2.2", "a", "Vous arrivez en retard à un rendez-vous. Écrivez le message que vous envoyez pour vous excuser et proposer une autre heure.",
              "apologise for lateness and propose a new time, register-appropriate", "Excusez-vous, puis proposez une heure."),
        _rung("A2.2", "b", "Vous ne pouvez pas venir au dîner de samedi chez une amie. Écrivez-lui un message pour vous excuser et proposer un autre jour.",
              "decline an invitation with an apology and propose another day, informal register", "Excusez-vous, puis proposez un jour."),
        _rung("A2.2", "c", "Vous devez annuler un rendez-vous chez le médecin. Écrivez un message au cabinet pour vous excuser et demander un autre rendez-vous.",
              "cancel an appointment with an apology and ask for a new one, formal register", "Vous écrivez à un cabinet : restez poli."),
        _rung("A2.2", "d", "Vous ne pouvez pas aller à la réunion de demain. Écrivez un message à votre responsable pour vous excuser et proposer un autre moment.",
              "excuse oneself from a meeting and propose another time, professional register", "Excusez-vous, puis proposez un moment."),
        _rung("A2.2", "e", "Votre train a du retard et vous allez manquer le début du cours. Écrivez un message au professeur pour le prévenir et vous excuser.",
              "warn of a delay and apologise, polite register", "Prévenez, puis excusez-vous."),
        _rung("A2.2", "f", "Vous avez oublié l’anniversaire d’un collègue. Écrivez-lui un petit message pour vous excuser et l’inviter à prendre un café.",
              "apologise for forgetting and make an invitation, friendly-professional register", "Excusez-vous, puis invitez."),
    ),
    # An opinion with a reason — connectors expected.
    "B1.1": (
        _rung("B1.1", "a", "Un ami hésite entre vivre en ville et vivre à la campagne. Donnez votre avis et une raison, en quatre phrases.",
              "give an opinion with a reason, connectors expected", "Une opinion, puis pourquoi."),
        _rung("B1.1", "b", "Une amie se demande s’il vaut mieux voyager seule ou en groupe. Donnez votre avis et une raison, en quatre phrases.",
              "give an opinion with a reason, connectors expected", "Une opinion, puis pourquoi."),
        _rung("B1.1", "c", "Vaut-il mieux apprendre une langue avec une application ou avec un professeur ? Donnez votre avis et justifiez-le, en quatre phrases.",
              "give an opinion with a reason, connectors expected", "Une opinion, puis pourquoi."),
        _rung("B1.1", "d", "Votre collègue pense que le télétravail est meilleur que le bureau. Êtes-vous d’accord ? Expliquez pourquoi, en quatre phrases.",
              "agree or disagree with an opinion and give a reason, connectors expected", "Dites si vous êtes d’accord, puis pourquoi."),
        _rung("B1.1", "e", "Un ami veut acheter une voiture alors qu’il habite en ville. Est-ce une bonne idée ? Donnez votre avis et une raison, en quatre phrases.",
              "give an opinion with a reason, connectors expected", "Une opinion, puis pourquoi."),
        _rung("B1.1", "f", "Est-ce une bonne idée de lire les nouvelles tous les matins ? Donnez votre avis et une raison, en quatre phrases.",
              "give an opinion with a reason, connectors expected", "Une opinion, puis pourquoi."),
    ),
    # Narrate across tenses, including a hypothetical.
    "B1.2": (
        _rung("B1.2", "a", "Racontez une fois où un projet ne s’est pas passé comme prévu : ce que vous aviez espéré, ce qui est arrivé, ce que vous feriez autrement.",
              "narrate a failed plan across tenses, including a hypothetical", "Trois temps différents sont attendus."),
        _rung("B1.2", "b", "Racontez un voyage qui ne s’est pas passé comme prévu : ce que vous aviez prévu, ce qui s’est passé, ce que vous feriez autrement.",
              "narrate a trip that went wrong across tenses, including a hypothetical", "Trois temps différents sont attendus."),
        _rung("B1.2", "c", "Racontez une décision que vous regrettez un peu : la situation, ce que vous avez choisi, ce que vous feriez aujourd’hui.",
              "narrate a regretted decision across tenses, including a hypothetical", "Trois temps différents sont attendus."),
        _rung("B1.2", "d", "Racontez une fête que vous aviez organisée et qui a mal tourné : ce que vous aviez prévu, ce qui est arrivé, ce que vous changeriez.",
              "narrate an event that went wrong across tenses, including a hypothetical", "Trois temps différents sont attendus."),
        _rung("B1.2", "e", "Racontez une fois où vous vous êtes perdu : où vous alliez, ce qui s’est passé, ce que vous feriez autrement.",
              "narrate getting lost across tenses, including a hypothetical", "Trois temps différents sont attendus."),
        _rung("B1.2", "f", "Racontez votre premier jour dans un nouveau travail ou une nouvelle école : ce que vous imaginiez, comment il s’est passé, ce que vous conseilleriez à quelqu’un.",
              "narrate a first day across tenses, including a conditional piece of advice", "Trois temps différents sont attendus."),
    ),
    # Argue a position while answering a serious objection.
    "B2.1": (
        _rung("B2.1", "a", "On propose d’interdire les voitures dans le centre de votre ville. Défendez une position en tenant compte d’une objection sérieuse.",
              "argue a position while conceding a counter-argument, abstract register", "Nommez l’objection avant d’y répondre."),
        _rung("B2.1", "b", "Certains proposent de rendre les transports publics gratuits. Défendez une position en répondant à une objection sérieuse.",
              "argue a position while conceding a counter-argument, abstract register", "Nommez l’objection avant d’y répondre."),
        _rung("B2.1", "c", "Faut-il interdire les téléphones portables à l’école ? Prenez position et répondez à l’argument le plus fort du camp opposé.",
              "argue a position while conceding a counter-argument, abstract register", "Nommez l’objection avant d’y répondre."),
        _rung("B2.1", "d", "La semaine de quatre jours devrait-elle devenir la norme ? Défendez votre point de vue en tenant compte d’une objection sérieuse.",
              "argue a position while conceding a counter-argument, abstract register", "Nommez l’objection avant d’y répondre."),
        _rung("B2.1", "e", "Faut-il limiter le nombre de touristes dans les villes très visitées ? Argumentez en répondant à une objection sérieuse.",
              "argue a position while conceding a counter-argument, abstract register", "Nommez l’objection avant d’y répondre."),
        _rung("B2.1", "f", "Le vote devrait-il être obligatoire ? Défendez une position en discutant un contre-argument sérieux.",
              "argue a position while conceding a counter-argument, abstract register", "Nommez l’objection avant d’y répondre."),
    ),
}

#: 2026-09-24 — the hint under the field is the app's own words, not the test:
#: the placement follows the learner's declared native language, so every
#: authored hint has its English and German version. The prompt stays French.
HINT_TRANSLATIONS: dict[str, dict[str, str]] = {
    "Commencez par saluer.": {"en": "Start with a greeting.", "de": "Beginnen Sie mit einer Begrüßung."},
    "Deux phrases courtes suffisent.": {"en": "Two short sentences are enough.", "de": "Zwei kurze Sätze genügen."},
    "Deux phrases simples.": {"en": "Two simple sentences.", "de": "Zwei einfache Sätze."},
    "Deux phrases suffisent.": {"en": "Two sentences are enough.", "de": "Zwei Sätze genügen."},
    "Deux phrases, une pour chaque demande.": {
        "en": "Two sentences, one for each request.",
        "de": "Zwei Sätze, einer für jede Bitte.",
    },
    "Deux phrases, à voix haute dans votre tête d’abord.": {
        "en": "Two sentences — say them in your head first.",
        "de": "Zwei Sätze — sagen Sie sie zuerst im Kopf.",
    },
    "Dites si vous êtes d’accord, puis pourquoi.": {
        "en": "Say whether you agree, then why.",
        "de": "Sagen Sie, ob Sie zustimmen, und dann warum.",
    },
    "Excusez-vous, puis invitez.": {"en": "Apologise, then invite.", "de": "Entschuldigen Sie sich, dann laden Sie ein."},
    "Excusez-vous, puis proposez un jour.": {
        "en": "Apologise, then suggest a day.",
        "de": "Entschuldigen Sie sich, dann schlagen Sie einen Tag vor.",
    },
    "Excusez-vous, puis proposez un moment.": {
        "en": "Apologise, then suggest a time.",
        "de": "Entschuldigen Sie sich, dann schlagen Sie einen Zeitpunkt vor.",
    },
    "Excusez-vous, puis proposez une heure.": {
        "en": "Apologise, then suggest a time.",
        "de": "Entschuldigen Sie sich, dann schlagen Sie eine Uhrzeit vor.",
    },
    "Le temps du passé est attendu ici.": {"en": "The past tense is expected here.", "de": "Hier wird die Vergangenheit erwartet."},
    "Nommez l’objection avant d’y répondre.": {
        "en": "Name the objection before you answer it.",
        "de": "Nennen Sie den Einwand, bevor Sie darauf antworten.",
    },
    "Pensez à la politesse.": {"en": "Remember to be polite.", "de": "Denken Sie an die Höflichkeit."},
    "Prévenez, puis excusez-vous.": {"en": "Let them know, then apologise.", "de": "Sagen Sie Bescheid, dann entschuldigen Sie sich."},
    "Trois informations, en phrases courtes.": {
        "en": "Three pieces of information, in short sentences.",
        "de": "Drei Angaben, in kurzen Sätzen.",
    },
    "Trois phrases au passé.": {"en": "Three sentences in the past tense.", "de": "Drei Sätze in der Vergangenheit."},
    "Trois temps différents sont attendus.": {"en": "Three different tenses are expected.", "de": "Drei verschiedene Zeitformen werden erwartet."},
    "Une opinion, puis pourquoi.": {"en": "An opinion, then why.", "de": "Eine Meinung, dann warum."},
    "Une ou deux phrases polies.": {"en": "One or two polite sentences.", "de": "Ein oder zwei höfliche Sätze."},
    "Une ou deux phrases suffisent.": {"en": "One or two sentences are enough.", "de": "Ein oder zwei Sätze genügen."},
    "Vous écrivez à un cabinet : restez poli.": {
        "en": "You are writing to a surgery: stay polite.",
        "de": "Sie schreiben an eine Praxis: Bleiben Sie höflich.",
    },
}


def hint_by_language(hint_fr: str) -> dict[str, str]:
    """``{fr, en, de}`` for an authored hint; ``{fr}`` alone for anything else."""
    return {"fr": hint_fr, **HINT_TRANSLATIONS.get(hint_fr, {})}


#: Every prompt by id. The stored turn names its prompt by this id.
PROMPTS_BY_ID: dict[str, PlacementPrompt] = {
    prompt.prompt_id: prompt for variants in PROMPT_VARIANTS.values() for prompt in variants
}

#: One prompt per band — the original WP-25 bank, kept for callers that only
#: need *a* prompt at a band. The session itself uses :func:`prompt_for_session`.
PROMPT_BANK: dict[str, PlacementPrompt] = {
    band: variants[0] for band, variants in PROMPT_VARIANTS.items()
}


def _used_prompt_ids(turns: list[dict[str, Any]] | None) -> set[str]:
    """The prompts a session has already shown, legacy turns included.

    A turn written before WP-69 carries no ``prompt_id``; its text still names
    the prompt, so it is matched on that.
    """

    by_text = {prompt.prompt_fr: prompt.prompt_id for prompt in PROMPTS_BY_ID.values()}
    used: set[str] = set()
    for turn in turns or []:
        if not isinstance(turn, dict):
            continue
        prompt_id = turn.get("prompt_id")
        if prompt_id:
            used.add(str(prompt_id))
            continue
        legacy = by_text.get(str(turn.get("prompt_fr") or ""))
        if legacy:
            used.add(legacy)
    return used


def prompt_for_session(
    band: str, *, session_key: str, turns: list[dict[str, Any]] | None = None
) -> PlacementPrompt:
    """The prompt this session shows at ``band`` now: fresh, and deterministic.

    Deterministic per session — the envelope that *shows* the prompt and the
    ``respond`` that *grades* the answer compute the same one from the same
    turns, and a reload shows the same question — but ordered differently for
    different sessions, so two learners (or one learner's re-run) do not walk
    the same sequence. A prompt already shown in this session is never chosen
    while the band has another; with six per band and at most six turns that
    never happens.
    """

    resolved = clamp_band(band_index(band))
    variants = PROMPT_VARIANTS[resolved]
    used = _used_prompt_ids(turns)

    def order(prompt: PlacementPrompt) -> str:
        return hashlib.sha256(f"{session_key}:{prompt.prompt_id}".encode()).hexdigest()

    fresh = [prompt for prompt in variants if prompt.prompt_id not in used]
    return min(fresh or list(variants), key=order)


_GRADING_RESPONSE_FORMAT: dict[str, Any] = {
    "type": "json_schema",
    "json_schema": {
        "name": "placement_grading",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "score_0_4": {"type": "number"},
                "demonstrated_band": {"type": "string", "enum": list(PLACEMENT_BANDS)},
                "dimensions": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {name: {"type": "number"} for name in DIMENSIONS},
                    "required": list(DIMENSIONS),
                },
                "evidence_fr": {"type": "string"},
                "evidence_native": {"type": "string"},
                "off_task": {"type": "boolean"},
            },
            "required": [
                "score_0_4",
                "demonstrated_band",
                "dimensions",
                "evidence_fr",
                "evidence_native",
                "off_task",
            ],
        },
    },
}

_GRADING_SYSTEM_PROMPT = (
    "You are placing a learner of French on the CEFR scale from one short written response. "
    "You are not teaching and not correcting: produce a measurement, nothing else.\n"
    "Rules:\n"
    "- score_0_4 rates how well the response meets the prompt AT THE PROMPT'S OWN BAND. "
    "A perfect A1 sentence answering an A1 prompt scores 4; the same sentence answering a B1 prompt does not.\n"
    "- demonstrated_band is the highest CEFR band the response itself evidences, independent of the prompt's band. "
    "Judge it from what the learner wrote, never from what the prompt asked for.\n"
    "- Each dimension is 0-4: range (lexical and structural variety), accuracy (grammar, agreement, spelling), "
    "coherence (does it hang together), task (did it do what was asked).\n"
    "- evidence_fr is ONE short French clause quoting or naming what you judged, so a learner can see the reason. "
    "Never longer than 20 words, never a correction, never advice.\n"
    "- evidence_native is the same note written for the learner in the language whose code is "
    "evidence_language (en, de or fr). Any words you quote from the learner's response stay in French, "
    "verbatim, inside quotation marks; only the note around them is in evidence_language.\n"
    "- off_task is true when the response is empty, in another language, or does not attempt the prompt. "
    "An off-task response scores 0 and demonstrates nothing.\n"
    "- Do not flatter and do not round up. A placement that is one band too high costs the learner their first week."
)


# ---------------------------------------------------------------------------
# The adaptive ladder
# ---------------------------------------------------------------------------


def band_index(band: str | None) -> int:
    """Position of ``band`` on the placement ladder, clamped into range."""
    try:
        return PLACEMENT_BANDS.index(str(band))
    except ValueError:
        return level_index(band) if str(band or "") in CEFR_LEVELS else 1


def clamp_band(index: int) -> str:
    return PLACEMENT_BANDS[max(0, min(len(PLACEMENT_BANDS) - 1, index))]


def opening_band(user: User | None, evidence: dict[str, Any] | None = None) -> str:
    """Where the ladder starts.

    One rung **below** what the learner said about themselves, floored at A1.2.
    Starting at the declaration and failing is a demoralising first minute; the
    ladder climbs quickly, so a rung of headroom costs at most one turn.

    WP-75: the learner's own days are a prior too. When
    :func:`journey_placement_evidence` says they met their band's objectives
    unaided, the ladder starts no lower than the top rung of that band — never
    higher: a few café orders are evidence of a band, not of the next one.
    """
    declared = declared_level_floor(user) if user is not None else None
    start = 1 if not declared else max(1, band_index(declared) - 1)
    if evidence and evidence.get("above_band") and evidence.get("band"):
        top_rung = f"{str(evidence['band']).upper()[:2]}.2"
        if top_rung in PLACEMENT_BANDS:
            start = max(start, band_index(top_rung))
    return clamp_band(start)


# ---------------------------------------------------------------------------
# WP-75 — placement is offered after the learner's own days, never at sign-up
# ---------------------------------------------------------------------------

#: Completed days before placement is offered at all.
PLACEMENT_OFFER_MIN_DAYS = 3
#: How many of the learner's latest completed days the evidence reads.
JOURNEY_EVIDENCE_WINDOW = 5
#: Unaided, fully met replies within that window that say "above this band".
JOURNEY_EVIDENCE_MET_UNAIDED = 3
#: A declaration at or below this floor is «Nouveau» (``starting_point="new"``).
NEW_LEARNER_FLOOR = "A1.1"


def journey_placement_evidence(db: Session, user: User) -> dict[str, Any]:
    """What the learner's completed days say about their band. Reads, never writes.

    Deliberately simple and honest: a day's reply either met its objective with
    no help recorded by the server, or it did not. ``above_band`` needs
    :data:`JOURNEY_EVIDENCE_MET_UNAIDED` such replies among the latest
    :data:`JOURNEY_EVIDENCE_WINDOW` days, each at (or above) the band the
    learner is currently estimated at — a learner meeting A1 objectives with no
    help has outgrown A1 as far as the days can tell.
    """

    from app.db.models.daily_journey import DailyJourney

    completed = (
        db.query(DailyJourney)
        .filter(DailyJourney.user_id == user.id, DailyJourney.status == "completed")
        .order_by(DailyJourney.completed_at.desc(), DailyJourney.local_date.desc())
    )
    total = int(completed.count())
    recent = completed.limit(JOURNEY_EVIDENCE_WINDOW).all()
    current_band = str(getattr(user, "cefr_estimate", "") or declared_level_floor(user) or "A1.1")[:2].upper()
    met_unaided = 0
    met_bands: list[str] = []
    for journey in recent:
        band = str(journey.level_band or "").upper()[:2]
        for step in journey.steps or []:
            if str(step.kind) != "respond":
                continue
            result = (step.private_task or {}).get("result") or {}
            if result.get("outcome") != "met" or result.get("assistance_level") not in (None, "none"):
                continue
            if band and band >= current_band:
                met_unaided += 1
                met_bands.append(band)
    return {
        "completed_days": total,
        "window": len(recent),
        "met_unaided": met_unaided,
        "band": min(met_bands) if met_bands else None,
        "above_band": met_unaided >= JOURNEY_EVIDENCE_MET_UNAIDED,
    }


def placement_offer(db: Session, user: User) -> bool:
    """Should the app offer the placement now?

    Only after :data:`PLACEMENT_OFFER_MIN_DAYS` completed days, only to a
    learner who has neither taken nor declined one, and only when it can tell
    them something: they declared more than «Nouveau», or their days suggest
    they are above the band they are working at. Never at sign-up.
    """

    evidence = journey_placement_evidence(db, user)
    if evidence["completed_days"] < PLACEMENT_OFFER_MIN_DAYS:
        return False
    decided = (
        db.query(PlacementSession.id)
        .filter(
            PlacementSession.user_id == user.id,
            PlacementSession.status.in_(("complete", "skipped")),
        )
        .first()
    )
    if decided is not None:
        return False
    declared = declared_level_floor(user) or NEW_LEARNER_FLOOR
    declared_new = level_index(declared) <= level_index(NEW_LEARNER_FLOOR)
    return (not declared_new) or bool(evidence["above_band"])


def next_band(
    current: str, score_0_4: float | None, turns: list[dict[str, Any]] | None = None
) -> str:
    """Escalate, hold, or de-escalate from one graded turn.

    An ungraded turn (``None`` — the provider did not answer) holds the band: a
    missing measurement must not move the ladder in either direction.

    A *first* low turn at a band the learner has just climbed to holds it too
    (``turns`` is the history before this one). The 2026-09-17 calibration placed
    a B1 learner at A2.2 because one misread B1.1 prompt sent the ladder straight
    back down; two low turns at that band are needed to descend, one is a second
    chance at the same rung.
    """
    if score_0_4 is None:
        return clamp_band(band_index(current))
    if score_0_4 >= 3.0:
        return clamp_band(band_index(current) + 1)
    if score_0_4 <= 1.5:
        if turns is not None and _climbed_into(turns, current) and not _low_turn_at(turns, current):
            return clamp_band(band_index(current))
        return clamp_band(band_index(current) - 1)
    return clamp_band(band_index(current))


def _score_of(turn: dict[str, Any]) -> float | None:
    score = (turn.get("grading") or {}).get("score_0_4")
    return float(score) if isinstance(score, (int, float)) else None


def _climbed_into(turns: list[dict[str, Any]], band: str) -> bool:
    """Did the learner *earn* this rung — a strong turn one band below it?

    The second chance is for a learner who climbed here and then misread one
    prompt. A learner who *started* high (a declared B2 who is not) and scores
    low on the first rung has earned nothing yet; the ladder descends at once,
    so a weak run still reaches the bottom inside the turn budget.
    """
    below = band_index(band) - 1
    return any(
        turn.get("band") == clamp_band(below) and band_index(str(turn.get("band"))) == below
        and (_score_of(turn) or 0.0) >= 3.0
        for turn in turns
    )


def _low_turn_at(turns: list[dict[str, Any]], band: str) -> bool:
    """Has an earlier graded turn at ``band`` already scored low?"""
    return any(
        turn.get("band") == band and (score := _score_of(turn)) is not None and score <= 1.5
        for turn in turns
    )


def demonstrated_index(*, band: str, score_0_4: float, grader_band: str | None = None) -> float:
    """What one graded turn says about the learner, as a ladder position.

    The prompt's own band anchors it — clearing a B1.1 prompt is evidence about
    B1.1 — and the score moves it. The grader's independent read of the response
    (``grader_band``) is averaged in when it gave one, so a learner who writes
    far above the prompt is not capped by the rung they happened to be on.
    """
    anchor = float(band_index(band))
    if score_0_4 >= 3.5:
        from_prompt = anchor + 1.0
    elif score_0_4 >= 2.5:
        from_prompt = anchor
    elif score_0_4 >= 1.5:
        from_prompt = anchor - 0.5
    else:
        from_prompt = anchor - 1.5
    if grader_band is None:
        return from_prompt
    return (from_prompt + float(band_index(grader_band))) / 2.0


# ---------------------------------------------------------------------------
# The estimate
# ---------------------------------------------------------------------------


@dataclass
class PlacementEstimate:
    """The result of a placement, or its honest absence."""

    status: str
    level: str | None
    confidence: float
    dimensions: dict[str, float] = field(default_factory=dict)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    graded_turns: int = 0
    version: str = PLACEMENT_VERSION

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "status": self.status,
            "level": self.level,
            "confidence": round(float(self.confidence), 3),
            "dimensions": {key: round(float(value), 2) for key, value in self.dimensions.items()},
            "dimension_labels": {key: DIMENSION_LABELS_FR[key] for key in self.dimensions if key in DIMENSION_LABELS_FR},
            "evidence": self.evidence,
            "graded_turns": self.graded_turns,
        }


def estimate_from_turns(turns: list[dict[str, Any]]) -> PlacementEstimate:
    """Turn the graded turns into a level, a confidence, and its evidence.

    A turn counts only when it carries a grading. Zero graded turns is the
    ``unassessed`` case and yields **no level at all** — the whole point of the
    package. Later turns weigh more than earlier ones: the ladder converges, so
    the last rung is the better evidence.
    """
    graded = [turn for turn in turns if isinstance(turn.get("grading"), dict)]
    if not graded:
        return PlacementEstimate(status="unassessed", level=None, confidence=0.0, graded_turns=0)

    positions: list[float] = []
    weights: list[float] = []
    dimension_totals: dict[str, list[float]] = {name: [] for name in DIMENSIONS}
    evidence: list[dict[str, Any]] = []
    for order, turn in enumerate(graded, start=1):
        grading = turn["grading"]
        score = float(grading.get("score_0_4") or 0.0)
        position = demonstrated_index(
            band=str(turn.get("band") or "A1.2"),
            score_0_4=score,
            grader_band=grading.get("demonstrated_band"),
        )
        positions.append(position)
        weights.append(float(order))
        dimensions = grading.get("dimensions")
        if isinstance(dimensions, dict):
            for name in DIMENSIONS:
                value = dimensions.get(name)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    dimension_totals[name].append(float(value))
        evidence.append(
            {
                "band": turn.get("band"),
                "prompt_fr": turn.get("prompt_fr"),
                "answer": turn.get("answer"),
                "score_0_4": round(score, 2),
                "demonstrated_band": grading.get("demonstrated_band"),
                "evidence_fr": grading.get("evidence_fr"),
                # The one-language rule: the note is the app's own words, so it
                # is also served in the learner's language when the grader wrote it.
                "evidence_native": grading.get("evidence_native"),
                "evidence_language": grading.get("evidence_language"),
                "model": grading.get("model"),
            }
        )

    weighted = sum(p * w for p, w in zip(positions, weights, strict=True)) / sum(weights)
    level = clamp_band(int(round(weighted)))

    # Confidence is agreement, not volume: turns that all say the same thing are
    # worth more than turns that disagree, and four turns is where it can start
    # being called a measurement at all.
    spread = statistics.pstdev(positions) if len(positions) > 1 else 1.0
    confidence = 0.34 + 0.11 * len(positions) - 0.20 * spread
    confidence = max(0.1, min(0.92, confidence))

    dimensions_mean = {
        name: sum(values) / len(values) for name, values in dimension_totals.items() if values
    }
    return PlacementEstimate(
        status="complete",
        level=level,
        confidence=confidence,
        dimensions=dimensions_mean,
        evidence=evidence,
        graded_turns=len(graded),
    )


def should_continue(turns: list[dict[str, Any]], estimate: PlacementEstimate) -> bool:
    """Is another rung worth the learner's time?"""
    asked = len(turns)
    if asked >= MAX_TURNS:
        return False
    if asked < MIN_TURNS:
        return True
    return estimate.confidence < CONFIDENCE_TO_STOP


# ---------------------------------------------------------------------------
# The paid grading call
# ---------------------------------------------------------------------------


def record_placement_cost(
    db: Session,
    result: Any,
    *,
    user_id: UUID | None,
    session_id: UUID | None,
    turn_index: int,
    band: str,
) -> None:
    """One priced pilot-ledger row per real placement grading call.

    Same policy as :func:`app.services.atelier_correction_cost.record_correction_cost`:
    the provider's own usage metadata, written through the caller's transaction,
    never committed here, and every telemetry failure swallowed — a learner must
    never lose their placement to a bookkeeping error.
    """
    try:
        PilotEventService(db).record(
            PLACEMENT_EVENT_TYPE,
            user_id=user_id,
            entity_type="placement_session",
            entity_id=session_id,
            payload={
                "provider": getattr(result, "provider", None),
                "model": getattr(result, "model", None),
                "prompt_tokens": int(getattr(result, "prompt_tokens", 0) or 0),
                "completion_tokens": int(getattr(result, "completion_tokens", 0) or 0),
                "total_tokens": int(getattr(result, "total_tokens", 0) or 0),
                "turn_index": int(turn_index),
                "band": str(band),
            },
            cost_usd=float(getattr(result, "cost", 0.0) or 0.0),
        )
    except Exception:  # pragma: no cover - defensive
        logger.warning("Placement cost row could not be written")


def normalize_grading(
    parsed: Any, *, model: str | None = None, language: str | None = None
) -> dict[str, Any]:
    """Validate the grader's answer. Raises ``ValueError`` on anything unusable.

    An unusable grading is a *failure*, not a zero: a zero would push the ladder
    down and end the placement one band too low on a provider hiccup.
    """
    if not isinstance(parsed, dict):
        raise ValueError("grading is not an object")
    score = parsed.get("score_0_4")
    if isinstance(score, bool) or not isinstance(score, (int, float)) or not 0 <= score <= 4:
        raise ValueError("grading carries no usable score")
    band = parsed.get("demonstrated_band")
    if band is not None and band not in PLACEMENT_BANDS:
        raise ValueError("grading names a band outside the ladder")
    raw_dimensions = parsed.get("dimensions")
    dimensions: dict[str, float] = {}
    if isinstance(raw_dimensions, dict):
        for name in DIMENSIONS:
            value = raw_dimensions.get(name)
            if isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 4:
                dimensions[name] = float(value)
    if not dimensions:
        raise ValueError("grading carries no dimension breakdown")
    off_task = bool(parsed.get("off_task"))
    evidence = str(parsed.get("evidence_fr") or "").strip()[:240]
    # The note in the learner's language (``language``); French learners and a
    # grader that left it out fall back to the French note, labelled ``fr``.
    evidence_language = normalize_control_language(language) if language else None
    native = str(parsed.get("evidence_native") or "").strip()[:240]
    if evidence_language == "fr" or not native:
        native, evidence_language = (evidence, "fr") if evidence else ("", None)
    return {
        "score_0_4": 0.0 if off_task else float(score),
        "demonstrated_band": None if off_task else band,
        "dimensions": dict.fromkeys(dimensions, 0.0) if off_task else dimensions,
        "evidence_fr": evidence or None,
        "evidence_native": native or None,
        "evidence_language": evidence_language if native else None,
        "off_task": off_task,
        "model": model,
        "graded_at": datetime.now(UTC).isoformat(),
    }


class PlacementService:
    """Start, resume, advance and finish one learner's placement."""

    def __init__(self, db: Session, *, llm_service: LLMService | None = None) -> None:
        self.db = db
        self._llm_service = llm_service
        self._llm_unavailable = False

    # -- session lifecycle -------------------------------------------------

    def latest_session(self, user: User) -> PlacementSession | None:
        return (
            self.db.query(PlacementSession)
            .filter(PlacementSession.user_id == user.id)
            .order_by(PlacementSession.created_at.desc())
            .first()
        )

    def active_session(self, user: User) -> PlacementSession | None:
        return (
            self.db.query(PlacementSession)
            .filter(PlacementSession.user_id == user.id, PlacementSession.status == "in_progress")
            .order_by(PlacementSession.created_at.desc())
            .first()
        )

    def start(self, user: User, *, restart: bool = False) -> PlacementSession:
        """Open a placement, or hand back the one already open.

        Idempotent by construction: two taps on «Commencer» produce one session,
        and a learner returning mid-placement resumes rather than restarting.
        ``restart`` is the Réglages re-run and is the only way to open a second
        session while one is in progress.
        """
        existing = self.active_session(user)
        if existing is not None:
            if not restart:
                return existing
            existing.status = "abandoned"
            self.db.add(existing)
        session = PlacementSession(
            user_id=user.id,
            status="in_progress",
            version=PLACEMENT_VERSION,
            current_band=opening_band(user, self._journey_evidence(user)),
            turns=[],
            estimate={},
            estimate_level=None,
            confidence=0.0,
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def _journey_evidence(self, user: User) -> dict[str, Any] | None:
        """WP-75: the learner's days as a prior for where the ladder starts."""
        try:
            return journey_placement_evidence(self.db, user)
        except Exception:  # pragma: no cover - a prior never blocks a placement
            logger.warning("placement: journey evidence unavailable")
            return None

    def skip(self, user: User) -> PlacementSession:
        """The learner declined. Recorded, so the offer is made once."""
        active = self.active_session(user)
        if active is not None:
            active.status = "skipped"
            active.completed_at = datetime.now(UTC)
            self.db.add(active)
            self.db.commit()
            self.db.refresh(active)
            return active
        session = PlacementSession(
            user_id=user.id,
            status="skipped",
            version=PLACEMENT_VERSION,
            current_band=opening_band(user),
            turns=[],
            estimate={},
            completed_at=datetime.now(UTC),
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    # -- the conversation --------------------------------------------------

    @staticmethod
    def current_prompt(session: PlacementSession) -> PlacementPrompt:
        """The question on screen now — never one this session already asked (WP-69)."""
        return prompt_for_session(
            str(session.current_band or ""),
            session_key=str(session.id or ""),
            turns=list(session.turns or []),
        )

    def respond(
        self,
        session: PlacementSession,
        *,
        answer: str,
        turn_index: int,
        language: str | None = None,
    ) -> PlacementSession:
        """Grade one answer and move the ladder.

        ``turn_index`` is the client's statement of *which* turn it is answering.
        Replaying an index that already exists returns the session untouched: the
        stored grading stands and no paid call is made.

        ``language`` is the learner's language (en / de / fr): the grader's
        evidence note is also written in it (the one-language rule).
        """
        turns = list(session.turns or [])
        if session.status != "in_progress":
            return session
        if turn_index < len(turns):
            return session
        prompt = self.current_prompt(session)
        bounded, truncated = bound_learner_answer({"text": answer}, max_chars=ANSWER_MAX_CHARS)
        text = str(bounded.get("text") or "")

        grading = self._grade(
            session=session,
            prompt=prompt,
            answer=text,
            turn_index=len(turns),
            language=language,
        )
        turns.append(
            {
                "index": len(turns),
                "band": prompt.band,
                "prompt_id": prompt.prompt_id,
                "prompt_fr": prompt.prompt_fr,
                "answer": text,
                "answer_truncated": truncated,
                "grading": grading,
                "answered_at": datetime.now(UTC).isoformat(),
            }
        )
        session.turns = turns
        score = float(grading["score_0_4"]) if grading else None
        session.current_band = next_band(prompt.band, score, turns[:-1])

        estimate = estimate_from_turns(turns)
        if not should_continue(turns, estimate):
            self._finish(session, estimate)
        else:
            session.estimate = estimate.as_dict()
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def finish_now(self, session: PlacementSession) -> PlacementSession:
        """End the placement with whatever evidence exists.

        Used by the learner's own «Terminer» and by a resumed session the learner
        does not want to continue. Zero graded turns lands on ``unassessed``,
        which is the honest answer, not a level.
        """
        if session.status == "in_progress":
            self._finish(session, estimate_from_turns(list(session.turns or [])))
            self.db.add(session)
            self.db.commit()
            self.db.refresh(session)
        return session

    def _finish(self, session: PlacementSession, estimate: PlacementEstimate) -> None:
        session.estimate = estimate.as_dict()
        session.status = estimate.status
        session.estimate_level = estimate.level
        session.confidence = float(estimate.confidence)
        session.completed_at = datetime.now(UTC)

    # -- grading -----------------------------------------------------------

    def _get_llm_service(self) -> LLMService | None:
        if self._llm_service is not None:
            return self._llm_service
        if self._llm_unavailable or not settings.ATELIER_CORRECTION_LLM_ENABLED:
            return None
        try:
            self._llm_service = LLMService()
        except Exception as exc:  # pragma: no cover - construction failure
            self._llm_unavailable = True
            logger.info("Placement grader unavailable: {}", exc)
            return None
        return self._llm_service

    def _grade(
        self,
        *,
        session: PlacementSession,
        prompt: PlacementPrompt,
        answer: str,
        turn_index: int,
        language: str | None = None,
    ) -> dict[str, Any] | None:
        """One paid grading call, or ``None``.

        ``None`` is a first-class outcome, not an error path to paper over: it
        means this turn contributes no evidence. Enough of them and the whole
        placement is ``unassessed``, which the learner is told in as many words.
        """
        if not answer.strip():
            return None
        llm = self._get_llm_service()
        if llm is None:
            return None
        payload = {
            "prompt_band": prompt.band,
            "prompt_fr": prompt.prompt_fr,
            "prompt_intent": prompt.intent,
            "learner_response": answer,
            "ladder": list(PLACEMENT_BANDS),
            "evidence_language": normalize_control_language(language) if language else "fr",
        }
        try:
            result = llm.generate_error_detection(
                [{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
                system_prompt=_GRADING_SYSTEM_PROMPT,
                response_format=_GRADING_RESPONSE_FORMAT,
                temperature=0.0,
                max_tokens=settings.ATELIER_CORRECTION_LLM_MAX_TOKENS,
                model=settings.ATELIER_CORRECTION_LLM_MODEL,
                request_timeout=settings.ATELIER_CORRECTION_LLM_TIMEOUT_SECONDS,
                disable_retries=True,
                reasoning_effort=settings.ATELIER_CORRECTION_LLM_REASONING_EFFORT,
            )
        except (LLMProviderError, ValueError, TypeError) as exc:
            logger.warning("Placement grading call failed: {}", exc)
            return None
        record_placement_cost(
            self.db,
            result,
            user_id=session.user_id,
            session_id=session.id,
            turn_index=turn_index,
            band=prompt.band,
        )
        try:
            return normalize_grading(
                json.loads(result.content), model=result.model, language=language
            )
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            logger.warning("Placement grading was unusable: {}", exc)
            return None


# ---------------------------------------------------------------------------
# What the rest of the app reads
# ---------------------------------------------------------------------------


def latest_placement_prior(db: Session, user: User) -> dict[str, Any] | None:
    """The placement result the CEFR service should treat as a prior.

    Returns ``None`` when there is no completed placement, when it produced no
    level, or when its confidence is below :data:`MIN_PRIOR_CONFIDENCE`. Every
    one of those is "we did not measure this learner", and none of them may be
    dressed up as one.
    """
    row = (
        db.query(PlacementSession)
        .filter(
            PlacementSession.user_id == user.id,
            PlacementSession.status == "complete",
            PlacementSession.estimate_level.isnot(None),
        )
        .order_by(PlacementSession.completed_at.desc(), PlacementSession.created_at.desc())
        .first()
    )
    if row is None or not row.estimate_level:
        return None
    if float(row.confidence or 0.0) < MIN_PRIOR_CONFIDENCE:
        return None
    return {
        "level": str(row.estimate_level),
        "confidence": round(float(row.confidence or 0.0), 3),
        "taken_at": row.completed_at.isoformat() if row.completed_at else None,
        "graded_turns": int((row.estimate or {}).get("graded_turns") or 0),
        "version": str(row.version or PLACEMENT_VERSION),
    }


__all__ = [
    "ANSWER_MAX_CHARS",
    "HINT_TRANSLATIONS",
    "hint_by_language",
    "CONFIDENCE_TO_STOP",
    "DIMENSIONS",
    "DIMENSION_LABELS_FR",
    "MAX_TURNS",
    "MIN_PRIOR_CONFIDENCE",
    "MIN_TURNS",
    "PLACEMENT_BANDS",
    "PLACEMENT_EVENT_TYPE",
    "PLACEMENT_VERSION",
    "PROMPT_BANK",
    "PROMPT_VARIANTS",
    "PROMPTS_BY_ID",
    "PlacementEstimate",
    "PlacementPrompt",
    "PlacementService",
    "JOURNEY_EVIDENCE_MET_UNAIDED",
    "JOURNEY_EVIDENCE_WINDOW",
    "PLACEMENT_OFFER_MIN_DAYS",
    "band_index",
    "clamp_band",
    "demonstrated_index",
    "estimate_from_turns",
    "journey_placement_evidence",
    "latest_placement_prior",
    "next_band",
    "normalize_grading",
    "opening_band",
    "placement_offer",
    "prompt_for_session",
    "record_placement_cost",
    "should_continue",
]
