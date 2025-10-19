"""Shared API dependencies."""
from sqlalchemy.orm import Session

from app.db.session import SessionLocal


def get_db() -> Session:
    """Yield a database session for request lifetime."""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
