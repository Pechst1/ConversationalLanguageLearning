"""Walk of 19 Nov 2026 (WALK3, «Found in this walk» 1–7): La Forge told learners that
right answers were wrong, and some feedback read as nonsense. One guard per item.

Item 1 (the retry judged on the old answer) is a client race and is guarded in
``web-frontend/lib/forge-verdict.test.js``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services import solution_gate
from app.services.answer_acceptance import is_preference_swap, is_real_correction, judge

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# 2 · «Wir sind heute Abend müde.» under «avoir»: «Nous sommes fatigués» was refused
# ---------------------------------------------------------------------------


def _lexicons() -> tuple[dict, dict]:
    base = ROOT / "app" / "data" / "grammar_templates"
    return (
        json.loads((base / "lexicon.json").read_text(encoding="utf-8")),
        json.loads((base / "lexicon_de.json").read_text(encoding="utf-8")),
    )


def test_avoir_state_german_gloss_is_not_an_etre_adjective():
    """A1 day 3: the German of «avoir sommeil» was «müde sein», the German of «être
    fatigué», so the right translation «Nous sommes fatigués ce soir.» was refused for
    a hidden constraint. No avoir-state complement may share its German with an
    adjective: the prompt must call for the avoir phrase."""

    _base, german = _lexicons()
    adjectives = {str(entry.get("deu") or "").casefold() for entry in german["adjectives"].values() if isinstance(entry, dict)}
    states = german["pools"]["avoir_state"]
    clashes = {fr: entry.get("deu") for fr, entry in states.items() if str(entry.get("deu") or "").casefold() in adjectives - {""}}
    assert not clashes, clashes
    assert states["sommeil"]["deu"] == "schläfrig"


def test_sommeil_item_asks_for_schlaefrig():
    from app.services import item_bank as ib

    bank = ib.ItemBank()
    seen = []
    for seed in range(40):
        for item in bank.generate("FR2_A11_AVOIR", 30, seed=f"walk3:{seed}"):
            if "sommeil" in item.sentence and item.de:
                seen.append(item.de)
        if seen:
            break
    assert seen
    for de in seen:
        assert "schläfrig" in de and "müde" not in de, de


# ---------------------------------------------------------------------------
# 3 · «Ils sont à Luxembourg» flagged for «au Luxembourg»
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("learner", "corrected"),
    [
        ("à Luxembourg", "au Luxembourg"),
        ("Ils sont à Luxembourg cette semaine.", "Ils sont au Luxembourg cette semaine."),
        ("Ils est au Luxembourg cette semaine.", "Ils est à Luxembourg cette semaine."),
        ("Je travaille à Québec.", "Je travaille au Québec."),
    ],
)
def test_city_and_country_of_one_name_is_no_mistake(learner, corrected):
    """A1 day 1: the model filed «à Luxembourg → au Luxembourg» (city vs country, both
    right); the error was replayed on day 4 and «sont à Luxembourg» refused. The swap is
    not a real correction, so it is neither shown, stored nor replayed."""

    assert is_preference_swap(learner, corrected)
    assert not is_real_correction(learner, corrected)


@pytest.mark.parametrize(
    ("learner", "corrected"),
    [
        ("à France", "en France"),
        ("à Portugal", "au Portugal"),
        ("Ils est à Luxembourg", "Ils sont au Luxembourg"),
    ],
)
def test_other_preposition_fixes_stay_real(learner, corrected):
    assert is_real_correction(learner, corrected)


def test_a_drill_does_not_replay_the_luxembourg_swap():
    from app.services.forge_drills import mine_fits

    assert not mine_fits("Ils est à Luxembourg cette semaine.", "Ils est au Luxembourg cette semaine.")


def test_dropped_errata_include_the_luxembourg_swap():
    from app.services.atelier import _drop_noop_errata

    kept, dropped = _drop_noop_errata(
        [
            {"learner_text": "Ils est", "corrected_target": "Ils sont", "task_error_type": "grammar"},
            {"learner_text": "à Luxembourg", "corrected_target": "au Luxembourg", "task_error_type": "grammar"},
        ]
    )
    assert dropped
    assert [erratum["corrected_target"] for erratum in kept] == ["Ils sont"]


# ---------------------------------------------------------------------------
# 4 · «Du hast „Ils a“ gewählt; Die Regel ist hier nicht der Unterschied.»
# ---------------------------------------------------------------------------


def test_a_miss_is_measured_against_the_nearer_accepted_answer():
    """A1 day 2: «Ils a» for «Sie (alle) haben …» (key «Elles ont», also «Ils ont») was
    measured against «Elles ont», so the right «Ils» was blamed as a word outside the rule."""

    verdict = judge("Ils a", ["Elles ont", "Ils ont"], typo=False)
    assert not verdict.correct
    assert verdict.expected == "Ils ont"


def _ils_a_item() -> dict:
    return {
        "id": "fr2-a11-avoir-fill-3f0b1a2bb0",
        "prompt": "___ un micro moderne.",
        "choices": ["Elles ont", "Elles avons", "Elles a"],
        "meaning": "They have a modern microphone.",
        "target_span": "Elles ont",
        "correct_answer": "Elles ont",
        "accepted_answers": ["Elles ont", "Ils ont"],
        "lesson_external_id": "FR2_A11_AVOIR",
    }


@pytest.mark.parametrize("language", ["de", "en", "fr"])
def test_ils_a_is_told_about_the_verb_not_the_pronoun(language):
    from app.db.models.grammar import GrammarConcept
    from app.services.atelier import AtelierCorrectionService

    concept = GrammarConcept(id=2, external_id="FR2_A11_AVOIR", name="Avoir", level="A1", category="Grammar")
    service = AtelierCorrectionService(None)
    service.explanation_language = language
    item = _ils_a_item()
    result = service._correct_recognize(concept, "fill", {"items": [item]}, {"answers": {item["id"]: "Ils a"}})
    [erratum] = result["errata"]
    assert erratum["corrected_target"] == "Ils ont", erratum
    for stale in ("nicht der Unterschied", "not what differs", "pas la règle qui diffère", "another word", "anderes Wort", "autre mot"):
        assert stale not in erratum["why_wrong"], erratum["why_wrong"]


@pytest.mark.parametrize(
    ("text", "learner", "target", "expected"),
    [
        (
            "Du hast „Ils a“ gewählt; hier ist „Elles ont“ nötig. Die Regel ist hier nicht der Unterschied: "
            "Die Zeile verlangt „Elles ont“, nicht „Ils a“.",
            "Ils a",
            "Elles ont",
            "Du hast „Ils a“ gewählt. Die Regel ist hier nicht der Unterschied.",
        ),
        (
            "Tu as écrit « ma » ; ici, c’est « mon ». Après pour, sans et avant de, on emploie l’infinitif.",
            "ma",
            "mon",
            "Tu as écrit « ma ». Après pour, sans et avant de, on emploie l’infinitif.",
        ),
        (
            "Du hast «sont» geschrieben; hier steht «sont». «à» blieb stehen, ist aber falsch: Hier steht «au».",
            "à",
            "au",
            "Du hast «sont» geschrieben; hier steht «sont». «à» blieb stehen, ist aber falsch.",
        ),
    ],
)
def test_a_withheld_hint_has_no_dangling_seam(text, learner, target, expected):
    """A clause that a «;» or «:» led into, once dropped because it names the answer,
    leaves its sentence ended, not glued to the next one with a «;»."""

    correction = {"errata": [{"learner_text": learner, "corrected_target": target}]}
    phrases, tokens = solution_gate.leak_terms(correction, learner)
    assert solution_gate.scrub_hint(text, phrases, tokens) == expected


def test_a_missing_elided_word_is_not_named_while_the_solution_waits():
    """B1 day 2: «Il manque « d' ».» gave the fix away before the retry."""

    correction = {"errata": [{"learner_text": "Avant aller", "corrected_target": "Avant d'aller"}]}
    phrases, tokens = solution_gate.leak_terms(correction, "Avant aller à un entretien, je relis mon CV.")
    text = "Il manque « d' ». Après pour, sans et avant de, on emploie l’infinitif : l'infinitif d'abord."
    assert solution_gate.scrub_hint(text, phrases, tokens) == (
        "Après pour, sans et avant de, on emploie l’infinitif : l'infinitif d'abord."
    )


