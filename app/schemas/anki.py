"""Anki import and synchronization schemas."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator


class AnkiImportRequest(BaseModel):
    """Request schema for importing Anki cards from CSV text."""
    
    csv_content: str = Field(
        ..., 
        description="CSV content from Anki export",
        min_length=1
    )
    deck_name: Optional[str] = Field(
        None,
        description="Optional deck name override"
    )
    preserve_scheduling: bool = Field(
        True,
        description="Whether to preserve existing Anki scheduling data"
    )
    
    @validator('csv_content')
    def validate_csv_content(cls, v):
        """Validate that CSV content looks reasonable."""
        if not v.strip():
            raise ValueError("CSV content cannot be empty")
        
        # Basic CSV validation - should have at least one comma or tab
        if ',' not in v and '\t' not in v:
            raise ValueError("Content does not appear to be valid CSV format")
        
        return v


class AnkiImportStatistics(BaseModel):
    """Statistics about the Anki import operation."""
    
    total: int = Field(..., description="Total cards processed")
    imported: int = Field(..., description="Successfully imported cards")
    paired: int = Field(..., description="Cards that were paired with reverse cards")
    skipped: int = Field(..., description="Cards that were skipped")
    errors: int = Field(..., description="Cards that had errors during import")
    french_to_german: int = Field(..., description="French to German cards")
    german_to_french: int = Field(..., description="German to French cards")


class AnkiImportResponse(BaseModel):
    """Response schema for Anki import operations."""
    
    success: bool = Field(..., description="Whether the import was successful")
    message: str = Field(..., description="Human-readable result message")
    statistics: Dict[str, Any] = Field(..., description="Detailed import statistics")


class AnkiVocabularyStatistics(BaseModel):
    """Statistics about imported Anki vocabulary."""
    
    total_vocabulary: int = Field(..., description="Total vocabulary words from Anki")
    user_progress_entries: int = Field(..., description="User progress entries for Anki cards")
    french_to_german_cards: int = Field(..., description="Number of French→German cards")
    german_to_french_cards: int = Field(..., description="Number of German→French cards")
    paired_cards: int = Field(..., description="Total cards that are part of pairs")
    unique_pairs: int = Field(..., description="Number of unique vocabulary pairs")


class AnkiReviewStatistics(BaseModel):
    """Statistics about review performance."""
    
    total_reviews: int = Field(..., description="Total reviews in the period")
    fsrs_reviews: int = Field(..., description="Reviews using FSRS scheduler")
    anki_reviews: int = Field(..., description="Reviews using Anki SM-2 scheduler")
    average_rating: float = Field(..., description="Average rating across all reviews")
    period_days: int = Field(..., description="Period covered by statistics in days")


class AnkiDueCardsStatistics(BaseModel):
    """Statistics about cards due for review."""
    
    total: int = Field(..., description="Total cards due")
    anki_scheduler: int = Field(..., description="Cards due using Anki scheduler")
    fsrs_scheduler: int = Field(..., description="Cards due using FSRS scheduler")


class AnkiStatisticsResponse(BaseModel):
    """Complete statistics response for Anki integration."""
    
    import_statistics: AnkiVocabularyStatistics
    review_statistics: AnkiReviewStatistics
    due_cards: AnkiDueCardsStatistics


class AnkiCardVocabulary(BaseModel):
    """Vocabulary information for an Anki card."""
    
    word: str = Field(..., description="The vocabulary word")
    language: str = Field(..., description="Language code (fr/de)")
    direction: Optional[str] = Field(None, description="Card direction (fr_to_de/de_to_fr)")
    french_translation: Optional[str] = Field(None, description="French text")
    german_translation: Optional[str] = Field(None, description="German text")
    deck_name: Optional[str] = Field(None, description="Original Anki deck name")


class AnkiDueCard(BaseModel):
    """Information about a card due for review."""
    
    progress_id: str = Field(..., description="Progress entry ID")
    word_id: int = Field(..., description="Vocabulary word ID")
    scheduler: str = Field(..., description="Scheduler type (anki/fsrs)")
    phase: Optional[str] = Field(None, description="Current learning phase")
    due_at: Optional[str] = Field(None, description="Precise due date/time (ISO format)")
    next_review_date: Optional[str] = Field(None, description="Next review date (ISO format)")
    proficiency_score: Optional[int] = Field(None, description="Proficiency score (0-100)")
    reps: int = Field(0, description="Number of times reviewed")
    ease_factor: Optional[float] = Field(None, description="Anki ease factor")
    interval_days: Optional[int] = Field(None, description="Current interval in days")
    vocabulary: Optional[AnkiCardVocabulary] = Field(None, description="Associated vocabulary")


class AnkiDueCardsResponse(BaseModel):
    """Response for due cards endpoint."""
    
    cards: List[AnkiDueCard] = Field(..., description="Cards due for review")
    total_count: int = Field(..., description="Number of cards returned")
    scheduler_type: Optional[str] = Field(None, description="Filter applied for scheduler type")


class AnkiSyncRequest(BaseModel):
    """Request for synchronizing changes back to Anki format."""
    
    deck_name: Optional[str] = Field(None, description="Specific deck to export")
    include_new_cards: bool = Field(True, description="Include cards created in the app")
    include_scheduling: bool = Field(True, description="Include current scheduling data")
    format_type: str = Field("csv", description="Export format (csv/apkg)")


class AnkiSyncResponse(BaseModel):
    """Response for Anki synchronization export."""
    
    success: bool = Field(..., description="Whether the export was successful")
    content: Optional[str] = Field(None, description="Exported content (for CSV)")
    download_url: Optional[str] = Field(None, description="Download URL (for binary formats)")
    cards_exported: int = Field(..., description="Number of cards included in export")
    format_type: str = Field(..., description="Format of the exported data")
    message: str = Field(..., description="Human-readable result message")


class AnkiHealthCheck(BaseModel):
    """Health check response for Anki integration."""
    
    anki_cards_imported: bool = Field(..., description="Whether any Anki cards have been imported")
    total_anki_vocabulary: int = Field(..., description="Total Anki vocabulary in system")
    active_users_with_anki: int = Field(..., description="Users with imported Anki cards")
    last_import_date: Optional[str] = Field(None, description="Most recent import date (ISO format)")
    schedulers_supported: List[str] = Field(..., description="List of supported schedulers")
    features_available: List[str] = Field(..., description="Available Anki integration features")


class AnkiReviewRequest(BaseModel):
    """Payload for submitting an Anki-style review."""

    word_id: int = Field(..., ge=1)
    rating: int = Field(..., ge=0, le=3, description="Anki rating 0=Again,1=Hard,2=Good,3=Easy")
    response_time_ms: Optional[int] = Field(None, ge=0)


class AnkiReviewResponse(BaseModel):
    """Response for an Anki review submission."""

    word_id: int
    scheduler: str = Field("anki")
    phase: Optional[str] = None
    ease_factor: Optional[float] = None
    interval_days: Optional[int] = None
    due_at: Optional[str] = None
    next_review: Optional[str] = None


class AnkiCardUpdate(BaseModel):
    """Data for a single card from AnkiConnect."""
    
    note_id: int
    card_id: int
    deck_name: str
    model_name: str
    fields: Dict[str, str]
    due: Optional[int] = None
    interval: Optional[int] = None
    ease: Optional[int] = None
    reps: Optional[int] = None
    lapses: Optional[int] = None
    ord: Optional[int] = None


class AnkiConnectSyncRequest(BaseModel):
    """Payload for syncing data from AnkiConnect."""
    
    cards: List[AnkiCardUpdate]
