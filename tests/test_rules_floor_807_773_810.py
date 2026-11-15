"""#807 / #773 / #810: the rules floor (``correction_contract``, no model) under every check.

#807 (walk 15 Nov, no model, a passé composé day): the basic check fixed the accents around
the verb and never the verb. «il a invite Lila», «ils ont expliquer la methode», «tu as
appele la banque», «je suis arrive», «Gus m a demande», «Margaux m a donne» were listed
with only their apostrophes, so the one slip that is the day's rule was never named. The
floor had no rule for an auxiliary followed by a verb form that is not a participle.

#773 (live walk 14 Nov, a model): La Forge marked «Est-ce que on commence le travail ?»
Right, while the recall drill marked «Est-ce que il pleut ?» wrong. The floor names «que on
→ qu'on»; La Forge's relecture took the model's «correct» as it came, where the Journal,
the Courrier and the scene add the floor's fixes to the model's reading.

#810 (walk 15 Nov, no model, Courrier): «ce n'est pas a moi», «je suis pas a la maison»
kept «a», «Peut-être c est à Gus» kept «c est», «pas d écharpe» kept «d écharpe»: the
corrected line printed under the check was still wrong in three places.
"""

from __future__ import annotations

import json
import re
from datetime import timedelta

import pytest

from app.services import correction_contract
from app.services.llm_service import LLMResult

# ---------------------------------------------------------------------------
# #807: the participle after an auxiliary
# ---------------------------------------------------------------------------

FORGE_INVITE = "L ete dernier, il a invite Lila au cinema."
FORGE_EXPLIQUER = "La semaine derniere, ils ont expliquer la methode de Gus. Mais c est quoi, cette methode ?"
FORGE_APPELE = "Avant-hier, tu as appele la banque."
JOURNAL_RETELL = (
    "Hier soir, je suis arrive au Mistral avec la cle de ma grand-mère. Gus m a demande qui j etais, "
    "et Margaux m a donne la cle."
)

WALK_PARTICIPLES = [
    (FORGE_INVITE, "a invité"),
    (FORGE_EXPLIQUER, "ont expliqué"),
    (FORGE_APPELE, "as appelé"),
    (JOURNAL_RETELL, "suis arrivé"),
    (JOURNAL_RETELL, "m'a demandé"),
    (JOURNAL_RETELL, "m'a donné"),
]


def _named(errata: list[dict], right: str) -> bool:
    participle = right.split()[-1]
    return any(participle in str(item.get("corrected_target") or "") for item in errata)


@pytest.mark.parametrize(("sentence", "right"), WALK_PARTICIPLES)
def test_the_floor_names_the_participle_after_an_auxiliary(sentence, right):
    errata = correction_contract.deterministic_errata(sentence, language="en")
    assert _named(errata, right), (
        f"«{sentence}»: the basic check never names «{right}»; it listed "
        f"{[(e['learner_text'], e['corrected_target']) for e in errata]}"
    )
    assert right in correction_contract.repair_text(sentence)


@pytest.mark.parametrize(("sentence", "right"), WALK_PARTICIPLES)
def test_la_forge_basic_check_names_the_participle(sentence, right):
    """La Forge's free sentence with no model to read it (#724's fallback)."""
    from app.services.atelier import _with_rule_fixes

    correction = _with_rule_fixes({}, sentence, language="en")
    assert _named(correction["errata"], right), correction["errata"]


@pytest.mark.parametrize(
    "right",
    [
        "Il a une invite à répondre.",
        "Il invite Lila.",
        "Il a demandé.",
        "Gus m'a demandé qui j'étais.",
        "J'ai envie de partir.",
        "J'ai hâte de te voir.",
        "J'en ai marre.",
        "Elle est calme.",
        "C'est pratique.",
        "La salle est vide.",
        "Il a entre vingt et trente ans.",
        "C'est entre nous.",
        "Il y a place pour deux.",
        "Je suis prêt a manger.",
        "Il va arriver demain.",
        "Je n'ai rien à manger.",
        "Ils ont classe le lundi.",
    ],
)
def test_a_form_that_is_not_after_an_auxiliary_or_is_a_word_is_left_alone(right):
    rules = [edit.rule_id for edit in correction_contract.deterministic_edits(right)]
    assert "FR_PARTICIPLE" not in rules, f"«{right}» is French as written: {rules}"


