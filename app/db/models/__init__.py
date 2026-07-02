"""Database models package."""
from app.db.models.achievement import Achievement, UserAchievement
from app.db.models.analytics import AnalyticsSnapshot
from app.db.models.anki_import_record import AnkiImportRecord
from app.db.models.atelier import (
    AtelierAttempt,
    AtelierCollectible,
    AtelierConceptBlueprint,
    AtelierExerciseSet,
    AtelierGenerationEvent,
    AtelierLanguagePack,
    AtelierSession,
)
from app.db.models.cefr import UserCEFRProgressHistory
from app.db.models.error import UserError, UserErrorConcept
from app.db.models.feedback import UserFeedbackReport
from app.db.models.grammar import (
    GrammarConcept,
    GrammarConceptArchive,
    GrammarConceptLocalization,
    UserGrammarProgress,
)
from app.db.models.graphic_novel import (
    GraphicNovelAttempt,
    GraphicNovelPanel,
    GraphicNovelScene,
    PersonalInputItem,
)
from app.db.models.library import BookEpisode, UserBook
from app.db.models.mission import RealWorldMission, RealWorldMissionAttempt, RealWorldMissionTurn
from app.db.models.npc import NPC, NPCMemory, NPCRelationship
from app.db.models.progress import ReviewLog, UserVocabularyProgress
from app.db.models.push_subscription import PushSubscription
from app.db.models.scenario import UserScenarioState
from app.db.models.serial import SerialEpisode, SerialThread
from app.db.models.session import (
    ConversationMessage,
    LearningSession,
    SessionLearningMoment,
    WordInteraction,
)
from app.db.models.story import Chapter, Scene, Story, StoryProgress
from app.db.models.user import RefreshToken, User
from app.db.models.vocabulary import UserConjugationProgress, VerbConjugation, VocabularyWord

__all__ = [
    "User",
    "RefreshToken",
    "VocabularyWord",
    "VerbConjugation",
    "UserConjugationProgress",
    "UserVocabularyProgress",
    "ReviewLog",
    "LearningSession",
    "ConversationMessage",
    "WordInteraction",
    "SessionLearningMoment",
    "Achievement",
    "UserAchievement",
    "AtelierAttempt",
    "AtelierCollectible",
    "AtelierConceptBlueprint",
    "AtelierExerciseSet",
    "AtelierGenerationEvent",
    "AtelierLanguagePack",
    "AtelierSession",
    "RealWorldMission",
    "RealWorldMissionAttempt",
    "RealWorldMissionTurn",
    "BookEpisode",
    "UserBook",
    "SerialEpisode",
    "SerialThread",
    "GraphicNovelAttempt",
    "GraphicNovelPanel",
    "GraphicNovelScene",
    "PersonalInputItem",
    "AnalyticsSnapshot",
    "AnkiImportRecord",
    "UserError",
    "UserErrorConcept",
    "UserScenarioState",
    "GrammarConcept",
    "GrammarConceptArchive",
    "GrammarConceptLocalization",
    "UserGrammarProgress",
    "UserCEFRProgressHistory",
    # Story RPG models
    "Story",
    "Chapter",
    "Scene",
    "StoryProgress",
    "NPC",
    "NPCRelationship",
    "NPCMemory",
    "UserFeedbackReport",
    "PushSubscription",
]
