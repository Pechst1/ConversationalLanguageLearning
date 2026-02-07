#!/usr/bin/env python
"""Script to seed stories from YAML files into the database."""
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import yaml
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models.story import Story, Chapter, Scene, StoryProgress
from app.db.models.npc import NPC


STORIES_DIR = project_root / "app" / "data" / "stories"


def load_yaml(path: Path) -> dict:
    """Load a YAML file."""
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def seed_story(db: Session, story_dir: Path) -> None:
    """Seed a single story from its directory."""
    story_yaml_path = story_dir / "story.yaml"
    if not story_yaml_path.exists():
        print(f"  ⚠ No story.yaml found in {story_dir}")
        return
    
    story_data = load_yaml(story_yaml_path)
    story_id = story_data["id"]
    
    # Check if story already exists
    existing = db.get(Story, story_id)
    if existing:
        print(f"  ℹ Story '{story_id}' already exists, updating...")
        db.delete(existing)
        db.commit()
    
    # Create story
    story = Story(
        id=story_id,
        title=story_data["title"],
        subtitle=story_data.get("subtitle"),
        source_book=story_data.get("source", {}).get("book"),
        source_author=story_data.get("source", {}).get("author"),
        gutenberg_id=story_data.get("source", {}).get("gutenberg_id"),
        target_levels=story_data.get("metadata", {}).get("target_levels", []),
        themes=story_data.get("metadata", {}).get("themes", []),
        learning_objectives=story_data.get("learning_objectives", {}),
        estimated_duration_minutes=story_data.get("metadata", {}).get("estimated_duration_minutes", 60),
        cover_image_url=story_data.get("metadata", {}).get("cover_image_url"),
        is_active=True,
    )
    db.add(story)
    print(f"  ✓ Created story: {story.title}")
    
    # Seed NPCs
    npcs_dir = story_dir / "npcs"
    if npcs_dir.exists():
        for npc_file in npcs_dir.glob("*.yaml"):
            seed_npc(db, story_id, npc_file)
    
    # Seed chapters
    chapters_dir = story_dir / "chapters"
    if chapters_dir.exists():
        chapter_order = [c["id"] for c in story_data.get("chapters", [])]
        for chapter_file in chapters_dir.glob("*.yaml"):
            seed_chapter(db, story_id, chapter_file, chapter_order)
    
    db.commit()
    print(f"  ✓ Story '{story_id}' seeded successfully")


def seed_npc(db: Session, story_id: str, npc_file: Path) -> None:
    """Seed an NPC from a YAML file."""
    npc_data = load_yaml(npc_file)
    npc_id = npc_data["id"]
    
    # Check if NPC already exists
    existing = db.get(NPC, npc_id)
    if existing:
        db.delete(existing)
    
    npc = NPC(
        id=npc_id,
        story_id=story_id,
        name=npc_data["name"],
        display_name=npc_data.get("display_name"),
        role=npc_data.get("role"),
        backstory=npc_data.get("backstory"),
        avatar_url=npc_data.get("appearance", {}).get("avatar_url"),
        appearance_description=npc_data.get("appearance", {}).get("description"),
        personality=npc_data.get("personality", {}),
        speech_pattern=npc_data.get("speech_pattern", {}),
        voice_config=npc_data.get("voice_config"),
        information_tiers=npc_data.get("information_tiers", {}),
        relationship_config=npc_data.get("relationship_config", {}),
    )
    db.add(npc)
    print(f"    ✓ Created NPC: {npc.name}")


def seed_chapter(db: Session, story_id: str, chapter_file: Path, chapter_order: list[str]) -> None:
    """Seed a chapter from a YAML file."""
    chapter_data = load_yaml(chapter_file)
    chapter_id = chapter_data["id"]
    
    # Determine order index from story.yaml
    order_index = chapter_order.index(chapter_id) if chapter_id in chapter_order else 99
    
    chapter = Chapter(
        id=chapter_id,
        story_id=story_id,
        order_index=chapter_data.get("order_index", order_index),
        title=chapter_data["title"],
        target_level=chapter_data.get("target_level"),
        learning_focus=chapter_data.get("learning_focus", {}),
        cliffhanger=chapter_data.get("cliffhanger"),
        unlock_conditions=chapter_data.get("unlock_conditions"),
    )
    db.add(chapter)
    print(f"    ✓ Created chapter: {chapter.title}")
    
    # Seed scenes
    for scene_data in chapter_data.get("scenes", []):
        seed_scene(db, chapter_id, scene_data)


def seed_scene(db: Session, chapter_id: str, scene_data: dict) -> None:
    """Seed a scene from chapter data."""
    scene_id = scene_data["id"]
    
    # Extract narration variants
    narration_variants = scene_data.get("narration", {})
    if isinstance(narration_variants, str):
        narration_variants = {"A1": narration_variants}
    
    # Extract objectives
    objectives = scene_data.get("objectives", [])
    
    # Extract NPCs present
    npcs_present = scene_data.get("npcs_present", [])
    
    # Build consequences from various sources
    consequences = []
    
    # Add effects from player_interaction options
    if "player_interaction" in scene_data:
        pi = scene_data["player_interaction"]
        if "options" in pi:
            for opt in pi["options"]:
                if "effects" in opt:
                    consequences.append({
                        "trigger": {"choice": opt["id"]},
                        "effects": opt["effects"],
                    })
        if "response_handling" in pi:
            for intent, handler in pi["response_handling"].items():
                if "effects" in handler:
                    consequences.append({
                        "trigger": {"intent": intent},
                        "effects": handler["effects"],
                    })
    
    # Build transition rules
    transition_rules = []
    if "transition" in scene_data:
        trans = scene_data["transition"]
        transition_rules.append({
            "condition": {"trigger": trans.get("trigger", "complete")},
            "next_scene": trans.get("next_scene") or trans.get("next_chapter"),
            "narration": trans.get("narration"),
        })
    
    scene = Scene(
        id=scene_id,
        chapter_id=chapter_id,
        order_index=scene_data.get("order_index", 0),
        location=scene_data.get("setting", {}).get("location"),
        description=scene_data.get("setting", {}).get("description") or scene_data.get("description"),
        atmosphere=scene_data.get("setting", {}).get("atmosphere"),
        narration_variants=narration_variants,
        objectives=objectives,
        npcs_present=npcs_present,
        consequences=consequences,
        transition_rules=transition_rules,
        player_interaction=scene_data.get("player_interaction", {}),
        estimated_duration_minutes=scene_data.get("estimated_duration_minutes", 10),
    )
    db.add(scene)
    print(f"      ✓ Created scene: {scene_id}")


def main():
    """Main entry point."""
    print("🌹 Story Seeder")
    print("=" * 40)
    
    db = SessionLocal()
    
    try:
        # Find all story directories
        story_dirs = [d for d in STORIES_DIR.iterdir() if d.is_dir()]
        
        if not story_dirs:
            print(f"No stories found in {STORIES_DIR}")
            return
        
        for story_dir in sorted(story_dirs):
            print(f"\n📖 Seeding: {story_dir.name}")
            seed_story(db, story_dir)
        
        print("\n" + "=" * 40)
        print("✅ All stories seeded successfully!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
