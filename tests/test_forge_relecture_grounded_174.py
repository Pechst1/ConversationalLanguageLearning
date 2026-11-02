"""#174 / #250: La Forge's keyed rungs, the relecture's errata held to the sentence.

Free production already passes the model's errata through the one checker every
correction passes (``held_to_sentence`` → ``correction_contract.verify_erratum``).
On a keyed rung (transform, a word_bank build) the key's verdict stands, and when
the key and the model agree the answer is wrong, the model's errata replaced the
key's as they came: a fix the learner's sentence does not bear out («Tu es» →
«Tu est», an agreement «with elle» in a sentence about «je») reached the learner.

Now each model erratum is held to its own item's answer. A fix that fails is
dropped, and an item with any dropped fix shows the key's own errata instead of
the model's, so a wrong answer never loses a fix it needs. A fill or classify
answer is a choice, not a sentence the checker can read: its errata pass as before.
"""

from __future__ import annotations

from app.services.atelier import AtelierCorrectionService


def _key_erratum(item_id: str, learner: str, target: str) -> dict:
    return {
        "item_id": item_id,
        "display_label": "Transform",
        "learner_text": learner,
        "corrected_target": target,
        "why_wrong": f"The key: «{target}».",
        "repair_hint": "",
        "severity": 2,
        "recurring": False,
        "task_error_type": "conjugation",
    }


def _model_erratum(item_id: str, learner: str, target: str, why: str) -> dict:
    return {
        "item_id": item_id,
        "display_label": "Form",
        "learner_text": learner,
        "corrected_target": target,
        "why_wrong": why,
        "repair_hint": "",
        "severity": 2,
        "recurring": False,
        "task_error_type": "agreement",
    }


def _merge(db_session, round_name: str, key: list[dict], model: list[dict], answers: dict, mode: str | None = None):  # type: ignore[no-untyped-def]
    service = AtelierCorrectionService(db_session)
    local = {"verdict": "incorrect", "score_0_4": 1.0, "errata": key, "corrected_answer": "key"}
    ai = {"verdict": "partial", "score_0_4": 2.0, "errata": model, "corrected_answer": "model"}
    learner_text = service._answer_text({"answers": answers})
    return service._merge_relecture(
        round_name, local, ai, learner_text=learner_text, accepted=[], mode=mode, answers=answers
    )


def _pairs(errata: list[dict]) -> list[tuple[str, str]]:
    return [(item["learner_text"], item["corrected_target"]) for item in errata]


def test_a_model_fix_the_sentence_does_not_bear_out_leaves_the_key_s_errata(db_session) -> None:
    key = [_key_erratum("t1", "Je suis mangé une pomme.", "J'ai mangé une pomme.")]
    model = [_model_erratum("t1", "mangé", "mangée", "With «elle», the participle agrees.")]

    final = _merge(db_session, "transform", key, model, {"t1": "Je suis mangé une pomme."})

    assert _pairs(final["errata"]) == [("Je suis mangé une pomme.", "J'ai mangé une pomme.")]
    assert final["dropped_errata"] == [{"learner_text": "mangé", "reason": "not_in_sentence"}]
    # The key's verdict and score stand, as before.
    assert final["verdict"] == "incorrect" and final["score_0_4"] == 1.0


def test_a_person_swap_wrong_for_the_subject_is_dropped(db_session) -> None:
    key = [_key_erratum("t1", "Tu es fatigué.", "Tu as été fatigué.")]
    model = [_model_erratum("t1", "es", "est", "Use «est».")]

    final = _merge(db_session, "transform", key, model, {"t1": "Tu es fatigué."})

    assert _pairs(final["errata"]) == [("Tu es fatigué.", "Tu as été fatigué.")]


