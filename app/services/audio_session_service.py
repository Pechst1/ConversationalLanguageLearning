"""Audio Session Service for zero-config, audio-only conversations.

This service handles:
- Smart auto-context generation (errors, interests, variety)
- Error-weaving into conversation prompts
- Session lifecycle for audio-only mode
"""
from __future__ import annotations

import asyncio
import json
import random
from datetime import datetime, timezone, timedelta
from typing import Any
from uuid import UUID

from loguru import logger
from sqlalchemy.orm import Session

from app.db.models.error import UserError
from app.db.models.grammar import GrammarConcept, UserGrammarProgress
from app.db.models.user import User
from app.db.models.session import LearningSession
from app.services.llm_service import LLMService


# Conversation style templates for variety
CONVERSATION_STYLES = [
    {
        "id": "casual",
        "name": "Casual Chat",
        "system_prompt_addition": "Tu parles de manière décontractée, comme un ami français. Utilise des expressions familières.",
    },
    {
        "id": "curious",
        "name": "Curious Interviewer", 
        "system_prompt_addition": "Tu poses beaucoup de questions sur la vie et les opinions de l'utilisateur. Tu es vraiment intéressé.",
    },
    {
        "id": "debate",
        "name": "Playful Debate",
        "system_prompt_addition": "Tu aimes discuter et parfois tu n'es pas d'accord pour provoquer une réflexion. Reste amical.",
    },
    {
        "id": "storyteller",
        "name": "Storyteller",
        "system_prompt_addition": "Tu racontes des petites histoires et tu invites l'utilisateur à continuer ou réagir.",
    },
]

# Context scenarios based on time of day
TIME_CONTEXTS = {
    "morning": ["Au café", "En route vers le travail", "Le petit-déjeuner"],
    "afternoon": ["Pause déjeuner", "Une promenade", "Au bureau"],
    "evening": ["Au restaurant", "Après le travail", "Chez des amis"],
    "night": ["Un film à la maison", "Lecture du soir", "Réflexions de la journée"],
}

# Roleplay Scenarios with specific missions
ROLEPLAY_SCENARIOS = [
    {
        "id": "bakery",
        "title": "À la Boulangerie",
        "description": "Buy bread and pastries for a breakfast with friends.",
        "difficulty": "A1",
        "objectives": [
            "Saluer le boulanger",
            "Commander une baguette et deux croissants",
            "Demander le prix total",
            "Payer et dire au revoir"
        ],
        "system_prompt": """Tu es un boulanger parisien sympathique.
- Tu vends du pain, des croissants, des pains au chocolat.
- Sois poli mais efficace.
- Si l'utilisateur ne salue pas, fais-lui remarquer gentiment.
- Le total doit être réaliste (ex: 1,20€ la baguette, 1,10€ le croissant)."""
    },
    {
        "id": "doctor",
        "title": "Chez le Médecin",
        "description": "Describe your symptoms and understand the doctor's advice.",
        "difficulty": "A2",
        "objectives": [
            "Expliquer que tu as mal à la tête et de la fièvre",
            "Dire depuis combien de temps ça dure",
            "Comprendre l'ordonnance du médecin"
        ],
        "system_prompt": """Tu es un médecin généraliste.
- Tu reçois un patient (l'utilisateur).
- Pose des questions sur les symptômes (Où ? Depuis quand ? Intensité ?).
- Sois professionnel et rassurant.
- Finis par donner un diagnostic simple (grippe, rhume) et une prescription."""
    },
    {
        "id": "directions",
        "title": "Perdu dans la ville",
        "description": "Ask a stranger for directions to the museum.",
        "difficulty": "A1",
        "objectives": [
            "Excuse-toi de déranger",
            "Demande où est le Musée du Louvre",
            "Demande si c'est loin",
            "Remercie la personne"
        ],
        "system_prompt": """Tu es un parisien pressé mais serviable dans la rue.
- L'utilisateur t'arrête pour demander son chemin.
- Donne des indications claires (tout droit, à gauche, prendre le métro).
- Utilise des impératifs (allez, tournez, prenez)."""
    },
    {
        "id": "restaurant_order",
        "title": "Commande au Restaurant",
        "description": "Order a full meal including specific dietary requests.",
        "difficulty": "B1",
        "objectives": [
            "Demander une table pour deux",
            "Commander une entrée et un plat",
            "Demander si un plat contient des arachides (allergie)",
            "Demander l'addition"
        ],
        "system_prompt": """Tu es serveur dans un bistro traditionnel.
- Accueille le client.
- Prends la commande.
- Si le client demande pour les allergènes, vérifie en cuisine (invente une réponse).
- Propose un dessert ou un café à la fin."""
    },
    {
        "id": "job_interview",
        "title": "Entretien d'embauche",
        "description": "Answer questions about your experience and motivation.",
        "difficulty": "B2",
        "objectives": [
            "Te présenter brièvement",
            "Expliquer ta motivation pour le poste",
            "Parler de tes qualités et défauts",
            "Poser une question sur l'entreprise"
        ],
        "system_prompt": """Tu es recruteur pour une entreprise tech française.
- Tu fais passer un entretien.
- Pose des questions classiques (Présentez-vous, Pourquoi nous ?, Qualités/Défauts).
- Sois formel (voussoiement obligatoire).
- Évalue la capacité du candidat à structurer sa pensée."""
    }
]


