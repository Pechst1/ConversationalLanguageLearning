"""WP-132B «Après la finale»: what a season life reads once T8 is played (content program D8).

D8: «s1 gets an authored epilogue week, then a generated continuation in the s1
world with a real arc. The old Berlin S2 bible is never loaded after s1.» Before this
module a life that finished T8 B met the generic generated days the next morning
(EXPERIENCE-REVIEW 2026-10-04 §6, «the gap after the finale»): a director that knew
nothing of the ending the learner had just chosen, in a world whose arcs were empty,
with Le Mistral open even after it closed.

After the finale, in order:

1. **The epilogue** — when ``app/data/season/<id>/epilogue.json`` exists (owner-
   approved story text; see ``WP-132B-EPILOGUE-PROPOSAL.md``). Its pages are in the
   tentpole format (``Day``/``Panel``/``Turn``, variants chosen by ``when`` on
   ``s1.ending`` like T8's endings, level variants in ``levels*.json``, plain tasks
   in ``tasks.json``), and :func:`attach_epilogue` appends them to the season as
   two-day segments ``e1``, ``e2``… So the clock, the reader, the settle, the
   reprise and the validators serve them exactly as they serve T1–T8: no second
   engine. A malformed epilogue is refused whole (logged), never half-served.
2. **Or the season's end, honestly** — with no epilogue, one authored *archive* day
   (:func:`season_end_brief`): the season's own «À suivre» captions of the
   learner's branches, T1 to T8, read again at the learner's level; one question,
   the season's own («tu le gardes, tu le partages, ou tu le laisses partir ?»);
   and the finale's last caption as its ending. Every French line on it is a bible
   line the learner has already read; only the task is chrome, in their language.
   It is served once, settled like a page (nothing set, no day counted), and marks
   the season ended (``state["ended"]``).
3. **Then the continuation** — generated days in the s1 world (never the old
   serial's season 2: ``living_story.roll_over_season`` already refuses it for a
   scripted world), told what this life's ending actually was
   (:func:`carried`, ``context["season_script"]["after_finale"]``), and seeded with
   it: the ending's facts become ``live["world_flags"]`` and the open question of
   the learner's own last page joins ``live["threads_archive"]``, which is what the
   written and the reprise seasons are built from (:func:`carry_into_live`).

**When the provider is down.** Every page above needs no model. A generated
continuation day that is lost is re-read by WP-124a's reprise: the last completed
page of this life — the epilogue's last day, or T8 B — never a stranger's scene,
never a reset.

**A life that ended before an epilogue shipped** keeps its ending: once the archive
day has closed the season (``ended.via == "season_end"``), :func:`position_for`
reports the season finished even though the season now has epilogue segments, so
a learner three weeks into the continuation is never pulled back to the morning
after the train.

Pure functions over the season files and ``live["season_script"]``; the hooks that
call them are a few lines each in ``format.load_season``, ``runtime`` and
``living_story.generate_scene`` (see the WP-132B report).
"""

from __future__ import annotations

import json
import logging
from dataclasses import replace as dc_replace
from pathlib import Path
from typing import Any

from pydantic import Field

from app.services.season.clock import SEASON_KEY, Position, played_log, position
from app.services.season.flags import PAINTING_BY_ENDING, effective_flags
from app.services.season.format import (
    Day,
    FlagSpec,
    Hook,
    Line,
    Panel,
    Reply,
    Season,
    SeasonFormatError,
    Segment,
    Tentpole,
    Turn,
    _check_tentpole,
    _Model,
    iter_movements,
)
from app.services.season.page import choose_day, hook_caption, resolve_day

logger = logging.getLogger(__name__)

