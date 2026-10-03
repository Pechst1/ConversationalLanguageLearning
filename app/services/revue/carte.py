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
    CarteReview,
    CarteReviewGrade,
    CarteReviewItem,
    CarteReviewResult,
    CarteReviewWord,
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
        place_id=str(place["id"]) if place and place.get("id") else None,
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
            return decorate(db, user.id, CarteView.model_validate(cached))
        except Exception as exc:  # noqa: BLE001 - a stale shape is rebuilt
            logger.debug("carte: cached view rebuilt ({})", exc)
    view = build_carte(db, user.id)
    cache_backend.set(CACHE_NAMESPACE, key, view.model_dump(mode="json"), CACHE_TTL_SECONDS)
    # WP-121: the due dots and the Relecture marks are read fresh, outside the cache.
    return decorate(db, user.id, view)


def invalidate(user_id: Any) -> None:
    """Forget a learner's cached map (a Papier was just filed)."""

    cache_backend.invalidate(CACHE_NAMESPACE, key=str(user_id))


# ===========================================================================
# WP-121 · Le Palais de mémoire
# ===========================================================================
#
# A.0 ``keep_papier_words``: every word a Papier kept enters the SRS at close, tied to
# the Papier's place (``kept_words.keep_revue_word``). A.2 ``decorate``: due counts per
# pin, outside the minute cache (a review must clear its dot at once). A.3
# ``review_for`` / ``grade_review``: the due words of one place, posed with the journey's
# recall formats (match_pairs · word_bank · unscramble · dictation) and graded through
# the evidence policy (``app.core.srs.memory``) and ``EnhancedSRSService``. No model call.

#: A.3: four words or more are matched in a grid; fewer are rebuilt one by one.
MATCH_MIN_WORDS = 4
#: The words of a matching grid (the journey's grid is four pairs).
MATCH_SIZE = 4
#: The longest piece of the claim a word bank asks the learner to rebuild.
CHUNK_WORDS = 6
#: The evidence each review format proves (``app.core.srs.memory.FORMAT_BY_NAME`` names).
REVIEW_EVIDENCE = {"match_pairs": "recognise", "word_bank": "word_bank", "unscramble": "tiles", "dictation": "transform"}
ROMY = "romy_tremblay"


def _period_week(period: str) -> str:
    try:
        from app.services.revue.weekly import week_of_period

        return week_of_period(period)
    except Exception:  # noqa: BLE001 - a malformed period keeps its own label
        return str(period or "")


def keep_papier_words(db: Session, row: RevueSession, *, dossier: Any, plan: Any, state: Any, kept: Any) -> int:
    """A.0: ``RvKept.words[]`` → the learner's SRS (``kept_words.keep_revue_word``).

    ``met`` = the claim's French, ``source="revue"``, the session, the dossier, the place
    (id and label) and the ISO week. A word the learner used (``used``) and the rubric
    judged ``correct`` in one of the turns' evidence starts one SRS step ahead.
    Idempotent per session. Never raises: a close is never lost to the palace (the
    writes run in a savepoint that rolls back alone). Returns the words kept.
    """

    from app.db.models.user import User
    from app.services.kept_words import keep_revue_word

    try:
        user = db.get(User, row.user_id)
        if user is None or not getattr(kept, "words", None):
            return 0
        place = next((p for p in dossier.places if p.id == plan.stage.place_id), dossier.places[0])
        geo = getattr(place, "geo", None)
        claims = dossier.claims_by_id()
        correct: set[str] = set()
        for event in state.events:
            if event.kind != "evidence":
                continue
            for outcome in event.payload.get("word_outcomes") or []:
                if isinstance(outcome, dict) and outcome.get("outcome") == "correct" and outcome.get("fr"):
                    correct.add(str(outcome["fr"]))
        met_base = {
            "source": "revue",
            "session_id": str(row.id),
            "dossier_id": str(row.dossier_id),
            "place_id": str(place.id),
            "place_label_fr": str(getattr(geo, "label_fr", None) or place.name_fr),
            "place_name_fr": str(place.name_fr),
            "week": _period_week(row.week),
        }
        count = 0
        with db.begin_nested():
            for word in kept.words:
                claim = claims.get(word.claim_id)
                result = keep_revue_word(
                    db,
                    user=user,
                    term=word.fr,
                    gloss=word.gloss,
                    sentence=claim.fr if claim is not None else word.fr,
                    met=met_base,
                    used_correctly=bool(word.used) and word.fr in correct,
                )
                count += result is not None
        return count
    except Exception as exc:  # noqa: BLE001 - the palace is an extra; the close stands
        logger.warning("revue: kept words not filed in the SRS ({})", exc)
        return 0


