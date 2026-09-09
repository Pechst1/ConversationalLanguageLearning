"""The generation budget has to hold two attempts, and the window has to clear the
latency actually measured.

Both numbers used to be a comment. On 2026-09-07 the per-call window sat at 25 s while
the scene draft's p95 was 25.0 s, and 8 of 173 paid drafts died on "The read operation
timed out" — tokens billed, no content, one of the two attempts gone. These tests pin
the two properties that failure violated, so the next person to move either number has
to move it deliberately.

The latency figures come from `var/reviews/atelier-longitudinal-*.json`, the five paid
14-day runs. No provider is contacted here.
"""

from __future__ import annotations

import json
import pathlib

from app.config import settings
from app.services import living_story

REVIEWS = pathlib.Path(__file__).resolve().parents[1] / "var" / "reviews"

# The slowest request that ever *completed* in the recorded runs. Anything at or above
# the old 25 s window is censored by that window, so it cannot be used as evidence of
# how long a healthy draft really takes.
SLOWEST_OBSERVED_COMPLETION = 25.0


def test_two_attempts_fit_inside_the_operation_budget() -> None:
    """A window that cannot be spent twice makes the second attempt a lie."""

    attempts = settings.ATELIER_STORY_MAX_ATTEMPTS
    assert attempts >= 2, "the retry that recovers a slow draw needs at least two attempts"
    assert (
        living_story.REQUEST_TIMEOUT_SECONDS * attempts
        <= living_story.OPERATION_BUDGET_SECONDS
    ), (
        f"{attempts} attempts of {living_story.REQUEST_TIMEOUT_SECONDS}s exceed the "
        f"{living_story.OPERATION_BUDGET_SECONDS}s operation budget: the last attempt "
        "would be cut off by the deadline instead of being given its window"
    )


def test_the_window_clears_every_completion_we_have_measured() -> None:
    """The window is a ceiling over real latency, not a slice through it."""

    assert living_story.REQUEST_TIMEOUT_SECONDS > SLOWEST_OBSERVED_COMPLETION, (
        "the per-call window must sit above the slowest completed request, or healthy "
        "generations are killed and paid for"
    )


def test_the_budget_stays_under_the_journey_claim() -> None:
    """The journey promises 90 s; the budget may not quietly outgrow it."""

    assert living_story.OPERATION_BUDGET_SECONDS <= 90


def test_recorded_runs_still_show_no_completion_above_the_window() -> None:
    """If a future run completes slower than the window, this test says so out loud.

    Skipped rather than failed when the reports are absent: they are evidence, not a
    build dependency.
    """

    reports = sorted(REVIEWS.glob("atelier-longitudinal-*.json"))
    if not reports:
        return

    completions: list[float] = []
    timeouts = 0
    for report in reports:
        payload = json.loads(report.read_text(encoding="utf-8"))
        for request in payload.get("requests") or []:
            elapsed = request.get("elapsed_seconds")
            if elapsed is None:
                continue
            if request.get("content"):
                completions.append(elapsed)
            elif "timed out" in str(request.get("error") or ""):
                timeouts += 1

    assert completions, "the recorded runs carry no completed request to measure"
    assert max(completions) < living_story.REQUEST_TIMEOUT_SECONDS, (
        f"a recorded request completed in {max(completions)}s, at or above the "
        f"{living_story.REQUEST_TIMEOUT_SECONDS}s window — raise the window"
    )
    # Documents the defect this change fixes; it is not a threshold to tune.
    assert timeouts > 0, "expected the pre-fix runs to still carry their timeout evidence"
