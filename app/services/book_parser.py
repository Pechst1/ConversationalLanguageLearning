"""Book-to-Course Parser for converting uploaded books into interactive language courses.

This service handles:
1. Parsing uploaded book files (TXT, EPUB, PDF)
2. Splitting content into chapters and scenes
3. Extracting characters for NPC definitions
4. Generating vocabulary lists per chapter
5. Creating learning objectives and scene transitions
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import IO, Sequence

from loguru import logger
from sqlalchemy.orm import Session

from app.db.models.story import Story, Chapter, Scene
from app.db.models.npc import NPC
from app.db.models.user import User
from app.services.llm_service import LLMService


@dataclass
class ParsedChapter:
    """A chapter extracted from a book."""
    
    title: str
    order_index: int
    content: str
    estimated_word_count: int
    scenes: list["ParsedScene"] = field(default_factory=list)


@dataclass
class ParsedScene:
    """A scene extracted from a chapter."""
    
    order_index: int
    content: str
    location: str | None = None
    characters_present: list[str] = field(default_factory=list)
    narration_a1: str = ""
    narration_b1: str = ""


@dataclass
class ParsedCharacter:
    """A character extracted from the book."""
    
    name: str
    description: str = ""
    role: str = ""  # protagonist, antagonist, supporting
    personality_traits: list[str] = field(default_factory=list)


@dataclass
class BookParseResult:
    """Result of parsing a book into course content."""
    
    title: str
    author: str | None
    source_type: str  # txt, epub, pdf
    chapters: list[ParsedChapter]
    characters: list[ParsedCharacter]
    vocabulary: list[dict]  # Extracted important words
    themes: list[str]
    estimated_duration_minutes: int
    
    # Metadata
    parsed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    total_word_count: int = 0


BOOK_PARSE_PROMPT = """You are analyzing a book chapter for a French language learning course.
The source text may be in any language (English, German, etc.) but ALL OUTPUT must be in FRENCH.

Given this chapter text, extract:
1. 3-5 distinct scenes (logical breaks in the narrative)
2. Characters present in this chapter
3. Key vocabulary words (5-10 interesting French words from the story context)
4. A simplified A1-level summary IN FRENCH (2-3 sentences, simple vocabulary)
5. A B1-level summary IN FRENCH (3-4 sentences, intermediate vocabulary)

IMPORTANT: 
- ALL summaries and narrations MUST be written in FRENCH
- Translate location names to French (e.g., "New York City" → "la ville de New York")
- Keep character names unchanged (e.g., "Ishmael" stays "Ishmael")
- Vocabulary should be French words relevant to the themes

