"""Story-quality plan, Phase 1, «Maßstab»: the judge — pages scored the way a reader reads them.

The loss rate says whether a day was served, not whether it was worth reading, so a prompt
change could only be guessed at. Here a stronger model than the writer
(``OPENAI_GRAPHIC_NOVEL_PREMIUM_SCRIPT_MODEL``, gpt-5.5 in production) reads each page and
answers the plan's six questions from 1 to 5, each with one sentence and the line it is about:

* **rubric** — every generated day of one or more live-read transcripts
  (``tests/test_wp133a_live_read.py``); «new» compares with the previous page's summary;
* **pairwise** — the same story positions of an old and a new run, shown in a seeded random
  order; the judge picks the page a reader would rather read;
* **benchmark** — the authored tentpole pages (``app/data/season/s1/t1.json`` … ``t8.json``) at
  one level, through the same rubric minus «new»: the bar the written days set.

The gate is the plan's: median ≥ 4 for «natural» and «clear_question», no question with a
median below 3, and the new page wins at least 2 of 3 comparisons, read on the whole run: a
run that missed a judgement it set out to make is ``incomplete``. Calls go through
:class:`~app.services.llm_service.LLMService` (injected, so tests pass a fake) under a spend cap
checked before every call. Nothing here runs in the app; ``scripts/story_judge.py`` is the CLI.
"""

from __future__ import annotations

import json
import random
import re
import statistics
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.services.chrome_language import chrome_language, level_band
from app.services.season.flags import effective_flags
from app.services.season.format import load_season
from app.services.season.page import reply_by_id, resolve_day, turns_of
from app.services.season.transcript import render_tentpole_day

#: The rubric: what 5 of 5 means (plan, «Rubrik mit Richter-Modell»).
QUESTIONS: dict[str, str] = {
    "natural": "every line is something this person would say in this moment.",
    "clear_question": (
        "one question to the learner, answerable in their own words; the task line says the same."
    ),
    "something_happens": (
        "at the end something is different from the start, even without the learner's answer."
    ),
    "new": (
        "the question is new, and the place or the lead character changes compared with the "
        "previous day."
    ),
    "voices": "you can tell each character by their line even without the name.",
    "level": "the words fit the learner's level; the drama is the same as it would be at C1.",
}

#: The plan's gate.
GATE_HIGH = ("natural", "clear_question")
GATE_HIGH_MEDIAN = 4
GATE_FLOOR_MEDIAN = 3
GATE_WINS = (2, 3)  # the new page wins at least 2 of every 3 comparisons

DEFAULT_CAP_USD = 0.60
DEFAULT_MAX_TOKENS = 4000
DEFAULT_REASONING_EFFORT = "low"
DEFAULT_SEED = "story-judge"
REQUEST_TIMEOUT_SECONDS = 180.0
LOWEST_SHOWN = 8


def default_model() -> str:
    """The judge reads with a stronger model than the writer: the premium script model."""

    # Imported here: reading and rendering pages needs no app settings (no ``.env``).
    from app.config import settings

    return str(settings.OPENAI_GRAPHIC_NOVEL_PREMIUM_SCRIPT_MODEL)


# ---------------------------------------------------------------------------
# Reading a transcript (the parser of the 2026-10-15 readability baseline)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Item:
    """One thing on a page, in reading order.

    ``kind`` is ``panel`` (``who`` its label, ``text`` the picture, ``note`` "silent"),
    ``caption``, ``written`` (text drawn in the art), ``document`` (``who`` SMS, LETTER, CARD,
    OBJECTION or DOCUMENT), ``line`` (``who`` the speaker, ``note`` the stage direction),
    ``choice`` (a solve's question), ``cards``, ``taken`` (the card the story took), ``task``
    or ``learner``.
    """

    kind: str
    text: str = ""
    who: str = ""
    note: str = ""


_SPEECH = re.compile(r"^\*\*(?P<who>[^*]+)\*\*(?P<rest>[^«]*)«(?P<text>.*)»\s*$")
_PANEL = re.compile(
    r"^\*\*(?P<label>[^*]+)\*\*(?P<silent>\s*\*\(silence\)\*)?(?:\s*—\s*\*(?P<visual>.*)\*)?\s*$"
)
_SOLVE = re.compile(r"^\S+ · (?:enquete|choix|dechiffrer|convaincre|balloon_choice)$")
_DIRECTION = re.compile(r"\(([^)]*)\)")
_QUOTED = re.compile(r"«(.*)»")
_TASK = re.compile(r"^\*Ta tâche\s*:\s*|\*$")
_CAPTION = re.compile(r"^> \*(?P<text>.*)\*\s*$")
_DOCUMENT = re.compile(r"^> \*\*(?P<kind>[A-Z]+)\*\* — (?P<text>.*)$")
_OBJECTION = re.compile(r"^> objection — «(?P<text>.*)»\s*$")
_TAKEN = re.compile(r"l'histoire prend : \[ (?P<label>.*?) \]")