# ---------------------------------------------------------------------------
# A.2 · due counts on the pins (and the Relecture mark, phase B)
# ---------------------------------------------------------------------------


def decorate(db: Session, user_id: Any, view: CarteView, *, now: Any = None) -> CarteView:
    """The cached map plus what changes by the minute: ``due_words`` per pin, ``due_total``
    and each pin's Relecture mark. A place's due words sit on its most recent pin only,
    so clusters and the total never count a word twice."""

    from app.services.kept_words import words_due_by_place

    try:
        due = words_due_by_place(db, user_id=user_id, now=now)
    except Exception as exc:  # noqa: BLE001 - the map draws without its dots
        logger.warning("carte: due words unavailable ({})", exc)
        due = {}
    try:
        from app.services.revue.relecture import marks_for

        marks = marks_for(db, user_id, now=now)
    except Exception as exc:  # noqa: BLE001 - the table may not exist yet
        logger.debug("carte: relecture marks unavailable ({})", exc)
        marks = {}
    latest: dict[str, str] = {}
    for pin in view.pins:  # newest first (build_carte's order)
        if pin.place_id and pin.place_id not in latest:
            latest[pin.place_id] = pin.session_id
    pins = []
    for pin in view.pins:
        count = len(due.get(pin.place_id or "", [])) if latest.get(pin.place_id or "") == pin.session_id else 0
        pins.append(pin.model_copy(update={"due_words": count, "relecture": marks.get(pin.session_id)}))
    total = sum(len(words) for place_id, words in due.items() if place_id in latest)
    return view.model_copy(update={"pins": pins, "due_total": total})


# ---------------------------------------------------------------------------
# A.3 · reviewing «ici»
# ---------------------------------------------------------------------------


def _opaque(*parts: Any) -> str:
    import hashlib

    return "o" + hashlib.sha256(":".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:10]


def _fold_word(text: str) -> str:
    import unicodedata

    decomposed = unicodedata.normalize("NFKD", str(text or "").replace("’", "'"))
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower().strip(".,;:!?«»\"()")


def _chunk(sentence: str, word: str) -> list[str]:
    """The piece of the claim around the word (≤ ``CHUNK_WORDS`` tokens), punctuation off its ends."""

    from app.services.kept_words import _bare_term

    tokens = [t for t in str(sentence or "").split() if t.strip(".,;:!?«»\"()")]
    bare = _fold_word(_bare_term(word)).split()
    stem = bare[0][: max(3, len(bare[0]) - 2)] if bare else ""
    index = next((i for i, token in enumerate(tokens) if stem and stem in _fold_word(token)), None)
    if index is None:
        tokens, index = str(word).split(), 0
    start = max(0, min(index - 2, len(tokens) - CHUNK_WORDS))
    piece = tokens[start: start + CHUNK_WORDS]
    return [t.strip(".,;:!?«»\"()") or t for t in piece]


def _line_for(state_json: Any, word: str) -> tuple[str, str]:
    """The thread line that carried the word (``(speaker_id, text_fr)``), Romy's or a guest's."""

    from app.services.revue.encounter import _contains_word

    for event in _events(state_json):
        kind, payload = event.get("kind"), _payload(event)
        text = str(payload.get("text_fr") or "")
        if kind == "turn_romy" and text and _contains_word(text, word):
            return ROMY, text
        if kind == "turn_guest" and text and payload.get("id") and _contains_word(text, word):
            return str(payload["id"]), text
    return ROMY, ""


def _distractor(plan: dict[str, Any], word: str) -> str | None:
    from app.services.kept_words import _bare_term

    for item in sorted((v for v in plan.get("vocabulary") or [] if isinstance(v, dict)), key=lambda v: str(v.get("fr"))):
        fr = str(item.get("fr") or "")
        if fr and _fold_word(fr) != _fold_word(word):
            return _bare_term(fr).split()[0]
    return None


def _shuffled(ids_texts: list[tuple[str, str]]) -> list[tuple[str, str]]:
    # The opaque ids are hashes: ordering by them is a stable shuffle.
    return sorted(ids_texts, key=lambda pair: pair[0])


