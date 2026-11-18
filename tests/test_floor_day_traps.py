"""#824 / #773: the basic check (``correction_contract``, no model) reads the day's card trap.

#824 (walk 16 Nov, no model, the avoir day): «Tu es faim ce soir ?», the avoir card's own
«Falsch» shape, went by unnamed («Die Prüfung ist gerade nicht verfügbar … zählt nicht»):
the être-for-avoir slip was read for «je suis» only. Seen again 18 Nov on the être day:
«Elle et a Paris cette semaine.», the classic «et» for «est», was not named either.

#773 (live walk 14 Nov, a model): La Forge marked «Est-ce que on commence le travail ?»
Right, while the recall drill marked «Est-ce que il pleut ?» wrong. The floor names «que on
→ qu'on»; La Forge's relecture took the model's «correct» as it came, where the Journal, the
Courrier and the scene add the floor's fixes to the model's reading.

The shared cause: the floor is a list of token patterns that never knew which card it is
checking. The guards below run each card's own trap, and the shapes built on it, through
the basic check, and hold La Forge's free check to it.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.services import correction_contract
from app.services.llm_service import LLMResult

# ---------------------------------------------------------------------------
# #824: être for avoir in every person
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("sentence", "right"),
    [
        ("Tu es faim ce soir ?", "Tu as faim ce soir ?"),
        ("Je suis vingt ans.", "J'ai vingt ans."),
        ("Je suis froid.", "J'ai froid."),
        ("Tu es froid ?", "Tu as froid ?"),
        ("Il est soif après le match.", "Il a soif après le match."),
        ("Elle est peur du noir.", "Elle a peur du noir."),
        ("On est faim !", "On a faim !"),
        ("Nous sommes faim.", "Nous avons faim."),
        ("Vous êtes soif ?", "Vous avez soif ?"),
        ("Ils sont sommeil.", "Ils ont sommeil."),
    ],
    ids=["tu", "je-ans", "je", "tu-froid", "il", "elle", "on", "nous", "vous", "ils"],
)
def test_avoir(sentence, right):
    """#824: the basic check names «avoir faim» whoever is hungry, with the card's form."""
    errata = correction_contract.deterministic_errata(sentence, language="de")
    fixed = correction_contract.repair_text(sentence)
    assert fixed == right, (
        f"«{sentence}»: the basic check printed «{fixed}»; it listed "
        f"{[(e['learner_text'], e['corrected_target']) for e in errata]}"
    )
    assert errata and all(e["why_wrong"] for e in errata)


@pytest.mark.parametrize(
    "right",
    [
        "Il est froid.",  # the soup, the room, the man
        "La soupe est froide.",
        "Elle est froide avec moi.",
        "Je suis froid avec elle.",
        "Ils sont froids.",
        "Vous êtes froid avec moi.",
        "Il est chaud.",
        "J'ai faim.",
        "Tu as soif ?",
        "C'est la faim.",
    ],
)
def test_etre_for_avoir_leaves_french_alone(right):
    rules = [edit.rule_id for edit in correction_contract.deterministic_edits(right)]
    assert "FR_AVOIR_STATE" not in rules, f"«{right}» is French as written: {rules}"
    assert correction_contract.repair_text(right) == right


# ---------------------------------------------------------------------------
# #824 (18 Nov): «et» for «est», the être card's sound-alike
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("sentence", "right"),
    [
        ("Elle et a Paris cette semaine.", "Elle est à Paris cette semaine."),
        ("Elle et à Paris cette semaine.", "Elle est à Paris cette semaine."),
        ("Il et a la maison.", "Il est à la maison."),
        ("Il et en retard.", "Il est en retard."),
        ("On et très contents.", "On est très contents."),
        ("Elle et ici.", "Elle est ici."),
        ("Il et malade.", "Il est malade."),
        ("Il pleut et elle et chez Gus.", "Il pleut et elle est chez Gus."),
    ],
    ids=["a", "à", "il-a", "en", "très", "ici", "adj", "after-et"],
)
def test_et_est(sentence, right):
    """#824: «Elle et a Paris» is the être card's slip of the ear: «est», and «à» after it."""
    errata = correction_contract.deterministic_errata(sentence, language="de")
    fixed = correction_contract.repair_text(sentence)
    assert fixed == right, (
        f"«{sentence}»: the basic check printed «{fixed}»; it listed "
        f"{[(e['learner_text'], e['corrected_target']) for e in errata]}"
    )
    assert all(e["why_wrong"] for e in errata)


