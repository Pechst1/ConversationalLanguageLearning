"""Story engine Phase 3 — what the learner said, what is settled, what is still open.

Before this module a later day knew the learner's past only through lines a model
had written about it (``events[].summary_fr``, ``story_so_far``), the last days'
task lines and the season's flags. What the learner actually SAID was kept nowhere
a later day could read: the name they gave Gus, the sister they came to find, the
«non» they gave Camille, the cat called Pablo they asked Lila about. So a character
asked again what was settled, forgot a name, and a question the learner asked fell
away with the day (#145, #79, #132, #171).

One small ledger per life, ``live["memory"]``:

* ``said`` — the learner's own lines, verbatim, with the line each one answered,
  whom it was said to and who heard it. Always written; no model is needed.
* ``facts`` — what is settled about the learner, one row per key (their name, where
  they come from, why they are here, a decision): reported by the day's ending model
  or the tentpole reader, and kept only with a verbatim quote of the learner's own
  words. A row knows who heard it (``known_by``); when the learner later says
  otherwise to someone else, the old version is kept for those who only heard it.
* ``open`` — questions still open across days: a question the learner asked that
  the scene did not answer, or the day's question a plan chose to leave open
  (``carries_over``). A later page answers it or comes back to it; nobody coming
  back to it for ``OPEN_DAYS`` days lets it lapse.

Written once per settled day by ``living_story.settle_resolution`` (same lock, same
transaction, idempotent per event). Read through :func:`view`: the page writers see
everything with who knows it; a character sees only what they heard or were told.

Pure functions: no database, no model call.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Collection, Iterable
from dataclasses import dataclass
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, ValidationError, field_validator

MEMORY_KEY = "memory"
VERSION = 1

#: How much one life keeps.
MAX_SAID = 60
MAX_FACTS = 24
MAX_OPEN = 12
MAX_CLOSED = 8
#: Settled event ids remembered, so a replayed settle writes nothing twice.
MAX_DAYS = 60
#: An open question nobody came back to lapses after this many days.
OPEN_DAYS = 10
#: The learner's lines a writer reads: the page writers the last ``VIEW_SAID``, a
#: character the last ``CHARACTER_SAID`` of those they heard (the facts outlive them).
VIEW_SAID = 8
CHARACTER_SAID = 6
#: Field caps.
QUOTE_CHARS = 300
LINE_CHARS = 240
FACT_CHARS = 200
VALUE_CHARS = 60
KEY_CHARS = 40
#: What one ending (or one tentpole reading) may report.
MAX_LEARNED = 4
MAX_LEFT_OPEN = 2
MAX_ANSWERED = 4

#: A ``meant`` that is bookkeeping, not a reading of the learner's words.
_NOT_A_READING = ("fallback:", "season:", "learner said:")


# ---------------------------------------------------------------------------
# Text
# ---------------------------------------------------------------------------


def fold(text: Any) -> str:
    """Case, punctuation and spacing folded: the reading every quote check uses
    (the same as ``living_story._folded``)."""

    return " ".join(re.sub(r"[^\w\s]", " ", str(text or "").casefold()).split())


def verbatim(quote: Any, texts: Iterable[Any]) -> bool:
    """True when ``quote`` is copied from one of ``texts`` (up to case, punctuation
    and spacing)."""

    folded = fold(quote)
    return bool(folded) and any(folded in fold(text) for text in texts)


def _clip(value: Any, limit: int) -> str:
    """One line, cut at a word under ``limit`` characters with an ellipsis."""

    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"


def _cut(value: Any, limit: int) -> str:
    """One line, cut at a word under ``limit`` characters and nothing added: a cut
    quote is still a verbatim prefix of what was said."""

    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(" ,;:")


def slug(value: Any) -> str:
    """A fact key: lower case, ASCII, words joined by «_» («Pourquoi ici» → pourquoi_ici)."""

    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")[:KEY_CHARS].strip("_")


_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")


def last_question(line: Any) -> str:
    """The last question in a character's line, else its last sentence (what the
    learner's next reply answered)."""

    sentences = [part.strip() for part in _SENTENCE_END.split(" ".join(str(line or "").split())) if part.strip()]
    if not sentences:
        return ""
    question = next((part for part in reversed(sentences) if part.endswith("?")), sentences[-1])
    return _clip(question, LINE_CHARS)


# ---------------------------------------------------------------------------
# The learner's name, without a model
# ---------------------------------------------------------------------------

