"""WP-125B — the walk checks over life records, proven on bad and good records."""
from __future__ import annotations

from tests.walk_checks_wp125b import check_letter_levels, check_letter_repeats, letter_volume

_BREAD = {
    "title": "Plus de pain blanc",
    "brief": "Il n'y a plus votre pain. Choisissez un autre pain et demandez quelque chose.",
    "opening_message": "Bonjour ! Il n'y a plus de pain blanc. Vous voulez un autre pain ?",
}
_PARCEL = {
    "title": "Le colis perdu",
    "brief": "Le colis n'est pas chez vous. Expliquez et demandez une solution.",
    "opening_message": "Bonjour, votre paquet est arrivé, mais pas chez vous. Quelle est votre rue ?",
}


def _record(level: str, letters_by_day: dict[int, list[dict]]) -> dict:
    return {
        "persona": "test",
        "quality": "strong",
        "true_level": level,
        "days": [{"day": day, "courrier": {"letters": letters}} for day, letters in sorted(letters_by_day.items())],
    }


def _answered(letter: dict, ident: str, **extra) -> dict:
    return {**letter, "id": ident, "reply": "Bonjour, merci.", "recap": {"outcome": "partial"}, **extra}


def test_a_reprint_the_next_day_fires():
    record = _record("A1", {2: [_answered(_BREAD, "m1")], 3: [_answered(_BREAD, "m2")]})
    problems = check_letter_repeats(record)
    assert len(problems) == 1 and "word-for-word" in problems[0]


def test_the_same_request_a_week_later_and_a_different_one_are_quiet():
    record = _record(
        "A1",
        {2: [_answered(_BREAD, "m1")], 3: [_answered(_PARCEL, "m2")], 9: [_answered(_BREAD, "m3")]},
    )
    assert check_letter_repeats(record) == []


def test_a_follow_up_that_names_the_exchange_is_quiet_and_a_reprint_with_a_chain_note_is_not():
    follow_up = {**_BREAD, "opening_message": "Merci pour votre réponse d'hier ! Je vous garde le pain aux céréales ?"}
    good = _record(
        "A1",
        {2: [_answered(_BREAD, "m1")], 3: [_answered(follow_up, "m2", chain_note="Lettre 2 sur 2 · suite de « Plus de pain blanc »")]},
    )
    assert check_letter_repeats(good) == []
    bad = _record(
        "A1",
        {2: [_answered(_BREAD, "m1")], 3: [_answered(_BREAD, "m2", chain_note="Lettre 2 sur 2 · suite de « Plus de pain blanc »")]},
    )
    assert len(check_letter_repeats(bad)) == 1


def test_a_skipped_letter_shown_again_is_not_a_repeat():
    waiting = {**_BREAD, "id": "m1", "skipped": True}
    record = _record("A1", {2: [waiting], 3: [dict(waiting)], 4: [_answered(_BREAD, "m1")]})
    assert check_letter_repeats(record) == []
    assert letter_volume(record)["letters"] == 1


def test_the_bread_question_to_a_c1_learner_fires_and_to_an_a2_learner_does_not():
    letters = {2: [_answered(_BREAD, "m1")]}
    problems = check_letter_levels(_record("C1.1", letters))
    assert len(problems) == 1 and "C1 learner" in problems[0]
    assert check_letter_levels(_record("A2.1", letters)) == []
    # A1 bread is two bands below B1.
    assert len(check_letter_levels(_record("B1.1", letters))) == 1


def test_an_open_letter_reaches_two_bands_and_a_recorded_fit_wins():
    romy = {"id": "r1", "title": "Trois questions de Romy", "brief": "Romy écrit un article."}
    assert check_letter_levels(_record("C1.1", {1: [romy]})) == []
    frame = {"id": "s1", "title": "Un mot de Lila Bonnet", "brief": "Lila vous écrit après la scène."}
    assert len(check_letter_levels(_record("C1.1", {3: [frame]}))) == 1
    assert check_letter_levels(_record("B2.1", {3: [frame]})) == []
    # A recorded fit (a richer frame the walk recorded) is read as recorded.
    recorded = {**frame, "letter_fit": {"source": "story_frame", "level": "C1", "reach": "C1", "request_key": "story:x"}}
    assert check_letter_levels(_record("C1.1", {3: [recorded]})) == []
