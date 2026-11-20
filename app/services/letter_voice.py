"""Deterministic guards for what a Courrier character says: one address form, one band.

Root cause these guards exist for (#117): the Courrier had a lexical guard for the
letter (``letter_level_verdict``) and nothing else. A letter could mix «tu» and
«vous» between its opening and its P.S., and the character's *replies*
(``MissionConversationService.respond``) were never checked at all, so an A1.1
learner got the plus-que-parfait, the subjunctive and the future from a friend
whose letter was written in the present tense. Scenes already have these guards
(``living_story._check_scene_address_register``, ``_check_register``); the Courrier
had none. This module is the Courrier's equivalent, shared by the letter writer and
the reply writer so the two cannot drift apart again.

The detectors only flag forms that cannot be read any other way. «ils viennent» is
the indicative present as much as the subjunctive, «il était fatigué» is an
adjective, not a pluperfect: a guard that flags ordinary A1 French costs the learner
a good reply, which is worse than the bug it replaces.

Pure functions, no model calls.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache

from app.services.pragmatics import address_markers

_ADVERBS = r"(?:\s+(?:déjà|pas|jamais|encore|enfin|bien|toujours|vraiment))*"

#: Participles after «avoir»: «j'avais prévu», «il n'avait pas oublié».
_AVOIR_PARTICIPLES = (
    r"(?:\w+é|eu|pris|fait|dit|vu|lu|su|pu|voulu|dû|mis|ouvert|reçu|prévu"
    r"|fini|compris|perdu|entendu|attendu|connu|bu|cru|écrit|offert|appris|promis|décidé)"
)
#: «être» takes a participle in the pluperfect only for the movement verbs and the
#: pronominal ones; «était fatigué / fermé / occupé / né» are adjectives or states.
_ETRE_PARTICIPLES = (
    r"(?:parti|venu|arrivé|allé|tombé|resté|rentré|retourné|entré|sorti|monté|descendu|passé"
    r"|devenu|revenu|mort|décédé)(?:e|s|es)?"
)
_AVOIR_AUX = r"(?:avais|avait|avions|aviez|avaient)"
_ETRE_AUX = r"(?:étais|était|étions|étiez|étaient)"
#: «j'avais prévu», «elle était partie», «elle s'était trompée», «nous nous étions perdus».
_PLUS_QUE_PARFAIT = re.compile(
    rf"\b{_AVOIR_AUX}{_ADVERBS}\s+{_AVOIR_PARTICIPLES}\b"
    rf"|\b(?!c['’]){_ETRE_AUX}{_ADVERBS}\s+{_ETRE_PARTICIPLES}\b"
    rf"|\b(?:je\s+m['’]étais|tu\s+t['’]étais|s['’](?:était|étaient)|nous\s+nous\s+étions|vous\s+vous\s+étiez)"
    rf"{_ADVERBS}\s+\w+",
    re.IGNORECASE,
)
#: Subjunctive forms that are spelt differently from the indicative present. Left out on
#: purpose: «viennent, prennent, partent, doivent» (3rd person plural, same in both),
#: «sois/soit» after «que tu/il» are fine, «veuille, sache…» are not indicative anywhere.
_SUBJ_FORMS = (
    r"(?:sois|soit|soient|soyez|soyons|aies|ait|aient|aie|ayez|ayons|fasse|fasses|fassent|fassiez"
    r"|puisse|puisses|puissent|puissiez|aille|ailles|aillent|sache|saches|sachent|sachiez"
    r"|veuille|veuilles|veuillent|vienne|viennes|prenne|prennes|parte|partes|doive|doives)"
)
#: «qu'il y ait eu», «que tu viennes», «il faut que», «bien que».
_SUBJUNCTIVE = re.compile(
    rf"\bqu['’]\s*(?:il|elle|on|ils|elles)\s+(?:y\s+)?{_SUBJ_FORMS}\b"
    rf"|\bque\s+(?:je|j['’]|tu|nous|vous|il|elle|on|ils|elles)\s*(?:y\s+)?{_SUBJ_FORMS}\b"
    r"|\b(?:bien que|il faut que|pour que|avant que|à moins que|jusqu['’]à ce que)\b",
    re.IGNORECASE,
)
_FUTURE_ENDING = r"(?:ai|as|a|ons|ez|ont)"
#: Future stems spelt like no present: «ser-», «aur-», «ir-», «pourr-»… (every person).
_FUTURE_SHORT_STEMS = (
    r"(?:ser|aur|ir|fer|pourr|devr|voudr|verr|saur|enverr|faudr|vaudr|courr|mourr|recevr"
    r"|dir|lir|rir|croir|boir|vivr|suivr|plair)"
)
#: Longer ones, also behind a prefix («reviendra», «comprendrez», «découvrira»). Only the
#: listed «-ir» verbs: «désirez», «admirons» are the present of «-irer» verbs.
_FUTURE_LONG_STEMS = (
    r"(?:viendr|tiendr|prendr|mettr|[ée]crir|uir|connaîtr|connaitr|paraîtr|paraitr|battr|rompr"
    r"|ondr|endr|perdr|mordr|tordr|coudr|moudr|joindr|peindr|craindr|plaindr"
    r"|finir|choisir|partir|sortir|dormir|ouvrir|offrir|souffrir|servir|sentir|r[ée]ussir|grandir"
    r"|r[ée]fl[ée]chir|agir|ob[ée]ir|remplir|bâtir|batir|nourrir|guérir|guerir|rougir|maigrir|grossir)"
)
_FUTURE = re.compile(
    rf"\b(?:re|ré)?{_FUTURE_SHORT_STEMS}{_FUTURE_ENDING}\b"
    rf"|\b\w*{_FUTURE_LONG_STEMS}{_FUTURE_ENDING}\b"
    r"|\b\w{3,}(?:erai|eras|era|erons|erez|eront)\b",
    re.IGNORECASE,
)

#: Tenses each learner band has not met; A1 also gets no future.
_BAND_TENSES = {
    "A1": ("plus-que-parfait", "subjonctif", "futur simple"),
    "A2": ("plus-que-parfait", "subjonctif"),
}
_DETECTORS = {
    "plus-que-parfait": _PLUS_QUE_PARFAIT,
    "subjonctif": _SUBJUNCTIVE,
    "futur simple": _FUTURE,
}
#: What the writer is asked to use instead, per band. It describes the French; it never
#: names the reader's level (an actor told its reader is a beginner turns into a tutor).
_BAND_STYLE = {
    "A1": "Use only everyday words in short sentences, in the present tense and the passé composé.",
    "A2": "Use only everyday words in short sentences; no subjunctive and no plus-que-parfait.",
}


def above_band_tenses(text: str | None, level: str | None) -> list[str]:
    """The tenses in ``text`` the learner's band has not met; empty from B1 up."""

    band = str(level or "").strip().upper()[:2]
    return [tense for tense in _BAND_TENSES.get(band, ()) if _DETECTORS[tense].search(text or "")]


