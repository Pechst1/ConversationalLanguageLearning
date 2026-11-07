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

import functools

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
            if _GENDERED_ENGLISH.search(item.en):
                continue  # «his friend»: the English names a sex, no twin
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


# -- the twin never makes the key accept a wrong sentence, in any unit ---------------

_GENDERED_ENGLISH = __import__("re").compile(r"\b(?:he|him|his|she|her|hers|himself|herself)\b", __import__("re").IGNORECASE)


def _person_nouns() -> dict[str, str]:
    """Every person noun's written forms (singular and plural) and its gender."""

    forms: dict[str, str] = {}
    both: set[str] = set()
    for entry in ib.lexicon().pool("noun"):
        if entry.get("kind") != "person" or "pron" in (entry.get("tags") or []):
            continue
        for key in ("fr", "pl"):
            if isinstance(entry.get(key), str):
                word = entry[key].lower()
                if forms.setdefault(word, str(entry.get("g"))) != str(entry.get("g")):
                    both.add(word)
    # An epicene noun («collègue», «élève») is either gender.
    return {word: gender for word, gender in forms.items() if word not in both}


@functools.lru_cache(maxsize=1)
def _sweep(seeds: int = 3, count: int = 100) -> tuple:
    """Items of every unit over several seeds (built once, shared by the sweeps)."""

    bank = ib.default_bank()
    found = []
    for unit in sorted(bank.templates):
        for seed in range(seeds):
            found.extend((unit, item) for item in bank.generate(unit, count, seed=f"sweep-{seed}"))
    return tuple(found)


def _words_of(sentence: str) -> list[str]:
    return __import__("re").findall(r"[\w'’-]+", sentence.lower().replace("’", "'"))


def test_no_accepted_sentence_of_any_unit_contradicts_the_gender_the_english_names():
    nouns = _person_nouns()
    seen = 0
    for unit, item in _sweep():
        if not _GENDERED_ENGLISH.search(item.en):
            continue
        key = {nouns[w] for w in _words_of(item.sentence) if w in nouns}
        for other in item.accepted:
            now = {nouns[w] for w in _words_of(other) if w in nouns}
            assert not (now - key), (unit, item.en, item.sentence, other)
        seen += 1
    assert seen, "some items name a gender in English"


def test_the_reported_pronoun_units_never_accept_the_other_sex():
    seen = 0
    for unit in (
        "FR2_A22_IMPERATIVE_PRONOUNS",
        "FR2_A21_COD",
        "FR2_A21_COI",
        "FR2_A22_PRONOUN_POSITION",
    ):
        for seed in range(6):
            for item in ib.default_bank().generate(unit, 200, seed=f"x{seed}"):
                if "neighbour" not in item.en:
                    continue
                masculine = " voisin " in f" {item.sentence.lower()} ".replace("?", " ").replace(".", " ").replace("!", " ")
                for other in item.accepted:
                    assert (" voisin " in f" {other.lower()} ".replace("?", " ").replace(".", " ").replace("!", " ")) == masculine, (
                        unit, item.en, item.sentence, other)
                seen += 1
    assert seen


_MASC_DET = r"(?:le|un|mon|ton|son|ce|cet)"
_FEM_DET = r"(?:la|une|ma|ta|sa|cette)"


def test_no_accepted_sentence_of_any_unit_is_ungrammatical_on_a_person_noun():
    """«mon vieille amie», «le voisine», «une ami»: the frame redid the noun but not
    the words that agree with it."""

    import re

    nouns = _person_nouns()
    feminine = "|".join(sorted((w for w, g in nouns.items() if g == "f"), key=len, reverse=True))
    masculine = "|".join(sorted((w for w, g in nouns.items() if g == "m"), key=len, reverse=True))
    wrong = [
        # a masculine determiner (with at most one adjective between) before a feminine noun,
        # except mon/ton/son straight before a vowel («mon amie»)
        re.compile(rf"\b(?:le|un|ce|cet)\s+(?:[\w'-]+\s+)?(?:{feminine})\b"),
        re.compile(rf"\b(?:mon|ton|son)\s+[\w'-]+\s+(?:{feminine})\b"),
        re.compile(rf"\b(?:mon|ton|son)\s+(?:{feminine})\b"),
        # a feminine determiner before a masculine noun
        re.compile(rf"\b{_FEM_DET}\s+(?:[\w'-]+\s+)?(?:{masculine})\b"),
    ]
    checked = 0
    for unit, item in _sweep():
        for sentence in item.accepted:
            text = sentence.lower().replace("’", "'")
            for pattern in wrong:
                for found in pattern.finditer(text):
                    if pattern.pattern.startswith(r"\b(?:mon|ton|son)\s+(?:") and re.match(
                        r"(?:mon|ton|son)\s+[aeiouyhâêéèîôû]", found.group(0)
                    ):
                        continue  # «mon amie»: the euphonic form is right
                    raise AssertionError((unit, item.en, item.sentence, sentence, found.group(0)))
            checked += 1
    assert checked
