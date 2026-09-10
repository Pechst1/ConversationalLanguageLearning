"""WP-30 — «Le journal de bord»: the API.

Authenticated with the existing ``get_current_user`` dependency; no new token
path, no bypass. Every route answers the same envelope, so the Cahier tab
renders one state machine rather than five.

The load-bearing rule of this router is what it *omits*: while an entry is being
written, the response carries :class:`JournalCueView` — who, where, how long ago
— and no scene text at all. :class:`JournalRevealView` is attached only once
``entry_text`` exists on the row. The two are separate models rather than one
model with nullable fields, so "the reveal leaked into the prompt" is a type
error rather than a review comment.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.db.models.journal import JournalEntry
from app.db.models.user import User
from app.services.journal import (
    ENTRY_MAX_CHARS,
    FOLLOWUP_MAX_CHARS,
    FOLLOWUP_OFFSET_DAYS,
    JOURNAL_VERSION,
    MIN_ENTRY_WORDS,
    RECALL_OFFSET_DAYS,
    JournalService,
)

router = APIRouter(prefix="/journal", tags=["journal"])


class JournalCueView(BaseModel):
    """What the learner sees *before* writing.

    There is no ``setup_fr``, no ``character_line_fr`` and no ``title_fr`` here,
    and there must never be: free recall with the scene on screen is copying.
    """

    character_name: str | None = None
    location_name: str | None = None
    scene_date: str | None = None
    days_ago: int | None = None


class JournalRevealView(BaseModel):
    """The scene as it was. Attached only after the learner has written."""

    title_fr: str | None = None
    setup_fr: str | None = None
    character_line_fr: str | None = None
    callback_fr: str | None = None


class JournalCorrectionView(BaseModel):
    """One correction in the foreground; the rest on demand."""

    assessment_status: str = "unavailable"
    assessment_truncated: bool = False
    verdict: str | None = None
    corrected_answer: str = ""
    explanation_language: str | None = None
    foreground: dict | None = None
    errata: list[dict] = Field(default_factory=list)


class JournalEntryView(BaseModel):
    id: str
    status: str
    scene_date: str
    offered_on: str
    followup_due_on: str
    cue: JournalCueView
    prompt_fr: str
    entry_text: str | None = None
    correction: JournalCorrectionView | None = None
    #: The content half, deliberately not folded into the correction.
    content_recall: dict | None = None
    reaction_fr: str | None = None
    reveal: JournalRevealView | None = None
    vocabulary_credit: dict | None = None
    errata_recorded: int = 0


class JournalFollowupView(BaseModel):
    entry_id: str
    prompt_fr: str
    due_on: str
    answered: bool = False
    text: str | None = None
    signal: str | None = None


class JournalEnvelope(BaseModel):
    """One shape for every journal route."""

    version: str = JOURNAL_VERSION
    #: 'none' | 'offered' | 'written' | 'unavailable' | 'skipped'
    status: str
    entry: JournalEntryView | None = None
    followup: JournalFollowupView | None = None
    recall_offset_days: int = RECALL_OFFSET_DAYS
    followup_offset_days: int = FOLLOWUP_OFFSET_DAYS
    min_entry_words: int = MIN_ENTRY_WORDS


class WriteRequest(BaseModel):
    text: str = Field(default="", max_length=ENTRY_MAX_CHARS * 4)


class FollowupRequest(BaseModel):
    text: str = Field(default="", max_length=FOLLOWUP_MAX_CHARS * 4)


#: The brief, in French. It names the length and says the scene is hidden, so a
#: learner is never guessing at what the empty field wants.
ENTRY_PROMPT_FR = (
    "De mémoire, sans relire la scène : que s’est-il passé ? Deux à quatre "
    "phrases, en français."
)


def _entry_view(entry: JournalEntry) -> JournalEntryView:
    written = bool(entry.entry_text)
    return JournalEntryView(
        id=str(entry.id),
        status=str(entry.status),
        scene_date=entry.scene_date.isoformat(),
        offered_on=entry.offered_on.isoformat(),
        followup_due_on=entry.followup_due_on.isoformat(),
        cue=JournalCueView(**dict(entry.cue or {})),
        prompt_fr=ENTRY_PROMPT_FR,
        entry_text=entry.entry_text,
        # Everything below exists only once the learner has written. Guarding on
        # the stored text rather than on the status keeps a failed correction
        # from hiding the learner's own paragraph back from them.
        correction=(
            JournalCorrectionView(**{
                key: value
                for key, value in dict(entry.correction or {}).items()
                if key in JournalCorrectionView.model_fields
            })
            if written
            else None
        ),
        content_recall=dict(entry.content_recall or {}) or None if written else None,
        reaction_fr=entry.reaction_fr if written else None,
        reveal=JournalRevealView(**dict(entry.scene_reveal or {})) if written else None,
        vocabulary_credit=dict(entry.vocabulary_credit or {}) or None if written else None,
        errata_recorded=len(entry.errata_ids or []) if written else 0,
    )


def _followup_view(entry: JournalEntry) -> JournalFollowupView:
    return JournalFollowupView(
        entry_id=str(entry.id),
        prompt_fr=str(entry.followup_prompt_fr or ""),
        due_on=entry.followup_due_on.isoformat(),
        answered=entry.followup_answered_at is not None,
        text=entry.followup_text,
        signal=entry.followup_signal,
    )


def _envelope(
    db: Session, user: User, entry: JournalEntry | None
) -> JournalEnvelope:
    service = JournalService(db)
    followup = service.followup_due(user)
    return JournalEnvelope(
        status=str(entry.status) if entry is not None else "none",
        entry=_entry_view(entry) if entry is not None else None,
        followup=_followup_view(followup) if followup is not None else None,
    )


def _load(db: Session, user: User, entry_id: uuid.UUID) -> JournalEntry:
    entry = (
        db.query(JournalEntry)
        .filter(JournalEntry.id == entry_id, JournalEntry.user_id == user.id)
        .first()
    )
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Entrée introuvable"
        )
    return entry


@router.get("/state", response_model=JournalEnvelope)
def read_state(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JournalEnvelope:
    """What the journal should show today.

    Creating the offer on a GET is deliberate and safe: it is idempotent, writes
    no learner content, and the alternative — a client that has to POST before
    it can render — turns an empty tab into a mutation.
    """
    entry = JournalService(db).offer(current_user)
    return _envelope(db, current_user, entry)


@router.get("/entries", response_model=list[JournalEntryView])
def list_entries(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[JournalEntryView]:
    """The learner's own writing, newest first. Their journal, not a report."""
    rows = (
        db.query(JournalEntry)
        .filter(
            JournalEntry.user_id == current_user.id,
            JournalEntry.entry_text.isnot(None),
        )
        .order_by(JournalEntry.scene_date.desc())
        .limit(max(1, min(int(limit), 100)))
        .all()
    )
    return [_entry_view(row) for row in rows]