def _items_for(user_id: Any, words: list[dict[str, Any]], sessions: dict[str, RevueSession]) -> list[dict[str, Any]]:
    """The review's items: a matching grid per four words, then one rebuild per word left
    (a word bank with one spare chip, an unscramble when no spare exists, a dictation
    when the word's line has a clip)."""

    from app.services.journey_answer_key import answer_key_for

    items: list[dict[str, Any]] = []
    rest = list(words)
    while len(rest) >= MATCH_MIN_WORDS:
        group, rest = rest[:MATCH_SIZE], rest[MATCH_SIZE:]
        item_id = "m:" + ",".join(w["progress_id"] for w in group)
        fr = [(_opaque(user_id, item_id, "f", w["progress_id"]), w["word"]) for w in group]
        native = [(_opaque(user_id, item_id, "n", w["progress_id"]), w["gloss"] or w["word"]) for w in group]
        order = [part for f, n in zip(fr, native, strict=True) for part in (f[0], n[0])]
        items.append({
            "id": item_id,
            "task_type": "match_pairs",
            "progress_ids": [w["progress_id"] for w in group],
            "prompt_fr": None,
            "options": [{"id": i, "text_fr": t, "side": "fr"} for i, t in _shuffled(fr)]
            + [{"id": i, "text_fr": t, "side": "native"} for i, t in _shuffled(native)],
            "answer_key": answer_key_for(item_id, {"task_type": "match_pairs", "correct_tile_order": order}),
            "audio_url": None,
            "_order": order,
        })
    for word in rest:
        if word.get("audio_url"):
            item_id = "d:" + word["progress_id"]
            items.append({"id": item_id, "task_type": "dictation", "progress_ids": [word["progress_id"]],
                          "prompt_fr": None, "options": [], "answer_key": None, "audio_url": word["audio_url"],
                          "_answer": word["line_fr"] or word["sentence_fr"]})
            continue
        session = sessions.get(word["session_id"])
        spare = _distractor(session.plan if session is not None and isinstance(session.plan, dict) else {}, word["word"])
        chunk = _chunk(word["sentence_fr"], word["word"])
        task = "word_bank" if spare and _fold_word(spare) not in {_fold_word(t) for t in chunk} else "unscramble"
        item_id = ("w:" if task == "word_bank" else "u:") + word["progress_id"]
        tiles = [(_opaque(user_id, item_id, index, text), text) for index, text in enumerate(chunk)]
        bank = tiles + ([(_opaque(user_id, item_id, "spare", spare), spare)] if task == "word_bank" and spare else [])
        order = [tile_id for tile_id, _ in tiles]
        items.append({
            "id": item_id,
            "task_type": task,
            "progress_ids": [word["progress_id"]],
            "prompt_fr": None,
            "options": [{"id": i, "text_fr": t, "side": None} for i, t in _shuffled(bank)],
            "answer_key": answer_key_for(item_id, {"task_type": task, "correct_tile_order": order}),
            "audio_url": None,
            "_answer_texts": chunk,
            "_bank": dict(bank),
        })
    return items


def _review_words(db: Session, user_id: Any, place_id: str, *, now: Any = None) -> tuple[list[dict[str, Any]], dict[str, RevueSession]]:
    from app.services.kept_words import words_due_by_place

    due = words_due_by_place(db, user_id=user_id, now=now).get(place_id, [])
    session_ids = {w.session_id for w in due if w.session_id}
    sessions: dict[str, RevueSession] = {}
    if session_ids:
        import uuid as _uuid

        keys = []
        for sid in session_ids:
            try:
                keys.append(_uuid.UUID(sid))
            except ValueError:
                continue
        for session in db.scalars(select(RevueSession).where(RevueSession.user_id == user_id, RevueSession.id.in_(keys))):
            sessions[str(session.id)] = session
    words = []
    for w in due:
        session = sessions.get(w.session_id)
        speaker, line = _line_for(session.state if session is not None else None, w.word)
        words.append({
            "progress_id": w.progress_id,
            "word_id": w.word_id,
            "word": w.word,
            "gloss": w.gloss,
            "sentence_fr": w.sentence_fr,
            "session_id": w.session_id,
            "week": w.week,
            "place_label_fr": w.place_label_fr,
            "speaker_id": speaker,
            "line_fr": line or w.sentence_fr,
            "audio_url": None,
        })
    return words, sessions


def review_for(db: Session, user: Any, place_id: str, *, now: Any = None) -> CarteReview:
    """The due words of one place with what carried them, and the items to pose."""

    from app.services.revue.knowledge import cast_name

    words, sessions = _review_words(db, user.id, place_id, now=now)
    latest = max(sessions.values(), key=lambda s: (s.closed_at or s.started_at), default=None)
    plan = latest.plan if latest is not None and isinstance(latest.plan, dict) else {}
    stage = plan.get("stage") if isinstance(plan.get("stage"), dict) else {}
    closing = _closing(_events(latest.state)) if latest is not None else {}
    dispatch = closing.get("dispatch") if isinstance(closing.get("dispatch"), dict) else {}
    items = _items_for(user.id, words, sessions)
    return CarteReview(
        place_id=place_id,
        place_label_fr=words[0]["place_label_fr"] if words else "",
        plate_url=str(stage["plate_url"]) if stage.get("plate_url") else None,
        week=words[0]["week"] if words else (latest.week if latest is not None else ""),
        headline_fr=str(dispatch.get("headline_fr") or "") or None,
        words=[
            CarteReviewWord(
                progress_id=w["progress_id"], word_id=w["word_id"], word=w["word"], gloss=w["gloss"],
                sentence_fr=w["sentence_fr"], speaker_id=w["speaker_id"], speaker_name=cast_name(w["speaker_id"]),
                line_fr=w["line_fr"], session_id=w["session_id"], week=w["week"],
            )
            for w in words
        ],
        items=[CarteReviewItem(**{k: v for k, v in item.items() if not k.startswith("_")}) for item in items],
    )