@pytest.mark.parametrize(
    "right",
    [
        "Elle et moi, on part.",
        "Elle et lui sont à Paris.",
        "Elle et son frère sont à Paris.",
        "Elle et Paul sont là.",
        "Paul et elle sont là.",
        "C'est pour elle et pour moi.",
        "Entre elle et lui, rien.",
        "Il y avait Paul, elle et Marie.",
        "Il y avait Paul, elle et à côté, Marie.",
        "Il pleut, et elle a froid.",
        "Elle et sa sœur sont malades.",
        "Elle et deux amis arrivent.",
        "Il y a Lila, elle et en plus Gus.",
        "Il et elle sont arrivés.",
        "Elle et a mangé.",
    ],
)
def test_et_is_left_alone(right):
    rules = [edit.rule_id for edit in correction_contract.deterministic_edits(right)]
    assert correction_contract.repair_text(right) == right, f"«{right}» is left as written: {rules}"


# ---------------------------------------------------------------------------
# Every A1 card's own trap, and the shapes the walks wrote on it
# ---------------------------------------------------------------------------


def _card_traps(level: str) -> list[tuple[str, str, str]]:
    path = Path(__file__).resolve().parents[1] / "app" / "data" / "rule_cards" / f"fr2_{level}.json"
    cards = json.loads(path.read_text(encoding="utf-8"))["cards"]
    out = []
    for card_id, card in sorted(cards.items()):
        contrast = card.get("contrast") or {}
        if contrast.get("wrong") and contrast.get("right"):
            out.append((card_id, contrast["wrong"], re.sub(r"[\[\]{}]", "", contrast["right"])))
    return out


#: The A1 cards whose «Falsch» line the floor cannot read yet: each needs a rule of its
#: own (an article, a conjugation table, a word order), and each is a model's job until
#: then. ``strict``: a card that starts passing must leave this list, so the guard keeps
#: what it gains.
_NOT_READ_YET = {
    "FR2_A11_ADJ_AGREEMENT", "FR2_A11_ALLER_VENIR", "FR2_A11_ER_VERBS", "FR2_A11_FAIRE_PRENDRE",
    "FR2_A11_IL_Y_A", "FR2_A11_JE_VOUDRAIS", "FR2_A11_LE_LA", "FR2_A11_NEGATION", "FR2_A11_NUMBERS",
    "FR2_A11_PLACES", "FR2_A11_UN_UNE", "FR2_A12_CEST_IL_EST", "FR2_A12_DAYS_DATES", "FR2_A12_ER_SPELLING",
    "FR2_A12_FREQUENCY", "FR2_A12_FUTUR_PROCHE", "FR2_A12_IMPERATIVE", "FR2_A12_IR_RE_VERBS",
    "FR2_A12_MODALS", "FR2_A12_NUMBERS_BIG", "FR2_A12_PC_CHUNKS", "FR2_A12_PRONOMINAL", "FR2_A12_QUANTITIES",
    "FR2_A12_QUEL_EXCLAMATIF", "FR2_A12_TIME",
}

_A1_TRAPS = _card_traps("A1")


@pytest.mark.parametrize(
    ("card", "wrong", "right"),
    [
        pytest.param(
            *trap,
            id=trap[0],
            marks=[pytest.mark.xfail(strict=True, reason="no floor rule reads this card yet")]
            if trap[0] in _NOT_READ_YET
            else [],
        )
        for trap in _A1_TRAPS
    ],
)
def test_card(card, wrong, right):
    """#824's guard: each A1 card's own «Falsch» line comes out as the card's «Richtig»,
    and the floor knows the edit it makes there is that card's trap."""
    fixed = correction_contract.repair_text(wrong)
    assert fixed == right, f"{card}: «{wrong}» is printed as «{fixed}», the card says «{right}»"
    from app.services.correction_contract import card_trap_edits

    assert card_trap_edits(wrong, card), f"{card}: the floor fixes «{wrong}» but does not know it is the card's trap"


#: Sentences the walks wrote on a card's trap, with the card's right form.
_TRAP_SHAPES = [
    ("FR2_A11_AVOIR", "Tu es faim ce soir ?", "Tu as faim ce soir ?"),
    ("FR2_A11_AVOIR", "Je suis vingt ans.", "J'ai vingt ans."),
    ("FR2_A11_AVOIR", "Je suis froid.", "J'ai froid."),
    ("FR2_A11_ETRE", "Elle et a Paris cette semaine.", "Elle est à Paris cette semaine."),
    ("FR2_A11_QUESTIONS", "Est-ce que on commence le travail ?", "Est-ce qu'on commence le travail ?"),
    ("FR2_A11_QUESTIONS", "Est-ce que il pleut ?", "Est-ce qu'il pleut ?"),
]


