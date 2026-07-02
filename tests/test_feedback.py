"""Tests for the global pilot feedback channel."""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models.feedback import UserFeedbackReport
from app.db.models.user import User
from tests.test_users import register_and_login

ROOT = Path(__file__).resolve().parents[1]


def test_feedback_submit_requires_authentication(client: TestClient) -> None:
    response = client.post(
        "/api/v1/feedback/reports",
        json={"category": "bug", "route": "/atelier"},
    )

    assert response.status_code == 401


def test_feedback_submit_persists_current_user_context(client: TestClient, db_session) -> None:
    token = register_and_login(client, "feedback@example.com", "verysecure")

    response = client.post(
        "/api/v1/feedback/reports",
        json={
            "category": "layout",
            "message": "The bottom action felt too close to the nav.",
            "route": "/atelier",
            "url": "http://127.0.0.1:3001/atelier",
            "screen": "Atelier",
            "viewport": {"width": 390, "height": 844},
            "user_agent": "pytest",
            "context_payload": {"pathname": "/atelier", "asPath": "/atelier"},
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["category"] == "layout"
    assert data["route"] == "/atelier"
    assert data["viewport"]["width"] == 390

    report = db_session.scalar(select(UserFeedbackReport).where(UserFeedbackReport.id == uuid.UUID(data["id"])))
    user = db_session.scalar(select(User).where(User.email == "feedback@example.com"))
    assert report is not None
    assert report.user_id == user.id
    assert report.message == "The bottom action felt too close to the nav."


def test_feedback_submit_rejects_invalid_category_and_long_note(client: TestClient) -> None:
    token = register_and_login(client, "feedback-validation@example.com", "verysecure")
    headers = {"Authorization": f"Bearer {token}"}

    invalid_category = client.post(
        "/api/v1/feedback/reports",
        json={"category": "complaint", "route": "/atelier"},
        headers=headers,
    )
    assert invalid_category.status_code == 422

    long_note = client.post(
        "/api/v1/feedback/reports",
        json={"category": "bug", "route": "/atelier", "message": "x" * 1001},
        headers=headers,
    )
    assert long_note.status_code == 422


def test_feedback_admin_list_requires_admin(client: TestClient, db_session) -> None:
    user_token = register_and_login(client, "feedback-user@example.com", "verysecure")

    create_response = client.post(
        "/api/v1/feedback/reports",
        json={"category": "bug", "route": "/atelier"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert create_response.status_code == 201

    forbidden_response = client.get(
        "/api/v1/feedback/reports",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert forbidden_response.status_code == 403

    admin_token = register_and_login(client, "feedback-admin@example.com", "verysecure")
    admin = db_session.scalar(select(User).where(User.email == "feedback-admin@example.com"))
    admin.role = "admin"
    db_session.add(admin)
    db_session.commit()

    list_response = client.get(
        "/api/v1/feedback/reports",
        params={"category": "bug", "route": "/atelier"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
    assert list_response.json()[0]["category"] == "bug"


def test_feedback_frontend_contract_is_wired() -> None:
    layout = (ROOT / "web-frontend/components/layout/Layout.tsx").read_text()
    api = (ROOT / "web-frontend/services/api.ts").read_text()

    assert "FeedbackWidget" in layout
    assert "status === 'authenticated'" in layout
    assert "submitFeedbackReport" in api
    assert "/feedback/reports" in api
