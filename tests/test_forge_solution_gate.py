"""Owner, 2026-11-13: the solution waits until the second chance is spent.

«The user should not see what is right when he then gets another chance to fix it;
only afterwards the solution.» Guard: for every La Forge item type with a second
chance, the payload served before the chance (``_attempt_response``, ``_attempt_read``)
holds neither the corrected line nor the corrected span; the one served after the
repair, or after «Show the solution», does.
"""
from __future__ import annotations

import json
import unicodedata
from uuid import uuid4

import pytest

from app.api.v1.endpoints.atelier import _attempt_read, _attempt_response
from app.db.models.atelier import AtelierAttempt, AtelierSession
from app.db.models.user import User
from app.services import solution_gate
from app.services.atelier import AtelierCorrectionService
from app.services.correction_contract import deterministic_errata


def _fold(text: str) -> str:
    return unicodedata.normalize("NFC", text).replace("’", "'").lower()


# The owner's screenshot: «Oui j'ai un carte bancaire», task «je peux + payer».
SENTENCE = {
    "round": "sentence",
    "mode": "sentence",
    "answer": {"text": "Oui j'ai un carte bancaire"},
    "prompt": {"items": [{"id": "s1", "prompt": "Tu peux payer par carte ?", "instruction": "Réponds avec « je peux » et l'infinitif.", "example_answer": "Oui, je peux payer par carte."}]},
    "correction": {
        "assessment_status": "checked",
        "verdict": "partial",
        "corrected_answer": "Oui, j'ai une carte bancaire.",
        "errata": [
            {
                "learner_text": "un carte",
                "corrected_target": "une carte",
                "why_wrong": "„Un“ ist maskulin; das feminine Substantiv „carte“ verlangt „une“.",
                "repair_hint": "Setze vor „carte“ den Artikel „une“.",
                "task_error_type": "gender_agreement",
                "display_label": "Artikel",
            },
            {
                "learner_text": "",
                "corrected_target": "",
                "why_wrong": "Deine Antwort nennt eine Karte, verwendet aber nicht das geforderte Modalverb mit Infinitiv.",
                "repair_hint": "Antworte auf die Frage mit „je peux“ und dem Infinitiv „payer“.",
                "task_error_type": "task_compliance",
            },
        ],
    },
    "secrets": ["Oui, j'ai une carte bancaire.", "une carte", "une"],
}

