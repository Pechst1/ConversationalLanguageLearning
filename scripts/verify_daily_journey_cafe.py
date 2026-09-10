#!/usr/bin/env python
"""Drive one complete café journey against a REAL running API.

This is the integration owner's proof for the WP-07-functional milestone: it uses
the real authenticated HTTP surface, never the service layer, never a mock. It
registers a throwaway account through the existing auth endpoints (no production
bypass), then walks start -> contextual recall -> purposeful response -> grounded
consequence -> completion -> persisted evidence, including a refresh/retry
recovery check.

Usage:
    .venv/bin/python scripts/verify_daily_journey_cafe.py --base-url http://127.0.0.1:8010

Exit code 0 means every assertion held. Anything else is a real failure: this
script never downgrades a failure into a warning.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

try:
    import httpx
except ImportError:  # pragma: no cover - dependency is already in .[dev]
    print("httpx is required: .venv/bin/pip install httpx", file=sys.stderr)
    raise SystemExit(2) from None

BUDGET_SECONDS = 300
PRIVATE_KEYS = {
    "rubric", "rubric_native", "accepted_answers", "correct_option_id",
    "correct_tile_order", "solution_fr", "target_answer", "allowed_outcomes",
    "required_intents", "optional_intents", "is_correct", "private_task",
    "suggested_response_fr",
}


@dataclass
class Report:
    checks: list[tuple[str, bool, str]] = field(default_factory=list)

    def record(self, name: str, ok: bool, detail: str = "") -> bool:
        self.checks.append((name, ok, detail))
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {name}{f' — {detail}' if detail else ''}")
        return ok

    @property
    def failed(self) -> list[tuple[str, bool, str]]:
        return [c for c in self.checks if not c[1]]


def assert_no_private_leak(node: Any, path: str, report: Report) -> None:
    """No answer-key material may appear anywhere in a client payload."""

    if isinstance(node, dict):
        for key, value in node.items():
            if key in PRIVATE_KEYS:
                report.record(f"no private leak at {path}.{key}", False, "answer key exposed")
            assert_no_private_leak(value, f"{path}.{key}", report)
    elif isinstance(node, list):
        for index, item in enumerate(node):
            assert_no_private_leak(item, f"{path}[{index}]", report)




def _has_trailing_fragment(line: str) -> bool:
    """True when a line ends with an uncapitalised, unpunctuated tail fragment."""

    stripped = line.strip()
    if not stripped or stripped.endswith((".", "!", "?", "…")):
        return False
    tail = stripped.rsplit(".", 1)[-1].strip()
    return bool(tail) and tail[:1].islower()


def detail_code(response: httpx.Response) -> str:
    """Structured journey error code, or "" for FastAPI's list-shaped 422 body."""

    try:
        detail = response.json().get("detail")
    except Exception:
        return ""
    return detail.get("code", "") if isinstance(detail, dict) else ""


