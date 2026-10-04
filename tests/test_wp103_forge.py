"""WP-103 «Retour d'essai» — La Forge half (T3, T8, T9, T10, T11). No model calls.

The owner's test of La Forge (English-speaking A1 learner, 2026-09-29):

* T9 — «Lila cherche un poster grand» got «Right / Well done!», and ten seconds later
  «3 corrections». Locally only an accepted answer may say «right»; anything else is
  «checking» until the model's verdict, and a shown «right» is never reversed.
* T10 — one of the three corrections was wrong («poster» is French) and the one
  explanation was printed three times. Accepted answers now include «Lila cherche un
  grand poster»; a French word called English is dropped; notes are one per issue.
* T8 — «Correct / À corriger» ended at the sort. «À corriger» now opens the correction.
* T11 — «Romy texts you from the newsroom…» wrapped every production item.
* T3 — every drill says what to produce.
"""

from __future__ import annotations

import json

import pytest

from app.services import forge_grading as grading
from app.services import item_bank as ib
from app.services.atelier import AtelierCorrectionService, _accepted_answers

OWNER_ANSWER = "Lila cherche un poster grand"


@pytest.fixture(scope="module")
def lila_item() -> ib.BankItem:
    """The owner's item: «Lila is looking for a big poster.» (frame adj-pre)."""

    bank = ib.ItemBank()
    frame = next(f for unit in bank.templates for f in bank.frames(unit) if f.frame_id == "adj-pre")
    lex = bank.lex
    bindings = {
        "C": next(entry for entry in lex.pool("cast") if "Lila" in str(entry.get("fr"))),
        "N": next(entry for entry in lex.pool("noun") if entry.get("id") == "affiche"),
        "A": next(entry for entry in lex.pool("adj") if entry.get("id") == "grand"),
    }
    return bank.render(frame, bindings)


# ---------------------------------------------------------------------------
# T10 — the accepted answers, the loanword guard, one note per issue
# ---------------------------------------------------------------------------


def test_the_owners_item_accepts_the_poster_and_the_affiche(lila_item):
    assert lila_item.en == "Lila is looking for a big poster."
    assert "Lila cherche une grande affiche." in lila_item.accepted
    assert "Lila cherche un grand poster." in lila_item.accepted
    sentence = ib.output_item(lila_item, round_name="sentence", requirement={"label": "X"})
    assert set(sentence["accepted_answers"]) >= {
        "Lila cherche une grande affiche.",
        "Lila cherche un grand poster.",
    }


#: What the corrector said to the owner: three corrections, one of them false, and the
#: same explanation three times.
OWNER_RELECTURE = {
    "verdict": "partial",
    "score_0_4": 2,
    "corrected_answer": "Lila cherche une grande affiche.",
    "concept_hits": [],
    "missing_targets": [],
    "errata": [
        {
            "display_label": "Vocabulary",
            "learner_text": "poster",
            "corrected_target": "affiche",
            "why_wrong": "«poster» is an English word. In French, say «affiche».",
            "repair_hint": "Use «une affiche».",
            "severity": 2,
            "task_error_type": "vocabulary_choice",
        },
        {
            "display_label": "Adjective position",
            "learner_text": "un poster grand",
            "corrected_target": "une grande affiche",
            "why_wrong": "«grand» goes before the noun. «grand» goes before the noun.",
            "repair_hint": "Put grand before the noun.",
            "severity": 2,
            "task_error_type": "word_order",
        },
        {
            "display_label": "Agreement",
            "learner_text": "un",
            "corrected_target": "une",
            "why_wrong": "«grand» goes before the noun.",
            "repair_hint": "Use une.",
            "severity": 1,
            "task_error_type": "agreement",
        },
    ],
    "lexical_gaps": [
        {"learner_fragment": "poster", "source_language": "en", "french": "affiche", "gloss": "poster"}
    ],
}


