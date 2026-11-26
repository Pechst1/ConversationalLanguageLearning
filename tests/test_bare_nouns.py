"""#1083: a month's word card read «le janvier · January», next to «le dimanche ·
Sunday». A month takes no article («en janvier»; «le 8 janvier» only with a date),
and «le dimanche» means «on Sundays», not «Sunday».

Why the code allowed it: the card draws its article from the noun's gender alone
(``frenchHeadword`` in ``web-frontend/lib/french-noun.ts``: a known gender gives
le / la), and the server sent a gender for every noun the lexicon marks ``m`` / ``f``.
Nothing said a noun is cited without an article. The curated list
``app/data/lexical/fr_bare_nouns.json`` now says it, and ``word_grammar``, the one
place a card's gender comes from, gives such a noun none (as it already does for an
epicene noun, which has no one article), so every surface shows the bare word.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

from app.schemas.vocabulary import VocabularyWordRead
from app.services.core_lexicon import _entries, _fields
from app.services.lexical_coverage import LEXICON_PATH
from app.services.lexicon_grammar import word_grammar

MONTHS = (
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
)
DAYS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
#: The glosses name the month or the day («Sunday»), which is the bare word, not
#: «le dimanche» («on Sundays»).
GLOSS_EN = {
    "janvier": "January", "février": "February", "mars": "March", "avril": "April",
    "mai": "May", "juin": "June", "juillet": "July", "août": "August",
    "septembre": "September", "octobre": "October", "novembre": "November",
    "décembre": "December", "lundi": "Monday", "mardi": "Tuesday",
    "mercredi": "Wednesday", "jeudi": "Thursday", "vendredi": "Friday",
    "samedi": "Saturday", "dimanche": "Sunday",
}


def _card_french(word: str, pos: str | None, gender: str | None) -> str:
    """The card's French side as ``frenchHeadword`` writes it: a noun with a known
    gender carries le / la / l'; anything else is shown as it is."""

    if str(pos or "").lower() not in {"noun", "nom", "n"} or gender not in {"m", "f"}:
        return word
    if word[:1] in "aeiouéèêâîôûh":
        return f"l’{word}"
    return ("la " if gender == "f" else "le ") + word


def _core_row(lemma: str) -> SimpleNamespace:
    """The catalogue row the core lexicon seeds for ``lemma`` (``core_lexicon._fields``)."""

    for position, (name, entry) in enumerate(_entries(), start=1):
        if name == lemma:
            return SimpleNamespace(language="fr", **_fields(name, entry, "core:test", position))
    raise AssertionError(f"{lemma} is not in the core lexicon")


def test_month_day_cards_bare() -> None:
    lemmas = json.loads(LEXICON_PATH.read_text(encoding="utf-8"))["lemmas"]
    for lemma in MONTHS + DAYS:
        assert lemma in lemmas, lemma
        row = _core_row(lemma)
        shown = _card_french(lemma, *word_grammar(row))
        assert shown == lemma, f"the card reads «{shown} · {row.english_translation}»"
        assert row.english_translation == GLOSS_EN[lemma], lemma
        # The schema every Lexique row and the word sheet read sends the same,
        # whatever gender an imported row stored.
        read = VocabularyWordRead(id=1, language="fr", word=lemma, normalized_word=lemma, gender="m")
        shown = _card_french(lemma, read.part_of_speech, read.gender)
        assert shown == lemma, f"the Lexique row reads «{shown}»"


def test_nouns_keep_article() -> None:
    for lemma, expected in (("menu", "le menu"), ("semaine", "la semaine"), ("mois", "le mois")):
        row = _core_row(lemma)
        assert _card_french(lemma, *word_grammar(row)) == expected


def test_scene_month_bare() -> None:
    from app.services.journey_learning import _lexicon_label

    month = SimpleNamespace(lemma="janvier", part_of_speech="noun", gender="m")
    assert _lexicon_label(month) == "janvier", "the scene teaches «le janvier»"
    noun = SimpleNamespace(lemma="menu", part_of_speech="noun", gender="m")
    assert _lexicon_label(noun) == "le menu"
