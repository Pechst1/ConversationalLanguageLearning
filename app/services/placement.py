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


#: One prompt per band. Each asks for a *production*, not a recognition, because
#: a placement that can be passed by picking an option measures nothing.
PROMPT_BANK: dict[str, PlacementPrompt] = {
    "A1.1": PlacementPrompt(
        band="A1.1",
        prompt_fr="Bonjour ! Présentez-vous en une ou deux phrases : votre prénom et d’où vous venez.",
        intent="introduce oneself: name and origin, present tense",
        hint_fr="Une ou deux phrases suffisent.",
    ),
    "A1.2": PlacementPrompt(
        band="A1.2",
        prompt_fr="Vous êtes au café. Commandez une boisson et demandez le prix.",
        intent="order a drink and ask the price, polite present tense",
        hint_fr="Deux phrases, à voix haute dans votre tête d’abord.",
    ),
    "A2.1": PlacementPrompt(
        band="A2.1",
        prompt_fr="Racontez ce que vous avez fait le week-end dernier, en trois phrases.",
        intent="narrate a past weekend in three sentences, past tense required",
        hint_fr="Le temps du passé est attendu ici.",
    ),
    "A2.2": PlacementPrompt(
        band="A2.2",
        prompt_fr="Vous arrivez en retard à un rendez-vous. Écrivez le message que vous envoyez pour vous excuser et proposer une autre heure.",
        intent="apologise for lateness and propose a new time, register-appropriate",
        hint_fr="Excusez-vous, puis proposez une heure.",
    ),
    "B1.1": PlacementPrompt(
        band="B1.1",
        prompt_fr="Un ami hésite entre vivre en ville et vivre à la campagne. Donnez votre avis et une raison, en quatre phrases.",
        intent="give an opinion with a reason, connectors expected",
        hint_fr="Une opinion, puis pourquoi.",
    ),
    "B1.2": PlacementPrompt(
        band="B1.2",
        prompt_fr="Racontez une fois où un projet ne s’est pas passé comme prévu : ce que vous aviez espéré, ce qui est arrivé, ce que vous feriez autrement.",
        intent="narrate a failed plan across tenses, including a hypothetical",
        hint_fr="Trois temps différents sont attendus.",
    ),
    "B2.1": PlacementPrompt(
        band="B2.1",
        prompt_fr="On propose d’interdire les voitures dans le centre de votre ville. Défendez une position en tenant compte d’une objection sérieuse.",
        intent="argue a position while conceding a counter-argument, abstract register",
        hint_fr="Nommez l’objection avant d’y répondre.",
    ),
}


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
                "off_task": {"type": "boolean"},
            },
            "required": ["score_0_4", "demonstrated_band", "dimensions", "evidence_fr", "off_task"],
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


def opening_band(user: User | None) -> str:
    """Where the ladder starts.

    One rung **below** what the learner said about themselves, floored at A1.2.
    Starting at the declaration and failing is a demoralising first minute; the
    ladder climbs quickly, so a rung of headroom costs at most one turn.
    """
    declared = declared_level_floor(user) if user is not None else None
    if not declared:
        return "A1.2"
    return clamp_band(max(1, band_index(declared) - 1))


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


def normalize_grading(parsed: Any, *, model: str | None = None) -> dict[str, Any]:
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
    return {
        "score_0_4": 0.0 if off_task else float(score),
        "demonstrated_band": None if off_task else band,
        "dimensions": dict.fromkeys(dimensions, 0.0) if off_task else dimensions,
        "evidence_fr": evidence or None,
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
            current_band=opening_band(user),
            turns=[],
            estimate={},
            estimate_level=None,
            confidence=0.0,
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

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
        return PROMPT_BANK[clamp_band(band_index(session.current_band))]

    def respond(self, session: PlacementSession, *, answer: str, turn_index: int) -> PlacementSession:
        """Grade one answer and move the ladder.

        ``turn_index`` is the client's statement of *which* turn it is answering.
        Replaying an index that already exists returns the session untouched: the
        stored grading stands and no paid call is made.
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
        )
        turns.append(
            {
                "index": len(turns),
                "band": prompt.band,
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
            return normalize_grading(json.loads(result.content), model=result.model)
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
    "PlacementEstimate",
    "PlacementPrompt",
    "PlacementService",
    "band_index",
    "clamp_band",
    "demonstrated_index",
    "estimate_from_turns",
    "latest_placement_prior",
    "next_band",
    "normalize_grading",
    "opening_band",
    "record_placement_cost",
    "should_continue",
]
