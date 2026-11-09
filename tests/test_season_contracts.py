"""S5 stage 1 · every guard that refuses model output is proven satisfiable by the
data and the prompt that feed it.

The season-end walk of 9 Nov 2026 (draft PR #649) found seven places where a guard
and the data it guards had drifted apart. The fake provider answers whatever it is
asked, so none of them showed in a green suite; each was found by a learner. These
tests read the SHIPPED prompts and season data, not fixtures, so the next drift fails
here instead.
"""

from __future__ import annotations

import ast
import copy
import importlib
import json
import re
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.config import settings
from app.services import living_story as engine
from app.services import season_writer
from app.services.season import agency
from app.services.season.format import Hook, Turn, iter_movements, load_season
from app.services.season.page import _Ctx, _panels
from app.services.season.turns import reaction_lines, reaction_text
from app.services.season.world import built_stages, season_world_bible

ROOT = Path(__file__).resolve().parents[1]
SEASON = "s1"


# ---------------------------------------------------------------------------
# 1 · a json_object call carries the word «JSON»
# ---------------------------------------------------------------------------


def _json_call_sites() -> list[tuple[str, int, ast.expr]]:
    """Every ``_json_call(...)`` in ``app/``: (module, line, the system prompt argument)."""

    sites = []
    for path in sorted((ROOT / "app").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        module = ".".join(path.relative_to(ROOT).with_suffix("").parts)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            if name == "_json_call":
                sites.append((module, node.lineno, node.args[0]))
    return sites


def test_every_named_prompt_sent_as_a_json_object_says_json():
    """OpenAI answers 400 to ``response_format=json_object`` unless the messages say
    «json»: the season critic was refused on every review (walk #649, finding 1)."""

    sites = _json_call_sites()
    assert len(sites) >= 10, "the scan must find the story engine's callers"
    checked, missing = 0, []
    for module, line, arg in sites:
        if not isinstance(arg, ast.Name):
            continue  # built per call: covered by the call itself (next test)
        value = getattr(importlib.import_module(module), arg.id, None)
        if not isinstance(value, str):
            continue  # a local variable: covered by the call itself
        checked += 1
        if not re.search("json", value, re.IGNORECASE):
            missing.append(f"{module}:{line} {arg.id}")
    assert checked >= 8
    assert missing == []


def test_a_json_object_call_always_says_json_whatever_the_caller_passed(monkeypatch):
    """The prompts built per call (``planner_system(context)``, a lane's ``system``)
    cannot be read statically: the call itself guarantees the word."""

    sent = {}

    class Client:
        def generate_chat_completion(self, messages, **kwargs):
            sent["system"] = kwargs.get("system_prompt") or ""
            sent["messages"] = messages
            sent["response_format"] = kwargs.get("response_format")
            return SimpleNamespace(
                content='{"accepted": true, "issues": []}', model="m", provider="p",
                total_tokens=1, cost=0.0, finish_reason="stop",
            )

    monkeypatch.setattr(engine, "_client", lambda: Client())
    import time

    review, _ = engine._json_call(
        "Check the proposal. List concrete issues.", {"proposal": {}},
        season_writer.SeasonReview, deadline=time.monotonic() + 30,
    )
    assert review.accepted is True
    assert sent["response_format"] == {"type": "json_object"}
    assert re.search("json", sent["system"], re.IGNORECASE), sent["system"]


# ---------------------------------------------------------------------------
# 2 · an identifier pattern is stated where the identifier is produced
# ---------------------------------------------------------------------------


def test_the_season_writer_states_the_arc_id_pattern_it_enforces():
    assert season_writer._SLUG.pattern in season_writer.SEASON_WRITER


def test_the_agency_rules_state_the_id_pattern_they_enforce():
    assert agency._SLUG.pattern in json.dumps(agency.AGENCY_RULES)


def _draft(arc_ids: list[str]) -> season_writer.SeasonDraft:
    return season_writer.SeasonDraft.model_validate(
        {
            "title_fr": "Le pain du dimanche",
            "logline": "A season grown from the learner's own open rows.",
            "logline_fr": "Une saison qui part de ta vie au quartier.",
            "your_arc": "From guest to the one who keeps the bread.",
            "first_episode_seed": "Sunday morning, the bakery is closed.",
            "arcs": [
                {
                    "id": arc_id,
                    "title_fr": "Le pain",
                    "characters": ["user"],
                    "grounded_in": "e1:plant",
                    "stages": [
                        {"id": f"s{i}", "summary": "One sentence of the stage."} for i in range(3)
                    ],
                }
                for arc_id in arc_ids
            ],
            "open_threads": [
                {"text": "Will the bread come?", "text_fr": "Le pain arrivera-t-il ?", "grounded_in": "e1:plant"}
            ]
            * 3,
        }
    )


def test_the_writer_normalises_a_hyphenated_arc_id_before_validating():
    """B1's first draft was refused for ``arc_id:unlabeled-key`` (walk #649)."""

    draft = season_writer.normalised_draft(_draft(["unlabeled-key", "Rue-De-Lancry", "le_pain"]))
    season_writer.validate_season(
        draft, material=[{"id": "e1:plant"}], cast_ids=[]
    )
    assert [arc.id for arc in draft.arcs] == ["unlabeled_key", "rue_de_lancry", "le_pain"]


def test_a_generated_agency_contract_keeps_a_hyphenated_id():
    raw = {
        "speaker": "lila_bonnet",
        "subjects": {"keep-name": "Whether Lila may print the learner's name."},
        "conditions": {"first-name-only": "Only the first name."},
        "effects": [
            {
                "id": "name-printed",
                "actions": ["accept"],
                "subject": "keep-name",
                "allowed_conditions": ["first-name-only"],
                "outcome_en": "Lila prints the name.",
            },
            {
                "id": "name_kept",
                "actions": ["decline"],
                "subject": "keep-name",
                "outcome_en": "Lila keeps the name out.",
            },
        ],
    }
    contract = agency.generated_contract(SEASON, "g1", None, raw)
    assert contract is not None
    assert set(contract.subjects) == {"keep_name"}
    assert set(contract.conditions) == {"first_name_only"}
    assert [spec.id for spec in contract.effects] == ["name_printed", "name_kept"]
    assert contract.effects[0].allowed_conditions == ["first_name_only"]


# ---------------------------------------------------------------------------
# 3 · every place a page is sent to can be entered
# ---------------------------------------------------------------------------


def _locations(value) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key in ("location_id", "location") and isinstance(item, str) and item:
                found.add(item)
            else:
                found |= _locations(item)
    elif isinstance(value, list):
        for item in value:
            found |= _locations(item)
    return found


def _closing_hook_places() -> set[str]:
    """The places named by the hook the season ends on (its last tentpole's hooks)."""

    season = load_season(SEASON)
    last = [segment.id for segment in season.segments if segment.kind == "tentpole"][-1]
    tentpole = season.tentpoles[last]
    places = set()
    for day in tentpole.days:
        for movement in day.movements:
            if isinstance(movement, Hook) and movement.panel.location_id:
                places.add(movement.panel.location_id)
    return places


def test_every_place_a_generated_page_is_sent_to_is_built():
    """5 of 8 interlude beats named places a page may not be set in since ``3e8e19f3``;
    the writer obeyed the beat and was refused (8 drafts at ``buttes_chaumont`` on B1)."""

    world = season_world_bible(SEASON)
    built = set(built_stages(SEASON))
    assert built, "the forge's register is shipped"
    beats = {beat["id"]: beat.get("location_id") for beat in engine.interlude_beats(world)}
    unbuilt_beats = {beat: place for beat, place in beats.items() if place and place not in built}
    assert unbuilt_beats == {}
    arcs = _locations(world.get("season_arcs") or [])
    assert arcs - built == set()


def test_the_closing_hook_names_a_built_place_or_one_marked_to_be_built():
    """Rue de Lancry, the season's closing hook, is promised and can never be entered
    (walk #649): it is marked as not built, and the writer is told not to set a page there."""

    from app.services.season.world import unbuilt_places

    built = set(built_stages(SEASON))
    marked = unbuilt_places(SEASON)
    hooks = _closing_hook_places()
    assert hooks, "the season ends on a hook that names a place"
    for place in hooks:
        assert place in built or place in marked, place
    assert not (set(marked) & built), "a place is either built or to be built"
    from app.services.season.epilogue import continuation_rules

    rules = " ".join(continuation_rules(SEASON))
    for place in hooks - built:
        assert marked[place] in rules, f"the continuation is not told {place} cannot be entered"


# ---------------------------------------------------------------------------
# 4 · «vous» is refused by who it addresses, not by the word
# ---------------------------------------------------------------------------


def _task(line: str):
    return SimpleNamespace(objective_native=line, hint_native="")


@pytest.mark.parametrize(
    "line",
    [
        "Dis à Gus si tu préfères garder cette histoire entre vous, et pourquoi.",
        "Propose à Gus un nom pour votre souvenir de la table.",
        "Imagine avec Romy ce que vous feriez si le soleil revenait.",
    ],
)
def test_a_plural_vous_in_a_tu_task_is_accepted(line):
    engine._check_task_tutoiement(_task(line))


@pytest.mark.parametrize(
    "line",
    [
        "Votre nom, pour Romy, et votre ville.",
        "Dites à Romy votre nom.",
        "Vous pouvez demander le prix à Gus.",
        "N'oubliez pas de répondre à Lila.",
    ],
)
def test_a_task_that_says_vous_to_the_learner_is_still_refused(line):
    with pytest.raises(engine.StoryUnavailable, match="task_says_vous"):
        engine._check_task_tutoiement(_task(line))


# ---------------------------------------------------------------------------
# 5 · the interlude beat is the open chapter's own
# ---------------------------------------------------------------------------


def test_the_interlude_beat_does_not_change_while_its_chapter_stays_open(db_session, monkeypatch):
    """The director was dealt the beat from ``chapters_total`` after the chapter had
    already counted itself, so the second day of an interlude chapter got another beat."""

    from tests.test_living_story_address import make_user

    user = make_user(db_session)
    thread_id = uuid4()
    seed = str(thread_id)
    # A chapter index whose next deal is another beat, or the test proves nothing.
    opened_at = next(
        index for index in range(40)
        if engine.interlude_beat(seed, index, {})["id"] != engine.interlude_beat(seed, index + 1, {})["id"]
    )
    stored = engine.interlude_beat(seed, opened_at, {})
    live = {
        "day_index": 40,
        "chapters_total": opened_at + 1,
        "season_chapters": 3,
        "season_stage": "interlude",
        "chapter": {
            "id": "chapter-interlude",
            "title_fr": "Un soir ordinaire",
            "dramatic_question": "Qui ferme le bar ?",
            "shape": engine.DEFAULT_SHAPE,
            "scene_count": 1,
            "resolved_commitments": 0,
            "resolved": False,
            "beats": ["setup"],
            "interlude": True,
            "interlude_beat_id": stored["id"],
        },
    }
    thread = SimpleNamespace(
        id=thread_id, world_bible={}, state={engine.STATE_KEY: live}, user_id=user.id,
        current_episode_index=0,
    )
    monkeypatch.setattr(engine, "_active_thread", lambda db, u: thread)
    context = engine.story_context(db_session, user)
    interlude = context["season"]["interlude"]
    assert interlude is not None
    assert interlude["id"] == stored["id"]


# ---------------------------------------------------------------------------
# 6 · every authored reply survives for its own turn
# ---------------------------------------------------------------------------

#: Lines that are not a reply from the person the learner answers.
_NOT_SPOKEN = {"caption", "toi", "letter", "card"}


class _EveryLine(_Ctx):
    """Every authored line shown: the contract is about the data, not one route."""

    def ok(self, cond) -> bool:
        return True


def _rendered(beats) -> list[dict]:
    return _panels(beats, _EveryLine(flags={}, band="A2", language="en", neutral=False, names={}))


def _authored_turns():
    season = load_season(SEASON)
    for tentpole in season.tentpoles.values():
        for day in tentpole.days:
            for movement in iter_movements(day.movements):
                if isinstance(movement, Turn):
                    yield f"{tentpole.id}.{day.day}{day.variant or ''}", movement
        for movements in (tentpole.shared or {}).values():
            for movement in iter_movements(movements):
                if isinstance(movement, Turn):
                    yield f"{tentpole.id}.shared", movement


def test_every_authored_reply_survives_for_its_own_turn():
    """The season's biggest choice (``ep3.b.turn``, an SMS from Lila) was answered with
    «…»: ``reaction_lines`` dropped every line that was not ``speech``."""

    turns = list(_authored_turns())
    ids = {turn.id for _, turn in turns}
    assert {"ep1.b.turn", "ep3.b.turn"} <= ids
    lost = []
    for where, turn in turns:
        for reply in turn.replies:
            panels = _rendered(reply.beats)
            said = [
                line for panel in panels for line in panel["lines"]
                if line.get("text_fr") and line.get("who") not in _NOT_SPOKEN
            ]
            if not said:
                continue
            kept = {row["text_fr"] for row in reaction_lines(panels, addressee=turn.to)}
            text = reaction_text(panels, addressee=turn.to, labelled=False)
            for line in said:
                if line["text_fr"] not in kept or line["text_fr"] not in text:
                    lost.append(f"{where} {turn.id}.{reply.id}: {line['who']} «{line['text_fr'][:40]}»")
    assert lost == []


def test_an_sms_reply_is_said_by_the_person_the_learner_texts():
    turn = next(turn for _, turn in _authored_turns() if turn.id == "ep3.b.turn")
    reply = next(reply for reply in turn.replies if reply.id == "stay")
    rows = reaction_lines(_rendered(reply.beats), addressee=turn.to)
    assert rows and {row["speaker_id"] for row in rows} == {"lila_bonnet"}


# ---------------------------------------------------------------------------
# 7 · a question the ending decided is not archived as open
# ---------------------------------------------------------------------------


def test_every_season_thread_names_the_flags_that_decide_it():
    world = season_world_bible(SEASON)
    flags = {flag.id for flag in load_season(SEASON).flags}
    threads = engine.season_threads(world)
    assert threads
    for row in threads:
        assert row.get("decided_by"), f"{row['key']} names no flag that decides it"
        assert set(row["decided_by"]) <= flags, row


@pytest.mark.parametrize("ending", ["garder", "partager", "laisser_partir"])
def test_after_the_finale_no_decided_thread_is_archived_open(monkeypatch, ending):
    """B1 sold the café and the reprise asked «L'avenir du Mistral : le garder, le
    changer, ou le laisser partir ?» again (walk #649): season 1's threads stayed
    ``open`` in ``threads_archive`` after the finale."""

    monkeypatch.setattr(settings, "ATELIER_SEASON_WRITER_ENABLED", False)
    world = copy.deepcopy(season_world_bible(SEASON))
    # What the finale leaves in the life (``epilogue.carry_into_live``).
    live = {
        "season_index": 1,
        "world_flags": {"s1.ending": ending, "lila.in_berlin": True},
        "threads": {},
    }
    thread = SimpleNamespace(id="thread-finale", world_bible=world)
    engine.roll_over_season(None, thread, live, day=120, today="2027-01-20")
    archived = {row["key"]: row["state"] for row in live["threads_archive"] if row.get("season") == 1}
    keys = [row["key"] for row in engine.season_threads(world)]
    assert set(keys) <= set(archived)
    assert [key for key in keys if archived[key] == "open"] == []
