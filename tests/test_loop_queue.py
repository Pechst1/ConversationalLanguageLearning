"""The night shift's ready-to-merge guard (scripts/loop/loop_queue.py)."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

_PATH = Path(__file__).resolve().parents[1] / "scripts" / "loop" / "loop_queue.py"
_SPEC = importlib.util.spec_from_file_location("loop_queue", _PATH)
assert _SPEC and _SPEC.loader
loop_queue = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(loop_queue)


def _green_pr(**overrides: Any) -> dict[str, Any]:
    pr: dict[str, Any] = {
        "state": "OPEN",
        "isDraft": False,
        "labels": [{"name": "loop:merge-ready"}, {"name": "lane:code"}],
        "headRefName": "claude/night-2026-10-14-115",
        "mergeable": "MERGEABLE",
        "additions": 40,
        "deletions": 10,
        "files": [{"path": "web-frontend/src/components/atelier/Forge.tsx"}],
        "statusCheckRollup": [
            {"__typename": "CheckRun", "name": f"check {i}", "status": "COMPLETED", "conclusion": "SUCCESS"}
            for i in range(6)
        ],
    }
    pr.update(overrides)
    return pr


def test_small_green_code_fix_may_merge() -> None:
    assert loop_queue.merge_blockers(_green_pr()) == []


def test_running_or_failed_checks_block() -> None:
    checks = _green_pr()["statusCheckRollup"]
    checks[0] = {"__typename": "CheckRun", "name": "walk", "status": "IN_PROGRESS", "conclusion": None}
    checks[1] = {"__typename": "CheckRun", "name": "backend", "status": "COMPLETED", "conclusion": "FAILURE"}
    blockers = loop_queue.merge_blockers(_green_pr(statusCheckRollup=checks))
    assert "walk: still running" in blockers
    assert "backend: FAILURE" in blockers


def test_too_few_checks_block() -> None:
    assert any("checks reported" in b for b in loop_queue.merge_blockers(_green_pr(statusCheckRollup=[])))


def test_story_engine_and_owner_paths_block() -> None:
    pr = _green_pr(files=[{"path": "app/services/season/turns.py"}, {"path": ".github/workflows/ci.yml"}])
    assert any("owner-only paths" in b for b in loop_queue.merge_blockers(pr))


def test_owner_review_draft_and_foreign_branch_block() -> None:
    pr = _green_pr(
        isDraft=True,
        headRefName="codex/next",
        labels=[{"name": "loop:merge-ready"}, {"name": "needs-owner-review"}],
    )
    blockers = loop_queue.merge_blockers(pr)
    assert {"draft", "needs-owner-review", "not a night-shift branch"} <= set(blockers)


def test_large_diff_blocks() -> None:
    assert any("changed lines" in b for b in loop_queue.merge_blockers(_green_pr(additions=500)))


def test_rest_pr_reads_like_gh_pr_view(monkeypatch: Any) -> None:
    """Cloud sessions block GraphQL: the REST answers must feed the same guard."""
    pr = {
        "number": 160, "title": "fix", "state": "open", "draft": False, "merged_at": None,
        "labels": [{"name": "loop:merge-ready"}], "head": {"ref": "claude/night-2026-10-16-160", "sha": "abc"},
        "mergeable": True, "additions": 30, "deletions": 5,
    }
    runs = [{"name": f"check {i}", "status": "completed", "conclusion": "success"} for i in range(5)]
    monkeypatch.setattr(loop_queue, "api_json", lambda method, path, body=None: (
        pr if path == "pulls/160" else {"statuses": [{"context": "render", "state": "success"}]}))
    monkeypatch.setattr(loop_queue, "api_list", lambda path, limit=1000: (
        runs if "check-runs" in path else [{"filename": "web-frontend/lib/day-plan.ts"}]))
    rolled = loop_queue.pr_rollup(160)
    assert loop_queue.merge_blockers(rolled) == []
    pr["mergeable"] = False
    runs[0]["conclusion"] = "failure"
    blockers = loop_queue.merge_blockers(loop_queue.pr_rollup(160))
    assert "mergeable=CONFLICTING" in blockers and "check 0: FAILURE" in blockers


def test_label_removal_tolerates_a_missing_label(monkeypatch: Any) -> None:
    def missing(*_: Any, **__: Any) -> str:
        raise SystemExit("gh api DELETE failed: HTTP 404: Label does not exist")
    monkeypatch.setattr(loop_queue, "api", missing)
    loop_queue.remove_label(5, "queue:ready")
