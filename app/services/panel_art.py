"""Per-panel illustrations for story-engine scenes (2026-09-25).

A story-engine scene is a graphic-novel page of 4-6 panels, and until now every panel
showed the same location plate. This module draws each panel from its own
``visual_direction``, in the approved screen-print style, with the approved cast
portraits (``docs/design-reference/cast/<id>/reference.webp``) as references so faces
stay the same from panel to panel.

How it runs:

* ``bind_journey`` publishes the scene with the location plate on every panel (the
  reader never waits for art) and calls :func:`request_scene_art`, which marks the
  panels ``rendering`` and queues the scene on the session.
* Once that transaction commits, the scene is rendered in a small in-process pool
  (no Celery worker is needed). Each panel is written back as soon as it is drawn, so
  the reader, which polls while any panel is ``rendering``, swaps art in panel by
  panel. A panel whose drawing fails keeps its location plate (``setting_reference``).
* A rolled-back transaction queues nothing.

Rules carried over from ``scripts/art/atelier_art.py`` (the owner's art pipeline):
one style for people and places, never the old model sheets as references, and the
image API's limit of input images per minute is respected.

Off unless ``ATELIER_PANEL_ART_ENABLED``: each panel is a paid image call
(≈ US$0.05 at medium quality).

WP-88 — production-safe:

* **References must ship.** Without ``docs/design-reference/cast/*/reference.webp``
  faces drift from panel to panel, so art stays off rather than draw strangers.
* **Durable storage.** In production a drawing written to the container's disk is
  lost at the next deploy (and invisible to a second instance), so art stays off
  unless ``GRAPHIC_NOVEL_IMAGE_STORAGE=s3`` with a bucket.
* **It is paid for in the open.** Every drawn panel writes a
  ``journey_panel_art_cost`` row. Art has its own per-learner daily allowance
  (``ATELIER_PANEL_ART_DAILY_ALLOWANCE_USD``), apart from the text cap, and a day
  whose text spend is already past ``ATELIER_PANEL_ART_TEXT_PRESSURE`` of the cap
  draws nothing. A panel the allowance does not cover keeps its plate: art
  degrades, the day never does.
* ``ATELIER_PANEL_ART_BANDS`` limits drawing to the bands where pictures carry
  the most meaning (A1–A2 first).
"""

from __future__ import annotations

import base64
import io
import re
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
from loguru import logger
from sqlalchemy import event
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

ART_SOURCE = "panel_art"
SETTING_SOURCE = "setting_reference"
RENDERING = "rendering"
READY = "ready"
FAILED = "failed"
#: WP-108: when a panel went ``rendering`` (epoch seconds). A drawing that has not
#: come within ``RENDERING_TIMEOUT_SECONDS`` is served as its plate, so a lost job or a
#: restarted process can never leave a page «sous presse» forever.
RENDERING_SINCE_KEY = "rendering_since"
#: Default only: the live value is ``settings.ATELIER_PANEL_ART_RENDER_TIMEOUT_SECONDS`` (read
#: through :func:`rendering_timeout_seconds`). Four panels take ~95 s with reference pacing
#: and more under load, so the heal must not fire on a drawing that is still coming.
RENDERING_TIMEOUT_SECONDS = 240.0
TIMEOUT_REASON = "timeout"

PENDING_KEY = "panel_art_pending"
MAX_REFERENCES_PER_PANEL = 2
PANEL_SIZE = "1536x1024"  # the location plates' landscape frame

REPO = Path(__file__).resolve().parents[2]
CAST_REFERENCES = REPO / "docs/design-reference/cast"

PANEL_RULES = (
    "One panel of a French graphic novel. No speech bubbles, no captions, no lettering, no "
    "readable text or signage anywhere. Cinematic framing as directed. Anyone called 'you', "
    "'the learner' or 'Toi' is the reader's own character: seen from behind or cropped at the "
    "frame edge, never showing a face. "
)


@dataclass(frozen=True)
class PanelJob:
    scene_id: str
    panel_index: int
    prompt: str
    references: tuple[str, ...]


@dataclass(frozen=True)
class SceneArtJob:
    scene_id: str
    bind: Any
    #: The panels this job draws; ``None`` is every panel still ``rendering`` (WP-90:
    #: a scene whose other panels wait on its prefetch's drawings names its own).
    indices: tuple[int, ...] | None = None


@dataclass(frozen=True)
class PrefetchArtJob:
    """WP-90: draw a prefetched draft's panels, keyed to its prefetch row."""

    prefetch_id: str
    bind: Any


@dataclass(frozen=True)
class AdoptArtJob:
    """WP-90: a bound scene whose panels are still being drawn by its prefetch."""

    scene_id: str
    prefetch_id: str
    bind: Any


# ---------------------------------------------------------------------------
# Queueing on the session, dispatching after its commit
# ---------------------------------------------------------------------------

#: Tests replace this with an inline or recording dispatcher.
dispatcher: Callable[[SceneArtJob], Any] | None = None
_EXECUTOR: ThreadPoolExecutor | None = None
_EXECUTOR_LOCK = threading.Lock()


def references_available() -> bool:
    return CAST_REFERENCES.is_dir() and any(CAST_REFERENCES.glob("*/reference.webp"))


