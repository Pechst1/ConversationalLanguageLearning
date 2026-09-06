"""WP-04 — the five-minute planner and integrated review selection.

One journey is a *plan*, not a drill quota. The legacy Atelier ladder in
:mod:`app.services.atelier` owes a learner three recognition modes of three
items, three transforms and three output rounds — fifteen obligations for every
selected concept. Nothing in this module reproduces that shape: a plan is three
to five explicit steps, and a hundred due words still produce at most two recall
opportunities.

The planner is deliberately narrow:

* It **selects** at most two relevant existing due/fragile targets plus at most
  one new anchor from the candidates WP-05 already ranked. It never calls a
  scheduler, never moves a due date, and never marks anything reviewed — an
  omitted candidate stays exactly as due as it was.
* It **shapes** one recall task per selected target from the scene's own
  authored affordances (:mod:`app.services.journey_content`). No second content
  source, no model call.
* It **estimates** every step from a bounded, documented cost model covering
  reading, answering, normal feedback, audio playback and one repair allowance,
  and it fits the mandatory plan inside the budget before returning.

``plan_journey`` is pure: it takes no ``Session``, performs no I/O beyond
reading WP-03's authored scenario data, and returns a byte-identical
:class:`~app.services.journey_contracts.PlannedJourney` for identical inputs.
Every identifier it mints is derived by hash from stable content, so a refresh
never re-randomises an option order or a tile layout.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from typing import Any, Literal

from app.services.journey_content import render_authored_text, scenario_target_affordances
from app.services.journey_contracts import (
    DEFAULT_BUDGET_SECONDS,
    MAX_PLANNED_STEPS,
    MAX_RECALL_STEPS,
    MAX_RESPOND_TURNS,
    ControlLanguage,
    HelpKind,
    InputMode,
    LearningCandidate,
    PlannedJourney,
    PlannedStep,
    RecallTask,
    ResponseTask,
    ScenarioBrief,
    StepKind,
    StepStatus,
    TargetRef,
    normalize_answer_text,
)

PLANNER_VERSION = "journey-planner-v1"

# --------------------------------------------------------------------------
# Selection policy (CONTRACTS §9)
# --------------------------------------------------------------------------

#: At most two *existing* due/fragile targets may become today's obligation.
MAX_DUE_TARGETS = 2
#: Plus at most one brand-new anchor, which is an offer and never an obligation.
MAX_NEW_TARGETS = 1
MAX_SELECTED_TARGETS = MAX_DUE_TARGETS + MAX_NEW_TARGETS

#: Below this scene fit a target may still be *rehearsed* (it is genuinely due),
#: but it is never attached to the response step as an elicited target. Without
#: an explicit elicitation obligation an omitted word must not become a lapse
#: (CONTRACTS §7), so an unrelated urgent word never rides along on the reply.
ELICITATION_FIT_THRESHOLD = 0.5

#: ``LearningCandidate.metadata`` keys that mean "the learner already produced
#: this independently, a rehearsal would be redundant". Absent or falsy is the
#: honest default: nothing is skipped by accident.
DEMONSTRATED_FLAG_KEYS: tuple[str, ...] = (
    "demonstrated_independently",
    "already_demonstrated",
)
#: ``metadata["last_evidence_kind"]`` values that count as already demonstrated.
DEMONSTRATED_EVIDENCE_KINDS = frozenset({"produced_independent", "used_again_later"})

# --------------------------------------------------------------------------
# Estimate model (CONTRACTS §9)
# --------------------------------------------------------------------------

#: Reading pace for a mixed French/native prompt, in seconds per whitespace
#: token. 0.45 s/token ≈ 133 words per minute — a beginner reading French with a
#: native gloss, not a native skimming their own language.
DEFAULT_SECONDS_PER_TOKEN = 0.45
#: A measured pace outside this band is a measurement artefact, not a learner.
SECONDS_PER_TOKEN_BOUNDS = (0.30, 0.70)
#: A measured per-step multiplier is clamped here too. Beyond 1.35 the honest
#: answer is a shorter plan, not a longer estimate.
STEP_MULTIPLIER_BOUNDS = (0.80, 1.35)
#: How many measured journeys a pace profile needs before it is trusted at all.
#: Under this threshold the bounded defaults are used verbatim.
MIN_PACE_OBSERVATIONS = 5

#: Orientation, looking at the art, deciding to begin.
SCENE_BASE_SECONDS = 12
#: Reading the ending, the summary, and closing the day.
RESOLUTION_BASE_SECONDS = 45
#: Answering cost per recall renderer.
RECALL_ANSWER_SECONDS: dict[str, int] = {"choice": 18, "tiles": 26, "short_answer": 30}
#: Reading the normal (non-repair) feedback on a recall step.
RECALL_FEEDBACK_SECONDS = 10
#: Composing one learner turn in the response step.
RESPOND_TURN_SECONDS = 38
#: Reading the character's reply and the normal feedback.
RESPOND_FEEDBACK_SECONDS = 10
#: The single allowed repair (CONTRACTS §9: "repair at most once").
REPAIR_ALLOWANCE_SECONDS = 20
#: Listening to a character line when audio actually exists.
AUDIO_PLAYBACK_SECONDS_PER_TOKEN = 0.55

RecallTaskType = Literal["choice", "tiles", "short_answer"]

# --------------------------------------------------------------------------
# Control-language templates. Every learner-facing string is resolved into the
# brief's control language; French content keeps its own ``_fr`` fields.
# --------------------------------------------------------------------------

_CHOICE_INSTRUCTION: dict[str, str] = {
    "en": 'Which French phrase means "{native}"?',
    "de": 'Welcher französische Ausdruck bedeutet „{native}“?',
    "fr": "Quelle expression française veut dire « {native} » ?",
}
_TILES_INSTRUCTION_WITH_GLOSS: dict[str, str] = {
    "en": 'Put the words in order to say "{native}".',
    "de": 'Bring die Wörter in die richtige Reihenfolge für „{native}“.',
    "fr": "Remets les mots dans l'ordre pour dire « {native} ».",
}
_TILES_INSTRUCTION: dict[str, str] = {
    "en": "Put the words in the right order.",
    "de": "Bring die Wörter in die richtige Reihenfolge.",
    "fr": "Remets les mots dans le bon ordre.",
}
_SHORT_ANSWER_INSTRUCTION: dict[str, str] = {
    "en": 'How do you say "{native}" in French?',
    "de": 'Wie sagt man „{native}“ auf Französisch?',
    "fr": "Comment dit-on « {native} » en français ?",
}
_HINT_TEMPLATE: dict[str, str] = {
    "en": 'It is {count} word(s) long and starts with "{initial}".',
    "de": 'Es ist {count} Wort/Wörter lang und beginnt mit „{initial}“.',
    "fr": "C'est {count} mot(s) et ça commence par « {initial} ».",
}


def _localized(table: dict[str, str], control_language: ControlLanguage) -> str:
    return table.get(str(control_language), table["en"])


# --------------------------------------------------------------------------
# Public value objects
# --------------------------------------------------------------------------


class PlanUnavailable(RuntimeError):
    """The brief cannot support a real five-minute ending.

    Raised instead of emitting a placeholder plan. WP-02 maps this onto the
    frozen ``generation_unavailable`` error code and offers an honest retry; it
    must never be turned into a scene with no objective or no ending.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class PacingProfile:
    """Measured active pace, or nothing yet.

    ``observations`` is the number of *completed, measured* journeys behind the
    numbers. Below :data:`MIN_PACE_OBSERVATIONS` the profile is ignored
    entirely and the bounded defaults are used: two noisy samples must not be
    allowed to shrink a plan into a false promise or inflate it into a
    ten-minute day. Above the threshold both values are clamped, so provider
    waiting or a backgrounded app cannot leak into the learning estimate.
    """

    seconds_per_token: float = DEFAULT_SECONDS_PER_TOKEN
    step_multiplier: float = 1.0
    observations: int = 0

    @property
    def is_trusted(self) -> bool:
        return self.observations >= MIN_PACE_OBSERVATIONS

    def effective_seconds_per_token(self) -> float:
        if not self.is_trusted:
            return DEFAULT_SECONDS_PER_TOKEN
        low, high = SECONDS_PER_TOKEN_BOUNDS
        return min(max(float(self.seconds_per_token), low), high)

    def effective_step_multiplier(self) -> float:
        if not self.is_trusted:
            return 1.0
        low, high = STEP_MULTIPLIER_BOUNDS
        return min(max(float(self.step_multiplier), low), high)


