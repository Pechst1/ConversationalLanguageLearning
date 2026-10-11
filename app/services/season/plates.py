"""WP-165 · season plates: the image model paints places, not people.

Under the drawn art set (WP-157) a panel is its location plate with the SVG cast standing
on it; a generated picture with people in it is never shown. So the image model's job is
the room: a people-free plate in the owner's ``PLATE_STYLE`` (``scripts/art/atelier_art.py``).

The shared interface for three packages:

* WP-165 — the season's own places, and their light and weather variants;
* WP-167 — a news day's own plate, prompted new for that day;
* WP-168 — the places of a season the writer moved to a new city.

:func:`paint_plate` makes one image call, palette-locks it, checks the print (a plate
that drifted into gradients or photographic colour is painted once more and the flatter
one kept, :func:`style_problem`), stores the WebP where ``panel_art`` stores durable art
(S3 in production, ``var/`` locally) and records it in ``revue_places`` under its key, so
a key is painted once and shared. :func:`plate_url_for` is what a panel shows *now*: the
painted variant, else the painted base, else the static plate of ``season.world`` — it
never waits for a painting.

**Light and weather.** The director sets a scene's ``time_of_day`` (morning, day, evening,
night) and ``weather`` (dry, rain). A place's committed plate is painted in one light
(``season.world.place_light``); any other pair is a *variant*: an edit of that plate,
same layout, other light, painted lazily in the background the first time a scene asks
for it (:func:`schedule_variant`) while the base plate is served. At most 7 variants a
place (4 × 2 minus the base), about US$0.05 each, each painted once for every learner.
"""

from __future__ import annotations

import re
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from loguru import logger

from app.config import settings

if TYPE_CHECKING:
    from PIL import Image
    from sqlalchemy.orm import Session

PROMPT_VERSION = "season-plate-v1"
#: ``revue_places.id`` prefix: season plates share the Revue's table, never its ids.
KEY_PREFIX = "season:"
TIMES_OF_DAY: tuple[str, ...] = ("morning", "day", "evening", "night")
WEATHERS: tuple[str, ...] = ("dry", "rain")
#: A scene that names only one of the two gets the other from here.
DEFAULT_TIME_OF_DAY = "day"
DEFAULT_WEATHER = "dry"
#: The place template. ``{brief}`` names the place, three landmarks and the light.
PLATE_TEMPLATE = "{brief}. Seen from where a visitor would stand, room for figures in the foreground. "
#: A variant is an edit of the place's own plate: same room, same objects, other light.
VARIANT_TEMPLATE = (
    "Redraw this exact place keeping its layout, viewpoint, proportions and every key object, as the "
    "same flat screen print in the same inks. Change only the light and the weather. {brief}. "
)

#: The story's calendar is late autumn and winter in Paris (November to January).
LIGHT_PHRASES: dict[str, tuple[str, str]] = {
    # time of day: (outdoors, indoors)
    "morning": (
        "early morning in late autumn, a low pale sun from one side, long cool shadows, the first "
        "sunflower glow on the highest façades",
        "early morning, low pale sunlight slanting in through the window in flat bars, cool shadows",
    ),
    "day": (
        "plain late-autumn daylight under a pale sky, even and calm",
        "plain daylight from the windows, even and calm",
    ),
    "evening": (
        "dusk, the sky deep cobalt, street lamps and windows just lit in sunflower yellow",
        "dusk, the windows deep cobalt, the lamps just lit in flat warm pools",
    ),
    "night": (
        "night, the sky near-black ink and deep cobalt, only lamps, windows and signs lit, in flat "
        "pools of sunflower and vermilion",
        "night, the windows black-blue, the room lit only by its lamps in flat warm pools",
    ),
}
WEATHER_PHRASES: dict[str, tuple[str, str]] = {
    "dry": ("dry weather", "dry weather outside"),
    "rain": (
        "steady rain, slanted flat strokes of rain, the wet ground mirroring the lights in broken "
        "flat stripes, puddles",
        "rain outside, rain streaks on the windowpanes, the street beyond grey and wet",
    ),
}


class SeasonPlateOff(RuntimeError):
    """Painting is off here (flag, key or storage); the caller shows the static plate."""


