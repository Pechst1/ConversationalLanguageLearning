
import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import patch

# Add current directory to path
sys.path.append(os.getcwd())

from app.db.session import SessionLocal
from app.services.book_parser import BookParserService, ParsedChapter
from app.services.story_visualization import StoryVisualizationService
from app.db.models.story import Story, Scene, Chapter

async def main():
    db = SessionLocal()
    try:
        print("Starting Moby Dick import process (Limiting to first 3 chapters)...")
        
        file_path = Path("pg2701-h/pg2701-images.html")
        if not file_path.exists():
            print(f"Error: File not found at {file_path}")
            return

        # Check if story exists and delete it
        existing = db.query(Story).filter(Story.source_book.ilike("%Moby Dick%")).first()
        if existing:
            print(f"Deleting existing story: {existing.title}")
            db.query(Scene).filter(Scene.chapter_id.in_(
                db.query(Chapter.id).filter(Chapter.story_id == existing.id)
            )).delete(synchronize_session=False)
            db.query(Chapter).filter(Chapter.story_id == existing.id).delete(synchronize_session=False)
            db.delete(existing)
            db.commit()

        # Read file
        content = file_path.read_bytes()
        print(f"File size: {len(content)} bytes")
        
        # Monkey patch _split_into_chapters to return only first 3
        original_split = BookParserService._split_into_chapters
        
        def mocked_split(self, text):
            chapters = original_split(self, text)
            print(f"Found {len(chapters)} chapters. Limiting to first 3 for demo.")
            return chapters[:3]
            
        BookParserService._split_into_chapters = mocked_split

        print("Parsing book...")
        parser = BookParserService(db)
        # Pass the FULL content but we mocked split to limit processing
        result = parser.parse_book_file(content, "moby_dick.html")
        
        print(f"Parsed: {result.title} by {result.author}")
        print(f"Chapters processed: {len(result.chapters)}")
        
        print("Creating story in database...")
        story = parser.create_story_from_parse_result(result)
        
        # Manually trigger cover generation since we are bypassing the API endpoint locally
        print("Generating cover image...")
        viz_service = StoryVisualizationService(db)
        await viz_service.generate_story_cover(story, style_override="classic")
        
        print(f"Story created with ID: {story.id}")
        print(f"Cover URL: {story.cover_image_url}")

    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