@dataclass(frozen=True, slots=True)
class SelectedTarget:
    """One candidate the planner kept, with the scene fit it was kept for."""

    candidate: LearningCandidate
    fit: float
    demonstrated: bool

    @property
    def target(self) -> TargetRef:
        return self.candidate.target

    @property
    def is_elicitable(self) -> bool:
        """May this target be *required* in the spoken/written reply?"""

        return self.fit >= ELICITATION_FIT_THRESHOLD


@dataclass(frozen=True, slots=True)
class TargetSelection:
    """The outcome of selection, before any step is shaped."""

    selected: list[SelectedTarget]
    omitted: list[LearningCandidate]
    omission_reasons: dict[str, str]


# --------------------------------------------------------------------------
# Small deterministic helpers
# --------------------------------------------------------------------------


#: Unit separator; keeps hashed identifiers injection-proof across parts.
_SEPARATOR = chr(31)


def _digest(*parts: str) -> str:
    return hashlib.sha256(_SEPARATOR.join(parts).encode("utf-8")).hexdigest()


def target_identity(target: TargetRef) -> str:
    """The planner's candidate/target identifier: ``"{kind}:{id}"``.

    A vocabulary row and a grammar concept can share a primary key, so the bare
    record id is not unique across kinds. ``selected_target_ids`` and
    ``omitted_candidate_ids`` both use this composite form.
    """

    return f"{target.kind}:{target.id}"