def plate_key(
    place_id: str,
    *,
    time_of_day: str | None = None,
    weather: str | None = None,
    day: str | None = None,
) -> str:
    """The ``revue_places`` id of a plate: ``season:<place>[:<time>][:<weather>][:<day>]``.

    ``day`` is for a plate painted for one day only (a news day, WP-167): an ISO date
    plus whatever makes it unique to that day's story.
    """

    parts = [re.sub(r"[^a-z0-9_-]+", "-", str(place_id).lower()).strip("-") or "place"]
    if time_of_day in TIMES_OF_DAY:
        parts.append(str(time_of_day))
    if weather in WEATHERS:
        parts.append(str(weather))
    if day:
        parts.append(re.sub(r"[^a-z0-9_-]+", "-", str(day).lower()).strip("-"))
    return (KEY_PREFIX + ":".join(parts))[:120]


def generation_unavailable_reason() -> str | None:
    """Why :func:`paint_plate` would refuse, or ``None`` when it may paint."""

    from app.services.panel_art import durable_storage
    from app.services.revue import plates as revue_plates

    if not settings.ATELIER_SEASON_PLATES_ENABLED:
        return "ATELIER_SEASON_PLATES_ENABLED is false"
    if not (settings.OPENAI_API_KEY or revue_plates._art()._ENV.get("OPENAI_API_KEY")):  # noqa: SLF001
        return "no OPENAI_API_KEY"
    if not durable_storage():
        return "production needs GRAPHIC_NOVEL_IMAGE_STORAGE=s3 and a bucket"
    return None


def _clean(brief: str | None) -> str:
    return re.sub(r"\s+", " ", str(brief or "")).strip().rstrip(" .;,")


def prompt_for(brief: str) -> str:
    """Style (with its no-people clause), the place, the negative clause."""

    from app.services.revue import plates as revue_plates
    from app.services.revue import policy

    style = revue_plates._art().PLATE_STYLE  # noqa: SLF001 - the owner's one style
    return style + PLATE_TEMPLATE.format(brief=_clean(brief)) + policy.PLATE_NEGATIVE


def variant_prompt_for(brief: str) -> str:
    """An edit of the place's own plate: same room, the light and weather ``brief`` names."""

    from app.services.revue import plates as revue_plates
    from app.services.revue import policy

    style = revue_plates._art().PLATE_STYLE  # noqa: SLF001
    return style + VARIANT_TEMPLATE.format(brief=_clean(brief)) + policy.PLATE_NEGATIVE


# ---------------------------------------------------------------------------
# Light and weather
# ---------------------------------------------------------------------------


def normalise_light(time_of_day: Any = None, weather: Any = None) -> tuple[str | None, str | None]:
    """The closed (time_of_day, weather) pair a scene asks for, or ``(None, None)``.

    An unknown word is no word; when only one of the two is named the other takes its
    default (``day``, ``dry``), so a place has at most 4 × 2 lights."""

    tod = str(time_of_day or "").strip().lower()
    wet = str(weather or "").strip().lower()
    tod = tod if tod in TIMES_OF_DAY else ""
    wet = wet if wet in WEATHERS else ""
    if not tod and not wet:
        return None, None
    return tod or DEFAULT_TIME_OF_DAY, wet or DEFAULT_WEATHER


def light_phrase(place_id: str | None, time_of_day: str, weather: str) -> str:
    from app.services.season.world import place_is_outdoor

    side = 0 if place_is_outdoor(place_id) else 1
    return f"{LIGHT_PHRASES[time_of_day][side]}; {WEATHER_PHRASES[weather][side]}"


def variant_key(place_id: str | None, time_of_day: Any = None, weather: Any = None) -> str | None:
    """The key of the variant a scene in this light asks for, or ``None`` when no light is
    named, the place's own plate is that light already, or its light never changes."""

    from app.services.season.world import place_light, place_takes_variants

    if not place_id:
        return None
    tod, wet = normalise_light(time_of_day, weather)
    if tod is None or wet is None or not place_takes_variants(place_id):
        return None
    if place_light(place_id) == (tod, wet):
        return None
    return plate_key(place_id, time_of_day=tod, weather=wet)


# English words in an authored panel's ``visual`` that name its light (WP-165: a tentpole
# carries its light when it is trivially derivable from its own direction).
_LIGHT_WORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("night", ("night", "midnight", "nocturnal", "moonlight", "moonlit")),
    ("evening", ("evening", "dusk", "sunset", "twilight", "nightfall")),
    ("morning", ("morning", "dawn", "sunrise", "breakfast")),
    ("day", ("afternoon", "noon", "midday", "daylight", "sunlit", "sunny")),
)
_RAIN_WORDS = ("rain", "rainy", "raining", "drizzle", "downpour", "umbrella", "umbrellas")
_DRY_WORDS = ("sunny", "sunlit", "sunshine", "clear sky", "dry")