def band_style_line(level: str | None) -> str:
    """One sentence for a character's prompt: the French to write, without naming a level."""

    return _BAND_STYLE.get(str(level or "").strip().upper()[:2], "")


def voice_problems(texts: list[str | None], *, register: str | None, level: str | None) -> list[str]:
    """Why a character's own words must be rewritten, as hints for the writer.

    ``register`` is ``"tu"`` or ``"vous"`` (or ``None`` when unknown: only a text
    that mixes both is then wrong). ``texts`` are everything one character says in
    one go (a letter's opening and its P.S.).
    """

    joined = " ".join(str(item) for item in texts if item and str(item).strip())
    problems: list[str] = []
    tu_seen, vous_seen = address_markers(joined)
    if tu_seen and vous_seen:
        problems.append(
            "The character addresses the learner with both «tu» and «vous» (and their "
            "possessives). Use exactly one form in every sentence, the P.S. included."
        )
    elif register == "tu" and vous_seen:
        problems.append("This character says «tu» to the learner: never «vous», «votre» or «vos».")
    elif register == "vous" and tu_seen:
        problems.append("This character says «vous» to the learner: never «tu», «toi», «ton» or «ta».")
    tenses = above_band_tenses(joined, level)
    if tenses:
        problems.append(f"Too hard to read: no {', '.join(tenses)}. {band_style_line(level)}")
    problems.extend(french_problems(joined))
    return problems


