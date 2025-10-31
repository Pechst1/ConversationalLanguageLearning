"""Vocabulary browsing endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas import VocabularyListResponse, VocabularyWordRead
from app.services.vocabulary import VocabularyNotFoundError, VocabularyService
from app.utils.cache import cache_backend, build_cache_key

router = APIRouter(prefix="/vocabulary", tags=["vocabulary"])


@router.get("/", response_model=VocabularyListResponse)
def list_vocabulary(
    language: str | None = Query(default=None, max_length=10, description="Language code to filter by"),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(deps.get_db),
) -> VocabularyListResponse:
    """Return vocabulary items with optional pagination."""

    cache_key = build_cache_key(language=language, limit=limit, offset=offset)
    cached = cache_backend.get("vocabulary:list", cache_key)
    if cached is not None:
        return cached

    service = VocabularyService(db)
    items = service.list_words(language=language, limit=limit, offset=offset)
    total = service.count_words(language=language)
    response = VocabularyListResponse(total=total, items=items)
    payload = response.model_dump(mode="json")
    cache_backend.set("vocabulary:list", cache_key, payload, ttl_seconds=3600)
    return payload


@router.get("/{word_id}", response_model=VocabularyWordRead)
def get_vocabulary_word(word_id: int, db: Session = Depends(deps.get_db)) -> VocabularyWordRead:
    """Retrieve a vocabulary word by identifier."""

    cache_key = build_cache_key(word_id=word_id)
    cached = cache_backend.get("vocabulary:item", cache_key)
    if cached is not None:
        return cached

    service = VocabularyService(db)
    try:
        word = service.get_word(word_id)
    except VocabularyNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    payload = VocabularyWordRead.model_validate(word).model_dump(mode="json")
    cache_backend.set("vocabulary:item", cache_key, payload, ttl_seconds=3600)
    return payload


@router.get("/lookup", response_model=VocabularyWordRead)
def lookup_vocabulary_word(
    word: str = Query(..., min_length=1, description="Surface form to look up"),
    language: str | None = Query(default=None, max_length=10),
    db: Session = Depends(deps.get_db),
) -> VocabularyWordRead:
    """Lookup a vocabulary word by its surface form."""

    cache_key = build_cache_key(word=word.strip().lower(), language=language)
    cached = cache_backend.get("vocabulary:lookup", cache_key)
    if cached is not None:
        return cached

    service = VocabularyService(db)
    try:
        vocab_word = service.lookup_word(term=word, language=language)
    except VocabularyNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    payload = VocabularyWordRead.model_validate(vocab_word).model_dump(mode="json")
    cache_backend.set("vocabulary:lookup", cache_key, payload, ttl_seconds=600)
    return payload
