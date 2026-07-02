"""Static regression tests for the highest-value mobile user flows."""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web-frontend"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_public_onboarding_moves_from_minimal_account_creation_to_daily_atelier() -> None:
    home = read(WEB / "pages" / "index.tsx")
    signin = read(WEB / "pages" / "auth" / "signin.tsx")
    signup = read(WEB / "pages" / "auth" / "signup.tsx")
    forgot = read(WEB / "pages" / "auth" / "forgot-password.tsx")
    app_auth = read(WEB / "lib" / "app-auth.tsx")
    route_gate = read(WEB / "components" / "auth" / "RouteAuthGate.tsx")

    assert "if (status === 'authenticated')" in home
    assert "router.push('/atelier')" in home
    assert '<Link href="/auth/signin">Sign in</Link>' in home
    assert '<Link className="public-start" href="/auth/signup">Start</Link>' in home

    assert "sanitizeAuthCallbackUrl(router.query.callbackUrl)" in signin
    assert "const forgotPasswordHref = { pathname: '/auth/forgot-password', query: callbackQuery }" in signin
    assert "auth.signInWithCredentials" in signin
    assert "router.push(destination)" in signin
    assert "sanitizeAuthCallbackUrl(router.query.callbackUrl)" in forgot
    assert "const signInHref = { pathname: '/auth/signin', query: callbackQuery }" in forgot
    assert "href={signInHref}" in forgot
    assert "hasSessionRefreshError(sessionData)" in app_auth
    assert "const effectiveStatus: AppAuthStatus = refreshFailed ? 'unauthenticated' : nextSession.status" in app_auth
    assert "'/auth/forgot-password'" in route_gate
    assert "sanitizeAuthCallbackUrl(router.asPath)" in route_gate

    assert "Password must be at least 8 characters" in signup
    assert "function authErrorMessage" in signup
    assert "Array.isArray(detail)" in signup
    assert "defaultValues" in signup
    assert "nativeLanguage: 'en'" in signup
    assert "targetLanguage: 'fr'" in signup
    assert "proficiencyLevel: 'A1'" in signup
    assert "<details className=\"profile-details\">" in signup
    assert "apiService.register" in signup
    assert "full_name: data.name" in signup
    assert "interests: selectedTopics.join(',')" in signup
    assert "router.push({ pathname: '/auth/signin', query: callbackQuery })" in signup


def test_phone_shell_keeps_the_primary_product_modes_simple_and_reachable() -> None:
    shell = read(WEB / "lib" / "product-shell.ts")
    flags = read(WEB / "launch-flags.json")
    masthead = read(WEB / "components" / "layout" / "EditorialMasthead.tsx")
    phone_nav = read(WEB / "components" / "layout" / "PhoneProductNav.tsx")
    notebook = read(WEB / "pages" / "notebook.tsx")

    for tab in [
        "id: 'atelier'",
        "id: 'notebook'",
    ]:
        assert tab in shell

    assert "href: '/atelier'" in shell
    assert "href: '/notebook'" in shell
    assert "'/missions'" in shell
    assert "'/graphic-novel'" in shell
    assert "'/vocabulary/review'" in shell
    assert '"storyFeatureVisible": false' in flags
    assert "const STORY_ROUTES" in shell
    assert "...(STORY_FEATURE_VISIBLE ? STORY_ROUTES : [])" in shell
    assert "STORY_FEATURE_VISIBLE && STORY_ROUTES.includes(pathname)" in shell

    assert "<PhoneProductNav active={mobileSection} />" in masthead
    assert "PHONE_PRODUCT_TABS.map" in phone_nav
    assert "href={item.href}" in phone_nav
    assert 'aria-label="Primary"' in phone_nav
    assert "aria-current={isActive ? 'page' : undefined}" in phone_nav

    assert "storedNotebookMode" in notebook
    assert "notebookModeFromQuery" in notebook
    assert "router.push(" in notebook
    assert "<NotebookModeSwitch" in notebook
    assert "<GrammarNotebookSurface embedded />" in notebook
    assert "<VocabularyPage embedded />" in notebook
    assert "api.getCefrProgress()" in notebook
    assert "NotebookProgression" in notebook


