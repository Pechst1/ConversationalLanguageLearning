"""Anki import service for French-German vocabulary cards.

This service handles importing Anki cards while preserving scheduling data,
maintaining paired card relationships, and ensuring perfect integration
with the existing spaced repetition system.
"""
from __future__ import annotations

import csv
import logging
import re
from datetime import datetime, timedelta, timezone
from io import StringIO
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
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
    
    def extract_word(self, text: str, expected_language: str | None = None) -> str:
        """Extract the primary word from Anki card text."""
        if not text:
            return ""

        # Remove common Anki formatting and get first significant word
        text = re.sub(r'<[^>]+>', '', text)  # Remove HTML
        text = re.sub(r'\[[^\]]+\]', '', text)  # Remove brackets
        text = re.sub(r'\([^\)]+\)', '', text)  # Remove parentheses

        # Normalize unusual spacing (e.g., full-width spaces from Anki)
        text = text.replace("\u3000", " ")
        text = re.sub(r'\s+', ' ', text.strip())

        # If the field contains synonyms separated by commas/semicolons/slashes, prefer the first segment
        # This prevents cases like "global, weltweit" or "Motor / moteur" from leaking both languages.
        parts = re.split(r'[;,/|]+', text)
        if parts:
            text = parts[0].strip()

        if not text:
            return ""

        tokens: List[str] = []
        for raw_token in text.split():
            cleaned = raw_token.strip('.,;:!?«»"\'“”[]()')
            if not cleaned:
                continue
            tokens.append(cleaned)
            if len(tokens) >= 3:
                break

        if not tokens:
            return text

        deduped: List[str] = []
        for token in tokens:
            lowered = token.lower()
            if not deduped or deduped[-1].lower() != lowered:
                deduped.append(token)
        tokens = deduped

        if expected_language in {"french", "german"}:
            filtered: List[str] = []
            for token in tokens:
                lang = self.detect_language(token)
                if lang == expected_language:
                    filtered.append(token)
                elif expected_language == "german" and lang == "mixed":
                    filtered.append(token)
                elif expected_language == "french" and lang == "mixed":
                    filtered.append(token)
            if filtered:
                tokens = filtered

        # Preserve short multi-word expressions where relevant
        articles = {"le", "la", "les", "un", "une", "des", "du", "de", "der", "die", "das", "ein", "eine"}
        if tokens[0].lower() in articles and len(tokens) >= 2:
            return " ".join(tokens[: min(3, len(tokens))])

        return " ".join(tokens[: min(2, len(tokens))])


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

        csv_file = StringIO(csv_content)
        sample = csv_file.read(4096)
        csv_file.seek(0)

        delimiter = ","
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=[",", "\t", ";"])
            delimiter = dialect.delimiter
        except csv.Error:
            # Fall back to tab if it appears more frequently than commas
            if sample.count("\t") > sample.count(","):
                delimiter = "\t"

        reader = csv.DictReader(csv_file, delimiter=delimiter)

        for row_num, row in enumerate(reader):
            if not row:
                continue

            normalized_row = self._normalize_row_keys(row)
            if self._is_duplicate_header_row(normalized_row):
                logger.debug("Skipping duplicate header row during Anki import (row %s)", row_num)
                continue

            try:
                card_data = self._extract_card_data(row, normalized_row, row_num)
                if card_data:
                    cards.append(card_data)
            except Exception as e:
                logger.warning(f"Skipping row {row_num} due to error: {e}")
                continue
        
        return cards

    def _primary_text(self, text: str) -> str:
        """Return the primary field value before supplemental examples/notes."""

        if not text:
            return ""

        cleaned = text.strip().strip('"').replace("\r", " ").replace("\n", " ")
        segments = [segment.strip() for segment in re.split(r"\u3000+", cleaned) if segment.strip()]
        candidate = segments[0] if segments else cleaned

        candidate = re.sub(r"\[[^\]]+\]", "", candidate)  # remove bracket tags
        candidate = re.sub(r"\*([^*]+)\*", r"\1", candidate)  # remove emphasis markers
        candidate = re.sub(r"\s+", " ", candidate).strip()
        candidate = candidate.lstrip(",;: ")
        return candidate
    
    def _normalize_row_keys(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Return lower-cased, snake_case keys for flexible column access."""
        normalized: Dict[str, Any] = {}
        for key, value in row.items():
            if key is None:
                continue
            key_normalized = re.sub(r"[^a-z0-9]+", "_", key.strip().lower()).strip("_")
            normalized[key_normalized] = value.strip() if isinstance(value, str) else value
        return normalized

    def _is_duplicate_header_row(self, normalized_row: Dict[str, Any]) -> bool:
        """Detect rows that simply repeat the header names."""
        if not normalized_row:
            return False
        question = str(normalized_row.get("question", "")).strip().lower()
        answer = str(normalized_row.get("answer", "")).strip().lower()
        front = str(normalized_row.get("front", "")).strip().lower()
        back = str(normalized_row.get("back", "")).strip().lower()
        return (question == "question" and answer == "answer") or (front == "front" and back == "back")

    def _extract_card_data(
        self,
        row: Dict[str, str],
        normalized_row: Dict[str, Any],
        row_num: int
    ) -> Optional[Dict[str, Any]]:
        """Extract card data from a CSV row."""
        # Common Anki CSV column names (flexible detection)
        front_fields = [
            "front",
            "question",
            "word",
            "term",
            "card_export_column__field_a",
        ]
        back_fields = [
            "back",
            "answer",
            "translation",
            "definition",
            "card_export_column__field_b",
        ]

        front = None
        back = None

        # Find front and back content
        for field in front_fields:
            value = normalized_row.get(field)
            if isinstance(value, str) and value.strip():
                front = value.strip()
                break

        for field in back_fields:
            value = normalized_row.get(field)
            if isinstance(value, str) and value.strip():
                back = value.strip()
                break

        if not front or not back:
            logger.warning(f"Row {row_num}: Missing front or back content")
            return None

        # Extract additional data
        tags_raw = normalized_row.get("tags") or normalized_row.get("tag") or ""
        tags = tags_raw.strip().split() if isinstance(tags_raw, str) and tags_raw.strip() else []
        deck = normalized_row.get("deck") or normalized_row.get("c_deck") or ""
        note_id = normalized_row.get("note_id") or normalized_row.get("c_noteid") or ""
        card_id = normalized_row.get("card_id") or normalized_row.get("c_cardid") or ""
        card_type = (normalized_row.get("c_cardtype") or "").strip()
        direction_hint = None
        if card_type:
            lower = card_type.lower()
            if lower.startswith("fr"):
                direction_hint = "fr_to_de"
            elif lower.startswith("de"):
                direction_hint = "de_to_fr"
        if not direction_hint and isinstance(deck, str):
            lower_deck = deck.lower()
            if "fr" in lower_deck and "de" in lower_deck:
                if lower_deck.strip().startswith("fr"):
                    direction_hint = "fr_to_de"
                elif lower_deck.strip().startswith("de"):
                    direction_hint = "de_to_fr"

        front_primary = self._primary_text(front)
        back_primary = self._primary_text(back)

        # Detect languages based on primary content
        front_lang = self.parser.detect_language(front_primary or front)
        back_lang = self.parser.detect_language(back_primary or back)

        return {
            'front': front,
            'back': back,
            'front_primary': front_primary,
            'back_primary': back_primary,
            'front_language': front_lang,
            'back_language': back_lang,
            'tags': tags,
            'deck': deck.strip() if isinstance(deck, str) else deck,
            'note_id': str(note_id).strip(),
            'card_id': str(card_id).strip(),
            'raw_row': row,
            'normalized_row': normalized_row,
            'direction_hint': direction_hint,
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
        
        for index, card in enumerate(cards_data):
            # Create a key based on the core vocabulary being tested
            front_word = self.parser.extract_word(card['front'])
            back_word = self.parser.extract_word(card['back'])

            # Create pair key (normalize to handle slight variations)
            normalized_front = self.parser.normalize_text(front_word)
            normalized_back = self.parser.normalize_text(back_word)

            key_parts = sorted(
                part for part in [normalized_front, normalized_back] if part
            )
            pair_key = "||".join(key_parts) if key_parts else f"card_{index}"

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
        front_primary = card.get('front_primary') or front
        back_primary = card.get('back_primary') or back
        front_lang = card['front_language']
        back_lang = card['back_language']
        direction_hint = card.get('direction_hint')

        # Determine direction and languages
        if direction_hint == 'fr_to_de':
            direction = 'fr_to_de'
            word = self.parser.extract_word(front_primary, expected_language='french')
            language = 'fr'
            french_translation = front_primary
            german_translation = back_primary
        elif direction_hint == 'de_to_fr':
            direction = 'de_to_fr'
            word = self.parser.extract_word(front_primary, expected_language='german')
            language = 'de'
            french_translation = back_primary
            german_translation = front_primary
        elif front_lang == 'french' and back_lang in ['german', 'mixed']:
            direction = 'fr_to_de'
            word = self.parser.extract_word(front_primary, expected_language='french')
            language = 'fr'
            french_translation = front_primary
            german_translation = back_primary
        elif front_lang in ['german', 'mixed'] and back_lang == 'french':
            direction = 'de_to_fr'
            word = self.parser.extract_word(front_primary, expected_language='german')
            language = 'de'
            french_translation = back_primary
            german_translation = front_primary
        elif front_lang == 'french':
            # Default to French word even if back language unclear
            direction = 'fr_to_de'
            word = self.parser.extract_word(front_primary, expected_language='french')
            language = 'fr'
            french_translation = front_primary
            german_translation = back_primary
        else:
            # Default to German word
            direction = 'de_to_fr'
            word = self.parser.extract_word(front_primary, expected_language='german')
            language = 'de'
            french_translation = back_primary
            german_translation = front_primary
        
        # Check if word already exists
        existing = self.db.scalars(
            select(VocabularyWord).where(
                VocabularyWord.word == word,
                VocabularyWord.language == language,
                VocabularyWord.direction == direction,
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
        raw_row = card_data.get('raw_row', {}) or {}
        normalized_row = card_data.get('normalized_row') or self._normalize_row_keys(raw_row)  # type: ignore[arg-type]

        # Ease factor (stored as percentage in Anki exports)
        ease_value = self._parse_float_value(
            normalized_row.get('ease') or normalized_row.get('c_ease')
        )
        if ease_value is not None:
            progress.ease_factor = ease_value / 100 if ease_value > 10 else ease_value

        # Interval / reviews / lapses
        interval_value = self._parse_int_value(
            normalized_row.get('interval') or normalized_row.get('c_interval_in_days')
        )
        if interval_value is not None:
            progress.interval_days = interval_value

        reps_value = self._parse_int_value(
            normalized_row.get('reps') or normalized_row.get('c_reviews')
        )
        if reps_value is not None:
            progress.reps = reps_value

        lapses_value = self._parse_int_value(
            normalized_row.get('lapses') or normalized_row.get('c_lapses')
        )
        if lapses_value is not None:
            progress.lapses = lapses_value

        # Due dates and review timestamps
        due_source = (
            normalized_row.get('due')
            or normalized_row.get('c_due')
            or normalized_row.get('due_at')
        )
        due_at = self._parse_due_value(due_source)
        if due_at:
            progress.due_at = due_at
            progress.due_date = due_at.date()
            progress.next_review_date = due_at

        latest_review = (
            normalized_row.get('latestreview')
            or normalized_row.get('c_latestreview')
            or normalized_row.get('last_review')
        )
        last_review = self._parse_due_value(latest_review)
        if last_review:
            progress.last_review_date = last_review

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

    @staticmethod
    def _parse_int_value(value: Any) -> Optional[int]:
        """Safely parse an integer from various CSV representations."""
        if value is None:
            return None
        try:
            return int(float(str(value).strip()))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _parse_float_value(value: Any) -> Optional[float]:
        """Safely parse a float from various CSV representations."""
        if value is None:
            return None
        try:
            return float(str(value).strip())
        except (TypeError, ValueError):
            return None

    def _parse_due_value(self, value: Any) -> Optional[datetime]:
        """Parse due dates which may be stored as ISO strings or day offsets."""
        if value is None:
            return None

        text = str(value).strip()
        if not text:
            return None

        # Attempt ISO datetime or date parsing
        try:
            due_dt = datetime.fromisoformat(text)
            if due_dt.tzinfo is None:
                due_dt = due_dt.replace(tzinfo=timezone.utc)
            return due_dt
        except ValueError:
            pass

        # Day offsets (Anki sometimes stores days since collection epoch)
        int_value = self._parse_int_value(text)
        if int_value is not None:
            reference = datetime.now(timezone.utc)
            return reference + timedelta(days=int_value)

        return None
