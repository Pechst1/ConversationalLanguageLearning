"""WP-95 «Le Carnet» — what the learner can do in French, pressed as Seals.

The 58 can-dos of ``fr_core_can_dos_v2.json`` (WP-L2) are the Carnet's pages,
one per sub-band. A can-do is **stamped** the first time story evidence shows
it, and a stamp is never removed:

* ``scene`` — a respond step completed with its objective **met** (not
  partially) on an engine scene whose ``script_payload.can_do_id`` is set;
* ``authored`` — the same, on an authored scenario family mapped below
  (:data:`AUTHORED_SCENARIO_CAN_DOS`: the first-day café is «commander au café»);
* ``epreuve`` — a passed «Numéro spécial» (WP-94) stamps every can-do it asked for.

Readers: ``stamped_can_do_ids`` (the story engine picks the next can-do to
stage from what is still unstamped), ``carnet_payload`` (``GET /api/v1/can-dos``)
and ``next_can_do_summary`` (Home's level line, in ``GET /progress/cefr``).
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models.cefr import UserCanDoStamp
from app.services.level_checkpoint import _can_dos
from app.services.level_coverage import SUB_BANDS

logger = logging.getLogger(__name__)

SOURCE_SCENE = "scene"
SOURCE_EPREUVE = "epreuve"
SOURCE_AUTHORED = "authored"
SOURCES = frozenset({SOURCE_SCENE, SOURCE_EPREUVE, SOURCE_AUTHORED})

QUOTE_MAX_CHARS = 160

#: The authored scenario families (``journey_contracts.CapabilityKey``) and the
#: can-do each one shows when its objective is met. ``explain_delay`` is the
#: A2.1 «expliquer une raison»: saying *why* you are late is that task.
AUTHORED_SCENARIO_CAN_DOS: dict[str, str] = {
    "order_at_cafe": "CD_A11_ORDER_CAFE",
    "arrange_meeting": "CD_A12_APPOINTMENT",
    "explain_delay": "CD_A21_EXPLAIN_WHY",
}

_NATIVE_TITLE_KEYS = {"en": "title_en", "de": "title_de", "fr": "title_fr"}


# ----------------------------------------------------------------------
# Catalogue
# ----------------------------------------------------------------------


def catalog() -> list[dict[str, Any]]:
    """Every can-do with its band, in syllabus order."""

    out: list[dict[str, Any]] = []
    for band in SUB_BANDS:
        for item in _can_dos().get(band, []):
            if isinstance(item, dict) and item.get("id"):
                out.append({**item, "band": band})
    return out


def can_do_by_id(can_do_id: str | None) -> dict[str, Any] | None:
    if not can_do_id:
        return None
    for item in catalog():
        if item["id"] == can_do_id:
            return item
    return None


def native_title(item: dict[str, Any], native_language: str | None) -> str:
    key = _NATIVE_TITLE_KEYS.get((native_language or "en").split("-")[0].lower(), "title_en")
    return str(item.get(key) or item.get("title_en") or item.get("title_fr") or "")


def band_title_native(band: str, native_language: str | None) -> str:
    lang = (native_language or "en").split("-")[0].lower()
    if lang == "de":
        return f"Niveau {band}"
    if lang == "fr":
        return f"Niveau {band}"
    return f"Level {band}"


def authored_can_do_id(scenario_key: str | None) -> str | None:
    return AUTHORED_SCENARIO_CAN_DOS.get(str(scenario_key or ""))


# ----------------------------------------------------------------------
# Stamps
# ----------------------------------------------------------------------


def stamped_can_do_ids(db: Session, user_id: Any) -> set[str]:
    """The can-dos this learner has already pressed (the engine's contract)."""

    rows = db.query(UserCanDoStamp.can_do_id).filter(UserCanDoStamp.user_id == user_id).all()
    return {str(row[0]) for row in rows}


def stamps_by_id(db: Session, user_id: Any) -> dict[str, UserCanDoStamp]:
    rows = db.query(UserCanDoStamp).filter(UserCanDoStamp.user_id == user_id).all()
    return {row.can_do_id: row for row in rows}


def _clip_quote(text: str | None) -> str | None:
    value = " ".join(str(text or "").split())
    if not value:
        return None
    if len(value) <= QUOTE_MAX_CHARS:
        return value
    return value[: QUOTE_MAX_CHARS - 1].rstrip() + "…"


def stamp_can_do(
    db: Session,
    user_id: Any,
    can_do_id: str | None,
    *,
    source: str = SOURCE_SCENE,
    now: datetime | None = None,
    journey_id: Any = None,
    scene_id: str | None = None,
    scene_title_fr: str | None = None,
    character_id: str | None = None,
    quote_fr: str | None = None,
) -> UserCanDoStamp | None:
    """Press one can-do. First stamp only: returns the new row, or ``None``.

    Unknown can-do ids are ignored (the engine's payload is read defensively).
    Never commits; a concurrent duplicate is absorbed by a savepoint.
    """

    item = can_do_by_id(can_do_id)
    if item is None:
        return None
    existing = (
        db.query(UserCanDoStamp.id)
        .filter(UserCanDoStamp.user_id == user_id, UserCanDoStamp.can_do_id == item["id"])
        .first()
    )
    if existing is not None:
        return None
    row = UserCanDoStamp(
        user_id=user_id,
        can_do_id=item["id"],
        band=item["band"],
        stamped_at=now or datetime.now(UTC),
        journey_id=journey_id,
        scene_id=(str(scene_id)[:120] if scene_id else None),
        scene_title_fr=(str(scene_title_fr)[:200] if scene_title_fr else None),
        character_id=(str(character_id)[:80] if character_id else None),
        quote_fr=_clip_quote(quote_fr),
        source=source if source in SOURCES else SOURCE_SCENE,
    )
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError:
        logger.info("can_do: %s already stamped for %s (race)", item["id"], user_id)
        return None
    return row


# ----------------------------------------------------------------------
# Readers
# ----------------------------------------------------------------------


def _can_do_row(item: dict[str, Any], stamp: UserCanDoStamp | None, native: str | None) -> dict[str, Any]:
    stamped_at = stamp.stamped_at if stamp is not None else None
    if stamped_at is not None and stamped_at.tzinfo is None:
        stamped_at = stamped_at.replace(tzinfo=UTC)
    return {
        "id": item["id"],
        "title_fr": item.get("title_fr"),
        "title_native": native_title(item, native),
        "stamped_at": stamped_at.isoformat() if stamped_at is not None else None,
        "source": stamp.source if stamp is not None else None,
        "scene_id": stamp.scene_id if stamp is not None else None,
        "scene_title_fr": stamp.scene_title_fr if stamp is not None else None,
        "character_id": stamp.character_id if stamp is not None else None,
        "quote_fr": stamp.quote_fr if stamp is not None else None,
    }


def carnet_payload(
    db: Session, user_id: Any, *, current_band: str | None, native_language: str | None
) -> dict[str, Any]:
    """``GET /api/v1/can-dos`` — every band's page, stamps filled in."""

    stamps = stamps_by_id(db, user_id)
    bands = []
    for band in SUB_BANDS:
        items = [item for item in catalog() if item["band"] == band]
        if not items:
            continue
        bands.append(
            {
                "band": band,
                "title_native": band_title_native(band, native_language),
                "can_dos": [_can_do_row(item, stamps.get(item["id"]), native_language) for item in items],
            }
        )
    return {"current_band": current_band, "bands": bands}


def next_can_do_summary(
    db: Session, user_id: Any, *, band: str | None, native_language: str | None
) -> dict[str, Any]:
    """Home's level line: the next can-do of the band in force, and the count.

    ``next_can_do`` is the band's first unstamped can-do in syllabus order
    (``None`` once every one is pressed — then the épreuve is what is left).
    """

    items = [item for item in catalog() if item["band"] == band] if band else []
    stamped = stamped_can_do_ids(db, user_id)
    next_item = next((item for item in items if item["id"] not in stamped), None)
    return {
        "next_can_do": (
            {
                "id": next_item["id"],
                "title_fr": next_item.get("title_fr"),
                "title_native": native_title(next_item, native_language),
                "band": band,
            }
            if next_item is not None
            else None
        ),
        "can_dos_stamped": sum(1 for item in items if item["id"] in stamped),
        "can_dos_total": len(items),
    }


# ----------------------------------------------------------------------
# The day's scene: which can-do it asks for, and whether it is the épreuve
# ----------------------------------------------------------------------

SPECIAL_EPREUVE = "epreuve"


def _engine_scene_payload(db: Session, scene_id: Any) -> dict[str, Any]:
    import uuid

    from app.db.models.graphic_novel import GraphicNovelScene

    try:
        key = uuid.UUID(str(scene_id))
    except (TypeError, ValueError):
        return {}
    scene = db.get(GraphicNovelScene, key)
    payload = getattr(scene, "script_payload", None) if scene is not None else None
    return payload if isinstance(payload, dict) else {}


def scene_script(db: Session, story_context: dict[str, Any] | None) -> dict[str, Any]:
    """What today's engine scene says about can-dos, read defensively.

    The story engine's contract is ``script_payload.can_do_id`` (str|null),
    ``script_payload.special == "epreuve"`` and ``script_payload.epreuve =
    {band, can_do_ids, attempt, pass_line_fr, fail_line_fr}`` on the stored
    scene; the brief's own ``draft`` / ``source`` stand in while the scene row
    is not readable. Returns ``{scene_id, can_do_id, special, epreuve}``.
    """

    context = story_context if isinstance(story_context, dict) else {}
    scene_id = context.get("scene_id")
    payload = _engine_scene_payload(db, scene_id) if scene_id else {}
    draft = context.get("draft") if isinstance(context.get("draft"), dict) else {}
    source = context.get("source") if isinstance(context.get("source"), dict) else {}
    can_do_id = payload.get("can_do_id") if "can_do_id" in payload else draft.get("can_do_id")
    special = payload.get("special") or draft.get("special") or context.get("special")
    epreuve_raw = payload.get("epreuve") or draft.get("epreuve") or context.get("epreuve")
    if special != SPECIAL_EPREUVE and isinstance(source.get("epreuve"), dict) and payload.get("special") is None:
        # The engine was asked for a «Numéro spécial» and wrote the scene.
        special = SPECIAL_EPREUVE if draft.get("epreuve_pass_line_fr") else special
        epreuve_raw = epreuve_raw or source.get("epreuve")
    epreuve: dict[str, Any] | None = None
    if special == SPECIAL_EPREUVE:
        raw = epreuve_raw if isinstance(epreuve_raw, dict) else {}
        ids = raw.get("can_do_ids")
        if not isinstance(ids, list):
            ids = [item.get("id") for item in raw.get("can_dos") or [] if isinstance(item, dict)]
        epreuve = {
            "band": str(raw.get("band") or "") or None,
            "can_do_ids": [str(item) for item in ids if item],
            "attempt": raw.get("attempt"),
            "pass_line_fr": raw.get("pass_line_fr") or draft.get("epreuve_pass_line_fr"),
            "fail_line_fr": raw.get("fail_line_fr") or draft.get("epreuve_fail_line_fr"),
        }
    return {
        "scene_id": str(scene_id) if scene_id else None,
        "can_do_id": str(can_do_id) if can_do_id else None,
        "special": SPECIAL_EPREUVE if epreuve is not None else None,
        "epreuve": epreuve,
    }


def epreuve_snapshot_view(epreuve: dict[str, Any] | None, native_language: str | None) -> dict[str, Any] | None:
    """The journey snapshot's ``epreuve``: ``{band, can_dos: [{id, title_fr, title_native}]}``."""

    if not epreuve:
        return None
    ids = list(epreuve.get("can_do_ids") or [])
    band = epreuve.get("band")
    if not ids and band:
        ids = [item["id"] for item in catalog() if item["band"] == band]
    can_dos = []
    for cid in ids:
        item = can_do_by_id(cid)
        if item is not None:
            can_dos.append(
                {"id": item["id"], "title_fr": item.get("title_fr"), "title_native": native_title(item, native_language)}
            )
    return {"band": band, "can_dos": can_dos}


def _learner_quote(turns: list[dict[str, Any]] | None) -> str | None:
    """The learner's own words that did it: their longest turn."""

    texts = [str(turn.get("learner") or "").strip() for turn in turns or [] if isinstance(turn, dict)]
    texts = [text for text in texts if text]
    return max(texts, key=len) if texts else None


def settle_respond(
    db: Session,
    user: Any,
    *,
    journey: Any,
    story_context: dict[str, Any] | None,
    scenario_key: str | None,
    title_fr: str | None,
    character_id: str | None,
    outcome: str,
    turns: list[dict[str, Any]] | None,
    concept_evidence: list[dict[str, Any]] | None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """A respond step just completed: grade an épreuve, press any can-do.

    Returns what the journey keeps on the step (``can_do_stamped``,
    ``epreuve_result``, ``epreuve_band``, ``epreuve_line_fr``). Never commits.
    """

    from app.services import level_checkpoint as checkpoints

    now = now or datetime.now(UTC)
    met = str(outcome) == "met"
    script = scene_script(db, story_context)
    quote = _learner_quote(turns)
    common = {
        "now": now,
        "journey_id": getattr(journey, "id", None),
        "scene_id": script["scene_id"],
        "scene_title_fr": title_fr,
        "character_id": character_id,
        "quote_fr": quote,
    }
    out: dict[str, Any] = {"can_do_stamped": [], "epreuve_result": None}
    epreuve = script["epreuve"]
    if epreuve is not None:
        band = epreuve.get("band")
        if not band:
            view = checkpoints.current_checkpoint(db, user)
            band = view.get("band")
        verdict = checkpoints.grade_epreuve(
            db,
            band=str(band or ""),
            can_do_ids=epreuve.get("can_do_ids"),
            objective_met=met,
            turns=turns,
            concept_evidence=concept_evidence,
        )
        try:
            with db.begin_nested():
                checkpoints.record_checkpoint_result(
                    db, user, band=str(band), passed=verdict["passed"], now=now,
                    evidence={**verdict, "journey_id": str(common["journey_id"] or "")},
                    source="epreuve",
                )
        except checkpoints.CheckpointError as exc:
            # The state machine refuses (already closed, not ready, retry too
            # early): no verdict is claimed that was not recorded.
            logger.info("can_do: épreuve result refused for %s: %s", band, exc.code)
            return out
        out["epreuve_band"] = band
        out["epreuve_result"] = "passed" if verdict["passed"] else "failed"
        out["epreuve_line_fr"] = epreuve.get("pass_line_fr") if verdict["passed"] else epreuve.get("fail_line_fr")
        if verdict["passed"]:
            ids = list(epreuve.get("can_do_ids") or []) or [
                item["id"] for item in catalog() if item["band"] == band
            ]
            for cid in ids:
                if stamp_can_do(db, user.id, cid, source=SOURCE_EPREUVE, **common) is not None:
                    out["can_do_stamped"].append(cid)
        return out
    if not met:
        return out
    can_do_id = script["can_do_id"]
    source = SOURCE_SCENE
    if not can_do_id and not script["scene_id"]:
        can_do_id = authored_can_do_id(scenario_key)
        source = SOURCE_AUTHORED
    if can_do_id and stamp_can_do(db, user.id, can_do_id, source=source, **common) is not None:
        out["can_do_stamped"].append(can_do_id)
    return out


__all__ = [
    "AUTHORED_SCENARIO_CAN_DOS",
    "SOURCE_AUTHORED",
    "SOURCE_EPREUVE",
    "SOURCE_SCENE",
    "authored_can_do_id",
    "can_do_by_id",
    "carnet_payload",
    "catalog",
    "epreuve_snapshot_view",
    "scene_script",
    "settle_respond",
    "native_title",
    "next_can_do_summary",
    "stamp_can_do",
    "stamped_can_do_ids",
    "stamps_by_id",
]
