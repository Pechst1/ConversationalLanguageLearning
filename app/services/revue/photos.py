"""«Papier · photos» (owner, 2026-11-20): real photos of what a Papier story is about.

«I don't know why we only have one image. It'd be nice to have maybe even photos.» A story's
painted picture (WP-119 §8.4) stays its first picture; this module adds up to
``REVUE_PHOTOS_PER_STORY`` real photos from Wikimedia Commons, found once per story at the
morning intake (``app/tasks/revue.py``) and shown in the story's gallery with their credit.

* :func:`subjects_for` derives what to search for from the dossier's own fields, without a model
  call: its named places first (``entities`` of kind ``place``, those the stage's places name
  first; else a place's map label from ``geo``), then the one object the story is about
  (``vignette_object_fr``) and the words its picture shows (``visual.words``). A typed, private
  place («un vignoble en Bourgogne») is never searched: a photo of *a* vineyard is not the place.
  People are never a subject.
* :func:`find_photos` asks the Commons API once per subject (``generator=search`` in the File
  namespace, ``prop=imageinfo`` with a 1280 px thumbnail), within one 6 s budget for the story,
  one try, a generic User-Agent; any failure means no photos, never a failed dossier.
* :func:`photo_from_page` keeps a file only when it is a photo (JPEG or WebP), landscape or
  square, at least :data:`MIN_WIDTH` px wide, under a licence of the allow-list (CC0, public
  domain, CC BY, CC BY-SA — never fair use, never NC or ND), with an author, and not a picture of
  a person (:func:`is_person_picture`: ``policy.PHOTO_PERSON_WORDS``, a person the dossier names,
  Commons' personality-rights mark). The rule «never a portrait or a likeness» stays.
* :func:`ensure_photos` stores what was found in ``revue_story_media`` (``kind="photo"``) and
  marks the dossier row (``checks["photos"]``) so a story is searched once. The image is
  hot-linked from upload.wikimedia.org (Commons allows it); no bytes are copied.
* :func:`gallery_for` is what the stage sends: the story's painted picture, its other painted
  shots (``REVUE_PICTURES_PER_STORY``), then its photos (only while ``REVUE_PHOTOS_ENABLED``).
"""

from __future__ import annotations

import html
import re
import time
from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

import httpx
from loguru import logger

from app.config import settings
from app.services.revue import policy

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.schemas.revue import RvPicture
    from app.services.revue.dossier import EditorialDossier

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
#: Wikimedia asks for a descriptive User-Agent; this one names the app only (no person, no address).
USER_AGENT = "LAtelier-LePapier/1.0 (French-learning app; story photos from Wikimedia Commons; python-httpx)"
#: One budget for a story's whole search (every subject), one try each.
TIMEOUT_SECONDS = 6.0
#: The thumbnail Commons scales for us (``iiurlwidth``); the gallery never needs more.
THUMB_WIDTH = 1280
#: A photo narrower than this (the original file) is refused.
MIN_WIDTH = 1024
#: How many search hits one subject looks at.
SEARCH_LIMIT = 10
PHOTO_MIMES = frozenset({"image/jpeg", "image/webp"})
#: The credit every photo prints, French in every chrome language (like «Illustration · Le Papier»).
CREDIT_TEMPLATE = "Photo · {author} · {licence} · Wikimedia Commons"
ILLUSTRATION_CREDIT_FR = "Illustration · Le Papier"
_EXTMETADATA = (
    "LicenseShortName|License|LicenseUrl|Artist|Credit|Categories|ImageDescription|ObjectName|NonFree|Restrictions|UsageTerms"
)
_CC0_URL = "https://creativecommons.org/publicdomain/zero/1.0/"
_NO_AUTHOR = frozenset({
    "unknown", "unknown author", "anonymous", "anonyme", "auteur inconnu", "inconnu", "unbekannt", "n/a", "see below",
})
_ARTICLE = re.compile(r"^(?:l['’]\s*|(?:le|la|les|un|une|des|du|de la|de l['’])\s+)", re.IGNORECASE)