def _er_verbs() -> list[str]:
    from app.services.lexical_coverage import load_lexicon

    lemmas = load_lexicon().lemmas
    return sorted(
        word
        for word, entry in lemmas.items()
        if entry.get("pos") == "verb" and word.endswith("er") and entry.get("band") in {"A1", "A2"}
    )


def _third_person(verb: str) -> str:
    """The plain written «il …» form a learner types for the participle: «invite», «appele»."""
    return verb[:-2] + "e"


#: avoir forms with the subject each one takes.
_AVOIR = [("j'", "ai"), ("tu", "as"), ("il", "a"), ("nous", "avons"), ("vous", "avez"), ("ils", "ont")]
#: être forms: the -er verbs that make their passé composé with être.
_ETRE = [("je", "suis"), ("tu", "es"), ("il", "est"), ("nous", "sommes"), ("vous", "êtes"), ("ils", "sont")]
_ETRE_ER_VERBS = ("aller", "arriver", "entrer", "rester", "tomber", "rentrer", "monter", "retourner")


def test_every_a1_a2_er_verb_after_every_auxiliary_is_caught():
    """The guard of #807's done-when: an -er verb of the A1–A2 lexicon, written as its
    infinitive or as its bare «il» form, after each auxiliary form, is named."""
    verbs = _er_verbs()
    assert len(verbs) > 150, verbs
    missed: list[str] = []
    for verb in verbs:
        participle = verb[:-2] + "é"
        cases = [(subject, aux) for subject, aux in _AVOIR]
        if verb in _ETRE_ER_VERBS:
            cases += _ETRE
        for subject, aux in cases:
            for written in (verb, _third_person(verb)):
                if written == "entre":
                    continue  # «entre» is the preposition: «il est entre deux chaises»
                glue = "" if subject.endswith("'") else " "
                sentence = f"Hier, {subject}{glue}{aux} {written} avec Lila."
                fixed = correction_contract.repair_text(sentence)
                if not re.search(rf"(?<!\w){participle}e?s?(?!\w)", fixed):
                    missed.append(f"{sentence} -> {fixed}")
    assert not missed, f"{len(missed)} missed: {missed}"


@pytest.fixture
def journal(db_engine, db_session):
    """The Journal's table, as ``tests/test_journal.py`` sets it up for its own tests."""
    from app.db.models.journal import JournalEntry

    JournalEntry.__table__.create(bind=db_engine, checkfirst=True)
    yield


def test_the_journal_basic_check_names_the_participles(journal, db_session, monkeypatch):
    """#807 done-when: the Journal's basic check (no model) on the walk's retell."""
    from app.config import settings
    from tests.test_journal import TODAY, _concept, _journey, _user, _write

    monkeypatch.setattr(settings, "ATELIER_CORRECTION_LLM_ENABLED", False)
    user = _user(db_session)
    _journey(db_session, user, local_date=TODAY - timedelta(days=1), concept=_concept(db_session))
    entry = _write(db_session, user, None, JOURNAL_RETELL)

    rights = " | ".join(str(item.get("corrected_fr")) for item in entry.correction["errata"])
    for participle in ("arrivé", "demandé", "donné"):
        assert participle in rights, f"the Journal's basic check never names «{participle}»: {rights}"


# ---------------------------------------------------------------------------
# #773: La Forge's relecture keeps the floor's fixes
# ---------------------------------------------------------------------------

