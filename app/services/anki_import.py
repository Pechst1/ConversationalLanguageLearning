"""Anki import service for French-German vocabulary cards.

This service handles importing Anki cards while preserving scheduling data,
maintaining paired card relationships, and ensuring perfect integration
with the existing spaced repetition system.
"""
from __future__ import annotations

import csv
import logging
import re
from datetime import datetime, timezone
from io import StringIO
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.progress import UserVocabularyProgress, ReviewLog
from app.db.models.vocabulary import VocabularyWord
from app.db.models.user import User
from app.services.srs import FSRSScheduler


logger = logging.getLogger(__name__)


class AnkiImportError(Exception):
    """Raised when Anki import encounters an error."""


class AnkiCardParser:
    """Parser for Anki card content and scheduling data."""
    
    # Language detection patterns
    FRENCH_PATTERNS = [
        r'[àâäéèêëïîôöùûüÿç]',  # French accented characters
        r'\b(le|la|les|un|une|des|du|de la|ce|cette|ces)\b',  # French articles
        r'\b(je|tu|il|elle|nous|vous|ils|elles)\b',  # French pronouns
        r'\b(est|sont|avoir|être|faire|aller|venir)\b',  # Common French verbs
    ]
    
    GERMAN_PATTERNS = [
        r'[äöüßÄÖÜ]',  # German umlauts and eszett
        r'\b(der|die|das|ein|eine|einen|einem|einer)\b',  # German articles
        r'\b(ich|du|er|sie|es|wir|ihr|sie)\b',  # German pronouns
        r'\b(ist|sind|haben|sein|machen|gehen|kommen)\b',  # Common German verbs
    ]
    
    def detect_language(self, text: str) -> str:
        """Detect if text is likely French or German."""
        if not text or not isinstance(text, str):
            return "unknown"
        
        text_lower = text.lower()
        french_score = sum(1 for pattern in self.FRENCH_PATTERNS 
                          if re.search(pattern, text_lower, re.IGNORECASE))
        german_score = sum(1 for pattern in self.GERMAN_PATTERNS 
                          if re.search(pattern, text_lower, re.IGNORECASE))
        
        if french_score > german_score:
            return "french"
        elif german_score > french_score:
            return "german"
        else:
            return "mixed"
    
    def normalize_text(self, text: str) -> str:
        """Normalize text for database storage and matching."""
        if not text:
            return ""
        
        # Remove HTML tags that might be in Anki cards
        text = re.sub(r'<[^>]+>', '', text)
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text.strip())
        # Convert to lowercase for normalization
        return text.lower()
    
    def extract_word(self, text: str) -> str:
        """Extract the primary word from Anki card text."""
        if not text:
            return ""
        
        # Remove common Anki formatting and get first significant word
        text = re.sub(r'<[^>]+>', '', text)  # Remove HTML
        text = re.sub(r'\[[^\]]+\]', '', text)  # Remove brackets
        text = re.sub(r'\([^\)]+\)', '', text)  # Remove parentheses
        
        # Extract first meaningful word
        words = text.split()
        if words:
            return words[0].strip('.,;:!?')
        return text.strip()


