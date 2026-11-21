"""S1 «one day brief» — the day's rule and what hangs on it, decided once, stored.

Live walks for a week (#576, #443; 12 and 16 Nov) met the same thing: the rule
card taught one rule, La Forge drilled another as «today's rule», a test-out
offered a third. Six places each pick the day's rule from live state at their
own moment. The brief is written once, when the day is planned, inside the
existing ``plan_selection`` JSON (``plan_selection["brief"]``, no migration),
and never rebuilt for a journey that already exists.

Stage S1.1 (this module) is a *shadow*: the brief is built and stored behind
``DAY_BRIEF_ENABLED``; nothing reads it for the learner yet. Every surface keeps
its own chooser, and at each chooser :func:`shadow` logs one structured
``day_brief_disagreement`` warning when its answer differs from the brief's.
Those counts are the evidence for S1.2, which switches the readers.

Who will read which field:

* ``rule`` — S1.2: Home, the rule card, the day's Forge step and the Forge start.
* ``review_concept_ids`` — S1.2: the page review (WP-129).
* ``forge_anchor`` / ``forge_review_ids`` — S1.2: Forge step, Forge start (#169).
* ``test_out_concept_id`` — S1.2: the test-out offer at the séance recap.
* ``scene_grammar`` — S1.3: the scene writer's pick, the example line, drill relations.
* ``words`` — S1.3/S1.5: a pointer at the day's word plan (``day_words``), never a
  second list of new words.
* the whole brief — S1.5: Courrier and Journal.
"""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

#: ``plan_selection`` key the brief is stored under.
BRIEF_KEY = "brief"
BRIEF_VERSION = 1
#: The one log event a shadow disagreement is written as.
SHADOW_EVENT = "day_brief_disagreement"

ROLE_INTRODUCE = "introduce"
ROLE_REVIEW = "review"
ROLE_NONE = "none"

#: Where the rule came from. A brief built at planning reads the plan's own
#: RULE step; an older journey (no stored brief) falls back like
#: ``daily_journey._planned_rule_id``.
SOURCE_PLAN_RULE = "plan_rule_step"
SOURCE_PLAN_REVIEW = "plan_review_step"
SOURCE_NONE = "none"
SOURCE_LEGACY_INTRODUCTION = "legacy_introduction"
SOURCE_LEGACY_RULE_STEP = "legacy_rule_step"


@dataclass(frozen=True)
class BriefRule:
    """The day's one rule: ``concept_id`` / ``external_id`` and why (``role``)."""

    role: str = ROLE_NONE
    source: str = SOURCE_NONE
    concept_id: int | None = None
    external_id: str | None = None


@dataclass(frozen=True)
class SceneGrammar:
    """What the served page says about its own grammar pick (``story_context["grammar"]``).

    ``present`` is False when the page carried no plan (a shared page, an authored
    first day, the flag off): then nothing is known, not «no rule».
    """

    present: bool = False
    introduce: int | None = None
    woven: bool | None = None
    weave: tuple[int, ...] = ()