# ---------------------------------------------------------------------------
# What to search for
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Subject:
    """One thing to search Commons for. ``caption_fr``: what a photo of it may be captioned
    (a named place's name, from the dossier), when the file's own metadata names it too."""

    query: str
    kind: Literal["place", "object"]
    caption_fr: str | None = None


def _fold(text: str | None) -> list[str]:
    return policy._tokens(text or "")  # noqa: SLF001 - the policy's own accent-folded tokens


def _bare(text: str) -> str:
    """«une urne» → «urne»; whitespace folded."""

    value = re.sub(r"\s+", " ", str(text or "")).strip().rstrip(" .;,:")
    return _ARTICLE.sub("", value).strip()


def subjects_for(dossier: EditorialDossier, limit: int | None = None) -> list[Subject]:
    """Up to ``limit`` subjects, deterministic: named places (those the stage's places name
    first), a place's map label when no entity names it, then the story's object and the words
    its picture shows. A person is never a subject."""

    named = [entity.name.strip() for entity in dossier.entities if entity.kind == "place" and entity.name.strip()]
    places_text = [" ".join(_fold(f"{place.name_fr} {place.brief}")) for place in dossier.places]
    subjects: list[Subject] = []
    seen: set[str] = set()
    people = {" ".join(_fold(name)) for name in dossier.person_names()}

    def add(query: str, kind: Literal["place", "object"], caption: str | None = None) -> None:
        key = " ".join(_fold(query))
        if not key or key in seen or key in people:
            return
        seen.add(key)
        subjects.append(Subject(query=query, kind=kind, caption_fr=caption))

    def named_in(text: str) -> list[str]:
        return [name for name in named if f" {' '.join(_fold(name))} " in f" {text} "]

    story = f" {' '.join(_fold(' '.join([dossier.title_fr, dossier.summary_fr, *(c.fr for c in dossier.claims)])))} "

    def told(label: str) -> bool:
        """The story itself names the place (first real run: the budget story's stage was the Arc
        de Triomphe, and Commons gave a night view of the Arc for a story about pensions)."""

        head = " ".join(_fold(label.split(",")[0]))
        return bool(head) and f" {head} " in story

    for place, text in zip(dossier.places, places_text, strict=True):
        hits = named_in(text)
        for name in hits:
            add(name, "place", name)
        if (not hits and place.geo is not None and place.geo.precision in {"exact", "city"}
                and told(place.geo.label_fr)):
            add(place.geo.label_fr, "place", place.geo.label_fr)
    for name in named:
        add(name, "place", name)
    if dossier.vignette_object_fr:
        add(_bare(dossier.vignette_object_fr), "object")
    if dossier.visual is not None:
        for word in dossier.visual.words:
            add(_bare(word.fr), "object")
    return subjects if limit is None else subjects[: max(0, limit)]


# ---------------------------------------------------------------------------
# What a Commons file must be
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Photo:
    """A Commons photo the gallery may show (a ``revue_story_media`` row of kind ``photo``)."""

    page_url: str
    image_url: str
    width: int
    height: int
    licence: str
    licence_url: str | None
    author: str
    credit_fr: str
    subject: str
    caption_fr: str | None = None


def _meta(info: dict[str, Any], key: str) -> str:
    entry = (info.get("extmetadata") or {}).get(key) or {}
    value = entry.get("value") if isinstance(entry, dict) else entry
    return str(value or "")


