"""The feuilleton's view of an editorial dossier (WP-119 phase 5, §10b «Le feuilleton»).

The serial used to ask ``NewsService`` for a daily feuilleton seed, "today's top
cluster" as an untyped dict (§2). It now reads the same typed :class:`EditorialDossier`
La Revue uses, and this module adapts it to what the graphic-novel prompt and the
learner's source card already read:

- :func:`dossier_for_feuilleton` picks the week's dossier for a learner —
  ``weekly.available_for_week`` (live first, evergreens as fallback), ordered by the
  same topic-recency rule as La Revue's chooser.
- :func:`snapshot_for_prompt` turns a dossier into the ``source_snapshot`` dict the
  episode prompt, the cache key and ``source_usage`` read (the old seed's keys, pinned by
  :data:`PROMPT_SNAPSHOT_KEYS`), tagged ``learner_visible``.
- :func:`source_card` is the learner-facing card for that snapshot (title, trimmed
  summary, source, url) — exactly what ``graphic_novel.learner_facing_source`` shows.
- :func:`thread_seed` is the JSON kept on ``SerialThread.news_seed`` (column unchanged):
  the prompt snapshot plus the full dossier under ``"dossier"``.

The ranking rule is **copied** from ``revue.encounter`` (``EncounterService.ranked`` /
``_topic_last_seen`` / ``_interest_score`` / ``INTEREST_TOPICS`` / ``current_week``), not
imported: encounter is a 2 500-line module owned by another lead, and the feuilleton only
needs the small rule. Keep the two in step when the Revue's rule changes. The interest
term is the topic-word part of the Revue's score only (no title/summary word overlap).
"""

from __future__ import annotations

import unicodedata
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.services.revue.dossier import Claim, EditorialDossier, Source
from app.services.revue.evergreen import evergreens_for_week

PARIS = ZoneInfo("Europe/Paris")
SNAPSHOT_MODE = "revue_dossier"

#: The keys of the old ``feuilleton_daily_seed`` payload that the graphic-novel seam reads
#: (``_source_prompt``, ``_cache_key``, ``source_usage``, ``learner_facing_source``).
LEGACY_SEED_KEYS = frozenset(
    {
        "mode",
        "date",
        "seed_version",
        "title",
        "title_fr",
        "summary",
        "summary_fr",
        "source",
        "url",
        "items",
        "named_people",
        "digest",
        "source_policy",
    }
)
#: Every key :func:`snapshot_for_prompt` returns: the legacy ones, the source-card tag, and
#: the dossier's identity.
PROMPT_SNAPSHOT_KEYS = LEGACY_SEED_KEYS | {"learner_visible", "dossier_id", "week", "topic", "evergreen"}
#: Keys of an item in ``items`` (the first is the story, the others its facts).
ITEM_KEYS = frozenset({"title", "summary", "source", "source_id", "url", "published_at"})
#: Keys of the learner-facing card (empty values are dropped, as in ``learner_facing_source``).
SOURCE_CARD_KEYS = frozenset({"title", "summary", "source", "url"})

# -- copied from revue.encounter (see the module docstring) ---------------------------

#: Interest words (``users.interests``, comma-separated, any of en/fr/de) → topics.
INTEREST_TOPICS: dict[str, tuple[str, ...]] = {
    "food": ("food", "cooking", "cuisine", "gastronomie", "kochen", "essen", "vin", "wine", "wein", "restaurant"),
    "culture": ("culture", "kultur", "music", "musique", "musik", "art", "kunst", "cinema", "film", "books", "livres", "history", "histoire"),
    "city": ("city", "ville", "stadt", "shopping", "mode", "fashion", "travel", "voyage", "reisen"),
    "sport": ("sport", "sports", "cyclisme", "cycling", "football", "fussball", "velo"),
    "nature": ("nature", "natur", "environment", "environnement", "climat", "climate", "umwelt", "hiking"),
    "work": ("work", "travail", "arbeit", "business", "economy", "economie", "tech", "career"),
    "politics": ("politics", "politique", "politik", "news", "actualite"),
}


def current_week(now: datetime | None = None) -> str:
    """The ISO week in Paris, ``"2026-W40"`` (same as ``encounter.current_week``)."""

    local = (now or datetime.now(UTC)).astimezone(PARIS)
    year, number, _ = local.isocalendar()
    return f"{year}-W{number:02d}"


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(c for c in decomposed if not unicodedata.combining(c)).replace("’", "'").lower()


def _interests(user: Any) -> list[str]:
    return [part.strip().lower() for part in str(getattr(user, "interests", "") or "").split(",") if part.strip()]


def _interest_score(dossier: EditorialDossier, interests: list[str]) -> int:
    if not interests:
        return 0
    folded = {_fold(item) for item in interests}
    return 2 * sum(1 for word in INTEREST_TOPICS.get(dossier.topic, ()) if word in folded)


def topic_last_seen(db: Session | None, user: Any) -> dict[str, float]:
    """Topic → timestamp of the learner's latest closed Revue session on it (encounter's rule)."""

    if db is None or getattr(user, "id", None) is None:
        return {}
    from app.db.models.revue_session import RevueSession

    rows = db.scalars(
        select(RevueSession)
        .where(RevueSession.user_id == user.id, RevueSession.status == "closed")
        .order_by(RevueSession.started_at.desc())
        .limit(60)
    )
    seen: dict[str, float] = {}
    for row in rows:
        topic = None
        for event in (row.state or {}).get("events") or []:
            payload = event.get("payload") or {}
            if event.get("kind") == "choice" and payload.get("kind") == "dossier":
                topic = (payload.get("snapshot") or {}).get("topic")
                break
        stamp = row.closed_at or row.started_at
        if topic and stamp is not None:
            ts = (stamp if stamp.tzinfo else stamp.replace(tzinfo=UTC)).timestamp()
            seen[topic] = max(seen.get(topic, 0.0), ts)
    return seen


