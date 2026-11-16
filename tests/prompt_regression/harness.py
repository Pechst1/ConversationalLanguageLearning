"""Prompt regression for the story lanes (E-7 · «Loop v2»): golden cases, prompt
snapshots and replayed model answers, with no network and no paid call.

A **golden case** (``cases/<id>.json``) is one input state and the answers a model
gave to it:

* ``lane`` — ``page`` (Story Phase 2: planner → author → aids, ``story_split``) or
  ``turn`` (the reply lanes: tutor + voice, ``story_lanes.run_reply_lanes``);
* ``input`` — for a page, a captured ``story_context`` (``contexts/*.json``) plus a
  shallow patch; for a turn, the turn payload ``_turn_payload`` builds;
* ``answers`` — per output schema, the answers in the order the code asks for them,
  each stamped with the ``prompt_digest`` of the prompt it answered;
* ``expect`` — what the deterministic pipeline must make of those answers.

Running a case drives the real code — ``story_split.draw`` or ``run_reply_lanes`` —
with :class:`Replayer` in place of the model client: every prompt the code builds is
recorded exactly (system prompt, user message, call parameters), and the recorded
answer is handed back. The page then goes through ``living_story._validate_scene``
(every scene guard, the season's canon guards included); the reply lanes run their
own guards, the soft length rule and the met-gate.

The **snapshot** (``snapshots/<id>.txt``) is the rendered prompt of every call. Its
first line holds the digest of the exact bytes sent — the snapshot key. A changed
prompt fails with a unified diff; ``PROMPT_SNAPSHOT_UPDATE=1`` (pytest) or
``scripts/prompt_regression.py --update`` accepts it.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parent
CASES = ROOT / "cases"
CONTEXTS = ROOT / "contexts"
SNAPSHOTS = ROOT / "snapshots"
UPDATE_ENV = "PROMPT_SNAPSHOT_UPDATE"
#: The order calls are rendered in (the reply lanes run in parallel threads).
SCHEMA_ORDER = ("PagePlan", "PageText", "PageAids", "TutorVerdict", "VoiceReply", "StoryTurn", "TurnReview", "ReplyChoice", "SceneClosing", "CourrierReply")
#: Settings that change what a story call sends, pinned so a developer's ``.env``, CI
#: and the CLI render the same bytes. ``None`` routes keep each call's own effort.
PINNED_SETTINGS = {
    "STORY_WRITER_MODEL": None,
    "STORY_WRITER_REASONING_EFFORT": None,
    "STORY_LIVE_MODEL": None,
    "STORY_CRITIC_MODEL": None,
    "ATELIER_STORY_MAX_ATTEMPTS": 2,
    "OPENAI_MISSION_FAST_MODEL": "pinned-courrier-model",
}
#: Call parameters left out of the snapshot: the request timeout is the time left.
VOLATILE_PARAMS = frozenset({"request_timeout"})


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------


@dataclass
class Case:
    id: str
    lane: str
    level: str
    source: str
    input: dict
    answers: dict[str, list[dict]]
    expect: dict
    path: Path
    raw: dict = field(repr=False, default_factory=dict)

    @property
    def snapshot_path(self) -> Path:
        return SNAPSHOTS / f"{self.id}.txt"


def load_cases(ids: list[str] | None = None) -> list[Case]:
    cases = []
    for path in sorted(CASES.glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        case = Case(
            id=raw["id"],
            lane=raw["lane"],
            level=raw["level"],
            source=raw.get("source", ""),
            input=raw["input"],
            answers=raw.get("answers") or {},
            expect=raw.get("expect") or {},
            path=path,
            raw=raw,
        )
        if case.id != path.stem:
            raise ValueError(f"{path.name}: id {case.id!r} must match the file name")
        if ids and case.id not in ids:
            continue
        cases.append(case)
    return cases


def build_context(case: Case) -> dict:
    """The page lane's ``story_context``: a captured one, patched, with the season
    runtime handle (``_season``) rebuilt from the season files."""

    from app.services.season.format import load_season

    spec = case.input
    context = json.loads((CONTEXTS / spec["context"]).read_text(encoding="utf-8"))
    context.pop("_captured", None)
    context.update(json.loads(json.dumps(spec.get("patch") or {})))
    today = context.pop("_season", None)
    if today:
        context["_season"] = SimpleNamespace(
            season=load_season(today["season_id"]), flags=dict(today["flags"]), seed=today["seed"]
        )
    return context


# ---------------------------------------------------------------------------
# The replaying model client
# ---------------------------------------------------------------------------


@dataclass
class Call:
    schema: str
    attempt: int
    system: str
    user: str
    params: dict

    @property
    def digest(self) -> str:
        blob = json.dumps(
            {"system": self.system, "user": self.user, "params": self.params},
            ensure_ascii=False,
            sort_keys=True,
        )
        return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()


class Replayer:
    """Stands in for ``LLMService``: records each request, answers from the case."""

    def __init__(self, answers: dict[str, list[dict]]):
        self.answers = answers
        self.calls: list[Call] = []
        self.missing: list[str] = []
        self._lock = threading.Lock()

    def generate_chat_completion(self, messages, *, system_prompt=None, **kwargs):
        user = messages[-1]["content"]
        schema = json.loads(user)["output_schema"].get("title", "?")
        params = {key: value for key, value in sorted(kwargs.items()) if key not in VOLATILE_PARAMS}
        with self._lock:
            attempt = 1 + sum(1 for call in self.calls if call.schema == schema)
            self.calls.append(Call(schema, attempt, system_prompt or "", user, params))
            recorded = self.answers.get(schema) or []
            if attempt > len(recorded):
                self.missing.append(f"{schema} #{attempt}")
                raise LookupError(f"no recorded answer for {schema} #{attempt}")
            content = recorded[attempt - 1]["content"]
        text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
        return SimpleNamespace(
            content=text, model="replay", provider="replay", total_tokens=0, cost=0.0
        )


class Recorder:
    """Stands in for ``LLMService`` on ``--live``: each call goes to the real client, its
    answer is kept for replay, and a running total stops the run at the cap.

    The call is recorded without ``model`` (the harness pins the route to the provider's
    default, so a replay builds the same digest); ``model`` only selects what answers it.
    """

    def __init__(self, client: Any, *, model: str | None, cap_usd: float, spent: float = 0.0, stamp: str = "live"):
        self.client = client
        self.model = model
        self.cap_usd = cap_usd
        self.spent = spent
        self.stamp = stamp
        self.calls: list[Call] = []
        self.answers: dict[str, list[dict]] = {}
        self._lock = threading.Lock()

    def generate_chat_completion(self, messages, *, system_prompt=None, **kwargs):
        from app.services import living_story as engine

        with self._lock:
            if self.spent >= self.cap_usd:
                raise engine.StoryUnavailable("prompt_regression_cap_reached")
        user = messages[-1]["content"]
        schema = json.loads(user)["output_schema"].get("title", "?")
        params = {key: value for key, value in sorted(kwargs.items()) if key not in VOLATILE_PARAMS}
        result = self.client.generate_chat_completion(
            messages, system_prompt=system_prompt, **kwargs, **({"model": self.model} if self.model else {})
        )
        with self._lock:
            self.spent += float(result.cost or 0.0)
            attempt = 1 + sum(1 for call in self.calls if call.schema == schema)
            call = Call(schema, attempt, system_prompt or "", user, params)
            self.calls.append(call)
            try:
                content: Any = json.loads(result.content)
            except (TypeError, ValueError):
                content = result.content
            self.answers.setdefault(schema, []).append(
                {"origin": f"{self.stamp} {result.model}", "prompt_digest": call.digest, "content": content}
            )
        return result


def record_case(case: Case, recorder: Recorder) -> dict:
    """Run a turn case against the real model and keep its answers; returns what the
    pipeline made of them. Nothing is written when the run failed or hit the cap, so a
    half-recorded case can never replay as if it were whole."""

    from app.services import living_story as engine

    if case.lane not in ("turn", "authored"):
        raise ValueError(f"{case.id}: --live records turn and authored cases only")
    recorder.calls, recorder.answers = [], {}
    run = _run_turn if case.lane == "turn" else _run_authored
    with pinned_settings(), _patched(engine, "_client", lambda: recorder):
        observed, _ = run(case)
    if observed.get("failure"):
        return observed
    case.raw["answers"] = recorder.answers
    case.path.write_text(json.dumps(case.raw, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return observed


@contextmanager
def _patched(target: Any, name: str, value: Any):
    old = getattr(target, name)
    setattr(target, name, value)
    try:
        yield
    finally:
        setattr(target, name, old)


@contextmanager
def pinned_settings():
    from app.config import settings

    old = {key: getattr(settings, key) for key in PINNED_SETTINGS}
    try:
        for key, value in PINNED_SETTINGS.items():
            setattr(settings, key, value)
        yield
    finally:
        for key, value in old.items():
            setattr(settings, key, value)


# ---------------------------------------------------------------------------
# Running a case
# ---------------------------------------------------------------------------


@dataclass
class Result:
    case: Case
    calls: list[Call]
    observed: dict
    served: Any = None

    @property
    def digest(self) -> str:
        blob = "\n".join(call.digest for call in self.calls)
        return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()


def run_case(case: Case) -> Result:
    from app.services import living_story as engine

    replayer = Replayer(case.answers)
    with pinned_settings(), _patched(engine, "_client", lambda: replayer):
        if case.lane == "page":
            observed, served = _run_page(case)
        elif case.lane == "turn":
            observed, served = _run_turn(case)
        elif case.lane == "authored":
            observed, served = _run_authored(case)
        elif case.lane == "story":
            observed, served = _run_story(case)
        elif case.lane == "courrier":
            observed, served = _run_courrier(case, replayer)
        else:
            raise ValueError(f"{case.id}: unknown lane {case.lane!r}")
    observed["missing_answers"] = list(replayer.missing)
    calls = sorted(replayer.calls, key=lambda call: (SCHEMA_ORDER.index(call.schema), call.attempt))
    return Result(case=case, calls=calls, observed=observed, served=served)


def _run_page(case: Case) -> tuple[dict, Any]:
    from app.services import living_story as engine
    from app.services import story_split

    context = build_context(case)
    observed: dict[str, Any] = {"plan_refusals": [], "draw": "ok"}
    real_issue = story_split.plan_issue

    def plan_issue(plan, ctx):
        issue = real_issue(plan, ctx)
        if issue:
            observed["plan_refusals"].append(issue)
        return issue

    with _patched(story_split, "plan_issue", plan_issue), engine.written_ahead_of_time():
        try:
            draft = story_split.draw(context)(
                {}, lambda usage: None, deadline=time.monotonic() + 600
            )
        except engine.StoryUnavailable as exc:
            observed["draw"] = str(exc)
            return observed, None
    try:
        engine._validate_scene(draft, context)
        observed["scene_guard"] = "pass"
    except engine.SoftRejection as exc:
        observed["scene_guard"] = f"soft:{exc}"
        observed["scene_hint"] = exc.hint
    except engine.StoryUnavailable as exc:
        observed["scene_guard"] = str(exc)
        observed["scene_hint"] = exc.hint
    words = (
        draft.premise_fr.split()
        + [word for panel in draft.panels for word in panel.narration_fr.split()]
        + [
            word
            for panel in draft.panels
            for line in panel.dialogue
            for word in line.text_fr.split()
        ]
    )
    names = engine._cast_first_names(context)
    recent = [
        item.get("objective_native") or "" for item in (context.get("recent_situations") or [])
    ]
    observed.update(
        {
            "objective": draft.objective_native,
            "lead": draft.character_id,
            "voices": sorted(
                {line.character_id for panel in draft.panels for line in panel.dialogue}
            ),
            "premise_id": draft.season_checklist.premise_id if draft.season_checklist else None,
            "words": len(words),
            "word_limit": engine._SCENE_WORD_LIMITS.get(str(context.get("level")), 170),
            "reasked": next(
                (
                    asked
                    for asked in recent
                    if engine._task_overlap(draft.objective_native, asked, names) >= 0.6
                ),
                None,
            ),
        }
    )
    return observed, draft


def _with_ledger(payload: dict) -> dict:
    """The ledger ``_turn_payload`` puts on a turn, rebuilt from the case's own lines, so a
    snapshot shows what production sends and a recorded case cannot go stale against it."""

    from app.services import scene_ledger

    scene = payload.get("scene") or {}
    payload["ledger"] = scene_ledger.build(
        opening_line_fr=scene.get("opening_line_fr"),
        history=payload.get("history") or [],
        learner_text=payload.get("learner_text"),
        in_the_room=scene_ledger.room_of(scene),
    )
    plan = payload.setdefault("turn_plan", {})
    plan["learner_asked"] = payload["ledger"]["learner_asked"]
    return payload


def _run_turn(case: Case) -> tuple[dict, Any]:
    from app.services import living_story as engine
    from app.services import story_lanes as lanes

    payload = _with_ledger(json.loads(json.dumps(case.input["payload"])))
    observed: dict[str, Any] = {"tutor_refusals": [], "voice_refusals": [], "failure": None}

    def spy(name: str, real):
        def validate(proposal, *args, **kwargs):
            try:
                return real(proposal, *args, **kwargs)
            except engine.StoryUnavailable as exc:
                observed[f"{name}_refusals"].append(str(exc))
                raise

        return validate

    with (
        _patched(lanes, "validate_tutor", spy("tutor", lanes.validate_tutor)),
        _patched(lanes, "validate_voice", spy("voice", lanes.validate_voice)),
    ):
        try:
            # ``lexical`` (WP-89's known-word budget) needs the learner's database: not replayed.
            result = lanes.run_reply_lanes(payload, deadline=time.monotonic() + 600, lexical=None)
        except engine.StoryUnavailable as exc:
            observed["failure"] = str(exc)
            return observed, None
    level = (payload.get("story") or {}).get("level")
    observed.update(
        {
            "outcome": result.tutor.outcome,
            "gated": list(result.gated),
            "evidence_quotes": list(result.tutor.evidence_quotes),
            "reply_fr": result.voice.reply_fr,
            "reply_words": engine.reply_words(result.voice.reply_fr),
            "reply_limit": engine._REPLY_WORD_LIMITS.get(engine._reply_band(level)),
            "needs_clarification": result.voice.needs_clarification,
        }
    )
    return observed, result


def _run_story(case: Case) -> tuple[dict, Any]:
    """The story lane (the scene's ending and tomorrow's question) after a reply the
    learner has already seen: ``input`` holds the turn's payload and the two released
    verdicts. What ``settle_resolution`` will then do with the question is read here too."""

    from app.services import story_lanes as lanes
    from app.services import story_teaser

    payload = _with_ledger(json.loads(json.dumps(case.input["payload"])))
    tutor = lanes.TutorVerdict(**case.input["tutor"])
    voice = lanes.VoiceReply(**case.input["voice"])
    result = lanes.run_story_lane(payload, tutor, voice, deadline=time.monotonic() + 600)
    if result.turn is None:
        return {"failure": result.reason, "story_hint": result.hint}, None
    turn = result.turn
    known = " ".join([json.dumps(payload, ensure_ascii=False), turn.reply_fr, turn.resolution_fr])
    question = turn.tomorrow_question_fr
    return {
        "failure": None,
        "resolution_fr": turn.resolution_fr,
        "summary_native": turn.summary_native,
        "tomorrow_question_fr": question,
        "tomorrow_problem": story_teaser.question_problem(question, known=known, ledger=payload.get("ledger")),
        "still_open": [row["text_fr"] for row in payload["ledger"]["still_open"]],
    }, result


class _CourrierAnswers:
    """The Courrier's reply writer sends plain messages and gets plain text back, so it
    has no ``output_schema`` for the replayer to name the call by."""

    SCHEMA = "CourrierReply"

    def __init__(self, replayer: Replayer):
        self.replayer = replayer

    def generate_chat_completion(self, messages, *, system_prompt=None, **kwargs):
        from app.services.llm_service import LLMProviderError

        replayer = self.replayer
        params = {key: value for key, value in sorted(kwargs.items()) if key not in VOLATILE_PARAMS}
        data = [
            {**message, "content": json.loads(message["content"].removeprefix("Scene context: "))}
            if message["content"].startswith("Scene context: ")
            else message
            for message in messages
        ]
        user = json.dumps({"output_schema": None, "data": data}, ensure_ascii=False)
        attempt = 1 + sum(1 for call in replayer.calls if call.schema == self.SCHEMA)
        replayer.calls.append(Call(self.SCHEMA, attempt, system_prompt or "", user, params))
        recorded = replayer.answers.get(self.SCHEMA) or []
        if attempt > len(recorded):
            replayer.missing.append(f"{self.SCHEMA} #{attempt}")
            raise LLMProviderError(f"no recorded answer for {self.SCHEMA} #{attempt}")
        return SimpleNamespace(content=recorded[attempt - 1]["content"], model="replay", provider="replay", total_tokens=0, cost=0.0)


def _run_courrier(case: Case, replayer: Replayer) -> tuple[dict, Any]:
    """A reply on a thread: ``input`` holds the letter and the turns before the reply."""

    from app.services import missions

    letter = case.input["letter"]
    turns = [
        SimpleNamespace(role=row["role"], text=row["text"], turn_index=index, correction_payload=None)
        for index, row in enumerate(case.input.get("turns") or [], start=1)
    ]
    mission = SimpleNamespace(
        id=None,
        title=letter["title"],
        brief=letter["brief"],
        prompt_payload={"messenger": letter["messenger"], "conversation_opening": letter["messenger"]["opening_message"]},
        source_snapshot={},
        turns=turns,
        attempts=[],
        stakes_level=1,
        mission_type="message",
    )
    service = missions.MissionConversationService(db=None, llm_service=_CourrierAnswers(replayer))
    with _patched(missions, "_record_mission_llm_cost", lambda *a, **k: None), _patched(
        missions, "_learner_level_code", lambda db, user: case.level
    ):
        reply = service.respond(user=SimpleNamespace(id=None), mission=mission, user_text=case.input["learner_text"])
    return {"reply": reply}, reply


def _run_authored(case: Case) -> tuple[dict, Any]:
    """The reader of an authored day (``season.runtime.classify``) on a real page of the
    season: ``input`` names the page and the turn, and gives what the learner wrote."""

    from types import SimpleNamespace

    from app.services import scene_ledger
    from app.services.season import runtime
    from app.services.season.flags import effective_flags
    from app.services.season.format import load_season
    from app.services.season.page import resolve_day
    from app.services.season.turns import answers_question

    spec = case.input
    season = load_season(spec.get("season", "s1"))
    page = resolve_day(
        season,
        spec["tentpole"],
        spec["day"],
        flags=effective_flags(season, {}, seed="prompt-regression"),
        band=spec.get("band", case.level),
        language=spec.get("language", "en"),
    )
    turn = next(row for row in runtime.projected_turns(page) if row.get("id") == spec["turn"])
    history, text = list(spec.get("history") or []), spec["learner_text"]
    ledger = scene_ledger.build(
        opening_line_fr=spec.get("opening_line_fr") or runtime._opening_of([turn]), history=history, learner_text=text
    )
    if spec.get("closes"):
        return _run_closing(case, page, turn, history, text, ledger)
    runtime._ROUTE_CACHE.clear()
    choice = runtime.classify(
        None, None, scene_id=case.id, turn=turn, text=text, history=history, band=page.get("band"), ledger=ledger
    )
    played = runtime._checked_ack(
        None, None, choice.ack_fr, turn=turn, answer=SimpleNamespace(text=text), history=history, ledger=ledger, turn_index=len(history)
    )
    return {
        "failure": None,
        "reply_id": choice.reply_id,
        "clear": choice.clear,
        "learner_intent": choice.learner_intent,
        "ack_played": played,
        "answered": answers_question(turn, text, intent=choice.learner_intent),
    }, choice


def _run_closing(case: Case, page: dict, turn: dict, history: list, text: str, ledger: dict) -> tuple[dict, Any]:
    """The conversation's last words on an authored day (``season.closing``)."""

    from types import SimpleNamespace

    from app.services.season import closing, runtime
    from app.services.season.page import hook_caption

    problems: list[str] = []
    scenario = SimpleNamespace(
        title_fr=page["title_fr"],
        character_id=turn.get("to"),
        story_context={runtime.SEASON_CONTEXT_KEY: {"id": "s1", "page": page, "ending": hook_caption(page), "tail": runtime.page_tail(page)}},
    )
    beats = list(next(row for row in turn["replies"] if row["id"] == case.input["reply"]).get("beats") or [])
    panels, reading = closing.written_close(
        None,
        None,
        scenario=scenario,
        turn=turn,
        ledger=ledger,
        history=history,
        beats=beats,
        tail=closing.with_cuts("s1", page, runtime.page_tail(page)),
        band=page.get("band"),
        learner_text=text,
        on_problem=problems.append,
        on_usage=lambda usage: None,
    )
    said = [line["text_fr"] for panel in panels for line in panel["lines"]]
    return {
        "failure": None,
        "lines": said,
        "dropped": problems,
        "learner_intent": reading.learner_intent if reading else None,
        "tomorrow_question_fr": reading.tomorrow_question_fr if reading else None,
    }, reading