ESTCE_FORGE = "Est-ce que on commence le travail ?"
ESTCE_RECALL = "Est-ce que il pleut ?"


class _ModelSaysRight:
    """The model reading the free sentence: «correct», nothing to fix."""

    def __init__(self) -> None:
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


def _relecture(db_session, monkeypatch, text: str):
    from app.core.forge import Rung
    from app.services import verdicts
    from app.services.atelier import AtelierCorrectionService
    from app.services.forge import ForgeService, _store_state, forge_state_of
    from tests.test_forge_integration import _forge_session

    monkeypatch.setattr(AtelierCorrectionService, "_can_schedule_ai_review", lambda self: True)
    model = _ModelSaysRight()
    model.text = text
    user, concept, session, _shared = _forge_session(db_session)
    forge = ForgeService(db_session)
    forge.attach(user=user, session=session, keep_concepts=True)
    state = forge_state_of(session)
    state.tracks[0].rung = int(Rung.PRODUCE)
    _store_state(session, state)
    db_session.commit()
    nxt = forge.next_item(user=user, session=session)
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
    landed = service.run_ai_review_for_attempt(attempt.id)
    assert model.calls == 1
    return verdicts.from_forge(landed.correction_payload, text=text, verdict=landed.verdict).to_dict(), landed


@pytest.mark.parametrize(("text", "fix"), [(ESTCE_FORGE, "qu'on"), (ESTCE_RECALL, "qu'il")])
def test_la_forge_does_not_call_a_missing_elision_right(db_session, monkeypatch, text, fix):
    check, attempt = _relecture(db_session, monkeypatch, text)
    edits = [(edit["span"], edit["replacement"]) for edit in check["edits"]]
    assert attempt.verdict not in {"correct", "accepted"}, (
        f"«{text}» is marked «{attempt.verdict}» with {edits}: the rules floor names «{fix}» and the recall "
        "drill marks the same elision wrong"
    )
    assert check["outcome"] != "right", check
    assert any(fix in replacement for _span, replacement in edits), edits


def test_the_recall_item_and_the_forge_free_check_agree():
    """The recall drill's Wrong/Right pair and the free check read one rule: both sentences
    are named by the floor La Forge now holds its model to."""
    for wrong, right in ((ESTCE_RECALL, "Est-ce qu'il pleut ?"), (ESTCE_FORGE, "Est-ce qu'on commence le travail ?")):
        assert correction_contract.repair_text(wrong) == right
        assert correction_contract.deterministic_edits(right) == []


def test_a_right_sentence_the_model_passes_stays_right(db_session, monkeypatch):
    check, attempt = _relecture(db_session, monkeypatch, "Est-ce qu'on commence le travail ?")
    assert attempt.verdict == "correct", check


# ---------------------------------------------------------------------------
# #810: «pas a», «c est à», «d echarpe»
# ---------------------------------------------------------------------------

COURRIER_MARGAUX = "Salut Margaux ! Mais je n ai pas d echarpe, ce n est pas a moi. Peut-être c est a Gus ?"
COURRIER_FIBRE = "Mais je suis pas a la maison, je dors a l hotel !"


def test_the_courrier_line_is_fixed_in_every_place():
    assert correction_contract.repair_text(COURRIER_MARGAUX) == (
        "Salut Margaux ! Mais je n'ai pas d'écharpe, ce n'est pas à moi. Peut-être c'est à Gus ?"
    )
    assert correction_contract.repair_text(COURRIER_FIBRE) == "Mais je suis pas à la maison, je dors à l'hôtel !"


@pytest.mark.parametrize(
    "right",
    [
        "Il n'a pas à manger.",
        "Il n'a pas a manger.",
        "Elle ne l'a pas aimé.",
        "Il n'a pas a la clé.",
        "Je n'ai pas d'argent.",
        "La vitamine D est utile.",
    ],
)
def test_the_negation_fix_leaves_avoir_alone(right):
    assert correction_contract.repair_text(right) == right
