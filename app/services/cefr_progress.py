"""Deterministic CEFR estimate and forecast service.

WP-L7 (2026-09-24): the level is **syllabus coverage plus a checkpoint**. The
level shown is the sub-band the learner is working through; it rises when the
band's épreuve is passed (:mod:`app.services.level_checkpoint`), which the
story engine stages once the band's coverage is met
(:mod:`app.services.level_coverage`: ≥ 85 % of its units held, ≥ 80 % of its
core words known). The absolute counts that used to promote (``CEFR_THRESHOLDS``)
could not be reached past A2.1 with the catalogue; their performance half
survives as :data:`PERFORMANCE_GATES`, which only decides whether a placement or
declaration still stands once in-app evidence exists.

Kept from before: the placement / declaration prior is the floor until
:data:`DECLARED_LEVEL_EVIDENCE_ATTEMPTS`; the down-step smoothing; and nobody's
shown level drops on release day (the level shown before this rule is credited
once, as ``release_floor``). WP-L8's forecast is
:mod:`app.services.level_forecast`.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.db.models.atelier import AtelierAttempt
from app.db.models.cefr import UserCEFRProgressHistory
from app.db.models.daily_journey import DailyJourney
from app.db.models.error import UserError
from app.db.models.grammar import UserGrammarProgress
from app.db.models.graphic_novel import GraphicNovelAttempt
from app.db.models.mission import RealWorldMissionAttempt
from app.db.models.progress import UserVocabularyProgress
from app.db.models.user import User
from app.services.journey_rhythm import rhythm_of

logger = logging.getLogger(__name__)

CEFR_PROGRESS_VERSION = "cefr-progress-v2"
#: The payload version written before the coverage rule (release-day compat).
LEGACY_PROGRESS_VERSIONS = frozenset({"cefr-progress-v1"})
CEFR_LEVELS = ("A1.1", "A1.2", "A2.1", "A2.2", "B1.1", "B1.2", "B2.1", "B2.2")

#: WP-L7: the performance half of the old thresholds. It no longer promotes
#: anyone; once there is enough in-app evidence it decides how much of a
#: placement or declaration still stands (the highest band at or below the prior
#: whose gate the recent work meets).
PERFORMANCE_GATES: dict[str, dict[str, float]] = {
    "A1.1": {"avg_score": 0.0, "max_error_rate": 1.0},
    "A1.2": {"avg_score": 2.6, "max_error_rate": 0.42},
    "A2.1": {"avg_score": 2.8, "max_error_rate": 0.38},
    "A2.2": {"avg_score": 3.0, "max_error_rate": 0.34},
    "B1.1": {"avg_score": 3.1, "max_error_rate": 0.3},
    "B1.2": {"avg_score": 3.2, "max_error_rate": 0.26},
    "B2.1": {"avg_score": 3.3, "max_error_rate": 0.22},
    "B2.2": {"avg_score": 3.4, "max_error_rate": 0.18},
}


@dataclass(frozen=True)
class CEFRSignals:
    mastered_vocabulary: int
    mastered_grammar: int
    recent_error_count: int
    recent_attempt_count: int
    recent_error_rate: float
    recent_average_score: float
    active_days_14: int
    words_mastered_14: int
    concepts_mastered_14: int
    today_words_active: int
    today_concepts_active: int
    today_attempts: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "mastered_vocabulary": self.mastered_vocabulary,
            "mastered_grammar": self.mastered_grammar,
            "recent_error_count": self.recent_error_count,
            "recent_attempt_count": self.recent_attempt_count,
            "recent_error_rate": self.recent_error_rate,
            "recent_average_score": self.recent_average_score,
            "active_days_14": self.active_days_14,
            "words_mastered_14": self.words_mastered_14,
            "concepts_mastered_14": self.concepts_mastered_14,
            "today_words_active": self.today_words_active,
            "today_concepts_active": self.today_concepts_active,
            "today_attempts": self.today_attempts,
        }


def level_index(level: str | None) -> int:
    try:
        return CEFR_LEVELS.index(str(level or "A1.1"))
    except ValueError:
        return 0


def next_cefr_level(level: str | None) -> str | None:
    index = level_index(level)
    return CEFR_LEVELS[index + 1] if index + 1 < len(CEFR_LEVELS) else None


# The coarse level a learner picks at signup, mapped onto the internal half-step
# scale. C1/C2 clamp to the top of the scale this service models.
DECLARED_LEVEL_FLOOR: dict[str, str] = {
    "A1": "A1.1",
    "A2": "A2.1",
    "B1": "B1.1",
    "B2": "B2.1",
    "C1": "B2.2",
    "C2": "B2.2",
    "BEGINNER": "A1.1",
    "INTERMEDIATE": "B1.1",
    "ADVANCED": "B2.1",
}
# How much in-app work it takes before measured evidence is allowed to contradict
# what the learner said about themselves. Below this the app has simply not seen
# enough of them to argue.
DECLARED_LEVEL_EVIDENCE_ATTEMPTS = 40


def declared_level_floor(user: User) -> str | None:
    """The internal level implied by the learner's own statement at signup."""
    raw = str(getattr(user, "proficiency_level", None) or "").strip().upper()
    if not raw:
        return None
    if raw in CEFR_LEVELS:
        return raw
    return DECLARED_LEVEL_FLOOR.get(raw) or DECLARED_LEVEL_FLOOR.get(raw[:2])


