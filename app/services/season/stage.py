"""Le Quartier phase 1: an authored season page as the 3D stages it.

Owner decision 2026-10-28 («Go with all five»): the 3D walks the same page the 2D
reads (``script_payload["season_page"]``), movement by movement, each with its id —
the panels, the questions (a «Le choix» asked as one), the hook — so the beats a
reply sets off and the gestures of :mod:`app.services.season.gestures` can be
placed in it. Pure: no model, no database.

* :func:`stage_view` — the scene step's ``stage``;
* :func:`attempt_stage` — what one answer staged (``AttemptResult.stage``).

Additive to journey contract v1: ``None`` off an authored season page, so the 2D
reads every response as before.
"""

from __future__ import annotations

import logging
from typing import Any

from app.services.season.page import _default_beats, posed_as_turn, posed_choice

logger = logging.getLogger(__name__)

#: A line's kinds, as the page writes them (``page._line``).
LINE_KINDS = ("speech", "caption", "sms", "letter", "card", "toi", "all")


def line_view(line: dict[str, Any]) -> dict[str, Any] | None:
    text = str(line.get("text_fr") or "").strip()
    if not text:
        return None
    kind = str(line.get("kind") or "speech")
    return {
        "who": str(line.get("who") or "caption"),
        "name": line.get("name"),
        "kind": kind if kind in LINE_KINDS else "speech",
        "mood": line.get("mood"),
        "direction": line.get("direction") or None,
        "text_fr": text,
        "text_native": line.get("text_native") or None,
    }


def panel_view(panel: dict[str, Any], *, location_id: str | None = None) -> dict[str, Any]:
    return {
        "kind": "panel",
        "id": str(panel.get("id") or ""),
        "location_id": panel.get("location_id") or location_id,
        "in_frame": [str(who) for who in panel.get("in_frame") or []],
        "visual": panel.get("visual") or None,
        "silence": bool(panel.get("silence")),
        "flashback": bool(panel.get("flashback")),
        "diegetic": [str(text) for text in panel.get("diegetic") or []],
        "lines": [row for row in (line_view(line) for line in panel.get("lines") or []) if row],
    }


def _turn_view(turn: dict[str, Any], *, location_id: str | None, names: dict[str, str]) -> dict[str, Any]:
    panel = dict(turn.get("panel") or {})
    to = str(turn.get("to") or "")
    if turn.get("from_solve") and to:
        # A «Le choix» asked as a question: its addressee asks it, where they stand
        # (the 2D prints the prompt as the cards' caption; asked again, it is
        # theirs already: «Pardon ? Le café crème est pour toi…»).
        panel["in_frame"] = panel.get("in_frame") or [to]
        lines = list(panel.get("lines") or [])
        if len(lines) == 1 and lines[0].get("kind") == "caption":
            panel["lines"] = [{**lines[0], "who": to, "name": names.get(to), "kind": "speech"}]
    only_after = turn.get("only_after") or None
    return {
        "kind": "turn",
        "id": str(turn.get("id") or ""),
        "to": to,
        "to_name": turn.get("to_name") or names.get(to),
        "task_native": turn.get("task_native") or None,
        "choice": bool(turn.get("choice")),
        "only_after": {str(key): [str(value) for value in values] for key, values in only_after.items()} if only_after else None,
        "panel": panel_view(panel, location_id=location_id),
    }


def stage_view(
    page: dict[str, Any] | None,
    position: dict[str, Any] | None = None,
    *,
    storylets: list[dict[str, Any]] | None = None,
    names: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    """The scene step's ``stage``: today's resolved page, in order. A solve the page
    does not ask (a balloon choice, an enquête) is the panels the page plays for it;
    the hook keeps its whole panel, «À suivre…» included. ``names``: the cast's
    display names, for a question the page asks through «Le choix»."""

    if not isinstance(page, dict) or not page.get("movements") or not page.get("tentpole"):
        return None
    position = position or {}
    names = names or {}
    location = page.get("location_id")
    movements: list[dict[str, Any]] = []
    for movement in page.get("movements") or []:
        kind = movement.get("kind")
        if kind == "panel":
            movements.append(panel_view(movement, location_id=location))
        elif kind == "turn":
            movements.append(_turn_view(movement, location_id=location, names=names))
        elif posed_choice(movement):
            movements.append(_turn_view(posed_as_turn(movement), location_id=location, names=names))
        elif kind == "solve":
            movements.extend(panel_view(beat, location_id=location) for beat in _default_beats(movement))
        elif kind == "hook":
            movements.append(
                {
                    "kind": "hook",
                    "id": str(movement.get("id") or ""),
                    "role": movement.get("role") or "midpoint",
                    "panel": panel_view(movement.get("panel") or {}, location_id=location),
                }
            )
    segment = str(page.get("tentpole"))
    day = str(page.get("day") or position.get("day_in_segment") or "")
    return {
        "season_id": str(page.get("season_id") or position.get("season_id") or ""),
        "segment": segment,
        "day": day,
        "key": f"{segment}.{day}",
        "number": page.get("number"),
        "title_fr": str(page.get("title_fr") or ""),
        "story_date_fr": page.get("story_date_fr") or None,
        "location_id": location,
        "band": page.get("band") or None,
        "language": page.get("language") or None,
        "can_do_native": page.get("can_do_native") or None,
        "movements": movements,
        "storylets": list(storylets or []),
    }


def scene_stage(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    """The scene step's ``stage``, from the scene's ``script_payload``, with the day's
    gestures (``quartier.json``). ``None`` off an authored season page, and on any
    failure: a stage is a courtesy to the 3D, never the day's."""

    payload = payload if isinstance(payload, dict) else {}
    page = payload.get("season_page")
    if not isinstance(page, dict) or not page.get("tentpole"):
        return None
    try:
        from app.services.cast_registry import display_names
        from app.services.season.format import load_season
        from app.services.season.gestures import storylets_view

        season_id = str(page.get("season_id") or "")
        names = display_names(load_season(season_id).cast)
        storylets = storylets_view(
            season_id,
            f"{page['tentpole']}.{page.get('day')}",
            band=page.get("band"),
            language=page.get("language"),
            names=names,
        )
        return stage_view(page, payload.get("season"), storylets=storylets, names=names)
    except Exception:  # noqa: BLE001
        logger.exception("stage: the season page could not be staged")
        return None


def attempt_stage(
    turn_id: str,
    reply_id: str | None,
    beats: list[dict[str, Any]],
    *,
    next_turn_id: str | None,
    closing: bool,
) -> dict[str, Any]:
    """What one answer staged: the beats it set off, in order, each with its id (the
    addressee's first line back ``<turn>.ack``, the reply's own beats or the line
    asking again — ``<turn>.ask_again``, ``<turn>.en_francais`` — the turn's
    ``after``, and on closing the page's tail). ``reply_id`` is ``None`` when the
    scene asked again; ``next_turn_id`` is the question now asked."""

    return {
        "turn_id": str(turn_id),
        "reply_id": str(reply_id) if reply_id is not None else None,
        "beats": [panel_view(beat) for beat in beats if isinstance(beat, dict)],
        "next_turn_id": str(next_turn_id) if next_turn_id is not None else None,
        "closing": bool(closing),
    }
