"""Les planches: a painted plate for each new place of La Revue (WP-119 §8.1, phase 4).

A dossier names one or two places (§12.7): the site of the story for ``arrive`` and
``facts``, and a second view for ``pursue`` and ``make``. A place the season already
knows keeps its season plate. A new place gets one plate, painted once and shared by
every learner, cached forever in ``revue_places``.

* :data:`REVUE_PLATE_STYLE` is the owner's ``PLATE_STYLE`` (``scripts/art/atelier_art.py``)
  with the people clause instead of "No people…" (§12.4: real people and places are
  allowed, drawn small, from a distance or from behind, never as portraits), and the
  prompt ends on the negative clause the feasibility run showed was needed (no flags,
  emblems, logos or anything readable). National colours in architecture are fine.
* :func:`brief_for` validates a brief the builder wrote: **name + three landmarks +
  light** (§8.1 specificity rules); it refuses a brief for a ``kind: place`` entity that
  does not contain that entity's name, a brief with a ``PLATE_FORBIDDEN`` word, a brief
  with fewer than three descriptive clauses and a brief that says nothing of the light.
* :func:`paint` makes one image call (1536×1024, medium), palette-locks it, stores the
  WebP where ``panel_art`` stores durable art (S3 in production, ``var/`` locally) and
  writes the row. One call, and the result is final (owner, 2026-10-14): it never
  repaints. Gated by ``REVUE_PLATE_GENERATION_ENABLED`` (per environment) and
  ``panel_art.durable_storage()``.
* :func:`looks_wrong` is the cheap post-check: a large saturated blue-white-red band in
  the upper centre (a flag the model reached for). It is logged and kept on the row
  (``flagged``) for the owner; the picture stays.
* :func:`plate_for_place` is what the stage shows: the season plate, else the painted
  one, else the nearest known plate (``policy.PLACE_FALLBACKS``) marked ``stand_in`` so
  Romy's ``place_note`` says where they really are.

**Story pictures (§8.4).** A dossier with a ``visual`` gets one picture of its story, not of
its place: the site's brief plus the moment that says what happened, the people by their
role (:data:`policy.STORY_PEOPLE_CLAUSE`), the words the picture shows and a composition that
keeps the moment beside Romy at every crop (:data:`policy.STORY_STAGE_CLAUSE`), in the same
screen print and palette lock as every season plate. :func:`paint_story` paints it once, final, into
``revue_story_pictures``; :func:`site_plate` puts it on the stage before any place plate.
:func:`paint_dossier_pictures` and :func:`paint_period` are the intake's painters
(``app/tasks/revue.py``): every picture a period's kiosk is missing, one call each, within
the service's daily cap, each priced on the pilot ledger (:data:`PICTURE_COST_EVENT`).

See ``docs/implementation/atelier-v2/WP-119-LA-REVUE-DE-ROMY.md`` §8.1, §8.4, §10b phase 4, §12.4, §12.7.
"""

from __future__ import annotations

import hashlib
import importlib.util
import io
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Any, Literal

from loguru import logger
from PIL import Image

from app.config import settings
from app.db.models.revue_place import RevuePlace
from app.db.models.revue_story_picture import RevueStoryPicture
from app.services.revue import checks, policy
from app.services.revue.checks import brief_missing_place_names

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.services.revue.dossier import EditorialDossier, Place

#: Bumped whenever the template below changes; stored on each painted row.
PROMPT_VERSION = "revue-plate-v2"
PLATE_SIZE = "1536x1024"
PLATE_WEBP_QUALITY = 86
#: Key prefix under the durable art store (S3 bucket or ``GRAPHIC_NOVEL_LOCAL_IMAGE_DIR``).
STORAGE_PREFIX = "revue-plates"
#: §8.4: the story pictures' template version and key prefix.
STORY_PROMPT_VERSION = "revue-story-v1"
STORY_STORAGE_PREFIX = "revue-stories"
#: The pilot-ledger row each painting writes (no learner: the picture is everyone's).
PICTURE_COST_EVENT = "revue_picture_cost"

_ART_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "art" / "atelier_art.py"
_SEASON_NO_PEOPLE = "No people, no animals, no readable text or signage. "