Respond in JSON:
{
    "scenes": [
        {
            "content_summary": "Résumé EN FRANÇAIS de ce qui se passe",
            "location": "Lieu EN FRANÇAIS (traduit si nécessaire)",
            "characters": ["Character1", "Character2"],
            "key_quote": "Une citation importante de cette section"
        }
    ],
    "characters": [
        {"name": "Name", "role": "protagonist/supporting", "traits": ["trait1", "trait2"], "description": "Brief character description in French"}
    ],
    "vocabulary": [
        {"word": "mot français", "translation": "traduction allemande", "context": "Comment il est utilisé"}
    ],
    "narration_a1": "Résumé simple EN FRANÇAIS pour les débutants",
    "narration_b1": "Résumé plus détaillé EN FRANÇAIS pour les apprenants intermédiaires",
    "themes": ["thème1", "thème2"]
}"""


class BookParserService:
    """Parse uploaded books into interactive language learning courses."""
    
    SUPPORTED_FORMATS = {"txt", "epub", "pdf", "html", "htm"}
    MAX_CHAPTER_LENGTH = 15000  # Characters per chapter for LLM processing
    
    def __init__(
        self,
        db: Session,
        *,
        llm_service: LLMService | None = None,
    ) -> None:
        self.db = db
        self.llm_service = llm_service or LLMService()
    
    def parse_book_file(
        self,
        file_content: bytes,
        filename: str,
        *,
        title: str | None = None,
        author: str | None = None,
        max_chapters: int = 10,
    ) -> BookParseResult:
        """Parse an uploaded book file into structured course content.
        
        Args:
            file_content: Raw file bytes
            filename: Original filename (used to detect format)
            title: Optional override for book title
            author: Optional override for author name
            max_chapters: Maximum number of chapters to process (default 10)
            
        Returns:
            BookParseResult with extracted chapters, characters, vocabulary
        """
        # Detect format from filename
        extension = Path(filename).suffix.lower().lstrip(".")
        if extension not in self.SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported format: {extension}. Supported: {self.SUPPORTED_FORMATS}")
        
        # Extract raw text based on format
        if extension == "txt":
            text = file_content.decode("utf-8", errors="replace")
        elif extension == "epub":
            text = self._extract_epub_text(file_content)
        elif extension == "pdf":
            text = self._extract_pdf_text(file_content)
        elif extension in ("html", "htm"):
            text = self._extract_html_text(file_content)
        else:
            raise ValueError(f"Parser not implemented for: {extension}")
        
        # Extract title and author if not provided
        if not title:
            title = self._extract_title(text, filename)
        if not author:
            author = self._extract_author(text)
        
        # Split into chapters
        all_chapters = self._split_into_chapters(text)
        
        # Limit number of chapters processed
        chapters = all_chapters[:max_chapters]
        
        logger.info(
            "Processing chapters",
            total_found=len(all_chapters),
            processing=len(chapters),
            max_chapters=max_chapters,
        )
        
        # Process each chapter with LLM
        all_characters: dict[str, ParsedCharacter] = {}
        all_vocabulary: list[dict] = []
        all_themes: set[str] = set()
        
        for chapter in chapters:
            if len(chapter.content) > 100:  # Skip very short chapters
                analysis = self._analyze_chapter_with_llm(chapter)
                
                # Merge characters
                for char in analysis.get("characters", []):
                    name = char.get("name", "").strip()
                    if name and name not in all_characters:
                        all_characters[name] = ParsedCharacter(
                            name=name,
                            role=char.get("role", "supporting"),
                            personality_traits=char.get("traits", []),
                        )
                
                # Collect vocabulary (deduplicate later)
                all_vocabulary.extend(analysis.get("vocabulary", []))
                
                # Collect themes
                all_themes.update(analysis.get("themes", []))
                
                # Create scenes from analysis
                for i, scene_data in enumerate(analysis.get("scenes", [])):
                    chapter.scenes.append(ParsedScene(
                        order_index=i,
                        content=scene_data.get("content_summary", ""),
                        location=scene_data.get("location"),
                        characters_present=scene_data.get("characters", []),
                        narration_a1=analysis.get("narration_a1", ""),
                        narration_b1=analysis.get("narration_b1", ""),
                    ))
        
        # Calculate totals
        total_words = sum(c.estimated_word_count for c in chapters)
        estimated_duration = max(30, total_words // 50)  # ~50 words per minute for learning
        
        # Deduplicate vocabulary by word
        unique_vocab = {v["word"]: v for v in all_vocabulary}.values()
        
        logger.info(
            "Book parsing complete",
            title=title,
            chapters=len(chapters),
            characters=len(all_characters),
            vocabulary=len(list(unique_vocab)),
            duration_minutes=estimated_duration,
        )
        
        return BookParseResult(
            title=title,
            author=author,
            source_type=extension,
            chapters=chapters,
            characters=list(all_characters.values()),
            vocabulary=list(unique_vocab),
            themes=list(all_themes),
            estimated_duration_minutes=estimated_duration,
            total_word_count=total_words,
        )
    
    def create_story_from_parse_result(
        self,
        result: BookParseResult,
        *,
        target_levels: list[str] | None = None,
    ) -> Story:
        """Convert a BookParseResult into a Story model with chapters and scenes.
        
        This creates all the database records needed for the interactive story.
        """
        story_id = self._generate_story_id(result.title)
        
        story = Story(
            id=story_id,
            title=result.title,
            subtitle=f"Based on {result.author}" if result.author else None,
            source_book=result.title,
            source_author=result.author,
            target_levels=target_levels or ["A1", "A2", "B1"],
            themes=result.themes,
            learning_objectives={
                "vocabulary": [v["word"] for v in result.vocabulary[:20]],
                "grammar": [],
                "functions": ["reading comprehension", "cultural understanding"],
            },
            estimated_duration_minutes=result.estimated_duration_minutes,
            is_active=True,
        )
        self.db.add(story)
        
        # Create NPCs from characters
        for char in result.characters:
            npc_id = f"{story_id}_{self._slugify(char.name)}"
            npc = NPC(
                id=npc_id,
                name=char.name,
                story_id=story_id,
                role=char.role,
                personality={"traits": char.personality_traits},
                backstory=char.description or f"A character from {result.title}",
            )
            self.db.add(npc)
        
        # Create chapters and scenes
        for parsed_chapter in result.chapters:
            chapter_id = f"{story_id}_ch{parsed_chapter.order_index}"
            
            chapter = Chapter(
                id=chapter_id,
                story_id=story_id,
                order_index=parsed_chapter.order_index,
                title=parsed_chapter.title,
                target_level="A2",  # Default, can be adjusted
                learning_focus={
                    "vocabulary": [v["word"] for v in result.vocabulary if v.get("chapter") == parsed_chapter.order_index][:10],
                    "grammar": [],
                },
            )
            self.db.add(chapter)
            
            # Create scenes
            for parsed_scene in parsed_chapter.scenes:
                scene_id = f"{chapter_id}_s{parsed_scene.order_index}"
                
                scene = Scene(
                    id=scene_id,
                    chapter_id=chapter_id,
                    order_index=parsed_scene.order_index,
                    location=parsed_scene.location,
                    description=parsed_scene.content,
                    narration_variants={
                        "A1": parsed_scene.narration_a1,
                        "A2": parsed_scene.narration_a1,  # Use simpler for A2 too
                        "B1": parsed_scene.narration_b1,
                    },
                    npcs_present=[f"{story_id}_{self._slugify(c)}" for c in parsed_scene.characters_present],
                    objectives=self._generate_scene_objectives(parsed_scene, result.title),
                )
                self.db.add(scene)
        
        self.db.commit()
        self.db.refresh(story)
        
        logger.info(
            "Created story from book",
            story_id=story_id,
            chapters=len(result.chapters),
            npcs=len(result.characters),
        )
        
        return story
    
    def _generate_scene_objectives(self, scene: ParsedScene, story_title: str) -> list[dict]:
        """Generate meaningful objectives based on scene content."""
        objectives = []
        
        # Primary objective: interact with character if present
        if scene.characters_present:
            main_char = scene.characters_present[0]
            objectives.append({
                "id": f"talk_{self._slugify(main_char)}",
                "description": f"Sprich mit {main_char}",
                "type": "interaction",
            })
            
            # Secondary: learn something about the character
            if len(scene.characters_present) > 1:
                objectives.append({
                    "id": f"discover_{self._slugify(main_char)}",
                    "description": f"Erfahre mehr über die Situation",
                    "type": "discovery",
                    "optional": True,
                })
        else:
            # No characters - exploration objective
            location = scene.location or "die Szene"
            objectives.append({
                "id": "explore",
                "description": f"Erkunde {location}",
                "type": "exploration",
            })
        
        # Always add a comprehension objective
        objectives.append({
            "id": "comprehend",
            "description": "Verstehe die Handlung dieser Szene",
            "type": "comprehension",
            "optional": True,
        })
        
        return objectives
    
    def _extract_epub_text(self, content: bytes) -> str:
        """Extract plain text from EPUB file."""
        try:
            import ebooklib
            from ebooklib import epub
            from io import BytesIO
            from bs4 import BeautifulSoup
            
            book = epub.read_epub(BytesIO(content))
            text_parts = []
            
            for item in book.get_items():
                if item.get_type() == ebooklib.ITEM_DOCUMENT:
                    soup = BeautifulSoup(item.get_content(), "html.parser")
                    text_parts.append(soup.get_text(separator="\n"))
            
            return "\n\n".join(text_parts)
        except ImportError:
            logger.warning("ebooklib not installed, EPUB parsing limited")
            return content.decode("utf-8", errors="replace")
    
    def _extract_pdf_text(self, content: bytes) -> str:
        """Extract plain text from PDF file."""
        try:
            import fitz  # PyMuPDF
            from io import BytesIO
            
            doc = fitz.open(stream=content, filetype="pdf")
            text_parts = []
            
            for page in doc:
                text_parts.append(page.get_text())
            
            return "\n\n".join(text_parts)
        except ImportError:
            logger.warning("PyMuPDF not installed, PDF parsing limited")
            return ""

    def _extract_html_text(self, content: bytes) -> str:
        """Extract plain text from HTML file."""
        try:
            from bs4 import BeautifulSoup
            
            soup = BeautifulSoup(content, "html.parser")
            
            # Remove scripts and styles
            for script in soup(["script", "style"]):
                script.decompose()
                
            # Get text
            text = soup.get_text(separator="\n")
            
            # Clean up empty lines
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            return "\n".join(lines)
            
        except Exception as e:
            logger.error(f"HTML parsing failed: {e}")
            return content.decode("utf-8", errors="replace")
    
    def _extract_title(self, text: str, filename: str) -> str:
        """Extract title from text or infer from filename."""
        # Look for title patterns
        lines = text.split("\n")[:20]
        for line in lines:
            line = line.strip()
            if len(line) > 5 and len(line) < 100 and line.isupper():
                return line.title()
        
        # Fall back to filename
        return Path(filename).stem.replace("_", " ").replace("-", " ").title()
    
    def _extract_author(self, text: str) -> str | None:
        """Try to extract author from text."""
        patterns = [
            r"by\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",
            r"Author:\s*(.+)",
            r"par\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text[:2000], re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _split_into_chapters(self, text: str) -> list[ParsedChapter]:
        """Split text into chapters based on common patterns."""
        
        # Helper to convert Roman numerals to int
        def roman_to_int(s: str) -> int:
            roman_map = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}
            s = s.upper()
            result = 0
            for i, c in enumerate(s):
                if c not in roman_map:
                    return 0
                if i + 1 < len(s) and roman_map.get(s[i + 1], 0) > roman_map[c]:
                    result -= roman_map[c]
                else:
                    result += roman_map[c]
            return result
        
        def parse_chapter_number(num_str: str) -> int:
            """Parse chapter number from string (handles Roman numerals)."""
            num_str = num_str.strip()
            if num_str.isdigit():
                return int(num_str)
            # Try Roman numeral
            roman_val = roman_to_int(num_str)
            if roman_val > 0:
                return roman_val
            return 0
        
        # Common chapter patterns
        patterns = [
            r"(?:^|\n)\s*(?:CHAPTER|CHAPITRE|Chapter|Chapitre)\s+(\d+|[IVXLC]+)(?:\s*[:\.\-]\s*(.+?))?(?:\n|$)",
            r"(?:^|\n)\s*(\d+|[IVXLC]+)\.\s*(.+?)(?:\n|$)",
        ]
        
        chapters = []
        
        for pattern in patterns:
            matches = list(re.finditer(pattern, text, re.MULTILINE))
            if len(matches) >= 2:  # Found chapter markers
                for i, match in enumerate(matches):
                    start = match.end()
                    end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
                    
                    chapter_num_str = match.group(1)
                    chapter_num = parse_chapter_number(chapter_num_str)
                    chapter_title = match.group(2) if match.lastindex >= 2 else f"Chapter {chapter_num_str}"
                    content = text[start:end].strip()
                    
                    if len(content) > 100:
                        chapters.append(ParsedChapter(
                            title=chapter_title.strip() if chapter_title else f"Chapter {chapter_num_str}",
                            order_index=chapter_num if chapter_num > 0 else i,  # Use actual chapter number
                            content=content[:self.MAX_CHAPTER_LENGTH],
                            estimated_word_count=len(content.split()),
                        ))
                break
        
        # Sort chapters by their actual order_index (chapter number)
        chapters.sort(key=lambda c: c.order_index)
        
        # Re-index to be 0-based sequential after sorting
        for i, ch in enumerate(chapters):
            ch.order_index = i
        
        # Fallback: split by length
        if not chapters:
            chunk_size = 5000
            for i, start in enumerate(range(0, len(text), chunk_size)):
                content = text[start:start + chunk_size]
                if len(content) > 100:
                    chapters.append(ParsedChapter(
                        title=f"Part {i + 1}",
                        order_index=i,
                        content=content,
                        estimated_word_count=len(content.split()),
                    ))
        
        return chapters
    
    def _analyze_chapter_with_llm(self, chapter: ParsedChapter) -> dict:
        """Use LLM to analyze chapter content and extract structured data."""
        
        try:
            messages = [
                {"role": "user", "content": f"Analyze this chapter:\n\n{chapter.content[:12000]}"},
            ]
            
            result = self.llm_service.generate_chat_completion(
                messages,
                temperature=0.3,
                max_tokens=1500,
                system_prompt=BOOK_PARSE_PROMPT,
            )
            
            # Parse JSON response
            import json
            content = result.content.strip()
            if content.startswith("```"):
                lines = content.split("\n")[1:-1]
                content = "\n".join(lines)
            
            return json.loads(content)
            
        except Exception as e:
            logger.error("LLM analysis failed for chapter", error=str(e), chapter=chapter.title)
            return {
                "scenes": [],
                "characters": [],
                "vocabulary": [],
                "themes": [],
                "narration_a1": "",
                "narration_b1": "",
            }
    
    def _generate_story_id(self, title: str) -> str:
        """Generate a URL-safe story ID from title."""
        return self._slugify(title)[:40] + "_" + str(uuid.uuid4())[:8]
    
    def _slugify(self, text: str) -> str:
        """Convert text to URL-safe slug."""
        text = text.lower()
        text = re.sub(r"[^a-z0-9\s-]", "", text)
        text = re.sub(r"[\s-]+", "_", text)
        return text.strip("_")


__all__ = ["BookParserService", "BookParseResult", "ParsedChapter", "ParsedScene", "ParsedCharacter"]
