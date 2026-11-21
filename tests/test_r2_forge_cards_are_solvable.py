"""R2 (walk of 17 Nov 2026): La Forge never deals a card the learner cannot solve, and never
a vocative.

What each group stands for (the cards are in ``tests/test_walk_2026_11_17_forge_cards.py``):

1. **A free card states what it is judged on.** A coach scene keeps the reply it wants only
   in its English prompt and its goals; a French screen showed «Lila : « La fête des
   voisins ? »» and nothing more, yet the grader was handed «Reply in French: "Yes, I'm
   suggesting it to them."» and refused every other right answer. The grader now gets the
   card as shown (``own_sentence``), and a task note about unstated content is dropped
   once the card's rule is in the answer.
2. **Two refusals end in the solution.** A refused free answer whose solution is on screen
   is served one acceptable model answer (``model_answer``), said to nobody.
3. **A refusal says what is missing**, never «Relis la consigne» alone.
4. **A free card's floor fits its own answer** («J'ai trente ans.» against «5–24 words»).
5. **No vocative in any Forge format** — build, write, fill, pick, judge, burst — from the
   bank as it builds, and from a stored set as it is served and graded.
6. **A first miss on a choice says why**, not only the rule's name.

No model is called: the model's answers are fixtures (the notes the walk logged).
"""
from __future__ import annotations

import re
from dataclasses import replace
from types import SimpleNamespace

import pytest

from app.services import item_bank as ib
from app.services import solution_gate
from app.services.answer_acceptance import addressed_names
from app.services.atelier import AtelierCorrectionService
from app.services.forge_coaches import coach as coach_payload
from app.services.no_address import addresses_someone, unaddressed_payload
from tests.gold_transcripts.surfaces import make_concept

#: A bank unit whose items give a coach scene (main has no bank unit for the B1 rule yet).
PRONOUNS = "FR2_A22_PRONOUN_POSITION"
DOUBLE_PRONOUNS = "FR2_B11_DOUBLE_PRONOUNS"
REQUIREMENT = {"label": "Deux pronoms ensemble : je le lui donne", "external_id": "FR2_B11_DOUBLE_PRONOUNS", "target_count": 1}


def _service(language: str, native: str | None = None) -> AtelierCorrectionService:
    service = AtelierCorrectionService.__new__(AtelierCorrectionService)
    service.explanation_language = language
    service._learner_native = native or language
    service._answer_truncated = False
    return service


def lila_scene(question: str, reply: str, reply_en: str, reply_de: str | None = None) -> dict:
    """A coach scene as ``item_bank.scene_item`` builds it, on the logged card's words."""

    base = ib.default_bank().generate(PRONOUNS, 1, seed="r2")[0]
    target = next(pair for pair in ("la leur", "le lui", "le leur", "te le") if pair in reply)
    before, after = reply.split(target, 1)
    item = replace(
        base,
        sentence=f"{question} {reply}",
        en=f"{question} {reply_en}",
        de=(f"{question} {reply_de}" if reply_de else None),
        prefix=f"{question} {before}",
        target=target,
        suffix=after,
        accepted=(f"{question} {reply}",),
    )
    scene = ib.scene_item(item, coach=coach_payload("lila_bonnet"), requirement=REQUIREMENT)
    assert scene is not None
    return scene


# --------------------------------------------------------------------------- #
# 1 · the card states what it is judged on
# --------------------------------------------------------------------------- #


def test_a_coach_scene_on_a_french_screen_is_graded_as_the_card_the_learner_read():
    """B1 day 5: the grader read the English reply the French screen never showed."""

    scene = lila_scene("La fête des voisins ?", "Oui, je la leur propose.", "Yes, I'm suggesting it to them.")
    asked = _service("fr", "en")._compact_llm_task({"items": [scene]})["items"][0]
    assert asked.get("own_sentence") is True
    assert "suggesting" not in asked["prompt"] and "Reply in French" not in asked["prompt"]
    assert "La fête des voisins ?" in asked["prompt"]


def test_a_coach_scene_that_quoted_its_reply_keeps_it_as_the_task():
    """A German screen quotes the reply («Antworte auf Französisch: „…“»): that is the task."""

    scene = lila_scene(
        "La fête des voisins ?", "Oui, je la leur propose.", "Yes, I'm suggesting it to them.", "Ja, ich schlage es ihnen vor."
    )
    asked = _service("de")._compact_llm_task({"items": [scene]})["items"][0]
    assert "own_sentence" not in asked
    english = _service("en")._compact_llm_task({"items": [scene]})["items"][0]
    assert "own_sentence" not in english