def test_the_owners_poster_gets_one_correction_about_adjective_position(db_session, lila_item):
    """E-7-style fixture: «Lila cherche un poster grand» → a single correction,
    «un grand poster», explained by the adjective's position only."""

    service = AtelierCorrectionService(db_session)
    ai = service._normalize_llm_correction(
        OWNER_RELECTURE, concepts=[], fallback={"errata": []}, corrected_answer_mode="text", model="fake"
    )
    # The false «English» correction and gap are gone before anything else.
    assert all(item["learner_text"] != "poster" for item in ai["errata"])
    assert ai["lexical_gaps"] == []
    prompt = {"items": [ib.output_item(lila_item, round_name="sentence", requirement={"label": "X"})]}
    local = {"verdict": "partial", "score_0_4": 2.0, "local_status": "checking", "errata": []}
    final = service._merge_relecture(
        "sentence", local, ai, learner_text=OWNER_ANSWER, accepted=_accepted_answers(prompt)
    )
    assert len(final["errata"]) == 1
    erratum = final["errata"][0]
    assert (erratum["learner_text"], erratum["corrected_target"]) == ("un poster grand", "un grand poster")
    assert erratum["why_wrong"] == "«grand» goes before the noun: «un grand poster»."
    assert final["corrected_answer"] == "Lila cherche un grand poster."
    assert final["notes_native"] == ["«grand» goes before the noun: «un grand poster»."]
    assert final["verdict"] == "partial"
    assert not any("English" in note for note in final["notes_native"])


@pytest.mark.parametrize(
    ("erratum", "dropped"),
    [
        ({"learner_text": "poster", "why_wrong": "«poster» is an English word."}, True),
        ({"learner_text": "week-end", "why_wrong": "C'est un mot anglais."}, True),
        ({"learner_text": "building", "why_wrong": "«building» is English."}, False),
        # «anglais» the adjective is not a claim that a word is English.
        ({"learner_text": "anglais", "why_wrong": "«anglais» agrees with elle: «anglaise»."}, False),
    ],
)
def test_a_french_word_called_english_is_dropped(erratum, dropped):
    kept, _, gone = grading.drop_false_english([erratum])
    assert bool(gone) is dropped and bool(kept) is not dropped


def test_notes_are_one_per_issue_and_never_repeat():
    errata = [
        {"why_wrong": "«grand» goes before the noun. «grand» goes before the noun. Always."},
        {"why_wrong": "«Grand» goes before the noun!"},
        {"why_wrong": "", "repair_hint": "Use une with affiche."},
    ]
    assert grading.notes_native(errata) == ["«grand» goes before the noun. Always.", "Use une with affiche."]


def test_the_corrector_is_told_loanwords_are_french(db_session):
    prompt = AtelierCorrectionService(db_session)._correction_system_prompt()
    assert "Never call a French word English" in prompt
    assert "poster" in prompt and "One explanation per issue" in prompt


# ---------------------------------------------------------------------------
# T9 — no instant «Right»
# ---------------------------------------------------------------------------


def test_local_right_only_for_an_accepted_answer(lila_item):
    accepted = list(lila_item.accepted)
    right = grading.production_local_check(None, "lila cherche un grand poster !", accepted=accepted)
    assert right["local_status"] == "right"
    # Quotes, apostrophes, spacing and case are typography …
    assert grading.matches_accepted("« Lila  cherche une grande affiche »", accepted)
    assert grading.matches_accepted("J’ai vu l‘affiche.", ["J'ai vu l'affiche"])
    # … a different order, a missing word or an accent is not.
    assert grading.production_local_check(None, OWNER_ANSWER, accepted=accepted)["local_status"] == "checking"
    assert not grading.matches_accepted("Je suis alle", ["Je suis allé"])
    # A detector hit is a hint, never a «Right».
    assert grading.production_local_check(None, "Lila cherche un poster.", accepted=accepted)["local_status"] == "checking"


