"""One code asks the day's question again: ``day_contract.reask``, from the scene record.

The story-truth decision (11 Nov 2026): the scene record is the only place that knows
whether the day's question was answered, and ``day_contract.reask`` is the only code that
asks it again. The reply check only vetoes; it never writes a re-ask, and never serves a
reply with a question cut out of it. This reads the source, so a second writer fails here
before it reaches a learner.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

from app.services.season import day_contract

APP = Path(__file__).resolve().parent.parent / "app"
OWNER = APP / "services" / "season" / "day_contract.py"
#: The contract's own data class declares the field (``turns[].ask_again_fr``).
DECLARES = APP / "services" / "season" / "format.py"


def _trees():
    for path in sorted(APP.rglob("*.py")):
        yield path, ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _where(path: Path, node: ast.AST) -> str:
    return f"{path.relative_to(APP.parent)}:{getattr(node, 'lineno', '?')}"


def test_only_the_day_contract_reads_the_simpler_question():
    found = []
    for path, tree in _trees():
        if path in (OWNER, DECLARES):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and node.value == day_contract.ASK_AGAIN_KEY:
                found.append(_where(path, node))
            elif isinstance(node, ast.Attribute) and node.attr in ("ask_again_fr", "ASK_AGAIN_KEY"):
                found.append(_where(path, node))
            elif isinstance(node, ast.Name) and node.id == "ASK_AGAIN_KEY":
                found.append(_where(path, node))
    assert not found, f"the day's simpler question is read outside day_contract: {found}"


def test_reask_has_one_caller_and_it_hands_over_the_record():
    calls = []
    for path, tree in _trees():
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "reask"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "day_contract"
            ):
                calls.append((path, node))
    assert len(calls) == 1, [_where(path, node) for path, node in calls]
    path, call = calls[0]
    keywords = {keyword.arg for keyword in call.keywords}
    assert "ledger" in keywords, f"{_where(path, call)}: reask is not given the scene record"


def test_reask_reads_answered_from_the_record():
    source = inspect.getsource(day_contract.reask)
    assert "ledger" in inspect.signature(day_contract.reask).parameters
    assert "_open_in_record(ledger" in source


def test_nothing_else_writes_from_the_open_question():
    """A line built from the record's open question (``open_for_learner``) or from the
    trimmed reply of the check would be a second re-ask writer."""

    found = []
    for path, tree in _trees():
        if path.name == "scene_ledger.py":
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and node.value == "open_for_learner":
                found.append(_where(path, node))
            if isinstance(node, ast.Name | ast.Attribute):
                name = node.id if isinstance(node, ast.Name) else node.attr
                if name == "without_reasked_question":
                    found.append(_where(path, node))
    assert not found, f"another re-ask writer: {found}"
