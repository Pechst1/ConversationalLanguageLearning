"""WP-133b walk checks: a generated reaction or ending never agrees with a gender the
learner did not give, and a reaction never hands the learner's own line back.

Reads a day transcript of :mod:`tests.learner_walk`. Only model lines are judged
(``reply_source == "model"``, and the resolution of a day that had one): authored
and bible lines have their own validators. The walk's personas give no gender, so
``transcript["address"]`` defaults to neutral.

Wire into ``tests/walk_checks.CHECKS`` (see the WP-133b lane-fixes report).
"""

from __future__ import annotations

from typing import Any

from app.services import lane_guards


def _label(transcript: dict[str, Any], index: int) -> str:
    return f"{transcript.get('persona')} day {transcript.get('day')} event {index}"


def check_reply_lanes(transcript: dict[str, Any]) -> list[str]:
    """No gendered agreement in a model reaction or its day's ending; no echo."""

    address = transcript.get("address") or "neutral"
    problems: list[str] = []
    learner_texts: list[str] = []
    model_day = False
    for index, event in enumerate(transcript.get("events") or []):
        result = event.get("result") or {}
        text = str(((event.get("answer") or {}).get("input") or {}).get("text") or "")
        if event.get("step", {}).get("kind") != "respond" or not text:
            continue
        learner_texts.append(text)
        if result.get("reply_source") != "model":
            continue
        model_day = True
        reply = str(result.get("character_reply_fr") or "")
        own = lane_guards.learner_own_forms(learner_texts)
        hits = lane_guards.agreement_hits(reply, address, own=own)
        if hits:
            problems.append(f"{_label(transcript, index)}: reaction agrees with an ungiven gender ({hits[0]}): {reply!r}")
        echo = lane_guards.echo_hit(reply, text)
        if echo:
            problems.append(f"{_label(transcript, index)}: reaction echoes the learner ({echo!r}): {reply!r}")
    ending = transcript.get("resolution") or {}
    if model_day:
        own = lane_guards.learner_own_forms(learner_texts)
        for key in ("character_line_fr", "summary_native"):
            hits = lane_guards.agreement_hits(str(ending.get(key) or ""), address, own=own)
            if hits:
                problems.append(
                    f"{transcript.get('persona')} day {transcript.get('day')}: ending {key} agrees "
                    f"with an ungiven gender ({hits[0]}): {ending.get(key)!r}"
                )
    return problems
