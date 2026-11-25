"""#1069: the optional test asked «Say in French: They drove at night this morning.»

Walk 25 Nov 2026 (a2-en, day 2, «Passé composé with avoir», item 3 of 3): the key
was «Elles ont conduit la nuit ce matin.» The frame ``pc-avoir-pp`` binds a time
(«ce matin», ``time_past_end``) and a verb complement («la nuit», conduire's
``comps``). The bank's time guard reads time from a hand-kept list of expressions
(``_TIME_PATTERNS``): a complement that names a part of the day is not a time to
it, and morning-with-night was checked for two verbs only («lever», «coucher»).

The part of the day is its own axis: two bound entries (or a frame's own words
and an entry) that name a morning and a night/evening never share a sentence,
whatever the verb, and the checker names such a sentence.
"""
from __future__ import annotations

import random

import pytest

from app.services import item_bank as ib
from app.services import item_semantics as sem

BOTH = {"morning", "evening"}


@pytest.mark.parametrize(
    "sentence",
    [
        "Elles ont conduit la nuit ce matin.",
        "Tu as conduit la nuit ce matin, Lila.",
        "Ce matin, nous avons travaillé le soir.",
        "Il a lu toute la soirée ce matin.",
    ],
)
def test_a_sentence_with_a_morning_and_a_night_is_a_clash(sentence: str) -> None:
    kinds = {clash.kind for clash in sem.sentence_violations(sentence)}
    assert kinds & {"time", "daypart"}, f"«{sentence}» says morning and night, no clash named: {kinds}"


@pytest.mark.parametrize(
    "sentence",
    ["Elles ont conduit la nuit.", "Ce matin, elles ont conduit dans Paris.", "Hier soir, j'ai lu le journal."],
)
def test_one_part_of_the_day_is_fine(sentence: str) -> None:
    assert sem.sentence_violations(sentence) == [], sentence


def _entries_naming(part: str) -> list[dict]:
    """Every lexicon entry (pool entries and verb complements) naming only ``part``."""

    lex = ib.lexicon()
    entries = [entry for pool in lex.pools.values() for entry in pool if isinstance(entry, dict)]
    entries += [comp for verb in lex.verbs.values() for comp in verb.get("comps") or [] if isinstance(comp, dict)]
    return [entry for entry in entries if sem.dayparts(entry.get("fr")) == {part}]


def test_a_night_entry_never_binds_next_to_a_morning_one() -> None:
    """At the source: the bank's pair filter keeps «la nuit» away from «ce matin»."""

    mornings, nights = _entries_naming("morning"), _entries_naming("evening")
    assert any(entry.get("fr") == "la nuit" for entry in nights)
    assert any(entry.get("fr") == "ce matin" for entry in mornings)
    allowed = [
        f"«{night.get('fr')}» + «{morning.get('fr')}»"
        for night in nights
        for morning in mornings
        if sem.pair_clash(night, morning) is None or sem.pair_clash(morning, night) is None
    ]
    assert not allowed, f"{len(allowed)} morning/night pairs may share a sentence: {allowed[:10]}"


def _bank_sentences(bank: ib.ItemBank, frame, draws: int) -> list[str]:
    rng = random.Random(f"daypart:{frame.frame_id}")
    sentences: list[str] = []
    for _ in range(draws):
        try:
            sentences.append(bank.render(frame, bank._bind(frame, rng, frozenset())).sentence)
        except (ib.RenderError, KeyError, IndexError):
            continue
    return sentences


def test_no_bank_sentence_says_morning_and_night() -> None:
    """Every frame of FR2_A21_PC_AVOIR (the walk's unit) and every ``~voc`` frame
    of the bank, bound before the checker sees them: none names both parts of the day."""

    bank = ib.ItemBank()
    frames = [(frame, 2500) for frame in bank.frames("FR2_A21_PC_AVOIR")]
    frames += [
        (frame, 60)
        for unit in bank.templates
        if unit != "FR2_A21_PC_AVOIR"
        for frame in bank.frames(unit)
        if frame.frame_id.endswith("~voc")
    ]
    clashes = [
        f"{frame.frame_id}: {sentence}"
        for frame, draws in frames
        for sentence in _bank_sentences(bank, frame, draws)
        if sem.dayparts(sentence) == BOTH
    ]
    assert not clashes, "\n".join(clashes[:20])
