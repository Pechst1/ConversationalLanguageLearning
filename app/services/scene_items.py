"""WP-86 — «Le vocabulaire vient de l'histoire»: what a scene teaches, and a floor
of quick items built from the scene's own text.

Two halves, both pure (no ``Session``, no model call), so the story engine's
validator and the planner can both import this module:

* **The lexicon.** ``SceneDraft.lexicon`` names three to five words the scene
  teaches. :func:`validate_lexicon` keeps the entries a deterministic check can
  stand behind — the word is really in the scene, the gloss is a gloss and not
  the French copied, a noun says its gender — and *drops* the rest. A thin
  lexicon is never a refused scene: the scene is the day, the words are a bonus.
  Band fit is a soft score against the French 5000 deck's rank where the
  catalogue knows the lemma.
* **The floor.** A day whose due queue is thin still has the scene. The builders
  below pose quick items from it — rebuild a character's line (``unscramble``)
  and a cloze on a lexicon word in its own sentence (a ``choice``). Both are
  graded by identity, so WP-76's hashed answer key colours them on the device.
  «Qui a dit ça ?» (``who_said``) is no longer posed (QA-PRACTICE, owner
  2026-10-03: it tests the plot, not French); its builder stays so a journey
  planned before keeps rendering and grading.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

LEXICON_MIN = 3
LEXICON_MAX = 5
#: The highest French 5000 rank that still sits comfortably inside a band. A
#: soft score only: a scene about a flooded cellar may teach «inonder».
BAND_RANK_CEILING = {"A1": 1000, "A2": 2000, "B1": 3500, "B2": 5000, "C1": 8000}
#: A character line rebuilt as tiles is a quick item only while it is short.
LINE_UNSCRAMBLE_WORDS = (3, 8)
NOUN_TAGS = frozenset({"noun", "nom", "n"})
GENDERS = {"m": "m", "masculine": "m", "masc": "m", "f": "f", "feminine": "f", "fem": "f"}


def fold(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).casefold()
    text = "".join(char for char in text if not unicodedata.combining(char))
    return " ".join(text.replace("’", "'").split())


def _words(value: Any) -> list[str]:
    return [word for word in re.split(r"[^a-z0-9']+", fold(value)) if word]


def contains_surface(text: Any, surface: Any) -> bool:
    """Is ``surface`` a whole-word run of ``text`` (accents and case folded)?"""

    haystack = [word.split("'")[-1] if "'" in word else word for word in _words(text)]
    raw = _words(text)
    needle = _words(surface)
    if not needle:
        return False
    for words in (raw, haystack):
        if any(words[i:i + len(needle)] == needle for i in range(len(words))):
            return True
    return False


def scene_texts(draft: dict[str, Any]) -> dict[str, str]:
    """Every learner-facing French text of a draft, keyed by a stable line ref."""

    texts: dict[str, str] = {"premise": str(draft.get("premise_fr") or "")}
    for index, panel in enumerate(draft.get("panels") or []):
        if not isinstance(panel, dict):
            continue
        texts[f"panel:{index}:narration"] = str(panel.get("narration_fr") or "")
        for number, line in enumerate(panel.get("dialogue") or []):
            if isinstance(line, dict):
                texts[f"panel:{index}:line:{number}"] = str(line.get("text_fr") or "")
    texts["opening"] = str(draft.get("opening_line_fr") or "")
    return {ref: text for ref, text in texts.items() if text.strip()}


def band_fit(rank: int | None, level: str | None) -> float | None:
    """1.0 inside the band, 0.5 above it, ``None`` when the deck has no rank."""

    if rank is None:
        return None
    ceiling = BAND_RANK_CEILING.get(str(level or "").upper())
    if ceiling is None:
        return 1.0
    return 1.0 if int(rank) <= ceiling else 0.5


def validate_lexicon(
    entries: Iterable[dict[str, Any]],
    draft: dict[str, Any],
    *,
    level: str | None = None,
    rank_of: Callable[[str], int | None] | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Keep the entries a deterministic check can stand behind; drop the rest.

    Returns ``(kept, dropped)`` where ``dropped`` names each refusal for the
    record (``"brouillard: surface_not_in_scene"``). A kept entry comes back
    normalised: its ``line_ref`` points at a text that really holds the surface
    (repaired when the model named the wrong one), ``gender`` is ``m``/``f`` or
    ``None``, and ``band_fit`` is the soft score (``None`` when unranked).
    In-band words are kept before out-of-band ones, then in the model's order.
    """

    texts = scene_texts(draft)
    kept: list[dict[str, Any]] = []
    dropped: list[str] = []
    seen: set[str] = set()
    for raw in entries:
        entry = dict(raw) if isinstance(raw, dict) else {}
        surface = " ".join(str(entry.get("surface_fr") or "").split())
        lemma = " ".join(str(entry.get("lemma") or surface).split())
        gloss = " ".join(str(entry.get("gloss_native") or "").split())
        pos = fold(entry.get("part_of_speech"))
        name = surface or lemma or "?"
        if not surface or not lemma:
            dropped.append(f"{name}: no_surface")
            continue
        if fold(lemma) in seen:
            dropped.append(f"{name}: duplicate_lemma")
            continue
        ref = str(entry.get("line_ref") or "")
        if not contains_surface(texts.get(ref, ""), surface):
            ref = next((key for key, text in texts.items() if contains_surface(text, surface)), "")
        if not ref:
            dropped.append(f"{name}: surface_not_in_scene")
            continue
        if not gloss or fold(gloss) in {fold(surface), fold(lemma)}:
            dropped.append(f"{name}: gloss_missing_or_copied")
            continue
        gender = GENDERS.get(fold(entry.get("gender")))
        if pos in NOUN_TAGS and gender is None:
            dropped.append(f"{name}: noun_without_gender")
            continue
        rank = None
        if rank_of is not None:
            try:
                rank = rank_of(lemma)
            except Exception:  # noqa: BLE001 - a soft score never refuses a word
                rank = None
        seen.add(fold(lemma))
        kept.append(
            {
                "surface_fr": surface,
                "lemma": lemma,
                "gloss_native": gloss,
                "part_of_speech": pos or None,
                "gender": gender,
                "line_ref": ref,
                "band_fit": band_fit(rank, level),
            }
        )
    kept.sort(key=lambda item: 0 if item["band_fit"] in (None, 1.0) else 1)
    for extra in kept[LEXICON_MAX:]:
        dropped.append(f"{extra['surface_fr']}: over_limit")
    return kept[:LEXICON_MAX], dropped


