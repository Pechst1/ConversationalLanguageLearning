"""#597 (root cause #145) — «Bisher» never recaps a closing caption.

``story_outcome.callback_fr`` is the story's hook, and an authored season page fills
it with its closing caption («Deux clés pour la même porte. À suivre…»). Every reader
that presents the field as *what happened* (the Journal, the next day's «previously»
box, the chronicle, the recap) has to go through one rule,
``closing_filler.scene_fact``. This file pins the walk (day 2 after day 1), the rule
itself, and a source scan that fails when a reader prints the field without it.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path

import pytest

from tests import test_journey_end_to_end as support
from tests.test_season_one import _play, season_on  # noqa: F401 - fixture

assembled_client = support.assembled_client
clock = support.clock
journey_enabled = support.journey_enabled

CAPTION = "Deux clés pour la même porte. À suivre…"
STUB = "Margaux a dû partir avant de répondre."


def _scene(journey: dict) -> dict:
    return next(step for step in journey["steps"] if step["kind"] == "scene")


def test_bisher_no_caption(
    assembled_client, db_session, journey_enabled, clock, season_on  # noqa: F811
):
    provider = season_on
    provider.routes = {"Odile, c'est ma grand-mère.": "a"}
    d = support.Driver(
        assembled_client,
        support.register(assembled_client, f"bisher-{uuid.uuid4()}@example.com", cefr="A1.1"),
        db=db_session,
    )
    d.create()
    d.play(answer="Odile, c'est ma grand-mère.")
    assert d.finish("complete").status_code == 200
    clock.advance(days=1)
    day_two = _play(d, provider, clock, "Odile, c'est ma grand-mère.")
    previously = _scene(day_two)["prompt"].get("previously_fr") or []
    assert not [line for line in previously if "suivre" in line.lower()], (
        f"day 2's «Bisher» recaps a closing caption instead of what happened: {previously}"
    )
    # It falls back to what the scene established (its title), never to nothing and
    # never to the caption.
    assert previously == ["Le mauvais accueil"]


@pytest.mark.parametrize("hook", [CAPTION, STUB], ids=["tease", "stub"])
def test_callback_kept(hook):
    """The relationship memory is what a character may quote later: «À suivre…» is nobody's."""
    from types import SimpleNamespace

    from app.services.serial import SerialThreadService

    def callbacks_after(callback: str) -> list[str]:
        state: dict = {}
        SerialThreadService.__new__(SerialThreadService)._update_relationship_state(
            state=state,
            thread=SimpleNamespace(current_episode_index=0),
            character_id="margaux_barman",
            episode_index=0,
            success=True,
            summary_override="La clé reste chez Margaux.",
            callback_override=callback,
        )
        return state["relationships"]["margaux_barman"].get("callbacks") or []

    assert callbacks_after(hook) == []
    assert callbacks_after("un café en terrasse") == ["un café en terrasse"]


def test_one_rule():
    from app.services.journal import is_closing_filler

    assert is_closing_filler(CAPTION)
    assert is_closing_filler(STUB)
    assert not is_closing_filler("Tu as laissé la clé chez Margaux.")


APP = Path(__file__).resolve().parents[1] / "app"
_READ = re.compile(r"""\.callback_fr\b|get\(["']callback_fr["']\)|\[["']callback_fr["']\]""")

#: Readers that only carry the field from one record to the next (the episode's hook,
#: the serial ledger, a validator that checks its language), or read the *draft's own*
#: callback (a past fact the scene stages: a different field). None of them presents
#: the hook as something that happened; a reader that does goes through ``scene_fact``
#: and is not listed. A new line has to be looked at and added here.
_CARRIERS = {
    ("app/services/daily_journey.py", '"callback_fr": outcome_ref.callback_fr,'),
    # filtered when the PriorConsequence is built
    ("app/services/journey_content.py", 'fields = {"character": prior.character_name, "callback": prior.callback_fr}'),
    ("app/services/journey_conversation.py", "callback_fr=proposal.callback_fr,"),
    ("app/services/journey_conversation.py", "callback=proposal.callback_fr,"),
    ("app/services/season/runtime.py", 'callback_fr=proposal["callback_fr"],'),
    ("app/services/story_lanes.py", "callback_fr=ending.callback_fr,"),
    (
        "app/services/story_lanes.py",
        "written = [turn.resolution_fr, turn.summary_native, turn.callback_fr, *[c.text_fr for c in turn.commitments]]",
    ),
    ("app/services/story_lanes.py", "french = [turn.resolution_fr, turn.callback_fr]"),
    ("app/services/story_lanes.py", "callback_fr=authored.callback_fr,"),
    ("app/services/story_lanes.py", "callback_fr=turn.callback_fr or None,"),
    ("app/services/living_story.py", "callback_fr=turn.callback_fr or None,"),
    ("app/services/living_story.py", "callback_fr=turn.callback_fr,"),
    # serial.py drops a closing line before it is stored as a shared callback
    ("app/services/living_story.py", "callback_override=turn.callback_fr,"),
    # the hook is a teaser by design
    ("app/services/living_story.py", 'episode.hook = {"text": turn.callback_fr, "source_event_id": event_id}'),
    # a contract day writes the fact it kept: the plan's own «what changed», never a hook
    ("app/services/living_story.py", 'turn.callback_fr = ending["fact_fr"]'),
    # the private record; presented through daily_journey's scene_fact
    ("app/services/living_story.py", '"callback_fr": turn.callback_fr or None,'),
    # the scene draft's own callback (a past fact the scene stages), not the outcome's
    ("app/services/living_story.py", "if draft.callback_fr:"),
    (
        "app/services/living_story.py",
        'or _premise_overlap(draft.callback_fr, str(candidate.get("text_fr") or "")) >= CALLBACK_OVERLAP',
    ),
    ("app/services/living_story.py", "draft.callback_ref if draft.callback_fr else None,"),
    ("app/services/living_story.py", "callback_ref=draft.callback_ref if draft.callback_fr else None,"),
    ("app/services/living_story.py", "cues.append(draft.callback_fr)"),
    ("app/services/living_story.py", "draft.callback_ref = _names_agency_callback(draft.callback_fr, context)"),
    ("app/services/living_story.py", "if not _callback_grounded(draft.callback_fr, draft.callback_ref, ledger):"),
    ("app/services/living_story.py", 'f"\\"{_one_line(draft.callback_fr, 90)}\\" is not in this life\'s "'),
    ("app/services/living_story.py", '"callback_staged": bool(draft.callback_fr)'),
}


def test_readers_guarded():
    guarded = ("scene_fact(", "is_closing_filler(")
    unguarded: set[tuple[str, str]] = set()
    for path in sorted(APP.rglob("*.py")):
        if path.name == "closing_filler.py":
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        for number, line in enumerate(lines):
            if not _READ.search(line) or line.lstrip().startswith(("#", '"""')):
                continue
            window = "\n".join(lines[max(0, number - 2) : number + 3])
            if any(token in window for token in guarded):
                continue
            unguarded.add((path.relative_to(APP.parent).as_posix(), line.strip()))
    assert unguarded <= _CARRIERS, (
        "callback_fr is the story's hook and may be a closing caption (#597). A reader "
        "that presents it as what happened takes it through closing_filler.scene_fact; "
        f"one that only carries it is listed in _CARRIERS. Not guarded: {sorted(unguarded - _CARRIERS)}"
    )
