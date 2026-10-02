"""One tentpole day, resolved: the page for this learner (WP-111 → WP-110).

``resolve_day`` picks the day's variant, expands the shared blocks, keeps the
movements, lines and replies whose conditions hold, and writes every line at the
learner's band — the A2 line, or the B1 line where the bible gives one — with the
translation an A1/A2 learner reading another language gets, and the date-free
wording off the story's calendar (S-12). The result is plain JSON: it is stored on
the published scene (``script_payload["season_page"]``) for the reader to draw, and
it is what the season transcript prints.

``project`` maps the page onto today's three story steps until WP-110's page reader
lands: the panels before the first turn are the scene, the first turn is the reply,
and the day's hook is the ending. Everything else is kept on the page.
"""

from __future__ import annotations

from typing import Any

from app.services.season.flags import holds
from app.services.season.format import (
    B1_BANDS,
    Day,
    Hook,
    Include,
    Line,
    Option,
    Panel,
    Reply,
    Say,
    Season,
    Solve,
    Tentpole,
    Turn,
)

#: Languages whose A1/A2 learners get «Traduire la case».
TRANSLATED = frozenset({"en", "de"})


def _band2(band: str | None) -> str:
    return str(band or "A1")[:2].upper()


def translates(band: str | None, language: str | None) -> bool:
    return _band2(band) not in B1_BANDS and str(language or "") in TRANSLATED


class _Ctx:
    def __init__(self, *, flags: dict, band: str, language: str, neutral: bool, names: dict[str, str]):
        self.flags = flags
        self.band = band
        self.language = language
        self.neutral = neutral
        self.names = names

    def ok(self, cond) -> bool:
        return holds(cond, self.flags, band=self.band)

    def say(self, say: Say | None) -> dict[str, Any] | None:
        if say is None:
            return None
        text = say.text(self.band, neutral=self.neutral)
        native = say.native_for(self.language) if translates(self.band, self.language) else None
        return {"text_fr": text, "text_native": native}


def _line(line: Line, ctx: _Ctx) -> dict[str, Any] | None:
    if not ctx.ok(line.when):
        return None
    said = ctx.say(line.say)
    kind = line.who if line.who in {"caption", "sms", "letter", "card", "toi", "all"} else "speech"
    return {
        "who": line.who,
        "name": ctx.names.get(line.who),
        "kind": kind,
        "mood": line.mood,
        "direction": line.direction or None,
        **(said or {}),
    }


def _panel(panel: Panel, ctx: _Ctx) -> dict[str, Any] | None:
    if not ctx.ok(panel.when):
        return None
    return {
        "kind": "panel",
        "id": panel.id,
        "visual": panel.visual or None,
        "location_id": panel.location_id,
        "in_frame": list(panel.in_frame),
        "silence": panel.silence,
        "flashback": panel.flashback,
        "diegetic": list(panel.diegetic),
        "balloon": panel.balloon,
        "lines": [row for row in (_line(line, ctx) for line in panel.lines) if row],
    }


def _panels(panels: list[Panel], ctx: _Ctx) -> list[dict[str, Any]]:
    return [row for row in (_panel(panel, ctx) for panel in panels) if row]


def _reply(reply: Reply, ctx: _Ctx) -> dict[str, Any] | None:
    if not ctx.ok(reply.when):
        return None
    return {
        "id": reply.id,
        "label": reply.label,
        "means": reply.means,
        "examples": list(reply.examples),
        "clumsy": reply.clumsy,
        "path": reply.path,
        "repeat_once": reply.repeat_once,
        "sets": dict(reply.sets),
        "sets_if": [row.model_dump() for row in reply.sets_if],
        "beats": _panels(reply.beats, ctx),
        "again": _panels(reply.again, ctx),
    }


