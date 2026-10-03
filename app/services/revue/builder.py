"""The dossier builder: one story in, one checked editorial dossier out (WP-119 §3.1, §4.2).

The intake (``intake.py``) hands over a :class:`StoryInput` — the cluster's RSS items and,
when the article fetch worked, each article's text (``sources.py``). The builder:

1. asks the provider **once** for the dossier's editorial content (title, summary, typed
   claims with verbatim quotes, entities, uncertainties, two angles with
   ``participation``/``guest_fit``, a place whose ``brief`` is *name + three landmarks +
   light* (§8.1 rule 1), ``vignette_object_fr``) — :class:`DossierProvider`;
2. assembles an :class:`EditorialDossier` around it (id, week, sources, URLs, dates come
   from the feed, never from the model) after the **structural repairs**: a quote over
   :data:`MAX_QUOTE_WORDS` words is trimmed to its first sentence that is still verbatim in
   the source (§4.2 Anchor, «repairs a 41-word quote»); an interpretation or forecast with
   no ``attributed_to`` is attributed to its outlet; a place brief that does not name its
   place is prefixed with the name (§8.1); a claim the schema refuses is dropped;
3. runs :func:`checks.run_dossier_checks` and applies §4.2's table: an unanchored claim is
   dropped, a fact that reads as an opinion is retyped as an interpretation attributed to
   its outlet, a claim with a relative date or a stale/future source is dropped, a refused
   geo is left to ``geo.geocode_dossier``; fewer than two anchored claims, a story that is
   not this week or already expired → the dossier is **rejected** with its reason codes;
4. returns a :class:`BuildResult` with the dossier, the source hashes (``sources.text_hash``
   — the only trace of the article text that survives the build, §12.3) and the checks.

The provider is injectable: :class:`FakeDossierProvider` (deterministic, from the article
sentences — every test and the walk harness) and :class:`LLMDossierProvider` (the app's LLM
service through ``encounter.OpenAIRevueProvider.ask_json``, one JSON call per story).
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Protocol

from loguru import logger
from pydantic import ValidationError

from app.services.revue import checks, policy
from app.services.revue.dossier import (
    MAX_QUOTE_WORDS,
    Angle,
    Claim,
    EditorialDossier,
    Entity,
    Place,
    TimeScope,
    fold,
    quote_word_count,
    week_bounds,
)
from app.services.revue.sources import text_hash

BUILDER_VERSION = "revue-builder-v1"
#: What the provider may read of one article (the rest is not needed for six claims).
ARTICLE_CHARS_FOR_PROVIDER = 6000
#: The angle purposes a dossier offers, in the order the builder asks for them (§5.2).
ANGLE_PURPOSES = ("understand_change", "explain_disagreement", "choose_angle", "prepare_dispatch")
_SENTENCE = re.compile(r"(?<=[.!?…])\s+(?=[«\"A-ZÀÂÉÈÊÎÔÛÇ0-9])")


# ---------------------------------------------------------------------------
# Inputs and outputs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceItem:
    """One RSS item of the story, with the article text when it was fetched (build only)."""

    source_id: str
    name: str
    url: str
    title: str
    summary: str
    published_at: date
    article_text: str = ""
    fetch_status: str = "disabled"

    @property
    def text(self) -> str:
        """What quotes are checked against: the article, else the teaser (§4.1)."""

        if self.article_text.strip():
            return self.article_text
        return "\n".join(part for part in (self.title, self.summary) if part.strip())


@dataclass(frozen=True)
class StoryInput:
    """One clustered story, ready for the builder."""

    key: str
    topic: str
    week: str
    #: The kiosk period it is built for: the ISO week, or an ISO date in daily mode.
    period: str
    items: tuple[SourceItem, ...]
    today: date

    def source_texts(self) -> dict[str, str]:
        return {item.source_id: item.text for item in self.items}


@dataclass
class BuildResult:
    """The outcome of one build: a dossier, or the reasons it was rejected."""

    story_key: str
    dossier: EditorialDossier | None = None
    rejected: list[str] = field(default_factory=list)
    repairs: list[str] = field(default_factory=list)
    source_hashes: dict[str, str] = field(default_factory=dict)
    check_summary: dict[str, Any] = field(default_factory=dict)
    cost_usd: float = 0.0

    @property
    def ok(self) -> bool:
        return self.dossier is not None


class DossierProvider(Protocol):
    name: str

    def build_dossier(self, context: dict[str, Any]) -> dict[str, Any]: ...


# ---------------------------------------------------------------------------
# Small text helpers
# ---------------------------------------------------------------------------


def slug(text: str, *, limit: int = 60) -> str:
    folded = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode("ascii").lower()
    words = re.findall(r"[a-z0-9]+", folded)
    out = "-".join(words)
    return out[:limit].strip("-") or "sujet"


def sentences(text: str) -> list[str]:
    """Sentences of a paragraph-per-line text (lines first, then sentence ends)."""

    out: list[str] = []
    for line in str(text or "").splitlines():
        line = " ".join(line.split())
        if line:
            out.extend(part.strip() for part in _SENTENCE.split(line) if part.strip())
    return out


def trim_quote(quote: str, source_text: str) -> str | None:
    """A quote of at most :data:`MAX_QUOTE_WORDS` words that is still verbatim in the source.

    The repair §4.2 allows for an over-long quote: keep its first sentence (then the next
    ones, while they fit and stay verbatim). ``None`` when no sentence of the quote fits.
    """

    folded_source = fold(source_text)
    kept = ""
    for sentence in sentences(quote):
        candidate = f"{kept} {sentence}".strip() if kept else sentence
        if quote_word_count(candidate) > MAX_QUOTE_WORDS or fold(candidate) not in folded_source:
            break
        kept = candidate
    if kept:
        return kept
    # The first sentence alone is too long or not verbatim: no quote survives.
    return None


def _outlet(items: tuple[SourceItem, ...], source_id: str) -> str:
    return next((item.name for item in items if item.source_id == source_id), "la source")


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------


def provider_context(story: StoryInput) -> dict[str, Any]:
    """What the provider sees: the story's items and (truncated) article texts, the week."""

    monday, sunday = week_bounds(story.week)
    return {
        "week": story.week,
        "week_monday": monday.isoformat(),
        "week_sunday": sunday.isoformat(),
        "today": story.today.isoformat(),
        "topic": story.topic,
        "topics": list(policy.TOPICS),
        "guest_cast_ids": list(policy.GUEST_CAST_IDS),
        "items": [
            {
                "source_id": item.source_id,
                "outlet": item.name,
                "title": item.title,
                "summary": item.summary,
                "published_at": item.published_at.isoformat(),
                "text": item.text[:ARTICLE_CHARS_FOR_PROVIDER],
                "is_teaser_only": not bool(item.article_text.strip()),
            }
            for item in story.items
        ],
    }


