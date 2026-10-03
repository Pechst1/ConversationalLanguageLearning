"""WP-122 A: La Radio — the week's Papier as a bulletin (``app/services/revue/radio.py``).

* ``GET  /revue/radio/week`` — the rotation: the next unheard bulletin, the queue, the chip.
* ``GET  /revue/radio/{dossier_id}?band=`` — the bulletin, spoken for the caller (clips
  cached in ``line_audio_clips``; a replay makes no call), with its stage and dictée.
* ``POST /revue/radio/{dossier_id}/dictee`` — the dictée, graded by the journey's grader.
* ``POST /revue/radio/{dossier_id}/heard`` — «C'est entendu»: the rotation moves on.

Gate: a plain 404 while ``REVUE_ENABLED`` or ``REVUE_RADIO_ENABLED`` is off, checked
before authentication (as every Revue router does).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.config import settings
from app.core.rate_limit import paid_route_guard
from app.db.models.user import User
from app.schemas.revue_radio import (
    RadioBulletinView,
    RadioDictee,
    RadioDicteeRequest,
    RadioDicteeResult,
    RadioHeardRequest,
    RadioItem,
    RadioLine,
    RadioStage,
    RadioWeekView,
)
from app.services.revue import knowledge, radio
from app.services.revue.dossier import EditorialDossier


def require_radio_enabled() -> None:
    if not (getattr(settings, "REVUE_ENABLED", False) and getattr(settings, "REVUE_RADIO_ENABLED", False)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")


router = APIRouter(
    prefix="/revue/radio",
    tags=["revue"],
    # The flag check first (404 while off), then the paid-route guard: the bulletin GET pays for TTS.
    dependencies=[Depends(require_radio_enabled), Depends(paid_route_guard(get_current_user))],
)


def _item(dossier: EditorialDossier) -> RadioItem:
    return RadioItem(dossier_id=dossier.id, title_fr=dossier.title_fr, topic=dossier.topic, evergreen=dossier.evergreen)


def _dossier_or_404(dossier_id: str) -> EditorialDossier:
    dossier = radio.find_dossier(dossier_id)
    if dossier is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="revue_radio_dossier_not_found")
    return dossier


def _speaker_name(speaker: str) -> str:
    try:
        return knowledge.cast_name(speaker)
    except Exception:  # noqa: BLE001 - a name is a label, never a failure
        return speaker.split("_")[0].capitalize()


def _stage(db: Session, dossier: EditorialDossier) -> RadioStage:
    try:
        from app.services.revue.encounter import stage_for

        stage = stage_for(dossier, db=db)
        return RadioStage(plate_url=stage.plate_url, place_fr=stage.place_fr)
    except Exception:  # noqa: BLE001 - the plate is decoration; the bulletin plays without it
        return RadioStage(plate_url=None, place_fr=dossier.places[0].name_fr)


@router.get("/week", response_model=RadioWeekView)
def read_radio_week(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RadioWeekView:
    rotation = radio.radio_week(db, current_user.id)
    seconds = None
    if rotation.current is not None:
        script = radio.bulletin_script(rotation.current, radio.learner_band(current_user), week=rotation.week)
        seconds = int(5 * round(script.seconds / 5))
    return RadioWeekView(
        week=rotation.week,
        current=_item(rotation.current) if rotation.current is not None else None,
        queue=[_item(dossier) for dossier in rotation.queue],
        heard=rotation.heard,
        heard_today=rotation.heard_today,
        chip=rotation.chip,
        seconds=seconds,
    )


@router.get("/{dossier_id}", response_model=RadioBulletinView)
def read_bulletin(
    dossier_id: str,
    band: str | None = Query(default=None, max_length=8),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RadioBulletinView:
    dossier = _dossier_or_404(dossier_id)
    bulletin = radio.bulletin_for(db, dossier, band or radio.learner_band(current_user), owner_id=current_user.id)
    if bulletin.synthesized_lines or bulletin.cached_lines:
        db.commit()
    dictee = bulletin.dictee
    return RadioBulletinView(
        dossier_id=bulletin.dossier_id,
        title_fr=bulletin.title_fr,
        topic=bulletin.topic,
        band=bulletin.band,
        week=bulletin.week,
        seconds=bulletin.seconds,
        audio=bulletin.audio,  # type: ignore[arg-type]
        guest_id=bulletin.guest_id,
        lines=[
            RadioLine(
                index=line.index,
                speaker=line.speaker,
                speaker_name=_speaker_name(line.speaker),
                role=line.role,  # type: ignore[arg-type]
                text_fr=line.text_fr,
                clip_url=line.clip_url if bulletin.audio == "ready" else None,
                claim_id=line.claim_id,
            )
            for line in bulletin.lines
        ],
        dictee=RadioDictee(line_index=dictee.index, words=len(dictee.text_fr.split())),
        stage=_stage(db, dossier),
    )


@router.post("/{dossier_id}/dictee", response_model=RadioDicteeResult)
def grade_dictee(
    dossier_id: str,
    payload: RadioDicteeRequest,
    current_user: User = Depends(get_current_user),
) -> RadioDicteeResult:
    from app.services.chrome_language import user_chrome_language

    dossier = _dossier_or_404(dossier_id)
    script = radio.bulletin_script(dossier, payload.band or radio.learner_band(current_user))
    grade = radio.grade_dictee(script.dictee.text_fr, payload.text, language=user_chrome_language(current_user))
    return RadioDicteeResult(outcome=grade.outcome, expected_fr=grade.expected_fr, note=grade.note)  # type: ignore[arg-type]


@router.post("/{dossier_id}/heard", response_model=RadioWeekView)
def mark_heard(
    dossier_id: str,
    payload: RadioHeardRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RadioWeekView:
    dossier = _dossier_or_404(dossier_id)
    week = radio.current_week()
    radio.mark_heard(
        db,
        current_user.id,
        dossier,
        band=payload.band or radio.learner_band(current_user),
        week=week,
        dictee_outcome=payload.dictee,
    )
    db.commit()
    return read_radio_week(current_user=current_user, db=db)
