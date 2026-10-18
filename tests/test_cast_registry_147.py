"""ROOT CAUSE #147: the cast is one registry (id, name, gender, face, voice, first day).

The guard: everyone who speaks or is named in the cast intro, the teasers and the
authored days exists in :mod:`app.services.cast_registry`, speakers have a face, the
cast intro lists everyone who speaks on the first day (and names no one before
their day), and a pronoun in a letter follows the registry's gender.
"""
from __future__ import annotations

import json
from collections import defaultdict

from app.services import cast_registry as reg
from app.services import serial_notifications as sn
from app.services.cast_voices import CAST_ALIASES, CAST_VOICES
from app.services.missions import FIRST_LETTERS, REAL_WORLD_MISSION_DOMAINS
from app.services.season.format import SEASON_ROOT
from app.services.season.intro import season_intro
from tests import test_journey_end_to_end as _support
from tests import test_season_one as _season

season_on = _season.season_on  # the fake season provider
assembled_client = _support.assembled_client
clock = _support.clock
journey_enabled = _support.journey_enabled

#: Minor cast whose drawn portraits are not made yet. The test fails the day one
#: gets a face (remove it here) so this list cannot rot into an excuse.
KNOWN_FACELESS = {"bastien_roux", "mme_diallo", "maitre_vasseur"}


