"""Two spellings that are both right: no correction may turn one into the other (package V).

The 1990 rectifications («Les rectifications de l'orthographe», Journal officiel, 6 Dec
1990) made a second spelling of many words correct: «cout» beside «coût», «ognon»
beside «oignon», «évènement» beside «événement», «weekend» beside «week-end». Schools
in France, Belgium, Switzerland and Quebec teach the new forms; dictionaries list both.
The rule pass restored the circumflex of «plait» and «aout», and a model could «fix»
either form into the other: the learner was told correct French was wrong.

:func:`is_variant_edit` is the gate. It is true when a span and its replacement are the
same words, each written in an accepted spelling, or differ only in typography (the
two apostrophes, the space before «?»). Every rule edit and every model edit is refused
when it is true (``correction_contract.verify_edit``, ``deterministic_edits`` and the
sentence gaps of ``verify_correction``).

The test list is ``tests/verdict_corpus/valid_variants.txt``.
"""

from __future__ import annotations

import re
import unicodedata

__all__ = ["is_variant_edit", "same_word_variant"]

_APOSTROPHES = str.maketrans({"’": "'", "‘": "'", "ʼ": "'", "`": "'", "´": "'"})
#: Any space before a high punctuation mark or after «, before »: French and Swiss usage differ.
_SPACE_BEFORE_MARK = re.compile(r"[\s  ]+(?=[?!:;»])")
_SPACE_AFTER_GUILLEMET = re.compile(r"(?<=«)[\s  ]+")
_SPACES = re.compile(r"[\s  ]+")

#: The reform keeps the circumflex where it tells two words apart, and in these verb endings.
_CIRCUMFLEX_KEPT = frozenset(
    {
        "dû", "mûr", "mûre", "mûrs", "mûres", "mûrement", "sûr", "sûre", "sûrs", "sûres", "sûrement",
        "jeûne", "jeûnes", "jeûner", "jeûnent", "crû", "crûs", "crûe", "crûes", "croît", "croîs",
    }
)
_CIRCUMFLEX_KEPT_ENDINGS = ("îmes", "ûmes", "îtes", "ûtes")
_DROPPED_CIRCUMFLEX = str.maketrans({"î": "i", "û": "u"})

#: é before a syllable with a silent e may be written è: «évènement», «cèderai», «crèmerie».
#: The next syllable must hold a plain «e» (not «eu», «ei», «ea»: «déjeuner» stays).
_SILENT_E_SYLLABLE = re.compile(r"^[bcçdfghjklmnpqrstvwxz]+e(?![uiaœ])")

#: The tréma moves to the letter that is said: «aiguë» -> «aigüe», «ambiguïté» -> «ambigüité».
_TREMA = (("güe", "guë"), ("güi", "guï"))

#: Compounds the reform glues after these elements: «extraterrestre», «contrattaque».
_GLUED_PREFIXES = ("contre", "entre", "extra", "infra", "intra", "ultra", "porte", "supra")

#: Number words: the reform joins every part of a written number with hyphens.
_NUMBER_WORDS = frozenset(
    {
        "un", "une", "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf", "dix", "onze",
        "douze", "treize", "quatorze", "quinze", "seize", "vingt", "vingts", "trente", "quarante",
        "cinquante", "soixante", "cent", "cents", "mille", "et",
    }
)

#: Single words the reform (or older usage) spells two ways, each pair both right.
_PAIRS = (
    ("oignon", "ognon"),
    ("nénuphar", "nénufar"),
    ("chariot", "charriot"),
    ("asseoir", "assoir"),
    ("assieds", "assois"),
    ("clé", "clef"),
    ("paye", "paie"),
    ("payes", "paies"),
    ("payent", "paient"),
    ("payerai", "paierai"),
    ("relais", "relai"),
    ("week-end", "weekend"),
    ("porte-monnaie", "portemonnaie"),
    ("porte-clés", "porteclé"),
    ("combativité", "combattivité"),
    ("interpeller", "interpeler"),
    ("renouvelle", "renouvèle"),
    ("renouvellent", "renouvèlent"),
    ("renouvellement", "renouvèlement"),
    ("étiquette", "étiquète"),
    ("étiquettent", "étiquètent"),
    ("ruisselle", "ruissèle"),
    ("ruissellent", "ruissèlent"),
    ("ruissellement", "ruissèlement"),
    ("amoncelle", "amoncèle"),
    ("ficelle", "ficèle"),
    ("événement", "évènement"),
)


