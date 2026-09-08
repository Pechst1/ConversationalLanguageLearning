
from app.db.base import Base

# Import all models to register them with Base.metadata
from app.db.session import engine

# from app.db.models.analytics import ... (if relevant)

if __name__ == "__main__":
    print("Recreating missing tables...")
    Base.metadata.create_all(bind=engine)
    print("Tables created.")