def light_from_text(text: str | None, carried: dict[str, str] | None = None) -> dict[str, str]:
    """``{"time_of_day", "weather"}`` named by a panel's English direction, else ``carried``
    (the panel before it: within one page time runs on, it does not reset)."""

    out = dict(carried or {})
    words = f" {re.sub(r'[^a-z ]+', ' ', str(text or '').lower())} "
    for name, cues in _LIGHT_WORDS:
        if any(f" {cue} " in words for cue in cues):
            out["time_of_day"] = name
            break
    if any(f" {cue} " in words for cue in _RAIN_WORDS):
        out["weather"] = "rain"
    elif any(f" {cue} " in words for cue in _DRY_WORDS):
        out["weather"] = "dry"
    return out


# ---------------------------------------------------------------------------
# Lookups (never paint, never wait)
# ---------------------------------------------------------------------------

#: A key looked up and not painted is not looked up again for this long (a panel is
#: read often; a variant appears at most once).
MISS_TTL_SECONDS = 60.0
_MISSES: dict[str, float] = {}


def painted_url(db: Session | None, key: str) -> str | None:
    from app.services.revue import plates as revue_plates

    return revue_plates.painted_url(db, key)


def _lookup(db: Session | None, key: str) -> str | None:
    from app.services.revue import plates as revue_plates

    hit = revue_plates._PAINTED.get(key)  # noqa: SLF001
    if hit or db is None:
        return hit
    if time.monotonic() - _MISSES.get(key, float("-inf")) < MISS_TTL_SECONDS:
        return None
    hit = painted_url(db, key)
    if hit:
        _MISSES.pop(key, None)
        return hit
    _MISSES[key] = time.monotonic()
    return None


def plate_url_for(
    db: Session | None,
    place_id: str | None,
    *,
    time_of_day: str | None = None,
    weather: str | None = None,
) -> str | None:
    """The best plate there is right now; never paints, never waits.

    The painted variant, else the painted base, else the static plate of
    ``season.world``, else ``None``.
    """

    from app.services.season.world import plate_for

    if not place_id:
        return None
    key = variant_key(place_id, time_of_day, weather)
    if key:
        hit = _lookup(db, key)
        if hit:
            return hit
    return _lookup(db, plate_key(place_id)) or plate_for(place_id)


def scene_plate_url(
    db: Session | None,
    place_id: str | None,
    *,
    time_of_day: str | None = None,
    weather: str | None = None,
    fallback: str | None = None,
) -> str | None:
    """What a scene's panel opens on (bind time): :func:`plate_url_for`, and the missing
    variant queued for painting in the background. ``fallback`` (the world bible's image)
    only for a place ``season.world`` does not know."""

    url = plate_url_for(db, place_id, time_of_day=time_of_day, weather=weather)
    if variant_key(place_id, time_of_day, weather):
        schedule_variant(db, place_id, time_of_day=time_of_day, weather=weather)  # a no-op once painted
    return url or fallback


def panel_variant_url(db: Session | None, meta: dict | None) -> str | None:
    """Read time: a panel's painted variant once it exists (``None`` until then, and the
    panel keeps its stored ``plate_url``). A miss queues the painting again, in case the
    process that was painting it went away."""

    meta = meta or {}
    place = meta.get("plate_place_id")
    key = variant_key(place, meta.get("time_of_day"), meta.get("weather")) if place else None
    if not key:
        return None
    hit = _lookup(db, key)
    if hit is None and db is not None:
        schedule_variant(db, str(place), time_of_day=meta.get("time_of_day"), weather=meta.get("weather"))
    return hit


def plate_meta(place_id: str | None, time_of_day: Any = None, weather: Any = None) -> dict[str, str]:
    """What a panel's ``generation_metadata`` keeps so a read can find its variant."""

    tod, wet = normalise_light(time_of_day, weather)
    if not place_id or tod is None or wet is None:
        return {}
    return {"plate_place_id": str(place_id), "time_of_day": tod, "weather": wet}


# ---------------------------------------------------------------------------
# The style check (after palette_lock): a plate that is not a flat print
# ---------------------------------------------------------------------------

