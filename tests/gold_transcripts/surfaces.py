"""Drive each surface's production code with one gold input and return what the
learner would be shown.

Every adapter calls the same functions production calls, with the model client handed
in (``client``): the real :class:`LLMService` behind a spending meter on the weekly run, a fake
in the tests. Nothing here touches the database: the few writes the production paths
make (cost ledger rows, the learner's level read) are replaced by no-ops or by the
item's own level.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from contextlib import ExitStack, contextmanager
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parent
SETS = ROOT / "sets"
#: The page surface's captured story contexts, one per item of sets/page.json.
PAGES = SETS / "pages"
REPO = ROOT.parents[1]
#: The production story payload the scene items are laid on (a captured golden turn).
SCENE_TEMPLATE = REPO / "tests" / "prompt_regression" / "cases" / "turn-a1-reason-ignored.json"
WORLD = REPO / "app" / "data" / "season" / "s1" / "world.json"
UNITS = REPO / "app" / "data" / "grammar_review"
#: The keys of a cast member the story payload carries (the template's own).
CAST_KEYS = (
    "id", "name", "role", "personality", "wants", "speech_pattern", "contradiction",
    "secret", "flaw", "dynamic_with_user", "register_with_user", "gender",
)
#: The acknowledgements a Courrier reply falls back to when nothing was generated.
COURRIER_STOCK = ("je l'ai bien lu", "il me manque un détail concret")


# ---------------------------------------------------------------------------
# Gold sets
# ---------------------------------------------------------------------------


def load_set(surface: str) -> dict:
    return json.loads((SETS / f"{surface}.json").read_text(encoding="utf-8"))


def load_items(surface: str, ids: list[str] | None = None) -> list[dict]:
    """The set's items, each with the set's ``defaults`` filled in."""

    data = load_set(surface)
    defaults = data.get("defaults") or {}
    items = [{**json.loads(json.dumps(defaults)), **item} for item in data["items"]]
    return [item for item in items if not ids or item["id"] in ids]


@contextmanager
def _patched(target: Any, name: str, value: Any):
    old = getattr(target, name)
    setattr(target, name, value)
    try:
        yield
    finally:
        setattr(target, name, old)


# ---------------------------------------------------------------------------
# Scene answer: the reply lanes (tutor + voice)
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _world_cast() -> dict[str, dict]:
    world = json.loads(WORLD.read_text(encoding="utf-8"))
    return {member["id"]: member for member in world["cast"]}


def scene_payload(item: dict) -> dict:
    """The turn payload ``run_reply_lanes`` gets: the captured template with this
    item's character (from the season's world bible), scene, history and answer."""

    template = json.loads(SCENE_TEMPLATE.read_text(encoding="utf-8"))["input"]["payload"]
    payload = json.loads(json.dumps(template))
    character_id = item["character_id"]
    member = _world_cast()[character_id]
    cast_entry = {key: member[key] for key in CAST_KEYS if member.get(key) is not None}
    # The bible writes a sentence («vous — theatrical … until T3»); the engine carries the word.
    declared = str(item.get("register") or member.get("register_with_user") or "tu")
    cast_entry["register_with_user"] = "vous" if declared.strip().lower().startswith("vous") else "tu"
    cast_entry["register_note"] = payload["story"]["world"]["cast"][0].get("register_note")
    story = payload["story"]
    story["level"] = item.get("level", "A1")
    story["world"]["cast"] = [cast_entry]
    story["moods"] = {character_id: {}}
    story["relationships"] = {character_id: {"register": cast_entry["register_with_user"], "closeness": 1}}
    story["secrets"] = {character_id: "hidden"}
    scene = {**payload["scene"], **item["scene"], "character_id": character_id, "panels": []}
    payload["scene"] = scene
    payload["history"] = list(item.get("history") or [])
    payload["learner_text"] = item["learner_text"]
    payload["turns_left"] = item.get("turns_left", 1)
    return payload


def run_scene(item: dict, client: Any) -> dict:
    from app.services import living_story as engine
    from app.services import story_lanes as lanes

    payload = scene_payload(item)
    with _patched(engine, "_client", lambda: client):
        try:
            result = lanes.run_reply_lanes(payload, deadline=time.monotonic() + 120, lexical=None)
        except engine.StoryUnavailable as exc:
            return {"failure": str(exc)}
    tutor, voice = result.tutor, result.voice
    return {
        "failure": None,
        "reply_fr": voice.reply_fr,
        "needs_clarification": voice.needs_clarification,
        "outcome": tutor.outcome,
        "evidence_quotes": list(tutor.evidence_quotes),
        "correction": (
            {
                "span": tutor.correction_span_fr,
                "fix": tutor.correction_fr,
                "note": tutor.correction_note_native,
            }
            if (tutor.correction_fr or tutor.correction_span_fr)
            else None
        ),
        "gated": list(result.gated),
    }


# ---------------------------------------------------------------------------
# La Forge free text: the Atelier corrector's sentence round + the second-check merge
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _units() -> dict[str, dict]:
    units: dict[str, dict] = {}
    for path in sorted(UNITS.glob("units_*.json")):
        for unit in json.loads(path.read_text(encoding="utf-8"))["units"]:
            units[unit["external_id"]] = unit
    return units


def make_concept(external_id: str, concept_id: int = 1):
    from app.db.models.grammar import GrammarConcept

    unit = _units()[external_id]
    return GrammarConcept(
        id=concept_id,
        external_id=external_id,
        language="fr",
        name=unit["name_fr"],
        level=unit["cefr_level"],
        category=unit["category"],
        subskill=unit.get("subskill"),
        core_rule=unit["core_rule"],
        description=unit.get("when_to_use"),
    )


def forge_prompt_payload(item: dict) -> dict:
    task = {
        "id": item["id"],
        "type": item.get("type", "translate"),
        "instruction": item.get("instruction", "Write it in French."),
        "prompt": item["prompt"],
        "example_answer": item["example_answer"],
        "accepted_answers": list(item.get("accepted_answers") or []),
        "lesson_external_id": item["concept"],
    }
    return {"round": "sentence", "mode": "sentence", "id": item["id"], "items": [task]}


def _atelier_service(client: Any, concept: Any):
    from app.services import atelier as at

    svc = at.AtelierCorrectionService.__new__(at.AtelierCorrectionService)
    svc.db = _NoDB(concept)
    svc.llm_service = client
    svc._llm_unavailable = False
    svc._llm_failure_reason = None
    svc._answer_truncated = False
    svc._cost_user_id = None
    svc._cost_session_id = None
    svc._learner_native = "en"
    svc.explanation_language = at.DEFAULT_GLOSS_LANGUAGE
    svc._record_correction_cost = lambda result: None  # no ledger row outside production
    return svc


def run_forge(item: dict, client: Any) -> dict:
    from app.services import atelier as at

    concept = make_concept(item["concept"])
    svc = _atelier_service(client, concept)
    prompt_payload = forge_prompt_payload(item)
    answer_payload = {"text": item["learner_text"]}
    common = {
        "concept": concept, "round_name": "sentence", "mode": "sentence",
        "prompt_payload": prompt_payload, "answer_payload": answer_payload, "session": None,
    }
    local = svc._correct_for_round(**common, force_llm=False)
    ai = svc._correct_for_round(**common, force_llm=True)
    fallback = bool((ai.get("correction_debug") or {}).get("fallback_used"))
    if fallback:
        final = local
    else:
        final = svc._merge_relecture(
            "sentence", local, ai,
            learner_text=item["learner_text"],
            accepted=at._accepted_answers(prompt_payload),
            accents=at._free_answer_accents(concept, prompt_payload),
        )
    return {
        "failure": "second check stopped (fallback)" if fallback else None,
        "verdict": final.get("verdict"),
        "passes": at._verdict_passes(final.get("verdict")),
        "corrected_answer": final.get("corrected_answer"),
        "errata": [_erratum(e) for e in final.get("errata") or [] if isinstance(e, dict)],
        "notes": list(final.get("notes_native") or []) + list(final.get("style_notes_native") or []),
    }


def _erratum(raw: dict) -> dict:
    keys = ("learner_text", "corrected_target", "why_wrong", "repair_hint", "display_label", "task_error_type")
    return {key: raw.get(key) for key in keys if raw.get(key)}


# ---------------------------------------------------------------------------
# Courrier: the correspondent's reply, and the correction under the letter
# ---------------------------------------------------------------------------


def make_mission(item: dict):
    from app.db.models.mission import RealWorldMission

    corr = item["correspondent"]
    register = corr.get("register", "tu")
    payload = {
        "mission_format": "chat_message",
        "target_register": register,
        "success_objectives": list(item.get("goals") or []),
        "messenger": {
            "contact_name": corr["name"],
            "contact_role": corr.get("role", ""),
            "target_register": register,
            "register": register,
            "opening_message": corr["letter"],
        },
        "conversation_opening": corr["letter"],
    }
    return RealWorldMission(
        title=item.get("title") or f"Un mot de {corr['name']}",
        brief=item.get("brief") or corr["letter"],
        status="active",
        cadence="daily",
        mission_type="serial",
        prompt_payload=payload,
        objectives=[],
        source_snapshot={},
        selected_concept_ids=[],
        target_errata_ids=[],
        target_vocabulary_ids=[],
        stakes_level=1,
    )


def _learner(item: dict):
    return SimpleNamespace(id=None, native_language="en", proficiency_level=item.get("level", "A1"))


class _NoDB:
    """The services' ``db``: every write is dropped, a lookup finds only the item's
    own grammar concept."""

    def __init__(self, concept: Any = None) -> None:
        self._concept = concept

    def get(self, model: Any, ident: Any) -> Any:
        concept = self._concept
        if concept is not None and isinstance(concept, model) and str(ident) == str(concept.id):
            return concept
        return None

    def query(self, *args: Any, **kwargs: Any) -> _NoRows:
        return _NoRows()

    def execute(self, *args: Any, **kwargs: Any) -> _NoRows:
        return _NoRows()

    def __getattr__(self, name: str) -> Callable[..., Any]:
        def nothing(*args: Any, **kwargs: Any) -> Any:
            return None

        return nothing


class _NoRows:
    """A query (or result) that matches nothing, however it is filtered."""

    _EMPTY = {"first": None, "one_or_none": None, "scalar": None, "scalar_one_or_none": None,
              "all": [], "scalars": None, "count": 0}

    def __getattr__(self, name: str) -> Callable[..., Any]:
        if name in self._EMPTY:
            value = self._EMPTY[name]
            return lambda *a, **k: (_NoRows() if name == "scalars" else value)
        return lambda *a, **k: self

    def __iter__(self):
        return iter(())


@contextmanager
def _mission_sandbox(item: dict):
    from app.services import missions

    with ExitStack() as stack:
        stack.enter_context(_patched(missions, "_record_mission_llm_cost", lambda *a, **k: None))
        stack.enter_context(_patched(missions, "_learner_level_code", lambda db, user: item.get("level", "A1")))
        yield missions


class _Answered:
    """Counts the model answers that came back (a refused or failed call is not one)."""

    def __init__(self, inner: Any) -> None:
        self.inner = inner
        self.answers = 0

    def generate_chat_completion(self, messages, **kwargs):
        result = self.inner.generate_chat_completion(messages, **kwargs)
        self.answers += 1
        return result

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)


def run_courrier(item: dict, client: Any) -> dict:
    counted = _Answered(client)
    with _mission_sandbox(item) as missions:
        service = missions.MissionConversationService(_NoDB(), llm_service=counted)
        reply = service.respond(user=_learner(item), mission=make_mission(item), user_text=item["learner_text"])
    folded = (reply or "").casefold()
    stock = next((line for line in COURRIER_STOCK if line in folded), None)
    failure = None
    if not counted.answers:
        failure = "the model did not answer (timeout or error): the local fallback was shown"
    elif stock:
        failure = f"stock acknowledgement ({stock!r})"
    return {"failure": failure, "reply_fr": reply}


def run_correction(item: dict, client: Any) -> dict:
    with _mission_sandbox(item) as missions:
        service = missions.MissionCorrectionService(_NoDB(), llm_service=client)
        correction = service.correct_submission(
            user=_learner(item), mission=make_mission(item), text=item["learner_text"], mode="chat",
            near_realtime=False,
        )
    debug = correction.get("correction_debug") or {}
    return {
        "failure": "model correction did not complete (fallback)" if debug.get("fallback_used") else None,
        "corrected_answer": correction.get("corrected_answer"),
        "errata": [_erratum(e) for e in correction.get("errata") or [] if isinstance(e, dict)],
    }


# ---------------------------------------------------------------------------
# The night writer's page: story_split's planner, author and aids, the story critic and
# the scene guards, through the production retry loop (``living_story._approved``)
# ---------------------------------------------------------------------------

#: The prefetch's budget for one page written ahead of time.
PAGE_BUDGET_SECONDS = 330


def page_context(item: dict) -> dict:
    """The item's captured ``story_context`` with its season runtime handle rebuilt."""

    from app.services.season.format import load_season

    context = json.loads((PAGES / f"{item['id']}.json").read_text(encoding="utf-8"))
    context.pop("_captured", None)
    today = context.pop("_season", None)
    if today:
        context["_season"] = SimpleNamespace(
            season=load_season(today["season_id"]), flags=dict(today["flags"]), seed=today["seed"]
        )
    return context


