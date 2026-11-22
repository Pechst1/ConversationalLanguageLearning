"""«Papier · l'écho» (``REVUE_ECHO_ENABLED``): what the learner did at the paper comes back in the story.

:func:`echo_for` reads the learner's last finished Papier of the last :data:`WINDOW_DAYS` days and
returns a compact record of it, every field from what is stored on that session (no model call):

* the story's headline in our French (the dossier snapshot's ``title_fr``) and its rubric (topic);
* the desk (the session's assignment) and what the learner did there: at the counter the side they
  took and their sentence as printed after Romy's check; at «Le titre» the headline they printed.
  A text is quoted only when it was printed checked (``souvenirs.QUOTABLE_PROOFS``);
* who was there (Romy, the regulars at the counter, the witness of «Le micro»);
* the words kept (the close's ``kept.words``);
* at most :data:`MAX_REGULAR_FACTS` things the regulars remember of it (the ``NPCMemory`` rows
  ``knowledge.remember`` wrote for that session).

A story that is sensitive (``policy.is_sensitive`` on its headline or summary) or that the counter's
desk skipped (``RevueDossier.checks["comptoir"] == "skip"``) has no echo. Neither has a session
that is not finished, or one older than the window. And it is offered once: after a scene written
since the Papier closed has been played to its end, no later scene is offered it (later acts of
the same day never are: ``living_story.later_act_context`` drops it).

:func:`director_block` is the one short block the day scene's director reads (``living_story``
adds it to the director-only context under :data:`CONTEXT_KEY`), with its instruction: one
character who was there may mention it once, in one line; nothing beyond the record.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from loguru import logger
from sqlalchemy import select

CONTEXT_KEY = "papier_echo"
WINDOW_DAYS = 3
MAX_REGULAR_FACTS = 2
MAX_KEPT_WORDS = 5
#: The sessions read to find the latest finished one (a learner rarely leaves more open).
SCAN = 8
PARIS = ZoneInfo("Europe/Paris")
ROMY_ID = "romy_tremblay"
CHAT_DESK_FR = "Avec Romy"

INSTRUCTION = (
    "papier_echo is what this learner did yesterday or lately as Romy's stagiaire at «Le Papier» "
    "(her newspaper piece), as stored. You MAY let ONE character from papier_echo.present (Romy "
    "first) refer to it ONCE, naturally, in one short line — e.g. Romy says the piece ran («notre "
    "papier»), or a regular still disagrees with what the learner said at the counter — and that "
    "line may reuse ONE of papier_echo.kept_words. Never state anything about the news story beyond "
    "papier_echo (headline_fr and what the learner did); never quote more than it holds; never "
    "refer to it twice in the scene. If today's situation makes it forced, leave it out entirely."
)


def enabled() -> bool:
    from app.config import settings

    return bool(getattr(settings, "REVUE_ENABLED", False) and getattr(settings, "REVUE_ECHO_ENABLED", False))


@dataclass(frozen=True)
class Echo:
    """The learner's last finished Papier, as the scene may speak of it."""

    session_id: str
    closed_at: datetime
    headline_fr: str
    rubric: str
    desk: str
    desk_fr: str
    did: dict[str, str]
    present: list[dict[str, str]]
    kept_words: list[str] = field(default_factory=list)
    regulars_remember: list[dict[str, str]] = field(default_factory=list)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _snapshot(row: Any) -> dict[str, Any]:
    from app.services.revue.souvenirs import _events, _payload

    for event in _events(row):
        payload = _payload(event)
        if event.get("kind") == "choice" and payload.get("kind") == "dossier":
            snapshot = payload.get("snapshot")
            return snapshot if isinstance(snapshot, dict) else {}
    return {}


def _closing(row: Any) -> dict[str, Any]:
    from app.services.revue.souvenirs import _events, _payload

    closed = [_payload(e).get("closing") for e in _events(row) if e.get("kind") == "closed"]
    return closed[-1] if closed and isinstance(closed[-1], dict) else {}