# ---------------------------------------------------------------------------
# Snapshots
# ---------------------------------------------------------------------------


def _short(digest: str, n: int = 16) -> str:
    return digest.split(":", 1)[-1][:n]


def render(result: Result) -> str:
    """The snapshot text: every call's parameters, system prompt and data, readable.
    The output schema is named by its digest (the pydantic models are code)."""

    case = result.case
    lines = [
        f"# prompt snapshot · {case.id} · lane {case.lane} · level {case.level}",
        f"# key: {result.digest}",
        f"# accept a change: {UPDATE_ENV}=1 python -m pytest tests/test_prompt_regression.py"
        " (or scripts/prompt_regression.py --update)",
        "",
    ]
    for number, call in enumerate(result.calls, start=1):
        message = json.loads(call.user)
        schema = json.dumps(message.get("output_schema"), ensure_ascii=False, sort_keys=True)
        lines += [
            f"======== call {number} · {call.schema} #{call.attempt} · {_short(call.digest)} ========",
            "params: " + json.dumps(call.params, ensure_ascii=False, sort_keys=True),
            f"output_schema: {call.schema} sha256:{hashlib.sha256(schema.encode()).hexdigest()[:16]}",
            "-------- system --------",
            call.system.rstrip("\n"),
            "-------- data --------",
            json.dumps(message.get("data"), ensure_ascii=False, indent=1),
            "",
        ]
    return "\n".join(lines) + "\n"