def _tokens(*texts: str | None) -> int:
    return sum(len((text or "").split()) for text in texts)


def _fold(value: str | None) -> str:
    return normalize_answer_text(value).casefold()


def candidate_is_demonstrated(candidate: LearningCandidate) -> bool:
    """Has the learner already produced this target independently?

    Read from ``LearningCandidate.metadata`` so the planner stays pure. The
    honest default is ``False``: a target is only treated as demonstrated when
    the evidence layer explicitly says so, never inferred from a due date.
    """

    metadata = candidate.metadata or {}
    for key in DEMONSTRATED_FLAG_KEYS:
        if bool(metadata.get(key)):
            return True
    return str(metadata.get("last_evidence_kind") or "") in DEMONSTRATED_EVIDENCE_KINDS


def scenario_fit(target: TargetRef, affordances: list[str], scenario: ScenarioBrief) -> float:
    """How well this target suits the scene, in ``[0, 1]``.

    An exact match against what the scene affords is 1.0, a containment match
    0.75, and a partial token overlap proportional. A target the response task
    already declares is 1.0 by definition, so a thin authored affordance list
    cannot demote something the scene demonstrably needs.
    """

    for declared in scenario.response_task.targets:
        if declared.kind == target.kind and declared.id == target.id:
            return 1.0
    label = _fold(target.label_fr)
    if not label:
        return 0.0
    folded = [_fold(item) for item in affordances if item]
    best = 0.0
    label_tokens = set(label.split())
    for phrase in folded:
        if not phrase:
            continue
        if phrase == label:
            return 1.0
        if label in phrase or phrase in label:
            best = max(best, 0.75)
            continue
        if label_tokens:
            overlap = len(label_tokens & set(phrase.split())) / len(label_tokens)
            best = max(best, round(overlap * 0.8, 4))
    return best


def supported_input_modes(
    scenario: ScenarioBrief, *, input_mode: InputMode = InputMode.TEXT
) -> list[str]:
    """The modes the response step offers.

    Text is always available (CONTRACTS §10): a denied microphone, a failed
    transcription or a text-only device must never block the day's objective.
    Voice is added only when the journey was actually created for voice.
    """

    if input_mode is InputMode.VOICE:
        return [str(InputMode.TEXT), str(InputMode.VOICE)]
    return [str(InputMode.TEXT)]


def default_outcome_key(scenario: ScenarioBrief) -> str | None:
    """The ending the plan shows before the learner has spoken.

    The first *authored* allowed outcome that actually has a resolution line.
    WP-06 replaces it with the outcome the learner earned; until then the plan
    shows a real, authored ending rather than an invented one.
    """

    for key in scenario.response_task.allowed_outcomes:
        if scenario.resolution_lines.get(key):
            return key
    for key, line in scenario.resolution_lines.items():
        if line:
            return key
    return None


# --------------------------------------------------------------------------
# 1. Selection
# --------------------------------------------------------------------------