BUILDER_INSTRUCTIONS = """You are the fact desk of «Le Papier de Romy», a French-learning app.
From the INPUT articles about one French news story of the week, write ONE editorial dossier as JSON:
{"title_fr": str, "summary_fr": str (2-3 plain sentences, A2-B1 French),
 "topic": one of INPUT.topics,
 "claims": [{"id": "c1", "kind": "fact"|"interpretation"|"forecast", "fr": str (our own simple French sentence),
             "quote": str (VERBATIM from one item's text, at most 40 words), "source_id": str,
             "attributed_to": str|null (REQUIRED for interpretation and forecast: who says so)}] (3 to 5 claims),
 "entities": [{"name": str, "kind": "person"|"place"|"organisation"|"other", "role": str|null (required for a person)}],
 "uncertainties": [str] (what the sources do not say; 1-3),
 "angles": [{"id": "a1", "fr": str, "purpose": "understand_change"|"explain_disagreement"|"choose_angle"|"prepare_dispatch",
             "participation": "none"|"helps"|"works"|"formal", "guest_fit": one of INPUT.guest_cast_ids or null}] (exactly 2),
 "places": [{"id": snake_case str, "name_fr": str, "brief": str}] (1 or 2),
 "time_scope": {"happening": "YYYY-MM-DD/YYYY-MM-DD", "relevant_until": "YYYY-MM-DD"},
 "vignette_object_fr": str (one drawable object, with its article: «une urne»)}
Rules: every quote is copied character for character from that item's text; a fact reports, it never judges
(no «heureusement», «scandaleux», «il faut»); no relative dates («demain», «jeudi», «la semaine prochaine») —
write absolute dates; happening must overlap week_monday..week_sunday and relevant_until must be on or after
week_sunday; a place brief is the place's NAME + three distinctive, checkable landmarks + the light, never a
type of place, and names no person; participation is how the learner would take part (helps at a stall, works
on a site, formal role) — "none" when they only watch."""