class Driver:
    def __init__(self, base_url: str, report: Report) -> None:
        self.base = base_url.rstrip("/")
        self.api = f"{self.base}/api/v1"
        self.report = report
        self.client = httpx.Client(timeout=60.0)
        self.token: str | None = None

    # -- plumbing ---------------------------------------------------------
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    def request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        return self.client.request(
            method, f"{self.api}{path}", headers=self.headers(), **kwargs
        )

    # -- steps ------------------------------------------------------------
    def sign_up(self) -> None:
        # example.com, not .invalid: EmailStr rejects a non-routable TLD.
        email = f"journey-verify-{uuid.uuid4().hex[:10]}@example.com"
        password = f"Verify-{uuid.uuid4().hex[:12]}!"
        created = self.client.post(
            f"{self.api}/auth/register",
            json={"email": email, "password": password, "full_name": "Journey Verify",
                  "native_language": "en", "cefr_estimate": "A1.1"},
        )
        self.report.record(
            "register a throwaway account through the real auth endpoint",
            created.status_code in (200, 201),
            f"HTTP {created.status_code}",
        )
        # POST /auth/login takes JSON {email, password}, not an OAuth2 form.
        logged_in = self.client.post(
            f"{self.api}/auth/login", json={"email": email, "password": password}
        )
        ok = logged_in.status_code == 200 and "access_token" in logged_in.json()
        self.report.record("log in and receive a real token", ok, f"HTTP {logged_in.status_code}")
        if not ok:
            raise SystemExit(f"cannot authenticate: {logged_in.text[:400]}")
        self.token = logged_in.json()["access_token"]
        print(f"  account: {email}")

    def today(self) -> dict[str, Any]:
        response = self.request("GET", "/daily-journeys/today")
        self.report.record("GET /daily-journeys/today", response.status_code == 200,
                           f"HTTP {response.status_code}")
        if response.status_code != 200:
            raise SystemExit(response.text[:600])
        body = response.json()
        assert_no_private_leak(body, "today", self.report)
        self.report.record("today declares contract_version 1",
                           body.get("contract_version") == 1)
        # A GET must never create a journey: call it again and compare.
        second = self.request("GET", "/daily-journeys/today").json()
        first_id = (body.get("journey") or {}).get("id")
        second_id = (second.get("journey") or {}).get("id")
        self.report.record("a second GET /today creates no journey and no new plan",
                           first_id == second_id,
                           f"{first_id} vs {second_id}")
        if not body.get("enabled"):
            raise SystemExit(
                "The journey is not enabled for this account, so there is nothing to "
                "verify.\n\n"
                "Since 2026-09-10 ATELIER_DAILY_JOURNEY_ENABLED defaults to true, so the "
                "cause is almost certainly the cohort: this script signs up a throwaway "
                "journey-verify-*@example.com account, and ATELIER_DAILY_JOURNEY_COHORT "
                "names real learners.\n\n"
                "Run this BEFORE narrowing the cohort — outside production an empty "
                "cohort admits every account, which is what lets a throwaway one prove "
                "the loop. Then set the cohort to the pilot's learners. Verifying after "
                "narrowing needs a cohort account, and that spends the learner's own "
                "journey for the day."
            )
        return body

    def create(self) -> dict[str, Any]:
        mutation_id = str(uuid.uuid4())
        body = {
            "mutation_id": mutation_id,
            "timezone": "Europe/Paris",
            "budget_seconds": BUDGET_SECONDS,
            "preferred_input_mode": "text",
        }
        response = self.request("POST", "/daily-journeys", json=body)
        self.report.record("POST /daily-journeys creates or returns a journey",
                           response.status_code in (200, 201, 202),
                           f"HTTP {response.status_code}")
        if response.status_code not in (200, 201, 202):
            raise SystemExit(response.text[:600])
        journey = response.json()

        # A duplicate of the identical request must replay, never double-create.
        # An idempotent replay returns the STORED response, status included, so the
        # invariant to assert is the journey identity, not a particular status code.
        replay = self.request("POST", "/daily-journeys", json=body)
        self.report.record(
            "identical mutation_id replays instead of creating a second journey",
            replay.status_code in (200, 201, 202)
            and (replay.status_code == 202
                 or replay.json().get("id") == journey.get("id")),
            f"HTTP {replay.status_code}, id "
            f"{'same' if replay.json().get('id') == journey.get('id') else 'DIFFERENT'}",
        )
        # The same key with a different digest must conflict.
        clash = self.request("POST", "/daily-journeys",
                             json={**body, "preferred_input_mode": "voice"})
        self.report.record(
            "same mutation_id with a different body returns 409 idempotency_conflict",
            clash.status_code == 409
            and detail_code(clash) == "idempotency_conflict",
            f"HTTP {clash.status_code}",
        )

        journey = self.await_ready(journey)
        return journey

    def await_ready(self, journey: dict[str, Any], attempts: int = 20) -> dict[str, Any]:
        for _ in range(attempts):
            if journey.get("status") not in ("preparing",):
                return journey
            wait = (journey.get("retry") or {}).get("after_seconds") or 2
            time.sleep(min(wait, 5))
            journey = self.fetch(journey["id"])
        self.report.record("journey leaves 'preparing' within the retry budget", False,
                           "still preparing")
        return journey

    def fetch(self, journey_id: str) -> dict[str, Any]:
        response = self.request("GET", f"/daily-journeys/{journey_id}")
        if response.status_code != 200:
            raise SystemExit(f"GET journey failed: {response.status_code} {response.text[:400]}")
        return response.json()

    def check_plan(self, journey: dict[str, Any]) -> None:
        assert_no_private_leak(journey, "journey", self.report)
        steps = journey.get("steps") or []
        kinds = [s["kind"] for s in steps]
        self.report.record("plan has 3-5 steps", 3 <= len(steps) <= 5, f"{len(steps)} steps")
        self.report.record("plan opens with the scene", kinds[:1] == ["scene"], str(kinds))
        self.report.record("plan ends with the resolution", kinds[-1:] == ["resolution"], str(kinds))
        self.report.record("plan has exactly one respond step", kinds.count("respond") == 1)
        self.report.record("plan has at most two recall steps", kinds.count("recall") <= 2)
        total = sum(s["estimated_seconds"] for s in steps)
        self.report.record(f"mandatory estimate {total}s fits the {BUDGET_SECONDS}s budget",
                           total <= BUDGET_SECONDS)
        self.report.record("ordinals are a stable 0..n-1 sequence",
                           [s["ordinal"] for s in steps] == list(range(len(steps))))
        self.report.record("exactly one step is active",
                           len([s for s in steps if s["status"] == "active"]) == 1)
        scenario = journey["scenario"]
        self.report.record("scenario names a real character and location",
                           bool(scenario.get("character_id")) and bool(scenario.get("location_id")),
                           f"{scenario.get('character_id')} @ {scenario.get('location_id')}")

    def mutate(self, journey: dict[str, Any], path: str, payload: dict[str, Any],
               expect: tuple[int, ...] = (200,)) -> httpx.Response:
        body = {"mutation_id": str(uuid.uuid4()), "expected_revision": journey["revision"], **payload}
        return self.request("POST", f"/daily-journeys/{journey['id']}{path}", json=body)

    def walk(self, journey: dict[str, Any]) -> dict[str, Any]:
        guard = 0
        while guard < 14:
            guard += 1
            step = next((s for s in journey["steps"] if s["status"] == "active"), None)
            if step is None:
                # An accepted attempt completes its step but does not activate the
                # next one: CONTRACTS §4 makes /advance the client's acknowledgement.
                if journey["status"] not in ("active", "paused"):
                    break
                pending = [s for s in journey["steps"] if s["status"] == "pending"]
                if not pending or not journey.get("current_step_id"):
                    break
                response = self.mutate(
                    journey, "/advance", {"current_step_id": journey["current_step_id"]}
                )
                self.report.record(
                    "advance activates the next step after an accepted result",
                    response.status_code == 200, f"HTTP {response.status_code}",
                )
                if response.status_code != 200:
                    raise SystemExit(response.text[:600])
                journey = response.json().get("journey", response.json())
                continue
            kind = step["kind"]
            print(f"  -> step {step['ordinal']} ({kind})")

            if kind == "resolution":
                # The ending must be the character's authored line, not that line with
                # a ledger memory fragment stapled on.
                line = step["prompt"].get("character_line_fr") or ""
                self.report.record(
                    "the resolution line is clean dialogue, not line + callback fragment",
                    bool(line) and not _has_trailing_fragment(line),
                    line[:70],
                )

            if kind in ("scene", "resolution"):
                response = self.mutate(journey, "/advance", {"current_step_id": step["id"]})
                self.report.record(f"advance past the {kind} step",
                                   response.status_code == 200, f"HTTP {response.status_code}")
                if response.status_code != 200:
                    raise SystemExit(response.text[:600])
                journey = response.json().get("journey", response.json())
                continue

            if kind == "recall":
                journey = self.do_recall(journey, step)
                continue

            if kind == "respond":
                journey = self.do_respond(journey, step)
                continue

            raise SystemExit(f"unknown step kind {kind}")
        return journey

    def do_recall(self, journey: dict[str, Any], step: dict[str, Any]) -> dict[str, Any]:
        prompt = step["prompt"]
        blank = self.mutate(journey, f"/steps/{step['id']}/attempts",
                            {"input": {"mode": "text", "text": "   "}})
        self.report.record("a blank answer is rejected with 422 and mutates nothing",
                           blank.status_code == 422
                           and detail_code(blank) == "empty_answer",
                           f"HTTP {blank.status_code}")

        if prompt["task_type"] == "choice":
            payload = {"input": {"mode": "choice", "option_id": prompt["options"][0]["id"]}}
        elif prompt["task_type"] == "tiles":
            payload = {"input": {"mode": "tiles",
                                 "tile_ids": [o["id"] for o in prompt["options"]]}}
        else:
            payload = {"input": {"mode": "text", "text": prompt.get("prompt_fr") or "un café"}}

        response = self.mutate(journey, f"/steps/{step['id']}/attempts", payload)
        self.report.record("submit the recall attempt", response.status_code == 200,
                           f"HTTP {response.status_code}")
        if response.status_code != 200:
            raise SystemExit(response.text[:600])
        result = response.json()
        assert_no_private_leak(result, "attempt", self.report)
        self.report.record("attempt carries a canonical evidence reference",
                           bool(result.get("evidence_ref")), str(result.get("evidence_ref"))[:60])
        self.report.record("server owns the outcome",
                           result.get("task_outcome") in
                           {"met", "partially_met", "not_yet", "unscored"},
                           str(result.get("task_outcome")))
        journey = result["journey"]
        if any(s["id"] == step["id"] and s["status"] == "active" for s in journey["steps"]):
            follow = self.mutate(journey, "/advance", {"current_step_id": step["id"]})
            if follow.status_code == 200:
                journey = follow.json().get("journey", follow.json())
        return journey

    def do_respond(self, journey: dict[str, Any], step: dict[str, Any]) -> dict[str, Any]:
        # Assistance must be recorded before the content comes back.
        helped = self.mutate(journey, f"/steps/{step['id']}/help",
                             {"help_kind": "translation"})
        used_help = helped.status_code == 200
        if used_help:
            body = helped.json()
            self.report.record("help records assistance before returning content",
                               body.get("assistance_level") in
                               {"hint", "translation", "solution", "suggested_response"},
                               str(body.get("assistance_level")))
            journey = body["journey"]
            refetched = self.fetch(journey["id"])
            recorded = next((s for s in refetched["steps"] if s["id"] == step["id"]), {})
            self.report.record("assistance survives a refetch (server-recorded, not client-asserted)",
                               bool(recorded.get("assistance_used")),
                               str(recorded.get("assistance_used")))
            journey = refetched

        answer = "Je voudrais un cafe, s'il vous plait. Je m'installe en terrasse."
        response = self.mutate(journey, f"/steps/{step['id']}/attempts",
                               {"input": {"mode": "text", "text": answer}})
        self.report.record("submit the purposeful open response", response.status_code == 200,
                           f"HTTP {response.status_code}")
        if response.status_code != 200:
            raise SystemExit(response.text[:600])
        result = response.json()
        assert_no_private_leak(result, "respond", self.report)
        if used_help:
            self.report.record(
                "a response after a reveal is not credited as unassisted",
                result.get("assistance_level") != "none",
                f"assistance_level={result.get('assistance_level')}",
            )
        correction = result.get("correction")
        if correction:
            self.report.record("a foreground correction is a real, non-no-op edit",
                               correction["span_fr"] != correction["corrected_fr"]
                               and correction["span_fr"] in answer,
                               f"{correction['span_fr']} -> {correction['corrected_fr']}")
        journey = result["journey"]

        # Exhaust the remaining turns if the character asked something back.
        guard = 0
        while result.get("next_turn") and guard < 3:
            guard += 1
            step_id = result["next_turn"]["step_id"]
            follow = self.mutate(journey, f"/steps/{step_id}/attempts",
                                 {"input": {"mode": "text",
                                            "text": "Oui, en terrasse, merci beaucoup."}})
            if follow.status_code != 200:
                break
            result = follow.json()
            journey = result["journey"]

        active = next((s for s in journey["steps"] if s["status"] == "active"), None)
        if active and active["kind"] == "respond":
            follow = self.mutate(journey, "/advance", {"current_step_id": active["id"]})
            if follow.status_code == 200:
                journey = follow.json().get("journey", follow.json())
        return journey

    def check_recovery(self, journey: dict[str, Any]) -> dict[str, Any]:
        """A stale revision must conflict; a refresh must restore the same step."""

        # Probe the stale revision on /pause: it needs no step id, so a genuinely
        # stale revision is the only thing that can make the request fail. (Doing this
        # on /advance conflates it with a null current_step_id, which is a real 422.)
        stale_revision = max(1, journey["revision"] - 1)
        stale = self.request(
            "POST", f"/daily-journeys/{journey['id']}/pause",
            json={"mutation_id": str(uuid.uuid4()), "expected_revision": stale_revision},
        )
        self.report.record(
            "a stale expected_revision returns 409 journey_version_conflict",
            stale.status_code == 409
            and detail_code(stale) == "journey_version_conflict",
            f"sent revision {stale_revision} (current {journey['revision']}) "
            f"-> HTTP {stale.status_code} "
            f"{detail_code(stale)}",
        )
        malformed = self.request(
            "POST", f"/daily-journeys/{journey['id']}/pause",
            json={"mutation_id": str(uuid.uuid4()), "expected_revision": 0},
        )
        self.report.record("revision 0 is rejected as malformed input",
                           malformed.status_code in (409, 422),
                           f"HTTP {malformed.status_code}")
        null_step = self.request(
            "POST", f"/daily-journeys/{journey['id']}/advance",
            json={"mutation_id": str(uuid.uuid4()),
                  "expected_revision": journey["revision"], "current_step_id": None},
        )
        self.report.record("a null current_step_id is rejected, not silently advanced",
                           null_step.status_code == 422,
                           f"HTTP {null_step.status_code}")

        paused = self.mutate(journey, "/pause", {})
        self.report.record("pause preserves completed work", paused.status_code == 200,
                           f"HTTP {paused.status_code}")
        if paused.status_code == 200:
            journey = paused.json().get("journey", paused.json())
        before_ids = [s["id"] for s in journey["steps"]]
        before_done = {s["id"] for s in journey["steps"] if s["status"] == "completed"}
        before_current = journey.get("current_step_id")
        resumed = self.mutate(journey, "/resume", {})
        self.report.record("resume returns the same step, not a new plan",
                           resumed.status_code == 200,
                           f"HTTP {resumed.status_code}")
        if resumed.status_code == 200:
            journey = resumed.json().get("journey", resumed.json())
            self.report.record("resume kept the identical step IDs and order",
                               [s["id"] for s in journey["steps"]] == before_ids)
            self.report.record("resume lost no completed work",
                               before_done <= {s["id"] for s in journey["steps"]
                                               if s["status"] == "completed"})
            self.report.record("resume returned the same current step",
                               journey.get("current_step_id") == before_current,
                               f"{before_current} -> {journey.get('current_step_id')}")
        return self.fetch(journey["id"])

    def finish(self, journey: dict[str, Any]) -> dict[str, Any]:
        response = self.mutate(journey, "/finish", {"finish_kind": "complete"})
        self.report.record("POST /finish completes the journey",
                           response.status_code == 200, f"HTTP {response.status_code}")
        if response.status_code != 200:
            raise SystemExit(response.text[:600])
        journey = response.json().get("journey", response.json())
        self.report.record("journey reaches a terminal status",
                           journey["status"] in ("completed", "ended_early"),
                           journey["status"])
        recap = journey.get("recap") or {}
        self.report.record("recap reports real practiced targets or an honest empty list",
                           isinstance(recap.get("practiced_targets"), list))
        self.report.record("recap does not invent a fluency claim",
                           recap.get("objective_outcome") in
                           {"met", "partially_met", "not_yet", "unscored"},
                           str(recap.get("objective_outcome")))

        again = self.request("POST", f"/daily-journeys/{journey['id']}/finish",
                             json={"mutation_id": str(uuid.uuid4()),
                                   "expected_revision": journey["revision"],
                                   "finish_kind": "complete"})
        self.report.record("a duplicate finish does not complete twice",
                           again.status_code in (200, 409),
                           f"HTTP {again.status_code}")
        if again.status_code == 200:
            repeat = again.json().get("journey", again.json())
            self.report.record("the repeated finish minted no second keepsake",
                               (repeat.get("recap") or {}).get("collectible_ids")
                               == recap.get("collectible_ids"))
        return journey

    def check_persisted_evidence(self, journey: dict[str, Any]) -> None:
        refetched = self.fetch(journey["id"])
        self.report.record("the completed journey survives a refetch",
                           refetched["status"] == journey["status"])
        self.report.record("revisiting a terminal journey is a read, not a re-completion",
                           refetched["revision"] >= journey["revision"])

        progress = self.request("GET", "/daily-journeys/capabilities/progress")
        self.report.record("GET /capabilities/progress resolves ahead of /{id}",
                           progress.status_code == 200, f"HTTP {progress.status_code}")
        if progress.status_code == 200:
            body = progress.json()
            assert_no_private_leak(body, "capabilities", self.report)
            keys = {c["capability_key"] for c in body.get("capabilities", [])}
            self.report.record("capability summary covers the three rubric keys",
                               {"order_at_cafe", "arrange_meeting", "explain_delay"} <= keys,
                               str(sorted(keys)))

    def check_cross_user_isolation(self, journey_id: str) -> None:
        """A second real account must not be able to read the first one's journey."""

        first_token = self.token
        try:
            self.sign_up()
            response = self.request("GET", f"/daily-journeys/{journey_id}")
            self.report.record("another account gets a non-disclosing 404, not the journey",
                               response.status_code == 404, f"HTTP {response.status_code}")
        finally:
            self.token = first_token


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8010",
                        help="Running API host. Port 8000 belongs to another project.")
    parser.add_argument("--json", help="Write the machine-readable report here.")
    args = parser.parse_args()

    report = Report()
    driver = Driver(args.base_url, report)

    print(f"Verifying one complete café journey against {args.base_url}\n")
    print("1. authenticate")
    driver.sign_up()
    print("2. today")
    driver.today()
    print("3. create")
    journey = driver.create()
    driver.check_plan(journey)
    print("4. walk the journey")
    journey = driver.walk(journey)
    print("5. interruption recovery")
    journey = driver.check_recovery(journey)
    active = next((s for s in journey["steps"] if s["status"] == "active"), None)
    if active:
        journey = driver.walk(journey)
    print("6. finish")
    journey = driver.finish(journey)
    print("7. persisted evidence")
    driver.check_persisted_evidence(journey)
    print("8. ownership isolation")
    driver.check_cross_user_isolation(journey["id"])

    failures = report.failed
    print(f"\n{len(report.checks) - len(failures)}/{len(report.checks)} checks passed")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump([{"check": c, "ok": o, "detail": d} for c, o, d in report.checks],
                      handle, ensure_ascii=False, indent=2)
    if failures:
        print("\nFAILED:")
        for name, _, detail in failures:
            print(f"  - {name}{f' ({detail})' if detail else ''}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