def page_lines(draft: Any, context: dict) -> list[str]:
    """The page as the live-read transcripts write it (``season.transcript``)."""

    from app.services.season.transcript import render_generated_day

    names = {
        str(member.get("id")): str(member.get("name") or member.get("id"))
        for member in ((context.get("world") or {}).get("cast") or [])
        if isinstance(member, dict)
    }
    lines = render_generated_day(draft.model_dump(mode="json"), [], {}, names=names)
    return [line for line in lines if not line.startswith("*Checklist")]


def _spent(client: Any) -> float | None:
    """What a paid run's meter has spent so far; ``None`` for a fake."""

    value = getattr(client, "spent_usd", None)
    return float(value) if isinstance(value, int | float) else None


def _cost(client: Any, before: float | None, usage: list | None = None) -> float:
    """What one page or act cost: the meter's own count when the run is paid (every call,
    the critic's and a refused attempt's included), else the usage the engine recorded."""

    from app.services import living_story as engine

    after = _spent(client)
    if before is not None and after is not None:
        return round(after - before, 4)
    return round(engine.usage_cost_usd(usage or []), 4)


def _attempts(usage: list) -> int:
    return len({entry.get("attempt") for entry in usage if isinstance(entry, dict)}) or 1


def _write_page(context: dict, client: Any) -> tuple[dict, Any]:
    """The page written ahead of time on ``context``, as the prefetch writes it:
    ``(output, draft)``, the draft ``None`` when the day is lost."""

    from uuid import uuid4

    from app.services import living_story as engine
    from app.services import story_split

    reviews: list[dict] = []
    before = _spent(client)
    started = time.monotonic()
    with _patched(engine, "_client", lambda: client), engine.written_ahead_of_time():
        if not story_split.applies(context):
            return {"failure": "story_split does not apply to this context", "seconds": 0.0}, None
        try:
            draft, usage = engine._approved(
                engine.DIRECTOR,
                engine._prompt_payload(context),
                engine.SceneDraft,
                lambda p: engine._validate_scene(p, context),
                db=_NoDB(),
                user=SimpleNamespace(id=uuid4()),
                candidates=1,
                choose=lambda p: engine._scene_score(p, context),
                story_review=engine._season_story_review(context, reviews),
                digest=lambda p: engine.scene_digest(p, context),
                draw=story_split.draw(context),
            )
        except engine.StoryUnavailable as exc:
            return {
                "failure": f"lost day: {exc}", "seconds": round(time.monotonic() - started, 1),
                "reviews": len(reviews), "cost_usd": _cost(client, before),
            }, None
    seconds = round(time.monotonic() - started, 1)
    output = {
        "failure": None if seconds <= PAGE_BUDGET_SECONDS else f"lost day: {seconds:.0f} s, over the {PAGE_BUDGET_SECONDS} s budget",
        "seconds": seconds,
        "cost_usd": _cost(client, before, usage),
        "title": draft.title_fr,
        "objective": draft.objective_native,
        "lead": draft.character_id,
        "place": draft.location_id,
        "page_lines": page_lines(draft, context),
        "attempts": _attempts(usage),
        "model_calls": len(usage),
        "reviews": len(reviews),
    }
    return output, draft


