"""#1048: La Forge's typed gap refused «J'ai un» for „Ich habe einen Termin im Mistral“.

Walk 24 Nov 2026 (a1-de-fresh, day 2, avoir, typed gap): the line was
«___ rendez-vous au Mistral.» under „Ich habe einen Termin im Mistral.“ The bank's
object was «rendez-vous au Mistral» with the glosses «an appointment at Le Mistral»
and «einen Termin im Mistral»: the glosses carry an article the French has not, so
«J'ai un» made a right, faithful sentence and was a miss. A blank is graded against
the item's own forms; the item has to say what its gloss says.

Guard: a verb's object and its glosses agree on the indefinite article. An object
whose English gloss starts with «a/an», or whose German gloss holds «ein/eine/einen…»,
starts with «un/une/des»; an object starting with «un/une» has «a/an/one» in English and
an indefinite article in German. Where a language drops the article for good reason
(a German verb that holds the noun, an English mass noun), it is listed below; an
idiom without an article in French must keep its glosses article-free too.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "app" / "data" / "grammar_templates"

_FR_INDEFINITE = re.compile(r"^(un|une|des)\s", re.IGNORECASE)
_FR_SINGULAR = re.compile(r"^(un|une)\s", re.IGNORECASE)
#: «a lot» (beaucoup) is an adverb, not an article and a noun.
_EN_INDEFINITE = re.compile(r"^(a|an)\s(?!lot\b)", re.IGNORECASE)
_EN_SINGULAR = re.compile(r"^(a|an|one)\s", re.IGNORECASE)
#: German puts a place or a dative before the object («im Mistral einen Kaffee»).
_DE_INDEFINITE = re.compile(r"\b(ein|eine|einen|einem|einer|eines)\b", re.IGNORECASE)

#: French idioms without an article: their glosses must not add one.
IDIOMS_WITHOUT_ARTICLE: frozenset[str] = frozenset()
#: Objects with an article whose gloss rightly has none: (language, verb, object).
GLOSS_WITHOUT_ARTICLE: frozenset[tuple[str, str, str]] = frozenset(
    {
        ("en", "donner", "un conseil à Gus"),  # «advice» takes no article in English
        ("de", "faire", "une promenade"),  # «spazieren»: the German verb holds the noun
        ("de", "faire", "une promenade le long du canal"),
    }
)


def _objects() -> list[tuple[str, str, str, str | None]]:
    """``(verb, fr, en, de)`` for every verb object of the bank."""

    lexicon = json.loads((DATA / "lexicon.json").read_text(encoding="utf-8"))
    german = json.loads((DATA / "lexicon_de.json").read_text(encoding="utf-8"))["verbs"]
    rows: list[tuple[str, str, str, str | None]] = []
    for verb in lexicon["verbs"]:
        comps = (german.get(verb["id"]) or german.get(verb.get("inf")) or {}).get("comps") or {}
        for comp in verb.get("comps") or []:
            if not isinstance(comp, dict) or not isinstance(comp.get("fr"), str):
                continue
            de = comps.get(comp["fr"])
            de = de.get("deu") if isinstance(de, dict) else de
            rows.append((verb["id"], comp["fr"], str(comp.get("en") or ""), de if isinstance(de, str) else None))
    return rows


def test_the_walks_object_says_what_its_glosses_say() -> None:
    rows = {fr: (en, de) for verb, fr, en, de in _objects() if verb == "avoir"}
    mistral = [fr for fr in rows if fr.endswith("rendez-vous au Mistral")]
    assert mistral, sorted(rows)
    for fr in mistral:
        en, de = rows[fr]
        assert _FR_INDEFINITE.match(fr), f"«{fr}» has no article, its glosses do: «{en}» / «{de}»"


def test_every_object_and_its_glosses_agree_on_the_indefinite_article() -> None:
    clashes: list[str] = []
    for verb, fr, en, de in _objects():
        has_article = bool(_FR_INDEFINITE.match(fr))
        if fr in IDIOMS_WITHOUT_ARTICLE:
            if _EN_INDEFINITE.match(en) or (de and _DE_INDEFINITE.search(de)):
                clashes.append(f"{verb}: idiom «{fr}» glossed with an article: «{en}» / «{de}»")
            continue
        if not has_article and en and _EN_INDEFINITE.match(en):
            clashes.append(f"{verb}: «{fr}» has no article, «{en}» has one")
        if not has_article and de and _DE_INDEFINITE.search(de):
            clashes.append(f"{verb}: «{fr}» has no article, «{de}» has one")
        if _FR_SINGULAR.match(fr):
            if en and not _EN_SINGULAR.match(en) and ("en", verb, fr) not in GLOSS_WITHOUT_ARTICLE:
                clashes.append(f"{verb}: «{fr}» has an article, «{en}» has none")
            if de and not _DE_INDEFINITE.search(de) and ("de", verb, fr) not in GLOSS_WITHOUT_ARTICLE:
                clashes.append(f"{verb}: «{fr}» has an article, «{de}» has none")
    assert not clashes, "\n".join(clashes)