class AudioSessionService:
    """Service for audio-only conversation sessions with smart context."""

    def __init__(self, db: Session, llm_service: LLMService | None = None) -> None:
        self.db = db
        self.llm = llm_service or LLMService()

    def get_available_scenarios(self) -> list[dict]:
        """Return list of available roleplay scenarios."""
        return ROLEPLAY_SCENARIOS

    def _get_time_context(self) -> str:
        """Get appropriate context based on current time."""
        hour = datetime.now().hour
        if 5 <= hour < 12:
            period = "morning"
        elif 12 <= hour < 17:
            period = "afternoon"
        elif 17 <= hour < 21:
            period = "evening"
        else:
            period = "night"
        
        return random.choice(TIME_CONTEXTS[period])

    def _get_conversation_style(self) -> dict:
        """Pick a conversation style for variety."""
        return random.choice(CONVERSATION_STYLES)

    def _fetch_due_errors(self, user_id: UUID, limit: int = 3) -> list[UserError]:
        """Get errors to weave into conversation."""
        now = datetime.now(timezone.utc)
        return (
            self.db.query(UserError)
            .filter(
                UserError.user_id == user_id,
                UserError.next_review_date <= now,
                UserError.state != "mastered"
            )
            .order_by(UserError.lapses.desc(), UserError.next_review_date.asc())
            .limit(limit)
            .all()
        )

    def _fetch_weak_grammar(self, user_id: UUID, limit: int = 2) -> list[GrammarConcept]:
        """Get grammar concepts the user struggles with."""
        weak_progress = (
            self.db.query(UserGrammarProgress)
            .filter(
                UserGrammarProgress.user_id == user_id,
                UserGrammarProgress.last_score < 7,  # Below "good"
                UserGrammarProgress.times_reviewed > 0
            )
            .order_by(UserGrammarProgress.last_score.asc())
            .limit(limit)
            .all()
        )
        
        concept_ids = [p.concept_id for p in weak_progress]
        if not concept_ids:
            return []
        
        return self.db.query(GrammarConcept).filter(GrammarConcept.id.in_(concept_ids)).all()

    def _fetch_recent_vocabulary(self, user_id: UUID, limit: int = 5) -> list[str]:
        """Get recently learned vocabulary words."""
        # This would query UserVocabularyProgress - simplified for now
        return []

    def _build_error_weaving_instructions(self, errors: list[UserError]) -> str:
        """Create instructions for weaving errors into conversation."""
        if not errors:
            return ""
        
        instructions = "\n\n# ERREURS À PRATIQUER (subtly weave these into conversation):\n"
        for i, error in enumerate(errors, 1):
            instructions += f"""
{i}. Concept: {error.subcategory or error.error_category}
   - Erreur typique: "{error.original_text}"
   - Correction: "{error.correction}"
   - Crée des situations où l'utilisateur doit utiliser cette structure correctement.
"""
        return instructions

    def _build_grammar_focus_instructions(self, concepts: list[GrammarConcept]) -> str:
        """Create instructions for practicing weak grammar."""
        if not concepts:
            return ""
        
        instructions = "\n\n# GRAMMAIRE À PRATIQUER:\n"
        for concept in concepts:
            instructions += f"- {concept.name} ({concept.level}): Utilise des structures qui encouragent l'utilisateur à pratiquer ce concept.\n"
        return instructions

    async def _search_user_interests(self, interests: str) -> str:
        """Use search to find current topics related to user interests."""
        if not interests:
            return ""
        
        # For now, return empty - will integrate Perplexity/search API later
        # This is where we'd call a search-enabled LLM
        return ""

    async def create_audio_session(
        self,
        user: User,
        duration_minutes: int = 5,
        scenario_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a new audio-only session.
        
        Args:
            scenario_id: Optional ID of a specific roleplay scenario.
                         If None, creates a dynamic casual session.
        """
        # Gather context
        due_errors = self._fetch_due_errors(user.id)
        weak_grammar = self._fetch_weak_grammar(user.id)
        
        # Determine Session Type (Roleplay vs Casual)
        scenario = None
        if scenario_id:
            scenario = next((s for s in ROLEPLAY_SCENARIOS if s["id"] == scenario_id), None)
        
        if scenario:
            # ROLEPLAY MODE
            topic = f"Roleplay: {scenario['title']}"
            style_name = "Roleplay"
            objectives = scenario.get("objectives", [])
            objectives_text = "\n".join([f"- {obj}" for obj in objectives])
            
            system_prompt = f"""Tu joues un rôle spécifique dans une simulation pour apprenant de français.

# SCÉNARIO: {scenario['title']}
{scenario['description']}

# TON RÔLE:
{scenario['system_prompt']}

# OBJECTIFS DE L'UTILISATEUR (Aide-le à les atteindre):
{objectives_text}

# RÈGLES DU JEU DE RÔLE:
1. Reste strictment dans ton personnage.
2. Ne mentionne pas que c'est un exercice, sauf si l'utilisateur est bloqué.
3. Si l'utilisateur réussit un objectif, passe naturellement à la suite.
4. Parle avec le niveau de langue adapté à la situation (ex: formel pour un médecin).

# ADAPTATION:
- Niveau utilisateur: {user.proficiency_level}
{self._build_error_weaving_instructions(due_errors)}
"""
        else:
            # DYNAMIC CASUAL MODE
            time_context = self._get_time_context()
            style = self._get_conversation_style()
            topic = time_context
            style_name = style['name']
            
            # Search for interest-based topics
            interest_context = await self._search_user_interests(user.interests or "")
            
            system_prompt = f"""Tu es un locuteur français natif ayant une conversation audio avec un apprenant.

# CONTEXTE DE LA SESSION:
- Situation: {time_context}
- Durée prévue: {duration_minutes} minutes
- Niveau de l'utilisateur: {user.proficiency_level}
- Style de conversation: {style['name']}

# TON STYLE:
{style['system_prompt_addition']}

# RÈGLES AUDIO-ONLY:
1. Parle naturellement, comme dans une vraie conversation
2. Garde tes réponses à 2-3 phrases maximum
3. Pose des questions ouvertes pour encourager l'utilisateur à parler
4. Si tu ne comprends pas, demande poliment de répéter
5. Adapte ta vitesse au niveau de l'utilisateur
{self._build_error_weaving_instructions(due_errors)}
{self._build_grammar_focus_instructions(weak_grammar)}

# INTÉRÊTS DE L'UTILISATEUR:
{user.interests or 'Non spécifiés - reste général'}
{interest_context}

IMPORTANT: Ne mentionne JAMAIS que tu pratiques des erreurs ou de la grammaire. 
La conversation doit sembler 100% naturelle."""

        # Generate opening message
        opening_prompt = f"""Commence la conversation de manière naturelle en français.
Contexte: {time_context}
Fais une remarque ou pose une question pour lancer la discussion.
Maximum 2 phrases."""

        try:
            result = self.llm.generate_chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": opening_prompt}
                ],
                temperature=0.8,
                max_tokens=150
            )
            opening_message = result.content
        except Exception as e:
            logger.error(f"Failed to generate opening: {e}")
            opening_message = "Bonjour ! Comment ça va aujourd'hui ?"

        # Create session record
        session = LearningSession(
            user_id=user.id,
            planned_duration_minutes=duration_minutes,
            conversation_style=style['id'],
            topic=time_context,
            difficulty_preference=user.proficiency_level,
            status="in_progress",
            level_before=user.level,
            level_after=user.level,
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)

        return {
            "session_id": str(session.id),
            "opening_message": opening_message,
            "context": {
                "situation": time_context,
                "style": style['name'],
                "duration_minutes": duration_minutes,
            },
            "target_errors": [
                {"category": e.error_category, "subcategory": e.subcategory} 
                for e in due_errors
            ],
            "system_prompt": system_prompt,  # Store for subsequent turns
        }

    async def process_user_response(
        self,
        session_id: UUID,
        user_text: str,
        system_prompt: str,
        conversation_history: list[dict],
    ) -> dict[str, Any]:
        """Process user's spoken response and generate AI reply.
        
        Args:
            session_id: Active session ID
            user_text: Transcribed user speech
            system_prompt: The system prompt from session start
            conversation_history: Previous messages in the conversation
        
        Returns:
            Dict with AI response, detected errors, and XP
        """
        from app.core.error_detection.detector import ErrorDetector
        from app.core.error_concepts import get_concept_for_pattern, get_concept_for_category
        from app.db.models.error import UserErrorConcept
        from app.db.models.session import LearningSession
        from datetime import datetime, timezone
        
        # Get session and user
        session = self.db.get(LearningSession, session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        user = session.user
        
        # Add user message to history
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(conversation_history)
        messages.append({"role": "user", "content": user_text})

        try:
            result = self.llm.generate_chat_completion(
                messages=messages,
                temperature=0.8,
                max_tokens=200
            )
            ai_response = result.content
        except Exception as e:
            logger.error(f"Failed to generate response: {e}")
            ai_response = "Pardon, je n'ai pas bien compris. Tu peux répéter ?"

        # Run error detection on user_text
        error_detector = ErrorDetector(llm_service=self.llm)
        error_result = error_detector.analyze(
            user_text,
            learner_level=user.proficiency_level or "A1",
            use_llm=True,
        )
        
        # Persist errors to UserError table for SRS tracking
        detected_errors = []
        processed_concepts: set[str] = set()
        
        for error in error_result.errors:
            # Skip low confidence errors
            if error.confidence < 0.6:
                continue
            
            # Extract subcategory from error
            subcategory = getattr(error, 'subcategory', None) or error.code.replace('llm_', '') if error.code.startswith('llm_') else error.code
            
            # Check for existing error with same category + subcategory
            existing = self.db.query(UserError).filter(
                UserError.user_id == user.id,
                UserError.error_category == error.category,
                UserError.subcategory == subcategory,
            ).first()
            
            if existing:
                # Update existing error - repeated mistake
                existing.occurrences = (existing.occurrences or 1) + 1
                existing.lapses = (existing.lapses or 0) + 1
                existing.original_text = error.span
                existing.context_snippet = error.message
                existing.correction = error.suggestion
                existing.difficulty = min(10.0, (existing.difficulty or 5.0) + 0.5)
                existing.next_review_date = datetime.now(timezone.utc)
                if existing.state in ("review", "mastered"):
                    existing.state = "relearning"
                existing.updated_at = datetime.now(timezone.utc)
            else:
                # Create new error record
                user_error = UserError(
                    user_id=user.id,
                    session_id=session_id,
                    message_id=None,
                    error_category=error.category,
                    error_pattern=subcategory,
                    subcategory=subcategory,
                    original_text=error.span,
                    correction=error.suggestion,
                    context_snippet=error.message,
                    state="new",
                    stability=0.0,
                    difficulty=5.0,
                    occurrences=1,
                    next_review_date=datetime.now(timezone.utc),
                )
                self.db.add(user_error)
            
            # Update parent concept for concept-level SRS
            concept = get_concept_for_pattern(subcategory)
            if not concept:
                concept = get_concept_for_category(error.category)
            
            if concept and concept.id not in processed_concepts:
                processed_concepts.add(concept.id)
                
                user_concept = self.db.query(UserErrorConcept).filter(
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
                    self.db.add(user_concept)
            
            # Format for response
            detected_errors.append({
                "code": error.code,
                "message": error.message,
                "span": error.span,
                "correction": error.suggestion,
                "category": error.category,
                "severity": error.severity,
                "concept_id": concept.id if concept else None,
                "concept_name": concept.name if concept else None,
            })
        
        self.db.commit()
        
        # Calculate XP (base + penalty for errors)
        xp_awarded = 10
        if detected_errors:
            xp_awarded = max(5, xp_awarded - len(detected_errors) * 2)

        return {
            "ai_response": ai_response,
            "detected_errors": detected_errors,
            "xp_awarded": xp_awarded,
        }


__all__ = ["AudioSessionService"]
