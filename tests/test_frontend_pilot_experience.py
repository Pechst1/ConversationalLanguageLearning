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
    # WP-82: the studio's chrome follows the one language rule (lib/studio-copy.ts).
    studio = (FRONTEND / "lib" / "studio-copy.ts").read_text(encoding="utf-8")
    assert "{t.choose_scene}" in page
    assert "choose_scene: 'Choisir une scène'" in studio and "choose_scene: 'Choose a scene'" in studio
    assert "dueWordsReused" in page
    assert "producedWords" in page
    assert "turns" in page

    # 2026-09-04: the recap counts read as French. The flat "N tours parlés ·
    # ... malgré N fautes de forme" line (which printed "1 tours" and
    # "malgré 0 fautes") is superseded by the plural helper and the
    # no-mistake wording.
    assert "plural(state.turns, t.turns_one, t.turns_many)" in page
    assert "turns_one: '{n} tour parlé'" in studio and "turns_many: '{n} tours parlés'" in studio
    assert "turns_one: '{n} turn spoken'" in studio
    assert "no_errors: 'sans faute de forme'" in studio
    assert "fillStudio(t.with_errors, { n: state.errors.length })" in page


def test_audio_call_states_never_lie_or_dead_end():
    page = _source("pages/audio-session.tsx")

    # The kicker states the real stage: an ended call is not "en cours".
    # WP-82: the stage words live in lib/studio-copy.ts, in the chrome language.
    studio = (FRONTEND / "lib" / "studio-copy.ts").read_text(encoding="utf-8")
    assert "{t.stage[state.status]}" in page
    # WP-20 D-14: the kicker is sentence case like the rest of the system.
    assert "ended: 'Appel terminé'" in studio and "ended: 'Call ended'" in studio
    assert "APPEL CLASSÉ" not in page
    # Screen readers get words, not the internal status key.
    assert "aria-label={state.status}" not in page
    assert "state.status === 'listening' ? t.your_turn" in page
    # A voice that never reports its end must not strand the mic in `speaking`.
    assert "SPEAKING_TIMEOUT_MS" in page
    assert "utterance.onerror = handBack" in page
    # A refused microphone is explained on the page, not only in a toast.
    assert "micError" in page
    # WP-21 moved the mic-denied explanation into the learner-language copy
    # table; WP-82 resolves it in the page's chrome language.
    assert "useChromeLanguage" in page
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
    # WP-46: the card's title lives in the settings copy table now.
    assert "copy.card_device_title" in settings
    device_copy = _source("lib/settings-copy.ts")
    for title in (
        "Receive the edition on this device",
        "Die Ausgabe auf diesem Gerät empfangen",
        "Recevoir l’édition sur cet appareil",
    ):
        assert title in device_copy, title
