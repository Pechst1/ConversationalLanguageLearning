from fastapi import APIRouter, Depends, Body, Header
from sqlalchemy.orm import Session
from app.api import deps
from app.services.notification_service import NotificationService
from app.config import settings
from app.db.models.user import User

router = APIRouter(prefix="/notifications", tags=["notifications"])

@router.get("/vapid-public-key")
def get_vapid_public_key():
    return {"publicKey": settings.VAPID_PUBLIC_KEY}

@router.post("/subscribe")
def subscribe(
    subscription: dict = Body(...),
    user_agent: str | None = Header(default=None),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    service = NotificationService(db)
    service.subscribe(current_user.id, subscription, user_agent)
    return {"status": "success"}

@router.post("/test")
def test_notification(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    service = NotificationService(db)
    service.send_notification(current_user.id, "This is a test notification from your Language App!", "Success!")
    return {"status": "sent"}
