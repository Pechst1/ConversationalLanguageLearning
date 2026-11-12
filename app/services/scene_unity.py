"""One page is one scene: the state a generated page declares, and the one comparison
made against it (#621, root cause #145).

Live walk of 9 Nov: under the header «Le quai de Valmy», four panels read «Le soir. Au
téléphone : l'assurance. Margaux essuie un verre déjà sec.», «Dehors, sur le quai.», «Le
lendemain matin. Le même banc.» and Gus's «Bonjour. Bonne journée à vous.». The writer
is told one place and one moment now (``story_split.PLANNER``, ``story_split.AUTHOR``,
``living_story.DIRECTOR``); what follows only says what the page's own state says:

* ``SceneDraft.scene_cast``: who is in the scene (on a planned page, the plan's ``cast``
  and its lead). A speaker is in that list, or the page says otherwise than it planned.
* ``Panel.location_id``: where a panel happens. Empty is no claim: the scene's place.
* ``Panel.time_jump``: this panel opens a deliberate jump (later, or back: a flashback).
  Its caption says when; the panels after it may stay where it went.

The comparison is exact and reads no meaning: **the words of a caption are never read.**
A caption that says «Le lendemain» on a panel that declares no jump passes, on purpose:
clause patterns over French are what got #600 and #631 rejected, and a writer free to
tell a story is worth more here than a guard that thinks it can read one. The story
critic reads the page as a reader does.

Soft, always: :func:`gap` rides the one retry of ``living_story._check_reading_aids``,
and a page is served after it either way. A scene that wanders never costs a day, and
never reaches the reader as it wandered: what the soft rejection carries to be served
is :func:`held_to_scene`, the page with what its own state put outside the scene taken
out (the walk's page was served as written when the retry wandered too).

A page without this state (an authored tentpole, which is never validated here; a
draft stored before this; a model that left the fields out) makes no claim and passes.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

#: A place id, as long as the schema of ``SceneDraft.location_id`` allows.
PLACE_CHARS = 80
#: One deliberate jump on a page; the second is the walk's page, hopping every panel.
MAX_TIME_JUMPS = 1
#: The fewest panels :func:`held_to_scene` leaves a page (``SceneDraft.panels``' floor).
MIN_PANELS_KEPT = 2


def lenient_place(value: Any) -> str | None:
    """A panel's place, or ``None`` (no claim) for anything that is not an id: a scratch
    value here never costs a page."""

    text = value.strip() if isinstance(value, str) else ""
    if not text or len(text) > PLACE_CHARS or text.casefold() in ("none", "null", "n/a"):
        return None
    return text


def lenient_jump(value: Any) -> bool:
    """Anything but a plain yes is no jump."""

    return value is True or (isinstance(value, str) and value.strip().casefold() in ("true", "yes", "1"))


def lenient_cast(value: Any) -> list[str]:
    """The scene's cast as far as it holds: the ids, once each."""

    if not isinstance(value, list | tuple):
        return []
    return list(dict.fromkeys(item.strip() for item in value if isinstance(item, str) and item.strip()))


def _listed(numbers: Iterable[int]) -> str:
    return ", ".join(str(number) for number in numbers)


def speakers_outside_cast(draft: Any) -> dict[str, list[int]]:
    """``{speaker id: panels they speak in (from 1)}`` for each speaker the scene's cast
    does not list. The lead is always in the scene. No cast declared, nothing compared."""

    cast = set(draft.scene_cast or [])
    if not cast:
        return {}
    cast.add(draft.character_id)
    outside: dict[str, list[int]] = {}
    for number, panel in enumerate(draft.panels, start=1):
        for line in panel.dialogue:
            if line.character_id not in cast and number not in outside.setdefault(line.character_id, []):
                outside[line.character_id].append(number)
    return outside