def run_page(item: dict, client: Any) -> dict:
    return _write_page(page_context(item), client)[0]


# ---------------------------------------------------------------------------
# A day of acts (Phase 2 «Folge in Akten»): the page, then each later act the day plays,
# written as the night writes it (``living_story.draft_later_act``)
# ---------------------------------------------------------------------------

#: The rhythm a day of acts is measured on: the one that plays the most acts.
DAY_RHYTHM = "intensif"
#: The most one act cost on the production loop (2 Nov, Opus 5.5: US$0.68), and what the
#: judge's readings of a day may cost at worst (three readings by the page judge). A paid
#: run writes an act only while both still fit under its cap, so the day it wrote is
#: always judged.
ACT_AT_MOST_USD = 0.70
DAY_JUDGE_USD = 0.15


def day_roles(item: dict, context: dict | None = None) -> list[str]:
    """The later acts the day plays, in the order the night writes them
    (``story_acts.WRITING_ORDER``, «Le soir» first): what ``journey_planner.acts_to_write``
    gives an Intensif learner at the item's level, less what the chapter's shape does
    not play (``living_story.ACT_ROLES_BY_SHAPE``)."""

    from app.services import living_story as engine
    from app.services.journey_planner import acts_to_write
    from app.services.journey_rhythm import RHYTHM_BUDGET_SECONDS
    from app.services.story_acts import WRITING_ORDER

    planned = set(acts_to_write(budget_seconds=RHYTHM_BUDGET_SECONDS[DAY_RHYTHM], band=item["level"]))
    roles = [str(role) for role in WRITING_ORDER if role in planned]
    if context is not None:
        kept = engine.ACT_ROLES_BY_SHAPE.get(engine.page_shape(context))
        roles = [role for role in roles if kept is None or role in kept]
    return roles