#: ``app/data/season/<id>/EPILOGUE_FILE`` — the authored epilogue week (proposal-only data).
EPILOGUE_FILE = "epilogue.json"
#: The ``file_id`` its level variants and plain tasks are keyed under (``levels*.json``,
#: ``tasks.json``), like ``t8``.
EPILOGUE_FILE_ID = "epilogue"
#: ``live["season_script"][END_KEY]`` — the season is closed: ``{on, event_id, via}``.
END_KEY = "ended"
#: ``context["season_script"][CARRIED_KEY]`` — what the continuation inherits.
CARRIED_KEY = "after_finale"
#: ``story_context["season"][SEASON_END_KEY]`` marks the archive day.
SEASON_END_KEY = "season_end"
#: The archive day's segment id (never a segment of the season itself).
SEASON_END_SEGMENT = "end"
#: ``live[CARRIED_MARK]`` — the season whose ending has been carried into the life.
CARRIED_MARK = "season_carried"
#: The finale's three endings (bible 08, «Ending selection»).
ENDINGS = ("garder", "partager", "laisser_partir")
#: Lila's paths the epilogue must read for every ending.
PATHS = ("romance", "friendship", "open")
#: The bands every ending's epilogue page must resolve at.
BANDS = ("A1", "A2", "B1", "B2", "C1")


# ---------------------------------------------------------------------------
# The epilogue file
# ---------------------------------------------------------------------------


class AfterPage(Tentpole):
    """An epilogue page (``e1``…``e9``), or the archive day (``end``): a tentpole in
    every respect but its id."""

    id: str = Field(pattern=r"^(e[1-9]|end)$")


class EpilogueFile(_Model):
    """``epilogue.json``: the epilogue's segments (two days each, played in order after
    the season's last segment), its pages, and the flags only it sets."""

    id: str = Field(min_length=1)
    title_fr: str = Field(min_length=1)
    intent: str = ""
    segments: list[Segment] = Field(min_length=1)
    pages: list[AfterPage] = Field(min_length=1)
    flags: list[FlagSpec] = Field(default_factory=list)


def epilogue_path(season_id: str, *, root: Path | None = None) -> Path:
    from app.services.season.format import SEASON_ROOT

    return (root or SEASON_ROOT) / season_id / EPILOGUE_FILE


def read_epilogue(folder: Path, *, levels: dict[str, Any], tasks: dict[str, Any]) -> EpilogueFile | None:
    """The epilogue of the season in ``folder`` with its level variants and plain tasks
    folded in, or ``None`` when it has none. Raises on a malformed file."""

    from app.services.season.levels import apply_levels, apply_tasks

    path = folder / EPILOGUE_FILE
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SeasonFormatError(f"{path.name}: {exc}") from exc
    raw = apply_tasks(apply_levels(raw, levels, file_id=EPILOGUE_FILE_ID), tasks, file_id=EPILOGUE_FILE_ID)
    try:
        return EpilogueFile.model_validate(raw)
    except ValueError as exc:
        raise SeasonFormatError(f"{path.name}: {exc}") from exc


def with_epilogue(season: Season, epilogue: EpilogueFile) -> Season:
    """``season`` with the epilogue's segments, pages and flags appended (unchecked)."""

    known = {row.id for row in season.flags}
    return season.model_copy(
        update={
            "segments": [*season.segments, *epilogue.segments],
            "tentpoles": {**season.tentpoles, **{page.id: page for page in epilogue.pages}},
            "flags": [*season.flags, *[row for row in epilogue.flags if row.id not in known]],
        }
    )


def epilogue_ids(season: Season) -> list[str]:
    """The epilogue's segment ids, in play order ([] for a season without one)."""

    return [segment.id for segment in season.segments if segment.id[:1] == "e" and segment.id in season.tentpoles]


def has_epilogue(season: Season) -> bool:
    return bool(epilogue_ids(season))


def is_epilogue_segment(segment_id: str | None) -> bool:
    return bool(segment_id) and str(segment_id)[:1] == "e" and str(segment_id)[1:].isdigit()


def _probe_flags(ending: str, path: str) -> dict[str, Any]:
    return {"s1.ending": ending, "s1.painting": PAINTING_BY_ENDING.get(ending), "s1.lila_path": path}


def world_addressees(folder: Path) -> set[str] | None:
    """The cast a page's turn may address: the season world's cast (``world.json``).
    ``runtime.tentpole_brief`` refuses a day whose speaker the world lacks."""

    path = folder / "world.json"
    if not path.is_file():
        return None
    try:
        cast = json.loads(path.read_text(encoding="utf-8")).get("cast") or []
    except (OSError, json.JSONDecodeError):
        return None
    return {str(member.get("id")) for member in cast if isinstance(member, dict) and member.get("id")} or None


