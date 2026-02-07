"""API endpoints for Story RPG feature."""
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, BackgroundTasks
from loguru import logger
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.db.models.user import User
from app.db.models.error import UserError
from app.services.story_service import StoryService
from app.services.npc_service import NPCService
from app.schemas.story import (
    StoryRead,
    StoryWithProgressRead,
    StoryProgressRead,
    StoryStartRequest,
    StoryStartResponse,
    StoryInputRequest,
    StoryInputResponse,
    SceneRead,
    ChapterRead,
    ObjectiveRead,
    NPCInSceneRead,
    NPCResponseRead,
    ConsequenceRead,
)

router = APIRouter()

@router.post("/upload-book")
async def upload_book(
    *,
    file: UploadFile = File(...),
    title: str | None = Form(None),
    author: str | None = Form(None),
    target_levels: str | None = Form("A1,A2,B1"),
    max_chapters: int = Form(5),
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Upload a book file and convert it to an interactive language course in the background.
    Returns a task_id to track progress.
    """
    # Validate file type
    filename = file.filename or "unknown.txt"
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    
    if extension not in {"txt", "epub", "pdf", "html", "htm"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format: {extension}. Use TXT, EPUB, PDF, or HTML.",
        )
    
    # Read file content
    content = await file.read()
    
    if len(content) > 10_000_000:  # 10MB limit
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File too large. Maximum size is 10MB.",
        )

    # Create task ID
    import uuid
    task_id = str(uuid.uuid4())
    
    # Initial status
    upload_tasks[task_id] = {
        "status": "processing",
        "progress": 0,
        "message": "Starting upload...",
        "filename": filename
    }
    
    # Start background task
    background_tasks.add_task(
        process_book_task,
        task_id,
        content,
        filename,
        title,
        author,
        target_levels,
        max_chapters
    )
    
    return {"task_id": task_id, "message": "Upload started"}

@router.get("/upload-status/{task_id}")
async def get_upload_status(task_id: str) -> dict:
    """Get the status of a book upload task."""
    status = upload_tasks.get(task_id)
    if not status:
        raise HTTPException(status_code=404, detail="Task not found")
    return status

# Global task storage (in-memory for now)
# Global task storage (in-memory for now)
upload_tasks = {}

class ContentImportRequest(BaseModel):
    url: str

@router.post("/import")
async def import_content(
    request: ContentImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Import content from URL (YouTube/Article)."""
    from app.services.content_import import ContentImportService, ContentImportError
    
    service = ContentImportService(db)
    try:
        return service.import_from_url(request.url, current_user.id)
    except ContentImportError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Import failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process content"
        )

