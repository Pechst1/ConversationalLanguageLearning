"""Static regression coverage for the promised phrase on La Une."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ATELIER_PAGE = ROOT / "web-frontend" / "pages" / "atelier.tsx"
LA_UNE = ROOT / "web-frontend" / "components" / "laune" / "LaUne.tsx"
API = ROOT / "web-frontend" / "services" / "api.ts"


def test_la_une_prints_yesterdays_phrase_only_when_present() -> None:
    page = ATELIER_PAGE.read_text(encoding="utf-8")
    component = LA_UNE.read_text(encoding="utf-8")
    api = API.read_text(encoding="utf-8")

    assert "const phraseOfDay = today?.phrase_of_day || null" in page
    assert "{phraseOfDay && (" in page
    assert "<LuPhraseDuJour" in page
    assert 'aria-label="La phrase d’hier"' in component
    assert 'className="paru">Paru' in component
    assert "font-family: var(--serif)" in component
    assert "phrase_of_day?:" in api
