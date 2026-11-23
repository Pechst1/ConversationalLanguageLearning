"""#1028 - failing the optional test-out never lowers a rung the learner already holds.

Walk of 23 Nov 2026 (`a2-en`, day 2): «Passé composé with avoir» stood at Level 5
(``forge_rung`` 4). The end sheet offered its test; the learner got 1 of 3 right and
read «Your practice picks up at level 2.»: ``forge_rung`` went from 4 to 1.

ROOT CAUSE: ``ForgeService._finish_test_out`` wrote the test-out's placement (the
lowest rung it failed, right for a rule *entering* the forge) as the rule's level,
instead of merging it with the level the learner already holds (owner decision #88:
a miss never steps the level down).
"""
from __future__ import annotations

from datetime import UTC, datetime

from app.core import forge as core
from app.core.forge import Rung
from app.services.forge import ForgeService, _store_state, forge_state_of
from app.services.grammar import GrammarService
from tests.test_atelier import _concept, _user

#: The walk's test: 1 of 3 right, the build item and the production item missed.
ONE_OF_THREE = [(int(Rung.DISCRIMINATE), True), (int(Rung.BUILD), False), (int(Rung.PRODUCE), False)]


def _finish(db_session, *, held: int | None, results):
    user = _user(db_session)
    concept = _concept(db_session, "FR_A2_NEG_001")
    progress = GrammarService(db_session).get_or_create_progress(user_id=user.id, concept_id=concept.id)
    progress.forge_rung = held
    db_session.add(progress)
    db_session.commit()
    forge = ForgeService(db_session)
    session = forge.start_test_out(user=user, concept_id=concept.id, short=True)
    state = forge_state_of(session)
    state.result = core.evaluate_test_out(results).to_dict()
    forge._finish_test_out(user=user, session=session, state=state, now=datetime.now(UTC))
    _store_state(session, state)
    db_session.commit()
    db_session.refresh(progress)
    return progress, forge_state_of(session).result, session.recap_payload["test_out"]


def test_failed_test_keeps_level(db_session) -> None:
    progress, result, recap = _finish(db_session, held=int(Rung.PRODUCE), results=ONE_OF_THREE)
    assert result["passed"] is False
    assert progress.forge_rung == int(Rung.PRODUCE), (
        f"a failed test-out moved the rule from level 5 to level {progress.forge_rung + 1}"
    )
    assert result["placement_rung"] == int(Rung.PRODUCE), (
        f"the sheet says «picks up at level {result['placement_rung'] + 1}» for a rule held at level 5"
    )
    assert recap["placement_rung"] == int(Rung.PRODUCE)
    assert result["placement_rung_name"] == core.rung_name(Rung.PRODUCE)


def test_failed_test_places_a_new_rule(db_session) -> None:
    progress, result, _recap = _finish(db_session, held=None, results=ONE_OF_THREE)
    assert progress.forge_rung == int(Rung.BUILD)
    assert result["placement_rung"] == int(Rung.BUILD)


def test_failed_test_lifts_a_lower_rule(db_session) -> None:
    progress, result, _recap = _finish(db_session, held=int(Rung.RECOGNISE), results=ONE_OF_THREE)
    assert progress.forge_rung == int(Rung.BUILD)
    assert result["placement_rung"] == int(Rung.BUILD)


def test_passed_test_tops_the_rule(db_session) -> None:
    passed = [(int(Rung.DISCRIMINATE), True), (int(Rung.BUILD), True), (int(Rung.PRODUCE), True)]
    progress, result, _recap = _finish(db_session, held=int(Rung.BUILD), results=passed)
    assert result["passed"] is True
    assert progress.forge_rung == int(core.TOP_RUNG)