def epilogue_problems(
    season: Season,
    epilogue: EpilogueFile,
    *,
    locations: set[str] | None = None,
    addressees: set[str] | None = None,
) -> list[str]:
    """Everything that would stop the epilogue reading whole, for every ending.

    The format's own cross-references (speakers, flags, conditions, locations), plus
    the WP-132B promise: every day of every page resolves for each of the three
    endings, on each of Lila's paths, at every band — no ending meets a blank day —
    and every turn addresses someone the season's world has (``addressees``).
    """

    problems: list[str] = []
    ids = [segment.id for segment in epilogue.segments]
    pages = {page.id: page for page in epilogue.pages}
    if len(set(ids)) != len(ids):
        problems.append("epilogue: segment ids repeat")
    clash = set(ids) & {segment.id for segment in season.segments}
    if clash:
        problems.append(f"epilogue: segment ids {sorted(clash)} are already the season's")
    for segment in epilogue.segments:
        if not is_epilogue_segment(segment.id):
            problems.append(f"epilogue: segment {segment.id!r} is not named e1…e9")
        if segment.kind != "tentpole" or segment.days != 2:
            problems.append(f"epilogue: {segment.id} must be a two-day authored page (kind tentpole, days 2)")
        if segment.id not in pages:
            problems.append(f"epilogue: {segment.id} has no page")
    for page_id in pages:
        if page_id not in ids:
            problems.append(f"epilogue: page {page_id} is in no segment")
    joined = with_epilogue(season, epilogue)
    for page in epilogue.pages:
        problems.extend(f"epilogue {message}" for message in _check_tentpole(joined, page, locations=locations))
        for ending in ENDINGS:
            for path in PATHS:
                for band in BANDS:
                    for letter in ("a", "b"):
                        if choose_day(page, letter, _probe_flags(ending, path), band=band) is None:
                            problems.append(f"epilogue {page.id}.{letter}: no day for ending {ending}, path {path}, {band}")
        for day in page.days:
            hooks = [row for row in day.movements if isinstance(row, Hook)]
            if not hooks:
                problems.append(f"epilogue {page.id}.{day.day} ({day.variant or 'all'}): no hook to end on")
            turns = [row for row in iter_movements(day.movements) if isinstance(row, Turn)]
            if not turns:
                problems.append(f"epilogue {page.id}.{day.day} ({day.variant or 'all'}): no turn for the learner")
            for turn in turns:
                if addressees is not None and turn.to not in addressees:
                    problems.append(f"epilogue {page.id}.{day.day}: turn {turn.id} addresses {turn.to!r}, who is not in the season world's cast")
    return sorted(dict.fromkeys(problems))


def attach_epilogue(season: Season, folder: Path, *, levels: dict[str, Any], tasks: dict[str, Any]) -> Season:
    """``format.load_season``'s hook: the season with its epilogue, when it has a whole one.

    A missing file leaves the season as it is. A file that does not parse or does not
    hold together is refused whole and logged: the life then closes its season with
    the archive day, never with half an epilogue (``scripts/season_check.py`` and
    ``tests/test_wp132b_epilogue.py`` fail loudly on the same file).
    """

    try:
        epilogue = read_epilogue(folder, levels=levels, tasks=tasks)
    except SeasonFormatError:
        logger.exception("season %s: the epilogue does not parse; the season ends without it", season.id)
        return season
    if epilogue is None:
        return season
    problems = epilogue_problems(season, epilogue, addressees=world_addressees(folder))
    if problems:
        logger.error("season %s: the epilogue is refused: %s", season.id, "; ".join(problems[:8]))
        return season
    return with_epilogue(season, epilogue)


# ---------------------------------------------------------------------------
# Where a life stands after the finale
# ---------------------------------------------------------------------------


def ended(state: dict | None) -> dict[str, Any] | None:
    row = (state or {}).get(END_KEY)
    return dict(row) if isinstance(row, dict) else None


def finale_played(season: Season, state: dict | None) -> bool:
    """Has this life played the season's own last segment (T8 B)?"""

    own = [segment for segment in season.segments if not is_epilogue_segment(segment.id)]
    if not own:
        return False
    last = own[-1]
    log = played_log(state)
    return sum(1 for row in log if row.get("segment") == last.id) >= (2 if last.kind == "tentpole" else 1)


