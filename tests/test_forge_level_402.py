"""#402 — the level a rule shows is the level the code applies, from one place.

Walk 31 Oct (fake provider, fresh A2.1 learner):

* every La Forge header explained «Wrong: down one», but a miss keeps the level
  (owner decision #88); the legend is now chosen from the staircase's own rule
  (``core.level_rule()``, sent as ``forge.level_rule``);
* day 1's end sheet said «Level 5» for a rule, day 2's header said «Level 4»: a
  due rule entered the séance one rung *below* its stored level (the warm-up was
  written into the level, ``forge_units``), and a miss on that warm-up stored the
  lower rung. The warm-up is now only how the first item is posed; the level is
  the stored one, and the end sheet reads the staircase (``ForgeState.level_read``)
  instead of recomputing a level from the last item's rung.
"""
from __future__ import annotations

import random
from datetime import UTC, datetime

from app.core import forge as core
from app.core.forge import ForgeState, ForgeUnit, Role, Rung, Verdict
from app.db.models.atelier import AtelierAttempt, AtelierSession
from app.db.models.grammar import UserGrammarProgress
from app.services.atelier import AtelierSRSService
from app.services.forge import ForgeService, PickedUnit, _store_state, forge_state_of, forge_units
from tests.test_atelier import _concept, _user

# -- 1. the legend's rule is the staircase's rule ---------------------------------


def test_level_rule_is_what_the_staircase_does() -> None:
    rule = core.level_rule()
    assert rule["wrong"] == 0, "owner decision #88: a miss never steps the level down inside a séance"
    for level in range(int(Rung.RECOGNISE), int(Rung.FREE_USE)):
        state = ForgeState.seance([ForgeUnit(1, Role.TODAY.value, level)], length=8)
        state.record(concept_id=1, rung=level, verdict=Verdict.wrong())
        assert state.track(1).rung - level == rule["wrong"]
        state = ForgeState.seance([ForgeUnit(1, Role.TODAY.value, level)], length=8)
        state.record(concept_id=1, rung=level, verdict=Verdict.right())
        assert state.track(1).rung - level == rule["right"]


def test_no_answer_ever_lowers_a_level_inside_a_seance() -> None:
    """#88 as a property: warm-ups, contrast pairs, spaced entries, provisional
    climbs taken back — no sequence of answers takes a level below where it began."""

    outcomes = [core.OUTCOME_CORRECT, core.OUTCOME_INCORRECT, core.OUTCOME_PARTIAL]
    for seed in range(300):
        rnd = random.Random(seed)
        units = [
            ForgeUnit(1, Role.TODAY.value, rnd.randint(0, 5)),
            ForgeUnit(2, Role.DUE.value, (lvl := rnd.randint(1, 5)), warmup=lvl - 1, needs_spaced=rnd.random() < 0.3),
            ForgeUnit(3, Role.CONTRAST.value, (c := rnd.randint(0, 5)), warmup=min(c, int(Rung.DISCRIMINATE))),
        ]
        state = ForgeState.seance(units, length=12)
        floor = {track.concept_id: track.rung for track in state.tracks}
        while (slot := state.next_slot()) is not None:
            if rnd.random() < 0.25:
                verdict = Verdict(core.OUTCOME_INCORRECT, checked=False, local=core.OUTCOME_CORRECT)
            else:
                verdict = Verdict(rnd.choice(outcomes))
            state.record(concept_id=slot.concept_id, rung=slot.rung, verdict=verdict)
            entry = state.history[-1]
            if not entry["checked"] and rnd.random() < 0.7:
                state.settle(entry, Verdict(rnd.choice(outcomes)))
            for track in state.tracks:
                assert track.rung >= floor[track.concept_id], (seed, state.history)
                floor[track.concept_id] = max(floor[track.concept_id], track.rung)


# -- 2. the end sheet, the stored level and the next day's header agree -----------


