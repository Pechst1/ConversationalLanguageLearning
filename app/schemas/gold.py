"""Package O-2 — l'or on screen (``GET /api/v1/gold`` and ``/gold/ledger``)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class GoldEntry(BaseModel):
    """One ledger line as «D'où vient ton or» prints it."""

    id: str
    amount: int
    #: ``pending`` (dashed square) · ``settled`` (filled) · ``void`` (fading).
    state: str
    entry_kind: str
    source_kind: str
    category: str | None = None
    reason_fr: str = ""
    #: The word or the rule the entry paid for, when it has one.
    subject: str | None = None
    delayed_recall: bool = False
    plafond_cut: bool = False
    local_date: str
    created_at: str | None = None
    settled_at: str | None = None
    voided_at: str | None = None
    void_reason: str | None = None


class GoldToday(BaseModel):
    local_date: str
    settled: int
    earn_settled: int
    pending: int
    earned_before_plafond: int
    #: ``open`` · ``half`` (past the full rate) · ``closed`` (the plafond paid all it pays).
    plafond: str
    plafond_full_rate_up_to: int
    plafond_stops_at: int
    rhythm: str
    #: The journée pleine mark of the learner's rhythm.
    mark: int
    pleine: bool


class GoldWeekDay(BaseModel):
    local_date: str
    settled: int
    pleine: bool


class GoldWeek(BaseModel):
    week_id: str
    settled: int
    journees_pleines: int
    journees_pleines_goal: int
    days: list[GoldWeekDay] = Field(default_factory=list)


class GoldView(BaseModel):
    """``visible`` false: l'or is not on this learner's screen yet (nothing else is sent)."""

    visible: bool
    mode: str | None = None
    balance: int | None = None
    today: GoldToday | None = None
    week: GoldWeek | None = None
    #: Today's entries, newest first.
    entries: list[GoldEntry] = Field(default_factory=list)


class GoldLedgerDay(BaseModel):
    local_date: str
    settled: int
    pending: int
    pleine: bool


class GoldLedgerWeek(BaseModel):
    visible: bool
    week_id: str | None = None
    #: Every entry of the week; ``entries`` lists the newest of them.
    entries_total: int | None = None
    settled: int | None = None
    pending: int | None = None
    mark: int | None = None
    days: list[GoldLedgerDay] = Field(default_factory=list)
    entries: list[GoldEntry] = Field(default_factory=list)


__all__ = ["GoldEntry", "GoldLedgerDay", "GoldLedgerWeek", "GoldToday", "GoldView", "GoldWeek", "GoldWeekDay"]
