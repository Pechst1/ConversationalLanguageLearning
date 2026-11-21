"""The facts a learner states in a reply: dates and numbers, and the reason given (#379, #145).

A line written before the learner spoke (a task's scripted example) can say the
opposite of what they just said: on the 30 Oct walk the learner answered «le deux
decembre, parce que je suis fatigue de Berlin» and was offered «Je rentre le 19
décembre, parce que je reste pour la fête.» to say aloud as theirs.

Pure, no model call. :func:`contradicts` is deliberately narrow: it only speaks when
the learner stated a kind of fact (a number, a month, a reason) and the line states
that kind differently. A reply with no such facts vetoes nothing.

#556 added what they refused (:func:`stance_of`): on the 9 Nov walk the line was «Oui, on
partage.» after «Non, je ne partage pas la pizza». A reading here decides only which
line a card offers, so a wrong one costs a line, never a turn: it may be simple.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from typing import Any

_UNITS = {
    "zero": 0, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6, "sept": 7, "huit": 8, "neuf": 9,
    "dix": 10, "onze": 11, "douze": 12, "treize": 13, "quatorze": 14, "quinze": 15, "seize": 16,
    "vingt": 20, "trente": 30, "quarante": 40, "cinquante": 50, "soixante": 60,
}
#: «un» and «une» are the article far more often than the number: never read as one.
_MULTIPLIERS = {"cent": 100, "cents": 100, "mille": 1000}
_MONTHS = frozenset(
    "janvier fevrier mars avril mai juin juillet aout septembre octobre novembre decembre".split()
)
_REASON = re.compile(r"\b(?:parce qu'|parce que|puisque|puisqu'|car)\s*(.*)$")
#: Words that carry no reason: a reason is compared by what it is about.
_LIGHT = frozenset(
    "parce puisque pour avec dans mais suis fais est sont etre avoir tres trop aussi encore alors donc "
    "cette comme moins plus bien beaucoup que qui quoi leur nous vous elle elles ils".split()
)


def fold(text: Any) -> str:
    value = unicodedata.normalize("NFKD", str(text or "")).casefold()
    value = "".join(char for char in value if not unicodedata.combining(char))
    return " ".join(value.replace("’", "'").replace("-", " ").split())


def _tokens(text: Any) -> list[str]:
    return re.findall(r"\d+|[a-z']+", fold(text))


def numbers_of(text: Any) -> frozenset[int]:
    """Every number in the text, digits or words («deux», «dix-neuf», «quatre-vingts»)."""

    found: set[int] = set()
    run: list[str] = []

    def flush() -> None:
        if not run:
            return
        total, current = 0, 0
        for word in run:
            if word == "et":
                continue
            if word in _MULTIPLIERS:
                current = (current or 1) * _MULTIPLIERS[word]
                total, current = total + current, 0
            elif word == "vingt" and current == 4:
                current = 80
            elif word == "vingts":
                current = (current or 1) * 20
            else:
                current += _UNITS.get(word, 1)
        found.add(total + current)
        run.clear()

    for piece in _tokens(text):
        if piece.isdigit():
            flush()
            found.add(int(piece))
        elif (
            piece in _UNITS
            or piece in _MULTIPLIERS
            or piece == "vingts"
            or (piece == "et" and run)
            # «vingt et un», and «quatre-vingt-un» where «un» follows «vingt».
            or (piece == "un" and run and run[-1] in ("et", "vingt"))
        ):
            run.append(piece)
        else:
            flush()
    flush()
    return frozenset(found)


def months_of(text: Any) -> frozenset[str]:
    return frozenset(token for token in _tokens(text) if token in _MONTHS)


def reason_of(text: Any) -> frozenset[str]:
    """What the reason given («parce que …») is about, as word stems; empty when none."""

    match = _REASON.search(fold(text))
    if not match:
        return frozenset()
    words = re.findall(r"[a-z]+", match.group(1))
    return frozenset(word[:5] for word in words if len(word) >= 4 and word not in _LIGHT)


#: A negation's second word. «ne» is often dropped in speech and by learners, so these
#: mark it; the three that also mean something else count only with «ne».
_ALWAYS_NEGATES = frozenset({"pas", "jamais"})
_NEGATES_WITH_NE = frozenset({"plus", "rien", "personne"})
#: «je ne veux pas partager» refuses the sharing, not the wanting.
_CARRIERS = frozenset(
    "veux veut voulons voulez veulent peux peut pouvons pouvez peuvent dois doit devons devez doivent "
    "vais vas va allons allez vont faut vouloir pouvoir devoir aller falloir".split()
)
#: Words of politeness and assent: a reply of nothing else is about nothing.
_SAYS_NOTHING = frozenset("accord merci bonjour bonsoir salut pardon desole vraiment voila ouais".split())
#: «je n'ai pas partagé»: the verb is the word after the negation.
_AUXILIARIES = frozenset("ai as a avons avez ont suis es est sommes etes sont".split())
_OBJECTS = frozenset("le la les y en me te se lui leur nous vous".split())
_INFINITIVE = re.compile(r"(?:er|ir|re|oir)$")
_VERB_ENDING = re.compile(r"(?:ent|ons|ez|er|ir|re|ais|ait|ai|es|e|s|t|é|i|u)$")
_CLAUSE = re.compile(r"[,;:]|\bmais\b")
_SENTENCE = re.compile(r"[^.!?…]+[.!?…]*")


@lru_cache(maxsize=1)
def _irregular_forms() -> dict[str, str]:
    """The lexicon's irregular forms, folded as this module folds: «lis» is «lire»."""

    from app.services.lexical_coverage import load_lexicon

    return {fold(form): fold(lemma) for form, lemma in load_lexicon().forms.items()}


