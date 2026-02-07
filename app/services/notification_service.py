"""Service for handling Web Push notifications."""
import json
from sqlalchemy.orm import Session
from sqlalchemy import select
from pywebpush import webpush, WebPushException
from app.config import settings
from app.db.models.push_subscription import PushSubscription

class NotificationService:
    def __init__(self, db: Session):
        self.db = db

    def subscribe(self, user_id, subscription_info: dict, user_agent: str = None):
        """Register a new push subscription."""
        endpoint = subscription_info.get("endpoint")
        if not endpoint:
            raise ValueError("Endpoint required")
            
        keys = subscription_info.get("keys")
        
        # Check if exists
        stmt = select(PushSubscription).where(
            PushSubscription.user_id == user_id,
            PushSubscription.endpoint == endpoint
        )
        existing = self.db.scalars(stmt).first()
        if existing:
            existing.keys = keys
            existing.user_agent = user_agent
        else:
            sub = PushSubscription(
                user_id=user_id,
                endpoint=endpoint,
                keys=keys,
                user_agent=user_agent
            )
            self.db.add(sub)
        
        self.db.commit()

    def send_notification(self, user_id, message: str, title: str = "Language Learning"):
        """Send a push notification to all user devices."""
        if not settings.VAPID_PRIVATE_KEY:
            print("VAPID keys not configured, skipping notification.")
            return

        # Fetch all subscriptions
        stmt = select(PushSubscription).where(PushSubscription.user_id == user_id)
        subs = self.db.scalars(stmt).all()
        
        payload = json.dumps({"title": title, "body": message})
        
        for sub in subs:
            try:
                webpush(
                    subscription_info={
                        "endpoint": sub.endpoint,
                        "keys": sub.keys
                    },
                    data=payload,
                    vapid_private_key=settings.VAPID_PRIVATE_KEY,
                    vapid_claims={"sub": settings.VAPID_SUBJECT}
                )
            except WebPushException as ex:
                # 404/410 means subscription expired/unsubscribed
                if ex.response and ex.response.status_code in [404, 410]:
                    self.db.delete(sub)
                else:
                    print(f"WebPush failed for {sub.id}: {ex}")
        
        self.db.commit()
