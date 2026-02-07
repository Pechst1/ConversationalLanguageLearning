"""Story visualization service for AI-generated scene images.

This service generates immersive visuals for story scenes using AI image generation,
creating an illustrated book experience that adapts to the narrative.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import httpx
from loguru import logger
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models.story import Scene, Chapter, Story
from app.db.models.user import User
from app.utils.cache import cache_backend


@dataclass
class GeneratedImage:
    """Result of image generation."""
    
    url: str  # URL to the generated image
    prompt: str  # The prompt used
    style: str  # The art style applied
    cached: bool = False
    generated_at: datetime | None = None


# Art styles for different story moods
ART_STYLES = {
    "whimsical": "watercolor illustration, soft edges, dreamy atmosphere, children's book style",
    "dramatic": "digital art, dramatic lighting, cinematic composition, detailed",
    "classic": "oil painting style, classical composition, rich colors, museum quality",
    "minimal": "minimalist illustration, clean lines, muted colors, elegant simplicity",
    "fantasy": "fantasy art, magical atmosphere, glowing elements, ethereal lighting",
}

# Style mapping based on themes
THEME_TO_STYLE = {
    "philosophy": "minimal",
    "adventure": "dramatic",
    "friendship": "whimsical",
    "love": "classic",
    "magic": "fantasy",
    "nature": "whimsical",
    "mystery": "dramatic",
    "childhood": "whimsical",
}


class StoryVisualizationService:
    """Generate AI visualizations for story scenes."""
    
    CACHE_TTL_SECONDS = 86400 * 7  # 1 week cache
    DEFAULT_STYLE = "whimsical"
    
    def __init__(self, db: Session) -> None:
        self.db = db
        self.api_key = settings.OPENAI_API_KEY
        self._client: httpx.AsyncClient | None = None
    
    @property
    def client(self) -> httpx.AsyncClient:
        if not self._client:
            self._client = httpx.AsyncClient(
                timeout=60.0,
                headers={"Authorization": f"Bearer {self.api_key}"}
            )
        return self._client
    
    async def generate_scene_image(
        self,
        scene: Scene,
        *,
        user: User | None = None,
        style_override: str | None = None,
        include_avatar: bool = False,
    ) -> GeneratedImage:
        """Generate an AI image for a story scene.
        
        Args:
            scene: The scene to visualize
            user: Optional user for avatar inclusion
            style_override: Override the automatic style selection
            include_avatar: Whether to include user's avatar in the image
            
        Returns:
            GeneratedImage with URL and metadata
        """
        # Check cache first
        cache_key = self._get_cache_key(scene.id, style_override, include_avatar)
        cached = cache_backend.get("story:visuals", cache_key)
        if cached:
            logger.debug("Returning cached scene image", scene_id=scene.id)
            return GeneratedImage(
                url=cached["url"],
                prompt=cached["prompt"],
                style=cached["style"],
                cached=True,
                generated_at=datetime.fromisoformat(cached["generated_at"]),
            )
        
        # Get chapter and story for context
        chapter = self.db.get(Chapter, scene.chapter_id)
        story = self.db.get(Story, chapter.story_id) if chapter else None
        
        # Determine art style
        style = style_override or self._determine_style(story, scene)
        style_description = ART_STYLES.get(style, ART_STYLES[self.DEFAULT_STYLE])
        
        # Build the prompt
        prompt = self._build_image_prompt(scene, chapter, story, style_description, include_avatar, user)
        
        # Generate the image
        try:
            image_url = await self._call_dalle(prompt)
        except Exception as e:
            logger.error("Image generation failed", error=str(e), scene_id=scene.id)
            # Return a fallback/placeholder
            return GeneratedImage(
                url=self._get_fallback_image(style),
                prompt=prompt,
                style=style,
                cached=False,
            )
        
        # Cache the result
        result = GeneratedImage(
            url=image_url,
            prompt=prompt,
            style=style,
            cached=False,
            generated_at=datetime.now(timezone.utc),
        )
        
        cache_backend.set(
            "story:visuals",
            cache_key,
            {
                "url": image_url,
                "prompt": prompt,
                "style": style,
                "generated_at": result.generated_at.isoformat(),
            },
            ttl_seconds=self.CACHE_TTL_SECONDS,
        )
        
        logger.info(
            "Generated scene image",
            scene_id=scene.id,
            style=style,
        )
        
        return result
    
    async def generate_chapter_cover(
        self,
        chapter: Chapter,
        *,
        style_override: str | None = None,
    ) -> GeneratedImage:
        """Generate a cover image for a chapter."""
        
        story = self.db.get(Story, chapter.story_id)
        style = style_override or self._determine_style(story, None)
        style_description = ART_STYLES.get(style, ART_STYLES[self.DEFAULT_STYLE])
        
        # Build cover prompt
        prompt = f"""A beautiful book chapter title page illustration.
Title: "{chapter.title}"
{f"From the book: {story.title}" if story else ""}