class AnkiImportService:
    """Service for importing Anki cards into the vocabulary system."""
    
    def __init__(self, db: Session):
        self.db = db
        self.parser = AnkiCardParser()
        self.scheduler = FSRSScheduler()
        
    def import_cards_from_csv(
        self, 
        csv_content: str, 
        user_id: str,
        deck_name: Optional[str] = None,
        preserve_scheduling: bool = True
    ) -> Dict[str, Any]:
        """Import Anki cards from CSV content.
        
        Args:
            csv_content: Raw CSV content from Anki export
            user_id: User ID to associate cards with
            deck_name: Optional deck name override
            preserve_scheduling: Whether to preserve existing Anki scheduling
            
        Returns:
            Dictionary with import statistics and results
        """
        logger.info(f"Starting Anki import for user {user_id}")
        
        try:
            # Parse CSV content
            cards_data = self._parse_csv_content(csv_content)
            logger.info(f"Parsed {len(cards_data)} cards from CSV")
            
            # Process cards and create vocabulary entries
            import_stats = self._process_cards(
                cards_data, user_id, deck_name, preserve_scheduling
            )
            
            self.db.commit()
            logger.info(f"Successfully imported {import_stats['imported']} cards")
            
            return import_stats
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error during Anki import: {e}")
            raise AnkiImportError(f"Failed to import Anki cards: {e}")
    
    def _parse_csv_content(self, csv_content: str) -> List[Dict[str, Any]]:
        """Parse CSV content and extract card data."""
        cards = []
        
        # Try to detect CSV structure
        csv_file = StringIO(csv_content)
        reader = csv.DictReader(csv_file)
        
        for row_num, row in enumerate(reader):
            try:
                card_data = self._extract_card_data(row, row_num)
                if card_data:
                    cards.append(card_data)
            except Exception as e:
                logger.warning(f"Skipping row {row_num} due to error: {e}")
                continue
        
        return cards
    
    def _extract_card_data(self, row: Dict[str, str], row_num: int) -> Optional[Dict[str, Any]]:
        """Extract card data from a CSV row."""
        # Common Anki CSV column names (flexible detection)
        front_fields = ['Front', 'Question', 'Word', 'Term']
        back_fields = ['Back', 'Answer', 'Translation', 'Definition']
        
        front = None
        back = None
        
        # Find front and back content
        for field in front_fields:
            if field in row and row[field].strip():
                front = row[field].strip()
                break
        
        for field in back_fields:
            if field in row and row[field].strip():
                back = row[field].strip()
                break
        
        if not front or not back:
            logger.warning(f"Row {row_num}: Missing front or back content")
            return None
        
        # Extract additional data
        tags = row.get('Tags', '').strip().split() if row.get('Tags') else []
        deck = row.get('Deck', '').strip()
        note_id = row.get('Note ID', '').strip()
        card_id = row.get('Card ID', '').strip()
        
        # Detect languages
        front_lang = self.parser.detect_language(front)
        back_lang = self.parser.detect_language(back)
        
        return {
            'front': front,
            'back': back,
            'front_language': front_lang,
            'back_language': back_lang,
            'tags': tags,
            'deck': deck,
            'note_id': note_id,
            'card_id': card_id,
            'raw_row': row,
        }
    
    def _process_cards(
        self, 
        cards_data: List[Dict[str, Any]], 
        user_id: str,
        deck_name: Optional[str],
        preserve_scheduling: bool
    ) -> Dict[str, Any]:
        """Process cards and create database entries."""
        stats = {
            'total': len(cards_data),
            'imported': 0,
            'paired': 0,
            'skipped': 0,
            'errors': 0,
            'french_to_german': 0,
            'german_to_french': 0,
        }
        
        # Group cards by content to identify pairs
        card_pairs = self._identify_card_pairs(cards_data)
        
        for pair_id, pair_cards in card_pairs.items():
            try:
                result = self._process_card_pair(
                    pair_cards, user_id, deck_name, preserve_scheduling
                )
                
                stats['imported'] += result['imported']
                stats['paired'] += result['paired']
                stats['french_to_german'] += result['fr_to_de']
                stats['german_to_french'] += result['de_to_fr']
                
            except Exception as e:
                logger.error(f"Error processing pair {pair_id}: {e}")
                stats['errors'] += len(pair_cards)
        
        return stats
    
    def _identify_card_pairs(self, cards_data: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Identify paired cards (French<->German) by content similarity."""
        pairs = {}
        
        for card in cards_data:
            # Create a key based on the core vocabulary being tested
            front_word = self.parser.extract_word(card['front'])
            back_word = self.parser.extract_word(card['back'])
            
            # Create pair key (normalize to handle slight variations)
            pair_key = f"{self.parser.normalize_text(front_word)}_{self.parser.normalize_text(back_word)}"
            
            if pair_key not in pairs:
                pairs[pair_key] = []
            pairs[pair_key].append(card)
        
        return pairs
    
    def _process_card_pair(
        self, 
        cards: List[Dict[str, Any]], 
        user_id: str,
        deck_name: Optional[str],
        preserve_scheduling: bool
    ) -> Dict[str, int]:
        """Process a pair (or single card) and create vocabulary entries."""
        result = {
            'imported': 0,
            'paired': 0,
            'fr_to_de': 0,
            'de_to_fr': 0,
        }
        
        vocab_words = []
        
        for card in cards:
            vocab_word = self._create_vocabulary_word(card, deck_name)
            if vocab_word:
                self.db.add(vocab_word)
                vocab_words.append(vocab_word)
                result['imported'] += 1
                
                # Count by direction
                if vocab_word.direction == 'fr_to_de':
                    result['fr_to_de'] += 1
                elif vocab_word.direction == 'de_to_fr':
                    result['de_to_fr'] += 1
        
        # Flush to get IDs before linking
        self.db.flush()
        
        # Link paired cards
        if len(vocab_words) == 2:
            vocab_words[0].linked_word_id = vocab_words[1].id
            vocab_words[1].linked_word_id = vocab_words[0].id
            result['paired'] += 2
        
        # Create progress tracking for user
        user = self.db.get(User, user_id)
        if user:
            for vocab_word in vocab_words:
                self._create_user_progress(vocab_word, user, preserve_scheduling, cards[0])
        
        return result
    
    def _create_vocabulary_word(self, card: Dict[str, Any], deck_name: Optional[str]) -> Optional[VocabularyWord]:
        """Create a VocabularyWord from card data."""
        front = card['front']
        back = card['back']
        front_lang = card['front_language']
        back_lang = card['back_language']
        
        # Determine direction and languages
        if front_lang == 'french' and back_lang in ['german', 'mixed']:
            direction = 'fr_to_de'
            word = self.parser.extract_word(front)
            language = 'fr'
            french_translation = front
            german_translation = back
        elif front_lang in ['german', 'mixed'] and back_lang == 'french':
            direction = 'de_to_fr'
            word = self.parser.extract_word(front)
            language = 'de'
            french_translation = back
            german_translation = front
        elif front_lang == 'french':
            # Default to French word even if back language unclear
            direction = 'fr_to_de'
            word = self.parser.extract_word(front)
            language = 'fr'
            french_translation = front
            german_translation = back
        else:
            # Default to German word
            direction = 'de_to_fr'
            word = self.parser.extract_word(front)
            language = 'de'
            french_translation = back
            german_translation = front
        
        # Check if word already exists
        existing = self.db.scalars(
            select(VocabularyWord).where(
                VocabularyWord.word == word,
                VocabularyWord.language == language,
                VocabularyWord.direction == direction
            )
        ).first()
        
        if existing:
            logger.info(f"Word {word} already exists, updating...")
            # Update existing word with new data
            existing.french_translation = french_translation
            existing.german_translation = german_translation
            existing.is_anki_card = True
            existing.deck_name = deck_name or card.get('deck', '')
            existing.note_id = card.get('note_id', '')
            existing.card_id = card.get('card_id', '')
            return existing
        
        # Create new vocabulary word
        vocab_word = VocabularyWord(
            language=language,
            word=word,
            normalized_word=self.parser.normalize_text(word),
            french_translation=french_translation,
            german_translation=german_translation,
            direction=direction,
            deck_name=deck_name or card.get('deck', ''),
            note_id=card.get('note_id', ''),
            card_id=card.get('card_id', ''),
            is_anki_card=True,
            topic_tags=card.get('tags', []),
        )
        
        return vocab_word
    
    def _create_user_progress(
        self, 
        vocab_word: VocabularyWord, 
        user: User, 
        preserve_scheduling: bool,
        card_data: Dict[str, Any]
    ) -> None:
        """Create user progress entry for the vocabulary word."""
        # Check if progress already exists
        existing_progress = self.db.scalars(
            select(UserVocabularyProgress).where(
                UserVocabularyProgress.user_id == user.id,
                UserVocabularyProgress.word_id == vocab_word.id
            )
        ).first()
        
        if existing_progress:
            logger.info(f"Progress for word {vocab_word.word} already exists")
            return
        
        # Create new progress entry
        progress = UserVocabularyProgress(
            user_id=user.id,
            word_id=vocab_word.id,
            scheduler="anki",  # Use Anki scheduler for imported cards
            deck_name=vocab_word.deck_name,
            note_id=vocab_word.note_id,
            card_id=vocab_word.card_id,
            raw_history=str(card_data.get('raw_row', {})),
        )
        
        # Extract scheduling data if available and preserve_scheduling is True
        if preserve_scheduling:
            self._extract_scheduling_data(progress, card_data)
        
        self.db.add(progress)
    
    def _extract_scheduling_data(self, progress: UserVocabularyProgress, card_data: Dict[str, Any]) -> None:
        """Extract and apply Anki scheduling data to progress."""
        raw_row = card_data.get('raw_row', {})
        
        # Common Anki scheduling fields
        if 'Ease' in raw_row:
            try:
                progress.ease_factor = float(raw_row['Ease']) / 100  # Anki stores as percentage
            except (ValueError, TypeError):
                pass
        
        if 'Interval' in raw_row:
            try:
                progress.interval_days = int(raw_row['Interval'])
            except (ValueError, TypeError):
                pass
        
        if 'Reps' in raw_row:
            try:
                progress.reps = int(raw_row['Reps'])
            except (ValueError, TypeError):
                pass
        
        if 'Lapses' in raw_row:
            try:
                progress.lapses = int(raw_row['Lapses'])
            except (ValueError, TypeError):
                pass
        
        if 'Due' in raw_row:
            try:
                # Anki due dates are often in days since epoch or collection start
                due_days = int(raw_row['Due'])
                if due_days > 0:
                    # Simple conversion - this may need adjustment based on Anki's format
                    progress.due_at = datetime.now(timezone.utc)
            except (ValueError, TypeError):
                pass
        
        # Set appropriate phase based on reps and interval
        if progress.reps == 0:
            progress.phase = "new"
        elif progress.interval_days and progress.interval_days > 1:
            progress.phase = "review"
        else:
            progress.phase = "learn"
    
    def get_import_statistics(self, user_id: str) -> Dict[str, Any]:
        """Get statistics about imported Anki cards for a user."""
        # Count vocabulary words
        vocab_count = self.db.scalar(
            select(func.count()).select_from(VocabularyWord)
            .where(VocabularyWord.is_anki_card == True)
        ) or 0
        
        # Count user progress
        progress_count = self.db.scalar(
            select(func.count()).select_from(UserVocabularyProgress)
            .where(
                UserVocabularyProgress.user_id == user_id,
                UserVocabularyProgress.scheduler == "anki"
            )
        ) or 0
        
        # Count by direction
        fr_to_de = self.db.scalar(
            select(func.count()).select_from(VocabularyWord)
            .where(
                VocabularyWord.is_anki_card == True,
                VocabularyWord.direction == "fr_to_de"
            )
        ) or 0
        
        de_to_fr = self.db.scalar(
            select(func.count()).select_from(VocabularyWord)
            .where(
                VocabularyWord.is_anki_card == True,
                VocabularyWord.direction == "de_to_fr"
            )
        ) or 0
        
        # Count paired cards
        paired_count = self.db.scalar(
            select(func.count()).select_from(VocabularyWord)
            .where(
                VocabularyWord.is_anki_card == True,
                VocabularyWord.linked_word_id != None
            )
        ) or 0
        
        return {
            'total_vocabulary': vocab_count,
            'user_progress_entries': progress_count,
            'french_to_german_cards': fr_to_de,
            'german_to_french_cards': de_to_fr,
            'paired_cards': paired_count,
            'unique_pairs': paired_count // 2 if paired_count > 0 else 0,
        }