def _quoted_item(line: str, items: list[Item]) -> Item | None:
    """A ``>`` line: a caption, text in the art, a message, or a document read in a solve
    (whose lines run on, so they join the document before them)."""

    if line.startswith("> ✎"):
        return Item("written", line[3:].strip())
    for pattern, kind in ((_DOCUMENT, None), (_OBJECTION, "OBJECTION")):
        match = pattern.match(line)
        if match:
            return Item("document", match.group("text").strip(), who=kind or match.group("kind"))
    caption = _CAPTION.match(line)
    if caption:
        return Item("caption", caption.group("text").strip())
    text = line[1:].strip()
    if items and items[-1].kind == "document" and items[-1].who == "DOCUMENT":
        last = items.pop()
        return Item(
            "document", " / ".join(part for part in (last.text, text) if part), who="DOCUMENT"
        )
    return Item("document", text, who="DOCUMENT") if text else None


def parse_lines(lines: Iterable[str]) -> list[Item]:
    """A transcript's day section (or ``render_tentpole_day``'s lines) as reading-order items.

    The harness's own notes — the route a reply took, the director's checklist, a turn left
    unplayed — are not on the learner's page, so they are dropped.
    """

    items: list[Item] = []
    for raw in lines:
        line = raw.rstrip()
        if line.strip() == "---":
            break  # the transcript's trailer (spend, flags) is not a page
        if not line.strip():
            continue
        if line.startswith("*Ta tâche"):
            items.append(Item("task", _TASK.sub("", line).strip()))
        elif line.startswith("**Toi**"):
            quoted = _QUOTED.search(line)
            items.append(Item("learner", quoted.group(1).strip() if quoted else ""))
        elif line.startswith(">"):
            item = _quoted_item(line, items)
            if item:
                items.append(item)
        elif line.startswith("Cartes : "):
            items.append(Item("cards", line[len("Cartes : ") :].strip()))
        elif line.startswith("*→"):
            taken = _TAKEN.search(line)
            if taken:
                items.append(Item("taken", taken.group("label").strip()))
        elif speech := _SPEECH.match(line):
            who = speech.group("who").strip()
            if _SOLVE.match(who):
                items.append(Item("choice", speech.group("text").strip(), who=who))
            else:
                direction = _DIRECTION.search(speech.group("rest"))
                note = direction.group(1).strip() if direction else ""
                items.append(Item("line", speech.group("text").strip(), who=who, note=note))
        elif panel := _PANEL.match(line):
            silent = "silent" if panel.group("silent") else ""
            visual = (panel.group("visual") or "").strip()
            items.append(Item("panel", visual, who=panel.group("label").strip(), note=silent))
    return items


def days(text: str) -> Iterator[str]:
    """The generated days of a transcript: each ``## `` section whose heading says «(jour généré)»."""

    for part in re.split(r"^## ", text, flags=re.M):
        if part and "(jour généré)" in part.splitlines()[0]:
            yield part


def classify(day: str) -> tuple[list[tuple[str, str]], list[tuple[str, str]], str | None]:
    """The baseline's view of one day: ``(page, replies, task)``, ``page`` and ``replies`` as
    ``(kind, text)`` captions and lines before and after the learner's first turn."""

    page: list[tuple[str, str]] = []
    replies: list[tuple[str, str]] = []
    task: str | None = None
    seen_learner = False
    for item in parse_lines(day.splitlines()[1:]):
        if item.kind == "task":
            task = item.text
        elif item.kind == "learner":
            seen_learner = True
        elif item.kind in ("caption", "line", "choice"):
            kind = "caption" if item.kind == "caption" else "line"
            (replies if seen_learner else page).append((kind, item.text))
    return page, replies, task


@dataclass
class Page:
    """One page as the judge reads it."""

    source: str
    key: str
    title: str
    #: ``generated`` (written by the model) or ``authored`` (a tentpole or epilogue page).
    kind: str
    level: str
    items: list[Item]
    day: int | None = None
    #: What «new» compares with; ``None`` when there is no previous page.
    previous_summary: str | None = None

    @property
    def label(self) -> str:
        if not self.source:
            return self.key
        path = Path(self.source)
        where = f"{path.parent.name}/{path.name}" if path.parent.name else path.name
        return f"{where} {self.key}"

    @property
    def text(self) -> str:
        return render_page(self.items)


