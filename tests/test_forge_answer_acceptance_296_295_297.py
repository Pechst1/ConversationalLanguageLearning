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
  check treated an accent as a different word. A free answer's accent is now read
  as the keyed rungs read it: a spelling accent is accepted and named, an accent
  that is grammar or meaning («mange» for «mangé», «a» for «à») is refused and
  named, never as an order.
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
    # The note goes; the model's reading of the learner's French is not overturned
    # by it. The key does that, for an answer it lists (see the merge test below).
    assert ai["verdict"] == "partial"
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


def _relecture(service, typed: str, accepted: list[str], *, accents: str = "lenient", ai_verdict: str = "partial") -> dict:
    """A free answer the local check could not call right, then the model's reading."""

    local_check = grading.production_local_check(None, typed, accepted=accepted)
    assert local_check["local_status"] == grading.LOCAL_CHECKING, typed
    local = {"verdict": "partial", "score_0_4": 2.0, "local_status": local_check["local_status"], "errata": []}
    ai = {
        "verdict": ai_verdict,
        "score_0_4": 4.0 if ai_verdict == "correct" else 3.0,
        "corrected_answer": accepted[0],
        "errata": [] if ai_verdict == "correct" else [
            {
                "display_label": "Word order",
                "learner_text": typed,
                "corrected_target": accepted[0],
                "why_wrong": "The words are right, but not in this order.",
                "task_error_type": "word_order",
            }
        ],
    }
    return service._merge_relecture("sentence", local, ai, learner_text=typed, accepted=accepted, accents=accents)


#: The review of the second attempt: an accent that is grammar or meaning was let
#: through as «correct». The keyed rungs refuse each of these (answer_acceptance).
_GRAMMAR_ACCENTS = [
    ("Elle a mange une pomme.", "Elle a mangé une pomme.", "mange", "mangé"),
    ("Gus à un téléphone dans le salon.", GUS, "à", "a"),
    ("Ou habites-tu ?", "Où habites-tu ?", "ou", "où"),
    ("Il a ete la", "Il a été là.", "la", "là"),
]


@pytest.mark.parametrize(("typed", "answer", "written", "expected"), _GRAMMAR_ACCENTS)
@pytest.mark.parametrize("ai_verdict", ["partial", "correct"])
def test_a_grammar_accent_in_a_free_answer_is_refused_and_named_as_the_accent(db_session, typed, answer, written, expected, ai_verdict):
    """Partial, whatever the model said; the accent is the one erratum, never «Word
    order»; the correction is the accepted answer."""

    final = _relecture(AtelierCorrectionService(db_session), typed, [answer], ai_verdict=ai_verdict)
    assert final["verdict"] == "partial" and 2.0 <= final["score_0_4"] <= 2.5, final
    assert [(e["learner_text"], e["corrected_target"], e["task_error_type"]) for e in final["errata"]] == [
        (written, expected, "orthography")
    ], final
    assert final["errata"][0]["display_label"] == "Accent"
    assert final["corrected_answer"] == answer
    shown = " ".join(final["notes_native"]).lower()
    assert "word order" not in shown and "not in this order" not in shown, final
    assert f"«{expected}»" in " ".join(final["notes_native"]), final
    assert "accent_notes" not in final


def test_a_spelling_accent_in_a_free_answer_is_still_right_and_named(db_session):
    final = _relecture(AtelierCorrectionService(db_session), "gus a un telephone dans le salon", [GUS])
    assert final["verdict"] == "correct" and final["score_0_4"] == 4.0 and final["errata"] == [], final
    assert final["notes_native"] == ["Right — watch the accent: «téléphone»."]
    assert final["corrected_answer"] == GUS


def test_an_item_that_tests_accents_refuses_a_spelling_accent_in_a_free_answer(db_session):
    service = AtelierCorrectionService(db_session)
    final = _relecture(service, "Je prefere le the.", ["Je préfère le thé."], accents="strict")
    assert final["verdict"] == "partial", final
    assert [(e["learner_text"], e["corrected_target"]) for e in final["errata"]] == [("prefere", "préfère")]
    # The same answer where the item does not test accents is right, accent named.
    lenient = _relecture(service, "Je prefere le the.", ["Je préfère le thé."])
    assert lenient["verdict"] == "correct" and lenient["errata"] == [], lenient
    service.explanation_language = "de"
    german = _relecture(service, "Il a ete la", ["Il a été là."])
    assert german["errata"][0]["display_label"] == "Akzent"
    assert german["notes_native"] == ["Hier ändert der Akzent das Wort: «là», nicht «la»."]


def test_a_refusal_names_the_accent_that_refuses_it():
    from app.services.answer_acceptance import judge

    verdict = judge("Il a ete la", ["Il a été là."])
    assert not verdict.correct and (verdict.learner_word, verdict.expected_word) == ("la", "là")
    accepted = judge("Il a ete malade", ["Il a été malade."])
    assert accepted.correct and accepted.expected_word == "été"