# ---------------------------------------------------------------------------
# #747: the French itself. The guards above read the register and the tenses of a
# character's line and nothing else, so «mais que allons-nous prendre ?» and «d'une
# sandwich» reached an A1.1 learner who copies what a character writes. Two mistakes a
# reader can check without a parser: a word that must elide before a vowel, and an
# article whose gender a known noun contradicts. Both flag only forms that cannot be
# right; a false hit costs one rewrite of a good line, never the line itself.
# ---------------------------------------------------------------------------

_VOWEL = "aeiouéèêëàâäîïôöûùüœæ"
#: Words that take no elision although they start with a vowel («je crois que oui», «le
#: onze»), and «ou» («la ou le bleu»), a conjunction rather than the next word.
_NO_ELISION_BEFORE = frozenset({"oui", "ouais", "onze", "onzième", "ouate", "ouistiti", "uhlan", "euh", "ou"})
#: «que allons» → «qu'allons», «je ai» → «j'ai». Not after a hyphen: «donne-le à Marie».
_ELISION = re.compile(rf"(?<![\w'’-])((?i:que|je|me|te|se|ne|de|le|la))\s+([{_VOWEL}][\w'’-]*)")
_SI_IL = re.compile(r"(?<![\w'’-])((?i:si))\s+(ils?)\b")
_CE_EST = re.compile(r"(?<![\w'’-])((?i:ce))\s+(est|était)\b")


def _elided(word: str, following: str) -> str:
    head = "qu" if word.lower() == "que" else word[0]
    if word[0].isupper():
        head = head[0].upper() + head[1:]
    return f"{head}'{following}"


def missing_elisions(text: str | None) -> list[tuple[str, str]]:
    """``(as written, as it must be written)`` for each word that must elide and does not."""

    raw = str(text or "").replace("’", "'")
    found: list[tuple[str, str]] = []
    for match in _ELISION.finditer(raw):
        word, following = match.group(1), match.group(2)
        head = re.split(r"[-']", following)[0]
        if head in _NO_ELISION_BEFORE or (word.lower() == "la" and head == "une"):
            continue
        found.append((f"{word} {following}", _elided(word, following)))
    for pattern in (_SI_IL, _CE_EST):
        for match in pattern.finditer(raw):
            found.append((f"{match.group(1)} {match.group(2)}", _elided(match.group(1), match.group(2))))
    return found


#: Nouns of the A1/A2 lists whose other gender is also a word, or which name a person of
#: either sex: «une livre de pommes», «la tour», «un crème», «une médecin», «une enfant».
_EITHER_GENDER = frozenset(
    {
        "livre", "tour", "poste", "solde", "aide", "mort", "orange", "physique", "crème", "fin", "mode",
        "manche", "page", "enfant", "médecin", "professeur", "docteur", "chef", "auteur", "écrivain",
        "ingénieur", "guide", "propriétaire", "membre", "après-midi", "gens", "radio",
    }
)
_ARTICLE_NOUN = re.compile(rf"(?<![\w-])((?i:un|une))\s+([a-zç{_VOWEL}][\w-]*)(?![\w'’-])")