def _option(option: Option, ctx: _Ctx) -> dict[str, Any] | None:
    if not ctx.ok(option.when):
        return None
    return {
        "id": option.id,
        "label": ctx.say(option.label),
        "subtitle": ctx.say(option.subtitle),
        "correct": option.correct,
        "sets": dict(option.sets),
        "sets_if": [row.model_dump() for row in option.sets_if],
        "beats": _panels(option.beats, ctx),
    }


def _task(task: dict[str, str], language: str) -> str | None:
    return task.get(language) or task.get("en") or None


def _movement(movement: Any, tentpole: Tentpole, ctx: _Ctx) -> list[dict[str, Any]]:
    if not ctx.ok(getattr(movement, "when", {})):
        return []
    if isinstance(movement, Include):
        rows: list[dict[str, Any]] = []
        for inner in tentpole.shared.get(movement.ref) or []:
            rows.extend(_movement(inner, tentpole, ctx))
        return rows
    if isinstance(movement, Panel):
        panel = _panel(movement, ctx)
        return [panel] if panel else []
    if isinstance(movement, Hook):
        panel = _panel(movement.panel, ctx)
        return [{"kind": "hook", "id": movement.id, "role": movement.role, "panel": panel}] if panel else []
    if isinstance(movement, Turn):
        panel = _panel(movement.panel, ctx)
        replies = [row for row in (_reply(reply, ctx) for reply in movement.replies) if row]
        if not panel or not replies:
            return []
        fallback = movement.fallback if any(r["id"] == movement.fallback for r in replies) else replies[-1]["id"]
        return [
            {
                "kind": "turn",
                "id": movement.id,
                "to": movement.to,
                "to_name": ctx.names.get(movement.to),
                "panel": panel,
                "task_native": _task(movement.task, ctx.language),
                "listens_for": movement.listens_for,
                "replies": replies,
                "fallback": fallback,
                "gate": movement.gate,
                "small": movement.small,
                "sets": dict(movement.sets),
                "sets_if": [row.model_dump() for row in movement.sets_if],
                "after": _panels(movement.after, ctx),
            }
        ]
    if isinstance(movement, Solve):
        b1 = _band2(ctx.band) in B1_BANDS
        source = movement.options_b1 if (b1 and movement.options_b1) else movement.options
        options = [row for row in (_option(option, ctx) for option in source) if row]
        return [
            {
                "kind": "solve",
                "id": movement.id,
                "mechanic": movement.mechanic,
                "to": movement.to,
                "prompt": ctx.say(movement.prompt),
                "task_native": _task(movement.task, ctx.language),
                "visual": movement.visual or None,
                "document": ctx.say(movement.document),
                "options": options,
                "multi": bool(b1 and movement.multi_b1),
                "nudge": _panels(movement.nudge, ctx),
                "objections": [ctx.say(item) for item in movement.objections],
                "lands_means": movement.lands_means or None,
                "lands_examples": list(movement.lands_examples),
                "lands": _panels(movement.lands, ctx),
                "fails": _panels(movement.fails, ctx),
                "give_up": ctx.say(movement.give_up),
                "interlude_after": movement.interlude_after,
                "interlude": _panels(movement.interlude, ctx),
                "sets_on_land": dict(movement.sets_on_land),
                "sets_on_fail": dict(movement.sets_on_fail),
                "default": movement.default,
                "flag": movement.flag,
            }
        ]
    return []


def choose_day(tentpole: Tentpole, letter: str, flags: dict[str, Any], *, band: str | None = None) -> Day | None:
    """The day's variant whose condition holds (the first one, in file order)."""

    for day in tentpole.days:
        if day.day == letter and holds(day.when, flags, band=band):
            return day
    return None


