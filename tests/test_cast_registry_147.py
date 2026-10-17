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