def sentence_of(draft: dict[str, Any], entry: dict[str, Any]) -> str:
    """The sentence of the scene an entry was taught in (its whole line)."""

    texts = scene_texts(draft)
    text = texts.get(str(entry.get("line_ref") or ""), "")
    if not contains_surface(text, entry.get("surface_fr")):
        text = next(
            (value for value in texts.values() if contains_surface(value, entry.get("surface_fr"))),
            "",
        )
    for sentence in re.split(r"(?<=[.!?…])\s+", text):
        if contains_surface(sentence, entry.get("surface_fr")):
            return sentence.strip()
    return text.strip()


# --------------------------------------------------------------------------
# The floor: three quick items out of the scene itself
# --------------------------------------------------------------------------

WHO_SAID_INSTRUCTION = {
    "en": "Who said this?",
    "de": "Wer hat das gesagt?",
    "fr": "Qui a dit ça ?",
}
CLOZE_INSTRUCTION = {
    "en": "Complete the line from the scene.",
    "de": "Ergänze den Satz aus der Szene.",
    "fr": "Complétez la phrase de la scène.",
}
LINE_UNSCRAMBLE_INSTRUCTION = {
    "en": "Put {name}'s line back in order.",
    "de": "Bring den Satz von {name} wieder in die richtige Reihenfolge.",
    "fr": "Remettez dans l'ordre la réplique de {name}.",
}
#: EXERCISE-QA: a nameless rebuild, for a line whose speaker the world does not name
#: (a walk-on «clerk_2» must never reach the learner as a name).
SCENE_UNSCRAMBLE_INSTRUCTION = {
    "en": "Put the line from the scene back in order.",
    "de": "Bring den Satz aus der Szene wieder in die richtige Reihenfolge.",
    "fr": "Remettez dans l'ordre la phrase de la scène.",
}
#: EXERCISE-QA: a gap needs a sentence around it. «La ___» or «___.» is a guess, not
#: a word recalled in context.
CLOZE_MIN_CONTEXT_WORDS = 2
BLANK = "___"


