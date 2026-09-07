"""WP-16 / decision D-0 — one daily Séance, pinned in the frontend source.

Source-scanning, in the style of the other `test_frontend_*` pins: these assert
the *shape* of the decision, not the styling. The behavioural assertions live in
`web-frontend/lib/atelier-next.test.js` (node) and
`tests/test_wp16_one_evidence_source.py` (backend).
"""
from __future__ import annotations

from pathlib import Path

import pytest

WEB = Path(__file__).resolve().parents[1] / "web-frontend"
RESOLVER = WEB / "lib" / "atelier-next.ts"
HOME_SCREEN = WEB / "components" / "atelier-v2" / "home" / "HomeScreen.tsx"
ATELIER_PAGE = WEB / "pages" / "atelier.tsx"
GRAMMAR_PAGE = WEB / "pages" / "grammar.tsx"
JOURNEY_SESSION = WEB / "components" / "atelier-v2" / "journey" / "JourneySession.tsx"


def _read(path: Path) -> str:
    assert path.exists(), f"missing {path}"
    return path.read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# 1. The resolver
# --------------------------------------------------------------------------

def test_the_resolver_exports_the_practice_entry():
    source = _read(RESOLVER)
    assert "export function resolvePracticeEntry(" in source
    assert "export function practiceHref(" in source
    assert "PRACTICE_LABEL = 'Plus de pratique'" in source


def test_the_legacy_session_can_be_dropped_from_the_primary_chain():
    """With the journey enabled the drill loop is never the day's one action."""

    source = _read(RESOLVER)
    assert "skipSession" in source
    assert "if (!skipSession && progress.sessionStatus === 'active')" in source
    assert "if (!skipSession && progress.sessionStatus === 'none')" in source
    # ... and only when the server says the capability is on.
    assert "if (journeyEnvelope?.enabled === true) {" in source
    assert "skipSession: true" in source


def test_the_practice_entry_is_inert_with_the_capability_off():
    source = _read(RESOLVER)
    body = source.split("export function resolvePracticeEntry(")[1]
    assert "envelope.enabled !== true) return null" in body.split("\n\n")[0] + body[:400]


# --------------------------------------------------------------------------
# 2. Home
# --------------------------------------------------------------------------

def test_the_home_tile_can_carry_one_secondary_line():
    source = _read(HOME_SCREEN)
    assert "secondary?: {" in source
    # The secondary must be a SIBLING of the tile, never nested inside the
    # tile's own button/link.
    assert "av2-day-tile-cell" in source
    assert "av2-day-tile__more" in source
    assert "function DayTileControl(" in source


def test_home_offers_practice_only_as_the_seance_tiles_secondary():
    source = _read(ATELIER_PAGE)
    assert "practiceEntry" in source
    seance_tile = source.split("id: 'seance',")[1].split("id: 'lexique',")[0]
    assert "secondary: practiceEntry" in seance_tile
    # The day's one 3D-press action is still driven by the recommendation, not
    # by the practice entry.
    assert "onSelect: () => onRecommendedAction(recommendation)" in source


# --------------------------------------------------------------------------
# 3. Practice-mode entry
# --------------------------------------------------------------------------

def test_the_drill_loop_is_entered_by_concept_or_by_the_errata_queue():
    source = _read(ATELIER_PAGE)
    assert "String(router.query.mode || '') === 'practice'" in source
    assert "router.query.concept ?? router.query.concept_id" in source
    assert "practiceQueue === 'errata'" in source
    # The header says what this loop is.
    assert "atelier-practice-strip" in source
    assert "practiceConceptTitle" in source


def test_the_cahier_concept_fiche_still_seats_its_concept():
    """«Travailler cette règle à l'Atelier» must carry the rule it is on."""

    source = _read(GRAMMAR_PAGE)
    assert "/atelier?concept_id=${concept.id}" in source


# --------------------------------------------------------------------------
# 4. The recap points into the drill loop
# --------------------------------------------------------------------------

def test_the_recap_points_at_the_servers_own_practice_href():
    source = _read(JOURNEY_SESSION)
    assert "onPractice?: (href: string) => void;" in source
    assert "item.practice_href" in source
    assert "copy.practice_this" in source


@pytest.mark.parametrize("path", [RESOLVER, HOME_SCREEN, ATELIER_PAGE, JOURNEY_SESSION])
def test_every_wp16_edit_says_which_package_it_belongs_to(path: Path):
    assert "WP-16" in _read(path)
