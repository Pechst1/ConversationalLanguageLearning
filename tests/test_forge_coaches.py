"""WP-S5 — every rule has a coach, and free use is a two-line scene with them.

* One cast member per family of units covers every A1–A2 unit; a v1 concept's
  authored rule card keeps its speaker, so the card's face is the feedback's.
* The coach rides on the séance: the atelier concept, the forge's ``next`` and
  ``rules``, and every observed answer (``coach_mood``: happy on a checked
  right answer, cross on a checked wrong one, moved when the rule became held).
* The free-use rung is a scene: the coach's line, then the learner's reply
  that needs the rule — in the conversation-turn shape the page renders.
* The learner's own story (the living-story chronicle, read only) is preferred.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.db.models.atelier import AtelierSession
from app.db.models.grammar import GrammarConcept
from app.db.models.user import User
from app.services import forge_coaches as fc
from app.services import item_bank as ib
from app.services.atelier import AtelierExerciseGenerator, AtelierScheduler, session_exercise_set
from app.services.forge_story import focus_from_chronicle
from app.services.rule_cards import rule_card_for

ROOT = Path(__file__).resolve().parents[1]
REQUIREMENT = {"concept_id": 1, "external_id": "X", "label": "X", "target_count": 1}


def _units(level: set[str], version: str = "v2") -> list[str]:
    with (ROOT / "templates" / f"french_core_grammar_{version}.tsv").open(encoding="utf-8") as handle:
        return [row["external_id"] for row in csv.DictReader(handle, delimiter="\t") if row["cefr_level"] in level]


# --------------------------------------------------------------------------- #
# The coach map
# --------------------------------------------------------------------------- #


def test_every_a1_a2_unit_has_exactly_one_coach() -> None:
    data = json.loads(fc.COACHES_PATH.read_text(encoding="utf-8"))
    listed = [unit for family in data["families"] for unit in family["units"]]
    assert len(listed) == len(set(listed)), "a unit belongs to one family"
    for unit in _units({"A1", "A2"}):
        coach = fc.coach_for_unit(unit)
        assert coach is not None, unit
        assert coach["family_title"]["en"] and coach["family_title"]["fr"] and coach["family_title"]["de"]


def test_the_coaches_are_the_drawn_cast() -> None:
    bible = json.loads((ROOT / "app" / "prompts" / "serial" / "world_bible_paris_v2.json").read_text(encoding="utf-8"))
    cast = {member["id"] for member in bible["cast"]} | {"landlord_marchand"}
    portraits = ROOT / "web-frontend" / "public" / "assets" / "serial" / "characters"
    for coach_id in fc.cast_ids():
        assert coach_id in cast, coach_id
        for mood in fc.MOODS:
            assert (portraits / coach_id / f"portrait-{mood}.webp").exists(), (coach_id, mood)


def test_the_map_is_coherent() -> None:
    assert fc.coach_for_unit("FR2_A11_LE_LA")["name"] == "Margaux"  # articles at the counter
    assert fc.coach_for_unit("FR2_A21_PC_AVOIR")["name"] == "Gus"  # past tenses
    assert fc.coach_for_unit("FR2_A11_QUESTIONS")["name"] == "Romy"  # questions, journalism
    assert fc.coach_for_unit("FR2_A11_ADJ_AGREEMENT")["name"] == "Lila"  # adjectives, description
    assert fc.coach_for_unit("FR2_A21_COD")["name"] == "Marin"  # pronouns
    assert fc.coach_for_unit("FR2_A11_ALLER_VENIR")["name"] == "Marin"  # verbs of movement


def test_a_rule_card_speaker_is_the_rule_coach() -> None:
    v1 = _units({"A1", "A2"}, "v1")
    with_cards = [external_id for external_id in v1 if (rule_card_for(external_id) or {}).get("speaker")]
    assert with_cards
    for external_id in with_cards:
        assert fc.coach_for_concept(external_id)["id"] == rule_card_for(external_id)["speaker"], external_id
    for external_id in v1:
        if ib.units_for_external_id(external_id):
            assert fc.coach_for_concept(external_id) is not None, external_id


@pytest.mark.parametrize(
    ("correct", "checked", "held", "mood"),
    [
        (True, True, False, "happy"),
        (False, True, False, "cross"),
        (True, True, True, "moved"),
        (True, False, False, "neutral"),
        (None, True, False, "neutral"),
    ],
)
def test_the_coach_face_follows_the_answer(correct, checked, held, mood) -> None:
    assert fc.coach_mood(correct=correct, checked=checked, held=held) == mood


# --------------------------------------------------------------------------- #
# Free use: a two-line scene
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("unit", ["FR2_A21_COD", "FR2_A11_IL_Y_A", "FR2_A21_PC_AVOIR", "FR2_A11_JE_VOUDRAIS", "FR2_A12_TIME"])
def test_free_use_is_a_two_line_scene_with_the_coach(unit: str) -> None:
    coach = fc.coach_for_unit(unit)
    detector = ib.unit_detector(unit)
    scenes = [
        scene
        for item in ib.default_bank().generate(unit, 20, seed=f"scene:{unit}", detector=detector)
        if (scene := ib.scene_item(item, coach=coach, requirement=REQUIREMENT))
    ]
    assert len(scenes) >= 12, unit
    for scene in scenes:
        coach_line, reply = scene["scene"]["lines"]
        assert coach_line["speaker"] == coach["id"] and coach_line["fr"] and coach_line["en"]
        assert reply["speaker"] == "learner" and reply["fr"] == scene["example_answer"]
        # The reply needs the rule, and is graded against it.
        assert scene["target_span"] in scene["example_answer"]
        if detector is not None:
            assert detector(scene["example_answer"]), scene["example_answer"]
        # The page's conversation turn: a byline and one prompt.
        assert scene["type"] == "conversation_turn"
        assert scene["character"] == {"id": coach["id"], "name": coach["name"], "register": coach["register"]}
        assert coach_line["fr"] in scene["prompt"] and reply["en"] in scene["prompt"]
        assert not ib.spoils("production", scene)
        # «Tu …, Lila ?» said by the coach to the learner: the name is gone.
        assert coach["name"].split()[-1] not in f"{coach_line['fr']} {reply['fr']}"


def test_a_question_answer_item_splits_into_the_coachs_question_and_the_reply() -> None:
    coach = fc.coach_for_unit("FR2_A21_COD")
    item = next(
        item
        for item in ib.default_bank().generate("FR2_A21_COD", 30, seed="split")
        if item.frame_id.startswith("cod-tu")
    )
    scene = ib.scene_item(item, coach=coach, requirement=REQUIREMENT)
    question, reply = scene["scene"]["lines"]
    assert question["fr"].endswith("?") and question["fr"].startswith("Tu ")
    assert reply["fr"].startswith("Oui, je ")


def test_the_scene_is_valid_in_a_seance_set(db_session: Session) -> None:
    AtelierScheduler(db_session).ensure_catalog()
    concept = db_session.query(GrammarConcept).filter(GrammarConcept.external_id == "FR_A1_NOUN_001").one()
    user = User(id=uuid4(), email=f"{uuid4()}@example.com", hashed_password="x", target_language="fr", cefr_estimate="A1.1")
    db_session.add(user)
    db_session.commit()
    session = AtelierSession(user_id=user.id, selected_concept_ids=[concept.id], quote_payload={}, status="in_progress",
                             recap_payload={})
    db_session.add(session)
    db_session.commit()

    exercise_set = session_exercise_set(db_session, user=user, session=session, concept=concept, fast_path=True)

    payload = exercise_set.payload
    assert AtelierExerciseGenerator.validate_payload(payload, concept=concept)
    assert payload["coach"]["id"] == "margaux_barman"
    turn = payload["output_ladder"]["conversation"]["items"][0]
    assert turn["scene"]["lines"][0]["speaker"] == "margaux_barman"
    assert turn["character"]["name"] == "Margaux"


def test_a_coached_scene_keeps_its_coach_over_the_legacy_serial_character() -> None:
    from app.api.v1.endpoints.atelier import _with_serial_conversation

    payload = {"output_ladder": {"conversation": {"items": [{"id": "x", "scene": {"lines": []}, "character": {"name": "Lila"}}]}}}
    context = {"character": {"name": "Someone"}, "thread_id": "t", "episode_index": 0, "scene_context": ""}
    assert _with_serial_conversation(payload, context=context, concept=None) is payload


# --------------------------------------------------------------------------- #
# The forge serves the coach
# --------------------------------------------------------------------------- #


def test_the_forge_serves_the_coach_and_their_face(db_session: Session) -> None:
    from app.services.atelier import AtelierCorrectionService
    from app.services.forge import ForgeService
    from tests.test_forge_integration import _forge_session, _right, _wrong

    user, concept, session, _shared = _forge_session(db_session, "FR_A2_NEG_001")
    forge = ForgeService(db_session)
    forge.attach(user=user, session=session, keep_concepts=True)
    expected = fc.coach_for_concept("FR_A2_NEG_001")
    assert expected["id"] == "margaux_barman"

    view = forge.view(user=user, session=session)
    assert view["rules"][0]["coach"] == expected
    assert view["next"]["coach"] == expected

    service = AtelierCorrectionService(db_session)
    moods = []
    for answer in (_right, _wrong):
        nxt = forge.next_item(user=user, session=session)
        attempt = service.submit_attempt(
            session=session,
            user=user,
            concept=concept,
            round_name=nxt["round"],
            mode=nxt["mode"],
            exercise_id=f"forge:{concept.id}:{nxt['round']}:{nxt['item_id']}",
            answer_payload=answer(nxt["item"], nxt["round"], nxt["mode"]),
        )
        forge.observe_attempt(user=user, session=session, attempt=attempt)
        db_session.refresh(attempt)
        moods.append(attempt.correction_payload["forge"]["coach_mood"])
        assert attempt.correction_payload["forge"]["coach"] == expected
        assert attempt.correction_payload["forge"]["held"] is False
    assert moods == ["happy", "cross"]


def test_the_atelier_concept_carries_its_coach(db_session: Session) -> None:
    from app.services.atelier import serialize_concept

    AtelierScheduler(db_session).ensure_catalog()
    concept = db_session.query(GrammarConcept).filter(GrammarConcept.external_id == "FR_A1_SYN_001").one()
    assert serialize_concept(concept)["coach"]["name"] == "Romy"


# --------------------------------------------------------------------------- #
# The learner's own story
# --------------------------------------------------------------------------- #


def test_the_chronicle_names_the_story_the_bank_prefers() -> None:
    chronicle = [
        {"kind": "season", "characters": ["lila_bonnet"], "facts": []},
        {"characters": ["romy_tremblay", "user"], "location_id": "newsroom"},
        {"characters": ["augustin_de_roncourt"], "location_id": "brocante"},
    ]
    assert focus_from_chronicle(chronicle) == {"lila", "romy", "redaction", "gus", "brocante"}
    assert focus_from_chronicle(None) == frozenset()
