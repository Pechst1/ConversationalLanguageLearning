# ruff: noqa: F811 - the v2 fixture is imported by name and requested as an argument
"""R4 (walk of 19 Nov 2026): the drill explains in the mother tongue from B1, as the scene does.

Owner decision 18 Nov 2026 (``a159dc32``): fiction stays French, the interface is French
from B1, and an explanation is in the learner's mother tongue at every level. The scene's
correction notes were moved; the walk of 19 Nov showed the drill left out. An English
B1.1 learner read, in French:

* La Forge's wrong-answer notes («« lampe » est féminin.»), because
  ``AtelierCorrectionService.explanation_language`` was the chrome language;
* the day's drill rule line and the Rappel's note («Chaque nom est masculin ou féminin :
  un café, une table.»), because the unit brief's ``rule_short_native`` was read in the
  chrome language;
* the scene words' glosses in the deck («la succession — ensemble des démarches
  légales…»), because the scene writes its lexicon glosses in its control language
  (French from B1) and the deck showed them as the mother-tongue gloss.

Pinned here, without a model call: for a B1.1 learner with English or German, those
come in that language while the chrome stays French; an A1 learner is unchanged.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import Session

from app.db.models.grammar import GrammarConcept
from app.db.models.user import User
from app.services import atelier as atelier_module
from app.services import grammar_items
from app.services.atelier import AtelierCorrectionService
from app.services.chrome_language import user_chrome_language
from app.services.journey_contracts import LearningCandidate, TargetKind, TargetRef
from app.services.journey_learning import _with_grammar_briefs
from app.services.scene_deck import gloss_language, glosses_in_mother_tongue, mark_scene_words
from tests.test_wp_s4_one_picker import v2  # noqa: F401 - fixture

UN_UNE = "FR2_A11_UN_UNE"
#: The unit's one-line rule (catalogue ``rule_short``), per language.
RULE = {
    "en": "Every noun is masculine or feminine",
    "de": "Jedes Nomen ist männlich oder weiblich",
    "fr": "Chaque nom est masculin ou féminin",
}
#: «Je lui vois demain.» for «Je le vois demain.»: the slip's note, per language (#449).
OBJECT_NOTE = {"en": "direct object", "de": "direktes Objekt", "fr": "COD"}


def _learner(db: Session, *, native: str, level: str) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"r4-explain-{uuid.uuid4().hex[:10]}@example.com",
        hashed_password="x",
        native_language=native,
        target_language="fr",
        proficiency_level=level[:2],
        cefr_estimate=level,
        daily_goal_minutes=20,
    )
    db.add(user)
    db.commit()
    return user


# --------------------------------------------------------------------------- #
# La Forge: why an answer was wrong
# --------------------------------------------------------------------------- #


class _Stop(Exception):
    pass


def _forge_explanation_language(db: Session, monkeypatch, user: User) -> str:
    """The language ``submit_attempt`` sets for the attempt's explanations."""

    service = AtelierCorrectionService(db)
    seen: dict[str, str] = {}

    def correct(**_kwargs):
        seen["language"] = service.explanation_language
        raise _Stop

    monkeypatch.setattr(service, "correct", correct)
    monkeypatch.setattr(atelier_module, "session_vocabulary_context", lambda _session: [])
    with pytest.raises(_Stop):
        service.submit_attempt(
            session=SimpleNamespace(id=uuid.uuid4()),
            user=user,
            concept=None,
            round_name="transform",
            mode="rewrite",
            exercise_id="t1",
            answer_payload={"answers": {"t1": "Je lui vois demain."}},
            prompt_payload_override={"items": []},
            retest_of=uuid.uuid4(),
        )
    return seen["language"]


def _object_miss(language: str) -> str:
    service = AtelierCorrectionService(None)
    service.explanation_language = language
    item = {
        "id": "t1",
        "type": "directed_rewrite",
        "instruction": "Replace 'Marc' with 'le', the direct object pronoun.",
        "source": "Je vois Marc demain.",
        "expected_answer": "Je le vois demain.",
    }
    concept = GrammarConcept(id=7, external_id="FR2_B11_DOUBLE_PRONOUNS", name="Deux pronoms ensemble", level="B1", category="Pronouns")
    result = service._correct_transform_rule_based(concept, {"items": [item]}, {"answers": {"t1": "Je lui vois demain."}})
    [erratum] = result["errata"]
    return f"{erratum['why_wrong']} {erratum['repair_hint']}"


@pytest.mark.parametrize("native", ["en", "de"])
def test_a_b1_forge_miss_is_explained_in_the_mother_tongue(db_session: Session, monkeypatch, native: str) -> None:
    user = _learner(db_session, native=native, level="B1.1")

    assert user_chrome_language(user) == "fr"  # the chrome stays French from B1
    language = _forge_explanation_language(db_session, monkeypatch, user)
    assert language == native
    note = _object_miss(language)
    assert OBJECT_NOTE[native] in note, note
    assert "COD" not in note


