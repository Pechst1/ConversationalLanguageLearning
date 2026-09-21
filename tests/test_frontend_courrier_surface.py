"""WP-65 — «Le Courrier, surface»: static regression tests over the frontend.

The node suite in `web-frontend/components/courrier/courrier-correspondance.test.js`
renders the components and holds their copy down. What is pinned here is the
*wiring* between WP-64's payload and the four surfaces, because that is what
silently rots: a backend field renamed, a Home row dropped in a merge, or the
deleted readiness tile creeping back in under another name.

No server, no browser: the web preview cannot render an authed route, so these
read the sources (the house pattern — see `test_frontend_serial_surfaces.py`).
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web-frontend"


def read_web(path: str) -> str:
    return (WEB / path).read_text(encoding="utf-8")


def code_only(source: str) -> str:
    """The file without its comments.

    These files explain themselves at length, and several of the sentences a
    surface must never *print* are ones its comments must be free to name — the
    deleted «Prêt pour la vraie vie» tile is the whole point of one of them. A
    forbidden-string scan that reads the prose finds the gravestone and calls it
    the corpse.
    """

    without_blocks = re.sub(r"/\*.*?\*/", " ", source, flags=re.S)
    return re.sub(r"^\s*//.*$", " ", without_blocks, flags=re.M)


def test_courrier_payload_fields_are_typed_and_read() -> None:
    """WP-64's `_courrier_fields` reaches the page, flat and inside `courrier`."""

    api = read_web("services/api.ts")
    for field in (
        "MissionCorrespondent",
        "MissionChain",
        "MissionThreadLetter",
        "MissionCourrier",
        "MissionMeasured",
    ):
        assert f"export interface {field}" in api, field
    # `lapsed` is a real status, not an unknown string falling through.
    assert "'completed' | 'lapsed'" in api
    for field in ("correspondent?:", "chain?:", "expires_at?:", "thread_history?:", "courrier?:"):
        assert field in api, field
    # `outcome` stays inside the block: the top-level key is the legacy serial
    # state delta and is typed as an object.
    assert "outcome?: MissionLetterOutcome | null;" in api

    missions = read_web("pages/missions.tsx")
    assert "const courrier = mission?.courrier || null;" in missions
    assert "mission?.correspondent || courrier?.correspondent" in missions
    assert "mission?.thread_history || courrier?.thread_history" in missions
    assert "courrier?.outcome" in missions


def test_correspondent_view_is_mounted_on_the_courrier() -> None:
    missions = read_web("pages/missions.tsx")
    assert "<CrCorrespondent" in missions
    assert "history={threadHistory}" in missions
    assert "expiresAt={expiresAt}" in missions
    assert "chain={chain}" in missions


def test_the_readiness_tile_is_gone_and_the_honest_debrief_replaced_it() -> None:
    """`readiness.overall` was `55 + words * 0.45` dressed as a percentage."""

    missions = read_web("pages/missions.tsx")
    code = code_only(missions)
    assert "mission.recap.readiness" not in code
    assert "cr-readiness" not in code
    assert "Prêt pour la vraie vie" not in code
    assert "<CrDebrief" in missions
    assert "measured={measured}" in missions
    assert "storySummary={storySummary}" in missions

    correspondance = read_web("components/courrier/Correspondance.tsx")
    assert "recap.measured" in correspondance
    # Nothing on this surface may print a percentage of anything.
    assert "%" not in code_only(correspondance)


def test_a_lapsed_letter_is_never_a_failure_screen() -> None:
    missions = read_web("pages/missions.tsx")
    correspondance = read_web("components/courrier/Correspondance.tsx")
    assert "const lapsed = mission?.status === 'lapsed';" in missions
    # No composer, no ribbon, no situation on a letter that stopped waiting.
    assert "{!completed && !lapsed && (" in missions
    assert "<CrLapsedNotice" in missions
    printed = code_only(correspondance)
    for forbidden in ("échec", "Échec", "vous avez perdu", "Réessayer"):
        assert forbidden not in printed, forbidden


def test_the_soft_deadline_is_a_sentence_not_a_countdown() -> None:
    correspondance = read_web("components/courrier/Correspondance.tsx")
    assert "si vous pouvez" in correspondance
    assert "Répondez avant ${weekday}" in correspondance
    assert "Répondez d’ici demain" in correspondance


def test_home_shows_the_waiting_letter_as_a_quiet_row() -> None:
    """The day's SECOND action: a row in the entries list, never a press."""

    atelier = read_web("pages/atelier.tsx")
    waiting = read_web("components/courrier/courrier-waiting.tsx")
    assert "useCourrierHomeEntry" in atelier
    assert "...(courrierEntry ? [courrierEntry] : [])" in atelier
    # The same entry list as «Votre dossier» — the HomeScreen renders those as
    # `.av2-row` links, so no second primary can appear on La Une.
    assert "const homeEntries: HomeEntry[]" in atelier
    assert "Une lettre vous attend" in waiting
    assert "av2-btn--primary" not in waiting


def test_home_materialises_chain_and_story_born_letters_through_missions_today() -> None:
    """WP-64 opens the day's second letter inside `/missions/today`."""

    waiting = read_web("components/courrier/courrier-waiting.tsx")
    assert "apiService.getMissionsToday()" in waiting
    assert "COURRIER_TODAY_KEY = 'missions/today'" in waiting
    assert "oncePerLoad(COURRIER_TODAY_KEY" in waiting
    # A completed or lapsed letter waits on nobody.
    assert "mission.status === 'available' || mission.status === 'in_progress'" in waiting


def test_the_feuilleton_says_a_story_born_letter_is_waiting() -> None:
    feuilleton = read_web("pages/graphic-novel.tsx")
    waiting = read_web("components/courrier/courrier-waiting.tsx")
    assert "CrStoryLetterRow" in feuilleton
    assert "from '@/components/courrier/courrier-waiting'" in feuilleton
    assert "courrier.origin" in waiting or "courrier?.origin" in waiting
    assert "'story_born'" in waiting


def test_new_courrier_css_is_scoped_and_token_only() -> None:
    """`.av2 .cr-…` is (0,2,0); the legacy `.x-page button` resets are (0,1,1)."""

    correspondance = read_web("components/courrier/Correspondance.tsx")
    block = correspondance.split("export function CourrierCorrespondanceStyles")[1]
    for line in block.splitlines():
        stripped = line.strip()
        if stripped.startswith(".") and "{" in stripped:
            assert stripped.startswith(".av2 .cr-"), stripped
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(", block), "hard-coded colour"
    assert "var(--av2-" in block


def test_the_new_surfaces_have_gallery_specimens() -> None:
    gallery = read_web("pages/atelier-v2-gallery.tsx")
    for component in ("CrCorrespondent", "CrDebrief", "CrLapsedNotice", "CrLetterRow"):
        assert component in gallery, component
