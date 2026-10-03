"""The weekly intake: RSS → candidates → clusters → the week's sourced stories (WP-119 §4.1).

Runs on Monday 05:00 Europe/Paris (``app/tasks/revue.py``) and on demand with
``refresh=True`` (``POST /api/v1/admin/revue/refresh``). One run, for one *period*:

1. **Candidates.** Every feed of ``NewsService.FRANCE_SOURCE_REGISTRY`` (now with culture,
   gastronomy and sport feeds and a ``fetch_policy`` per source), fetched once and parsed
   by ``NewsService._parse_rss_items`` (reused, not copied; the publication date is read
   from the same XML, which that parser does not keep). French only
   (``_looks_like_language``), deduplicated (``_dedupe_items``), the sensitive first
   filter (``policy.is_sensitive``, §4.1) and nothing older than the week's window.
2. **Clusters.** Items about the same thing share ``NewsService._feuilleton_cluster_key``
   (the first named person, else three salient words). A cluster is ranked by
   **recency, cluster size (distinct outlets) and topic spread** — the feuilleton's taste
   (+2 politics, +2 names) stays out of the intake.
3. **Spread.** :data:`TOPIC_SPREAD` deals the target (``REVUE_STORIES_PER_WEEK``, six):
   two food or culture, two city or society, one sport or nature, one politics; a slot a
   group cannot fill goes to the best remaining cluster of any topic.
4. **Build.** For each chosen story the article pages are fetched (``sources.py``: robots,
   one attempt, six seconds) and the builder makes and checks one dossier (``builder.py``).
   A rejected story gives its place to the next candidate of the same group, then of any
   group.
5. **Top-up.** A thin week is filled with that week's evergreens (§4.3) up to the target.
6. **Persist.** One ``revue_dossiers`` row per dossier for the period (built ones carry
   their source hashes; top-ups carry ``checks.evergreen_top_up``). ``weekly.load_week``
   reads these rows before the hand-authored files. An existing period is kept unless
   ``refresh=True``.

:func:`dossiers_for` is the bridge §11 promises a season gap day.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any

import httpx
from loguru import logger
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.services.revue import policy
from app.services.revue.builder import (
    BUILDER_VERSION,
    BuildResult,
    DossierProvider,
    SourceItem,
    StoryInput,
    build_dossier,
)
from app.services.revue.dossier import EditorialDossier, week_bounds
from app.services.revue.evergreen import evergreens_for_week
from app.services.revue.sources import RobotsCache, fetch_article
from app.services.revue.weekly import is_daily_period, week_of_period

#: The target spread of a week (§4.1): (topics, slots) per group, in dealing order.
TOPIC_SPREAD: tuple[tuple[tuple[str, ...], int], ...] = (
    (("food", "culture"), 2),
    (("city", "work"), 2),
    (("sport", "nature"), 1),
    (("politics",), 1),
)
#: Items per feed read per run.
ITEMS_PER_FEED = 25
#: A feed gets this long, once.
FEED_TIMEOUT_SECONDS = 8.0
#: How far before the period's start an item may be published and still be "this week".
MAX_ITEM_AGE_DAYS = 10

#: Topic words, accent-folded, matched on title + summary (a trailing ``*`` is a prefix).
TOPIC_WORDS: dict[str, tuple[str, ...]] = {
    "food": ("cuisine*", "restaurant*", "chef*", "gastronom*", "vin", "vins", "vendange*", "fromage*", "pain",
             "boulanger*", "marche*", "recette*", "alimentation", "alimentaire*", "repas", "cafe*", "bistrot*"),
    "culture": ("musee*", "exposition*", "festival*", "cinema", "film*", "livre*", "roman*", "theatre*",
                "concert*", "musique*", "artiste*", "prix goncourt", "goncourt", "patrimoine", "opera"),
    "city": ("paris", "mairie", "ville*", "quartier*", "metro", "transport*", "velo*", "logement*", "loyer*",
             "rue*", "habitant*", "urbanisme"),
    "work": ("greve*", "salari*", "emploi*", "chomage", "syndicat*", "travail*", "entreprise*", "retraite*"),
    "sport": ("football", "rugby", "tennis", "match*", "tour de france", "championnat*", "olympi*", "course",
              "stade*", "equipe*", "athlet*", "cyclis*", "hippique", "arc de triomphe"),
    "nature": ("climat*", "meteo", "canicule*", "foret*", "environnement", "biodiversite", "pluie*", "secheresse",
               "jardin*", "animal*", "animaux", "parc*"),
    "politics": ("gouvernement", "ministre*", "assemblee", "senat", "depute*", "budget*", "election*", "president*",
                 "loi", "lois", "reforme*", "premier ministre", "parlement*", "elysee"),
}
#: Registry ``topic_tags`` that are not policy topics, mapped onto one.
_TAG_TOPIC = {"society": "city", "daily_life": "city", "gastronomy": "food", "sports": "sport"}

_WORD = re.compile(r"[a-z0-9]+")


def _fold(text: str) -> str:
    import unicodedata

    return unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode("ascii").lower()


def _news() -> Any:
    """A ``NewsService`` for its parsing helpers only: no HTTP client is opened."""

    from app.services.news_service import NewsService

    return object.__new__(NewsService)


def registry() -> list[dict[str, Any]]:
    from app.services.news_service import NewsService

    return [dict(row) for row in NewsService.FRANCE_SOURCE_REGISTRY]


# ---------------------------------------------------------------------------
# Candidates
# ---------------------------------------------------------------------------


@dataclass
class Candidate:
    """One French RSS item that passed the first filters."""

    source_id: str
    source_name: str
    title: str
    url: str
    summary: str
    published_at: date
    topic: str
    fetch_policy: str
    cluster_key: str = ""


@dataclass
class Story:
    key: str
    topic: str
    items: list[Candidate]
    score: tuple[Any, ...] = ()

    @property
    def outlets(self) -> int:
        return len({item.source_name for item in self.items})

    @property
    def newest(self) -> date:
        return max(item.published_at for item in self.items)


def _matches(word: str, folded: str, tokens: set[str]) -> bool:
    if " " in word:
        return word in folded
    if word.endswith("*"):
        stem = word[:-1]
        return any(token.startswith(stem) for token in tokens)
    return word in tokens


def topic_for(text: str, tags: Iterable[str] = ()) -> str:
    """The policy topic a story's text speaks to most; the feed's tags break ties."""

    folded = _fold(text)
    tokens = set(_WORD.findall(folded))
    scores = {topic: sum(1 for word in words if _matches(word, folded, tokens)) for topic, words in TOPIC_WORDS.items()}
    mapped = [_TAG_TOPIC.get(tag, tag) for tag in tags]
    for rank, tag in enumerate(mapped):
        if tag in scores:
            scores[tag] += 0.5 / (rank + 1)
    best = max(scores.items(), key=lambda pair: (pair[1], -policy.TOPICS.index(pair[0])))
    if best[1] > 0:
        return best[0]
    return next((tag for tag in mapped if tag in policy.TOPICS), "city")


def _pub_dates(xml_text: str) -> dict[str, date]:
    """``link`` → publication date, from the same RSS/Atom the parser read."""

    from defusedxml import ElementTree as DefusedET

    try:
        root = DefusedET.fromstring(xml_text)
    except Exception:  # noqa: BLE001 - the parser already logged it
        return {}
    dates: dict[str, date] = {}
    for item in root.findall(".//item"):
        link = (item.findtext("link") or "").strip()
        raw = item.findtext("pubDate") or item.findtext("{http://purl.org/dc/elements/1.1/}date") or ""
        parsed = _parse_date(raw)
        if link and parsed:
            dates[link] = parsed
    for entry in root.findall(".//{*}entry"):
        raw = entry.findtext("{*}published") or entry.findtext("{*}updated") or ""
        parsed = _parse_date(raw)
        for node in entry.findall("{*}link"):
            href = (node.attrib.get("href") or "").strip()
            if href and parsed:
                dates[href] = parsed
    return dates


def _parse_date(raw: str) -> date | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return parsedate_to_datetime(raw).date()
    except (TypeError, ValueError, IndexError):
        pass
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def parse_feed(source: dict[str, Any], xml_text: str, *, today: date) -> list[Candidate]:
    """One feed's items as candidates (French, not sensitive, dated)."""

    news = _news()
    items = news._parse_rss_items(xml_text, source_hint=source["id"], language="fr", limit=ITEMS_PER_FEED)
    dates = _pub_dates(xml_text)
    out: list[Candidate] = []
    for item in news._dedupe_items(items):
        text = f"{item.get('title', '')} {item.get('summary', '')}"
        if not news._looks_like_language(text, "fr"):
            continue
        if policy.is_sensitive(text):
            continue
        out.append(
            Candidate(
                source_id=str(source["id"]),
                source_name=str(source.get("name") or source["id"]),
                title=str(item.get("title") or ""),
                url=str(item.get("url") or ""),
                summary=str(item.get("summary") or ""),
                published_at=dates.get(str(item.get("url") or ""), today),
                topic=topic_for(text, source.get("topic_tags") or ()),
                fetch_policy=str(source.get("fetch_policy") or "allows"),
            )
        )
    return out


