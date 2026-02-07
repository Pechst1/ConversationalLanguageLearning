from sqlalchemy.orm import Session
from app.db.models.story import Story
from app.db.models.user import User
from app.services.session_service import SessionService
from app.db.models.session import LearningSession

class ArticleConversationService:
    def __init__(self, db: Session):
        self.db = db
        self.session_service = SessionService(db=db)

    def start_article_session(self, story_id: str, user: User) -> LearningSession:
        """Create a new conversational session based on an article/story."""
        story = self.db.query(Story).filter(Story.id == story_id).first()
        if not story:
            raise ValueError(f"Story with id {story_id} not found")

        # Create session with special scenario marker
        # We use 'article:{id}' as the scenario identifier to signal SessionService
        # to load the story content into the context.
        result = self.session_service.create_session(
            user=user,
            planned_duration_minutes=15,
            topic=story.title,
            conversation_style="content_discussion",
            difficulty_preference="balanced",
            scenario=f"article:{story.id}",
            anki_direction="fr_to_de", # Default, can be adjusted
            generate_greeting=True
        )
        
        return result.session
