from typing import Annotated

from fastapi import APIRouter, Body, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.api import deps
from app.config import settings
from app.db.models.user import User
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/vapid-public-key")
def get_vapid_public_key():
    if not settings.VAPID_PUBLIC_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Push notifications are not configured.",
        )
    return {"publicKey": settings.VAPID_PUBLIC_KEY}


@router.post("/subscribe")
def subscribe(
    subscription: Annotated[dict, Body(...)],
    db: Annotated[Session, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.get_current_user)],
    user_agent: Annotated[str | None, Header()] = None,
):
    service = NotificationService(db)
    try:
        service.subscribe(current_user.id, subscription, user_agent)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"status": "success"}


@router.post("/test")
def test_notification(
    db: Annotated[Session, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.get_current_user)],
):
    service = NotificationService(db)
    service.send_notification(current_user.id, "This is a test notification from your Language App!", "Success!")
    return {"status": "sent"}
