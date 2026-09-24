"""WP-L4 — grammar items, posed deterministically from a unit brief.

The journey planner is a pure function, so everything here is too: the input
is a unit brief (:func:`app.services.grammar_units.unit_brief`, carried in a
candidate's ``metadata["grammar_brief"]`` or as the day's introduction) and the
sentences of today's scene; the output is ordinary :class:`RecallTask` objects
in formats every client already renders (``choice``, ``word_bank`` / ``tiles``,
``transform``). No model call, no invented French: every sentence is the
catalogue's, the authored card's, or the scene's.

The four steps of the Essai (§2.4), weakest first:

* **recognise** — «which sentence follows today's rule?»: one sentence that
  uses the unit (the scene's first, else a catalogue example) among scene
  sentences no one could read as using it — or no item when that is not
  unambiguous;
* **choose** — the ✗/✓ contrast pair: «which one is right?»;
* **build** — an example sentence rebuilt from chips, with the wrong form of
  the contrast pair (or another form of the paradigm) as a spare chip;
* **transform** — «correct this sentence»: the ✗ sentence of a contrast pair,
  answered by its ✓ (the second pair when the unit has one, so the choose item
  did not just show it).

The no-spoil rule holds per item: a prompt never prints its own answer, and a
builder returns ``None`` rather than pose a format it cannot pose honestly.

Rappel formats scale with the unit's stability (§2.4, WP-L4): low (< 3 days) →
recognise / choose; medium (< 10 days) → build / transform; high → no item,
the unit is asked for inside the reply instead (Réemploi, a free-use prompt).
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Any

from app.services.journey_contracts import ControlLanguage, RecallTask, TargetKind, TargetRef

#: Stability (days) below which a due unit is posed as a pick.
LOW_STABILITY_DAYS = 3.0
#: Stability (days) from which a due unit gets no item: it is asked for in the reply.
REEMPLOI_STABILITY_DAYS = 10.0
#: A sentence longer than this is not a quick item.
MAX_ITEM_WORDS = 14

#: No title: the catalogue's name is jargon (and English); the card's one-line
#: rule is the item's hint, behind the «La règle» affordance.
_RECOGNISE: dict[str, str] = {
    "en": "Which sentence follows today's rule?",
    "de": "Welcher Satz folgt der Regel von heute?",
    "fr": "Quelle phrase suit la règle du jour ?",
}
_CHOOSE: dict[str, str] = {
    "en": "Which one is right?",
    "de": "Was ist richtig?",
    "fr": "Laquelle est juste ?",
}
_BUILD_BANK: dict[str, str] = {
    "en": "Build the sentence. Some chips are not needed.",
    "de": "Bau den Satz. Nicht jeder Baustein wird gebraucht.",
    "fr": "Construisez la phrase. Certains mots sont en trop.",
}
_BUILD_TILES: dict[str, str] = {
    "en": "Put the words in the right order.",
    "de": "Bring die Wörter in die richtige Reihenfolge.",
    "fr": "Remettez les mots dans le bon ordre.",
}
_TRANSFORM: dict[str, str] = {
    "en": "Correct this sentence.",
    "de": "Korrigiere diesen Satz.",
    "fr": "Corrigez cette phrase.",
}
_FIRST_WORD_HINT: dict[str, str] = {
    "en": 'It starts with "{word}".',
    "de": "Er beginnt mit „{word}“.",
    "fr": "Elle commence par « {word} ».",
}


#: The WP-L10 markup: ``[x]`` carries the rule, ``{x}`` is silent.
_MARKUP = re.compile(r"[\[\]{}]")


def plain(value: str | None) -> str:
    """A marked French string as it is said: the WP-L10 marks removed."""

    return " ".join(_MARKUP.sub("", str(value or "")).split())


def fold_apostrophes(text: str | None) -> str:
    return re.sub(r"[’ʼ‘]", "'", str(text or ""))


#: Fixed expressions a broad detector reads as the form but that teach nothing
#: about it: «un peu» is an adverb, not a noun phrase with an article. A match
#: that *is* one of these (the whole span) never counts; a longer span that
#: merely starts with one («un peu de pain», a quantity) still does.
FIXED_EXPRESSIONS: frozenset[str] = frozenset(
    {
        "un peu", "un jour", "une fois", "des fois", "un instant", "un moment",
        "un autre", "une autre", "les uns", "les unes", "l'un", "l'une",
        "tout le monde", "tout le temps", "la plupart", "le plus", "le moins",
        "la fois", "les deux",
    }
)

#: Articles and determiners: the left edge of a noun phrase.
_DETERMINERS = frozenset(
    {
        "un", "une", "des", "le", "la", "les", "du", "au", "aux",
        "mon", "ma", "mes", "ton", "ta", "tes", "son", "sa", "ses",
        "notre", "nos", "votre", "vos", "leur", "leurs", "ce", "cet", "cette", "ces",
    }
)
#: Words that follow a determiner without making a noun phrase that shows gender.
_NOT_A_NOUN = frozenset(
    {
        "peu", "fois", "autre", "autres", "uns", "unes", "plupart", "plus", "moins",
        "deux", "trois", "même", "mêmes", "de", "du", "des", "que", "qui", "quoi",
    }
)
#: Any determiner followed by a word: «does this sentence hold a noun phrase?»
_NOUN_PHRASE = re.compile(
    r"\b(?:un|une|des|le|la|les|du|au|aux|mon|ma|mes|ton|ta|tes|son|sa|ses|notre|nos|"
    r"votre|vos|leurs?|ce|cet|cette|ces)\s+[a-zàâçéèêëîïôûùüÿœ]{2,}|\bl'[a-zàâçéèêëîïôûùüÿœ]",
    re.IGNORECASE,
)


def _is_fixed_expression(span: str) -> bool:
    return " ".join(span.casefold().split()) in FIXED_EXPRESSIONS


def detector_span(patterns: list[str] | None, text: str | None) -> str | None:
    """The first span of ``text`` a regex detector recognises, or ``None``.

    Apostrophes are folded first (iOS types U+2019; the patterns use ``'``).
    A match that is only a fixed expression («un peu», «une fois») is skipped:
    the detector is looking for the form, not for the words that spell it.
    """

    folded = fold_apostrophes(text)
    for pattern in patterns or []:
        try:
            matches = list(re.finditer(pattern, folded, re.IGNORECASE))
        except re.error:
            continue
        for match in matches:
            span = match.group(0).strip()
            if span and not _is_fixed_expression(span):
                return span
    return None


def raw_detector_hit(patterns: list[str] | None, text: str | None) -> bool:
    """Does any detector match anywhere, fixed expressions included?"""

    folded = fold_apostrophes(text)
    for pattern in patterns or []:
        try:
            if re.search(pattern, folded, re.IGNORECASE):
                return True
        except re.error:
            continue
    return False


def _word_bounds(text: str, start: int, end: int) -> tuple[int, int]:
    """Widen ``[start, end)`` to whole words: never mark half of «école»."""

    while start > 0 and (text[start - 1].isalpha() or text[start - 1] in "'-"):
        start -= 1
    while end < len(text) and (text[end].isalpha() or text[end] == "-"):
        end += 1
    return start, end


def _is_noun_phrase(span: str) -> bool:
    """A determiner followed by a word that can be the noun (or its adjective)."""

    words = [word.strip(".,;:!?«»\"()") for word in fold_apostrophes(span).casefold().split()]
    words = [word for word in words if word]
    for index, word in enumerate(words):
        if word.startswith("l'") and len(word) > 3:
            return True
        if word in _DETERMINERS and index + 1 < len(words) and words[index + 1] not in _NOT_A_NOUN:
            return True
    return False


def rule_span(brief: dict[str, Any], text: str | None) -> tuple[int, int] | None:
    """Where ``text`` uses the unit, as a trustworthy ``(start, end)``, or ``None``.

    Offsets are into ``fold_apostrophes(text)`` (same length as ``text``). The
    detector's match, widened to whole words, and — for a noun-phrase unit
    (articles, gender, agreement) — only when it is a determiner and its noun:
    a card may only mark what its rule explains.
    """

    patterns = list(brief.get("detectors") or [])
    if not patterns or not text:
        return None
    folded = fold_apostrophes(text)
    for pattern in patterns:
        try:
            matches = list(re.finditer(pattern, folded, re.IGNORECASE))
        except re.error:
            continue
        for match in matches:
            span = match.group(0)
            if not span.strip() or _is_fixed_expression(span):
                continue
            start = match.start() + (len(span) - len(span.lstrip()))
            end = match.end() - (len(span) - len(span.rstrip()))
            start, end = _word_bounds(folded, start, end)
            if brief.get("noun_phrase") and not _is_noun_phrase(folded[start:end]):
                continue
            return start, end
    return None


def mentions_rule(brief: dict[str, Any], text: str | None) -> bool:
    """Could a learner read ``text`` as using the rule? (the distractor test)

    Any detector hit at all, fixed expressions included; for a noun-phrase unit
    any determiner with a word after it, since every such phrase shows gender.
    """

    if raw_detector_hit(list(brief.get("detectors") or []), text):
        return True
    return bool(brief.get("noun_phrase")) and bool(_NOUN_PHRASE.search(fold_apostrophes(text)))


def _localized(table: dict[str, str], language: str) -> str:
    return table.get(language) or table["en"]


def _digest(*parts: Any) -> str:
    return hashlib.sha256("|".join(str(part) for part in parts).encode()).hexdigest()


def _fold(value: str | None) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[’ʼ‘]", "'", text)
    return " ".join(re.sub(r"[^0-9a-z'\s]+", " ", text).split())


def _words(sentence: str) -> list[str]:
    """Whitespace words, a free-standing « ? ! : ; » kept on the word before it."""

    words: list[str] = []
    for word in str(sentence or "").split():
        if words and word in {"?", "!", ":", ";", "»"}:
            words[-1] = f"{words[-1]} {word}"
        elif word.strip():
            words.append(word)
    return words


def grammar_target(brief: dict[str, Any]) -> TargetRef:
    """The unit as a journey target (a concept, not a phrase to recall)."""

    return TargetRef(
        kind=TargetKind.GRAMMAR,
        id=str(brief["concept_id"]),
        label_fr=str(brief.get("title_fr") or ""),
        label_native=str(brief.get("title_native") or "") or None,
        concept_title=True,
    )


def _hint(brief: dict[str, Any], language: str | None = None) -> str | None:
    """The unit's one-line rule: the catalogue's, else the card's in ``language``."""

    short = str(brief.get("rule_short_native") or "").strip()
    if short:
        return short
    card = brief.get("rule_card")
    rule = card.get("rule") if isinstance(card, dict) else None
    if isinstance(rule, dict) and language:
        return str(rule.get(language) or rule.get("en") or "").strip() or None
    return None


def _usable(sentence: str) -> bool:
    return 2 <= len(_words(sentence)) <= MAX_ITEM_WORDS


def form_sentences(brief: dict[str, Any], sentences: list[str]) -> list[str]:
    """Sentences that use the unit: today's scene first, then the catalogue's."""

    patterns = list(brief.get("detectors") or [])
    found: list[str] = []
    for sentence in [*sentences, *(brief.get("examples") or [])]:
        text = plain(sentence)
        if not _usable(text) or _fold(text) in {_fold(item) for item in found}:
            continue
        if patterns and rule_span(brief, text) is None:
            continue
        found.append(text)
    if not patterns:
        # No detector: the catalogue's own examples are the unit by definition.
        found = [plain(item) for item in brief.get("examples") or [] if _usable(plain(item))]
    return found


def scene_rule_card(
    brief: dict[str, Any],
    sentences: list[str],
    *,
    speakers: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    """The unit's card, its headline taken from today's scene when a line uses it.

    Only a trustworthy use (:func:`rule_span`) replaces the authored example,
    and only with what the scene knows: the line's speaker (``speakers`` maps a
    folded sentence, :func:`_fold`, to the character who said it) and no
    translation — the scene has none, and the authored one belongs to the
    authored sentence. An authored example said by a character is only
    replaced by a character's line: narration never takes a face away.
    """

    card = brief.get("rule_card")
    if not isinstance(card, dict):
        return None
    card = dict(card)
    speakers = speakers or {}
    for sentence in sentences:
        text = plain(sentence)
        if not _usable(text):
            continue
        bounds = rule_span(brief, text)
        if bounds is None:
            continue
        speaker = speakers.get(_fold(text))
        if card.get("speaker") and not speaker:
            continue
        start, end = bounds
        card["example"] = {"fr": f"{text[:start]}[{text[start:end]}]{text[end:]}"}
        card["speaker"] = speaker or None
        card["from_scene"] = True
        break
    return card


def recognise_item(
    brief: dict[str, Any],
    *,
    sentences: list[str],
    language: ControlLanguage,
    optional: bool = False,
) -> RecallTask | None:
    """«Which sentence follows today's rule?» — or ``None`` when it would be ambiguous.

    Exactly one option may use the rule: the answer is a trustworthy use
    (:func:`rule_span`), and every distractor is a sentence no one could read
    as using it (:func:`mentions_rule`: no detector hit at all, and for a
    noun-phrase unit no noun phrase). A scene without such sentences gets no
    recognise item: the Essai starts with «choose».
    """

    patterns = list(brief.get("detectors") or [])
    if not patterns:
        return None
    uses = form_sentences(brief, sentences)
    if not uses:
        return None
    answer = uses[0]
    others: list[str] = []
    for sentence in sentences:
        text = plain(sentence)
        if (
            _usable(text)
            and not mentions_rule(brief, text)
            and _fold(text) not in {_fold(item) for item in [answer, *others]}
        ):
            others.append(text)
    if not others:
        return None
    others.sort(key=lambda text: _digest(brief["concept_id"], "recognise", text))
    target = grammar_target(brief)
    texts = [answer, *others[:2]]
    options = [{"id": "opt_" + _digest(target.id, "r", text)[:8], "text_fr": text} for text in texts]
    options.sort(key=lambda option: _digest(target.id, "order", option["text_fr"]))
    return RecallTask(
        task_type="choice",
        instruction_native=_localized(_RECOGNISE, language),
        prompt_fr=None,
        options=options,
        target=target,
        optional=optional,
        correct_option_id="opt_" + _digest(target.id, "r", answer)[:8],
        accepted_answers=[answer],
        hint_native=_hint(brief, language),
        translation_native=None,
        solution_fr=answer,
        estimated_seconds=0,
    )


def choose_item(
    brief: dict[str, Any],
    *,
    language: ControlLanguage,
    pair: dict[str, str] | None = None,
    optional: bool = False,
) -> RecallTask | None:
    pairs = list(brief.get("contrast_pairs") or [])
    pair = pair or (pairs[0] if pairs else None)
    if not pair:
        return None
    right, wrong = plain(pair.get("right")), plain(pair.get("wrong"))
    if not right or not wrong or _fold(right) == _fold(wrong):
        return None
    target = grammar_target(brief)
    options = [
        {"id": "opt_" + _digest(target.id, "c", text)[:8], "text_fr": text} for text in (right, wrong)
    ]
    options.sort(key=lambda option: _digest(target.id, "order", option["text_fr"]))
    return RecallTask(
        task_type="choice",
        instruction_native=_localized(_CHOOSE, language),
        prompt_fr=None,
        options=options,
        target=target,
        optional=optional,
        correct_option_id="opt_" + _digest(target.id, "c", right)[:8],
        accepted_answers=[right],
        hint_native=_hint(brief, language),
        translation_native=None,
        solution_fr=right,
        estimated_seconds=0,
    )


def contrast_swaps(brief: dict[str, Any]) -> list[tuple[str, str]]:
    """``(wrong word, right word)`` pairs where a ✗/✓ sentence differs by one word."""

    swaps: list[tuple[str, str]] = []
    for pair in brief.get("contrast_pairs") or []:
        wrong = [word.strip(".,;:!?") for word in _words(plain(pair.get("wrong")))]
        right = [word.strip(".,;:!?") for word in _words(plain(pair.get("right")))]
        if len(wrong) != len(right):
            continue
        diffs = [(w, r) for w, r in zip(wrong, right, strict=True) if _fold(w) != _fold(r)]
        if len(diffs) == 1 and all(diffs[0]):
            swaps.append(diffs[0])
    return swaps


def build_item(
    brief: dict[str, Any],
    *,
    sentences: list[str],
    language: ControlLanguage,
    avoid: list[str] | None = None,
    optional: bool = False,
) -> RecallTask | None:
    avoid_folded = {_fold(item) for item in avoid or []}
    candidates = [
        text for text in form_sentences(brief, sentences) if 3 <= len(_words(text)) <= 10
    ]
    if not candidates:
        return None
    swaps = contrast_swaps(brief)

    def spare_chips(text: str) -> list[str]:
        """The ✗ counterpart of a ✓ word the sentence uses — and nothing that
        could stand in the sentence as well (so the build has one answer)."""

        words = {_fold(word.strip(".,;:!?")) for word in _words(text)}
        spare: list[str] = []
        for wrong, right in swaps:
            if _fold(right) in words and _fold(wrong) not in words and wrong not in spare:
                spare.append(wrong)
        return spare[:2]

    # A sentence where the contrast bites first, then one not shown yet, then
    # the shortest: the quickest honest build.
    sentence = sorted(
        candidates,
        key=lambda text: (
            not spare_chips(text),
            _fold(text) in avoid_folded,
            len(_words(text)),
            candidates.index(text),
        ),
    )[0]
    tokens = _words(sentence)
    target = grammar_target(brief)
    extras = spare_chips(sentence)
    extras = [word for word in extras if word][:2]
    answer = [
        {"id": "tile_" + _digest(target.id, "b", index, token)[:8], "text_fr": token}
        for index, token in enumerate(tokens)
    ]
    correct = [tile["id"] for tile in answer]
    chips = [
        *answer,
        *({"id": "chip_" + _digest(target.id, "x", word)[:8], "text_fr": word} for word in extras),
    ]
    if len({chip["id"] for chip in chips}) != len(chips):
        return None
    shown = sorted(chips, key=lambda chip: _digest(target.id, "bank", chip["id"]))
    if [chip["id"] for chip in shown] == correct and len(shown) > 1:
        shown = shown[1:] + shown[:1]
    return RecallTask(
        task_type="word_bank" if extras else "tiles",
        instruction_native=_localized(_BUILD_BANK if extras else _BUILD_TILES, language),
        prompt_fr=None,
        options=shown,
        target=target,
        optional=optional,
        correct_tile_order=correct,
        accepted_answers=[sentence],
        hint_native=_localized(_FIRST_WORD_HINT, language).format(word=tokens[0]),
        translation_native=None,
        solution_fr=sentence,
        estimated_seconds=0,
    )


def transform_item(
    brief: dict[str, Any],
    *,
    language: ControlLanguage,
    prefer_second_pair: bool = False,
    optional: bool = False,
) -> RecallTask | None:
    pairs = list(brief.get("contrast_pairs") or [])
    if not pairs:
        return None
    pair = pairs[1] if prefer_second_pair and len(pairs) > 1 else pairs[0]
    right, wrong = plain(pair.get("right")), plain(pair.get("wrong"))
    if not right or not wrong or _fold(right) == _fold(wrong):
        return None
    target = grammar_target(brief)
    return RecallTask(
        task_type="transform",
        instruction_native=_localized(_TRANSFORM, language),
        prompt_fr=wrong,
        options=[],
        target=target,
        optional=optional,
        accepted_answers=[right],
        hint_native=_hint(brief, language),
        translation_native=None,
        solution_fr=right,
        estimated_seconds=0,
    )


def guided_items(
    brief: dict[str, Any], *, sentences: list[str], language: ControlLanguage
) -> list[RecallTask]:
    """The introduction day's Essai: recognise → choose → build → transform."""

    items: list[RecallTask] = []
    recognise = recognise_item(brief, sentences=sentences, language=language)
    if recognise is not None:
        items.append(recognise)
    choose = choose_item(brief, language=language)
    if choose is not None:
        items.append(choose)
    shown = [str(recognise.solution_fr)] if recognise is not None else []
    build = build_item(brief, sentences=sentences, language=language, avoid=shown)
    if build is not None:
        items.append(build)
    transform = transform_item(brief, language=language, prefer_second_pair=True)
    if transform is not None:
        items.append(transform)
    return items


def review_band(stability: float | None) -> str:
    """``low`` · ``medium`` · ``high`` — the Rappel format band for a stability."""

    value = float(stability or 0.0)
    if value < LOW_STABILITY_DAYS:
        return "low"
    if value < REEMPLOI_STABILITY_DAYS:
        return "medium"
    return "high"


def review_item(
    brief: dict[str, Any],
    *,
    sentences: list[str],
    language: ControlLanguage,
    day_key: str,
) -> RecallTask | None:
    """One Rappel item for a due unit, its format scaled by stability.

    ``None`` for a strong unit (it is asked for in the reply instead) or when
    no format can be posed. Which of the band's two formats comes first turns
    with the day, so a unit is not asked the same way twice running.
    """

    band = review_band(brief.get("stability"))
    if band == "high":
        return None
    if band == "low":
        builders = [
            lambda: choose_item(brief, language=language),
            lambda: recognise_item(brief, sentences=sentences, language=language),
        ]
    else:
        builders = [
            lambda: transform_item(brief, language=language),
            lambda: build_item(brief, sentences=sentences, language=language),
        ]
    if int(_digest(brief.get("concept_id"), day_key)[:2], 16) % 2:
        builders.reverse()
    fallbacks = [
        lambda: choose_item(brief, language=language),
        lambda: recognise_item(brief, sentences=sentences, language=language),
    ]
    for build in [*builders, *fallbacks]:
        task = build()
        if task is not None:
            return task
    return None


__all__ = [
    "FIXED_EXPRESSIONS",
    "detector_span",
    "fold_apostrophes",
    "mentions_rule",
    "raw_detector_hit",
    "rule_span",
    "plain",
    "LOW_STABILITY_DAYS",
    "REEMPLOI_STABILITY_DAYS",
    "build_item",
    "choose_item",
    "form_sentences",
    "grammar_target",
    "guided_items",
    "recognise_item",
    "review_band",
    "review_item",
    "scene_rule_card",
    "transform_item",
]
