"""Static regression coverage for the promised phrase on La Une."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ATELIER_PAGE = ROOT / "web-frontend" / "pages" / "atelier.tsx"
HOME = ROOT / "web-frontend" / "components" / "atelier-v2" / "home" / "HomeScreen.tsx"
API = ROOT / "web-frontend" / "services" / "api.ts"


def test_la_une_prints_yesterdays_phrase_only_when_present() -> None:
    page = ATELIER_PAGE.read_text(encoding="utf-8")
    component = HOME.read_text(encoding="utf-8")
    api = API.read_text(encoding="utf-8")

    assert "const phraseOfDay = today?.phrase_of_day || null" in page
    assert "phrase={phraseOfDay ?" in page
    assert "<HomeScreen" in page
    # 2026-09-24: the section's name is chrome (one-language rule); the
    # French wording lives in the copy table, the phrase itself stays French.
    assert "aria-label={copy.home_phrase}" in component
    copy = (ROOT / "web-frontend" / "lib" / "atelier-v2-copy.ts").read_text(encoding="utf-8")
    assert "home_phrase: 'La phrase d’hier'" in copy
    # The block only ever renders for a phrase that was published, so the "Paru"
    # badge restated its own precondition and was removed in the density pass.
    assert 'className="paru"' not in component
    # Garamond italic, through the design system's French-text class.
    assert 'className="av2-fr av2-headline av2-headline--rule av2-home__quote"' in component
    assert "phrase_of_day?:" in api
