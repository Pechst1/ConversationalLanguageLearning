"""«Les habitués se souviennent» (owner 2026-11-21, ``REVUE_MEMORY_ENABLED``).

Deterministic, no model call. From the learner's own past Papiers (their closed
``revue_sessions``: the ``artifact`` event and the ``closed`` event's closing), :func:`facts_before`
builds a small ``souvenirs`` structure — the side they took at the counter last time and who sat
on the other side, the headline they had printed, their score at the intox, their last «Le fil»,
how many Papiers they filed — and :func:`line_for` chooses ONE authored line
(``souvenirs/lines.json``, 4–5 templates per assignment per band, fr/en/de) in the mouth of a
regular who has cause to say it:

* the regular who sat on the other side at the counter last time (``opponent``) or on the same
  side (``ally``), only when they sit at today's counter;
* Romy, handing out the assignment, otherwise.

**The pilot's rule.** The app never states something the learner did not say or decide: every
slot comes from a stored fact of THIS learner (a stance they voted, a headline printed after
Romy's check, a score, a weekday, a count). A headline is quoted only when it was printed checked
(``proof`` ``clean`` | ``fixed`` | ``corrected``, never ``as_written``) and is short. No fact, no
line. **Never twice in a row:** the lines of a learner's sessions are chosen in order, each
avoiding the one before (recomputed, never stored, so a reload says the same line).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.db.models.revue_session import RevueSession
from app.schemas.revue_rendez_vous import RvSouvenir

LINES_PATH = Path(__file__).with_name("lines.json")
PARIS = ZoneInfo("Europe/Paris")
#: A printed text the line may quote: checked before print.
QUOTABLE_PROOFS = frozenset({"clean", "fixed", "corrected"})
QUOTE_MAX_WORDS = 12
#: The sessions a learner's chain reads (newest); older ones no longer speak.
HISTORY = 60
#: The facts older than this are not spoken of.
MAX_AGE_DAYS = 30
#: The session's assignment → the templates' ``mode`` (the artifact it files).
MODE_TEMPLATES = {"comptoir": "opinion", "fil": "fil", "titre": "titre", "intox": "intox"}
FR_DAYS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
EN_DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
DE_DAYS = ("Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag")


@lru_cache(maxsize=1)
def lines() -> dict[str, Any]:
    return json.loads(LINES_PATH.read_text(encoding="utf-8"))


def band_key(band: str) -> str:
    return {"A1": "a1", "A2": "a2"}.get(str(band).upper()[:2], "b1")


# ---------------------------------------------------------------------------
# Facts: what the learner did, read from their stored Papiers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Filed:
    """One closed Papier of the learner, as stored."""

    session_id: str
    kind: str  # the artifact's kind: opinion | fil | titre | intox | photo | micro | a chat make
    closed_at: datetime
    printed_fr: str = ""
    proof: str | None = None
    stance: str | None = None
    #: The regulars at that counter and their sides (``closing.comptoir_page.quotes``).
    sides: tuple[tuple[str, str], ...] = ()
    score: int | None = None
    total: int | None = None


@dataclass
class Souvenirs:
    """The facts a line may rest on, each the learner's latest of its kind."""

    count: int = 0
    stance: Filed | None = None
    headline: Filed | None = None
    intox: Filed | None = None
    fil: Filed | None = None
    sessions: list[Filed] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        return self.count == 0


def _events(row: Any) -> list[dict[str, Any]]:
    state = getattr(row, "state", None) or {}
    return [e for e in (state.get("events") if isinstance(state, dict) else None) or [] if isinstance(e, dict)]


def _payload(event: dict[str, Any]) -> dict[str, Any]:
    payload = event.get("payload")
    return payload if isinstance(payload, dict) else {}


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def filed_of(row: Any) -> Filed | None:
    """The stored Papier of a closed session, or ``None`` (not closed, no artifact)."""

    if getattr(row, "status", None) != "closed" or getattr(row, "closed_at", None) is None:
        return None
    events = _events(row)
    artifacts = [_payload(e) for e in events if e.get("kind") == "artifact"]
    if not artifacts:
        return None
    artifact = artifacts[-1]
    closed = [_payload(e).get("closing") for e in events if e.get("kind") == "closed"]
    closing = closed[-1] if closed and isinstance(closed[-1], dict) else {}
    page = closing.get("comptoir_page") if isinstance(closing.get("comptoir_page"), dict) else {}
    sides = tuple(
        (str(q.get("cast_id")), str(q.get("stance")))
        for q in page.get("quotes") or []
        if isinstance(q, dict) and q.get("cast_id") and q.get("stance")
    )
    def _int(value: Any) -> int | None:
        return value if isinstance(value, int) and not isinstance(value, bool) else None

    total = None
    if artifact.get("kind") == "intox":
        intox_page = closing.get("intox_page") if isinstance(closing.get("intox_page"), dict) else {}
        total = _int(intox_page.get("total")) or 5
    return Filed(
        session_id=str(row.id),
        kind=str(artifact.get("kind") or ""),
        closed_at=_aware(row.closed_at),  # type: ignore[arg-type]
        printed_fr=str(artifact.get("text_fr") or ""),
        proof=str(artifact["proof"]) if artifact.get("proof") else None,
        stance=str(artifact["stance"]) if artifact.get("stance") in {"pour", "contre", "nuance"} else None,
        sides=sides,
        score=_int(artifact.get("score")),
        total=total,
    )