def _skipped(db: Any, dossier_id: str) -> bool:
    """Whether the counter's desk judged the story unfit for an argument (a death, a war, a party's
    politics…): it is no story for a scene either."""

    from app.db.models.revue_session import RevueDossier

    row = db.get(RevueDossier, dossier_id)
    checks = getattr(row, "checks", None) or {}
    return isinstance(checks, dict) and checks.get("comptoir") == "skip"


def _name(cast_id: str) -> str:
    from app.services.cast_registry import display_name
    from app.services.revue import comptoir

    return display_name(cast_id, "") or comptoir.NAME_FR.get(cast_id, "") or cast_id


def _regulars(db: Any, user_id: Any, session_id: str) -> list[dict[str, str]]:
    """What the regulars (not Romy: hers is the record itself) remember of the session."""

    from app.db.models.npc import NPCMemory

    rows = db.scalars(
        select(NPCMemory)
        .where(NPCMemory.user_id == user_id, NPCMemory.scene_id == session_id[:50], NPCMemory.npc_id != ROMY_ID)
        .order_by(NPCMemory.created_at.asc(), NPCMemory.npc_id.asc())
        .limit(MAX_REGULAR_FACTS)
    ).all()
    return [{"id": str(r.npc_id), "name": _name(str(r.npc_id)), "fr": str(r.content)[:400]} for r in rows if r.content]


def _echoed(db: Any, user_id: Any, closed_at: datetime) -> bool:
    """Once: a scene written after the Papier closed (so it was offered the echo) and played to
    its end has had its chance; the next one is not offered it again."""

    from app.db.models.graphic_novel import GraphicNovelScene

    return db.scalars(
        select(GraphicNovelScene.id)
        .where(
            GraphicNovelScene.user_id == user_id,
            GraphicNovelScene.created_at > closed_at,
            GraphicNovelScene.completed_at.is_not(None),
        )
        .limit(1)
    ).first() is not None


def echo_for(db: Any, user_id: Any, *, now: datetime | None = None) -> Echo | None:
    """The learner's last finished Papier of the last :data:`WINDOW_DAYS` days, or ``None``."""

    from app.db.models.revue_session import RevueSession
    from app.services.revue import assignments, policy
    from app.services.revue.souvenirs import QUOTABLE_PROOFS, filed_of

    now = now or datetime.now(UTC)
    since = now - timedelta(days=WINDOW_DAYS)
    rows = db.scalars(
        select(RevueSession)
        .where(RevueSession.user_id == user_id, RevueSession.status == "closed", RevueSession.closed_at.is_not(None))
        .order_by(RevueSession.closed_at.desc())
        .limit(SCAN)
    ).all()
    found = next(
        ((row, filed) for row in rows if (filed := filed_of(row)) is not None and filed.closed_at <= now),
        None,
    )
    if found is None:
        return None
    row, filed = found
    if filed.closed_at < since or _echoed(db, user_id, filed.closed_at):
        return None
    snapshot = _snapshot(row)
    headline = str(snapshot.get("title_fr") or "").strip()
    if not headline:
        return None
    if policy.is_sensitive(f"{headline} {snapshot.get('summary_fr') or ''}") or _skipped(db, str(row.dossier_id)):
        return None

    desk = assignments.mode_of_row(row)
    entry = assignments.assignment(desk)
    desk_fr = entry.name_fr if entry is not None else CHAT_DESK_FR
    quotable = filed.proof in QUOTABLE_PROOFS and bool(filed.printed_fr.strip())
    did: dict[str, str] = {}
    if filed.kind == "opinion":
        if filed.stance:
            did["stance"] = filed.stance
        if quotable:
            did["sentence_fr"] = filed.printed_fr.strip()
    elif filed.kind == "titre" and quotable:
        did["headline_fr"] = filed.printed_fr.strip()

    present = [ROMY_ID]
    present += [cast for cast, _side in filed.sides if cast not in present]
    if filed.witness and filed.witness not in present:
        present.append(filed.witness)

    kept = _closing(row).get("kept")
    words = [str(w.get("fr")).strip() for w in (kept or {}).get("words") or [] if isinstance(w, dict) and w.get("fr")]
    return Echo(
        session_id=str(row.id),
        closed_at=filed.closed_at,
        headline_fr=headline,
        rubric=str(snapshot.get("topic") or ""),
        desk=desk,
        desk_fr=desk_fr,
        did=did,
        present=[{"id": cast, "name": _name(cast)} for cast in present],
        kept_words=list(dict.fromkeys(w for w in words if w))[:MAX_KEPT_WORDS],
        regulars_remember=_regulars(db, row.user_id, str(row.id)),
    )