#: «Je m'appelle Lena» (and the learner's «je m'apelle»), «mon prénom, c'est Lena»,
#: «moi, c'est Lena», «appelle-moi Lena».
_STATED_NAME = re.compile(
    r"\b(?:je\s+m['’ ]?\s?app?elle|mon\s+(?:pr[ée]nom|nom)\s*,?\s*(?:est|c['’]\s?est)"
    r"|moi\s*,?\s*c['’]\s?est|appelle[- ]moi)\s+([^\W\d_][\w'’-]{1,30})",
    re.IGNORECASE,
)
#: «Je suis Lena.» — only where the word ends the clause («je suis Lena, la
#: petite-fille…», «je suis Lena et…»), never «je suis Lena Müller» or «je suis perdu».
_SELF_NAME = re.compile(
    r"\bje\s+suis\s+([^\W\d_][\w'’-]{1,30})(?=\s*(?:$|[.,!?;…]|\bet\b))",
    re.IGNORECASE,
)
#: A line that asks who the learner is («C'est qui, vous ?», «Tu t'appelles
#: comment ?», «Ton prénom ?»): only after one does «Je suis X.» give a name.
_ASKS_WHO = re.compile(
    r"c['’]\s?est\s+qui\b|\bqui\s+(?:es[- ]tu|êtes[- ]vous)\b|\b(?:tu\s+es|t['’]\s?es|vous\s+êtes)\s+qui\b"
    r"|\bcomment\s+(?:tu\s+t['’]\s?appelles|vous\s+vous\s+appelez|t['’]\s?appelles|on\s+t['’]\s?appelle)"
    r"|\b(?:tu\s+t['’]\s?appelles|vous\s+vous\s+appelez)\s+comment\b"
    r"|\b(?:ton|votre)\s+(?:pr[ée])?nom\b|\bprésente[sz]?[- ](?:toi|vous)\b",
    re.IGNORECASE,
)
#: French endings a learner's «je suis …» word may carry: «allemande» is «allemand»,
#: «italienne» is «italien» — an adjective, not a name.
_WORD_ENDINGS = ("nes", "es", "ne", "s", "e")


def word_check(words: Collection[str]) -> Callable[[str], bool]:
    """``is_word`` over a French lexicon, reading feminine and plural endings back to
    the form the lexicon holds."""

    def is_word(word: str) -> bool:
        word = str(word or "").casefold()
        variants = {word}
        for ending in _WORD_ENDINGS:
            if word.endswith(ending) and len(word) - len(ending) >= 3:
                variants.add(word[: -len(ending)])
        return any(variant in words for variant in variants)

    return is_word


def asks_who(line: Any) -> bool:
    """True when a character's line asks who the learner is."""

    return bool(_ASKS_WHO.search(str(line or "")))


def stated_name(
    text: Any,
    *,
    asked: Any = None,
    not_names: Collection[str] = (),
    is_word: Callable[[str], bool] | None = None,
) -> str | None:
    """The first name a learner gives for themselves, or ``None``.

    After «je m'appelle» a capitalised word is a name («Je m'appelle Pierre»), and a
    lower-case one too unless it is a French word («je m'appelle lena» yes, «je
    m'appelle pas…» no). «Je suis Lena.» counts only as the answer to a line that
    asked who the learner is (``asked``), for a capitalised word that ends the clause
    and is no French word («Je suis Allemande.» names nobody). Never a name of the
    story's own cast. ``is_word(word)`` is the French lexicon (:func:`word_check`);
    without it only a capitalised word counts.
    """

    banned = {fold(name) for name in not_names if name}
    patterns = [(_STATED_NAME, False)] + ([(_SELF_NAME, True)] if asks_who(asked) else [])
    for pattern, weak in patterns:
        for match in pattern.finditer(str(text or "")):
            name = match.group(1).strip("'’-")
            if len(name) < 2 or fold(name) in banned:
                continue
            word, capital = name.casefold(), name[:1].isupper()
            if weak:
                if not capital or (is_word is not None and is_word(word)):
                    continue
            elif not capital and (is_word is None or is_word(word)):
                continue
            return name[:1].upper() + name[1:]
    return None


# ---------------------------------------------------------------------------
# What a model reports (the day's ending, a tentpole reading)
# ---------------------------------------------------------------------------


#: Keys a model may use for the learner's name: one row, whatever it is called.
_NAME_KEYS = frozenset({"nom", "prenom", "first_name", "firstname", "learner_name", "given_name"})