def position_for(season: Season, state: dict | None, *, today: Any) -> Position:
    """``clock.position``, except that a season already closed by the archive day
    stays closed when an epilogue ships later (see the module docstring)."""

    pos = position(season, state, today=today)
    if (
        not pos.finished
        and pos.segment is not None
        and is_epilogue_segment(pos.segment.id)
        and (ended(state) or {}).get("via") == "season_end"
    ):
        return Position(season.id, None, len(season.segments), 0, pos.season_day, finished=True)
    return pos


def season_finished(season: Season, state: dict | None) -> bool:
    return position_for(season, state, today=None).finished


def phase(season: Season, state: dict | None, *, today: Any = None) -> str:
    """``season`` (T1–T8), ``epilogue``, ``season_end`` (the archive day is owed) or
    ``continuation``."""

    pos = position_for(season, state, today=today)
    if not pos.finished:
        return "epilogue" if pos.segment is not None and is_epilogue_segment(pos.segment.id) else "season"
    if ended(state) or has_epilogue(season):
        return "continuation"
    return "season_end"


# ---------------------------------------------------------------------------
# What the continuation inherits
# ---------------------------------------------------------------------------

#: The open question every ending hands on (bible 08, «State out → season 2»).
OPEN_QUESTION = "Who is «L.», and what did Odile leave in Paris besides the flat?"

#: What each ending left true (bible 08, each ending's «What happened» and «Who
#: remembers what»), for the director of the generated continuation. Director
#: facts, never shown to a learner.
ENDING_FACTS: dict[str, tuple[str, ...]] = {
    "garder": (
        "The learner kept Odile's flat above Le Mistral and lives there now.",
        "Le Mistral is exactly as it was; Margaux runs it alone, on a nine-year lease.",
        "M. Marchand left the building for a residence without stairs; Solvel owns his floors, he kept the café's walls.",
        "Only four people know Odile's notebook page; Gus knows nothing of it.",
        "The painting «Le Mistral sur le canal» is with the learner; its back reads «Pour Odile, qui part. — L., 1970» and «Toujours rue de Lancry. — L., 2021».",
        "Marin has put his co-op folder in a drawer.",
    ),
    "partager": (
        "Le Mistral is a co-operative, «Le Mistral à nous»; Margaux is member number 1 and no longer runs it alone.",
        "Odile's flat is the co-op's workshop (children's painting classes, the meeting room); the learner rents the little room under the roof.",
        "Gus lost the café of his childhood as it was; he forgives the learner in his own way («Tu m'as coûté une banquette»).",
        "Gus has the painting in his loft, face to the wall, and says he does not know where it is.",
        "Romy's article «Le feu du Mistral» is public; it earned her a Paris contract.",
        "M. Marchand bought one share of the co-op; he never comes, but he pays.",
    ),
    "laisser_partir": (
        "Le Mistral has closed: its neon went out on the last night. Never stage it as an open café.",
        "Odile's flat is sold to Solvel; the learner kept only Odile's kitchen table.",
        "Margaux has gone to Brittany, to Marin's father's, to see the sea; she writes postcards («Elle est grande.»).",
        "Gus bought the booth's bench and keeps it in his loft.",
        "The painting left with a second-hand dealer's van; it is somewhere in Paris.",
        "Romy's photo essay on the last night is the best thing she has written; M. Marchand sent the learner a Christmas card.",
    ),
}

#: What every ending shares (bible 08: the platform, Camille, the letter).
COMMON_FACTS: tuple[str, ...] = (
    "Lila left for Berlin on 8 January; she lives there now. She writes; she is never in a Paris scene.",
    "Odile's last letter has been read: she left two things in Paris, the flat and someone; for the other, «regarde derrière le tableau du Mistral».",
    "Camille Marchand has met the learner and still says vous; the switch to tu belongs to a later season.",
    "The café question of season 1 is closed. Do not reopen it.",
)

#: The rules no generated day after the finale may break (D8, WP-124a, the review).
CONTINUATION_RULES: tuple[str, ...] = (
    "The whole cast knows the learner: never a stranger's welcome, never the vous of strangers from the group.",
    "This is the s1 world after its finale, not a new story: carry the ending, the choices and the relationships.",
    "Never the old serial's second season («Choisir Paris», a Berlin opening, Montréal, Créteil).",
    "The continuation may look for «L.», ask about the rue de Lancry, follow the painting; it never reveals who L. is — that answer belongs to the next authored season.",
)


