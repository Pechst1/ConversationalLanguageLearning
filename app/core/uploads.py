"""Bound user-controlled imports before decoding or queueing their contents."""
from fastapi import HTTPException, UploadFile, status
from starlette.responses import JSONResponse

MAX_BOOK_UPLOAD_BYTES = 10_000_000
MAX_ANKI_UPLOAD_BYTES = 20_000_000


class ImportBodyLimitMiddleware:
    """Bound multipart spooling and JSON parsing, including chunked requests."""

    def __init__(self, app, *, api_prefix: str):
        self.app = app
        self.limits = {
            f"{api_prefix}/anki/import": MAX_ANKI_UPLOAD_BYTES + 65_536,
            f"{api_prefix}/anki/import/text": MAX_ANKI_UPLOAD_BYTES + 65_536,
            f"{api_prefix}/stories/upload-book": MAX_BOOK_UPLOAD_BYTES + 65_536,
            f"{api_prefix}/stories/library/upload": MAX_BOOK_UPLOAD_BYTES + 65_536,
        }

    async def __call__(self, scope, receive, send):
        limit = self.limits.get(scope.get("path", "").rstrip("/"))
        if scope["type"] != "http" or limit is None:
            return await self.app(scope, receive, send)
        for key, value in scope.get("headers", []):
            if key.lower() == b"content-length":
                try:
                    length = int(value)
                except ValueError:
                    response = JSONResponse({"detail": "Invalid Content-Length."}, status_code=400)
                    return await response(scope, receive, send)
                if length < 0 or length > limit:
                    response = JSONResponse({"detail": "Request exceeds the import limit."}, status_code=413)
                    return await response(scope, receive, send)
        size = 0

        async def bounded_receive():
            nonlocal size
            message = await receive()
            if message["type"] == "http.request":
                size += len(message.get("body", b""))
                if size > limit:
                    raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Request exceeds the import limit.")
            return message

        await self.app(scope, bounded_receive, send)


async def read_bounded_upload(file: UploadFile, *, limit: int) -> bytes:
    """Read at most one byte beyond the limit, including clients without a size."""

    if file.size is not None and file.size > limit:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "File exceeds the upload limit.")
    content = await file.read(limit + 1)
    if len(content) > limit:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "File exceeds the upload limit.")
    if not content:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "File is empty.")
    return content
