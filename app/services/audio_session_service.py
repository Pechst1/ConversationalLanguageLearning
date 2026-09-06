"""Audio Session Service for zero-config, audio-only conversations.

This service handles:
- Smart auto-context generation (errors, interests, variety)
- Error-weaving into conversation prompts
- Session lifecycle for audio-only mode
"""
from __future__ import annotations

import random
from datetime import datetime
from typing import Any
from uuid import UUID

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.error import UserError
from app.db.models.grammar import GrammarConcept, UserGrammarProgress
from app.db.models.serial import SerialThread
from app.db.models.session import ConversationMessage, LearningSession
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services.atelier_rewards import AtelierRewardService
from app.services.daily_words import DailyWordSlateService
from app.services.error_memory import ErrorMemoryService
from app.services.llm_service import LLMService
from app.services.pilot_events import PilotEventService
from app.services.serial import SerialThreadService
from app.services.vocabulary_credit import VocabularyCreditService

# Spoken turns must come back fast and always with content: gpt-5 class models
# bill reasoning against the completion ceiling, so the call sets an explicit
# minimal effort and keeps headroom above the 2-3 sentences we actually want.
SPOKEN_REASONING_EFFORT = "minimal"
OPENING_MAX_TOKENS = 400
REPLY_MAX_TOKENS = 500
OPENING_FALLBACK = "Bonjour ! Comment ça va aujourd'hui ?"
REPLY_FALLBACK = "Pardon, je n'ai pas bien compris. Tu peux répéter ?"

# Whisper decides the commas, the capitals and whether "3" is written "trois";
# a spoken session must never bill the learner for those.
TRANSCRIPTION_ARTIFACT_TOKENS = (
    "punctuation",
    "capitalization",
    "capitalisation",
    "spelling",
    "orthograph",
    "typo",
)

