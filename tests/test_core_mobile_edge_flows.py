"""Static regression tests for common mobile usage edge cases."""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web-frontend"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_atelier_recovers_from_offline_empty_and_unfinished_states() -> None:
    atelier = read(WEB / "pages" / "atelier.tsx")

    assert "setLoadError('Atelier is unavailable right now." in atelier
    assert "setLoadError('Could not start today’s session." in atelier
    assert "function AtelierLoadNotice" in atelier
    assert "onRetry" in atelier
    assert "Session not ready" in atelier
    assert "const [activeSessionReady, setActiveSessionReady] = useState(false)" in atelier
    assert "setActiveSessionReady(true)" in atelier
    assert "const canStart = activeSessionReady && (hasActiveSession || concepts.length > 0)" in atelier
    assert "disabled={loading || (recommendation.kind === 'start_session' && !canStart)}" in atelier
    assert '<button className="btn solid" type="button" onClick={onRetry}>Retry</button>' in atelier
    assert "toast('This drill is already submitted.')" in atelier
    assert "disabled={submitting || completedDrills < total}" in atelier
    assert "Could not complete the session." in atelier


def test_lean_mission_blocks_empty_messages_and_requires_one_reply_before_finish() -> None:
    missions = read(WEB / "pages" / "missions.tsx")

    assert "const text = reply.trim()" in missions
    assert "if (!mission || !text || submitting || completed) return" in missions
    assert "Message did not send." in missions
    assert "const canSend = reply.trim().length > 0 && !submitting && !completed" in missions
    assert "disabled={!canSend}" in missions
    assert "disabled={completing || !interactionReady}" in missions
    assert "Send first" in missions
    assert "TranslateButton text={translatePrompt} label=\"Translate frame\"" in missions
    assert "TranslateButton text={messenger.opening_message}" in missions
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

    assert "setScene(contextSceneKey ? null : next.active_scene || next.available_scene || null)" in feuilleton
    assert "autoCreateContextRef.current === contextSceneKey" in feuilleton
    assert "Task sheet locked" in feuilleton
    assert "Panel tasks unlock below the episode panels after the edition is generated." in feuilleton
    assert "No scene on the stand." in feuilleton
    assert "disabled={creating}" in feuilleton

    assert "const answer = (answers[taskId] || '').trim()" in feuilleton
    assert "if (!answer)" in feuilleton
    assert "Write or choose an answer first." in feuilleton
    assert "The correction could not be submitted. Try once more." in feuilleton
    assert "const hasPendingTask = Boolean(nextTaskId) && submittedCount < taskCount" in feuilleton
    assert "disabled={!hasPendingTask}" in feuilleton
    assert "const allTasksDone = taskCount === 0 || submittedCount >= taskCount" in feuilleton
    assert "if (!panelCount || !allTasksDone) return null" in feuilleton
    assert "The service did not return a complete Feuilleton." in feuilleton


def test_story_flow_handles_auth_fetch_locked_and_incomplete_chapter_edges() -> None:
    stories = read(WEB / "pages" / "stories.tsx")
    story_detail = read(WEB / "pages" / "stories" / "[storyId].tsx")
    chapter_page = read(WEB / "pages" / "stories" / "[storyId]" / "chapter" / "[chapterId].tsx")
    chapter_progress = read(WEB / "components" / "stories" / "ChapterProgressCard.tsx")
    chapter_timeline = read(WEB / "components" / "stories" / "ChapterTimeline.tsx")

    assert "apiService.get<Story[]>('/stories')" in stories
    assert "useStoryDetail(resolvedStoryId)" in story_detail
    assert "useChapter(resolvedStoryId, resolvedChapterId)" in chapter_page
    assert "const [storyList, setStoryList] = useState(stories)" in stories
    assert "setStoryList([])" in stories
    assert "No Library Texts Available" in stories
    assert "Upload First Book" in stories
    assert "href={isLocked ? '#' : `/story/${story.id}`}" in stories
    assert "disabled={isLocked}" in stories

    assert "Loading story..." in story_detail
    assert "Story not found" in story_detail
    assert "disabled={!user_progress?.current_chapter_id}" in story_detail
    assert "Starting..." in story_detail
    assert "Loading chapter..." in chapter_page
    assert "Starting session..." in chapter_page
    assert "throw new Error('Failed to create session')" in chapter_page
    assert "Chapter not found" in chapter_page
    assert "Back to Story" in chapter_page

    assert "disabled={!canComplete || loading}" in chapter_progress
    assert "Complete more goals to finish" in chapter_progress
    assert "Complete at least" in chapter_progress
    assert "is_locked" in chapter_timeline
    assert "Lock className" in chapter_timeline
    assert "Current Chapter" in chapter_timeline


def test_settings_safety_edges_for_account_and_device_actions() -> None:
    settings = read(WEB / "pages" / "settings.tsx")
    api = read(WEB / "services" / "api.ts")

    assert "await api.getSettings()" in settings
    assert "persistVisualSettings(loadedTheme, loadedFontSize)" in settings
    assert "await api.updateSettings(payload)" in settings
    assert "settingsLoadError" in settings
    assert "Reload settings before saving changes." in settings
    assert "Could not load your saved settings" in settings
    assert "setSaveMessage('Failed to save settings')" in settings

    assert "confirm('Are you ABSOLUTELY sure?" in settings
    assert "await api.deleteAccount()" in settings
    assert "await appSignOut({ callbackUrl: '/' })" in settings
    assert "setSaveMessage('Failed to delete account. Please try again.')" in settings
    assert "passwordForm.newPassword.length < 8" in settings
    assert "Enter your current password and a new password with at least 8 characters." in settings
    assert "await appSignOut({ callbackUrl: '/auth/signin' })" in settings
    assert "confirm('Sign out from every device, including this one?')" in settings
    assert "await api.signOutAllDevices()" in settings
    assert "await api.exportUserData()" in settings

    assert "async changePassword" in api
    assert "async changeEmail" in api
    assert "async exportUserData" in api
    assert "async signOutAllDevices" in api
    assert "async deleteAccount" in api
