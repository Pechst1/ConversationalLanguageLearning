"""#174: the answer bank. A reviewed variant of a key is right, a reviewed wrong answer stays wrong.

Each example issue is a case in both directions, with the flag on and with it off (main's
behaviour). The mechanics run on a small bank written here; the stored bank's own entries
are read in ``test_stored_bank_*``.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.config import settings
from app.services import answer_bank
from app.services.answer_acceptance import feedback_note, judge, judge_repair

CLE_KEY = "Ma clé est dans mon sac, avec mes lunettes."
CLE_SOURCE = "Mon clé est dans mon sac, avec mes lunettes."

BANK = {
    "repair_pairs": {
        "entries": {
            "FR2_A11_ON_NOUS#x": {
                "hash": "h",
                "kind": "fix_the_mistake",
                "key": "Romy et moi, on envoie une lettre.",
                "accepted": ["Romy et moi, nous envoyons une lettre.", "Romy et moi envoyons une lettre."],
                "wrong": [
                    {
                        "form": "Romy et moi, on envoyons une lettre.",
                        "why_en": "After on the verb takes the il/elle ending.",
                        "why_de": "Nach on steht das Verb in der il/elle-Form.",
                    },
                    {
                        "form": "Romy et moi, on envoie une letre.",
                        "why_en": "A word is misspelt.",
                        "why_de": "Ein Wort ist falsch geschrieben.",
                    },
                    {
                        "form": "Romy et moi, on envoie une léttre.",
                        "why_en": "Only an accent: the accent rule judges this, not the bank.",
                        "why_de": "Nur ein Akzent.",
                    },
                ],
            },
            "FR2_A21_PC_ETRE#y": {
                "hash": "h",
                "kind": "fix_the_mistake",
                "key": "Tu es arrivée à la gare samedi dernier.",
                "accepted": ["Tu es arrivé à la gare samedi dernier."],
                "wrong": [
                    {
                        "form": "Tu as arrivé à la gare samedi dernier.",
                        "why_en": "Arriver takes être in the passé composé.",
                        "why_de": "Arriver bildet das passé composé mit être.",
                    },
                    {
                        "form": "Tu es arrivés à la gare samedi dernier.",
                        "why_en": "The participle says arrivée here.",
                        "why_de": "Leaks the answer.",
                    },
                ],
            },
            "OTHER#z": {
                "hash": "h",
                "kind": "fix_the_mistake",
                "key": "Tu es arrivée à la gare samedi dernier.",
                "accepted": [],
                "wrong": [],
            },
            "CAUSE#c": {
                "hash": "h",
                "kind": "fix_the_mistake",
                "key": "Je reste parce qu'il pleut.",
                "accepted": ["Parce qu'il pleut, je reste."],
                "wrong": [],
            },
            "REJECTED#k": {
                "hash": "h",
                "kind": "fix_the_mistake",
                "key": "Im est au Mistral, Marin.",
                "key_rejected": True,
                "accepted": [],
                "wrong": [],
            },
        }
    },
    "season_words": {
        "entries": {
            "clé#w": {"hash": "h", "kind": "cloze_word", "key": "clé", "accepted": ["clef"], "wrong": [
                {"form": "clés", "why_en": "One key, not several.", "why_de": "Ein Schlüssel, nicht mehrere."},
            ]},
        }
    },
}


@pytest.fixture
def bank(monkeypatch):
    monkeypatch.setattr(settings, "ANSWER_BANK_ENABLED", True)
    monkeypatch.setattr(answer_bank, "load_bank", lambda source: BANK.get(source, {}))
    answer_bank._index.cache_clear()
    yield
    answer_bank._index.cache_clear()


@pytest.fixture
def bank_off(monkeypatch):
    monkeypatch.setattr(settings, "ANSWER_BANK_ENABLED", False)
    monkeypatch.setattr(answer_bank, "load_bank", lambda source: BANK.get(source, {}))
    answer_bank._index.cache_clear()
    yield
    answer_bank._index.cache_clear()


# --- #966: «clef» is «clé» -------------------------------------------------------------


@pytest.mark.parametrize("answer", ["Ma clef est dans mon sac, avec mes lunettes.", "ma clef est dans mon sac avec mes lunettes"])
def test_966_clef_is_right_in_the_fix(bank, answer):
    assert judge(answer, [CLE_KEY], typo=False).correct
    assert judge_repair(answer, CLE_SOURCE, [CLE_KEY], typo=False).correct


def test_966_the_mistake_itself_stays_wrong(bank):
    assert not judge("Mon clef est dans mon sac, avec mes lunettes.", [CLE_KEY], typo=False).correct
    assert not judge_repair(CLE_SOURCE, CLE_SOURCE, [CLE_KEY], typo=False).correct


def test_966_flag_off_is_mains_behaviour(bank_off):
    assert not judge("Ma clef est dans mon sac, avec mes lunettes.", [CLE_KEY], typo=False).correct


def test_966_the_word_card_takes_clef_with_or_without_its_article(bank):
    assert judge("clef", ["clé"]).correct
    assert judge("la clef", ["la clé"], article_optional=True).correct
    # «clés» stays wrong; the one contract already names it (a ``form`` miss), so its note stands.
    verdict = judge("clés", ["clé"])
    assert not verdict.correct and verdict.note == "form"


# --- #606: «nous» for «X et moi, on …» ---------------------------------------------------


@pytest.mark.parametrize("answer", ["Romy et moi, nous envoyons une lettre.", "Romy et moi envoyons une lettre"])
def test_606_nous_is_right_where_the_bank_lists_it(bank, answer):
    assert judge(answer, ["Romy et moi, on envoie une lettre."], typo=False).correct


def test_606_on_with_the_nous_ending_stays_wrong_with_its_reason(bank):
    verdict = judge("Romy et moi, on envoyons une lettre.", ["Romy et moi, on envoie une lettre."])
    assert not verdict.correct and verdict.note == "bank"
    assert feedback_note(verdict, "en") == "After on the verb takes the il/elle ending."


# --- #723's class: a lenient comparison does not let a listed wrong answer through ------


def test_723_typo_tolerance_no_longer_accepts_a_listed_wrong_answer(monkeypatch):
    monkeypatch.setattr(answer_bank, "load_bank", lambda source: BANK.get(source, {}))
    answer_bank._index.cache_clear()
    key = ["Romy et moi, on envoie une lettre."]
    monkeypatch.setattr(settings, "ANSWER_BANK_ENABLED", False)
    assert judge("Romy et moi, on envoie une letre.", key, typo=True).correct  # main forgives it as a typo
    monkeypatch.setattr(settings, "ANSWER_BANK_ENABLED", True)
    assert not judge("Romy et moi, on envoie une letre.", key, typo=True).correct
    answer_bank._index.cache_clear()


def test_723_a_key_the_judge_refused_is_never_indexed(bank):
    assert answer_bank.bank_verdict("Il est au Mistral, Marin.", ["Im est au Mistral, Marin."]) is None


def test_an_accent_only_wrong_form_is_left_to_the_accent_rule(bank):
    verdict = judge("Romy et moi, on envoie une léttre.", ["Romy et moi, on envoie une lettre."])
    assert verdict.note != "bank"


# --- #926 / two items, one key: the strict merge ----------------------------------------


def test_926_two_items_with_one_key_accept_only_what_both_accept(bank):
    # PR #933 makes the item say which «you» it means; the bank never widens past an item that disagrees.
    assert not judge("Tu es arrivé à la gare samedi dernier.", ["Tu es arrivée à la gare samedi dernier."], typo=False).correct
    verdict = judge("Tu as arrivé à la gare samedi dernier.", ["Tu es arrivée à la gare samedi dernier."])
    assert verdict.note == "bank" and not verdict.correct


# --- the owner's rule: no solution before a retry --------------------------------------


def test_a_reason_that_shows_the_answer_is_not_shown(bank):
    hit = answer_bank.bank_verdict("Tu es arrivés à la gare samedi dernier.", ["Tu es arrivée à la gare samedi dernier."])
    assert hit is not None and not hit.correct
    assert answer_bank.why_for_learner(hit, ["Tu es arrivée à la gare samedi dernier."], "en") is None
    hit = answer_bank.bank_verdict("Tu as arrivé à la gare samedi dernier.", ["Tu es arrivée à la gare samedi dernier."])
    assert answer_bank.why_for_learner(hit, [], "de") == "Arriver bildet das passé composé mit être."


def test_a_contract_note_is_kept_over_the_banks(bank):
    # «arrivés» for «arrivée» is a ``form`` miss the one contract names itself.
    verdict = judge("Tu es arrivés à la gare samedi dernier.", ["Tu es arrivée à la gare samedi dernier."])
    assert not verdict.correct and verdict.note == "form"


def test_flag_off_the_bank_says_nothing(bank_off):
    assert answer_bank.bank_verdict("clef", ["clé"]) is None
    assert judge("Romy et moi, on envoyons une lettre.", ["Romy et moi, on envoie une lettre."]).note != "bank"


# --- an order drill takes a reviewed word order, with the same tiles -----------------


def _tiles() -> dict:
    words = ["Je", "reste", "parce", "qu'il", "pleut", "."]
    return {
        "solution_fr": "Je reste parce qu'il pleut.",
        "correct_tile_order": [f"t{i}" for i in range(len(words))],
        "options": [{"id": f"t{i}", "text_fr": word} for i, word in enumerate(words)],
    }


def test_order_drill_takes_the_banked_order(bank):
    from app.services.journey_answer_key import tiles_spell_an_answer

    assert tiles_spell_an_answer(_tiles(), ["t2", "t3", "t4", "t0", "t1", "t5"])
    assert not tiles_spell_an_answer(_tiles(), ["t1", "t0", "t2", "t3", "t4", "t5"])


def test_order_drill_flag_off_keeps_the_stored_order(bank_off):
    from app.services.journey_answer_key import tiles_spell_an_answer

    assert not tiles_spell_an_answer(_tiles(), ["t2", "t3", "t4", "t0", "t1", "t5"])


# --- #927: the end sheet lists the learner's right line ---------------------------------


def _attempt(text: str) -> SimpleNamespace:
    item = {"expected_answer": "Vous avez cherché les clés hier.", "source_fr": "Vous avez chercher les clés hier."}
    return SimpleNamespace(
        correction_payload={},
        prompt_payload={"items": [item]},
        verdict="correct",
        answer_payload={"text": text},
        round="transform",
        mode="transform",
    )


def test_927_a_right_whole_line_is_the_learners_words(monkeypatch):
    from app.services.atelier import AtelierSRSService

    monkeypatch.setattr(settings, "ANSWER_BANK_ENABLED", True)
    assert AtelierSRSService._forge_proof_line(_attempt("Tu as cherché les clés hier.")) == ("Tu as cherché les clés hier.", False)
    # A right part stands for the key it completed.
    assert AtelierSRSService._forge_proof_line(_attempt("cherché")) == ("Vous avez cherché les clés hier.", False)
    monkeypatch.setattr(settings, "ANSWER_BANK_ENABLED", False)
    assert AtelierSRSService._forge_proof_line(_attempt("Tu as cherché les clés hier.")) == ("Vous avez cherché les clés hier.", False)


# --- the stored bank ---------------------------------------------------------------------


def test_stored_bank_is_well_formed():
    for source in answer_bank.SOURCES:
        bank = answer_bank.load_bank(source)
        for item_id, entry in (bank.get("entries") or {}).items():
            assert entry["key"] and entry["hash"], item_id
            accepted = {answer_bank._fold(form) for form in [entry["key"], *entry["accepted"]]}
            for wrong in entry["wrong"]:
                assert answer_bank._fold(wrong["form"]) not in accepted, (source, item_id, wrong)
                assert wrong["why_en"].strip() and wrong["why_de"].strip(), (source, item_id)
    json.dumps(answer_bank.coverage())


# --- the stored bank, read as the judges read it ----------------------------------------


@pytest.fixture
def stored(monkeypatch):
    monkeypatch.setattr(settings, "ANSWER_BANK_ENABLED", True)
    answer_bank.reset_cache()
    yield
    answer_bank.reset_cache()


def test_stored_966_clef_is_a_reviewed_spelling_of_cle(stored):
    assert judge("clef", ["clé"]).correct


def test_stored_variant_is_right_and_off_is_mains(stored, monkeypatch):
    key = ["Comme il pleut, je reste."]
    assert judge("Puisqu'il pleut, je reste.", key, typo=False).correct
    monkeypatch.setattr(settings, "ANSWER_BANK_ENABLED", False)
    assert not judge("Puisqu'il pleut, je reste.", key, typo=False).correct


def test_stored_723_class_the_rules_own_trap_is_no_typo(stored, monkeypatch):
    key = ["Ils prennent le bus."]
    verdict = judge("Ils prendent le bus.", key, typo=True)
    assert not verdict.correct and verdict.note == "bank"
    assert "prennent" not in (feedback_note(verdict, "en") or "")
    monkeypatch.setattr(settings, "ANSWER_BANK_ENABLED", False)
    assert judge("Ils prendent le bus.", key, typo=True).correct  # main forgave the rule's own trap as a typo
