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


# --- #384: a plural «Sie» said to someone -----------------------------------

_VOCATIVE_END = re.compile(r",\s+[A-ZÄÖÜ][\w.]*(?:\s[A-ZÄÖÜ]\w+)?[.?!]$")


def _said_to(item) -> str:
    return str(dict(item.bindings).get("VOC", {}).get("deu") or "")


def test_a_plural_sie_said_to_someone_leads_with_their_name():
    """#384: «Sie (alle) sind fertig, Lila.» read as «you all, Lila», and the learner wrote
    «Vous êtes prêts.» for «Ils sont prêts». The name leads, and «sie» is small."""

    bank = default_bank()
    seen = 0
    for unit in template_units():
        for item in bank.generate(unit, 200, seed="plural-sie"):
            if not item.de or not item.sentence.lower().startswith(("ils ", "elles ")):
                continue
            name = _said_to(item)
            if not name:
                continue
            seen += 1
            assert not (item.de.startswith("Sie") and _VOCATIVE_END.search(item.de)), (unit, item.sentence, item.de)
            assert item.de.startswith(f"{name}, sie "), (unit, item.sentence, item.de)
            assert "(alle)" not in item.de, (unit, item.de)
    assert seen > 20


def test_the_name_leads_and_nothing_else_moves():
    plural = {"S": {"fr": "ils", "p": 5}, "VOC": {"fr": "Lila", "deu": "Lila", "p": 2}}
    assert disambiguate_plural_sie("Sie sind fertig, Lila.", plural) == "Lila, sie sind fertig."
    assert disambiguate_plural_sie("Sie kaufen ein Buch, Lila?", plural) == "Lila, sie kaufen ein Buch?"
    assert disambiguate_plural_sie("Sie schlafen, Lila.", plural) == "Lila, sie schlafen."
    # Review on #409: a reflexive stays right after its verb, in every tense.
    assert disambiguate_plural_sie("Sie ziehen sich schwarz an, Lila.", plural) == "Lila, sie ziehen sich schwarz an."
    assert (
        disambiguate_plural_sie("Sie haben sich schnell fertig gemacht, Lila.", plural)
        == "Lila, sie haben sich schnell fertig gemacht."
    )
    # A question and its answer: the name goes with the question.
    assert (
        disambiguate_plural_sie("Sie wollen Birnen, Lila? Ja, sie wollen zwei.", plural)
        == "Lila, sie wollen Birnen? Ja, sie wollen zwei."
    )
    assert disambiguate_plural_sie("Sie kaufen Äpfel, Brot und Käse, Lila.", plural) == "Lila, sie kaufen Äpfel, Brot und Käse."
    marchand = {"S": plural["S"], "VOC": {"fr": "M. Marchand", "deu": "Herr Marchand", "p": 2}}
    assert disambiguate_plural_sie("Sie sind da, Herr Marchand.", marchand) == "Herr Marchand, sie sind da."
    # No name to say it to: #126 as before.
    assert disambiguate_plural_sie("Sie sind fertig.", {"S": plural["S"]}) == "Sie (alle) sind fertig."