def _lila_key(flags: dict[str, Any]) -> str | None:
    """The copy of the key at the platform (bible 08, F4): Lila keeps it on the
    romance path and gives it back on the friendship path."""

    if not flags.get("s1.lila_has_key"):
        return None
    return "kept_by_lila" if flags.get("s1.lila_path") == "romance" else "returned_to_you"


def last_page_caption(season: Season, state: dict | None, flags: dict[str, Any], *, band: str, language: str) -> dict[str, Any] | None:
    """The «À suivre…» of the last season page this life played (the epilogue's last
    day, or T8 B), at the learner's band: the open question in the season's own words."""

    rows = [row for row in played_log(state) if row.get("kind") == "tentpole" and row.get("segment") in season.tentpoles]
    if not rows:
        return None
    row = rows[-1]
    letter = "a" if int(row.get("day_in_segment") or 1) == 1 else "b"
    page = resolve_day(season, str(row["segment"]), letter, flags=flags, band=band, language=language)
    caption = hook_caption(page or {})
    if not caption or not str(caption.get("text_fr") or "").strip():
        return None
    return {"key": str(row.get("key") or ""), "text_fr": caption["text_fr"], "text_native": caption.get("text_native")}


def carried(season: Season, state: dict | None, flags: dict[str, Any], *, band: str, language: str) -> dict[str, Any]:
    """What the generated continuation must know of this life's season (D8)."""

    ending = str(flags.get("s1.ending") or "") or None
    facts = [*ENDING_FACTS.get(str(ending), ()), *COMMON_FACTS]
    if flags.get("marchand.sundays"):
        facts.append("M. Marchand comes to Sunday lunch at the learner's, by the 46 bus, as he did at Odile's.")
    if flags.get("romy.footage") == "kept" and ending == "garder":
        facts.append("Romy gave the learner the memory card with Margaux's admission, without a word.")
    key = _lila_key(flags)
    if key == "kept_by_lila":
        facts.append("Lila kept her copy of the key «pour revenir»: nothing promised, they write to each other.")
    elif key == "returned_to_you":
        facts.append("Lila gave the copy of the key back, «tu me la redonnes quand je reviens».")
    caption = last_page_caption(season, state, flags, band=band, language=language)
    return {
        "season_id": season.id,
        "ended": ended(state),
        "ending": ending,
        "painting": flags.get("s1.painting"),
        "flat_decision": flags.get("s1.flat_decision"),
        "lila_path": flags.get("s1.lila_path"),
        "lila_key": key,
        "kiss": bool(flags.get("s1.kiss")),
        "marchand_sundays": bool(flags.get("marchand.sundays")),
        "camille": {"met": bool(flags.get("camille.met")), "register": "vous"},
        "romy_footage": flags.get("romy.footage"),
        "gus_aristocracy_exposed": bool(flags.get("gus.aristocracy_exposed")),
        "facts": facts,
        "open_question": OPEN_QUESTION,
        "last_page": caption,
        "rules": list(CONTINUATION_RULES),
        "closed_locations": ["le_mistral"] if ending == "laisser_partir" else [],
    }


def context_extra(today: Any) -> dict[str, Any]:
    """``runtime.context_block``'s hook: ``{CARRIED_KEY: …}`` once the season is over."""

    if today is None or not today.pos.finished:
        return {}
    return {
        CARRIED_KEY: carried(today.season, today.state, today.flags, band=today.band, language=today.language),
        "phase": phase(today.season, today.state, today=today.local_date),
    }


_A_SUIVRE = ("À suivre…", "À suivre...", "À suivre", "La suite…")


def _strip_a_suivre(text: str) -> str:
    text = " ".join(str(text or "").split())
    for tail in _A_SUIVRE:
        if text.endswith(tail):
            text = text[: -len(tail)].rstrip()
    return text


