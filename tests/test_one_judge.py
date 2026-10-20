"""#174 / #146: one judge for right and wrong.

Every keyed La Forge item, the model-judged free use and every saved error decide
"right" through ``app.services.answer_acceptance``. A correct sentence that differs
from the stored key only in typography, in an authored word order, or by swapping
one right form for another is accepted, never saved as an error, and a miss whose
rule form is right never cites the rule. Real errors and missing accents on a
spelling unit stay wrong.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.services import item_bank as ib
from app.services.answer_acceptance import is_real_correction
from app.services.atelier import AtelierCorrectionService, _drop_noop_errata

ETRE = "FR2_A11_ETRE"


def _bank_item(unit: str, frame_id: str, *, contains: str | None = None) -> ib.BankItem:
    bank = ib.default_bank()
    for seed in range(400):
        for item in bank.generate(unit, 12, seed=seed):
            if item.frame_id == frame_id and (contains is None or contains in item.sentence):
                return item
    raise AssertionError(f"no {frame_id} item")


def _concept(external_id: str = ETRE):
    from app.db.models.grammar import GrammarConcept

    return GrammarConcept(id=1, external_id=external_id, name="Je suis, tu es", level="A1", category="Verbs")


def _build(item: dict, answer: str) -> dict:
    tokens = answer.rstrip(".").split() + ["."]
    service = AtelierCorrectionService(None)
    service.explanation_language = "de"
    return service._correct_recognize(_concept(), "word_bank", {"items": [item]}, {"answers": {item["id"]: tokens}})


@pytest.fixture(scope="module")
def place_with() -> dict:
    item = _bank_item(ETRE, "etre-place-with")
    payload = ib.word_bank_item(item, lesson_external_id=ETRE)
    assert payload is not None
    return payload


# --- #173: a tile build in another authored order ---------------------------------


def test_the_frame_lists_the_other_adjunct_order(place_with: dict) -> None:
    key = place_with["correct_answer"]
    others = [answer for answer in place_with["accepted_answers"] if answer != key]
    assert others, "etre-place-with must list «… avec C P.» as also right"
    assert all(" avec " in other for other in others)


def test_a_tile_build_in_the_other_order_is_right(place_with: dict) -> None:
    other = next(answer for answer in place_with["accepted_answers"] if answer != place_with["correct_answer"])
    result = _build(place_with, other)
    assert result["verdict"] == "correct"
    assert result["errata"] == []
    assert result["corrected_answer"][place_with["id"]] == other


def test_an_order_only_miss_says_order_and_never_cites_the_rule(place_with: dict) -> None:
    words = place_with["correct_answer"].rstrip(".").split()
    # Keep «Ils sont» (the rule's form) in place, scramble the rest into a wrong order.
    head, rest = words[:2], words[2:]
    wrong = " ".join([*head, *reversed(rest)]) + "."
    assert place_with["target_span"].lower() in " ".join(head).lower()
    result = _build(place_with, wrong)
    assert result["verdict"] == "incorrect"
    [erratum] = result["errata"]
    assert erratum["task_error_type"] == "word_order"
    assert "Regel" not in erratum["why_wrong"]
    assert "Reihenfolge" in erratum["why_wrong"]


def test_a_wrong_form_still_cites_the_rule(place_with: dict) -> None:
    span = place_with["target_span"]
    wrong_form = place_with["correct_answer"].replace(span, "es" if span != "es" else "sont", 1)
    result = _build(place_with, wrong_form)
    assert result["verdict"] == "incorrect"
    [erratum] = result["errata"]
    assert erratum["task_error_type"] != "word_order"
    assert "Regel" in erratum["why_wrong"]


def test_when_the_order_breaks_the_rule_form_the_rule_is_cited() -> None:
    """Negation: «ne … pas» around the verb is the rule; an order that breaks the
    form span is a rule miss, not a word-order note (review of #179, point 4)."""

    from app.services.atelier import _form_right_only_order_differs

    item = {"target_span": "ne mange pas"}
    assert not _form_right_only_order_differs(item, "Je ne pas mange de pain.", "Je ne mange pas de pain.")
    assert _form_right_only_order_differs(item, "De pain je ne mange pas.", "Je ne mange pas de pain.")


def test_other_words_are_still_wrong(place_with: dict) -> None:
    result = _build(place_with, place_with["correct_answer"].replace(" avec ", " sans ", 1))
    assert result["verdict"] == "incorrect"


# --- #166: the model-judged free use -----------------------------------------------


def _relecture(errata: list[dict], verdict: str = "partial") -> dict:
    payload = {
        "verdict": verdict,
        "score_0_4": 2.0,
        "corrected_answer": "Ils sont au Luxembourg cette semaine.",
        "concept_hits": [],
        "missing_targets": [],
        "errata": errata,
        "lexical_gaps": [],
    }
    return AtelierCorrectionService(None)._normalize_llm_correction(
        payload, concepts=[], fallback={"errata": []}, corrected_answer_mode="text", model="fake"
    )


@pytest.mark.parametrize(
    "learner",
    [
        "ils sont au Luxembourg cette semaine",
        "Ils sont au Luxembourg cette semaine",
        "ils sont au luxembourg cette semaine.",
    ],
)
def test_a_typography_only_complaint_is_not_a_failing_verdict(learner: str) -> None:
    result = _relecture(
        [
            {
                "learner_text": learner,
                "corrected_target": "Ils sont au Luxembourg cette semaine.",
                "why_wrong": "Capital letter and full stop.",
                "task_error_type": "spelling",
            }
        ]
    )
    assert result["errata"] == []
    assert result["verdict"] == "correct"
    assert result["score_0_4"] == 4.0


def test_an_intonation_question_is_not_corrected_to_an_inversion() -> None:
    result = _relecture(
        [
            {
                "learner_text": "Vous êtes disponible jeudi matin ?",
                "corrected_target": "Êtes-vous disponible jeudi matin ?",
                "why_wrong": "Inversion is required.",
                "task_error_type": "question_form",
            }
        ]
    )
    assert result["errata"] == []
    assert result["verdict"] == "correct"


def test_a_real_error_keeps_the_failing_verdict() -> None:
    result = _relecture(
        [
            {
                "learner_text": "ils est au Luxembourg",
                "corrected_target": "ils sont au Luxembourg",
                "why_wrong": "ils → sont",
                "task_error_type": "grammar_target",
            }
        ]
    )
    assert len(result["errata"]) == 1
    assert result["verdict"] == "partial"


def test_a_model_miss_with_no_errata_at_all_is_left_alone() -> None:
    """Off task with nothing to correct (wrong language, wrong form missing) stays
    the model's call: only dropped no-op corrections promote the verdict."""

    assert _relecture([], verdict="incorrect")["verdict"] == "incorrect"


def test_a_missing_accent_on_a_spelling_unit_stays_a_correction() -> None:
    kept, dropped = _drop_noop_errata(
        [{"learner_text": "Nous commencons", "corrected_target": "Nous commençons", "task_error_type": "spelling"}]
    )
    assert len(kept) == 1 and not dropped


# --- #93: no saved error for a right sentence ------------------------------------


@pytest.mark.parametrize(
    ("learner", "corrected", "real"),
    [
        ("ils sont au Luxembourg cette semaine", "Ils sont au Luxembourg cette semaine.", False),
        ("C'est à côté", "C’est à côté", False),
        ("Tu viens?", "Tu viens ?", False),
        ("Vous êtes disponible jeudi matin ?", "Êtes-vous disponible jeudi matin ?", False),
        ("Vous êtes disponible jeudi matin ?", "Est-ce que vous êtes disponible jeudi matin ?", False),
        ("la appartement", "l'appartement", True),
        ("Nous commencons", "Nous commençons", True),
        ("ils est", "ils sont", True),
    ],
)
def test_is_real_correction(learner: str, corrected: str, real: bool) -> None:
    assert is_real_correction(learner, corrected) is real


def test_a_right_sentence_is_never_saved_as_an_error(db_session) -> None:
    from app.db.models.error import UserError
    from app.db.models.user import User
    from app.services.error_memory import ErrorMemoryService

    user = User(id=uuid4(), email=f"one-judge-{uuid4().hex}@example.com", hashed_password="x", target_language="fr", native_language="de")
    db_session.add(user)
    db_session.flush()
    service = ErrorMemoryService(db_session)
    swap = {
        "display_label": "Question",
        "learner_text": "Vous êtes disponible jeudi matin ?",
        "corrected_target": "Êtes-vous disponible jeudi matin ?",
        "why_wrong": "Inversion",
        "severity": 2,
        "recurring": True,
        "task_error_type": "question_form",
    }
    assert service.record_erratum(user=user, erratum=swap, source_type="journal") is None
    real = {**swap, "learner_text": "la appartement", "corrected_target": "l'appartement", "task_error_type": "elision"}
    assert service.record_erratum(user=user, erratum=real, source_type="journal") is not None
    assert db_session.query(UserError).filter(UserError.user_id == user.id).count() == 1


# --- #235: a gap whose gloss names a noun with more than one French word ----------

UN_UNE = "FR2_A11_UN_UNE"


def _tableau_item() -> ib.BankItem:
    """«Marin has a painting in the living room.» as the bank poses it."""

    bank = ib.default_bank()
    frame = next(f for f in bank.frames(UN_UNE) if f.frame_id == "unune-has")
    bindings = {
        "C": next(e for e in bank.lex.pool("cast") if "Marin" in str(e.get("fr"))),
        "N": next(e for e in bank.lex.pool("noun") if e.get("id") == "tableau"),
        "R": next(e for e in bank.lex.pool("noun") if e.get("fr") == "salon"),
    }
    return bank.render(frame, bindings)


def _fill(item: ib.BankItem, answer: str) -> dict:
    payload = ib.fill_item(item, lesson_external_id=UN_UNE)
    assert payload is not None
    service = AtelierCorrectionService(None)
    service.explanation_language = "en"
    return service._correct_recognize(
        _concept(UN_UNE), "fill", {"items": [payload]}, {"answers": {payload["id"]: answer}}
    )


def test_gap_lists_both_nouns() -> None:
    item = _tableau_item()
    assert item.sentence == "Marin a un tableau dans le salon."
    assert "Marin a une peinture dans le salon." in item.accepted
    payload = ib.fill_item(item, lesson_external_id=UN_UNE)
    assert payload["correct_answer"] == "un tableau"
    assert set(payload["accepted_answers"]) == {"un tableau", "une peinture"}


@pytest.mark.parametrize("answer", ["une peinture", "Une peinture", "une  peinture.", "un tableau", "un Tableau"])
def test_other_noun_ok(answer: str) -> None:
    result = _fill(_tableau_item(), answer)
    assert result["verdict"] == "correct", result["errata"]
    assert result["errata"] == []


def test_wrong_article() -> None:
    result = _fill(_tableau_item(), "un peinture")
    assert result["verdict"] == "incorrect"
    [erratum] = result["errata"]
    assert erratum["corrected_target"] == "une peinture"
    # The noun was allowed: the miss is about the article's gender, not «this item
    # needs un tableau», and it names the form that goes with the noun typed.
    assert "un tableau" not in erratum["why_wrong"]
    assert "“une peinture”" in erratum["why_wrong"]
    assert "masculine or feminine" in erratum["why_wrong"]


def test_gloss_mates_decided() -> None:
    """The cause of #235: the bank poses «a painting» and keys one French noun. The
    core lexicon knows another noun glossed the same («peinture»); each such pair is
    either accepted (``alt_fr``) or reviewed as a different thing (``distinct_fr``),
    so a new noun cannot ship with a second right answer nobody listed."""

    import json

    from app.services.answer_acceptance import fold_all

    core = json.loads((ib.TEMPLATE_DIR.parent / "lexical" / "fr_core_lexicon.json").read_text(encoding="utf-8"))["lemmas"]
    by_gloss: dict[str, set[str]] = {}
    for lemma, entry in core.items():
        if entry.get("pos") != "noun":
            continue
        for segment in (entry.get("gloss") or {}).get("en", "").split(";"):
            by_gloss.setdefault(segment.strip().lower(), set()).add(fold_all(lemma))
    lexicon = json.loads((ib.TEMPLATE_DIR / "lexicon.json").read_text(encoding="utf-8"))
    undecided: list[str] = []
    for noun in lexicon["nouns"]:
        own = {fold_all(noun["fr"]), fold_all(noun.get("lemma") or noun["fr"])}
        decided = {fold_all(alt["fr"] if isinstance(alt, dict) else alt) for alt in noun.get("alt_fr") or []}
        decided |= {fold_all(word) for word in noun.get("distinct_fr") or []}
        for mate in sorted(by_gloss.get(str(noun["en"]).lower(), set()) - own - decided):
            undecided.append(f"{noun['fr']} ({noun['en']}) / {mate}")
    assert not undecided, undecided
