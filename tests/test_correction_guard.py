"""#133: a Courrier correction keeps the learner's question and lists every change it makes.

Live walk 2026-10-14: «Qu est-ce que c est, jeudi a dix-huit heures ?» came back as
«C'est jeudi à dix-huit heures ?» (another question) with two of its changes
(«a → à», «Qu est-ce que → Qu'est-ce que») unlisted.
"""

from __future__ import annotations

import json
from uuid import uuid4

import pytest

from app.db.models.mission import RealWorldMission
from app.db.models.user import User
from app.services.llm_service import LLMResult
from app.services.missions import MissionCorrectionService

LEARNER = (
    "Salut Margaux ! Je ne vends pas le appartement. Camille a une clé aussi, c est bizarre. "
    "Qu est-ce que c est, jeudi a dix-huit heures ? Mercredi je visite avec Lila. Bisous, Vincent"
)
# What the live model returned: the question rewritten, two changes unlisted.
MODEL_REWRITE = (
    "Salut Margaux ! Je ne vends pas l'appartement. Camille a une clé aussi, c'est bizarre. "
    "C'est jeudi à dix-huit heures ? Mercredi je visite avec Lila. Bisous, Vincent"
)
EXPECTED = (
    "Salut Margaux ! Je ne vends pas l'appartement. Camille a une clé aussi, c'est bizarre. "
    "Qu'est-ce que c'est, jeudi à dix-huit heures ? Mercredi je visite avec Lila. Bisous, Vincent"
)


def _mission() -> RealWorldMission:
    return RealWorldMission(
        user_id=uuid4(),
        cadence="ad_hoc",
        mission_type="message",
        title="Réponse à Margaux",
        brief="Réponds à la lettre de Margaux.",
        selected_concept_ids=[],
        target_errata_ids=[],
        target_vocabulary_ids=[],
        source_snapshot={},
        objectives=[],
        prompt_payload={},
        recap_payload={},
    )


def _note(learner: str, corrected: str, why: str) -> dict:
    return {
        "display_label": "Élision",
        "learner_text": learner,
        "corrected_target": corrected,
        "why_wrong": why,
        "repair_hint": "Écris l'apostrophe.",
        "severity": 1,
        "recurring": False,
        "task_error_type": "orthography",
        "external_id": "",
    }


class _Rewriter:
    """The model of the walk: lists two fixes, makes four changes, rewrites the question."""

    def generate_error_detection(self, messages, **kwargs):  # type: ignore[no-untyped-def]
        return LLMResult(
            provider="stub",
            model="stub-correction",
            content=json.dumps(
                {
                    "verdict": "needs_revision",
                    "score_0_4": 2,
                    "corrected_answer": MODEL_REWRITE,
                    "objective_progress": [],
                    "concept_hits": [],
                    "missing_targets": [],
                    "errata": [
                        _note("le appartement", "l'appartement", "Devant une voyelle, « le » s'élide."),
                        _note("c est bizarre", "c'est bizarre", "C'est prend une apostrophe."),
                    ],
                    "vocabulary_links": [],
                }
            ),
            prompt_tokens=1,
            completion_tokens=1,
            total_tokens=2,
            cost=0,
            raw_response={},
        )


def test_the_corrected_form_keeps_the_learners_question_and_lists_what_changed(db_session):
    user = User(id=uuid4(), email="guard-133@example.com", hashed_password="x", proficiency_level="A2")
    correction = MissionCorrectionService(db_session, llm_service=_Rewriter()).correct_submission(
        user=user, mission=_mission(), text=LEARNER, mode="chat"
    )

    assert correction["corrected_answer"] == EXPECTED
    listed = " | ".join(f"{e['learner_text']} -> {e['corrected_target']}" for e in correction["errata"])
    assert "a dix-huit -> à dix-huit" in listed or "a -> à" in listed, listed
    assert "Qu est-ce -> Qu'est-ce" in listed, listed


def test_without_a_model_the_same_text_is_repaired_the_same_way(db_session):
    user = User(id=uuid4(), email="guard-133b@example.com", hashed_password="x", proficiency_level="A2")
    correction = MissionCorrectionService(db_session, llm_service=None).correct_submission(
        user=user, mission=_mission(), text=LEARNER, mode="chat"
    )
    assert "Qu'est-ce que c'est, jeudi à dix-huit heures ?" in correction["corrected_answer"]
    assert "C'est jeudi" not in correction["corrected_answer"]


def test_a_change_no_erratum_lists_is_found():
    from app.services.correction_guard import unlisted_changes

    listed = [
        _note("le appartement", "l'appartement", "x"),
        _note("c est bizarre", "c'est bizarre", "x"),
    ]
    found = unlisted_changes(LEARNER, MODEL_REWRITE, listed)
    assert found, "the rewrite of the question and the a -> à are not listed"
    # The same text with the question kept and every change listed has none.
    listed += [_note("Qu est", "Qu'est", "x"), _note("c est", "c'est", "x"), _note("a dix-huit", "à dix-huit", "x")]
    assert unlisted_changes(LEARNER, EXPECTED, listed) == []


def test_the_walks_rewrite_is_refused_even_when_every_other_change_is_listed():
    from app.services.correction_guard import drops_question, unlisted_changes

    assert drops_question(LEARNER, MODEL_REWRITE)
    assert not drops_question(LEARNER, EXPECTED)
    listed = [
        _note("le appartement", "l'appartement", "x"),
        _note("c est", "c'est", "x"),
        _note("a dix-huit", "à dix-huit", "x"),
    ]
    assert unlisted_changes(LEARNER, "C'est jeudi à dix-huit heures ?", listed)


@pytest.mark.parametrize(
    "sentence",
    [
        "Il a trois heures de retard.",
        "Elle a deux heures de route.",
        "Le train a 2 heures de retard.",
        "Il a dix heures de cours.",
        "Camille a une clé aussi.",
        "Elle a dit qu'elle vient.",
    ],
)
def test_a_correct_a_is_never_turned_into_an_accented_a(sentence, db_session):
    user = User(id=uuid4(), email="guard-133c@example.com", hashed_password="x", proficiency_level="A2")
    correction = MissionCorrectionService(db_session, llm_service=None).correct_submission(
        user=user, mission=_mission(), text=sentence, mode="chat"
    )
    assert correction["corrected_answer"] == sentence
    assert not any("à" in str(e.get("corrected_target")) for e in correction["errata"])


@pytest.mark.parametrize(
    "sentence",
    ["J'ai un rendez-vous.", "Dis-moi ce qu'il y a.", "C'est l'heure.", "Qu'est-ce que c'est ?", "Il s'est levé."],
)
def test_a_sentence_with_its_apostrophes_is_left_alone(sentence, db_session):
    user = User(id=uuid4(), email="guard-133d@example.com", hashed_password="x", proficiency_level="A2")
    correction = MissionCorrectionService(db_session, llm_service=None).correct_submission(
        user=user, mission=_mission(), text=sentence, mode="chat"
    )
    assert correction["corrected_answer"] == sentence
    assert not [e for e in correction["errata"] if e.get("external_id", "").startswith("FR_ORTHO_")]