def _when_fr(closed_at: datetime, now: datetime) -> str:
    days = (now.astimezone(PARIS).date() - closed_at.astimezone(PARIS).date()).days
    return {0: "aujourd'hui", 1: "hier", 2: "avant-hier"}.get(days, f"il y a {days} jours")


def director_block(echo: Echo, *, now: datetime | None = None) -> dict[str, Any]:
    """The one short block the scene's director reads."""

    now = now or datetime.now(UTC)
    block: dict[str, Any] = {
        "instruction": INSTRUCTION,
        "when_fr": _when_fr(echo.closed_at, now),
        "headline_fr": echo.headline_fr,
        "rubric": echo.rubric,
        "desk_fr": echo.desk_fr,
        "learner_did": dict(echo.did),
        "present": [dict(p) for p in echo.present],
        "kept_words": list(echo.kept_words),
    }
    if echo.regulars_remember:
        block["regulars_remember"] = [dict(r) for r in echo.regulars_remember]
    return block


def director_context(db: Any, user: Any, *, now: datetime | None = None) -> dict[str, Any] | None:
    """:func:`director_block` of the learner's echo, or ``None`` (switch off, no echo). Never raises."""

    if not enabled() or not getattr(user, "id", None):
        return None
    try:
        # A savepoint: a failed read rolls back alone and never aborts the scene's transaction.
        with db.begin_nested():
            echo = echo_for(db, user.id, now=now)
    except Exception:  # noqa: BLE001 - a scene is never lost to its echo
        logger.exception("revue echo: unreadable")
        return None
    return director_block(echo, now=now) if echo is not None else None


# ---------------------------------------------------------------------------
# The guard: what a written page may say of the echo (no model call)
# ---------------------------------------------------------------------------
#
# The instruction asks for one line, by someone who was there, with nothing beyond the record.
# A page is refused (the scene's reask names why) when a line that speaks of the learner's piece
# is said twice, is said by someone not in ``present``, or states a number or a proper name the
# record does not hold. A line «speaks of the piece» when it names the paper («Le Papier», «ton
# article», «notre papier», «le micro-trottoir», «dans le journal») or shares a proper name or
# two content words with the headline or what the learner printed. Lines that touch none of it
# are never read further: a sheet of paper («le papier») is not the newspaper.

_MARKERS = (
    re.compile(r"\bLe Papier\b"),
    re.compile(r"\b(?:ton|ta|notre|votre|mon|ma)\s+(?:papier|article|micro-trottoir)\b", re.IGNORECASE),
    re.compile(r"\bmicro-trottoir\b", re.IGNORECASE),
    re.compile(r"\b(?:dans|au)\s+(?:le\s+)?journal\b", re.IGNORECASE),
)
#: A word without its elision («l'écrivain» is «l» and «écrivain»).
_WORD = re.compile(r"[^\W\d_][\w-]*", re.UNICODE)
_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
_CAPITAL = re.compile(r"\b[A-ZÀ-ÖØ-Þ][\w-]{2,}")
#: What opens a sentence or a quote: the capital after it is no name.
_OPENERS = ".!?«»:;—–\"(…"
#: Capitalised words that are not a fact about the story.
_COMMON_CAPS = {
    "monsieur", "madame", "mademoiselle", "papier", "romy", "paris", "mistral", "comptoir", "titre",
    "micro", "trottoir", "journal", "hier", "oui", "non", "merci", "bravo", "bonjour",
}
_MIN_KEYWORD = 5
_STOP = {
    "parce", "comme", "alors", "aussi", "encore", "toujours", "jamais", "quand", "depuis", "avant",
    "apres", "entre", "contre", "leurs", "notre", "votre", "cette", "celui", "celle", "pense", "faire",
}


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text).replace("’", "'"))
    return "".join(c for c in text if not unicodedata.combining(c)).casefold()


def _words(text: str) -> set[str]:
    return {_fold(w).strip("-") for w in _WORD.findall(str(text or ""))}


