"""The improvement loop's work queue, kept in GitHub issue labels.

The walks file `walk-finding` issues; triage gives each one a state, a lane and a size;
the night shift claims `queue:ready` issues, fixes them on their own branches and opens
PRs; `merge-ready` lists the small code fixes whose checks are all green (the owner merges
them, by hand or with `--merge`); `digest` writes the morning summary. See
docs/ops/improvement-loop.md.

    python scripts/loop/loop_queue.py ensure-labels
    python scripts/loop/loop_queue.py ready [--lane code|story] [--limit N]
    python scripts/loop/loop_queue.py claim N --run RUN
    python scripts/loop/loop_queue.py release N --reason TEXT
    python scripts/loop/loop_queue.py mark-pr N --pr PR
    python scripts/loop/loop_queue.py merge-ready [--merge] [--max N]
    python scripts/loop/loop_queue.py digest --date YYYY-MM-DD

Everything goes through the `gh` CLI with the caller's own login, so a merge made with
`--merge` starts CI on main like any other push (a merge by the Actions token would not,
and Render deploys only once main's checks pass). The night shift itself only lists.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from typing import Any

REPO = os.environ.get("LOOP_REPO", "Pechst1/ConversationalLanguageLearning")

# name -> (colour, description)
LABELS: dict[str, tuple[str, str]] = {
    "queue:ready": ("0e8a16", "Loop queue: reproduced, small, has a done-when check"),
    "queue:working": ("fbca04", "Loop queue: claimed by a night-shift agent"),
    "queue:pr": ("1d76db", "Loop queue: a PR that fixes it is open"),
    "queue:owner": ("d93f0b", "Loop queue: needs a product decision from the owner"),
    "lane:code": ("c5def5", "Fixed in UI/drill/API code; checked by tests and the scripted walk"),
    "lane:story": ("d4c5f9", "Fixed in the story engine; checked by a guard plus a test from the walk's exact text"),
    "size:S": ("ededed", "One focused change, a few files"),
    "size:M": ("bfbfbf", "Several files or one subsystem"),
    "loop:merge-ready": ("0e8a16", "Small code fix the owner may merge as soon as every check is green"),
    "needs-owner-review": ("b60205", "PR changes story behaviour or product copy: owner merges"),
}
STATE_LABELS = ("queue:ready", "queue:working", "queue:pr", "queue:owner")
SEVERITY_ORDER = {"sev:blocker": 0, "sev:high": 1, "sev:medium": 2, "sev:low": 3}

# A PR is listed as ready to merge only when it touches none of these. Story engine, data model,
# deploy and the loop's own rules always wait for the owner.
MERGE_DENY_PREFIXES = (
    ".github/",
    ".claude/",
    "alembic/",
    "app/core/",
    "app/db/",
    "app/services/season/",
    "app/services/living_story",
    "app/services/journey_conversation",
    "scripts/loop/",
    "docs/ops/improvement-loop.md",
    "render.yaml",
    "Dockerfile",
    "docker-compose",
    "requirements",
    "pyproject.toml",
    "web-frontend/package.json",
    "web-frontend/package-lock.json",
    "ios/",
)
MERGE_MAX_LINES = 400
MERGE_MIN_CHECKS = 5
CHECK_OK = {"SUCCESS", "SKIPPED", "NEUTRAL"}


def gh(*args: str, input_text: str | None = None) -> str:
    result = subprocess.run(  # noqa: S603 - fixed gh argv, no shell
        ["gh", *args], capture_output=True, text=True, input=input_text, check=False,  # noqa: S607 - gh from PATH
    )
    if result.returncode != 0:
        raise SystemExit(f"gh {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def gh_json(*args: str) -> Any:
    return json.loads(gh(*args) or "null")


def label_names(item: dict[str, Any]) -> set[str]:
    return {label["name"] for label in item.get("labels", [])}


def set_state(number: int, state: str) -> None:
    """Move an issue to one queue state, removing the others."""
    others = [name for name in STATE_LABELS if name != state]
    gh("issue", "edit", str(number), "-R", REPO, "--add-label", state,
       "--remove-label", ",".join(others))


def ensure_labels() -> None:
    existing = {item["name"] for item in gh_json("label", "list", "-R", REPO, "--limit", "300", "--json", "name")}
    for name, (colour, description) in LABELS.items():
        if name not in existing:
            gh("label", "create", name, "-R", REPO, "--color", colour, "--description", description)
            print(f"created {name}")


def ready_issues(lane: str | None, limit: int) -> list[dict[str, Any]]:
    query = ["issue", "list", "-R", REPO, "--state", "open", "--label", "queue:ready",
             "--limit", "200", "--json", "number,title,labels,createdAt,url"]
    if lane:
        query += ["--label", f"lane:{lane}"]
    issues = gh_json(*query)

    def rank(issue: dict[str, Any]) -> tuple[int, int, str]:
        names = label_names(issue)
        severity = min((SEVERITY_ORDER[n] for n in names if n in SEVERITY_ORDER), default=2)
        size = 0 if "size:S" in names else 1
        return (severity, size, issue["createdAt"])

    issues.sort(key=rank)
    return [
        {
            "number": issue["number"],
            "title": issue["title"],
            "url": issue["url"],
            "labels": sorted(label_names(issue)),
        }
        for issue in issues[:limit]
    ]


def claim(number: int, run: str) -> None:
    issue = gh_json("issue", "view", str(number), "-R", REPO, "--json", "labels,state")
    if issue["state"] != "OPEN" or "queue:ready" not in label_names(issue):
        raise SystemExit(f"#{number} is not queue:ready; not claimed")
    set_state(number, "queue:working")
    gh("issue", "comment", str(number), "-R", REPO, "-b", f"Night shift {run}: working on this.")


def release(number: int, reason: str) -> None:
    set_state(number, "queue:ready")
    gh("issue", "comment", str(number), "-R", REPO, "-b",
       f"Night shift gave this back to the queue: {reason}")


def mark_pr(number: int, pr: int) -> None:
    set_state(number, "queue:pr")
    gh("issue", "comment", str(number), "-R", REPO, "-b", f"Fix proposed in #{pr}.")


def merge_blockers(pr: dict[str, Any]) -> list[str]:
    """Why this PR is not ready to merge; empty means it is."""
    blockers: list[str] = []
    names = label_names(pr)
    if pr.get("state") != "OPEN":
        blockers.append("not open")
    if pr.get("isDraft"):
        blockers.append("draft")
    if "loop:merge-ready" not in names:
        blockers.append("no loop:merge-ready label")
    if "needs-owner-review" in names:
        blockers.append("needs-owner-review")
    if not pr.get("headRefName", "").startswith("claude/night-"):
        blockers.append("not a night-shift branch")
    if pr.get("mergeable") != "MERGEABLE":
        blockers.append(f"mergeable={pr.get('mergeable')}")
    lines = int(pr.get("additions", 0)) + int(pr.get("deletions", 0))
    if lines > MERGE_MAX_LINES:
        blockers.append(f"{lines} changed lines > {MERGE_MAX_LINES}")
    denied = [f["path"] for f in pr.get("files", []) if f["path"].startswith(MERGE_DENY_PREFIXES)]
    if denied:
        blockers.append("touches owner-only paths: " + ", ".join(sorted(denied)[:5]))
    checks = pr.get("statusCheckRollup") or []
    if len(checks) < MERGE_MIN_CHECKS:
        blockers.append(f"only {len(checks)} checks reported")
    for check in checks:
        name = check.get("name") or check.get("context") or "?"
        if check.get("__typename") == "StatusContext":
            if check.get("state") != "SUCCESS":
                blockers.append(f"{name}: {check.get('state')}")
        elif check.get("status") != "COMPLETED":
            blockers.append(f"{name}: still running")
        elif check.get("conclusion") not in CHECK_OK:
            blockers.append(f"{name}: {check.get('conclusion')}")
    return blockers


def merge_ready(limit: int, merge: bool) -> None:
    prs = gh_json("pr", "list", "-R", REPO, "--state", "open", "--label", "loop:merge-ready",
                  "--limit", "50", "--json", "number")
    merged = 0
    for item in prs:
        if merged >= limit:
            print(f"cap {limit} reached; the rest wait for the next run")
            break
        pr = gh_json("pr", "view", str(item["number"]), "-R", REPO, "--json",
                     "number,title,state,isDraft,labels,headRefName,mergeable,additions,"
                     "deletions,files,statusCheckRollup")
        blockers = merge_blockers(pr)
        if blockers:
            print(f"#{pr['number']} waits: {'; '.join(blockers)}")
            continue
        if merge:
            gh("pr", "merge", str(pr["number"]), "-R", REPO, "--squash", "--delete-branch")
            print(f"#{pr['number']} merged: {pr['title']}")
        else:
            print(f"#{pr['number']} ready to merge: {pr['title']}")
        merged += 1


def digest(date: str) -> str:
    def count(label: str) -> list[dict[str, Any]]:
        return gh_json("issue", "list", "-R", REPO, "--state", "open", "--label", label,
                       "--limit", "200", "--json", "number,title")

    ready, working, owner = count("queue:ready"), count("queue:working"), count("queue:owner")
    prs = gh_json("pr", "list", "-R", REPO, "--state", "all", "--search",
                  f"head:claude/night- created:>={date}", "--limit", "50",
                  "--json", "number,title,state,isDraft,labels,url")
    lines = [f"## Night shift · {date}", ""]
    lines.append(f"Queue: {len(ready)} ready · {len(working)} in work · {len(owner)} waiting for you")
    lines.append("")
    if prs:
        lines.append("| PR | state | lane | title |")
        lines.append("|---|---|---|---|")
        for pr in prs:
            names = label_names(pr)
            state = "draft" if pr["isDraft"] else pr["state"].lower()
            lane = "story" if "needs-owner-review" in names else "code"
            auto = " · auto" if "loop:merge-ready" in names else ""
            lines.append(f"| #{pr['number']} | {state}{auto} | {lane} | {pr['title']} |")
    else:
        lines.append("No night-shift PRs tonight.")
    if working:
        lines += ["", "Still claimed (an agent may have stopped): "
                  + ", ".join(f"#{i['number']}" for i in working)]
    if owner:
        lines += ["", "Waiting for your decision:"]
        lines += [f"- #{i['number']} {i['title']}" for i in owner[:15]]
    return "\n".join(lines)


def main(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("ensure-labels")
    p = sub.add_parser("ready")
    p.add_argument("--lane", choices=["code", "story"])
    p.add_argument("--limit", type=int, default=50)
    p = sub.add_parser("claim")
    p.add_argument("number", type=int)
    p.add_argument("--run", required=True)
    p = sub.add_parser("release")
    p.add_argument("number", type=int)
    p.add_argument("--reason", required=True)
    p = sub.add_parser("mark-pr")
    p.add_argument("number", type=int)
    p.add_argument("--pr", type=int, required=True)
    p = sub.add_parser("merge-ready")
    p.add_argument("--max", type=int, default=4)
    p.add_argument("--merge", action="store_true", help="merge them (owner only); default lists")
    p = sub.add_parser("digest")
    p.add_argument("--date", required=True)
    args = parser.parse_args(argv)

    if args.command == "ensure-labels":
        ensure_labels()
    elif args.command == "ready":
        print(json.dumps(ready_issues(args.lane, args.limit), indent=1, ensure_ascii=False))
    elif args.command == "claim":
        claim(args.number, args.run)
    elif args.command == "release":
        release(args.number, args.reason)
    elif args.command == "mark-pr":
        mark_pr(args.number, args.pr)
    elif args.command == "merge-ready":
        merge_ready(args.max, args.merge)
    elif args.command == "digest":
        print(digest(args.date))


if __name__ == "__main__":
    main(sys.argv[1:])
