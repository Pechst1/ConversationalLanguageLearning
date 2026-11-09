"""ROOT CAUSE #147: a person's name lives in the cast registry, and nowhere else.

The guard: no file under ``app/`` keeps a literal table of the cast's names, whether as a dict,
a set, a list, a tuple or a regular expression. Anything naming two or more people by name
fails. Read the registry instead (``display_name``, ``bank_ids``, ``vocative_names``,
``name_words``…).

``ALLOWED`` goes to zero. Each entry names who removes it; an entry that no longer holds a
table fails too, so it cannot outlive its reason.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from app.services import cast_registry

REPO = Path(__file__).resolve().parents[1]
#: The registry's own files.
THE_REGISTRY = {"app/services/cast_registry.py", "app/services/cast_aliases.py"}
#: file -> who takes it off the list.
ALLOWED: dict[str, str] = {}


def _people_by_word() -> dict[str, str]:
    """Every spelling of every person, casefolded → registry id."""

    words: dict[str, str] = {}
    for row in cast_registry.all_members().values():
        for spelling in cast_registry._spellings(row):
            words[spelling.casefold()] = row.id
    words.update((alias.casefold(), cast_id) for alias, cast_id in cast_registry.aliases().items())
    for cast_id, lexicon in cast_registry.bank_ids().items():
        words[lexicon.casefold()] = cast_id
    return words


def _alternatives(pattern: str) -> list[str]:
    """The words of a regular expression's alternation: «\\b(?:Margaux|M\\. Marchand)\\b»."""

    plain = re.sub(r"\\[bBwWsSdD]|\(\?:|[()^$+*?\[\]]", "", pattern).replace("\\.", ".")
    return [part.strip().casefold() for part in plain.split("|")]


def _collection_items(node: ast.AST) -> list[ast.expr] | None:
    if isinstance(node, ast.Dict):
        return [key for key in node.keys if key is not None] + list(node.values)
    if isinstance(node, ast.Set | ast.List | ast.Tuple):
        return list(node.elts)
    return None


def tables_in(source: str, *, words: dict[str, str] | None = None) -> list[tuple[int, list[str]]]:
    """(line, the people it names) for each literal naming two people or more."""

    words = words if words is not None else _people_by_word()
    found: list[tuple[int, list[str]]] = []
    for node in ast.walk(ast.parse(source)):
        items = _collection_items(node)
        if items is not None:
            named = {
                words[item.value.strip().casefold()]
                for item in items
                if isinstance(item, ast.Constant)
                and isinstance(item.value, str)
                and item.value.strip().casefold() in words
            }
            if len(named) >= 2:
                found.append((getattr(node, "lineno", 0), sorted(named)))
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and "|" in node.value:
            named = {words[part] for part in _alternatives(node.value) if part in words}
            if len(named) >= 2:
                found.append((node.lineno, sorted(named)))
    return found


def _python_files() -> dict[str, str]:
    return {
        path.relative_to(REPO).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted((REPO / "app").rglob("*.py"))
    }


def test_the_guard_sees_a_table_in_every_shape():
    source = """
A = {"margaux_barman": "Margaux", "lila_bonnet": "Lila"}
B = {"Gus", "Romy"}
C = ("margaux", "gus")
D = r"(?:Margaux|Marin|M\\. Marchand)"
E = rf"\\b(margaux|gus)\\b"
"""
    assert [line for line, _people in tables_in(source)] == [2, 3, 4, 5, 6]


def test_the_guard_leaves_alone_what_is_not_a_table():
    source = """
A = {"id": "margaux", "name": "Margaux"}  # one person
B = "Margaux et Lila parlent."  # prose
C = ("margaux_barman",)
D = "tu|vous"
"""
    assert tables_in(source) == []


def test_no_literal_cast_name_table_in_python():
    offenders = {
        path: found
        for path, source in _python_files().items()
        if path not in THE_REGISTRY and path not in ALLOWED and (found := tables_in(source))
    }
    assert not offenders, f"read the cast registry instead of keeping a table: {offenders}"


def test_the_allow_list_only_holds_what_is_still_true():
    files = _python_files()
    stale = [path for path in ALLOWED if not tables_in(files[path])]
    assert not stale, f"no table left here: take it off ALLOWED: {stale}"
