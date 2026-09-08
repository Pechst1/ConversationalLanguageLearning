"""Tests for the explainable grammar notebook API."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.core.security import decode_token
from app.db.models.atelier import AtelierConceptBlueprint
from app.db.models.error import UserError
from app.db.models.grammar import (
    GrammarConcept,
    GrammarConceptArchive,
    GrammarConceptLocalization,
    UserGrammarProgress,
)
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
    now = datetime.now(UTC)

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
    assert item["state_label"] == "En cours"
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


def test_grammar_notebook_catalog_is_curated_archives_legacy_and_localizes(
    client: TestClient, db_session, local_demo_auth
):
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

    fr_response = client.get("/api/v1/grammar/notebook", params={"locale": "fr", "limit": 100})
    assert fr_response.status_code == 200
    fr_first = next(item for item in fr_response.json() if item["external_id"] == "FR_B1_COND_001")
    assert fr_first["display_title"] == "Si + présent → futur (condition réelle)"
    assert fr_first["localized_title"] == "Si + présent → futur (condition réelle)"
    assert fr_first["localized_category"] == "Conditionnelles"
    db_session.refresh(legacy)
    assert legacy.active is False
    archive = (
        db_session.query(GrammarConceptArchive)
        .filter(GrammarConceptArchive.concept_id == legacy.id)
        .one()
    )
    assert archive.archive_reason == "not_in_focused_french_core_catalog"
    assert db_session.query(GrammarConceptLocalization).filter(GrammarConceptLocalization.locale == "de").count() >= len(items)
    assert db_session.query(GrammarConceptLocalization).filter(GrammarConceptLocalization.locale == "fr").count() >= len(items)


def test_grammar_notebook_uses_local_demo_user_without_auth(client: TestClient, local_demo_auth):
    response = client.get("/api/v1/grammar/notebook")

    assert response.status_code == 200


def test_grammar_notebook_notes_patch_does_not_record_review(client: TestClient, db_session):
    token = _token(client)
    user = _user_from_token(db_session, token)
    concept = _notebook_concept(db_session)
    next_review = datetime.now(UTC) + timedelta(days=5)
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
    assert progress.next_review.replace(tzinfo=UTC) == next_review
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


def test_grammar_summary_denominator_matches_the_notebook_index(client: TestClient, db_session) -> None:
    """Le Relevé and the Cahier index must count the same catalog.

    A legacy row stored with `language="French"` slipped past the archival sweep
    (it matched `language == "fr"` exactly), so it stayed active forever:
    /grammar/summary counted it and Le Relevé printed "N / 56" while the Cahier
    index, which filters on the catalog version, listed 54 fiches.
    """
    stray = GrammarConcept(
        external_id=f"FR_LEGACY_{uuid4().hex[:6]}",
        language="French",  # the spelling that used to escape archival
        name="Legacy partitive rule",
        level="A1",
        category="Articles",
        subskill="legacy",
        active=True,
    )
    other_language = GrammarConcept(
        external_id=f"ES_LEGACY_{uuid4().hex[:6]}",
        language="es",
        name="Spanish articles",
        level="A1",
        active=True,
    )
    db_session.add_all([stray, other_language])
    db_session.commit()

    token = _token(client)
    headers = {"Authorization": f"Bearer {token}"}
    user = _user_from_token(db_session, token)
    for concept in (stray, other_language):
        db_session.add(UserGrammarProgress(
            user_id=user.id,
            concept_id=concept.id,
            state="in_arbeit",
            next_review=datetime.now(UTC) - timedelta(days=1),
        ))
    db_session.commit()

    # The summary must also be right before the notebook initializes its catalog.
    summary = client.get("/api/v1/grammar/summary", headers=headers)
    assert summary.status_code == 200
    notebook = client.get("/api/v1/grammar/notebook?limit=500", headers=headers)
    assert notebook.status_code == 200

    body = summary.json()
    assert body["total_concepts"] == len(notebook.json())
    assert sum(body["level_counts"].values()) == body["total_concepts"]
    assert body["started"] == 0
    assert body["due_today"] == 0
    assert sum(body["state_counts"].values()) == 0
    assert body["new_available"] == body["total_concepts"]
    db_session.refresh(other_language)
    assert other_language.active is True, "other languages must be preserved"

    db_session.refresh(stray)
    assert stray.active is False


def test_notebook_notes_hide_review_provenance_and_survive_a_seance(client: TestClient, db_session) -> None:
    """`UserGrammarProgress.notes` is shared by the learner and the recorders.

    The Atelier stamps "Atelier session <uuid>" into the same column the Cahier
    reads as "Notes en marge", so the fiche printed a session UUID as the
    learner's own note and every séance silently overwrote whatever they wrote.
    """
    from app.services.grammar import GrammarService

    token = _token(client)
    headers = {"Authorization": f"Bearer {token}"}
    user = _user_from_token(db_session, token)

    concept = (
        db_session.query(GrammarConcept)
        .filter(GrammarConcept.catalog_version == FRENCH_CORE_CATALOG_VERSION)
        .order_by(GrammarConcept.id)
        .first()
    )
    assert concept is not None

    service = GrammarService(db_session)
    # A séance runs before the learner has written anything.
    service.record_review(user=user, concept_id=concept.id, score=6.0, notes=f"Atelier session {uuid4()}")

    fiche = client.get(f"/api/v1/grammar/notebook/{concept.id}", headers=headers).json()
    assert fiche["personal_notes"] is None
    assert fiche["progress"]["notes"] is None

    saved = client.patch(
        f"/api/v1/grammar/notebook/{concept.id}/notes",
        headers=headers,
        json={"notes": "Ma note perso : futur après si."},
    )
    assert saved.status_code == 200
    assert saved.json()["personal_notes"] == "Ma note perso : futur après si."

    # A later séance must not clobber it.
    service.record_review(user=user, concept_id=concept.id, score=7.0, notes=f"Atelier session {uuid4()}")
    after = client.get(f"/api/v1/grammar/notebook/{concept.id}", headers=headers).json()
    assert after["personal_notes"] == "Ma note perso : futur après si."


def test_notebook_rows_carry_french_titles_in_every_locale(client: TestClient) -> None:
    """The Cahier index speaks French whatever the instructional locale is."""
    token = _token(client)
    headers = {"Authorization": f"Bearer {token}"}

    for locale in ("en", "fr"):
        rows = client.get(f"/api/v1/grammar/notebook?locale={locale}&limit=500", headers=headers)
        assert rows.status_code == 200
        payload = rows.json()
        assert payload
        assert all(row["title_fr"] for row in payload), locale
        assert all(row["category_label_fr"] for row in payload), locale