def _day(db_session, user, concept_id: int) -> tuple[AtelierSession, ForgeState]:
    units = forge_units(db_session, user, [PickedUnit(concept_id, Role.DUE.value)], now=datetime.now(UTC))
    state = ForgeState.seance(units, length=6)
    session = AtelierSession(
        user_id=user.id, selected_concept_ids=[concept_id], status="in_progress", quote_payload={},
        started_at=datetime.now(UTC),
    )
    db_session.add(session)
    db_session.flush()
    _store_state(session, state)
    return session, state


def test_seance_end_level_is_the_next_days_level(db_session) -> None:
    user = _user(db_session)
    concept = _concept(db_session, "FR_A2_NEG_001")
    stored = int(Rung.PRODUCE)  # «Level 5»
    db_session.add(UserGrammarProgress(user_id=user.id, concept_id=concept.id, forge_rung=stored, reps=3, stability=10))
    db_session.flush()
    service = ForgeService(db_session)

    # Day 2 (the rule is due): its header shows the stored level, not the warm-up's rung.
    session, state = _day(db_session, user, concept.id)
    view = service.view(user=user, session=session)
    assert view["rules"][0]["rung"] == stored, "the header reads the rule's level, not the warm-up step"
    assert view["level_rule"] == core.level_rule()
    slot = state.next_slot()
    assert slot.rung == stored - 1, "the warm-up is still posed one step easier"

    # The learner misses the warm-up.
    state.pending = {"concept_id": concept.id, "rung": slot.rung, "round": "transform"}
    _store_state(session, state)
    attempt = AtelierAttempt(
        atelier_session_id=session.id, user_id=user.id, concept_id=concept.id,
        round="transform", mode="rewrite", exercise_id=f"forge:{concept.id}:transform:w",
        prompt_payload={"items": [{"id": "w"}]}, answer_payload={"answers": {"w": "Je mange pas."}},
        correction_payload={"assessment_status": "checked", "checked": True},
        verdict="incorrect", score_0_4=1.0,
    )
    db_session.add(attempt)
    db_session.flush()
    service.observe_attempt(user=user, session=session, attempt=attempt)
    shown = attempt.correction_payload["forge"]
    assert shown["new_rung"] == stored, "a miss keeps the level (#88)"
    assert shown["level_before"] == stored

    recap = AtelierSRSService(db_session).complete_session(session=session, user=user)
    sheet = next(row for row in recap["forge"]["rules"] if row["concept_id"] == concept.id)["rung"]
    progress = (
        db_session.query(UserGrammarProgress)
        .filter(UserGrammarProgress.user_id == user.id, UserGrammarProgress.concept_id == concept.id)
        .one()
    )
    assert sheet == stored, f"the end sheet says Level {sheet + 1} after a missed warm-up at Level {stored + 1}"
    assert progress.forge_rung == sheet, "the stored level is the level the end sheet shows"

    # Day 3: the rule's first item opens at the level the sheet showed.
    next_session, _next_state = _day(db_session, user, concept.id)
    next_view = service.view(user=user, session=next_session)
    assert next_view["rules"][0]["rung"] == sheet


def test_sheet_takes_back_only_a_climb_still_being_read() -> None:
    state = ForgeState.seance([ForgeUnit(1, Role.TODAY.value, int(Rung.PRODUCE))], length=6)
    state.record(
        concept_id=1, rung=int(Rung.PRODUCE),
        verdict=Verdict(core.OUTCOME_INCORRECT, checked=False, local=core.OUTCOME_CORRECT),
    )
    assert state.track(1).rung == int(Rung.FREE_USE)
    assert state.level_read(1) == int(Rung.PRODUCE), "a provisional climb is not shown before it is read"
    state.settle(state.history[-1], Verdict.right())
    assert state.level_read(1) == state.track(1).rung == int(Rung.FREE_USE)


def test_forge_state_round_trips_the_warmup(db_session) -> None:
    user = _user(db_session)
    concept = _concept(db_session, "FR_A2_NEG_001")
    db_session.add(UserGrammarProgress(user_id=user.id, concept_id=concept.id, forge_rung=3, reps=3, stability=10))
    db_session.flush()
    session, state = _day(db_session, user, concept.id)
    again = forge_state_of(session)
    assert again.track(concept.id).rung == 3 and again.track(concept.id).warmup == 2
