"""La Carte (WP-120 §5): the learner's Papiers as pins on a map of France.

:func:`pins_for` is a pure read of the learner's **closed** ``revue_sessions`` (only
closed Papiers pin, owner decision §7.3). For each one it reads, from the session's
own JSON (never a model call):

* the place: ``plan.stage.place_id`` looked up in the dossier snapshot (the first
  ``choice{kind:"dossier"}`` event), its ``geo`` (WP-120 §3), or the gazetteer when a
  snapshot predates geo; a place without coordinates gives no pin (``counts.unplaced``);
* the card: the filed dispatch's headline (the ``closed`` event's ``closing``), the
  kept words, the learner's artifact (the last ``artifact`` event) and its spans, the
  kept question, the stage's plate;
* the vignette (phase B), when the ``revue_vignettes`` table exists: ring, kept mark and
  the dossier's pictogram. The vignette lead's modules are imported lazily and guarded.

``quartier`` is the season's «Mon quartier» layer: the ``SEASON_ONE_LOCATIONS`` the
learner has already lived a day in (``location_id`` of the scenario briefs of their
completed days, and their panels). ``counts`` per level use the drawings' bounds, the
same numbers ``web-frontend/public/assets/carte/carte-projection.json`` carries.

Cached per learner for :data:`CACHE_TTL_SECONDS` under :data:`CACHE_NAMESPACE`.
"""

from __future__ import annotations

from typing import Any

from loguru import logger
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.db.models.revue_session import RevueSession
from app.schemas.revue_carte import (
    CarteCounts,
    CartePin,
    CarteQuartierPlace,
    CarteView,
    CarteVignette,
)
from app.utils.cache import cache_backend

CACHE_NAMESPACE = "revue:carte"
CACHE_TTL_SECONDS = 60
MAX_PINS = 400

#: (lat_min, lat_max, lon_min, lon_max) of the Île-de-France and Paris drawings
#: (``scripts/geo/build_carte.py`` → ``carte-projection.json`` ``drawings.*.bounds``).
IDF_BOUNDS = (48.119, 49.243, 1.444, 3.561)
PARIS_BOUNDS = (48.814, 48.904, 2.222, 2.472)
#: Journey statuses whose day happened (``story_archive.LIVED_STATUSES``).
LIVED_STATUSES = ("completed", "ended_early")


def _inside(bounds: tuple[float, float, float, float], lat: float, lon: float) -> bool:
    lat_min, lat_max, lon_min, lon_max = bounds
    return lat_min <= lat <= lat_max and lon_min <= lon <= lon_max


def level_of(lat: float, lon: float) -> str:
    """The innermost drawing a point sits on."""

    if _inside(PARIS_BOUNDS, lat, lon):
        return "paris"
    if _inside(IDF_BOUNDS, lat, lon):
        return "idf"
    return "france"


# ---------------------------------------------------------------------------
# Reading one closed session
# ---------------------------------------------------------------------------


def _events(state: Any) -> list[dict[str, Any]]:
    events = (state or {}).get("events") if isinstance(state, dict) else None
    return [e for e in events or [] if isinstance(e, dict)]


def _payload(event: dict[str, Any]) -> dict[str, Any]:
    payload = event.get("payload")
    return payload if isinstance(payload, dict) else {}


def _snapshot(events: list[dict[str, Any]]) -> dict[str, Any]:
    for event in events:
        payload = _payload(event)
        if event.get("kind") == "choice" and payload.get("kind") == "dossier" and isinstance(payload.get("snapshot"), dict):
            return payload["snapshot"]
    return {}


def _closing(events: list[dict[str, Any]]) -> dict[str, Any]:
    closed = [e for e in events if e.get("kind") == "closed" and isinstance(_payload(e).get("closing"), dict)]
    return _payload(closed[-1])["closing"] if closed else {}


