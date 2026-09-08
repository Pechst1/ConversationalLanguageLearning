from typing import Annotated

from fastapi import APIRouter, Body, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.api import deps
from app.config import settings
from app.db.models.user import User
from app.services.notification_service import NotificationService
from app.services.pilot_events import PilotEventService

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


@router.post("/native/subscribe")
def subscribe_native(
    subscription: Annotated[dict, Body(...)],
    db: Annotated[Session, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.get_current_user)],
    user_agent: Annotated[str | None, Header()] = None,
):
    """Register the APNs token emitted by the Capacitor iOS shell."""
    service = NotificationService(db)
    try:
        service.subscribe_native(
            current_user.id,
            token=subscription.get("token", ""),
            platform=subscription.get("platform", "ios"),
            environment=subscription.get("environment")
            or ("sandbox" if settings.APNS_USE_SANDBOX else "production"),
            user_agent=user_agent,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"status": "success"}


@router.post("/test")
def test_notification(
    db: Annotated[Session, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.get_current_user)],
):
    service = NotificationService(db)
    delivered = service.send_notification(
        current_user.id,
        "Votre notification pilote est bien reliée.",
        "Feuilleton",
        data={"route": "/atelier"},
    )
    return {"status": "sent" if delivered else "not_configured", "deliveries": delivered}


@router.post("/tap", status_code=status.HTTP_204_NO_CONTENT)
def record_notification_tap(
    payload: Annotated[dict, Body(...)],
    db: Annotated[Session, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.get_current_user)],
) -> None:
    """Record engagement before the native shell follows the deep link."""
    PilotEventService(db).record(
        "notification_tap",
        user_id=current_user.id,
        entity_type="notification",
        entity_id=payload.get("notification_id"),
        payload={
            "route": str(payload.get("route") or "/atelier")[:500],
            "kind": str(payload.get("kind") or "unknown")[:80],
        },
    )
    db.commit()
