"""#1049: a rule card's line about its own speaker is never handed to a stand-in.

Walk 24 Nov 2026, day 2: the Avoir card showed Margaux's face over Romy's «J'ai vingt-cinq ans et
j'ai faim !». Margaux has run the Mistral since 2003; the line is Romy's. The met gate
(:func:`card_for_learner`) checked only the stand-in's register, so a first-person line stating
the speaker's age, job or family moved to someone of whom it is false. Root cause #147: a line's
facts belong to its speaker.
"""

from __future__ import annotations

import re

from app.services.forge_coaches import card_for_learner
from app.services.rule_cards import _cards, rule_card_for
from app.services.season.clock import SEASON_KEY

ROMY = "romy_tremblay"
AVOIR = "FR2_A11_AVOIR"


def _state(*played: tuple[str, int]) -> dict:
    rows = [{"segment": segment, "day_in_segment": day} for segment, day in played]
    return {"relationships": {}, "living_story": {SEASON_KEY: {"id": "s1", "played": rows, "flags": {}}}}


DAY_TWO = _state(("t1", 1), ("t1", 2))
AFTER_T4 = _state(("t4", 1))


def test_romys_age_is_not_handed_to_a_stand_in_before_romy_is_met():
    card = rule_card_for(AVOIR)
    assert card["speaker"] == ROMY and "vingt-cinq ans" in card["example"]["fr"]
    shown = card_for_learner(card, external_id=AVOIR, state=DAY_TWO)
    assert shown["speaker"] is None, (
        f"«{card['example']['fr']}» is Romy's age, but the card hands it to {shown['speaker']}"
    )
    assert shown.get("unvoiced") is True, "the card says it names nobody, so no surface puts the coach's face on it"
    assert shown["example"] == card["example"], "the card keeps its example"
    assert card["speaker"] == ROMY, "the shared card is not changed"


def test_once_romy_is_met_the_card_is_hers_again():
    card = rule_card_for(AVOIR)
    shown = card_for_learner(card, external_id=AVOIR, state=AFTER_T4)
    assert shown["speaker"] == ROMY
    assert not shown.get("unvoiced")


# --------------------------------------------------------------------------- #
# The guard: every card whose example says something about its speaker is marked
# --------------------------------------------------------------------------- #

_FAMILY = (
    r"fr[èe]re|s(?:œ|oe)ur|m[èe]re|p[èe]re|parents|grands?-parents|grand-m[èe]re|grand-p[èe]re|"
    r"tante|oncle|fils|fille|enfants?|mari|femme|cousine?|neveu|ni[èe]ce|famille"
)
_JOBS = (
    r"serveu(?:r|se)|journaliste|[ée]tudiante?|professeure?|prof|m[ée]decin|avocate?|"
    r"infirmi(?:er|[èe]re)|architecte|ing[ée]nieure?|barman|patronne?|libraire|boulang(?:er|[èe]re)|"
    r"cuisini(?:er|[èe]re)|photographe|musicienne?|chauffeur|vendeu(?:r|se)|retrait[ée]e?|"
    r"propri[ée]taire|g[ée]rante?|comptable|secr[ée]taire|traductrice|traducteur"
)
_OWN_FACT = (
    ("age", re.compile(r"\bj'ai\s+[\w-]+(?:\s+et\s+[\w-]+)?\s+ans\b|\bmes\s+[\w-]+\s+ans\b", re.I)),
    ("family", re.compile(rf"\b(?:mon|ma|mes|notre|nos)\s+(?:{_FAMILY})\b", re.I)),
    ("job", re.compile(rf"\bje\s+suis\s+(?:une?\s+)?(?:{_JOBS})\b|\bje\s+travaille\s+comme\b", re.I)),
)


def own_facts(french: str) -> list[str]:
    """What a first-person line says about the person saying it: their age, job or family."""

    text = re.sub(r"[\[\]{}]", "", french).replace("’", "'")
    return [kind for kind, pattern in _OWN_FACT if pattern.search(text)]


def test_the_guard_reads_a_speakers_own_facts():
    assert own_facts("J'[ai] vingt-cinq ans et j'[ai] faim !") == ["age"]
    assert own_facts("Ma mère ? Je lui téléphone tous les dimanches.") == ["family"]
    assert own_facts("Je suis serveuse au Mistral.") == ["job"]
    assert own_facts("Je suis au café. Et toi, tu es où ?") == []
    assert own_facts("C'est Paul, mon voisin. Il est infirmier.") == []


def test_every_card_whose_example_is_about_its_speaker_keeps_its_speaker():
    """A card whose example states its speaker's age, job or family is marked ``keeps_speaker``:
    before that speaker is met it names nobody, never a stand-in of whom it is false."""

    unmarked = {
        external_id: (card["example"]["fr"], facts)
        for external_id, card in _cards().items()
        if (facts := own_facts(str((card.get("example") or {}).get("fr") or "")))
        and not card.get("keeps_speaker")
    }
    assert not unmarked, unmarked


def test_a_card_that_keeps_its_speaker_names_nobody_before_they_are_met():
    for external_id, card in _cards().items():
        if not card.get("keeps_speaker"):
            continue
        shown = card_for_learner(dict(card), external_id=external_id, state=_state())
        assert shown["speaker"] in {None, card["speaker"]}, (external_id, shown["speaker"])


def test_every_card_as_served_fits_the_journeys_card_payload():
    """The journey's card model forbids unknown keys: an authored mark or the gate's
    ``unvoiced`` must not cost a learner their rule step."""

    from app.schemas.daily_journey import RuleCardPayload

    for external_id, card in _cards().items():
        RuleCardPayload.model_validate(card)
        RuleCardPayload.model_validate(card_for_learner(dict(card), external_id=external_id, state=DAY_TWO))