def _keywords(text: str) -> set[str]:
    return {w for w in _words(text) if len(w) >= _MIN_KEYWORD and w not in _STOP}


def _name_spans(text: str) -> list[str]:
    """The capitalised words of ``text`` that open neither it, a sentence nor a quote."""

    text = str(text or "")
    out = []
    for match in _CAPITAL.finditer(text):
        before = text[: match.start()].rstrip()
        if before and before[-1] not in _OPENERS:
            out.append(match.group(0))
    return out


def _names(text: str) -> set[str]:
    return {_fold(name).strip("-") for name in _name_spans(text)}


def _numbers(text: str) -> list[str]:
    return [n.replace(",", ".") for n in _NUMBER.findall(str(text or ""))]


def _record_text(block: dict[str, Any]) -> str:
    did = block.get("learner_did") or {}
    parts = [block.get("headline_fr"), block.get("rubric"), block.get("desk_fr"), block.get("when_fr")]
    parts += [str(v) for v in did.values()]
    parts += [str(p.get("name") or "") for p in block.get("present") or [] if isinstance(p, dict)]
    parts += [str(w) for w in block.get("kept_words") or []]
    for row in block.get("regulars_remember") or []:
        if isinstance(row, dict):
            parts += [str(row.get("name") or ""), str(row.get("fr") or "")]
    return " ".join(str(p) for p in parts if p)


def _speaks_of_it(text: str, block: dict[str, Any]) -> bool:
    if any(marker.search(text) for marker in _MARKERS):
        return True
    did = block.get("learner_did") or {}
    story = " ".join(str(v) for v in [block.get("headline_fr"), *did.values()] if v)
    words = _words(text)
    if _names(block.get("headline_fr") or "") - _COMMON_CAPS & words:
        return True
    return len(_keywords(story) & words) >= 2


def page_issue(
    lines: list[tuple[str | None, str]], block: dict[str, Any] | None, *, known_names: set[str] | None = None
) -> tuple[str, str] | None:
    """``(reason, hint)`` when the page's echo breaks the instruction, else ``None``.

    ``lines`` are the page's printed lines as ``(speaker id or None for narration, text)``;
    ``block`` is the context's ``papier_echo``; ``known_names`` the world's names (the cast's,
    the places'), which a line may always say."""

    if not isinstance(block, dict) or not block.get("headline_fr"):
        return None
    seen: set[str] = set()
    mentions: list[tuple[str | None, str]] = []
    for speaker, text in lines:
        text = str(text or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        if _speaks_of_it(text, block):
            mentions.append((speaker, text))
    if not mentions:
        return None
    if len(mentions) > 1:
        quoted = " / ".join(f"«{text[:70]}»" for _s, text in mentions[:3])
        return (
            "papier_echo_repeated",
            f"The learner's Papier is spoken of in {len(mentions)} lines ({quoted}). papier_echo may "
            "come up once, in one short line: keep the best one and take the others out.",
        )
    speaker, text = mentions[0]
    present = {str(p.get("id")) for p in block.get("present") or [] if isinstance(p, dict)}
    if speaker is not None and speaker not in present:
        return (
            "papier_echo_absent_speaker",
            f"{speaker} speaks of the learner's Papier («{text[:80]}») but was not there: only "
            f"{sorted(present)} (papier_echo.present) may. Give the line to one of them or leave it out.",
        )
    record = _record_text(block)
    allowed = _words(record) | _COMMON_CAPS | _words(" ".join(known_names or ()))
    numbers = [n for n in _numbers(text) if n not in set(_numbers(record))]
    names = _names(text) - allowed
    if numbers or names:
        invented = ", ".join(dict.fromkeys([*numbers, *(n for n in _name_spans(text) if _fold(n).strip("-") in names)]))
        return (
            "papier_echo_beyond_record",
            f"«{text[:80]}» says {invented} about the learner's Papier, which papier_echo does not hold. "
            "Say only what papier_echo holds (headline_fr, what the learner did, kept_words), or leave it out.",
        )
    return None


__all__ = ["CONTEXT_KEY", "Echo", "director_block", "director_context", "echo_for", "enabled", "page_issue"]