def rank(dossiers: list[EditorialDossier], *, last_seen: dict[str, float], interests: list[str]) -> list[EditorialDossier]:
    """Least-recently-seen topic first, then interests, then the provider's order."""

    keyed = [
        ((last_seen.get(d.topic, 0.0), -_interest_score(d, interests), index), d)
        for index, d in enumerate(dossiers)
    ]
    keyed.sort(key=lambda pair: pair[0])
    return [d for _, d in keyed]


# -- choosing --------------------------------------------------------------------------


def available_dossiers(week: str) -> list[EditorialDossier]:
    """``weekly.available_for_week`` (live first, evergreens to fill); evergreens if it fails."""

    try:
        from app.services.revue.weekly import available_for_week

        dossiers = list(available_for_week(week))
        if dossiers:
            return dossiers
    except Exception as exc:  # noqa: BLE001 - a malformed weekly file must not stop the edition
        logger.bind(week=week).warning("feuilleton: weekly dossiers unavailable ({}); evergreens only", exc)
    return evergreens_for_week(week)


def dossier_for_feuilleton(user: Any, week: str | None = None, *, db: Session | None = None) -> EditorialDossier | None:
    """The week's dossier for this learner's feuilleton edition, or ``None`` when there is none."""

    week = week or current_week()
    dossiers = available_dossiers(week)
    if not dossiers:
        return None
    try:
        last_seen = topic_last_seen(db, user)
    except Exception as exc:  # noqa: BLE001 - recency is a preference, not a requirement
        logger.bind(week=week).warning("feuilleton: topic recency unavailable ({})", exc)
        last_seen = {}
    return rank(dossiers, last_seen=last_seen, interests=_interests(user))[0]


# -- adapting --------------------------------------------------------------------------


def _lead_source(dossier: EditorialDossier) -> Source:
    facts = dossier.facts()
    if facts:
        source = dossier.source_by_id(facts[0].source_id)
        if source is not None:
            return source
    return dossier.sources[0]


def _claim_item(dossier: EditorialDossier, claim: Claim) -> dict[str, str]:
    source = dossier.source_by_id(claim.source_id)
    return {
        "title": claim.fr,
        "summary": claim.quote,
        "source": source.name if source else claim.source_id,
        "source_id": claim.source_id,
        "url": claim.url,
        "published_at": claim.published_at.isoformat(),
    }


def _digest(dossier: EditorialDossier, lead: Source) -> str:
    names = {source.id: source.name for source in dossier.sources}
    lines = [
        "Sujet de la semaine:",
        f"- {dossier.title_fr} ({lead.name})",
        f"Résumé: {dossier.summary_fr}",
    ]
    if dossier.facts():
        lines.append("Faits (sourcés):")
        lines.extend(f"- {c.fr} ({names.get(c.source_id, c.source_id)})" for c in dossier.facts())
    readings = [*dossier.interpretations(), *dossier.forecasts()]
    if readings:
        lines.append("Lectures attribuées (pas des faits):")
        lines.extend(f"- {c.fr} — {c.attributed_to}" for c in readings)
    if dossier.uncertainties:
        lines.append("Ce que les sources ne disent pas:")
        lines.extend(f"- {text}" for text in dossier.uncertainties)
    return "\n".join(lines)


def snapshot_for_prompt(dossier: EditorialDossier) -> dict[str, Any]:
    """The ``source_snapshot`` dict the episode prompt reads (keys: :data:`PROMPT_SNAPSHOT_KEYS`)."""

    lead = _lead_source(dossier)
    story_item = {
        "title": dossier.title_fr,
        "summary": dossier.summary_fr,
        "source": lead.name,
        "source_id": lead.id,
        "url": lead.url,
        "published_at": lead.published_at.isoformat(),
    }
    kind = "evergreen" if dossier.evergreen else "weekly"
    return {
        "mode": SNAPSHOT_MODE,
        "date": dossier.time_scope.start.isoformat(),
        "seed_version": dossier.dossier_version,
        "dossier_id": dossier.id,
        "week": dossier.week,
        "topic": dossier.topic,
        "evergreen": dossier.evergreen,
        "title": dossier.title_fr,
        "title_fr": dossier.title_fr,
        "summary": dossier.summary_fr,
        "summary_fr": dossier.summary_fr,
        "source": lead.name,
        "url": lead.url,
        "items": [story_item, *(_claim_item(dossier, claim) for claim in dossier.facts()[:3])],
        "named_people": dossier.person_names(),
        "digest": _digest(dossier, lead),
        "source_policy": (
            f"Editorial dossier ({kind}, {dossier.dossier_version}): typed claims with verbatim quotes "
            "from dated sources; interpretations and forecasts are attributed, never told as facts."
        ),
        "learner_visible": True,
    }


def source_card(dossier: EditorialDossier) -> dict[str, Any]:
    """The learner-facing source card: title, trimmed summary, source, url."""

    # Lazy: graphic_novel imports this module.
    from app.services.graphic_novel import learner_facing_source

    return learner_facing_source(snapshot_for_prompt(dossier))


def thread_seed(dossier: EditorialDossier) -> dict[str, Any]:
    """What ``SerialThread.news_seed`` keeps: the prompt snapshot (no card tag) plus the dossier."""

    seed = {key: value for key, value in snapshot_for_prompt(dossier).items() if key != "learner_visible"}
    seed["dossier"] = dossier.model_dump(mode="json")
    return seed