def placement_prior(db: Session, user: User) -> dict[str, Any] | None:
    """WP-25 — the placement result, when there is one worth trusting.

    Imported lazily because :mod:`app.services.placement` reads this module's
    ladder; a module-level import would close the cycle. The placement service
    owns the "is this worth trusting" decision (level present, status complete,
    confidence above its floor) and this module never second-guesses it.
    """
    try:
        from app.services.placement import latest_placement_prior
    except Exception:  # pragma: no cover - defensive
        return None
    try:
        return latest_placement_prior(db, user)
    except Exception:  # pragma: no cover - a level must never 500 an endpoint
        return None


class CEFRProgressService:
    """Compute, smooth, persist, and serialize CEFR estimates."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def recompute(
        self,
        user: User,
        *,
        source: str = "recompute",
        persist: bool = True,
        track: bool | None = None,
    ) -> dict[str, Any]:
        """Compute the estimate. ``persist`` stores it and commits; ``track``
        (default: ``persist``) writes the checkpoint rows — the held units of the
        band in force, ``ready``, the release-day and confirmed-prior credits —
        with a flush only, for callers that own their transaction."""

        from app.services import level_checkpoint as checkpoints

        track = persist if track is None else track
        now = datetime.now(UTC)
        signals = self._signals(user=user, now=now)
        placement = placement_prior(self.db, user)
        rows = checkpoints.rows_by_band(self.db, user.id)
        release_floor = self._release_floor(user=user, placement=placement)
        confirmed_prior = self._confirmed_prior(user=user, signals=signals, placement=placement)
        computed_level = self._computed_level(
            rows=rows, release_floor=release_floor, confirmed_prior=confirmed_prior
        )
        measured_level = self._smooth_level(user=user, computed_level=computed_level)
        estimate_level, estimate_source = self._estimate_with_declaration(
            user=user,
            signals=signals,
            measured_level=measured_level,
            placement=placement,
        )
        target_level = self._target_level(user=user, estimate_level=estimate_level)
        if track:
            # Durable credits: the release-day level and a confirmed prior close
            # the band below them for good, whatever later happens to the payload.
            for level, credit_source in (
                (release_floor, checkpoints.SOURCE_RELEASE),
                (confirmed_prior, checkpoints.SOURCE_PRIOR_CONFIRMED),
            ):
                below = _band_below(level)
                if below and (below not in rows or rows[below].status not in checkpoints.CLOSED_STATES):
                    rows[below] = checkpoints.credit_band(self.db, user.id, below, source=credit_source, now=now)
        level_state = self._level_state(
            user=user,
            band=estimate_level,
            rows=rows,
            signals=signals,
            now=now,
            persist=track,
        )
        payload = self._payload(
            user=user,
            signals=signals,
            computed_level=computed_level,
            estimate_level=estimate_level,
            estimate_source=estimate_source,
            target_level=target_level,
            placement=placement,
            level_state=level_state,
            release_floor=release_floor,
            now=now,
        )
        if persist:
            user.cefr_estimate = estimate_level
            user.cefr_estimate_payload = payload
            self.db.add(user)
            self.db.add(
                UserCEFRProgressHistory(
                    user_id=user.id,
                    estimate_level=estimate_level,
                    source=source,
                    signal_snapshot=signals.as_dict(),
                    payload={**payload, "computed_level": computed_level},
                )
            )
            self.db.commit()
            self.db.refresh(user)
        return payload

    def current(self, user: User, *, recompute_if_missing: bool = True) -> dict[str, Any]:
        payload = user.cefr_estimate_payload if isinstance(getattr(user, "cefr_estimate_payload", None), dict) else {}
        if payload and payload.get("version") == CEFR_PROGRESS_VERSION:
            return payload
        if recompute_if_missing:
            return self.recompute(user, source="lazy")
        placement = placement_prior(self.db, user)
        estimate = str(
            getattr(user, "cefr_estimate", None)
            or (placement or {}).get("level")
            or declared_level_floor(user)
            or "A1.1"
        )
        target = self._target_level(user=user, estimate_level=estimate)
        if placement and estimate == placement.get("level"):
            source = "placement"
        elif estimate == declared_level_floor(user):
            source = "declared"
        else:
            source = "measured"
        return {
            "version": CEFR_PROGRESS_VERSION,
            "estimate": estimate,
            "estimate_source": source,
            "declared_level": declared_level_floor(user),
            "placement": placement,
            "computed_estimate": estimate,
            "target": target,
            "next_level": next_cefr_level(estimate),
            "signals": {},
            "thresholds": PERFORMANCE_GATES,
            "forecast": None,
            "coverage": None,
            "checkpoint": None,
            "level_label": estimate,
            "today_delta": {"words_active": 0, "concepts_active": 0, "attempts": 0},
        }

    # ------------------------------------------------------------------
    # Signals
    # ------------------------------------------------------------------

    def _signals(self, *, user: User, now: datetime) -> CEFRSignals:
        start_14 = now - timedelta(days=14)
        start_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        mastered_vocabulary = int(
            self.db.query(func.count(UserVocabularyProgress.id))
            .filter(UserVocabularyProgress.user_id == user.id)
            .filter(
                or_(
                    UserVocabularyProgress.mastered_date.isnot(None),
                    UserVocabularyProgress.proficiency_score >= 90,
                    UserVocabularyProgress.state == "mastered",
                )
            )
            .scalar()
            or 0
        )
        mastered_grammar = int(
            self.db.query(func.count(UserGrammarProgress.id))
            .filter(UserGrammarProgress.user_id == user.id)
            .filter(or_(UserGrammarProgress.state == "gemeistert", UserGrammarProgress.score >= 8))
            .scalar()
            or 0
        )
        recent_error_count = int(
            self.db.query(func.count(UserError.id))
            .filter(UserError.user_id == user.id, UserError.created_at >= start_14)
            .scalar()
            or 0
        )
        recent_scores = self._recent_scores(user=user, start=start_14)
        recent_attempt_count = len(recent_scores)
        recent_average_score = round(sum(recent_scores) / recent_attempt_count, 3) if recent_scores else 0.0
        denominator = max(recent_attempt_count + recent_error_count, 1)
        recent_error_rate = round(recent_error_count / denominator, 3)
        active_days = set(self._active_days(user=user, start=start_14))
        words_mastered_14 = int(
            self.db.query(func.count(UserVocabularyProgress.id))
            .filter(UserVocabularyProgress.user_id == user.id, UserVocabularyProgress.mastered_date >= start_14)
            .scalar()
            or 0
        )
        concepts_mastered_14 = int(
            self.db.query(func.count(UserGrammarProgress.id))
            .filter(UserGrammarProgress.user_id == user.id, UserGrammarProgress.updated_at >= start_14)
            .filter(or_(UserGrammarProgress.state == "gemeistert", UserGrammarProgress.score >= 8))
            .scalar()
            or 0
        )
        today_words_active = int(
            self.db.query(func.count(UserVocabularyProgress.id))
            .filter(UserVocabularyProgress.user_id == user.id, UserVocabularyProgress.updated_at >= start_today)
            .scalar()
            or 0
        )
        today_concepts_active = int(
            self.db.query(func.count(UserGrammarProgress.id))
            .filter(UserGrammarProgress.user_id == user.id, UserGrammarProgress.updated_at >= start_today)
            .scalar()
            or 0
        )
        today_attempts = 0
        for model in (AtelierAttempt, RealWorldMissionAttempt, GraphicNovelAttempt):
            today_attempts += int(
                self.db.query(func.count(model.id))
                .filter(model.user_id == user.id, model.created_at >= start_today)
                .scalar()
                or 0
            )
        return CEFRSignals(
            mastered_vocabulary=mastered_vocabulary,
            mastered_grammar=mastered_grammar,
            recent_error_count=recent_error_count,
            recent_attempt_count=recent_attempt_count,
            recent_error_rate=recent_error_rate,
            recent_average_score=recent_average_score,
            active_days_14=len(active_days),
            words_mastered_14=words_mastered_14,
            concepts_mastered_14=concepts_mastered_14,
            today_words_active=today_words_active,
            today_concepts_active=today_concepts_active,
            today_attempts=today_attempts,
        )

    def _recent_scores(self, *, user: User, start: datetime) -> list[float]:
        scores: list[float] = []
        for model in (AtelierAttempt, RealWorldMissionAttempt, GraphicNovelAttempt):
            rows = (
                self.db.query(model.score_0_4)
                .filter(model.user_id == user.id, model.created_at >= start)
                .all()
            )
            scores.extend(float(row[0] or 0.0) for row in rows)
        return scores

    def _active_days(self, *, user: User, start: datetime) -> list[str]:
        days: set[str] = set()
        for model in (AtelierAttempt, RealWorldMissionAttempt, GraphicNovelAttempt):
            rows = self.db.query(model.created_at).filter(model.user_id == user.id, model.created_at >= start).all()
            for row in rows:
                created = row[0]
                if created:
                    days.add(created.date().isoformat())
        # WP-L8: a finished daily journey is an active day too — it is where
        # most of the learning now happens.
        journeys = (
            self.db.query(DailyJourney.local_date)
            .filter(
                DailyJourney.user_id == user.id,
                DailyJourney.completed_at.isnot(None),
                DailyJourney.completed_at >= start,
            )
            .all()
        )
        days.update(row[0].isoformat() for row in journeys if row[0])
        return sorted(days)

    # ------------------------------------------------------------------
    # The level
    # ------------------------------------------------------------------

    def _release_floor(self, *, user: User, placement: dict[str, Any] | None) -> str | None:
        """The level this learner was shown before the coverage rule, if it must hold.

        WP-L7's release rule: **no learner's shown level drops on release day**.
        A level the old threshold walk *measured* is credited once. A level that
        only stands on a placement or declaration is not: it keeps its existing
        rule (a floor until 40 attempts, then the evidence decides). Carried
        forward in every payload (``release_floor``) and written as a
        ``credited`` checkpoint row on the first persisted recompute.
        """

        payload = user.cefr_estimate_payload if isinstance(getattr(user, "cefr_estimate_payload", None), dict) else {}
        if payload.get("version") == CEFR_PROGRESS_VERSION:
            carried = payload.get("release_floor")
            return str(carried) if carried in CEFR_LEVELS else None
        shown = str(getattr(user, "cefr_estimate", None) or "A1.1")
        if shown not in CEFR_LEVELS or level_index(shown) <= 0:
            return None
        if payload:
            # A payload from before the coverage rule (v1, or older and unversioned).
            return shown if payload.get("estimate_source") == "measured" else None
        # No payload at all: the shown level stands on the column. Above the
        # prior, nothing but a measurement can have put it there.
        prior = (placement or {}).get("level") or declared_level_floor(user)
        if prior is None or level_index(shown) > level_index(str(prior)):
            return shown
        return None

    def _confirmed_prior(
        self,
        *,
        user: User,
        signals: CEFRSignals,
        placement: dict[str, Any] | None,
    ) -> str | None:
        """How much of a placement / declaration the in-app evidence confirms.

        Only once :data:`DECLARED_LEVEL_EVIDENCE_ATTEMPTS` exist: the highest band
        at or below the prior whose :data:`PERFORMANCE_GATES` the recent work
        meets (walking up from A1.1, stopping at the first gate missed). A B1 who
        writes like a B1 is not sent back to prove A1.1's épreuve; one who does
        not falls back, as the old walk made them fall.
        """

        if signals.recent_attempt_count < DECLARED_LEVEL_EVIDENCE_ATTEMPTS:
            return None
        prior = str(placement["level"]) if placement and placement.get("level") else declared_level_floor(user)
        if not prior or prior not in CEFR_LEVELS:
            return None
        confirmed = None
        for level in CEFR_LEVELS[: level_index(prior) + 1]:
            gate = PERFORMANCE_GATES[level]
            if (
                signals.recent_average_score >= gate["avg_score"]
                and signals.recent_error_rate <= gate["max_error_rate"]
            ):
                confirmed = level
            else:
                break
        return confirmed if confirmed and level_index(confirmed) > 0 else None

    @staticmethod
    def _computed_level(
        *,
        rows: dict[str, Any],
        release_floor: str | None,
        confirmed_prior: str | None,
    ) -> str:
        """The band the evidence puts the learner in: one above the highest closed band."""

        from app.services.level_checkpoint import highest_closed_band

        level = "A1.1"
        closed = highest_closed_band(rows)
        if closed:
            level = next_cefr_level(closed) or closed
        for floor in (release_floor, confirmed_prior):
            if floor and level_index(floor) > level_index(level):
                level = floor
        return level

    def _level_state(
        self,
        *,
        user: User,
        band: str,
        rows: dict[str, Any],
        signals: CEFRSignals,
        now: datetime,
        persist: bool,
    ) -> dict[str, Any]:
        """Coverage of the band in force, its checkpoint and the forecast. Never raises."""

        from app.services import level_checkpoint as checkpoints
        from app.services.level_coverage import band_coverage, held_unit_ids
        from app.services.level_forecast import build_forecast, rhythm_priors

        state: dict[str, Any] = {"coverage": None, "checkpoint": None, "forecast": None, "rhythm_priors": None}
        try:
            row = rows.get(band)
            held_now = held_unit_ids(self.db, user, now=now)
            # WP-L7: a unit once held stays counted in its band's coverage — a
            # lapse makes it fragile and it comes back in the reviews; it does
            # not uncover the band.
            held_before = checkpoints.held_ever(row)
            closed = row is not None and row.status in checkpoints.CLOSED_STATES
            coverage = band_coverage(
                self.db,
                user,
                band,
                now=now,
                held=held_now | held_before,
                checkpoint_passed=closed,
            )
            if persist and not closed:
                band_held = held_before | (held_now & set(coverage.unit_ids))
                if band_held != held_before or (coverage.coverage_met and (row is None or row.status == checkpoints.STATE_OPEN)):
                    row = checkpoints.track_band(
                        self.db,
                        user.id,
                        band,
                        held_unit_ids=band_held,
                        coverage_met=coverage.coverage_met,
                        now=now,
                    )
                    rows[band] = row
            view = checkpoints.checkpoint_view(band, row, coverage_met=coverage.coverage_met, now=now)
            state["coverage"] = coverage
            state["checkpoint"] = view
            state["forecast"] = build_forecast(
                self.db,
                user,
                coverage=coverage,
                checkpoint=view,
                active_days=signals.active_days_14,
                target=next_cefr_level(band),
                now=now,
            )
        except Exception:  # pragma: no cover - a level must never 500 an endpoint
            logger.exception("cefr_progress: coverage could not be computed")
        try:
            state["rhythm_priors"] = rhythm_priors(now=now)
        except Exception:  # pragma: no cover - defensive
            logger.exception("cefr_progress: rhythm priors could not be computed")
        return state

    def _estimate_with_declaration(
        self,
        *,
        user: User,
        signals: CEFRSignals,
        measured_level: str,
        placement: dict[str, Any] | None = None,
    ) -> tuple[str, str]:
        """Reconcile what the learner said, what a placement measured, and what
        the app has actually seen.

        A self-declared B1 who has just signed up has covered nothing *in this
        app*, so the evidence alone puts them at A1.1 and the front page would
        tell them they are a beginner. That is not an estimate, it is an
        artefact of an empty database.

        Until there is enough in-app work to argue with (DECLARED_LEVEL_EVIDENCE_
        ATTEMPTS), a **prior** is the floor. After that the measurement wins
        outright, including downwards -- a prior is a starting point, not a
        permanent claim (WP-L7: :meth:`_confirmed_prior` is how much of it the
        evidence keeps).

        WP-25 gives that prior a better source than the learner's own guess. The
        order is placement, then declaration, then nothing: a placement is five
        minutes of graded French, a declaration is a dropdown. The placement
        service already refused to hand over anything it could not stand behind
        (no level, too little confidence), so a prior that arrives here is one
        worth using, and its source is named "placement" so no surface can
        present it as either a self-declaration or a measurement of in-app work.
        """
        prior_level = None
        prior_source = "declared"
        if placement and placement.get("level"):
            prior_level = str(placement["level"])
            prior_source = "placement"
        else:
            prior_level = declared_level_floor(user)
        if not prior_level:
            return measured_level, "measured"
        if signals.recent_attempt_count >= DECLARED_LEVEL_EVIDENCE_ATTEMPTS:
            return measured_level, "measured"
        # ``>=`` and not ``>``: below the evidence threshold a measurement equal
        # to the prior has not *confirmed* anything -- a day-one A1.1 learner
        # with zero attempts is still self-declared, and every surface that
        # says "mesuré" or "vérifié" on that basis lies (found on the
        # 2026-09-11 QA walk).
        if level_index(prior_level) >= level_index(measured_level):
            return prior_level, prior_source
        return measured_level, "measured"

    def _smooth_level(self, *, user: User, computed_level: str) -> str:
        previous = str(getattr(user, "cefr_estimate", None) or "A1.1")
        if level_index(computed_level) >= level_index(previous):
            return computed_level
        recent = (
            self.db.query(UserCEFRProgressHistory)
            .filter(UserCEFRProgressHistory.user_id == user.id)
            .order_by(UserCEFRProgressHistory.created_at.desc())
            .limit(3)
            .all()
        )
        recent_computed = [
            str((row.payload or {}).get("computed_level") or row.estimate_level)
            for row in recent
            if isinstance(row.payload, dict) or row.estimate_level
        ]
        if len(recent_computed) >= 3 and all(level_index(level) < level_index(previous) for level in recent_computed):
            return computed_level
        return previous

    @staticmethod
    def _target_level(*, user: User, estimate_level: str) -> str:
        raw = str(getattr(user, "cefr_target_level", None) or "").strip().upper()
        if raw in CEFR_LEVELS and level_index(raw) > level_index(estimate_level):
            return raw
        return next_cefr_level(estimate_level) or estimate_level

    def _payload(
        self,
        *,
        user: User,
        signals: CEFRSignals,
        computed_level: str,
        estimate_level: str,
        estimate_source: str,
        target_level: str,
        now: datetime,
        level_state: dict[str, Any],
        release_floor: str | None = None,
        placement: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        coverage = level_state.get("coverage")
        coverage_dict = coverage.as_dict() if coverage is not None else None
        return {
            "version": CEFR_PROGRESS_VERSION,
            "estimate": estimate_level,
            # "declared" means the learner told us and the app has not yet seen
            # enough work to agree or disagree; surfaces must not present that
            # as a measurement.
            "estimate_source": estimate_source,
            "declared_level": declared_level_floor(user),
            # WP-25: present whenever a placement stands, whether or not it is
            # the estimate in force -- a surface that says "niveau estime
            # (placement)" needs the date and the confidence behind it.
            "placement": placement,
            "computed_estimate": computed_level,
            "target": target_level,
            "next_level": next_cefr_level(estimate_level),
            # WP-L6: the rhythm's minutes (10 = Régulier when nothing is stored).
            "daily_minutes": int(getattr(user, "daily_goal_minutes", None) or 10),
            "rhythm": rhythm_of(user),
            "signals": signals.as_dict(),
            "thresholds": PERFORMANCE_GATES,
            # WP-L7: «A1.1 · 60 %», the coverage behind it, and the épreuve.
            "level_label": coverage_dict["label"] if coverage_dict else estimate_level,
            "coverage": coverage_dict,
            "checkpoint": level_state.get("checkpoint"),
            "release_floor": release_floor,
            "breakdown": self._breakdown(
                signals=signals,
                coverage=coverage_dict,
                estimate_source=estimate_source,
            ),
            # WP-L8: an estimate — the rhythm's prior before 7 active days,
            # measured after. Never a promise.
            "forecast": level_state.get("forecast"),
            "rhythm_priors": level_state.get("rhythm_priors"),
            "today_delta": {
                "words_active": signals.today_words_active,
                "concepts_active": signals.today_concepts_active,
                "attempts": signals.today_attempts,
            },
            "generated_at": now.isoformat(),
        }

    @staticmethod
    def _breakdown(
        *,
        signals: CEFRSignals,
        coverage: dict[str, Any] | None,
        estimate_source: str = "measured",
    ) -> dict[str, Any]:
        coverage = coverage or {}
        units = coverage.get("units") or {}
        words = coverage.get("words") or {}
        return {
            # These counters only ever count what this app has verified. Against a
            # self-declared level they are not a measure of the learner's French,
            # and a surface must not draw them as if they were.
            # A placement measured the learner's French, but these counters
            # count in-app work, of which a freshly-placed learner has none --
            # so a placement estimate leaves them unverified too, and says why.
            "status": "unverified" if estimate_source in {"declared", "placement"} else "measured",
            "band": coverage.get("band"),
            "percent": coverage.get("percent"),
            # WP-L7: words known / the band's words needed; units held / needed.
            "vocabulary": {
                "current": int(words.get("known") or 0),
                "target": int(words.get("required") or 0),
                "total": int(words.get("total") or 0),
            },
            "grammar": {
                "current": int(units.get("held") or 0),
                "target": int(units.get("required") or 0),
                "total": int(units.get("total") or 0),
            },
            "score": {"current": signals.recent_average_score},
            "error_rate": {"current": signals.recent_error_rate},
        }


def _band_below(level: str | None) -> str | None:
    if not level or level not in CEFR_LEVELS:
        return None
    index = level_index(level)
    return CEFR_LEVELS[index - 1] if index > 0 else None


__all__ = [
    "CEFR_LEVELS",
    "CEFR_PROGRESS_VERSION",
    "DECLARED_LEVEL_EVIDENCE_ATTEMPTS",
    "DECLARED_LEVEL_FLOOR",
    "LEGACY_PROGRESS_VERSIONS",
    "PERFORMANCE_GATES",
    "CEFRProgressService",
    "declared_level_floor",
    "placement_prior",
    "next_cefr_level",
]
