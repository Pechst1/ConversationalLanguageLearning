"""Service for fetching live content (news/Substack) for conversation context."""
from __future__ import annotations

import html
import re
from urllib.parse import quote_plus

import httpx
from defusedxml import ElementTree as DefusedET
from defusedxml.common import DefusedXmlException
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.services.revue.policy import SENSITIVE_TERMS
from app.utils.cache import build_cache_key, cache_backend

#: WP-119 phase 5: the two entry points left from the pre-Revue news path. Legacy — no new
#: callers; new consumers read an ``EditorialDossier`` (``app.services.revue``). Behaviour is
#: unchanged until their callers move.
#: - ``NewsService.fetch_news_context`` — ``app/api/v1/endpoints/sessions.py``,
#:   ``app/services/auto_context_service.py`` (and ``fetch_news_digest``, which wraps it).
#: - ``NewsService.fetch_france_context`` — ``app/services/missions.py`` (mission source snapshot).
LEGACY_ENTRY_POINTS: dict[str, tuple[str, ...]] = {
    "fetch_news_context": ("app/api/v1/endpoints/sessions.py", "app/services/auto_context_service.py"),
    "fetch_france_context": ("app/services/missions.py",),
}


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
            # WP-119 §12.3: teasers and open articles fetch; paywalled pages give the chapô only.
            "fetch_policy": "allows",
        },
        {
            "id": "rfi_france",
            "name": "RFI",
            "url": "https://www.rfi.fr/fr/france/rss",
            "region_tags": ["france"],
            "topic_tags": ["society", "politics"],
            # WP-119 §12.3: articles fetch; robots.txt allows /fr/.
            "fetch_policy": "allows",
        },
        {
            "id": "france24_france",
            "name": "France 24",
            "url": "https://www.france24.com/fr/france/rss",
            "region_tags": ["france"],
            "topic_tags": ["society", "politics"],
            # WP-119 §12.3: robots.txt and bot wall refuse article fetches (WP-119 §12.3): RSS only.
            "fetch_policy": "refuses",
        },
        {
            "id": "franceinfo_france",
            "name": "Franceinfo",
            "url": "https://www.francetvinfo.fr/france.rss",
            "region_tags": ["france", "paris"],
            "topic_tags": ["society", "daily_life"],
            # WP-119 §12.3: articles fetch.
            "fetch_policy": "allows",
        },
        # WP-119 phase 3 «Le kiosque» (§4.1): culture, gastronomy and sport feeds for the
        # weekly intake's topic spread. ``fetch_policy``: may the intake fetch the article page
        # (robots.txt is still checked on every fetch)? "refuses" = build from the RSS teaser.
        {
            "id": "franceinfo_culture",
            "name": "Franceinfo",
            "url": "https://www.francetvinfo.fr/culture.rss",
            "region_tags": ["france", "paris"],
            "topic_tags": ["culture"],
            "fetch_policy": "allows",
        },
        {
            "id": "franceinfo_sports",
            "name": "Franceinfo",
            "url": "https://www.francetvinfo.fr/sports.rss",
            "region_tags": ["france"],
            "topic_tags": ["sport"],
            "fetch_policy": "allows",
        },
        {
            "id": "le_monde_culture",
            "name": "Le Monde",
            "url": "https://www.lemonde.fr/culture/rss_full.xml",
            "region_tags": ["france", "paris"],
            "topic_tags": ["culture"],
            # Teasers fetch; paywalled pages give the chapô only.
            "fetch_policy": "allows",
        },
        {
            "id": "le_monde_gastronomie",
            "name": "Le Monde",
            "url": "https://www.lemonde.fr/gastronomie/rss_full.xml",
            "region_tags": ["france"],
            "topic_tags": ["food"],
            "fetch_policy": "allows",
        },
        {
            "id": "rfi_culture",
            "name": "RFI",
            "url": "https://www.rfi.fr/fr/culture/rss",
            "region_tags": ["france"],
            "topic_tags": ["culture"],
            "fetch_policy": "allows",
        },
        {
            "id": "lequipe_une",
            "name": "L'Équipe",
            "url": "https://dwh.lequipe.fr/api/edito/rss?path=/",
            "region_tags": ["france"],
            "topic_tags": ["sport"],
            # WP-119 §12.3: live pages refuse bots; RSS teaser only.
            "fetch_policy": "refuses",
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
    FEUILLETON_SENSITIVE_TERMS = SENSITIVE_TERMS
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
        Legacy (WP-119 phase 5, see ``LEGACY_ENTRY_POINTS``): called by
        endpoints/sessions.py and auto_context_service.py only.

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
        """Return a France-specific, attributed source snapshot for missions.

        Legacy (WP-119 phase 5, see ``LEGACY_ENTRY_POINTS``): called by missions.py only.
        """
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

    # kept for revue.intake (WP-119 phase 5 removed the daily feuilleton seed; §2 keeps this)
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

    # kept for revue.intake (WP-119 phase 5 removed the daily feuilleton seed; §2 keeps this)
    def _is_sensitive_for_feuilleton(self, item: dict[str, object]) -> bool:
        text = f"{item.get('title', '')} {item.get('summary', '')}".lower()
        return any(term in text for term in self.FEUILLETON_SENSITIVE_TERMS)

    # kept for revue.intake (WP-119 phase 5 removed the daily feuilleton seed; §2 keeps this)
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

    # kept for revue.intake (WP-119 phase 5 removed the daily feuilleton seed; §2 keeps this)
    def _clean_feuilleton_seed_item(self, item: dict[str, object]) -> dict[str, object]:
        cleaned = dict(item)
        cleaned["title"] = self._clean_feuilleton_news_text(cleaned.get("title"))
        cleaned["summary"] = self._clean_feuilleton_news_text(cleaned.get("summary"))
        return cleaned

    # kept for revue.intake (WP-119 phase 5 removed the daily feuilleton seed; §2 keeps this)
    def _clean_feuilleton_news_text(self, value: object) -> str:
        text = self._clean_text(str(value or ""))
        if not text:
            return ""
        text = re.sub(r"\b([mts]a)(col[eè]re|colere)\b", r"\1 colère", text, flags=re.IGNORECASE)
        text = re.sub(r"(?:^|[\s.;:!?])I(?=$|[\s.;:!?])", " ", text)
        text = re.sub(r"(?:^|\s)Personnes cit[ée]es?\s*:\s*[^.]+\.?", " ", text, flags=re.IGNORECASE)
        text = re.sub(r"\s+([,.;:!?])", r"\1", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip(" .;:")

    # kept: _cluster_feuilleton_items scores with it; taste belongs to the consumer (§2.7)
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

    # kept for revue.intake (WP-119 phase 5 removed the daily feuilleton seed; §2 keeps this)
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

    # kept for revue.intake (WP-119 phase 5 removed the daily feuilleton seed; §2 keeps this)
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
            root = DefusedET.fromstring(xml_text)
        except (DefusedET.ParseError, DefusedXmlException) as exc:
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
