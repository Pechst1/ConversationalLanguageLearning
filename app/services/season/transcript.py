"""A season life, written down (WP-111): what a learner read, day by day.

For the owner's read of «the first ten days»: each tentpole day is its authored page
as this learner met it — every panel, the learner's own lines as balloons, the
reactions their lines routed to, the solves with the card the story took — and each
generated day is the page the director wrote, the learner's reply, the character's
answer and the ending. Plain markdown; no database, no model.
"""

from __future__ import annotations

from typing import Any

from app.services.season.page import option_by_id, reply_by_id


def _line(line: dict[str, Any]) -> str:
    text = str(line.get("text_fr") or "").strip()
    who = line.get("who")
    if line.get("kind") == "caption":
        return f"> *{text}*"
    if line.get("kind") in ("sms", "letter", "card"):
        return f"> **{str(line.get('kind')).upper()}** — {text}"
    if who == "toi":
        return f"**Toi** (bulle) — «{text}»"
    name = line.get("name") or who
    direction = f" *({line['direction']})*" if line.get("direction") else ""
    return f"**{name}**{direction} — «{text}»"


def _panel(panel: dict[str, Any], label: str | None = None) -> list[str]:
    out: list[str] = []
    head = f"**{label or panel.get('id')}**"
    if panel.get("silence"):
        head += " *(silence)*"
    if panel.get("visual"):
        head += f" — *{panel['visual']}*"
    out.append(head)
    for text in panel.get("diegetic") or []:
        out.append(f"> ✎ {text}")
    out.extend(_line(line) for line in panel.get("lines") or [])
    out.append("")
    return out


def render_tentpole_day(page: dict[str, Any], routing: list[dict[str, Any]]) -> list[str]:
    """The page, with the learner's lines where they said them."""

    routes = {row.get("turn_id"): row for row in routing or []}
    out: list[str] = []
    for movement in page.get("movements") or []:
        kind = movement.get("kind")
        if kind == "panel":
            out.extend(_panel(movement))
        elif kind == "hook":
            out.extend(_panel(movement["panel"], label=f"{movement['id']} · {movement['role']}"))
        elif kind == "turn":
            out.extend(_panel(movement["panel"]))
            if movement.get("task_native"):
                out.append(f"*Ta tâche : {movement['task_native']}*")
                out.append("")
            row = routes.get(movement.get("id"))
            if row is None:
                out.append("*(Cette réplique n'a pas été jouée aujourd'hui : WP-110 la pose dans la page.)*")
                out.append("")
                continue
            out.append(f"**Toi** (bulle) — «{row.get('learner')}»")
            reply = reply_by_id(movement, row.get("reply_id"))
            out.append(f"*→ la scène lit : {reply.get('label')}*")
            out.append("")
            for beat in reply.get("beats") or []:
                out.extend(_panel(beat))
            for beat in movement.get("after") or []:
                out.extend(_panel(beat))
        elif kind == "solve":
            prompt = str((movement.get("prompt") or {}).get("text_fr") or "")
            quoted = prompt if prompt.startswith("«") else f"«{prompt}»"
            out.append(f"**{movement['id']} · {movement['mechanic']}** — {quoted}")
            if movement.get("document"):
                out.append("> " + str(movement["document"].get("text_fr") or "").replace("\n", "\n> "))
            labels = [
                str((option.get("label") or {}).get("text_fr") or option.get("id"))
                for option in movement.get("options") or []
            ]
            if labels:
                out.append("Cartes : " + " · ".join(f"[ {label} ]" for label in labels))
            for objection in movement.get("objections") or []:
                out.append(f"> objection — «{(objection or {}).get('text_fr')}»")
            chosen = option_by_id(movement, movement.get("default"))
            if chosen is not None:
                label = (chosen.get("label") or {}).get("text_fr") or chosen.get("id")
                out.append(f"*→ non posé avant WP-112 ; l'histoire prend : [ {label} ]*")
                out.append("")
                for beat in chosen.get("beats") or []:
                    out.extend(_panel(beat))
            elif movement.get("mechanic") == "enquete":
                out.append("*→ non posé avant WP-112 ; un personnage montre l'indice :*")
                out.append("")
                for beat in movement.get("nudge") or []:
                    out.extend(_panel(beat))
            else:
                out.append("*→ non posé avant WP-112.*")
                out.append("")
    return out


def render_generated_day(
    draft: dict[str, Any],
    exchanges: list[dict[str, Any]],
    ending: dict[str, Any],
    *,
    names: dict[str, str] | None = None,
) -> list[str]:
    names = names or {}

    def name(who: Any) -> str:
        return names.get(str(who)) or str(who)

    out: list[str] = [f"> *{draft.get('premise_fr')}*", ""]
    for index, panel in enumerate(draft.get("panels") or [], start=1):
        head = f"**P{index}** — *{panel.get('visual_direction')}*"
        out.append(head)
        if panel.get("narration_fr"):
            out.append(f"> *{panel['narration_fr']}*")
        for line in panel.get("dialogue") or []:
            out.append(f"**{name(line.get('character_id'))}** — «{line.get('text_fr')}»")
        out.append("")
    out.append(f"**{name(draft.get('character_id'))}** (se tourne vers toi) — «{draft.get('opening_line_fr')}»")
    out.append(f"*Ta tâche : {draft.get('objective_native')}*")
    out.append("")
    for exchange in exchanges:
        out.append(f"**Toi** — «{exchange.get('learner')}»")
        out.append(f"**{name(draft.get('character_id'))}** — «{exchange.get('character')}»")
        out.append("")
    if ending.get("character_line_fr"):
        out.append(f"> *{ending['character_line_fr']}*")
    checklist = draft.get("season_checklist") or {}
    if checklist:
        out.append(
            f"*Checklist du réalisateur : {checklist.get('premise_id') or '—'} · "
            f"{checklist.get('change_before')} → {checklist.get('change_after')} · "
            f"petit moment : {checklist.get('small_moment_id') or '—'}*"
        )
    out.append("")
    return out