def _room_for_an_act(client: Any) -> bool:
    cap = getattr(client, "cap_usd", None)
    spent = _spent(client)
    if not isinstance(cap, int | float) or spent is None or cap == float("inf"):
        return True
    return spent + ACT_AT_MOST_USD + DAY_JUDGE_USD <= cap


def _write_act(context: dict, first: dict, role: str, client: Any) -> dict:
    """One later act against the day's first act (``first``, its ``SceneDraft`` as
    stored), as ``story_acts.write_act`` has it written at night. An act the critic
    refuses, or one over the 330 s a night task has, is dropped."""

    from uuid import uuid4

    from app.services import living_story as engine

    act_context = engine.later_act_context(context, first, role)
    reviews: list[dict] = []
    before = _spent(client)
    started = time.monotonic()
    with _patched(engine, "_client", lambda: client), engine.written_ahead_of_time():
        try:
            act, usage = engine.draft_later_act(
                act_context, db=_NoDB(), user=SimpleNamespace(id=uuid4()), reviews=reviews
            )
        except engine.StoryUnavailable as exc:
            return {
                "role": role, "failure": f"dropped: {exc}", "hint": compact(exc.hint, 300),
                "seconds": round(time.monotonic() - started, 1), "cost_usd": _cost(client, before),
                "reviews": len(reviews),
            }
    seconds = round(time.monotonic() - started, 1)
    return {
        "role": role,
        "failure": None if seconds <= PAGE_BUDGET_SECONDS else f"dropped: {seconds:.0f} s, over the {PAGE_BUDGET_SECONDS} s a night task has",
        "seconds": seconds,
        "cost_usd": _cost(client, before, usage),
        "title": act.title_fr,
        "objective": act.objective_native,
        "lead": act.character_id,
        "place": act.location_id,
        "page_lines": page_lines(act, act_context),
        "attempts": _attempts(usage),
        "model_calls": len(usage),
        "reviews": len(reviews),
    }


