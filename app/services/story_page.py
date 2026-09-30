"""WP-110 «La planche vivante»: a finished day as one page, with the learner in it.

The six movements of the page, as rows the reader draws one after the other:

1. ``act`` — the characters acting (the scene's panels);
2. ``turn`` — the turn to *you*: the panel the question is asked in, with the
   learner's own line drawn as a balloon in it (characters keep captions, S-2/F-2);
3. ``reaction`` — what the learner's line set off (the WP-89 conversation, drawn);
4. ``solve`` — the solve moment (until WP-112 poses it: the card the story took);
5. ``ending`` — the ending drawn (a tentpole's hook panel; a generated day's ending
   is the reader's own «case finale»);
6. «À suivre…» — ``a_suivre_fr``.

Built only for a completed scene: before that the page would print reactions to
lines the learner has not said. Pure: reads the scene's stored payload, no model.
"""

from __future__ import annotations

from typing import Any

from app.services.season.page import option_by_id, reply_by_id
from app.services.season.world import plate_for

YOU = "toi"


def _line(line: dict[str, Any], names: dict[str, str]) -> dict[str, Any] | None:
    text = str(line.get("text_fr") or "").strip()
    if not text:
        return None
    who = str(line.get("who") or "")
    kind = str(line.get("kind") or "speech")
    if kind == "caption":
        return None  # a caption is the panel's narration, not a line
    you = who == YOU
    return {
        "character_id": who or "narrator",
        "character_name": None if you else (line.get("name") or names.get(who)),
        "text_fr": text,
        "text_native": line.get("text_native"),
        "mood": line.get("mood"),
        "kind": "you" if you else kind if kind in ("sms", "letter", "card") else "speech",
        "you": you,
    }


def _narration(panel: dict[str, Any]) -> str:
    parts = [str(text).strip() for text in panel.get("diegetic") or [] if str(text).strip()]
    parts += [
        str(line.get("text_fr") or "").strip()
        for line in panel.get("lines") or []
        if line.get("kind") == "caption" and str(line.get("text_fr") or "").strip()
    ]
    return " ".join(parts)


class _Tentpole:
    """Rows from a season page and the replies the learner's lines routed to."""

    def __init__(self, names: dict[str, str], ending_fr: str):
        self.names = names
        self.ending_fr = ending_fr
        self.rows: list[dict[str, Any]] = []
        self.location: str | None = None

    def panel(self, panel: dict[str, Any], movement: str, *, you: str | None = None) -> None:
        self.location = panel.get("location_id") or self.location
        lines = [row for row in (_line(line, self.names) for line in panel.get("lines") or []) if row]
        if you:
            lines.append(
                {
                    "character_id": YOU,
                    "character_name": None,
                    "text_fr": you,
                    "text_native": None,
                    "mood": None,
                    "kind": "you",
                    "you": True,
                }
            )
        narration = _narration(panel)
        if movement == "ending" and narration.strip() == self.ending_fr:
            # The reader's «case finale» says the hook; the drawn ending does not repeat it.
            narration = ""
        image = plate_for(self.location)
        self.rows.append(
            {
                "id": f"{movement}:{panel.get('id')}:{len(self.rows)}",
                "movement": movement,
                "narration_fr": narration,
                "dialogue": lines,
                "image_url": image,
                "image_status": "setting_reference" if image else "unavailable",
                "alt_native": None,
                "flashback": bool(panel.get("flashback")),
                "silence": bool(panel.get("silence")),
            }
        )

    def build(self, page: dict[str, Any], routing: list[dict[str, Any]]) -> list[dict[str, Any]]:
        routes = {row.get("turn_id"): row for row in routing or [] if isinstance(row, dict)}
        for movement in page.get("movements") or []:
            kind = movement.get("kind")
            if kind == "panel":
                self.panel(movement, "act")
            elif kind == "turn":
                row = routes.get(movement.get("id"))
                learner = str((row or {}).get("learner") or "").strip() or None
                self.panel(movement["panel"], "turn", you=learner)
                if row is None:
                    continue
                reply = reply_by_id(movement, row.get("reply_id"))
                for beat in [*(reply.get("beats") or []), *(movement.get("after") or [])]:
                    self.panel(beat, "reaction")
            elif kind == "solve":
                self.solve(movement)
            elif kind == "hook":
                self.panel(movement["panel"], "ending")
        return self.rows

    def solve(self, movement: dict[str, Any]) -> None:
        prompt = str((movement.get("prompt") or {}).get("text_fr") or "").strip()
        chosen = option_by_id(movement, movement.get("default"))
        label = str(((chosen or {}).get("label") or {}).get("text_fr") or "").strip()
        lines = []
        if label:
            lines.append(
                {
                    "character_id": YOU,
                    "character_name": None,
                    "text_fr": label,
                    "text_native": None,
                    "mood": None,
                    "kind": "card",
                    "you": True,
                }
            )
        image = plate_for(self.location)
        self.rows.append(
            {
                "id": f"solve:{movement.get('id')}:{len(self.rows)}",
                "movement": "solve",
                "narration_fr": prompt,
                "dialogue": lines,
                "image_url": image,
                "image_status": "setting_reference" if image else "unavailable",
                "alt_native": None,
                "flashback": False,
                "silence": False,
            }
        )
        beats = (chosen or {}).get("beats") if chosen else None
        if beats is None and movement.get("mechanic") == "enquete":
            beats = movement.get("nudge")
        for beat in beats or []:
            self.panel(beat, "reaction")


