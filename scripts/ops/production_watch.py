#!/usr/bin/env python3
"""Production watch: health, worker heartbeat and Render events → one GitHub issue.

#134: the API was OOM-killed on five nights and nobody heard about it until the
next live walk met a 502. This runs every ten minutes from
``.github/workflows/production-watch.yml`` and alerts through a GitHub issue
labelled ``ops-alert`` (GitHub notifies the owner by mail and in the app):

* ``/health`` must answer 200 (three tries, 20 s apart, so a deploy's hand-over
  is not an outage);
* ``/health/worker`` must report a fresh Celery heartbeat;
* with ``RENDER_API_KEY`` set (a repository secret), Render's own service events
  are read too: a server killed for memory or crashed, a failed deploy, memory
  above 90 % of the plan, and a Blueprint whose last sync failed.

Each problem has a stable key. A key is reported once (its marker is written into
the issue), so a 10-minute schedule never repeats itself; the issue is closed with
a short note when every live check is green again. Standard library only: the
workflow runs it without installing anything.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

RENDER_API = "https://api.render.com/v1"
GITHUB_API = "https://api.github.com"
LABEL = "ops-alert"
ISSUE_TITLE = "Production alert"
KEY_MARKER = "<!-- ops-alert-keys:"

#: Render plan → instance memory (MiB); the memory metric is compared against it.
PLAN_MEMORY_MIB = {"starter": 512, "standard": 2048, "pro": 4096, "pro_plus": 8192}

#: Render's memory series carry their unit ("bytes" today; the API docs show "GB").
UNIT_MIB = {
    "bytes": 1 / 1048576, "b": 1 / 1048576,
    "kb": 1000 / 1048576, "kib": 1 / 1024,
    "mb": 1_000_000 / 1048576, "mib": 1.0,
    "gb": 1_000_000_000 / 1048576, "gib": 1024.0,
}


@dataclass(frozen=True)
class Problem:
    key: str
    text: str
    #: Live problems keep the issue open; events (a past kill, a failed deploy) do not.
    live: bool


def http_json(url: str, *, headers: dict[str, str] | None = None, method: str = "GET",
              body: dict | None = None, timeout: int = 30) -> tuple[int, object]:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method=method, headers=headers or {})  # noqa: S310 - fixed http(s) hosts
    if data is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            raw = response.read()
            return response.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read() or b"null")
        except json.JSONDecodeError:
            return exc.code, None
    except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as exc:
        return 0, str(exc)


# --- live checks -------------------------------------------------------------


def check_api(api_url: str, tries: int, pause: float) -> list[Problem]:
    status: int = 0
    for attempt in range(tries):
        status, _ = http_json(f"{api_url}/health", timeout=20)
        if status == 200:
            break
        if attempt + 1 < tries:
            time.sleep(pause)
    if status == 200:
        problems: list[Problem] = []
        worker_status, body = http_json(f"{api_url}/health/worker", timeout=20)
        if worker_status != 200:
            age = body.get("age_seconds") if isinstance(body, dict) else None
            detail = f"last heartbeat {age:.0f} s ago" if isinstance(age, (int, float)) else f"HTTP {worker_status}"
            problems.append(Problem(
                "worker-stale",
                f"The Celery worker is not alive (`/health/worker`: {detail}). Push notifications, "
                "the overnight prefetch and story pictures stop until it is back.",
                live=True,
            ))
        return problems
    shown = f"HTTP {status}" if status else "no answer"
    return [Problem(
        "api-down",
        f"`{api_url}/health` failed {tries} times in a row ({shown}). Learners see «could not be opened».",
        live=True,
    )]


# --- Render ------------------------------------------------------------------


def render_get(path: str, key: str, params: dict[str, str] | None = None) -> object:
    url = f"{RENDER_API}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    status, body = http_json(url, headers={"Authorization": f"Bearer {key}", "Accept": "application/json"})
    if status != 200:
        raise RuntimeError(f"Render API {path} answered {status}")
    return body


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def check_render(key: str, since: datetime) -> list[Problem]:
    problems: list[Problem] = []
    services = [row["service"] for row in render_get("/services", key, {"limit": "50"})]  # type: ignore[index,union-attr]
    for service in services:
        sid, name = service["id"], service["name"]
        events = render_get(f"/services/{sid}/events", key, {"limit": "50"})
        for row in events:  # type: ignore[union-attr]
            event = row["event"]
            when = parse_time(event["timestamp"])
            if when < since:
                continue
            details = event.get("details") or {}
            stamp = when.strftime("%Y-%m-%d %H:%M UTC")
            if event["type"] == "server_failed":
                reason = details.get("reason") or {}
                if reason.get("oomKilled"):
                    limit = reason["oomKilled"].get("memoryLimit", "its memory limit")
                    why = f"killed for running out of memory ({limit})"
                elif reason.get("nonZeroExit") is not None:
                    why = f"crashed (exit {reason['nonZeroExit']})"
                else:
                    why = "failed"
                problems.append(Problem(
                    f"server-failed:{name}:{event['timestamp']}",
                    f"**{name}** was {why} at {stamp}. Render restarts it; the API answers 502 until it is back.",
                    live=False,
                ))
            elif event["type"] == "deploy_ended" and details.get("deployStatus") not in (None, "succeeded"):
                problems.append(Problem(
                    f"deploy-failed:{name}:{details.get('deployId')}",
                    f"**{name}**: deploy {details.get('deployStatus')} at {stamp}; the previous version keeps running.",
                    live=False,
                ))

        plan = (service.get("serviceDetails") or {}).get("plan", "")
        limit_mib = PLAN_MEMORY_MIB.get(plan)
        if limit_mib:
            metrics = render_get("/metrics/memory", key, {
                "resource": sid,
                "startTime": (datetime.now(UTC) - timedelta(minutes=15)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "resolutionSeconds": "60",
            })
            peak_mib = max(
                (value["value"] * UNIT_MIB.get(str(series.get("unit", "bytes")).lower(), UNIT_MIB["bytes"])
                 for series in metrics for value in series.get("values", [])),  # type: ignore[union-attr]
                default=0.0,
            )
            if peak_mib > 0.9 * limit_mib:
                problems.append(Problem(
                    f"memory-high:{name}",
                    f"**{name}** used {peak_mib:.0f} MiB of {limit_mib} MiB ({plan}) in the last 15 minutes; "
                    "above 100 % Render kills it.",
                    live=True,
                ))

    for row in render_get("/blueprints", key, {"limit": "20"}):  # type: ignore[union-attr]
        blueprint = row["blueprint"]
        if blueprint.get("status") == "error":
            problems.append(Problem(
                f"blueprint-error:{blueprint['id']}:{blueprint.get('lastSync')}",
                f"Blueprint **{blueprint['name']}**: the last sync of `{blueprint.get('path')}` failed, so "
                "manifest changes are not reaching Render (Render → Blueprints shows why).",
                live=False,
            ))
    return problems


# --- GitHub issue --------------------------------------------------------------


class Issues:
    def __init__(self, repo: str, token: str) -> None:
        self.base = f"{GITHUB_API}/repos/{repo}"
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def call(self, method: str, path: str, body: dict | None = None, params: dict | None = None) -> object:
        url = f"{self.base}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        status, data = http_json(url, headers=self.headers, method=method, body=body)
        if status >= 300 or status == 0:
            raise RuntimeError(f"GitHub {method} {path} answered {status}: {data}")
        return data

    def open_issue(self) -> dict | None:
        """The current incident, however old: it is never looked up through the history window."""

        rows = self.call("GET", "/issues", params={"labels": LABEL, "state": "open", "per_page": "5"})
        return next((i for i in rows if "pull_request" not in i), None)  # type: ignore[union-attr]

    def recent(self) -> list[dict]:
        since = (datetime.now(UTC) - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
        return list(self.call("GET", "/issues", params={  # type: ignore[arg-type]
            "labels": LABEL, "state": "all", "since": since, "per_page": "20",
        }))

    def reported_keys(self, issues: list[dict]) -> set[str]:
        keys: set[str] = set()
        for issue in issues:
            texts = [issue.get("body") or ""]
            if issue.get("comments"):
                texts += [c.get("body") or "" for c in self.call("GET", f"/issues/{issue['number']}/comments",  # type: ignore[union-attr]
                                                               params={"per_page": "100"})]
            for text in texts:
                for line in text.splitlines():
                    if line.startswith(KEY_MARKER):
                        keys.update(k for k in line[len(KEY_MARKER):].rstrip("->").strip().split() if k)
        return keys


def render_body(problems: list[Problem], owner: str) -> str:
    lines = [f"- {p.text}" for p in problems]
    marker = KEY_MARKER + " " + " ".join(p.key for p in problems) + " -->"
    mention = f"@{owner} " if owner else ""
    return "\n".join([
        f"{mention}Production needs a look:",
        "",
        *lines,
        "",
        "Checked by the production watch (`.github/workflows/production-watch.yml`). "
        "It closes this issue when the live checks are green again.",
        marker,
    ])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--api-url", default=os.environ.get("ATELIER_API_URL", "https://atelier-api-3njh.onrender.com"))
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--owner", default=os.environ.get("ALERT_MENTION", ""))
    # GitHub runs the */10 schedule only every two to five hours (19 Oct: 21:37, 23:40,
    # 01:51, 07:27 UTC), so a kill between runs must still be in the window. Events are
    # reported once across three days of issues, so a long window never repeats one.
    parser.add_argument("--lookback-minutes", type=int, default=12 * 60)
    parser.add_argument("--tries", type=int, default=3)
    parser.add_argument("--pause", type=float, default=20.0)
    parser.add_argument("--dry-run", action="store_true", help="print the problems; touch no issue")
    args = parser.parse_args()

    problems = check_api(args.api_url.rstrip("/"), args.tries, args.pause)
    render_key = os.environ.get("RENDER_API_KEY", "").strip().split(" ")[0]
    if render_key:
        try:
            since = datetime.now(UTC) - timedelta(minutes=args.lookback_minutes)
            problems += check_render(render_key, since)
        except Exception as exc:  # noqa: BLE001 - Render being unreadable is reported, not fatal
            print(f"::warning title=Render API::could not read Render ({exc})")
    else:
        print("RENDER_API_KEY is not set: checking /health and /health/worker only.")

    for problem in problems:
        print(f"[{'live' if problem.live else 'event'}] {problem.key}: {problem.text}")
    if not problems:
        print("All green.")
    if args.dry_run:
        return 0

    token = os.environ.get("GITHUB_TOKEN", "")
    if not (token and args.repo):
        print("::warning::GITHUB_TOKEN or the repository is missing: no issue written.")
        return 0
    issues = Issues(args.repo, token)
    open_issue = issues.open_issue()
    # A live problem (down, stale, memory) is new again once its incident closed;
    # an event (one kill, one failed deploy) is reported once across recent history.
    reported_live = issues.reported_keys([open_issue]) if open_issue else set()
    recent = [i for i in issues.recent() if not open_issue or i["number"] != open_issue["number"]]
    reported_events = reported_live | issues.reported_keys(recent)
    new = [p for p in problems if p.key not in (reported_live if p.live else reported_events)]

    if new:
        body = render_body(new, args.owner)
        if open_issue:
            issues.call("POST", f"/issues/{open_issue['number']}/comments", {"body": body})
            print(f"Commented on #{open_issue['number']} ({len(new)} new).")
        else:
            created = issues.call("POST", "/issues", {"title": ISSUE_TITLE, "body": body, "labels": [LABEL]})
            print(f"Opened #{created['number']}.")  # type: ignore[index]
            open_issue = created  # type: ignore[assignment]
    elif problems:
        print("Nothing new to report.")

    # An issue opened or extended in this run stays open until a later run sees green.
    if open_issue and not new and not any(p.live for p in problems):
        issues.call("POST", f"/issues/{open_issue['number']}/comments", {
            "body": "Green again: `/health` and the worker heartbeat answer normally"
                    + (" and memory is below 90 %." if render_key else ".") + " Closing.",
        })
        issues.call("PATCH", f"/issues/{open_issue['number']}", {"state": "closed", "state_reason": "completed"})
        print(f"Closed #{open_issue['number']}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