def _authored() -> tuple[dict[str, set[tuple[int, str]]], dict[str, set[tuple[int, str]]]]:
    """(who appears in frame or speaks, who speaks) -> the (tentpole, day) pages."""

    seen: dict[str, set[tuple[int, str]]] = defaultdict(set)
    spoke: dict[str, set[tuple[int, str]]] = defaultdict(set)
    for path in sorted((SEASON_ROOT / "s1").glob("t[0-9].json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        number = int(data["number"])
        for day in data.get("days", []):
            page = (number, str(day["day"]))
            for movement in day.get("movements", []):
                for cid in movement.get("in_frame") or []:
                    seen[cid].add(page)
                for line in movement.get("lines") or []:
                    who = line.get("who")
                    if who:
                        seen[who].add(page)
                        spoke[who].add(page)
    return seen, spoke


def test_every_authored_character_is_in_the_registry():
    seen, _ = _authored()
    unknown = {
        cid for cid in seen
        if reg.resolve_id(cid) is None and cid not in reg.NON_PEOPLE and cid not in reg.EXTRAS
    }
    assert not unknown, f"named in the season but missing from the cast registry: {sorted(unknown)}"


def test_every_speaker_has_a_face_and_a_first_day_that_matches_the_story():
    seen, spoke = _authored()
    for cid, pages in seen.items():
        found = reg.member(cid)
        if found is None:
            continue
        assert found.first_day == min(pages), f"{cid}: registry says {found.first_day}, story says {min(pages)}"
    for cid in spoke:
        found = reg.member(cid)
        if found is None:
            continue
        if found.id in KNOWN_FACELESS:
            assert found.face is None, f"{found.id} now has a face: take it off KNOWN_FACELESS"
        else:
            assert found.face, f"{found.id} speaks but has no face"


def test_the_cast_intro_lists_everyone_who_speaks_on_day_one_and_nobody_early():
    _, spoke = _authored()
    intro = season_intro("s1", "en")["cast_intro"]
    listed = {reg.resolve_id(row["character_id"]) for row in intro}
    assert None not in listed
    day_one = {reg.resolve_id(cid) for cid, pages in spoke.items() if (1, "a") in pages} - {None}
    assert day_one <= listed, f"speak on day one but not in the cast intro: {sorted(day_one - listed)}"
    for row in intro:
        found = reg.member(row["character_id"])
        assert found.face, f"{found.id} is in the cast intro without a face"
        assert found.first_day <= (1, "b"), f"{found.id} is introduced on {found.first_day}, not on day one"
        assert row["name"] == found.short_name


def test_teasers_voices_and_portraits_only_name_registered_people():
    for cid in (*sn.MORNING_LINES, *sn.CHARACTER_NAMES, *sn.PORTRAIT_CHARACTERS.values(), *CAST_VOICES):
        assert reg.member(cid), f"{cid} is not in the cast registry"
    for alias in CAST_ALIASES:
        assert reg.resolve_id(alias) == reg.resolve_id(CAST_ALIASES[alias])
    for cid, voice in CAST_VOICES.items():
        assert reg.member(cid).voice == voice
    for cid in sn.MORNING_LINES:
        assert reg.member(cid).face, f"{cid} greets in a teaser but has no face"


def test_94_a_pronoun_in_a_letter_follows_the_registry_gender():
    """M. Marchand is a man: «Elle n'est pas contente» may not sit under his name."""

    assert reg.member("landlord_marchand").pronoun_fr == "Il"
    assert reg.member("camille_marchand").pronoun_fr == "Iel"
    checked = 0
    for domain in (*REAL_WORLD_MISSION_DOMAINS, *FIRST_LETTERS.values()):
        found = reg.member(domain.get("character_id")) or reg.member(
            "landlord_marchand" if domain.get("contact_name") == "M. Marchand" else str(domain.get("contact_name") or "")
        )
        twist = str(domain.get("twist") or "")
        if found is None or not twist.startswith(("Il ", "Elle ")):
            continue
        checked += 1
        assert twist.startswith(found.pronoun_fr + " "), (domain["domain"], found.id, twist)
    assert checked >= 1  # Romy's letter


def test_94_the_landlord_task_states_the_radiator_problem():
    landlord = next(d for d in REAL_WORLD_MISSION_DOMAINS if d.get("contact_name") == "M. Marchand")
    assert "radiateur" in landlord["opening_message"].lower()
    assert "radiateur" in landlord["brief"].lower()
    assert not landlord["twist"].startswith("Elle ")


# ---------------------------------------------------------------------------
# #217 — one display name per person on the day-1 reply thread
# ---------------------------------------------------------------------------


def test_217_the_day_one_reply_thread_names_each_person_once(monkeypatch):
    """Gus was «Gus» on the opening line and «Augustin « Gus » de Roncourt» on every
    later line, with a second «… anhören» button: the thread took the speaker's name
    from the world bible's full name. Every name the thread prints (the reaction
    lines the server sends, the page's own lines) is the registry's display name."""

    import app.services.living_story as engine
    import app.services.story_lanes as lanes
    from app.services.season import runtime
    from tests.test_season_story_qa import _lines, _page, _say, _scenario

    real = runtime.classify
    monkeypatch.setattr(runtime, "classify", lambda db, user, **kw: real(db, user, **{**kw, "use_model": False}))
    monkeypatch.setattr(lanes, "margin_correction", lambda *a, **k: None)
    monkeypatch.setattr(engine, "story_revision", lambda *a, **k: "rev")
    runtime._ROUTE_CACHE.clear()

    page = _page()
    scenario = _scenario(page)
    history: list[dict] = []
    reactions: list[dict] = []
    for index, text in enumerate(["Odile est ma grand-mère.", "Je suis ici pour la clé.", "Oui, je comprends."]):
        evaluation = _say(scenario, text, history, index)
        reactions.extend(evaluation.reply_lines)
        history.append(
            {"learner": text, "character": evaluation.character_reply_fr,
             **({"route": dict(evaluation.route)} if evaluation.route else {})}
        )
    assert "augustin_de_roncourt" in {row["speaker_id"] for row in reactions}
    for row in reactions:
        expected = reg.display_name(row["speaker_id"])
        assert row["speaker_name"] == expected, (
            f"{row['speaker_id']} is «{row['speaker_name']}» in the thread, the registry says «{expected}»"
        )
    named = [line for line in _lines(page["movements"]) if line.get("name")]
    assert named
    for line in named:
        assert line["name"] == reg.display_name(line["who"]), line


def test_217_the_served_day_one_thread_names_everyone_by_the_registry(
    assembled_client, db_session, journey_enabled, clock, season_on
):
    """Through the real API with the fake provider: the respond step's opening speaker
    and every speaker of the first reply carry the registry's display name."""

    import uuid

    from tests import test_journey_end_to_end as support

    season_on.routes = {"Odile est ma grand-mère": "a"}
    d = support.Driver(
        assembled_client, support.register(assembled_client, f"c217-{uuid.uuid4()}@example.com", cefr="A2.1"), db=db_session
    )
    d.create()
    step = None
    for _ in range(40):
        step = d.current()
        if step is None or step["kind"] == "respond":
            break
        if step["kind"] == "recall":
            d.attempt(d.recall_answer(step, correct=True))
            if d.journey.get("current_step_id") == step["id"]:
                d.advance()
        else:
            d.advance()
    assert step and step["kind"] == "respond"
    prompt = step["prompt"]
    assert prompt["character_name"] == reg.display_name(prompt["character_id"]), prompt["character_name"]
    body = d.attempt({"mode": "text", "text": "Odile est ma grand-mère"}).json()
    lines = body.get("character_lines") or []
    assert lines
    for line in lines:
        assert line["speaker_name"] == reg.display_name(line["speaker_id"]), line
