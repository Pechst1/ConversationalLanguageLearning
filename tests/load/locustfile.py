"""Locust scenarios exercising conversational flows under load."""
from __future__ import annotations

import random
import string
import uuid

from locust import FastHttpUser, between, task


def _random_email() -> str:
    token = uuid.uuid4().hex[:10]
    return f"load-{token}@example.com"


def _random_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(random.choice(alphabet) for _ in range(length))


class LearnerUser(FastHttpUser):
    """Simulate a learner completing conversational sessions."""

    wait_time = between(1, 3)

    def on_start(self) -> None:
        self.email = _random_email()
        self.password = _random_password()
        self.token: str | None = None
        self.session_id: str | None = None
        self._register()
        self._login()
        self._create_session()

    def _headers(self) -> dict[str, str]:
        if not self.token:
            return {}
        return {"Authorization": f"Bearer {self.token}"}

    def _register(self) -> None:
        payload = {
            "email": self.email,
            "password": self.password,
            "native_language": "en",
            "target_language": "fr",
            "proficiency_level": "B1",
        }
        self.client.post("/api/v1/auth/register", json=payload, name="auth:register")

    def _login(self) -> None:
        payload = {"email": self.email, "password": self.password}
        response = self.client.post("/api/v1/auth/login", json=payload, name="auth:login")
        if response.ok:
            self.token = response.json().get("access_token")

    def _create_session(self) -> None:
        payload = {"planned_duration_minutes": random.choice([10, 15, 20])}
        response = self.client.post(
            "/api/v1/sessions",
            json=payload,
            headers=self._headers(),
            name="sessions:create",
        )
        if response.ok:
            self.session_id = response.json()["session"]["id"]

    @task(3)
    def send_message(self) -> None:
        if not self.session_id:
            return
        payload = {
            "content": random.choice(
                [
                    "Bonjour, je voudrais pratiquer mon français aujourd'hui",
                    "J'aime cuisiner des plats français le weekend",
                    "Je me prépare pour un voyage à Paris bientôt",
                ]
            )
        }
        self.client.post(
            f"/api/v1/sessions/{self.session_id}/messages",
            json=payload,
            headers=self._headers(),
            name="sessions:message",
        )

    @task(1)
    def fetch_summary(self) -> None:
        if not self.session_id:
            return
        self.client.get(
            f"/api/v1/sessions/{self.session_id}/summary",
            headers=self._headers(),
            name="sessions:summary",
        )

    @task(1)
    def fetch_analytics(self) -> None:
        self.client.get(
            "/api/v1/analytics/summary",
            headers=self._headers(),
            name="analytics:summary",
        )