def resolve_day(
    season: Season,
    tentpole_id: str,
    letter: str,
    *,
    flags: dict[str, Any],
    band: str,
    language: str,
    neutral: bool = False,
) -> dict[str, Any] | None:
    """The page of one tentpole day for this learner, as plain JSON (or ``None``)."""

    tentpole = season.tentpoles.get(tentpole_id)
    if tentpole is None:
        return None
    day = choose_day(tentpole, letter, flags, band=band)
    if day is None:
        return None
    names = {member.id: member.name for member in season.cast}
    ctx = _Ctx(flags=flags, band=band, language=language, neutral=neutral and bool(day.holiday), names=names)
    movements: list[dict[str, Any]] = []
    for movement in day.movements:
        movements.extend(_movement(movement, tentpole, ctx))
    return {
        "season_id": season.id,
        "tentpole": tentpole.id,
        "number": tentpole.number,
        "tentpole_title_fr": tentpole.title_fr,
        "day": day.day,
        "variant": day.variant,
        "title_fr": day.title_fr or tentpole.title_fr,
        "story_date_fr": day.story_date_fr,
        "holiday": day.holiday,
        "location_id": day.location_id,
        "minutes": day.minutes,
        "band": band,
        "language": language,
        "previously": [row.model_dump() for row in day.previously],
        "movements": movements,
        "lexicon": [row.model_dump() for row in day.lexicon],
        "can_do_native": day.can_do.get(language) or day.can_do.get("en"),
    }


# ---------------------------------------------------------------------------
# Walking a page
# ---------------------------------------------------------------------------


def turns_of(page: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in page.get("movements") or [] if row.get("kind") == "turn"]


def solves_of(page: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in page.get("movements") or [] if row.get("kind") == "solve"]


def hook_of(page: dict[str, Any]) -> dict[str, Any] | None:
    return next((row for row in page.get("movements") or [] if row.get("kind") == "hook"), None)


def hook_caption(page: dict[str, Any]) -> dict[str, Any] | None:
    """The hook's caption line (the «À suivre…»), or its last line."""

    hook = hook_of(page)
    lines = ((hook or {}).get("panel") or {}).get("lines") or []
    caption = next((line for line in reversed(lines) if line.get("kind") == "caption"), None)
    return caption or (lines[-1] if lines else None)


def reply_by_id(turn: dict[str, Any], reply_id: str | None) -> dict[str, Any]:
    replies = turn.get("replies") or []
    return next((row for row in replies if row.get("id") == reply_id), None) or next(
        (row for row in replies if row.get("id") == turn.get("fallback")), replies[0]
    )


def option_by_id(solve: dict[str, Any], option_id: str | None) -> dict[str, Any] | None:
    return next((row for row in solve.get("options") or [] if row.get("id") == option_id), None)


