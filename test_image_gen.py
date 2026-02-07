
import asyncio
import os
import sys

# Add current directory to path
sys.path.append(os.getcwd())

from app.db.session import SessionLocal
from app.services.story_visualization import StoryVisualizationService
from app.db.models.story import Story, Scene, Chapter
from datetime import datetime

async def main():
    db = SessionLocal()
    try:
        print("Starting Image Generation Test...")
        viz_service = StoryVisualizationService(db)

        # 1. Test Scene Generation
        # Try to find a scene
        scene = db.query(Scene).first()
        if not scene:
            print("No scene found in DB. Creating a dummy one.")
            # Note: This might fail FK constraints if we don't handle parent objects.
            # So let's create a full chain if needed.
            story = Story(id="test_story", title="Test Story", source_book="Test Book", is_active=True)
            chapter = Chapter(id="test_ch1", story_id="test_story", order_index=0, title="Test Chapter")
            scene = Scene(id="test_scene1", chapter_id="test_ch1", order_index=0, description="A beautiful garden in Paris.", narration_variants={})
            
            # Use merge to avoid unique constraint if it exists from previous run
            db.merge(story)
            db.merge(chapter)
            db.merge(scene)
            db.commit()
            
            # Query back to get relationships loaded
            scene = db.query(Scene).get("test_scene1")

        print(f"Testing Scene Image for scene: {scene.id}")
        image = await viz_service.generate_scene_image(scene, style_override="whimsical")
        print(f"Scene Image URL: {image.url}")

        # 2. Test Story Cover Generation (New Feature)
        print("\nTesting Story Cover Generation...")
        story = db.query(Story).filter(Story.id == scene.chapter.story_id).first()
        if story:
            cover = await viz_service.generate_story_cover(story, style_override="classic")
            print(f"Story Cover URL: {cover.url}")
            
            # Verify it persisted
            db.refresh(story)
            print(f"Story.cover_image_url in DB: {story.cover_image_url}")
        else:
            print("Could not find story for cover test.")

    except Exception as e:
        print(f"Test Failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