@lru_cache(maxsize=1)
def _band_noun_genders() -> dict[str, str]:
    """``noun → m/f`` for the A1/A2 nouns of the core lexicon: the words a learner copies."""

    from app.services.lexical_coverage import LEXICON_PATH

    try:
        lemmas = json.loads(LEXICON_PATH.read_text(encoding="utf-8")).get("lemmas") or {}
    except (OSError, ValueError):  # pragma: no cover - a missing lexicon checks nothing
        return {}
    return {
        str(lemma): str(entry["gender"])
        for lemma, entry in lemmas.items()
        if entry.get("pos") == "noun"
        and entry.get("gender") in {"m", "f"}
        and str(entry.get("band") or "") in {"A1", "A2"}
        and lemma not in _EITHER_GENDER
    }


def wrong_articles(text: str | None) -> list[tuple[str, str]]:
    """``(as written, as it must be written)`` for «une sandwich», «un salade»."""

    genders = _band_noun_genders()
    found: list[tuple[str, str]] = []
    for match in _ARTICLE_NOUN.finditer(str(text or "")):
        article, noun = match.group(1), match.group(2)
        wanted = {"m": "un", "f": "une"}.get(genders.get(noun, ""))
        if wanted and article.lower() != wanted:
            fixed = wanted.capitalize() if article[0].isupper() else wanted
            found.append((f"{article} {noun}", f"{fixed} {noun}"))
    return found


def french_problems(text: str | None) -> list[str]:
    """The rewrite hints for the French of one character's line."""

    problems: list[str] = []
    elisions = missing_elisions(text)
    if elisions:
        pairs = ", ".join(f"«{fixed}», not «{written}»" for written, fixed in elisions)
        problems.append(f"Elide before a vowel: write {pairs}.")
    articles = wrong_articles(text)
    if articles:
        pairs = ", ".join(f"«{fixed}», not «{written}»" for written, fixed in articles)
        problems.append(f"Wrong gender: write {pairs}.")
    return problems


# ---------------------------------------------------------------------------
# #747: the note printed under a letter says where things are; it may not put a thing
# the letter placed somewhere else («ma serviette est au travail» in Nina's line, «la
# serviette est restée chez Nina» in the note under it).
# ---------------------------------------------------------------------------

_DETERMINER = (
    r"(?:la|le|les|l['’]|un|une|des|mon|ma|mes|ton|ta|tes|son|sa|ses|notre|nos|votre|vos|leur|leurs"
    r"|ce|cet|cette)"
)
_PLACED = re.compile(
    r"(?<![\w-])(?i:(?:ma|ta|sa|mon|ton|son|la|le|notre|votre|leur)\s+|l['’])"
    r"(?P<thing>[a-zàâäçéèêëîïôöùûüœ-]{3,})"
    r"\s+(?i:est|sont|était|reste)(?:\s+(?:encore|toujours|déjà|bien))?(?:\s+rest[ée]e?s?)?"
    rf"\s+(?i:au|aux|à\s+la|à\s+l['’]|chez|dans|sur|sous)\s*(?:(?i:{_DETERMINER})\s*)?"
    r"(?P<place>[^\W\d_][\w-]*)"
)


def _places(text: str | None) -> dict[str, set[str]]:
    places: dict[str, set[str]] = {}
    for match in _PLACED.finditer(str(text or "")):
        places.setdefault(match.group("thing").lower(), set()).add(match.group("place").lower())
    return places


def contradicted_things(line: str | None, note: str | None) -> list[str]:
    """The things ``note`` puts somewhere else than the character's ``line`` does."""

    said = _places(line)
    return sorted(thing for thing, where in _places(note).items() if thing in said and not where & said[thing])


def register_word(value: object) -> str | None:
    """«tu» / «vous» from a stored register description, else ``None``."""

    text = str(value or "").strip().lower()
    if text.startswith("tu"):
        return "tu"
    if text.startswith("vous"):
        return "vous"
    return None
