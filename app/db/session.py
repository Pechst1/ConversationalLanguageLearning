"""Database session and engine management."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Yield a database session for request lifecycle."""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