#: Width the plate is reduced to before measuring (a stroke of grain disappears, a
#: gradient across a wall does not).
_STYLE_WIDTH = 128
#: A ramp: at least this many neighbouring pixels, each step between these levels (of
#: 255) in the same direction, adding up to at least this much. A flat fill steps 0, an
#: edge of a shape steps far more, hatching changes direction.
_RAMP_STEP = (0.3, 8.0)
_RAMP_MIN_PIXELS = 5
_RAMP_MIN_CHANGE = 8.0
#: Calibrated on 2026-10-11 against the 11 raw season plates (0.020–0.064), 25 painted
#: panels of the old shaded style (0.13–0.17 for the soft-lit ones) and synthetic skies
#: (1.0). A plate above it is not a flat print.
GRADIENT_MAX = 0.10
#: Share of the locked plate within ``_INK_RADIUS`` of a brand ink: the originals hold
#: 0.65–0.88; a photograph's colours stay far from the inks even after the lock.
PALETTE_MIN = 0.55
_INK_RADIUS = 30.0


def _luma(image: Image.Image, width: int) -> Any:
    import numpy as np
    from PIL import Image as PILImage
    from PIL import ImageFilter

    height = max(8, round(width * image.height / max(1, image.width)))
    small = image.convert("RGB").resize((width, height), PILImage.Resampling.BOX).filter(ImageFilter.MedianFilter(3))
    return np.asarray(small, dtype=np.float32) @ np.array([0.299, 0.587, 0.114], dtype=np.float32)


def gradient_share(image: Image.Image) -> float:
    """Share of the plate covered by smooth ramps (rows and columns), 0–1."""

    import numpy as np

    luma = _luma(image, _STYLE_WIDTH)
    lo, hi = _RAMP_STEP
    mask = np.zeros(luma.shape, dtype=bool)
    for lines, out in ((luma, mask), (luma.T, mask.T)):
        steps = np.diff(lines, axis=1)
        for index in range(steps.shape[0]):
            row = steps[index]
            start, sign, total = -1, 0.0, 0.0
            for i in range(len(row) + 1):
                step = float(row[i]) if i < len(row) else 0.0
                fits = i < len(row) and lo <= abs(step) <= hi
                if fits and start >= 0 and np.sign(step) == sign:
                    total += abs(step)
                    continue
                if start >= 0 and i - start >= _RAMP_MIN_PIXELS and total >= _RAMP_MIN_CHANGE:
                    out[index, start : i + 1] = True
                start, sign, total = (i, float(np.sign(step)), abs(step)) if fits else (-1, 0.0, 0.0)
    return float(mask.mean())


def ink_share(image: Image.Image) -> float:
    """Share of the plate within reach of one of the palette lock's inks, 0–1."""

    import numpy as np
    from PIL import Image as PILImage
    from PIL import ImageFilter

    from app.services.revue import plates as revue_plates

    inks = np.array(
        [[int(code[i : i + 2], 16) for i in (1, 3, 5)] for code in revue_plates._art().LOCK_PALETTE],  # noqa: SLF001
        dtype=np.float32,
    )
    small = image.convert("RGB").resize((192, 128), PILImage.Resampling.BOX).filter(ImageFilter.MedianFilter(3))
    pixels = np.asarray(small, dtype=np.float32).reshape(-1, 3)
    distance = np.sqrt(((pixels[:, None, :] - inks[None, :, :]) ** 2).sum(-1)).min(1)
    return float((distance <= _INK_RADIUS).mean())


def style_report(locked: Image.Image, raw: Image.Image | None = None) -> dict[str, float]:
    """``gradient`` (measured on the raw paint: the lock bands a gradient, it does not
    remove it) and ``ink`` (on the locked plate the learner sees)."""

    return {"gradient": gradient_share(raw if raw is not None else locked), "ink": ink_share(locked)}


def style_problem(locked: Image.Image, raw: Image.Image | None = None) -> str | None:
    """``gradients``, ``off_palette``, ``flag`` (the Revue's flag band) or ``None``."""

    from app.services.revue import plates as revue_plates

    report = style_report(locked, raw)
    if report["gradient"] > GRADIENT_MAX:
        return "gradients"
    if report["ink"] < PALETTE_MIN:
        return "off_palette"
    if revue_plates.looks_wrong(locked):
        return "flag"
    return None


def _style_cost(locked: Image.Image, raw: Image.Image | None) -> float:
    report = style_report(locked, raw)
    return max(0.0, report["gradient"] - GRADIENT_MAX) * 10 + max(0.0, PALETTE_MIN - report["ink"])


# ---------------------------------------------------------------------------
# Painting
# ---------------------------------------------------------------------------


