"""Regression tests for the Atelier practice system."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.core.error_detection.rules import DetectedError
from app.core.security import decode_token
from app.db.models.atelier import AtelierAttempt, AtelierConceptBlueprint, AtelierLanguagePack, AtelierSession
from app.db.models.error import UserError, UserErrorConcept
from app.db.models.grammar import GrammarConcept, UserGrammarProgress
from app.db.models.progress import UserVocabularyProgress
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services.error_memory import ErrorMemoryService
from app.services.atelier import AtelierCorrectionService, AtelierExerciseGenerator, AtelierSRSService, AtelierScheduler
from app.services.atelier_assets import AtelierAssetService
from app.services.llm_service import LLMResult


def _user(db_session) -> User:
    user = User(
        id=uuid4(),
        email=f"{uuid4()}@example.com",
        hashed_password="test",
        target_language="fr",
    )
    db_session.add(user)
    db_session.commit()
    return user


def _concept(db_session, external_id: str) -> GrammarConcept:
    AtelierScheduler(db_session).ensure_catalog()
    return db_session.query(GrammarConcept).filter(GrammarConcept.external_id == external_id).one()


def _token(client: TestClient) -> str:
    email = f"{uuid4()}@example.com"
    password = "atelier-secure"
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


class _FakeLLMService:
    def __init__(self, content: dict):
        self.content = content
        self.calls: list[dict] = []

    def generate_chat_completion(self, messages, **kwargs):
        self.calls.append({"method": "generate_chat_completion", "messages": messages, **kwargs})
        return self._result()

    def generate_error_detection(self, messages, **kwargs):
        self.calls.append({"method": "generate_error_detection", "messages": messages, **kwargs})
        return self._result(model="gpt-4o")

    def _result(self, model: str = "gpt-4o-mini") -> LLMResult:
        return LLMResult(
            provider="openai",
            model=model,
            content=json.dumps(self.content),
            prompt_tokens=10,
            completion_tokens=10,
            total_tokens=20,
            cost=0.0,
            raw_response={},
        )


def test_generator_creates_three_recognize_modes_and_three_transform_items(db_session):
    concept = _concept(db_session, "FR_B1_COND_001")

    payload = AtelierExerciseGenerator(db_session).get_or_create(concept).payload

    assert set(payload["recognize"]) == {"fill", "word_bank", "classify"}
    assert all(len(mode["items"]) == 3 for mode in payload["recognize"].values())
    assert len(payload["transform"]["items"]) == 3
    assert payload["produce"]["requirements"][0]["target_count"] == 2
    assert set(payload["output_ladder"]) == {"sentence", "speak", "conversation"}
    assert payload["output_ladder"]["sentence"]["items"][0]["type"] == "short_sentence"
    assert payload["output_ladder"]["speak"]["items"][0]["type"] == "spoken_response"
    assert payload["output_ladder"]["conversation"]["items"][0]["type"] == "conversation_turn"
    first_bank = payload["recognize"]["word_bank"]["items"][0]
    assert first_bank["tokens"] != first_bank["answer_tokens"]
    assert first_bank["correct_answer"] == "Si elle appelle, je repondrai"


def test_atelier_asset_service_creates_language_pack_and_blueprint(db_session):
    concept = _concept(db_session, "FR_B1_COND_001")
    asset_service = AtelierAssetService(db_session)

    language_pack = asset_service.ensure_language_pack("fr")
    blueprint = asset_service.ensure_concept_blueprint(concept)

    assert isinstance(language_pack, AtelierLanguagePack)
    assert isinstance(blueprint, AtelierConceptBlueprint)
    assert language_pack.payload["correction_style"]["address"] == "you"
    assert blueprint.review_status == "approved"
    assert asset_service.validate_blueprint_payload(blueprint.payload)
    assert blueprint.payload["pedagogy"]["pattern"] == "si + present -> future simple / imperative"
    assert blueprint.payload["visual_motif"]["style"] == "atelier_bauhaus_v1"
    assert blueprint.payload["visual_motif"]["primitives"][0]["role"] == "condition"
    assert "the learner" not in json.dumps(blueprint.payload["correction_rubric"]["why_templates"]).lower()


def test_atelier_today_returns_blueprint_payload(client: TestClient):
    token = _token(client)
    response = client.get("/api/v1/atelier/today", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    concept = response.json()["concepts"][0]
    blueprint = concept["atelier_blueprint"]
    assert blueprint["visual_motif"]["style"] == "atelier_bauhaus_v1"
    assert blueprint["exercise_recipe"]["recognize"]["word_bank"]["subitems"] == 3
    assert blueprint["correction_rubric"]["tone"]["address"] == "you"


def test_start_session_with_preferred_concept_keeps_full_atelier_set(client: TestClient, db_session):
    token = _token(client)
    AtelierScheduler(db_session).ensure_catalog()
    concept = db_session.query(GrammarConcept).filter(GrammarConcept.external_id == "FR_A2_NEG_001").one()

    response = client.post(
        "/api/v1/atelier/sessions",
        json={"preferred_concept_id": concept.id},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["concepts"][0]["id"] == concept.id
    assert len(payload["concepts"]) == 3


def test_atelier_blueprint_template_works_for_non_french_concept(db_session):
    concept = GrammarConcept(
        external_id="ES_A1_ART_001",
        language="es",
        name="Definite articles el/la/los/las",
        level="A1",
        category="Articles",
        subskill="definite_articles",
        core_rule="Use el, la, los, or las according to noun gender and number.",
        main_traps="using el with feminine nouns; forgetting plural agreement",
        anchor_examples="el libro | la mesa | los amigos",
        exercise_tags=["articles", "gender", "number"],
        is_foundation=True,
        active=True,
    )
    db_session.add(concept)
    db_session.commit()
    db_session.refresh(concept)

    asset_service = AtelierAssetService(db_session)
    asset_service.ensure_language_pack("es")
    blueprint = asset_service.ensure_concept_blueprint(concept)

    assert blueprint.language == "es"
    assert blueprint.payload["concept_external_id"] == "ES_A1_ART_001"
    assert blueprint.payload["visual_motif"]["style"] == "atelier_bauhaus_v1"
    assert blueprint.payload["exercise_recipe"]["output_ladder"]["conversation_turn"]["subitems"] == 1


def test_output_ladder_counts_non_tense_concept_from_metadata(db_session):
    concept = GrammarConcept(
        external_id=f"FR_B1_REL_{uuid4().hex[:8]}",
        language="fr",
        name="Relative pronouns: qui, que, dont",
        level="B1",
        category="Pronouns",
        subskill="relative_clauses",
        core_rule="Use qui, que, ou, or dont according to the role inside the relative clause.",
        main_traps="using que where dont is needed after a de-complement",
        anchor_examples="Le dossier dont je parle reste ici.",
        exercise_tags=["relative_pronoun", "dont", "de_complement"],
        active=True,
    )
    db_session.add(concept)
    db_session.commit()
    item = AtelierExerciseGenerator(db_session)._output_item(
        "relative-output",
        "short_sentence",
        "Write one sentence with the target relation.",
        "Mention a file without repeating le dossier.",
        "Le dossier dont je parle reste ici.",
        concept,
        1,
        min_words=5,
        max_words=24,
    )

    correction = AtelierCorrectionService(db_session).correct(
        concept=concept,
        round_name="sentence",
        mode="short_sentence",
        exercise_id="relative-output",
        prompt_payload={"items": [item]},
        answer_payload={"text": "Le dossier dont je parle reste sur la table."},
    )

    assert correction["verdict"] == "accepted"
    assert correction["missing_targets"] == []
    assert correction["concept_hits"][0]["detected_count"] >= 1


def test_word_bank_accepts_natural_comma_spacing(db_session):
    concept = _concept(db_session, "FR_B1_COND_001")
    payload = AtelierExerciseGenerator(db_session)._fallback_payload(concept)
    items = payload["recognize"]["word_bank"]["items"]

    correction = AtelierCorrectionService(db_session).correct(
        concept=concept,
        round_name="recognize",
        mode="word_bank",
        exercise_id="FR_B1_COND_001:word_bank",
        prompt_payload={"items": items},
        answer_payload={
            "answers": {
                "si-bank-1": "Si elle appelle, je repondrai",
                "si-bank-2": "Si tu as faim, mange",
                "si-bank-3": "Si nous partons maintenant, nous arriverons tot",
            }
        },
    )

    assert correction["verdict"] == "correct"
    assert correction["errata"] == []


def test_word_bank_reports_specific_si_type_errors(db_session):
    concept = _concept(db_session, "FR_B1_COND_001")
    payload = AtelierExerciseGenerator(db_session)._fallback_payload(concept)
    items = payload["recognize"]["word_bank"]["items"]

    correction = AtelierCorrectionService(db_session).correct(
        concept=concept,
        round_name="recognize",
        mode="word_bank",
        exercise_id="FR_B1_COND_001:word_bank",
        prompt_payload={"items": items},
        answer_payload={
            "answers": {
                "si-bank-1": "Si elle appelle, je repondrai",
                "si-bank-2": "Si tu as faim, mange",
                "si-bank-3": "Si nous partons maintenat, nous arrivons tot",
            }
        },
    )

    assert correction["verdict"] == "partial"
    assert len(correction["errata"]) == 1
    erratum = correction["errata"][0]
    assert erratum["display_label"] == "Future result + spelling"
    assert "arrivons" in erratum["why_wrong"]
    assert "maintenat" in erratum["why_wrong"]


def test_word_bank_explains_conditional_instead_of_future(db_session):
    concept = _concept(db_session, "FR_B1_COND_001")
    payload = AtelierExerciseGenerator(db_session)._fallback_payload(concept)
    items = payload["recognize"]["word_bank"]["items"]

    correction = AtelierCorrectionService(db_session).correct(
        concept=concept,
        round_name="recognize",
        mode="word_bank",
        exercise_id="FR_B1_COND_001:word_bank",
        prompt_payload={"items": [items[0]]},
        answer_payload={"answers": {"si-bank-1": "Si elle appelle, je repondrais"}},
    )

    erratum = correction["errata"][0]
    assert erratum["display_label"] == "Conditional vs future"
    assert "conditional" in erratum["why_wrong"]
    assert "repondrai" in erratum["repair_hint"]


def test_word_bank_explains_future_inside_si_clause(db_session):
    concept = _concept(db_session, "FR_B1_COND_001")
    payload = AtelierExerciseGenerator(db_session)._fallback_payload(concept)
    items = payload["recognize"]["word_bank"]["items"]

    correction = AtelierCorrectionService(db_session).correct(
        concept=concept,
        round_name="recognize",
        mode="word_bank",
        exercise_id="FR_B1_COND_001:word_bank",
        prompt_payload={"items": [items[2]]},
        answer_payload={"answers": {"si-bank-3": "si nous arriverons maintenant, nous partons tot"}},
    )

    erratum = correction["errata"][0]
    assert erratum["display_label"] == "Future placed after si"
    assert "future `arriverons` inside the si-clause" in erratum["why_wrong"]
    assert "Si nous partons maintenant, nous arriverons tot" in erratum["repair_hint"]


def test_fill_mode_reports_specific_si_type_feedback(db_session):
    concept = _concept(db_session, "FR_B1_COND_001")
    payload = AtelierExerciseGenerator(db_session)._fallback_payload(concept)
    items = payload["recognize"]["fill"]["items"]

    correction = AtelierCorrectionService(db_session).correct(
        concept=concept,
        round_name="recognize",
        mode="fill",
        exercise_id="FR_B1_COND_001:fill",
        prompt_payload={"items": items},
        answer_payload={
            "answers": {
                "si-fill-1": "appelle",
                "si-fill-2": "prends",
                "si-fill-3": "irons",
            }
        },
    )

    assert correction["verdict"] == "partial"
    assert len(correction["errata"]) == 1
    erratum = correction["errata"][0]
    assert erratum["display_label"] == "Target form needed"
    assert "future simple" in erratum["why_wrong"]
    assert "the learner" not in erratum["why_wrong"].lower()


def test_classify_mode_reports_specific_feedback(db_session):
    concept = _concept(db_session, "FR_B1_COND_001")
    payload = AtelierExerciseGenerator(db_session)._fallback_payload(concept)
    items = payload["recognize"]["classify"]["items"]

    correction = AtelierCorrectionService(db_session).correct(
        concept=concept,
        round_name="recognize",
        mode="classify",
        exercise_id="FR_B1_COND_001:classify",
        prompt_payload={"items": items},
        answer_payload={
            "answers": {
                "si-classify-1": "present",
                "si-classify-2": "future",
                "si-classify-3": "future",
            }
        },
    )

    assert correction["verdict"] == "partial"
    assert len(correction["errata"]) == 1
    erratum = correction["errata"][0]
    assert erratum["display_label"] == "Form classification"
    assert "imperative command" in erratum["why_wrong"]
    assert "the learner" not in erratum["why_wrong"].lower()


def test_generator_uses_strict_structured_output_when_llm_available(db_session):
    concept = _concept(db_session, "FR_B1_COND_001")
    payload = AtelierExerciseGenerator(db_session)._fallback_payload(concept)
    payload.pop("concept", None)
    fake_llm = _FakeLLMService(payload)

    exercise_set = AtelierExerciseGenerator(db_session, llm_service=fake_llm).get_or_create(concept)

    assert exercise_set.source == "llm"
    assert exercise_set.model == "gpt-4o-mini"
    assert fake_llm.calls[0]["response_format"]["type"] == "json_schema"
    assert fake_llm.calls[0]["response_format"]["json_schema"]["strict"] is True
    assert len(exercise_set.payload["recognize"]["word_bank"]["items"]) == 3


def test_transform_correction_uses_structured_llm_output(db_session):
    concept = _concept(db_session, "FR_B1_COND_001")
    payload = AtelierExerciseGenerator(db_session).get_or_create(concept).payload
    fake_llm = _FakeLLMService(
        {
            "verdict": "incorrect",
            "score_0_4": 1,
            "corrected_answer": "",
            "corrected_answers": [
                {"item_id": "si-transform-1", "corrected_answer": "S'il arrive, on commencera le diner."}
            ],
            "concept_hits": [
                {
                    "external_id": "FR_B1_COND_001",
                    "label": concept.name,
                    "detected_count": 0,
                    "target_count": 1,
                }
            ],
            "missing_targets": [],
            "errata": [
                {
                    "display_label": "Si clause frame",
                    "learner_text": "Quand il arrivera, on commencera le diner.",
                    "corrected_target": "S'il arrive, on commencera le diner.",
                    "why_wrong": "The learner changed the requested si frame into quand.",
                    "repair_hint": "The learner should keep si, use present in the condition, and put future in the result.",
                    "severity": 3,
                    "recurring": True,
                    "task_error_type": "si_present_result_form",
                    "external_id": "FR_B1_COND_001",
                }
            ],
        }
    )

    result = AtelierCorrectionService(db_session, llm_service=fake_llm).correct(
        concept=concept,
        round_name="transform",
        mode="rewrite",
        exercise_id="si-transform",
        prompt_payload=payload["transform"],
        answer_payload={"answers": {"si-transform-1": "Quand il arrivera, on commencera le diner."}},
    )

    assert result["corrected_answer"]["si-transform-1"].startswith("S'il arrive")
    assert result["errata"][0]["concept_id"] == concept.id
    assert "si frame" in result["errata"][0]["why_wrong"]
    assert "the learner" not in result["errata"][0]["why_wrong"].lower()
    assert result["errata"][0]["why_wrong"].startswith("You")
    assert result["errata"][0]["repair_hint"].startswith("You")
    assert result["correction_debug"]["model"] == "gpt-4o"
    assert result["correction_debug"]["prompt_version"].startswith("atelier-correction")
    assert fake_llm.calls[0]["method"] == "generate_error_detection"
    assert fake_llm.calls[0]["response_format"]["json_schema"]["strict"] is True


def test_si_rewrite_stays_in_si_frame_and_not_quand(db_session):
    concept = _concept(db_session, "FR_B1_COND_001")
    payload = AtelierExerciseGenerator(db_session).get_or_create(concept).payload

    result = AtelierCorrectionService(db_session).correct(
        concept=concept,
        round_name="transform",
        mode="rewrite",
        exercise_id="si-transform",
        prompt_payload=payload["transform"],
        answer_payload={"answers": {"si-transform-1": "Quand il arrivera, on commencera le diner."}},
    )

    assert result["verdict"] != "correct"
    assert result["corrected_answer"]["si-transform-1"].startswith("S'il arrive")
    assert "si" in result["errata"][0]["repair_hint"].lower()


def test_negation_correction_names_article_change(db_session):
    concept = _concept(db_session, "FR_A2_NEG_001")
    payload = AtelierExerciseGenerator(db_session).get_or_create(concept).payload

    result = AtelierCorrectionService(db_session).correct(
        concept=concept,
        round_name="transform",
        mode="rewrite",
        exercise_id="neg-transform",
        prompt_payload=payload["transform"],
        answer_payload={"answers": {"neg-transform-1": "Je ne bois pas du cafe et je ne mange pas une pomme."}},
    )

    erratum = result["errata"][0]
    assert "quantity" in erratum["why_wrong"].lower()
    assert "de/d'" in erratum["repair_hint"]


def test_produce_accepts_submission_with_missing_targets(db_session):
    user = _user(db_session)
    concepts = [_concept(db_session, "FR_B1_COND_001"), _concept(db_session, "FR_B1_TENSE_001"), _concept(db_session, "FR_A2_NEG_001")]
    session = AtelierSession(user_id=user.id, selected_concept_ids=[concept.id for concept in concepts])
    db_session.add(session)
    db_session.commit()

    result = AtelierCorrectionService(db_session).correct(
        concept=None,
        round_name="produce",
        mode="integrated_writing",
        exercise_id="integrated-writing",
        prompt_payload={},
        answer_payload={"text": "Je vais regarder la course a Barcelone avec des amis."},
        session=session,
    )

    assert result["verdict"] == "accepted"
    assert result["missing_targets"]
    assert all(erratum["task_error_type"] == "task_compliance" for erratum in result["errata"])


def test_output_ladder_short_sentence_scores_active_use(db_session):
    concept = _concept(db_session, "FR_B1_COND_001")
    payload = AtelierExerciseGenerator(db_session)._fallback_payload(concept)
    prompt_payload = {"round": "sentence", "mode": "sentence", **payload["output_ladder"]["sentence"]}

    result = AtelierCorrectionService(db_session).correct(
        concept=concept,
        round_name="sentence",
        mode="sentence",
        exercise_id="FR_B1_COND_001:sentence",
        prompt_payload=prompt_payload,
        answer_payload={"text": "Si je finis tot, je t'appellerai."},
    )

    assert result["verdict"] == "accepted"
    assert result["score_0_4"] >= 3
    assert result["concept_hits"][0]["detected_count"] == 1
    assert result["errata"] == []


def test_output_ladder_missing_target_is_not_recurring_erratum(db_session):
    concept = _concept(db_session, "FR_B1_COND_001")
    payload = AtelierExerciseGenerator(db_session)._fallback_payload(concept)
    prompt_payload = {"round": "conversation", "mode": "conversation", **payload["output_ladder"]["conversation"]}

    result = AtelierCorrectionService(db_session).correct(
        concept=concept,
        round_name="conversation",
        mode="conversation",
        exercise_id="FR_B1_COND_001:conversation",
        prompt_payload=prompt_payload,
        answer_payload={"text": "On attend au cafe."},
    )

    assert result["verdict"] == "partial"
    assert result["missing_targets"][0]["missing_count"] == 1
    assert result["errata"][0]["task_error_type"] == "task_compliance"
    assert result["errata"][0]["recurring"] is False


def test_complete_session_schedules_recurring_errata_and_updates_progress(db_session):
    user = _user(db_session)
    concept = _concept(db_session, "FR_B1_COND_001")
    session = AtelierSession(user_id=user.id, selected_concept_ids=[concept.id])
    db_session.add(session)
    db_session.commit()

    AtelierCorrectionService(db_session).submit_attempt(
        session=session,
        user=user,
        concept=concept,
        round_name="transform",
        mode="rewrite",
        exercise_id="si-transform",
        answer_payload={"answers": {"si-transform-1": "Quand il arrivera, on commencera le diner."}},
    )

    recap = AtelierSRSService(db_session).complete_session(session=session, user=user)

    assert recap["errata_logged"] == 1
    assert db_session.query(UserError).filter(UserError.user_id == user.id).count() == 1
    assert db_session.query(UserGrammarProgress).filter(UserGrammarProgress.user_id == user.id, UserGrammarProgress.concept_id == concept.id).count() == 1


def test_atelier_attempt_persists_error_memory_before_completion(db_session):
    user = _user(db_session)
    concept = _concept(db_session, "FR_B1_COND_001")
    session = AtelierSession(user_id=user.id, selected_concept_ids=[concept.id])
    db_session.add(session)
    db_session.commit()

    attempt = AtelierCorrectionService(db_session).submit_attempt(
        session=session,
        user=user,
        concept=concept,
        round_name="recognize",
        mode="fill",
        exercise_id="FR_B1_COND_001:fill",
        answer_payload={"answers": {"si-fill-1": "appelle", "si-fill-2": "prends", "si-fill-3": "irons"}},
    )

    error = db_session.query(UserError).filter(UserError.user_id == user.id).one()
    assert error.source_type == "atelier"
    assert error.review_mode == "grammar"
    assert error.source_attempt_id == attempt.id
    assert error.memory_key
    assert attempt.correction_payload["memory_updates"][0]["id"] == str(error.id)
    assert attempt.correction_payload["errata"][0]["id"] == str(error.id)


def test_multiple_errata_can_share_one_error_concept_memory(db_session):
    user = _user(db_session)
    concept = _concept(db_session, "FR_B1_COND_001")
    session = AtelierSession(user_id=user.id, selected_concept_ids=[concept.id])
    db_session.add(session)
    db_session.commit()

    attempt = AtelierCorrectionService(db_session).submit_attempt(
        session=session,
        user=user,
        concept=concept,
        round_name="recognize",
        mode="fill",
        exercise_id="FR_B1_COND_001:fill",
        answer_payload={
            "answers": {
                "si-fill-1": "appelle",
                "si-fill-2": "mangeras",
                "si-fill-3": "irons",
            }
        },
    )

    assert len(attempt.correction_payload["memory_updates"]) == 2
    assert db_session.query(UserError).filter(UserError.user_id == user.id).count() == 2
    concept_memories = db_session.query(UserErrorConcept).filter(UserErrorConcept.user_id == user.id).all()
    assert len(concept_memories) == 1
    assert concept_memories[0].total_occurrences == 2


def test_due_errata_pulls_linked_concept_into_atelier_selection(db_session):
    user = _user(db_session)
    concept = _concept(db_session, "FR_A2_NEG_001")
    db_session.add(
        UserError(
            user_id=user.id,
            concept_id=concept.id,
            error_category="grammar",
            error_pattern="pronoun_choice",
            display_label="Pronoun choice",
            task_error_type="pronoun_choice",
            original_text="en",
            correction="la",
            why_wrong="You used the wrong pronoun.",
            repair_hint="Choose the pronoun that matches the object.",
            next_review_date=datetime.now(timezone.utc) - timedelta(days=1),
            state="new",
            lapses=2,
            occurrences=3,
        )
    )
    db_session.commit()

    selected = AtelierScheduler(db_session).select_today(user)

    assert selected[0].concept.id == concept.id


def test_lexical_errata_are_persisted_as_vocabulary_errors(db_session):
    user = _user(db_session)
    concept = _concept(db_session, "FR_B1_COND_001")
    session = AtelierSession(user_id=user.id, selected_concept_ids=[concept.id])
    db_session.add(session)
    db_session.commit()
    attempt = AtelierAttempt(
        atelier_session_id=session.id,
        user_id=user.id,
        concept_id=concept.id,
        round="produce",
        mode="integrated_writing",
        exercise_id="integrated-writing",
        correction_payload={
            "errata": [
                {
                    "display_label": "Vocabulary choice",
                    "learner_text": "tu me maintiens",
                    "corrected_target": "tu me soutiendras",
                    "why_wrong": "You chose the wrong verb for the intended meaning.",
                    "repair_hint": "Use soutenir when the intended meaning is support or take care of someone.",
                    "severity": 3,
                    "recurring": True,
                    "task_error_type": "lexical_choice",
                    "concept_id": concept.id,
                    "external_id": concept.external_id,
                }
            ]
        },
        verdict="incorrect",
        score_0_4=1,
    )
    db_session.add(attempt)
    db_session.commit()

    recap = AtelierSRSService(db_session).complete_session(session=session, user=user)
    error = db_session.query(UserError).filter(UserError.user_id == user.id).one()

    assert recap["errata_logged"] == 1
    assert error.error_category == "vocabulary"
    assert error.next_review_date is not None
    word = db_session.query(VocabularyWord).filter(VocabularyWord.normalized_word == "soutenir").one()
    progress = db_session.query(UserVocabularyProgress).filter(
        UserVocabularyProgress.user_id == user.id,
        UserVocabularyProgress.word_id == word.id,
    ).one()
    assert progress.state == "relearning"
    assert progress.next_review_date is not None


def test_error_memory_records_conversation_lexical_error_and_links_vocabulary(db_session):
    user = _user(db_session)
    update = ErrorMemoryService(db_session).record_detected_error(
        user=user,
        source_type="conversation",
        detected_error=DetectedError(
            code="lexical_choice",
            message="You used maintenir, but the intended meaning is to support someone.",
            span="tu me maintiens",
            suggestion="tu me soutiens",
            category="vocabulary",
            severity="high",
            confidence=0.92,
            subcategory="lexical_choice",
        ),
        source_payload={"mode": "chat"},
    )
    db_session.commit()

    assert update
    error = db_session.query(UserError).filter(UserError.user_id == user.id).one()
    assert error.source_type == "conversation"
    assert error.review_mode == "vocabulary"
    assert error.linked_word_id is not None
    word = db_session.get(VocabularyWord, error.linked_word_id)
    assert word.normalized_word == "soutenir"
    progress = db_session.query(UserVocabularyProgress).filter(
        UserVocabularyProgress.user_id == user.id,
        UserVocabularyProgress.word_id == word.id,
    ).one()
    assert progress.state == "relearning"


def test_error_memory_repeats_same_pattern_without_duplicate_rows(db_session):
    user = _user(db_session)
    service = ErrorMemoryService(db_session)
    error = DetectedError(
        code="pronoun_choice",
        message="You used en for a direct object that needs la.",
        span="en",
        suggestion="la",
        category="grammar",
        severity="medium",
        confidence=0.9,
        subcategory="pronoun_choice",
    )

    first = service.record_detected_error(user=user, source_type="story", detected_error=error)
    second = service.record_detected_error(user=user, source_type="audio", detected_error=error)
    db_session.commit()

    assert first["action"] == "created"
    assert second["action"] == "repeated"
    row = db_session.query(UserError).filter(UserError.user_id == user.id).one()
    assert row.occurrences == 2
    assert row.lapses == 1


def test_atelier_api_today_session_attempt_and_complete(client: TestClient):
    token = _token(client)
    headers = {"Authorization": f"Bearer {token}"}

    today = client.get("/api/v1/atelier/today", headers=headers)
    assert today.status_code == 200
    assert len(today.json()["concepts"]) == 3

    started = client.post("/api/v1/atelier/sessions", headers=headers, json={})
    assert started.status_code == 201
    data = started.json()
    session_id = data["session_id"]
    concept = data["concepts"][0]
    exercise_set = next(item for item in data["exercise_sets"] if item["concept_id"] == concept["id"])
    fill_items = exercise_set["payload"]["recognize"]["fill"]["items"]

    attempt = client.post(
        f"/api/v1/atelier/sessions/{session_id}/attempts",
        headers=headers,
        json={
            "concept_id": concept["id"],
            "round": "recognize",
            "mode": "fill",
            "exercise_id": f"{concept['external_id']}:fill",
            "answer_payload": {
                "answers": {item["id"]: item["correct_answer"] for item in fill_items}
            },
        },
    )
    assert attempt.status_code == 200
    assert attempt.json()["verdict"] == "correct"
    duplicate = client.post(
        f"/api/v1/atelier/sessions/{session_id}/attempts",
        headers=headers,
        json={
            "concept_id": concept["id"],
            "round": "recognize",
            "mode": "fill",
            "exercise_id": f"{concept['external_id']}:fill",
            "answer_payload": {
                "answers": {item["id"]: item["correct_answer"] for item in fill_items}
            },
        },
    )
    assert duplicate.status_code == 409

    active = client.get("/api/v1/atelier/sessions/active", headers=headers)
    assert active.status_code == 200
    active_session = active.json()["session"]
    assert active_session["session_id"] == session_id
    assert active_session["submitted_map"][f"recognize:fill:{concept['id']}"] is True
    assert active_session["attempts"][0]["round"] == "recognize"

    read_session = client.get(f"/api/v1/atelier/sessions/{session_id}", headers=headers)
    assert read_session.status_code == 200
    assert read_session.json()["current_position"]["round"] == "recognize"

    writing = client.post(
        f"/api/v1/atelier/sessions/{session_id}/attempts",
        headers=headers,
        json={
            "concept_id": None,
            "round": "produce",
            "mode": "integrated_writing",
            "exercise_id": "integrated-writing",
            "answer_payload": {"text": "Si je vais a Barcelone, je regarderai la course."},
        },
    )
    assert writing.status_code == 200
    assert writing.json()["verdict"] == "accepted"

    completed = client.post(f"/api/v1/atelier/sessions/{session_id}/complete", headers=headers)
    assert completed.status_code == 200
    assert "streak_after" in completed.json()["recap"]


def test_atelier_today_includes_due_errata_and_review_endpoint(client: TestClient, db_session):
    token = _token(client)
    headers = {"Authorization": f"Bearer {token}"}
    user_id = decode_token(token)["sub"]
    user = db_session.get(User, UUID(user_id))
    concept = _concept(db_session, "FR_A2_NEG_001")
    erratum = UserError(
        user_id=user.id,
        concept_id=concept.id,
        error_category="grammar",
        error_pattern="pronoun_choice",
        display_label="Pronoun choice",
        task_error_type="pronoun_choice",
        original_text="en",
        correction="la",
        why_wrong="You used en for a direct object that needs la.",
        repair_hint="Use la when the pronoun replaces a specific feminine direct object.",
        next_review_date=datetime.now(timezone.utc) - timedelta(days=1),
        state="new",
        lapses=1,
        occurrences=2,
    )
    db_session.add(erratum)
    db_session.commit()

    today = client.get("/api/v1/atelier/today", headers=headers)
    assert today.status_code == 200
    payload = today.json()
    assert payload["due_errata"]
    selected = next(item for item in payload["concepts"] if item["id"] == concept.id)
    assert selected["due_errata"][0]["display_label"] == "Pronoun choice"

    task = client.get(f"/api/v1/atelier/errata/{erratum.id}/task", headers=headers)
    assert task.status_code == 200
    assert task.json()["task"]["target_answer"] == "la"
    assert task.json()["task"]["display_label"] == "Pronoun choice"

    wrong_attempt = client.post(
        f"/api/v1/atelier/errata/{erratum.id}/attempt",
        headers=headers,
        json={"answer_text": "en"},
    )
    assert wrong_attempt.status_code == 200
    wrong_payload = wrong_attempt.json()
    assert wrong_payload["verdict"] == "needs_repair"
    assert wrong_payload["is_correct"] is False
    assert wrong_payload["erratum"]["state"] == "relearning"
    assert wrong_payload["erratum"]["metadata"]["review_attempts"][0]["answer_text"] == "en"

    repaired_attempt = client.post(
        f"/api/v1/atelier/errata/{erratum.id}/attempt",
        headers=headers,
        json={"answer_text": "la"},
    )
    assert repaired_attempt.status_code == 200
    repaired_payload = repaired_attempt.json()
    assert repaired_payload["verdict"] == "repaired"
    assert repaired_payload["is_correct"] is True
    assert repaired_payload["erratum"]["state"] == "review"
    assert len(repaired_payload["erratum"]["metadata"]["review_attempts"]) == 2