def _plain(value: str) -> str:
    """Commons metadata is HTML: tags dropped, entities decoded, whitespace folded."""

    text = re.sub(r"<[^>]+>", " ", value or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _https(url: str) -> str | None:
    """A licence link as the gallery may open it: https only («http://creativecommons.org/…» and
    «//creativecommons.org/…» are upgraded; anything else is dropped)."""

    url = url.strip()
    if url.startswith("//"):
        url = "https:" + url
    elif url.startswith("http://"):
        url = "https://" + url[len("http://"):]
    return url if url.startswith("https://") else None


def licence_of(info: dict[str, Any]) -> tuple[str, str | None] | None:
    """(short name, licence URL) when the file's licence is on the allow-list — CC0, public
    domain, CC BY, CC BY-SA (any version) — else ``None``: fair use, non-free, NC, ND, GFDL-only
    or anything unknown is refused."""

    if _plain(_meta(info, "NonFree")).lower() in {"true", "1", "yes"}:
        return None
    short = _plain(_meta(info, "LicenseShortName"))
    code = _plain(_meta(info, "License")).lower()
    url = _https(_plain(_meta(info, "LicenseUrl")))
    words = set(re.split(r"[^a-z0-9.]+", f"{short} {code}".lower()))
    if not short and not code:
        return None
    if {"nc", "nd"} & words or "fair use" in f"{short} {code}".lower():
        return None
    if code == "cc0" or short.lower().startswith("cc0"):
        return "CC0", url or _CC0_URL
    if code == "pd" or code.startswith("pd-") or short.lower().startswith(("public domain", "domaine public")):
        return "Domaine public", url
    name = _cc_name(code) or _cc_name(short)
    return (name, url) if name else None


def _cc_name(text: str) -> str | None:
    """«cc-by-sa-4.0» or «CC BY-SA 4.0» → «CC BY-SA 4.0»; anything but CC BY / CC BY-SA → ``None``."""

    match = re.fullmatch(
        r"cc[- ]by(?P<sa>[- ]sa)?(?:[- ](?P<version>\d(?:\.\d)?))?(?:[- ](?P<port>[a-z]{2,3}))?", text.strip().lower()
    )
    if match is None:
        return None
    name = "CC BY-SA" if match["sa"] else "CC BY"
    if match["version"]:
        name += f" {match['version']}"
    if match["port"]:
        name += f" {match['port']}"
    return name


def author_of(info: dict[str, Any]) -> str | None:
    """The file's author as printed in its credit (HTML stripped), or ``None`` when Commons
    names nobody (an unknown author is no credit)."""

    author = _plain(_meta(info, "Artist"))
    if not author or author.lower().strip(" .") in _NO_AUTHOR:
        return None
    return author if len(author) <= 120 else author[:119].rstrip() + "…"


def credit_line(author: str, licence: str) -> str:
    return CREDIT_TEMPLATE.format(author=author, licence=licence)


def _described(page: dict[str, Any], info: dict[str, Any]) -> str:
    categories = _plain(_meta(info, "Categories")).replace("|", " ")
    return " ".join(
        part for part in (
            str(page.get("title") or ""), _plain(_meta(info, "ObjectName")), _plain(_meta(info, "ImageDescription")), categories,
        ) if part
    )


def is_person_picture(page: dict[str, Any], info: dict[str, Any], dossier: EditorialDossier | None = None) -> bool:
    """A picture of a person: Commons' personality-rights mark, a :data:`policy.PHOTO_PERSON_WORDS`
    word in its title, description or categories, or a person the dossier names."""

    if "personality" in _plain(_meta(info, "Restrictions")).lower():
        return True
    text = _described(page, info)
    if policy.photo_person_hits(text):
        return True
    if dossier is not None:
        from app.services.revue.checks import person_names_in

        if person_names_in(text, dossier):
            return True
    return False


#: A chart, a diagram, a map or a logo saved as a JPEG is not a photo (first real run: «budget» kept
#: the Ukrainian defence budget's infographic for a story on the French budget).
_GRAPHICS = re.compile(
    r"(?<![\w-])(?:infographics?|information graphics|diagrams?|charts?|pie charts?|logos?|maps?|"
    r"infographies?|diagrammes?|graphiques?)(?![\w-])",
    re.IGNORECASE,
)


def photo_from_page(
    page: dict[str, Any], subject: Subject, dossier: EditorialDossier | None = None,
) -> tuple[Photo | None, str]:
    """The page as a :class:`Photo`, or ``None`` and the reason it was refused (``no_info``,
    ``not_a_photo``, ``portrait_orientation``, ``too_small``, ``licence``, ``no_author``,
    ``person``)."""

    infos = page.get("imageinfo") or []
    info = infos[0] if infos else None
    if not isinstance(info, dict):
        return None, "no_info"
    if str(info.get("mime") or "").lower() not in PHOTO_MIMES:
        return None, "not_a_photo"
    width, height = int(info.get("width") or 0), int(info.get("height") or 0)
    if not width or not height or height > width:
        return None, "portrait_orientation"
    if width < MIN_WIDTH:
        return None, "too_small"
    image_url = str(info.get("thumburl") or info.get("url") or "")
    page_url = str(info.get("descriptionurl") or "")
    if not image_url.startswith("https://") or not page_url.startswith("https://"):
        return None, "no_info"
    licence = licence_of(info)
    if licence is None:
        return None, "licence"
    author = author_of(info)
    if author is None:
        return None, "no_author"
    if is_person_picture(page, info, dossier):
        return None, "person"
    if _GRAPHICS.search(_described(page, info)):
        return None, "not_a_photo"
    thumb_w = int(info.get("thumbwidth") or width)
    thumb_h = int(info.get("thumbheight") or height)
    caption = None
    if subject.caption_fr:
        wanted = _fold(subject.query)
        have = set(_fold(_described(page, info)))
        if wanted and all(token in have for token in wanted):
            caption = subject.caption_fr
    return (
        Photo(
            page_url=page_url,
            image_url=image_url,
            width=thumb_w,
            height=thumb_h,
            licence=licence[0],
            licence_url=licence[1],
            author=author,
            credit_fr=credit_line(author, licence[0]),
            subject=subject.query,
            caption_fr=caption,
        ),
        "ok",
    )


# ---------------------------------------------------------------------------
# The fetch
# ---------------------------------------------------------------------------


def search_params(subject: Subject) -> dict[str, str | int]:
    """The Commons API query for one subject: bitmaps in the File namespace, with the image
    info, a :data:`THUMB_WIDTH` thumbnail and the licence metadata."""

    return {
        "action": "query",
        "format": "json",
        "formatversion": 2,
        "generator": "search",
        "gsrsearch": f"{subject.query} filetype:bitmap",
        "gsrnamespace": 6,
        "gsrlimit": SEARCH_LIMIT,
        "prop": "imageinfo",
        "iiprop": "url|extmetadata|size|mime",
        "iiurlwidth": THUMB_WIDTH,
        "iiextmetadatafilter": _EXTMETADATA,
        "iiextmetadatalanguage": "fr",
    }


def _pages(payload: Any) -> list[dict[str, Any]]:
    pages = ((payload or {}).get("query") or {}).get("pages") or []
    if isinstance(pages, dict):  # formatversion=1
        pages = list(pages.values())
    return sorted((page for page in pages if isinstance(page, dict)), key=lambda page: int(page.get("index") or 0))


class CommonsUnavailable(RuntimeError):
    """The search failed (network, HTTP status, JSON, budget): not the same as «nothing kept»."""


def commons_client() -> httpx.Client:
    """The client the search opens itself: HTTP/2. First real run (2026-11-22): over HTTP/1.1
    every httpx request was answered 403 «Please respect our robot policy», whatever the
    User-Agent, while the same request over HTTP/2 (httpx, curl) was served."""

    return httpx.Client(http2=True, follow_redirects=True)


def find_photos(
    dossier: EditorialDossier, *, client: httpx.Client | None = None, limit: int | None = None,
    clock: Any = time.monotonic, raise_errors: bool = False,
) -> list[Photo]:
    """Up to ``limit`` (``REVUE_PHOTOS_PER_STORY``) photos for ``dossier``, one per subject, in
    subject order. One request per subject, one try, all within :data:`TIMEOUT_SECONDS`; any
    error (network, HTTP, JSON) returns no photos at all — or, with ``raise_errors``, raises
    :class:`CommonsUnavailable` so the caller can tell a failed search from an empty one."""

    wanted = int(settings.REVUE_PHOTOS_PER_STORY if limit is None else limit)
    if wanted <= 0:
        return []
    subjects = subjects_for(dossier)
    if not subjects:
        return []
    own = client is None
    http = client or commons_client()
    started = clock()
    found: list[Photo] = []
    titles: set[str] = set()
    try:
        for subject in subjects:
            if len(found) >= wanted:
                break
            left = TIMEOUT_SECONDS - (clock() - started)
            if left <= 0:
                raise TimeoutError("commons budget spent")
            response = http.get(COMMONS_API, params=search_params(subject), headers={"User-Agent": USER_AGENT}, timeout=left)
            response.raise_for_status()
            reasons: list[str] = []
            for page in _pages(response.json()):
                title = str(page.get("title") or "")
                if title in titles:
                    continue
                photo, reason = photo_from_page(page, subject, dossier)
                reasons.append(reason)
                if photo is not None:
                    found.append(photo)
                    titles.add(title)
                    break
            logger.bind(dossier=dossier.id, subject=subject.query, refused=reasons).debug("revue photos: searched")
    except Exception as exc:  # noqa: BLE001 - failure = no photos, never a failed dossier
        logger.bind(dossier=dossier.id).info("revue photos: Commons search failed ({}); no photos", type(exc).__name__)
        if raise_errors:
            raise CommonsUnavailable(type(exc).__name__) from exc
        return []
    finally:
        if own:
            http.close()
    return found


# ---------------------------------------------------------------------------
# Storing (once per story) and reading
# ---------------------------------------------------------------------------


def photos_enabled() -> bool:
    return bool(getattr(settings, "REVUE_PHOTOS_ENABLED", False))


def store_photos(db: Session, dossier_id: str, photos: Iterable[Photo]) -> int:
    """Write ``photos`` as the story's photo rows (positions 1…N); a story that has photo rows
    already keeps them. Returns how many were written. The caller commits."""

    from sqlalchemy import select

    from app.db.models.revue_story_media import RevueStoryMedia

    exists = db.scalar(
        select(RevueStoryMedia.id).where(RevueStoryMedia.dossier_id == dossier_id, RevueStoryMedia.kind == "photo").limit(1)
    )
    if exists is not None:
        return 0
    written = 0
    for position, photo in enumerate(photos, start=1):
        db.add(
            RevueStoryMedia(
                dossier_id=dossier_id[:120],
                kind="photo",
                position=position,
                image_url=photo.image_url,
                width=photo.width,
                height=photo.height,
                page_url=photo.page_url,
                licence=photo.licence[:80],
                licence_url=photo.licence_url,
                author=photo.author[:300],
                credit_fr=photo.credit_fr[:400],
                caption_fr=photo.caption_fr,
                subject=photo.subject[:200],
                cost_usd=0.0,
                flagged=False,
            )
        )
        written += 1
    return written


def ensure_photos(db: Session, period: str, *, client: httpx.Client | None = None) -> dict[str, int]:
    """Search Commons once for every dossier of ``period``'s kiosk not searched yet
    (``checks["photos"]`` records the count, ``0`` included, so a story is searched once).
    Returns dossier id → photos stored. Off while ``REVUE_PHOTOS_ENABLED`` is off.

    A search that FAILED (429, 403, network, budget) records nothing: the story is searched
    again the next morning, and the morning stops searching (Commons asked us to slow down)."""

    from sqlalchemy import select

    from app.db.models.revue_session import RevueDossier
    from app.services.revue.dossier import EditorialDossier
    from app.services.revue.leads import kiosk_periods

    if not photos_enabled():
        return {}
    out: dict[str, int] = {}
    rows = list(db.scalars(
        select(RevueDossier)
        .where(RevueDossier.period.in_(kiosk_periods(period)))
        .order_by(RevueDossier.period.desc(), RevueDossier.id.asc())
    ))
    for row in rows:
        if "photos" in (row.checks or {}):
            continue
        try:
            dossier = EditorialDossier.model_validate(row.payload)
        except Exception as exc:  # noqa: BLE001 - an unreadable row is left to the kiosk's own guard
            logger.bind(row=row.id).debug("revue photos: stored dossier unreadable ({})", exc)
            continue
        try:
            photos = find_photos(dossier, client=client, raise_errors=True)
        except CommonsUnavailable:
            break
        out[dossier.id] = store_photos(db, dossier.id, photos)
        row.checks = {**(row.checks or {}), "photos": out[dossier.id]}
        db.commit()
    return out


def _media_rows(db: Session | None, dossier_id: str) -> list[Any]:
    if db is None:
        return []
    from sqlalchemy import select

    from app.db.models.revue_story_media import RevueStoryMedia

    try:
        with db.begin_nested():  # a failed lookup must not poison the caller's transaction
            return list(db.scalars(
                select(RevueStoryMedia)
                .where(RevueStoryMedia.dossier_id == dossier_id)
                .order_by(RevueStoryMedia.kind.asc(), RevueStoryMedia.position.asc())
            ))
    except Exception as exc:  # noqa: BLE001 - a missing table (an old database) is no gallery, not a 500
        logger.debug("revue photos: media lookup failed for {} ({})", dossier_id, exc)
        return []


def gallery_for(db: Session | None, dossier: EditorialDossier) -> list[RvPicture]:
    """The story's pictures in order: its painted picture (when painted), its other painted shots
    (up to ``REVUE_PICTURES_PER_STORY``), then its Commons photos (while ``REVUE_PHOTOS_ENABLED``,
    up to ``REVUE_PHOTOS_PER_STORY``). An illustration carries no caption: the desk's caption is
    the answer of «La légende» (§8.4). With the default switches this is the painted picture alone."""

    from app.schemas.revue import RvPicture
    from app.services.revue import plates

    out: list[RvPicture] = []
    if dossier.visual is not None:
        first = plates.story_picture(db, dossier.id)
        if first is not None:
            out.append(RvPicture(kind="illustration", url=first.url, credit_fr=ILLUSTRATION_CREDIT_FR, width=1536, height=1024))
    shots = plates.pictures_per_story()
    photos_on = photos_enabled()
    if not out and not photos_on:
        return out
    rows = _media_rows(db, dossier.id) if (shots > 1 and out) or photos_on else []
    for row in rows:
        if row.kind == "illustration" and out and row.position <= shots:
            out.append(RvPicture(kind="illustration", url=row.image_url, credit_fr=row.credit_fr, width=row.width, height=row.height))
    photo_cap = max(0, int(getattr(settings, "REVUE_PHOTOS_PER_STORY", 3) or 0))
    if photos_on:
        for row in [row for row in rows if row.kind == "photo"][:photo_cap]:
            out.append(
                RvPicture(
                    kind="photo",
                    url=row.image_url,
                    width=row.width,
                    height=row.height,
                    alt_fr=row.caption_fr or "",
                    caption_fr=row.caption_fr,
                    credit_fr=row.credit_fr,
                    licence=row.licence,
                    licence_url=row.licence_url or row.page_url,
                    source_url=row.page_url,
                )
            )
    return out


__all__ = [
    "COMMONS_API",
    "MIN_WIDTH",
    "TIMEOUT_SECONDS",
    "USER_AGENT",
    "CommonsUnavailable",
    "commons_client",
    "Photo",
    "Subject",
    "author_of",
    "credit_line",
    "ensure_photos",
    "find_photos",
    "gallery_for",
    "is_person_picture",
    "licence_of",
    "photo_from_page",
    "search_params",
    "store_photos",
    "subjects_for",
]