@router.post("/{story_id}/discuss", response_model=dict)
async def start_story_discussion(
    story_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Start a conversational session based on this story/article."""
    from app.services.article_conversation import ArticleConversationService
    
    service = ArticleConversationService(db)
    try:
        session = service.start_article_session(story_id, current_user)
        return {"session_id": str(session.id)}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to start discussion session: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to start session")

async def process_book_task(
    task_id: str,
    content: bytes,
    filename: str,
    title: str | None,
    author: str | None,
    target_levels: str | None,
    max_chapters: int,
):
    """Background task to process book upload."""
    from app.services.book_parser import BookParserService
    from app.db.session import SessionLocal
    
    db = SessionLocal()
    try:
        upload_tasks[task_id]["message"] = "Parsing book content..."
        upload_tasks[task_id]["progress"] = 10
        
        parser = BookParserService(db)
        
        # Limit max_chapters
        chapter_limit = min(max(1, max_chapters), 50)
        
        parse_result = parser.parse_book_file(
            content,
            filename,
            title=title,
            author=author,
            max_chapters=chapter_limit,
        )
        
        upload_tasks[task_id]["message"] = f"Creating story from {len(parse_result.chapters)} chapters..."
        upload_tasks[task_id]["progress"] = 50
        
        levels = [l.strip() for l in (target_levels or "A1,A2,B1").split(",")]
        
        story = parser.create_story_from_parse_result(
            parse_result,
            target_levels=levels,
        )
        
        # Trigger cover generation
        from app.services.story_visualization import StoryVisualizationService
        viz_service = StoryVisualizationService(db)
        # Verify if async call is needed here or if we should sync call it? 
        # generate_story_cover is async. We are in async def, so await is fine.
        upload_tasks[task_id]["message"] = "Generating cover image..."
        upload_tasks[task_id]["progress"] = 80
        
        try:
            await viz_service.generate_story_cover(story)
        except Exception as e:
            logger.error(f"Cover generation failed: {e}")
            # Continue even if cover fails
            
        upload_tasks[task_id]["status"] = "completed"
        upload_tasks[task_id]["progress"] = 100
        upload_tasks[task_id]["message"] = "Ready!"
        upload_tasks[task_id]["story_id"] = story.id
        
    except Exception as e:
        logger.exception(f"Upload task {task_id} failed")
        upload_tasks[task_id]["status"] = "failed"
        upload_tasks[task_id]["error"] = str(e)
    finally:
        db.close()

async def generate_cover_task(story_id: str):
    """Background task to generate story cover."""
    from app.db.session import SessionLocal
    from app.db.models.story import Story
    from app.services.story_visualization import StoryVisualizationService
    
    db = SessionLocal()
    try:
        story = db.get(Story, story_id)
        if story:
            viz_service = StoryVisualizationService(db)
            await viz_service.generate_story_cover(story)
            logger.info(f"Generated cover for story {story_id}")
    except Exception as e:
        logger.error(f"Background cover generation failed for {story_id}: {e}")
    finally:
        db.close()


# ============================================================================
# Helper Functions for Error Tracking and XP
# ============================================================================

def _persist_story_errors(
    *,
    db: Session,
    user: User,
    story_id: str,
    scene_id: str,
    error_result,
) -> None:
    """Persist detected errors to UserError table for SRS tracking."""
    from app.core.error_concepts import get_concept_for_pattern, get_concept_for_category
    from app.db.models.error import UserErrorConcept
    
    # Track which concepts we've already processed this turn to avoid duplicates
    processed_concepts: set[str] = set()
    
    for error in error_result.errors:
        # Skip low confidence errors
        if error.confidence < 0.6:
            continue
        
        # Extract subcategory from error if available (new LLM schema)
        subcategory = getattr(error, 'subcategory', None) or error.code.replace('llm_', '') if error.code.startswith('llm_') else error.code
        
        # Check for existing error with same category + subcategory
        existing = db.query(UserError).filter(
            UserError.user_id == user.id,
            UserError.error_category == error.category,
            UserError.subcategory == subcategory,
        ).first()
        
        if existing:
            # Update existing error - repeated mistake
            existing.occurrences = (existing.occurrences or 1) + 1
            existing.lapses = (existing.lapses or 0) + 1
            existing.original_text = error.span  # Store the erroneous text
            existing.context_snippet = error.message  # Store the explanation
            existing.correction = error.suggestion  # Store the corrected version
            existing.difficulty = min(10.0, (existing.difficulty or 5.0) + 0.5)
            existing.next_review_date = datetime.now(timezone.utc)
            if existing.state in ("review", "mastered"):
                existing.state = "relearning"
            existing.updated_at = datetime.now(timezone.utc)
            
            logger.debug(
                "Story: Updated existing error",
                category=error.category,
                subcategory=subcategory,
                occurrences=existing.occurrences,
            )
        else:
            # Create new error record
            user_error = UserError(
                user_id=user.id,
                session_id=None,  # No session in story mode
                message_id=None,
                error_category=error.category,
                error_pattern=subcategory,  # Keep pattern for backwards compatibility
                subcategory=subcategory,  # New fine-grained category
                original_text=error.span,  # The exact erroneous text from user
                correction=error.suggestion,  # The corrected version
                context_snippet=error.message,  # The explanation
                state="new",
                stability=0.0,
                difficulty=5.0,
                occurrences=1,
                next_review_date=datetime.now(timezone.utc),
            )
            db.add(user_error)
            
            logger.debug(
                "Story: Created new error record",
                category=error.category,
                subcategory=subcategory,
                original_text=error.span,
            )
        
        # Update parent concept for concept-level SRS
        concept = get_concept_for_pattern(subcategory)
        if not concept:
            concept = get_concept_for_category(error.category)
        
        if concept and concept.id not in processed_concepts:
            processed_concepts.add(concept.id)
            
            user_concept = db.query(UserErrorConcept).filter(
                UserErrorConcept.user_id == user.id,
                UserErrorConcept.concept_id == concept.id,
            ).first()
            
            if user_concept:
                user_concept.increment_occurrence()
            else:
                user_concept = UserErrorConcept(
                    user_id=user.id,
                    concept_id=concept.id,
                    total_occurrences=1,
                    last_occurrence_date=datetime.now(timezone.utc),
                    next_review_date=datetime.now(timezone.utc),
                    state="new",
                )
                db.add(user_concept)
    
    db.commit()


def _calculate_story_xp(
    *,
    content: str,
    error_count: int,
    has_story_progress: bool,
    objectives_completed: list[str] | None = None,
) -> dict:
    """Calculate XP earned for a story interaction with breakdown."""
    breakdown = []
    total_xp = 0
    
    # Base engagement XP
    base_xp = 5
    total_xp += base_xp
    breakdown.append({"reason": "Konversation", "amount": base_xp})
    
    # Bonus for longer messages (more language practice)
    word_count = len(content.split())
    if word_count >= 10:
        length_bonus = 10
        total_xp += length_bonus
        breakdown.append({"reason": "Ausführliche Antwort", "amount": length_bonus})
    elif word_count >= 5:
        length_bonus = 5
        total_xp += length_bonus
        breakdown.append({"reason": "Gute Antwort", "amount": length_bonus})
    
    # Penalty for errors
    if error_count > 0:
        penalty = min(total_xp - 5, error_count * 2)  # Don't go below 5
        if penalty > 0:
            total_xp -= penalty
            breakdown.append({"reason": f"{error_count} Fehler", "amount": -penalty})
    else:
        # No error bonus (30%)
        bonus = int(total_xp * 0.3)
        if bonus > 0:
            total_xp += bonus
            breakdown.append({"reason": "Perfekte Grammatik", "amount": bonus})
    
    # Story progress bonus
    if has_story_progress and objectives_completed:
        progress_bonus = 20
        total_xp += progress_bonus
        breakdown.append({"reason": "Ziel erreicht!", "amount": progress_bonus})
    
    return {
        "total": total_xp,
        "breakdown": breakdown,
    }


# ============================================================================
# Scene Visualization Endpoints
# ============================================================================

@router.get("/{story_id}/scene/{scene_id}/visualization")
async def get_scene_visualization(
    story_id: str,
    scene_id: str,
    style: str | None = None,
    include_avatar: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Generate an AI visualization for a story scene.
    
    Returns a URL to a generated image that illustrates the scene.
    Results are cached for 1 week.
    
    Args:
        style: Optional art style override (whimsical, dramatic, classic, minimal, fantasy)
        include_avatar: Whether to include user's avatar in the image
    """
    from app.services.story_visualization import StoryVisualizationService
    from app.db.models.story import Scene
    
    scene = db.get(Scene, scene_id)
    if not scene:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scene not found",
        )
    
    viz_service = StoryVisualizationService(db)
    
    result = await viz_service.generate_scene_image(
        scene,
        user=current_user if include_avatar else None,
        style_override=style,
        include_avatar=include_avatar,
    )
    
    return {
        "scene_id": scene_id,
        "image_url": result.url,
        "art_style": result.style,
        "cached": result.cached,
        "generated_at": result.generated_at.isoformat() if result.generated_at else None,
    }


