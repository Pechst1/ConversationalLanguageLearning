"""Regressions for two broken Atelier exercise types:

- Transform round: the deterministic fallback generator used to hand out
  "transform" exercises whose expected_answer was identical to the source
  sentence for every grammar profile except three hand-authored ones — an
  unsolvable exercise where leaving the sentence untouched was the only way
  to be marked correct.
- Produce round ("Compose le paragraphe"): the stated min/max word count was
  purely decorative — neither the client nor the server ever enforced it,
  and the server-side prompt_payload for this round was silently stripped of
  min_words/max_words/prompt entirely because produce attempts are
  intentionally submitted with concept_id=None.
"""
from __future__ import annotations

from uuid import uuid4

from app.db.models.atelier import AtelierSession
from app.db.models.grammar import GrammarConcept
from app.services.atelier import AtelierCorrectionService, AtelierExerciseGenerator
from app.services.grammar_feedback import infer_grammar_profile

from .test_atelier import _FailingCorrectionLLMService, _FailingLLMService, _user

# Every profile the fallback transform generator must special-case, plus one
# concept crafted to fall through to the true "grammar_target" catch-all.
_PROFILE_CONCEPT_SPECS: dict[str, dict[str, object]] = {
    "article_after_negation": {
        "name": "Negation with partitive articles",
        "core_rule": "After ne...pas, du/de la/de l'/des/un/une become de/d', except after être.",
        "examples": "Je ne bois pas de café.",
    },
    "tense_aspect": {
        "name": "Imparfait vs passé composé",
        "core_rule": "Use imparfait for background/habit, passé composé for a bounded completed event.",
        "examples": "Il pleuvait quand je suis sorti.",
    },
    "si_present_result_form": {
        "external_id": "FR_B1_COND_001",
        "name": "Si type 1: present condition, future result",
        "core_rule": "Use si plus present, then future simple or imperative.",
        "examples": "S'il pleut, je prendrai le métro.",
    },
    "conditional_mood": {
        "name": "Conditionnel present",
        "core_rule": "Use the conditional for polite requests.",
        "examples": "Je voudrais un café.",
    },
    "mood": {
        "name": "Subjonctif present",
        "core_rule": "Use the subjunctive after expressions of necessity.",
        "examples": "Il faut que tu viennes.",
    },
    "relative_pronoun": {
        "name": "Relative pronouns: qui, que, dont",
        "category": "Pronouns",
        "core_rule": "Use qui, que, ou, or dont according to the role inside the relative clause.",
        "exercise_tags": ["relative_pronoun", "dont"],
    },
    "pronoun_choice": {
        "name": "Direct and indirect object pronouns",
        "core_rule": "Choose le, la, les, lui, leur, y, or en according to the object being replaced.",
        "exercise_tags": ["pronoun_choice", "le", "lui", "en"],
    },
    "determiner": {
        "name": "Articles and determiners",
        "core_rule": "Choose the determiner that matches the noun and the intended meaning.",
        "exercise_tags": ["determiner", "article"],
    },
    "agreement": {
        # This is the exact concept family from the live bug report
        # ("Gender and number basics" transform round showing an unchanged
        # sentence as both the learner's wrong answer's target and source).
        "name": "Gender and number basics",
        "core_rule": "Adjectives and participles agree in gender and number with what they describe.",
        "exercise_tags": ["agreement", "gender", "number"],
    },
    "preposition": {
        "name": "Common place prepositions",
        "core_rule": "Use à, de, dans, sur, or chez to connect places and actions.",
        "exercise_tags": ["preposition", "chez", "dans"],
    },
    "comparison": {
        "name": "Basic comparisons",
        "core_rule": "Use plus, moins, or aussi with que to compare two people or things.",
        "exercise_tags": ["comparison", "que"],
    },
}