def select_plan_targets(
    scenario: ScenarioBrief, candidates: list[LearningCandidate]
) -> TargetSelection:
    """At most two existing due/fragile targets plus at most one new anchor.

    Ranking is scene fit first, then the urgency WP-05 already computed, then
    how long the item has been due, then a stable identity tiebreak. A hundred
    due words therefore yield two obligations, not a hundred — and the other
    ninety-eight are reported in ``omitted``, still due, untouched.
    """

    affordances = _affordances_for(scenario)
    ranked: list[tuple[tuple[float, float, float, str], SelectedTarget]] = []
    seen: set[str] = set()
    duplicates: list[LearningCandidate] = []
    for candidate in candidates:
        identity = target_identity(candidate.target)
        if identity in seen:
            duplicates.append(candidate)
            continue
        seen.add(identity)
        fit = max(
            scenario_fit(candidate.target, affordances, scenario),
            round(min(max(float(candidate.relevance or 0.0), 0.0), 1.0), 4),
        )
        entry = SelectedTarget(
            candidate=candidate,
            fit=fit,
            demonstrated=candidate_is_demonstrated(candidate),
        )
        ranked.append(
            (
                (
                    -entry.fit,
                    -float(candidate.priority_score or 0.0),
                    -float(candidate.due_since_days or 0),
                    identity,
                ),
                entry,
            )
        )
    ranked.sort(key=lambda row: row[0])

    selected: list[SelectedTarget] = []
    omitted: list[LearningCandidate] = []
    reasons: dict[str, str] = {}
    due_used = 0
    new_used = 0
    for _key, entry in ranked:
        identity = target_identity(entry.target)
        if entry.candidate.is_new:
            if new_used >= MAX_NEW_TARGETS:
                omitted.append(entry.candidate)
                reasons[identity] = "new_anchor_cap_reached"
                continue
            new_used += 1
        else:
            if due_used >= MAX_DUE_TARGETS:
                omitted.append(entry.candidate)
                reasons[identity] = "due_target_cap_reached"
                continue
            due_used += 1
        selected.append(entry)
    for candidate in duplicates:
        omitted.append(candidate)
        reasons.setdefault(target_identity(candidate.target), "duplicate_candidate")
    return TargetSelection(selected=selected, omitted=omitted, omission_reasons=reasons)


def _affordances_for(scenario: ScenarioBrief) -> list[str]:
    try:
        return scenario_target_affordances(
            scenario.scenario_key,
            level_band=scenario.level_band,
            content_version=scenario.content_version,
        )
    except (OSError, ValueError, KeyError, TypeError):
        # A scenario family with no authored data simply affords nothing; that
        # is a thinner recall task, not a planner failure.
        return []


# --------------------------------------------------------------------------
# 2. Recall task shaping
# --------------------------------------------------------------------------


def _distractors(target: TargetRef, affordances: list[str], limit: int = 2) -> list[str]:
    """Scene phrases that are plausible here but are not the answer."""

    label = _fold(target.label_fr)
    pool: list[str] = []
    for phrase in affordances:
        folded = _fold(phrase)
        if not folded or folded == label:
            continue
        if label and (folded in label or label in folded):
            continue
        if folded in {_fold(item) for item in pool}:
            continue
        pool.append(phrase)
    pool.sort(key=lambda phrase: _digest(target.id, phrase))
    return pool[:limit]


def _hint_for(target: TargetRef, control_language: ControlLanguage) -> str:
    words = (target.label_fr or "").split()
    initial = words[0][:1] if words and words[0] else "?"
    return _localized(_HINT_TEMPLATE, control_language).format(
        count=len(words) or 1, initial=initial
    )


def public_recall_target(target: TargetRef) -> dict[str, Any]:
    """The recall target as the *asking* payload may carry it.

    WP-12 defect D-4: ``TargetRef.label_fr`` **is** the answer to a recall
    prompt — for a choice it is one of the options verbatim, for tiles and short
    answer it is the string being elicited — so shipping it inside the payload
    that poses the question both spoils it and bypasses the assistance ledger
    (the paid ``solution`` reveal returns exactly that string). The frozen
    ``TargetRef`` shape is kept intact, and every field that identifies the
    target without answering the question is kept with it; only the answer
    itself is withheld until the learner has answered or paid for it.
    """

    public = target.as_public()
    public["label_fr"] = ""
    return public