def run_day(item: dict, client: Any) -> dict:
    """The day's page («Le fil»), then each later act the day plays (:func:`day_roles`),
    written in the night's order and returned in play order (``ACT_ROLE_ORDER``). As at
    night, a lost page loses the day, and an act is written only once the one before it
    stands (``journey_prefetch.write_story_acts``): after a dropped act the rest are
    ``not_run``, as are the acts a paid run's cap cannot hold any more. A ``not_run`` act
    says nothing of the writer and is not scored."""

    from app.services.journey_contracts import ACT_ROLE_ORDER

    context = page_context({**item, "id": item["page"]})
    page, draft = _write_page(context, client)
    first = {"role": "fil", **page}
    if draft is None or page.get("failure"):
        return {"failure": page["failure"], "seconds": page.get("seconds", 0.0), "acts": [first]}
    written: dict[str, dict] = {}
    stored = draft.model_dump(mode="json")
    stopped = ""
    for role in day_roles(item, context):
        if not stopped and not _room_for_an_act(client):
            stopped = "the run's spending cap (what was written is kept for the judge)"
        if stopped:
            written[role] = {"role": role, "failure": None, "not_run": stopped}
            continue
        written[role] = _write_act(context, stored, role, client)
        if written[role].get("failure"):
            stopped = "the act before it was dropped, and the night writes no act after a dropped one"
    acts = [first, *(written[str(role)] for role in ACT_ROLE_ORDER if str(role) in written)]
    return {
        "failure": None,
        "seconds": round(sum(float(act.get("seconds") or 0.0) for act in acts), 1),
        "cost_usd": round(sum(float(act.get("cost_usd") or 0.0) for act in acts), 4),
        "acts": acts,
    }