class ReviewError(Exception):
    def __init__(self, status: int, code: str) -> None:
        super().__init__(code)
        self.status = status
        self.code = code


def _match_outcomes(order: list[str], pairs: list[str], progress_ids: list[str]) -> dict[str, bool]:
    """Per word: was the *first* pairing that touched its French card the right one."""

    right = {order[i]: order[i + 1] for i in range(0, len(order), 2)}
    by_fr = {order[2 * k]: pid for k, pid in enumerate(progress_ids)}
    outcome: dict[str, bool] = {}
    for i in range(0, len(pairs) - 1, 2):
        fr, native = pairs[i], pairs[i + 1]
        if fr in by_fr and by_fr[fr] not in outcome:
            outcome[by_fr[fr]] = right.get(fr) == native
    return {pid: outcome.get(pid, False) for pid in progress_ids}


def _same_line(said: str, answer: str) -> bool:
    fold = lambda text: [w for w in (_fold_word(t) for t in str(text or "").split()) if w]  # noqa: E731
    return bool(fold(said)) and fold(said) == fold(answer)


def grade_review(
    db: Session,
    user: Any,
    place_id: str,
    *,
    item_id: str,
    tile_ids: list[str] | None = None,
    text: str | None = None,
    assisted: bool = False,
    now: Any = None,
) -> CarteReviewGrade:
    """Grade one posed item and schedule its words through the existing SRS.

    The item is rebuilt from its id (the same deterministic builder as the GET), so the
    learner's answer is checked on the server, never trusted. Each word's evidence
    (``Evidence(format, correct, assisted)``) is mapped by ``grade_evidence`` to a rating
    and ``EnhancedSRSService.process_review`` moves its card.
    """

    from datetime import UTC, datetime

    from app.core.srs.memory import Evidence, format_for_name, grade_evidence
    from app.db.models.progress import UserVocabularyProgress
    from app.services.enhanced_srs import EnhancedSRSService

    now = now or datetime.now(UTC)
    words, sessions = _review_words(db, user.id, place_id, now=now)
    wanted = item_id.split(":", 1)[1].split(",") if ":" in item_id else []
    chosen = [w for pid in wanted for w in words if w["progress_id"] == pid]
    if not chosen or len(chosen) != len(wanted):
        raise ReviewError(409, "carte_review_item_not_due")
    item = next((i for i in _items_for(user.id, chosen, sessions) if i["id"] == item_id), None)
    if item is None:
        raise ReviewError(409, "carte_review_item_not_due")

    task = item["task_type"]
    if task == "match_pairs":
        correct = _match_outcomes(item["_order"], [str(t) for t in tile_ids or []], item["progress_ids"])
    elif task in {"word_bank", "unscramble"}:
        bank = item["_bank"]
        said = [bank.get(str(t), "") for t in tile_ids or []]
        ok = [_fold_word(t) for t in said] == [_fold_word(t) for t in item["_answer_texts"]]
        correct = {item["progress_ids"][0]: ok}
    else:
        correct = {item["progress_ids"][0]: _same_line(text or "", item["_answer"])}

    evidence_format = format_for_name(REVIEW_EVIDENCE.get(task))
    service = EnhancedSRSService(db)
    results: list[CarteReviewResult] = []
    for pid in item["progress_ids"]:
        import uuid as _uuid

        progress = db.get(UserVocabularyProgress, _uuid.UUID(pid))
        if progress is None or progress.user_id != user.id:
            continue
        grade = grade_evidence(Evidence(evidence_format, correct=correct[pid], assisted=assisted))
        if grade is None:
            continue
        service.process_review(progress, int(grade.rating), now=now, source="carte", review_format=task)
        due_at = progress.due_at or progress.next_review_date
        results.append(CarteReviewResult(
            progress_id=pid, word_id=int(progress.word_id), correct=correct[pid], rating=int(grade.rating),
            due_at=due_at.isoformat() if due_at else None,
        ))
    db.flush()
    remaining = len(_review_words(db, user.id, place_id, now=now)[0])
    return CarteReviewGrade(item_id=item_id, task_type=task, results=results, remaining=remaining)