@dataclass(frozen=True)
class DayBrief:
    version: int = BRIEF_VERSION
    local_date: str | None = None
    rule: BriefRule = field(default_factory=BriefRule)
    #: Concepts the page reviews (a RULE step marked ``review``), at most one today.
    review_concept_ids: tuple[int, ...] = ()
    #: The rule «Forge today's rule» opens on: the day's rule, else the picker's
    #: answer when the day was planned (a day with no rule card).
    forge_anchor: int | None = None
    #: At most one taught, due rule beside it on the day's Forge (#169).
    forge_review_ids: tuple[int, ...] = ()
    #: The one rule a test-out may be offered on today, as it stood at planning.
    test_out_concept_id: int | None = None
    scene_grammar: SceneGrammar = field(default_factory=SceneGrammar)
    #: Pointer at the day's word plan: the drill batch of ``batch_day``
    #: (``VocabularyDrillBatch.plan``) and the journey's reservation key.
    words: dict[str, Any] = field(default_factory=dict)
    decided_at: str | None = None
    #: True for a brief read back from an older journey's plan (no stored brief).
    legacy: bool = False

    # -- the values the shadow comparisons read ------------------------------

    @property
    def rule_concept_id(self) -> int | None:
        return self.rule.concept_id

    @property
    def introduced_concept_id(self) -> int | None:
        return self.rule.concept_id if self.rule.role == ROLE_INTRODUCE else None

    # -- JSON ----------------------------------------------------------------

    def to_json(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("legacy", None)
        data["review_concept_ids"] = list(self.review_concept_ids)
        data["forge_review_ids"] = list(self.forge_review_ids)
        data["scene_grammar"]["weave"] = list(self.scene_grammar.weave)
        return data

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> DayBrief:
        rule = data.get("rule") if isinstance(data.get("rule"), dict) else {}
        scene = data.get("scene_grammar") if isinstance(data.get("scene_grammar"), dict) else {}
        return cls(
            version=int(data.get("version") or BRIEF_VERSION),
            local_date=data.get("local_date"),
            rule=BriefRule(
                role=str(rule.get("role") or ROLE_NONE),
                source=str(rule.get("source") or SOURCE_NONE),
                concept_id=_positive_id(rule.get("concept_id")),
                external_id=rule.get("external_id") or None,
            ),
            review_concept_ids=_ids(data.get("review_concept_ids")),
            forge_anchor=_positive_id(data.get("forge_anchor")),
            forge_review_ids=_ids(data.get("forge_review_ids")),
            test_out_concept_id=_positive_id(data.get("test_out_concept_id")),
            scene_grammar=SceneGrammar(
                present=bool(scene.get("present")),
                introduce=_positive_id(scene.get("introduce")),
                woven=scene.get("woven") if isinstance(scene.get("woven"), bool) else None,
                weave=_ids(scene.get("weave")),
            ),
            words=dict(data.get("words") or {}),
            decided_at=data.get("decided_at"),
        )


def enabled() -> bool:
    return bool(getattr(settings, "DAY_BRIEF_ENABLED", False))


def _positive_id(value: Any) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _ids(values: Any) -> tuple[int, ...]:
    out: list[int] = []
    for value in values or ():
        number = _positive_id(value)
        if number is not None and number not in out:
            out.append(number)
    return tuple(out)


def _iso(value: datetime) -> str:
    return (value if value.tzinfo else value.replace(tzinfo=UTC)).isoformat()


# ---------------------------------------------------------------------------
# Building (once, where the day is planned)
# ---------------------------------------------------------------------------


def _rule_steps(steps: Any) -> list[dict[str, Any]]:
    from app.services.journey_contracts import StepKind

    return [
        dict(getattr(step, "public_prompt", None) or {})
        for step in steps or []
        if str(getattr(step, "kind", "")) == str(StepKind.RULE)
    ]


def rule_from_steps(steps: Any) -> tuple[BriefRule, tuple[int, ...]]:
    """The day's rule and the page's reviews, read from the planned steps.

    A RULE step that is not marked ``review`` introduces its unit; one marked
    ``review`` (WP-129) shows a known unit. An introducing card wins the day's
    rule; a review card is the day's rule only when nothing is introduced.
    """

    prompts = _rule_steps(steps)
    reviews = _ids(prompt.get("concept_id") for prompt in prompts if prompt.get("review"))
    for prompt in prompts:
        if not prompt.get("review") and (concept_id := _positive_id(prompt.get("concept_id"))):
            return BriefRule(role=ROLE_INTRODUCE, source=SOURCE_PLAN_RULE, concept_id=concept_id), reviews
    if reviews:
        return BriefRule(role=ROLE_REVIEW, source=SOURCE_PLAN_REVIEW, concept_id=reviews[0]), reviews
    return BriefRule(), reviews


def scene_grammar_of(scenario: Any) -> SceneGrammar:
    """The served page's grammar pick (``living_story.grammar_plan_for`` as stored)."""

    context = getattr(scenario, "story_context", None) or {}
    if not isinstance(context, dict):
        return SceneGrammar()
    outcome = context.get("grammar") if isinstance(context.get("grammar"), dict) else None
    source = context.get("source") if isinstance(context.get("source"), dict) else {}
    provenance = (outcome or {}).get("plan") or source.get("grammar_plan")
    if not isinstance(provenance, dict):
        return SceneGrammar()
    focus = (outcome or {}).get("focus") if isinstance((outcome or {}).get("focus"), dict) else {}
    woven = focus.get("woven")
    return SceneGrammar(
        present=True,
        introduce=_positive_id(provenance.get("introduce")),
        woven=woven if isinstance(woven, bool) else None,
        weave=_ids(provenance.get("weave")),
    )


def build(
    db: Any,
    user: Any,
    *,
    journey: Any,
    plan: Any,
    scenario: Any,
    story_units: list[str] | None = None,
    now: datetime | None = None,
) -> DayBrief:
    """The day's brief from the plan just persisted. Read-only; best effort per part:
    a part that cannot be read is left empty, never a reason to lose the day."""

    from app.db.models.grammar import GrammarConcept
    from app.db.savepoint import run_best_effort
    from app.services.vocabulary_pace import JOURNEY_NEW_WORDS_KEY

    now = now or datetime.now(UTC)
    rule, reviews = rule_from_steps(getattr(plan, "steps", None))
    if rule.concept_id is not None:
        concept = run_best_effort(
            db, "day_brief: rule concept", lambda: db.get(GrammarConcept, rule.concept_id), default=None, log=logger
        )
        if concept is not None:
            rule = BriefRule(
                role=rule.role,
                source=rule.source,
                concept_id=rule.concept_id,
                external_id=str(getattr(concept, "external_id", "") or "") or None,
            )

    def forge() -> tuple[int | None, tuple[int, ...]]:
        from app.services import forge_picker

        preferred = rule.concept_id or forge_picker.story_review_concept_id(db, user, list(story_units or []))
        picked = forge_picker.forge_plan(db, user, now, preferred_concept_id=preferred, origin="journey")
        anchor = picked.anchor
        due = tuple(unit.concept_id for unit in picked.units if unit.role == forge_picker.ROLE_DUE)
        return (anchor.concept_id if anchor is not None else None), due

    forge_anchor, forge_reviews = run_best_effort(
        db, "day_brief: forge anchor", forge, default=(None, ()), log=logger
    )

    def test_out() -> int | None:
        from app.services.forge import test_out_candidate

        concepts = [cid for cid in (forge_anchor, *forge_reviews) if cid is not None]
        offer = test_out_candidate(db, user=user, concept_ids=concepts, now=now) if concepts else None
        return _positive_id((offer or {}).get("concept_id"))

    test_out_id = run_best_effort(db, "day_brief: test-out", test_out, default=None, log=logger)
    local_date = getattr(journey, "local_date", None)
    return DayBrief(
        local_date=local_date.isoformat() if local_date is not None else None,
        rule=rule,
        review_concept_ids=reviews,
        forge_anchor=_positive_id(forge_anchor),
        forge_review_ids=_ids(forge_reviews),
        test_out_concept_id=test_out_id,
        scene_grammar=scene_grammar_of(scenario),
        words={
            "batch_day": local_date.isoformat() if local_date is not None else None,
            "reservation_key": JOURNEY_NEW_WORDS_KEY,
        },
        decided_at=_iso(now),
    )


def store(journey: Any, brief: DayBrief) -> None:
    """Write the brief into ``plan_selection``. Only where the day is planned."""

    journey.plan_selection = {**dict(getattr(journey, "plan_selection", None) or {}), BRIEF_KEY: brief.to_json()}


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------


def stored(journey: Any) -> DayBrief | None:
    """The brief stored with this journey's plan, or ``None`` (older day, flag off)."""

    selection = getattr(journey, "plan_selection", None) if journey is not None else None
    data = selection.get(BRIEF_KEY) if isinstance(selection, dict) else None
    if not isinstance(data, dict):
        return None
    try:
        return DayBrief.from_json(data)
    except Exception:  # pragma: no cover - a malformed row reads as an older day
        logger.warning("day_brief: stored brief unreadable", exc_info=True)
        return None


def for_day(journey: Any) -> DayBrief | None:
    """The day's brief: the stored one, or for a day planned before the brief, the
    same fallback ``daily_journey._planned_rule_id`` uses (the stored introduction,
    then the RULE step). Never builds or stores anything."""

    if journey is None:
        return None
    brief = stored(journey)
    if brief is not None:
        return brief
    local_date = getattr(journey, "local_date", None)
    selection = getattr(journey, "plan_selection", None)
    planned = selection.get("introduction") if isinstance(selection, dict) else None
    rule = BriefRule()
    if isinstance(planned, dict) and (concept_id := _positive_id(planned.get("concept_id"))):
        rule = BriefRule(role=ROLE_INTRODUCE, source=SOURCE_LEGACY_INTRODUCTION, concept_id=concept_id)
    reviews: tuple[int, ...] = ()
    prompts = _rule_steps(getattr(journey, "steps", None))
    reviews = _ids(prompt.get("concept_id") for prompt in prompts if prompt.get("review"))
    if rule.concept_id is None:
        for prompt in prompts:
            if concept_id := _positive_id(prompt.get("concept_id")):
                role = ROLE_REVIEW if prompt.get("review") else ROLE_INTRODUCE
                rule = BriefRule(role=role, source=SOURCE_LEGACY_RULE_STEP, concept_id=concept_id)
                break
    return DayBrief(
        local_date=local_date.isoformat() if local_date is not None else None,
        rule=rule,
        review_concept_ids=reviews,
        forge_anchor=rule.concept_id,
        legacy=True,
    )


# ---------------------------------------------------------------------------
# Shadow comparison (S1.1): log where a chooser and the brief disagree
# ---------------------------------------------------------------------------


def _normal(value: Any) -> Any:
    if isinstance(value, (list, tuple, set, frozenset)):
        return sorted(_ids(value))
    if isinstance(value, dict):
        return _positive_id(value.get("concept_id"))
    return _positive_id(value)


def shadow(journey: Any, chooser: str, value: Any, *, field: str) -> bool:
    """Compare a chooser's answer with the stored brief's ``field``; log a
    :data:`SHADOW_EVENT` warning on disagreement. Returns True when they disagree.

    A no-op with the flag off or for a journey with no stored brief (an older
    day's fallback is by construction what the choosers read today). Never raises.
    """

    if not enabled() or journey is None:
        return False
    try:
        brief = stored(journey)
        if brief is None:
            return False
        ours = _normal(getattr(brief, field))
        # A list field (the page's reviews) reads a chooser's «none» as an empty list.
        theirs = _normal([] if value is None and isinstance(ours, list) else value)
        if ours == theirs:
            return False
        journey_id = str(getattr(journey, "id", "") or "")
        logger.warning(
            "%s chooser=%s field=%s chooser_value=%s brief_value=%s journey_id=%s",
            SHADOW_EVENT,
            chooser,
            field,
            theirs,
            ours,
            journey_id,
            extra={
                "event_name": SHADOW_EVENT,
                "chooser": chooser,
                "brief_field": field,
                "chooser_value": theirs,
                "brief_value": ours,
                "journey_id": journey_id,
            },
        )
        return True
    except Exception:  # pragma: no cover - a shadow never touches the learner's day
        logger.debug("day_brief: shadow comparison failed", exc_info=True)
        return False


def shadow_today(db: Any, user: Any, chooser: str, value: Any, *, field: str, now: datetime | None = None) -> bool:
    """:func:`shadow` against the learner's journey of today (for choosers that
    know the user, not the journey: the Forge start, the test-out offer)."""

    if not enabled() or db is None or user is None:
        return False
    try:
        from app.services.vocabulary_pace import todays_journey

        journey = todays_journey(db, user, now=now)
    except Exception:  # pragma: no cover - a shadow never touches the learner's day
        logger.debug("day_brief: today's journey unreadable", exc_info=True)
        return False
    return shadow(journey, chooser, value, field=field)


def shadow_planning(
    journey: Any,
    *,
    introduction: Any,
    page_review: Any,
    forge: Any,
) -> None:
    """The choosers that ran while the day was planned, against the brief just stored."""

    brief = stored(journey)
    if brief is None:
        return
    shadow(journey, "daily_journey._introduction_for_today", introduction, field="introduced_concept_id")
    shadow(
        journey,
        "daily_journey._page_review_for_today",
        [item.get("concept_id") for item in page_review or [] if isinstance(item, dict)],
        field="review_concept_ids",
    )
    if isinstance(forge, dict):
        # Only a folded day plans a Forge step; otherwise the chooser did not run.
        shadow(journey, "daily_journey._forge_for_today", forge.get("concept_id"), field="forge_anchor")
    if brief.scene_grammar.present:
        shadow(
            journey,
            "living_story.grammar_plan_for",
            brief.scene_grammar.introduce,
            field="introduced_concept_id",
        )


__all__ = [
    "BRIEF_KEY",
    "BRIEF_VERSION",
    "ROLE_INTRODUCE",
    "ROLE_NONE",
    "ROLE_REVIEW",
    "SHADOW_EVENT",
    "BriefRule",
    "DayBrief",
    "SceneGrammar",
    "build",
    "enabled",
    "for_day",
    "rule_from_steps",
    "scene_grammar_of",
    "shadow",
    "shadow_planning",
    "shadow_today",
    "store",
    "stored",
]