def test_atelier_is_the_daily_session_and_review_handoff_center() -> None:
    atelier = read(WEB / "pages" / "atelier.tsx")
    vocabulary_review = read(WEB / "pages" / "vocabulary" / "review.tsx")

    assert "apiService.getAtelierToday()" in atelier
    assert "apiService.getActiveAtelierSession()" in atelier
    assert "apiService.getVocabularyDueContext" in atelier
    assert "apiService.startAtelierSession" in atelier
    assert "apiService.submitAtelierAttempt" in atelier
    assert "apiService.completeAtelierSession" in atelier
    assert "function TodayView" in atelier
    assert "function MissionBridge" in atelier
    assert "Use today&apos;s repairs in a message, conversation, or visual Feuilleton." in atelier
    assert "const query = conceptQueryString(concepts)" in atelier
    assert "href={`/missions${conceptIds ? `?${conceptIds}` : ''}`}" in atelier
    assert "href={`/graphic-novel${conceptIds ? `?${conceptIds}` : ''}`}" in atelier
    assert "session_id: result.session_id" in atelier
    assert "printed-hook" in atelier

    assert "Vocabulary review" in vocabulary_review
    assert "VocabularyReviewContinuation" in vocabulary_review
    assert "Queue claire" in vocabulary_review
    assert "onReturn" in vocabulary_review
    assert "onRefresh" in vocabulary_review
    assert "href={`/vocabulary?word=${wordId}`}" in vocabulary_review


def test_lean_mission_flow_is_complete_on_mobile() -> None:
    missions = read(WEB / "pages" / "missions.tsx")
    api = read(WEB / "services" / "api.ts")

    assert "apiService.getMissionsToday()" in missions
    assert "apiService.createMission({" in missions
    assert "apiService.submitMissionTurn(mission.id" in missions
    assert "apiService.completeMission(mission.id)" in missions
    assert "routeForMissionSerialBeat(result.next_serial)" in missions
    assert "Next act" in missions
    assert "apiService.translateToEnglish(text)" in missions
    assert "className=\"mission-stage\"" in missions
    assert "className=\"scene-frame\"" in missions
    assert "className=\"thread-body\"" in missions
    assert "className=\"composer\"" in missions
    assert "className=\"reward-strip\"" in missions
    assert "Token minted" in missions

    assert "custom_scenario?: string" in api
    assert "desired_outcome?: string" in api
    assert "relationship?: string" in api
    assert "register?: string" in api
    assert "return this.atelierPost<MissionTurnResult>(`/missions/${missionId}/turns`, data)" in api
    assert "export interface MissionCompleteResult" in api
    assert "next_serial?: SerialToday | null" in api
    assert "const response = await this.atelierPost<{ mission: RealWorldMission }>('/missions', data)" in api
    assert "return response;" in api


def test_feuilleton_scene_flow_has_creation_tasks_completion_and_context_returns() -> None:
    feuilleton = read(WEB / "pages" / "graphic-novel.tsx")
    api = read(WEB / "services" / "api.ts")

    assert "apiService.getGraphicNovelToday()" in feuilleton
    assert "apiService.createGraphicNovelScene" in feuilleton
    assert "apiService.submitGraphicNovelAttempt(scene.id" in feuilleton
    assert "apiService.completeGraphicNovelScene(scene.id)" in feuilleton
    assert 'aria-label="Create a new Feuilleton scene"' in feuilleton
    assert 'aria-label="Feuilleton mode"' in feuilleton
    assert 'aria-label="Panel count"' in feuilleton
    assert 'aria-label="Feuilleton reading actions"' in feuilleton
    assert 'aria-label="Final Feuilleton task"' in feuilleton
    assert 'aria-label="Feuilleton completion"' in feuilleton
    assert "function FeuilletonContinuationCard" in feuilleton
    assert "routeWithQuery('/missions', missionPairs)" in feuilleton
    assert "routeWithQuery('/atelier', atelierPairs)" in feuilleton

    assert "async getGraphicNovelToday()" in api
    assert "async createGraphicNovelScene" in api
    assert "async submitGraphicNovelAttempt" in api
    assert "async completeGraphicNovelScene" in api