def carry_into_live(live: dict[str, Any], *, season: Season | None = None) -> dict[str, Any]:
    """The finished season's ending, written into the life the continuation reads.

    ``world_flags`` gain the ending's facts (``season_writer.season_material`` turns
    them into ``flag`` rows); ``threads_archive`` gains the open question in the
    words of the learner's own last page (a ``thread`` row, the material the written
    and reprise seasons grow their first arc from). Once per season; returns ``live``.
    """

    from app.services.season.format import load_season

    state = live.get(SEASON_KEY) if isinstance(live.get(SEASON_KEY), dict) else None
    if not state or not state.get("id"):
        return live
    season = season or load_season(str(state["id"]))
    if live.get(CARRIED_MARK) == season.id or not season_finished(season, state):
        return live
    flags = effective_flags(season, state)
    carried_flags = {
        key: flags.get(key)
        for key in (
            "s1.ending",
            "s1.painting",
            "s1.flat_decision",
            "s1.lila_path",
            "s1.kiss",
            "lila.in_berlin",
            "camille.met",
            "marchand.sundays",
            "gus.aristocracy_exposed",
        )
        if flags.get(key) not in (None, "", False)
    }
    live = dict(live)
    live["world_flags"] = {**(live.get("world_flags") or {}), **carried_flags}
    caption = last_page_caption(season, state, flags, band="A2", language="en")
    text = _strip_a_suivre((caption or {}).get("text_fr") or "")
    if text:
        row = {"key": f"{season.id}.open_question", "text_fr": text, "state": "open", "season": 1}
        archive = [item for item in live.get("threads_archive") or [] if (item or {}).get("key") != row["key"]]
        live["threads_archive"] = [*archive, row][-20:]
    live[CARRIED_MARK] = season.id
    return live


# ---------------------------------------------------------------------------
# The archive day: the season ends, honestly, without an epilogue
# ---------------------------------------------------------------------------

#: The archive day's task, in the learner's language (chrome, not story text).
SEASON_END_TASK: dict[str, str] = {
    "en": "Season 1 is over. Answer its question in one sentence: what do you keep, share or let go?",
    "de": "Staffel 1 ist zu Ende. Beantworte ihre Frage in einem Satz: Was behältst du, was teilst du, was lässt du gehen?",
    "fr": "La saison 1 est finie. Réponds à sa question en une phrase : qu'est-ce que tu gardes, partages ou laisses partir ?",
}
SEASON_END_LISTENS = "Any sincere answer to the season's question: what the learner keeps, shares or lets go, and why."


def _hook_panel(tentpole: Tentpole, letter: str, flags: dict[str, Any], band: str) -> Panel | None:
    day = choose_day(tentpole, letter, flags, band=band)
    hook = next((row for row in (day.movements if day else []) if isinstance(row, Hook)), None)
    return hook.panel if hook else None


def archive_page(season: Season, flags: dict[str, Any], *, band: str) -> AfterPage | None:
    """The archive day as an authored page, built only from bible text: each
    tentpole's «À suivre» on the learner's branches, the season's question, and the
    finale's last caption. ``None`` when the finale cannot be read."""

    own = [segment for segment in season.segments if segment.kind == "tentpole" and not is_epilogue_segment(segment.id)]
    if not own or own[-1].id not in season.tentpoles:
        return None
    finale = season.tentpoles[own[-1].id]
    finale_b = choose_day(finale, "b", flags, band=band)
    finale_a = choose_day(finale, "a", flags, band=band)
    last_hook = _hook_panel(finale, "b", flags, band)
    if finale_b is None or last_hook is None:
        return None
    movements: list[Any] = []
    for segment in own[:-1]:
        tentpole = season.tentpoles.get(segment.id)
        panel = _hook_panel(tentpole, "b", flags, band) if tentpole else None
        if panel is not None:
            movements.append(panel.model_copy(update={"id": f"end.{segment.id}"}))
    # The finale's own turn says who the learner faces at the end, and its example
    # replies (bible lines) are the hint — nothing here is written for the day.
    finale_turn = next((row for row in (finale_a.movements if finale_a else []) if isinstance(row, Turn)), None)
    examples = [
        example
        for reply in (finale_turn.replies if finale_turn else [])
        for example in reply.examples
        if not reply.clumsy
    ]
    question = Panel(id="end.question", lines=[Line(who="caption", say=season.question)], balloon=True)
    movements.append(
        Turn(
            id="end.turn",
            to=finale_turn.to if finale_turn else "margaux_barman",
            panel=question,
            task=dict(SEASON_END_TASK),
            task_plain=dict(SEASON_END_TASK),
            listens_for=SEASON_END_LISTENS,
            replies=[Reply(id="answer", label="The learner's answer", means=SEASON_END_LISTENS, examples=examples[:3])],
            fallback="answer",
        )
    )
    movements.append(Hook(id="end.hook", role="a_suivre", panel=last_hook.model_copy(update={"id": "end.last"})))
    day = Day(
        day="b",
        story_date_fr=finale_b.story_date_fr,
        title_fr=season.title_fr,
        location_id=finale_b.location_id,
        movements=movements,
        minutes=4,
    )
    # One day, not two: built unvalidated (a tentpole proper needs Day A and Day B).
    return AfterPage.model_construct(
        id=SEASON_END_SEGMENT,
        number=len(own),
        title_fr=season.title_fr,
        intent="",
        state_in=[],
        flags_read=[],
        days=[day],
        shared=dict(finale.shared),
        state_out={},
        for_next_gap=[],
    )


