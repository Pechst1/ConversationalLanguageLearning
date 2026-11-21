"""R2 item 3 (a): the scene's ending is written from the moment the last reply is sent.

Real play (17 Nov) waited 15–30 s on «Wie es weitergeht, wird gerade geschrieben…»
at the end card. The story lane (ending + hook) is queued inside the last reply's
own request and dispatched after its commit — not when the learner taps on to the
end card — so the wait the learner sees is only what is left of the lane after
reading the closing panels (the client: ``r2-finale-closing.test.js``). This pins
that start; it already held before R2 and must keep holding.
"""
from __future__ import annotations

from tests.test_living_story import driver
from tests.test_wp87_lanes import (  # noqa: F401 - pytest fixtures
    _resolution,
    _respond,
    _to_respond,
    assembled_client,
    clock,
    jobs,
    journey_enabled,
    one_exchange,
    provider,
)


def test_story_lane_is_queued_by_the_last_reply_not_by_the_tap_to_the_end(
    assembled_client, db_session, journey_enabled, clock, provider, jobs  # noqa: F811
):
    d = driver(assembled_client, db_session)
    step = _to_respond(d)
    # ``one_exchange`` (WP-87's own fixture): this reply is the scene's last.
    _route, _body, response = _respond(assembled_client, d, step)
    assert response.status_code == 200, response.text

    # The last reply queues the ending itself (dispatched after its commit).
    assert len(jobs) == 1
    assert _resolution(d.journey)["prompt"]["story_pending"] is True

    # Moving on to the end card starts nothing more: the lane is already running.
    d.advance()
    assert len(jobs) == 1
