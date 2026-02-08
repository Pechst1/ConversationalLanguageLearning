"""Service for fetching live content (news/Substack) for conversation context."""
from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
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

        # 1) Google News RSS (no API key required)
        google_items = await self._fetch_google_news(
            interests,
            target_language=target_language,
            limit=limit + 4,
        )
        items.extend(google_items)

        # 2) Optional Substack RSS feeds configured via env
        substack_items = await self._fetch_substack_feeds(
            interests,
            target_language=target_language,
            limit=limit,
        )
        items.extend(substack_items)

        deduped: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for item in items:
            key = (item.get("title", "").lower(), item.get("url", ""))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
            if len(deduped) >= limit:
                break
        return deduped

    async def _fetch_google_news(
        self,
        interests: list[str],
        *,
        target_language: str,
        limit: int,
    ) -> list[dict[str, str]]:
        cfg = self.LANGUAGE_CONFIG.get(target_language, self.LANGUAGE_CONFIG["fr"])
        query_terms = interests[:3] if interests else ["language learning", "technology", "culture"]
        query = " OR ".join(query_terms)
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

            if interests:
                filtered = [
                    item
                    for item in language_filtered
                    if self._matches_interests(
                        f"{item.get('title', '')} {item.get('summary', '')}",
                        interests,
                    )
                ]
                results.extend(filtered)
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
        response = await self.client.get(url)
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
        root = ET.fromstring(xml_text)
        items: list[dict[str, str]] = []

        for item in root.findall("./channel/item"):
            title = self._clean_text(item.findtext("title") or "")
            link = (item.findtext("link") or "").strip()
            source = self._clean_text(item.findtext("source") or source_hint)
            description = self._clean_text(item.findtext("description") or "")

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
        haystack = (text or "").lower()
        return any(interest.lower() in haystack for interest in interests)

    def _looks_like_language(self, text: str, target_language: str) -> bool:
        stopwords = self.LANGUAGE_STOPWORDS.get(target_language)
        if not stopwords:
            return True
        tokens = re.findall(r"[a-zA-ZÀ-ÿ']+", (text or "").lower())
        if not tokens:
            return False
        matches = sum(1 for token in tokens if token in stopwords)
        # Keep threshold low to avoid over-filtering short headlines.
        return matches >= 1 or len(tokens) <= 4

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