def durable_storage() -> bool:
    """Outside production a local disk is fine; in production only S3 keeps a drawing."""

    if str(settings.APP_ENV or "").strip().lower() != "production":
        return True
    return (
        str(settings.GRAPHIC_NOVEL_IMAGE_STORAGE or "").strip().lower() == "s3"
        and bool(settings.GRAPHIC_NOVEL_IMAGE_S3_BUCKET)
    )


def unavailable_reason() -> str | None:
    """Why art is off, in one line for the startup log; ``None`` when it is on."""

    if not settings.ATELIER_PANEL_ART_ENABLED:
        return "ATELIER_PANEL_ART_ENABLED is false"
    if not settings.OPENAI_API_KEY:
        return "no OPENAI_API_KEY"
    if not references_available():
        return f"no cast references under {CAST_REFERENCES}"
    if not durable_storage():
        return "production needs GRAPHIC_NOVEL_IMAGE_STORAGE=s3 and a bucket"
    return None


def enabled() -> bool:
    return unavailable_reason() is None


def panel_cost_usd() -> float:
    return max(0.0, float(settings.ATELIER_PANEL_ART_COST_USD_PER_PANEL))


def rendering_timeout_seconds() -> float:
    try:
        return max(1.0, float(settings.ATELIER_PANEL_ART_RENDER_TIMEOUT_SECONDS))
    except (AttributeError, TypeError, ValueError):
        return RENDERING_TIMEOUT_SECONDS


def _band_allowed(level_band: str | None) -> bool:
    bands = {b.strip().upper() for b in str(settings.ATELIER_PANEL_ART_BANDS or "").split(",") if b.strip()}
    if not bands or not level_band:
        return True
    return str(level_band).strip().upper()[:2] in bands


