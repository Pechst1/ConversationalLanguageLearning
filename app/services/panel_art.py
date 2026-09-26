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


# ---------------------------------------------------------------------------
# Queueing on the session, dispatching after its commit
# ---------------------------------------------------------------------------

#: Tests replace this with an inline or recording dispatcher.
dispatcher: Callable[[SceneArtJob], Any] | None = None
_EXECUTOR: ThreadPoolExecutor | None = None
_EXECUTOR_LOCK = threading.Lock()


def enabled() -> bool:
    return bool(settings.ATELIER_PANEL_ART_ENABLED and settings.OPENAI_API_KEY)


def request_scene_art(db: Session, scene) -> bool:
    """Mark the scene's panels ``rendering`` and draw them once ``db`` commits."""

    if not enabled():
        return False
    for panel in scene.panels:
        panel.generation_metadata = {
            **(panel.generation_metadata or {}),
            "image_status": RENDERING,
        }
    db.info.setdefault(PENDING_KEY, []).append(SceneArtJob(str(scene.id), db.get_bind()))
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


@event.listens_for(Session, "after_commit")
def _dispatch_after_commit(session: Session) -> None:
    for job in session.info.pop(PENDING_KEY, []):
        try:
            if dispatcher is not None:
                dispatcher(job)
            else:
                _executor().submit(render_scene_art, job)
        except Exception:  # pragma: no cover - the panels keep their plates
            logger.exception("panel_art: could not dispatch scene {}", job.scene_id)


@event.listens_for(Session, "after_rollback")
def _discard_after_rollback(session: Session) -> None:
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
    from app.db.models.serial import SerialThread
    from app.services.serial import SerialThreadService

    thread = db.get(SerialThread, scene.serial_thread_id) if scene.serial_thread_id else None
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
            meta.update(image_source=ART_SOURCE, image_status=READY, image_prompt_sent=job.prompt)
            scene.image_model = settings.OPENAI_IMAGE_MODEL
            scene.image_quality = settings.OPENAI_IMAGE_QUALITY
        else:
            # The plate stays: a failed drawing is a panel without new art, never a gap.
            meta.update(image_status=FAILED, image_error=(error or "not stored")[:300])
        panel.generation_metadata = meta
        db.commit()


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
