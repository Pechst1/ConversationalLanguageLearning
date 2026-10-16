"""NATIVE-MEANING (owner, 2026-10-16): a production drill says what to produce.

A written cloze («…, ils veulent acheter tout l'immeuble.») or a sentence rebuild
with no meaning to aim for is guesswork: many words fit the gap, many orders fit
the tiles. From B1 the scene carries no line translations (``text_native`` is an
A1/A2 reading aid), so the day's build translates the few sentences its production
drills are cut from, once, into the learner's own language (``native_language``,
not the chrome language: every learner learns from their own language), and the
goal quotes it.

Best effort: no LLM, a timeout or a malformed answer leaves the goals as they were.
"""
from __future__ import annotations

import json
import logging
from collections.abc import Callable, Iterable
from typing import Any

from app.services.scene_items import BLANK, with_meaning

logger = logging.getLogger(__name__)

#: The recall formats that ask the learner to produce a sentence (or part of one).
MEANING_FORMATS = frozenset({"short_answer", "unscramble", "tiles", "word_bank"})
#: A goal that already quotes something (a meaning, a source) has its aim.
_QUOTES = ("«", "„", '"', "“")
_GAPS = ("…", BLANK)
#: One build translates at most this many sentences.
MAX_SENTENCES = 12

Translator = Callable[[list[str], str], list[str] | None]


def needs_meaning(task: dict[str, Any]) -> bool:
    goal = str(task.get("goal_native") or "")
    return str(task.get("task_type") or "") in MEANING_FORMATS and not any(mark in goal for mark in _QUOTES)


def full_sentence(task: dict[str, Any]) -> str | None:
    """The whole French sentence a production drill is cut from, or ``None``."""

    solution = " ".join(str(task.get("solution_fr") or "").split())
    if not solution:
        return None
    prompt = str(task.get("prompt_fr") or "")
    for gap in _GAPS:
        if gap in prompt:
            return " ".join(prompt.replace(gap, solution, 1).split())
    if str(task.get("task_type") or "") == "short_answer":
        # A short answer with no gap is a gloss to translate, not a sentence.
        return None
    return solution


def sentences_to_translate(tasks: Iterable[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for task in tasks:
        sentence = full_sentence(task) if needs_meaning(task) else None
        if sentence and sentence not in out:
            out.append(sentence)
    return out[:MAX_SENTENCES]


def apply_meaning(task: dict[str, Any], meanings: dict[str, str], language: Any) -> str | None:
    """The goal ``task`` should carry with its meaning, or ``None`` to leave it."""

    if not needs_meaning(task):
        return None
    meaning = meanings.get(full_sentence(task) or "")
    goal = str(task.get("goal_native") or "").strip()
    if not meaning or not goal:
        return None
    return with_meaning(goal, meaning, language)


def llm_translate(sentences: list[str], language_name: str) -> list[str] | None:
    """One call: the sentences, in order, in ``language_name``."""

    from app.config import settings
    from app.services.llm_service import LLMService

    result = LLMService().generate_chat_completion(
        messages=[{"role": "user", "content": json.dumps(sentences, ensure_ascii=False)}],
        system_prompt=(
            f"Translate each French sentence of the JSON array into natural, faithful {language_name}. "
            f"Return ONLY a JSON array of the {language_name} sentences, same order, same length."
        ),
        temperature=0.0,
        max_tokens=1200,
        model=settings.ATELIER_CORRECTION_LLM_MODEL,
        reasoning_effort="minimal",
        request_timeout=15.0,
    )
    text = (result.content or "").strip()
    if text.startswith("```"):
        text = text.strip("`").removeprefix("json").strip()
    parsed = json.loads(text)
    if not isinstance(parsed, list) or len(parsed) != len(sentences):
        return None
    return [str(item or "").strip() for item in parsed]


def native_meanings(
    tasks: Iterable[dict[str, Any]],
    native_language: Any,
    *,
    translate: Translator | None = None,
) -> dict[str, str]:
    """``{French sentence: its meaning in the learner's language}`` for the
    production drills that lack one. Empty for a French speaker, without an LLM,
    or on any failure."""

    from app.config import settings
    from app.services.glosses import EXPLANATION_LANGUAGE_NAMES, normalize_language

    language = normalize_language(native_language)
    if language == "fr" or language not in EXPLANATION_LANGUAGE_NAMES:
        return {}
    sentences = sentences_to_translate(tasks)
    if not sentences:
        return {}
    if translate is None:
        if not settings.ATELIER_LLM_ENABLED:
            return {}
        translate = llm_translate
    try:
        translated = translate(sentences, EXPLANATION_LANGUAGE_NAMES[language])
    except Exception:  # pragma: no cover - best effort by contract
        logger.warning("recall_meanings: translation failed", exc_info=True)
        return {}
    if not translated or len(translated) != len(sentences):
        return {}
    return {french: native for french, native in zip(sentences, translated, strict=True) if native}


__all__ = [
    "MEANING_FORMATS",
    "apply_meaning",
    "full_sentence",
    "native_meanings",
    "needs_meaning",
    "sentences_to_translate",
    "with_meaning",
]