def test_a_shown_right_is_never_reversed(db_session):
    service = AtelierCorrectionService(db_session)
    local = {"verdict": "correct", "score_0_4": 4.0, "local_status": "right", "errata": []}
    ai = {
        "verdict": "partial",
        "score_0_4": 2.5,
        "corrected_answer": "Lila cherche une grande affiche.",
        "errata": [{"learner_text": "poster", "corrected_target": "affiche", "why_wrong": "«affiche» is more usual."}],
    }
    final = service._merge_relecture(
        "sentence", local, ai, learner_text="Lila cherche un grand poster.",
        accepted=["Lila cherche un grand poster."],
    )
    assert final["verdict"] == "correct" and final["score_0_4"] == 4.0
    assert final["errata"] == [] and final["notes_native"] == []
    assert final["style_notes_native"] == ["«affiche» is more usual."]
    assert final["local_status"] == "right"


# ---------------------------------------------------------------------------
# T8 — «À corriger» leads somewhere
# ---------------------------------------------------------------------------


def _classify_correction(db_session, item, answer, band="A1"):
    service = AtelierCorrectionService(db_session)
    service._learner_band = band
    return service.correct(
        concept=None, round_name="recognize", mode="classify", exercise_id=f"X:classify:{item['id']}",
        prompt_payload={"items": [item]}, answer_payload={"answers": {item["id"]: answer}},
    )


def test_a_sentence_sorted_a_corriger_is_then_corrected(db_session, lila_item):
    item = ib.classify_item(lila_item, show_correct=False)
    assert item["source_fr"] == "Lila cherche une grand affiche."
    correction = _classify_correction(db_session, item, "À corriger")
    assert correction["verdict"] == "correct"
    assert correction["corrected_fr"] == "Lila cherche une grande affiche."
    follow_up = correction["follow_up"]
    assert follow_up["kind"] == "correct_it"
    assert follow_up["source_fr"] == "Lila cherche une grand affiche."
    assert follow_up["goal_native"] == 'Correct it so that it says: "Lila is looking for a big poster."'
    assert follow_up["accepted_fr"][0] == "Lila cherche une grande affiche."
    assert "Lila cherche un grand poster." in follow_up["accepted_fr"]
    # A1: tiles — the right sentence's words and the wrong word as a spare.
    assert sorted(follow_up["options"]) == sorted(["Lila", "cherche", "une", "grande", "affiche", "grand"])
    # Above A1 it is a field.
    assert "options" not in _classify_correction(db_session, item, "À corriger", band="B1")["follow_up"]


def test_a_wrong_sort_still_shows_the_right_sentence(db_session, lila_item):
    item = ib.classify_item(lila_item, show_correct=False)
    correction = _classify_correction(db_session, item, "Correct")
    assert correction["verdict"] != "correct"
    assert correction["corrected_fr"] == "Lila cherche une grande affiche."
    assert "follow_up" not in correction
    right = ib.classify_item(lila_item, show_correct=True)
    assert "corrected_fr" not in _classify_correction(db_session, right, "Correct")


def test_the_follow_up_key_stays_on_the_server(lila_item):
    item = ib.classify_item(lila_item, show_correct=False)
    served = ib.public_item(item, "en")
    assert "follow_up_key" not in served and served["source_fr"]
    payload = ib.public_payload({"recognize": {"classify": {"items": [item]}}}, "en")
    assert "follow_up_key" not in payload["recognize"]["classify"]["items"][0]


# ---------------------------------------------------------------------------
# T11 — no pseudo-scene; T3 — every drill says what to produce
# ---------------------------------------------------------------------------