def _call(prompt: str, reference: Image.Image | None = None) -> Image.Image:
    """One image call through the owner's pipeline; with ``reference``, an edit of it."""

    from app.services.revue import plates as revue_plates

    if reference is None:
        return revue_plates._call(prompt)  # noqa: SLF001
    art = revue_plates._art()  # noqa: SLF001
    env = art._ENV  # noqa: SLF001 - the script's own dotenv dict
    if not env.get("OPENAI_API_KEY") and settings.OPENAI_API_KEY:
        env["OPENAI_API_KEY"] = settings.OPENAI_API_KEY
    if not env.get("OPENAI_IMAGE_MODEL") and settings.OPENAI_IMAGE_MODEL:
        art.MODEL = settings.OPENAI_IMAGE_MODEL
    return art._call(prompt, size=revue_plates.PLATE_SIZE, reference=reference.convert("RGB"))  # noqa: SLF001


def paint_checked(prompt: str, *, reference: Image.Image | None = None, label: str = "plate") -> tuple[Image.Image, dict]:
    """Paint, palette-lock and check one plate; a plate that is not a flat print is painted
    once more and the flatter of the two kept. Returns the locked plate and what happened
    (``calls``, ``problem`` of the first, ``kept``, the ``report`` of the one kept)."""

    from app.services.revue import plates as revue_plates

    raw = _call(prompt, reference).convert("RGB")
    locked = revue_plates.palette_lock(raw)
    problem = style_problem(locked, raw)
    info: dict[str, Any] = {"calls": 1, "problem": problem, "kept": "first"}
    if problem:
        logger.info("season plates: {} is not a flat print ({}); painting once more", label, problem)
        raw_two = _call(prompt, reference).convert("RGB")
        locked_two = revue_plates.palette_lock(raw_two)
        info["calls"] = 2
        info["second_problem"] = style_problem(locked_two, raw_two)
        if _style_cost(locked_two, raw_two) <= _style_cost(locked, raw):
            raw, locked, info["kept"] = raw_two, locked_two, "second"
        if info["second_problem"] and info["kept"] == "second":
            logger.warning("season plates: {} still {} after one repaint; kept", label, info["second_problem"])
    info["report"] = style_report(locked, raw)
    return locked, info


def paint_plate(
    db: Session,
    key: str,
    brief: str,
    *,
    name_fr: str | None = None,
    reference: Image.Image | None = None,
) -> str:
    """Paint ``key`` once from ``brief`` and return its URL; a painted key is never repainted.

    One image call (1536×1024, medium, about US$0.05), two when the style check asks
    for a repaint. With ``reference`` (a variant) the call is an edit of that plate:
    ``brief`` then says the place and the new light. Raises :class:`SeasonPlateOff`
    when painting is off and lets the image API's error through: callers that serve a
    learner catch both and keep the static plate.
    """

    from sqlalchemy.exc import IntegrityError

    from app.db.models.revue_place import RevuePlace
    from app.services.revue import plates as revue_plates

    existing = painted_url(db, key)
    if existing:
        return existing
    reason = generation_unavailable_reason()
    if reason:
        raise SeasonPlateOff(reason)
    prompt = variant_prompt_for(brief) if reference is not None else prompt_for(brief)
    image, _info = paint_checked(prompt, reference=reference, label=key)
    url = revue_plates._store(key.replace(":", "-"), revue_plates._webp(image))  # noqa: SLF001
    db.add(
        RevuePlace(
            id=key,
            name_fr=(name_fr or key)[:200],
            brief=_clean(brief),
            plate_url=url,
            prompt_version=PROMPT_VERSION,
        )
    )
    try:
        db.commit()
    except IntegrityError:  # a concurrent paint won: theirs is the plate
        db.rollback()
        winner = db.get(RevuePlace, key)
        if winner is not None:
            revue_plates._PAINTED[key] = winner.plate_url  # noqa: SLF001
            return winner.plate_url
        raise
    revue_plates._PAINTED[key] = url  # noqa: SLF001
    _MISSES.pop(key, None)
    logger.info("season plates: painted {} ({})", key, PROMPT_VERSION)
    return url


# ---------------------------------------------------------------------------
# Variants, painted lazily in the background
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VariantJob:
    key: str
    place_id: str
    time_of_day: str
    weather: str
    bind: Any