CASES = {
    "free sentence": SENTENCE,
    "fill, three choices": {
        "round": "recognize",
        "mode": "fill",
        "answer": {"answers": {"f1": "va"}},
        "prompt": {"items": [{"id": "f1", "prompt": "Nous ___ au cinéma.", "choices": ["va", "allons", "allez"], "correct_answer": "allons"}]},
        "correction": {
            "assessment_status": "checked",
            "verdict": "incorrect",
            "corrected_answer": {"f1": "allons"},
            "errata": [{"item_id": "f1", "learner_text": "va", "corrected_target": "allons", "why_wrong": "Avec « nous », aller fait « allons ».", "repair_hint": "Choisis « allons ».", "task_error_type": "verb_conjugation"}],
        },
        # The options are on screen; which one is right is the secret.
        "secrets": [],
    },
    "typed form": {
        "round": "recognize",
        "mode": "fill",
        "answer": {"answers": {"t1": "finit"}},
        "prompt": {"items": [{"id": "t1", "prompt": "Ils ___ (finir) tard.", "correct_answer": "finissent"}]},
        "correction": {
            "assessment_status": "checked",
            "verdict": "incorrect",
            "corrected_answer": {"t1": "finissent"},
            "errata": [{"item_id": "t1", "learner_text": "finit", "corrected_target": "finissent", "why_wrong": "You wrote «finit»; here it is «finissent».", "task_error_type": "verb_conjugation"}],
        },
        "secrets": ["finissent"],
    },
    "word bank": {
        "round": "recognize",
        "mode": "word_bank",
        "answer": {"answers": {"w1": ["je", "ne", "mange", "jamais", "pas"]}},
        "prompt": {"items": [{"id": "w1", "tokens": ["je", "ne", "mange", "jamais", "pas"], "correct_answer": "je ne mange jamais"}]},
        "correction": {
            "assessment_status": "checked",
            "verdict": "incorrect",
            "corrected_answer": {"w1": "Je ne mange jamais."},
            "errata": [{"item_id": "w1", "learner_text": "je ne mange jamais pas", "corrected_target": "je ne mange jamais", "why_wrong": "« jamais » already makes the sentence negative, so « pas » goes: « je ne mange jamais ».", "task_error_type": "negation"}],
        },
        "secrets": ["Je ne mange jamais."],
    },
    "transform": {
        "round": "transform",
        "mode": "transform",
        "answer": {"answers": {"r1": "Elle est allé au marché."}},
        "prompt": {"items": [{"id": "r1", "source": "Elle va au marché.", "instruction": "Mets la phrase au passé composé.", "expected_answer": "Elle est allée au marché."}]},
        "correction": {
            "assessment_status": "checked",
            "verdict": "incorrect",
            "corrected_answer": {"r1": "Elle est allée au marché."},
            "errata": [{"item_id": "r1", "learner_text": "allé", "corrected_target": "allée", "why_wrong": "With être the participle agrees with the subject: « allée ».", "task_error_type": "gender_agreement"}],
        },
        "secrets": ["Elle est allée au marché.", "allée"],
    },
    "find the mistake": {
        "round": "transform",
        "mode": "spot",
        "answer": {"answers": {"p1": "Je suis allé à le parc."}},
        "prompt": {"items": [{"id": "p1", "source_fr": "Je suis allé à le parc.", "expected_answer": "Je suis allé au parc."}]},
        "correction": {
            "assessment_status": "checked",
            "verdict": "incorrect",
            "corrected_answer": {"p1": "Je suis allé au parc."},
            "errata": [{"item_id": "p1", "learner_text": "à le", "corrected_target": "au", "why_wrong": "« à le » contracts to « au ».", "task_error_type": "articles"}],
        },
        "secrets": ["Je suis allé au parc.", "au"],
    },
    "classify, three labels": {
        "round": "recognize",
        "mode": "classify",
        "answer": {"answers": {"c1": "imparfait"}},
        "prompt": {"items": [{"id": "c1", "prompt": "Hier, j'ai mangé une pomme.", "labels": ["présent", "imparfait", "passé composé"], "correct_label": "passé composé"}]},
        "correction": {
            "assessment_status": "checked",
            "verdict": "incorrect",
            "corrected_answer": {"c1": "passé composé"},
            "errata": [{"item_id": "c1", "learner_text": "imparfait", "corrected_target": "passé composé", "why_wrong": "« ai mangé » is avoir + participle: passé composé.", "task_error_type": "tense"}],
        },
        "secrets": [],
    },
}


def _attempt(db_session, case: dict, *, chance: bool = True) -> AtelierAttempt:
    user = User(id=uuid4(), email=f"{uuid4()}@example.com", hashed_password="test")
    db_session.add(user)
    db_session.flush()
    session = AtelierSession(user_id=user.id, selected_concept_ids=[])
    db_session.add(session)
    db_session.flush()
    correction = solution_gate.mark(dict(case["correction"]), chance=chance, language="de")
    attempt = AtelierAttempt(
        atelier_session_id=session.id,
        user_id=user.id,
        round=case["round"],
        mode=case["mode"],
        exercise_id=f"gate-{uuid4()}",
        verdict=case["correction"]["verdict"],
        score_0_4=1,
        answer_payload=case["answer"],
        prompt_payload=case["prompt"],
        correction_payload=correction,
    )
    db_session.add(attempt)
    db_session.commit()
    return attempt


def _served(attempt: AtelierAttempt) -> list[str]:
    return [
        _fold(json.dumps(_attempt_response(attempt).model_dump(mode="json"), ensure_ascii=False)),
        _fold(json.dumps(_attempt_read(attempt), ensure_ascii=False, default=str)),
    ]


def _holds(served: str, secret: str) -> bool:
    import re

    needle = _fold(secret)
    return re.search(rf"(?<![\w]){re.escape(needle)}(?![\w])", served) is not None


@pytest.mark.parametrize("name", list(CASES))
def test_nothing_of_the_solution_is_served_before_the_second_chance(db_session, name):
    case = CASES[name]
    attempt = _attempt(db_session, case)
    for served in _served(attempt):
        for secret in case["secrets"]:
            assert not _holds(served, secret), f"{name}: «{secret}» served before the second chance"
    correction = _attempt_response(attempt).model_dump(mode="json")["correction"]
    assert correction["corrected_answer"] in ({}, "")
    target = case["correction"]["errata"][0]["corrected_target"]
    for erratum in correction["errata"]:
        assert erratum["corrected_target"] == ""
        assert not _holds(_fold(erratum["hint"] + " " + erratum["why_wrong"] + " " + erratum["display_label"]), target)
    assert all(edit["replacement"] == "" for edit in _attempt_response(attempt).model_dump(mode="json")["check"]["edits"])


