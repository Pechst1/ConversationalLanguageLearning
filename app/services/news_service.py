"""Service for fetching current events and topic summaries for conversation context."""
from __future__ import annotations

import httpx
from datetime import timedelta
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.utils.cache import cache_backend, build_cache_key

class NewsService:
    """Fetches and summarizes news/events for conversation context."""
    
    BASE_URL = "https://api.perplexity.ai/chat/completions"
    
    def __init__(self):
        self.api_key = settings.PERPLEXITY_API_KEY
        self.client = httpx.AsyncClient(timeout=30.0)

    async def fetch_news_digest(self, interests: list[str] | None = None) -> str | None:
        """
        Fetch a digest of recent news, optionally tailored to interests.
        Returns None if API is not configured or fails.
        """
        if not self.api_key:
            logger.debug("Perplexity API key not set, skipping news fetch.")
            return None

        # Build cache key based on interests (sorted for consistency)
        interests_key = "_".join(sorted(interests)) if interests else "general"
        cache_key = build_cache_key("news_digest", interests_key)
        
        # Try cache first (cache for 4 hours)
        cached = await cache_backend.get(cache_key)
        if cached:
            return cached

        try:
            digest = await self._query_perplexity(interests)
            if digest:
                await cache_backend.set(cache_key, digest, expire=timedelta(hours=4))
            return digest
        except Exception as exc:
            logger.error(f"Failed to fetch news digest: {exc}")
            return None

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _query_perplexity(self, interests: list[str] | None) -> str:
        """Query Perplexity API for a news summary."""
        topics = ", ".join(interests) if interests else "general world events, technology, and culture"
        
        system_prompt = (
            "You are a helpful news assistant. "
            "Provide a concise, engaging summary of 3-4 distinct current events or interesting developments purely for conversational context. "
            "Focus on positive, intriguing, or significant stories. "
            "Avoid overly depressing or controversial political minutiae unless it's a major global event. "
            "Format as a simple bulleted list."
        )
        
        user_prompt = f"What are some interesting things happening right now regarding: {topics}? Keep it brief (under 150 words total)."

        response = await self.client.post(
            self.BASE_URL,
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": "llama-3.1-sonar-small-128k-online", 
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            }
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
    
    async def close(self):
        await self.client.aclose()
