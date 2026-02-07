"""Anki synchronization tasks."""
from __future__ import annotations

import httpx
from celery import shared_task
from loguru import logger

from app.db.session import SessionLocal
from app.db.models.user import User
from app.services.progress import ProgressService


ANKI_CONNECT_URL = "http://localhost:8765"
DEFAULT_DECK = "Französisch Wortschatz"  # Can be configured per user


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def sync_anki_cards_for_all_users(self):
    """
    Scheduled task to sync Anki cards for all users.
    Runs daily at 4 AM.
    
    This task connects to a local AnkiConnect instance and syncs
    vocabulary progress for all registered users.
    """
    logger.info("Starting scheduled Anki sync for all users")
    
    db = SessionLocal()
    try:
        users = db.query(User).all()
        synced_count = 0
        error_count = 0
        
        for user in users:
            try:
                result = sync_anki_for_user(user.id, DEFAULT_DECK)
                if result.get("success"):
                    synced_count += 1
                    logger.info(f"Synced Anki cards for user {user.id}: {result.get('cards_synced', 0)} cards")
                else:
                    error_count += 1
                    logger.warning(f"Failed to sync for user {user.id}: {result.get('error')}")
            except Exception as e:
                error_count += 1
                logger.error(f"Error syncing Anki for user {user.id}: {e}")
        
        logger.info(f"Anki sync complete: {synced_count} users synced, {error_count} errors")
        return {"synced": synced_count, "errors": error_count}
        
    except Exception as e:
        logger.error(f"Anki sync task failed: {e}")
        raise self.retry(exc=e)
    finally:
        db.close()


def sync_anki_for_user(user_id: str, deck_name: str) -> dict:
    """
    Sync Anki cards for a specific user from the local AnkiConnect instance.
    
    Note: This requires Anki to be running with AnkiConnect addon on the same machine.
    For server deployments, you may need to configure remote AnkiConnect access.
    """
    try:
        # Check if AnkiConnect is available
        response = httpx.post(
            ANKI_CONNECT_URL,
            json={"action": "version", "version": 6},
            timeout=5.0
        )
        if response.status_code != 200:
            return {"success": False, "error": "AnkiConnect not available"}
        
        # Find cards in the deck
        response = httpx.post(
            ANKI_CONNECT_URL,
            json={
                "action": "findCards",
                "version": 6,
                "params": {"query": f'deck:"{deck_name}"'}
            },
            timeout=30.0
        )
        
        data = response.json()
        if data.get("error"):
            return {"success": False, "error": data["error"]}
        
        card_ids = data.get("result", [])
        if not card_ids:
            return {"success": True, "cards_synced": 0, "message": "No cards found"}
        
        # Get card info in batches
        batch_size = 100
        all_cards = []
        
        for i in range(0, len(card_ids), batch_size):
            batch = card_ids[i:i + batch_size]
            response = httpx.post(
                ANKI_CONNECT_URL,
                json={
                    "action": "cardsInfo",
                    "version": 6,
                    "params": {"cards": batch}
                },
                timeout=60.0
            )
            
            data = response.json()
            if not data.get("error"):
                all_cards.extend(data.get("result", []))
        
        # Process and save to database
        db = SessionLocal()
        try:
            service = ProgressService(db)
            cards_data = []
            
            for card in all_cards:
                # Flatten fields
                fields = {k: v.get("value", "") for k, v in card.get("fields", {}).items()}
                
                cards_data.append({
                    "note_id": card.get("note"),
                    "card_id": card.get("cardId"),
                    "deck_name": card.get("deckName"),
                    "model_name": card.get("modelName"),
                    "fields": fields,
                    "due": card.get("due"),
                    "interval": card.get("interval"),
                    "ease": card.get("factor"),
                    "reps": card.get("reps"),
                    "lapses": card.get("lapses"),
                    "ord": card.get("ord"),
                })
            
            user = db.query(User).filter(User.id == user_id).first()
            if user and cards_data:
                result = service.sync_anki_progress(user=user, cards=cards_data)
                db.commit()
                return {"success": True, "cards_synced": result.get("synced", 0)}
            
            return {"success": True, "cards_synced": 0}
            
        finally:
            db.close()
            
    except httpx.ConnectError:
        logger.warning("AnkiConnect not available - Anki may not be running")
        return {"success": False, "error": "AnkiConnect not available"}
    except Exception as e:
        logger.error(f"Error in sync_anki_for_user: {e}")
        return {"success": False, "error": str(e)}


__all__ = ["sync_anki_cards_for_all_users", "sync_anki_for_user"]