def build_recall_task(
    *,
    target: TargetRef,
    scenario: ScenarioBrief,
    affordances: list[str],
    optional: bool,
) -> RecallTask | None:
    """One recall opportunity — a single task, never a fifteen-item ladder.

    Returns ``None`` when the target cannot be posed without revealing itself:
    a one-word target with no gloss and no distractors has no honest question,
    so it gets no step at all rather than a fake one.
    """

    language = scenario.control_language
    label_fr = (target.label_fr or "").strip()
    if not label_fr:
        return None
    gloss = (target.label_native or "").strip() or None
    tokens = label_fr.split()
    distractors = _distractors(target, affordances)

    if gloss and len(distractors) >= 2:
        task_type: RecallTaskType = "choice"
    elif len(tokens) >= 2:
        task_type = "tiles"
    elif gloss:
        task_type = "short_answer"
    else:
        return None

    hint = _hint_for(target, language)
    common: dict[str, Any] = {
        "target": target,
        "optional": optional,
        "hint_native": hint,
        "translation_native": gloss,
        "solution_fr": label_fr,
    }

    if task_type == "choice":
        texts = [label_fr, *distractors]
        options = [
            {"id": "opt_" + _digest(target.id, text)[:8], "text_fr": text} for text in texts
        ]
        options.sort(key=lambda option: _digest(target.id, "order", option["text_fr"]))
        correct_id = "opt_" + _digest(target.id, label_fr)[:8]
        return RecallTask(
            task_type="choice",
            instruction_native=_localized(_CHOICE_INSTRUCTION, language).format(native=gloss),
            prompt_fr=None,
            options=options,
            correct_option_id=correct_id,
            accepted_answers=[label_fr],
            estimated_seconds=0,
            **common,
        )

    if task_type == "tiles":
        ordered = [
            {"id": "tile_" + _digest(target.id, str(index), token)[:8], "text_fr": token}
            for index, token in enumerate(tokens)
        ]
        correct_order = [tile["id"] for tile in ordered]
        shown = sorted(ordered, key=lambda tile: _digest(target.id, "layout", tile["id"]))
        if [tile["id"] for tile in shown] == correct_order and len(shown) > 1:
            shown = shown[1:] + shown[:1]
        instruction = (
            _localized(_TILES_INSTRUCTION_WITH_GLOSS, language).format(native=gloss)
            if gloss
            else _localized(_TILES_INSTRUCTION, language)
        )
        return RecallTask(
            task_type="tiles",
            instruction_native=instruction,
            prompt_fr=None,
            options=shown,
            correct_tile_order=correct_order,
            accepted_answers=[label_fr],
            estimated_seconds=0,
            **common,
        )

    return RecallTask(
        task_type="short_answer",
        instruction_native=_localized(_SHORT_ANSWER_INSTRUCTION, language).format(native=gloss),
        prompt_fr=None,
        options=[],
        accepted_answers=[label_fr],
        estimated_seconds=0,
        **common,
    )


def _recall_help(task: RecallTask) -> list[str]:
    available = [str(HelpKind.HINT)] if task.hint_native else []
    if task.translation_native:
        available.append(str(HelpKind.TRANSLATION))
    if task.solution_fr:
        available.append(str(HelpKind.SOLUTION))
    return available


def _respond_help(task: ResponseTask) -> list[str]:
    available: list[str] = []
    if task.hint_native:
        available.append(str(HelpKind.HINT))
    if task.translation_native:
        available.append(str(HelpKind.TRANSLATION))
    if task.suggested_response_fr:
        available.append(str(HelpKind.SUGGESTED_RESPONSE))
    return available


# --------------------------------------------------------------------------
# 3. Estimates
# --------------------------------------------------------------------------


def _reading_seconds(seconds_per_token: float, *texts: str | None) -> float:
    return _tokens(*texts) * seconds_per_token


def _playback_seconds(audio_url: str | None, *texts: str | None) -> float:
    """Listening time, which is zero until a step actually carries audio."""

    if not audio_url:
        return 0.0
    return _tokens(*texts) * AUDIO_PLAYBACK_SECONDS_PER_TOKEN


def scene_seconds(scenario: ScenarioBrief, *, spt: float, multiplier: float) -> int:
    """Orientation plus reading the setup, the objective and the opening line."""

    reading = _reading_seconds(
        spt,
        scenario.setup_fr,
        scenario.setup_native,
        scenario.objective_native,
        scenario.opening_line_fr,
    )
    reading += _playback_seconds(None, scenario.opening_line_fr)
    return max(1, round(SCENE_BASE_SECONDS * multiplier + reading))


def recall_seconds(task: RecallTask, *, spt: float, multiplier: float) -> int:
    """Reading the task, answering it once, and reading the normal feedback."""

    texts = [task.instruction_native, task.prompt_fr]
    texts.extend(str(option.get("text_fr") or "") for option in task.options)
    fixed = RECALL_ANSWER_SECONDS.get(task.task_type, 30) + RECALL_FEEDBACK_SECONDS
    return max(1, round(fixed * multiplier + _reading_seconds(spt, *texts)))


def respond_seconds(task: ResponseTask, *, turns: int, spt: float, multiplier: float) -> int:
    """WP-03's authored envelope, floored by an explicit bottom-up model.

    The bottom-up model is reading the character line and the objective, one
    composition block per allowed turn, the normal feedback, and the single
    repair allowance. When the plan drops to one turn the authored envelope is
    reduced by exactly one composition block rather than discarded.

    Reading is priced with the measured ``spt``; everything the learner *does*
    is priced with the measured ``multiplier``. The two are never compounded on
    the same seconds, so a slow reader is not charged twice for the same line.
    """

    reading = _reading_seconds(spt, task.opening_line_fr, task.objective_native)
    reading += _playback_seconds(None, task.opening_line_fr)
    repair = REPAIR_ALLOWANCE_SECONDS if task.repair_allowed else 0
    fixed = RESPOND_TURN_SECONDS * turns + RESPOND_FEEDBACK_SECONDS + repair
    bottom_up = fixed * multiplier + reading
    authored = float(task.estimated_seconds or 0)
    dropped = max(0, (task.max_turns or MAX_RESPOND_TURNS) - turns)
    authored = max(0.0, authored - RESPOND_TURN_SECONDS * dropped) * multiplier
    return max(1, round(max(authored, bottom_up)))