def souvenirs_from(filed: list[Filed]) -> Souvenirs:
    """The facts of ``filed`` (any order): the latest of each kind, and the count."""

    ordered = sorted(filed, key=lambda f: f.closed_at, reverse=True)
    out = Souvenirs(count=len(ordered), sessions=ordered)
    for item in ordered:
        if item.kind == "opinion" and item.stance and out.stance is None:
            out.stance = item
        elif item.kind == "titre" and item.proof in QUOTABLE_PROOFS and item.printed_fr and out.headline is None:
            out.headline = item
        elif item.kind == "intox" and item.score is not None and out.intox is None:
            out.intox = item
        elif item.kind == "fil" and out.fil is None:
            out.fil = item
    return out


def history(db: Any, user_id: Any) -> list[RevueSession]:
    """The learner's sessions, oldest first (the last :data:`HISTORY`)."""

    rows = db.scalars(
        select(RevueSession).where(RevueSession.user_id == user_id).order_by(RevueSession.started_at.desc()).limit(HISTORY)
    ).all()
    return sorted(rows, key=lambda r: (_aware(r.started_at), str(r.id)))


# ---------------------------------------------------------------------------
# Choosing the line
# ---------------------------------------------------------------------------


def quand(when: datetime, now: datetime) -> dict[str, str] | None:
    """The time slot, sentence-initial, in fr/en/de; ``None`` when the fact is too old to speak of."""

    days = (now.astimezone(PARIS).date() - when.astimezone(PARIS).date()).days
    table = lines()["quand"]
    if days < 0 or days > MAX_AGE_DAYS:
        return None
    if days == 0:
        return dict(table["today"])
    if days == 1:
        return dict(table["yesterday"])
    if days <= 6:
        weekday = when.astimezone(PARIS).weekday()
        row = table["weekday"]
        return {
            "fr": row["fr"].format(jour=FR_DAYS[weekday].capitalize()),
            "en": row["en"].format(day=EN_DAYS[weekday]),
            "de": row["de"].format(tag=DE_DAYS[weekday]),
        }
    if days <= 13:
        return dict(table["last_week"])
    return dict(table["recently"])


def _speakers(template: dict[str, Any], memory: Souvenirs, present: list[str]) -> list[str]:
    """Who may say ``template`` today: Romy, or a regular at today's counter who sat on the other
    (``opponent``) or the same (``ally``) side of the learner last time."""

    from app.services.revue.comptoir import ROMY_ID

    speaker = template["speaker"]
    if speaker == "romy":
        return [ROMY_ID]
    fact = memory.stance
    if fact is None or fact.stance not in {"pour", "contre"}:
        return []
    opposite = {"pour": "contre", "contre": "pour"}[fact.stance]
    wanted = opposite if speaker == "opponent" else fact.stance
    found = [cast for cast, side in fact.sides if side == wanted and cast in present]
    # A regular before Romy: she hands out the work, they argue at the counter.
    return sorted(found, key=lambda cast: cast == ROMY_ID)


def _fact_for(template: dict[str, Any], memory: Souvenirs) -> Filed | None:
    fact = template["fact"]
    item = {"stance": memory.stance, "headline": memory.headline, "intox_score": memory.intox, "fil": memory.fil}.get(fact)
    if fact == "count":
        return memory.sessions[0] if memory.count >= int(template.get("min_count", 1)) else None
    if item is None:
        return None
    if template.get("stance") and item.stance != template["stance"]:
        return None
    if fact == "intox_score" and (item.score or 0) < int(template.get("min_score", 0)):
        return None
    if template.get("quote") and (item.proof not in QUOTABLE_PROOFS or len(item.printed_fr.split()) > QUOTE_MAX_WORDS):
        return None
    return item


@dataclass(frozen=True)
class Choice:
    template: dict[str, Any]
    speaker_id: str
    fact: Filed
    slots: dict[str, dict[str, str]]