def _plural(pair: tuple[str, str]) -> tuple[str, str]:
    return tuple(word if word.endswith(("s", "x", "z")) else word + "s" for word in pair)  # type: ignore[return-value]


_KNOWN_PAIRS = frozenset(frozenset(pair) for pair in (*_PAIRS, *map(_plural, _PAIRS)))


def _typography(value: object) -> str:
    text = unicodedata.normalize("NFC", "" if value is None else str(value)).translate(_APOSTROPHES)
    text = _SPACE_BEFORE_MARK.sub("", text)
    text = _SPACE_AFTER_GUILLEMET.sub("", text)
    return _SPACES.sub(" ", text).strip()


def _circumflex_variant(left: str, right: str) -> bool:
    if left.translate(_DROPPED_CIRCUMFLEX) != right.translate(_DROPPED_CIRCUMFLEX):
        return False
    for word in (left, right):
        if word in _CIRCUMFLEX_KEPT or word.endswith(_CIRCUMFLEX_KEPT_ENDINGS):
            return False
    return True


def _grave_variant(left: str, right: str) -> bool:
    if len(left) != len(right):
        return False
    differing = [i for i, (a, b) in enumerate(zip(left, right, strict=True)) if a != b]
    if not differing:
        return False
    for i in differing:
        if {left[i], right[i]} != {"é", "è"}:
            return False
        if not _SILENT_E_SYLLABLE.match(left[i + 1 :]):
            return False
    return True


def _trema_variant(left: str, right: str) -> bool:
    def moved(word: str) -> str:
        for new, old in _TREMA:
            word = word.replace(new, old)
        return word

    return left != right and moved(left) == moved(right)


def _glued_variant(left: str, right: str) -> bool:
    """«extra-terrestre» / «extraterrestre», «contre-attaque» / «contrattaque»."""

    hyphened, glued = (left, right) if "-" in left else (right, left)
    if "-" not in hyphened or "-" in glued or " " in glued:
        return False
    head, _, tail = hyphened.partition("-")
    if head not in _GLUED_PREFIXES:
        return False
    # «contre» + «attaque» drops its e before a vowel when glued.
    return glued in {head + tail, head[:-1] + tail}


def same_word_variant(left: str, right: str) -> bool:
    """``left`` and ``right`` are one word in two accepted spellings (casefolded)."""

    left, right = left.casefold(), right.casefold()
    if left == right:
        return True
    if frozenset((left, right)) in _KNOWN_PAIRS:
        return True
    return (
        _circumflex_variant(left, right)
        or _grave_variant(left, right)
        or _trema_variant(left, right)
        or _glued_variant(left, right)
    )


def _number_variant(left: str, right: str) -> bool:
    """«vingt et un» / «vingt-et-un», «deux cents» / «deux-cents»."""

    a, b = left.replace("-", " ").split(), right.replace("-", " ").split()
    return a == b and len(a) > 1 and all(word in _NUMBER_WORDS for word in a)


def is_variant_edit(span: object, replacement: object) -> bool:
    """True when replacing ``span`` with ``replacement`` changes no word, only its spelling
    between two accepted forms or its typography. Such an edit corrects nothing."""

    left, right = _typography(span), _typography(replacement)
    if not left or not right:
        return False
    if left == right:
        return True
    if left.casefold() == right.casefold():
        return False  # a capital is a real fix
    folded_left, folded_right = left.casefold(), right.casefold()
    if _number_variant(folded_left, folded_right):
        return True
    words_left, words_right = folded_left.split(" "), folded_right.split(" ")
    if len(words_left) != len(words_right):
        return False
    changed = False
    for a, b in zip(words_left, words_right, strict=True):
        if a == b:
            continue
        core_a, core_b = a.strip(".,;:!?«»\"()"), b.strip(".,;:!?«»\"()")
        if a.replace(core_a, "", 1) != b.replace(core_b, "", 1):
            return False  # punctuation around the word changed
        if not same_word_variant(core_a, core_b) and not _elided_variant(core_a, core_b):
            return False
        changed = True
    return changed


def _elided_variant(left: str, right: str) -> bool:
    """«d'ognon» / «d'oignon»: the same elided article before two accepted spellings."""

    if "'" not in left or "'" not in right:
        return False
    head_a, _, tail_a = left.partition("'")
    head_b, _, tail_b = right.partition("'")
    return head_a == head_b and tail_a != tail_b and same_word_variant(tail_a, tail_b)
