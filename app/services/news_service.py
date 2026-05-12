"""Service for fetching live content (news/Substack) for conversation context."""
from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from urllib.parse import quote_plus

import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.utils.cache import build_cache_key, cache_backend


class NewsService:
    """Fetch current content from RSS sources, with LLM fallback summarization."""

    PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"
    GOOGLE_NEWS_RSS = "https://news.google.com/rss/search"
    CACHE_TTL_SECONDS = 60 * 60 * 4
    FRANCE_CONTEXT_TTL_SECONDS = 60 * 60 * 5
    FEUILLETON_DAILY_SEED_TTL_SECONDS = 60 * 60 * 28
    FEUILLETON_DAILY_SEED_VERSION = "feuilleton-daily-seed-v2"
    FRANCE_SOURCE_REGISTRY = [
        {
            "id": "le_monde_front",
            "name": "Le Monde",
            "url": "https://www.lemonde.fr/rss/une.xml",
            "region_tags": ["france", "paris"],
            "topic_tags": ["society", "politics", "culture"],
        },
        {
            "id": "rfi_france",
            "name": "RFI",
            "url": "https://www.rfi.fr/fr/france/rss",
            "region_tags": ["france"],
            "topic_tags": ["society", "politics"],
        },
        {
            "id": "france24_france",
            "name": "France 24",
            "url": "https://www.france24.com/fr/france/rss",
            "region_tags": ["france"],
            "topic_tags": ["society", "politics"],
        },
        {
            "id": "franceinfo_france",
            "name": "Franceinfo",
            "url": "https://www.francetvinfo.fr/france.rss",
            "region_tags": ["france", "paris"],
            "topic_tags": ["society", "daily_life"],
        },
    ]
    FEUILLETON_SATIRE_SOURCE_REGISTRY = [
        {
            "id": "le_gorafi",
            "name": "Le Gorafi",
            "url": "https://www.legorafi.fr/feed/",
            "region_tags": ["france"],
            "topic_tags": ["satire", "humour", "absurdite"],
            "source_type": "satire_reference",
        },
    ]
    FEUILLETON_SENSITIVE_TERMS = (
        "abus",
        "agression sexuelle",
        "assassinat",
        "attentat",
        "décès",
        "disparition",
        "fusillade",
        "guerre",
        "meurtre",
        "mort ",
        "mortel",
        "otage",
        "pédocriminalité",
        "suicide",
        "terrorisme",
        "viol ",
        "violence conjugale",
    )
    FEUILLETON_COMIC_TERMS = (
        "annonce",
        "assemblée",
        "baccalauréat",
        "bureaucratie",
        "café",
        "candidature",
        "culture",
        "école",
        "festival",
        "formulaire",
        "gouvernement",
        "grève",
        "impôts",
        "mairie",
        "météo",
        "métro",
        "ministre",
        "polémique",
        "présidentielle",
        "rentrée",
        "sncf",
        "télévision",
    )
    LANGUAGE_CONFIG = {
        "fr": {"hl": "fr", "gl": "FR", "ceid": "FR:fr"},
        "de": {"hl": "de", "gl": "DE", "ceid": "DE:de"},
        "en": {"hl": "en-US", "gl": "US", "ceid": "US:en"},
        "es": {"hl": "es-419", "gl": "ES", "ceid": "ES:es"},
        "it": {"hl": "it", "gl": "IT", "ceid": "IT:it"},
        "pt": {"hl": "pt-BR", "gl": "BR", "ceid": "BR:pt-419"},
    }
    LANGUAGE_STOPWORDS = {
        "fr": {"le", "la", "les", "des", "une", "est", "pour", "avec", "dans", "sur", "et"},
        "de": {"der", "die", "das", "und", "mit", "für", "ist", "ein", "eine", "auf"},
        "en": {"the", "and", "for", "with", "is", "in", "to", "of", "on"},
        "es": {"el", "la", "los", "las", "para", "con", "es", "en", "y", "de"},
        "it": {"il", "lo", "la", "gli", "le", "per", "con", "e", "di", "in"},
        "pt": {"o", "a", "os", "as", "para", "com", "e", "de", "em", "que"},
    }
    DEFAULT_QUERY_TERMS = {
        "fr": ["actualites", "culture", "economie"],
        "de": ["nachrichten", "kultur", "wirtschaft"],
        "en": ["news", "culture", "economy"],
        "es": ["noticias", "cultura", "economia"],
        "it": ["notizie", "cultura", "economia"],
        "pt": ["noticias", "cultura", "economia"],
    }

    def __init__(self) -> None:
        self.api_key = settings.PERPLEXITY_API_KEY
        self.client = httpx.AsyncClient(timeout=12.0, follow_redirects=True)

    async def fetch_news_context(
        self,
        interests: list[str] | None = None,
        *,
        target_language: str = "fr",
        limit: int = 3,
    ) -> dict[str, object]:
        """
        Return live content context:
        {
          "digest": str | None,
          "items": list[{"title","url","source","summary"}]
        }
        """
        requested_language = self._normalize_language(target_language)
        normalized_interests = self._normalize_interests(interests)
        cache_key = build_cache_key(
            interests=normalized_interests,
            limit=limit,
            target_language=requested_language,
            substack_feeds=settings.SUBSTACK_FEED_URLS,
        )
        cached = cache_backend.get("news:context", cache_key)
        if cached:
            return cached

        items = await self._fetch_live_items(
            normalized_interests,
            target_language=requested_language,
            limit=limit,
        )
        digest: str | None = None
        if items:
            digest = self._format_items_as_digest(items)
        elif self.api_key:
            # Fallback only when RSS yielded nothing.
            digest = await self._query_perplexity(
                normalized_interests,
                target_language=requested_language,
            )

        payload = {"digest": digest, "items": items}
        cache_backend.set("news:context", cache_key, payload, ttl_seconds=self.CACHE_TTL_SECONDS)
        return payload

    async def fetch_news_digest(self, interests: list[str] | None = None) -> str | None:
        """Backward-compatible helper used by existing context builders."""
        context = await self.fetch_news_context(interests, target_language="fr", limit=3)
        return context.get("digest") if isinstance(context, dict) else None

    async def fetch_france_context(
        self,
        interests: list[str] | None = None,
        *,
        limit: int = 3,
        prefer_paris: bool = True,
    ) -> dict[str, object]:
        """Return a France-specific, attributed source snapshot for missions."""
        normalized_interests = self._normalize_interests(interests)
        cache_key = build_cache_key(
            interests=normalized_interests,
            limit=limit,
            prefer_paris=prefer_paris,
            source_ids=[source["id"] for source in self.FRANCE_SOURCE_REGISTRY],
        )
        cached = cache_backend.get("news:france-context", cache_key)
        if cached:
            return cached

        items: list[dict[str, str]] = []
        for source in self.FRANCE_SOURCE_REGISTRY:
            try:
                source_items = await self._fetch_rss_items(
                    source["url"],
                    source_hint=source["name"],
                    language="fr",
                    limit=limit + 3,
                )
            except Exception as exc:
                logger.debug("France mission feed fetch failed", source=source["id"], error=str(exc))
                continue
            for item in source_items:
                blob = f"{item.get('title', '')} {item.get('summary', '')}"
                if not self._looks_like_language(blob, "fr"):
                    continue
                item["source_id"] = source["id"]
                item["source"] = item.get("source") or source["name"]
                item["source_type"] = "france_rss"
                item["region_tags"] = source.get("region_tags", [])
                item["topic_tags"] = source.get("topic_tags", [])
                item["language_confidence"] = "high"
                items.append(item)

        deduped: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for item in items:
            key = (item.get("title", "").lower(), item.get("url", ""))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)

        def score(item: dict[str, str]) -> int:
            text = f"{item.get('title', '')} {item.get('summary', '')}".lower()
            france_score = 3
            if prefer_paris and any(token in text for token in ("paris", "ile-de-france", "île-de-france")):
                france_score += 2
            interest_score = self._item_interest_score(item, normalized_interests) if normalized_interests else 0
            return france_score + interest_score

        deduped.sort(key=score, reverse=True)
        selected = deduped[:limit]
        if selected:
            digest = self._format_items_as_digest(selected)
            payload: dict[str, object] = {
                "mode": "live_france_rss",
                "digest": digest,
                "items": selected,
                "source_policy": "France-specific RSS registry; title, summary, source and URL only.",
            }
        else:
            payload = {
                "mode": "curated_prompt",
                "digest": "La France prépare plusieurs rendez-vous publics cette semaine: transports, travail, culture et vie quotidienne restent des sujets naturels pour une courte mission.",
                "items": [
                    {
                        "title": "Curated France scenario",
                        "url": "",
                        "source": "Atelier curated fallback",
                        "summary": "A fixed France-focused prompt used when live feeds are unavailable.",
                        "language": "fr",
                        "source_type": "curated_prompt",
                        "language_confidence": "n/a",
                    }
                ],
                "source_policy": "Curated fallback; no live article was fetched.",
            }
        cache_backend.set("news:france-context", cache_key, payload, ttl_seconds=self.FRANCE_CONTEXT_TTL_SECONDS)
        return payload

    async def fetch_feuilleton_daily_seed(
        self,
        interests: list[str] | None = None,
        *,
        refresh: bool = False,
        today: str | None = None,
        limit: int = 12,
    ) -> dict[str, object]:
        """Return the editorial news seed shared by all Feuilletons for one day."""
        seed_date = today or date.today().isoformat()
        normalized_interests = self._normalize_interests(interests)
        factual_source_ids = [source["id"] for source in self.FRANCE_SOURCE_REGISTRY]
        satire_source_ids = [source["id"] for source in self.FEUILLETON_SATIRE_SOURCE_REGISTRY]
        cache_key = build_cache_key(
            date=seed_date,
            interests=normalized_interests,
            source_ids=factual_source_ids,
            satire_source_ids=satire_source_ids,
            seed_version=self.FEUILLETON_DAILY_SEED_VERSION,
        )
        if not refresh:
            cached = cache_backend.get("news:feuilleton-daily-seed", cache_key)
            if cached:
                cached["cache_status"] = "hit"
                return cached

        items: list[dict[str, object]] = []
        for source in self.FRANCE_SOURCE_REGISTRY:
            try:
                source_items = await self._fetch_rss_items(
                    source["url"],
                    source_hint=source["name"],
                    language="fr",
                    limit=limit,
                )
            except Exception as exc:
                logger.debug("Feuilleton seed feed fetch failed", source=source["id"], error=str(exc))
                continue

            for item in source_items:
                blob = f"{item.get('title', '')} {item.get('summary', '')}"
                if not self._looks_like_language(blob, "fr"):
                    continue
                enriched: dict[str, object] = {
                    **item,
                    "source_id": source["id"],
                    "source": item.get("source") or source["name"],
                    "source_type": "daily_news_seed",
                    "region_tags": source.get("region_tags", []),
                    "topic_tags": source.get("topic_tags", []),
                    "language_confidence": "high",
                }
                enriched["named_people"] = self._extract_named_people(enriched)
                if self._is_sensitive_for_feuilleton(enriched):
                    continue
                items.append(enriched)

        satire_refs = await self._fetch_feuilleton_satire_references(limit=4)
        candidates = self._dedupe_items(items)
        if normalized_interests:
            candidates.sort(
                key=lambda item: self._score_feuilleton_item(item, normalized_interests),
                reverse=True,
            )
        clusters = self._cluster_feuilleton_items(candidates[: max(limit * 2, 12)])

        selected: dict[str, object] | None = None
        supporting_items: list[dict[str, object]] = []
        if clusters:
            top_cluster = clusters[0]
            cluster_items = top_cluster.get("items") or []
            if cluster_items:
                selected = cluster_items[0]
                supporting_items = cluster_items[1:4]

        if not selected and candidates:
            selected = candidates[0]
            supporting_items = candidates[1:4]

        if not selected:
            payload = self._curated_feuilleton_seed(
                seed_date=seed_date,
                normalized_interests=normalized_interests,
                satire_refs=satire_refs,
            )
            cache_backend.set(
                "news:feuilleton-daily-seed",
                cache_key,
                payload,
                ttl_seconds=self.FEUILLETON_DAILY_SEED_TTL_SECONDS,
            )
            return payload

        named_people = selected.get("named_people") or []
        title = str(selected.get("title") or "L'actualité française du jour")
        summary = str(selected.get("summary") or "")
        payload = {
            "mode": "feuilleton_daily_seed",
            "date": seed_date,
            "seed_version": self.FEUILLETON_DAILY_SEED_VERSION,
            "title": title,
            "title_fr": title,
            "summary": summary,
            "summary_fr": self._feuilleton_summary_fr(selected, supporting_items),
            "source": selected.get("source") or "Source française",
            "url": selected.get("url") or "",
            "items": [selected, *supporting_items],
            "supporting_items": supporting_items,
            "satire_reference_items": satire_refs,
            "named_people": named_people,
            "digest": self._format_feuilleton_seed_digest(selected, supporting_items, satire_refs),
            "source_policy": (
                "Daily Feuilleton seed: French factual RSS for the topic; "
                "satirical feeds only as tone references, not as factual sources."
            ),
            "content_depth": "rss_title_summary_plus_supporting_headlines",
            "article_fetch_policy": "No full article scraping in v1; store title, summary, source, URL and fetched timestamp.",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "cache_status": "refreshed" if refresh else "miss",
        }
        cache_backend.set(
            "news:feuilleton-daily-seed",
            cache_key,
            payload,
            ttl_seconds=self.FEUILLETON_DAILY_SEED_TTL_SECONDS,
        )
        return payload

    async def _fetch_feuilleton_satire_references(self, limit: int = 4) -> list[dict[str, object]]:
        references: list[dict[str, object]] = []
        for source in self.FEUILLETON_SATIRE_SOURCE_REGISTRY:
            try:
                source_items = await self._fetch_rss_items(
                    source["url"],
                    source_hint=source["name"],
                    language="fr",
                    limit=limit,
                )
            except Exception as exc:
                logger.debug("Feuilleton satire reference fetch failed", source=source["id"], error=str(exc))
                continue
            for item in source_items:
                blob = f"{item.get('title', '')} {item.get('summary', '')}"
                if not self._looks_like_language(blob, "fr"):
                    continue
                references.append(
                    {
                        **item,
                        "source_id": source["id"],
                        "source": item.get("source") or source["name"],
                        "source_type": "satire_reference",
                        "topic_tags": source.get("topic_tags", []),
                        "usage": "tone_reference_only",
                    }
                )
                if len(references) >= limit:
                    return references
        return references[:limit]

    def _curated_feuilleton_seed(
        self,
        *,
        seed_date: str,
        normalized_interests: list[str],
        satire_refs: list[dict[str, object]],
    ) -> dict[str, object]:
        title = "Une petite annonce française devient un grand rituel"
        summary = (
            "Faute de flux disponible, l'édition part d'une scène publique française: "
            "une annonce ordinaire devient une procédure collective beaucoup trop sérieuse."
        )
        return {
            "mode": "feuilleton_curated_seed",
            "date": seed_date,
            "seed_version": self.FEUILLETON_DAILY_SEED_VERSION,
            "title": title,
            "title_fr": title,
            "summary": summary,
            "summary_fr": summary,
            "source": "Atelier",
            "url": "",
            "items": [],
            "supporting_items": [],
            "satire_reference_items": satire_refs,
            "named_people": [],
            "interests": normalized_interests,
            "digest": summary,
            "source_policy": "Curated fallback because live French RSS sources were unavailable.",
            "content_depth": "curated_prompt",
            "article_fetch_policy": "No live article fetched.",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "cache_status": "curated",
        }

    def _dedupe_items(self, items: list[dict[str, object]]) -> list[dict[str, object]]:
        deduped: list[dict[str, object]] = []
        seen: set[tuple[str, str]] = set()
        for item in items:
            key = (
                str(item.get("title") or "").strip().lower(),
                str(item.get("url") or "").strip(),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped

    def _is_sensitive_for_feuilleton(self, item: dict[str, object]) -> bool:
        text = f"{item.get('title', '')} {item.get('summary', '')}".lower()
        return any(term in text for term in self.FEUILLETON_SENSITIVE_TERMS)

    def _extract_named_people(self, item: dict[str, object]) -> list[str]:
        text = f"{item.get('title', '')} {item.get('summary', '')}"
        matches = re.findall(
            r"\b[A-ZÉÈÀÂÊÎÔÛÇ][A-Za-zÀ-ÿ'’-]+(?:\s+(?:d'|de|du|des|le|la|l'|[A-ZÉÈÀÂÊÎÔÛÇ][A-Za-zÀ-ÿ'’-]+)){1,3}",
            text,
        )
        blocked = {
            "Assemblée Nationale",
            "Conseil Constitutionnel",
            "France Info",
            "Franceinfo",
            "France Inter",
            "France Télévisions",
            "France 24",
            "Le Figaro",
            "Le Monde",
            "Le Parisien",
            "Open Source",
            "The Guardian",
        }
        people: list[str] = []
        for match in matches:
            cleaned = re.sub(r"\s+", " ", match).strip(" .,:;()[]")
            if not cleaned or cleaned in blocked:
                continue
            if cleaned.lower().startswith(("la ", "le ", "les ", "un ", "une ")):
                continue
            if cleaned not in people:
                people.append(cleaned)
            if len(people) >= 5:
                break
        return people

    def _score_feuilleton_item(self, item: dict[str, object], interests: list[str]) -> int:
        text = f"{item.get('title', '')} {item.get('summary', '')}".lower()
        score = 5
        score += self._interest_score(text, interests)
        score += sum(1 for term in self.FEUILLETON_COMIC_TERMS if term in text)
        score += 2 if item.get("named_people") else 0
        topic_tags = item.get("topic_tags") or []
        if "politics" in topic_tags:
            score += 2
        if "culture" in topic_tags or "daily_life" in topic_tags:
            score += 1
        return score

    def _cluster_feuilleton_items(self, items: list[dict[str, object]]) -> list[dict[str, object]]:
        clusters: dict[str, list[dict[str, object]]] = {}
        for item in items:
            key = self._feuilleton_cluster_key(item)
            clusters.setdefault(key, []).append(item)

        ranked: list[dict[str, object]] = []
        for key, cluster_items in clusters.items():
            score = len(cluster_items) * 3
            score += max(self._score_feuilleton_item(item, []) for item in cluster_items)
            ranked.append({"key": key, "score": score, "items": cluster_items})
        ranked.sort(key=lambda cluster: int(cluster["score"]), reverse=True)
        return ranked

    def _feuilleton_cluster_key(self, item: dict[str, object]) -> str:
        named_people = item.get("named_people") or []
        if named_people:
            return str(named_people[0]).lower()
        text = f"{item.get('title', '')} {item.get('summary', '')}".lower()
        tokens = [
            token
            for token in re.findall(r"[a-zA-ZÀ-ÿ']+", text)
            if len(token) >= 5
            and token not in self.LANGUAGE_STOPWORDS.get("fr", set())
            and token not in {"france", "français", "française", "depuis", "après", "avant"}
        ]
        return " ".join(tokens[:3]) or str(item.get("source_id") or "misc")

    def _feuilleton_summary_fr(
        self,
        selected: dict[str, object],
        supporting_items: list[dict[str, object]],
    ) -> str:
        title = str(selected.get("title") or "").strip()
        summary = str(selected.get("summary") or "").strip()
        people = selected.get("named_people") or []
        people_sentence = f" Personnes citées: {', '.join(str(person) for person in people[:3])}." if people else ""
        support = ""
        if supporting_items:
            outlets = ", ".join(
                str(item.get("source") or "source française")
                for item in supporting_items[:2]
            )
            support = f" Le sujet apparaît aussi dans {outlets}."
        if summary and summary.lower() != title.lower():
            return f"{title}. {summary}{people_sentence}{support}".strip()
        return f"{title}.{people_sentence}{support}".strip()

    def _format_feuilleton_seed_digest(
        self,
        selected: dict[str, object],
        supporting_items: list[dict[str, object]],
        satire_refs: list[dict[str, object]],
    ) -> str:
        lines = [
            "Sujet du jour:",
            f"- {selected.get('title', 'Actualité française')} ({selected.get('source', 'source française')})",
        ]
        summary = selected.get("summary")
        if summary:
            lines.append(f"Résumé: {summary}")
        named_people = selected.get("named_people") or []
        if named_people:
            lines.append(f"Personnes citées: {', '.join(str(person) for person in named_people[:5])}")
        if supporting_items:
            lines.append("Échos:")
            for item in supporting_items[:3]:
                lines.append(f"- {item.get('title')} ({item.get('source')})")
        if satire_refs:
            lines.append("Références satiriques récentes (ton seulement, pas faits):")
            for item in satire_refs[:3]:
                lines.append(f"- {item.get('title')} ({item.get('source')})")
        return "\n".join(lines)

    def _normalize_language(self, language: str | None) -> str:
        if not language:
            return "fr"
        base = language.lower().split("-")[0].strip()
        if base in self.LANGUAGE_CONFIG:
            return base
        return "fr"

    def _normalize_interests(self, interests: list[str] | None) -> list[str]:
        if not interests:
            return []
        return [item.strip() for item in interests if item and item.strip()]

    async def _fetch_live_items(
        self,
        interests: list[str],
        *,
        target_language: str,
        limit: int,
    ) -> list[dict[str, str]]:
        items: list[dict[str, str]] = []

        # 1) Optional Substack RSS feeds configured via env (prioritized for immersion feeds)
        substack_items = await self._fetch_substack_feeds(
            interests,
            target_language=target_language,
            limit=limit + 4,
        )
        items.extend(substack_items)

        # 2) Google News RSS (fallback/fill)
        google_items = await self._fetch_google_news(
            interests,
            target_language=target_language,
            limit=limit,
        )
        items.extend(google_items)

        deduped: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for item in items:
            key = (item.get("title", "").lower(), item.get("url", ""))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)

        if not interests:
            return deduped[:limit]

        scored_items: list[tuple[int, dict[str, str]]] = []
        for item in deduped:
            score = self._item_interest_score(item, interests)
            scored_items.append((score, item))

        matched_items = [entry for entry in scored_items if entry[0] > 0]
        if matched_items:
            matched_items.sort(key=lambda value: value[0], reverse=True)
            return [item for _, item in matched_items[:limit]]

        # If strict matching yields nothing, keep language-filtered fallback.
        return deduped[:limit]

    async def _fetch_google_news(
        self,
        interests: list[str],
        *,
        target_language: str,
        limit: int,
    ) -> list[dict[str, str]]:
        cfg = self.LANGUAGE_CONFIG.get(target_language, self.LANGUAGE_CONFIG["fr"])
        query_terms = interests[:3] if interests else self.DEFAULT_QUERY_TERMS.get(target_language, self.DEFAULT_QUERY_TERMS["fr"])
        formatted_terms: list[str] = []
        for term in query_terms:
            cleaned = term.strip().replace('"', "")
            if not cleaned:
                continue
            formatted_terms.append(f'"{cleaned}"' if " " in cleaned else cleaned)
        query = " OR ".join(formatted_terms) if formatted_terms else "actualites"
        url = (
            f"{self.GOOGLE_NEWS_RSS}?q={quote_plus(query)}"
            f"&hl={quote_plus(cfg['hl'])}&gl={quote_plus(cfg['gl'])}&ceid={quote_plus(cfg['ceid'])}"
        )
        raw_items = await self._fetch_rss_items(
            url,
            source_hint="Google News",
            language=target_language,
            limit=limit,
        )
        filtered = [
            item for item in raw_items
            if self._looks_like_language(
                f"{item.get('title', '')} {item.get('summary', '')}",
                target_language,
            )
        ]
        for item in filtered:
            item["source_type"] = "news"
        if interests:
            matched = [
                item
                for item in filtered
                if self._matches_interests(
                    f"{item.get('title', '')} {item.get('summary', '')}",
                    interests,
                )
            ]
            if matched:
                return matched[:limit]
        return filtered[:limit]

    async def _fetch_substack_feeds(
        self,
        interests: list[str],
        *,
        target_language: str,
        limit: int,
    ) -> list[dict[str, str]]:
        feed_urls = [url.strip() for url in settings.SUBSTACK_FEED_URLS.split(",") if url.strip()]
        if not feed_urls:
            return []

        results: list[dict[str, str]] = []
        for feed_url in feed_urls[:5]:
            try:
                feed_items = await self._fetch_rss_items(
                    feed_url,
                    source_hint="Substack",
                    language=target_language,
                    limit=limit,
                )
            except Exception as exc:
                logger.debug("Substack feed fetch failed", url=feed_url, error=str(exc))
                continue

            language_filtered = [
                item for item in feed_items
                if self._looks_like_language(
                    f"{item.get('title', '')} {item.get('summary', '')}",
                    target_language,
                )
            ]
            for item in language_filtered:
                item["source_type"] = "substack"

            if interests:
                language_filtered.sort(
                    key=lambda item: self._item_interest_score(item, interests),
                    reverse=True,
                )
                results.extend(language_filtered)
            else:
                results.extend(language_filtered)

            if len(results) >= limit:
                break
        return results[:limit]

    async def _fetch_rss_items(
        self,
        url: str,
        *,
        source_hint: str,
        language: str,
        limit: int,
    ) -> list[dict[str, str]]:
        response = await self.client.get(
            url,
            headers={
                "User-Agent": "ConversationalLanguageLearningBot/1.0 (+https://localhost)",
                "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
                "Accept-Language": "en-US,en;q=0.8",
            },
        )
        response.raise_for_status()
        return self._parse_rss_items(
            response.text,
            source_hint=source_hint,
            language=language,
            limit=limit,
        )

    def _parse_rss_items(
        self,
        xml_text: str,
        *,
        source_hint: str,
        language: str,
        limit: int,
    ) -> list[dict[str, str]]:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            logger.debug("Failed to parse feed XML", source=source_hint, error=str(exc))
            return []

        items: list[dict[str, str]] = []

        feed_title = self._clean_text(
            root.findtext("./channel/title")
            or root.findtext("{*}title")
            or source_hint
        )

        rss_items = root.findall(".//item")
        if rss_items:
            for item in rss_items:
                title = self._clean_text(
                    item.findtext("title")
                    or item.findtext("{*}title")
                    or ""
                )
                link = (
                    item.findtext("link")
                    or item.findtext("{*}link")
                    or ""
                ).strip()
                source = self._clean_text(
                    item.findtext("source")
                    or item.findtext("{*}source")
                    or (feed_title if source_hint.lower() == "substack" else source_hint)
                )
                description = self._clean_text(
                    item.findtext("description")
                    or item.findtext("{*}description")
                    or item.findtext("{*}summary")
                    or item.findtext("{*}encoded")
                    or ""
                )

                if not title or not link:
                    continue

                if source_hint.lower() == "substack" and "substack" not in source.lower():
                    source = f"{source} (Substack)".strip()

                items.append(
                    {
                        "title": title,
                        "url": link,
                        "source": source or source_hint,
                        "summary": description[:220],
                        "language": language,
                    }
                )
                if len(items) >= limit:
                    break
            return items

        # Fallback: Atom parsing (common for some feeds)
        for entry in root.findall(".//{*}entry"):
            title = self._clean_text(entry.findtext("{*}title") or "")
            link = ""
            for link_node in entry.findall("{*}link"):
                href = (link_node.attrib.get("href") or "").strip()
                rel = (link_node.attrib.get("rel") or "").strip().lower()
                if not href:
                    continue
                if not link or rel in {"alternate", ""}:
                    link = href
                if rel == "alternate":
                    break
            description = self._clean_text(
                entry.findtext("{*}summary")
                or entry.findtext("{*}content")
                or ""
            )
            source = feed_title if source_hint.lower() == "substack" else source_hint
            if source_hint.lower() == "substack" and source and "substack" not in source.lower():
                source = f"{source} (Substack)"

            if not title or not link:
                continue

            items.append(
                {
                    "title": title,
                    "url": link,
                    "source": source or source_hint,
                    "summary": description[:220],
                    "language": language,
                }
            )
            if len(items) >= limit:
                break

        return items

    def _clean_text(self, value: str) -> str:
        raw = html.unescape(value or "")
        raw = re.sub(r"<[^>]+>", " ", raw)
        raw = re.sub(r"\s+", " ", raw)
        return raw.strip()

    def _matches_interests(self, text: str, interests: list[str]) -> bool:
        return self._interest_score(text, interests) > 0

    def _item_interest_score(self, item: dict[str, str], interests: list[str]) -> int:
        text_blob = f"{item.get('title', '')} {item.get('summary', '')}"
        score = self._interest_score(text_blob, interests)
        if item.get("source_type") == "substack":
            # Small boost to ensure configured Substack feeds appear when relevant.
            score += 1
        return score

    def _interest_score(self, text: str, interests: list[str]) -> int:
        haystack = (text or "").lower()
        score = 0
        for interest in interests:
            raw = (interest or "").strip().lower()
            if not raw:
                continue
            words = re.findall(r"[a-zA-Z0-9À-ÿ']+", raw)
            if not words:
                continue
            pattern = r"\b" + r"\s+".join(re.escape(word) for word in words) + r"\b"
            if re.search(pattern, haystack):
                score += max(1, len(words))
        return score

    def _looks_like_language(self, text: str, target_language: str) -> bool:
        stopwords = self.LANGUAGE_STOPWORDS.get(target_language)
        if not stopwords:
            return True
        tokens = re.findall(r"[a-zA-ZÀ-ÿ']+", (text or "").lower())
        if not tokens:
            return False
        matches = sum(1 for token in tokens if token in stopwords)
        if len(tokens) <= 6:
            return matches >= 1
        return matches >= 2

    def _format_items_as_digest(self, items: list[dict[str, str]]) -> str:
        lines: list[str] = []
        for item in items[:4]:
            title = item.get("title", "Untitled")
            source = item.get("source", "Unknown source")
            url = item.get("url", "")
            summary = item.get("summary", "")
            if summary:
                lines.append(f"- {title} ({source}): {summary} [Link: {url}]")
            else:
                lines.append(f"- {title} ({source}) [Link: {url}]")
        return "\n".join(lines)

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=4))
    async def _query_perplexity(self, interests: list[str], *, target_language: str) -> str | None:
        """Fallback summarization via Perplexity when RSS is unavailable."""
        if not self.api_key:
            return None

        topics = ", ".join(interests) if interests else "general world events, technology, and culture"
        system_prompt = (
            "You are a helpful news assistant. "
            "Provide a concise summary of 3 current topics, each with one line."
        )
        user_prompt = (
            f"Give me fresh conversation starters about: {topics}. "
            f"Focus on concrete real-world developments and write in {target_language}."
        )

        response = await self.client.post(
            self.PERPLEXITY_URL,
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": "llama-3.1-sonar-small-128k-online",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    async def close(self) -> None:
        await self.client.aclose()
