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

    assert "if (status === 'authenticated')" in home
    assert "router.push('/atelier')" in home
    assert '<Link href="/auth/signin">Sign in</Link>' in home
    assert '<Link className="public-start" href="/auth/signup">Start</Link>' in home

    assert "typeof router.query.callbackUrl === 'string'" in signin
    assert ": '/atelier'" in signin
    assert "signIn('credentials'" in signin
    assert "router.push(destination)" in signin

    assert "defaultValues" in signup
    assert "nativeLanguage: 'en'" in signup
    assert "targetLanguage: 'fr'" in signup
    assert "proficiencyLevel: 'A1'" in signup
    assert "<details className=\"profile-details\">" in signup
    assert "apiService.register" in signup
    assert "full_name: data.name" in signup
    assert "interests: selectedTopics.join(',')" in signup
    assert "router.push('/auth/signin')" in signup


def test_phone_shell_keeps_the_primary_product_modes_simple_and_reachable() -> None:
    shell = read(WEB / "lib" / "product-shell.ts")
    masthead = read(WEB / "components" / "layout" / "EditorialMasthead.tsx")
    notebook = read(WEB / "pages" / "notebook.tsx")

    for tab in [
        "id: 'atelier'",
        "id: 'notebook'",
        "id: 'missions'",
        "id: 'feuilleton'",
    ]:
        assert tab in shell

    assert "href: '/atelier'" in shell
    assert "href: '/notebook'" in shell
    assert "href: '/missions'" in shell
    assert "href: '/graphic-novel'" in shell
    assert "'/vocabulary/review'" in shell
    assert "'/stories/[storyId]/chapter/[chapterId]'" in shell

    assert "PHONE_PRODUCT_TABS.map" in masthead
    assert "href: item.id === 'notebook' ? '/notebook' : item.href" in masthead
    assert 'aria-label="Mobile primary"' in masthead
    assert "aria-current={item.active ? 'page' : undefined}" in masthead

    assert "storedNotebookMode" in notebook
    assert "router.replace(mode === 'vocabulary' ? '/vocabulary' : '/grammar')" in notebook
    assert '<Link href="/grammar">Open Grammar</Link>' in notebook
    assert '<Link href="/vocabulary">Open Vocabulary</Link>' in notebook


def test_atelier_is_the_daily_session_and_review_handoff_center() -> None:
    atelier = read(WEB / "pages" / "atelier.tsx")
    vocabulary_review = read(WEB / "pages" / "vocabulary" / "review.tsx")

    assert "Promise.all([apiService.getAtelierToday(), apiService.getActiveAtelierSession()])" in atelier
    assert "apiService.startAtelierSession" in atelier
    assert "apiService.submitAtelierAttempt" in atelier
    assert "apiService.completeAtelierSession" in atelier
    assert "function TodayView" in atelier
    assert "function MissionBridge" in atelier
    assert "Use today&apos;s repairs in a message, conversation, or visual Feuilleton." in atelier
    assert "const query = conceptQueryString(concepts)" in atelier
    assert "href={`/missions${conceptIds ? `?${conceptIds}` : ''}`}" in atelier
    assert "href={`/graphic-novel${conceptIds ? `?${conceptIds}` : ''}`}" in atelier
    assert "href={`/missions?atelier_session_id=${recap.session_id}`}" in atelier

    assert "Vocabulary review" in vocabulary_review
    assert "VocabularyReviewContinuation" in vocabulary_review
    assert "hrefWithQuery('/missions', [['vocabulary_id', wordId]])" in vocabulary_review
    assert "hrefWithQuery('/graphic-novel', [['vocabulary_id', wordId]])" in vocabulary_review


def test_custom_mission_flow_is_complete_on_mobile() -> None:
    missions = read(WEB / "pages" / "missions.tsx")
    api = read(WEB / "services" / "api.ts")

    assert "api.getMissionsToday()" in missions
    assert "api.createMission({" in missions
    assert "api.submitMissionTurn(mission.id" in missions
    assert "api.completeMission(mission.id)" in missions
    assert 'data-testid="mobile-mission-switcher"' in missions
    assert 'data-testid="custom-mission-sheet"' in missions
    assert 'data-testid="custom-mission-scenario"' in missions
    assert 'data-testid="custom-mission-outcome"' in missions
    assert 'data-testid="custom-mission-relationship"' in missions
    assert 'data-testid="custom-mission-register"' in missions
    assert 'data-testid="custom-mission-create"' in missions
    assert 'data-testid="mission-turn-textarea"' in missions
    assert 'data-testid="mission-send-turn"' in missions
    assert 'data-testid="mobile-mission-debrief"' in missions
    assert 'data-testid="mission-feuilleton-mobile"' in missions

    assert "custom_scenario?: string" in api
    assert "desired_outcome?: string" in api
    assert "relationship?: string" in api
    assert "register?: string" in api
    assert "return this.atelierPost<MissionTurnResult>(`/missions/${missionId}/turns`, data)" in api
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


def test_story_reading_flow_fetches_library_detail_chapter_and_completion_contracts() -> None:
    stories_page = read(WEB / "pages" / "stories.tsx")
    story_detail = read(WEB / "pages" / "stories" / "[storyId].tsx")
    chapter_page = read(WEB / "pages" / "stories" / "[storyId]" / "chapter" / "[chapterId].tsx")
    story_hooks = read(WEB / "hooks" / "useStories.ts")
    session_layout = read(WEB / "components" / "stories" / "StorySessionLayout.tsx")

    assert "<EditorialMasthead />" in stories_page
    assert "UploadBookModal" in stories_page
    assert "<FeaturedStoryCard story={stories[0]} />" in stories_page
    assert "StoryCard key={story.id} story={story}" in stories_page

    assert "useStoryDetail(resolvedStoryId)" in story_detail
    assert "useStartStory()" in story_detail
    assert "router.push(`/stories/${resolvedStoryId}/chapter/${result.chapter.id}`)" in story_detail
    assert "router.push(`/stories/${resolvedStoryId}/chapter/${storyDetail.user_progress.current_chapter_id}`)" in story_detail

    assert "useChapter(resolvedStoryId, resolvedChapterId)" in chapter_page
    assert "useStartChapterSession()" in chapter_page
    assert "planned_duration_minutes: 15" in chapter_page
    assert "<StorySessionLayout" in chapter_page

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