@dataclass(frozen=True, slots=True)
class SceneLine:
    """One line a character says in the scene, as the learner read it."""

    character_id: str
    text_fr: str
    line_ref: str


def _digest(*parts: Any) -> str:
    return hashlib.sha256("\x1f".join(str(part) for part in parts).encode("utf-8")).hexdigest()


def _localized(table: dict[str, str], language: Any) -> str:
    return table.get(str(language or "en"), table["en"])


def draft_of(scenario: Any) -> dict[str, Any]:
    story = getattr(scenario, "story_context", None)
    draft = story.get("draft") if isinstance(story, dict) else None
    return draft if isinstance(draft, dict) else {}


def lexicon_of(scenario: Any) -> list[dict[str, Any]]:
    return [entry for entry in draft_of(scenario).get("lexicon") or [] if isinstance(entry, dict)]


def line_meanings(scenario: Any) -> dict[str, str]:
    """``{French line: its translation}`` for the lines the scene translated (WP-90's
    «Traduire la case», A1/A2): the dialogue's ``text_native`` and the opening line's
    ``translation_native``. WP-103 T3: a drill cut from a line says what it means."""

    draft = draft_of(scenario)
    meanings: dict[str, str] = {}
    for panel in draft.get("panels") or []:
        for line in (panel or {}).get("dialogue") or []:
            if not isinstance(line, dict):
                continue
            text, native = str(line.get("text_fr") or "").strip(), str(line.get("text_native") or "").strip()
            if text and native:
                meanings.setdefault(text, native)
    opening = str(draft.get("opening_line_fr") or "").strip()
    native = str(draft.get("translation_native") or "").strip()
    if opening and native:
        meanings.setdefault(opening, native)
    # A «translation» that is the French itself (an authored page falls back to
    # the line when it has none) is no translation: show none rather than it.
    return {text: native for text, native in meanings.items() if fold(native) != fold(text)}


def meaning_of(meanings: dict[str, str], text: str) -> str | None:
    """The translation of ``text`` (typography and accents folded), or ``None``."""

    wanted = fold(text).strip(" .!?…«»\"")
    for french, native in meanings.items():
        if fold(french).strip(" .!?…«»\"") == wanted:
            return native
    return None


def named(name: str | None) -> bool:
    """Is this a name a learner can read (not empty, not a machine id like «clerk_2»)?"""

    text = str(name or "").strip()
    return bool(text) and "_" not in text and not any(char.isdigit() for char in text)


def short_name(name: str) -> str:
    """«Romane « Romy » Tremblay» → «Romy»; «Marin Lévêque» → «Marin»."""

    nickname = re.search(r"«\s*([^»]+?)\s*»", str(name or ""))
    if nickname:
        return nickname.group(1)
    return (str(name or "").split() or [""])[0]


def cast_names(scenario: Any) -> dict[str, str]:
    """``{character_id: name}`` for the cast the scene's world knows."""

    story = getattr(scenario, "story_context", None) or {}
    source = story.get("source") if isinstance(story, dict) else None
    cast = ((source or {}).get("world") or {}).get("cast") or []
    names = {
        str(member["id"]): str(member.get("name") or member["id"])
        for member in cast
        if isinstance(member, dict) and member.get("id")
    }
    speaker = str(getattr(scenario, "character_id", "") or "")
    if speaker and speaker not in names:
        names[speaker] = str(getattr(scenario, "character_name", "") or speaker)
    return names


def minor_ids(scenario: Any) -> set[str]:
    """Cast members the world marks as minor (a baker, a notary, a clerk)."""

    story = getattr(scenario, "story_context", None) or {}
    source = story.get("source") if isinstance(story, dict) else None
    cast = ((source or {}).get("world") or {}).get("cast") or []
    return {
        str(member["id"])
        for member in cast
        if isinstance(member, dict)
        and member.get("id")
        and (member.get("minor") or str(member.get("role") or "").startswith("Minor character"))
    }