def graded_with_reading(service: AtelierCorrectionService, scene: dict, text: str, reading: dict) -> dict:
    # The card's rule on the walk: «Deux pronoms ensemble» (its own detector decides).
    concept = make_concept(DOUBLE_PRONOUNS)
    service._get_llm_service = lambda: object()
    service._correction_system_prompt = lambda: "system"
    service._llm_correction = lambda **kwargs: dict(reading)
    # No database here: the requirement's count finds nothing, so only the detector decides.
    service._count_hits = lambda requirement, line: 0
    payload = {"round": "conversation", "items": [scene]}
    fallback = service._correct_output_ladder_rule_based(concept, "conversation", payload, {"text": text})
    return service._correct_output_ladder_with_llm(concept, "conversation", payload, {"text": text}, fallback)


TASK_NOTE = {
    "item_id": "x",
    "learner_text": "Oui, je la leur propose pour samedi soir.",
    "corrected_target": "",
    "why_wrong": "« Je la leur propose » signifie que tu la proposes aux voisins, pas que la voisine t'en a parlé hier.",
    "task_error_type": "task_compliance",
}


def test_a_note_about_content_the_card_never_asked_is_dropped_once_the_rule_is_there():
    """B1 day 5 «La fête des voisins ?», retry: a grammatical answer with «la leur», refused
    for an intent the card never stated. The rule and correct French are all it may require."""

    scene = lila_scene("La fête des voisins ?", "Oui, je la leur propose.", "Yes, I'm suggesting it to them.")
    reading = {"verdict": "partial", "score_0_4": 2.0, "errata": [TASK_NOTE], "corrected_answer": TASK_NOTE["learner_text"]}
    graded = graded_with_reading(_service("fr", "en"), scene, TASK_NOTE["learner_text"], reading)
    assert graded["verdict"] in {"correct", "accepted"}
    assert not [item for item in graded["errata"] if item.get("task_error_type") == "task_compliance"]


def test_a_form_error_still_stands_and_an_answer_without_the_rule_keeps_its_note():
    scene = lila_scene("La fête des voisins ?", "Oui, je la leur propose.", "Yes, I'm suggesting it to them.")
    form = {"learner_text": "lui le", "corrected_target": "le lui", "why_wrong": "ordre", "task_error_type": "pronoun_order"}
    graded = graded_with_reading(
        _service("fr", "en"), scene, "Oui, je lui le propose samedi.",
        {"verdict": "partial", "score_0_4": 2.0, "errata": [form, TASK_NOTE]},
    )
    assert graded["verdict"] == "partial" and form in graded["errata"]
    no_rule = graded_with_reading(
        _service("fr", "en"), scene, "Oui, je propose la fête samedi.",
        {"verdict": "partial", "score_0_4": 2.0, "errata": [TASK_NOTE]},
    )
    assert TASK_NOTE in no_rule["errata"]


# --------------------------------------------------------------------------- #
# 2 · two refusals end in the solution
# --------------------------------------------------------------------------- #


def _attempt(correction: dict, scene: dict, text: str) -> SimpleNamespace:
    return SimpleNamespace(
        round="conversation", verdict=correction.get("verdict"), correction_payload=correction,
        answer_payload={"text": text}, prompt_payload={"round": "conversation", "items": [scene]},
    )


def test_a_free_card_refused_with_its_solution_on_screen_serves_one_model_answer():
    """B1 day 5: after «Voir la solution» the same critique came back and only «Passer» led on."""

    from app.api.v1.endpoints.atelier import _learner_correction

    scene = lila_scene("La piscine ?", "Oui, je la leur propose.", "Yes, I'm suggesting it to them.")
    refused = solution_gate.reveal(
        solution_gate.mark(
            {"verdict": "partial", "score_0_4": 2.0, "assessment_status": "checked", "errata": [TASK_NOTE],
             "corrected_answer": TASK_NOTE["learner_text"]},
            chance=True, language="fr",
        ),
        by="reveal",
    )
    served = _learner_correction(_attempt(refused, scene, TASK_NOTE["learner_text"]))
    assert served["model_answer"] == "Oui, je la leur propose."
    # While the chance is open, nothing right is served.
    open_chance = solution_gate.mark(dict(refused, solution=None), chance=True, language="fr")
    assert "model_answer" not in _learner_correction(_attempt(open_chance, scene, TASK_NOTE["learner_text"]))


def test_the_model_answer_is_said_to_nobody():
    from app.services.free_card_contract import model_answer

    payload = {"items": [{"example_answer": "Oui, je la leur propose, Lila."}]}
    assert model_answer(payload) == "Oui, je la leur propose."