def test_a_grounded_model_fix_still_replaces_the_key_s(db_session) -> None:
    key = [_key_erratum("t1", "Je suis mangé une pomme.", "J'ai mangé une pomme.")]
    model = [_model_erratum("t1", "suis", "ai", "«manger» takes «avoir»: «j'ai mangé».")]

    final = _merge(db_session, "transform", key, model, {"t1": "Je suis mangé une pomme."})

    assert _pairs(final["errata"]) == [("Je suis", "J'ai")]  # settled in the sentence: «je ai» → «j'ai»
    assert "avoir" in final["errata"][0]["why_wrong"]
    assert "dropped_errata" not in final


def test_each_item_is_held_to_its_own_answer(db_session) -> None:
    key = [
        _key_erratum("t1", "J'ai mangé un pomme.", "J'ai mangé une pomme."),
        _key_erratum("t2", "Nous sommes allé au marché.", "Nous sommes allés au marché."),
    ]
    model = [
        _model_erratum("t1", "un", "une", "«pomme» is feminine: «une pomme»."),
        # «sont» is right for «ils», not for the «nous» of t2's sentence.
        _model_erratum("t2", "sommes", "sont", "With «ils», use «sont»."),
    ]
    answers = {"t1": "J'ai mangé un pomme.", "t2": "Nous sommes allé au marché."}

    final = _merge(db_session, "transform", key, model, answers)

    assert _pairs(final["errata"]) == [("un", "une"), ("Nous sommes allé au marché.", "Nous sommes allés au marché.")]
    assert final["errata"][0]["why_wrong"].startswith("«pomme» is feminine")


def test_an_item_with_one_dropped_fix_shows_the_key_s_errata_instead(db_session) -> None:
    # A rung that asks for «vous»: «mange → mangez, with vous» is a fix the learner
    # needs, but «Tu mange» has no «vous» in it and the checker drops it. Showing the
    # model's other fix alone would hide it; the key's erratum says it all.
    key = [_key_erratum("t1", "Tu mange un pomme.", "Vous mangez une pomme.")]
    model = [
        _model_erratum("t1", "mange", "mangez", "With «vous», the ending is -ez."),
        _model_erratum("t1", "un", "une", "«pomme» is feminine: «une pomme»."),
    ]

    final = _merge(db_session, "transform", key, model, {"t1": "Tu mange un pomme."})

    assert _pairs(final["errata"]) == [("Tu mange un pomme.", "Vous mangez une pomme.")]
    assert final["dropped_errata"] == [{"learner_text": "mange", "reason": "not_in_sentence"}]


def test_a_built_sentence_is_held_too(db_session) -> None:
    key = [_key_erratum("w1", "Tu es fatigué", "Tu es fatiguée")]
    model = [_model_erratum("w1", "es", "est", "Use «est».")]

    final = _merge(db_session, "recognize", key, model, {"w1": ["Tu", "es", "fatigué"]}, mode="word_bank")

    assert _pairs(final["errata"]) == [("Tu es fatigué", "Tu es fatiguée")]


def test_a_chosen_blank_is_not_a_sentence_and_passes_as_before(db_session) -> None:
    # The learner chose «est» for «Tu ___ fatigué»: their answer has no «tu» in it,
    # so a checker reading the answer alone would drop a right fix.
    key = [_key_erratum("f1", "est", "es")]
    model = [_model_erratum("f1", "est", "es", "After «tu», être is «es».")]

    final = _merge(db_session, "recognize", key, model, {"f1": "est"}, mode="fill")

    assert final["errata"] == model


def test_free_production_is_unchanged(db_session) -> None:
    # Free production had the check already (refine_production_correction).
    service = AtelierCorrectionService(db_session)
    local = {"verdict": "partial", "score_0_4": 2.0, "local_status": "checking", "errata": []}
    ai = {
        "verdict": "partial",
        "score_0_4": 2.0,
        "corrected_answer": "Tu est fatigué.",
        "errata": [_model_erratum("s1", "es", "est", "Use «est».")],
    }

    final = service._merge_relecture("sentence", local, ai, learner_text="Tu es fatigué.", accepted=[])

    assert final["errata"] == []