def test_production_items_carry_no_pseudo_scene(lila_item):
    output = ib.output_item(lila_item, round_name="sentence", requirement={"label": "X"})
    assert output["prompt"] == 'Say in French: "Lila is looking for a big poster."'
    # QA-FORGE: a German learner never reads the English gloss; FORGE-DE: the
    # translate step comes back with the German meaning.
    assert output["prompt_l10n"]["de"] == "Sag auf Französisch: „Lila sucht ein großes Plakat.“"
    produce = ib.produce_block(lila_item, lila_item, requirement={"label": "X"})
    assert produce["prompt"].startswith("Write a short message in French")
    # A stored item written before WP-103 is served without its frame.
    stored = {
        "id": "x", "prompt": 'Romy texts you from the newsroom and wants a quick answer. Say in French: "Hi."',
        "prompt_l10n": {"de": "Romy schreibt dir aus der Redaktion und will schnell eine Antwort. Sag auf Französisch: „Hi.“"},
    }
    served = ib.public_item(stored, "en")
    assert served["prompt"] == 'Say in French: "Hi."'
    assert served["prompt_l10n"]["de"] == "Sag auf Französisch: „Hi.“"


def test_every_forge_drill_states_its_goal_in_the_learners_language(lila_item):
    build = ib.word_bank_item(lila_item)
    assert build["goal_native"] == 'Build: "Lila is looking for a big poster."'
    german = ib.public_item(build, "de")
    assert "Lila is looking" not in json.dumps(german, ensure_ascii=False)
    assert german["prompt"] == "Bau den Satz. Ein Wort brauchst du nicht."
    # FORGE-DE: the meaning cue is the German meaning.
    assert german["goal_native"] == "Bau den Satz: „Lila sucht ein großes Plakat.“"
    assert german["meaning_cue"] == "Lila sucht ein großes Plakat."
    assert ib.public_item(build, "fr")["meaning_cue"] is None
    fill = ib.fill_item(lila_item)
    assert fill["goal_native"] == 'Complete the sentence: "Lila is looking for a big poster."'
    repair = ib.transform_item(lila_item)
    assert repair["goal_native"].startswith("Correct it so that it says")
    assert repair["source_fr"] == repair["source"]
    say = ib.output_item(lila_item, round_name="sentence", requirement={"label": "X"})
    assert say["goal_native"] == 'Say in French: "Lila is looking for a big poster."'
    # A séance item written before WP-103 gets its goal from what it carries.
    legacy = ib.public_item(
        {"id": "wb", "prompt": "Build the sentence.", "meaning_cue": "I am here.", "tokens": ["Je"], "answer_tokens": ["Je"]},
        "en",
    )
    assert legacy["goal_native"] == 'Build: "I am here."'


def test_an_accepted_answer_is_right_at_once_and_stays_right(db_session, monkeypatch):
    """Through the submit path: the example answer is «right» on the spot (verdict
    correct, no errata), and the model's later partial reading changes nothing shown."""

    from tests.test_atelier import _FakeLLMService
    from tests.test_forge_instant_feedback import _sentence_session

    user, concept, session = _sentence_session(db_session, monkeypatch)
    fake = _FakeLLMService({"verdict": "partial", "score_0_4": 2, "errata": [
        {"display_label": "Style", "learner_text": "je t'appellerai", "corrected_target": "je vous appellerai",
         "why_wrong": "You could keep vous.", "repair_hint": "", "severity": 1, "recurring": False,
         "task_error_type": "register"},
    ]})
    service = AtelierCorrectionService(db_session, llm_service=fake)
    attempt = service.submit_attempt(
        session=session, user=user, concept=concept, round_name="sentence", mode="sentence",
        exercise_id="FR_B1_COND_001:sentence", answer_payload={"text": "Si je finis tôt, je t'appellerai."},
    )
    shown = attempt.correction_payload
    assert shown["local_status"] == "right" and shown["assessment_status"] == "provisional"
    assert attempt.verdict == "correct" and shown["errata"] == []
    landed = service.run_ai_review_for_attempt(attempt.id)
    assert landed.verdict == "correct"
    assert landed.correction_payload["second_check"]["verdict_changed"] is False
    assert landed.correction_payload["errata"] == []
    assert landed.correction_payload["style_notes_native"] == ["You could keep vous."]