# --------------------------------------------------------------------------- #
# 3 · a refusal says what is missing
# --------------------------------------------------------------------------- #


def test_a_task_note_with_nothing_left_to_say_names_what_is_missing_in_words():
    """B1 day 5 «Le vide-grenier ?»: «Relis la consigne : qu'est-ce qu'elle te demande
    d'utiliser ?» was the whole refusal."""

    note = {"learner_text": "", "corrected_target": "", "why_wrong": "", "repair_hint": "",
            "display_label": "Deux pronoms ensemble : je le lui donne", "task_error_type": "task_compliance"}
    view = solution_gate.learner_view(
        solution_gate.mark({"verdict": "partial", "errata": [note]}, chance=True, language="fr"),
        answer_payload={"text": "Oui, je te le propose pour dimanche matin, si tu veux."},
    )
    hint = view["errata"][0]["hint"]
    assert "Relis la consigne" not in hint
    assert "ne montre pas encore la règle de cette carte" in hint and "Deux pronoms ensemble" in hint


# --------------------------------------------------------------------------- #
# 4 · the floor fits the answer
# --------------------------------------------------------------------------- #


def _age_ask_item() -> ib.BankItem:
    for seed in range(40):
        for item in ib.default_bank().generate("FR2_A11_AVOIR", 12, seed=f"r2-age:{seed}"):
            if item.frame_id.startswith("avoir-age-ask") and "demande ton âge" in item.sentence:
                return item
    pytest.skip("the bank drew no «demande ton âge» item")


def test_a_free_card_never_asks_for_more_words_than_its_own_answer():
    """A1 day 3: «Marin fragt, wie alt du bist. Ich bin 30 Jahre alt.» — «0 von 5–24 Wörtern»
    for a three-word answer."""

    item = _age_ask_item()
    shortest = min(len(answer.split()) for answer in (item.sentence.split(". ")[-1], *item.accepted))
    for round_name in ("sentence", "conversation"):
        card = ib.output_item(item, round_name=round_name, requirement={"label": "avoir"})
        assert card is not None
        assert card["min_words"] <= shortest <= 3, (round_name, card["min_words"], item.sentence)


def test_a_stored_card_is_served_with_a_floor_that_fits_its_answer():
    stored = {"id": "x", "type": "short_sentence", "prompt": 'Say in French: "I am 30."', "example_answer": "J'ai trente ans.", "min_words": 5}
    assert ib.public_item(dict(stored), "de")["min_words"] <= 3


# --------------------------------------------------------------------------- #
# 5 · no vocative in any Forge format
# --------------------------------------------------------------------------- #

LANGUAGES = ("en", "de", "fr")


def _french_and_quotes(item: dict) -> list[str]:
    texts = [item.get(key) for key in ("prompt", "source_fr", "correct_answer", "correct_label", "example_answer", "expected_answer")]
    texts.extend(item.get("labels") or [])
    texts.extend(item.get("accepted_answers") or [])
    texts.append(item.get("goal_native"))
    return [text for text in texts if isinstance(text, str)]


def test_the_predicate_is_the_one_strip():
    assert addresses_someone("Je suis prêt, Margaux.")
    assert addresses_someone("Margaux, tu viens ?")
    assert not addresses_someone("On peut rester chez Lila.")


@pytest.fixture(scope="module")
def bank_items() -> list[ib.BankItem]:
    bank = ib.default_bank()
    items = []
    for unit in sorted(bank.templates):
        for seed in range(2):
            items.extend(bank.generate(unit, 6, seed=f"r2-voc:{unit}:{seed}"))
    return items


def test_no_fill_pick_or_judgement_the_bank_builds_addresses_anyone(bank_items):
    addressed = [item for item in bank_items if addressed_names(item.sentence)]
    assert addressed, "the bank still draws vocative twins (they are stripped as they are posed)"
    checked = 0
    for item in addressed:
        for payload in (
            ib.fill_item(item),
            ib.classify_item(item, show_correct=True),
            ib.classify_item(item, show_correct=False),
            ib.pair_item(item),
        ):
            if payload is None:
                continue
            checked += 1
            for language in LANGUAGES:
                for text in _french_and_quotes(ib.public_item(dict(payload), language)):
                    assert not addresses_someone(text), (item.frame_id, language, text)
            key = payload.get("follow_up_key") or {}
            assert not addresses_someone(key.get("corrected_fr")), item.frame_id
    assert checked


