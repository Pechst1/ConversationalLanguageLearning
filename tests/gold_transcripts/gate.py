"""The gold gate: no prompt or model change reaches the learner unless its gold score holds.

Two halves, one free and one paid:

* :func:`fingerprints` renders, for every weekly surface, every model call the
  production code would make on the gold inputs (system prompt, messages, model,
  reasoning effort, temperature, response format, …) with ``render.yaml``'s production
  settings, and hashes them. No key, no call, about five seconds. ``gate.json`` keeps
  the fingerprint each surface last passed the gate with; ``gold_transcripts.py check``
  (in PR CI) fails when the code now renders something else, so any change to what a
  model is asked, or which model is asked, is caught whatever file it was made in.
* ``gold_transcripts.py gate`` (paid, outside CI) runs the changed surfaces twice on the
  same night, once on the base (``origin/main``'s code in a worktree) and once on this
  checkout, both judged on this checkout's sets and criteria, and pairs the answers item
  by item (:func:`compare`). A surface whose paired score falls by more than
  :data:`TOLERANCE` points is blocked; one that holds or rises gets its new fingerprint
  written to ``gate.json``, and that commit is what turns the CI check green.

A fix that claims to improve a surface counts only when its verdict is ``rose``.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from tests.gold_transcripts import runner as R
from tests.gold_transcripts import surfaces as S
from tests.gold_transcripts.criteria import WEEKLY_SURFACES

GATE_FILE = Path(__file__).with_name("gate.json")

#: How far (points, 0–100) a surface's paired score may fall before the change is
#: blocked, and how far it must rise to count as «rose». Provisional: one item of a
#: 24–28 item surface that goes from full marks to a fallback moves it 3.6–4.2 points, so a
#: fall beyond 4 is more than one answer lost. The same-code calibration run
#: (``gate --all --calibrate --base HEAD``, kept in ``gate.json``'s ``calibration``)
#: measures the real noise of models and judge; set this just above its largest
#: difference.
TOLERANCE = 4.0
#: The share of a surface's items that must be scored on both sides; less is «incomplete»
#: (a cap reached, a judge outage) and blocks like a fall.
MIN_COVERAGE = 0.9

#: A side on which more than this share of a surface's items fell back (the model never
#: answered: an expired key, an outage) cannot judge anything: the verdict is «incomplete».
MAX_FALLBACK_SHARE = 0.5

#: «baseline»: the fingerprint main had when the gate started (14 Nov 2026), accepted
#: without a paired run; the next change to that surface runs the gate as usual.
PASSING = ("held", "rose", "baseline")


class _Recorder:
    """A model client that records every call it is asked to make and refuses it: the
    surfaces fall back after their first-attempt calls, and nothing is sent."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Any, dict]] = []

    def _refuse(self, kind: str, messages: Any, kwargs: dict) -> Any:
        from app.services.llm_service import LLMProviderError

        self.calls.append((kind, messages, dict(kwargs)))
        raise LLMProviderError("gold gate fingerprint: not sent")

    def generate_chat_completion(self, messages, **kwargs):
        return self._refuse("chat", messages, kwargs)

    def generate_error_detection(self, messages, **kwargs):
        return self._refuse("error", messages, kwargs)


def _stable(value: Any) -> Any:
    """JSON for what ``json`` cannot write, without memory addresses: a pydantic model's
    schema, else the type's qualified name."""

    schema = getattr(value, "model_json_schema", None)
    if callable(schema):
        try:
            return schema()
        except Exception:  # noqa: BLE001, S110 - an instance, not a class: its dump will do
            pass
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        return dump()
    kind = value if isinstance(value, type) else type(value)
    return f"{kind.__module__}.{kind.__qualname__}"


def surface_calls(surface: str) -> list[dict]:
    """Every first-attempt call ``surface`` makes on its gold inputs, under the
    production profile (the caller applies it)."""

    recorder = _Recorder()
    default = R.Meter(inner=None, cap_usd=0.0)
    for item in S.load_items(surface):
        try:
            S.SURFACES[surface](item, recorder)
        except Exception:  # noqa: BLE001, S110 - a refused call may surface as anything
            pass
    calls = []
    for kind, messages, kwargs in recorder.calls:
        # A call without ``model`` goes to the settings' default: a change there is a model change too.
        kwargs.setdefault("model", default._default_model(kind))
        calls.append({"kind": kind, "messages": messages, "kwargs": kwargs})
    return calls


def fingerprints(surfaces: tuple[str, ...] | list[str] = WEEKLY_SURFACES) -> dict[str, dict]:
    """Per surface: the hash of every call it makes, and how many calls that covers."""

    applied = R.apply_profile()
    try:
        out = {}
        for surface in surfaces:
            calls = surface_calls(surface)
            blob = json.dumps(calls, default=_stable, sort_keys=True, ensure_ascii=False)
            out[surface] = {"fingerprint": hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16], "calls": len(calls)}
        return out
    finally:
        R.restore_profile(applied)