@router.get("/{story_id}/chapter/{chapter_id}/cover")
async def get_chapter_cover(
    story_id: str,
    chapter_id: str,
    style: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Generate an AI cover image for a story chapter."""
    from app.services.story_visualization import StoryVisualizationService
    from app.db.models.story import Chapter
    
    chapter = db.get(Chapter, chapter_id)
    if not chapter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chapter not found",
        )
    
    viz_service = StoryVisualizationService(db)
    
    result = await viz_service.generate_chapter_cover(
        chapter,
        style_override=style,
    )
    
    return {
        "chapter_id": chapter_id,
        "image_url": result.url,
        "art_style": result.style,
    }


# ============================================================================
# Story Endpoints
# ============================================================================

@router.get("", response_model=list[StoryWithProgressRead])
async def list_stories(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """List all available stories with user progress."""
    service = StoryService(db)
    stories = service.list_available_stories(current_user)
    
    result = []
    for item in stories:
        story_data = StoryWithProgressRead(
            id=item.id,
            title=item.title,
            subtitle=item.subtitle,
            source_book=item.source_book,
            source_author=item.source_author,
            target_levels=item.target_levels,
            themes=item.themes,
            estimated_duration_minutes=item.estimated_duration_minutes,
            cover_image_url=item.cover_image_url,
            is_unlocked=item.is_unlocked,
            progress=StoryProgressRead(
                story_id=item.id,
                current_chapter_title=item.progress.current_chapter_title if item.progress else None,
                completion_percentage=item.progress.completion_percentage if item.progress else 0,
                status=item.progress.status if item.progress else "not_started",
                last_played_at=item.progress.last_played_at if item.progress else None,
            ) if item.progress else None,
        )
        result.append(story_data)
    
    return result


@router.get("/{story_id}", response_model=StoryWithProgressRead)
async def get_story(
    story_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Get story details with user progress."""
    service = StoryService(db)
    
    # Check if story exists in user's list
    stories = service.list_available_stories(current_user)
    story_item = next((s for s in stories if s.id == story_id), None)
    
    if not story_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Story not found",
        )
    
    return StoryWithProgressRead(
        id=story_item.id,
        title=story_item.title,
        subtitle=story_item.subtitle,
        source_book=story_item.source_book,
        source_author=story_item.source_author,
        target_levels=story_item.target_levels,
        themes=story_item.themes,
        estimated_duration_minutes=story_item.estimated_duration_minutes,
        cover_image_url=story_item.cover_image_url,
        is_unlocked=story_item.is_unlocked,
        progress=StoryProgressRead(
            story_id=story_item.id,
            current_chapter_title=story_item.progress.current_chapter_title if story_item.progress else None,
            completion_percentage=story_item.progress.completion_percentage if story_item.progress else 0,
            status=story_item.progress.status if story_item.progress else "not_started",
            last_played_at=story_item.progress.last_played_at if story_item.progress else None,
        ) if story_item.progress else None,
    )