# ---------------------------------------------------------------------------
# 5 · «je pense de monter» replayed under «Un, une, des : les articles indéfinis»
# ---------------------------------------------------------------------------


def test_de_before_an_infinitive_is_not_filed_as_an_article(db_session):
    """B1 day 4: the scene's «je pense de monter → je pense monter» changed only «de»,
    so it was filed as a determiner mistake (concept «Un, une, des») and the Forge
    replayed it under that heading. A «de» before an infinitive is a preposition."""

    from app.services.error_memory import ErrorMemoryService
    from tests.test_elision_one_classifier_119 import _setup

    _user, _le_la, un_une = _setup(db_session)
    memory = ErrorMemoryService(db_session)
    note = "After « penser » meaning to intend or plan, use the infinitive directly, without « de »."
    for span, fixed in (("je pense de monter", "je pense monter"), ("j'espère de partir", "j'espère partir")):
        assert memory.infer_concept_id_for_correction(learner_text=span, corrected_text=fixed, note=note) != un_une.id, span
    # A «de» before a noun is still the article's.
    assert memory.infer_concept_id_for_correction(learner_text="beaucoup des amis", corrected_text="beaucoup d'amis", note="") is not None


# ---------------------------------------------------------------------------
# 6 · «we had already left early»: tiles «parti» and «parties», no «partis», two spares
# ---------------------------------------------------------------------------


