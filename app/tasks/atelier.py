"""Celery tasks for Atelier quality guardrails."""
from __future__ import annotations

from loguru import logger

from app.celery_app import celery_app
from app.db.session import SessionLocal
from app.services.atelier import ATELIER_GENERATOR_VERSION
from app.services.atelier_audit import audit_atelier_word_banks


@celery_app.task(name="app.tasks.atelier.audit_atelier_word_banks")
def audit_atelier_word_bank_payloads(generator_version: str | None = None) -> dict[str, object]:
    """Audit generated word-bank payloads and alert through structured logs."""

    db = SessionLocal()
    version = generator_version or ATELIER_GENERATOR_VERSION
    try:
        flagged = audit_atelier_word_banks(db, generator_version=version)
        if flagged:
            logger.error(
                "Atelier word-bank audit found invalid generated items",
                generator_version=version,
                flagged_count=len(flagged),
                sample=flagged[:20],
            )
        else:
            logger.info("Atelier word-bank audit passed", generator_version=version)
        return {
            "generator_version": version,
            "flagged_count": len(flagged),
            "flagged": flagged[:50],
        }
    finally:
        db.close()


__all__ = ["audit_atelier_word_bank_payloads"]