def resolution_seconds(
    scenario: ScenarioBrief, outcome_key: str, *, spt: float, multiplier: float
) -> int:
    """Reading the ending the learner earned, plus closing the day."""

    reading = _reading_seconds(
        spt,
        render_authored_text(scenario.resolution_lines.get(outcome_key)),
        render_authored_text(scenario.resolution_summaries.get(outcome_key)),
    )
    return max(1, round(RESOLUTION_BASE_SECONDS * multiplier + reading))


# --------------------------------------------------------------------------
# 4. The plan
# --------------------------------------------------------------------------


def plan_journey(
    *,
    scenario: ScenarioBrief,
    candidates: list[LearningCandidate],
    budget_seconds: int = DEFAULT_BUDGET_SECONDS,
    pace: PacingProfile | None = None,
    input_mode: InputMode = InputMode.TEXT,
) -> PlannedJourney:
    """Build today's immutable plan.

    ``input_mode`` is a coordination addition, not a contract change: the frozen
    :class:`ScenarioBrief` carries no modality and ``RespondPrompt.input_modes``
    has to say whether voice is on offer. Omitting it yields the safe answer —
    text only, which is always available.
    """

    outcome_key = _require_plannable(scenario)
    profile = pace or PacingProfile()
    spt = profile.effective_seconds_per_token()
    multiplier = profile.effective_step_multiplier()
    notes: list[str] = []
    if pace is not None and not profile.is_trusted:
        notes.append(
            f"measured pace ignored: {profile.observations} observation(s), "
            f"{MIN_PACE_OBSERVATIONS} required"
        )
    if scenario.is_authored_fallback:
        notes.append("scene is the authored fallback; no serial episode was bound")

    selection = select_plan_targets(scenario, candidates)
    affordances = _affordances_for(scenario)
    task = scenario.response_task

    # --- fit the non-removable core (scene, response, resolution) -----------
    turns = max(1, min(int(task.max_turns or MAX_RESPOND_TURNS), MAX_RESPOND_TURNS))
    scene_cost = scene_seconds(scenario, spt=spt, multiplier=multiplier)
    resolution_cost = resolution_seconds(scenario, outcome_key, spt=spt, multiplier=multiplier)
    respond_cost = respond_seconds(task, turns=turns, spt=spt, multiplier=multiplier)
    while scene_cost + respond_cost + resolution_cost > budget_seconds and turns > 1:
        turns -= 1
        respond_cost = respond_seconds(task, turns=turns, spt=spt, multiplier=multiplier)
        notes.append("response reduced to one turn to keep the plan inside the budget")
    if scene_cost + respond_cost + resolution_cost > budget_seconds and (
        spt != DEFAULT_SECONDS_PER_TOKEN or multiplier != 1.0
    ):
        # A measured pace this slow cannot fit a scene that still has a real
        # ending. The plan stays whole and the estimate falls back to the base
        # pace rather than silently deleting the objective or the resolution.
        spt = DEFAULT_SECONDS_PER_TOKEN
        multiplier = 1.0
        scene_cost = scene_seconds(scenario, spt=spt, multiplier=multiplier)
        resolution_cost = resolution_seconds(scenario, outcome_key, spt=spt, multiplier=multiplier)
        respond_cost = respond_seconds(task, turns=turns, spt=spt, multiplier=multiplier)
        notes.append("measured pace set aside to the base pace: the core plan did not fit")
    if scene_cost + respond_cost + resolution_cost > budget_seconds:
        # Scene, response and resolution are not removable (CONTRACTS §3). If
        # they cannot fit even at the base pace the content is too long to be a
        # five-minute journey, and saying so beats shipping a false promise.
        raise PlanUnavailable("scene_exceeds_budget")

    # --- shape the recall steps inside whatever headroom is left -----------
    headroom = budget_seconds - (scene_cost + respond_cost + resolution_cost)
    recalls: list[tuple[SelectedTarget, RecallTask, int, bool]] = []
    used_targets: list[SelectedTarget] = []
    dropped: list[LearningCandidate] = []
    reasons = dict(selection.omission_reasons)
    for entry in selection.selected:
        identity = target_identity(entry.target)
        if len(recalls) >= MAX_RECALL_STEPS:
            # Still selected: it is elicited in the reply, it just gets no drill.
            used_targets.append(entry)
            continue
        planned_real = sum(1 for _e, _t, _c, was_skipped in recalls if not was_skipped)
        optional = entry.demonstrated or entry.candidate.is_new or planned_real >= 1
        recall = build_recall_task(
            target=entry.target,
            scenario=scenario,
            affordances=affordances,
            optional=optional,
        )
        if recall is None:
            used_targets.append(entry)
            notes.append(f"{identity}: no recall form could be posed without revealing it")
            continue
        if entry.demonstrated:
            recalls.append((entry, recall, 0, True))
            used_targets.append(entry)
            notes.append(f"{identity}: already produced independently, recall step skipped")
            continue
        cost = recall_seconds(recall, spt=spt, multiplier=multiplier)
        if cost > headroom:
            dropped.append(entry.candidate)
            reasons[identity] = "no_budget_headroom"
            continue
        headroom -= cost
        recalls.append((entry, recall, cost, False))
        used_targets.append(entry)

    # --- assemble ----------------------------------------------------------
    steps: list[PlannedStep] = []
    ordinal = 0
    steps.append(
        PlannedStep(
            ordinal=ordinal,
            kind=StepKind.SCENE,
            estimated_seconds=scene_cost,
            public_prompt={
                "setup_fr": scenario.setup_fr,
                "setup_native": scenario.setup_native,
                "objective_native": scenario.objective_native,
                "character_line_fr": scenario.opening_line_fr,
                "character_line_audio_url": None,
                "image_url": scenario.image_url,
            },
            private_task=None,
            target=None,
            optional=False,
            initial_status=StepStatus.PENDING,
        )
    )
    ordinal += 1
    for entry, recall, cost, skipped in recalls:
        steps.append(
            PlannedStep(
                ordinal=ordinal,
                kind=StepKind.RECALL,
                estimated_seconds=cost,
                public_prompt={
                    "task_type": recall.task_type,
                    "instruction_native": recall.instruction_native,
                    "prompt_fr": recall.prompt_fr,
                    "options": [dict(option) for option in recall.options],
                    "target": public_recall_target(recall.target),
                    "optional": recall.optional,
                    "help_available": _recall_help(recall),
                },
                private_task=replace(recall, estimated_seconds=cost),
                target=entry.target,
                optional=recall.optional,
                initial_status=StepStatus.SKIPPED if skipped else StepStatus.PENDING,
            )
        )
        ordinal += 1

    elicited = [entry.target for entry in used_targets if entry.is_elicitable]
    respond_task = replace(
        task,
        max_turns=turns,
        targets=list(elicited),
        estimated_seconds=respond_cost,
    )
    steps.append(
        PlannedStep(
            ordinal=ordinal,
            kind=StepKind.RESPOND,
            estimated_seconds=respond_cost,
            public_prompt={
                "turn_index": 0,
                "max_turns": turns,
                "repair_allowed": bool(task.repair_allowed),
                "character_id": task.character_id,
                "character_name": task.character_name,
                "character_line_fr": task.opening_line_fr,
                "character_line_audio_url": None,
                "objective_native": task.objective_native,
                "input_modes": supported_input_modes(scenario, input_mode=input_mode),
                "targets": [target.as_public() for target in elicited],
                "help_available": _respond_help(task),
            },
            private_task=respond_task,
            target=None,
            optional=False,
            initial_status=StepStatus.PENDING,
        )
    )
    ordinal += 1
    steps.append(
        PlannedStep(
            ordinal=ordinal,
            kind=StepKind.RESOLUTION,
            estimated_seconds=resolution_cost,
            public_prompt={
                "outcome_key": outcome_key,
                # The plan is built before the learner has spoken, so the ending
                # is rendered with no learner detail at all: every authored slot
                # falls back to wording that claims no drink and no day. WP-06
                # re-renders it with the real choice once the turn is graded.
                "character_line_fr": render_authored_text(
                    scenario.resolution_lines.get(outcome_key, "")
                ),
                "summary_native": render_authored_text(
                    scenario.resolution_summaries.get(outcome_key, "")
                ),
                "image_url": scenario.image_url,
            },
            private_task=None,
            target=None,
            optional=False,
            initial_status=StepStatus.PENDING,
        )
    )

    omitted = [*selection.omitted, *dropped]
    rationale = _rationale(
        selected=used_targets,
        recalls=recalls,
        omitted=omitted,
        reasons=reasons,
        candidates=candidates,
        notes=notes,
    )
    plan = PlannedJourney(
        scenario=scenario,
        steps=steps,
        estimated_active_seconds=sum(step.estimated_seconds for step in steps),
        budget_seconds=budget_seconds,
        selected_target_ids=[target_identity(entry.target) for entry in used_targets],
        omitted_candidate_ids=[target_identity(item.target) for item in omitted],
        rationale=rationale,
    )
    plan.validate()
    if len(plan.steps) > MAX_PLANNED_STEPS:  # pragma: no cover - validate() already raises
        raise PlanUnavailable("plan_exceeds_step_budget")
    return plan