class LearnerFact(BaseModel):
    """One thing the learner established about themselves, in their own words."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    key: str = Field(min_length=1, max_length=KEY_CHARS)
    fact_fr: str = Field(min_length=1, max_length=FACT_CHARS)
    quote: str = Field(min_length=1, max_length=QUOTE_CHARS)
    value: str | None = Field(default=None, max_length=VALUE_CHARS)

    @field_validator("key", mode="before")
    @classmethod
    def _key(cls, value: Any) -> str:
        key = slug(value)
        return "name" if key in _NAME_KEYS else key

    @field_validator("fact_fr", mode="before")
    @classmethod
    def _fact(cls, value: Any) -> str:
        return _clip(value, FACT_CHARS)

    @field_validator("quote", mode="before")
    @classmethod
    def _quote(cls, value: Any) -> str:
        return _cut(value, QUOTE_CHARS)

    @field_validator("value", mode="before")
    @classmethod
    def _value(cls, value: Any) -> str | None:
        return _cut(value, VALUE_CHARS) or None


def lenient_facts(value: Any, limit: int = MAX_LEARNED) -> list[LearnerFact]:
    """A model's ``learned`` list with every malformed row dropped: a fact is an
    aid to later days, never the reason a turn is refused."""

    if not isinstance(value, list):
        return []
    facts: list[LearnerFact] = []
    for item in value:
        if isinstance(item, LearnerFact):
            facts.append(item)
            continue
        if not isinstance(item, dict):
            continue
        try:
            facts.append(LearnerFact.model_validate(item))
        except ValidationError:
            continue
    return facts[:limit]


def lenient_lines(value: Any, limit: int, chars: int = QUOTE_CHARS) -> list[str]:
    """A list of short strings, blanks dropped, each cut at ``chars``."""

    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    lines = [_cut(item, chars) for item in value if isinstance(item, (str, int, float))]
    return [line for line in lines if line][:limit]


def grounded_facts(
    facts: Iterable[LearnerFact | dict], texts: list[str], *, limit: int = MAX_LEARNED
) -> list[LearnerFact]:
    """The reported facts the learner's own words support: the quote is verbatim in
    ``texts``, the value (when given) is inside the quote. Anything else is dropped,
    never retried: a fact is never worth a turn."""

    kept: list[LearnerFact] = []
    for fact in lenient_facts(list(facts), limit=limit * 2):
        if not fact.key or not verbatim(fact.quote, texts):
            continue
        if fact.value and fold(fact.value) not in fold(fact.quote):
            fact = fact.model_copy(update={"value": None})
        kept.append(fact)
    return kept[:limit]


#: #147: a name is not a gender. Every prompt that shows the learner's name says so
#: (the paid read of 2026-10-17: a neutral «Lena» became «elle» in a summary).
NAME_NOTE = (
    "Their name says nothing about their gender: how the learner is gendered, in any language, "
    "follows their address alone."
)
#: The page writers: the name goes in a character's mouth, never in the page's own voice
#: (the same read: «Est-ce que Lena va garder son billet ?», «Lila offers Lena a coffee»).
NAME_SCOPE = (
    "The name is for the characters' own lines: everything the page itself says (narration, "
    "visual_direction, alt text, the chapter, the objective, plants, callbacks) still speaks "
    "to the learner as «tu» and «you», or says «the learner», as if nobody knew it."
)

#: What the ending reports for the memory: the one-call actor (``ACTOR``) and the
#: story lane (``STORY``) read the same paragraph.
ENDING_REPORT = """learned lists what the learner established about themselves in this exchange,
each {key, fact_fr, quote, value}: key a short slug (name, from, job, why_here, family,
stay, or the subject of a decision), fact_fr one sentence starting «L'apprenant» that
keeps the learner's own words for anything gendered (never «il» or «elle» for the
learner), quote copied verbatim from the learner's words, value the bare answer copied
from the quote (a name, a city) or null. left_open lists the questions the learner asked
that nobody answered, copied verbatim. answered_open_ids lists the ids of
story.memory.open this exchange answered. Each stays empty when nothing applies."""

#: The three things an ending reports (``SemanticTurn`` and the story lane's
#: ``StoryTurn``), each read leniently.
LearnedFacts = Annotated[list[LearnerFact], BeforeValidator(lenient_facts)]
LeftOpen = Annotated[list[str], BeforeValidator(lambda value: lenient_lines(value, MAX_LEFT_OPEN, LINE_CHARS))]
AnsweredIds = Annotated[list[str], BeforeValidator(lambda value: lenient_lines(value, MAX_ANSWERED, 40))]


# ---------------------------------------------------------------------------
# Writing one day
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Day:
    """One settled day as the memory reads it (built in ``settle_resolution``).

    ``exchanges`` are the respond step's turns (``learner``, ``character``, and the
    ``route`` / ``heard`` each turn stored); ``turns`` a tentpole's projected turns
    (``id``, ``to``, ``question_fr``, ``task``, and ``present``: who was in the room)
    so each line knows what it answered and who heard it.
    ``learned`` / ``left_open`` / ``answered_open_ids`` come from the accepted ending.
    """

    event_id: str
    day: int
    date: str | None
    speaker: str
    witnesses: tuple[str, ...]
    exchanges: tuple[dict, ...]
    opening_fr: str = ""
    task: str = ""
    turns: tuple[dict, ...] = ()
    outcome: str = "met"
    learned: tuple[Any, ...] = ()
    left_open: tuple[str, ...] = ()
    answered_open_ids: tuple[str, ...] = ()
    carries_over: bool = False
    returns_to: str | None = None
    not_names: frozenset[str] = frozenset()
    is_word: Callable[[str], bool] | None = None


def _meant(value: Any) -> str:
    text = _clip(value, LINE_CHARS)
    return "" if not text or text.casefold().startswith(_NOT_A_READING) else text


def after_day(memory: dict | None, day: Day) -> dict:
    """The memory once ``day`` is settled. Idempotent per ``day.event_id``."""

    memory = dict(memory or {})
    settled = [str(row) for row in memory.get("days") or []]
    if day.event_id in settled:
        return memory
    said = [dict(row) for row in memory.get("said") or [] if isinstance(row, dict)]
    facts = [dict(row) for row in memory.get("facts") or [] if isinstance(row, dict)]
    rows = [dict(row) for row in memory.get("open") or [] if isinstance(row, dict)]
    witnesses = {str(item) for item in day.witnesses if item} | {day.speaker}
    turns = {str(turn.get("id")): turn for turn in day.turns if isinstance(turn, dict) and turn.get("id")}

    # The learner's lines, each with what it answered and who heard it.
    lines: list[tuple[str, str, str, set[str]]] = []  # (the line, said to, what it answered, heard by)
    new_said: list[dict] = []
    first: dict[tuple[str, str], int] = {}  # (the line, said to) -> its row
    reported: list[Any] = list(day.learned)
    previous = ""
    for exchange in day.exchanges:
        if not isinstance(exchange, dict):
            continue
        whole = " ".join(str(exchange.get("learner") or "").split())
        character = str(exchange.get("character") or "")
        if not whole:
            previous = character or previous
            continue
        route = exchange.get("route") if isinstance(exchange.get("route"), dict) else {}
        turn = turns.get(str(route.get("turn") or ""))
        if turn is not None:
            to = str(turn.get("to") or day.speaker)
            asked = str(turn.get("question_fr") or "")
            task = str(turn.get("task") or "")
            heard_by = witnesses | {to} | {str(who) for who in turn.get("present") or () if who}
        else:
            to = day.speaker
            asked = day.opening_fr if not new_said else last_question(previous)
            task = day.task if not new_said else ""
            heard_by = witnesses | {to}
        heard = exchange.get("heard") if isinstance(exchange.get("heard"), dict) else {}
        reported.extend(heard.get("learned") or [])
        previous = character
        repeated = first.get((fold(whole), to))
        if repeated is not None:
            # The same words to the same person again (asked twice): one row, which
            # keeps the place of the earlier lines in the readers' tail.
            line, _, answered, before = lines[repeated]
            lines[repeated] = (line, to, answered, before | heard_by)
            new_said[repeated]["heard_by"] = sorted(before | heard_by)
            continue
        first[(fold(whole), to)] = len(new_said)
        row = {
            "id": f"said:{day.day}:{len(new_said)}",
            "day": day.day,
            "date": day.date,
            "event_id": day.event_id,
            "to": to,
            "heard_by": sorted(heard_by),
            "asked_fr": _clip(asked, LINE_CHARS),
            "quote": _cut(whole, QUOTE_CHARS),
        }
        if meant := _meant(heard.get("meant")):
            row["meant"] = meant
        if task:
            row["task"] = _clip(task, LINE_CHARS)
        new_said.append(row)
        lines.append((whole, to, asked, heard_by))
    texts = [line for line, _, _, _ in lines]

    def said_in(quote: str) -> list[tuple[str, str, str, set[str]]]:
        folded = fold(quote)
        return [entry for entry in lines if folded and folded in fold(entry[0])]

    def addressee(quote: str) -> str:
        return next((to for _, to, _, _ in said_in(quote)), day.speaker)

    def asked_before(quote: str) -> str:
        return next((asked for _, _, asked, _ in said_in(quote)), "")

    def hearers(entries: list[tuple[str, str, str, set[str]]], to: str) -> list[str]:
        """Everyone who heard it: the learner may say a thing twice, to two people."""

        return sorted(set().union(*(heard for _, _, _, heard in entries)) if entries else witnesses | {to})

    # What is settled: the reported facts the learner's words support, and the name
    # the learner gave even when no model read the day.
    new_facts: dict[str, dict] = {}
    banned = {fold(name) for name in day.not_names if name}
    for fact in grounded_facts(reported, texts, limit=MAX_LEARNED * 3):
        value = fact.value
        if fact.key == "name":
            if not value or fold(value) in banned:
                value = stated_name(
                    fact.quote, asked=asked_before(fact.quote), not_names=day.not_names, is_word=day.is_word
                )
            if not value:
                continue  # a «name» nobody can point to in the learner's words
        to = addressee(fact.quote)
        if fact.key == "name":
            # Everyone the learner gave that name to, whatever words they used.
            entries = [
                entry
                for entry in lines
                if fold(stated_name(entry[0], asked=entry[2], not_names=day.not_names, is_word=day.is_word))
                == fold(value)
            ] or said_in(fact.quote)
        else:
            entries = said_in(fact.quote)
        new_facts[fact.key] = {
            "key": fact.key,
            "fact_fr": fact.fact_fr,
            "quote": fact.quote,
            **({"value": value} if value else {}),
            "to": to,
            "known_by": hearers(entries, to),
            "day": day.day,
            "date": day.date,
            "event_id": day.event_id,
        }
    if "name" not in new_facts:
        named = [
            (entry, name)
            for entry in lines
            if (name := stated_name(entry[0], asked=entry[2], not_names=day.not_names, is_word=day.is_word))
        ]
        if named:
            (line, to, _, _), name = named[0]
            new_facts["name"] = {
                "key": "name",
                "fact_fr": f"L'apprenant s'appelle {name}.",
                "quote": _cut(line, QUOTE_CHARS),
                "value": name,
                "to": to,
                "known_by": hearers([entry for entry, other in named if fold(other) == fold(name)], to),
                "day": day.day,
                "date": day.date,
                "event_id": day.event_id,
            }
    for row in new_facts.values():
        facts = _merge_fact(facts, row)

    # Questions: close what today answered, let the stale ones lapse, then open
    # today's. Only someone on today's page who knows a question can answer it.
    answered = {str(item) for item in day.answered_open_ids}
    for row in rows:
        if row.get("status") != "open":
            continue
        returned = row.get("id") == day.returns_to and (row.get("by") == "learner" or day.outcome != "not_yet")
        knows = bool(witnesses & {str(who) for who in row.get("known_by") or ()})
        if knows and (row.get("id") in answered or returned):
            row.update(status="answered", closed_day=day.day, closed_by=day.event_id)
        elif day.day - int(row.get("day") or day.day) >= OPEN_DAYS:
            row.update(status="lapsed", closed_day=day.day)
    still_open = {fold(row.get("question_fr")) for row in rows if row.get("status") == "open"}
    opened = 0
    for quote in list(day.left_open)[:MAX_LEFT_OPEN]:
        if not verbatim(quote, texts) or fold(quote) in still_open:
            continue
        to = addressee(quote)
        rows.append(
            {
                "id": f"open:{day.day}:{opened}",
                "by": "learner",
                "to": to,
                "question_fr": _cut(quote, LINE_CHARS),
                "known_by": hearers(said_in(quote), to),
                "day": day.day,
                "date": day.date,
                "event_id": day.event_id,
                "status": "open",
            }
        )
        still_open.add(fold(quote))
        opened += 1
    if day.carries_over and day.outcome != "met":
        question = last_question(day.opening_fr)
        if question and fold(question) not in still_open:
            rows.append(
                {
                    "id": f"open:{day.day}:{opened}",
                    "by": day.speaker,
                    "to": "learner",
                    "question_fr": question,
                    "known_by": sorted(witnesses),
                    "day": day.day,
                    "date": day.date,
                    "event_id": day.event_id,
                    "status": "open",
                }
            )
    open_rows = [row for row in rows if row.get("status") == "open"][-MAX_OPEN:]
    closed_rows = [row for row in rows if row.get("status") != "open"][-MAX_CLOSED:]
    return {
        "version": VERSION,
        "said": [*said, *new_said][-MAX_SAID:],
        "facts": facts,
        "open": [*closed_rows, *open_rows],
        "days": [*settled, day.event_id][-MAX_DAYS:],
    }


def _versions(fact: dict) -> list[dict]:
    """A fact's earlier versions (``before``), newest first; one stored on its own
    reads as the only one."""

    before = fact.get("before")
    rows = [before] if isinstance(before, dict) else before if isinstance(before, list) else []
    return [row for row in rows if isinstance(row, dict) and row.get("known_by")]


def _merge_fact(facts: list[dict], row: dict) -> list[dict]:
    """One row per key. The same fact again widens who knows it; a different one
    replaces it. Every earlier version stays (``before``, newest first) with those who
    only heard that one, so each person believes exactly one version: whoever hears
    this one leaves the older ones, and an older one that says the same is this one."""

    existing = next((fact for fact in facts if fact.get("key") == row["key"]), None)
    if existing is None:
        facts = [*facts, row]
    else:
        rest = [fact for fact in facts if fact is not existing]

        def says(fact: dict) -> str:
            return fold(fact.get("value") or fact.get("fact_fr"))

        earlier = _versions(existing)
        if says(existing) == says(row):
            current = {**existing, "known_by": sorted({*existing.get("known_by", []), *row["known_by"]}), "confirmed_day": row["day"]}
        else:
            current = dict(row)
            kept = ("fact_fr", "quote", "value", "day", "known_by")
            earlier = [{key: existing.get(key) for key in kept if existing.get(key)}, *earlier]
        current.pop("before", None)
        before = []
        for version in earlier:
            if says(version) == says(current):
                current["known_by"] = sorted({*current["known_by"], *(version.get("known_by") or ())})
            elif believers := sorted(set(version.get("known_by") or ()) - set(row["known_by"])):
                before.append({**version, "known_by": believers})
        facts = [*rest, {**current, **({"before": before} if before else {})}]
    if len(facts) > MAX_FACTS:
        # The learner's name outlives every other fact.
        named = [fact for fact in facts if fact.get("key") == "name"]
        others = [fact for fact in facts if fact.get("key") != "name"]
        facts = named + others[len(facts) - MAX_FACTS:]
    return facts


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------


def full_view(memory: dict | None) -> dict | None:
    """What the page writers (director, planner, critic) read: everything, with who
    knows it. ``None`` when nothing is remembered yet."""

    memory = memory if isinstance(memory, dict) else {}
    facts = []
    for row in memory.get("facts") or []:
        if not isinstance(row, dict) or not row.get("key"):
            continue
        fact = {
            "id": f"fact:{row['key']}",
            "key": row["key"],
            "fact_fr": row.get("fact_fr"),
            "quote": row.get("quote"),
            "day": row.get("day"),
            "known_by": list(row.get("known_by") or []),
        }
        if row.get("value"):
            fact["value"] = row["value"]
        if before := _versions(row):
            fact["before"] = [
                {key: version.get(key) for key in ("fact_fr", "quote", "known_by") if version.get(key)} for version in before
            ]
        facts.append(fact)
    said = [
        {
            key: row.get(key)
            for key in ("id", "day", "to", "heard_by", "asked_fr", "quote", "meant")
            if row.get(key) not in (None, "", [])
        }
        for row in (memory.get("said") or [])[-VIEW_SAID:]
        if isinstance(row, dict) and row.get("quote")
    ]
    open_rows = [
        {key: row.get(key) for key in ("id", "by", "to", "question_fr", "day", "known_by")}
        for row in memory.get("open") or []
        if isinstance(row, dict) and row.get("status") == "open"
    ]
    out: dict[str, Any] = {}
    name = next((fact for fact in facts if fact["key"] == "name" and fact.get("value")), None)
    if name:
        out["learner_name"] = {"value": name["value"], "known_by": name["known_by"]}
    if facts:
        out["facts"] = facts
    if said:
        out["said"] = said
    if open_rows:
        out["open"] = open_rows
    return out or None


def narrow(view: dict | None, among: Collection[str]) -> dict | None:
    """A full view narrowed to what ``among`` know: the facts they were told (in the
    version they heard), the lines they heard, the open questions they know of.

    One character: the who-knows lists are left out (it is all theirs). Several (the
    people on a page): each row keeps them, so the writer knows who may say what."""

    if not view:
        return None
    people = {str(item) for item in among if item}
    keep_lists = len(people) > 1

    def knows(names: Any) -> bool:
        return bool(people & {str(item) for item in names or []})

    def trimmed(row: dict, *lists: str) -> dict:
        return row if keep_lists else {key: value for key, value in row.items() if key not in lists}

    facts = []
    for fact in view.get("facts") or []:
        current = {key: value for key, value in fact.items() if key != "before"}
        before = [version for version in _versions(fact) if knows(version.get("known_by"))]
        if not knows(fact.get("known_by")):
            if not before:
                continue
            # They only heard an older version: that is what they believe.
            current.pop("value", None)
            current.update({key: before[0].get(key) for key in ("fact_fr", "quote", "known_by")})
            before = before[1:]
        if keep_lists and before:
            current["before"] = before
        facts.append(trimmed(current, "known_by"))
    limit = VIEW_SAID if keep_lists else CHARACTER_SAID
    said = [trimmed(row, "heard_by") for row in view.get("said") or [] if knows(row.get("heard_by"))][-limit:]
    open_rows = [trimmed(row, "known_by") for row in view.get("open") or [] if knows(row.get("known_by"))]
    out: dict[str, Any] = {}
    name = view.get("learner_name") or {}
    if name and knows(name.get("known_by")):
        out["learner_name"] = name if keep_lists else name.get("value")
    if facts:
        out["facts"] = facts
    if said:
        out["said"] = said
    if open_rows:
        out["open"] = open_rows
    return out or None


def view(memory: dict | None, *, among: Collection[str] | None = None) -> dict | None:
    """``full_view`` of the stored memory, narrowed to ``among`` when given."""

    full = full_view(memory)
    return full if among is None else narrow(full, among)


def known_to(view: dict | None, character_id: str) -> dict | None:
    """What one character knows of the learner, in short — their name and the settled
    facts (the tentpole reader's ``known``) — or ``None``."""

    narrowed = narrow(view, {character_id})
    if not narrowed:
        return None
    out: dict[str, Any] = {}
    if narrowed.get("learner_name"):
        out["learner_name"] = narrowed["learner_name"]
    facts = [str(row.get("fact_fr")) for row in narrowed.get("facts") or [] if row.get("fact_fr")]
    if facts:
        out["facts"] = facts
    return out or None


def name_in(view: dict | None) -> str | None:
    """The learner's name in a (full or narrowed) view, when the reader knows it."""

    name = (view or {}).get("learner_name")
    if isinstance(name, dict):
        return str(name.get("value") or "") or None
    return str(name or "") or None


def open_ids(view: dict | None) -> set[str]:
    return {str(row.get("id")) for row in (view or {}).get("open") or [] if row.get("id")}


def open_row(view: dict | None, row_id: Any) -> dict | None:
    return next((row for row in (view or {}).get("open") or [] if row.get("id") == row_id), None)


def returnable(view: dict | None, row_id: Any, on_page: Iterable[Any]) -> dict | None:
    """The open question a page may come back to: only through someone on it who
    knows the question (the paid read of 2026-10-17: Lila «returned» to what the
    learner had asked Marin, and the question closed unanswered)."""

    row = open_row(view, row_id)
    people = {str(who) for who in on_page if who}
    return row if row and people & {str(who) for who in row.get("known_by") or ()} else None


# ---------------------------------------------------------------------------
# A page brings back what the learner said, never what they did not say
# ---------------------------------------------------------------------------

#: A character telling the learner what the learner once told them: «tu m'as dit»,
#: «vous m'aviez dit», «tu as répondu», «tu me disais». A denial («tu ne m'as pas
#: dit») does not match: it claims nothing.
_TOLD = re.compile(
    r"\b(?:tu|vous)\s+(?:m['’]\s*|nous\s+)?(?:as|avais|avez|aviez)\s+(?:dit|répondu|raconté)\b"
    r"|\b(?:tu|vous)\s+(?:me\s+|m['’]\s*|nous\s+)?(?:disais|disiez)\b",
    re.IGNORECASE,
)
#: The words a telling quotes («…», “…”, "…").
_QUOTED = re.compile(r"[«“\"]\s*([^«»“”\"]+?)\s*[»”\"]")
#: What a telling says besides what was said: grammar, être and avoir, when it was
#: said, and «oui» or «non» (a refusal is «non» in anyone's words).
_NOT_WHAT = frozenset(
    """
    a à ah ai alors as au aussi aux avais avait avec avez aviez avons bien bon c ça ce cela
    ces cet cette comme d dans de déjà dernier dernière des du eh elle elles en es est et étais
    était été être eu fois hein hier il ils j je jour l la le les leur lui m ma mais me mes moi
    mon n ne non nous oh on ont ou où oui par pas plus pour qu que quand qui quoi s sa se ses
    si son sont suis sur t ta te tes toi ton tout très tu un une vous y
    """.split()
)


def _bare(word: str) -> str:
    return "".join(char for char in unicodedata.normalize("NFKD", word) if not unicodedata.combining(char))


def _said_forms(text: Any, lemmas: Callable[[str], Iterable[str]], names: Collection[str]) -> dict[str, set[str]]:
    """The words of a telling or of a remembered line that say something, each with
    its dictionary forms («restais» meets «reste» at «rester»), accents folded."""

    out: dict[str, set[str]] = {}
    for word in re.findall(r"[^\W\d_]+(?:-[^\W\d_]+)*", str(text or "").casefold()):
        if len(word) > 1 and word not in _NOT_WHAT and word not in names:
            out.setdefault(_bare(word), set()).update(_bare(form) for form in (word, *lemmas(word)))
    return out


def heard_from_learner(view: dict | None, who: Any) -> list[str]:
    """Everything ``who`` heard the learner say or was told about them, in the version
    they heard, the newest lines last: the facts, the learner's name, the lines
    (``said``)."""

    who = str(who or "")
    view = view or {}
    texts: list[str] = []
    for fact in view.get("facts") or []:
        believed = fact if who in (fact.get("known_by") or ()) else next(
            (version for version in _versions(fact) if who in version["known_by"]), None
        )
        if believed is not None:
            texts += [str(believed.get(key)) for key in ("fact_fr", "quote", "value") if believed.get(key)]
    name = view.get("learner_name") if isinstance(view.get("learner_name"), dict) else {}
    if name.get("value") and who in (name.get("known_by") or ()):
        texts.append(str(name["value"]))
    texts += [str(row["quote"]) for row in view.get("said") or [] if row.get("quote") and who in (row.get("heard_by") or ())]
    return list(dict.fromkeys(texts))


def unheard_tellings(
    view: dict | None,
    lines: Iterable[tuple[Any, Any]],
    lemmas: Callable[[str], Iterable[str]] = lambda word: (),
    *,
    cast: Collection[str] = (),
    learner_name: str | None = None,
) -> list[tuple[str, str]]:
    """``(character_id, sentence)`` for each sentence of a page in which a character
    tells the learner what the learner once told them, and half or more of the words
    it puts in the learner's mouth are in nothing that character heard from the
    learner (:func:`heard_from_learner`): one word they did hear does not carry the
    rest («tu restes à Berlin mercredi» to someone who heard only «je reste un peu»).
    A quoted telling is read by its quote, so what the character adds after it is
    theirs. ``lemmas`` gives a word's dictionary forms, so a telling in the
    character's own words still meets the learner's line. A telling that names
    someone in ``cast`` («Gus, tu m'as dit…», «tu as dit non à Camille») may be said to
    them or be about them, and is not read; the learner's name says nothing either.

    The paid read of 2026-10-17: Lila said «Tu m'avais dit : mercredi, tu rentres.» to
    a learner who had told her «Non, je ne vends pas. Je reste un peu.» and nothing
    about Wednesday, in two lives of six (never on main, where nobody brought the
    learner's words back). A question asks, it does not tell; «tu m'as dit non» tells
    only an answer; and with nothing remembered there is nothing to check."""

    if not view:
        return []
    others = {str(name).casefold() for name in cast if len(str(name or "")) > 1}
    skip = others | ({str(learner_name).casefold()} if learner_name else set())
    found: list[tuple[str, str]] = []
    for who, text in lines:
        for sentence in _SENTENCE_END.split(" ".join(str(text or "").split())):
            told = _TOLD.search(sentence)
            if not told or sentence.endswith("?") or others & set(re.findall(r"[^\W\d_]+", sentence.casefold())):
                continue
            # What was told follows the verb («tu m'as dit : …»), or comes first when
            # nothing does («« Je reste », tu m'as dit.»).
            after = sentence[told.end() :]
            what = after if re.search(r"[^\W\d_]", after) else sentence[: told.start()]
            claim = _said_forms(" ".join(_QUOTED.findall(what)) or what, lemmas, skip)
            heard = set().union(
                *(forms for line in heard_from_learner(view, who) for forms in _said_forms(line, lemmas, skip).values())
            )
            if claim and 2 * sum(bool(forms & heard) for forms in claim.values()) <= len(claim):
                found.append((str(who or ""), sentence))
    return found


# ---------------------------------------------------------------------------
# The ledger seam: a page may build on what the learner said, and cite it
# ---------------------------------------------------------------------------


def ledger_rows(memory: dict | None) -> list[tuple[str, str]]:
    """``(id, text)`` for every remembered line and fact, for the callback ledger: a
    callback that reaches back to what the learner said is grounded, not invented."""

    memory = memory if isinstance(memory, dict) else {}
    rows: list[tuple[str, str]] = []
    for row in memory.get("said") or []:
        if isinstance(row, dict) and row.get("quote"):
            rows.append((str(row.get("id") or ""), f"{row.get('asked_fr') or ''} {row['quote']}"))
    for row in memory.get("facts") or []:
        if isinstance(row, dict) and row.get("key"):
            rows.append((f"fact:{row['key']}", f"{row.get('fact_fr') or ''} {row.get('quote') or ''}"))
    return rows


def row_by_id(memory: dict | None, ref: Any) -> dict | None:
    """The remembered line or fact an id names — the provenance a margin note prints
    («Parce que vous avez dit à Lila « … »») — or ``None``."""

    memory = memory if isinstance(memory, dict) else {}
    ref = str(ref or "")
    if not ref:
        return None
    for row in memory.get("said") or []:
        if isinstance(row, dict) and str(row.get("id")) == ref:
            return {
                "kind": "said",
                "text_fr": row.get("asked_fr"),
                "quote": row.get("quote"),
                "character_id": row.get("to"),
                "event_id": row.get("event_id"),
                "date": row.get("date"),
                "day": row.get("day"),
            }
    if ref.startswith("fact:"):
        key = ref.split(":", 1)[1]
        for row in memory.get("facts") or []:
            if isinstance(row, dict) and row.get("key") == key:
                return {
                    "kind": "fact",
                    "text_fr": row.get("fact_fr"),
                    "quote": row.get("quote"),
                    "character_id": row.get("to"),
                    "event_id": row.get("event_id"),
                    "date": row.get("date"),
                    "day": row.get("day"),
                }
    return None


__all__ = [
    "MEMORY_KEY",
    "AnsweredIds",
    "Day",
    "LearnedFacts",
    "LearnerFact",
    "LeftOpen",
    "after_day",
    "fold",
    "full_view",
    "grounded_facts",
    "heard_from_learner",
    "known_to",
    "last_question",
    "ledger_rows",
    "lenient_facts",
    "lenient_lines",
    "name_in",
    "narrow",
    "open_ids",
    "open_row",
    "row_by_id",
    "stated_name",
    "unheard_tellings",
    "verbatim",
    "view",
]