def eligible(mode: str, band: str, memory: Souvenirs, present: list[str], now: datetime) -> list[Choice]:
    """Every template of ``mode`` at ``band`` whose facts the learner's memory holds."""

    if memory.empty:
        return []
    kind = MODE_TEMPLATES.get(mode)
    out: list[Choice] = []
    for template in lines()["templates"]:
        if template["mode"] != kind or template["band"] != band_key(band):
            continue
        fact = _fact_for(template, memory)
        if fact is None:
            continue
        speakers = _speakers(template, memory, present)
        if not speakers:
            continue
        slots: dict[str, dict[str, str]] = {}
        texts = template["fr"] + template["en"] + template["de"]
        if "{Quand}" in texts:
            when = quand(fact.closed_at, now)
            if when is None:
                continue
            slots["Quand"] = when
        if "{titre}" in texts:
            slots["titre"] = dict.fromkeys(("fr", "en", "de"), fact.printed_fr.strip().rstrip("."))
        if "{score}" in texts:
            slots["score"] = dict.fromkeys(("fr", "en", "de"), str(fact.score))
            slots["total"] = dict.fromkeys(("fr", "en", "de"), str(fact.total or 5))
        if "{n}" in texts:
            slots["n"] = dict.fromkeys(("fr", "en", "de"), str(memory.count))
        out.append(Choice(template=template, speaker_id=speakers[0], fact=fact, slots=slots))
    return out


def _pick(choices: list[Choice], session_id: str, avoid: str | None) -> Choice | None:
    pool = [c for c in choices if c.template["id"] != avoid]
    if not pool:
        return None
    index = int(hashlib.sha256(f"souvenir:{session_id}".encode()).hexdigest(), 16) % len(pool)
    return pool[index]


def _render(choice: Choice, language: str) -> str:
    text = choice.template[language]
    for name, values in choice.slots.items():
        text = text.replace("{" + name + "}", values[language])
    return text


def present_at(mode: str, topic: str | None) -> list[str]:
    """The regulars at the session's table: the counter's three for «Au comptoir», Romy otherwise."""

    from app.services.revue.comptoir import ROMY_ID, comptoir_guests

    if mode != "comptoir":
        return [ROMY_ID]

    class _Topic:
        def __init__(self, value: str | None) -> None:
            self.topic = value

    return comptoir_guests(_Topic(topic))  # type: ignore[arg-type]


def _topic_of(row: Any) -> str | None:
    for event in _events(row):
        payload = _payload(event)
        if event.get("kind") == "choice" and payload.get("kind") == "dossier":
            snapshot = payload.get("snapshot")
            return str(snapshot.get("topic")) if isinstance(snapshot, dict) and snapshot.get("topic") else None
    return None


def line_for(db: Any, row: Any, *, now: datetime | None = None) -> RvSouvenir | None:
    """The one line of session ``row``, or ``None`` (no memory, or nothing a line can rest on).

    The learner's sessions are walked oldest first; each one's line is chosen from the facts
    filed before it started, avoiding the line chosen for the session before it."""

    from app.services.cast_registry import display_name
    from app.services.revue.assignments import mode_of_row

    now = now or datetime.now(UTC)
    rows = history(db, row.user_id)
    if all(str(r.id) != str(row.id) for r in rows):
        rows.append(row)
    filed = {str(r.id): filed_of(r) for r in rows}
    avoid: str | None = None
    for current in rows:
        started = _aware(current.started_at) or now
        before = [f for key, f in filed.items() if f is not None and key != str(current.id) and f.closed_at <= started]
        mode = mode_of_row(current)
        plan = current.plan if isinstance(current.plan, dict) else {}
        band = str(((plan.get("learner") or {}).get("band")) or "A2")
        memory = souvenirs_from(before)
        # «Quand» is said as of the session's start, so a reload says the same line.
        choice = _pick(eligible(mode, band, memory, present_at(mode, _topic_of(current)), started), str(current.id), avoid)
        if str(current.id) == str(row.id):
            if choice is None:
                return None
            from app.services.revue.voice import french_typography

            return RvSouvenir(
                template_id=choice.template["id"],
                speaker_id=choice.speaker_id,
                speaker_fr=display_name(choice.speaker_id, choice.speaker_id),
                fr=french_typography(_render(choice, "fr")),
                en=_render(choice, "en"),
                de=_render(choice, "de"),
                about_session_id=choice.fact.session_id,
                fact=choice.template["fact"],
            )
        if choice is not None:
            avoid = choice.template["id"]
    return None


__all__ = ["Filed", "Souvenirs", "eligible", "filed_of", "line_for", "lines", "quand", "souvenirs_from"]
