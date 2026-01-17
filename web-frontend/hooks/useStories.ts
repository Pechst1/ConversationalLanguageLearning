import { useState, useCallback, useEffect } from 'react';
import apiService from '@/services/api';
import toast from 'react-hot-toast';

// ============================================================================
// Types
// ============================================================================

export interface StoryBase {
  id: number;
  story_key: string;
  title: string;
  description: string | null;
  difficulty_level: string | null;
  estimated_duration_minutes: number | null;
  theme_tags: string[];
  vocabulary_theme: string | null;
  cover_image_url: string | null;
  author: string | null;
  total_chapters: number;
  is_published: boolean;
}

export interface ChapterBase {
  id: number;
  chapter_key: string;
  sequence_order: number;
  title: string;
  synopsis: string | null;
  opening_narrative: string | null;
  min_turns: number;
  max_turns: number;
  narrative_goals: NarrativeGoal[];
  completion_criteria: CompletionCriteria | null;
  branching_choices: BranchingChoice[] | null;
  completion_xp: number;
  perfect_completion_xp: number;
}

export interface NarrativeGoal {
  goal_id: string;
  description: string;
  hint?: string;
  required_words: string[];
}

export interface CompletionCriteria {
  min_goals_completed: number;
  min_vocabulary_used: number;
}

export interface BranchingChoice {
  choice_id: string;
  text: string;
  hint?: string;
  next_chapter_id?: number;
}

export interface UserStoryProgressBase {
  id: string;
  user_id: string;
  story_id: number;
  current_chapter_id: number | null;
  status: 'in_progress' | 'completed' | 'abandoned';
  chapters_completed: ChapterCompletion[];
  total_chapters_completed: number;
  completion_percentage: number;
  total_xp_earned: number;
  total_time_spent_minutes: number;
  vocabulary_mastered_count: number;
  perfect_chapters_count: number;
  narrative_choices: Record<string, string>;
  started_at: string;
  last_accessed_at: string;
  completed_at: string | null;
}

export interface ChapterCompletion {
  chapter_id: number;
  completed_at: string;
  xp_earned: number;
  was_perfect: boolean;
  goals_completed: string[];
}

export interface StoryProgressSummary {
  is_started: boolean;
  is_completed: boolean;
  completion_percentage: number;
  current_chapter_number: number | null;
  current_chapter_title: string | null;
  chapters_completed: number;
  total_xp_earned: number;
}

export interface StoryListItem {
  story: StoryBase;
  user_progress: StoryProgressSummary | null;
}

export interface ChapterWithStatus {
  chapter: ChapterBase;
  is_locked: boolean;
  is_completed: boolean;
  was_perfect: boolean;
}

export interface StoryDetailResponse {
  story: StoryBase;
  chapters: ChapterWithStatus[];
  user_progress: UserStoryProgressBase | null;
}

export interface UserStoryProgressResponse {
  progress: UserStoryProgressBase;
  current_chapter: ChapterBase | null;
}

export interface ChapterCompletionRequest {
  session_id: string;
  goals_completed: string[];
}

export interface ChapterCompletionResponse {
  xp_earned: number;
  achievements_unlocked: any[];
  next_chapter_id: number | null;
  next_chapter: ChapterBase | null;
  story_completed: boolean;
  is_perfect: boolean;
}

export interface NarrativeChoiceRequest {
  choice_id: string;
}

export interface NextChapterResponse {
  next_chapter: ChapterBase;
  choice_recorded: string;
}

// ============================================================================
// Hook: useStories - List all available stories
// ============================================================================

export function useStories(params?: { difficulty?: string; theme?: string }) {
  const [stories, setStories] = useState<StoryListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchStories = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const queryParams = new URLSearchParams();
      if (params?.difficulty) queryParams.set('difficulty', params.difficulty);
      if (params?.theme) queryParams.set('theme', params.theme);

      const data = await apiService.get<StoryListItem[]>(
        `/stories${queryParams.toString() ? `?${queryParams.toString()}` : ''}`
      );

      setStories(data);
      return data;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch stories';
      setError(errorMessage);
      toast.error(errorMessage);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [params?.difficulty, params?.theme]);

  useEffect(() => {
    fetchStories();
  }, [fetchStories]);

  return {
    stories,
    loading,
    error,
    refetch: fetchStories,
  };
}

// ============================================================================
// Hook: useStoryDetail - Get full story details with chapters
// ============================================================================