@pytest.mark.parametrize(
    ("card", "sentence", "right"), _TRAP_SHAPES, ids=["faim", "ans", "froid", "et", "que-on", "que-il"]
)
def test_shape(card, sentence, right):
    fixed = correction_contract.repair_text(sentence)
    assert fixed == right, f"{card}: «{sentence}» is printed as «{fixed}», the card says «{right}»"
    assert correction_contract.deterministic_edits(fixed) == [], "the printed line is left as it is"
    from app.services.correction_contract import card_trap_edits

    assert card_trap_edits(sentence, card), f"{card}: «{sentence}» is the card's trap"


def test_every_card_the_floor_reads_is_a_card():
    """The floor's card map names real A1 cards, and none of them is still «not read»."""
    from app.services.correction_contract import CARD_TRAP_RULES

    cards = {card for card, _w, _r in _A1_TRAPS}
    assert {"FR2_A11_AVOIR", "FR2_A11_ETRE", "FR2_A11_QUESTIONS"} <= set(CARD_TRAP_RULES)
    assert set(CARD_TRAP_RULES) <= cards
    assert not set(CARD_TRAP_RULES) & _NOT_READ_YET
    assert cards - _NOT_READ_YET == set(CARD_TRAP_RULES)


# ---------------------------------------------------------------------------
# Review notes of #832 / #815 kept: the comparative «plus», «il n'y a»
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("sentence", "right"),
    [
        ("Je ne pas suis plus grand que toi.", "Je ne suis pas plus grand que toi."),
        ("Il ne pas parle plus fort.", "Il ne parle pas plus fort."),
        ("Je ne pas mange plus que toi.", "Je ne mange pas plus que toi."),
        ("Je pas parle plus fort.", "Je ne parle pas plus fort."),
        ("je ne pas oublie plus", "je n'oublie plus"),
        ("Il n'y a pas foule.", "Il n'y a pas foule."),
        ("Il n'y a jamais foule ici.", "Il n'y a jamais foule ici."),
        ("Il n'y a plus place.", "Il n'y a plus place."),
        ("Il n'y a pas place pour le doute.", "Il n'y a pas place pour le doute."),
    ],
)
def test_the_reviewed_lines_stay_as_main_prints_them(sentence, right):
    assert correction_contract.repair_text(sentence) == right


# ---------------------------------------------------------------------------
# La Forge's free check
# ---------------------------------------------------------------------------


class _Model:
    """The model reading the free sentence: «correct», nothing to fix."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.calls = 0

    def generate_error_detection(self, messages, **kwargs):
        self.calls += 1
        content = {
            "verdict": "correct",
            "score_0_4": 4,
            "corrected_answer": self.text,
            "concept_hits": [],
            "missing_targets": [],
            "errata": [],
        }
        return LLMResult(
            provider="openai",
            model="gpt-4o",
            content=json.dumps(content),
            prompt_tokens=10,
            completion_tokens=10,
            total_tokens=20,
            cost=0.0,
            raw_response={},
        )


def _submit(db_session, monkeypatch, text: str, *, external_id: str, model_configured: bool):
    from app.core.forge import Rung
    from app.services.atelier import AtelierCorrectionService
    from app.services.forge import ForgeService, _store_state, forge_state_of
    from app.services.grammar_catalog import FrenchCoreGrammarCatalog
    from tests.test_forge_integration import _forge_session

    monkeypatch.setattr(AtelierCorrectionService, "_can_schedule_ai_review", lambda self: model_configured)
    FrenchCoreGrammarCatalog(db_session, "v2").ensure_catalog()
    model = _Model(text)
    user, concept, session, _shared = _forge_session(db_session, external_id)
    forge = ForgeService(db_session)
    forge.attach(user=user, session=session, keep_concepts=True)
    state = forge_state_of(session)
    state.tracks[0].rung = int(Rung.PRODUCE)
    _store_state(session, state)
    db_session.commit()
    nxt = forge.next_item(user=user, session=session)
    assert nxt["round"] == "sentence"
    service = AtelierCorrectionService(db_session, llm_service=model)
    attempt = service.submit_attempt(
        session=session,
        user=user,
        concept=concept,
        round_name="sentence",
        mode="sentence",
        exercise_id=f"forge:{concept.id}:sentence:{nxt['item_id']}",
        answer_payload={"text": text},
    )
    forge.observe_attempt(user=user, session=session, attempt=attempt)
    return service, attempt, model


def _check(attempt, text: str) -> dict:
    from app.services import verdicts

    return verdicts.from_forge(attempt.correction_payload, text=text, verdict=attempt.verdict).to_dict()


def _edits(check: dict) -> list[tuple[str, str]]:
    return [(edit["span"], edit["replacement"]) for edit in check["edits"]]


ESTCE_FORGE = "Est-ce que on commence le travail ?"
ESTCE_RECALL = "Est-ce que il pleut ?"


@pytest.mark.parametrize(("text", "fix"), [(ESTCE_FORGE, "qu'on"), (ESTCE_RECALL, "qu'il")], ids=["on", "il"])
def test_forge_estce(db_session, monkeypatch, text, fix):
    """#773: La Forge does not call a missing «qu'» elision right when its model does."""
    service, attempt, model = _submit(
        db_session, monkeypatch, text, external_id="FR2_A11_QUESTIONS", model_configured=True
    )
    landed = service.run_ai_review_for_attempt(attempt.id)
    assert model.calls == 1
    check = _check(landed, text)
    edits = _edits(check)
    assert landed.verdict not in {"correct", "accepted"}, (
        f"«{text}» is marked «{landed.verdict}» with {edits}: the rules floor names «{fix}» and the recall "
        "drill marks the same elision wrong"
    )
    assert check["outcome"] != "right", check
    assert any(fix in replacement for _span, replacement in edits), edits