def spoken_lines(panels: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [line for panel in panels for line in panel.get("lines") or [] if line.get("text_fr")]


# ---------------------------------------------------------------------------
# WP-111 projection onto today's scene / reply / ending steps
# ---------------------------------------------------------------------------


def _default_beats(solve: dict[str, Any]) -> list[dict[str, Any]]:
    """What the page shows when a solve before the reply is not played: the
    default card's beats, or — for an enquête — the nudge (a character points)."""

    if solve.get("mechanic") == "enquete":
        return list(solve.get("nudge") or [])
    option = option_by_id(solve, solve.get("default"))
    return list((option or {}).get("beats") or [])


def project(page: dict[str, Any]) -> dict[str, Any]:
    """The page as three steps: ``scene_panels``, ``turn`` (or a solve posed as one)
    and the ``ending``.

    * Scene: every panel before the first turn, with the default beats of any solve
      met on the way (the calendar's «found by Lila»).
    * Reply: the first turn. A day with no free turn (T4 A, T5 B's Day A) poses its
      first solve as the question, its options as the replies.
    * Ending: the hook's caption.
    """

    scene: list[dict[str, Any]] = []
    first_turn: dict[str, Any] | None = None
    for movement in page.get("movements") or []:
        kind = movement.get("kind")
        if kind == "panel":
            scene.append(movement)
        elif posed_choice(movement):
            # WP-113: a posed solve met before any free question opens the reply.
            first_turn = posed_as_turn(movement)
            scene.append(first_turn["panel"])
            break
        elif kind == "solve":
            if first_turn is None:
                scene.extend(_default_beats(movement))
        elif kind == "turn":
            first_turn = movement
            scene.append(movement["panel"])
            break
        elif kind == "hook":
            break
    if first_turn is None:
        solve = next(iter(solves_of(page)), None)
        if solve is not None:
            first_turn = solve_as_turn(solve)
    return {"scene_panels": scene, "turn": first_turn, "ending": hook_caption(page)}


#: WP-113: the solves a learner now decides by tapping a card («Le choix»). The
#: other mechanics (enquête, convaincre, déchiffrer, the S-9 balloon) are WP-112's
#: and keep the story's default until then.
CHOICE_MECHANICS = ("choix",)
#: WP-113: the solves posed as a conversation: «Convaincre» (up to one exchange
#: per objection; any sincere argument lands).
CONVINCE_MECHANICS = ("convaincre",)


def posed_choice(movement: dict[str, Any]) -> bool:
    """A solve WP-113 asks the learner instead of defaulting: «Le choix», «Convaincre»."""

    return movement.get("kind") == "solve" and movement.get("mechanic") in (*CHOICE_MECHANICS, *CONVINCE_MECHANICS)


def posed_as_turn(solve: dict[str, Any]) -> dict[str, Any]:
    return convince_as_turn(solve) if solve.get("mechanic") in CONVINCE_MECHANICS else solve_as_turn(solve)


def _said_by(who: str | None, say: dict[str, Any] | None) -> dict[str, Any]:
    return {"who": who or "caption", "kind": "speech" if who else "caption", "mood": "neutral", "direction": None, **(say or {})}


def convince_as_turn(solve: dict[str, Any]) -> dict[str, Any]:
    """WP-113 «Convaincre» as a turn: the character's first objection is the question;
    each reply either lands (the solve's ``lands`` beats and ``sets_on_land``) or is
    met by the next objection; after the last objection, or a give-up, it fails
    (``fails``, ``sets_on_fail``). The interlude always plays once before the outcome."""

    to = solve.get("to")
    objections = list(solve.get("objections") or [])
    prompt = solve.get("prompt") or {}
    objection_panels = [
        {"kind": "panel", "id": f"{solve['id']}.objection{n + 1}", "lines": [_said_by(to, say)]} for n, say in enumerate(objections)
    ]
    give_up = solve.get("give_up") or {}
    return {
        "kind": "turn",
        "id": solve["id"],
        "to": to or "lila_bonnet",
        "to_name": None,
        "panel": {
            "kind": "panel",
            "id": f"{solve['id']}.prompt",
            "visual": solve.get("visual"),
            "location_id": None,
            "in_frame": [to] if to else [],
            "silence": False,
            "flashback": False,
            "diegetic": [],
            "balloon": True,
            "lines": [_said_by(None, prompt), *(objection_panels[0]["lines"] if objection_panels else [])],
        },
        "task_native": solve.get("task_native"),
        "listens_for": solve.get("lands_means") or "Whether the argument touches them.",
        "replies": [
            {
                "id": "lands",
                "label": "lands",
                "means": solve.get("lands_means") or "A sincere argument that touches them.",
                "examples": list(solve.get("lands_examples") or []),
                "clumsy": False,
                "path": None,
                "repeat_once": False,
                "sets": dict(solve.get("sets_on_land") or {}),
                "sets_if": [],
                "beats": list(solve.get("lands") or []),
                "again": [],
            },
            {
                "id": "give_up",
                "label": give_up.get("text_fr") or "give_up",
                "means": "The learner gives up or lets them be.",
                "examples": [give_up["text_fr"]] if give_up.get("text_fr") else [],
                "clumsy": False,
                "path": None,
                "repeat_once": False,
                "sets": dict(solve.get("sets_on_fail") or {}),
                "sets_if": [],
                "beats": list(solve.get("fails") or []),
                "again": [],
            },
            {
                "id": "objection",
                "label": "objection",
                "means": "The argument does not touch them yet, or is off the point.",
                "examples": [],
                "clumsy": False,
                "path": None,
                "repeat_once": False,
                "sets": {},
                "sets_if": [],
                "beats": [],
                "again": [],
            },
        ],
        "fallback": "objection",
        "gate": None,
        "small": False,
        "sets": {},
        "sets_if": [],
        "after": [],
        "from_solve": "convaincre",
        "convince": {
            "objections": objection_panels,
            "attempts": max(1, len(objection_panels)),
            "interlude": list(solve.get("interlude") or []),
            "fails": list(solve.get("fails") or []),
            "sets_on_fail": dict(solve.get("sets_on_fail") or {}),
        },
    }


def convince_outcome(turn: dict[str, Any], reply_id: str | None, *, attempt: int) -> list[dict[str, Any]]:
    """WP-113 «Convaincre»: what the page says after the learner's ``attempt``-th
    argument (0-based): the next objection, or the interlude and how it ends."""

    convince = turn.get("convince") or {}
    attempts = int(convince.get("attempts") or 1)
    interlude = list(convince.get("interlude") or [])
    if reply_id == "lands":
        lands = next((row for row in turn.get("replies") or [] if row.get("id") == "lands"), {})
        return [*interlude, *(lands.get("beats") or [])]
    if reply_id == "give_up" or attempt + 1 >= attempts:
        return [*interlude, *(convince.get("fails") or [])]
    objections = list(convince.get("objections") or [])
    return [objections[attempt + 1]] if attempt + 1 < len(objections) else []


def exchanges_for(turn: dict[str, Any]) -> int:
    """How many exchanges a turn can take: a «Convaincre» one per objection."""

    return int((turn.get("convince") or {}).get("attempts") or 1)


def choice_cards(turn: dict[str, Any]) -> list[dict[str, Any]]:
    """WP-113: a choice turn's cards for the client — ``[{id, label_fr, label_native}]``."""

    if not turn.get("choice"):
        return []
    return [
        {"id": str(reply.get("id")), "label_fr": str(reply.get("label") or reply.get("id")), "label_native": reply.get("label_native")}
        for reply in turn.get("replies") or []
    ]


def solve_as_turn(solve: dict[str, Any]) -> dict[str, Any]:
    """A solve posed as a question with its options as the replies. A «choix» is
    answered by tapping a card (WP-113); the others are a projection only."""

    prompt = solve.get("prompt") or {}
    replies = []
    for option in solve.get("options") or []:
        label = (option.get("label") or {}).get("text_fr") or option.get("id")
        replies.append(
            {
                "id": option["id"],
                "label": label,
                "means": f"The learner answers «{label}».",
                "examples": [label],
                "clumsy": False,
                "path": None,
                "repeat_once": False,
                "sets": dict(option.get("sets") or {}),
                "sets_if": list(option.get("sets_if") or []),
                "beats": list(option.get("beats") or []),
                "again": [],
                "label_native": (option.get("label") or {}).get("text_native"),
            }
        )
    return {
        "kind": "turn",
        "id": solve["id"],
        "to": solve.get("to") or "lila_bonnet",
        "to_name": None,
        "panel": {
            "kind": "panel",
            "id": f"{solve['id']}.prompt",
            "visual": solve.get("visual"),
            "location_id": None,
            "in_frame": [],
            "silence": False,
            "flashback": False,
            "diegetic": [],
            "balloon": True,
            "lines": [{"who": "caption", "kind": "caption", "mood": "neutral", "direction": None, **prompt}],
        },
        "task_native": solve.get("task_native"),
        "listens_for": "Which of the options the learner names.",
        "replies": replies,
        "fallback": solve.get("default") or (replies[0]["id"] if replies else "none"),
        "gate": None,
        "small": False,
        "sets": {},
        "sets_if": [],
        "after": list(solve.get("nudge") or []),
        "from_solve": solve.get("mechanic"),
        "choice": solve.get("mechanic") in CHOICE_MECHANICS,
    }