def render_page(items: Sequence[Item]) -> str:
    """The page as the judge reads it: the French text, with the pictures as [notes]."""

    out: list[str] = []
    panels = 0
    for item in items:
        if item.kind == "panel":
            panels += 1
            head = f"Panel {panels}" + (", no words" if item.note == "silent" else "")
            # A panel with no picture of its own keeps the one before (``format.Panel``).
            out.append(f"[{head}: {item.text or 'the same picture'}]")
        elif item.kind == "caption":
            out.append(f"Caption: {item.text}")
        elif item.kind == "written":
            out.append(f"[Written in the picture: {item.text}]")
        elif item.kind == "document":
            out.append(f"{item.who.capitalize()}: {item.text}")
        elif item.kind == "line":
            note = f" [{item.note}]" if item.note else ""
            out.append(f"{item.who}{note}: «{item.text}»")
        elif item.kind == "choice":
            out.append(f"Question with cards: «{item.text.strip('«»')}»")
        elif item.kind == "cards":
            out.append(f"Cards: {item.text}")
        elif item.kind == "taken":
            out.append(f"(The story takes the card: {item.text})")
        elif item.kind == "task":
            out.append(f"Task line: {item.text}")
        elif item.kind == "learner":
            out.append(f"Learner (scripted): «{item.text}»")
    return "\n".join(out)


def _short(text: str, limit: int) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[: limit - 1].rsplit(" ", 1)[0] + "…"


def summarize(page: Page, *, limit: int = 160) -> str:
    """What «new» compares today with: the previous page's title, where it opens and what it
    asked the learner (a deterministic summary, so it costs no call)."""

    opening = next(
        (
            item.text
            for item in page.items
            if item.kind == "caption" or (item.kind == "panel" and item.text)
        ),
        "",
    )
    asks: list[str] = []
    said: Item | None = None
    for item in page.items:
        if item.kind in ("line", "document"):
            said = item
        elif item.kind == "choice":
            asks.append(f"cards «{_short(item.text.strip('«»'), limit)}»")
        elif item.kind == "task" and said is not None:
            asks.append(
                f"{said.who}: «{_short(said.text, limit)}» (task: {_short(item.text, limit)})"
            )
            said = None
        elif item.kind == "learner":
            said = None
    parts = [f"«{page.title}»", f"opens: {_short(opening, 240)}"]
    if asks:
        parts.append("asks the learner: " + "; ".join(asks[-3:]))
    return " · ".join(parts)


_HEADING = re.compile(r"^Jour (?P<day>\d+) — (?P<rest>.+)$")
_GENERATED = re.compile(r"^(?P<key>\S+) \(jour généré\)(?: · (?P<title>.*))?$")
_AUTHORED = re.compile(r"^(?P<arc>\S+) · (?P<title>.+?) · (?:jour (?P<letter>[AB])|pont)\b")
_LEVEL = re.compile(r"niveau ([ABC][12](?:\.\d)?)")


def transcript_level(text: str, source: str = "") -> str | None:
    """The band a transcript was played at: its header says «niveau B1.1»; else its file name."""

    match = _LEVEL.search(text) or re.match(r"([ABC][12])", Path(source).name)
    return level_band(match.group(1)) if match else None


def read_transcript(text: str, *, source: str = "", level: str | None = None) -> list[Page]:
    """Every page of a live-read transcript, tentpole and generated, in order.

    Each page carries the previous page's summary for «new». A lost day re-reads an earlier
    page and shows no page of its own, so it is skipped and the page before it stays «yesterday».
    """

    band = level_band(level) if level else transcript_level(text, source)
    if band is None:
        raise ValueError(f"{source or 'transcript'}: no level in its header; pass one")
    pages: list[Page] = []
    for part in re.split(r"^## ", text, flags=re.M)[1:]:
        heading, _, body = part.partition("\n")
        match = _HEADING.match(heading.strip())
        if not match or match.group("rest").startswith("jour perdu"):
            continue
        day, rest = int(match.group("day")), match.group("rest").strip()
        generated = _GENERATED.match(rest)
        if generated:
            key = generated.group("key")
            key = key if re.fullmatch(r"g\d+\.\d+", key) else f"day {day}"
            kind, title = "generated", (generated.group("title") or "").strip()
        else:
            authored = _AUTHORED.match(rest)
            letter = (authored.group("letter") or "pont").lower() if authored else ""
            key = f"{authored.group('arc').lower()}.{letter}" if authored else rest
            kind, title = "authored", authored.group("title").strip() if authored else rest
        pages.append(
            Page(
                source=source,
                key=key,
                title=title,
                kind=kind,
                level=band,
                items=parse_lines(body.splitlines()),
                day=day,
                previous_summary=summarize(pages[-1]) if pages else None,
            )
        )
    return pages