#: Items as the walk served them (stored before this change), one per format.
STORED = [
    # A1 day 1, «Ergänze»: fill.
    {"id": "a1-fill", "prompt": "Tu ___ prêt, Marin ?", "choices": ["est", "es", "suis"], "correct_answer": "es",
     "accepted_answers": ["es"], "goal_l10n": {"de": "Ergänze den Satz: „Bist du fertig, Marin?“"}},
    # B1 day 3, MC cloze.
    {"id": "b1-fill", "prompt": "La rue est ___, Margaux.", "choices": ["moderne", "modernes"], "correct_answer": "moderne"},
    # A1 day 1, «Welcher Satz sagt»: pair.
    {"id": "a1-pair", "prompt": 'Which sentence says: "I am tall, Gus."', "labels": ["Je es grand, Gus.", "Je suis grand, Gus."],
     "correct_label": "Je suis grand, Gus.", "correct_answer": "Je suis grand, Gus.", "classify_kind": "minimal_pair",
     "goal_l10n": {"de": "Welcher Satz sagt: „Ich bin groß, Gus.“?"}},
    # B1 day 6, judge (then corrected).
    {"id": "b1-judge", "prompt": "Il part en Lille demain, Romy.", "labels": ["Correct", "À corriger"], "correct_label": "À corriger",
     "correct_answer": "À corriger", "classify_kind": "judgement", "source_fr": "Il part en Lille demain, Romy.",
     "follow_up_key": {"corrected_fr": "Il part à Lille demain, Romy.", "accepted_fr": ["Il part à Lille demain, Romy."]}},
    # A1 day 2 exam: judged, then rebuilt with tiles.
    {"id": "a1-exam", "prompt": "Je es prêt, Margaux.", "labels": ["Correct", "À corriger"], "correct_label": "À corriger",
     "correct_answer": "À corriger", "classify_kind": "judgement", "source_fr": "Je es prêt, Margaux.",
     "follow_up_key": {"corrected_fr": "Je suis prêt, Margaux.", "accepted_fr": ["Je suis prêt, Margaux."]}},
    # A1 / B1 bursts.
    {"id": "b1-burst", "prompt": "La tasse est beau, Margaux.", "labels": ["Correct", "À corriger"], "correct_label": "À corriger",
     "correct_answer": "À corriger", "classify_kind": "judgement"},
    {"id": "mexique", "prompt": "Ils sont au Mexique cette semaine, Marin.", "labels": ["Correct", "À corriger"],
     "correct_label": "Correct", "correct_answer": "Correct", "classify_kind": "judgement"},
]


@pytest.mark.parametrize("stored", STORED, ids=[item["id"] for item in STORED])
def test_a_stored_item_of_any_format_is_served_and_graded_without_its_name(stored):
    served = ib.public_item(dict(stored), "de")
    graded = unaddressed_payload({"round": "recognize", "items": [dict(stored)]})["items"][0]
    for item in (served, graded):
        for text in _french_and_quotes(item):
            assert not addresses_someone(text), text
        assert not addresses_someone((item.get("follow_up_key") or {}).get("corrected_fr"))
        for text in (item.get("goal_l10n") or {}).values():
            assert not re.search(r",\s*(?:Marin|Gus|Margaux|Romy|Lila)\b", text), text
    # What is served is what is graded: a pick's right label is one of the served labels.
    if served.get("classify_kind") == "minimal_pair":
        assert graded["correct_label"] in served["labels"]


# --------------------------------------------------------------------------- #
# 6 · a first miss on a choice says why
# --------------------------------------------------------------------------- #


def test_a_first_miss_on_a_choice_gives_the_reason_not_only_the_rule_name():
    """B1 day 3: «Tu as choisi « noire » ; Règle : Les adjectifs : accord et place.»"""

    concept = make_concept("FR2_A11_ADJ_AGREEMENT")
    item = {"id": "adj-1", "prompt": "Gus a un micro ___.", "choices": ["noire", "noirs", "noir"], "correct_answer": "noir",
            "lesson_external_id": concept.external_id}
    erratum = _service("fr")._recognize_erratum(concept, "fill", item, "noire", "noir")
    correction = solution_gate.mark({"verdict": "incorrect", "errata": [erratum], "corrected_answer": "noir"}, chance=True, language="fr")
    hint = solution_gate.learner_view(correction, answer_payload={"answers": {"adj-1": "noire"}}, context=item["prompt"])["errata"][0]["hint"]
    assert not re.fullmatch(r"Tu as choisi « noire » ?;? ?Règle ?: .*", hint), hint
    assert "adjectif" in hint.casefold()
    assert not re.search(r"\bnoir\b", hint), hint
