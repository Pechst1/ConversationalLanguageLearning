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


def test_failed_verify_label_blocks() -> None:
    pr = _green_pr(labels=[{"name": "loop:merge-ready"}, {"name": "loop:failed-verify"}])
    assert "failed verify" in loop_queue.merge_blockers(pr)


def test_linked_issues_reads_fixes_part_of_and_refs() -> None:
    body = "Fixes #175\nfixes #88, Part of #143 and refs #197. Not #12 alone. Fixes #175 again."
    assert loop_queue.linked_issues(body) == [175, 88, 143, 197]


class _FakeGitHub:
    """Just enough of the REST API for pr_reject: labels and comments live in dicts."""

    def __init__(self, prior_attempts: int) -> None:
        self.labels: dict[int, set[str]] = {200: {"lane:code", "loop:merge-ready"}, 197: {"queue:pr"}}
        self.comments: dict[int, list[str]] = {
            197: [f"{loop_queue.REJECTED_MARK} {i + 1} (#1) failed review." for i in range(prior_attempts)]}
        self.closed: list[int] = []

    def api(self, method: str, path: str, body: Any = None, accept: str | None = None) -> str:
        number = int(path.split("/")[1])
        if method == "POST" and path.endswith("/labels"):
            self.labels.setdefault(number, set()).update(body["labels"])
        elif method == "DELETE" and "/labels/" in path:
            self.labels[number].discard(path.rsplit("/", 1)[1].replace("%3A", ":"))
        elif method == "POST" and path.endswith("/comments"):
            self.comments.setdefault(number, []).append(body["body"])
        elif method == "PATCH" and path.startswith("pulls/"):
            self.closed.append(number)
        return "{}"

    def api_json(self, method: str, path: str, body: Any = None) -> Any:
        number = int(path.split("/")[1])
        if path.startswith("pulls/"):
            return {"number": number, "body": "Fixes #197\nFixes #175", "head": {"ref": "claude/night-x-197"}}
        if number == 175:
            return {"number": 175, "state": "closed", "labels": []}
        return {"number": number, "state": "open", "labels": [{"name": n} for n in self.labels[number]]}

    def api_list(self, path: str, limit: int = 1000) -> list[dict[str, Any]]:
        return [{"body": b} for b in self.comments.get(int(path.split("/")[1]), [])]


def _reject(monkeypatch: Any, prior_attempts: int) -> _FakeGitHub:
    gh = _FakeGitHub(prior_attempts)
    for name in ("api", "api_json", "api_list"):
        monkeypatch.setattr(loop_queue, name, getattr(gh, name))
    loop_queue.pr_reject(200, "The test passes without the fix.")
    return gh


def test_rejected_pr_closes_and_its_issue_goes_back_with_the_notes(monkeypatch: Any) -> None:
    gh = _reject(monkeypatch, prior_attempts=0)
    assert gh.closed == [200]
    assert "loop:failed-verify" in gh.labels[200] and "loop:merge-ready" not in gh.labels[200]
    assert "queue:ready" in gh.labels[197] and "queue:pr" not in gh.labels[197]
    assert "The test passes without the fix." in gh.comments[197][-1]
    assert "claude/night-x-197" in gh.comments[197][-1]


def test_second_rejection_hands_the_issue_to_the_owner(monkeypatch: Any) -> None:
    gh = _reject(monkeypatch, prior_attempts=1)
    assert "queue:owner" in gh.labels[197] and "queue:ready" not in gh.labels[197]
    assert "waits for the owner" in gh.comments[197][-1]


def test_nothing_merges_onto_a_red_main(monkeypatch: Any, capsys: Any) -> None:
    merged: list[str] = []
    monkeypatch.setattr(loop_queue, "api_list", lambda path, limit=1000: [
        {"number": 160, "labels": [{"name": "loop:merge-ready"}]}])
    monkeypatch.setattr(loop_queue, "main_is_green", lambda: (False, "main CI abc1234: failure"))
    monkeypatch.setattr(loop_queue, "pr_rollup", lambda n: {**_green_pr(), "number": n, "title": "fix"})
    monkeypatch.setattr(loop_queue, "api", lambda method, path, body=None, accept=None: merged.append(path) or "")
    loop_queue.merge_ready(4, merge=True)
    assert merged == []
    out = capsys.readouterr().out
    assert "nothing merged: main CI abc1234: failure" in out and "#160 ready to merge" in out
