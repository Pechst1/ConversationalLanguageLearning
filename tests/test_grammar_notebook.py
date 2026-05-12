"""Tests for the explainable grammar notebook API."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.core.security import decode_token
from app.db.models.error import UserError
from app.db.models.atelier import AtelierConceptBlueprint
from app.db.models.grammar import GrammarConcept, GrammarConceptArchive, GrammarConceptLocalization, UserGrammarProgress
from app.db.models.user import User
from app.services.atelier_assets import AtelierAssetService
from app.services.grammar_catalog import FRENCH_CORE_CATALOG_VERSION, FrenchCoreGrammarCatalog


def _token(client: TestClient) -> str:
    email = f"{uuid4()}@example.com"
    password = "notebook-secure"
    client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "target_language": "fr",
            "native_language": "en",
        },
    )
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return response.json()["access_token"]


def _user_from_token(db_session, token: str) -> User:
    payload = decode_token(token)
    return db_session.get(User, UUID(payload["sub"]))


def _notebook_concept(db_session) -> GrammarConcept:
    FrenchCoreGrammarCatalog(db_session).ensure_catalog(archive_legacy=True)
    return db_session.query(GrammarConcept).filter(GrammarConcept.external_id == "FR_B1_COND_001").one()


def test_grammar_notebook_list_and_detail_include_blueprint_progress_and_errata(client: TestClient, db_session):
    token = _token(client)
    user = _user_from_token(db_session, token)
    concept = _notebook_concept(db_session)
    now = datetime.now(timezone.utc)

    progress = UserGrammarProgress(
        user_id=user.id,
        concept_id=concept.id,
        score=6.0,
        reps=2,
        state="in_arbeit",
        notes="Watch the result clause.",
        last_review=now - timedelta(days=2),
        next_review=now + timedelta(days=3),
    )
    due_error = UserError(
        user_id=user.id,
        concept_id=concept.id,
        error_category="grammar",
        display_label="Future result",
        task_error_type="future_result",
        original_text="Si elle appelle, je repondrais",
        correction="Si elle appelle, je repondrai",
        why_wrong="You used conditional where the result needs future simple.",
        repair_hint="Keep si + present, then use future simple.",
        source_type="atelier",
        review_mode="grammar",
        next_review_date=now - timedelta(days=1),
        occurrences=2,
        state="review",
    )
    recent_error = UserError(
        user_id=user.id,
        concept_id=concept.id,
        error_category="grammar",
        display_label="Si frame",
        task_error_type="si_clause_frame",
        original_text="Quand il arrivera, on commencera.",
        correction="S'il arrive, on commencera.",
        why_wrong="You changed the requested si frame.",
        repair_hint="Keep the si trigger in the source frame.",
        source_type="atelier",
        review_mode="grammar",
        next_review_date=now + timedelta(days=4),
        occurrences=1,
        state="learning",
    )
    db_session.add_all([progress, due_error, recent_error])
    db_session.commit()

    list_response = client.get(
        "/api/v1/grammar/notebook",
        params={"q": "si type 1", "limit": 20},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_response.status_code == 200
    items = list_response.json()
    item = next(row for row in items if row["id"] == concept.id)
    assert item["mastery"] == 6.0
    assert item["state_label"] == "In Arbeit"
    assert item["due_errata_count"] == 1
    assert item["recent_errata_count"] == 1
    assert item["motif"]["style"] == "atelier_bauhaus_v1"
    assert item["display_title"]
    assert item["catalog_version"] == FRENCH_CORE_CATALOG_VERSION
    assert item["source_refs"]["source_codes"]
    assert item["blueprint_status"] == "approved"
    assert item["blueprint_quality"]["valid"] is True

    detail_response = client.get(
        f"/api/v1/grammar/notebook/{concept.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["atelier_blueprint"]["pedagogy"]["core_rule"]
    assert "required context" not in detail["atelier_blueprint"]["pedagogy"]["core_rule"].lower()
    assert detail["atelier_blueprint"]["sentence_xray"]["sentence"]
    assert detail["atelier_blueprint"]["sentence_xray"]["explanation"]
    assert len(detail["atelier_blueprint"]["sentence_xray"]["marks"]) >= 2
    assert detail["personal_notes"] == "Watch the result clause."
    assert detail["due_errata"][0]["display_label"] == "Future result"
    assert detail["recent_errata"][0]["display_label"] == "Si frame"


def test_grammar_notebook_catalog_is_curated_archives_legacy_and_localizes(client: TestClient, db_session):
    legacy = GrammarConcept(
        external_id="FR_C2_LEGACY_001",
        language="fr",
        name="Legacy micro topic",
        level="C2",
        category="Style",
        active=True,
    )
    db_session.add(legacy)
    db_session.commit()

    response = client.get("/api/v1/grammar/notebook", params={"locale": "de", "limit": 100})

    assert response.status_code == 200
    items = response.json()
    assert 50 <= len(items) <= 56
    assert all(item["level"] != "C2" for item in items)
    assert all(item["catalog_version"] == FRENCH_CORE_CATALOG_VERSION for item in items)
    first = next(item for item in items if item["external_id"] == "FR_B1_COND_001")
    assert first["display_title"] == "Si-Satz Typ 1: Präsens und Futur"
    assert first["localized_title"] == "Si-Satz Typ 1: Präsens und Futur"
    db_session.refresh(legacy)
    assert legacy.active is False
    archive = (
        db_session.query(GrammarConceptArchive)
        .filter(GrammarConceptArchive.concept_id == legacy.id)
        .one()
    )
    assert archive.archive_reason == "not_in_focused_french_core_catalog"
    assert db_session.query(GrammarConceptLocalization).filter(GrammarConceptLocalization.locale == "de").count() >= len(items)


def test_grammar_notebook_uses_local_demo_user_without_auth(client: TestClient):
    response = client.get("/api/v1/grammar/notebook")

    assert response.status_code == 200


def test_grammar_notebook_notes_patch_does_not_record_review(client: TestClient, db_session):
    token = _token(client)
    user = _user_from_token(db_session, token)
    concept = _notebook_concept(db_session)
    next_review = datetime.now(timezone.utc) + timedelta(days=5)
    progress = UserGrammarProgress(
        user_id=user.id,
        concept_id=concept.id,
        score=4.0,
        reps=3,
        state="in_arbeit",
        next_review=next_review,
    )
    db_session.add(progress)
    db_session.commit()

    response = client.patch(
        f"/api/v1/grammar/notebook/{concept.id}/notes",
        json={"notes": "Future after si is wrong."},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    db_session.refresh(progress)
    assert progress.notes == "Future after si is wrong."
    assert progress.reps == 3
    assert progress.next_review.replace(tzinfo=timezone.utc) == next_review
    assert response.json()["personal_notes"] == "Future after si is wrong."


def test_grammar_notebook_notes_patch_creates_progress_without_review(client: TestClient, db_session):
    token = _token(client)
    user = _user_from_token(db_session, token)
    concept = _notebook_concept(db_session)

    response = client.patch(
        f"/api/v1/grammar/notebook/{concept.id}/notes",
        json={"notes": "My own example: Si je peux, je viendrai."},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    progress = (
        db_session.query(UserGrammarProgress)
        .filter(UserGrammarProgress.user_id == user.id, UserGrammarProgress.concept_id == concept.id)
        .one()
    )
    assert progress.notes == "My own example: Si je peux, je viendrai."
    assert progress.reps == 0
    assert progress.next_review is None


def test_atelier_blueprint_quality_gate_rejects_placeholder_payload(db_session):
    service = AtelierAssetService(db_session)
    payload = {
        "display_title": "Generic",
        "pedagogy": {
            "core_rule": "Use Generic in the required context.",
            "when_to_use": "Use it when the sentence context asks for this grammar relation rather than a neighboring contrast.",
            "pattern": "Generic",
            "main_traps": [],
            "micro_examples": [],
            "contrast_rules": ["No contrast note yet."],
        },
        "sentence_xray": {
            "sentence": "Generic",
            "explanation": "marks the grammar relation to practice",
            "marks": [{"token": "Generic", "role": "target", "explanation": "marks the grammar relation to practice"}],
        },
        "visual_motif": {
            "style": "atelier_bauhaus_v1",
            "concept_metaphor": "target grammar relation",
            "primitives": [
                {"type": "rect", "role": "source", "x": 0, "y": 0, "w": 10, "h": 10},
            ],
        },
        "exercise_recipe": {},
        "correction_rubric": {"why_templates": ["The learner is wrong."]},
        "detection_hints": {},
    }

    quality = service.blueprint_quality(payload)

    assert quality["valid"] is False
    assert service.validate_blueprint_payload(payload) is False


def test_generated_blueprint_has_specific_content_and_unique_motif(db_session):
    first = GrammarConcept(
        external_id=f"FR_C1_AGR_{uuid4().hex[:6]}",
        language="fr",
        name="Häufige Kongruenzfallen",
        level="C1",
        category="Allgemein",
        subskill="agreement_traps",
        active=True,
    )
    second = GrammarConcept(
        external_id=f"FR_C1_NEG_{uuid4().hex[:6]}",
        language="fr",
        name="Negation erweitert: ne... point; ne... guère",
        level="C1",
        category="Satzbau",
        subskill="advanced_negation",
        active=True,
    )
    db_session.add_all([first, second])
    db_session.commit()
    db_session.refresh(first)
    db_session.refresh(second)
    service = AtelierAssetService(db_session)

    first_payload = service.ensure_concept_blueprint(first).payload
    second_payload = service.ensure_concept_blueprint(second).payload

    assert first_payload["display_title"] == "Common agreement traps"
    assert first_payload["pedagogy"]["micro_examples"]
    assert len(first_payload["pedagogy"]["main_traps"]) >= 2
    assert len(first_payload["sentence_xray"]["marks"]) >= 2
    assert first_payload["visual_motif"]["signature"] != second_payload["visual_motif"]["signature"]
    assert db_session.query(AtelierConceptBlueprint).filter(AtelierConceptBlueprint.concept_id == first.id).count() == 1
