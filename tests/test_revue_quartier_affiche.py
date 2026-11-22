# ruff: noqa: F811 - fixtures are imported by name and requested as arguments
"""``REVUE_QUARTIER_AFFICHE_ENABLED``: today's edition for the Quartier's Morris column.

``GET /revue/week`` carries ``affiche`` (the story's headline in our French and whether the
period's Papier is filed) only while the switch is on; ``None`` when there is no edition.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.v1.endpoints.revue import affiche_of
from app.config import settings
from app.schemas.revue import RvOffer, RvWeek
from app.services.revue.evergreen import evergreens_for_week
from tests.test_revue_kiosk import (  # noqa: F401 - fixtures
    WEEK,
    api,
    db,
    evergreens,
    login,
    revue_tables,
)


def _week(client: TestClient, headers: dict[str, str]) -> dict:
    response = client.get("/api/v1/revue/week", headers=headers, params={"week": WEEK})
    assert response.status_code == 200, response.text
    return response.json()


def test_switch_off_the_week_carries_no_poster(api: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "REVUE_ENABLED", True)
    monkeypatch.setattr(settings, "REVUE_QUARTIER_AFFICHE_ENABLED", False)
    headers, _ = login(api)
    assert _week(api, headers).get("affiche") is None


def test_the_poster_is_the_recommendation_then_the_paper_in_hand_then_read(api: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "REVUE_ENABLED", True)
    monkeypatch.setattr(settings, "REVUE_QUARTIER_AFFICHE_ENABLED", True)
    headers, _ = login(api)
    week = _week(api, headers)
    recommended = week["recommended"]
    poster = week["affiche"]
    assert poster == {
        "dossier_id": recommended["dossier_id"],
        "headline_fr": (recommended.get("headline_fr") or recommended["title_fr"]).strip(),
        "done": False,
    }
    dossier = evergreens_for_week(WEEK)[0]
    started = api.post("/api/v1/revue/sessions", headers=headers, json={"week": WEEK, "dossier_id": dossier.id})
    assert started.status_code == 201, started.text
    poster = _week(api, headers)["affiche"]
    assert poster["dossier_id"] == dossier.id and poster["done"] is False and poster["headline_fr"]
    closed = api.post(f"/api/v1/revue/sessions/{started.json()['id']}/close", headers=headers)
    assert closed.status_code == 200, closed.text
    poster = _week(api, headers)["affiche"]
    assert poster["dossier_id"] == dossier.id and poster["done"] is True


def test_no_edition_no_poster() -> None:
    offer = RvOffer(
        week=RvWeek(iso=WEEK, label="Semaine 40", range=""),
        recommended=None,
        recommended_reason="first",
        alternatives=[],
        evergreen_only=True,
    )
    assert affiche_of(offer) is None
