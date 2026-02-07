"""Service for importing native content (YouTube, Articles) as Stories."""
from __future__ import annotations

import re
import uuid
from typing import Any
from urllib.parse import urlparse, parse_qs

import requests
from bs4 import BeautifulSoup
from loguru import logger
from sqlalchemy.orm import Session
from youtube_transcript_api import YouTubeTranscriptApi

from app.db.models.story import Story, Chapter, Scene
from app.services.llm_service import LLMService

class ContentImportError(Exception):
    """Failed to import content."""

class ContentImportService:
    """Service to import external content and convert to Lessons."""
    
    def __init__(self, db: Session, llm_service: LLMService | None = None) -> None:
        self.db = db
        self.llm = llm_service or LLMService()

    def import_from_url(self, url: str, user_id: uuid.UUID) -> dict[str, Any]:
        """Main entry point: Import content from a URL."""
        
        # 1. Identify content type and extract text
        if "youtube.com" in url or "youtu.be" in url:
            content_type = "youtube"
            text_content, metadata = self._extract_youtube(url)
        else:
            content_type = "article"
            text_content, metadata = self._extract_article(url)
            
        if not text_content:
            raise ContentImportError("Could not extract text from this URL. Try another source.")

        # 2. Process with LLM to generate Lesson Plan
        lesson_plan = self._generate_lesson_plan(text_content, metadata)
        
        # 3. Save to Database
        story = self._save_to_db(lesson_plan, url, content_type, metadata)
        
        return {
            "story_id": story.id,
            "title": story.title,
            "chapters_count": len(story.chapters)
        }

    def _extract_youtube(self, url: str) -> tuple[str, dict]:
        """Extract transcript from YouTube."""
        # Extract video ID
        query = urlparse(url).query
        params = parse_qs(query)
        video_id = params.get("v", [None])[0]
        if not video_id and "youtu.be" in url:
            video_id = url.split("/")[-1]
            
        if not video_id:
            raise ContentImportError("Invalid YouTube URL")

        try:
            # Try getting French transcript, fall back to auto-generated
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            try:
                transcript = transcript_list.find_transcript(['fr'])
            except:
                # If no French, try auto-generated
                try:
                    transcript = transcript_list.find_generated_transcript(['fr'])
                except:
                    # Fallback: Translate from English? For now, fail.
                    raise ContentImportError("No French subtitles found for this video.")

            full_text = " ".join([t['text'] for t in transcript.fetch()])
            
            # Get video title (simple hack or oembed)
            title = f"YouTube Video ({video_id})" # Fallback
            try:
                r = requests.get(f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json", timeout=5)
                if r.status_code == 200:
                    title = r.json().get("title", title)
            except:
                pass

            return full_text, {"title": title, "author": "YouTube Import"}
            
        except Exception as e:
            logger.error(f"YouTube import failed: {e}")
            raise ContentImportError(f"Could not fetch YouTube transcript: {str(e)}")

    def _extract_article(self, url: str) -> tuple[str, dict]:
        """Extract text from a web article."""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
                'Referer': 'https://www.google.com/',
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive'
            }
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove scripts and styles
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()
                
            # Get main text (heuristics)
            # Try to find common article containers
            article = soup.find('article') or soup.find('main') or soup.find(class_=re.compile(r'content|article|post'))
            
            if article:
                text = article.get_text(separator=' ', strip=True)
            else:
                text = soup.get_text(separator=' ', strip=True)
                
            title = soup.title.string if soup.title else "Imported Article"
            
            # Truncate if too long (LLM context limit)
            if len(text) > 20000:
                text = text[:20000] + "..."
                
            return text, {"title": title, "author": urlparse(url).netloc}
            
        except Exception as e:
            raise ContentImportError(f"Failed to fetch article: {str(e)}")

    def _generate_lesson_plan(self, text: str, metadata: dict) -> dict:
        """Use LLM to structure the content into a Lesson."""
        
        system_prompt = """You are an expert French teacher creating a lesson from raw content.
Your goal: Analyze the text and structure it into a "Story" for a learning app.

Input: Raw French text.

Output JSON Format:
{
  "title": "Refined Title",
  "summary": "Brief summary in English",
  "cefr_level": "A1/A2/B1/etc",
  "chapters": [
    {
      "title": "Part 1 Title",
      "text_segment": "The first chunk of text...",
      "key_vocabulary": [{"word": "pomme", "translation": "apple", "gender": "f"}],
      "comprehension_question": "What happened in this part?"
    }
  ]
}

Rules:
1. Divide text into logical chapters (max 3-5 chapters).
2. 'text_segment' must be the ORIGINAL text, just split up. Do not rewrite unless fixing bad formatting.
3. Extract 3-5 key vocab words per chapter.
4. Estimate CEFR level based on complexity.
"""
        
        user_prompt = f"Title: {metadata.get('title')}\n\nContent:\n{text[:15000]}" # Limit context
        
        try:
            result = self.llm.generate_chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,
                response_format={"type": "json_object"},
                max_tokens=2000
            ) 
            
            # Parse JSON
            import json
            return json.loads(result.content)
        except Exception as e:
            logger.error(f"LLM Lesson generation failed: {e}")
            raise ContentImportError("Failed to generate lesson from content.")

    def _save_to_db(self, plan: dict, url: str, content_type: str, metadata: dict) -> Story:
        """Persist the lesson plan as a Story."""
        
        story_id = f"import_{uuid.uuid4().hex[:8]}"
        
        # Create Story
        # Store metadata in themes list as key:value strings to satisfy schema
        themes_list = ["imported", f"type:{content_type}", f"url:{url}"]
        
        story = Story(
            id=story_id,
            title=plan.get("title", metadata.get("title")),
            subtitle=plan.get("summary", "Imported Content"),
            source_book=f"Imported from {content_type.capitalize()}",
            source_author=metadata.get("author", "Unknown"),
            themes=themes_list,
            target_levels=[plan.get("cefr_level", "B1")],
            is_active=True
        )
        self.db.add(story)
        
        # Create Chapters and Scenes
        for i, chap_data in enumerate(plan.get("chapters", []), 1):
            chapter_id = f"{story_id}_ch{i}"
            
            chapter = Chapter(
                id=chapter_id,
                story_id=story_id,
                order_index=i,
                title=chap_data.get("title", f"Part {i}"),
                target_level=plan.get("cefr_level", "B1"),
                learning_focus={"vocabulary": chap_data.get("key_vocabulary", [])}
            )
            self.db.add(chapter)
            
            # Create a single Scene for this chapter containing the text
            scene = Scene(
                id=f"{chapter_id}_scene1",
                chapter_id=chapter_id,
                order_index=1,
                location="Standard View",
                description="Reading segment",
                # Store the text as a narration variant
                narration_variants={"default": chap_data.get("text_segment", "")},
                objectives=[{"id": "read", "description": "Read the text", "type": "reading"}],
                player_interaction={
                    "type": "quiz",
                    "question": chap_data.get("comprehension_question"),
                    "vocabulary": chap_data.get("key_vocabulary")
                }
            )
            self.db.add(scene)
            
        self.db.commit()
        self.db.refresh(story)
        return story
