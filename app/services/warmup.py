"""WP-153 · build the process-wide caches at start-up, not on a learner's request.

The first generated day of a fresh process used to pay for them: the spaCy lemma
pipeline behind lexical coverage (the largest part), the core lexicon and the
season files. On the 7-day walk five learners reached that day together and the
API went silent for 9–14 s. Every cache here is pure (files and model weights,
no database, no learner), so building it early changes nothing but when it is
paid. A cache that fails to build is logged and left to build lazily, as before.
"""
from __future__ import annotations

from collections.abc import Callable
from time import perf_counter
from typing import Any

from loguru import logger

from app.config import settings


def _season_caches(season_id: str) -> None:
    from app.services import season_lexicon
    from app.services.season.format import load_season

    load_season(season_id)
    season_lexicon.load(season_id)


def warm_caches() -> dict[str, float]:
    """Build the caches the first generated day reads; return seconds per cache."""

    from app.services.lexical_coverage import default_resolver, load_lexicon

    steps: list[tuple[str, Callable[[], Any]]] = [
        ("lemma_resolver", default_resolver),
        ("core_lexicon", load_lexicon),
    ]
    season_id = (settings.ATELIER_SEASON_SCRIPT or "").strip()
    if season_id:
        steps.append((f"season_{season_id}", lambda: _season_caches(season_id)))
    timings: dict[str, float] = {}
    for name, build in steps:
        started = perf_counter()
        try:
            build()
        except Exception as exc:  # noqa: BLE001 - a cache that fails here builds lazily, as before
            logger.warning("warm-up of {} failed ({}); it will build on first use", name, exc)
        timings[name] = round(perf_counter() - started, 3)
    logger.info("caches warmed: {}", timings)
    return timings


__all__ = ["warm_caches"]
