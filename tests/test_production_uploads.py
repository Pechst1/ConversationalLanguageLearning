import asyncio
from io import BytesIO
from types import SimpleNamespace
from zipfile import ZIP_DEFLATED, ZipFile

import httpx
import pytest
from fastapi import FastAPI, HTTPException, Request, UploadFile

from app.api.v1.endpoints import anki, stories
from app.core.uploads import ImportBodyLimitMiddleware, read_bounded_upload
from app.services.book_parser import BookParserService


def test_unknown_upload_size_reads_only_up_to_the_limit():
    source = BytesIO(b"a" * 100)
    file = UploadFile(source, filename="book.txt")
    with pytest.raises(HTTPException) as error:
        asyncio.run(read_bounded_upload(file, limit=10))
    assert error.value.status_code == 413 and source.tell() == 11


def test_known_oversized_upload_is_never_read():
    source = BytesIO(b"a" * 100)
    file = UploadFile(source, filename="cards.csv", size=100)
    with pytest.raises(HTTPException) as error:
        asyncio.run(read_bounded_upload(file, limit=10))
    assert error.value.status_code == 413 and source.tell() == 0


@pytest.mark.parametrize("content, status", [(b"", 400), (b"a" * 11, 413)])
def test_anki_rejects_invalid_uploads_without_wrapping_them_in_500(monkeypatch, content, status):
    monkeypatch.setattr(anki, "MAX_ANKI_UPLOAD_BYTES", 10)
    with pytest.raises(HTTPException) as error:
        asyncio.run(anki.import_anki_cards(file=UploadFile(BytesIO(content), filename="cards.csv"), db=None, current_user=None))
    assert error.value.status_code == status


def test_csv_text_limit_counts_utf8_bytes(monkeypatch):
    monkeypatch.setattr(anki, "MAX_ANKI_UPLOAD_BYTES", 10)
    with pytest.raises(HTTPException) as error:
        anki.import_anki_cards_text(request=SimpleNamespace(csv_content="é,é,é,é"), db=None, current_user=None)
    assert error.value.status_code == 413


def test_both_book_upload_doors_reject_before_queueing(monkeypatch):
    monkeypatch.setattr(stories, "MAX_BOOK_UPLOAD_BYTES", 10)
    for handler in (stories.upload_book, stories.upload_library_book):
        with pytest.raises(HTTPException) as error:
            asyncio.run(handler(file=UploadFile(BytesIO(b"a" * 11), filename="book.txt"), db=None, current_user=None, background_tasks=None))
        assert error.value.status_code == 413


@pytest.mark.asyncio
async def test_chunked_body_is_bounded_before_json_or_multipart_parsing():
    class SmallLimit(ImportBodyLimitMiddleware):
        def __init__(self, app, **kwargs):
            super().__init__(app, **kwargs)
            self.limits = dict.fromkeys(self.limits, 10)

    app = FastAPI()
    app.add_middleware(SmallLimit, api_prefix="/api/v1")

    @app.post("/api/v1/anki/import/text")
    async def read_body(request: Request):
        return {"size": len(await request.body())}

    async def chunks():
        yield b"a" * 6
        yield b"b" * 6

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        result = await client.post("/api/v1/anki/import/text", content=chunks())
        assert result.status_code == 413
        result = await client.post("/api/v1/anki/import/text", content=b"tiny", headers={"Content-Length": "100"})
        assert result.status_code == 413


def test_epub_expansion_is_limited_before_optional_parser_imports():
    content = BytesIO()
    with ZipFile(content, "w", ZIP_DEFLATED) as archive:
        archive.writestr("huge.html", b"a" * 40_000_001)
    with pytest.raises(ValueError, match="unpacked size"):
        BookParserService(None)._extract_epub_text(content.getvalue())