@router.post("/{story_id}/start", response_model=StoryStartResponse)
async def start_story(
    story_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Start or resume a story."""
    from app.services.progress import ProgressService
    
    service = StoryService(db)
    
    try:
        result = service.start_story(current_user, story_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    
    # Queue vocabulary from the chapter for SRS practice
    progress_service = ProgressService(db)
    queued_words = service.queue_scene_vocabulary(
        user=current_user,
        chapter=result.scene.chapter,
        progress_service=progress_service,
    )
    
    if queued_words:
        logger.info(
            "Story vocab queued for SRS",
            story_id=story_id,
            chapter=result.scene.chapter.title,
            words_count=len(queued_words),
        )
    
    # Build response
    scene_context = result.scene
    progress = result.progress
    
    # Convert NPCs to schema
    npcs = [
        NPCInSceneRead(
            id=npc.npc.id,
            name=npc.npc.name,
            display_name=npc.npc.display_name,
            role=npc.npc.role,
            avatar_url=npc.npc.avatar_url,
            relationship_level=npc.relationship_level,
            trust=npc.trust,
            mood=npc.mood,
        )
        for npc in scene_context.npcs
    ]
    
    # Convert objectives to schema
    objectives = [
        ObjectiveRead(
            id=obj.get("id", ""),
            description=obj.get("description", ""),
            type=obj.get("type", "task"),
            optional=obj.get("optional", False),
        )
        for obj in scene_context.objectives
    ]
    
    return StoryStartResponse(
        progress=StoryProgressRead(
            story_id=progress.story_id,
            current_chapter_id=progress.current_chapter_id,
            current_scene_id=progress.current_scene_id,
            completion_percentage=progress.completion_percentage or 0,
            status=progress.status,
            story_flags=progress.story_flags or {},
            philosophical_learnings=progress.philosophical_learnings or [],
            book_quotes_unlocked=progress.book_quotes_unlocked or [],
            started_at=progress.started_at,
            last_played_at=progress.last_played_at,
        ),
        scene=SceneRead(
            id=scene_context.scene.id,
            chapter_id=scene_context.chapter.id,
            location=scene_context.scene.location,
            atmosphere=scene_context.scene.atmosphere,
            narration=scene_context.narration,
            objectives=objectives,
            npcs_present=npcs,
            estimated_duration_minutes=scene_context.scene.estimated_duration_minutes or 10,
        ),
        chapter=ChapterRead(
            id=scene_context.chapter.id,
            story_id=scene_context.story.id,
            order_index=scene_context.chapter.order_index,
            title=scene_context.chapter.title,
            target_level=scene_context.chapter.target_level,
        ),
    )


@router.get("/{story_id}/scene", response_model=SceneRead | None)
async def get_current_scene(
    story_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Get current scene for a story."""
    service = StoryService(db)
    scene_context = service.get_current_scene(current_user, story_id)
    
    if not scene_context:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active scene found. Start the story first.",
        )
    
    # Convert NPCs
    npcs = [
        NPCInSceneRead(
            id=npc.npc.id,
            name=npc.npc.name,
            display_name=npc.npc.display_name,
            role=npc.npc.role,
            avatar_url=npc.npc.avatar_url,
            relationship_level=npc.relationship_level,
            trust=npc.trust,
            mood=npc.mood,
        )
        for npc in scene_context.npcs
    ]
    
    # Convert objectives
    objectives = [
        ObjectiveRead(
            id=obj.get("id", ""),
            description=obj.get("description", ""),
            type=obj.get("type", "task"),
            optional=obj.get("optional", False),
        )
        for obj in scene_context.objectives
    ]
    
    return SceneRead(
        id=scene_context.scene.id,
        chapter_id=scene_context.chapter.id,
        location=scene_context.scene.location,
        atmosphere=scene_context.scene.atmosphere,
        narration=scene_context.narration,
        objectives=objectives,
        npcs_present=npcs,
        estimated_duration_minutes=scene_context.scene.estimated_duration_minutes or 10,
    )