@router.post("/{entry_id}/write", response_model=JournalEnvelope)
def write_entry(
    entry_id: uuid.UUID,
    payload: WriteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JournalEnvelope:
    """Store the recap, correct it, and reveal the scene.

    Replaying it is a no-op: the entry already carries text, so no second paid
    correction is bought and the stored verdict stands.
    """
    entry = _load(db, current_user, entry_id)
    if entry.status == "offered" and not str(payload.text or "").strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Écrivez d’abord quelques phrases.",
        )
    entry = JournalService(db).write(current_user, entry, text=payload.text)
    return _envelope(db, current_user, entry)


@router.post("/{entry_id}/skip", response_model=JournalEnvelope)
def skip_entry(
    entry_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JournalEnvelope:
    """The learner declined this scene. Asked once, then let go."""
    entry = _load(db, current_user, entry_id)
    entry = JournalService(db).skip(entry)
    return _envelope(db, current_user, entry)


@router.post("/{entry_id}/followup", response_model=JournalEnvelope)
def answer_followup(
    entry_id: uuid.UUID,
    payload: FollowupRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JournalEnvelope:
    """One line, a week later. Its answer is the ``used_again_later`` signal."""
    entry = _load(db, current_user, entry_id)
    if not str(payload.text or "").strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Une phrase suffit.",
        )
    JournalService(db).answer_followup(current_user, entry, text=payload.text)
    return _envelope(db, current_user, JournalService(db).offer(current_user))