def fetch_candidates(
    *,
    today: date,
    client: httpx.Client | None = None,
    sources: list[dict[str, Any]] | None = None,
) -> tuple[list[Candidate], dict[str, str]]:
    """Every registry feed, once; returns the candidates and a per-feed status."""

    own = client is None
    http = client or httpx.Client(follow_redirects=True)
    statuses: dict[str, str] = {}
    candidates: list[Candidate] = []
    try:
        for source in sources if sources is not None else registry():
            try:
                response = http.get(
                    source["url"],
                    headers={
                        "User-Agent": "ConversationalLanguageLearningBot/1.0 (+https://localhost)",
                        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9",
                    },
                    timeout=FEED_TIMEOUT_SECONDS,
                )
                response.raise_for_status()
            except httpx.HTTPError as exc:
                statuses[source["id"]] = f"failed:{type(exc).__name__}"
                continue
            found = parse_feed(source, response.text, today=today)
            statuses[source["id"]] = f"ok:{len(found)}"
            candidates.extend(found)
    finally:
        if own:
            http.close()
    return candidates, statuses


# ---------------------------------------------------------------------------
# Clusters and the spread
# ---------------------------------------------------------------------------


def cluster(candidates: list[Candidate], *, window: tuple[date, date]) -> list[Story]:
    """Group candidates about the same thing; rank by recency, size, then title."""

    news = _news()
    start, end = window
    stories: dict[str, Story] = {}
    for candidate in candidates:
        if not (start - timedelta(days=MAX_ITEM_AGE_DAYS) <= candidate.published_at <= end):
            continue
        item = {"title": candidate.title, "summary": candidate.summary, "source_id": candidate.source_id}
        item["named_people"] = news._extract_named_people(item)
        key = news._feuilleton_cluster_key(item)
        candidate.cluster_key = key
        story = stories.setdefault(key, Story(key=key, topic=candidate.topic, items=[]))
        if all(existing.url != candidate.url for existing in story.items):
            story.items.append(candidate)
    for story in stories.values():
        # The cluster's topic is its items' majority (ties: the newest item's).
        counts: dict[str, int] = {}
        for item in story.items:
            counts[item.topic] = counts.get(item.topic, 0) + 1
        newest = max(story.items, key=lambda item: item.published_at)
        story.topic = max(counts, key=lambda topic: (counts[topic], topic == newest.topic))
        story.items.sort(key=lambda item: (item.fetch_policy != "allows", -item.published_at.toordinal()))
        story.score = (-story.newest.toordinal(), -story.outlets, -len(story.items), story.key)
    return sorted(stories.values(), key=lambda story: story.score)


