"""Anki import and synchronization endpoints."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.db.models.user import User
from app.schemas.anki import (
    AnkiImportRequest,
    AnkiImportResponse,
    AnkiStatisticsResponse,
)
from app.services.anki_import import AnkiImportService, AnkiImportError
from app.services.enhanced_srs import EnhancedSRSService


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/anki", tags=["anki"])


@router.post("/import", response_model=AnkiImportResponse)
async def import_anki_cards(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    file: UploadFile = File(..., description="Anki CSV export file"),
    deck_name: Optional[str] = Form(None, description="Override deck name"),
    preserve_scheduling: bool = Form(True, description="Preserve Anki scheduling data"),
) -> AnkiImportResponse:
    """Import Anki cards from a CSV file.
    
    Upload your Anki deck export (CSV format) to import French-German vocabulary cards.
    The system will automatically:
    - Detect French and German content
    - Create paired cards (French↔German)
    - Preserve your existing review progress
    - Maintain synchronization with Anki
    """
    
    # Validate file
    if not file.filename or not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV file"
        )
    
    try:
        # Read file content
        content = await file.read()
        csv_content = content.decode('utf-8')
        
        logger.info(f"Processing Anki import for user {current_user.id}: {file.filename}")
        
        # Import cards
        import_service = AnkiImportService(db)
        result = import_service.import_cards_from_csv(
            csv_content=csv_content,
            user_id=str(current_user.id),
            deck_name=deck_name,
            preserve_scheduling=preserve_scheduling
        )
        
        logger.info(f"Anki import completed for user {current_user.id}: {result}")
        
        return AnkiImportResponse(
            success=True,
            message=f"Successfully imported {result['imported']} cards",
            statistics=result
        )
        
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File encoding not supported. Please ensure your CSV is UTF-8 encoded."
        )
    except AnkiImportError as e:
        logger.error(f"Anki import error for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error during Anki import for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during import"
        )


@router.post("/import/text", response_model=AnkiImportResponse)
async def import_anki_cards_text(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    request: AnkiImportRequest,
) -> AnkiImportResponse:
    """Import Anki cards from CSV text content.
    
    Alternative endpoint for importing cards by pasting CSV content directly.
    Useful for smaller imports or when file upload is not convenient.
    """
    
    try:
        logger.info(f"Processing text-based Anki import for user {current_user.id}")
        
        # Import cards
        import_service = AnkiImportService(db)
        result = import_service.import_cards_from_csv(
            csv_content=request.csv_content,
            user_id=str(current_user.id),
            deck_name=request.deck_name,
            preserve_scheduling=request.preserve_scheduling
        )
        
        logger.info(f"Text-based Anki import completed for user {current_user.id}: {result}")
        
        return AnkiImportResponse(
            success=True,
            message=f"Successfully imported {result['imported']} cards",
            statistics=result
        )
        
    except AnkiImportError as e:
        logger.error(f"Anki import error for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error during text-based Anki import for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during import"
        )


@router.get("/statistics", response_model=AnkiStatisticsResponse)
async def get_anki_statistics(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AnkiStatisticsResponse:
    """Get statistics about imported Anki cards and review progress.
    
    Returns detailed statistics about:
    - Total imported vocabulary
    - French→German vs German→French cards  
    - Paired card relationships
    - Review performance by scheduler type
    """
    
    try:
        # Get import statistics
        import_service = AnkiImportService(db)
        import_stats = import_service.get_import_statistics(str(current_user.id))
        
        # Get review statistics
        srs_service = EnhancedSRSService(db)
        review_stats = srs_service.get_review_statistics(str(current_user.id))
        
        # Get due cards count
        due_cards = len(srs_service.get_due_cards(str(current_user.id), limit=1000))
        anki_due_cards = len(srs_service.get_due_cards(str(current_user.id), limit=1000, scheduler_type="anki"))
        fsrs_due_cards = len(srs_service.get_due_cards(str(current_user.id), limit=1000, scheduler_type="fsrs"))
        
        return AnkiStatisticsResponse(
            import_statistics=import_stats,
            review_statistics=review_stats,
            due_cards={
                'total': due_cards,
                'anki_scheduler': anki_due_cards,
                'fsrs_scheduler': fsrs_due_cards,
            }
        )
        
    except Exception as e:
        logger.error(f"Error getting Anki statistics for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving statistics"
        )


@router.get("/due-cards")
async def get_due_cards(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = 20,
    scheduler_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Get vocabulary cards that are due for review.
    
    Args:
        limit: Maximum number of cards to return
        scheduler_type: Filter by scheduler ('anki' or 'fsrs')
    
    Returns cards due for review with their vocabulary information.
    """
    
    try:
        srs_service = EnhancedSRSService(db)
        due_progress = srs_service.get_due_cards(
            str(current_user.id), 
            limit=limit, 
            scheduler_type=scheduler_type
        )
        
        # Format response with vocabulary details
        cards = []
        for progress in due_progress:
            card_info = {
                'progress_id': str(progress.id),
                'word_id': progress.word_id,
                'scheduler': progress.scheduler,
                'phase': progress.phase,
                'due_at': progress.due_at.isoformat() if progress.due_at else None,
                'next_review_date': progress.next_review_date.isoformat() if progress.next_review_date else None,
                'proficiency_score': progress.proficiency_score,
                'reps': progress.reps,
                'ease_factor': progress.ease_factor,
                'interval_days': progress.interval_days,
            }
            
            # Add vocabulary details if available
            if progress.word:
                card_info['vocabulary'] = {
                    'word': progress.word.word,
                    'language': progress.word.language,
                    'direction': progress.word.direction,
                    'french_translation': progress.word.french_translation,
                    'german_translation': progress.word.german_translation,
                    'deck_name': progress.word.deck_name,
                }
            
            cards.append(card_info)
        
        return {
            'cards': cards,
            'total_count': len(cards),
            'scheduler_type': scheduler_type,
        }
        
    except Exception as e:
        logger.error(f"Error getting due cards for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving due cards"
        )