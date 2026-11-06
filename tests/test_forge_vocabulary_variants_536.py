"""#536 — La Forge judges a sentence on the rule being practised, not on one vocabulary word.

The 5 Nov live walk, «Mon, ma, mes : les possessifs»: «leurs cahiers» for «They look for
their notebooks» was «Not yet» (the key said «carnets»), «Elle cherche ses appareils,
Gus.» for «her cameras» was «Not yet» (the key said «appareils photo»), and «Find the
mistake» for «I look for my cousin.» took one gender of «cousin» only.

Root cause (#174): a right answer was judged against one stored string, and the item
bank listed a second right word only where an author had remembered to. Now the English
gloss decides: a noun with another French word for the same gloss lists it
(``alt_fr``), and person nouns the English glosses alike (cousin / cousine) list each
other. A miss on a word other than the rule's still names that word, not the rule.
"""

from __future__ import annotations

import pytest

from app.services import item_bank as ib
from app.services.atelier import AtelierCorrectionService

UNIT = "FR2_A11_POSSESSIVES"


def _item(en: str, sentence: str | None = None, *, count: int = 400) -> ib.BankItem:
    bank = ib.default_bank()
    for seed in range(40):
        for item in bank.generate(UNIT, count, seed=f"night-{seed}"):
            if item.en == en and (sentence is None or item.sentence == sentence):
                return item
    raise AssertionError(f"no item glossed {en!r} in {UNIT}")


def _correct(db_session, mode: str, payload: dict, answer, *, round_name: str = "recognize") -> dict:
    return AtelierCorrectionService(db_session).correct(
        concept=None,
        round_name=round_name,
        mode=mode,
        exercise_id=f"X:{mode}:{payload['id']}",
        prompt_payload={"items": [payload]},
        answer_payload={"answers": {payload["id"]: answer}},
    )


def test_a_gap_for_their_notebooks_takes_cahiers_as_well_as_carnets(db_session):
    fill = ib.fill_item(_item("They look for their notebooks, Lila."), lesson_external_id=UNIT)
    assert fill is not None
    for typed in ("leurs carnets", "leurs cahiers", "Leurs cahiers."):
        correction = _correct(db_session, "fill", fill, typed)
        assert correction["verdict"] == "correct", (typed, correction)
        assert correction["errata"] == []


def test_a_build_of_her_cameras_takes_appareils_as_well_as_appareils_photo(db_session):
    built = ib.word_bank_item(_item("She looks for her cameras, Gus."), lesson_external_id=UNIT)
    assert built is not None
    for sentence in ("Elle cherche ses appareils photo, Gus.", "Elle cherche ses appareils, Gus."):
        words = sentence.replace(",", " ,").replace(".", " .").split()
        correction = _correct(db_session, "word_bank", built, words)
        assert correction["verdict"] == "correct", (sentence, correction)


def test_a_miss_on_the_vocabulary_names_that_word_and_never_the_rule(db_session):
    fill = ib.fill_item(_item("They look for their notebooks, Lila."), lesson_external_id=UNIT)
    assert fill is not None
    correction = _correct(db_session, "fill", fill, "leurs voitures")
    assert correction["verdict"] != "correct"
    shown = " ".join(correction["notes_native"]).lower()
    assert "leurs voitures" in shown and "leurs carnets" in shown, shown
    assert "possessive" not in shown and "rule" not in shown, shown


def test_the_cousin_repair_lists_both_genders_the_english_allows():
    item = _item("I look for my cousin.", "Je cherche ma cousine.")
    repair = ib.transform_item(item)
    assert repair is not None
    assert {"Je cherche ma cousine.", "Je cherche mon cousin."} <= set(repair["accepted_answers"])
    # What the screen shows as wrong is never accepted.
    assert repair["source"] not in repair["accepted_answers"]


def test_the_cousin_repair_accepts_either_fix(db_session):
    repair = ib.transform_item(_item("I look for my cousin.", "Je cherche ma cousine."))
    assert repair is not None
    for fix in ("Je cherche ma cousine.", "Je cherche mon cousin."):
        correction = _correct(db_session, "rewrite", repair, fix, round_name="transform")
        assert correction["verdict"] == "correct", (fix, correction)


def test_a_person_noun_the_english_glosses_alike_lists_its_twin_in_every_item():
    twins = {("cousin", "cousine"), ("ami", "amie"), ("voisin", "voisine"), ("étudiant", "étudiante")}
    bank = ib.default_bank()
    checked = 0
    for seed in range(10):
        for item in bank.generate(UNIT, 300, seed=f"twin-{seed}"):
            for masculine, feminine in twins:
                for one, other in ((masculine, feminine), (feminine, masculine)):
                    sentence = " " + item.sentence.lower().replace(",", " ").replace(".", " ") + " "
                    if f" {one} " in sentence and f" {other} " not in sentence:
                        listed = " ".join(item.accepted).lower()
                        assert other in listed, (item.sentence, item.accepted)
                        checked += 1
    assert checked, "the possessives unit has person nouns to check"


@pytest.mark.parametrize(
    ("noun", "other"), [("carnet", "cahier"), ("appareil photo", "appareil")]
)
def test_a_noun_with_a_second_french_word_for_its_gloss_lists_it(noun, other):
    entries = {entry["fr"]: entry for entry in ib.lexicon().pool("noun")}
    listed = [alt["fr"] if isinstance(alt, dict) else alt for alt in entries[noun].get("alt_fr") or []]
    assert other in listed