def _builds(unit: str, count: int = 40, seeds: int = 6):
    from app.services import item_bank as ib

    bank = ib.ItemBank()
    for seed in range(seeds):
        for item in bank.generate(unit, count, seed=f"walk3-build:{unit}:{seed}"):
            payload = ib.word_bank_item(item, lesson_external_id=unit)
            if payload is not None:
                yield item, payload


@pytest.mark.parametrize("unit", ["FR2_B11_PLUS_QUE_PARFAIT", "FR2_A21_PC_ETRE", "FR2_A11_ETRE"])
def test_a_build_says_one_word_is_extra_and_holds_one(unit):
    seen = 0
    for _item, payload in _builds(unit):
        spare = len(payload["tokens"]) - len(payload["answer_tokens"])
        if payload["instruction_key"] == "forge.word_bank":
            assert spare == 1, (payload["correct_answer"], payload["tokens"])
            seen += 1
        else:
            assert spare == 0, payload["tokens"]
    assert seen


def test_a_build_whose_gloss_hides_the_gender_offers_the_generic_form():
    hidden = {"je_f", "tu_f", "nous_f", "vous_f"}
    seen = []
    for item, payload in _builds("FR2_B11_PLUS_QUE_PARFAIT", seeds=12):
        if not any(str(entry.get("id")) in hidden for _slot, entry in item.bindings if isinstance(entry, dict)):
            continue
        masculine = [answer for answer in item.accepted if answer != item.sentence and len(answer) < len(item.sentence)]
        if not masculine or "parties" not in item.sentence and "partie " not in item.sentence:
            continue
        seen.append(payload)
        tiles = {token.casefold() for token in payload["tokens"]}
        assert payload["correct_answer"] in item.accepted
        assert "parties" not in tiles and "partie" not in tiles, payload["tokens"]
        assert payload["target_span"] in payload["correct_answer"], payload
    assert seen


# ---------------------------------------------------------------------------
# 7 · Two-option items: no retry (it would be trivial), but the miss gives the reason
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("language", ["de", "en", "fr"])
def test_a_missed_judgement_says_why_not_only_what(language):
    """A1 day 1: «Elle es prête.» sorted «Correct» read «„Elle es prête.“ stimmt nicht;
    richtig ist „Elle est prête.“» and nothing else. A two-way choice gets no retry, so
    the right sentence is the other answer; the reason must come with it."""

    from app.db.models.grammar import GrammarConcept
    from app.services.atelier import JUDGEMENT_TO_CORRECT, AtelierCorrectionService

    concept = GrammarConcept(id=1, external_id="FR2_A11_ETRE", name="Être", level="A1", category="Grammar")
    service = AtelierCorrectionService(None)
    service.explanation_language = language
    item = {"id": "j1", "prompt": "Elle es prête.", "source_fr": "Elle es prête.", "judgement_fix_fr": "Elle est prête."}
    erratum = service._judgement_erratum(concept, item, "Correct", JUDGEMENT_TO_CORRECT)
    why = erratum["why_wrong"]
    assert "Elle est prête" in why
    assert ".“." not in why and ".”." not in why and ". »." not in why, why
    assert why.count("«") + why.count("„") + why.count("“") >= 3
    assert len(why) > len(service._judgement_erratum(concept, {**item, "judgement_fix_fr": ""}, "Correct", JUDGEMENT_TO_CORRECT)["why_wrong"])
    assert "elle" in why.casefold().split("prête", 2)[-1], why


def test_a_choice_between_two_gets_no_second_chance():
    """The owner rule (no solution before a retry) holds because there is no retry: a
    choice between two is final, and the speed round is a designed exception."""

    assert not solution_gate.second_chance_for(
        round_name="recognize", exercise_id="U:recognize:classify:j1", prompt_payload={"items": [{"id": "j1", "labels": ["Correct", "À corriger"]}]},
        answer_payload={"answers": {"j1": "Correct"}}, first_submission=True, retest=False, rule_check=False,
    )