def _require_plannable(scenario: ScenarioBrief) -> str:
    """Refuse to plan a scene that cannot honestly end."""

    if not (scenario.setup_fr or "").strip():
        raise PlanUnavailable("scene_has_no_setup")
    if not (scenario.objective_native or "").strip():
        raise PlanUnavailable("scene_has_no_objective")
    task = scenario.response_task
    if not (task.opening_line_fr or "").strip():
        raise PlanUnavailable("response_task_has_no_opening_line")
    if not (task.objective_native or "").strip():
        raise PlanUnavailable("response_task_has_no_objective")
    outcome_key = default_outcome_key(scenario)
    if not outcome_key:
        raise PlanUnavailable("scenario_has_no_ending")
    return outcome_key


def _rationale(
    *,
    selected: list[SelectedTarget],
    recalls: list[tuple[SelectedTarget, RecallTask, int, bool]],
    omitted: list[LearningCandidate],
    reasons: dict[str, str],
    candidates: list[LearningCandidate],
    notes: list[str],
) -> str:
    """A short, deterministic, honest account of what today contains.

    Internal (it is not part of the frozen wire contract) and written in
    English for operators and tests; nothing here is rendered to a learner.
    """

    parts: list[str] = []
    if not candidates:
        parts.append(
            "no review item was due and no new anchor was offered, "
            "so today is the scene and the response only"
        )
    else:
        parts.append(
            f"{len(selected)} of {len(candidates)} candidate(s) selected; "
            f"{sum(1 for _e, _t, _c, skipped in recalls if not skipped)} recall step(s) planned"
        )
    unrelated = [
        target_identity(entry.target) for entry in selected if not entry.is_elicitable
    ]
    if unrelated:
        parts.append(
            "rehearsed but not required in the reply (no scene fit): " + ", ".join(sorted(unrelated))
        )
    if omitted:
        grouped: dict[str, list[str]] = {}
        for candidate in omitted:
            identity = target_identity(candidate.target)
            grouped.setdefault(reasons.get(identity, "not_selected"), []).append(identity)
        for reason in sorted(grouped):
            ids = sorted(grouped[reason])
            shown = ", ".join(ids[:3]) + (f" and {len(ids) - 3} more" if len(ids) > 3 else "")
            parts.append(f"{len(ids)} candidate(s) stayed due, untouched ({reason}): {shown}")
    parts.extend(notes)
    return "; ".join(parts)