def _generated(scene_panels: list[dict[str, Any]], thread: dict[str, Any], names: dict[str, str]) -> list[dict[str, Any]]:
    rows = [
        {
            "id": f"act:{panel.get('id')}",
            "movement": "act",
            "narration_fr": str(panel.get("narration_fr") or ""),
            "dialogue": [
                {
                    "character_id": str(line.get("character_id") or ""),
                    "character_name": line.get("character_name"),
                    "text_fr": str(line.get("text_fr") or ""),
                    "text_native": line.get("text_native"),
                    "mood": line.get("mood"),
                    "kind": "speech",
                    "you": False,
                }
                for line in panel.get("dialogue") or []
                if str(line.get("text_fr") or "").strip()
            ],
            "image_url": panel.get("image_url"),
            "image_status": panel.get("image_status") or "unavailable",
            "alt_native": panel.get("alt_native"),
            "flashback": False,
            "silence": False,
        }
        for panel in scene_panels
    ]
    exchanges = [row for row in thread.get("exchanges") or [] if isinstance(row, dict)]
    if not exchanges:
        return rows
    who = str(thread.get("character_id") or "")
    name = names.get(who)
    last = scene_panels[-1] if scene_panels else {}

    def said(text: str) -> dict[str, Any]:
        return {"character_id": who, "character_name": name, "text_fr": text, "text_native": None,
                "mood": None, "kind": "speech", "you": False}

    def you(text: str) -> dict[str, Any]:
        return {"character_id": YOU, "character_name": None, "text_fr": text, "text_native": None,
                "mood": None, "kind": "you", "you": True}

    def row(index: int, movement: str, lines: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "id": f"{movement}:{index}",
            "movement": movement,
            "narration_fr": "",
            "dialogue": lines,
            "image_url": last.get("image_url"),
            "image_status": last.get("image_status") or "unavailable",
            "alt_native": last.get("alt_native"),
            "flashback": False,
            "silence": False,
        }

    opening = str(thread.get("opening_fr") or "").strip()
    rows.append(row(0, "turn", [*([said(opening)] if opening else []), you(exchanges[0]["learner"])]))
    for index, exchange in enumerate(exchanges, start=1):
        lines = [said(exchange["character"])] if str(exchange.get("character") or "").strip() else []
        if index < len(exchanges):
            lines.append(you(exchanges[index]["learner"]))
        if lines:
            rows.append(row(index, "reaction", lines))
    return rows


def episode_page(scene: Any, scene_panels: list[dict[str, Any]], names: dict[str, str]) -> dict[str, Any] | None:
    """The finished page of a completed scene, or None (not finished, or nothing to draw)."""

    if getattr(scene, "status", None) != "completed":
        return None
    payload = scene.script_payload or {}
    recap = scene.recap_payload or {}
    a_suivre = str(payload.get("next_teaser_fr") or "").strip() or None
    season_page = payload.get("season_page")
    if isinstance(season_page, dict) and season_page.get("movements"):
        ending_fr = str(recap.get("resolution_fr") or "").strip()
        rows = _Tentpole(names, ending_fr).build(season_page, payload.get("season_routing") or [])
        # The tentpole's teaser is the hook the finale already says.
        return {"rows": rows, "a_suivre_fr": None if a_suivre == ending_fr else a_suivre}
    thread = payload.get("page_thread")
    if not isinstance(thread, dict):
        return None
    return {"rows": _generated(scene_panels, thread, names), "a_suivre_fr": a_suivre}
