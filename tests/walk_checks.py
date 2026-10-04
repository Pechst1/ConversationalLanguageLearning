"""EXERCISE-QA 2026-10-03 — the automated reader of the learner walk's transcripts.

Every check returns human-readable problems (``"<persona> day N [step] …"``);
:func:`run_all` concatenates them. The checks read only what the learner is shown
(the public prompts and the attempt results), plus the stored answer key where a
check is *about* the key (a miss must show it).

The checks are deliberately strict about what the product authors and lenient
about what the walk's scripted story provider writes: the fake director's
English placeholder prose (``tests/test_living_story_longitudinal.OBJECTIVES`` and
friends) is not product content, so strings it authored are skipped by
:func:`_is_fake`.
"""
from __future__ import annotations

import json
import re
from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# What the walk's fake story provider writes (never judged)
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _fake_strings() -> frozenset[str]:
    from tests import test_living_story_longitudinal as longitudinal

    strings = {
        *longitudinal.OBJECTIVES,
        *longitudinal.PREMISES,
        "A day between two tentpoles.",
        "Any sincere answer.",
        "Say what you think.",
        "What do you think?",
        "Got a minute?",
        "So, what do we do?",
        "You answered Romy.",
        "The day ends.",
        "The canal in the rain.",
        "Two friends at the zinc.",
        "A glass.",
        "The friend turns to you.",
        "Romy note votre réponse.",
        "Tu en penses quoi ?",
        "Tu as une minute ?",
        "Alors, on fait quoi ?",
        "Il pleut sur le canal.",
        "Un silence.",
        "Merci ! On s'organise pour samedi.",
        "Je reste encore un peu.",
        "D'accord.",
        "La journée se termine.",
        "Vous avez parlé.",
    }
    from tests.learner_walk import B1_MOVES

    # learner_walk.fit_level: the walk director's B1+ objectives.
    strings |= set(B1_MOVES.values())
    return frozenset(" ".join(text.split()) for text in strings)


def _is_fake(text: str) -> bool:
    folded = " ".join(str(text or "").split())
    if not folded:
        return False
    if folded in _fake_strings():
        return True
    return any(fake in folded for fake in _fake_strings() if len(fake) > 12) or folded.startswith("You answered on day")


# ---------------------------------------------------------------------------
# Walking a transcript
# ---------------------------------------------------------------------------

#: Public fields written in the learner's language (native or chrome).
NATIVE_KEYS = frozenset(
    {
        "instruction_native", "objective_native", "hint_native", "note_native", "goal_native",
        "summary_native", "setup_native", "title_native", "register_reason_native",
        "translation_native", "label_native", "content_native", "rule_short_native",
        "next_task_native", "next_hint_native", "next_translation_native", "alt_native",
    }
)
#: Fields that are always the learner's *native* language (meanings, glosses).
MEANING_KEYS = frozenset({"translation_native", "label_native", "text_native"})


def _iter_strings(node: Any, path: str = "") -> Iterator[tuple[str, str, str]]:
    """``(path, key, text)`` for every string in a JSON tree."""

    if isinstance(node, dict):
        for key, value in node.items():
            sub = f"{path}.{key}" if path else str(key)
            if isinstance(value, str):
                yield sub, str(key), value
            elif isinstance(value, list) and all(isinstance(item, str) for item in value):
                for index, item in enumerate(value):
                    yield f"{sub}[{index}]", str(key), item
            else:
                yield from _iter_strings(value, sub)
    elif isinstance(node, list):
        for index, item in enumerate(node):
            yield from _iter_strings(item, f"{path}[{index}]")


def _shown(event: dict[str, Any]) -> list[dict[str, Any]]:
    """What the learner reads in this event: the prompt, then the verdict."""

    shown = [event["step"].get("prompt") or {}]
    result = event.get("result") or {}
    if result:
        shown.append({key: result.get(key) for key in ("correction", "character_reply_fr", "next_turn")})
    return shown


def _label(transcript: dict[str, Any], index: int, event: dict[str, Any]) -> str:
    step = event["step"]
    task = (step.get("prompt") or {}).get("task_type")
    kind = f"{step.get('kind')}:{task}" if task else str(step.get("kind"))
    return f"{transcript['persona']} {transcript['quality']} day {transcript['day']} #{index} [{kind}]"


def _band(cefr: str) -> int:
    return {"A1": 1, "A2": 2, "B1": 3, "B2": 4, "C1": 5, "C2": 6}.get(str(cefr or "")[:2].upper(), 1)