SURFACES: dict[str, Callable[[dict, Any], dict]] = {
    "scene": run_scene,
    "forge": run_forge,
    "courrier": run_courrier,
    "correction": run_correction,
    "page": run_page,
    "day": run_day,
}


# ---------------------------------------------------------------------------
# The code-decided criteria
# ---------------------------------------------------------------------------


def _fold(text: Any) -> str:
    from app.services import living_story as engine

    return engine._folded(str(text or ""))


def checks(surface: str, item: dict, output: dict) -> dict[str, tuple[str, str]]:
    """``{criterion id: (pass|fail|na, reason)}`` for the ``check`` criteria."""

    failed = output.get("failure")
    served = ("fail", str(failed)) if failed else ("pass", "")
    truth = item.get("truth") or {}
    if surface == "scene":
        learner = _fold(" ".join([item["learner_text"], *[h.get("learner", "") for h in item.get("history") or []]]))
        invented = [q for q in output.get("evidence_quotes") or [] if _fold(q) not in learner]
        return {
            "served": served,
            "quotes_real": ("na", "no grade") if failed else (("fail", f"invented: {invented}") if invented else ("pass", "")),
        }
    if surface in ("courrier", "page"):
        return {"served": served}
    if surface == "day":
        # One verdict per act; an act the cap left unwritten says nothing and is not counted.
        out: dict[str, tuple[str, str]] = {}
        for act in output.get("acts") or []:
            if act.get("not_run"):
                continue
            out[f"{act['role']}.served"] = ("fail", str(act["failure"])) if act.get("failure") else ("pass", "")
        return out
    if surface == "forge":
        want = bool(truth.get("correct"))
        got = bool(output.get("passes"))
        verdict = ("pass", "") if got == want else ("fail", f"shown {'right' if got else 'not yet'}, should be {'right' if want else 'not yet'}")
        return {"checked": served, "verdict_right": verdict}
    if surface == "correction":
        want_clean = bool(truth.get("correct"))
        errata = output.get("errata") or []
        if failed:
            verdict = ("na", "no model correction")
        elif want_clean:
            verdict = ("pass", "") if not errata else ("fail", f"{len(errata)} correction(s) on a correct sentence")
        else:
            verdict = ("pass", "") if errata else ("fail", "no correction for a sentence with errors")
        text = _fold(item["learner_text"])
        outside = [e.get("learner_text") for e in errata if e.get("learner_text") and _fold(e["learner_text"]) not in text]
        spans = ("na", "no corrections") if not errata else (("fail", f"not in the sentence: {outside}") if outside else ("pass", ""))
        return {"checked": served, "verdict_right": verdict, "spans_real": spans}
    raise ValueError(surface)


_WS = re.compile(r"\s+")


def compact(value: Any, limit: int = 400) -> str:
    text = _WS.sub(" ", str(value or "")).strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"
