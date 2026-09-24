"""WP-25 — source-level contracts for the placement's onboarding hand-off.

The backend can be perfectly honest and the package still fail its purpose if
nobody is ever offered the placement. These read the frontend source, because
the preview is auth-gated and none of this is reachable from a browser test.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "web-frontend"


def _source(relative_path: str) -> str:
    return (FRONTEND / relative_path).read_text(encoding="utf-8")


def test_signup_lands_in_the_scene_not_on_the_placement():
    """WP-75 flipped WP-25's hand-off: the placement is never the first task."""
    page = _source("pages/auth/signup.tsx")
    helper = _source("lib/onboarding-signup.ts")
    assert "export const AFTER_SIGNUP_DESTINATION = '/atelier?start=today';" in helper
    # A learner who arrived from a deep link keeps their own destination.
    assert "const landing = afterSignUpDestination(destination);" in page
    # WP-47: the account is signed in with the credentials just typed and sent
    # straight to that landing; the sign-in form is the fallback, address kept.
    assert "auth.signInWithCredentials(payload.email, data.password)" in page
    assert "router.replace(landing);" in page
    assert "query: { callbackUrl: landing, email: payload.email }" in page
    assert "'/placement'" not in page


def test_home_offers_the_placement_only_when_the_server_says_so():
    home = _source("components/atelier-v2/home/HomeScreen.tsx")
    chip = _source("components/onboarding/PlacementOfferChip.tsx")
    assert "<PlacementOfferChip" in home
    assert "'/placement/offer'" in chip
    assert "body?.offer === true" in chip
    assert "Faire le point sur votre niveau" in chip


def test_the_placement_route_exists_and_is_not_public():
    assert (FRONTEND / "pages/placement.tsx").exists()
    gate = _source("components/auth/RouteAuthGate.tsx")
    # Every pathname absent from PUBLIC_PATHNAMES is protected, so the contract
    # is the *absence* of the route from that set.
    assert "'/placement'" not in gate


def _placement_copy() -> str:
    # 2026-09-24: the placement's chrome follows the declared native language;
    # its sentences live in one en/de/fr table and the page reads them by key.
    return _source("lib/placement-copy.ts")


def test_the_offer_is_skippable_and_says_what_skipping_costs():
    page = _source("pages/placement.tsx")
    copy = _placement_copy()
    assert "{copy.skip}" in page
    assert "Passer pour l’instant" in copy and "Not now" in copy
    assert "api.skipPlacement()" in page
    assert "{copy.offer_fine}" in page
    assert "Sans bilan, votre niveau continue de suivre vos scènes." in copy


def test_an_unmeasured_placement_says_so_instead_of_naming_a_level():
    page = _source("pages/placement.tsx")
    assert "status === 'unassessed'" in page
    assert "{copy.unassessed_title}" in page and "{copy.unassessed_lead}" in page
    copy = _placement_copy()
    assert "Niveau non évalué" in copy and "Level not measured" in copy
    assert "nous n’avons rien mesuré" in copy and "we measured nothing" in copy


def test_the_result_is_labelled_as_an_estimate_not_a_verdict():
    page = _source("pages/placement.tsx")
    assert "copy.estimated" in page
    assert "confidenceLabel" in page
    copy = _placement_copy()
    assert "Niveau estimé" in copy and "Estimated level" in copy
    assert "réponses corrigées" in copy


def test_reglages_can_re_run_the_placement():
    page = _source("pages/settings.tsx")
    copy = _source("lib/settings-copy.ts")
    # WP-46: Réglages reads in the learner's own language, so the row's words
    # live in the copy table. The row is pinned by its key on the page and by
    # its three sentences in the table.
    assert "copy.row_placement" in page
    assert "copy.action_placement" in page
    assert "/placement?rerun=1" in page
    for label in ("Level check", "Einstufung", "Bilan de niveau"):
        assert label in copy, label


def test_the_screen_is_on_the_av2_system_and_speaks_french():
    page = _source("pages/placement.tsx")
    assert "AtelierV2Root" in page
    assert "av2-headline" in page
    # No uppercase ink slab, no legacy neo-brutalist chrome.
    assert "neo-" not in page
    assert "text-sm" not in page
    # Learner-facing strings are French. Checked as whole rendered labels
    # rather than substrings: "Continuer" contains "Continue".
    for english in (">Continue<", "Start the test", "Your level is", "Skip for now"):
        assert english not in page


def test_one_primary_action_per_state():
    """The design rule: one `tone="primary"` in each branch of the screen."""
    page = _source("pages/placement.tsx")
    assert page.count('tone="primary"') == 4  # offer, question, unassessed, result


def test_the_client_sends_the_turn_index_so_a_retry_costs_nothing():
    api = _source("services/api.ts")
    assert "respondToPlacement" in api
    assert "turn_index: turnIndex" in api
    assert "'placement' | 'measured'" in api
    assert "placement?: PlacementPrior | null;" in api


# ---------------------------------------------------------------------------
# WP-45 — the screen foot, on `Bilan.dc.html` + canvas note «note-pied».
# ---------------------------------------------------------------------------


def test_the_actions_live_in_a_screen_foot_that_follows_the_body():
    """WP-39's CTA finding: at 390x844 the tab bar is fixed, so a primary action
    that is not *after* the body in the flow ends up under it."""
    page = _source("pages/placement.tsx")
    body = page.index('className="av2-screen__body pl-body"')
    foot = page.index('<ScreenFoot className="pl-foot">')
    assert body < foot, "the foot must come after the body in the DOM"
    # Every state hands its actions to the frame rather than rendering them in
    # the body, and the old in-flow spacer is gone.
    assert page.count("<PlacementFrame\n          foot={") + page.count(
        "<PlacementFrame\n        foot={"
    ) == 4
    assert "pl-spacer" not in page


def test_the_foot_clears_the_phone_tab_bar():
    """Walked in the pane at 390x844: the quiet action ends 48px above the bar.

    The clearance comes from the page frame this route is mounted in, which
    already ends 96px above the viewport floor. The screen must therefore *not*
    reserve the bar's height a second time — doing so pushed the foot back down
    under the bar — and the foot gives back its own safe-area inset, because the
    bar below it owns that inset.
    """
    page = _source("pages/placement.tsx")
    assert "@media (max-width: 760px)" in page
    assert "padding-bottom: var(--phone-bottom-nav-space" not in page
    assert "--av2-safe-bottom: 0px;" in page
    # And the screen is sized by its parent, never by the viewport: 100dvh here
    # is taller than the space left under the masthead.
    assert "min-height: 100%;" in page
    assert "min-height: 100dvh" not in page


def test_the_page_carries_no_hard_coded_colour():
    page = _source("pages/placement.tsx")
    import re

    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", page)