def load_gate(path: Path = GATE_FILE) -> dict:
    if not path.exists():
        return {"surfaces": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def save_gate(gate: dict, path: Path = GATE_FILE) -> None:
    path.write_text(json.dumps(gate, ensure_ascii=False, indent=1, sort_keys=False) + "\n", encoding="utf-8")


def stale(current: dict[str, dict], gate: dict) -> dict[str, str]:
    """Surface → why it must pass the gate again (empty: every surface is gated)."""

    out = {}
    for surface, now in current.items():
        entry = (gate.get("surfaces") or {}).get(surface)
        if not entry:
            out[surface] = "never gated"
        elif entry.get("verdict") not in PASSING:
            out[surface] = f"its last gate verdict is «{entry.get('verdict')}»"
        elif entry.get("fingerprint") != now["fingerprint"]:
            out[surface] = "its prompts or models changed since it last passed"
    return out


def _scored(result: dict, surface: str) -> dict[str, float]:
    return {
        row["id"]: float(row["score"])
        for row in (result.get("items") or {}).get(surface) or []
        if row.get("status") == "scored" and row.get("score") is not None
    }


def compare(base: dict, head: dict, surface: str, *, tolerance: float = TOLERANCE) -> dict:
    """Pair the two runs' answers item by item and give the surface its verdict."""

    a, b = _scored(base, surface), _scored(head, surface)
    fell_back = {
        side: sum(1 for row in (result.get("items") or {}).get(surface) or [] if row.get("failure"))
        for side, result in (("base", base), ("head", head))
    }
    total = max(len((head.get("items") or {}).get(surface) or []), len((base.get("items") or {}).get(surface) or []))
    paired = sorted(set(a) & set(b))
    coverage = len(paired) / total if total else 0.0
    out: dict[str, Any] = {"items": total, "paired": len(paired), "coverage": round(coverage, 3)}
    if not paired:
        out.update(base=None, head=None, diff=None, verdict="incomplete")
        return out
    base_score = 100 * sum(a[i] for i in paired) / len(paired)
    head_score = 100 * sum(b[i] for i in paired) / len(paired)
    diff = head_score - base_score
    if coverage < MIN_COVERAGE or fell_back["base"] > MAX_FALLBACK_SHARE * total:
        # A base that mostly fell back says nothing about the head, even when both read 0.
        verdict = "incomplete"
    elif fell_back["head"] > MAX_FALLBACK_SHARE * total:
        # A head that mostly fell back never passes: a fall when the base answered, else
        # an outage that measured nothing.
        verdict = "fell" if diff < -tolerance else "incomplete"
    elif diff < -tolerance:
        verdict = "fell"
    elif diff > tolerance:
        verdict = "rose"
    else:
        verdict = "held"
    moved = sorted(
        ((round(100 * (b[i] - a[i])), i) for i in paired if abs(b[i] - a[i]) >= 0.2),
        key=lambda pair: pair[0],
    )
    out.update(
        fallbacks=fell_back, base=round(base_score, 1), head=round(head_score, 1), diff=round(diff, 1), verdict=verdict,
        worse=[f"{i} {d:+d}" for d, i in moved if d < 0][:8],
        better=[f"{i} {d:+d}" for d, i in reversed(moved) if d > 0][:8],
    )
    return out


def _fmt(value: float | None) -> str:
    return "–" if value is None else f"{value:.1f}"


def render(rows: dict[str, dict], *, base_ref: str, head_ref: str, spent: float, tolerance: float = TOLERANCE) -> str:
    """The gate's verdict as Markdown, for the PR body."""

    lines = [
        f"### Gold gate: {'passed' if all(r['verdict'] in PASSING for r in rows.values()) else 'blocked'}",
        "",
        f"Paired run on the same inputs: base `{base_ref}` against head `{head_ref}`, "
        f"tolerance {tolerance:g} points, spent US${spent:.2f}.",
        "",
        "| surface | base | head | change | paired | verdict |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for surface, row in rows.items():
        change = "–" if row.get("diff") is None else f"{row['diff']:+.1f}"
        lines.append(
            f"| {surface} | {_fmt(row.get('base'))} | {_fmt(row.get('head'))} | {change} | "
            f"{row['paired']}/{row['items']} | {row['verdict']} |"
        )
    for surface, row in rows.items():
        if row.get("worse") or row.get("better"):
            lines.append("")
            lines.append(f"{surface}: worse {', '.join(row.get('worse') or []) or 'none'}; "
                         f"better {', '.join(row.get('better') or []) or 'none'}")
    return "\n".join(lines)