def season_end_brief(today: Any, context: dict[str, Any]):
    """``living_story.generate_scene``'s hook: the archive day when it is owed, else ``None``.

    Served through ``runtime.tentpole_brief`` like any authored page (no model call),
    on a position outside the season's calendar (``end.b``): settling it sets nothing
    and counts no day, and :func:`after_settle` closes the season.
    """

    from app.services.season import runtime

    if today is None or phase(today.season, today.state, today=today.local_date) != "season_end":
        return None
    page = archive_page(today.season, today.flags, band=today.band)
    if page is None:
        logger.error("season %s: the archive day could not be built", today.season.id)
        return None
    season = today.season.model_copy(update={"tentpoles": {**today.season.tentpoles, SEASON_END_SEGMENT: page}})
    pos = Position(
        season_id=season.id,
        segment=Segment(id=SEASON_END_SEGMENT, kind="tentpole", days=2),
        segment_index=len(season.segments),
        day_in_segment=2,
        season_day=today.pos.season_day,
    )
    brief = runtime.tentpole_brief(dc_replace(today, season=season, pos=pos), context)
    if brief is None:
        return None
    season_ctx = dict(brief.story_context.get(runtime.SEASON_CONTEXT_KEY) or {})
    season_ctx[SEASON_END_KEY] = True
    return dc_replace(brief, story_context={**brief.story_context, runtime.SEASON_CONTEXT_KEY: season_ctx})


def after_settle(live: dict[str, Any], season_ctx: dict[str, Any] | None, *, date_iso: str | None, event_id: str) -> dict[str, Any]:
    """``runtime.settle``'s hook, once a day is settled: the archive day closes the
    season; a finished epilogue closes it too; a finished season's ending is carried
    into the life (:func:`carry_into_live`). Idempotent."""

    from app.services.season.format import load_season

    state = live.get(SEASON_KEY) if isinstance(live.get(SEASON_KEY), dict) else None
    if not state or not state.get("id"):
        return live
    try:
        season = load_season(str(state["id"]))
    except Exception:  # noqa: BLE001 - closing a season never costs the day's settle
        logger.exception("season %s: could not be loaded after settle", state.get("id"))
        return live
    state = dict(state)
    if not ended(state):
        via = None
        if (season_ctx or {}).get(SEASON_END_KEY):
            via = "season_end"
        elif has_epilogue(season) and season_finished(season, state):
            via = "epilogue"
        if via:
            state[END_KEY] = {"on": date_iso, "event_id": event_id, "via": via}
    live = {**live, SEASON_KEY: state}
    if finale_played(season, state):
        live = carry_into_live(live, season=season)
    return live


__all__ = [
    "CARRIED_KEY",
    "END_KEY",
    "EPILOGUE_FILE",
    "SEASON_END_KEY",
    "AfterPage",
    "EpilogueFile",
    "after_settle",
    "archive_page",
    "attach_epilogue",
    "carried",
    "carry_into_live",
    "context_extra",
    "epilogue_problems",
    "has_epilogue",
    "phase",
    "position_for",
    "read_epilogue",
    "season_end_brief",
    "season_finished",
]
