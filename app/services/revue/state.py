"""Conversation state: what happened in one Revue (WP-119 §3.3).

An append-only event log kept on the journey row. Nothing in it is regenerated:
reopening a Revue replays these events, and only the next turn is generated. Every
derived view (claims shown, questions, choices, the current artefact, words used
correctly, the guest on stage, support level, turns used, closed) is computed by
replay, never stored beside the log.

Payload conventions the replay reads (other keys are kept and ignored):

- ``claim_shown``: ``claim_id`` or ``claim_ids``
- ``question_raised``: ``text``, ``answerable`` (bool; the dossier could answer it)
- ``guest_enter``: ``id`` (``None`` clears the stage)
- ``evidence``: ``word`` or ``words``, ``correct`` (bool) — the evidence itself is
  written through the existing evidence policy (Credit check, §4.2); this is the record
- ``support_changed``: optional ``level`` (int); without it each event counts one level

No DB code here. See ``docs/implementation/atelier-v2/WP-119-LA-REVUE-DE-ROMY.md``.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

STATE_VERSION = "revue-state-v1"

EventKind = Literal[
    "turn_learner",
    "turn_romy",
    "turn_guest",
    "claim_shown",
    "question_raised",
    "choice",
    "guest_enter",
    "guest_position",
    "artifact",
    "evidence",
    "support_changed",
    "closed",
]


class StateEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seq: int = Field(ge=1)
    at: datetime
    kind: EventKind
    payload: dict[str, Any] = Field(default_factory=dict)


class ConversationState(BaseModel):
    """The Revue's event log and its replayed views (§3.3)."""

    model_config = ConfigDict(extra="forbid")

    state_version: Literal["revue-state-v1"] = STATE_VERSION
    events: list[StateEvent] = Field(default_factory=list)

    @model_validator(mode="after")
    def _monotonic(self) -> ConversationState:
        previous = 0
        for event in self.events:
            if event.seq <= previous:
                raise ValueError(f"event seq {event.seq} does not follow {previous}")
            previous = event.seq
        return self

    # -- writing -----------------------------------------------------------------

    def append(self, kind: EventKind, /, **payload: Any) -> StateEvent:
        """Append one event (next ``seq``, ``at`` = now, UTC) and return it."""

        event = StateEvent(
            seq=(self.events[-1].seq + 1) if self.events else 1,
            at=datetime.now(UTC),
            kind=kind,
            payload=payload,
        )
        self.events.append(event)
        return event

    def to_json(self) -> dict[str, Any]:
        """A JSON-safe dict for the journey row's JSON column."""

        return self.model_dump(mode="json")

    @classmethod
    def from_json(cls, data: dict[str, Any] | str | None) -> ConversationState:
        """Rebuild from :meth:`to_json` output (a dict or its JSON string); ``None`` → empty."""

        if data is None:
            return cls()
        if isinstance(data, str | bytes):
            data = json.loads(data)
        return cls.model_validate(data)

    # -- replay ------------------------------------------------------------------

    def _of(self, *kinds: str) -> list[StateEvent]:
        return [event for event in self.events if event.kind in kinds]

    @property
    def claims_shown(self) -> set[str]:
        shown: set[str] = set()
        for event in self._of("claim_shown"):
            if event.payload.get("claim_id"):
                shown.add(str(event.payload["claim_id"]))
            shown.update(str(claim_id) for claim_id in event.payload.get("claim_ids") or [])
        return shown

    @property
    def questions(self) -> list[dict[str, Any]]:
        return [
            {**event.payload, "answerable": bool(event.payload.get("answerable", False)), "seq": event.seq}
            for event in self._of("question_raised")
        ]

    @property
    def choices(self) -> list[dict[str, Any]]:
        return [{**event.payload, "seq": event.seq} for event in self._of("choice")]

    @property
    def current_artifact(self) -> dict[str, Any] | None:
        artifacts = self._of("artifact")
        return dict(artifacts[-1].payload) if artifacts else None

    @property
    def words_used_correctly(self) -> set[str]:
        words: set[str] = set()
        for event in self._of("evidence"):
            if event.payload.get("correct") is not True:
                continue
            if event.payload.get("word"):
                words.add(str(event.payload["word"]))
            words.update(str(word) for word in event.payload.get("words") or [])
        return words

    @property
    def guest_on_stage(self) -> str | None:
        entries = self._of("guest_enter")
        if not entries:
            return None
        guest = entries[-1].payload.get("id")
        return str(guest) if guest else None

    @property
    def support_level(self) -> int:
        level = 0
        for event in self._of("support_changed"):
            explicit = event.payload.get("level")
            level = explicit if isinstance(explicit, int) and not isinstance(explicit, bool) else level + 1
        return level

    @property
    def turns_used(self) -> int:
        """Learner turns — what the plan's ``budget.turns`` bounds (§5.3)."""

        return len(self._of("turn_learner"))

    @property
    def closed(self) -> bool:
        return bool(self._of("closed"))