def _lemma(word: str) -> str:
    return _irregular_forms().get(word, word)


def _stem(word: str) -> str:
    """«partage» and «partager», «vends» and «vendre», «lis» and «lire» are one word here."""

    lemma = _lemma(word)
    base = _VERB_ENDING.sub("", lemma)
    return (base if len(base) >= 3 else lemma)[:5]


def _carries_meaning(word: str) -> bool:
    if word == "ne":
        # The negation's first word, never a word of meaning: the lexicon folds it to
        # «naître» (#748), which made every negative reply «about» being born.
        return False
    lemma = _lemma(word)
    if len(word) < 4 and lemma == word:
        return False
    return not any(
        form in _LIGHT or form in _CARRIERS or form in _SAYS_NOTHING for form in (word, lemma)
    ) and (word not in _ALWAYS_NEGATES and word not in _NEGATES_WITH_NE)


def _clause_words(clause: str) -> list[str]:
    words: list[str] = []
    for piece in re.findall(r"[a-z']+", clause):
        head, _, tail = piece.rpartition("'")
        if head == "n":
            words.append("ne")
        elif head == "d":
            # «pas d'argent» is «pas de» + «argent»: the «de» marks what is refused (#748).
            words.append("de")
        if tail:
            words.append(tail)
    return words


def _negated_in(words: list[str]) -> set[str]:
    negated: set[str] = set()
    has_ne = "ne" in words
    for index, word in enumerate(words):
        if word not in _ALWAYS_NEGATES and not (has_ne and word in _NEGATES_WITH_NE):
            continue
        head = words[index - 1] if index else ""
        after = next((other for other in words[index + 1 :] if other not in _OBJECTS), "")
        if after == "de" and word != "rien":
            # #748: «je ne veux pas de pizza», «pas de café pour moi», «jamais de viande»
            # refuse the thing after «de», the commonest refusal at A1. Read as wanted,
            # the refused pizza came back as the line to say aloud.
            thing = next((other for other in words[index + 2 :] if other not in _OBJECTS), "")
            if thing:
                negated.add(thing)
        elif head in _AUXILIARIES or _INFINITIVE.search(after):
            negated.add(after)
        if head not in _CARRIERS and head not in _AUXILIARIES:
            negated.add(head)
    return negated


