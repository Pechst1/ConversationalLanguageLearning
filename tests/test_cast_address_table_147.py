"""#147: every authored turn, against what the registry says about the person it is for.

An authored page keeps its own reading of how a person speaks (``turns.turn_address``, read
from their lines). The registry reads the cast (``cast_registry.address_now``). This table walks
every turn of every tentpole, epilogue day and bridge, at every band, and asks that they agree.

It does not hide what it finds. ``KNOWN_DISAGREEMENTS`` is the data as it stands; a new
disagreement fails, and so does the end of a known one, so the list cannot rot.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.services import address, cast_registry
from app.services.season.bridges import bridge_page, load_bridges
from app.services.season.flags import effective_flags
from app.services.season.format import load_season
from app.services.season.page import _Ctx, _movement, display_names
from app.services.season.runtime import projected_turns
from app.services.season.turns import turn_address

BANDS = ("A1", "A2", "B1", "B2", "C1")
GUS = "augustin_de_roncourt"

#: REAL, reported on the PR, not fixed here: T3 A's page has Gus on «tu» from its first panel
#: («Tu marches derrière moi.», «promets-moi une chose : tu ne vends pas à Solvel.»), and
#: season.json says the flag is set at «T3 A», but ``register.augustin_de_roncourt`` only flips
#: in T3's ``state_out``, which ``_settle_tentpole`` applies at the end of T3 **B**. So on both
#: days of T3 the person is «vous» and the page is «tu». The move belongs at T3 A's opening.
KNOWN_DISAGREEMENTS: dict[tuple[str, str, str], tuple[str, str]] = {
    ("t3", "a", "a.turn1"): ("tu", "vous"),
}


def _flags_for(when: dict[str, Any] | None) -> dict[str, Any]:
    """The flags that make a day variant's ``when`` hold."""

    flags: dict[str, Any] = {}
    for key, want in (when or {}).items():
        if isinstance(want, dict) and "not" in want:
            flags[key] = None
        elif key not in ("any", "all", "band", "path"):
            flags[key] = want
    return flags


def _day_page(season, tentpole, day, flags, band) -> dict[str, Any]:
    """One day's page, this variant whatever the flags say elsewhere (``page.resolve_day``'s body)."""

    ctx = _Ctx(flags=flags, band=band, language="de", neutral=False, names=display_names(season.cast))
    movements: list[dict[str, Any]] = []
    for movement in day.movements:
        movements.extend(_movement(movement, tentpole, ctx))
    return {"movements": movements, "band": band, "language": "de"}


def _authored_turns():
    """(where, the turn, the registers of the day it is played on)."""

    season = load_season("s1")
    carried = dict(effective_flags(season, None))
    for tentpole in season.tentpoles.values():
        for day in tentpole.days:
            flags = {**carried, **_flags_for(day.when)}
            registers = address.season_registers(season, flags)
            for band in BANDS:
                for turn in projected_turns(_day_page(season, tentpole, day, flags, band)):
                    yield (tentpole.id, day.day, str(turn.get("id"))), turn, registers
        # ``_settle_tentpole``: a tentpole's fixed state applies once its Day B is played.
        carried.update(tentpole.state_out)
    for gap_id, bridge in load_bridges("s1").items():
        registers = address.season_registers(season, effective_flags(season, None))
        for band in BANDS:
            missing = [moment.premise for moment in bridge.moments]
            page = bridge_page(season, bridge, missing, flags={}, band=band, language="de")
            for turn in projected_turns(page) if page else []:
                yield (f"bridge:{gap_id}", "-", str(turn.get("id"))), turn, registers


def test_the_table_reaches_every_tentpole_and_every_addressee():
    seen = {where[0] for where, _turn, _registers in _authored_turns()}
    assert {f"t{number}" for number in range(1, 9)} <= seen
    assert {"e1", "e2", "e3"} <= seen
    assert any(where.startswith("bridge:") for where in seen)
    addressees = {str(turn.get("to")) for _where, turn, _registers in _authored_turns()}
    assert {GUS, "margaux_barman", "lila_bonnet", "marin_leveque", "romy_tremblay", "camille_marchand"} <= addressees


def test_every_authored_turn_agrees_with_the_registry():
    found: dict[tuple[str, str, str], tuple[str, str]] = {}
    unknown: list[tuple[str, str, str]] = []
    for where, turn, registers in _authored_turns():
        person = str(turn.get("to") or "")
        said = turn_address(turn)
        registry = cast_registry.address_now(person, None, registers=registers)
        if registry is None:
            unknown.append(where)
        elif said is not None and said != registry:
            found[where] = (said, registry)
    assert not unknown, f"a turn is for someone the cast cannot say anything about: {sorted(set(unknown))}"
    assert found == KNOWN_DISAGREEMENTS, (
        "turn_address on the page and the registry disagree. Report it, or take a fixed row "
        f"off KNOWN_DISAGREEMENTS: {found}"
    )


@pytest.mark.parametrize(
    "number, expected",
    [(1, "vous"), (2, "vous"), (4, "tu"), (5, "tu"), (6, "tu")],
)
def test_t3_is_where_gus_moves_to_tu(number, expected):
    """Before T3 the flag says «vous», after T3 B's ``state_out`` it says «tu»."""

    season = load_season("s1")
    flags = dict(effective_flags(season, None))
    for tentpole in season.tentpoles.values():
        if tentpole.number < number:
            flags.update(tentpole.state_out)
    registers = address.season_registers(season, flags)
    assert cast_registry.address_now(GUS, None, registers=registers) == expected


def test_t4_b_says_tu_to_gus_on_the_page_and_in_the_registry():
    """The first page after the flip: the two sources agree again."""

    rows = [row for row in _authored_turns() if row[0][:2] == ("t4", "b") and row[1].get("to") == GUS]
    assert rows
    for _where, turn, registers in rows:
        assert turn_address(turn) in (None, "tu")
        assert cast_registry.address_now(GUS, None, registers=registers) == "tu"
