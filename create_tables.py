from app.db.base import Base
from app.db.session import engine
from app.db.models.push_subscription import PushSubscription
from app.db.models.user import User

if __name__ == "__main__":
    print("Creating tables...")
    Base.metadata.create_all(bind=engine)
    print("Tables created.")