def stored_key(text: str) -> str | None:
    for line in text.splitlines()[:3]:
        if line.startswith("# key: "):
            return line[len("# key: ") :].strip()
    return None


def snapshot_diff(result: Result, *, context: int = 3, limit: int = 160) -> str | None:
    """``None`` when the stored snapshot matches; otherwise why not, with a diff."""

    path = result.case.snapshot_path
    rendered = render(result)
    if not path.exists():
        return f"{result.case.id}: no snapshot yet ({path.relative_to(ROOT.parents[1])})."
    stored = path.read_text(encoding="utf-8")
    if stored_key(stored) == result.digest:
        return None
    diff = list(
        difflib.unified_diff(
            stored.splitlines(),
            rendered.splitlines(),
            fromfile=f"snapshot/{result.case.id}",
            tofile=f"current/{result.case.id}",
            n=context,
            lineterm="",
        )
    )
    body = [line for line in diff if not line.startswith(("--- ", "+++ "))]
    if all(line.startswith(("@@", " ", "-# key:", "+# key:")) for line in body):
        diff.append(
            "(the rendered text is the same: the exact bytes sent differ — whitespace or key order)"
        )
    if len(diff) > limit:
        diff = diff[:limit] + [f"… {len(diff) - limit} more diff lines"]
    return (
        f"{result.case.id}: the prompt changed (key {stored_key(stored)} → {result.digest}).\n"
        + "\n".join(diff)
        + f"\nIf this change is intended, accept it: {UPDATE_ENV}=1 python -m pytest "
        "tests/test_prompt_regression.py, or scripts/prompt_regression.py --update."
    )


