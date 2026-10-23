"""Forge answer acceptance, 2026-10-23 live walk (#296, #295, #297).

One flaw behind all three (root cause #174): a right answer was judged against one
stored string, and nothing checked that the string was what the learner was asked
for.

* #296 — «Build: "Marin asks how old you are. I am 41 years old."» stored both
  sentences as the target, so the learner who built only «J'ai quarante et un ans.»
  was refused. A tile build's target is now the one sentence the prompt quotes; the
  context sentence is said before the quote.
* #295 — English «they» / «you» name no gender and no politeness, but the key kept
  one French person. Every person the English allows is now an accepted answer, and
  a note addressed to the item's author never reaches the learner.
* #297 — «gus a un telephone dans le salon» was labelled «Word order»: the order
  check treated an accent as a different word. A missing accent is now named as an
  accent (and accepted), never as an order.
"""

from __future__ import annotations

import re

import pytest

from app.services import forge_grading as grading
from app.services import item_bank as ib
from app.services.atelier import AtelierCorrectionService

_SENTENCE_END = re.compile(r"[.!?…](?:\s+|$)")


def _sentences(text: str) -> int:
    plain = re.sub(r"\b(M|MM|Mme|Mlle|Dr|Mr|Mrs|Ms)\.", r"\1", str(text))
    return len(_SENTENCE_END.findall(plain.strip() + " "))


def _quoted(goal: str) -> str:
    match = re.search(r'["“„«]\s*(.+?)\s*["”“»]', goal)
    assert match, f"the build goal quotes no sentence: {goal!r}"
    return match.group(1)


def _frame_item(unit: str, frame_id: str, predicate=lambda item: True, *, count: int = 400) -> ib.BankItem:
    bank = ib.default_bank()
    for seed in range(40):
        for item in bank.generate(unit, count, seed=f"night-{seed}"):
            if item.frame_id == frame_id and predicate(item):
                return item
    raise AssertionError(f"no {frame_id} item in {unit} matched")


# ---------------------------------------------------------------------------
# #296 — the build target is the sentence the prompt quotes
# ---------------------------------------------------------------------------


def test_the_age_build_asks_for_and_accepts_only_the_sentence_it_quotes():
    item = _frame_item("FR2_A11_AVOIR", "avoir-age-ask")
    assert _sentences(item.sentence) == 2  # the frame is a question and its answer
    built = ib.word_bank_item(item)
    assert built is not None
    # What the learner was asked for is quoted, and only that.
    assert _sentences(_quoted(built["goal_native"])) == 1
    assert built["correct_answer"].startswith("J'ai ") and built["correct_answer"].endswith(" ans.")
    assert _sentences(built["correct_answer"]) == 1
    assert "demande ton âge" not in " ".join(built["answer_tokens"])
    # The question that sets the scene is read before the quote, not built.
    assert built["goal_native"].startswith("Marin asks how old you are.") or "asks how old you are" in built["goal_native"]
    assert built["meaning_cue"].startswith("I am ")


def test_a_build_of_only_the_answer_sentence_is_marked_right(db_session):
    item = _frame_item("FR2_A11_AVOIR", "avoir-age-ask")
    built = ib.word_bank_item(item, lesson_external_id="FR2_A11_AVOIR")
    assert built is not None
    service = AtelierCorrectionService(db_session)
    correction = service.correct(
        concept=None,
        round_name="recognize",
        mode="word_bank",
        exercise_id=f"X:word_bank:{built['id']}",
        prompt_payload={"items": [built]},
        # The learner builds what the prompt quotes: the answer to the question.
        answer_payload={"answers": {built["id"]: ib._tokens(item.sentence.split("? ")[-1].split(". ")[-1])}},
    )
    assert correction["verdict"] == "correct", correction


def test_no_build_of_a_day_targets_more_than_the_prompt_quotes():
    """The guard: across every unit, a tile build's target has no more sentences than
    the prompt's quotation marks hold. An exchange is built as its answer alone (the
    context is read before the quote) or, when the answer is too short to be a build,
    as the whole exchange (all of it quoted)."""

    bank = ib.default_bank()
    checked = answer_only = whole = 0
    for unit in sorted(ib.template_units()):
        for item in bank.generate(unit, 60, seed="guard-296"):
            built = ib.word_bank_item(item)
            if built is None:
                continue
            checked += 1
            quote = _quoted(built["goal_native"])
            assert _sentences(built["correct_answer"]) <= _sentences(quote), (unit, built["goal_native"], built["correct_answer"])
            assert ib.normalize(" ".join(built["answer_tokens"]).replace(" .", ".")) == ib.normalize(
                built["correct_answer"]
            ), (unit, built["answer_tokens"])
            if _sentences(item.sentence) > 1 and built["correct_answer"] != item.sentence:
                # An exchange built as its answer: the quote is that answer alone.
                answer_only += 1
                assert _sentences(quote) == 1 and _sentences(built["correct_answer"]) == 1, (unit, built["goal_native"])
            elif _sentences(item.sentence) > 1:
                whole += 1
                assert _sentences(quote) == _sentences(built["correct_answer"]), (unit, built["goal_native"])
    assert checked > 500 and answer_only > 20 and whole > 20


# ---------------------------------------------------------------------------
# #295 — every person the English allows is right
# ---------------------------------------------------------------------------

_SIBLING = {"ils": "elles", "elles": "ils", "tu": "vous", "vous": "tu"}


def _subject_items():
    bank = ib.default_bank()
    out = []
    for unit in sorted(ib.template_units()):
        for item in bank.generate(unit, 40, seed="guard-295"):
            for _slot, entry in item.bindings:
                if "pron" in (entry.get("tags") or []) and entry.get("en") in ("they", "you"):
                    said = re.findall(r"[\wÀ-ÿ']+", item.sentence.casefold())
                    if entry.get("fr") in _SIBLING and entry["fr"] in said and re.search(rf"\b{entry['en']}\b", item.en, re.I):
                        out.append((item, entry))
    return out


