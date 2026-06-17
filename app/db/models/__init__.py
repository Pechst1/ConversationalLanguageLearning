"""Database models package."""
from app.db.models.user import RefreshToken, User
from app.db.models.vocabulary import VocabularyWord
from app.db.models.progress import UserVocabularyProgress, ReviewLog
from app.db.models.session import (
    LearningSession,
    ConversationMessage,
    WordInteraction,
    SessionLearningMoment,
)
from app.db.models.achievement import Achievement, UserAchievement
from app.db.models.atelier import (
    AtelierAttempt,
    AtelierConceptBlueprint,
    AtelierExerciseSet,
    AtelierLanguagePack,
    AtelierSession,
)
from app.db.models.mission import RealWorldMission, RealWorldMissionAttempt, RealWorldMissionTurn
from app.db.models.serial import SerialEpisode, SerialThread
from app.db.models.graphic_novel import (
    GraphicNovelAttempt,
    GraphicNovelPanel,
    GraphicNovelScene,
    PersonalInputItem,
)
from app.db.models.analytics import AnalyticsSnapshot
from app.db.models.anki_import_record import AnkiImportRecord
from app.db.models.error import UserError, UserErrorConcept
from app.db.models.scenario import UserScenarioState
from app.db.models.grammar import GrammarConcept, GrammarConceptArchive, GrammarConceptLocalization, UserGrammarProgress
from app.db.models.cefr import UserCEFRProgressHistory
from app.db.models.story import Story, Chapter, Scene, StoryProgress
from app.db.models.npc import NPC, NPCRelationship, NPCMemory

__all__ = [
    "User",
    "RefreshToken",
    "VocabularyWord",
    "UserVocabularyProgress",
    "ReviewLog",
    "LearningSession",
    "ConversationMessage",
    "WordInteraction",
    "SessionLearningMoment",
    "Achievement",
    "UserAchievement",
    "AtelierAttempt",
    "AtelierConceptBlueprint",
    "AtelierExerciseSet",
    "AtelierLanguagePack",
    "AtelierSession",
    "RealWorldMission",
    "RealWorldMissionAttempt",
    "RealWorldMissionTurn",
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
]
