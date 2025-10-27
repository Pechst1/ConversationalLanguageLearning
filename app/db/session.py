"""Database session and engine management."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
from loguru import logger

from app.config import settings

# Improved engine configuration with better connection pooling
engine = create_engine(
    str(settings.DATABASE_URL),
    pool_pre_ping=True,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,  # Recycle connections after 1 hour
    echo=settings.DEBUG if hasattr(settings, 'DEBUG') else False,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,  # Keep objects usable after commit
)


def get_db():
    """Yield a database session for request lifecycle."""
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def get_db_context():
    """Get database session as context manager."""
    return SessionLocal()