"""WP-35 — source-level contracts for «Votre dossier».

The page is auth-gated and the preview cannot render an authenticated route, so
these read the frontend source. They cover the two things a behavioural test on
the state module cannot: that the page is reachable at all, and that the claim
flow never becomes a switch the learner can flip.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "web-frontend"


def _source(relative_path: str) -> str:
    return (FRONTEND / relative_path).read_text(encoding="utf-8")


def test_the_dossier_route_exists_and_is_not_public() -> None:
    assert (FRONTEND / "pages/dossier.tsx").exists()
    gate = _source("components/auth/RouteAuthGate.tsx")
    # Every pathname absent from PUBLIC_PATHNAMES is protected, so the contract
    # is the *absence* of the route from that set. A learner model is the most
    # personal payload in the product.
    assert "'/dossier'" not in gate


def test_reglages_is_the_way_in() -> None:
    page = _source("pages/settings.tsx")
    copy = _source("lib/settings-copy.ts")
    # WP-46: the row's words moved to lib/settings-copy.ts, because Réglages
    # is administrative and reads in the learner's own language.
    assert "copy.row_dossier" in page
    assert "'/dossier'" in page
    for label in ("Your file", "Ihre Akte", "Votre dossier"):
        assert label in copy, label


def test_the_page_states_what_it_believes_and_why() -> None:
    screen = _source("components/atelier-v2/dossier/DossierScreen.tsx")
    for heading in (
        "Votre niveau",
        "Ce que vous savez faire",
        "Vos fautes notées",
        "Vos mots",
        "La scène du jour",
    ):
        assert heading in screen
    # Every belief is printed with the evidence that produced it.
    assert "EvidenceLine" in screen
    assert "evidenceSentence" in screen


def test_the_claim_is_a_check_and_never_a_switch() -> None:
    """«Je connais déjà» must open two questions, not toggle a state."""

    screen = _source("components/atelier-v2/dossier/DossierScreen.tsx")
    page = _source("pages/dossier.tsx")
    assert "Je connais déjà" in screen
    # The claim goes through the check route; there is no client-side path that
    # marks anything known.
    assert "openDossierClaim" in page
    assert "verifyDossierClaim" in page
    for forbidden in ("markKnown", "setKnown", "skipVerification", "trustClaim"):
        assert forbidden not in page
        assert forbidden not in screen


def test_the_client_never_sees_an_accepted_answer() -> None:
    api = _source("services/api.ts")
    start = api.index("export interface DossierClaimItem")
    end = api.index("export interface DossierClaimCheck")
    item = api[start:end]
    assert "accepted" not in item
    assert "solution" not in item


def test_the_no_scene_state_promises_nothing() -> None:
    state = _source("components/atelier-v2/dossier/dossier-state.ts")
    assert "Pas encore de scène aujourd’hui." in state
    # A prospective "today's scene will pick up…" would be a promise the planner
    # has not made (WP-28 open item 5).
    assert "reprendra" not in state
    assert "demain" not in state


def test_the_screen_is_on_the_av2_system_and_speaks_french() -> None:
    page = _source("pages/dossier.tsx")
    screen = _source("components/atelier-v2/dossier/DossierScreen.tsx")
    assert "AtelierV2Root" in page
    assert "av2-headline" in screen
    assert "neo-" not in screen
    assert "text-sm" not in screen
    for english in (">Continue<", "Your level", "I already know", "What we know about you"):
        assert english not in screen