# Conversation style templates for variety. `name` is published in the start
# payload as `context.style`, so it is written in the publication language.
CONVERSATION_STYLES = [
    {
        "id": "casual",
        "name": "Conversation détendue",
        "system_prompt_addition": "Tu parles de manière décontractée, comme un ami français. Utilise des expressions familières.",
    },
    {
        "id": "curious",
        "name": "Entretien curieux", 
        "system_prompt_addition": "Tu poses beaucoup de questions sur la vie et les opinions de l'utilisateur. Tu es vraiment intéressé.",
    },
    {
        "id": "debate",
        "name": "Débat amical",
        "system_prompt_addition": "Tu aimes discuter et parfois tu n'es pas d'accord pour provoquer une réflexion. Reste amical.",
    },
    {
        "id": "storyteller",
        "name": "Conteur",
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
        "description": "Acheter du pain et des viennoiseries pour un petit-déjeuner entre amis.",
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
        "description": "Décrire ses symptômes et comprendre les conseils du médecin.",
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
        "description": "Demander son chemin jusqu'au musée à un inconnu.",
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
        "description": "Commander un repas complet et signaler une contrainte alimentaire.",
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
        "description": "Répondre aux questions sur son parcours et sa motivation.",
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


class AudioSessionNotFoundError(Exception):
    """The requested audio session does not exist for the current user."""


class AudioSessionUnavailableError(Exception):
    """The audio session cannot accept another response."""


class AudioSessionService:
    """Service for audio-only conversation sessions with smart context."""

    def __init__(
        self,
        db: Session,
        llm_service: LLMService | None = None,
        *,
        initialize_llm: bool = True,
    ) -> None:
        self.db = db
        self.llm = llm_service or (LLMService() if initialize_llm else None)

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
        
        return random.choice(TIME_CONTEXTS[period])  # noqa: S311 - content variety only

    def _get_conversation_style(self) -> dict:
        """Pick a conversation style for variety."""
        return random.choice(CONVERSATION_STYLES)  # noqa: S311 - content variety only

    def _serial_call_context(self, user: User) -> tuple[SerialThread | None, dict[str, Any] | None]:
        thread = self.db.scalar(
            select(SerialThread)
            .where(SerialThread.user_id == user.id, SerialThread.status == "active")
            .order_by(SerialThread.updated_at.desc())
        )
        if not thread:
            return None, None
        service = SerialThreadService(self.db)
        cast = service.cast_payload(thread)
        if not cast:
            return thread, None
        episode = service.current_episode(thread)
        required = [
            str(value)
            for value in ((episode.brief_payload or {}).get("required_cast") or [])
            if str(value).strip()
        ] if episode else []
        by_id = {str(member.get("id")): member for member in cast}
        member = next(
            (by_id[value] for value in required if value in by_id),
            by_id.get("romy_tremblay") or cast[0],
        )
        return thread, member

    def _fetch_due_errors(self, user_id: UUID, limit: int = 3) -> list[UserError]:
        """Get errors to weave into conversation."""
        user = self.db.get(User, user_id)
        if not user:
            return []
        return ErrorMemoryService(self.db).due_error_records(user, limit=limit)

    def _fetch_weak_grammar(self, user_id: UUID, limit: int = 2) -> list[GrammarConcept]:
        """Get grammar concepts the user struggles with.

        The SRS columns are `score`/`reps` on ``user_grammar_progress``; the
        older `last_score`/`times_reviewed` names raised AttributeError here and
        made every call to ``/audio-session/start`` fail with a 500.
        """
        weak_progress = (
            self.db.query(UserGrammarProgress)
            .filter(
                UserGrammarProgress.user_id == user_id,
                UserGrammarProgress.score < 7,  # Below "good"
                UserGrammarProgress.reps > 0,
            )
            .order_by(UserGrammarProgress.score.asc())
            .limit(limit)
            .all()
        )

        concept_ids = [p.concept_id for p in weak_progress]
        if not concept_ids:
            return []

        return (
            self.db.query(GrammarConcept)
            .filter(GrammarConcept.id.in_(concept_ids), GrammarConcept.active.is_(True))
            .all()
        )

    def _build_error_weaving_instructions(self, errors: list[UserError]) -> str:
        """Create instructions for weaving errors into conversation."""
        if not errors:
            return ""
        
        instructions = "\n\n# ERREURS À PRATIQUER (subtly weave these into conversation):\n"
        for i, error in enumerate(errors, 1):
            instructions += f"""
{i}. Concept: {error.display_label or error.subcategory or error.error_category}
   - Erreur typique: "{error.original_text}"
   - Correction: "{error.correction}"
   - Pourquoi: {error.why_wrong or error.context_snippet or 'Use this contrast correctly.'}
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
        time_context = self._get_time_context()
        style = self._get_conversation_style()
        serial_thread, cast_member = self._serial_call_context(user) if not scenario_id else (None, None)
        
        # Determine Session Type (Roleplay vs Casual)
        scenario = None
        if scenario_id:
            scenario = next((s for s in ROLEPLAY_SCENARIOS if s["id"] == scenario_id), None)
        
        if scenario:
            # ROLEPLAY MODE
            topic = f"Scène : {scenario['title']}"
            style_name = "Scène jouée"
            session_style_id = "roleplay"
            opening_context = scenario["title"]
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
            topic = time_context
            style_name = style['name']
            session_style_id = style["id"]
            opening_context = time_context

            relationship = (cast_member or {}).get("relationship") or {}
            cast_instruction = ""
            if cast_member:
                callbacks = ", ".join(str(item) for item in relationship.get("callbacks") or [])
                cast_instruction = f"""
# PERSONNAGE DU FEUILLETON
Tu es {cast_member.get('name')}, {cast_member.get('role') or 'une personne de son histoire'}.
Ta dynamique avec l'apprenant : {cast_member.get('dynamic_with_user') or 'une relation qui se construit'}.
Vous vous parlez au registre « {relationship.get('register') or 'vous'} ».
Dernier souvenir commun : {relationship.get('last_summary') or 'votre histoire vient de commencer'}.
Rappels possibles : {callbacks or 'aucun encore'}.
Reste ce personnage pendant tout l'appel. Corrige discrètement par reformulation,
sans interrompre le fil ni annoncer une leçon.
"""
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
{cast_instruction}

IMPORTANT: Ne mentionne JAMAIS que tu pratiques des erreurs ou de la grammaire. 
La conversation doit sembler 100% naturelle."""

        # Generate opening message
        opening_prompt = f"""Commence la conversation de manière naturelle en français.
Contexte: {opening_context}
{f"Tu es {cast_member.get('name')}; reprends subtilement votre relation existante." if cast_member else ""}
Fais une remarque ou pose une question pour lancer la discussion.
Maximum 2 phrases."""

        try:
            result = self.llm.generate_chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": opening_prompt}
                ],
                temperature=0.8,
                # gpt-5 reasoning models spend the whole budget on reasoning and
                # return empty content when the ceiling is tight and the effort is
                # unset -- every opening line fell back to the canned greeting.
                max_tokens=OPENING_MAX_TOKENS,
                reasoning_effort=SPOKEN_REASONING_EFFORT,
            )
            opening_message = (result.content or "").strip() or OPENING_FALLBACK
        except Exception as e:
            logger.error(f"Failed to generate opening: {e}")
            opening_message = OPENING_FALLBACK

        # Create session record
        session = LearningSession(
            user_id=user.id,
            planned_duration_minutes=duration_minutes,
            conversation_style=session_style_id,
            topic=topic,
            scenario=str(cast_member.get("id")) if cast_member else (scenario["id"] if scenario else None),
            difficulty_preference=user.proficiency_level,
            status="in_progress",
            level_before=user.level,
            level_after=user.level,
        )
        self.db.add(session)
        self.db.flush()
        self.db.add(
            ConversationMessage(
                session_id=session.id,
                sender="ai",
                content=opening_message,
                sequence_number=1,
                xp_earned=0,
                generation_prompt=system_prompt,
            )
        )
        PilotEventService(self.db).record(
            "plan_started",
            user_id=user.id,
            entity_type="audio_session",
            entity_id=session.id,
            payload={"scenario_id": scenario["id"] if scenario else None, "duration_minutes": duration_minutes},
        )
        self.db.commit()
        self.db.refresh(session)

        return {
            "session_id": str(session.id),
            "opening_message": opening_message,
            "context": {
                "situation": opening_context,
                "style": style_name,
                "duration_minutes": duration_minutes,
                "scenario_id": scenario["id"] if scenario else None,
                "cast_member": cast_member,
                "serial_thread_id": str(serial_thread.id) if serial_thread else None,
            },
            "target_errors": [
                {"category": e.error_category, "subcategory": e.subcategory} 
                for e in due_errors
            ],
        }

    async def process_user_response(
        self,
        session_id: UUID,
        user_id: UUID,
        user_text: str,
        conversation_history: list[dict],
    ) -> dict[str, Any]:
        """Process user's spoken response and generate AI reply.
        
        Args:
            session_id: Active session ID
            user_id: Authenticated owner of the session
            user_text: Transcribed user speech
            conversation_history: Previous messages in the conversation
        
        Returns:
            Dict with AI response, detected errors, and XP
        """
        from app.core.error_detection.detector import ErrorDetector
        # Fetch by both identifiers so one user cannot write into another
        # user's learning history by guessing or obtaining a session UUID.
        session = self.db.scalar(
            select(LearningSession).where(
                LearningSession.id == session_id,
                LearningSession.user_id == user_id,
            ).with_for_update()
        )
        if not session:
            raise AudioSessionNotFoundError("Audio session not found")
        if session.status != "in_progress":
            raise AudioSessionUnavailableError("Audio session is no longer active")

        user = self.db.scalar(
            select(User).where(User.id == user_id).with_for_update()
        )
        if user is None:
            raise AudioSessionNotFoundError("Audio session not found")

        system_prompt = self.db.scalar(
            select(ConversationMessage.generation_prompt)
            .where(
                ConversationMessage.session_id == session.id,
                ConversationMessage.generation_prompt.is_not(None),
            )
            .order_by(ConversationMessage.sequence_number)
            .limit(1)
        )
        if not system_prompt:
            raise AudioSessionUnavailableError(
                "Audio session must be restarted"
            )

        # Add user message to history
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(
            {
                "role": message["role"],
                "content": message["content"][:4000],
            }
            for message in conversation_history[-20:]
            if message.get("role") in {"user", "assistant"}
            and isinstance(message.get("content"), str)
        )
        messages.append({"role": "user", "content": user_text})

        try:
            result = self.llm.generate_chat_completion(
                messages=messages,
                temperature=0.8,
                # See create_audio_session: a tight ceiling without an explicit
                # effort starves gpt-5 content and turns every reply into the
                # "je n'ai pas bien compris" fallback.
                max_tokens=REPLY_MAX_TOKENS,
                reasoning_effort=SPOKEN_REASONING_EFFORT,
            )
            ai_response = (result.content or "").strip() or REPLY_FALLBACK
        except Exception as e:
            logger.error(f"Failed to generate response: {e}")
            ai_response = REPLY_FALLBACK

        # Run error detection on user_text
        error_detector = ErrorDetector(llm_service=self.llm, explanation_language=getattr(user, "native_language", None))
        error_result = error_detector.analyze(
            user_text,
            learner_level=user.proficiency_level or "A1",
            use_llm=True,
        )
        
        # Persist errors to unified error memory for SRS tracking
        detected_errors = []
        error_memory = ErrorMemoryService(self.db)
        seen_spans: list[str] = []

        # Shortest span first: the detector files the same repair on the word and
        # again on the whole sentence, and the precise card is the useful one.
        for error in sorted(error_result.errors, key=lambda item: len(item.span or "")):
            # Skip low confidence errors
            if error.confidence < 0.6:
                continue
            # The learner spoke; commas, capitals and spelling are Whisper's
            # rendering, not a mistake they made. Charging them for those turned
            # clean turns into "fautes de forme" on the recap and filed junk
            # errata into the SRS.
            if not self._is_spoken_mistake(error.category, error.code, error.severity):
                continue
            # The detector answers with alternatives and parenthetical glosses
            # ("allée (wenn weiblich) oder allé"); the recap has room for the
            # repair itself, and the gloss already lives in the explanation.
            suggestion = self._primary_suggestion(error.suggestion)
            # A "correction" that repeats the learner's own words is not a
            # correction: it must not be filed, counted, or printed on the recap
            # (same rule the mission corrector applies to its errata).
            if not self._is_real_correction(error.span, suggestion):
                continue
            # One card per fix: a span that merely restates a repair already
            # filed (the same words inside a longer quote) is the same mistake.
            folded_span = self._fold_for_comparison(error.span)
            if any(folded_span in seen or seen in folded_span for seen in seen_spans):
                continue
            seen_spans.append(folded_span)

            memory_update = error_memory.record_detected_error(
                user=user,
                detected_error=error,
                source_type="audio",
                session=session,
                source_payload={"mode": "audio_session"},
            )
            
            # Format for response
            detected_errors.append({
                "code": error.code,
                "message": error.message,
                "span": error.span,
                "correction": suggestion,
                "category": error.category,
                "severity": error.severity,
                "memory": memory_update,
            })
        
        # XP rewards participation. Errors feed the repair loop; they never
        # subtract from the reward for taking a conversational risk.
        xp_awarded = 10

        last_sequence = self.db.scalar(
            select(func.max(ConversationMessage.sequence_number)).where(
                ConversationMessage.session_id == session.id
            )
        ) or 0
        previous_user_error_payloads = self.db.scalars(
            select(ConversationMessage.errors_detected).where(
                ConversationMessage.session_id == session.id,
                ConversationMessage.sender == "user",
            )
        ).all()
        had_previous_error = any(bool(payload) for payload in previous_user_error_payloads)
        user_message = ConversationMessage(
            session_id=session.id,
            sender="user",
            content=user_text,
            sequence_number=last_sequence + 1,
            errors_detected=detected_errors or None,
            xp_earned=xp_awarded,
        )
        self.db.add_all(
            [
                user_message,
                ConversationMessage(
                    session_id=session.id,
                    sender="ai",
                    content=ai_response,
                    sequence_number=last_sequence + 2,
                    xp_earned=0,
                ),
            ]
        )

        session.xp_earned = int(session.xp_earned or 0) + xp_awarded
        if detected_errors:
            session.incorrect_responses = int(session.incorrect_responses or 0) + 1
        else:
            session.correct_responses = int(session.correct_responses or 0) + 1
        response_count = int(session.correct_responses or 0) + int(
            session.incorrect_responses or 0
        )
        session.accuracy_rate = (
            float(session.correct_responses or 0) / response_count
            if response_count
            else None
        )
        user.total_xp = int(user.total_xp or 0) + xp_awarded
        user.mark_activity()
        self.db.flush([user_message])

        vocabulary_credit = self._credit_daily_words(
            user=user,
            session=session,
            message=user_message,
            learner_text=user_text,
        )
        PilotEventService(self.db).record(
            "speaking_turn",
            user_id=user.id,
            entity_type="audio_session",
            entity_id=session.id,
            payload={
                "words": len(user_text.split()),
                "errors": len(detected_errors),
                "due_words_reused": vocabulary_credit.get("words") or [],
            },
            cost_usd=float(getattr(result, "cost", 0.0) or 0.0) if "result" in locals() else 0.0,
        )
        self.db.commit()

        minted_collectibles: list[dict[str, Any]] = []
        recovery = had_previous_error and not detected_errors
        if detected_errors or recovery:
            minted_collectibles = AtelierRewardService(self.db).mint_conversation_effort_token(
                user_id=user.id,
                source_kind="audio_turn",
                source_ref=f"{session.id}:{user_message.sequence_number}",
                recovery=recovery,
                word_count=len(user_text.split()),
                error_count=len(detected_errors),
                session_id=session.id,
            )

        return {
            "ai_response": ai_response,
            "detected_errors": detected_errors,
            "xp_awarded": xp_awarded,
            "vocabulary_credit": vocabulary_credit,
            "minted_collectibles": minted_collectibles,
        }

    def complete_serial_call(
        self,
        *,
        user: User,
        session: LearningSession,
        user_messages: list[ConversationMessage],
    ) -> dict[str, Any] | None:
        """Write voice-call closeness and callbacks into the canonical serial memory."""
        character_id = str(session.scenario or "")
        if not character_id or not user_messages:
            return None
        thread, _ = self._serial_call_context(user)
        if not thread:
            return None
        cast = SerialThreadService(self.db).cast_payload(thread)
        member = next((item for item in cast if str(item.get("id")) == character_id), None)
        if not member:
            return None
        import json

        state = json.loads(json.dumps(thread.state or {}))
        relationships = dict(state.get("relationships") or {})
        entry = dict(relationships.get(character_id) or {})
        entry["closeness"] = min(5, max(0, int(entry.get("closeness") or 0)) + 1)
        entry["register"] = str(entry.get("register") or (member.get("relationship") or {}).get("register") or "vous")
        last_words = " ".join((user_messages[-1].content or "").split())[:120]
        entry["last_summary"] = f"Vous avez parlé au téléphone; l’apprenant a dit « {last_words} »."
        callbacks = [str(value) for value in entry.get("callbacks") or [] if str(value).strip()]
        callback = f"appel · {last_words[:70]}"
        if callback not in callbacks:
            callbacks.append(callback)
        entry["callbacks"] = callbacks[-5:]
        relationships[character_id] = entry
        state["relationships"] = relationships
        calls = [value for value in state.get("voice_calls") or [] if isinstance(value, dict)]
        calls.append({
            "character_id": character_id,
            "character_name": member.get("name"),
            "summary": entry["last_summary"],
            "turns": len(user_messages),
            "completed_at": datetime.now().isoformat(),
        })
        state["voice_calls"] = calls[-8:]
        thread.state = state
        self.db.add(thread)
        return {"cast_member": member, "relationship": entry}

    def _credit_daily_words(
        self,
        *,
        user: User,
        session: LearningSession,
        message: ConversationMessage,
        learner_text: str,
    ) -> dict[str, Any]:
        """Credit honest reuse of today's slate words in an audio turn."""
        slate = DailyWordSlateService(self.db).get_or_create(user=user)
        entries = [entry for entry in slate.get("words") or [] if isinstance(entry, dict)]
        if not entries:
            return {"produced_correct": 0, "word_ids": [], "words": []}

        normalized_text = self._normalize_match_text(learner_text)
        matched_entries = [
            entry
            for entry in entries
            if self._contains_word(normalized_text, str(entry.get("word") or ""))
        ]
        if not matched_entries:
            return {"produced_correct": 0, "word_ids": [], "words": []}

        ids = [int(entry["word_id"]) for entry in matched_entries if str(entry.get("word_id") or "").isdigit()]
        words = (
            self.db.query(VocabularyWord)
            .filter(VocabularyWord.id.in_(ids))
            .all()
            if ids
            else []
        )
        credit_service = VocabularyCreditService(self.db)
        results = [
            credit_service.apply(
                user=user,
                word=word,
                event_type="produced_correct",
                source_type="audio",
                learner_text=learner_text,
                context=session.topic or "Conversation audio",
                session=session,
                message=message,
                source_payload={
                    "credit_source": "audio_daily_word_reuse",
                    "session_id": str(session.id),
                },
            )
            for word in words
        ]
        message.words_used = [str(entry.get("word") or "") for entry in matched_entries]
        self.db.add(message)
        DailyWordSlateService(self.db).record_encounters(user=user, word_ids=ids, kind="place")
        return {
            **credit_service.summarize(results),
            "word_ids": ids,
            "words": [str(entry.get("word") or "") for entry in matched_entries],
        }

    @staticmethod
    def _is_spoken_mistake(category: str | None, code: str | None, severity: str | None) -> bool:
        """False for findings a speaker cannot have made out loud.

        Punctuation, capitalisation and spelling belong to the transcription,
        and a low-severity style note is not a "faute de forme" worth filing
        against a spoken turn.
        """
        label = f"{category or ''} {code or ''}".casefold()
        if any(token in label for token in TRANSCRIPTION_ARTIFACT_TOKENS):
            return False
        if (category or "").casefold() != "grammar" and (severity or "").casefold() == "low":
            return False
        return True

    @staticmethod
    def _primary_suggestion(suggestion: str) -> str:
        """Keep the repair itself, drop the alternatives and the gloss."""
        import re

        value = (suggestion or "").strip()
        cut = re.split(r"\s+/\s+|\s+\(|\s+oder\s+|\s+ou bien\s+", value, maxsplit=1)[0]
        return cut.strip().strip(",;:") or value

    @classmethod
    def _is_real_correction(cls, span: str, suggestion: str) -> bool:
        """True when the suggestion actually changes the spoken words.

        Accents and elisions are meaningful (marche/marché, je ai/j'ai) so they
        survive the fold, unlike the vocabulary matcher; punctuation and case are
        not audible and so must not count as a repair on their own.
        """
        original = cls._fold_for_comparison(span)
        repaired = cls._fold_for_comparison(suggestion)
        return bool(original and repaired and original != repaired)

    @staticmethod
    def _fold_for_comparison(value: str) -> str:
        import re

        folded = (value or "").casefold()
        for quote in ("‘", "’", "ʼ", "`", "´"):
            folded = folded.replace(quote, "'")
        # Keep the elision apostrophe, drop every other mark: it is not spoken.
        folded = re.sub(r"[^\w'’\s]+", " ", folded, flags=re.UNICODE)
        return re.sub(r"\s+", " ", folded).strip()

    @staticmethod
    def _normalize_match_text(value: str) -> str:
        import re
        import unicodedata

        normalized = unicodedata.normalize("NFKD", value.casefold())
        without_marks = "".join(char for char in normalized if not unicodedata.combining(char))
        return " ".join(re.findall(r"[a-z0-9]+", without_marks))

    @classmethod
    def _contains_word(cls, normalized_text: str, word: str) -> bool:
        normalized_word = cls._normalize_match_text(word)
        return bool(normalized_word) and f" {normalized_word} " in f" {normalized_text} "


__all__ = [
    "AudioSessionNotFoundError",
    "AudioSessionService",
    "AudioSessionUnavailableError",
]