def _stance_read() -> bool:
    """#556's stance reading is the story-truth stack's: off with ``STORY_SCENE_RECORD``."""

    from app.services import scene_record

    return scene_record.enabled()


def stance_of(text: Any) -> dict[str, bool]:
    """What a text says yes or no to: ``{stem: affirmed}``. A question says neither, and a
    word both negated and affirmed in one reply is left out: nothing can be read from it."""

    stance: dict[str, bool] = {}
    torn: set[str] = set()
    for sentence in _SENTENCE.findall(fold(text)):
        if sentence.rstrip().endswith("?"):
            continue
        for clause in _CLAUSE.split(sentence):
            words = _clause_words(clause)
            negated = _negated_in(words)
            for word in words:
                if not _carries_meaning(word):
                    continue
                stem, affirmed = _stem(word), word not in negated
                if stance.get(stem, affirmed) is not affirmed:
                    torn.add(stem)
                stance[stem] = affirmed
    return {stem: affirmed for stem, affirmed in stance.items() if stem not in torn}


def content_of(text: Any) -> frozenset[str]:
    """The words that say what a text is about, as stems, questions included."""

    return frozenset(_stem(word) for word in _clause_words(fold(text)) if _carries_meaning(word))


def _goes_against(said: dict[str, bool], line: dict[str, bool]) -> bool:
    return any(stem in line and line[stem] is not affirmed for stem, affirmed in said.items())


KINDS = ("numbers", "months", "reason")


def facts_of(text: Any) -> dict[str, frozenset]:
    """The kinds of fact the text states, each with its value; a kind not stated is absent."""

    found = {"numbers": numbers_of(text), "months": months_of(text), "reason": reason_of(text)}
    return {kind: value for kind, value in found.items() if value}


def clashes(learner_text: Any, line: Any) -> frozenset[str]:
    """The kinds of fact the learner stated that ``line`` states differently."""

    said, offered = facts_of(learner_text), facts_of(line)
    kinds = set()
    for kind, value in said.items():
        other = offered.get(kind, frozenset())
        # A reason is the same reason when it is about one of the same things.
        if (kind == "reason" and not (value & other)) or (kind != "reason" and value != other):
            kinds.add(kind)
    if _stance_read() and _goes_against(stance_of(learner_text), stance_of(line)):
        kinds.add("stance")
    return frozenset(kinds)


def contradicts(learner_text: Any, line: Any) -> bool:
    """Does ``line`` state a date, number or reason that is not the learner's own?

    A kind of fact the learner did not state never counts against the line."""

    return bool(clashes(learner_text, line))


def latest_clash(turns: list[Any], line: Any) -> int | None:
    """The index of the latest turn whose fact ``line`` contradicts, or ``None``.

    Per kind of fact, only the latest turn that states it counts: a learner who
    changed «le 2 décembre» to «finalement le 19» has the 19th as their date. A stance
    is per word: «Non, je ne partage pas» stands until they say they share."""

    clash = None
    for kind in KINDS:
        latest = next((index for index in reversed(range(len(turns))) if kind in facts_of(turns[index])), None)
        if latest is not None and kind in clashes(turns[latest], line):
            clash = latest if clash is None else max(clash, latest)
    decided: dict[str, tuple[int, bool]] = {}
    for index, turn in enumerate(turns if _stance_read() else []):
        decided.update({stem: (index, affirmed) for stem, affirmed in stance_of(turn).items()})
    offered = stance_of(line)
    for stem, (index, affirmed) in decided.items():
        if stem in offered and offered[stem] is not affirmed:
            clash = index if clash is None else max(clash, index)
    return clash