@pytest.mark.parametrize("name", list(CASES))
def test_the_solution_is_served_once_the_chance_is_spent(db_session, name):
    case = CASES[name]
    attempt = _attempt(db_session, case)
    attempt.correction_payload = solution_gate.reveal(dict(attempt.correction_payload), by="reveal")
    db_session.commit()
    served = _attempt_response(attempt).model_dump(mode="json")["correction"]
    assert served["corrected_answer"] == case["correction"]["corrected_answer"]
    assert served["errata"][0]["corrected_target"] == case["correction"]["errata"][0]["corrected_target"]


def test_a_repair_sent_spends_the_chance(db_session):
    attempt = _attempt(db_session, SENTENCE)
    updated = AtelierCorrectionService(db_session).record_micro_repair(
        attempt=attempt, text="Oui j'ai une carte bancaire", erratum_index=0
    )
    served = _attempt_response(updated).model_dump(mode="json")["correction"]
    assert served["corrected_answer"] == "Oui, j'ai une carte bancaire."
    assert served["solution"]["state"] == "shown"


def test_before_the_chance_the_learner_sees_where_and_why(db_session):
    attempt = _attempt(db_session, SENTENCE)
    served = _attempt_response(attempt).model_dump(mode="json")["correction"]
    first, task = served["errata"]
    # Where: the marked word of the learner's own line.
    assert first["mark"] == {"start": 9, "end": 11, "text": "un", "erratum": 0}
    assert served["marks"][0]["text"] == "un"
    # Why: the rule, without the form. The clause naming «une» is gone; the rest stays.
    assert first["hint"] == "„Un“ ist maskulin."
    assert "une" not in first["hint"]
    # The task: what it asks, never the answer's own words («payer» is the task's, «peux» too).
    assert task["hint"]
    assert served["solution"]["state"] == "withheld"


def test_a_right_answer_is_never_withheld(db_session):
    case = {**SENTENCE, "correction": {"assessment_status": "checked", "verdict": "correct", "corrected_answer": "Oui, je peux payer.", "errata": []}}
    attempt = _attempt(db_session, case)
    assert _attempt_response(attempt).model_dump(mode="json")["correction"]["corrected_answer"] == "Oui, je peux payer."


@pytest.mark.parametrize(
    ("kwargs", "chance"),
    [
        ({}, True),
        ({"first_submission": False}, False),  # the retry is the chance: its miss shows the solution
        ({"retest": True}, False),
        ({"rule_check": True}, False),
        ({"exercise_id": "c:recognize:classify:lead+4"}, False),  # the burst
        ({"round_name": "recognize", "answer_payload": {"answers": {"j1": "correcte"}}, "prompt_payload": {"items": [{"id": "j1", "labels": ["correcte", "à corriger"]}]}}, False),
        ({"round_name": "recognize", "answer_payload": {"answers": {"f1": "va"}}, "prompt_payload": {"items": [{"id": "f1", "choices": ["va", "allons", "allez"]}]}}, True),
    ],
)
def test_which_answers_get_a_second_chance(kwargs, chance):
    base = {
        "round_name": "sentence",
        "exercise_id": "c:sentence:sentence:s1",
        "prompt_payload": {},
        "answer_payload": {"text": "x"},
        "first_submission": True,
        "retest": False,
        "rule_check": False,
    }
    assert solution_gate.second_chance_for(**{**base, **kwargs}) is chance


@pytest.mark.parametrize(
    ("learner", "language"),
    [("un carte", "de"), ("un carte", "en"), ("un carte", "fr"), ("le maison", "de"), ("ce arbre", "en"), ("je vais à le marché", "fr"), ("elle est allé", "de")],
)
def test_every_rule_hint_keeps_the_answer_out(learner, language):
    errata = deterministic_errata(learner, language=language)
    assert errata, learner
    for erratum in errata:
        hint = erratum["hint"]
        assert hint, erratum["external_id"]
        phrases, tokens = solution_gate.leak_terms({"errata": [erratum]}, learner)
        assert solution_gate.scrub_hint(hint, phrases, tokens) == hint, (erratum["external_id"], hint)


def test_the_scrub_drops_only_the_clause_that_names_the_answer():
    phrases, tokens = solution_gate.leak_terms(
        {"corrected_answer": "Je suis allée au marché.", "errata": [{"learner_text": "allé", "corrected_target": "allée"}]},
        "Je suis allé au marché.",
    )
    assert solution_gate.scrub_hint("Das Alter sagt man mit avoir: « allée ».", phrases, tokens) == "Das Alter sagt man mit avoir."
    assert solution_gate.scrub_hint("Write « allée ».", phrases, tokens) == ""
