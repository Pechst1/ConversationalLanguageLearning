"""Article text for the weekly intake (WP-119 §4.1, §12.3).

The builder anchors claims in verbatim quotes, and an RSS teaser is one or two
sentences, so the intake fetches the article page — politely:

* **robots.txt first**, with the intake's own user agent, through the stdlib
  ``urllib.robotparser`` (a 401/403 on robots.txt disallows everything, any other 4xx
  allows everything, a network failure or a timeout disallows: we fetch only what we
  could verify). One robots.txt per host per run (``robots`` cache).
* **one attempt, six seconds** for robots.txt and the page together
  (:data:`FETCH_BUDGET_SECONDS`); no retry, no backoff.
* **the registry's ``fetch_policy``** (``NewsService.FRANCE_SOURCE_REGISTRY``): a source
  that refuses bots («refuses») is never fetched; its stories are built from the teaser.
* **store only quotes and a hash.** :class:`ArticleText` holds the full text for the
  build, in memory; what the intake persists is the dossier (its quotes) and
  :attr:`ArticleText.sha256`. Nothing here writes the text anywhere.

Extraction is a paragraph extractor over BeautifulSoup's ``html.parser`` (a declared
dependency): drop scripts, navigation, asides, forms and figures, prefer ``<article>``
or ``<main>``, keep paragraphs of at least :data:`MIN_PARAGRAPH_CHARS` characters.
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx
from loguru import logger

from app.services.revue.dossier import fold

#: The whole fetch (robots.txt and the page) gets this long, once (§12.3).
FETCH_BUDGET_SECONDS = 6.0
USER_AGENT = "ConversationalLanguageLearningBot/1.0 (+https://localhost; Le Papier de Romy)"
#: Paragraphs shorter than this are bylines, captions, buttons.
MIN_PARAGRAPH_CHARS = 40
#: More than this is not an article page we want to read through.
MAX_TEXT_CHARS = 40_000

FetchStatus = Literal["fetched", "policy_refused", "robots_refused", "robots_unverified", "failed", "empty", "disabled"]

_DROP_TAGS = ("script", "style", "noscript", "nav", "header", "footer", "aside", "form", "figure", "figcaption", "button", "svg", "iframe")


@dataclass(frozen=True)
class ArticleText:
    """One article fetch. ``text`` is for the build only; persist ``sha256``, never ``text``."""

    url: str
    status: FetchStatus
    text: str = ""
    reason: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == "fetched" and bool(self.text)

    @property
    def sha256(self) -> str | None:
        return text_hash(self.text) if self.text else None


def text_hash(text: str) -> str:
    """SHA-256 of the folded text: the same article hashes the same after whitespace changes."""

    return hashlib.sha256(fold(text).encode("utf-8")).hexdigest()


def extract_text(html: str) -> str:
    """The article's paragraphs, one per line ("" when nothing readable is left)."""

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup(list(_DROP_TAGS)):
        tag.decompose()
    root = soup.find("article") or soup.find("main") or soup.body or soup
    paragraphs: list[str] = []
    for node in root.find_all(["p", "h2", "li"]):
        text = " ".join(node.get_text(" ", strip=True).split())
        if node.name == "p" and len(text) >= MIN_PARAGRAPH_CHARS:
            paragraphs.append(text)
    text = "\n".join(dict.fromkeys(paragraphs))
    return text[:MAX_TEXT_CHARS]


@dataclass
class RobotsCache:
    """One parsed robots.txt per host per intake run (``None`` = could not be verified)."""

    parsers: dict[str, RobotFileParser | None] = field(default_factory=dict)


def _robots_for(
    client: httpx.Client, url: str, *, deadline: float, cache: RobotsCache, clock: Callable[[], float] = time.monotonic
) -> RobotFileParser | None:
    parts = urlsplit(url)
    host = f"{parts.scheme}://{parts.netloc}"
    if host in cache.parsers:
        return cache.parsers[host]
    parser = RobotFileParser()
    remaining = deadline - clock()
    try:
        if remaining <= 0:
            raise httpx.TimeoutException("budget spent before robots.txt")
        response = client.get(f"{host}/robots.txt", headers={"User-Agent": USER_AGENT}, timeout=remaining)
    except httpx.HTTPError as exc:
        logger.bind(host=host).info("revue intake: robots.txt unverified ({})", exc)
        cache.parsers[host] = None
        return None
    if response.status_code in (401, 403):
        parser.disallow_all = True
    elif response.status_code >= 400:
        parser.allow_all = True
    else:
        parser.parse(response.text.splitlines())
    cache.parsers[host] = parser
    return parser


def fetch_article(
    url: str,
    *,
    fetch_policy: str | None = "allows",
    client: httpx.Client | None = None,
    robots: RobotsCache | None = None,
    budget_seconds: float = FETCH_BUDGET_SECONDS,
    enabled: bool | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> ArticleText:
    """Fetch one article page under §12.3's rules; never raises."""

    if enabled is None:
        from app.config import settings

        enabled = bool(getattr(settings, "REVUE_ARTICLE_FETCH_ENABLED", True))
    if not enabled:
        return ArticleText(url=url, status="disabled")
    if (fetch_policy or "allows") != "allows":
        return ArticleText(url=url, status="policy_refused", reason=str(fetch_policy))
    if not url.startswith(("http://", "https://")):
        return ArticleText(url=url, status="failed", reason="not_http")

    own_client = client is None
    http = client or httpx.Client(follow_redirects=True)
    cache = robots if robots is not None else RobotsCache()
    deadline = clock() + budget_seconds
    try:
        parser = _robots_for(http, url, deadline=deadline, cache=cache, clock=clock)
        if parser is None:
            return ArticleText(url=url, status="robots_unverified")
        if not parser.can_fetch(USER_AGENT, url):
            return ArticleText(url=url, status="robots_refused")
        remaining = deadline - clock()
        if remaining <= 0:
            return ArticleText(url=url, status="failed", reason="budget_spent")
        try:
            response = http.get(
                url,
                headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml", "Accept-Language": "fr-FR,fr;q=0.9"},
                timeout=remaining,
            )
        except httpx.HTTPError as exc:
            return ArticleText(url=url, status="failed", reason=type(exc).__name__)
        if response.status_code >= 400:
            return ArticleText(url=url, status="failed", reason=f"http_{response.status_code}")
        text = extract_text(response.text)
        if not text:
            return ArticleText(url=url, status="empty")
        return ArticleText(url=url, status="fetched", text=text)
    finally:
        if own_client:
            http.close()


__all__ = [
    "FETCH_BUDGET_SECONDS",
    "USER_AGENT",
    "ArticleText",
    "RobotsCache",
    "extract_text",
    "fetch_article",
    "text_hash",
]