def write_snapshot(result: Result) -> None:
    SNAPSHOTS.mkdir(parents=True, exist_ok=True)
    result.case.snapshot_path.write_text(render(result), encoding="utf-8")


def stale_answers(result: Result) -> list[str]:
    """The recorded answers whose prompt has changed since they were recorded."""

    stale = []
    for call in result.calls:
        recorded = (result.case.answers.get(call.schema) or [])[call.attempt - 1 : call.attempt]
        if recorded and recorded[0].get("prompt_digest") != call.digest:
            stale.append(f"{call.schema} #{call.attempt}")
    return stale


def stamp_answers(result: Result) -> bool:
    """Mark each recorded answer as answering the prompt the code builds today."""

    changed = False
    for call in result.calls:
        recorded = (result.case.answers.get(call.schema) or [])[call.attempt - 1 : call.attempt]
        if recorded and recorded[0].get("prompt_digest") != call.digest:
            recorded[0]["prompt_digest"] = call.digest
            changed = True
    if changed:
        result.case.raw["answers"] = result.case.answers
        result.case.path.write_text(
            json.dumps(result.case.raw, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
    return changed


# ---------------------------------------------------------------------------
# Expectations
# ---------------------------------------------------------------------------


def check(result: Result) -> list[str]:
    """What is wrong with the replay: the case's own ``expect`` and the properties
    every served page or reply must have."""

    observed, case = result.observed, result.case
    problems = []
    if observed.get("missing_answers"):
        problems.append(
            f"the code asked for answers the case does not record: {observed['missing_answers']}"
        )
    for key, want in case.expect.items():
        got = observed.get(key)
        if (
            isinstance(want, list)
            and all(isinstance(item, str) for item in want)
            and isinstance(got, list)
        ):
            # A list of strings matches item by item, each expected text a substring.
            if len(got) != len(want) or any(
                w not in str(g) for w, g in zip(want, got, strict=False)
            ):
                problems.append(f"{key}: expected {want!r}, got {got!r}")
        elif got != want:
            problems.append(f"{key}: expected {want!r}, got {got!r}")
    if case.lane == "page" and observed.get("scene_guard") == "pass":
        if observed["words"] > observed["word_limit"]:
            problems.append(
                f"served page runs {observed['words']} words over the {case.level} limit {observed['word_limit']}"
            )
        if observed["reasked"]:
            problems.append(f"served page re-asks «{observed['reasked']}»")
        required = (
            ((build_context(case).get("season_script") or {}).get("brief") or {}).get("today") or {}
        ).get("required_premise")
        if required and observed["premise_id"] != required.get("id"):
            problems.append(f"served page skips the owed premise {required.get('id')!r}")
    if case.lane == "turn" and not observed.get("failure"):
        from app.services import living_story as engine

        issue = engine.reply_length_issue(observed["reply_fr"], case.level)
        if issue:
            problems.append(f"served reply above the {case.level} line: {issue}")
        learner = [
            case.input["payload"]["learner_text"],
            *[h.get("learner", "") for h in case.input["payload"].get("history") or []],
        ]
        folded = [engine._folded(text) for text in learner]
        invented = [
            q
            for q in observed["evidence_quotes"]
            if not any(engine._folded(q) in text for text in folded)
        ]
        if invented:
            problems.append(f"served grade quotes words the learner never wrote: {invented}")
    return problems
