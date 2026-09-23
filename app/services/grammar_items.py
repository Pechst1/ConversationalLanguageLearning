"""WP-L4 — grammar items, posed deterministically from a unit brief.

The journey planner is a pure function, so everything here is too: the input
is a unit brief (:func:`app.services.grammar_units.unit_brief`, carried in a
candidate's ``metadata["grammar_brief"]`` or as the day's introduction) and the
sentences of today's scene; the output is ordinary :class:`RecallTask` objects
in formats every client already renders (``choice``, ``word_bank`` / ``tiles``,
``transform``). No model call, no invented French: every sentence is the
catalogue's, the authored card's, or the scene's.

The four steps of the Essai (§2.4), weakest first:

* **recognise** — «which sentence uses this rule?»: one sentence the unit's
  detector recognises (the scene's first, else a catalogue example) among
  scene sentences it does not recognise;
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

_RECOGNISE: dict[str, str] = {
    "en": "Which sentence uses this rule: {title}?",
    "de": "Welcher Satz nutzt diese Regel: {title}?",
    "fr": "Quelle phrase utilise cette règle : {title} ?",
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


def detector_span(patterns: list[str] | None, text: str | None) -> str | None:
    """The first span of ``text`` a regex detector recognises, or ``None``.

    Apostrophes are folded first (iOS types U+2019; the patterns use ``'``).
    """

    folded = fold_apostrophes(text)
    for pattern in patterns or []:
        try:
            match = re.search(pattern, folded, re.IGNORECASE)
        except re.error:
            continue
        if match and match.group(0).strip():
            return match.group(0).strip()
    return None


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


def _hint(brief: dict[str, Any]) -> str | None:
    return str(brief.get("rule_short_native") or "").strip() or None


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
        if patterns and detector_span(patterns, text) is None:
            continue
        found.append(text)
    if not patterns:
        # No detector: the catalogue's own examples are the unit by definition.
        found = [plain(item) for item in brief.get("examples") or [] if _usable(plain(item))]
    return found


def scene_rule_card(brief: dict[str, Any], sentences: list[str]) -> dict[str, Any] | None:
    """The unit's card, its headline taken from today's scene when a line uses it."""

    card = brief.get("rule_card")
    if not isinstance(card, dict):
        return None
    card = dict(card)
    patterns = list(brief.get("detectors") or [])
    for sentence in sentences:
        text = plain(sentence)
        span = detector_span(patterns, text) if patterns else None
        if not span or not _usable(text):
            continue
        folded = text.replace("’", "'")
        index = folded.casefold().find(span.casefold())
        if index < 0:
            continue
        card["example"] = {"fr": f"{text[:index]}[{text[index:index + len(span)]}]{text[index + len(span):]}"}
        card["speaker"] = None
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
            and detector_span(patterns, text) is None
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
        instruction_native=_localized(_RECOGNISE, language).format(
            title=brief.get("title_native") or brief.get("title_fr") or ""
        ),
        prompt_fr=None,
        options=options,
        target=target,
        optional=optional,
        correct_option_id="opt_" + _digest(target.id, "r", answer)[:8],
        accepted_answers=[answer],
        hint_native=_hint(brief),
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
        hint_native=_hint(brief),
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
        hint_native=_hint(brief),
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
    "detector_span",
    "fold_apostrophes",
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
