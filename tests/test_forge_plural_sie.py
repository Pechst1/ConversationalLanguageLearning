"""#126: a German meaning that opens with «Sie sind …» reads as polite «you», not «they»."""

from __future__ import annotations

import re

from app.services.item_bank import default_bank, disambiguate_plural_sie, template_units

_SINGULAR_VERBS = {"ist", "hat", "war", "wird", "kann", "will", "muss", "darf", "soll", "mag"}


def test_plural_pronoun_subject_is_never_a_bare_capital_sie():
    bank = default_bank()
    seen_plural = 0
    for unit in template_units():
        for item in bank.generate(unit, 120, seed="plural-sie"):
            if not item.de:
                continue
            lowered = item.sentence.lower()
            if lowered.startswith(("ils ", "elles ")):
                seen_plural += 1
                assert not re.match(r"Sie\s(?!\(alle\))", item.de), (unit, item.sentence, item.de)
            elif re.match(r"Sie\s", item.de) and lowered.startswith("elle "):
                assert item.de.split()[1].lower().rstrip(",") in _SINGULAR_VERBS or not item.de.split()[1].endswith("en"), (
                    unit,
                    item.sentence,
                    item.de,
                )
    assert seen_plural > 50


def test_quoted_prompts_name_the_plural():
    plural = {"S": {"fr": "ils", "p": 5}}
    assert disambiguate_plural_sie("Sie sind in der Redaktion.", plural) == "Sie (alle) sind in der Redaktion."
    assert disambiguate_plural_sie("Heute sind sie da.", plural) == "Heute sind sie da."
    assert disambiguate_plural_sie("Sie ist da.", {"S": {"fr": "elle", "p": 2}}) == "Sie ist da."


_VOCATIVE_END = re.compile(r",\s+[A-ZÄÖÜ]\w+[.?!]$")


def test_a_plural_sie_never_ends_on_the_name_it_could_be_said_to():
    """#384: «Sie (alle) sind fertig, Lila.» still read as «you all, Lila» (the card above
    showed Gus with «vous»). A vocative turns the sentence into a lead-in."""

    bank = default_bank()
    seen = 0
    for unit in template_units():
        for item in bank.generate(unit, 200, seed="plural-sie"):
            if not item.de or not item.sentence.lower().startswith(("ils ", "elles ")):
                continue
            if not _VOCATIVE_END.search(item.sentence):
                continue
            seen += 1
            assert not (item.de.startswith("Sie") and _VOCATIVE_END.search(item.de)), (unit, item.sentence, item.de)
    assert seen > 20


def test_a_plural_sie_with_a_vocative_leads_with_the_name():
    plural = {"S": {"fr": "ils", "p": 5}, "VOC": {"fr": "Lila", "deu": "Lila", "p": 2}}
    assert disambiguate_plural_sie("Sie sind fertig, Lila.", plural) == "Lila, sie sind alle fertig."
    assert disambiguate_plural_sie("Sie kaufen ein Buch, Lila?", plural) == "Lila, sie kaufen alle ein Buch?"
    assert disambiguate_plural_sie("Sie schlafen, Lila.", plural) == "Lila, sie schlafen alle."
    assert disambiguate_plural_sie("Sie sind fertig.", {"S": plural["S"]}) == "Sie (alle) sind fertig."