def load_transcript(path: Path | str, *, level: str | None = None) -> list[Page]:
    path = Path(path)
    return read_transcript(path.read_text(encoding="utf-8"), source=str(path), level=level)


def generated_pages(pages: Iterable[Page]) -> list[Page]:
    return [page for page in pages if page.kind == "generated"]


# ---------------------------------------------------------------------------
# The authored pages (benchmark)
# ---------------------------------------------------------------------------


def _bible_answer(turn: dict[str, Any]) -> dict[str, Any]:
    """A turn answered with the bible's own example at this level: the first route that has one."""

    reply = next((row for row in turn.get("replies") or [] if row.get("examples")), None)
    reply = reply or reply_by_id(turn, turn.get("fallback"))
    examples = reply.get("examples") or []
    return {
        "turn_id": turn.get("id"),
        "learner": examples[0] if examples else reply.get("label"),
        "reply_id": reply.get("id"),
    }


def benchmark_pages(level: str = "B1", *, season_id: str = "s1", day: str = "a") -> list[Page]:
    """One authored page per tentpole (Day A by default), as a learner at ``level`` reads it.

    The season loader writes every line at the level (``levels.py``), ``resolve_day`` keeps what
    holds on the default flags, and ``render_tentpole_day`` lays the page out exactly as the
    live-read transcripts print a tentpole day — with the bible's example answer where the
    transcript has the harness's. From B1 the task line is French, as the app serves it.
    """

    band = level_band(level) or "B1"
    season = load_season(season_id)
    flags = effective_flags(season, {}, seed=DEFAULT_SEED)
    language = chrome_language("en", band)
    tentpoles = sorted(
        (row for row in season.tentpoles.values() if re.fullmatch(r"t\d", row.id)),
        key=lambda row: row.number,
    )
    pages: list[Page] = []
    for tentpole in tentpoles:
        page = resolve_day(season, tentpole.id, day, flags=flags, band=band, language=language)
        if page is None:
            continue
        routing = [_bible_answer(turn) for turn in turns_of(page)]
        lines = "\n".join(render_tentpole_day(page, routing)).splitlines()
        pages.append(
            Page(
                source=f"app/data/season/{season_id}/{tentpole.id}.json",
                key=f"{tentpole.id}.{day}",
                title=str(page.get("title_fr") or tentpole.title_fr),
                kind="authored",
                level=band,
                items=parse_lines(lines),
            )
        )
    return pages


# ---------------------------------------------------------------------------
# The prompts
# ---------------------------------------------------------------------------

READING = (
    "The page is in French, as the learner reads it. [Brackets] describe the drawing; they are "
    "not text the learner reads. Lines marked «Learner (scripted)» are canned test answers: never "
    "score them, only the page and how the characters answer them."
)


def questions_for(page: Page, *, include_new: bool = True) -> list[str]:
    """The six questions; «new» only when there is a previous page to compare with."""

    skip_new = not include_new or not page.previous_summary
    return [key for key in QUESTIONS if not (key == "new" and skip_new)]


def rubric_messages(page: Page, questions: Sequence[str]) -> tuple[str, str]:
    """``(system, user)`` for one page: the asked questions' 5/5 and the page."""

    definitions = "\n".join(f"- {key}: {QUESTIONS[key]}" for key in questions)
    system = (
        "You judge one day of a French comic-strip story written for language learners, the way "
        f"a reader reads it.\n{READING}\n\n"
        f"Score each question below from 1 to 5. 5 means:\n{definitions}\n"
        "1 means the page clearly fails it; 3 means it half holds.\n\n"
        "Answer with strict JSON only, one key per question: "
        '{"<question>": {"score": <integer 1-5>, "reason": "<one sentence>", '
        '"line": "<the line it is about, copied from the page>"}}'
    )
    head = [f"Learner level: {page.level}"]
    if "new" in questions and page.previous_summary:
        head.append(f"Previous day: {page.previous_summary}")
    head.append("Questions: " + ", ".join(questions))
    return system, "\n".join([*head, "", f"Page «{page.title}»:", page.text])


PAIRWISE_SYSTEM = (
    "You compare two versions, A and B, of the same day of a French comic-strip story written for "
    f"language learners, the way a reader reads them.\n{READING}\n\n"
    "Pick the page a reader would rather read: lines a person would really say, one clear question "
    "the learner can answer in their own words, something that happens, characters you can tell "
    "apart, words at the learner's level. Length is no merit.\n\n"
    'Answer with strict JSON only: {"better": "A" or "B", "reason": "<one or two sentences>"}'
)