#: Tests replace this with a recording dispatcher (as ``panel_art.dispatcher``).
dispatcher: Callable[[VariantJob], Any] | None = None
#: A variant whose painting failed is not tried again for this long.
RETRY_AFTER_SECONDS = 3600.0
_LOCK = threading.Lock()
_IN_FLIGHT: set[str] = set()
_FAILED: dict[str, float] = {}
_EXECUTOR: ThreadPoolExecutor | None = None


def _executor() -> ThreadPoolExecutor:
    global _EXECUTOR
    with _LOCK:
        if _EXECUTOR is None:
            # One at a time: the image API allows few reference images a minute, and a
            # variant is never urgent (the base plate is on screen meanwhile).
            _EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="season-plate")
        return _EXECUTOR


def variant_brief(place_id: str, time_of_day: str, weather: str, db: Session | None = None) -> str | None:
    """The place without its own light, then the light asked for."""

    from app.services.season.world import place_brief

    base = place_brief(place_id, with_light=False)
    if base is None and db is not None:
        from app.db.models.revue_place import RevuePlace

        try:
            row = db.get(RevuePlace, plate_key(place_id))
        except Exception:  # noqa: BLE001 - an old database without the table
            row = None
        base = row.brief if row is not None else None
    if not base:
        return None
    return f"{_clean(base)}. Now: {light_phrase(place_id, time_of_day, weather)}"


def base_plate_image(db: Session | None, place_id: str) -> Image.Image | None:
    """The place's committed plate (the reference a variant is an edit of), or ``None``."""

    from PIL import Image as PILImage

    from app.services.season.world import static_plate_path

    path = static_plate_path(place_id)
    if path is None:
        return None
    try:
        with PILImage.open(path) as image:
            return image.convert("RGB")
    except OSError:
        return None


def schedule_variant(
    db: Session | None,
    place_id: str | None,
    *,
    time_of_day: str | None = None,
    weather: str | None = None,
) -> str | None:
    """Queue the painting of a missing variant; never waits, never raises.

    Returns the queued key, or ``None``: no variant is needed, it is painted or in
    flight, it failed within the hour, painting is off, or there is no brief to paint
    it from."""

    key = variant_key(place_id, time_of_day, weather)
    if key is None or db is None or not place_id:
        return None
    try:
        if generation_unavailable_reason() or _lookup(db, key):  # the flag first: no query when off
            return None
        tod, wet = normalise_light(time_of_day, weather)
        if tod is None or wet is None or variant_brief(place_id, tod, wet, db) is None:
            return None
        with _LOCK:
            if key in _IN_FLIGHT or time.monotonic() - _FAILED.get(key, float("-inf")) < RETRY_AFTER_SECONDS:
                return None
            _IN_FLIGHT.add(key)
        job = VariantJob(key=key, place_id=str(place_id), time_of_day=tod, weather=wet, bind=db.get_bind())
        (dispatcher or (lambda queued: _executor().submit(paint_variant, queued)))(job)
    except Exception:  # noqa: BLE001 - the base plate is on screen; a variant is never worth a 500
        logger.exception("season plates: could not queue {}", key)
        with _LOCK:
            _IN_FLIGHT.discard(key)
        return None
    logger.info("season plates: queued {}", key)
    return key


def paint_variant(job: VariantJob) -> str | None:
    """The background job: paint one variant in its own session. Never raises."""

    from sqlalchemy.orm import sessionmaker

    from app.services.season.world import location_name_fr

    factory = sessionmaker(bind=job.bind, autoflush=False, expire_on_commit=False)
    try:
        with factory() as db:
            brief = variant_brief(job.place_id, job.time_of_day, job.weather, db)
            if brief is None:
                return None
            name = f"{location_name_fr(job.place_id)} ({job.time_of_day}, {job.weather})"
            return paint_plate(db, job.key, brief, name_fr=name, reference=base_plate_image(db, job.place_id))
    except SeasonPlateOff:
        return None
    except Exception as exc:  # noqa: BLE001 - the base plate stays on screen
        _FAILED[job.key] = time.monotonic()
        logger.warning("season plates: painting {} failed ({})", job.key, exc)
        return None
    finally:
        with _LOCK:
            _IN_FLIGHT.discard(job.key)


def reset_for_tests() -> None:
    """Forget every cached lookup, in-flight and failed key (tests only)."""

    from app.services.revue import plates as revue_plates

    _MISSES.clear()
    _FAILED.clear()
    with _LOCK:
        _IN_FLIGHT.clear()
    revue_plates._PAINTED.clear()  # noqa: SLF001
