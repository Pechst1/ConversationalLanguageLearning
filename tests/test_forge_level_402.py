"""#402: La Forge's level legend, the level carried to the next day, «Ta phrase».

Walk 31 Oct (`a2-en`): the header said «Wrong: down one» while a miss kept the
level (owner decision #88); day 1's end sheet said «Level 5» and day 2's header
«Level 4» for the same rule; and a line of the learner's "own" sentences carried
a word the exercise had printed.

Root cause: three places each hard-coded their own idea of the level. The
legend was prose, the due rule's warm-up *was* the level (it lowered the
staircase's rung and, with it, the stored level), and «mine» claimed every word
of a line for the learner.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core import forge as core
from app.core.forge import ForgeState, Rung, Verdict
from app.db.models.atelier import AtelierAttempt
from app.db.models.grammar import UserGrammarProgress
from app.services.forge import PickedUnit, forge_units
from tests.test_forge_drills import _error, _forge_seance


def _due_state(db: Session, *, stored_rung: int) -> tuple[ForgeState, int]:
    from tests.test_atelier import _concept, _user

    user = _user(db)
    concept = _concept(db, "FR_A2_NEG_001")
    now = datetime.now(UTC)
    db.add(
        UserGrammarProgress(
            user_id=user.id,
            concept_id=concept.id,
            forge_rung=stored_rung,
            reps=4,
            stability=9.0,
            introduced_at=now - timedelta(days=2),
        )
    )
    db.commit()
    units = forge_units(db, user, [PickedUnit(concept.id, "due")], now=now)
    return ForgeState.seance(units, length=8), concept.id


def test_the_legend_states_the_rule_the_staircase_applies(db_session: Session):
    user, _concept, session, forge = _forge_seance(db_session, rung=Rung.BUILD)
    rule = forge.view(user=user, session=session).get("level_rule")
    assert rule is not None, "the forge view does not tell the page what a right or wrong answer does"
    assert rule["right"] == core.step_rung(2, Verdict.right()) - 2
    assert rule["wrong"] == core.step_rung(2, Verdict.wrong()) - 2, (
        "the legend must state what a miss does to the level, as the staircase applies it"
    )


def test_a_due_rule_opens_the_next_day_at_the_level_it_ended_on(db_session: Session):
    state, concept_id = _due_state(db_session, stored_rung=int(Rung.PRODUCE))
    track = state.track(concept_id)
    assert track.rung == int(Rung.PRODUCE), (
        f"a rule that ended at level 5 (rung 4) is on level {track.rung + 1} the next day"
    )
    # The warm-up is how the first item is posed, not the learner's level.
    slot = state.next_slot()
    assert slot is not None and slot.rung == int(Rung.PRODUCE) - 1


def test_a_warm_up_miss_does_not_take_the_level_down(db_session: Session):
    state, concept_id = _due_state(db_session, stored_rung=int(Rung.PRODUCE))
    slot = state.next_slot()
    state.record(concept_id=concept_id, rung=slot.rung, verdict=Verdict.wrong())
    assert state.track(concept_id).rung == int(Rung.PRODUCE), "a miss on the easier warm-up lowered the level"
    # The item that comes back is the easier one again; a right answer there restores nothing it did not lose.
    again = state.track(concept_id)
    assert again.warmup == slot.rung
    state.record(concept_id=concept_id, rung=slot.rung, verdict=Verdict.right())
    assert state.track(concept_id).rung == int(Rung.PRODUCE)
    assert state.track(concept_id).warmup is None, "the warm-up is over once it was answered right"


def test_an_own_sentence_marks_only_the_words_the_learner_wrote(db_session: Session):
    from app.services.forge import BankItemProvider

    user, concept, session, _forge = _forge_seance(db_session, rung=Rung.TRANSFORM)
    printed = "Samedi dernier, tu es mis du sucre dans le café."
    attempt = AtelierAttempt(
        atelier_session_id=session.id,
        user_id=user.id,
        concept_id=concept.id,
        round="transform",
        mode="rewrite",
        exercise_id="x",
        prompt_payload={"items": [{"id": "i1", "source": printed}]},
        answer_payload={"answers": {"i1": "Samedi dernier, tu es mit du sucre dans le café."}},
        correction_payload={},
        verdict="incorrect",
        score_0_4=1.0,
    )
    db_session.add(attempt)
    db_session.commit()
    _error(
        db_session, user, learner="mit", corrected="mis", concept_id=concept.id,
        source_type="atelier", source_attempt_id=attempt.id,
    )
    provider = BankItemProvider.for_session(db_session, user=user, session=session)
    found = provider.mine_candidates(concept.id)
    assert found, "the slip was not offered as a repair at all"
    assert found[0].get("own_words") == "mit", "only the word the learner wrote is theirs, not «es»"
    item = provider.mine_item(concept_id=concept.id, exclude=set())
    assert item is not None
    assert "wrote this" not in item.payload["goal_l10n"]["en"], (
        "the card claims the whole line («You wrote this earlier») although the exercise printed most of it"
    )