export function useStoryDetail(storyId: number | null) {
  const [storyDetail, setStoryDetail] = useState<StoryDetailResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchStoryDetail = useCallback(async () => {
    if (!storyId) return null;

    try {
      setLoading(true);
      setError(null);

      const data = await apiService.get<StoryDetailResponse>(`/stories/${storyId}`);

      setStoryDetail(data);
      return data;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch story details';
      setError(errorMessage);
      toast.error(errorMessage);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [storyId]);

  useEffect(() => {
    if (storyId) {
      fetchStoryDetail();
    }
  }, [fetchStoryDetail, storyId]);

  return {
    storyDetail,
    loading,
    error,
    refetch: fetchStoryDetail,
  };
}

// ============================================================================
// Hook: useStartStory - Begin or resume a story
// ============================================================================

export function useStartStory() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const startStory = useCallback(async (storyId: number) => {
    try {
      setLoading(true);
      setError(null);

      const data = await apiService.post<UserStoryProgressResponse>(
        `/stories/${storyId}/start`
      );

      toast.success('Story started!');
      return data;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to start story';
      setError(errorMessage);
      toast.error(errorMessage);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  return {
    startStory,
    loading,
    error,
  };
}

// ============================================================================
// Hook: useChapter - Get chapter data
// ============================================================================

export function useChapter(storyId: number | null, chapterId: number | null) {
  const [chapter, setChapter] = useState<ChapterBase | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchChapter = useCallback(async () => {
    if (!storyId || !chapterId) return null;

    try {
      setLoading(true);
      setError(null);

      // Get chapter from story detail
      const storyDetail = await apiService.get<StoryDetailResponse>(`/stories/${storyId}`);
      const chapterWithStatus = storyDetail.chapters.find(c => c.chapter.id === chapterId);

      if (!chapterWithStatus) {
        throw new Error('Chapter not found');
      }

      setChapter(chapterWithStatus.chapter);
      return chapterWithStatus.chapter;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch chapter';
      setError(errorMessage);
      toast.error(errorMessage);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [storyId, chapterId]);

  useEffect(() => {
    if (storyId && chapterId) {
      fetchChapter();
    }
  }, [fetchChapter, storyId, chapterId]);

  return {
    chapter,
    loading,
    error,
    refetch: fetchChapter,
  };
}

// ============================================================================
// Hook: useStartChapterSession - Start a session for a chapter
// ============================================================================

export function useStartChapterSession() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const startChapterSession = useCallback(async (params: {
    storyId: number;
    chapterId: number;
    planned_duration_minutes?: number;
    difficulty_preference?: string;
  }) => {
    try {
      setLoading(true);
      setError(null);

      // Create session with story context
      const sessionData = await apiService.post('/sessions', {
        story_id: params.storyId,
        story_chapter_id: params.chapterId,
        planned_duration_minutes: params.planned_duration_minutes || 15,
        conversation_style: 'storytelling',
        difficulty_preference: params.difficulty_preference,
        generate_greeting: true,
      });

      return sessionData;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to start chapter session';
      setError(errorMessage);
      toast.error(errorMessage);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  return {
    startChapterSession,
    loading,
    error,
  };
}

// ============================================================================
// Hook: useCompleteChapter - Mark chapter as complete
// ============================================================================

export function useCompleteChapter() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const completeChapter = useCallback(async (
    storyId: number,
    chapterId: number,
    payload: ChapterCompletionRequest
  ) => {
    try {
      setLoading(true);
      setError(null);

      const data = await apiService.post<ChapterCompletionResponse>(
        `/stories/${storyId}/chapters/${chapterId}/complete`,
        payload
      );

      if (data.story_completed) {
        toast.success('🎊 Story completed!', { duration: 4000 });
      } else if (data.is_perfect) {
        toast.success('⭐ Perfect chapter completion!', { duration: 3000 });
      } else {
        toast.success('Chapter completed!', { duration: 2000 });
      }

      return data;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to complete chapter';
      setError(errorMessage);
      toast.error(errorMessage);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  return {
    completeChapter,
    loading,
    error,
  };
}

// ============================================================================
// Hook: useMakeChoice - Record narrative choice
// ============================================================================

export function useMakeChoice() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const makeChoice = useCallback(async (
    storyId: number,
    payload: NarrativeChoiceRequest
  ) => {
    try {
      setLoading(true);
      setError(null);

      const data = await apiService.post<NextChapterResponse>(
        `/stories/${storyId}/make-choice`,
        payload
      );

      toast.success('Choice recorded');
      return data;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to record choice';
      setError(errorMessage);
      toast.error(errorMessage);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  return {
    makeChoice,
    loading,
    error,
  };
}

// ============================================================================
// Hook: useCurrentStory - Get user's current in-progress story
// ============================================================================

export function useCurrentStory() {
  const [currentStory, setCurrentStory] = useState<StoryListItem | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchCurrentStory = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      // Fetch all stories and find the one in progress
      const stories = await apiService.get<StoryListItem[]>('/stories');

      const inProgressStory = stories.find(
        story => story.user_progress?.is_started && !story.user_progress?.is_completed
      );

      setCurrentStory(inProgressStory || null);
      return inProgressStory || null;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch current story';
      setError(errorMessage);
      // Don't show toast for this error as it's likely just no story in progress
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCurrentStory();
  }, [fetchCurrentStory]);

  return {
    currentStory,
    loading,
    error,
    refetch: fetchCurrentStory,
  };
}
