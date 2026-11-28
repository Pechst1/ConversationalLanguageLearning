"""#1126: La Forge gave the learner a new age in every avoir item.

Walk of 28 Nov 2026 (`a1-de-fresh`, day 2, La Forge on «Avoir»), one séance:
«Gus demande ton âge. J'ai vingt-trois ans.», «Marin demande ton âge. J'ai cinquante-six
ans.», then the tile build «Margaux fragt, wie alt du bist. Bau den Satz: „Ich bin 69 Jahre
alt.“». The learner never said an age; the frame ``avoir-age-ask`` bound a fact about the
learner («ton âge», «wie alt du bist») to a random number of the ``num:age`` pool, and a
learner who typed their real age was marked wrong.

An age item now asks about a person of the cast, whose age the cast entry bounds
(``num:age@C``): «Margaux demande l'âge de Gus. Gus a soixante-neuf ans.»
"""

from __future__ import annotations

import re

from app.services import item_bank as ib

UNIT = "FR2_A11_AVOIR"

#: A number framed as the learner's own age, in any language the learner reads.
_LEARNERS_AGE = re.compile(
    r"\bton\s+âge\b|\bquel\s+âge\s+(?:as-tu|tu\s+as|avez-vous)\b|\bwie\s+alt\s+(?:du\s+bist|bist\s+du|Sie\s+sind)\b"
    r"|\bhow\s+old\s+(?:you\s+are|are\s+you)\b|\byour\s+age\b",
    re.IGNORECASE,
)


def _sample(seeds: int = 12, count: int = 120) -> list[ib.BankItem]:
    bank = ib.default_bank()
    items: list[ib.BankItem] = []
    for seed in range(seeds):
        items.extend(bank.generate(UNIT, count, seed=f"age-1126:{seed}"))
    return items


def _texts(item: ib.BankItem) -> list[str]:
    """Every line of the item the learner reads: the French, the English and German
    meaning, the posed (vocative-free) twin, and the tile build's goal."""

    texts = [item.sentence, item.en or "", item.de or ""]
    posed = ib.without_vocative(item) or item
    texts += [posed.sentence, posed.en or "", posed.de or ""]
    meaning = (ib._meaning_l10n(posed).get("meaning_l10n") or {}).values()
    texts += [str(text) for text in meaning]
    built = ib.word_bank_item(item)
    if built:
        texts += [str(built.get(key) or "") for key in ("goal_native", "meaning_cue", "correct_answer")]
    return texts


def test_no_age_item_frames_a_random_number_as_the_learners_own():
    """The walk's séance: no avoir item says the number is the learner's age."""

    framed = sorted(
        {text for item in _sample() if re.search(r"\bans\b", item.sentence) for text in _texts(item) if _LEARNERS_AGE.search(text)}
    )
    assert framed == [], f"an item frames a random number as the learner's own age: {framed[:4]}"


def test_a_third_person_age_item_is_still_served():
    """«Gus a soixante-neuf ans»: the unit still drills the age with avoir, about the cast."""

    items = [item for item in _sample(4) if re.search(r"\bans\b", item.sentence)]
    third = [item for item in items if re.search(r"\b(?:a|ont)\s+[\w-]+(?:\s+[\w-]+){0,3}\s+ans\b", item.sentence)]
    assert third, "the unit serves no third-person age item"
    exchange = [item for item in items if "l'âge de" in item.sentence]
    assert exchange, "the age exchange is gone, not reframed"
    item = exchange[0]
    cast = dict(item.bindings)["C"]
    age = int(dict(item.bindings)["M"]["value"])
    if cast.get("age"):
        # The number is the cast's own fact, not a draw from the whole pool.
        assert cast["age"][0] <= age <= cast["age"][1], (item.sentence, cast.get("age"))
    # The answer is about the person asked: «Elle a trente ans.» for Lila.
    pronoun = "Elle" if cast.get("g") == "f" else "Il"
    assert item.sentence.split(". ")[-1].startswith(f"{pronoun} a "), item.sentence
    assert item.de and "du" not in item.de.split(), item.de


def test_no_frame_asks_the_learners_own_fact():
    """The structural guard, over every unit's frames: a frame may not ask the learner's
    own age and answer it from a pool (nothing knows that slot is a fact about the
    learner)."""

    asking = [
        (unit, frame.frame_id)
        for unit in sorted(ib.template_units())
        for frame in ib.default_bank().frames(unit)
        if any(_LEARNERS_AGE.search(str(text or "")) for text in (frame.fr, frame.en, frame.de))
    ]
    assert asking == []