@router.get("/{story_id}/progress", response_model=StoryProgressRead | None)
async def get_story_progress(
    story_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Get user's progress in a story."""
    service = StoryService(db)
    progress = service.get_story_progress(current_user, story_id)
    
    if not progress:
        return None
    
    # Get chapter title if available
    chapter_title = None
    if progress.current_chapter_id:
        from app.db.models.story import Chapter
        chapter = db.get(Chapter, progress.current_chapter_id)
        chapter_title = chapter.title if chapter else None
    
    return StoryProgressRead(
        story_id=progress.story_id,
        current_chapter_id=progress.current_chapter_id,
        current_chapter_title=chapter_title,
        current_scene_id=progress.current_scene_id,
        completion_percentage=progress.completion_percentage or 0,
        status=progress.status,
        story_flags=progress.story_flags or {},
        philosophical_learnings=progress.philosophical_learnings or [],
        book_quotes_unlocked=progress.book_quotes_unlocked or [],
        started_at=progress.started_at,
        last_played_at=progress.last_played_at,
    )


@router.post("/{story_id}/input", response_model=StoryInputResponse)
async def process_story_input(
    story_id: str,
    request: StoryInputRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Process player input in a story and get NPC response."""
    from app.core.conversation.generator import ConversationGenerator, ConversationHistoryMessage
    from app.core.error_detection.detector import ErrorDetector
    from app.services.progress import ProgressService
    from app.services.llm_service import LLMService
    
    story_service = StoryService(db)
    npc_service = NPCService(db)
    llm_service = LLMService()
    
    # Get current scene
    scene_context = story_service.get_current_scene(current_user, story_id)
    if not scene_context:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active scene found. Start the story first.",
        )
    
    # Get story progress
    progress = story_service.get_story_progress(current_user, story_id)
    if not progress:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No progress found for this story.",
        )
    
    # Determine target NPC (use scene's primary NPC if not specified)
    target_npc_id = request.target_npc_id
    if not target_npc_id and scene_context.npcs:
        # Pick first non-narrator NPC
        for npc_info in scene_context.npcs:
            if npc_info.npc.id != "narrator":
                target_npc_id = npc_info.npc.id
                break
    
    # If still no NPC, use narrator
    if not target_npc_id and scene_context.npcs:
        target_npc_id = scene_context.npcs[0].npc.id
    
    # Common result variables
    result = {}
    errors_detected = []
    xp_error_count = 0
    objectives_completed_descriptions = []
    
    # === CHOICE INTERACTION ===
    if request.choice_id:
        # Load player interaction config
        player_interaction = scene_context.scene.player_interaction or {}
        options = player_interaction.get("options", [])
        
        selected_option = next((opt for opt in options if opt["id"] == request.choice_id), None)
        
        if not selected_option:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid choice ID.",
            )
            
        # Apply effects (flags, etc.)
        updated_flags = []
        consequences = []
        if "effects" in selected_option:
            for effect in selected_option["effects"]:
                if effect["type"] == "set_flag":
                    story_service.set_story_flag(
                        current_user, story_id, effect["target"], effect["value"]
                    )
                    updated_flags.append(effect["target"])
                    consequences.append(ConsequenceRead(
                        type="flag_set",
                        target=effect["target"],
                        value=effect["value"],
                        description=None
                    ))

        # Get response (fixed narration usually)
        response_text = selected_option.get("response", {}).get("narration", "")
        
        # Check transition based on choice trigger
        # We simulate a "choice_made" trigger or specific choice trigger
        transition_trigger = "choice_made" 
        
        # Build Result dict compatible with response
        result = {
            "response": response_text,
            "emotion": "neutral",
            "relationship_delta": 0,
            "new_relationship_level": 0,
            "new_mood": "neutral",
            "triggers_unlocked": updated_flags,
            "objectives_completed": [], 
            "should_transition": True # Usually choices lead to transition
        }
    
    # === LLM INTERACTION ===
    else:
        if not target_npc_id:
             raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No NPC available to respond.",
            )

        # Run Error Detection on player input
        error_detector = ErrorDetector(llm_service=llm_service)
        error_result = error_detector.analyze(
            request.content,
            learner_level=current_user.proficiency_level or "A1",
            use_llm=True,
        )
        
        # Persist errors to UserError table for SRS tracking
        if error_result.errors:
            _persist_story_errors(
                db=db,
                user=current_user,
                story_id=story_id,
                scene_id=scene_context.scene.id,
                error_result=error_result,
            )
        
        # Format errors for response
        errors_detected = [
            {
                "code": err.code,
                "message": err.message,
                "span": err.span,
                "correction": err.suggestion,
                "category": err.category,
                "severity": err.severity,
            }
            for err in error_result.errors
        ]
        xp_error_count = len(error_result.errors)
        
        # Build conversation history from request
        history = []
        if request.conversation_history:
            for msg in request.conversation_history:
                history.append(ConversationHistoryMessage(
                    role=msg.get("role", "user"),
                    content=msg.get("content", ""),
                ))
        
        # Build scene description
        scene_description = scene_context.narration
        if scene_context.scene.location:
            scene_description = f"Ort: {scene_context.scene.location}\n\n{scene_description}"
        
        # Generate NPC response
        progress_service = ProgressService(db)
        generator = ConversationGenerator(
            progress_service=progress_service,
            llm_service=llm_service,
        )
        
        # Get target NPC
        npc_info = next((n for n in scene_context.npcs if n.npc.id == target_npc_id), None)
        npc = npc_info.npc if npc_info else None
        
        if not npc:
             raise HTTPException(status_code=404, detail="NPC not found")
        
        result = generator.generate_npc_response(
            user=current_user,
            npc_service=npc_service,
            npc_id=target_npc_id,
            player_input=request.content,
            scene_description=scene_description,
            learner_level=current_user.proficiency_level or "A1",
            conversation_history=history,
            scene_objectives=[obj.get("description", "") for obj in scene_context.objectives],
            story_flags=progress.story_flags or {},
        )
        
        # Update relationship based on response
        if result["relationship_delta"] != 0 or result["new_mood"]:
            npc_service.update_relationship(
                user=current_user,
                npc_id=target_npc_id,
                level_delta=result["relationship_delta"],
                new_mood=result["new_mood"],
            )
    
    # === COMMON POST-PROCESSING ===
    
    # Set story flags for any triggers unlocked
    for trigger in result["triggers_unlocked"]:
        story_service.set_story_flag(current_user, story_id, trigger, True)
    
    # Add memory of this interaction
    if len(request.content) > 20:  # Only memorable if substantial
        memory_content = f"Der Spieler sagte: '{request.content[:100]}...'"
        npc_service.add_memory(
            user=current_user,
            npc_id=target_npc_id,
            memory_type="conversation",
            content=memory_content,
            sentiment="neutral",
            scene_id=scene_context.scene.id,
        )
    
    # Use LLM-evaluated objectives from the generator result
    objectives_completed_descriptions = result.get("objectives_completed", [])
    
    # DEBUG: Log objective evaluation
    logger.info(
        "Objective evaluation result",
        objectives_returned=objectives_completed_descriptions,
        scene_objectives=[obj.get("description") for obj in scene_context.objectives],
        should_transition=result.get("should_transition", False),
    )
    
    # Map descriptions to IDs and collect completed objective info
    completed_objective_ids = []
    completed_objective_details = []  # For frontend display
    
    for obj_desc in objectives_completed_descriptions:
        # Find matching objective by description (fuzzy matching with normalization)
        obj_desc_lower = obj_desc.lower().strip()
        for obj in scene_context.objectives:
            obj_full_desc = obj.get("description", "").lower().strip()
            # Check for exact match, substring, or significant overlap
            if (obj_full_desc == obj_desc_lower 
                or obj_desc_lower in obj_full_desc 
                or obj_full_desc in obj_desc_lower
                or any(word in obj_full_desc for word in obj_desc_lower.split() if len(word) > 4)):
                obj_id = obj.get("id", "")
                obj_description = obj.get("description", "")
                if obj_id not in completed_objective_ids:  # Avoid duplicates
                    completed_objective_ids.append(obj_id)
                    completed_objective_details.append({
                        "id": obj_id,
                        "description": obj_description,
                    })
                    story_service.set_story_flag(
                        current_user, story_id, f"objective_{obj_id}_completed", True
                    )
                break  # Found match, move to next
    
    # Check for scene transition based on LLM evaluation or Choice config
    scene_transition = None
    should_transition = result.get("should_transition", False)
    
    # FALLBACK: Force transition if all non-optional objectives are complete
    if not should_transition and scene_context.objectives:
        non_optional_objectives = [
            obj for obj in scene_context.objectives 
            if not obj.get("optional", False)
        ]
        if non_optional_objectives:
            # Check if all non-optional objectives are in completed list (fuzzy matching)
            def objective_matches(obj_desc, completed_list):
                obj_desc_lower = obj_desc.lower().strip()
                for completed_desc in completed_list:
                    completed_lower = completed_desc.lower().strip()
                    if (obj_desc_lower == completed_lower 
                        or completed_lower in obj_desc_lower 
                        or obj_desc_lower in completed_lower
                        or any(word in obj_desc_lower for word in completed_lower.split() if len(word) > 4)):
                        return True
                return False
            
            all_complete = all(
                objective_matches(obj.get("description", ""), objectives_completed_descriptions)
                for obj in non_optional_objectives
            )
            if all_complete:
                logger.info(
                    "Forcing scene transition: all objectives complete",
                    objectives=len(non_optional_objectives),
                    completed=len(objectives_completed_descriptions),
                )
                should_transition = True
    
    # SECOND FALLBACK: If we matched objectives to IDs, check if all non-optional are complete
    if not should_transition and completed_objective_ids and scene_context.objectives:
        non_optional_ids = [
            obj.get("id", "") for obj in scene_context.objectives 
            if not obj.get("optional", False)
        ]
        if non_optional_ids and all(obj_id in completed_objective_ids for obj_id in non_optional_ids):
            logger.info(
                "Forcing scene transition: all objective IDs matched",
                required_ids=non_optional_ids,
                completed_ids=completed_objective_ids,
            )
            should_transition = True
    
    if should_transition:
        # LLM determined all objectives are complete, advance scene
        next_scene_context = story_service.advance_scene(
            current_user, story_id, "objectives_complete"
        )
        if next_scene_context:
            # Get transition narration from scene data if available
            transition_narration = None
            if scene_context.scene.transition_rules:
                for rule in scene_context.scene.transition_rules:
                    if rule.get("narration"):
                        narration_variants = rule.get("narration", {})
                        user_level = current_user.proficiency_level or "A1"
                        transition_narration = narration_variants.get(user_level) or narration_variants.get("A1") or str(narration_variants)
                        break
            
            scene_transition = {
                "next_scene_id": next_scene_context.scene.id,
                "transition_narration": transition_narration or "Et c'est alors que quelque chose d'extraordinaire se produit...",
                "chapter_change": next_scene_context.chapter.id != scene_context.chapter.id,
                "new_chapter_title": next_scene_context.chapter.title if next_scene_context.chapter.id != scene_context.chapter.id else None,
            }
    
    # Get updated NPC info
    npc = npc_service.get_npc(target_npc_id)
    relationship = npc_service.get_or_create_relationship(current_user, target_npc_id)
    
    # Build consequences from triggers
    consequences = []
    for trigger in result["triggers_unlocked"]:
        consequences.append(ConsequenceRead(
            type="flag_set",
            target=trigger,
            value=True,
            description=None,
        ))
    if result["relationship_delta"] != 0:
        consequences.append(ConsequenceRead(
            type="relationship_change",
            target=target_npc_id,
            value=result["relationship_delta"],
            description=None,
        ))
    for obj_detail in completed_objective_details:
        consequences.append(ConsequenceRead(
            type="objective_complete",
            target=obj_detail["id"],
            value=True,
            description=obj_detail["description"],  # Include description for frontend
        ))
    
    # Build scene transition response if applicable
    scene_transition_response = None
    if scene_transition:
        from app.schemas.story import SceneTransitionRead
        scene_transition_response = SceneTransitionRead(
            next_scene_id=scene_transition["next_scene_id"],
            transition_narration=scene_transition.get("transition_narration"),
            chapter_change=scene_transition.get("chapter_change", False),
            new_chapter_title=scene_transition.get("new_chapter_title"),
        )
    
    # Calculate and apply XP
    xp_result = _calculate_story_xp(
        content=request.content,
        error_count=len(error_result.errors),
        has_story_progress=bool(completed_objective_ids),
        objectives_completed=completed_objective_ids,
    )
    
    # Apply XP to user
    if xp_result["total"] > 0:
        current_user.total_xp = (current_user.total_xp or 0) + xp_result["total"]
        current_user.mark_activity()
        db.commit()
    
    return StoryInputResponse(
        npc_response=NPCResponseRead(
            npc_id=target_npc_id,
            npc_name=npc.name if npc else "Unknown",
            content=result["response"],
            emotion=result["emotion"],
            relationship_delta=result["relationship_delta"],
            new_relationship_level=relationship.level,
            new_mood=result["new_mood"],
        ),
        consequences=consequences,
        xp_earned=xp_result["total"],
        xp_breakdown=xp_result["breakdown"],
        errors_detected=errors_detected,
        updated_flags=result["triggers_unlocked"],
        scene_transition=scene_transition_response,
    )


# ============================================================================
# Chapter-Level Endpoints (merged from worktree)
# ============================================================================

@router.get("/{story_id}/chapters", response_model=list["ChapterWithStatusRead"])
async def get_story_chapters(
    story_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Get all chapters for a story with completion status."""
    from app.db.models.story import Story, Chapter
    from app.schemas.story import ChapterWithStatusRead

    story_service = StoryService(db)

    # Get story
    story = db.get(Story, story_id)
    if not story:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Story not found",
        )

    # Get user progress
    progress = story_service.get_story_progress(current_user, story_id)

    # Get all chapters ordered
    chapters = db.query(Chapter).filter(
        Chapter.story_id == story_id
    ).order_by(Chapter.order_index).all()

    # Build completed/perfect chapter sets
    completed_chapter_ids = set()
    perfect_chapter_ids = set()

    if progress and progress.chapters_completed_details:
        for detail in progress.chapters_completed_details:
            completed_chapter_ids.add(detail["chapter_id"])
            if detail.get("was_perfect"):
                perfect_chapter_ids.add(detail["chapter_id"])
    elif progress and progress.chapters_completed:
        completed_chapter_ids = set(progress.chapters_completed)

    current_chapter_order = None
    if progress and progress.current_chapter_id:
        current_chapter = db.get(Chapter, progress.current_chapter_id)
        if current_chapter:
            current_chapter_order = current_chapter.order_index

    result = []
    for chapter in chapters:
        is_completed = chapter.id in completed_chapter_ids
        is_locked = False

        # Lock chapters after the current one (if not completed)
        if current_chapter_order is not None and not is_completed:
            if chapter.order_index > current_chapter_order:
                is_locked = True

        result.append(ChapterWithStatusRead(
            id=chapter.id,
            story_id=chapter.story_id,
            order_index=chapter.order_index,
            title=chapter.title,
            target_level=chapter.target_level,
            is_locked=is_locked,
            is_completed=is_completed,
            was_perfect=chapter.id in perfect_chapter_ids,
            completion_xp=chapter.completion_xp or 75,
            perfect_completion_xp=chapter.perfect_completion_xp or 150,
        ))

    return result


@router.post("/{story_id}/chapters/{chapter_id}/check-goals")
async def check_chapter_goals(
    story_id: str,
    chapter_id: str,
    request: "GoalCheckRequest",
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> "GoalCheckResponse":
    """Check narrative goal completion for a chapter session using French morphological matching."""
    from app.db.models.story import Chapter
    from app.schemas.story import GoalCheckRequest, GoalCheckResponse
    import uuid

    story_service = StoryService(db)

    # Get chapter
    chapter = db.get(Chapter, chapter_id)
    if not chapter or chapter.story_id != story_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chapter not found",
        )

    # Parse session_id
    try:
        session_uuid = uuid.UUID(request.session_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid session_id format",
        )

    # Check goals using French morphological matching
    result = story_service.check_narrative_goals(session_uuid, chapter)

    return GoalCheckResponse(
        goals_completed=result.goals_completed,
        goals_remaining=result.goals_remaining,
        completion_rate=result.completion_rate,
    )


@router.post("/{story_id}/chapters/{chapter_id}/complete")
async def complete_chapter(
    story_id: str,
    chapter_id: str,
    request: "ChapterCompletionRequest",
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> "ChapterCompletionResponse":
    """Complete a chapter and unlock the next one."""
    from app.db.models.story import Chapter
    from app.schemas.story import ChapterCompletionRequest, ChapterCompletionResponse, ChapterRead
    from app.services.story_service import GoalCheckResult
    import uuid

    story_service = StoryService(db)

    # Get chapter
    chapter = db.get(Chapter, chapter_id)
    if not chapter or chapter.story_id != story_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chapter not found",
        )

    # Parse session_id
    try:
        session_uuid = uuid.UUID(request.session_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid session_id format",
        )

    # Check goals first to get proper completion state
    goal_result = story_service.check_narrative_goals(session_uuid, chapter)

    # Complete chapter
    try:
        reward = story_service.complete_chapter_with_goals(
            current_user,
            chapter_id,
            session_uuid,
            goal_result,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # Apply XP to user
    if reward.xp_earned > 0:
        current_user.total_xp = (current_user.total_xp or 0) + reward.xp_earned
        current_user.mark_activity()
        db.commit()

    # Build response
    next_chapter_read = None
    if reward.next_chapter:
        next_chapter_read = ChapterRead(
            id=reward.next_chapter.id,
            story_id=reward.next_chapter.story_id,
            order_index=reward.next_chapter.order_index,
            title=reward.next_chapter.title,
            target_level=reward.next_chapter.target_level,
        )

    return ChapterCompletionResponse(
        xp_earned=reward.xp_earned,
        achievements_unlocked=reward.achievements_unlocked,
        next_chapter_id=reward.next_chapter.id if reward.next_chapter else None,
        next_chapter=next_chapter_read,
        story_completed=reward.story_completed,
        is_perfect=reward.is_perfect,
    )


@router.post("/{story_id}/make-choice")
async def make_narrative_choice(
    story_id: str,
    request: "NarrativeChoiceRequest",
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> "NarrativeChoiceResponse":
    """Make a narrative branching choice and advance to the corresponding chapter."""
    from app.schemas.story import NarrativeChoiceRequest, NarrativeChoiceResponse, ChapterRead

    story_service = StoryService(db)

    try:
        result = story_service.make_narrative_choice(
            current_user,
            story_id,
            request.choice_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    next_chapter_read = ChapterRead(
        id=result.next_chapter.id,
        story_id=result.next_chapter.story_id,
        order_index=result.next_chapter.order_index,
        title=result.next_chapter.title,
        target_level=result.next_chapter.target_level,
    )

    return NarrativeChoiceResponse(
        next_chapter_id=result.next_chapter.id,
        next_chapter=next_chapter_read,
        choice_recorded=result.choice_recorded,
    )


# Import schemas at module level for type hints
from app.schemas.story import (
    GoalCheckRequest,
    GoalCheckResponse,
    ChapterCompletionRequest,
    ChapterCompletionResponse,
    NarrativeChoiceRequest,
    NarrativeChoiceResponse,
    ChapterWithStatusRead,
)
