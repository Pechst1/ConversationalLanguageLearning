"""NPC service for managing relationships and memories."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Sequence

from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from app.db.models.npc import NPC, NPCRelationship, NPCMemory
from app.db.models.user import User

if TYPE_CHECKING:
    pass


@dataclass
class NPCInfo:
    """Full NPC information including relationship context."""
    id: str
    name: str
    display_name: str | None
    role: str | None
    avatar_url: str | None
    personality: dict
    speech_pattern: dict
    relationship_level: int
    trust: int
    mood: str
    total_interactions: int
    available_secrets: list[str]


@dataclass
class MemoryItem:
    """A single memory item."""
    id: str
    memory_type: str
    content: str
    sentiment: str
    scene_id: str | None
    player_quote: str | None
    created_at: datetime


@dataclass
class NPCPromptContext:
    """Context for building an NPC response prompt."""
    npc: NPC
    relationship_level: int
    trust: int
    mood: str
    recent_memories: list[str]
    available_secrets: list[str]
    notable_quotes: list[str]


class NPCService:
    """Service for managing NPC relationships and memories."""

    def __init__(self, db: Session):
        self.db = db

    def get_npc(self, npc_id: str) -> NPC | None:
        """Get an NPC by ID."""
        return self.db.get(NPC, npc_id)

    def get_or_create_relationship(self, user: User, npc_id: str) -> NPCRelationship:
        """Get or create a relationship between user and NPC."""
        stmt = select(NPCRelationship).where(
            NPCRelationship.user_id == user.id,
            NPCRelationship.npc_id == npc_id,
        )
        relationship = self.db.execute(stmt).scalar_one_or_none()
        
        if not relationship:
            # Get NPC's default relationship config
            npc = self.db.get(NPC, npc_id)
            initial_level = 1
            if npc and npc.relationship_config:
                initial_level = npc.relationship_config.get("initial_level", 1)
            
            relationship = NPCRelationship(
                user_id=user.id,
                npc_id=npc_id,
                level=initial_level,
                trust=0,
                mood="neutral",
            )
            self.db.add(relationship)
            self.db.commit()
            self.db.refresh(relationship)
        
        return relationship

    def get_npc_info(self, user: User, npc_id: str) -> NPCInfo | None:
        """Get full NPC information with relationship context."""
        npc = self.get_npc(npc_id)
        if not npc:
            return None
        
        relationship = self.get_or_create_relationship(user, npc_id)
        available_secrets = self._get_available_secrets(npc, relationship.level)
        
        return NPCInfo(
            id=npc.id,
            name=npc.name,
            display_name=npc.display_name,
            role=npc.role,
            avatar_url=npc.avatar_url,
            personality=npc.personality or {},
            speech_pattern=npc.speech_pattern or {},
            relationship_level=relationship.level,
            trust=relationship.trust,
            mood=relationship.mood,
            total_interactions=relationship.total_interactions,
            available_secrets=available_secrets,
        )

    def update_relationship(
        self,
        user: User,
        npc_id: str,
        level_delta: int = 0,
        trust_delta: int = 0,
        new_mood: str | None = None,
    ) -> NPCRelationship:
        """Update the relationship between user and NPC."""
        relationship = self.get_or_create_relationship(user, npc_id)
        
        if level_delta != 0:
            relationship.update_level(level_delta)
        
        if trust_delta != 0:
            relationship.update_trust(trust_delta)
        
        if new_mood:
            relationship.mood = new_mood
        
        relationship.last_interaction_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(relationship)
        
        return relationship

    def add_memory(
        self,
        user: User,
        npc_id: str,
        memory_type: str,
        content: str,
        *,
        scene_id: str | None = None,
        sentiment: str = "neutral",
        importance: int = 5,
        player_quote: str | None = None,
    ) -> NPCMemory:
        """Add a memory for an NPC about the user."""
        memory = NPCMemory(
            user_id=user.id,
            npc_id=npc_id,
            memory_type=memory_type,
            content=content,
            scene_id=scene_id,
            sentiment=sentiment,
            importance=importance,
            player_quote=player_quote,
        )
        self.db.add(memory)
        self.db.commit()
        self.db.refresh(memory)
        
        return memory

    def get_memories(
        self,
        user: User,
        npc_id: str,
        *,
        limit: int = 10,
        memory_type: str | None = None,
    ) -> list[MemoryItem]:
        """Get NPC's memories of interactions with user."""
        stmt = (
            select(NPCMemory)
            .where(
                NPCMemory.user_id == user.id,
                NPCMemory.npc_id == npc_id,
            )
            .order_by(desc(NPCMemory.importance), desc(NPCMemory.created_at))
            .limit(limit)
        )
        
        if memory_type:
            stmt = stmt.where(NPCMemory.memory_type == memory_type)
        
        memories = self.db.execute(stmt).scalars().all()
        
        return [
            MemoryItem(
                id=str(m.id),
                memory_type=m.memory_type,
                content=m.content,
                sentiment=m.sentiment,
                scene_id=m.scene_id,
                player_quote=m.player_quote,
                created_at=m.created_at,
            )
            for m in memories
        ]

    def get_prompt_context(self, user: User, npc_id: str) -> NPCPromptContext | None:
        """Get full context for building an NPC response prompt."""
        npc = self.get_npc(npc_id)
        if not npc:
            return None
        
        relationship = self.get_or_create_relationship(user, npc_id)
        
        # Get recent memories
        recent_memories = self.get_memories(user, npc_id, limit=5)
        memory_texts = [m.content for m in recent_memories]
        
        # Get notable player quotes
        quote_memories = self.get_memories(user, npc_id, memory_type="notable_quote", limit=3)
        notable_quotes = [m.player_quote for m in quote_memories if m.player_quote]
        
        # Get available secrets at current relationship level
        available_secrets = self._get_available_secrets(npc, relationship.level)
        
        return NPCPromptContext(
            npc=npc,
            relationship_level=relationship.level,
            trust=relationship.trust,
            mood=relationship.mood,
            recent_memories=memory_texts,
            available_secrets=available_secrets,
            notable_quotes=notable_quotes,
        )

    def _get_available_secrets(self, npc: NPC, relationship_level: int) -> list[str]:
        """Get secrets available at the current relationship level."""
        if not npc.information_tiers:
            return []
        
        available = []
        for level_str, secrets in npc.information_tiers.items():
            try:
                required_level = int(level_str)
                if relationship_level >= required_level:
                    if isinstance(secrets, list):
                        available.extend(secrets)
                    else:
                        available.append(secrets)
            except ValueError:
                continue
        
        return available

    def check_information_unlock(
        self,
        user: User,
        npc_id: str,
    ) -> list[str]:
        """Check which new information has been unlocked at current level."""
        npc = self.get_npc(npc_id)
        if not npc:
            return []
        
        relationship = self.get_or_create_relationship(user, npc_id)
        
        # Get all available secrets for current level
        available = self._get_available_secrets(npc, relationship.level)
        
        # Check which secrets have already been shared
        shared_level = relationship.has_shared_secret or 0
        
        # Get newly available secrets
        newly_available = []
        if npc.information_tiers:
            for level_str, secrets in npc.information_tiers.items():
                try:
                    required_level = int(level_str)
                    # Only include if this level is newly reached
                    if required_level > shared_level and required_level <= relationship.level:
                        if isinstance(secrets, list):
                            newly_available.extend(secrets)
                        else:
                            newly_available.append(secrets)
                except ValueError:
                    continue
        
        return newly_available

    def mark_secret_shared(self, user: User, npc_id: str, level: int) -> None:
        """Mark that secrets up to a certain level have been shared."""
        relationship = self.get_or_create_relationship(user, npc_id)
        if level > (relationship.has_shared_secret or 0):
            relationship.has_shared_secret = level
            self.db.commit()

    def build_npc_system_prompt(
        self,
        context: NPCPromptContext,
        scene_description: str,
        player_level: str,
    ) -> str:
        """Build a system prompt for NPC response generation."""
        npc = context.npc
        personality = npc.personality or {}
        speech = npc.speech_pattern or {}
        
        # Format personality traits
        traits = personality.get("core_traits", [])
        traits_str = ", ".join(traits) if traits else "keine spezifischen Eigenschaften"
        
        # Format memories
        memories_str = ""
        if context.recent_memories:
            memories_str = "\n".join(f"- {m}" for m in context.recent_memories[:3])
        else:
            memories_str = "Keine vorherigen Interaktionen."
        
        # Format quotes
        quotes_str = ""
        if context.notable_quotes:
            quotes_str = f"\nBemerkenswerte Aussagen des Spielers: {', '.join(context.notable_quotes)}"
        
        # Determine speech complexity
        base_complexity = speech.get("base_complexity", "A2")
        adapt_to_player = speech.get("adapt_to_player", True)
        target_complexity = player_level if adapt_to_player else base_complexity
        
        prompt = f"""Du bist {npc.name}, {npc.role or 'ein Charakter in der Geschichte'}.

PERSÖNLICHKEIT:
- Eigenschaften: {traits_str}
- Geduld: {personality.get('patience', 0.5)}/1.0
- Formalität: {personality.get('formality', 0.5)}/1.0
- Humor: {personality.get('humor', 0.3)}/1.0

SPRECHMUSTER:
- Zielkomplexität: {target_complexity}
- Sprechgeschwindigkeit: {speech.get('speaking_speed', 'normal')}
- Eigenheiten: {', '.join(speech.get('quirks', []))}

BEZIEHUNG ZUM SPIELER:
- Level: {context.relationship_level}/10
- Vertrauen: {context.trust}
- Stimmung: {context.mood}

ERINNERUNGEN AN DEN SPIELER:
{memories_str}{quotes_str}

AKTUELLE SITUATION:
{scene_description}

VERFÜGBARE GEHEIMNISSE (bei Level {context.relationship_level}):
{', '.join(context.available_secrets) if context.available_secrets else 'Keine'}

SPIELER-SPRACHLEVEL: {player_level}

ANWEISUNGEN:
1. SPRICH NUR AUF FRANZÖSISCH - das ist eine französische Sprachlernanwendung
2. Bleibe im Charakter als {npc.name}
3. Reagiere authentisch auf den Spieler basierend auf eurer Geschichte
4. Bei Sprachfehlern: Reagiere natürlich, NICHT lehrerhaft - korrigiere NIE direkt
5. Passe deine Sprache an Level {target_complexity} an (verwende einfachere Wörter für niedrigere Levels)
6. Teile Geheimnisse nur wenn die Beziehung es erlaubt (aktuell Level {context.relationship_level})
7. Halte deine Antworten zwischen 1-3 Sätzen, um das Gespräch interaktiv zu halten

Antworte NUR auf FRANZÖSISCH, nur mit deinem Dialog (ohne Anführungszeichen, ohne "{npc.name} sagt:")."""

        return prompt

    def evaluate_npc_reaction(
        self,
        npc_id: str,
        player_response_analysis: dict,
    ) -> tuple[int, str | None]:
        """
        Evaluate how an NPC would react to the player's response.
        
        Returns:
            Tuple of (relationship_delta, new_mood or None)
        """
        npc = self.get_npc(npc_id)
        if not npc:
            return (0, None)
        
        config = npc.relationship_config or {}
        likes = config.get("likes_when", [])
        dislikes = config.get("dislikes_when", [])
        
        delta = 0
        new_mood = None
        
        # Check for positive triggers
        for like in likes:
            if like in player_response_analysis.get("triggers", []):
                delta += 1
                new_mood = "happy"
        
        # Check for negative triggers
        for dislike in dislikes:
            if dislike in player_response_analysis.get("triggers", []):
                delta -= 1
                new_mood = "upset"
        
        # Check for register mismatch
        if player_response_analysis.get("register_mismatch"):
            formality = (npc.personality or {}).get("formality", 0.5)
            if formality > 0.7:  # Formal NPC
                delta -= 1
                new_mood = "offended"
        
        # Check for humor attempt
        if player_response_analysis.get("humor_attempt"):
            humor = (npc.personality or {}).get("humor", 0.5)
            if humor > 0.5:
                delta += 1
                new_mood = "amused"
        
        return (delta, new_mood)