def test_the_relecture_reads_a_free_answer_with_the_items_accent_policy(db_session, monkeypatch):
    """Through the background relecture: the attempt's unit decides, as it does for
    the keyed rungs. A spelling unit refuses «tot» for «tôt»; another accepts it."""

    from app.services import answer_acceptance
    from tests.test_atelier import _FakeLLMService
    from tests.test_forge_instant_feedback import _sentence_session

    user, concept, session = _sentence_session(db_session, monkeypatch)
    model = {"verdict": "partial", "score_0_4": 3, "errata": [
        {"display_label": "Word order", "learner_text": "tot", "corrected_target": "tôt",
         "why_wrong": "The words are right, but not in this order.", "repair_hint": "", "severity": 1,
         "recurring": False, "task_error_type": "word_order"},
    ]}
    service = AtelierCorrectionService(db_session, llm_service=_FakeLLMService(model))

    def landed(text: str) -> dict:
        attempt = service.submit_attempt(
            session=session, user=user, concept=concept, round_name="sentence", mode="sentence",
            exercise_id="FR_B1_COND_001:sentence", answer_payload={"text": text},
        )
        assert attempt.correction_payload["local_status"] == grading.LOCAL_CHECKING
        return service.run_ai_review_for_attempt(attempt.id).correction_payload

    right = landed("Si je finis tot, je t'appellerai.")
    assert right["verdict"] == "correct" and right["errata"] == [], right
    assert right["notes_native"] == ["Right — watch the accent: «tôt»."]

    monkeypatch.setattr(answer_acceptance, "ACCENT_STRICT_UNITS", frozenset({concept.external_id}))
    refused = landed("Si je finis tot, je t'appellerai.")
    assert refused["verdict"] == "partial", refused
    assert [(e["learner_text"], e["corrected_target"], e["task_error_type"]) for e in refused["errata"]] == [
        ("tot", "tôt", "orthography")
    ]
    assert not any("order" in note.lower() for note in refused["notes_native"]), refused


def test_an_accepted_answer_the_model_doubted_over_the_prompt_is_right_after_the_merge(db_session):
    service = AtelierCorrectionService(db_session)
    local_check = grading.production_local_check(None, "Tu dînes", accepted=["Vous dînez", "Tu dînes"])
    assert local_check["local_status"] == grading.LOCAL_RIGHT
    local = {"verdict": "correct", "score_0_4": 4.0, "local_status": local_check["local_status"], "errata": []}
    ai = {"verdict": "partial", "score_0_4": 2.0, "corrected_answer": "Vous dînez", "errata": []}
    final = service._merge_relecture("sentence", local, ai, learner_text="Tu dînes", accepted=["Vous dînez", "Tu dînes"])
    assert final["verdict"] == "correct" and final["errata"] == [], final


_TUTOR_CORRECTIONS = [
    ("Tu viens pas ?", "Tu ne viens pas ?", "Include «ne» in the question: French negation needs «ne … pas»."),
    ("Où tu habites ?", "Où est-ce que tu habites ?", "Add «est-ce que» to the question to make it a full form."),
    ("Il part", "Il part à quelle heure ?", "Specify the time in the question with «à quelle heure»."),
    ("Je sais pas", "Je ne sais pas.", "Give the full form in the task: «je ne sais pas»."),
]


@pytest.mark.parametrize(("typed", "target", "why"), _TUTOR_CORRECTIONS)
def test_a_correction_of_the_learners_french_is_not_an_author_note(db_session, typed, target, why):
    """The review of the first attempt: «Include «ne» in the question» corrects the
    learner's French. Dropping it as a note to the author turned a wrong answer into
    «correct», 4.0 and recorded the missing negation as mastered."""

    assert not grading.is_author_note(why)
    service = AtelierCorrectionService(db_session)
    relecture = {
        "verdict": "partial",
        "score_0_4": 2,
        "corrected_answer": target,
        "concept_hits": [],
        "missing_targets": [],
        "errata": [
            {
                "display_label": "Form",
                "learner_text": typed,
                "corrected_target": target,
                "why_wrong": why,
                "repair_hint": "Say it in full.",
                "severity": 2,
                "task_error_type": "grammar",
            }
        ],
    }
    ai = service._normalize_llm_correction(
        relecture, concepts=[], fallback={"errata": []}, corrected_answer_mode="text", model="fake"
    )
    assert ai["verdict"] == "partial" and ai["score_0_4"] <= 2.5, ai
    assert [e["corrected_target"] for e in ai["errata"]] == [target], ai


def test_no_trap_and_no_wrong_sentence_of_any_item_is_in_its_key():
    """The review's note 2: widening the key with the other gender («je suis entrée»
    / «je suis entré») must not make a distractor right. Across every unit, no trap
    is an accepted gap-filler and no ✗ sentence is an accepted sentence."""

    bank = ib.default_bank()
    checked = widened = 0
    for unit in sorted(ib.template_units()):
        for item in bank.generate(unit, 150, seed="guard-295-keys"):
            checked += 1
            widened += len(item.accepted) > 1
            spans = {ib.normalize(span) for span in ib.target_answers(item)}
            accepted = {ib.normalize(sentence) for sentence in item.accepted}
            clashes = [t for t in item.traps if ib.normalize(t) in spans and ib.normalize(t) != ib.normalize(item.target)]
            clashes += [w for w in item.wrong_sentences if ib.normalize(w) in accepted]
            assert not clashes, (unit, item.frame_id, item.sentence, clashes)
    assert checked > 1000 and widened > 50