@cache
def _art() -> ModuleType:
    """The owner's art pipeline (``scripts/art/atelier_art.py``), loaded once by path.

    The style, the palette lock and the image call live there so there is one style in
    version control; this module only adds the Revue's clauses.
    """

    name = "atelier_art_pipeline"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _ART_SCRIPT)
    if spec is None or spec.loader is None:  # pragma: no cover - the script ships in the image
        raise ImportError(f"cannot load {_ART_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _revue_style() -> str:
    base = _art().PLATE_STYLE
    if _SEASON_NO_PEOPLE not in base:  # the season style changed: fail loudly, not silently
        raise RuntimeError("atelier_art.PLATE_STYLE no longer carries the no-people clause to replace")
    return base.replace(_SEASON_NO_PEOPLE, policy.PLATE_PEOPLE_CLAUSE + " ")


def _story_style() -> str:
    base = _art().PLATE_STYLE
    if _SEASON_NO_PEOPLE not in base:
        raise RuntimeError("atelier_art.PLATE_STYLE no longer carries the no-people clause to replace")
    return base.replace(_SEASON_NO_PEOPLE, policy.STORY_PEOPLE_CLAUSE + " ")


#: ``PLATE_STYLE`` with the people clause (§8.1, §12.4) instead of "No people, no animals…".
REVUE_PLATE_STYLE = _revue_style()
#: §8.4: the same screen print, with the story's people (by role, never a likeness).
REVUE_STORY_STYLE = _story_style()

#: The place template (§8.1). ``{brief}`` is a brief that passed :func:`brief_for`.
PLATE_TEMPLATE = "{brief}, France, seen from where a visitor would stand. "


def prompt_for(brief: str) -> str:
    """The full image prompt: style with the people clause, the place, the negative clause."""

    return REVUE_PLATE_STYLE + PLATE_TEMPLATE.format(brief=brief) + policy.PLATE_NEGATIVE


# ---------------------------------------------------------------------------
# The brief rule (§8.1 specificity: name + three landmarks + light)
# ---------------------------------------------------------------------------

#: Words that say what the light is; a brief without one leaves the model to guess the hour.
LIGHT_WORDS: tuple[str, ...] = (
    "light", "lights", "lit", "daylight", "sunlight", "sunlit", "sun", "sunny", "sunset", "sunrise",
    "dawn", "dusk", "morning", "afternoon", "evening", "night", "noon", "twilight", "overcast", "grey",
    "gray", "rain", "rainy", "fog", "foggy", "mist", "misty", "lamp", "lamps", "lamplight", "glow",
    "shade", "shadow", "shadows", "lumiere", "matin", "soir", "nuit", "aube", "crepuscule", "soleil",
)
#: Descriptive clauses (comma, semicolon or colon separated) a brief needs: the place or its
#: name, then at least two more landmarks and the light (§8.1 rule 1).
MIN_BRIEF_CLAUSES = 3
MAX_BRIEF_CHARS = 600


class PlateBriefError(ValueError):
    """A brief the plate pipeline refuses; ``reason`` is a stable code."""

    def __init__(self, reason: str, **detail: Any) -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


def _normalise(brief: str | None) -> str:
    text = re.sub(r"\s+", " ", str(brief or "")).strip()
    return text.rstrip(" .;,")


def brief_for(place: Place, dossier: EditorialDossier | None = None) -> str:
    """Validate and normalise the builder's brief for ``place``; raise :class:`PlateBriefError`.

    Reasons: ``empty_brief``, ``brief_too_long``, ``forbidden_words`` (``policy.PLATE_FORBIDDEN``:
    portraits, emblems, logos, text), ``brief_without_place_name`` (the brief is for a
    ``kind: place`` entity of the dossier and does not contain its name — the same rule as
    ``checks.check_render``), ``brief_too_thin`` (fewer than :data:`MIN_BRIEF_CLAUSES`
    clauses: a type, not a place), ``brief_without_light``. Well-known places are named;
    a private or unremarkable place stays typed (§8.1 rule 2), so the name is only
    required when the dossier lists the place as an entity.
    """

    text = _normalise(place.brief)
    if not text:
        raise PlateBriefError("empty_brief", place_id=place.id)
    if len(text) > MAX_BRIEF_CHARS:
        raise PlateBriefError("brief_too_long", place_id=place.id, chars=len(text))
    hits = policy.plate_forbidden_hits(text)
    if hits:
        raise PlateBriefError("forbidden_words", place_id=place.id, words=hits)
    if dossier is not None:
        missing = brief_missing_place_names(place.id, place.name_fr, text, dossier)
        if missing:
            raise PlateBriefError("brief_without_place_name", place_id=place.id, missing=missing)
    clauses = [part for part in re.split(r"[,;:]", text) if part.strip()]
    if len(clauses) < MIN_BRIEF_CLAUSES:
        raise PlateBriefError("brief_too_thin", place_id=place.id, clauses=len(clauses))
    tokens = set(policy._tokens(text))  # noqa: SLF001 - the policy's own accent-folded tokens
    if not tokens & set(LIGHT_WORDS):
        raise PlateBriefError("brief_without_light", place_id=place.id)
    return text


# ---------------------------------------------------------------------------
# The post-check: a flag the model reached for
# ---------------------------------------------------------------------------

#: The part of the plate searched for a flag: the upper centre, where a podium's flags hang.
_FLAG_REGION = (0.12, 0.0, 0.88, 0.7)  # x0, y0, x1, y1 as fractions
_FLAG_GRID = (192, 128)
#: A stripe stacked vertically (a draped flag seen from the front, colours one above the
#: other) is at least this many grid rows tall, over at least this many adjacent columns…
_DRAPED_MIN_RUN = 8
_DRAPED_MIN_COLUMNS = 3
#: …a hanging flag's stripe at least this many grid columns wide, over a tenth of the height.
_HANGING_MIN_RUN = 4
_HANGING_MIN_ROWS_FRACTION = 0.1
#: The white and red stripes of one flag are about the same size.
_STRIPE_RATIO = 2.5

_BLUE, _WHITE, _RED = 1, 2, 3


def _colour_labels(image: Image.Image) -> Any:
    """0 other, 1 saturated blue, 2 white or paper, 3 saturated red (per pixel)."""

    import numpy as np

    hsv = np.asarray(image.convert("HSV"), dtype=np.float32) / 255.0
    hue, sat, val = hsv[..., 0] * 360.0, hsv[..., 1], hsv[..., 2]
    labels = np.zeros(hue.shape, dtype=np.int8)
    labels[(hue >= 205) & (hue <= 250) & (sat >= 0.4) & (val >= 0.25)] = _BLUE
    labels[(sat <= 0.3) & (val >= 0.75)] = _WHITE
    labels[((hue <= 15) | (hue >= 345)) & (sat >= 0.5) & (val >= 0.4)] = _RED
    return labels


def _runs(line: Any) -> list[tuple[int, int, int]]:
    """(label, start, length) runs of a line, minus one-pixel unlabelled seams."""

    out: list[tuple[int, int, int]] = []
    start = 0
    for i in range(1, len(line) + 1):
        if i == len(line) or line[i] != line[start]:
            out.append((int(line[start]), start, i - start))
            start = i
    return [run for run in out if not (run[0] == 0 and run[2] <= 1)]


def _tricolour_hits(lines: Any, min_run: int) -> list[tuple[int, int]]:
    """(line index, white start) for each blue | white | red run triple (either order)."""

    found: list[tuple[int, int]] = []
    for index, line in enumerate(lines):
        runs = _runs(line)
        for i, (a, b, c) in enumerate(zip(runs, runs[1:], runs[2:], strict=False)):
            if b[0] != _WHITE or {a[0], c[0]} != {_BLUE, _RED}:
                continue
            red, blue = (a, c) if a[0] == _RED else (c, a)
            beyond = (runs[i - 1] if i > 0 else None) if red is a else (runs[i + 3] if i + 3 < len(runs) else None)
            if beyond is not None and beyond[0] == _WHITE:
                continue  # red | white | red…: a striped awning, not a flag
            if b[2] < min_run or red[2] < min_run or blue[2] < 2:
                continue  # the blue may merge into a blue wall: only its presence counts
            if max(b[2], red[2]) / min(b[2], red[2]) > _STRIPE_RATIO:
                continue
            found.append((index, b[1]))
    return found


def _longest_chain(found: list[tuple[int, int]], drift: int = 3) -> int:
    """The most hits on neighbouring lines (gap ≤ 1) whose white stripe stays in place."""

    found = sorted(found)
    best = 0
    for i, (line, pos) in enumerate(found):
        length, last_line, last_pos = 1, line, pos
        for next_line, next_pos in found[i + 1:]:
            if next_line - last_line > 2:
                break
            if next_line - last_line >= 1 and abs(next_pos - last_pos) <= drift:
                length, last_line, last_pos = length + 1, next_line, next_pos
        best = max(best, length)
    return best


def looks_wrong(image: Image.Image) -> bool:
    """A large blue | white | red flag (either order) in the upper centre of the plate.

    Deliberately simple (§8.1): the plate is cut to a 192×128 grid of colour labels
    (saturated blue, white/paper, saturated red); a flag is the same three runs side by
    side, white in the middle and about as large as the red, either down several
    neighbouring columns (a draped flag, stripes one above the other — what the
    feasibility run's press room got) or along a tenth of the rows (a flag hanging flat).
    Calibrated on 31 plates (the season set, the 2026-10-02 feasibility run and the
    phase-4 evidence): fires on the feasibility press room only. The caller keeps the
    picture (one call, final) and notes it on the row for the owner.
    """

    small = image.convert("RGB").resize(_FLAG_GRID)
    w, h = small.size
    x0, y0, x1, y1 = (int(f * s) for f, s in zip(_FLAG_REGION, (w, h, w, h), strict=True))
    labels = _colour_labels(small)[y0:y1, x0:x1]
    if _longest_chain(_tricolour_hits(labels.T, _DRAPED_MIN_RUN)) >= _DRAPED_MIN_COLUMNS:
        return True
    return _longest_chain(_tricolour_hits(labels, _HANGING_MIN_RUN)) >= max(2, int(_HANGING_MIN_ROWS_FRACTION * h))


# ---------------------------------------------------------------------------
# Painting and storing
# ---------------------------------------------------------------------------


class PlateGenerationOff(RuntimeError):
    """``paint`` was asked for a new plate while generation is off or storage is not durable."""


def generation_unavailable_reason() -> str | None:
    """Why :func:`paint` would refuse to paint, or ``None`` when it may."""

    from app.services.panel_art import durable_storage

    if not settings.REVUE_PLATE_GENERATION_ENABLED:
        return "REVUE_PLATE_GENERATION_ENABLED is false"
    if not (settings.OPENAI_API_KEY or _art()._ENV.get("OPENAI_API_KEY")):  # noqa: SLF001
        return "no OPENAI_API_KEY"
    if not durable_storage():
        return "production needs GRAPHIC_NOVEL_IMAGE_STORAGE=s3 and a bucket"
    return None


def _call(prompt: str) -> Image.Image:
    """One image call through the owner's pipeline (``atelier_art._call``), 1536×1024 medium.

    The key and the model come from ``.env`` as the script reads them; the app's settings
    fill them in where there is no ``.env`` (a deployed container).
    """

    art = _art()
    env = art._ENV  # noqa: SLF001 - the script's own dotenv dict
    if not env.get("OPENAI_API_KEY") and settings.OPENAI_API_KEY:
        env["OPENAI_API_KEY"] = settings.OPENAI_API_KEY
    if not env.get("OPENAI_IMAGE_MODEL") and settings.OPENAI_IMAGE_MODEL:
        art.MODEL = settings.OPENAI_IMAGE_MODEL
    return art._call(prompt, size=PLATE_SIZE)  # noqa: SLF001


def palette_lock(image: Image.Image) -> Image.Image:
    return _art().palette_lock(image)


def _webp(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="WEBP", quality=PLATE_WEBP_QUALITY, method=4)
    return buffer.getvalue()


def _store(place_id: str, content: bytes, *, prefix: str = STORAGE_PREFIX) -> str:
    """Store a plate where ``panel_art`` stores durable art; return its public URL.

    ``s3`` → the bucket (immutable cache headers); ``local`` and ``data_uri`` → the local
    image directory (a plate is never inlined: it is shared and kept forever). ``prefix``:
    :data:`STORAGE_PREFIX` for a place, :data:`STORY_STORAGE_PREFIX` for a story picture.
    """

    from app.services.graphic_novel_image_storage import DecodedImage, GraphicNovelImageStorage

    digest = hashlib.sha256(content).hexdigest()
    safe = re.sub(r"[^a-z0-9_-]+", "-", place_id.lower()).strip("-") or "place"
    key = f"{prefix}/{safe}-{digest[:16]}.webp"
    image = DecodedImage(content=content, content_type="image/webp", extension=".webp", source_kind="generated")
    storage = GraphicNovelImageStorage()
    if str(settings.GRAPHIC_NOVEL_IMAGE_STORAGE).strip().lower() == "s3":
        return storage._store_s3(key=key, image=image)  # noqa: SLF001
    return storage._store_local(key=key, image=image)  # noqa: SLF001


#: Painted plates seen in this process (place id → url): rows are never rewritten, so a
#: hit is good forever. Lets :func:`plate_for_place` answer without a session.
_PAINTED: dict[str, str] = {}


def painted_url(db: Session | None, place_id: str) -> str | None:
    if place_id in _PAINTED:
        return _PAINTED[place_id]
    if db is None:
        return None
    try:
        with db.begin_nested():  # a failed lookup must not poison the caller's transaction
            row = db.get(RevuePlace, place_id)
    except Exception as exc:  # noqa: BLE001 - a missing table (an old database) is a stand-in, not a 500
        logger.debug("revue plates: lookup failed for {} ({})", place_id, exc)
        return None
    if row is None:
        return None
    _PAINTED[place_id] = row.plate_url
    return row.plate_url


def paint(db: Session, place_id: str, brief: str, *, name_fr: str | None = None) -> str:
    """Paint ``place_id`` once and return its plate URL; a painted place is never repainted.

    ``brief`` must already have passed :func:`brief_for`. One image call, and its result
    is final: when :func:`looks_wrong` fires it is logged, never painted again. Raises
    :class:`PlateGenerationOff` when the flag is off or storage is not durable, and lets
    the image API's error through.
    """

    from sqlalchemy.exc import IntegrityError

    existing = painted_url(db, place_id)
    if existing:
        return existing
    reason = generation_unavailable_reason()
    if reason:
        raise PlateGenerationOff(reason)
    prompt = prompt_for(_normalise(brief))
    image = _call(prompt).convert("RGB")
    flagged = looks_wrong(image)
    if flagged:  # one call, final (owner, 2026-10-14): noted for the owner, never repainted
        logger.warning("revue plates: {} shows a flag band; kept (final)", place_id)
    url = _store(place_id, _webp(palette_lock(image)))
    row = RevuePlace(
        id=place_id,
        name_fr=(name_fr or place_id)[:200],
        brief=_normalise(brief),
        plate_url=url,
        prompt_version=PROMPT_VERSION,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:  # a concurrent paint won: theirs is the plate (ours was still paid for)
        db.rollback()
        _record_cost(db, kind="place", entity_id=place_id, prompt_version=PROMPT_VERSION, flagged=flagged)
        winner = db.get(RevuePlace, place_id)
        if winner is not None:
            _PAINTED[place_id] = winner.plate_url
            return winner.plate_url
        raise
    _record_cost(db, kind="place", entity_id=place_id, prompt_version=PROMPT_VERSION, flagged=flagged)
    _PAINTED[place_id] = url
    logger.info("revue plates: painted {} ({})", place_id, PROMPT_VERSION)
    return url


#: Asked by a painting run before every image call: the reason to hold it (``"limit"``,
#: ``"budget"``), or ``None`` to paint.
PaintGate = Callable[[], str | None]


def paint_dossier_places(
    db: Session, dossier: EditorialDossier, *, places: list[Place] | None = None, gate: PaintGate | None = None,
) -> dict[str, str]:
    """Paint every new place of ``dossier`` (or of ``places``) that has none yet.

    Returns place id → plate URL or the refusal reason (``known``, ``painted``, a
    :class:`PlateBriefError` reason, ``off``, ``error``, or what ``gate`` held it for). Never
    raises: a place without a plate shows its stand-in.
    """

    from app.services.season.world import SEASON_ONE_LOCATIONS

    out: dict[str, str] = {}
    for place in (dossier.places[:2] if places is None else places):
        if place.id in SEASON_ONE_LOCATIONS:
            out[place.id] = "known"
            continue
        if painted_url(db, place.id):
            out[place.id] = "painted"
            continue
        try:
            brief = brief_for(place, dossier)
            held = gate() if gate is not None else None
            out[place.id] = held or paint(db, place.id, brief, name_fr=place.name_fr)
        except PlateBriefError as exc:
            logger.info("revue plates: brief for {} refused ({})", place.id, exc.reason)
            out[place.id] = exc.reason
        except PlateGenerationOff:
            out[place.id] = "off"
        except Exception as exc:  # noqa: BLE001 - the stand-in covers a failed paint
            logger.warning("revue plates: painting {} failed ({})", place.id, exc)
            out[place.id] = "error"
    return out


# ---------------------------------------------------------------------------
# Story pictures (§8.4)
# ---------------------------------------------------------------------------


def picture_cost_usd() -> float:
    """What one 1536×1024 medium picture costs (``REVUE_PICTURE_COST_USD``), for the ledger."""

    return max(0.0, float(getattr(settings, "REVUE_PICTURE_COST_USD", 0.06) or 0.0))


def _model_name() -> str:
    return str(getattr(_art(), "MODEL", "") or settings.OPENAI_IMAGE_MODEL or "")[:80]


def _record_cost(db: Session, *, kind: str, entity_id: str, prompt_version: str, flagged: bool) -> None:
    """One pilot-ledger row per painting, with no learner (the picture is everyone's), so the
    service's daily cap (``spend_guard.service_budget_reached``) and the digest count it.
    Written after the picture's own commit; telemetry never fails a painting."""

    try:
        from app.services.pilot_events import PilotEventService

        PilotEventService(db).record(
            PICTURE_COST_EVENT,
            user_id=None,
            entity_type=f"revue_{kind}",
            entity_id=entity_id,
            payload={"kind": kind, "prompt_version": prompt_version, "flagged": flagged, "model": _model_name()},
            cost_usd=picture_cost_usd(),
        )
        db.commit()
    except Exception as exc:  # noqa: BLE001 - the picture is stored either way
        db.rollback()
        logger.warning("revue plates: the cost row for {} was not written ({})", entity_id, exc)


@dataclass(frozen=True)
class StoryPicture:
    """A painted story picture as the stage reads it (a ``revue_story_pictures`` row)."""

    url: str
    caption_fr: str
    place_id: str
    flagged: bool = False


#: Story pictures seen in this process (dossier id → picture): rows are final, so a hit is
#: good forever. A miss is not remembered: the worker may paint it a minute later.
_STORIES: dict[str, StoryPicture] = {}


def story_picture(db: Session | None, dossier_id: str) -> StoryPicture | None:
    """The story's painted picture, or ``None`` (not painted yet, never, or no table)."""

    if dossier_id in _STORIES:
        return _STORIES[dossier_id]
    if db is None:
        return None
    try:
        with db.begin_nested():  # a failed lookup must not poison the caller's transaction
            row = db.get(RevueStoryPicture, dossier_id)
    except Exception as exc:  # noqa: BLE001 - a missing table (an old database) is the place plate, not a 500
        logger.debug("revue plates: story lookup failed for {} ({})", dossier_id, exc)
        return None
    if row is None:
        return None
    picture = StoryPicture(url=row.picture_url, caption_fr=row.caption_fr, place_id=row.place_id, flagged=bool(row.flagged))
    _STORIES[dossier_id] = picture
    return picture


def _sentence(text: str | None) -> str:
    """``text`` as one prompt sentence: whitespace folded, a full stop, a trailing space."""

    value = re.sub(r"\s+", " ", str(text or "")).strip().rstrip(" ,;:")
    if not value:
        return ""
    return value + ("" if value[-1] in ".!?" else ".") + " "


def _site_text(place: Place, dossier: EditorialDossier) -> str:
    """The site as the story's painter reads it: the brief that passed :func:`brief_for`; a
    brief refused for its form (too thin, no light: the story brings its own light, no name:
    the name goes first) keeps its words; one with a forbidden word or a person's name, or
    none at all, is replaced by the place's name."""

    name = _normalise(place.name_fr)
    try:
        text = brief_for(place, dossier)
    except PlateBriefError as exc:
        if exc.reason in {"forbidden_words", "empty_brief", "brief_too_long"}:
            return name
        text = _normalise(place.brief)
        if exc.reason == "brief_without_place_name":
            text = f"{name}: {text}"
    return name if checks.person_names_in(text, dossier) else text


def story_prompt_for(dossier: EditorialDossier) -> str:
    """The story picture's full prompt (§8.4): the season's screen print with the story's
    people, the site, the moment, the object that carries the idea, the words it must show,
    the viewpoint and light, the stage's composition, the negative clause.

    Refuses (:class:`PlateBriefError`) a dossier without a visual (``no_visual``) and a visual
    the staging checks refuse (``person_named``, ``forbidden_words``): the builder repairs or
    drops those, so this is the painter's own last look before money is spent.
    """

    visual = dossier.visual
    if visual is None or not dossier.places:
        raise PlateBriefError("no_visual", dossier_id=dossier.id)
    for failure in checks.failures(checks.check_visual(dossier)):
        if failure.reason in {"person_named", "forbidden_words"}:
            raise PlateBriefError(failure.reason, dossier_id=dossier.id, **failure.detail)
    site = _site_text(dossier.places[0], dossier)
    shows = [word.shows.strip().rstrip(".") for word in visual.words if word.shows.strip()]
    viewpoint = visual.viewpoint.strip()
    seen = f"Seen {viewpoint}" if viewpoint.lower().startswith(("from ", "through ", "across ", "over ")) else f"Viewpoint: {viewpoint}"
    return (
        REVUE_STORY_STYLE
        + _sentence(f"The place: {site}, France")
        + _sentence(f"The scene, one moment of this week's news: {visual.moment}")
        + (_sentence(f"At the heart of the moment: {visual.symbol}") if visual.symbol else "")
        + (_sentence("The picture clearly shows " + "; ".join(shows)) if shows else "")
        + _sentence(seen)
        + _sentence(f"Light: {visual.light}")
        + policy.STORY_STAGE_CLAUSE
        + " "
        + policy.PLATE_NEGATIVE
    )


def paint_story(db: Session, dossier: EditorialDossier) -> str:
    """Paint ``dossier``'s story picture once and return its URL; a painted story is never repainted.

    One image call (1536×1024, medium) and its result is final (owner, 2026-10-14): when
    :func:`looks_wrong` fires it is noted on the row (``flagged``) for the owner, never painted
    again. Palette-locked and stored like a plate, under :data:`STORY_STORAGE_PREFIX`; the row
    keeps the caption and the full prompt; the cost goes on the pilot ledger. Raises
    :class:`PlateBriefError` (no visual, a refused one), :class:`PlateGenerationOff`, and lets
    the image API's error through.
    """

    from sqlalchemy.exc import IntegrityError

    existing = story_picture(db, dossier.id)
    if existing is not None:
        return existing.url
    prompt = story_prompt_for(dossier)
    visual = dossier.visual
    if visual is None:  # pragma: no cover - story_prompt_for refused it already
        raise PlateBriefError("no_visual", dossier_id=dossier.id)
    reason = generation_unavailable_reason()
    if reason:
        raise PlateGenerationOff(reason)
    image = _call(prompt).convert("RGB")
    flagged = looks_wrong(image)
    if flagged:
        logger.warning("revue plates: the story picture of {} shows a flag band; kept (final)", dossier.id)
    url = _store(dossier.id, _webp(palette_lock(image)), prefix=STORY_STORAGE_PREFIX)
    place_id = dossier.places[0].id
    db.add(
        RevueStoryPicture(
            dossier_id=dossier.id,
            place_id=place_id[:120],
            picture_url=url,
            caption_fr=visual.caption_fr,
            prompt=prompt,
            prompt_version=STORY_PROMPT_VERSION,
            model=_model_name() or None,
            cost_usd=picture_cost_usd(),
            flagged=flagged,
        )
    )
    try:
        db.commit()
    except IntegrityError:  # a concurrent paint won: theirs is the picture (ours was still paid for)
        db.rollback()
        _record_cost(db, kind="story", entity_id=dossier.id, prompt_version=STORY_PROMPT_VERSION, flagged=flagged)
        winner = story_picture(db, dossier.id)
        if winner is not None:
            return winner.url
        raise
    _record_cost(db, kind="story", entity_id=dossier.id, prompt_version=STORY_PROMPT_VERSION, flagged=flagged)
    _STORIES[dossier.id] = StoryPicture(url=url, caption_fr=visual.caption_fr, place_id=place_id, flagged=flagged)
    logger.info("revue plates: painted the story picture of {} ({})", dossier.id, STORY_PROMPT_VERSION)
    return url


def paint_dossier_pictures(db: Session, dossier: EditorialDossier, *, gate: PaintGate | None = None) -> dict[str, str]:
    """Every picture ``dossier`` is missing: its story picture, and a plate for each new place
    the story picture does not cover (the second view; the site too when there is no story
    picture). Returns key → URL or reason, the story under ``"story"``. ``gate`` is asked
    before each image call (a painted story makes none). Never raises."""

    out: dict[str, str] = {}
    story_ok = False
    held: str | None = None
    if dossier.visual is not None and dossier.places:
        try:
            held = gate() if gate is not None and story_picture(db, dossier.id) is None else None
            if held:
                out["story"] = held
            else:
                out["story"] = paint_story(db, dossier)
                story_ok = True
        except PlateBriefError as exc:
            logger.info("revue plates: the story picture of {} was refused ({})", dossier.id, exc.reason)
            out["story"] = exc.reason
        except PlateGenerationOff:
            out["story"] = "off"
        except Exception as exc:  # noqa: BLE001 - the place plate covers a failed paint; tomorrow retries
            logger.warning("revue plates: painting the story of {} failed ({})", dossier.id, exc)
            db.rollback()
            out["story"] = "error"
    # A held story is painted by the next run: its site needs no place plate meanwhile.
    places = dossier.places[1:2] if story_ok or held else dossier.places[:2]
    out.update(paint_dossier_places(db, dossier, places=places, gate=gate))
    return out


@dataclass
class PaintReport:
    """What one painting run did (the beat logs it, the admin route returns it)."""

    period: str
    status: str = "painted"
    painted: int = 0
    pictures: dict[str, dict[str, str]] = field(default_factory=dict)
    cost_usd: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "period": self.period,
            "status": self.status,
            "painted": self.painted,
            "pictures": {key: dict(value) for key, value in self.pictures.items()},
            "cost_usd": round(self.cost_usd, 6),
        }


def _painted_now(value: str) -> bool:
    return "/" in value or value.startswith("data:")


def paint_period(db: Session, period: str, *, limit: int | None = None) -> PaintReport:
    """Paint what ``period``'s kiosk is missing, one picture after another, until done, the
    service's daily cap is met (``spend_guard.service_budget_reached``) or ``limit`` image
    calls are made; both are asked before every call, so a dossier's second picture is held
    like any other. Off (``status``) when painting is unavailable. What is already painted
    costs nothing; what was held or failed is painted by the next run."""

    from app.services import spend_guard
    from app.services.revue.encounter import available_dossiers

    report = PaintReport(period=period)
    reason = generation_unavailable_reason()
    if reason:
        report.status = f"off: {reason}"
        return report
    calls = 0
    held: str | None = None

    def gate() -> str | None:
        nonlocal calls, held
        if held is None:
            if limit is not None and calls >= limit:
                held = "limit"
            elif spend_guard.service_budget_reached(db):
                held = "budget"
            else:
                calls += 1
        return held

    for dossier in available_dossiers(period, db):
        if held:
            break
        known = story_picture(db, dossier.id) is not None  # paint_story answers a painted story with its URL
        result = paint_dossier_pictures(db, dossier, gate=gate)
        report.pictures[dossier.id] = result
        report.painted += sum(1 for key, value in result.items() if _painted_now(value) and not (key == "story" and known))
    if held:
        report.status = held
    report.cost_usd = round(report.painted * picture_cost_usd(), 6)
    logger.bind(period=period, painted=report.painted, status=report.status).info("revue plates: painted {} picture(s)", report.painted)
    return report


# ---------------------------------------------------------------------------
# What the stage shows
# ---------------------------------------------------------------------------


PlateKind = Literal["story", "painted", "season", "stand_in"]


@dataclass(frozen=True)
class PlateChoice:
    """The plate the stage shows for a place. ``stand_in``: another place's plate stands in
    (Romy's ``place_note`` then says where they really are); ``plate_place_id`` is whose
    plate it is (the place itself when painted or known). ``kind``: the story's own picture
    (§8.4, with its ``caption_fr``), a painted place, a season plate, or a stand-in."""

    url: str | None
    plate_place_id: str
    stand_in: bool
    kind: PlateKind = "season"
    caption_fr: str | None = None


def plate_for_place(db: Session | None, place: Place) -> PlateChoice:
    """Season plate for a known id; the painted plate when there is one (whatever the flag:
    a painted plate is paid for); else the nearest known plate by ``policy.PLACE_FALLBACKS``
    with ``stand_in=True``. Never paints (painting takes ~35 s; see :func:`paint_dossier_places`)."""

    from app.services.season.world import SEASON_ONE_LOCATIONS, plate_for

    if place.id in SEASON_ONE_LOCATIONS:
        return PlateChoice(url=plate_for(place.id), plate_place_id=place.id, stand_in=False, kind="season")
    painted = painted_url(db, place.id)
    if painted:
        return PlateChoice(url=painted, plate_place_id=place.id, stand_in=False, kind="painted")
    kind = policy.place_kind(f"{place.id} {place.name_fr} {place.brief}")
    fallback = policy.fallback_place_for(kind)
    return PlateChoice(url=plate_for(fallback), plate_place_id=fallback, stand_in=True, kind="stand_in")


def site_plate(db: Session | None, dossier: EditorialDossier, place: Place) -> PlateChoice:
    """§8.4: what the stage shows for ``place``: the story's own picture when ``place`` is the
    site and the picture is painted, else :func:`plate_for_place`. Never paints."""

    if dossier.visual is not None and dossier.places and place.id == dossier.places[0].id:
        picture = story_picture(db, dossier.id)
        if picture is not None:
            return PlateChoice(url=picture.url, plate_place_id=place.id, stand_in=False, kind="story",
                               caption_fr=picture.caption_fr)
    return plate_for_place(db, place)

