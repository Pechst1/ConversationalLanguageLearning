"""EXERCISE-QA 2026-10-03 — every exercise sentence the app authors, rendered in en/de/fr.

The walk (``tests/test_learner_walk.py``) reads the days a persona actually meets;
this file reads the *tables* those days are made from, so a row no walk happens
to deal is still checked. For every module that authors exercise copy, every
``{"en": …, "de": …, "fr": …}`` table found at module level is rendered with
sample values and must:

* exist in all three languages, non-empty;
* carry the same ``{placeholders}`` in each language, and leave none behind;
* be in its own language (no English row under «de», no German under «en»);
* never pluralise with a slash or brackets («Wort/Wörter», «word(s)», «mot(s)»).
"""
from __future__ import annotations

import importlib
import re
import string
from typing import Any

import pytest

from tests.walk_checks import detect_language

#: Modules whose tables a learner reads inside an exercise (prompts, goals,
#: hints, verdict notes). The Forge's own modules belong to the Forge package and
#: are covered by its suite.
MODULES = (
    "app.services.answer_acceptance",
    "app.services.journey_contracts",
    "app.services.journey_learning",
    "app.services.journey_planner",
    "app.services.scene_items",
    "app.services.grammar_items",
    "app.services.learner_copy",
)
LANGUAGES = ("en", "de", "fr")
_PLURAL_SLASH = re.compile(r"Wort/Wörter|\bword\(s\)|\bmot\(s\)|\(e\)s\b|\bWörter?\(n\)")


def _tables(module: Any) -> list[tuple[str, dict[str, str]]]:
    """``(name, {en, de, fr})`` for every trilingual table at module level (one level of nesting)."""

    found: list[tuple[str, dict[str, str]]] = []

    def visit(name: str, value: Any, depth: int) -> None:
        if isinstance(value, dict):
            keys = set(value)
            if {"en", "de"} <= keys and keys <= {"en", "de", "fr"} and all(isinstance(v, str) for v in value.values()):
                found.append((name, value))
                return
            if depth < 2:
                for key, item in value.items():
                    visit(f"{name}[{key!r}]", item, depth + 1)

    for attribute in dir(module):
        if attribute.startswith("__"):
            continue
        visit(f"{module.__name__}.{attribute}", getattr(module, attribute), 0)
    return found


def _fields(template: str) -> set[str]:
    return {field for _text, field, _spec, _conv in string.Formatter().parse(template) if field}


def _render(template: str) -> str:
    sample = {field: "Lila" if "name" in field or "speaker" in field else "chat" for field in _fields(template)}
    try:
        return template.format(**sample)
    except (KeyError, IndexError, ValueError):
        return template


ALL_TABLES = [(name, table) for module in MODULES for name, table in _tables(importlib.import_module(module))]


def test_the_scan_finds_the_exercise_tables():
    names = [name for name, _table in ALL_TABLES]
    assert len(ALL_TABLES) > 150
    for table in ("RECALL_GOALS", "NOTE_COPY", "LEARNER_COPY", "_ORDER_NOTES", "CLOZE_INSTRUCTION"):
        assert any(f".{table}" in name for name in names), table


@pytest.mark.parametrize(("name", "table"), ALL_TABLES, ids=[name for name, _ in ALL_TABLES])
def test_every_exercise_table_is_whole_and_in_its_own_language(name, table):
    missing = [language for language in LANGUAGES if not str(table.get(language) or "").strip()]
    assert not missing, f"{name} has no {missing}"
    fields = {language: _fields(table[language]) for language in LANGUAGES}
    assert fields["en"] == fields["de"] == fields["fr"], f"{name}: placeholders differ {fields}"
    for language in LANGUAGES:
        rendered = _render(table[language])
        assert not re.search(r"\{[a-z_]+\}", rendered), f"{name}[{language}] leaves a placeholder: {rendered!r}"
        assert not _PLURAL_SLASH.search(rendered), f"{name}[{language}] pluralises with a slash: {rendered!r}"
        detected = detect_language(rendered)
        foreign = {"de": "en", "en": "de", "fr": "en"}[language]
        assert detected != foreign, f"{name}[{language}] reads as {detected}: {rendered!r}"