@dataclass
class LLMDossierProvider:
    """One structured JSON call per story through the Revue's LLM plumbing (cost on ``spent_usd``)."""

    name: str = "llm-dossier"
    _llm: Any = None

    @property
    def spent_usd(self) -> float:
        return float(getattr(self._client(), "spent_usd", 0.0) or 0.0)

    def _client(self) -> Any:
        if self._llm is None:
            from app.services.revue.encounter import OpenAIRevueProvider

            self._llm = OpenAIRevueProvider(name="openai-revue-builder", max_tokens=3200)
        return self._llm

    def build_dossier(self, context: dict[str, Any]) -> dict[str, Any]:
        return self._client().ask_json(
            BUILDER_INSTRUCTIONS,
            context,
            system="You write careful, sourced French news dossiers for language learners. Answer with JSON only.",
            temperature=0.2,
            label="build_dossier",
        )


@dataclass
class FakeDossierProvider:
    """Deterministic dossiers from the article sentences (tests, the walk harness, dev).

    ``script`` maps a story's first source id (or ``"*"``) to a raw dict returned as is —
    the tests inject an over-long quote or an unanchored claim through it.
    """

    name: str = "fake-dossier"
    script: dict[str, dict[str, Any]] = field(default_factory=dict)
    spent_usd: float = 0.0
    calls: list[dict[str, Any]] = field(default_factory=list)

    def build_dossier(self, context: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(context)
        items = context.get("items") or []
        first = items[0]["source_id"] if items else ""
        if first in self.script:
            return dict(self.script[first])
        if "*" in self.script:
            return dict(self.script["*"])
        claims: list[dict[str, Any]] = []
        for item in items:
            for sentence in sentences(item["text"]):
                words = quote_word_count(sentence)
                if words < 6 or words > MAX_QUOTE_WORDS:
                    continue
                claims.append(
                    {
                        "id": f"c{len(claims) + 1}",
                        "kind": "fact",
                        "fr": sentence,
                        "quote": sentence,
                        "source_id": item["source_id"],
                        "attributed_to": None,
                    }
                )
                if len(claims) >= 4:
                    break
            if len(claims) >= 4:
                break
        lead = items[0] if items else {"title": "Un sujet", "summary": ""}
        topic = context.get("topic") or "city"
        guests = policy.guests_for(topic) if topic in policy.TOPICS else []
        guest = guests[0]["id"] if guests else None
        city = _city_in(" ".join(f"{i['title']} {i['text']}" for i in items)) or "Paris"
        return {
            "title_fr": lead["title"],
            "summary_fr": lead.get("summary") or (claims[0]["fr"] if claims else lead["title"]),
            "topic": topic,
            "claims": claims,
            "entities": [{"name": city, "kind": "place", "role": None}],
            "uncertainties": ["Les sources ne disent pas ce qui va se passer ensuite."],
            "angles": [
                {"id": "a1", "fr": "Ce que ça change pour les gens", "purpose": "understand_change",
                 "participation": "none", "guest_fit": guest},
                {"id": "a2", "fr": "Expliquer l'histoire en trois lignes", "purpose": "prepare_dispatch",
                 "participation": "none", "guest_fit": None},
            ],
            "places": [{"id": f"lieu_{slug(city, limit=30).replace('-', '_')}", "name_fr": city,
                        "brief": f"{city}: a street of stone façades, a café terrace, a newspaper kiosk, morning light"}],
            "time_scope": {
                "happening": f"{context['week_monday']}/{context['week_sunday']}",
                "relevant_until": (date.fromisoformat(context["week_sunday"]) + timedelta(days=14)).isoformat(),
            },
            "vignette_object_fr": "un journal",
        }


def _city_in(text: str) -> str | None:
    try:
        from app.services.revue.geo import city_entry
    except Exception:  # noqa: BLE001 - geo is optional for the fake
        return None
    for token in re.findall(r"[A-ZÀÂÉÈÎÔ][\w'’-]+(?:[- ](?:sur|en|de|la|le)?[- ]?[A-Z][\w'’-]+)*", text or ""):
        entry = city_entry(token)
        if entry is not None:
            return token
    return None


def default_provider() -> DossierProvider:
    from app.config import settings

    if getattr(settings, "OPENAI_API_KEY", None) or getattr(settings, "ANTHROPIC_API_KEY", None):
        return LLMDossierProvider()
    logger.warning("revue builder: no LLM provider configured; dossiers come from the deterministic builder")
    return FakeDossierProvider()


# ---------------------------------------------------------------------------
# Assembly and repairs
# ---------------------------------------------------------------------------


def _assemble(story: StoryInput, raw: dict[str, Any], result: BuildResult) -> EditorialDossier | None:
    items = {item.source_id: item for item in story.items}
    texts = story.source_texts()

    claims: list[Claim] = []
    for index, row in enumerate(raw.get("claims") or []):
        if not isinstance(row, dict):
            continue
        claim_id = str(row.get("id") or f"c{index + 1}")
        source_id = str(row.get("source_id") or "")
        item = items.get(source_id)
        if item is None:
            result.repairs.append(f"drop:{claim_id}:unknown_source")
            continue
        quote = str(row.get("quote") or "").strip()
        if quote_word_count(quote) > MAX_QUOTE_WORDS:
            trimmed = trim_quote(quote, texts[source_id])
            if trimmed is None:
                result.repairs.append(f"drop:{claim_id}:quote_too_long")
                continue
            result.repairs.append(f"trim:{claim_id}:{quote_word_count(quote)}->{quote_word_count(trimmed)}")
            quote = trimmed
        kind = str(row.get("kind") or "fact")
        attributed = (str(row.get("attributed_to") or "").strip()) or None
        if kind in {"interpretation", "forecast"} and not attributed:
            attributed = item.name
            result.repairs.append(f"attribute:{claim_id}")
        try:
            claims.append(
                Claim(
                    id=claim_id,
                    kind=kind,  # type: ignore[arg-type]
                    fr=str(row.get("fr") or "").strip(),
                    quote=quote,
                    source_id=source_id,
                    url=item.url,
                    published_at=item.published_at,
                    attributed_to=attributed,
                )
            )
        except ValidationError as exc:
            result.repairs.append(f"drop:{claim_id}:schema:{exc.errors()[0].get('type')}")

    entities: list[Entity] = []
    for row in raw.get("entities") or []:
        try:
            entities.append(Entity.model_validate({k: row.get(k) for k in ("name", "kind", "role")}))
        except (ValidationError, AttributeError):
            result.repairs.append("drop:entity")

    angles: list[Angle] = []
    for index, row in enumerate((raw.get("angles") or [])[:2]):
        try:
            data = {k: row.get(k) for k in ("id", "fr", "purpose", "participation", "guest_fit") if row.get(k) is not None}
            data.setdefault("id", f"a{index + 1}")
            if data.get("guest_fit") not in policy.GUEST_CAST_IDS:
                data.pop("guest_fit", None)
            angles.append(Angle.model_validate(data))
        except (ValidationError, AttributeError):
            result.repairs.append(f"drop:angle:{index}")

    places: list[Place] = []
    for index, row in enumerate((raw.get("places") or [])[:2]):
        try:
            name = str(row.get("name_fr") or "").strip()
            brief = str(row.get("brief") or "").strip()
            if name and fold(name).casefold() not in fold(brief).casefold():
                # §8.1 rule 1: the brief names its place (a type paints a type).
                brief = f"{name}: {brief}" if brief else name
                result.repairs.append(f"brief_named:{row.get('id')}")
            places.append(Place(id=str(row.get("id") or f"lieu_{index + 1}"), name_fr=name, brief=brief))
        except (ValidationError, AttributeError):
            result.repairs.append(f"drop:place:{index}")

    used_sources = list(dict.fromkeys(claim.source_id for claim in claims))
    sources = [
        {"id": sid, "name": items[sid].name, "url": items[sid].url, "published_at": items[sid].published_at}
        for sid in used_sources
    ]
    topic = str(raw.get("topic") or story.topic)
    if topic not in policy.TOPICS:
        topic = story.topic
    title = str(raw.get("title_fr") or story.items[0].title).strip()
    prefix = story.period.lower()
    try:
        return EditorialDossier(
            id=f"{prefix}-{slug(title)}"[:120],
            week=story.week,
            topic=topic,
            title_fr=title,
            summary_fr=str(raw.get("summary_fr") or "").strip() or title,
            claims=claims,
            entities=entities,
            uncertainties=[{"id": f"u{i + 1}", "fr": str(u).strip()} for i, u in enumerate(
                [u for u in raw.get("uncertainties") or [] if str(u).strip()][:3])],
            angles=angles,
            places=places,
            time_scope=TimeScope.model_validate(raw.get("time_scope") or {}),
            sources=sources,
            evergreen=False,
            vignette_object_fr=(str(raw.get("vignette_object_fr") or "").strip() or None),
        )
    except ValidationError as exc:
        result.rejected.extend(sorted({f"schema:{error['loc'][0] if error['loc'] else '?'}" for error in exc.errors()}))
        return None


def _apply_checks(dossier: EditorialDossier, story: StoryInput, result: BuildResult) -> EditorialDossier | None:
    """§4.2's table on the dossier-level checks; ``None`` when the dossier must be dropped."""

    texts = story.source_texts()
    names = {item.source_id: item.name for item in story.items}
    for _round in range(2):
        results = checks.run_dossier_checks(dossier, source_texts=texts, week=story.week)
        failed = checks.failures(results)
        if not failed:
            return dossier
        fatal = sorted(
            {f.reason for f in failed if f.reason in {"not_this_week", "expired"}}
            | {f.reason for f in failed if f.reason == "relative_date" and f.detail.get("field") == "summary_fr"}
        )
        if fatal:
            result.rejected.extend(fatal)
            return None
        drop: set[str] = set()
        retype: set[str] = set()
        for failure in failed:
            claim_id = failure.detail.get("claim_id")
            if failure.check == "anchor" and claim_id:
                drop.add(claim_id)
            elif failure.check == "temporal" and claim_id:
                drop.add(claim_id)
            elif failure.check == "attribution" and claim_id:
                if failure.reason == "fact_reads_as_opinion":
                    retype.add(claim_id)
                else:
                    drop.add(claim_id)
            elif failure.check == "geo":
                place_id = failure.detail.get("place_id")
                for place in dossier.places:
                    if place.id == place_id:
                        place.geo = None
                result.repairs.append(f"geo_dropped:{place_id}")
        claims: list[Claim] = []
        for claim in dossier.claims:
            if claim.id in drop:
                result.repairs.append(f"drop:{claim.id}:{_reason_for(failed, claim.id)}")
                continue
            if claim.id in retype:
                claim = claim.model_copy(update={"kind": "interpretation", "attributed_to": names.get(claim.source_id, "la source")})
                result.repairs.append(f"retype:{claim.id}")
            claims.append(claim)
        if len(claims) < checks.MIN_ANCHORED_CLAIMS:
            result.rejected.append("too_few_claims_anchored")
            return None
        used = {claim.source_id for claim in claims}
        try:
            dossier = dossier.model_copy(
                update={"claims": claims, "sources": [s for s in dossier.sources if s.id in used]}
            )
            dossier = EditorialDossier.model_validate(dossier.model_dump())
        except ValidationError:
            result.rejected.append("schema_after_repair")
            return None
    final = checks.failures(checks.run_dossier_checks(dossier, source_texts=texts, week=story.week))
    if final:
        result.rejected.extend(sorted({f.reason or f.check for f in final}))
        return None
    return dossier


def _reason_for(failed: list[checks.CheckResult], claim_id: str) -> str:
    return next((f.reason or f.check for f in failed if f.detail.get("claim_id") == claim_id), "check")


def build_dossier(
    story: StoryInput,
    provider: DossierProvider | None = None,
    *,
    geocode: Callable[[EditorialDossier], EditorialDossier] | None = None,
) -> BuildResult:
    """One provider call, the structural repairs, the checks on meaning (§4.2)."""

    provider = provider or default_provider()
    result = BuildResult(story_key=story.key)
    spent_before = float(getattr(provider, "spent_usd", 0.0) or 0.0)
    try:
        raw = provider.build_dossier(provider_context(story))
    except Exception as exc:  # noqa: BLE001 - one story never costs the week
        logger.bind(story=story.key).warning("revue builder: provider failed ({})", exc)
        result.rejected.append("provider_failed")
        return result
    finally:
        result.cost_usd = round(float(getattr(provider, "spent_usd", 0.0) or 0.0) - spent_before, 6)
    if not isinstance(raw, dict):
        result.rejected.append("provider_not_an_object")
        return result
    dossier = _assemble(story, raw, result)
    if dossier is None:
        return result
    dossier = _apply_checks(dossier, story, result)
    if dossier is None:
        logger.bind(story=story.key, reasons=result.rejected).info("revue_check_failed dossier rejected")
        return result
    if geocode is None:
        from app.services.revue.geo import geocode_dossier as geocode
    try:
        dossier = geocode(dossier)
    except Exception as exc:  # noqa: BLE001 - a pin is a quiet extra
        logger.bind(story=story.key).info("revue builder: geocoding skipped ({})", exc)
    result.dossier = dossier
    result.source_hashes = {
        item.source_id: text_hash(item.text) for item in story.items if item.source_id in {s.id for s in dossier.sources}
    }
    results = checks.run_dossier_checks(dossier, source_texts=story.source_texts(), week=story.week)
    result.check_summary = {
        "passed": checks.passed(results),
        "checks": sorted({r.check for r in results}),
        "repairs": list(result.repairs),
        "fetch": {item.source_id: item.fetch_status for item in story.items},
        "builder_version": BUILDER_VERSION,
        "provider": getattr(provider, "name", None),
    }
    return result


__all__ = [
    "BUILDER_INSTRUCTIONS",
    "BUILDER_VERSION",
    "BuildResult",
    "DossierProvider",
    "FakeDossierProvider",
    "LLMDossierProvider",
    "SourceItem",
    "StoryInput",
    "build_dossier",
    "default_provider",
    "provider_context",
    "sentences",
    "slug",
    "trim_quote",
]