def _chrome(transcript: dict[str, Any]) -> str:
    """The language the app's own words must be in (``chrome_language``)."""

    return "fr" if _band(transcript["cefr"]) >= 3 else str(transcript["native"])


# ---------------------------------------------------------------------------
# 1. Language leaks
# ---------------------------------------------------------------------------

_QUOTED = re.compile(r"„[^“”]*[“”]|“[^”]*”|\"[^\"]*\"|«[^»]*»|‹[^›]*›")
_WORD = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿœŒßäöüÄÖÜ']+")
_MARKERS = {
    "en": frozenset(
        "the you your what which is are this that with of say write does don't word words sentence "
        "build tap correct right wrong answer meaning means rebuild complete fix someone".split()
    ),
    "de": frozenset(
        "der die das und ist du nicht ein eine zu mit was sag welche welcher wort wörter satz bau "
        "oben richtig deine dein auf wie heißt heißen bedeutet ergänze bring tippe hier achte als auch oder für".split()
    ),
    "fr": frozenset(
        "le la les est et vous tu une des que pas dans pour avec ce cette qui quel quelle "
        "phrase mot mots complétez construisez reconstruisez écrivez".split()
    ),
}


def detect_language(text: str) -> str | None:
    """``en``/``de``/``fr`` by function words outside quotes, or ``None`` when unsure."""

    bare = _QUOTED.sub(" ", str(text or ""))
    words = [word.lower().strip("'") for word in _WORD.findall(bare)]
    if len(words) < 3:
        return None
    scores = {lang: sum(word in markers for word in words) for lang, markers in _MARKERS.items()}
    best = max(scores, key=lambda lang: scores[lang])
    ranked = sorted(scores.values(), reverse=True)
    if ranked[0] < 2 or ranked[0] == ranked[1]:
        return None
    return best


def _has_markers(text: str, language: str) -> bool:
    """Does ``text`` hold at least one function word of ``language`` (outside quotes)?"""

    bare = _QUOTED.sub(" ", str(text or ""))
    return any(word.lower().strip("'") in _MARKERS.get(language, ()) for word in _WORD.findall(bare))


