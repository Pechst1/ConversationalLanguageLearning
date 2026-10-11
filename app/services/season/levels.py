"""T-2 (content program 2026-10-03): a season's level variants, kept beside the bible.

The tentpoles carry the owner-approved bible text verbatim (``scripts/season_check.py``
fails on any bible line not carried word for word), written at A2 with B1 where
it differs. The level variants — ``a1``, ``b1`` where the bible wrote none,
``b2`` and ``c1`` — live in ``app/data/season/<id>/levels*.json`` instead, so the
bible files stay exactly as approved and a variant can be regenerated without
touching them:

* ``lines`` — ``{level_key: {"a1"?, "b1"?, "b2"?, "c1"?}}``. The key is a
  fingerprint of the canonical text (:func:`level_key`), so the same line said
  twice shares its variants, and a bible edit makes the old variant unreachable
  (stale) rather than wrong;
* ``examples`` — ``{"<file>:<turn>:<reply>": {"a1": [...], "b2": [...], "c1": [...]}}``
  for a turn's example replies, and ``"<file>:<solve>:lands"`` for a convaincre's.

:func:`apply_levels` folds the overlay into the raw season JSON before
validation; it only ever fills a field the bible left empty.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

LEVELS_FILE = "levels.json"
VARIANT_FIELDS = ("a1", "b1", "b2", "c1")


def level_key(a2: str, b1: str | None = None) -> str:
    """Fingerprint of a line's canonical text (A2, and B1 where the bible wrote one)."""

    source = f"{a2.strip()}␟{(b1 or '').strip()}"
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:12]


def is_say(node: Any) -> bool:
    return isinstance(node, dict) and isinstance(node.get("a2"), str) and bool(node["a2"].strip())


def iter_says(node: Any) -> Iterator[dict[str, Any]]:
    """Every Say / Wording in raw season JSON (depth first, the neutral wording too)."""

    if isinstance(node, dict):
        if is_say(node):
            yield node
        for value in node.values():
            yield from iter_says(value)
    elif isinstance(node, list):
        for value in node:
            yield from iter_says(value)


def iter_example_slots(file_id: str, node: Any) -> Iterator[tuple[str, dict[str, Any], str]]:
    """``(key, owner dict, field)`` for every example list a level may vary:
    a turn's replies (``examples``) and a convaincre's ``lands_examples``."""

    if isinstance(node, dict):
        if node.get("kind") == "turn" and isinstance(node.get("replies"), list):
            for reply in node["replies"]:
                if isinstance(reply, dict) and reply.get("id"):
                    yield f"{file_id}:{node.get('id')}:{reply['id']}", reply, "examples"
        if node.get("kind") == "solve" and node.get("lands_examples"):
            yield f"{file_id}:{node.get('id')}:lands", node, "lands_examples"
        for value in node.values():
            yield from iter_example_slots(file_id, value)
    elif isinstance(node, list):
        for value in node:
            yield from iter_example_slots(file_id, value)


def read_levels(folder: Path) -> dict[str, Any]:
    """``levels.json`` plus any ``levels_*.json`` shards (merged in name order)."""

    merged: dict[str, Any] = {"lines": {}, "examples": {}}
    for path in sorted(folder.glob("levels*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for key, variants in (payload.get("lines") or {}).items():
            merged["lines"].setdefault(key, {}).update(variants or {})
        merged["examples"].update(payload.get("examples") or {})
    return merged


def apply_levels(raw: Any, levels: dict[str, Any], *, file_id: str) -> Any:
    """Fill the level variants into raw season JSON, in place; returns ``raw``."""

    lines = levels.get("lines") or {}
    for say in iter_says(raw):
        key = level_key(say["a2"], say.get("b1"))
        variants = lines.get(key)
        if not isinstance(variants, dict):
            continue
        for field in VARIANT_FIELDS:
            if not say.get(field) and isinstance(variants.get(field), str) and variants[field].strip():
                say[field] = variants[field].strip()
        native_a1 = variants.get("a1_native")
        if isinstance(native_a1, dict) and not say.get("native_a1"):
            say["native_a1"] = {lang: str(text).strip() for lang, text in native_a1.items() if str(text).strip()}
        say.setdefault("level_src", key)
    examples = levels.get("examples") or {}
    for key, owner, field in iter_example_slots(file_id, raw):
        by_level = examples.get(key)
        if not isinstance(by_level, dict):
            continue
        target = f"{field}_by_level"
        owner.setdefault(target, {})
        for level, values in by_level.items():
            if level in VARIANT_FIELDS and isinstance(values, list):
                owner[target].setdefault(level, [str(value) for value in values if str(value).strip()])
    return raw


TASKS_FILE = "tasks.json"


def read_tasks(folder: Path) -> dict[str, Any]:
    """QA-STORY 2026-10-03: ``tasks.json`` — per turn/solve, keyed ``"<file>:<id>"``:
    ``tasks`` (the plain one-sentence task, en/de/fr) and ``ask_again`` (the
    addressee's line when a reply expresses none of the routes)."""

    path = folder / TASKS_FILE
    if not path.is_file():
        return {"tasks": {}, "ask_again": {}}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {"tasks": dict(payload.get("tasks") or {}), "ask_again": dict(payload.get("ask_again") or {})}


def iter_task_owners(node: Any) -> Iterator[dict[str, Any]]:
    """Every turn and solve in raw season JSON (days, replies' beats and shared blocks)."""

    if isinstance(node, dict):
        if node.get("kind") in ("turn", "solve") and node.get("id"):
            yield node
        for value in node.values():
            yield from iter_task_owners(value)
    elif isinstance(node, list):
        for value in node:
            yield from iter_task_owners(value)


def apply_tasks(raw: Any, overlay: dict[str, Any], *, file_id: str) -> Any:
    """Fold the plain tasks and ask-again lines into raw season JSON, in place."""

    tasks = overlay.get("tasks") or {}
    asks = overlay.get("ask_again") or {}
    for owner in iter_task_owners(raw):
        key = f"{file_id}:{owner['id']}"
        plain = tasks.get(key)
        if isinstance(plain, dict) and not owner.get("task_plain"):
            owner["task_plain"] = {lang: str(text).strip() for lang, text in plain.items() if str(text).strip()}
        ask = asks.get(key)
        if owner.get("kind") == "turn" and isinstance(ask, dict) and not owner.get("ask_again"):
            owner["ask_again"] = {k: str(v).strip() for k, v in ask.items() if str(v).strip()}
    return raw


__all__ = [
    "TASKS_FILE",
    "apply_tasks",
    "iter_task_owners",
    "read_tasks",
    "LEVELS_FILE",
    "VARIANT_FIELDS",
    "apply_levels",
    "is_say",
    "iter_example_slots",
    "iter_says",
    "level_key",
    "read_levels",
]
