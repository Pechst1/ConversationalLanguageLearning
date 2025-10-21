"""Vocabulary browsing endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas import VocabularyListResponse, VocabularyWordRead
from app.services.vocabulary import VocabularyNotFoundError, VocabularyService

router = APIRouter(prefix="/vocabulary", tags=["vocabulary"])


@router.get("/", response_model=VocabularyListResponse)
def list_vocabulary(
    language: str | None = Query(default=None, max_length=10, description="Language code to filter by"),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(deps.get_db),
) -> VocabularyListResponse:
    """Return vocabulary items with optional pagination."""

    service = VocabularyService(db)
    items = service.list_words(language=language, limit=limit, offset=offset)
    total = service.count_words(language=language)
    return VocabularyListResponse(total=total, items=items)


@router.get("/{word_id}", response_model=VocabularyWordRead)
def get_vocabulary_word(word_id: int, db: Session = Depends(deps.get_db)) -> VocabularyWordRead:
    """Retrieve a vocabulary word by identifier."""

    service = VocabularyService(db)
    try:
        return service.get_word(word_id)
    except VocabularyNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