def test_an_a1_forge_miss_is_unchanged(db_session: Session, monkeypatch) -> None:
    user = _learner(db_session, native="de", level="A1.1")

    assert user_chrome_language(user) == "de"
    assert _forge_explanation_language(db_session, monkeypatch, user) == "de"


# --------------------------------------------------------------------------- #
# The day's drill (Rappel, guided items): the rule line and a trap's reason
# --------------------------------------------------------------------------- #


def _brief(db: Session, user: User) -> dict:
    concept = db.query(GrammarConcept).filter(GrammarConcept.external_id == UN_UNE).one()
    candidate = LearningCandidate(
        target=TargetRef(kind=TargetKind.GRAMMAR, id=str(concept.id), label_fr=concept.name, concept_title=True),
        priority_score=1.0,
        due_since_days=0,
        estimated_seconds=60,
    )
    [out] = _with_grammar_briefs(db, user=user, candidates=[candidate], level=user.cefr_estimate)
    return out.metadata["grammar_brief"]


@pytest.mark.parametrize("native", ["en", "de"])
def test_a_b1_drill_explains_the_rule_in_the_mother_tongue(db_session: Session, v2, native: str) -> None:
    user = _learner(db_session, native=native, level="B1.1")
    brief = _brief(db_session, user)
    chrome = user_chrome_language(user)
    assert chrome == "fr"

    # The rule line the Rappel's note and the items' hint carry.
    assert brief["rule_short_native"].startswith(RULE[native]), brief["rule_short_native"]
    transform = grammar_items.transform_item(brief, language=chrome)
    assert transform is not None
    assert transform.hint_native.startswith(RULE[native]), transform.hint_native
    # The instruction is chrome: it stays French.
    assert transform.instruction_native == grammar_items.transform_instruction(
        transform.source_fr or "", transform.solution_fr or "", "fr"
    )
    # A choice's reason for its trap (#537) explains too.
    choose = grammar_items.choose_item(brief, language=chrome)
    if choose is not None and choose.why_native:
        assert choose.why_native == grammar_items.pair_why(
            next(pair for pair in brief["contrast_pairs"] if pair.get("why")), native
        )


def test_an_a1_drill_is_unchanged(db_session: Session, v2) -> None:
    user = _learner(db_session, native="de", level="A1.1")
    brief = _brief(db_session, user)

    assert "explain_language" not in brief
    assert brief["rule_short_native"].startswith(RULE["de"])
    transform = grammar_items.transform_item(brief, language="de")
    assert transform is not None and transform.hint_native.startswith(RULE["de"])


# --------------------------------------------------------------------------- #
# The day deck: a word taken from the day's scene
# --------------------------------------------------------------------------- #

SUCCESSION_FR = "ensemble des démarches légales pour transmettre les biens d'une personne décédée"


def _journey(control_language: str) -> SimpleNamespace:
    brief = {"control_language": control_language, "story_context": {"draft": {"lexicon": []}}}
    return SimpleNamespace(steps=[SimpleNamespace(private_task={"scenario_brief": brief})])


def _deck_card(*, control_language: str, native: str, gloss: str) -> dict:
    lines = {7: {"sentence_fr": "Pas avant les papiers de la succession.", "translation": None, "gloss": gloss}}
    lines = glosses_in_mother_tongue(lines, written_in=gloss_language(_journey(control_language)), native=native)
    payload = {"new_words": [{"word_id": 7, "word": "succession", "translation": "succession; inheritance, estate"}]}
    return mark_scene_words(payload, scene_ids={7}, lines=lines, gloss_language=native)["new_words"][0]


@pytest.mark.parametrize("native", ["en", "de"])
def test_a_b1_scene_word_is_not_glossed_in_french(native: str) -> None:
    """The walk's day 3: the scene (control language «fr» at B1) glossed «succession» in
    French; the card keeps the dictionary's gloss in the mother tongue."""

    card = _deck_card(control_language="fr", native=native, gloss=SUCCESSION_FR)
    assert card["translation"] == "succession; inheritance, estate"
    assert SUCCESSION_FR not in str(card)
    # The scene line is still quoted: only the gloss is the dictionary's.
    assert card["example_sentence"] == "Pas avant les papiers de la succession."
    assert card["scene_word"] is True


def test_an_a1_scene_word_keeps_the_scenes_gloss() -> None:
    card = _deck_card(control_language="de", native="de", gloss="der Nachlass")
    assert card["translation"] == "der Nachlass"
    assert card["translation_language"] == "de"