def scene_lines(scenario: Any) -> list[SceneLine]:
    """The characters' own lines, in reading order, opening line last."""

    draft = draft_of(scenario)
    lines: list[SceneLine] = []
    for index, panel in enumerate(draft.get("panels") or []):
        for number, line in enumerate((panel or {}).get("dialogue") or []):
            if isinstance(line, dict) and line.get("character_id") and line.get("text_fr"):
                lines.append(
                    SceneLine(str(line["character_id"]), str(line["text_fr"]).strip(), f"panel:{index}:line:{number}")
                )
    opening = str(draft.get("opening_line_fr") or getattr(scenario, "opening_line_fr", "") or "")
    speaker = str(draft.get("character_id") or getattr(scenario, "character_id", "") or "")
    if opening.strip() and speaker:
        lines.append(SceneLine(speaker, opening.strip(), "opening"))
    unique: dict[str, SceneLine] = {}
    for line in lines:
        unique.setdefault(fold(line.text_fr), line)
    return list(unique.values())


def build_who_said_task(
    *, target: Any, line: SceneLine, names: dict[str, str], optional: bool, control_language: Any
) -> Any | None:
    """«Qui a dit ça ?» — a line of the scene and up to three faces.

    A pick graded by option id. Needs a second person in the cast to choose;
    the speaker's card carries their ``character_id`` so the device draws the
    face. Evidence-free on the server: knowing who said a line is reading the
    story, not knowing the word (``journey_learning.evaluate_recall``).
    """

    from app.services.journey_contracts import RecallTask

    if line.character_id not in names:
        return None
    others = sorted(
        (cid for cid in names if cid != line.character_id),
        key=lambda cid: _digest(target.id, line.line_ref, "who-other", cid),
    )[:2]
    if not others:
        return None
    people = [line.character_id, *others]
    cards = [
        {"id": "who_" + _digest(target.id, line.line_ref, cid)[:8], "text_fr": names[cid], "character_id": cid}
        for cid in people
    ]
    shown = sorted(cards, key=lambda card: _digest(target.id, "who-layout", card["id"]))
    return RecallTask(
        task_type="who_said",
        instruction_native=_localized(WHO_SAID_INSTRUCTION, control_language),
        prompt_fr=line.text_fr,
        options=shown,
        target=target,
        optional=optional,
        correct_option_id=cards[0]["id"],
        # The correction on a wrong pick names the speaker, not the line.
        accepted_answers=[names[line.character_id]],
        solution_fr=None,
        estimated_seconds=0,
    )


def _blanked(sentence: str, surface: str) -> str | None:
    pattern = re.compile(r"(?<![\wÀ-ÿ])" + re.escape(surface) + r"(?![\wÀ-ÿ])", re.IGNORECASE)
    blanked, count = pattern.subn(BLANK, sentence, count=1)
    return blanked if count else None


def build_cloze_task(
    *,
    target: Any,
    surface: str,
    sentence: str,
    distractors: Iterable[str],
    optional: bool,
    control_language: Any,
    meaning: str | None = None,
    speaker_name: str | None = None,
) -> Any | None:
    """A lexicon word blanked out of its own scene sentence; pick it back.
    WP-103 T3: with the line's translation, the goal says what it means."""

    from app.services.journey_contracts import RecallTask, recall_goal

    prompt = _blanked(sentence, surface)
    if not prompt or BLANK not in prompt:
        return None
    if len(re.findall(r"[^\W\d_]+", prompt.replace(BLANK, " "))) < CLOZE_MIN_CONTEXT_WORDS:
        return None
    words = [surface]
    for other in distractors:
        other = " ".join(str(other or "").split())
        if other and fold(other) not in {fold(word) for word in words} and not contains_surface(sentence, other):
            words.append(other)
        if len(words) == 3:
            break
    if len(words) < 2:
        return None
    cards = [{"id": "clz_" + _digest(target.id, "cloze", word)[:8], "text_fr": word} for word in words]
    shown = sorted(cards, key=lambda card: _digest(target.id, "cloze-layout", card["id"]))
    return RecallTask(
        task_type="choice",
        instruction_native=_localized(CLOZE_INSTRUCTION, control_language),
        prompt_fr=prompt,
        options=shown,
        target=target,
        optional=optional,
        correct_option_id=cards[0]["id"],
        accepted_answers=[surface],
        solution_fr=sentence,
        estimated_seconds=0,
        # A cloze shows its line: without a translation, the line is the goal.
        goal_native=(
            recall_goal("complete_line", control_language, speaker=short_name(speaker_name), meaning=meaning)
            if meaning and speaker_name
            else (
                _localized(CLOZE_INSTRUCTION, control_language).rstrip(".") + f' : "{meaning}"'
                if meaning and str(control_language or "en")[:2] == "fr"
                else (
                    _localized(CLOZE_INSTRUCTION, control_language).rstrip(".") + f': "{meaning}"'
                    if meaning
                    else _localized(CLOZE_INSTRUCTION, control_language)
                )
            )
        ),
    )