def test_story_reading_flow_is_parked_behind_launch_flag_without_deleting_contracts() -> None:
    stories_page = read(WEB / "pages" / "stories.tsx")
    story_runtime = read(WEB / "pages" / "story" / "[id].tsx")
    story_detail = read(WEB / "pages" / "stories" / "[storyId].tsx")
    chapter_page = read(WEB / "pages" / "stories" / "[storyId]" / "chapter" / "[chapterId].tsx")
    learn_new = read(WEB / "pages" / "learn" / "new.tsx")
    redirects = read(WEB / "next.config.js")
    story_hooks = read(WEB / "hooks" / "useStories.ts")
    session_layout = read(WEB / "components" / "stories" / "StorySessionLayout.tsx")

    assert "STORY_FEATURE_VISIBLE" in stories_page
    assert "void router.replace('/atelier')" in stories_page
    assert "if (!STORY_FEATURE_VISIBLE) return null" in stories_page
    assert "source: '/stories/:path*', destination: '/atelier'" in redirects
    assert "source: '/bibliotheque/:path*', destination: '/atelier'" in redirects
    assert "<EditorialMasthead />" in stories_page
    assert "UploadBookModal" in stories_page
    assert "<FeaturedStoryCard story={storyList[0]} />" in stories_page
    assert "StoryCard key={story.id} story={story}" in stories_page

    assert "STORY_FEATURE_VISIBLE" in story_runtime
    assert "void router.replace('/atelier')" in story_runtime
    assert "if (!STORY_FEATURE_VISIBLE) return null" in story_runtime

    assert "STORY_FEATURE_VISIBLE" in story_detail
    assert "void router.replace('/atelier')" in story_detail
    assert "if (!STORY_FEATURE_VISIBLE) return null" in story_detail
    assert "useStoryDetail(resolvedStoryId)" in story_detail
    assert "useStartStory()" in story_detail
    assert "router.push(`/stories/${resolvedStoryId}/chapter/${result.chapter.id}`)" in story_detail
    assert "router.push(`/stories/${resolvedStoryId}/chapter/${storyDetail.user_progress.current_chapter_id}`)" in story_detail

    assert "STORY_FEATURE_VISIBLE" in chapter_page
    assert "void router.replace('/atelier')" in chapter_page
    assert "if (!STORY_FEATURE_VISIBLE) return null" in chapter_page
    assert "useChapter(resolvedStoryId, resolvedChapterId)" in chapter_page
    assert "useStartChapterSession()" in chapter_page
    assert "planned_duration_minutes: 15" in chapter_page
    assert "<StorySessionLayout" in chapter_page

    assert "STORY_FEATURE_VISIBLE && (" in learn_new
    assert "STORY_FEATURE_VISIBLE && isImportModalOpen" in learn_new

    assert "`/stories${queryParams.toString() ? `?${queryParams.toString()}` : ''}`" in story_hooks
    assert "apiService.get<any>(`/stories/${storyId}`)" in story_hooks
    assert "apiService.get<any[]>(`/stories/${storyId}/chapters`)" in story_hooks
    assert "apiService.get<any | null>(`/stories/${storyId}/progress`).catch(() => null)" in story_hooks
    assert "apiService.post<StoryStartResponse>(" in story_hooks
    assert "`/stories/${storyId}/start`" in story_hooks
    assert "apiService.post<SessionStartEnvelope>('/sessions'" in story_hooks
    assert "`/stories/${storyId}/chapters/${chapterId}/check-goals`" in story_hooks
    assert "`/stories/${storyId}/chapters/${chapterId}/complete`" in story_hooks

    assert "useLearningSession(sessionId)" in session_layout
    assert "sendMessage(draft)" in session_layout
    assert "checkGoals(storyId, chapterId, sessionId)" in session_layout
    assert "completeChapter(storyId, chapterId" in session_layout
    assert "apiService.markGrammarPracticedInContext(conceptIds)" in session_layout