def test_every_they_and_you_item_lists_the_other_person_or_names_its_own():
    """The done-when: the English either names the person («you (informal)») or the
    key lists the other one as a variant."""

    pairs = _subject_items()
    assert len(pairs) > 40
    missing, listed, named = [], 0, 0
    for item, entry in pairs:
        sibling = _SIBLING[entry["fr"]]
        words = {word for sentence in item.accepted for word in re.findall(r"[\wÀ-ÿ]+", sentence.casefold())}
        if sibling in words:
            listed += 1
        elif re.search(r"\((?:informal|formal or plural|m\.|f\.)\)", item.en):
            named += 1
        else:
            missing.append((item.sentence, item.en, sibling))
    assert not missing, missing[:5]
    assert listed > 20


def test_a_frame_that_writes_tu_itself_names_the_person_in_english():
    item = _frame_item("FR2_A11_JE_VOUDRAIS", "tu-veux")
    assert item.en.startswith("Do you (informal) want")
    polite = _frame_item("FR2_A11_JE_VOUDRAIS", "voulez-vous")
    assert "you (formal or plural)" in polite.en


def test_ils_and_elles_aident_both_pass_the_fill(db_session):
    item = _frame_item(
        "FR2_A11_ER_VERBS", "er-comp", lambda it: it.en.startswith("They help") and it.target in {"Ils aident", "Elles aident"}
    )
    fill = ib.fill_item(item, lesson_external_id="FR2_A11_ER_VERBS")
    assert fill is not None
    service = AtelierCorrectionService(db_session)
    for answer in ("Ils aident", "Elles aident", "ils aident", "elles aident."):
        correction = service.correct(
            concept=None,
            round_name="recognize",
            mode="fill",
            exercise_id=f"X:fill:{fill['id']}",
            prompt_payload={"items": [fill]},
            answer_payload={"answers": {fill["id"]: answer}},
        )
        assert correction["verdict"] == "correct", (answer, correction)


def test_tu_and_vous_dinez_both_pass():
    item = _frame_item(
        "FR2_A11_ER_VERBS", "er-comp", lambda it: it.en.startswith("You have dinner") and it.target in {"Tu dînes", "Vous dînez"}
    )
    keys = ib.target_answers(item)
    assert {"Tu dînes", "Vous dînez"} <= set(keys)


def test_the_tutor_note_to_the_prompt_author_never_reaches_the_learner(db_session):
    service = AtelierCorrectionService(db_session)
    relecture = {
        "verdict": "partial",
        "score_0_4": 2,
        "corrected_answer": "Vous dînez au Mistral.",
        "concept_hits": [],
        "missing_targets": [],
        "errata": [
            {
                "display_label": "Subject",
                "learner_text": "Tu dînes",
                "corrected_target": "Vous dînez",
                "why_wrong": (
                    "“Tu dînes” is a valid present-tense form, but the prompt gives no subject to "
                    "determine the expected person. Add a subject or other context to the prompt so "
                    "only one answer is correct."
                ),
                "repair_hint": "Add a subject to the prompt.",
                "severity": 1,
                "task_error_type": "agreement",
            }
        ],
    }
    ai = service._normalize_llm_correction(
        relecture, concepts=[], fallback={"errata": []}, corrected_answer_mode="text", model="fake"
    )
    assert ai["errata"] == []
    assert ai["verdict"] == "correct"
    assert grading.notes_native([{"why_wrong": relecture["errata"][0]["why_wrong"]}]) == []
    from app.services.forge_grading import is_author_note

    assert is_author_note("Add a subject or other context to the prompt.")
    assert not is_author_note("«grand» goes before the noun: «un grand poster».")


# ---------------------------------------------------------------------------
# #297 — an accent, a capital and a full stop are never «Word order»
# ---------------------------------------------------------------------------

GUS = "Gus a un téléphone dans le salon."


@pytest.mark.parametrize(
    ("typed", "named"),
    [
        ("gus a un telephone dans le salon", "accent"),
        ("Gus a un telephone dans le salon.", "accent"),
        ("gus a un téléphone dans le salon.", "capital"),
        ("Gus a un téléphone dans le salon", "full stop"),
    ],
)
def test_a_missing_accent_capital_or_stop_is_never_word_order(db_session, typed, named):
    service = AtelierCorrectionService(db_session)
    local_check = grading.production_local_check(None, typed, accepted=[GUS])
    local = {"verdict": "partial", "score_0_4": 2.0, "local_status": local_check["local_status"], "errata": []}
    if local_check["local_status"] == grading.LOCAL_RIGHT:
        local.update({"verdict": "correct", "score_0_4": 4.0})
    ai = {"verdict": "partial", "score_0_4": 2.0, "corrected_answer": GUS, "errata": []}
    final = service._merge_relecture("sentence", local, ai, learner_text=typed, accepted=[GUS])
    shown = " ".join([*final["notes_native"], *[str(e.get("display_label")) for e in final["errata"]]]).lower()
    assert "word order" not in shown and "not in this order" not in shown, final
    assert not any(e.get("task_error_type") == "word_order" for e in final["errata"]), final
    assert final["verdict"] in {"correct", "accepted"}, final
    if named == "accent":
        assert "téléphone" in shown, final


def test_reordering_still_names_a_real_reorder():
    moved = grading.reordering_correction("Lila cherche un poster grand", ["Lila cherche un grand poster."])
    assert moved is not None and moved[1]["task_error_type"] == "word_order"
    assert grading.reordering_correction("gus a un telephone dans le salon", [GUS]) is None
