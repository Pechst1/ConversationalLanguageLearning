"""#826 — La Forge's counter: an answer nobody could check does not grow the séance.

16 Nov walk (fake provider): day 1, item 6/6 came back «basic check only» and
the counter turned into 6/7; on day 2 every unchecked line added one more item
(5/6 → 5/8 → 6/9 → 7/10), so «Beenden» kept moving away and the learner left
through the header at 8/10.

#708 made the counter a dry run of the composer: the items the séance deals
from here if every one is answered right. An unchecked answer is neither right
nor the learner's miss, but it does not climb, so the dry run after it needs one
more item to take the rule where the right answer would have, and the composer
deals it. The length the learner was shown moved under an outcome they did not
cause. The séance's end is now a promise only a checked answer can move.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core import forge as core
from app.core.forge import ForgeState, ForgeUnit, Verdict

#: «Nur Grundprüfung»: free production's instant local check, its relecture pending.
BASIC_CHECK_ONLY = Verdict(core.OUTCOME_INCORRECT, checked=False, local=core.OUTCOME_CORRECT)
#: «Prüfung nicht verfügbar»: nobody could read it, and no relecture is coming.
NOT_AVAILABLE = Verdict(core.OUTCOME_INCORRECT, checked=False)
#: «Nur Grundprüfung» where the local check found nothing to go on.
BASIC_CHECK_NO_HIT = Verdict(core.OUTCOME_INCORRECT, checked=False, local=core.OUTCOME_INCORRECT)
#: What a relecture that never lands leaves the basic-checked answer with.
NEVER_READ = Verdict(core.OUTCOME_INCORRECT, checked=False)


def _days_seance(rung: int = 0) -> ForgeState:
    from app.services.forge_picker import DAY_REVIEW_SHARE

    return ForgeState.seance([ForgeUnit(1, "today", rung=rung)], length=16, review_share=DAY_REVIEW_SHARE)


def _play(state: ForgeState, verdicts: dict[int, Verdict], *, settle: dict[int, Verdict] | None = None) -> list[tuple[int, int, int]]:
    """Play the séance to its end: (item number, length shown before, length shown after).

    ``verdicts`` maps an item number (1-based) to its verdict, every other item
    is right; ``settle`` maps an item number to the verdict its relecture lands
    with, right after the answer.
    """

    shown: list[tuple[int, int, int]] = []
    for _ in range(40):
        slot = state.next_slot()
        if slot is None:
            break
        item = state.position + 1
        before = state.shown_length
        state.record(
            concept_id=slot.concept_id,
            rung=slot.rung,
            verdict=verdicts.get(item, Verdict.right()),
            fingerprint=f"item-{item}",
            role=slot.role,
        )
        if settle and item in settle:
            state.settle(state.history[-1], settle[item])
        shown.append((item, before, state.shown_length))
    return shown


def test_two_unchecked_keep_the_length() -> None:
    length = _days_seance().shown_length
    assert length >= core.MIN_SEANCE_ITEMS

    state = _days_seance()
    shown = _play(state, {2: BASIC_CHECK_ONLY, 4: NOT_AVAILABLE}, settle={2: NEVER_READ})

    grown = [(item, before, after) for item, before, after in shown if before != length or after != length]
    assert not grown, (
        f"the séance opened on «of {length}», and an unchecked answer moved it: "
        + ", ".join(f"item {item}: {before} → {after}" for item, before, after in grown)
    )
    assert state.finished and state.position == length, (
        f"«Beenden» came at {state.position} of {length}, not on the counter's last item"
    )
    assert state.shown_length == length, "the end sheet counts the items answered"


def test_unchecked_last_item_ends_it() -> None:
    """Day 1 of the walk: item 6/6 came back «basic check only» and the counter read 6/7."""

    length = _days_seance().shown_length
    state = _days_seance()
    shown = _play(state, {length: BASIC_CHECK_NO_HIT}, settle={length: NEVER_READ})
    _item, before, after = shown[length - 1]
    assert (before, after) == (length, length), (
        f"item {length}/{before} came back unchecked and the counter read {length}/{after}"
    )
    assert state.finished and state.position == length


def test_checked_miss_still_grows() -> None:
    """The promise holds against the unchecked answer only: a checked miss keeps the
    rung and books a reprise, so the séance may grow by the item that costs (#708)."""

    plain = _days_seance()
    _play(plain, {3: Verdict.wrong()})

    state = _days_seance()
    _play(state, {2: NOT_AVAILABLE, 3: Verdict.wrong()})
    assert state.position == plain.position, (
        f"a checked miss grows a séance of {plain.position}; after an unchecked answer it ended at {state.position}"
    )


def test_view_counter_holds(db_session: Session) -> None:
    """End to end on the forge's view, the real item provider: the counter each screen
    reads and the end sheet's «answered» are one number from item 1 to «Beenden»."""

    from app.services.forge import ForgeService, _store_state, forge_state_of
    from tests.test_forge_integration import _forge_session

    user, concept, session, _shared = _forge_session(db_session, "FR_A2_NEG_001")
    state = _days_seance()
    state.tracks[0].concept_id = concept.id
    _store_state(session, state)
    db_session.add(session)
    db_session.commit()
    service = ForgeService(db_session)
    service.coach_for = lambda *_args, **_kwargs: None  # type: ignore[method-assign]

    unchecked = {2: NOT_AVAILABLE, 4: BASIC_CHECK_ONLY}
    first = service.view(user=user, session=session)
    length = first["length"]
    assert first["next"] is not None and first["next"]["length"] == length

    screens: list[tuple[int, int, bool]] = []
    for _ in range(30):
        view = service.view(user=user, session=session)
        if view["finished"]:
            break
        item = view["next"]
        assert item is not None
        number = view["answered"] + 1
        state = forge_state_of(session)
        state.record(
            concept_id=concept.id,
            rung=int(item["rung"]),
            verdict=unchecked.get(number, Verdict.right()),
            fingerprint=item["fingerprint"],
        )
        if number == 4:
            state.settle(state.history[-1], NEVER_READ)
        _store_state(session, state)
        db_session.commit()
        after = service.view(user=user, session=session)
        screens.append((after["answered"], after["length"], after["finished"]))
        if after["next"] is not None:
            assert after["next"]["length"] == after["length"]

    assert [total for _answered, total, _done in screens] == [length] * len(screens), (
        f"the counter opened on «of {length}» and read " + ", ".join(f"{n}/{t}" for n, t, _d in screens)
    )
    answered, total, finished = screens[-1]
    assert finished and answered == total == length, f"«Beenden» at {answered} of {total}"
    assert all(not done for _n, _t, done in screens[:-1]), "«Beenden» came before the counter's last item"