def spread(stories: list[Story]) -> list[list[Story]]:
    """The ranked stories of each :data:`TOPIC_SPREAD` group, in rank order."""

    return [[story for story in stories if story.topic in topics] for topics, _slots in TOPIC_SPREAD]


def slots_for(target: int) -> list[int]:
    """Slots per :data:`TOPIC_SPREAD` group for ``target`` stories (2/2/1/1 at six)."""

    base = [slots for _topics, slots in TOPIC_SPREAD]
    total = sum(base)
    if target == total:
        return base
    scaled = [max(0, (slots * target) // total) for slots in base]
    order = sorted(range(len(base)), key=lambda i: (-base[i], i))
    index = 0
    while sum(scaled) < target:
        scaled[order[index % len(order)]] += 1
        index += 1
    return scaled


# ---------------------------------------------------------------------------
# The run
# ---------------------------------------------------------------------------


@dataclass
class IntakeReport:
    period: str
    week: str
    status: str = "built"
    feeds: dict[str, str] = field(default_factory=dict)
    candidates: int = 0
    clusters: int = 0
    built: list[str] = field(default_factory=list)
    rejected: dict[str, list[str]] = field(default_factory=dict)
    evergreen_top_up: list[str] = field(default_factory=list)
    topics: dict[str, int] = field(default_factory=dict)
    cost_usd: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "period": self.period,
            "week": self.week,
            "status": self.status,
            "feeds": dict(self.feeds),
            "candidates": self.candidates,
            "clusters": self.clusters,
            "built": list(self.built),
            "rejected": {key: list(value) for key, value in self.rejected.items()},
            "evergreen_top_up": list(self.evergreen_top_up),
            "topics": dict(self.topics),
            "cost_usd": round(self.cost_usd, 6),
        }


def period_window(period: str) -> tuple[date, date]:
    """The days a period's stories may be about: the ISO week, or the last seven days to the date."""

    if is_daily_period(period):
        day = date.fromisoformat(period)
        return day - timedelta(days=6), day
    return week_bounds(period)


def _story_input(story: Story, *, week: str, period: str, today: date, fetch: Callable[[Candidate], tuple[str, str]]) -> StoryInput:
    items: list[SourceItem] = []
    seen: dict[str, int] = {}
    for candidate in story.items[:3]:
        count = seen.get(candidate.source_id, 0) + 1
        seen[candidate.source_id] = count
        source_id = candidate.source_id if count == 1 else f"{candidate.source_id}_{count}"
        text, status = fetch(candidate)
        items.append(
            SourceItem(
                source_id=source_id,
                name=candidate.source_name,
                url=candidate.url,
                title=candidate.title,
                summary=candidate.summary,
                published_at=candidate.published_at,
                article_text=text,
                fetch_status=status,
            )
        )
    return StoryInput(key=story.key, topic=story.topic, week=week, period=period, items=tuple(items), today=today)


def build_period(
    period: str,
    *,
    candidates: list[Candidate],
    provider: DossierProvider | None = None,
    client: httpx.Client | None = None,
    target: int | None = None,
    today: date | None = None,
    fetch_enabled: bool | None = None,
    report: IntakeReport | None = None,
) -> tuple[list[tuple[EditorialDossier, BuildResult | None]], IntakeReport]:
    """Cluster, spread, fetch, build and top up; nothing is persisted here."""

    from app.config import settings

    week = week_of_period(period)
    window = period_window(period)
    today = today or window[1]
    target = int(target if target is not None else getattr(settings, "REVUE_STORIES_PER_WEEK", 6))
    report = report or IntakeReport(period=period, week=week)
    report.candidates = len(candidates)
    stories = cluster(candidates, window=window)
    report.clusters = len(stories)
    robots = RobotsCache()

    def fetch(candidate: Candidate) -> tuple[str, str]:
        article = fetch_article(
            candidate.url, fetch_policy=candidate.fetch_policy, client=client, robots=robots, enabled=fetch_enabled
        )
        return (article.text if article.ok else ""), article.status

    queues = spread(stories)
    slots = slots_for(target)
    built: list[tuple[EditorialDossier, BuildResult | None]] = []
    used: set[str] = set()
    ids: set[str] = set()

    def try_story(story: Story) -> bool:
        used.add(story.key)
        result = build_dossier(
            _story_input(story, week=week, period=period, today=today, fetch=fetch), provider
        )
        report.cost_usd += result.cost_usd
        if not result.ok or result.dossier is None or result.dossier.id in ids:
            report.rejected[story.key] = result.rejected or ["duplicate_id"]
            return False
        ids.add(result.dossier.id)
        built.append((result.dossier, result))
        report.built.append(result.dossier.id)
        return True

    # Each group first fills its own slots, trying its next story when one is rejected.
    for queue, wanted in zip(queues, slots, strict=True):
        got = 0
        for story in queue:
            if got >= wanted:
                break
            if story.key not in used and try_story(story):
                got += 1
    # Then the best remaining stories of any topic take the slots a group could not fill.
    for story in stories:
        if len(built) >= target:
            break
        if story.key not in used:
            try_story(story)

    # §4.3: a thin week is filled with that week's evergreens.
    for evergreen in evergreens_for_week(week):
        if len(built) >= target:
            break
        if evergreen.id not in ids:
            ids.add(evergreen.id)
            built.append((evergreen, None))
            report.evergreen_top_up.append(evergreen.id)
    for dossier, _result in built:
        report.topics[dossier.topic] = report.topics.get(dossier.topic, 0) + 1
    return built, report


def persist(db: Session, period: str, built: list[tuple[EditorialDossier, BuildResult | None]]) -> None:
    from app.db.models.revue_session import RevueDossier

    db.execute(delete(RevueDossier).where(RevueDossier.period == period))
    for dossier, result in built:
        checks_payload: dict[str, Any]
        if result is None:
            checks_payload = {"evergreen_top_up": True, "passed": True}
        else:
            checks_payload = dict(result.check_summary)
        db.add(
            RevueDossier(
                id=_row_id(period, dossier.id),
                week=week_of_period(period),
                period=period,
                topic=dossier.topic,
                payload=dossier.model_dump(mode="json"),
                source_hashes=dict(result.source_hashes) if result else {},
                checks=checks_payload,
                builder_version=BUILDER_VERSION,
                built_at=datetime.now(UTC),
            )
        )
    db.commit()


def _row_id(period: str, dossier_id: str) -> str:
    """Built dossiers carry their period in their id; an evergreen top-up is keyed per period."""

    if dossier_id.startswith(period.lower()):
        return dossier_id[:120]
    return f"{period.lower()}:{dossier_id}"[:120]


def has_period(db: Session, period: str) -> bool:
    from app.db.models.revue_session import RevueDossier

    return db.scalar(select(RevueDossier.id).where(RevueDossier.period == period).limit(1)) is not None


def run_intake(
    db: Session,
    period: str,
    *,
    refresh: bool = False,
    provider: DossierProvider | None = None,
    client: httpx.Client | None = None,
    sources: list[dict[str, Any]] | None = None,
    target: int | None = None,
    today: date | None = None,
    fetch_enabled: bool | None = None,
) -> IntakeReport:
    """One intake run for ``period``; a period already built is kept unless ``refresh``."""

    week = week_of_period(period)
    report = IntakeReport(period=period, week=week)
    if not refresh and has_period(db, period):
        report.status = "kept"
        return report
    window = period_window(period)
    today = today or min(window[1], datetime.now(UTC).date())
    candidates, statuses = fetch_candidates(today=today, client=client, sources=sources)
    report.feeds = statuses
    built, report = build_period(
        period,
        candidates=candidates,
        provider=provider,
        client=client,
        target=target,
        today=today,
        fetch_enabled=fetch_enabled,
        report=report,
    )
    persist(db, period, built)
    from app.services.revue import weekly

    weekly.forget_cache()
    logger.bind(**{k: v for k, v in report.as_dict().items() if k in {"period", "built", "evergreen_top_up"}}).info(
        "revue intake: {} dossiers for {}", len(built), period
    )
    return report


def dossiers_for(week: str, topic: str | None = None, *, db: Session | None = None) -> list[EditorialDossier]:
    """§11's bridge: the week's checked dossiers (of ``topic`` when given), for any consumer."""

    from app.services.revue.weekly import available_for_week

    dossiers = available_for_week(week, db=db) if db is not None else available_for_week(week)
    return [dossier for dossier in dossiers if topic is None or dossier.topic == topic]


__all__ = [
    "TOPIC_SPREAD",
    "Candidate",
    "IntakeReport",
    "Story",
    "build_period",
    "cluster",
    "dossiers_for",
    "fetch_candidates",
    "parse_feed",
    "period_window",
    "persist",
    "registry",
    "run_intake",
    "slots_for",
    "topic_for",
]