def panels_elsewhere(draft: Any) -> list[tuple[int, str]]:
    """``(panel from 1, its place)`` for each panel that declares another place than the
    scene's and is not inside a jump: the panel opening the jump, or one after it that
    stays where it went. Coming back to the scene's place needs nothing."""

    elsewhere: list[tuple[int, str]] = []
    jumped_to: str | None = None
    for number, panel in enumerate(draft.panels, start=1):
        place = panel.location_id
        if panel.time_jump:
            jumped_to = place
            continue
        if place == draft.location_id:
            jumped_to = None
        elif place and place != jumped_to:
            elsewhere.append((number, place))
    return elsewhere


def time_jumps(draft: Any) -> list[int]:
    """The panels (from 1) that declare a jump."""

    return [number for number, panel in enumerate(draft.panels, start=1) if panel.time_jump]


def jumps_without_caption(draft: Any) -> list[int]:
    """The panels (from 1) that declare a jump and have no caption to say when."""

    return [
        number
        for number, panel in enumerate(draft.panels, start=1)
        if panel.time_jump and not str(panel.narration_fr or "").strip()
    ]


def issues(draft: Any) -> list[str]:
    """One instruction per thing the page's state contradicts, for the one retry."""

    found: list[str] = []
    for who, numbers in speakers_outside_cast(draft).items():
        found.append(
            f"{who} speaks in panel {_listed(numbers)} and is not in the scene's cast "
            f"{sorted(draft.scene_cast)}. Nobody comes in for one line: give it to someone who "
            "is there, let a gesture carry it, or plan them into the scene from its start."
        )
    elsewhere = panels_elsewhere(draft)
    if elsewhere:
        places = "; ".join(f"panel {number} at {place}" for number, place in elsewhere)
        found.append(
            f"This scene happens at {draft.location_id}, and its location_id says {places}. "
            f"Tell that part at {draft.location_id}, where the page is: what came before is "
            "already true, and one line says it. A deliberate cut to another time is one panel "
            "with time_jump true and a caption that says when."
        )
    jumps = time_jumps(draft)
    if len(jumps) > MAX_TIME_JUMPS:
        found.append(
            f"This page jumps in time {len(jumps)} times (panels {_listed(jumps)}). Keep the "
            f"jump the story needs, at most {MAX_TIME_JUMPS}, and tell the rest as one moment."
        )
    silent = jumps_without_caption(draft)
    if silent:
        found.append(
            f"Panel {_listed(silent)} jumps in time with no caption. Its caption says when, in "
            "a few words, so the reader can follow."
        )
    return found


def gap(draft: Any) -> str | None:
    """What the page's state contradicts, as the one retry's hint, or ``None``."""

    return " ".join(issues(draft)) or None


def held_to_scene(draft: Any, *, keep: int = MIN_PANELS_KEPT) -> Any:
    """The page as it may be served: a copy with what its own state says left the scene
    taken out, or ``draft`` itself when nothing did. The one retry is told (:func:`gap`);
    this is what a soft rejection carries, so the page served when the retry wanders
    again, or fails, is still one scene (#621: the walk's page was served as written).

    Like the comparison, it reads no word, and it adds none:

    * a jump with no caption is no jump (nothing says when);
    * a line by someone the cast does not list is taken out;
    * a panel at another place, outside a jump, is taken out, and so is a panel left
      with nothing to read once those lines are gone: while ``keep`` panels remain.
      A silent panel the writer drew stays.

    Extra jumps that each say when are left to the retry: every panel still says where
    and when it is.
    """

    if gap(draft) is None:
        return draft
    held = draft.model_copy(deep=True)
    for panel in held.panels:
        if panel.time_jump and not str(panel.narration_fr or "").strip():
            panel.time_jump = False
    emptied: set[int] = set()
    outside = speakers_outside_cast(held)
    for number in sorted({number for numbers in outside.values() for number in numbers}):
        panel = held.panels[number - 1]
        panel.dialogue = [line for line in panel.dialogue if line.character_id not in outside]
        if not panel.dialogue and not str(panel.narration_fr or "").strip():
            emptied.add(number)
    gone = emptied | {number for number, _place in panels_elsewhere(held)}
    if gone and len(held.panels) - len(gone) >= keep:
        held.panels = [panel for number, panel in enumerate(held.panels, start=1) if number not in gone]
    return held
