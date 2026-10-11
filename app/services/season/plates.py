"""WP-165 · season plates: the image model paints places, not people.

Under the drawn art set (WP-157) a panel is its location plate with the SVG cast standing
on it; a generated picture with people in it is never shown. So the image model's job is
the room: a people-free plate in the owner's ``PLATE_STYLE`` (``scripts/art/atelier_art.py``).

The shared interface for three packages:

* WP-165 — the season's own places, and their light and weather variants;
* WP-167 — a news day's own plate, prompted new for that day;
* WP-168 — the places of a season the writer moved to a new city.

:func:`paint_plate` makes one image call, palette-locks it, stores the WebP where
``panel_art`` stores durable art (S3 in production, ``var/`` locally) and records it in
``revue_places`` under its key, so a key is painted once and shared. :func:`plate_url_for`
is what a panel shows *now*: the painted variant, else the painted base, else the static
plate of ``season.world`` — it never waits for a painting.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from loguru import logger

from app.config import settings

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

PROMPT_VERSION = "season-plate-v1"
#: ``revue_places.id`` prefix: season plates share the Revue's table, never its ids.
KEY_PREFIX = "season:"
TIMES_OF_DAY: tuple[str, ...] = ("morning", "day", "evening", "night")
WEATHERS: tuple[str, ...] = ("dry", "rain")
#: The place template. ``{brief}`` names the place, three landmarks and the light.
PLATE_TEMPLATE = "{brief}. Seen from where a visitor would stand, room for figures in the foreground. "


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


def prompt_for(brief: str) -> str:
    """Style (with its no-people clause), the place, the negative clause."""

    from app.services.revue import plates as revue_plates
    from app.services.revue import policy

    style = revue_plates._art().PLATE_STYLE  # noqa: SLF001 - the owner's one style
    text = re.sub(r"\s+", " ", str(brief or "")).strip().rstrip(" .;,")
    return style + PLATE_TEMPLATE.format(brief=text) + policy.PLATE_NEGATIVE


def painted_url(db: Session | None, key: str) -> str | None:
    from app.services.revue import plates as revue_plates

    return revue_plates.painted_url(db, key)


def paint_plate(db: Session, key: str, brief: str, *, name_fr: str | None = None) -> str:
    """Paint ``key`` once from ``brief`` and return its URL; a painted key is never repainted.

    One image call (1536×1024, medium, about US$0.05). Raises :class:`SeasonPlateOff`
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
    image = revue_plates._call(prompt_for(brief)).convert("RGB")  # noqa: SLF001
    url = revue_plates._store(key.replace(":", "-"), revue_plates._webp(revue_plates.palette_lock(image)))  # noqa: SLF001
    db.add(
        RevuePlace(
            id=key,
            name_fr=(name_fr or key)[:200],
            brief=re.sub(r"\s+", " ", str(brief or "")).strip(),
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
    logger.info("season plates: painted {} ({})", key, PROMPT_VERSION)
    return url


def plate_url_for(
    db: Session | None,
    place_id: str | None,
    *,
    time_of_day: str | None = None,
    weather: str | None = None,
) -> str | None:
    """The best plate there is right now; never paints, never waits.

    The painted variant, else the painted base, else the static plate of
    ``season.world`` (which may be a borrowed one), else ``None``.
    """

    from app.services.season.world import plate_for

    if not place_id:
        return None
    if time_of_day or weather:
        hit = painted_url(db, plate_key(place_id, time_of_day=time_of_day, weather=weather))
        if hit:
            return hit
    return painted_url(db, plate_key(place_id)) or plate_for(place_id)
