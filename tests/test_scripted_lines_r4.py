"""Round 4 (third real-model walk, 19 Nov 2026, item 2): scripted lines that state
what the learner did not say or do.

B. A1 day 2: the learner refused flatly («Je ne vendre pas. Ce pas simple pour moi.»).
   No authored reply of T1 B's first turn meant «no»; the reader took the turn's
   fallback, «Not sure yet», and Camille answered «"Pas encore" ? Mon grand-père n'aime
   pas attendre.», quoting words the learner never said (stored route: ``b.turn1`` →
   ``b``, heard «The learner does not know yet.», intent «no»).
C. A1 day 1: the Courrier's first letter said «Tu as oublié ton écharpe sur la table»
   on a day with no scarf, and offered «Merci, Margaux !» (a vocative) and «Oui, c'est
   mon écharpe.» as the only answers.
"""

from __future__ import annotations

import re

import pytest

from app.services.cast_registry import vocative_names
from app.services.missions import FIRST_LETTERS
from app.services.season.format import load_season
from app.services.season.page import resolve_day, turns_of
from app.services.season.turns import match_reply

BANDS = ("A1", "A2", "B1", "B2", "C1")
#: A reaction that opens on a quotation («"Pas encore" ?») repeats the learner's words.
_QUOTES = re.compile(r'^\s*["«“]')


def _camille_turn(band: str) -> dict:
    page = resolve_day(load_season("s1"), "t1", "b", flags={}, band=band, language="de")
    return next(turn for turn in turns_of(page) if turn["id"] == "b.turn1")


def _said(reply: dict) -> list[str]:
    return [
        str(line.get("text_fr") or "")
        for beat in reply.get("beats") or []
        for line in beat.get("lines") or []
    ]


@pytest.mark.parametrize("band", BANDS)
def test_a_refusal_has_its_own_reply_and_it_quotes_nothing(band: str) -> None:
    turn = _camille_turn(band)
    replies = {reply["id"]: reply for reply in turn["replies"]}
    reply_id, _ = match_reply(turn, "Non, je ne vends pas.")
    assert reply_id == "e"
    assert all(
        not _QUOTES.search(line) and "encore" not in line for line in _said(replies[reply_id])
    ), _said(replies[reply_id])
    # «Pas encore» stays Camille's answer to a «not yet», and only to it.
    assert any("Pas encore" in line for line in _said(replies["b"]))
    assert match_reply(turn, "Je ne sais pas encore.")[0] == "b"


@pytest.mark.parametrize("band", BANDS)
def test_the_fallback_quotes_nothing(band: str) -> None:
    """The walk's reading: a «no» that fits no reply takes the fallback (``turns``:
    «A yes or a no … choose the fallback»). The fallback's line must hold for any reply."""

    turn = _camille_turn(band)
    fallback = next(reply for reply in turn["replies"] if reply["id"] == turn["fallback"])
    assert turn["fallback"] != "b"
    assert not any(_QUOTES.search(line) for line in _said(fallback)), _said(fallback)


#: Same fault, other turns: a fallback whose reaction quotes the clumsy example's words.
#: Not rewritten in round 4 (new lines for the owner to read; each changes a path gate
#: or a flag); listed so that a new one fails.
KNOWN_QUOTING_FALLBACKS = {
    ("t2", "b.turn2"): "«Un peu, c'est bien.» — the clumsy route of Lila's path gate 1",
    (
        "t3",
        "a.turn1",
    ): "«Tout le monde ne sait pas encore…» — Gus's answer to a refused promise (a bible line)",
    ("t4", "b.turn1"): "«Pardon, c'est assez.» — the clumsy route of Margaux's confession",
    (
        "e3",
        "ep3.b.turn",
    ): "«Moi aussi, je suis là.» — the clumsy route of the epilogue's last choice",
}


def test_no_other_fallback_quotes_the_learner() -> None:
    season = load_season("s1")
    found: set[tuple[str, str]] = set()
    for tentpole_id, tentpole in season.tentpoles.items():
        for day in {row.day for row in tentpole.days}:
            for band in BANDS:
                page = resolve_day(season, tentpole_id, day, flags={}, band=band, language="en")
                for turn in turns_of(page or {"movements": []}) if page else []:
                    fallback = next(
                        (
                            r
                            for r in turn.get("replies") or []
                            if r.get("id") == turn.get("fallback")
                        ),
                        None,
                    )
                    if fallback and any(_QUOTES.search(line) for line in _said(fallback)):
                        found.add((tentpole_id, str(turn["id"])))
    assert found <= set(KNOWN_QUOTING_FALLBACKS), sorted(found - set(KNOWN_QUOTING_FALLBACKS))


@pytest.mark.parametrize("group", sorted(FIRST_LETTERS))
def test_the_first_letter_asks_and_states_nothing(group: str) -> None:
    letter = FIRST_LETTERS[group]
    said = " ".join(
        str(letter.get(key) or "")
        for key in ("opening_message", "opening_message_tu", "brief", "brief_tu")
    )
    for claim in ("as oublié", "avez oublié", "a ton écharpe", "a votre écharpe"):
        assert claim not in said, f"the letter states «{claim}»"
    if group == "A":
        assert "C'est la tienne ?" in letter["opening_message_tu"]
        assert "C'est la vôtre ?" in letter["opening_message"]
        replies = letter["quick_replies"]
        assert "Oui, c'est mon écharpe." in replies and "Non, ce n'est pas à moi." in replies


@pytest.mark.parametrize("group", sorted(FIRST_LETTERS))
def test_no_reply_chip_addresses_a_character_by_name(group: str) -> None:
    names = [name for name in vocative_names() if name]
    for chip in FIRST_LETTERS[group]["quick_replies"]:
        for name in names:
            assert not re.search(
                rf"(?:^|[,!?] ?){re.escape(name)}\b|\b{re.escape(name)} ?[!?,]", chip
            ), (chip, name)
