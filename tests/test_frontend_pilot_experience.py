"""Source-level contracts for the pre-pilot learning experience."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "web-frontend"


def _source(relative_path: str) -> str:
    return (FRONTEND / relative_path).read_text(encoding="utf-8")


def test_la_une_leads_with_explained_prescription_without_hiding_edition():
    page = _source("pages/atelier.tsx")
    component = _source("components/atelier-v2/home/HomeScreen.tsx")

    # 2026-09-06: the Claude-design Home keeps one story and one action; the
    # because-line survives as one quiet clause under the action.
    assert "<HomeScreen" in page
    # WP-16 / D-0: the because-line is the legacy primary action's clause and is
    # suppressed with that action when the daily journey owns the day.
    assert "note={journeyOwnsPrimary ? null : prescriptionBecause}" in page
    assert "av2-home__note" in component
    assert "{note}" in component
    assert "Ajuster le temps de l’édition" in component
    # The day's word count moved to the En bref lexique row.
    assert "mots' du jour" not in page
    assert "du jour" in page


def test_audio_primary_action_smart_starts_and_summary_is_honest():
    page = _source("pages/audio-session.tsx")

    assert "onClick={() => void startSession()}" in page
    assert "Choisir une scène" in page
    assert "dueWordsReused" in page
    assert "producedWords" in page
    assert "turns" in page

    # 2026-09-04: the recap counts read as French. The flat "N tours parlés ·
    # ... malgré N fautes de forme" line (which printed "1 tours" and
    # "malgré 0 fautes") is superseded by the plural helper and the
    # no-mistake wording.
    assert "plural(state.turns, 'tour parlé', 'tours parlés')" in page
    assert "communiqué sans faute de forme relevée." in page
    assert "'faute de forme', 'fautes de forme'" in page


def test_audio_call_states_never_lie_or_dead_end():
    page = _source("pages/audio-session.tsx")

    # The kicker states the real stage: a classed call is not "en cours".
    assert "KICKER_BY_STATUS" in page
    assert "ended: 'APPEL CLASSÉ'" in page
    # Screen readers get French, not the internal status key.
    assert "aria-label={state.status}" not in page
    assert "METER_LABEL_BY_STATUS[state.status]" in page
    # A voice that never reports its end must not strand the mic in `speaking`.
    assert "SPEAKING_TIMEOUT_MS" in page
    assert "utterance.onerror = handBack" in page
    # A refused microphone is explained on the page, not only in a toast.
    assert "micError" in page
    # WP-21 moved the mic-denied explanation into the learner-language copy
    # table; the page must resolve it rather than hardcode one language.
    assert "useLearnerLanguage" in page
    assert "mic_denied" in page
    copy = (FRONTEND / "lib" / "atelier-v2-copy.ts").read_text(encoding="utf-8")
    assert "Micro refusé" in copy
    # Classing the call waits for the turn that is already on its way.
    assert "pendingTurnRef" in page
    assert "await pending;" in page
    # Muting must not silence the character outright.
    assert "{(state.showText || isMuted) && state.aiResponse" in page


def test_achievements_have_no_manual_progress_gate():
    """Achievements unlock on their own; no screen may ask a learner to check.

    The `/achievements` page carried this promise until WP-20 deleted it as one
    of the eight off-system legacy screens. The promise outlived the page, so it
    is now asserted against the whole frontend instead of one file: the API call
    survives (`apiService.checkAchievements`, kept per WP-20 "keep every API"),
    but nothing a learner can see may invoke it or offer a manual gate.
    """
    frontend_root = FRONTEND
    assert not (frontend_root / "pages" / "achievements.tsx").exists()

    offenders = []
    for folder in ("pages", "components"):
        for path in (frontend_root / folder).rglob("*.tsx"):
            text = path.read_text(encoding="utf-8")
            if "Check Progress" in text or "checkAchievements" in text:
                offenders.append(str(path.relative_to(frontend_root)))
    assert offenders == []


def test_native_push_routes_taps_back_into_the_product():
    app = _source("pages/_app.tsx")
    native_push = _source("lib/native-push.ts")
    settings = _source("pages/settings.tsx")

    assert "listenForNativePushActions" in app
    assert "router.push(route)" in app
    assert "pushNotificationActionPerformed" in native_push
    assert "route.startsWith('/')" in native_push
    assert "Recevoir l’édition sur cet appareil" in settings