def check_language(transcript: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    native = str(transcript["native"])
    chrome = _chrome(transcript)
    foreign = {"de": "en", "en": "de"}.get(native)
    for index, event in enumerate(transcript["events"]):
        for shown in _shown(event):
            for path, key, text in _iter_strings(shown):
                if not (key in NATIVE_KEYS or key in MEANING_KEYS or key == "notes_native"):
                    continue
                if _is_fake(text):
                    continue
                lang = detect_language(text)
                if lang is None:
                    continue
                if key == "title_native" and ":" in text:
                    # «Le plus, le moins: am meisten, am wenigsten» — the French form, then its gloss.
                    lang = detect_language(text.split(":", 1)[1])
                    if lang is None:
                        continue
                if lang == foreign:
                    problems.append(f"{_label(transcript, index, event)} {path}: {lang} text for a {native} learner: {text!r}")
                elif key not in MEANING_KEYS and lang not in {chrome, native} and not _has_markers(text, chrome):
                    problems.append(f"{_label(transcript, index, event)} {path}: {lang} where {chrome} is expected: {text!r}")
    return problems


# ---------------------------------------------------------------------------
# 2. Translation ↔ French
# ---------------------------------------------------------------------------

_DIGITS = re.compile(r"\d+")


@lru_cache(maxsize=1)
def cast_names() -> frozenset[str]:
    """First names and surnames of the season's cast («Gus», «Lila», «Marchand» …)."""

    data = json.loads((ROOT / "app/data/season/s1/season.json").read_text(encoding="utf-8"))
    names: set[str] = set()
    skip = {"de", "M.", "Mme", "Maître", "L'employée", "«", "»"}
    for member in data.get("cast") or []:
        for token in re.split(r"[\s«»]+", str(member.get("name") or "")):
            token = token.strip()
            if token and token not in skip and token[:1].isupper() and len(token) > 2:
                names.add(token)
    return frozenset(names)


def _pairs(node: Any) -> Iterator[tuple[str, str, str]]:
    """``(path, french, translation)`` pairs a learner reads side by side."""

    stack: list[tuple[str, Any]] = [("", node)]
    while stack:
        path, item = stack.pop()
        if isinstance(item, dict):
            french = item.get("text_fr") or item.get("setup_fr") or item.get("prompt_fr")
            meaning = item.get("text_native") or item.get("setup_native") or item.get("translation_native")
            if isinstance(french, str) and isinstance(meaning, str) and french.strip() and meaning.strip():
                yield path, french, meaning
            for key, value in item.items():
                if isinstance(value, (dict, list)):
                    stack.append((f"{path}.{key}" if path else key, value))
        elif isinstance(item, list):
            for index, value in enumerate(item):
                stack.append((f"{path}[{index}]", value))


def check_translations(transcript: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    names = cast_names()
    chrome = _chrome(transcript)
    seen: dict[str, str] = {}
    for index, event in enumerate(transcript["events"]):
        for path, french, meaning in _pairs(event["step"].get("prompt") or {}):
            if _is_fake(meaning) or _is_fake(french):
                continue
            label = f"{_label(transcript, index, event)} {path}"
            if chrome != "fr" and " ".join(french.split()) == " ".join(meaning.split()) and len(french.split()) > 5:
                problems.append(f"{label}: the translation is the French itself: {french!r}")
            for name in names:
                in_fr = re.search(rf"\b{re.escape(name)}\b", french) is not None
                in_tr = re.search(rf"\b{re.escape(name)}\b", meaning) is not None
                if in_fr != in_tr:
                    problems.append(f"{label}: «{name}» is in only one of {french!r} / {meaning!r}")
            if sorted(_DIGITS.findall(french)) != sorted(_DIGITS.findall(meaning)):
                problems.append(f"{label}: numbers differ: {french!r} / {meaning!r}")
            key = " ".join(meaning.split()).casefold()
            other = seen.get(key)
            if other is not None and _fold(other) != _fold(french) and len(key.split()) > 2:
                problems.append(f"{label}: one translation for two French lines: {other!r} and {french!r} → {meaning!r}")
            seen.setdefault(key, french)
    return problems


# ---------------------------------------------------------------------------
# 3. Duplicates in a day, and an answer printed one item earlier
# ---------------------------------------------------------------------------


def _fold(text: Any) -> str:
    from app.services.answer_acceptance import fold_all

    return fold_all(text)


def _item_face(prompt: dict[str, Any], *, cards: bool = True) -> str:
    options = sorted(_fold(option.get("text_fr")) for option in prompt.get("options") or []) if cards else []
    return " | ".join(
        [
            str(prompt.get("task_type") or ""),
            _fold(prompt.get("instruction_native")),
            _fold(prompt.get("goal_native")),
            _fold(prompt.get("prompt_fr")),
            _fold(prompt.get("source_fr")),
            ",".join(options),
        ]
    )


def _visible_french(prompt: dict[str, Any]) -> str:
    parts = [prompt.get("prompt_fr"), prompt.get("source_fr")]
    parts.extend(option.get("text_fr") for option in prompt.get("options") or [] if option.get("side") != "native")
    return " ".join(_fold(part) for part in parts if part)


#: Formats that ask the learner to *produce* French: retrieval, not recognition.
PRODUCTION_FORMATS = frozenset({"short_answer", "transform", "dictation"})


def check_duplicates(transcript: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    faces: list[tuple[int, str]] = []
    faces_bare: dict[int, str] = {}
    previous: dict[str, Any] | None = None
    previous_target: str | None = None
    previous_index = -9
    for index, event in enumerate(transcript["events"]):
        if event["step"].get("kind") != "recall":
            continue
        target = (event.get("key") or {}).get("target") or {}
        target_id = f"{target.get('kind')}:{target.get('id')}" if target else None
        prompt = event["step"].get("prompt") or {}
        face = _item_face(prompt)
        for other_index, other in faces:
            if face == other:
                problems.append(f"{_label(transcript, index, event)}: the same item as #{other_index}")
                break
            stem = _fold(prompt.get("prompt_fr") or prompt.get("source_fr") or prompt.get("goal_native"))
            if stem and _item_face(prompt, cards=False) == faces_bare[other_index]:
                problems.append(f"{_label(transcript, index, event)}: nearly the same item as #{other_index}")
                break
        faces.append((index, face))
        faces_bare[index] = _item_face(prompt, cards=False)
        accepted = [answer for answer in (event.get("key") or {}).get("accepted_answers") or [] if answer]
        same_target = target_id is not None and target_id == previous_target and previous_index == index - 1
        if previous is not None and same_target and prompt.get("task_type") in PRODUCTION_FORMATS and accepted:
            shown = _visible_french(previous)
            for answer in accepted[:1]:
                folded = _fold(answer)
                if len(folded) >= 3 and re.search(rf"(?:^|\s){re.escape(folded)}(?:$|\s)", shown):
                    problems.append(
                        f"{_label(transcript, index, event)}: asks to produce «{answer}», printed by the item just before"
                    )
        previous = prompt
        previous_target = target_id
        previous_index = index
    return problems


# ---------------------------------------------------------------------------
# 4. Level fit
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _lexicon_bands() -> dict[str, int]:
    from app.services.answer_acceptance import strip_accents

    data = json.loads((ROOT / "app/data/lexical/fr_core_lexicon.json").read_text(encoding="utf-8"))
    del strip_accents
    bands: dict[str, int] = {}

    def keep(word: str, band: int) -> None:
        bands[word] = min(band, bands.get(word, band))

    lemmas = data.get("lemmas") or {}
    for lemma, entry in lemmas.items():
        if isinstance(entry, dict) and " " not in lemma:
            keep(lemma.casefold(), _band(entry.get("band")))
    lemma_band = dict(bands)
    for form, lemma in (data.get("forms") or {}).items():
        band = lemma_band.get(str(lemma).casefold())
        if band is not None:
            keep(form.casefold(), band)
    return bands


def item_words_above(text: str, cefr: str, *, slack: int = 1) -> list[str]:
    """Words of ``text`` whose lexicon band is more than ``slack`` above ``cefr``."""

    from app.services.answer_acceptance import fold_typography

    bands = _lexicon_bands()
    limit = _band(cefr) + slack
    words: list[str] = []
    for raw in re.findall(r"[^\W\d_]+(?:['-][^\W\d_]+)*", str(text or "")):
        if raw[:1].isupper() and raw in cast_names():
            continue
        whole = fold_typography(raw).casefold()
        token = whole.split("'")[-1]
        # «d'abord», «aujourd'hui» are words of their own, not «abord», «hui».
        band = bands.get(whole, bands.get(token))
        # A participle («arrivé») is its verb's word, whatever its own adjective entry says.
        for ending, infinitive in (("ées", "er"), ("és", "er"), ("ée", "er"), ("é", "er")):
            if band is not None and token.endswith(ending):
                verb = bands.get(token[: -len(ending)] + infinitive)
                band = min(band, verb) if verb is not None else band
                break
        if band is not None and band > limit:
            words.append(raw)
    return words


def check_level(transcript: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    for index, event in enumerate(transcript["events"]):
        if event["step"].get("kind") != "recall":
            continue
        accepted = " ".join((event.get("key") or {}).get("accepted_answers") or [])
        if _is_fake(accepted) or any(_is_fake(line) and line[:20] in accepted for line in _fake_strings()):
            continue
        above = item_words_above(accepted, transcript["cefr"])
        if above:
            problems.append(
                f"{_label(transcript, index, event)}: answer uses words above {transcript['cefr']}: {sorted(set(above))}"
            )
    return problems


# ---------------------------------------------------------------------------
# 5. A miss shows what was expected
# ---------------------------------------------------------------------------

#: Picks the client grades and reveals from the hashed key (``lib/answer-key.ts``).
REVEALED_BY_KEY = frozenset({"choice", "classify", "listen_tap", "who_said", "match_pairs"})


def check_feedback(transcript: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    for index, event in enumerate(transcript["events"]):
        if event["step"].get("kind") != "recall" or "result" not in event:
            continue
        result = event["result"]
        if result.get("task_outcome") in ("met", None):
            continue
        prompt = event["step"].get("prompt") or {}
        task_type = prompt.get("task_type")
        correction = result.get("correction") or {}
        if task_type in REVEALED_BY_KEY:
            if not prompt.get("answer_key"):
                problems.append(f"{_label(transcript, index, event)}: a missed pick with no key to reveal the answer")
            continue
        if not str(correction.get("corrected_fr") or "").strip():
            problems.append(f"{_label(transcript, index, event)}: a miss without the expected answer")
        elif not (correction.get("notes_native") or correction.get("note_native")):
            problems.append(f"{_label(transcript, index, event)}: a miss without a why")
    return problems


# ---------------------------------------------------------------------------
# 6. Empty strings, placeholders, machine keys
# ---------------------------------------------------------------------------

_PLACEHOLDER = re.compile(r"(?<![\w\](])\{[a-z_]{2,}\}(?!\w)|\bNone\b|\bnull\b|\bundefined\b|\[votre|\bTODO\b|Wort/Wörter|word\(s\)|mot\(s\)")
_MACHINE_KEY = re.compile(r"^[a-z]+(?:_[a-z0-9]+){1,}$")
#: A snake_case id inside a sentence («Bring den Satz von clerk_2 …»).
_MACHINE_TOKEN = re.compile(r"(?<![\w/.])[a-z]+(?:_[a-z0-9]+)+(?![\w/.])")
#: Keys whose value is a machine value by design (ids, enums, urls).
_MACHINE_FIELDS = frozenset(
    {
        "id", "kind", "task_type", "character_id", "speaker_id", "outcome_key", "image_url", "audio_url",
        "character_line_audio_url", "salt", "digests", "side", "input_modes", "help_available", "status",
        "task_outcome", "reply_source", "evidence_ref", "desk", "unit_id", "external_id", "location_id",
        "concept_id", "scene_example_speaker", "speaker", "shape", "mood", "kind_key", "image_status",
    }
)
#: Text a learner reads that must never be empty when present.
_REQUIRED_TEXT = ("instruction_native",)


def check_strings(transcript: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    for index, event in enumerate(transcript["events"]):
        for shown in _shown(event):
            for path, key, text in _iter_strings(shown):
                if key in _MACHINE_FIELDS or key.endswith(("_id", "_url", "_key")):
                    continue
                if _PLACEHOLDER.search(text) and not _markup_or_word(path, text, transcript):
                    problems.append(f"{_label(transcript, index, event)} {path}: placeholder or plural slash: {text!r}")
                if _MACHINE_KEY.match(text.strip()) and key not in {"mode", "register"}:
                    problems.append(f"{_label(transcript, index, event)} {path}: machine key shown: {text!r}")
                elif (key in NATIVE_KEYS or key.endswith("_fr")) and _MACHINE_TOKEN.search(text):
                    problems.append(f"{_label(transcript, index, event)} {path}: machine key inside text: {text!r}")
        prompt = event["step"].get("prompt") or {}
        if event["step"].get("kind") == "recall":
            for key in _REQUIRED_TEXT:
                if not str(prompt.get(key) or "").strip():
                    problems.append(f"{_label(transcript, index, event)}: empty {key}")
            for option in prompt.get("options") or []:
                if not str(option.get("text_fr") or "").strip():
                    problems.append(f"{_label(transcript, index, event)}: an empty option")
            cloze = str(prompt.get("prompt_fr") or "")
            if "___" in cloze and len(re.findall(r"\w+", cloze.replace("___", ""))) < 2:
                problems.append(f"{_label(transcript, index, event)}: a gap with no sentence around it: {cloze!r}")
    return problems


def _markup_or_word(path: str, text: str, transcript: dict[str, Any]) -> bool:
    """Not a placeholder: a rule card's ``[x]`` markup («[votre] sac»), or «null»,
    which is German for «zéro»."""

    if "rule_card" in path:
        return True
    return text.strip().casefold() == "null" and str(transcript.get("native")) == "de"


# ---------------------------------------------------------------------------
# 7. Story events the learner has not seen
# ---------------------------------------------------------------------------


def _names_in(text: str) -> set[str]:
    return {name for name in cast_names() if re.search(rf"\b{re.escape(name)}\b", text or "")}


def _story_text(event: dict[str, Any]) -> str:
    """Everything the story itself says in this step (scene, reply, ending)."""

    texts = [text for _path, _key, text in _iter_strings(event["step"].get("prompt") or {})]
    result = event.get("result") or {}
    texts.extend(text for _path, _key, text in _iter_strings({"r": result.get("character_reply_fr"), "l": result.get("character_lines"), "n": result.get("next_turn")}))
    return " ".join(texts)


def check_spoilers(transcript: dict[str, Any]) -> list[str]:
    """An item (or a rule card) names a cast member the learner has not met yet."""

    problems: list[str] = []
    met = set(transcript.get("names_met_before") or [])
    for index, event in enumerate(transcript["events"]):
        kind = event["step"].get("kind")
        if kind in ("scene", "respond", "resolution", "read"):
            met |= _names_in(_story_text(event))
            continue
        if kind not in ("recall", "rule"):
            continue
        shown = " ".join(text for _path, _key, text in _iter_strings(event["step"].get("prompt") or {}))
        unseen = _names_in(shown) - met
        if unseen:
            problems.append(f"{_label(transcript, index, event)}: names {sorted(unseen)} before the learner has met them")
    return problems


def names_met(transcript: dict[str, Any]) -> set[str]:
    met: set[str] = set()
    for event in transcript["events"]:
        if event["step"].get("kind") in ("scene", "respond", "resolution", "read"):
            met |= _names_in(_story_text(event))
    return met


def check_grading(transcript: dict[str, Any]) -> list[str]:
    """A deliberately wrong answer is never met; a right one (even with phone
    typography or an accent slip) is never refused."""

    problems: list[str] = []
    for index, event in enumerate(transcript["events"]):
        intent = (event.get("answer") or {}).get("intent")
        outcome = (event.get("result") or {}).get("task_outcome")
        if event["step"].get("kind") != "recall" or outcome is None:
            continue
        if intent == "wrong" and outcome == "met":
            problems.append(f"{_label(transcript, index, event)}: a wrong answer was graded right: {event['answer']['input']}")
        if intent in ("right", "right-with-slip") and outcome != "met":
            problems.append(f"{_label(transcript, index, event)}: a right answer was refused: {event['answer']['input']}")
    return problems


# ---------------------------------------------------------------------------
# 8. EXPERIENCE-REVIEW 2026-10-04: repairs, Rappel wording, corrections of wishes
# ---------------------------------------------------------------------------

#: What a learner types when they give up: no French was tried.
GIVE_UP = re.compile(
    r"\b(?:je\s+(?:ne\s+)?sais\s+pas|sais\s+pas|keine\s+ahnung|wei(?:ß|ss)\s+(?:ich\s+)?nicht|i\s+don'?t\s+know)\b",
    re.IGNORECASE,
)
#: «today's rule» in the three chrome languages.
TODAY = re.compile(r"\b(?:von heute|today's|du jour)\b", re.IGNORECASE)


def check_repairs(transcript: dict[str, Any]) -> list[str]:
    """«Write what you said, correctly» is asked only of the learner's own French —
    never of a give-up or of a tapped card."""

    problems: list[str] = []
    for index, event in enumerate(transcript["events"]):
        prompt = event["step"].get("prompt") or {}
        target = prompt.get("target") or {}
        if event["step"].get("kind") != "recall" or target.get("kind") != "error":
            continue
        shown = str(prompt.get("prompt_fr") or prompt.get("source_fr") or "")
        if GIVE_UP.search(shown):
            problems.append(f"{_label(transcript, index, event)}: asks to repair a give-up: {shown!r}")
    return problems


def check_rule_of_today(transcript: dict[str, Any]) -> list[str]:
    """An item about a rule learnt on another day never calls it «today's rule»."""

    problems: list[str] = []
    today = {
        str((event["step"].get("prompt") or {}).get("concept_id"))
        for event in transcript["events"]
        if event["step"].get("kind") == "rule"
    }
    for index, event in enumerate(transcript["events"]):
        prompt = event["step"].get("prompt") or {}
        target = prompt.get("target") or {}
        if event["step"].get("kind") != "recall" or target.get("kind") != "grammar":
            continue
        if str(target.get("id")) in today:
            continue
        for key in ("instruction_native", "goal_native"):
            if TODAY.search(str(prompt.get(key) or "")):
                problems.append(f"{_label(transcript, index, event)}: a Rappel of another day's rule says «today»: {prompt.get(key)!r}")
    return problems


def check_wishes_are_not_corrected(transcript: dict[str, Any]) -> list[str]:
    """«je veux» + an infinitive or «que» is a wish, never a blunt request to soften."""

    problems: list[str] = []
    for index, event in enumerate(transcript["events"]):
        correction = (event.get("result") or {}).get("correction") or {}
        if _fold(correction.get("corrected_fr")) != "je voudrais":
            continue
        said = str(((event.get("answer") or {}).get("input") or {}).get("text") or "")
        if re.search(r"\bje\s+veux\s+(?:que\b|[a-zàâçéèêëîïôûùüÿœ]+(?:er|ir|re|oir)\b)", said, re.IGNORECASE):
            problems.append(f"{_label(transcript, index, event)}: a wish corrected to «je voudrais»: {said!r}")
    return problems


CHECKS = (
    check_grading,
    check_language,
    check_translations,
    check_duplicates,
    check_level,
    check_feedback,
    check_strings,
    check_spoilers,
    check_repairs,
    check_rule_of_today,
    check_wishes_are_not_corrected,
)


#: Defects the walk found inside a package another agent owns, reported there and
#: filtered here so the gate stays green on everything else. Each entry is
#: ``(substring of the problem, owner, where it lives)``; remove it with the fix.
#: The filter is narrow on purpose: one exact symptom, one step kind.
KNOWN_DEFECTS: tuple[tuple[str, str, str], ...] = ()


def _known(problem: str) -> bool:
    return any(symptom in problem for symptom, _owner, _where in KNOWN_DEFECTS)


def run_all(transcripts: list[dict[str, Any]], db: Any = None, *, include_known: bool = False) -> list[str]:
    del db
    problems: list[str] = []
    for transcript in transcripts:
        if transcript.get("private_leaks"):
            problems.append(f"{transcript['persona']} day {transcript['day']}: answer key on the wire: {transcript['private_leaks']}")
        for check in CHECKS:
            problems.extend(check(transcript))
    return problems if include_known else [problem for problem in problems if not _known(problem)]



# ---------------------------------------------------------------------------
# EXPERIENCE-REVIEW 2026-10-04: invariants of a whole life (tests/test_experience_walk.py)
# ---------------------------------------------------------------------------


def check_life(record: dict[str, Any]) -> list[str]:
    """A month of one learner: every surface answered, every day playable."""

    problems: list[str] = []
    who = f"{record['persona']} {record['quality']}"
    for day in record["days"]:
        label = f"{who} day {day['day']}"
        journey = day.get("journey") or {}
        if journey.get("error"):
            problems.append(f"{label}: the day could not be played: {journey['error']}")
        if (day.get("la_une") or {}).get("status_code"):
            problems.append(f"{label}: La Une answered {day['la_une']['status_code']}")
        if (day.get("courrier") or {}).get("status_code"):
            problems.append(f"{label}: the Courrier answered {day['courrier']['status_code']}")
        if (day.get("drill") or {}).get("status_code"):
            problems.append(f"{label}: the drill answered {day['drill']['status_code']}")
        due = (((day.get("drill") or {}).get("summary")) or {}).get("due_total") or 0
        if due > MAX_DUE_BACKLOG:
            problems.append(f"{label}: {due} words due at once — the drill's backlog crowds out new words")
        for letter in (day.get("courrier") or {}).get("letters") or []:
            correction = letter.get("correction") or {}
            answer = str(letter.get("answer_back") or "")
            if correction.get("verdict") == "unassessed" and "manque" in answer:
                problems.append(f"{label}: an unassessed letter is told something is missing: {answer!r}")
            if "Achieve:" in answer:
                problems.append(f"{label}: English in a correspondent's reply: {answer!r}")
            for objective in letter.get("objectives") or []:
                unit_level = _unit_level(str(objective or ""))
                level = _band(str((day.get("journey") or {}).get("learner_level") or record["true_level"]))
                # Two levels below can be the learner's own mistake or a unit they met
                # before placement; three is the catalogue's first units.
                if unit_level and unit_level < level - 2:
                    problems.append(f"{label}: a level-{level} learner's letter asks for {objective!r} (3+ levels below)")
    # Wave 1 package checks (each in its own module, wired here by the orchestrator).
    from tests.walk_checks_wp125a import check_letter_omissions

    problems.extend(check_letter_omissions(record))
    return problems


#: More words than this due at once means the drill cannot reach the day's new
#: words (it takes 30 due a session): the band check's light checks flooded it.
MAX_DUE_BACKLOG = 150


@lru_cache(maxsize=1)
def _unit_titles() -> dict[str, int]:
    """French unit titles → their band number, from the v2 catalogue."""

    import csv

    path = ROOT / "templates/french_core_grammar_v2.tsv"
    titles: dict[str, int] = {}
    if not path.exists():
        return titles
    with path.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            title = str(row.get("name_fr") or "").strip()
            if title:
                titles[title] = _band(str(row.get("cefr_level") or ""))
    return titles


def _unit_level(objective: str) -> int | None:
    """The band of the unit a «Placer une fois : …» objective names, when known."""

    if not objective.startswith("Placer une fois"):
        return None
    title = objective.split(":", 1)[-1].strip()
    return _unit_titles().get(title)
