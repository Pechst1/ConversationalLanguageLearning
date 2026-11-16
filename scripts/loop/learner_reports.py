"""Beta: turn the learners' «Something here looks wrong» taps into walk findings.

The app stores each tap as a `looks_wrong` feedback report (category, surface, step kind,
the verdict and the correction the screen showed). This script reads the new ones from the
production API with an owner account and files one `walk-finding` issue per report, so the
learners' reports join the same queue the walks feed.

The repository is public. An issue therefore names the report and its shape (surface, step
kind, verdict, correction kind), never the learner's words or the correction's text: the
exact text is on /pilot-ops («What looked wrong?») behind the owner's role. Each issue goes
to `queue:owner`, because only the owner can read the text and decide what the finding is.

    ATELIER_API_URL=https://<api-host> ATELIER_ADMIN_EMAIL=… ATELIER_ADMIN_PASSWORD=… \\
        python scripts/loop/learner_reports.py [--days 2] [--file]

Without `--file` it prints what it would file. A report is filed once: each issue carries
the marker `learner-report:<id>`, and a report whose marker is already on an issue is skipped.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import loop_queue  # noqa: E402

MARKER = "learner-report:"
LABELS = ["walk-finding", "source:learner", "queue:owner"]
SOURCE_LABEL = ("5319e7", "Filed from a learner's in-app report (the text stays on /pilot-ops)")


def _request(method: str, url: str, body: Any = None, token: str | None = None) -> Any:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method=method)  # noqa: S310 - operator-set host
    request.add_header("Content-Type", "application/json")
    request.add_header("Accept", "application/json")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
        return json.loads(response.read().decode() or "null")


def fetch_reports(api_url: str, email: str, password: str, limit: int = 200) -> list[dict[str, Any]]:
    base = api_url.rstrip("/")
    if not base.endswith("/api/v1"):
        base += "/api/v1"
    token = _request("POST", f"{base}/auth/login", {"email": email, "password": password})["access_token"]
    return _request("GET", f"{base}/feedback/reports?category=looks_wrong&limit={limit}", token=token) or []


def _created(report: dict[str, Any]) -> datetime:
    value = str(report.get("created_at") or "").replace("Z", "+00:00")
    moment = datetime.fromisoformat(value)
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def issue_for(report: dict[str, Any]) -> dict[str, Any]:
    """The issue for one report: its shape only, never the learner's or the correction's text."""

    context = report.get("context_payload") or {}
    correction = context.get("correction") or {}
    surface = str(context.get("surface") or report.get("screen") or report.get("route") or "app")
    step = context.get("step_kind")
    outcome = context.get("outcome")
    kind = correction.get("kind") if isinstance(correction, dict) else None
    short = str(report["id"])[:8]
    where = surface + (f" · {step}" if step else "")
    title = f"Learner report {short}: a {outcome or 'verdict'} on {where} looked wrong"
    lines = [
        f"A beta learner tapped «Something here looks wrong» on {_created(report):%Y-%m-%d %H:%M} UTC.",
        "",
        f"- Surface: `{surface}`",
        f"- Step kind: `{step or 'unknown'}`",
        f"- Verdict: `{outcome or 'unknown'}`",
        f"- Correction kind: `{kind or 'none'}`",
        f"- Learner added a note: {'yes' if report.get('message') else 'no'}",
        "",
        f"The exact text is on /pilot-ops, «What looked wrong?», report `{short}`. It stays out of "
        "this public repository. Triage: read it there, then give this issue a lane, a size, a "
        "**Done when:** comment and `queue:ready`, or close it as not a defect.",
        "",
        f"<!-- {MARKER}{report['id']} -->",
    ]
    return {"title": title, "body": "\n".join(lines) + loop_queue.FOOTER, "labels": LABELS}


def filed_ids() -> set[str]:
    ids: set[str] = set()
    for item in loop_queue.api_list("issues?state=all&labels=source:learner", limit=2000):
        body = item.get("body") or ""
        start = body.find(MARKER)
        if start >= 0:
            ids.add(body[start + len(MARKER):].split(" ", 1)[0].split("-->", 1)[0].strip())
    return ids


def new_reports(reports: list[dict[str, Any]], filed: set[str], *, since: datetime) -> list[dict[str, Any]]:
    fresh = [r for r in reports if str(r.get("id")) not in filed and _created(r) >= since]
    return sorted(fresh, key=_created)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--days", type=int, default=2, help="reports from the last N days (default 2)")
    parser.add_argument("--file", action="store_true", help="create the issues (default: print them)")
    args = parser.parse_args(argv)

    missing = [k for k in ("ATELIER_API_URL", "ATELIER_ADMIN_EMAIL", "ATELIER_ADMIN_PASSWORD") if not os.environ.get(k)]
    if missing:
        print(f"Set {', '.join(missing)}: the reports are read from the API with an owner account.")
        return 2
    reports = fetch_reports(
        os.environ["ATELIER_API_URL"], os.environ["ATELIER_ADMIN_EMAIL"], os.environ["ATELIER_ADMIN_PASSWORD"]
    )
    since = datetime.now(UTC) - timedelta(days=max(1, args.days))
    filed = filed_ids()
    todo = new_reports(reports, filed, since=since)
    if args.file:
        existing = {item["name"] for item in loop_queue.api_list("labels")}
        if "source:learner" not in existing:
            loop_queue.api("POST", "labels", {"name": "source:learner", "color": SOURCE_LABEL[0],
                                              "description": SOURCE_LABEL[1]})
    for report in todo:
        issue = issue_for(report)
        if args.file:
            created = loop_queue.api_json("POST", "issues", issue)
            print(f"filed #{created['number']}: {issue['title']}")
        else:
            print(f"would file: {issue['title']}")
    print(f"{len(todo)} new of {len(reports)} report(s); {len(filed)} filed before.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