def test_a_right_sentence_the_model_passes_stays_right(db_session, monkeypatch):
    text = "Est-ce qu'on commence le travail ?"
    service, attempt, _model = _submit(
        db_session, monkeypatch, text, external_id="FR2_A11_QUESTIONS", model_configured=True
    )
    landed = service.run_ai_review_for_attempt(attempt.id)
    assert landed.verdict == "correct", _check(landed, text)


def test_the_recall_item_and_the_forge_free_check_agree():
    """#773: the card's Wrong/Right pair (what the recall drill keys) and the free check
    read one rule: the floor La Forge holds its model to names the recall item's «Wrong»
    as the card's trap, and the card's «Right» as nothing to fix."""
    from app.services.correction_contract import card_trap_edits
    from app.services.forge_grading import with_floor_errata

    card = {c: (w, r) for c, w, r in _A1_TRAPS}["FR2_A11_QUESTIONS"]
    assert card == (ESTCE_RECALL, "Est-ce qu'il pleut ?")
    for wrong in (ESTCE_RECALL, ESTCE_FORGE):
        assert card_trap_edits(wrong, "FR2_A11_QUESTIONS")
        held = with_floor_errata({"verdict": "correct", "score_0_4": 4.0, "errata": []}, wrong, language="en")
        assert held["verdict"] == "partial", held
    held = with_floor_errata({"verdict": "correct", "score_0_4": 4.0, "errata": []}, card[1], language="en")
    assert held["verdict"] == "correct"


def test_forge_avoir_miss(db_session, monkeypatch):
    """#824 done-when: with no model, La Forge's free item «Tu es faim ce soir ?» on the avoir
    rule is the card's own trap. It counts as a miss with the avoir note, never «zählt nicht»."""
    text = "Tu es faim ce soir ?"
    _service, attempt, model = _submit(
        db_session, monkeypatch, text, external_id="FR2_A11_AVOIR", model_configured=False
    )
    assert model.calls == 0
    check = _check(attempt, text)
    assert ("Tu es faim", "Tu as faim") in _edits(check), check["edits"]
    assert check["counts"] is True and check["outcome"] == "not_yet", (
        f"the card's own trap is read without a model: {check['outcome']!r}, counts={check['counts']!r}, "
        f"failure={check.get('failure')!r}"
    )
    assert attempt.verdict == "incorrect"
    from app.core import forge as core
    from app.services.forge import verdict_from_attempt

    seen = verdict_from_attempt(attempt)
    assert (seen.checked, seen.outcome) == (True, core.OUTCOME_INCORRECT), "La Forge files it as a miss"
    assert "tu as faim" in json.dumps(attempt.correction_payload, ensure_ascii=False).casefold()


def test_another_slip_on_the_avoir_day_still_waits_for_a_reading(db_session, monkeypatch):
    """#334 stands for everything that is not the day's trap: «trente-deux an» on the avoir
    day is named, and with no model it still counts for nothing."""
    text = "J'ai trente-deux an."
    _service, attempt, _model = _submit(
        db_session, monkeypatch, text, external_id="FR2_A11_AVOIR", model_configured=False
    )
    check = _check(attempt, text)
    assert ("an", "ans") in _edits(check)
    assert check["counts"] is False
