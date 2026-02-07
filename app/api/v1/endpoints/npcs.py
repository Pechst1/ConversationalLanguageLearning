"""API endpoints for NPC interactions."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.db.models.user import User
from app.services.npc_service import NPCService
from app.schemas.story import (
    NPCDetailRead,
    NPCRelationshipRead,
    NPCMemoryRead,
)

router = APIRouter()


@router.get("/{npc_id}", response_model=NPCDetailRead)
async def get_npc(
    npc_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Get NPC details."""
    service = NPCService(db)
    npc = service.get_npc(npc_id)
    
    if not npc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="NPC not found",
        )
    
    return NPCDetailRead(
        id=npc.id,
        name=npc.name,
        display_name=npc.display_name,
        role=npc.role,
        avatar_url=npc.avatar_url,
        backstory=npc.backstory,
        appearance_description=npc.appearance_description,
        personality=npc.personality or {},
        speech_pattern=npc.speech_pattern or {},
    )


@router.get("/{npc_id}/relationship", response_model=NPCRelationshipRead)
async def get_npc_relationship(
    npc_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Get user's relationship status with an NPC."""
    service = NPCService(db)
    npc = service.get_npc(npc_id)
    
    if not npc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="NPC not found",
        )
    
    relationship = service.get_or_create_relationship(current_user, npc_id)
    
    return NPCRelationshipRead(
        npc_id=npc_id,
        npc_name=npc.name,
        npc_avatar_url=npc.avatar_url,
        level=relationship.level,
        trust=relationship.trust,
        mood=relationship.mood,
        total_interactions=relationship.total_interactions,
        positive_interactions=relationship.positive_interactions,
        negative_interactions=relationship.negative_interactions,
        first_interaction_at=relationship.first_interaction_at,
        last_interaction_at=relationship.last_interaction_at,
    )


@router.get("/{npc_id}/memories", response_model=list[NPCMemoryRead])
async def get_npc_memories(
    npc_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: int = 10,
):
    """Get NPC's memories of interactions with user."""
    service = NPCService(db)
    npc = service.get_npc(npc_id)
    
    if not npc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="NPC not found",
        )
    
    memories = service.get_memories(current_user, npc_id, limit=limit)
    
    return [
        NPCMemoryRead(
            id=m.id,
            memory_type=m.memory_type,
            content=m.content,
            sentiment=m.sentiment,
            scene_id=m.scene_id,
            player_quote=m.player_quote,
            created_at=m.created_at,
        )
        for m in memories
    ]