def _concept(**kwargs) -> GrammarConcept:
    return GrammarConcept(
        external_id=kwargs.get("external_id") or f"TEST_{uuid4().hex[:8]}",
        language="fr",
        name=kwargs["name"],
        level=kwargs.get("level", "B1"),
        category=kwargs.get("category"),
        subskill=kwargs.get("subskill"),
        core_rule=kwargs.get("core_rule"),
        main_traps=kwargs.get("main_traps"),
        anchor_examples=kwargs.get("anchor_examples"),
        examples=kwargs.get("examples"),
        exercise_tags=kwargs.get("exercise_tags", []),
        active=True,
    )


def test_every_known_profile_maps_to_its_intended_fallback_bucket(db_session) -> None:
    # Guards the test fixtures themselves: if infer_grammar_profile's keyword
    # matching ever drifts, we want a clear failure here, not a silent gap in
    # the coverage below.
    for expected_key, spec in _PROFILE_CONCEPT_SPECS.items():
        concept = _concept(**spec)
        assert infer_grammar_profile(concept).key == expected_key, spec["name"]


def test_fallback_transform_items_never_leave_the_sentence_unchanged(db_session) -> None:
    generator = AtelierExerciseGenerator(db_session)

    for profile_key, spec in _PROFILE_CONCEPT_SPECS.items():
        concept = _concept(**spec)
        items = generator._fallback_transform_items(concept, ["unused"], prefix="test")

        assert len(items) == 3, profile_key
        for item in items:
            assert item["source"].strip(), profile_key
            assert item["expected_answer"].strip(), profile_key
            assert item["instruction"].strip(), profile_key
            assert item["type"] in {"directed_rewrite", "contrast_rewrite", "repair_rewrite"}, profile_key
            # The bug: an unsolvable "transform" exercise where the answer key
            # is identical to what the learner was given to start with.
            assert item["source"] != item["expected_answer"], (
                f"{profile_key} transform item has source == expected_answer: {item['source']!r}"
            )


def test_fallback_transform_catch_all_also_avoids_the_identity_bug(db_session) -> None:
    # A concept that matches none of the eleven named profiles falls through
    # to infer_grammar_profile's generic "grammar_target" bucket.
    concept = _concept(
        name="Some future grammar point nobody has classified yet",
        core_rule="Zzyx frobnicate the target morpheme before the verb.",
    )
    assert infer_grammar_profile(concept).key == "grammar_target"

    generator = AtelierExerciseGenerator(db_session)
    items = generator._fallback_transform_items(concept, ["unused"], prefix="test")

    assert len(items) == 3
    for item in items:
        assert item["source"] != item["expected_answer"]


def test_agreement_transform_exercise_requires_a_real_change(db_session) -> None:
    """End-to-end reproduction of the reported bug: the concept family from
    the screenshot ("Gender and number basics" / agreement) used to accept
    the untouched source sentence as a correct transform answer."""
    user = _user(db_session)
    concept = _concept(**_PROFILE_CONCEPT_SPECS["agreement"])
    db_session.add(concept)
    db_session.commit()
    db_session.refresh(concept)

    generator = AtelierExerciseGenerator(db_session, llm_service=_FailingLLMService())
    exercise_set = generator.get_or_create(concept, reuse_shared_cache=False)
    items = exercise_set.payload["transform"]["items"]
    assert len(items) == 3
    for item in items:
        assert item["source"] != item["expected_answer"]

    session = AtelierSession(
        user_id=user.id,
        selected_concept_ids=[concept.id],
        quote_payload={"exercise_set_ids": {str(concept.id): str(exercise_set.id)}},
        status="in_progress",
        recap_payload={},
    )
    db_session.add(session)
    db_session.commit()

    correction_service = AtelierCorrectionService(db_session, llm_service=_FailingCorrectionLLMService())

    # Submitting every sentence back unchanged must NOT be accepted.
    unchanged_attempt = correction_service.submit_attempt(
        session=session,
        user=user,
        concept=concept,
        round_name="transform",
        mode="rewrite",
        exercise_id=f"{concept.external_id}:transform",
        answer_payload={"answers": {item["id"]: item["source"] for item in items}},
    )
    assert unchanged_attempt.verdict != "correct"
    assert unchanged_attempt.correction_payload.get("errata")

    # The real expected_answers are still accepted.
    correct_attempt = correction_service.submit_attempt(
        session=session,
        user=user,
        concept=concept,
        round_name="transform",
        mode="rewrite",
        exercise_id=f"{concept.external_id}:transform:resubmit",
        answer_payload={"answers": {item["id"]: item["expected_answer"] for item in items}},
    )
    assert correct_attempt.verdict == "correct"
    assert not correct_attempt.correction_payload.get("errata")


