"""Static regression tests for common mobile usage edge cases."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web-frontend"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_atelier_recovers_from_offline_empty_and_unfinished_states() -> None:
    atelier = read(WEB / "pages" / "atelier.tsx")

    # The home screen is the Claude-design Home (components/atelier-v2/home);
    # load errors surface as a notice with a Retry, and the start CTA stays
    # disabled until the active session is confirmed.
    assert "function describeAtelierError" in atelier
    assert "setLoadError(describeAtelierError(error, 'load'))" in atelier
    assert "setLoadError(describeAtelierError(error, 'session'))" in atelier
    assert "from '@/components/atelier-v2/home/HomeScreen'" in atelier
    assert "notice={loadError ?" in atelier
    assert "onRetry: onRetry" in atelier
    assert "const [activeSessionReady, setActiveSessionReady] = useState(false)" in atelier
    assert "setActiveSessionReady(true)" in atelier
    assert "const canStart = activeSessionReady && (hasActiveSession || concepts.length > 0)" in atelier
    assert "const seanceDisabled = loading || (!hasActiveSession && !canStart)" in atelier
    assert "toast('Cet exercice est déjà classé.')" in atelier
    # Finish gate lives on the L'Épreuve topbar (EpTopbar finishDisabled prop).
    # It only blocks filing an *empty* edition: a session with classed drills can
    # always be closed early, behind one confirm, because that work is already
    # banked server-side (see tests/test_atelier_honest_edition.py).
    assert "finishDisabled={submitting || completedDrills < 1}" in atelier
    assert "partial={completedDrills < total}" in atelier
    assert "La séance n’a pas pu être terminée." in atelier


def test_lean_mission_blocks_empty_messages_and_requires_one_reply_before_finish() -> None:
    missions = read(WEB / "pages" / "missions.tsx")

    assert "const text = reply.trim()" in missions
    assert "if (!mission || !text || submitting || completed) return" in missions
    # Le Courrier is a French publication surface: the send-failure toast speaks it too.
    assert "Le message n’est pas parti." in missions
    assert "const canSend = reply.trim().length > 0 && !submitting && !completed" in missions
    # "Le Courrier" composer: submit gated by canSend, Terminer gated by interaction.
    assert "canSubmit={canSend}" in missions
    assert "canFinish={interactionReady}" in missions
    assert "finishing={completing}" in missions
    assert "finishLabel=\"Terminer\"" in missions
    # The situation frame + the character opening both carry a translate assist.
    assert "translate={translateFrame}" in missions
    assert "apiService.translateToEnglish(openingMessage)" in missions
    assert "writeLocalDayProgressFlag('missionDone')" in missions


def test_mission_deep_links_preserve_thread_context_and_clear_stale_state() -> None:
    missions = read(WEB / "pages" / "missions.tsx")

    assert "function querySeed" in missions
    assert "conceptIds: queryNumberList(routerQuery.concept_id)" in missions
    assert "vocabularyIds: queryNumberList(routerQuery.vocabulary_id)" in missions
    assert "erratumIds: queryStringList(routerQuery.erratum_id)" in missions
    assert "serialThreadId: firstQuery(routerQuery.serial_thread_id)" in missions
    assert "cadence: nextSeed.atelierSessionId ? 'post_session' : 'ad_hoc'" in missions
    assert "preferred_concept_ids: nextSeed.conceptIds.length ? nextSeed.conceptIds : undefined" in missions
    assert "preferred_errata_ids: nextSeed.erratumIds.length ? nextSeed.erratumIds : undefined" in missions
    assert "preferred_vocabulary_ids: nextSeed.vocabularyIds.length ? nextSeed.vocabularyIds : undefined" in missions
    assert "router.replace({ pathname: '/missions', query: { mission: next.id } }, undefined, { shallow: true })" in missions
    assert "setReply('')" in missions


def test_feuilleton_locks_task_sheet_until_scene_and_requires_real_answers() -> None:
    feuilleton = read(WEB / "pages" / "graphic-novel.tsx")

    assert "setScene(next?.active_scene || next?.available_scene || null)" in feuilleton
    assert "autoCreateContextRef.current === contextSceneKey" in feuilleton
    assert "Feuille de tâches verrouillée" in feuilleton
    assert "Les tâches se déplient sous les planches une fois l’édition composée." in feuilleton
    assert "Aucune scène sur le pupitre." in feuilleton
    assert "disabled={creating || scene.status === 'writing'}" in feuilleton

    assert "const answer = (answers[taskId] || '').trim()" in feuilleton
    assert "if (!answer)" in feuilleton
    assert "Écrivez ou choisissez d’abord une réponse." in feuilleton
    assert "La correction n’a pas pu être transmise. Réessayez." in feuilleton
    assert "setGenerationFailure(null)" in feuilleton
    assert "loaded.status === 'writing' && feuilletonGenerationIsStalled(loaded)" in feuilleton
    assert "scene.status === 'generating' && <EditionArtProgress scene={scene}" in feuilleton
    assert "L’histoire est prête." in feuilleton
    # Reader rebuild: the sticky bar carries no counters — it exposes Quitter plus
    # the single action still due (scrolls to it), so the pin follows that element id.
    assert "<FeuilletonReader" in feuilleton  # the paged reader carries its own sticky nav
    # Reader rebuild: the gated completion card is gone; the episode ends on one
    # action that is only ever "Terminer l'épisode" or the next beat once filed.
    assert "Terminer l’épisode" in feuilleton
    assert "const filed = scene.status === 'completed'" in feuilleton
    assert "La rédaction n’a pas livré un Feuilleton complet." in feuilleton


def test_story_flow_handles_auth_fetch_locked_and_incomplete_chapter_edges() -> None:
    """Every honest edge of the parked reading flow, on the migrated pages.

    WP-20 replaced the `/stories` cluster with the `/bibliotheque` one on the
    Atelier V2 system, which moved these strings from English to French and from
    hand-rolled markup to the design system's own states. Every edge asserted
    here is the same edge — empty shelf, locked text, "loading", "not found",
    "starting", the completion gate and the locked-chapter mark — pinned at its
    new wording. Nothing was dropped: the locked row's disabled state and the
    completion gate are asserted more precisely than before, because the av2
    `Action` separates `disabled` (cannot) from `pending` (in flight).
    """
    stories = read(WEB / "pages" / "bibliotheque.tsx")
    story_detail = read(WEB / "pages" / "bibliotheque" / "[storyId].tsx")
    chapter_page = read(WEB / "pages" / "bibliotheque" / "[storyId]" / "chapter" / "[chapterId].tsx")
    chapter_progress = read(WEB / "components" / "stories" / "ChapterProgressCard.tsx")
    chapter_timeline = read(WEB / "components" / "stories" / "ChapterTimeline.tsx")

    assert "apiService.get<Story[]>('/stories')" in stories
    assert "useStoryDetail(resolvedStoryId)" in story_detail
    assert "useChapter(resolvedStoryId, resolvedChapterId)" in chapter_page
    assert "const [storyList, setStoryList] = useState(stories)" in stories
    assert "setStoryList([])" in stories
    # An empty shelf says so and offers the import, rather than showing nothing.
    assert "L’étagère est encore vide." in stories
    assert "Importer un premier livre" in stories
    # A locked text is inert and reads as locked; it is no longer an <a href="#">.
    assert "disabled={isLocked}" in stories
    assert "/bibliotheque/${story.id}" in stories

    assert "Ouverture du texte…" in story_detail
    assert "Ce texte est introuvable." in story_detail
    assert "disabled={!user_progress?.current_chapter_id}" in story_detail
    assert "Ouverture…" in story_detail
    assert "Ouverture du chapitre…" in chapter_page
    assert "Ouverture de la séance…" in chapter_page
    assert "throw new Error('Failed to create session')" in chapter_page
    assert "Ce chapitre est introuvable." in chapter_page
    assert "Retour au texte" in chapter_page

    assert "disabled={!canComplete}" in chapter_progress
    assert "pending={loading}" in chapter_progress
    assert "Encore quelques objectifs à atteindre" in chapter_progress
    assert "Atteignez au moins" in chapter_progress
    assert "is_locked" in chapter_timeline
    assert "<LockIcon size={14} />" in chapter_timeline
    assert "Chapitre en cours" in chapter_timeline


def test_settings_safety_edges_for_account_and_device_actions() -> None:
    settings = read(WEB / "pages" / "settings.tsx")
    api = read(WEB / "services" / "api.ts")

    assert "await api.getSettings()" in settings
    assert "persistVisualSettings(loadedTheme, loadedFontSize)" in settings
    assert "await api.updateSettings(payload)" in settings
    assert "settingsLoadError" in settings
    assert "Rechargez le dossier avant de classer les modifications." in settings
    assert "Votre dossier n’a pas pu être chargé." in settings
    # Superseded 2026-09-04: the save failure used to be one unconditional
    # generic line, which is how a rejected default_vocab_direction (422 on
    # every save for English natives) stayed invisible. The generic sentence is
    # still the fallback; a 422 now names the fields the API refused.
    assert "'Les modifications n’ont pas pu être classées.'," in settings
    assert "Les modifications n’ont pas pu être classées : ${rejected.join(', ')}." in settings

    assert "confirm('Supprimer définitivement ce compte" in settings
    assert "await api.deleteAccount()" in settings
    assert "await appSignOut({ callbackUrl: '/' })" in settings
    assert "setSaveMessage('Le compte n’a pas pu être supprimé. Réessayez.')" in settings
    assert "passwordForm.newPassword.length < 8" in settings
    assert "Saisissez votre mot de passe actuel et un nouveau mot de passe d’au moins 8 caractères." in settings
    assert "await appSignOut({ callbackUrl: '/auth/signin' })" in settings
    assert "confirm('Fermer toutes les sessions, y compris celle-ci ?')" in settings
    assert "await api.signOutAllDevices()" in settings
    assert "await api.exportUserData()" in settings

    assert "async changePassword" in api
    assert "async changeEmail" in api
    assert "async exportUserData" in api
    assert "async signOutAllDevices" in api
    assert "async deleteAccount" in api
