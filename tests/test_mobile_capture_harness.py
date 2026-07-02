"""Static regressions for the mobile pilot screenshot harness and shell polish."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web-frontend"


def read_web(path: str) -> str:
    return (WEB / path).read_text(encoding="utf-8")


def test_mobile_capture_defaults_to_project_screenshot_folder_and_seeded_account() -> None:
    source = read_web("scripts/capture-mobile-states.mjs")

    assert "docs/pilot-smoke-qa-screenshots" in source
    assert "defaultCaptureDate" in source
    assert "seed_pilot_capture_account.py" in source
    assert "CAPTURE_SEED_PILOT" in source
    assert "pilotSeed" in source
    assert "captureScope: requestedFrames.length ? 'partial' : 'full'" in source
    assert "Unknown capture frame(s)" in source
    assert "1280x800:desktop" in source
    assert "mobile: !desktopLike" in source


def test_mobile_capture_splits_onboarding_from_active_atelier_and_checks_smoke() -> None:
    source = read_web("scripts/capture-mobile-states.mjs")

    assert "name: 'atelier-onboarding'" in source
    assert "waitFor: atelierOnboardingExpression" in source
    assert "name: 'atelier-home-active'" in source
    assert "dismissAtelierOnboardingIfPresent()" in source
    assert "active Atelier capture is occluded by serial onboarding" in source
    assert "duplicate editorial masthead" in source
    assert ".missions-page .mission-error" not in source
    assert "CAPTURE_SKIP_SMOKE_ASSERTIONS" in source


def test_serial_episode_canonical_and_query_routes_are_captured_under_one_shell() -> None:
    capture = read_web("scripts/capture-mobile-states.mjs")
    shell = read_web("lib/product-shell.ts")

    assert "route: '/serial/episode/0'" in capture
    assert "route: '/serial/episode?index=0'" in capture
    assert "name: 'serial-episode-query-detail'" in capture
    assert "'/serial/episode'" in shell
    assert "OWN_SHELL_ROUTES" in shell


def test_polish_fixes_keep_confusing_surfaces_hidden() -> None:
    feedback = read_web("components/feedback/FeedbackWidget.tsx")
    feuilleton = read_web("pages/graphic-novel.tsx")
    settings = read_web("pages/settings.tsx")
    cast = read_web("pages/serial/cast.tsx")

    assert "MessageSquarePlus" in feedback
    assert ">{'!'}</button>" not in feedback
    assert "scene && !scene.serial_thread_id" in feuilleton
    assert "CREATE FIRST SCENE" in feuilleton
    assert "break-all" in settings
    assert "Private model sheet" in cast
    assert "Model sheet asset" not in cast