def chips_for_thread(chips: list[str], learner_turns: list[Any]) -> list[str]:
    """#557: the suggested replies that still fit what the learner has said.

    Live walk 6 Nov: after «Non, je ne peux pas venir à ta fête» the chips were still the
    letter's opening set, «Oui, je viens à ta fête !» among them. A chip goes when it says
    the opposite of where the learner stands now, or when everything in it has been said.
    A question says neither. Nothing left means no chips, never a wrong one.
    """

    if not learner_turns:
        return list(chips)
    decided: dict[str, bool] = {}
    for turn in learner_turns:
        decided.update(stance_of(turn))
    said = [content_of(turn) for turn in learner_turns]
    kept = []
    for chip in chips:
        words = content_of(chip)
        if _goes_against(decided, stance_of(chip)) or (words and any(words <= turn for turn in said)):
            continue
        kept.append(chip)
    return kept


def _lexicon_verb(key: str, lexicon: Any) -> bool:
    def verb(lemma: str | None) -> bool:
        return bool(lemma) and (lexicon.lemmas.get(lemma) or {}).get("pos") == "verb"

    # The lexicon's form table holds the irregular verbs: «aime» and «parlé» are read here.
    regular = re.sub(r"(?:es|ent|é|ée|és|ées)$", "", key)
    return verb(lexicon.forms.get(key)) or verb(key) or verb(f"{key}r") or verb(f"{regular}er")


_SUBJECTS = frozenset("je tu il elle on nous vous ils elles".split())


def has_verb(text: Any) -> bool:
    """Does the text hold a verb? Read from the lexicon, or from a subject with a word after it."""

    from app.services.lexical_coverage import load_lexicon, tokenize

    lexicon = load_lexicon()
    keys = [token.key for token in tokenize(str(text or ""))]
    return any(
        _lexicon_verb(key, lexicon) or (key in _SUBJECTS and index + 1 < len(keys)) for index, key in enumerate(keys)
    )


def reads_as_sentence(text: Any) -> bool:
    """At least three words and a verb: not a prop («LARTSIM»), not a fragment («fatigué»)."""

    return len(str(text or "").split()) >= 3 and has_verb(text)


_ELIDED = ("qu", "l", "d", "j", "n", "m", "t", "s", "c")
_FOLD_ACCENTS = str.maketrans("", "", "\u0300\u0301\u0302\u0303\u0308\u0327")


def _bare(word: str) -> str:
    return unicodedata.normalize("NFD", word).translate(_FOLD_ACCENTS)


@lru_cache(maxsize=1)
def _accented_words() -> frozenset[str]:
    """Every lexicon word that carries an accent, without it: «verite», «grand-mere»."""

    from app.services.lexical_coverage import load_lexicon

    lexicon = load_lexicon()
    words = set(lexicon.lemmas) | set(lexicon.forms)
    return frozenset(_bare(word) for word in words if _bare(word) != word)


def looks_misspelled(text: Any) -> bool:
    """A word the lexicon knows, written without its accent or its apostrophe (8 Nov:
    «grand-mere», «lappartement»). Rare words and names are not touched: a word is held
    against the text only when the lexicon can name the word it should have been. This
    sees spelling only: «il ne sais pas» reads fine, the margin's correction catches it."""

    from app.services.lexical_coverage import load_lexicon, tokenize

    lexicon = load_lexicon()

    def known(word: str) -> bool:
        # «arrive» is the verb, not «arrivé» without its accent.
        return word in lexicon.lemmas or word in lexicon.forms or _lexicon_verb(word, lexicon)

    for token in tokenize(str(text or "")):
        key = token.key
        if known(key) or key in lexicon.elisions or any(char.isdigit() for char in key):
            continue
        if key in _accented_words():
            return True
        if any(key.startswith(lead) and known(key[len(lead) :]) for lead in _ELIDED):
            return True
    return False
