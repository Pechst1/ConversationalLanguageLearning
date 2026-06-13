"""Persistence backends for generated Feuilleton images."""
from __future__ import annotations

import base64
import hashlib
import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote_to_bytes, urlparse

import httpx

from app.config import settings


_CONTENT_TYPE_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/svg+xml": ".svg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


@dataclass(frozen=True)
class DecodedImage:
    """Image bytes plus enough metadata to persist and serve them."""

    content: bytes
    content_type: str
    extension: str
    source_kind: str


def is_data_uri(value: object) -> bool:
    """Return true when a value is a data URI."""

    return isinstance(value, str) and value.strip().lower().startswith("data:")


def _extension_for_content_type(content_type: str) -> str:
    normalized = content_type.split(";", 1)[0].strip().lower() or "application/octet-stream"
    return _CONTENT_TYPE_EXTENSIONS.get(normalized) or mimetypes.guess_extension(normalized) or ".bin"


def _quote_key(key: str) -> str:
    return "/".join(quote(part) for part in key.split("/"))


def _decode_data_uri(uri: str) -> DecodedImage:
    header, separator, data = uri.partition(",")
    if separator != "," or not header.lower().startswith("data:"):
        raise ValueError("Invalid data URI image payload")
    metadata = header[5:]
    parts = [part.strip() for part in metadata.split(";") if part.strip()]
    content_type = parts[0] if parts and "/" in parts[0] else "application/octet-stream"
    if any(part.lower() == "base64" for part in parts):
        content = base64.b64decode(data)
    else:
        content = unquote_to_bytes(data)
    return DecodedImage(
        content=content,
        content_type=content_type,
        extension=_extension_for_content_type(content_type),
        source_kind="data_uri",
    )


def _extension_from_url(url: str, content_type: str) -> str:
    parsed = urlparse(url)
    suffix = Path(parsed.path).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".svg", ".webp", ".gif"}:
        return ".jpg" if suffix == ".jpeg" else suffix
    return _extension_for_content_type(content_type)


class GraphicNovelImageStorage:
    """Store generated image payloads behind stable URLs."""

    async def persist_payload(
        self,
        payload: dict[str, Any],
        *,
        scene_id: object,
        panel_index: int,
        image_role: str = "panel",
    ) -> dict[str, Any]:
        """Persist a generated image payload according to configured storage mode."""

        mode = settings.GRAPHIC_NOVEL_IMAGE_STORAGE
        if mode == "data_uri":
            return payload

        url = payload.get("url")
        if not isinstance(url, str) or not url.strip():
            return payload

        decoded = await self._decode_or_fetch(url.strip())
        if decoded is None:
            return payload

        digest = hashlib.sha256(decoded.content).hexdigest()
        key = self._object_key(
            scene_id=scene_id,
            panel_index=panel_index,
            image_role=image_role,
            digest=digest,
            extension=decoded.extension,
        )
        if mode == "local":
            persisted_url = self._store_local(key=key, image=decoded)
            backend = "local"
        elif mode == "s3":
            persisted_url = self._store_s3(key=key, image=decoded)
            backend = "s3"
        else:  # Settings validation should keep this unreachable.
            raise ValueError(f"Unsupported graphic novel image storage backend: {mode}")

        updated = dict(payload)
        updated["url"] = persisted_url
        updated["content_type"] = decoded.content_type
        updated["storage"] = {
            "backend": backend,
            "key": key,
            "content_type": decoded.content_type,
            "byte_size": len(decoded.content),
            "sha256": digest,
            "source": decoded.source_kind,
        }
        return updated

    async def _decode_or_fetch(self, url: str) -> DecodedImage | None:
        if is_data_uri(url):
            return _decode_data_uri(url)

        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return None

        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
        content_type = response.headers.get("content-type", "application/octet-stream").split(";", 1)[0]
        return DecodedImage(
            content=response.content,
            content_type=content_type,
            extension=_extension_from_url(url, content_type),
            source_kind="remote_url",
        )

    def _object_key(
        self,
        *,
        scene_id: object,
        panel_index: int,
        image_role: str,
        digest: str,
        extension: str,
    ) -> str:
        safe_role = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in image_role.lower()).strip("-")
        role = safe_role or "panel"
        return f"scenes/{scene_id}/{role}-{panel_index}-{digest[:16]}{extension}"

    def _store_local(self, *, key: str, image: DecodedImage) -> str:
        base_dir = Path(settings.GRAPHIC_NOVEL_LOCAL_IMAGE_DIR)
        path = base_dir / key
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_bytes(image.content)
        return f"{settings.GRAPHIC_NOVEL_LOCAL_IMAGE_URL_PREFIX.rstrip('/')}/{_quote_key(key)}"

    def _store_s3(self, *, key: str, image: DecodedImage) -> str:
        bucket = settings.GRAPHIC_NOVEL_IMAGE_S3_BUCKET
        if not bucket:
            raise RuntimeError("GRAPHIC_NOVEL_IMAGE_S3_BUCKET is required when image storage is s3")
        try:
            import boto3  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - optional production dependency
            raise RuntimeError("boto3 is required when GRAPHIC_NOVEL_IMAGE_STORAGE=s3") from exc

        client = boto3.client(
            "s3",
            region_name=settings.GRAPHIC_NOVEL_IMAGE_S3_REGION,
            endpoint_url=settings.GRAPHIC_NOVEL_IMAGE_S3_ENDPOINT_URL,
            aws_access_key_id=settings.GRAPHIC_NOVEL_IMAGE_S3_ACCESS_KEY_ID,
            aws_secret_access_key=settings.GRAPHIC_NOVEL_IMAGE_S3_SECRET_ACCESS_KEY,
        )
        put_kwargs: dict[str, Any] = {
            "Bucket": bucket,
            "Key": key,
            "Body": image.content,
            "ContentType": image.content_type,
            "CacheControl": "public, max-age=31536000, immutable",
        }
        if settings.GRAPHIC_NOVEL_IMAGE_S3_ACL:
            put_kwargs["ACL"] = settings.GRAPHIC_NOVEL_IMAGE_S3_ACL
        client.put_object(**put_kwargs)
        return self._s3_public_url(bucket=bucket, key=key)

    def _s3_public_url(self, *, bucket: str, key: str) -> str:
        quoted_key = _quote_key(key)
        if settings.GRAPHIC_NOVEL_IMAGE_S3_PUBLIC_BASE_URL:
            return f"{settings.GRAPHIC_NOVEL_IMAGE_S3_PUBLIC_BASE_URL.rstrip('/')}/{quoted_key}"
        if settings.GRAPHIC_NOVEL_IMAGE_S3_ENDPOINT_URL:
            return f"{settings.GRAPHIC_NOVEL_IMAGE_S3_ENDPOINT_URL.rstrip('/')}/{bucket}/{quoted_key}"
        if settings.GRAPHIC_NOVEL_IMAGE_S3_REGION:
            return f"https://{bucket}.s3.{settings.GRAPHIC_NOVEL_IMAGE_S3_REGION}.amazonaws.com/{quoted_key}"
        return f"https://{bucket}.s3.amazonaws.com/{quoted_key}"