def pairwise_messages(first: Page, second: Page, *, key: str, level: str) -> tuple[str, str]:
    user = "\n".join(
        [
            f"Learner level: {level}",
            f"Story position: {key}",
            "",
            f"Page A «{first.title}»:",
            first.text,
            "",
            f"Page B «{second.title}»:",
            second.text,
        ]
    )
    return PAIRWISE_SYSTEM, user


def new_shown_first(seed: str, position: str) -> bool:
    """Seeded per position, so a rerun shows each pair the same way whatever else is compared."""

    return random.Random(f"{seed}:{position}").random() < 0.5  # noqa: S311 - a seeded order, not security


def pairwise_plan(
    old_pages: Sequence[Page], new_pages: Sequence[Page], *, seed: str = DEFAULT_SEED
) -> tuple[list[tuple[str, Page, Page, bool]], list[dict[str, str]]]:
    """``([(key, old, new, new_first)], unmatched)``: the generated positions both runs reached.

    The order is seeded on level and position: g1.1 of an A1 run and of a C1 run are two
    stories, and need not be shown the same way round.
    """

    old_by_key = {page.key: page for page in generated_pages(old_pages)}
    new_by_key = {page.key: page for page in generated_pages(new_pages)}
    pairs = [
        (key, old, new, new_shown_first(seed, f"{new.level}:{key}"))
        for key, old in old_by_key.items()
        if (new := new_by_key.get(key)) is not None
    ]
    unmatched = [{"key": key, "only_in": "old"} for key in old_by_key if key not in new_by_key]
    unmatched += [{"key": key, "only_in": "new"} for key in new_by_key if key not in old_by_key]
    return pairs, unmatched


# ---------------------------------------------------------------------------
# The judge (one model, one spend cap)
# ---------------------------------------------------------------------------


class SpendCapReached(RuntimeError):
    """The next call could pass the cap: the run stops here, cleanly."""


def call_ceiling_usd(model: str, system: str, user: str, max_tokens: int) -> float:
    """The most one call can cost: the prompt over-counted at three characters a token, and the
    whole completion budget (gpt-5 reasoning is billed against it), at ``llm_service``'s rate
    for the model — an unpriced one such as gpt-5.5 at its conservative rate."""

    from app.services.llm_service import estimate_text_cost_usd

    prompt_tokens = (len(system) + len(user)) // 3 + 32
    return estimate_text_cost_usd(model, prompt_tokens, max_tokens)


def _json_object(content: str) -> dict[str, Any] | None:
    text = str(content or "").strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        value = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


@dataclass
class Judge:
    """One judge model behind a spend cap. ``client`` is an ``LLMService`` or a test's fake."""

    client: Any
    model: str
    cap_usd: float = DEFAULT_CAP_USD
    reasoning_effort: str | None = DEFAULT_REASONING_EFFORT
    max_tokens: int = DEFAULT_MAX_TOKENS
    spent_usd: float = 0.0
    calls: int = 0
    failed: int = 0
    #: What failed calls may have cost: an empty gpt-5 answer (the reasoning used the whole
    #: budget) raises, yet is billed. Each failed call counts at its ceiling.
    uncertain_usd: float = 0.0
    dearest_usd: float = 0.0
    #: Why the run stopped (the cap), once it has.
    stopped: str | None = None

    def ask(self, system: str, user: str) -> tuple[dict[str, Any] | None, float, str | None]:
        """One strict-JSON call: ``(answer, cost, error)``.

        Before the call, the accumulated ``result.cost`` (and what failed calls may have cost)
        plus the most this call could cost — its ceiling, or the dearest call so far if that was
        more — must stay within the cap; otherwise :class:`SpendCapReached`, and every later call
        is refused the same way.
        """

        if self.stopped:
            raise SpendCapReached(self.stopped)
        ceiling = call_ceiling_usd(self.model, system, user, self.max_tokens)
        bound = max(ceiling, self.dearest_usd)
        if self.spent_usd + self.uncertain_usd + bound > self.cap_usd + 1e-9:
            held = (
                f" (+ up to US${self.uncertain_usd:.4f} in failed calls)"
                if self.uncertain_usd
                else ""
            )
            self.stopped = (
                f"spend cap: US${self.spent_usd:.4f} spent{held}, the next call could cost up to "
                f"US${bound:.4f}, cap US${self.cap_usd:.2f}"
            )
            raise SpendCapReached(self.stopped)
        effort = {"reasoning_effort": self.reasoning_effort} if self._reasons() else {}
        try:
            result = self.client.generate_chat_completion(
                [{"role": "user", "content": user}],
                system_prompt=system,
                model=self.model,
                temperature=0.0,
                max_tokens=self.max_tokens,
                response_format={"type": "json_object"},
                request_timeout=REQUEST_TIMEOUT_SECONDS,
                # One provider, one attempt: a retry or a fallback model is spend nobody planned.
                disable_retries=True,
                max_provider_attempts=1,
                **effort,
            )
        except Exception as exc:  # a failed call is recorded on its page; the run goes on
            self.failed += 1
            self.uncertain_usd = round(self.uncertain_usd + ceiling, 6)
            return None, 0.0, f"{type(exc).__name__}: {exc}"[:300]
        cost = max(0.0, float(getattr(result, "cost", 0.0) or 0.0))
        self.spent_usd = round(self.spent_usd + cost, 6)
        self.calls += 1
        self.dearest_usd = max(self.dearest_usd, cost)
        answer = _json_object(getattr(result, "content", ""))
        return answer, cost, None if answer is not None else "the answer is not a JSON object"

    def _reasons(self) -> bool:
        # gpt-5 models take an effort; gpt-4o rejects the field (graphic_novel's rule).
        return bool(self.reasoning_effort) and str(self.model).startswith("gpt-5")

    def fields(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "reasoning_effort": self.reasoning_effort if self._reasons() else None,
            "max_tokens": self.max_tokens,
            "cap_usd": self.cap_usd,
            "spent_usd": round(self.spent_usd, 6),
            "calls": self.calls,
            "failed_calls": self.failed,
            "failed_calls_up_to_usd": round(self.uncertain_usd, 6),
            "stopped": self.stopped,
        }


