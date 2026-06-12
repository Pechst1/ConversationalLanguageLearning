"""Static regression tests for Atelier's visible cross-mode thread handoff."""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ATELIER_PAGE = ROOT / "web-frontend" / "pages" / "atelier.tsx"


def read_atelier() -> str:
    return ATELIER_PAGE.read_text(encoding="utf-8")


def test_atelier_renders_today_practice_thread() -> None:
    source = read_atelier()

    assert "function TodayView" in source
    assert "roadmap-shell" in source
    assert ">Today</span>" in source
    assert 'aria-label="Atelier roadmap"' in source
    assert "Use today&apos;s repairs in a message, conversation, or visual Feuilleton." in source


def test_today_thread_hands_context_to_mission_feuilleton_and_notebook() -> None:
    source = read_atelier()

    assert "function NotebookBridge" in source
    assert "function MissionBridge" in source
    assert "const query = conceptQueryString(concepts)" in source
    assert "const nodes: RoadmapNode[] = [" in source
    assert "serialActionFromToday(today, activeSession)" in source
    assert "const conceptIds = concepts.map((concept) => `concept_id=${concept.id}`).join('&')" in source
    assert "href={`/grammar?concept=${concept.id}`}" in source
    assert "href={`/missions${conceptIds ? `?${conceptIds}` : ''}`}" in source
    assert "href={`/graphic-novel${conceptIds ? `?${conceptIds}` : ''}`}" in source
