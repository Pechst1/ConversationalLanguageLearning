import React from 'react';
import { apiClient, ApiError } from '../api/client';
import type {
  AnkiProgressSummary,
  AnkiReviewResponse,
  AnkiWordProgress,
  AuthTokens,
  QueueWord,
  UserProfile,
} from '../types/api';

interface RefreshOptions {
  background?: boolean;
}

interface LearnerContextValue {
  profile: UserProfile | null;
  ankiSummary: AnkiProgressSummary | null;
  ankiProgress: AnkiWordProgress[];
  dueAnkiCards: AnkiWordProgress[];
  reviewQueue: QueueWord[];
  isLoading: boolean;
  isSyncing: boolean;
  lastSyncedAt: string | null;
  error: string | null;
  refresh: (options?: RefreshOptions) => Promise<void>;
  submitAnkiReview: (wordId: number, rating: number, responseTimeMs?: number) => Promise<AnkiReviewResponse>;
  clearError: () => void;
}

const LearnerContext = React.createContext<LearnerContextValue | undefined>(undefined);

interface LearnerProviderProps {
  authTokens: AuthTokens | null;
  children: React.ReactNode;
}

export const LearnerProvider: React.FC<LearnerProviderProps> = ({ authTokens, children }) => {
  const [profile, setProfile] = React.useState<UserProfile | null>(null);
  const [ankiSummary, setAnkiSummary] = React.useState<AnkiProgressSummary | null>(null);
  const [ankiProgress, setAnkiProgress] = React.useState<AnkiWordProgress[]>([]);
  const [reviewQueue, setReviewQueue] = React.useState<QueueWord[]>([]);
  const [isLoading, setIsLoading] = React.useState(false);
  const [isSyncing, setIsSyncing] = React.useState(false);
  const [lastSyncedAt, setLastSyncedAt] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  const accessToken = authTokens?.accessToken ?? null;

  React.useEffect(() => {
    apiClient.setAccessToken(accessToken);
    if (!accessToken) {
      setProfile(null);
      setAnkiSummary(null);
      setAnkiProgress([]);
      setReviewQueue([]);
      setLastSyncedAt(null);
      setError(null);
    }
  }, [accessToken]);

  const refresh = React.useCallback(
    async (options?: RefreshOptions) => {
      if (!accessToken) {
        return;
      }

      const isBackground = options?.background ?? false;
      setError(null);
      if (isBackground) {
        setIsSyncing(true);
      } else {
        setIsLoading(true);
      }

      try {
        const [user, summary, progress, queue] = await Promise.all([
          apiClient.getCurrentUser(),
          apiClient.getAnkiSummary(),
          apiClient.getAnkiProgress(),
          apiClient.getReviewQueue(20),
        ]);

        setProfile(user);
        setAnkiSummary(summary);
        setAnkiProgress(progress);
        setReviewQueue(queue);
        setLastSyncedAt(new Date().toISOString());
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Unable to load learner data';
        setError(message);
        if (err instanceof ApiError && err.status === 401) {
          apiClient.setAccessToken(null);
        }
      } finally {
        if (isBackground) {
          setIsSyncing(false);
        } else {
          setIsLoading(false);
        }
      }
    },
    [accessToken]
  );

  const submitAnkiReview = React.useCallback(
    async (wordId: number, rating: number, responseTimeMs?: number) => {
      if (!accessToken) {
        throw new ApiError('You need to sign in to review cards', 401);
      }

      try {
        const response = await apiClient.submitAnkiReview({
          word_id: wordId,
          rating,
          response_time_ms: responseTimeMs,
        });

        setAnkiProgress((prev) =>
          prev.map((card) =>
            card.word_id === wordId
              ? {
                  ...card,
                  learning_stage: response.phase ?? card.learning_stage,
                  ease_factor: response.ease_factor ?? card.ease_factor,
                  interval_days: response.interval_days ?? card.interval_days,
                  due_at: response.due_at ?? card.due_at,
                  next_review: response.next_review ?? card.next_review,
                  reps: card.reps + 1,
                }
              : card
          )
        );

        await refresh({ background: true });

        return response;
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Unable to submit review';
        setError(message);
        throw err;
      }
    },
    [accessToken, refresh]
  );

  const dueAnkiCards = React.useMemo(() => {
    if (!ankiProgress.length) {
      return [];
    }

    const now = Date.now();
    return [...ankiProgress]
      .filter((card) => {
        const dueDateString = card.due_at ?? card.next_review ?? null;
        if (!dueDateString) {
          return card.learning_stage.toLowerCase().includes('learn');
        }
        const dueDate = Date.parse(dueDateString);
        if (Number.isNaN(dueDate)) {
          return false;
        }
        return dueDate <= now;
      })
      .sort((a, b) => {
        const aDate = Date.parse(a.due_at ?? a.next_review ?? '') || 0;
        const bDate = Date.parse(b.due_at ?? b.next_review ?? '') || 0;
        return aDate - bDate;
      });
  }, [ankiProgress]);

  const clearError = React.useCallback(() => setError(null), []);

  React.useEffect(() => {
    if (accessToken) {
      void refresh();
    }
  }, [accessToken, refresh]);

  const value = React.useMemo(
    () => ({
      profile,
      ankiSummary,
      ankiProgress,
      dueAnkiCards,
      reviewQueue,
      isLoading,
      isSyncing,
      lastSyncedAt,
      error,
      refresh,
      submitAnkiReview,
      clearError,
    }),
    [
      profile,
      ankiSummary,
      ankiProgress,
      dueAnkiCards,
      reviewQueue,
      isLoading,
      isSyncing,
      lastSyncedAt,
      error,
      refresh,
      submitAnkiReview,
      clearError,
    ]
  );

  return <LearnerContext.Provider value={value}>{children}</LearnerContext.Provider>;
};

export const useLearnerContext = () => {
  const context = React.useContext(LearnerContext);
  if (!context) {
    throw new Error('useLearnerContext must be used within a LearnerProvider');
  }
  return context;
};