def _score(value: Any) -> int | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return int(number) if number.is_integer() and 1 <= number <= 5 else None


def read_scores(
    answer: dict[str, Any] | None, questions: Sequence[str]
) -> dict[str, dict[str, Any]]:
    """The judge's answer, per asked question: ``{score, reason, line}``; a missing or out-of-range
    score is kept as ``None`` with the reason, and counts in no median."""

    scores: dict[str, dict[str, Any]] = {}
    for key in questions:
        row = (answer or {}).get(key)
        if not isinstance(row, dict):
            scores[key] = {"score": None, "reason": "", "line": "", "error": "not answered"}
            continue
        cell = {
            "score": _score(row.get("score")),
            "reason": str(row.get("reason") or "").strip(),
            "line": str(row.get("line") or "").strip(),
        }
        if cell["score"] is None:
            cell["error"] = f"score {row.get('score')!r} is not 1-5"
        scores[key] = cell
    return scores


# ---------------------------------------------------------------------------
# The modes
# ---------------------------------------------------------------------------


def judge_pages(
    pages: Sequence[Page], judge: Judge, *, include_new: bool = True
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """``(rows, skipped)``: each page through the rubric, until the cap stops the run."""

    rows: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for index, page in enumerate(pages):
        questions = questions_for(page, include_new=include_new)
        system, user = rubric_messages(page, questions)
        try:
            answer, cost, error = judge.ask(system, user)
        except SpendCapReached as stop:
            skipped += [{"page": rest.label, "reason": str(stop)} for rest in pages[index:]]
            break
        row = {
            "page": page.label,
            "source": page.source,
            "key": page.key,
            "day": page.day,
            "title": page.title,
            "level": page.level,
            "previous": page.previous_summary if "new" in questions else None,
            "questions": questions,
            "scores": read_scores(answer, questions) if answer is not None else {},
            "cost_usd": cost,
            "read": page.text,
        }
        if error:
            row["error"] = error
        rows.append(row)
    return rows, skipped


def score_table(rows: Sequence[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Per question asked: the median and count of its valid scores."""

    table: dict[str, dict[str, Any]] = {}
    for key in QUESTIONS:
        if not any(key in row.get("questions", ()) for row in rows):
            continue
        scores = [
            cell["score"]
            for row in rows
            if (cell := (row.get("scores") or {}).get(key)) and cell.get("score") is not None
        ]
        table[key] = {
            "median": statistics.median(scores) if scores else None,
            "count": len(scores),
            "scores": scores,
        }
    return table


def lowest_lines(
    rows: Sequence[dict[str, Any]], *, limit: int = LOWEST_SHOWN
) -> list[dict[str, Any]]:
    """The lowest-scored lines with the judge's reasons, lowest first."""

    order = list(QUESTIONS)
    found = [
        {
            "question": key,
            "score": cell["score"],
            "page": row["page"],
            "line": cell["line"],
            "reason": cell["reason"],
        }
        for row in rows
        for key, cell in (row.get("scores") or {}).items()
        if cell.get("score") is not None
    ]
    found.sort(key=lambda item: (item["score"], order.index(item["question"])))
    return found[:limit]


def gate(
    table: dict[str, dict[str, Any]] | None = None,
    *,
    wins: int | None = None,
    compared: int | None = None,
    planned: int | None = None,
    taken: int | None = None,
) -> dict[str, Any]:
    """The plan's gate over what this run measured: ``pass``, ``fail`` or ``incomplete``.

    ``taken`` of ``planned``: the judgements the run set out to make (each asked question of
    each page; each story position, counting one that only one run reached) and those it got.
    Any fewer (the spend cap stopped the run, a call failed, an answer was malformed) is
    ``incomplete`` whatever the medians say: the gate is read on the whole run, never on what
    happened to come back."""

    criteria: list[dict[str, Any]] = []
    if table is not None:
        for key in GATE_HIGH:
            median = (table.get(key) or {}).get("median")
            criteria.append(
                {
                    "criterion": f"{key} median ≥ {GATE_HIGH_MEDIAN}",
                    "measured": median,
                    "ok": None if median is None else median >= GATE_HIGH_MEDIAN,
                }
            )
        medians = {
            key: row["median"] for key, row in table.items() if row.get("median") is not None
        }
        lowest = min(medians, key=lambda key: medians[key]) if medians else None
        criteria.append(
            {
                "criterion": f"no question median below {GATE_FLOOR_MEDIAN}",
                "measured": f"{lowest} {medians[lowest]:g}" if lowest else None,
                "ok": None if lowest is None else medians[lowest] >= GATE_FLOOR_MEDIAN,
            }
        )
    if compared is not None:
        need, out_of = GATE_WINS
        criteria.append(
            {
                "criterion": f"new wins at least {need} of {out_of} comparisons",
                "measured": f"{wins or 0} of {compared}",
                "ok": None if not compared else (wins or 0) * out_of >= need * compared,
            }
        )
    oks = [row["ok"] for row in criteria]
    if planned is not None and (taken or 0) < planned:
        verdict = "incomplete"
    else:
        verdict = "fail" if False in oks else "pass" if oks and all(oks) else "incomplete"
    report: dict[str, Any] = {"criteria": criteria, "verdict": verdict}
    if planned is not None:
        report["judgements"] = {"planned": planned, "taken": taken or 0}
    return report


def rubric_report(
    pages: Sequence[Page],
    judge: Judge,
    *,
    mode: str = "rubric",
    include_new: bool = True,
    sources: Sequence[str] = (),
) -> dict[str, Any]:
    """Rubric and benchmark: every page scored, the medians, the lowest lines and the gate."""

    rows, skipped = judge_pages(pages, judge, include_new=include_new)
    table = score_table(rows)
    planned = sum(len(questions_for(page, include_new=include_new)) for page in pages)
    taken = sum(
        1
        for row in rows
        for cell in (row.get("scores") or {}).values()
        if cell.get("score") is not None
    )
    return {
        "mode": mode,
        **judge.fields(),
        "sources": list(sources),
        "pages": rows,
        "skipped": skipped,
        "summary": table,
        "lowest": lowest_lines(rows),
        "gate": gate(table, planned=planned, taken=taken),
    }


def pairwise_report(
    pairs: Sequence[tuple[Sequence[Page], Sequence[Page]]],
    judge: Judge,
    *,
    seed: str = DEFAULT_SEED,
    sources: Sequence[tuple[str, str]] = (),
) -> dict[str, Any]:
    """Old against new, position by position, in a seeded order; wins for new and the gate."""

    comparisons: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    planned = 0
    for old_pages, new_pages in pairs:
        plan, missing = pairwise_plan(old_pages, new_pages, seed=seed)
        unmatched += missing
        planned += len(plan) + len(missing)
        for key, old, new, new_first in plan:
            first, second = (new, old) if new_first else (old, new)
            system, user = pairwise_messages(first, second, key=key, level=new.level)
            label = f"{old.label} ↔ {new.label}"
            try:
                answer, cost, error = judge.ask(system, user)
            except SpendCapReached as stop:
                skipped.append({"page": label, "reason": str(stop)})
                continue
            better = str((answer or {}).get("better") or "").strip().upper()
            winner = None
            if better in ("A", "B"):
                winner = "new" if (better == "A") == new_first else "old"
            row = {
                "page": label,
                "key": key,
                "level": new.level,
                "new_shown_as": "A" if new_first else "B",
                "better": better or None,
                "winner": winner,
                "reason": str((answer or {}).get("reason") or "").strip(),
                "cost_usd": cost,
            }
            if error or winner is None:
                row["error"] = error or f"«better» is {better!r}, not A or B"
            comparisons.append(row)
    wins = sum(1 for row in comparisons if row["winner"] == "new")
    compared = sum(1 for row in comparisons if row["winner"] is not None)
    return {
        "mode": "pairwise",
        **judge.fields(),
        "seed": seed,
        "sources": [{"old": old, "new": new} for old, new in sources],
        "comparisons": comparisons,
        "unmatched": unmatched,
        "skipped": skipped,
        "wins_new": wins,
        "compared": compared,
        "gate": gate(wins=wins, compared=compared, planned=planned, taken=compared),
    }


# ---------------------------------------------------------------------------
# The summary
# ---------------------------------------------------------------------------


def _fmt(value: Any) -> str:
    return "—" if value is None else f"{value:g}" if isinstance(value, float | int) else str(value)


def _cell(text: Any) -> str:
    """Judge prose inside a Markdown table row: one line, no column breaks."""

    return " ".join(str(text or "").split()).replace("|", "/")


def _quoted(line: str) -> str:
    """The quoted line, guillemets added only when the judge did not copy them."""

    return line if "«" in line else f"«{line}»"


def markdown(report: dict[str, Any]) -> str:
    """The short summary: medians and counts, the lowest lines, the gate, what was skipped."""

    mode = report["mode"]
    effort = f", reasoning {report['reasoning_effort']}" if report.get("reasoning_effort") else ""
    judged = len(report.get("pages") or report.get("comparisons") or [])
    failed = (
        f" {report['failed_calls']} failed (up to US${report['failed_calls_up_to_usd']:.4f})."
        if report.get("failed_calls")
        else ""
    )
    out = [
        f"# Story judge · {mode}",
        "",
        f"Judge {report['model']}{effort} · {judged} judged, {len(report.get('skipped') or [])} "
        f"skipped · US${report['spent_usd']:.4f} of the US${report['cap_usd']:.2f} cap in "
        f"{report['calls']} calls.{failed}",
        "",
    ]
    if mode == "pairwise":
        out += [
            f"New won {report['wins_new']} of {report['compared']} comparisons.",
            "",
            "| Position | New shown as | Picked | Winner | Why |",
            "|---|---|---|---|---|",
        ]
        out += [
            f"| {row['page']} | {row['new_shown_as']} | {_fmt(row['better'])} | {_fmt(row['winner'])} "
            f"| {_cell(row.get('error') or row['reason'])} |"
            for row in report["comparisons"]
        ]
        if report.get("unmatched"):
            out += [
                "",
                "Not compared (one run only): "
                + ", ".join(f"{row['key']} ({row['only_in']})" for row in report["unmatched"]),
            ]
    else:
        out += ["| Question | Median | Count | Scores |", "|---|---|---|---|"]
        out += [
            f"| {key} | {_fmt(row['median'])} | {row['count']} | {' '.join(str(s) for s in row['scores'])} |"
            for key, row in report["summary"].items()
        ]
        out += ["", "**Lowest-scored lines**", ""]
        out += [
            f"- {row['question']} {row['score']} · {row['page']} — {_quoted(row['line'])} — {row['reason']}"
            for row in report["lowest"]
        ] or ["- none scored"]
        errors = [f"- {row['page']}: {row['error']}" for row in report["pages"] if row.get("error")]
        if errors:
            out += ["", "**Calls without scores**", "", *errors]
    verdict = report["gate"]
    out += ["", f"**Gate** (plan, Phase 1): {verdict['verdict']}"]
    if verdict.get("judgements"):
        count = verdict["judgements"]
        out.append(f"- judgements taken: {count['taken']} of {count['planned']} planned")
    out += [
        f"- {row['criterion']}: {_fmt(row['measured'])} — "
        + {True: "pass", False: "fail", None: "not measured"}[row["ok"]]
        for row in verdict["criteria"]
    ]
    if report.get("skipped"):
        out += ["", "**Skipped**", ""] + [
            f"- {row['page']} — {row['reason']}" for row in report["skipped"]
        ]
    return "\n".join(out) + "\n"


__all__ = [
    "DEFAULT_CAP_USD",
    "DEFAULT_MAX_TOKENS",
    "DEFAULT_REASONING_EFFORT",
    "DEFAULT_SEED",
    "QUESTIONS",
    "Item",
    "Judge",
    "Page",
    "SpendCapReached",
    "benchmark_pages",
    "call_ceiling_usd",
    "classify",
    "days",
    "default_model",
    "gate",
    "generated_pages",
    "judge_pages",
    "load_transcript",
    "lowest_lines",
    "markdown",
    "new_shown_first",
    "pairwise_messages",
    "pairwise_plan",
    "pairwise_report",
    "parse_lines",
    "questions_for",
    "read_scores",
    "read_transcript",
    "render_page",
    "rubric_messages",
    "rubric_report",
    "score_table",
    "summarize",
    "transcript_level",
]