def _produce_session(db_session):
    user = _user(db_session)
    concept = _concept(
        name="Gender and number basics",
        core_rule="Adjectives and participles agree in gender and number with what they describe.",
        exercise_tags=["agreement"],
    )
    db_session.add(concept)
    db_session.commit()
    db_session.refresh(concept)

    generator = AtelierExerciseGenerator(db_session, llm_service=_FailingLLMService())
    exercise_set = generator.get_or_create(concept, reuse_shared_cache=False)

    session = AtelierSession(
        user_id=user.id,
        selected_concept_ids=[concept.id],
        quote_payload={"exercise_set_ids": {str(concept.id): str(exercise_set.id)}},
        status="in_progress",
        recap_payload={},
    )
    db_session.add(session)
    db_session.commit()
    return user, concept, exercise_set, session


def test_produce_prompt_payload_carries_word_count_even_with_no_concept(db_session) -> None:
    """Root cause of the produce-round bug: attempts are submitted with
    concept_id=None by design (produce spans the whole session), but the
    prompt-payload builder used to return an empty stub whenever concept was
    None, silently dropping min_words/max_words/prompt for every produce
    attempt regardless of LLM availability."""
    user, concept, exercise_set, session = _produce_session(db_session)
    correction_service = AtelierCorrectionService(db_session, llm_service=_FailingCorrectionLLMService())

    prompt_payload = correction_service._prompt_payload(
        None, "produce", "integrated_writing", "integrated-writing", user=user, session=session
    )

    assert prompt_payload.get("min_words")
    assert prompt_payload.get("max_words")
    assert prompt_payload.get("prompt")
    assert prompt_payload["min_words"] == exercise_set.payload["produce"]["min_words"]


def test_produce_round_rejects_a_paragraph_under_the_minimum_word_count(db_session) -> None:
    user, concept, exercise_set, session = _produce_session(db_session)
    correction_service = AtelierCorrectionService(db_session, llm_service=_FailingCorrectionLLMService())
    min_words = exercise_set.payload["produce"]["min_words"]

    short_text = " ".join(["mot"] * max(1, min_words - 3))
    assert len(short_text.split()) < min_words

    attempt = correction_service.submit_attempt(
        session=session,
        user=user,
        concept=None,
        round_name="produce",
        mode="integrated_writing",
        exercise_id="integrated-writing",
        answer_payload={"text": short_text},
    )

    assert attempt.verdict == "needs_review"
    errata = attempt.correction_payload.get("errata") or []
    assert any(item.get("task_error_type") == "length_compliance" for item in errata)


def test_produce_round_accepts_a_paragraph_meeting_the_minimum_word_count(db_session) -> None:
    user, concept, exercise_set, session = _produce_session(db_session)
    correction_service = AtelierCorrectionService(db_session, llm_service=_FailingCorrectionLLMService())
    min_words = exercise_set.payload["produce"]["min_words"]

    long_enough_text = " ".join(["mot"] * (min_words + 5))

    attempt = correction_service.submit_attempt(
        session=session,
        user=user,
        concept=None,
        round_name="produce",
        mode="integrated_writing",
        exercise_id="integrated-writing",
        answer_payload={"text": long_enough_text},
    )

    errata = attempt.correction_payload.get("errata") or []
    assert not any(item.get("task_error_type") == "length_compliance" for item in errata)
