"""Security regressions for user-supplied story import URLs."""

from __future__ import annotations

import pytest

from app.services.content_import import ContentImportError, ContentImportService


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "http://127.0.0.1/admin",
        "http://[::1]/admin",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.1.2.3/internal",
        "https://user:password@93.184.216.34/article",
        "https://93.184.216.34:8443/article",
    ],
)
def test_article_import_rejects_non_public_targets(url: str):
    with pytest.raises(ContentImportError):
        ContentImportService._validate_public_article_url(url)


def test_youtube_detection_requires_an_exact_supported_hostname():
    assert ContentImportService._is_youtube_url(
        "https://www.youtube.com/watch?v=abcdefghijk"
    )
    assert ContentImportService._is_youtube_url(
        "https://youtu.be/abcdefghijk"
    )
    assert not ContentImportService._is_youtube_url(
        "https://youtube.com.attacker.example/watch?v=abcdefghijk"
    )
    assert not ContentImportService._is_youtube_url(
        "javascript:youtube.com/watch?v=abcdefghijk"
    )


def test_article_redirects_are_revalidated_before_following(monkeypatch):
    calls: list[str] = []

    class RedirectResponse:
        status_code = 302
        headers = {"Location": "http://127.0.0.1/private"}
        encoding = "utf-8"

        def raise_for_status(self) -> None:
            pass

        def iter_content(self, chunk_size: int):  # type: ignore[no-untyped-def]
            return iter(())

        def close(self) -> None:
            pass

    def fake_get(url: str, **kwargs):  # type: ignore[no-untyped-def]
        calls.append(url)
        return RedirectResponse()

    monkeypatch.setattr(
        "app.services.content_import.requests.get",
        fake_get,
    )

    with pytest.raises(ContentImportError, match="Private or non-public"):
        ContentImportService._fetch_public_article(
            "https://93.184.216.34/article",
            headers={},
        )

    assert calls == ["https://93.184.216.34/article"]


def test_article_download_has_a_hard_size_limit(monkeypatch):
    class LargeResponse:
        status_code = 200
        headers = {"Content-Type": "text/html"}
        encoding = "utf-8"

        def raise_for_status(self) -> None:
            pass

        def iter_content(self, chunk_size: int):  # type: ignore[no-untyped-def]
            return iter((b"123456", b"789012"))

        def close(self) -> None:
            pass

    monkeypatch.setattr(ContentImportService, "ARTICLE_MAX_BYTES", 10)
    monkeypatch.setattr(
        "app.services.content_import.requests.get",
        lambda *args, **kwargs: LargeResponse(),
    )

    with pytest.raises(ContentImportError, match="2 MB import limit"):
        ContentImportService._fetch_public_article(
            "https://93.184.216.34/article",
            headers={},
        )
