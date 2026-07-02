"""Celery tasks for user-owned guided reading uploads."""
from __future__ import annotations

import base64
from uuid import UUID

from app.celery_app import celery_app
from app.db.models.user import User
from app.db.session import SessionLocal
from app.services.book_library import BookLibraryService


def process_user_book_upload_inline(
    *,
    book_id: str,
    file_content_b64: str,
    filename: str,
    title: str | None = None,
    author: str | None = None,
    target_level: str | None = None,
    user_id: str | None = None,
) -> dict[str, str | int]:
    """Process a user book upload using durable DB status fields."""

    db = SessionLocal()
    try:
        user = db.get(User, UUID(str(user_id))) if user_id else None
        content = base64.b64decode(file_content_b64.encode("ascii"))
        book = BookLibraryService(db).process_upload(
            book_id=book_id,
            file_content=content,
            filename=filename,
            title=title,
            author=author,
            target_level=target_level,
            user=user,
        )
        return {"book_id": str(book.id), "status": book.status, "total_episodes": int(book.total_episodes or 0)}
    finally:
        db.close()


@celery_app.task(name="app.tasks.book_library.process_user_book_upload")
def process_user_book_upload(
    *,
    book_id: str,
    file_content_b64: str,
    filename: str,
    title: str | None = None,
    author: str | None = None,
    target_level: str | None = None,
    user_id: str | None = None,
) -> dict[str, str | int]:
    return process_user_book_upload_inline(
        book_id=book_id,
        file_content_b64=file_content_b64,
        filename=filename,
        title=title,
        author=author,
        target_level=target_level,
        user_id=user_id,
    )


__all__ = ["process_user_book_upload", "process_user_book_upload_inline"]