def tile_words(text: str) -> list[str]:
    """A sentence cut into tiles: one word per tile, quotation marks dropped, and
    French spaced punctuation («?», «!», «:», «;») kept on the word before it —
    a tile that is only «?» is a puzzle about typography (QA-PRACTICE)."""

    tiles: list[str] = []
    for raw in str(text or "").split():
        token = raw.strip("«»“”\"„")
        if not token:
            continue
        if tiles and not any(char.isalnum() for char in token):
            tiles[-1] = f"{tiles[-1]} {token}"
            continue
        tiles.append(token)
    return tiles


def build_line_unscramble_task(
    *,
    target: Any,
    line: SceneLine,
    speaker_name: str | None,
    optional: bool,
    control_language: Any,
    meaning: str | None = None,
) -> Any | None:
    """A character's line (three to eight words) rebuilt as tiles. WP-103 T3: the
    goal names the speaker, and the line's meaning when the scene translated it."""

    from app.services.journey_contracts import RecallTask, recall_goal

    tokens = tile_words(line.text_fr)
    low, high = LINE_UNSCRAMBLE_WORDS
    if not low <= len(tokens) <= high:
        return None
    tiles = [
        {"id": "tile_" + _digest(target.id, line.line_ref, index, token)[:8], "text_fr": token}
        for index, token in enumerate(tokens)
    ]
    order = [tile["id"] for tile in tiles]
    if len(set(order)) != len(order) or len({fold(t) for t in tokens}) < 2:
        return None
    shown = sorted(tiles, key=lambda tile: _digest(target.id, "line-layout", tile["id"]))
    if [tile["id"] for tile in shown] == order:
        shown = shown[1:] + shown[:1]
    sentence = " ".join(tokens)
    if not named(speaker_name):
        if not meaning:
            return None
        return RecallTask(
            task_type="unscramble",
            instruction_native=_localized(SCENE_UNSCRAMBLE_INSTRUCTION, control_language),
            prompt_fr=None,
            options=shown,
            target=target,
            optional=optional,
            correct_tile_order=order,
            accepted_answers=[sentence],
            solution_fr=sentence,
            estimated_seconds=0,
            goal_native=recall_goal("rebuild_scene", control_language, meaning=meaning),
        )
    return RecallTask(
        task_type="unscramble",
        instruction_native=_localized(LINE_UNSCRAMBLE_INSTRUCTION, control_language).format(
            name=speaker_name
        ),
        prompt_fr=None,
        options=shown,
        target=target,
        optional=optional,
        correct_tile_order=order,
        accepted_answers=[sentence],
        solution_fr=sentence,
        estimated_seconds=0,
        goal_native=(
            recall_goal("rebuild_line", control_language, speaker=short_name(speaker_name), meaning=meaning)
            if meaning
            else recall_goal("rebuild_speaker", control_language, speaker=short_name(speaker_name))
        ),
    )


_ARTICLE = re.compile(r"^(?:le|la|les|un|une|des|du|l')\s*", re.IGNORECASE)