def _artifact(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    artifacts = [e for e in events if e.get("kind") == "artifact"]
    return _payload(artifacts[-1]) if artifacts else None


def _place_geo(place: dict[str, Any]) -> dict[str, Any] | None:
    geo = place.get("geo")
    if isinstance(geo, dict) and geo.get("lat") is not None and geo.get("lon") is not None:
        return geo
    # A snapshot taken before WP-120 §3 landed: ask the gazetteer (no model, no network).
    try:
        from app.services.revue.dossier import Place
        from app.services.revue.geo import resolve_place

        resolved = resolve_place(Place.model_validate({k: place[k] for k in ("id", "name_fr", "brief", "known") if k in place}))
    except Exception as exc:  # noqa: BLE001 - a malformed old snapshot simply gives no pin
        logger.debug("carte: no geo for {} ({})", place.get("id"), exc)
        return None
    return resolved.model_dump() if resolved is not None else None


def _place(plan: dict[str, Any], snapshot: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    places = [p for p in snapshot.get("places") or [] if isinstance(p, dict)]
    stage = plan.get("stage") if isinstance(plan.get("stage"), dict) else {}
    place_id = stage.get("place_id")
    ordered = [p for p in places if p.get("id") == place_id] + [p for p in places if p.get("id") != place_id]
    for place in ordered:
        geo = _place_geo(place)
        if geo is not None:
            return place, geo
    return (ordered[0] if ordered else None), None


def _kept_words(closing: dict[str, Any]) -> list[str]:
    kept = closing.get("kept") if isinstance(closing.get("kept"), dict) else {}
    words = [w for w in kept.get("words") or [] if isinstance(w, dict) and w.get("fr")]
    # The words the learner used first, then the rest, each once.
    ordered = [w for w in words if w.get("used")] + [w for w in words if not w.get("used")]
    return list(dict.fromkeys(str(w["fr"]) for w in ordered))


def _spans(raw: Any) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for span in raw or []:
        if isinstance(span, (list, tuple)) and len(span) == 2:
            try:
                spans.append((int(span[0]), int(span[1])))
            except (TypeError, ValueError):
                continue
    return spans


def _pin(row: RevueSession) -> CartePin | None:
    events = _events(row.state)
    snapshot = _snapshot(events)
    plan = row.plan if isinstance(row.plan, dict) else {}
    place, geo = _place(plan, snapshot)
    if geo is None:
        return None
    lat, lon = float(geo["lat"]), float(geo["lon"])
    closing = _closing(events)
    dispatch = closing.get("dispatch") if isinstance(closing.get("dispatch"), dict) else {}
    artifact = _artifact(events)
    stage = plan.get("stage") if isinstance(plan.get("stage"), dict) else {}
    headline = str(dispatch.get("headline_fr") or snapshot.get("title_fr") or row.dossier_id)
    precision = geo.get("precision") if geo.get("precision") in {"exact", "city", "region"} else "city"
    return CartePin(
        session_id=str(row.id),
        dossier_id=row.dossier_id,
        week=row.week,
        closed_at=row.closed_at.isoformat() if row.closed_at else None,
        place_label_fr=str(geo.get("label_fr") or (place or {}).get("name_fr") or ""),
        lat=lat,
        lon=lon,
        precision=precision,
        level=level_of(lat, lon),  # type: ignore[arg-type]
        headline_fr=headline,
        kept_words=_kept_words(closing),
        contribution_kind=str(artifact.get("kind")) if artifact and artifact.get("kind") else None,
        contribution_fr=str(artifact.get("text_fr")) if artifact and artifact.get("text_fr") else None,
        contribution_spans=_spans(artifact.get("contribution")) if artifact else [],
        question_fr=str(closing["question_kept_fr"]) if closing.get("question_kept_fr") else None,
        plate_url=str(stage["plate_url"]) if stage.get("plate_url") else None,
    )


# ---------------------------------------------------------------------------
# Vignettes (phase B), guarded
# ---------------------------------------------------------------------------


def _vignettes(db: Session, session_ids: list[Any], topics: dict[str, str | None]) -> dict[str, CarteVignette]:
    if not session_ids:
        return {}
    try:
        from app.db.models.revue_vignette import RevuePictogram, RevueVignette
    except ImportError:
        return {}
    try:
        if not inspect(db.get_bind()).has_table(RevueVignette.__tablename__):
            return {}
        rows = list(db.scalars(select(RevueVignette).where(RevueVignette.session_id.in_(session_ids))))
        dossier_ids = {row.dossier_id for row in rows}
        pictograms = (
            {p.dossier_id: p.svg for p in db.scalars(select(RevuePictogram).where(RevuePictogram.dossier_id.in_(dossier_ids)))}
            if dossier_ids and inspect(db.get_bind()).has_table(RevuePictogram.__tablename__)
            else {}
        )
    except Exception as exc:  # noqa: BLE001 - the map draws plain pins without its stamps
        logger.warning("carte: vignettes unavailable ({})", exc)
        return {}
    try:
        from app.services.revue.pictogram import fallback_svg
    except ImportError:  # pragma: no cover - phase B not present
        fallback_svg = None  # type: ignore[assignment]
    out: dict[str, CarteVignette] = {}
    for row in rows:
        svg = pictograms.get(row.dossier_id)
        if not svg and fallback_svg is not None:
            try:
                svg = fallback_svg(topics.get(str(row.session_id)))
            except Exception:  # noqa: BLE001
                svg = ""
        ring = row.ring if row.ring in {"headline", "question", "report"} else "headline"
        out[str(row.session_id)] = CarteVignette(ring=ring, kept_contribution=bool(row.kept_contribution), pictogram_svg=svg or "")  # type: ignore[arg-type]
    return out


# ---------------------------------------------------------------------------
# «Mon quartier»: season places already lived
# ---------------------------------------------------------------------------


def visited_season_places(db: Session, user_id: Any) -> list[str]:
    """Season location ids the learner has lived a day in, first visit first.

    Read from their completed days' scenario briefs (``private_task.scenario_brief``:
    the brief's ``location_id`` and each panel's), so a place the story has not reached
    yet never appears.
    """

    from app.db.models.daily_journey import DailyJourney, DailyJourneyStep

    rows = db.execute(
        select(DailyJourneyStep.private_task)
        .join(DailyJourney, DailyJourney.id == DailyJourneyStep.journey_id)
        .where(DailyJourney.user_id == user_id, DailyJourney.status.in_(LIVED_STATUSES))
        .order_by(DailyJourney.local_date.asc(), DailyJourney.created_at.asc(), DailyJourneyStep.ordinal.asc())
    ).all()
    seen: dict[str, None] = {}
    for (task,) in rows:
        brief = (task or {}).get("scenario_brief") if isinstance(task, dict) else None
        if not isinstance(brief, dict):
            continue
        ids = [brief.get("location_id")]
        ids += [p.get("location_id") for p in brief.get("panels") or [] if isinstance(p, dict)]
        for location_id in ids:
            if location_id:
                seen.setdefault(str(location_id), None)
    return list(seen)


def quartier_for(db: Session, user_id: Any) -> list[CarteQuartierPlace]:
    from app.services.season.world import SEASON_ONE_LOCATIONS, plate_for

    places: list[CarteQuartierPlace] = []
    for location_id in visited_season_places(db, user_id):
        row = SEASON_ONE_LOCATIONS.get(location_id)
        geo = (row or {}).get("geo")
        if not row or not isinstance(geo, dict):
            continue
        places.append(
            CarteQuartierPlace(
                id=location_id,
                name_fr=str(row["name_fr"]),
                label_fr=str(geo.get("label_fr") or row["name_fr"]),
                lat=float(geo["lat"]),
                lon=float(geo["lon"]),
                plate_url=plate_for(location_id),
            )
        )
    return places


# ---------------------------------------------------------------------------
# The view
# ---------------------------------------------------------------------------


def build_carte(db: Session, user_id: Any) -> CarteView:
    rows = list(
        db.scalars(
            select(RevueSession)
            .where(RevueSession.user_id == user_id, RevueSession.status == "closed")
            .order_by(RevueSession.closed_at.desc(), RevueSession.started_at.desc())
            .limit(MAX_PINS)
        )
    )
    pins: list[CartePin] = []
    unplaced = 0
    topics: dict[str, str | None] = {}
    for row in rows:
        topics[str(row.id)] = _snapshot(_events(row.state)).get("topic")
        pin = _pin(row)
        if pin is None:
            unplaced += 1
        else:
            pins.append(pin)
    stamps = _vignettes(db, [row.id for row in rows if str(row.id) in {p.session_id for p in pins}], topics)
    pins = [pin.model_copy(update={"vignette": stamps.get(pin.session_id)}) for pin in pins]
    try:
        quartier = quartier_for(db, user_id)
    except Exception as exc:  # noqa: BLE001 - the season layer is a quiet extra
        logger.warning("carte: quartier unavailable ({})", exc)
        quartier = []
    counts = CarteCounts(
        france=len(pins),
        idf=sum(1 for p in pins if p.level in {"idf", "paris"}),
        paris=sum(1 for p in pins if p.level == "paris"),
        unplaced=unplaced,
    )
    return CarteView(pins=pins, quartier=quartier, counts=counts)


def pins_for(db: Session, user: Any) -> CarteView:
    """The learner's map, cached for a minute."""

    key = str(user.id)
    cached = cache_backend.get(CACHE_NAMESPACE, key)
    if isinstance(cached, dict):
        try:
            return CarteView.model_validate(cached)
        except Exception as exc:  # noqa: BLE001 - a stale shape is rebuilt
            logger.debug("carte: cached view rebuilt ({})", exc)
    view = build_carte(db, user.id)
    cache_backend.set(CACHE_NAMESPACE, key, view.model_dump(mode="json"), CACHE_TTL_SECONDS)
    return view


def invalidate(user_id: Any) -> None:
    """Forget a learner's cached map (a Papier was just filed)."""

    cache_backend.invalidate(CACHE_NAMESPACE, key=str(user_id))