def affordable_panels(db: Session, user: Any, wanted: int) -> int:
    """How many of ``wanted`` panels today's art allowance still covers (WP-88)."""

    from app.services import spend_guard

    cost = panel_cost_usd()
    if wanted <= 0:
        return 0
    zone = spend_guard.learner_zone(user)
    user_id = getattr(user, "id", None)
    try:
        cap = spend_guard.daily_cap_usd()
        pressure = float(settings.ATELIER_PANEL_ART_TEXT_PRESSURE)
        if cap > 0 and spend_guard.spend_today_usd(db, user_id, zone=zone) >= cap * pressure:
            return 0
        if cost <= 0:
            return wanted
        left = float(settings.ATELIER_PANEL_ART_DAILY_ALLOWANCE_USD) - spend_guard.art_spend_today_usd(
            db, user_id, zone=zone
        )
    except Exception as exc:  # noqa: BLE001 - a ledger read never costs the day; no art
        logger.warning("panel_art: allowance check failed, keeping plates: {}", exc)
        return 0
    return max(0, min(wanted, int((left + 1e-9) // cost)))


def request_scene_art(
    db: Session,
    scene,
    *,
    level_band: str | None = None,
    user: Any = None,
    panels: list | None = None,
) -> bool:
    """Mark the panels today's allowance covers ``rendering``; draw them once ``db`` commits.

    ``panels`` limits the request to some of the scene's panels (WP-90: the ones its
    prefetch did not draw)."""

    if not enabled() or not _band_allowed(level_band):
        return False
    if user is None and getattr(scene, "user_id", None) is not None:
        from app.db.models.user import User

        user = db.get(User, scene.user_id)
    subset = panels is not None
    panels = sorted(scene.panels if panels is None else panels, key=lambda p: p.panel_index)
    count = affordable_panels(db, user, len(panels))
    if count <= 0:
        return False
    for panel in panels[:count]:
        panel.generation_metadata = {
            **(panel.generation_metadata or {}),
            "image_status": RENDERING,
            RENDERING_SINCE_KEY: time.time(),
        }
    indices = tuple(int(panel.panel_index) for panel in panels[:count]) if subset else None
    db.info.setdefault(PENDING_KEY, []).append(SceneArtJob(str(scene.id), db.get_bind(), indices))
    return True


def _executor() -> ThreadPoolExecutor:
    global _EXECUTOR
    with _EXECUTOR_LOCK:
        if _EXECUTOR is None:
            _EXECUTOR = ThreadPoolExecutor(
                max_workers=max(1, int(settings.ATELIER_PANEL_ART_SCENES_IN_FLIGHT)),
                thread_name_prefix="panel-art",
            )
        return _EXECUTOR


_ADOPT_EXECUTOR: ThreadPoolExecutor | None = None


def _adopt_executor() -> ThreadPoolExecutor:
    """Adoption mostly waits; it gets its own threads so it never holds up drawing."""

    global _ADOPT_EXECUTOR
    with _EXECUTOR_LOCK:
        if _ADOPT_EXECUTOR is None:
            _ADOPT_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="panel-adopt")
        return _ADOPT_EXECUTOR


_WORKER_CHECK_TTL_SECONDS = 30.0
_WORKER_CHECK: tuple[float, bool] | None = None


def worker_available(*, now: float | None = None) -> bool:
    """Is a Celery worker alive to take a drawing? (WP-108)

    Reuses the ``/health/worker`` logic (a fresh beat-and-worker heartbeat in Redis), cached
    for 30 s so a burst of scenes costs one look. Eager mode and the in-process test
    broker have no worker by definition. Anything unclear is «no worker»: the drawing then
    runs in this process, which always finishes or fails."""

    global _WORKER_CHECK
    from app.celery_app import broker_is_memory, is_eager

    if is_eager() or broker_is_memory():
        return False
    moment = time.monotonic() if now is None else now
    cached = _WORKER_CHECK
    if cached is not None and moment - cached[0] < _WORKER_CHECK_TTL_SECONDS:
        return cached[1]
    try:
        from app.core.observability import worker_health

        alive = worker_health().get("status") == "ok"
    except Exception:  # noqa: BLE001 - can't tell is «no worker»
        alive = False
    _WORKER_CHECK = (moment, alive)
    return alive


def _dispatch_prefetch(job: PrefetchArtJob) -> None:
    """On the Celery worker, where the prefetch itself runs (see the WP-90 note below);
    in this process when no worker is alive to take it (WP-108)."""

    if worker_available():
        try:
            from app.tasks.journey_prefetch import draw_prefetched_panel_art

            draw_prefetched_panel_art.apply_async(args=[job.prefetch_id])
            return
        except Exception as exc:  # pragma: no cover - broker down
            logger.info("panel_art: prefetch {} drawn in process ({})", job.prefetch_id, exc)
    else:
        logger.info("panel_art: no worker alive, prefetch {} drawn in process", job.prefetch_id)
    _executor().submit(render_prefetch_art, job)


def heal_stale_rendering(db: Session, scenes, *, now: float | None = None) -> int:
    """Serve any panel still ``rendering`` past the timeout as its plate (WP-108).

    Called whenever an episode is read, so it needs no background job and rows stuck
    before this existed heal on their next read. A panel with no ``rendering_since``
    (written before WP-108) counts from its creation. Returns how many were released."""

    stamp = time.time() if now is None else now
    timeout = rendering_timeout_seconds()
    healed = 0
    for scene in scenes:
        for panel in scene.panels:
            meta = panel.generation_metadata or {}
            if meta.get("image_status") != RENDERING:
                continue
            since = meta.get(RENDERING_SINCE_KEY)
            if not isinstance(since, (int, float)):
                created = getattr(panel, "created_at", None)
                if created is not None and created.tzinfo is None:
                    created = created.replace(tzinfo=UTC)  # SQLite hands back naive UTC
                since = created.timestamp() if created is not None else None
            if since is None or stamp - float(since) < timeout:
                continue
            meta = {k: v for k, v in meta.items() if k not in (AWAITING_KEY, RENDERING_SINCE_KEY)}
            meta.update(image_status=FAILED, image_error=TIMEOUT_REASON)
            panel.generation_metadata = meta
            healed += 1
    if healed:
        db.commit()
    return healed


def savepoint_released(session: Session) -> bool:
    """True when ``after_commit`` is only a SAVEPOINT release, not the real commit.

    SQLAlchemy fires ``after_commit`` (and ``after_rollback``) for ``begin_nested()`` too.
    The journey binds a scene inside a savepoint (WP-69), so treating the release as the
    commit dispatched the drawing while the outer transaction was still open: on PostgreSQL
    the worker thread could not see the scene yet, found nothing and returned silently, and
    the panels sat ``rendering`` until the heal (2026-09-30)."""

    return session.in_nested_transaction()


@event.listens_for(Session, "after_commit")
def _dispatch_after_commit(session: Session) -> None:
    if savepoint_released(session):
        return  # the job stays queued for the real commit
    for job in session.info.pop(PENDING_KEY, []):
        try:
            if dispatcher is not None:
                dispatcher(job)
            elif isinstance(job, PrefetchArtJob):
                _dispatch_prefetch(job)
            elif isinstance(job, AdoptArtJob):
                _adopt_executor().submit(adopt_prefetched_art, job)
            else:
                _executor().submit(render_scene_art, job)
        except Exception:  # pragma: no cover - the panels keep their plates
            logger.exception("panel_art: could not dispatch {}", job)


@event.listens_for(Session, "after_rollback")
def _discard_after_rollback(session: Session) -> None:
    if savepoint_released(session):
        # A savepoint rolled back; earlier work in the transaction (and its queued
        # drawings) is still going to commit. A job for the rolled-back scene finds
        # nothing to draw and ends as «missing».
        return
    session.info.pop(PENDING_KEY, None)


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------


def _visual(world: dict) -> dict:
    return (world or {}).get("visual_design") or {}


def _style(world: dict) -> str:
    direction = _visual(world).get("art_direction") or {}
    style = direction.get("style") or (
        "Flat screen-printed illustration in the spirit of vintage French travel posters: large "
        "flat colour shapes, no outlines, slight print misregistration and paper grain."
    )
    palette = direction.get("palette") or ""
    return f"{style} {palette}".strip() + " "


def _cast_names(world: dict) -> dict[str, list[str]]:
    """Every cast id with the words a visual direction may use for them."""

    names: dict[str, list[str]] = {}
    for member in (world or {}).get("cast") or []:
        cid = str(member.get("id") or "")
        if not cid:
            continue
        full = str(member.get("name") or "")
        words = {cid.split("_")[0], *full.replace("«", " ").replace("»", " ").split()}
        names[cid] = sorted({w.strip(".,").casefold() for w in words if len(w.strip(".,")) > 2})
    return names


def characters_in_panel(panel, world: dict, in_frame: list[str] | None = None) -> list[str]:
    """Cast ids in frame: the panel's speakers first, then anyone its direction names.

    ``in_frame`` overrides both — a voice on the phone is not in the picture."""

    if in_frame is not None:
        return [str(cid) for cid in in_frame]

    speakers = [
        str(line.get("character_id"))
        for line in (panel.overlay_payload or {}).get("dialogue") or []
        if line.get("character_id")
    ]
    direction = str(panel.image_prompt or "").casefold()
    named = [
        cid
        for cid, words in _cast_names(world).items()
        if any(re.search(rf"\b{re.escape(word)}\b", direction) for word in words)
    ]
    return list(dict.fromkeys([*speakers, *named]))


def panel_job(
    scene, panel, world: dict, *, location_id: str | None = None, in_frame: list[str] | None = None
) -> PanelJob:
    """``location_id`` and ``in_frame`` let an authored panel leave the scene's place
    (a cut to someone waiting elsewhere) and name who is actually in the picture."""

    visual = _visual(world)
    location_id = location_id or str((scene.script_payload or {}).get("location_id") or "")
    place = ((visual.get("locations") or {}).get(location_id) or {}).get("canonical_descriptor")
    looks = visual.get("characters") or {}
    names = {str(m.get("id")): str(m.get("name") or m.get("id")) for m in world.get("cast") or []}
    cast = characters_in_panel(panel, world, in_frame)
    references = tuple(
        cid for cid in cast if (CAST_REFERENCES / cid / "reference.webp").is_file()
    )[:MAX_REFERENCES_PER_PANEL]
    people = []
    for cid in cast:
        who = names.get(cid, cid)
        look = (looks.get(cid) or {}).get("canonical_descriptor") or ""
        ref = (
            f" (reference image {references.index(cid) + 1}: same face, hair and clothes)"
            if cid in references
            else ""
        )
        people.append(f"{who}{ref}: {look}".strip(": "))
    prompt = (
        _style(world)
        + PANEL_RULES
        + (f"Place: {place} " if place else "")
        + (("In frame: " + "; ".join(people) + ". ") if people else "")
        + f"The panel: {panel.image_prompt}"
    )
    return PanelJob(str(scene.id), int(panel.panel_index), prompt[:3800], references)


# ---------------------------------------------------------------------------
# The image API
# ---------------------------------------------------------------------------


class _ReferencePace:
    """The image API takes a limited number of input images per minute."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.sent: list[float] = []

    def wait(self, count: int) -> None:
        limit = max(1, int(settings.ATELIER_PANEL_ART_REFERENCES_PER_MINUTE))
        count = min(count, limit)
        while True:
            with self.lock:
                now = time.monotonic()
                self.sent = [t for t in self.sent if now - t < 60]
                if len(self.sent) + count <= limit:
                    self.sent.extend([now] * count)
                    return
                pause = 60 - (now - self.sent[0]) + 0.5
            time.sleep(max(0.5, pause))


_PACE = _ReferencePace()


def _png(path: Path) -> bytes:
    from PIL import Image

    buffer = io.BytesIO()
    Image.open(path).save(buffer, format="PNG")
    return buffer.getvalue()


def _base_url() -> str:
    return str(settings.OPENAI_API_BASE or "https://api.openai.com/v1").rstrip("/")


def draw(job: PanelJob) -> bytes:
    """One panel image, as raw bytes. Raises on failure."""

    data = {
        "model": settings.OPENAI_IMAGE_MODEL,
        "prompt": job.prompt,
        "size": PANEL_SIZE,
        "quality": settings.OPENAI_IMAGE_QUALITY,
        "n": 1,
    }
    headers = {"Authorization": f"Bearer {settings.OPENAI_API_KEY}"}
    timeout = float(settings.OPENAI_IMAGE_TIMEOUT_SECONDS)
    response = None
    for attempt in range(3):
        with httpx.Client(timeout=timeout) as client:
            if job.references:
                _PACE.wait(len(job.references))
                files = [
                    ("image[]", (f"{cid}.png", _png(CAST_REFERENCES / cid / "reference.webp"), "image/png"))
                    for cid in job.references
                ]
                response = client.post(
                    f"{_base_url()}/images/edits",
                    headers=headers,
                    data={key: str(value) for key, value in data.items()},
                    files=files,
                )
            else:
                response = client.post(f"{_base_url()}/images/generations", headers=headers, json=data)
        if response.status_code != 429 and response.status_code < 500:
            break
        time.sleep(15 * (attempt + 1))
    if response is None or response.status_code >= 400:
        status = response.status_code if response is not None else "none"
        body = response.text[:200] if response is not None else ""
        raise RuntimeError(f"image API {status}: {body}")
    item = response.json()["data"][0]
    if item.get("b64_json"):
        return base64.b64decode(item["b64_json"])
    with httpx.Client(timeout=60) as client:
        return client.get(item["url"]).content


# ---------------------------------------------------------------------------
# Rendering a scene
# ---------------------------------------------------------------------------


def _world_for(db: Session, scene) -> dict:
    return _world_for_thread(db, scene.serial_thread_id)


def _world_for_thread(db: Session, thread_id: Any) -> dict:
    from app.db.models.serial import SerialThread
    from app.services.serial import SerialThreadService

    thread = None
    if thread_id:
        try:
            thread = db.get(SerialThread, thread_id if isinstance(thread_id, UUID) else UUID(str(thread_id)))
        except ValueError:
            thread = None
    world = thread.world_bible if thread is not None else None
    return world if isinstance(world, dict) and world.get("cast") else SerialThreadService._load_world_bible()


def _store(job: PanelJob, raw: bytes) -> dict:
    import asyncio

    from app.services.graphic_novel_image_storage import GraphicNovelImageStorage

    payload = {
        "url": "data:image/png;base64," + base64.b64encode(raw).decode("ascii"),
        "model": settings.OPENAI_IMAGE_MODEL,
        "quality": settings.OPENAI_IMAGE_QUALITY,
        "size": PANEL_SIZE,
        "references": list(job.references),
    }
    return asyncio.run(
        GraphicNovelImageStorage().persist_payload(
            payload, scene_id=job.scene_id, panel_index=job.panel_index
        )
    )


def _write_back(factory, job: PanelJob, stored: dict | None, error: str | None) -> None:
    from app.db.models.graphic_novel import GraphicNovelScene

    with factory() as db:
        scene = db.get(GraphicNovelScene, UUID(job.scene_id))
        if scene is None:
            return
        panel = next((p for p in scene.panels if p.panel_index == job.panel_index), None)
        if panel is None:
            return
        meta = dict(panel.generation_metadata or {})
        if stored is not None and str(stored.get("url") or "").startswith(("/", "http")):
            panel.image_url = stored["url"]
            panel.image_payload = {k: v for k, v in stored.items() if k != "prompt"}
            # A drawing that lands after the timeout heal still wins: the panel is READY and
            # the stale ``timeout`` reason goes with it.
            for stale in ("image_error", RENDERING_SINCE_KEY, AWAITING_KEY):
                meta.pop(stale, None)
            meta.update(image_source=ART_SOURCE, image_status=READY, image_prompt_sent=job.prompt)
            scene.image_model = settings.OPENAI_IMAGE_MODEL
            scene.image_quality = settings.OPENAI_IMAGE_QUALITY
            _record_cost(db, scene, job)
        else:
            # The plate stays: a failed drawing is a panel without new art, never a gap.
            meta.update(image_status=FAILED, image_error=(error or "not stored")[:300])
        panel.generation_metadata = meta
        db.commit()


def _record_cost(db: Session, scene, job: PanelJob) -> None:
    """One ledger row per drawn panel: art is never free in the books (WP-88)."""

    from app.services.pilot_events import PilotEventService
    from app.services.spend_guard import PANEL_ART_EVENT_TYPE

    PilotEventService(db).record(
        PANEL_ART_EVENT_TYPE,
        user_id=scene.user_id,
        entity_type="graphic_novel_scene",
        entity_id=scene.id,
        payload={
            "panel_index": job.panel_index,
            "model": settings.OPENAI_IMAGE_MODEL,
            "quality": settings.OPENAI_IMAGE_QUALITY,
            "size": PANEL_SIZE,
            "estimated": True,
            "basis": "ATELIER_PANEL_ART_COST_USD_PER_PANEL",
        },
        cost_usd=panel_cost_usd(),
    )


def render_scene_art(job: SceneArtJob) -> str:
    """Draw every panel still ``rendering``; write each back as soon as it is done."""

    from app.db.models.graphic_novel import GraphicNovelScene

    factory = sessionmaker(bind=job.bind, autoflush=False, expire_on_commit=False)
    with factory() as db:
        scene = db.get(GraphicNovelScene, UUID(job.scene_id))
        if scene is None:
            return "missing"
        world = _world_for(db, scene)
        jobs = [
            panel_job(scene, panel, world)
            for panel in sorted(scene.panels, key=lambda p: p.panel_index)
            if (panel.generation_metadata or {}).get("image_status") == RENDERING
            # WP-90: a panel waiting on its prefetch's drawing is not this job's.
            and not (panel.generation_metadata or {}).get(AWAITING_KEY)
            and (job.indices is None or panel.panel_index in job.indices)
        ]
    started = time.monotonic()

    def one(panel: PanelJob) -> bool:
        try:
            stored = _store(panel, draw(panel))
            _write_back(factory, panel, stored, None)
            return True
        except Exception as exc:  # noqa: BLE001 - a panel keeps its plate
            logger.warning("panel_art: scene {} panel {} failed: {}", panel.scene_id, panel.panel_index, exc)
            _write_back(factory, panel, None, f"{exc.__class__.__name__}: {exc}")
            return False

    workers = max(1, int(settings.ATELIER_PANEL_ART_CONCURRENCY))
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="panel-draw") as pool:
        drawn = sum(pool.map(one, jobs))
    logger.info(
        "panel_art: scene {} drew {}/{} panels in {:.0f}s",
        job.scene_id, drawn, len(jobs), time.monotonic() - started,
    )
    return "done" if drawn == len(jobs) else "partial"


# ---------------------------------------------------------------------------
# WP-90 «La planche» — art ready before the tap
# ---------------------------------------------------------------------------
#
# A scene drawn after it is bound opens on the location plate: the drawing arrives about
# a minute after the learner does. A *prefetched* scene (WP-26, the warm draft for the
# next day) is known hours ahead, so its panels are drawn then:
#
# * ``prefetch_scene_for`` calls :func:`request_prefetch_art` in the prefetch's own
#   transaction. It checks the flag, the band and the art allowance of the day it runs
#   (the allowance is per learner-local day, and the drawing is charged to the day it
#   is drawn), writes a zero-cost ``journey_prefetch_art_requested`` row naming the
#   panels, and queues the drawing for after the commit.
# * The drawing runs as its own Celery task (``draw_prefetched_panel_art``) because the
#   prefetch already runs on the worker: a task there is queued durably and survives the
#   beat's child process, where threads left behind by a finished task would not be
#   (``worker_max_tasks_per_child``, a deploy). With no broker it runs in this process.
# * Each drawn panel writes the usual ``journey_panel_art_cost`` row — keyed to the
#   prefetch row (``entity_type = journey_scene_prefetch``) and carrying the stored
#   image — so the ledger is both the bill and the store. A failed one writes a
#   zero-cost ``journey_prefetch_art_failed`` row.
# * ``bind_journey`` calls :func:`attach_prefetched_art`: drawn panels are attached
#   (``ready``), panels whose drawing is still in flight wait for it (an
#   :class:`AdoptArtJob` after the commit, which draws them itself if the prefetch's
#   drawing fails or never comes), and only the rest are requested as usual.
# * A discarded prefetch leaves its drawings unused; their cost rows stay, honestly.

PREFETCH_ART_REQUESTED_EVENT = "journey_prefetch_art_requested"
PREFETCH_ART_FAILED_EVENT = "journey_prefetch_art_failed"
#: On a bound panel's ``generation_metadata``: the prefetch whose drawing it waits for.
AWAITING_KEY = "awaiting_prefetch"
#: A prefetch drawing requested longer ago than this is not waited for at bind time.
PREFETCH_IN_FLIGHT_SECONDS = 20 * 60
#: How long a bound scene waits for drawings still in flight before drawing them itself.
ADOPT_WAIT_SECONDS = 150.0
ADOPT_POLL_SECONDS = 3.0


def _prefetch_vocabulary() -> tuple[str, str, str]:
    from app.services.journey_latency import (
        PREFETCH_DISCARDED_EVENT,
        PREFETCH_ENTITY_TYPE,
        PREFETCH_EVENT,
    )

    return PREFETCH_ENTITY_TYPE, PREFETCH_EVENT, PREFETCH_DISCARDED_EVENT


@dataclass
class PrefetchLedger:
    requested: set[int]
    requested_at: Any
    ready: dict[int, dict]
    failed: set[int]
    discarded: bool

    def in_flight(self) -> bool:
        from datetime import UTC, datetime

        if not self.requested or self.requested_at is None:
            return False
        at = self.requested_at if self.requested_at.tzinfo else self.requested_at.replace(tzinfo=UTC)
        return (datetime.now(UTC) - at).total_seconds() < PREFETCH_IN_FLIGHT_SECONDS

    def pending(self) -> set[int]:
        return self.requested - set(self.ready) - self.failed


def prefetch_ledger(db: Session, prefetch_id: str) -> PrefetchLedger:
    """What the ledger says about one prefetch's drawings."""

    from sqlalchemy import select

    from app.db.models.pilot_event import PilotEvent
    from app.services.spend_guard import PANEL_ART_EVENT_TYPE

    entity_type, _, discarded_event = _prefetch_vocabulary()
    rows = db.scalars(
        select(PilotEvent)
        .where(
            PilotEvent.entity_type == entity_type,
            PilotEvent.entity_id == str(prefetch_id),
            PilotEvent.event_type.in_(
                [
                    PANEL_ART_EVENT_TYPE,
                    PREFETCH_ART_REQUESTED_EVENT,
                    PREFETCH_ART_FAILED_EVENT,
                    discarded_event,
                ]
            ),
        )
        .order_by(PilotEvent.occurred_at.asc())
    ).all()
    ledger = PrefetchLedger(set(), None, {}, set(), False)
    for row in rows:
        payload = row.payload or {}
        if row.event_type == discarded_event:
            ledger.discarded = True
        elif row.event_type == PREFETCH_ART_REQUESTED_EVENT:
            ledger.requested |= {int(i) for i in payload.get("panel_indices") or []}
            ledger.requested_at = row.occurred_at
        elif row.event_type == PREFETCH_ART_FAILED_EVENT:
            ledger.failed.add(int(payload.get("panel_index", -1)))
        elif payload.get("image_url"):
            ledger.ready.setdefault(int(payload.get("panel_index", -1)), payload)
    ledger.failed -= set(ledger.ready)
    return ledger


def _draft_stand_ins(prefetch_id: str, brief: dict) -> tuple[Any, list[Any]]:
    """The scene and panels ``panel_job`` would see once the draft is bound."""

    from types import SimpleNamespace

    context = brief.get("story_context") or {}
    draft = context.get("draft") or {}
    scene = SimpleNamespace(
        id=f"prefetch-{prefetch_id}",
        script_payload={"location_id": draft.get("location_id") or brief.get("location_id")},
    )
    panels = [
        SimpleNamespace(
            panel_index=index,
            image_prompt=str(panel.get("visual_direction") or ""),
            overlay_payload={"dialogue": list(panel.get("dialogue") or [])},
        )
        for index, panel in enumerate(draft.get("panels") or [])
    ]
    return scene, panels


def request_prefetch_art(db: Session, user: Any, prefetch_row, brief) -> int:
    """Queue a prefetched draft's panels for drawing; how many were requested."""

    if not enabled() or not _band_allowed(getattr(brief, "level_band", None)):
        return 0
    draft = (getattr(brief, "story_context", None) or {}).get("draft") or {}
    wanted = len(draft.get("panels") or [])
    count = affordable_panels(db, user, wanted)
    if count <= 0:
        return 0
    from app.services.pilot_events import PilotEventService

    entity_type, _, _ = _prefetch_vocabulary()
    PilotEventService(db).record(
        PREFETCH_ART_REQUESTED_EVENT,
        user_id=getattr(user, "id", None),
        entity_type=entity_type,
        entity_id=prefetch_row.id,
        payload={"panel_indices": list(range(count)), "panels": wanted},
        cost_usd=0.0,
    )
    db.info.setdefault(PENDING_KEY, []).append(PrefetchArtJob(str(prefetch_row.id), db.get_bind()))
    return count


def _scene_for_prefetch(db: Session, prefetch_id: str):
    from sqlalchemy import select

    from app.db.models.graphic_novel import GraphicNovelScene

    return db.scalars(
        select(GraphicNovelScene).where(
            GraphicNovelScene.source_snapshot["prefetch_id"].as_string() == str(prefetch_id)
        )
    ).first()


def _taken_over(factory, prefetch_id: str, panel_index: int) -> bool:
    """Is this drawing no longer wanted? The prefetch was discarded, or its scene is
    bound and that panel is not waiting for it (drawn already, or drawn by the scene)."""

    with factory() as db:
        if prefetch_ledger(db, prefetch_id).discarded:
            return True
        scene = _scene_for_prefetch(db, prefetch_id)
        if scene is None:
            return False
        panel = next((p for p in scene.panels if p.panel_index == panel_index), None)
        return panel is None or (panel.generation_metadata or {}).get(AWAITING_KEY) != str(prefetch_id)


def _record_prefetch_panel(factory, user_id, prefetch_id: str, job: PanelJob, stored, error) -> bool:
    from app.services.pilot_events import PilotEventService
    from app.services.spend_guard import PANEL_ART_EVENT_TYPE

    entity_type, _, _ = _prefetch_vocabulary()
    ok = stored is not None and str(stored.get("url") or "").startswith(("/", "http"))
    with factory() as db:
        if ok:
            PilotEventService(db).record(
                PANEL_ART_EVENT_TYPE,
                user_id=user_id,
                entity_type=entity_type,
                entity_id=prefetch_id,
                payload={
                    "panel_index": job.panel_index,
                    "model": settings.OPENAI_IMAGE_MODEL,
                    "quality": settings.OPENAI_IMAGE_QUALITY,
                    "size": PANEL_SIZE,
                    "estimated": True,
                    "basis": "ATELIER_PANEL_ART_COST_USD_PER_PANEL",
                    "prefetch": True,
                    "image_url": stored["url"],
                    "image_payload": {k: v for k, v in stored.items() if k != "prompt"},
                    "prompt_sent": job.prompt,
                },
                cost_usd=panel_cost_usd(),
            )
        else:
            PilotEventService(db).record(
                PREFETCH_ART_FAILED_EVENT,
                user_id=user_id,
                entity_type=entity_type,
                entity_id=prefetch_id,
                payload={"panel_index": job.panel_index, "error": (error or "not stored")[:300]},
                cost_usd=0.0,
            )
        db.commit()
    return ok


def render_prefetch_art(job: PrefetchArtJob) -> str:
    """Draw the requested panels of a prefetched draft; one ledger row each."""

    from app.db.models.pilot_event import PilotEvent

    _, prefetch_event, _ = _prefetch_vocabulary()
    factory = sessionmaker(bind=job.bind, autoflush=False, expire_on_commit=False)
    with factory() as db:
        row = db.get(PilotEvent, UUID(job.prefetch_id))
        if row is None or row.event_type != prefetch_event:
            return "missing"
        ledger = prefetch_ledger(db, job.prefetch_id)
        if ledger.discarded:
            return "discarded"
        brief = (row.payload or {}).get("brief") or {}
        scene, panels = _draft_stand_ins(job.prefetch_id, brief)
        world = _world_for_thread(db, brief.get("serial_thread_id"))
        user_id = row.user_id
        todo = ledger.pending()
        jobs = [panel_job(scene, panel, world) for panel in panels if panel.panel_index in todo]
    started = time.monotonic()

    def one(panel: PanelJob) -> bool:
        if _taken_over(factory, job.prefetch_id, panel.panel_index):
            return False
        try:
            stored = _store(panel, draw(panel))
            return _record_prefetch_panel(factory, user_id, job.prefetch_id, panel, stored, None)
        except Exception as exc:  # noqa: BLE001 - the bound scene draws it instead
            logger.warning("panel_art: prefetch {} panel {} failed: {}", job.prefetch_id, panel.panel_index, exc)
            _record_prefetch_panel(factory, user_id, job.prefetch_id, panel, None, f"{exc.__class__.__name__}: {exc}")
            return False

    workers = max(1, int(settings.ATELIER_PANEL_ART_CONCURRENCY))
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="panel-prefetch") as pool:
        drawn = sum(pool.map(one, jobs))
    logger.info(
        "panel_art: prefetch {} drew {}/{} panels in {:.0f}s",
        job.prefetch_id, drawn, len(jobs), time.monotonic() - started,
    )
    return "done" if drawn == len(jobs) else "partial"


def _attach(panel, ready: dict, prefetch_id: str) -> None:
    meta = {k: v for k, v in (panel.generation_metadata or {}).items() if k != AWAITING_KEY}
    panel.image_url = ready["image_url"]
    panel.image_payload = dict(ready.get("image_payload") or {"url": ready["image_url"]})
    meta.update(
        image_source=ART_SOURCE,
        image_status=READY,
        image_prompt_sent=ready.get("prompt_sent"),
        prefetch_id=str(prefetch_id),
    )
    panel.generation_metadata = meta


def attach_prefetched_art(
    db: Session, scene, prefetch_id: str, *, level_band: str | None = None, user: Any = None
) -> dict[str, int]:
    """At bind time: attach what the prefetch drew, wait for what it is still drawing,
    and request only the rest. No panel is drawn twice while its drawing is on the way."""

    prefetch_id = str(prefetch_id)
    ledger = prefetch_ledger(db, prefetch_id)
    in_flight = ledger.in_flight()
    attached, awaiting, missing = 0, [], []
    for panel in sorted(scene.panels, key=lambda p: p.panel_index):
        ready = ledger.ready.get(int(panel.panel_index))
        if ready is not None:
            _attach(panel, ready, prefetch_id)
            attached += 1
        elif in_flight and int(panel.panel_index) in ledger.pending():
            panel.generation_metadata = {
                **(panel.generation_metadata or {}),
                "image_status": RENDERING,
                RENDERING_SINCE_KEY: time.time(),
                AWAITING_KEY: prefetch_id,
            }
            awaiting.append(panel)
        else:
            missing.append(panel)
    if attached:
        scene.image_model = settings.OPENAI_IMAGE_MODEL
        scene.image_quality = settings.OPENAI_IMAGE_QUALITY
    if awaiting:
        db.info.setdefault(PENDING_KEY, []).append(AdoptArtJob(str(scene.id), prefetch_id, db.get_bind()))
    requested = 0
    if missing and request_scene_art(db, scene, level_band=level_band, user=user, panels=missing):
        requested = sum(
            1 for p in missing if (p.generation_metadata or {}).get("image_status") == RENDERING
        )
    return {"attached": attached, "awaiting": len(awaiting), "requested": requested}


def adopt_prefetched_art(job: AdoptArtJob, *, wait_seconds: float | None = None) -> str:
    """Fill a bound scene's waiting panels as its prefetch draws them.

    A drawing that fails, or has not come within ``ADOPT_WAIT_SECONDS``, is drawn by
    the scene itself, inside today's allowance; a panel the allowance does not cover
    keeps its plate."""

    from app.db.models.graphic_novel import GraphicNovelScene
    from app.db.models.user import User

    factory = sessionmaker(bind=job.bind, autoflush=False, expire_on_commit=False)
    deadline = time.monotonic() + (ADOPT_WAIT_SECONDS if wait_seconds is None else wait_seconds)
    to_draw: list[int] = []
    while True:
        with factory() as db:
            scene = db.get(GraphicNovelScene, UUID(job.scene_id))
            if scene is None:
                return "missing"
            ledger = prefetch_ledger(db, job.prefetch_id)
            waiting = [
                p for p in scene.panels if (p.generation_metadata or {}).get(AWAITING_KEY) == job.prefetch_id
            ]
            expired = time.monotonic() >= deadline
            released = []
            for panel in waiting:
                ready = ledger.ready.get(int(panel.panel_index))
                if ready is not None:
                    _attach(panel, ready, job.prefetch_id)
                    scene.image_model = settings.OPENAI_IMAGE_MODEL
                    scene.image_quality = settings.OPENAI_IMAGE_QUALITY
                elif expired or int(panel.panel_index) in ledger.failed or ledger.discarded:
                    released.append(panel)
            if released:
                user = db.get(User, scene.user_id) if scene.user_id else None
                count = affordable_panels(db, user, len(released)) if enabled() else 0
                for position, panel in enumerate(sorted(released, key=lambda p: p.panel_index)):
                    meta = {k: v for k, v in (panel.generation_metadata or {}).items() if k != AWAITING_KEY}
                    if position < count:
                        meta["image_status"] = RENDERING
                        meta[RENDERING_SINCE_KEY] = time.time()
                        to_draw.append(int(panel.panel_index))
                    else:
                        meta.pop("image_status", None)
                    panel.generation_metadata = meta
            left = len(waiting) - len(released) - sum(
                1 for p in waiting if int(p.panel_index) in ledger.ready
            )
            db.commit()
        if left <= 0:
            break
        time.sleep(ADOPT_POLL_SECONDS)
    if to_draw:
        render_scene_art(SceneArtJob(job.scene_id, job.bind, tuple(to_draw)))
        return "drew_missing"
    return "adopted"