def target_surfaces(target: Any, metadata: dict[str, Any] | None = None) -> list[str]:
    """How a target may appear in the scene: its taught surface, then its label
    with and without the article."""

    label = " ".join(str(getattr(target, "label_fr", "") or "").split())
    forms = [str((metadata or {}).get("surface_fr") or ""), label, _ARTICLE.sub("", label)]
    return [form for index, form in enumerate(forms) if form and form not in forms[:index]]


def floor_tasks(
    scenario: Any,
    targets: list[tuple[Any, dict[str, Any]]],
    *,
    expected_reply: str | None = None,
) -> list[tuple[Any, Any]]:
    """Every scene-derived quick item today could pose, best first.

    ``targets`` are ``(TargetRef, candidate metadata)`` pairs. Each item is
    tied to a word of today that appears in the line it is built from, so the
    evidence it earns lands on a real catalogue row. Lines that would say the
    reply before the learner writes it are not used. Interleaved — a cloze, a
    rebuilt line, then round again — so a floor is a mix and not grids of tiles.

    QA-PRACTICE (owner, 2026-10-03, «was bringt eine solche Aufgabe?»): no
    «Qui a dit ça ?» — naming who said a line is plot memory, not French. The
    slot it held is filled by the planner's language items.
    """

    from app.services.journey_content import line_spoils_reply

    language = getattr(scenario, "control_language", "en")
    names = cast_names(scenario)
    lines = [line for line in scene_lines(scenario) if not line_spoils_reply(line.text_fr, expected_reply)]
    lexicon = lexicon_of(scenario)
    draft = draft_of(scenario)
    glossed = [t for t, _m in targets if getattr(t, "label_native", None)]
    meanings = line_meanings(scenario)

    def owner(text: str) -> tuple[Any, str] | None:
        for target, metadata in targets:
            for surface in target_surfaces(target, metadata):
                if contains_surface(text, surface):
                    return target, surface
        return None

    rebuilt: list[tuple[Any, Any]] = []
    for line in lines:
        found = owner(line.text_fr)
        if found is None:
            continue
        target, _surface = found
        task = build_line_unscramble_task(
            target=target,
            line=line,
            speaker_name=names.get(line.character_id),
            optional=True,
            control_language=language,
            meaning=meaning_of(meanings, line.text_fr),
        )
        if task is not None:
            rebuilt.append((target, task))
    clozes: list[tuple[Any, Any]] = []
    for entry in lexicon:
        sentence = sentence_of(draft, entry)
        if not sentence or line_spoils_reply(sentence, expected_reply):
            continue
        found = owner(entry.get("surface_fr") or "")
        if found is None:
            continue
        target, _surface = found
        others = [str(item.get("surface_fr") or "") for item in lexicon if item is not entry]
        # Every card in the blank's shape: an article only when the blank has one.
        bare_blank = not _ARTICLE.match(str(entry.get("surface_fr") or ""))
        others += [
            _ARTICLE.sub("", label) if bare_blank else label
            for label in (str(getattr(t, "label_fr", "")) for t in glossed if t is not target)
        ]
        task = build_cloze_task(
            target=target,
            surface=str(entry.get("surface_fr")),
            sentence=sentence,
            distractors=others,
            optional=True,
            control_language=language,
            meaning=meaning_of(meanings, sentence),
        )
        if task is not None:
            clozes.append((target, task))
    ordered: list[tuple[Any, Any]] = []
    for index in range(max(len(clozes), len(rebuilt), 0)):
        for bucket in (clozes, rebuilt):
            if index < len(bucket):
                ordered.append(bucket[index])
    return ordered


__all__ = [
    "BAND_RANK_CEILING",
    "LEXICON_MAX",
    "LEXICON_MIN",
    "SceneLine",
    "band_fit",
    "build_cloze_task",
    "build_line_unscramble_task",
    "line_meanings",
    "meaning_of",
    "build_who_said_task",
    "tile_words",
    "cast_names",
    "contains_surface",
    "draft_of",
    "floor_tasks",
    "lexicon_of",
    "scene_lines",
    "scene_texts",
    "sentence_of",
    "target_surfaces",
    "validate_lexicon",
]