Style: {style_description}
The image should be evocative and set the mood for the chapter.
No text or letters in the image."""
        
        try:
            image_url = await self._call_dalle(prompt)
        except Exception as e:
            logger.error("Chapter cover generation failed", error=str(e))
            image_url = self._get_fallback_image(style)
        
        return GeneratedImage(
            url=image_url,
            prompt=prompt,
            style=style,
            generated_at=datetime.now(timezone.utc),
        )

    async def generate_story_cover(
        self,
        story: Story,
        *,
        style_override: str | None = None,
    ) -> GeneratedImage:
        """Generate a cover image for a story (book cover)."""
        
        style = style_override or self._determine_style(story, None)
        style_description = ART_STYLES.get(style, ART_STYLES[self.DEFAULT_STYLE])
        
        # Create a rich prompt for the book cover
        prompt = f"""A beautiful book cover illustration.
Title: "{story.title}"
Author: "{story.source_author or 'Unknown'}"

Themes: {', '.join(story.themes[:3]) if story.themes else 'General'}

Style: {style_description}
Create a high-quality, artistic book cover design.
No text or letters in the image, just the artwork."""
        
        try:
            image_url = await self._call_dalle(prompt)
            
            # Update story with new cover URL
            story.cover_image_url = image_url
            self.db.add(story)
            self.db.commit()
            
        except Exception as e:
            logger.error("Story cover generation failed", error=str(e))
            image_url = self._get_fallback_image(style)
            # Don't save fallback to DB to allow retrying? Or save it? 
            # Better to save it so we have something.
            story.cover_image_url = image_url
            self.db.add(story)
            self.db.commit()
        
        return GeneratedImage(
            url=image_url,
            prompt=prompt,
            style=style,
            generated_at=datetime.now(timezone.utc),
        )
    
    def _build_image_prompt(
        self,
        scene: Scene,
        chapter: Chapter | None,
        story: Story | None,
        style_description: str,
        include_avatar: bool,
        user: User | None,
    ) -> str:
        """Build a detailed prompt for scene visualization."""
        
        parts = []
        
        # Scene description
        if scene.description:
            parts.append(f"Scene: {scene.description[:200]}")
        
        # Location
        if scene.location:
            parts.append(f"Setting: {scene.location}")
        
        # Atmosphere
        if scene.atmosphere:
            parts.append(f"Mood: {scene.atmosphere}")
        
        # Characters (NPCs)
        if scene.npcs_present:
            npc_names = ", ".join(scene.npcs_present[:3])
            parts.append(f"Characters present: {npc_names}")
        
        # Book context
        if story and story.source_book:
            parts.append(f"From the story: {story.source_book}")
        
        # User avatar placeholder
        if include_avatar and user:
            avatar_desc = user.avatar_description if hasattr(user, 'avatar_description') else "a young person"
            parts.append(f"Include a figure representing the reader: {avatar_desc}")
        
        # Style and format
        parts.append(f"\nArt style: {style_description}")
        parts.append("Create an immersive illustration suitable for a language learning storybook.")
        parts.append("No text or letters in the image. Focus on visual storytelling.")
        
        return "\n".join(parts)
    
    def _determine_style(self, story: Story | None, scene: Scene | None) -> str:
        """Determine the best art style based on story themes."""
        
        if story and story.themes:
            for theme in story.themes:
                theme_lower = theme.lower()
                for key in THEME_TO_STYLE:
                    if key in theme_lower:
                        return THEME_TO_STYLE[key]
        
        # Default based on scene atmosphere
        if scene and scene.atmosphere:
            atmo = scene.atmosphere.lower()
            if "tense" in atmo or "dark" in atmo:
                return "dramatic"
            if "magical" in atmo or "wonder" in atmo:
                return "fantasy"
            if "peaceful" in atmo or "calm" in atmo:
                return "whimsical"
        
        return self.DEFAULT_STYLE
    
    async def _call_dalle(self, prompt: str, size: str = "1024x1024") -> str:
        """Call DALL-E API to generate an image."""
        
        if not self.api_key:
            raise ValueError("OpenAI API key not configured")
        
        response = await self.client.post(
            "https://api.openai.com/v1/images/generations",
            json={
                "model": "dall-e-3",
                "prompt": prompt,
                "n": 1,
                "size": size,
                "quality": "standard",
            },
        )
        
        response.raise_for_status()
        data = response.json()
        
        return data["data"][0]["url"]
    
    def _get_cache_key(self, scene_id: str, style: str | None, include_avatar: bool) -> str:
        """Generate a cache key for a scene visualization."""
        key_parts = f"{scene_id}:{style or 'auto'}:{include_avatar}"
        return hashlib.md5(key_parts.encode()).hexdigest()
    
    def _get_fallback_image(self, style: str) -> str:
        """Return a fallback placeholder image URL."""
        # Using a gradient placeholder service
        colors = {
            "whimsical": "E8D5B7,F5E6D3",
            "dramatic": "2C3E50,34495E",
            "classic": "8B4513,D2691E",
            "minimal": "F5F5F5,EEEEEE",
            "fantasy": "4B0082,8A2BE2",
        }
        color = colors.get(style, "CCCCCC,EEEEEE")
        return f"https://via.placeholder.com/1024x1024/{color.split(',')[0]}/{color.split(',')[1]}?text=Scene"


__all__ = ["StoryVisualizationService", "GeneratedImage", "ART_STYLES"]
