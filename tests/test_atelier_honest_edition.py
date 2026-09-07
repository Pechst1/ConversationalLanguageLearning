"""Static guards for the honest-edition contract in the Atelier client.

Two promises the session UI must keep, neither of which the backend can enforce
on its own:

1. A drill the learner earned their way out of disappears from the ladder -- the
   adaptive lock has to steer `advanceBaseDrill`, not merely decorate a card.
2. The edition can be closed early. Every classed drill is already banked
   server-side, so refusing to let go of the learner is a bug, not a safeguard.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "web-frontend"


def _source(relative_path: str) -> str:
    return (FRONTEND / relative_path).read_text(encoding="utf-8")


def test_advance_skips_locked_recognize_modes_and_rungs():
    source = _source("pages/atelier.tsx")
    advance = source.split("const advanceBaseDrill = () => {", 1)[1].split("\n  const goNext", 1)[0]
    # The recognition ladder must consult the locks rather than stepping to the
    # next index blindly (the pre-fix behaviour walked into skipped modes).
    assert "lockedRecognizeModes(adaptiveLocks" in advance
    assert "roundIsLocked(adaptiveLocks" in advance
    assert "recognizeModes[modeIndex + 1]" not in advance


def test_drill_counts_exclude_locked_rungs():
    source = _source("pages/atelier.tsx")
    assert "function sessionDrillEntries(" in source
    # Superseded 2026-09-04: a lock retires the rungs still ahead of the learner,
    # never the drills already classed on that rung. Dropping the whole rung took
    # finished items out of the numerator too (24 drills done, "18/25" on the
    # cap) and contradicted the lock's own "N exercice(s) retiré(s)" copy, so the
    # entry list now consults `submitted` and keeps the banked items.
    assert "const modeIsLocked = skippedModes.has(recognizeMode.id);" in source
    assert "if (modeIsLocked && !keepLockedItem(key)) return;" in source
    assert "const transformIsLocked = roundIsLocked(locks, concept.id, 'transform');" in source
    assert "if (transformIsLocked && !keepLockedItem(key)) return;" in source
    # Numerator and denominator must come from the same lock-aware entry list.
    assert "submittedDrills(session, submitted, adaptiveLocks)" in source
    assert "totalDrills(session, adaptiveLocks, submitted)" in source


def test_finish_is_available_once_anything_is_banked():
    source = _source("pages/atelier.tsx")
    assert "finishDisabled={submitting || completedDrills < 1}" in source
    assert "partial={completedDrills < total}" in source
    # The old gate refused to file an incomplete edition at all.
    assert "finishDisabled={submitting || completedDrills < total}" not in source


def test_partial_finish_confirms_once_and_says_so():
    topbar = _source("components/epreuve/Epreuve.tsx")
    assert "partial = false" in topbar
    assert "if (partial && !confirming)" in topbar
    assert "Clore ici ?" in topbar
    recap = _source("pages/atelier.tsx")
    assert "Édition close en avance" in recap


def test_prescription_quotes_the_estimate_not_the_budget():
    page = _source("pages/atelier.tsx")
    # The headline minutes must not be the learner's daily-goal setting.
    assert "const prescribedMinutes = Math.max(1, Number(remainingMinutes || sessionMins || 8));" in page
    assert "overrunMinutes={overBudgetMinutes}" in page
    home = _source("components/atelier-v2/home/HomeScreen.tsx")
    assert "Plus long que les {overrunMinutes} minutes" in home


def test_planned_drills_come_from_the_server_plan():
    page = _source("pages/atelier.tsx")
    assert "sessionNode?.plannedDrills" in page
    assert "const DRILLS_PER_CONCEPT = 15;" in page


def test_lock_copy_reports_the_drills_it_actually_retired():
    epreuve = _source("components/epreuve/Epreuve.tsx")
    assert "retired = 0" in epreuve
    assert "retiré" in epreuve
    # It must not claim a closed concept when only one rung was retired.
    assert "le concept se ferme en avance" not in epreuve
    page = _source("pages/atelier.tsx")
    # The moment reports what it just retired, not the concept's running total.
    assert "retired={Number(activeLock.retired_now ?? activeLock.retired_drills ?? 0)}" in page


def test_studio_is_reachable_from_the_day_plan():
    """The voice loop must be prescribed, not merely present at an unlinked URL."""
    page = _source("pages/atelier.tsx")
    plan = _source("lib/atelier-next.ts")
    assert "| { kind: 'studio' }" in plan
    assert "if (!progress.studioDone && progress.studioSuggested)" in plan
    assert "void router.push('/audio-session');" in page
    # It also has to be offered where the learner just finished speaking practice.
    assert "Ouvrir le studio" in page
    # The day's one action names speaking when the studio is prescribed.
    assert "studioIsPrescribed ? 'Parler'" in page


def test_a_read_episode_no_longer_outranks_the_rest_of_the_plan():
    plan = _source("lib/atelier-next.ts")
    assert "if (serialAction && !serialActionDone) {" in plan
    # The unconditional early return buried review, missions and the studio.
    assert "  if (serialAction) {\n    return serialAction;\n  }\n\n  if (progress.errataDue" not in plan


def test_dead_app_shell_is_gone():
    """Sidebar.tsx linked half the app while being imported by nothing."""
    assert not (FRONTEND / "components" / "layout" / "Sidebar.tsx").exists()
    assert not (FRONTEND / "components" / "layout" / "Navbar.tsx").exists()


def test_backend_never_hands_out_a_retired_frontend_route():
    """A route the API gives a learner must exist in the current product shell.

    `/dashboard` and `/daily-practice` survive only as redirect stubs to
    /atelier, so sending someone there is a pointless bounce; two SRS payloads
    used to do exactly that.
    """
    retired = ("/daily-practice", "/dashboard")
    offenders = []
    for path in (ROOT / "app").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for route in retired:
            if f'"{route}' in text or f"'{route}" in text:
                offenders.append(f"{path.relative_to(ROOT)}:{route}")
    assert offenders == []


def test_reachable_surfaces_carry_no_neo_brutalist_styling():
    """The offset-shadow layer was a second visual language, and it broke dark mode.

    Only surfaces a learner can actually open are asserted here; the unreachable
    /stories, /learn and /sessions cluster is documented in
    docs/design-audit-2026-07-30.md rather than reskinned.
    """
    import re

    reachable = [
        "pages/settings.tsx", "pages/progress.tsx", "pages/achievements.tsx",
        "pages/practice.tsx", "pages/vocabulary.tsx", "pages/vocabulary/review.tsx",
        "pages/auth/signin.tsx", "pages/auth/signup.tsx", "pages/auth/forgot-password.tsx",
        "pages/atelier.tsx", "pages/notebook.tsx",
    ]
    offenders = {}
    for relative in reachable:
        code = re.sub(r"/\*.*?\*/", "", _source(relative), flags=re.S)
        hits = re.findall(
            r"shadow-\[\d+px_\d+px_0|(?:bg|text|border)-(?:gray|black|white|bauhaus)[-\w]*",
            code,
        )
        if hits:
            offenders[relative] = sorted(set(hits))
    assert offenders == {}


def test_journal_surfaces_use_only_the_type_scale():
    """Six steps, in rem, with an 11px floor — no raw px font sizes anywhere."""
    import re

    for relative in [
        "components/laune/LaUne.tsx",
        "components/epreuve/Epreuve.tsx",
        "components/cahiers/Cahiers.tsx",
        "components/courrier/Courrier.tsx",
    ]:
        source = _source(relative)
        assert not re.findall(r"font-size: *[0-9.]+px", source), relative
        assert "font-size: var(--t-" in source or "font-size: var(--av2-t-" in source, relative


def test_component_resets_cannot_outrank_component_classes():
    """Element-scoped resets stripped border/padding/type from chips and rows.

    `.nc button` is class+type and beat `.nc-chip`; wrapping the resets in
    :where() drops them to zero specificity.
    """
    import re

    for relative in [
        "components/laune/LaUne.tsx",
        "components/cahiers/Cahiers.tsx",
        "components/courrier/Courrier.tsx",
    ]:
        source = _source(relative)
        bare = re.findall(r"^\s*\.(?:lu|nc|cr|fe)(?:-embed)? (?:a|button|input|textarea)[ ,{]", source, re.M)
        assert bare == [], f"{relative}: {bare}"
        assert ":where(" in source, relative


def test_cahier_replaces_the_off_system_progress_pages_with_le_releve():
    """2026-08-31 overhaul: the embedded Progrès tab put the pre-journal English
    Anki dashboard (raw stage table, global `vocabulary_words` dump) and an
    "XP Earned" achievements grid inside the French Cahier. Both pages stay
    routable but unlinked; the Cahier's third tab is Le Relevé, which is French
    throughout and reads learner-scoped payloads only."""
    notebook = _source("pages/notebook.tsx")
    cahiers = _source("components/cahiers/Cahiers.tsx")

    # 1. The off-system pages are still not embedded anywhere in the Cahier.
    assert "import ProgressPage from './progress';" not in notebook
    assert "import AchievementsPage from './achievements';" not in notebook
    assert "<ProgressPage embedded />" not in notebook
    assert "<AchievementsPage embedded />" not in notebook
    assert "'progres'" not in cahiers

    # 2. Le Relevé is wired: imported by the shell and offered as a tab.
    assert "import Releve from '@/components/releve/Releve';" in notebook
    assert "<Releve />" in notebook
    assert "{ id: 'releve', label: 'Relevé'" in cahiers
    # Tab order stays Grammaire · Vocabulaire · Relevé (Bibliothèque is flagged).
    assert cahiers.index("id: 'vocabulaire'") < cahiers.index("id: 'releve'")
    assert cahiers.index("id: 'releve'") < cahiers.index("id: 'bibliotheque'")


def test_le_releve_is_french_and_learner_scoped():
    """The replacement surface may not reintroduce what got the old pages parked:
    English chrome, or the global word table read as if it were the learner's."""
    import re

    raw = _source("components/releve/Releve.tsx")
    # The file documents the English dashboard it replaces; only shipped code counts.
    releve = re.sub(r"/\*.*?\*/", "", raw, flags=re.S)

    # French publication furniture, one section head each.
    assert "Le Relevé" in releve
    assert 't="Le cours"' in releve
    assert 't="Le registre"' in releve
    assert 't="La collection"' in releve
    # The honest empty state, not a scoreboard with nothing on it.
    assert "Rien d’accroché encore" in releve
    assert "La collection commence avec la première édition bouclée." in releve

    # The English dashboard vocabulary must not come back.
    for banned in ("Anki Sync", "XP Earned", "No Achievements Yet", "Connect to local Anki"):
        assert banned not in releve, banned

    # Learner-scoped endpoints only: no global `vocabulary_words` dump.
    for banned_call in ("getAnkiProgress", "getAnkiSummary", "api.getVocabulary("):
        assert banned_call not in releve, banned_call
    for expected_call in (
        "api.getCefrProgress()",
        "api.getAnalyticsSummary()",
        "api.getGrammarSummary()",
        "api.getUserAchievements()",
        "api.getAtelierAlmanac()",
    ):
        assert expected_call in releve, expected_call

    # Tokens only, both themes, and every state designed.
    assert not re.findall(r"#[0-9a-fA-F]{3,8}\b", releve)
    assert not re.findall(r"font-size: *[0-9.]+px", releve)
    # Le Relevé is on the Claude design system: its type comes from the
    # `--av2-t-*` tokens in CahierV2.tsx, and every state uses the primitives.
    assert "from '@/components/atelier-v2/ui'" in releve
    assert "<Skeleton" in releve  # loading
    assert "<Notice" in releve or "ArchiveNotice" in releve  # error — notice with Retry
    assert 'tone="empty"' in releve  # empty collection
