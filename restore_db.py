
from app.db.base import Base
from app.db.session import engine

# Import all models to register them with Base.metadata
from app.db.models.user import User
from app.db.models.story import Story, Chapter, Scene, StoryProgress
from app.db.models.npc import NPC
from app.db.models.vocabulary import VocabularyWord
from app.db.models.progress import UserVocabularyProgress
from app.db.models.grammar import GrammarConcept, UserGrammarProgress
from app.db.models.error import UserError
from app.db.models.session import LearningSession
from app.db.models.achievement import Achievement, UserAchievement
# from app.db.models.analytics import ... (if relevant)

if __name__ == "__main__":
    print("Recreating missing tables...")
    Base.metadata.create_all(bind=engine)
    print("Tables created.")