__all__ = [
    "AUDIO_PLAYBACK_SECONDS_PER_TOKEN",
    "DEFAULT_SECONDS_PER_TOKEN",
    "DEMONSTRATED_EVIDENCE_KINDS",
    "DEMONSTRATED_FLAG_KEYS",
    "ELICITATION_FIT_THRESHOLD",
    "MAX_DUE_TARGETS",
    "MAX_NEW_TARGETS",
    "MAX_SELECTED_TARGETS",
    "MIN_PACE_OBSERVATIONS",
    "PLANNER_VERSION",
    "RECALL_ANSWER_SECONDS",
    "RECALL_FEEDBACK_SECONDS",
    "REPAIR_ALLOWANCE_SECONDS",
    "RESOLUTION_BASE_SECONDS",
    "RESPOND_FEEDBACK_SECONDS",
    "RESPOND_TURN_SECONDS",
    "SCENE_BASE_SECONDS",
    "SECONDS_PER_TOKEN_BOUNDS",
    "STEP_MULTIPLIER_BOUNDS",
    "PacingProfile",
    "PlanUnavailable",
    "SelectedTarget",
    "TargetSelection",
    "build_recall_task",
    "candidate_is_demonstrated",
    "default_outcome_key",
    "plan_journey",
    "public_recall_target",
    "recall_seconds",
    "resolution_seconds",
    "respond_seconds",
    "scenario_fit",
    "scene_seconds",
    "select_plan_targets",
    "supported_input_modes",
    "target_identity",
]
