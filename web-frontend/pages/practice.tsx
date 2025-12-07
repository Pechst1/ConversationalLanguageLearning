import React from 'react';
import { getSession } from 'next-auth/react';
import { format, formatDistanceToNow } from 'date-fns';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card';
import apiService from '@/services/api';
import { AnkiReviewResponse, ReviewResponse } from '@/types/reviews';
import { CheckCircle, XCircle, Clock, Type, CircleDot, RefreshCw } from 'lucide-react';
import toast from 'react-hot-toast';
import { AnkiSync } from '@/components/AnkiSync';

interface PracticeWord {
  wordId: number;
  word: string;
  translation: string;
  difficulty: number;
  scheduler?: 'anki' | 'fsrs' | string;
  stage?: 'new' | 'learning' | 'due' | string;
}

type PracticeDirection = 'fr_to_de' | 'de_to_fr';

interface PracticeProps {
  queueWords: PracticeWord[];
  counters: {
    newCount: number;
    learningCount: number;
    dueCount: number;
  };
  direction?: PracticeDirection;
}

function cleanSurface(word: string, translation?: string | null) {
  if (!word) return '';
  const seg = word.split(/[;,/|]+/)[0].trim();
  let result = seg;
  if (translation) {
    const tl = String(translation).trim().toLowerCase();
    const regex = new RegExp(`\\s+${tl.replace(/[-/\\^$*+?.()|[\]{}]/g, '\\$&')}$`, 'i');
    result = result.replace(regex, '').trim();
  }
  return result;
}

function formatIntervalLabel(days?: number | null) {
  if (days === null || days === undefined) {
    return 'soon';
  }
  if (days === 0) {
    return '0 days (later today)';
  }
  if (days === 1) {
    return '1 day';
  }
  return `${days} days`;
}

function formatDueDateLabel(value?: string | null) {
  if (!value) {
    return '';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '';
  }
  return date.toLocaleDateString(undefined, { dateStyle: 'medium' });
}

function formatStateLabel(value?: string | null) {
  if (!value) {
    return '';
  }
  return value
    .split(/[_\s]+/)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
    .join(' ');
}

function isAnkiReviewResponse(
  response: ReviewResponse | AnkiReviewResponse
): response is AnkiReviewResponse {
  return 'scheduler' in response && typeof response.scheduler === 'string' && response.scheduler.toLowerCase() === 'anki';
}

function formatReviewFeedbackMessage(response: ReviewResponse | AnkiReviewResponse) {
  if (isAnkiReviewResponse(response)) {
    const intervalText = formatIntervalLabel(response.interval_days ?? null);
    const dueDateText = formatDueDateLabel(response.due_at ?? response.next_review ?? undefined);
    const phase = formatStateLabel(response.phase);
    const easeFactor =
      typeof response.ease_factor === 'number' && Number.isFinite(response.ease_factor)
        ? response.ease_factor.toFixed(2)
        : null;

    let message = `Due again in ${intervalText}`;
    if (dueDateText) {
      message += ` on ${dueDateText}`;
    }
    message += '.';

    if (phase) {
      message += ` Phase: ${phase}.`;
    }

    if (easeFactor) {
      message += ` Ease factor: ${easeFactor}.`;
    }

    return message;
  }

  const intervalText = formatIntervalLabel(response.scheduled_days);
  const dueDateText = formatDueDateLabel(response.next_review);
  const state = formatStateLabel(response.state);

  let message = `Due again in ${intervalText}`;
  if (dueDateText) {
    message += ` on ${dueDateText}`;
  }
  message += '.';

  if (state) {
    message += ` Current state: ${state}.`;
  }

  return message;
}

const FETCH_LIMIT = 50;
const FETCH_THRESHOLD = 3;

export default function PracticePage({ queueWords, counters, direction: initialDirection }: PracticeProps) {
  const [localQueue, setLocalQueue] = React.useState<PracticeWord[]>(queueWords);
  const [currentWordIndex, setCurrentWordIndex] = React.useState(0);
  const [showAnswer, setShowAnswer] = React.useState(false);
  const [score, setScore] = React.useState(0);
  const [completed, setCompleted] = React.useState(false);
  const [counts] = React.useState(counters);
  const [lastReviewFeedback, setLastReviewFeedback] = React.useState<{
    word: string;
    message: string;
  } | null>(null);
  const [isFetchingMore, setIsFetchingMore] = React.useState(false);
  const [direction, setDirection] = React.useState<PracticeDirection>(initialDirection || 'fr_to_de');
  const [isLoadingDirection, setIsLoadingDirection] = React.useState(false);

  const queueRef = React.useRef(localQueue);
  const cardShownAtRef = React.useRef<number>(Date.now());

  // Keep ref in sync
  React.useEffect(() => {
    queueRef.current = localQueue;
  }, [localQueue]);

  const currentWord = localQueue[currentWordIndex];
  const queueLength = localQueue.length;
  const nextIndex = currentWordIndex + 1;
  const finalTotal = Math.max(queueLength, counters.dueCount + counters.newCount + counters.learningCount);

  const mapQueueItem = React.useCallback((item: any, dir: PracticeDirection): PracticeWord => ({
    wordId: item.word_id,
    word: item.word,
    translation: (dir === 'fr_to_de' ? item.german_translation : item.french_translation) || item.english_translation || '',
    difficulty: item.difficulty_level || 1,
    scheduler: item.scheduler || undefined,
    stage: item.stage || item.queue_stage || item.stage_type || undefined,
  }), []);

  const handleRefreshQueue = async (overrideDirection?: PracticeDirection) => {
    const targetDirection = overrideDirection || direction;
    setIsLoadingDirection(true);
    try {
      const raw = await apiService.getProgressQueue({ limit: FETCH_LIMIT, direction: targetDirection });
      if (Array.isArray(raw)) {
        const mapped = raw.map(item => mapQueueItem(item, targetDirection));
        setLocalQueue(mapped);
        setCurrentWordIndex(0);
        setCompleted(false);
        setScore(0);
        setShowAnswer(false);
        setLastReviewFeedback(null);
      }
    } catch (error) {
      toast.error('Failed to refresh queue');
    } finally {
      setIsLoadingDirection(false);
    }
  };

  const loadMoreItems = React.useCallback(async () => {
    if (isFetchingMore) return queueRef.current.length;

    setIsFetchingMore(true);
    let updatedLength = queueRef.current.length;
    try {
      const raw = await apiService.getProgressQueue({ limit: FETCH_LIMIT, direction });
      if (!Array.isArray(raw) || !raw.length) {
        return updatedLength;
      }

      setLocalQueue((prev) => {
        const existingIds = new Set(prev.map((item) => item.wordId));
        const mapped = raw
          .map(item => mapQueueItem(item, direction))
          .filter((item) => !existingIds.has(item.wordId));

        if (!mapped.length) {
          updatedLength = prev.length;
          queueRef.current = prev;
          return prev;
        }

        const combined = [...prev, ...mapped];
        updatedLength = combined.length;
        queueRef.current = combined;
        return combined;
      });

      return updatedLength;
    } catch (error) {
      console.error('Failed to load more practice items', error);
      toast.error('Could not load additional practice items');
      return updatedLength;
    } finally {
      setIsFetchingMore(false);
    }
  }, [isFetchingMore, mapQueueItem, direction]);

  const ensureQueueDepth = React.useCallback(async (nextIndex: number) => {
    const remaining = queueRef.current.length - nextIndex;
    if (remaining > FETCH_THRESHOLD) {
      return queueRef.current.length;
    }
    return loadMoreItems();
  }, [loadMoreItems]);

  React.useEffect(() => {
    cardShownAtRef.current = Date.now();
  }, [currentWordIndex]);

  const handleShowTranslation = React.useCallback(() => {
    setShowAnswer(true);
  }, []);

  const handleRating = async (rating: number) => {
    const now = Date.now();
    const elapsedMs = Math.max(0, Math.round(now - cardShownAtRef.current));
    const responsePayload = {
      word_id: currentWord.wordId,
      rating,
      response_time_ms: elapsedMs,
    };

    try {
      const usesAnkiScheduler = currentWord.scheduler?.toLowerCase() === 'anki';
      const reviewResponse: ReviewResponse | AnkiReviewResponse = usesAnkiScheduler
        ? await apiService.submitAnkiReview(responsePayload)
        : await apiService.submitReview(responsePayload);

      const updatedScore = score + (rating >= 2 ? 1 : 0);
      setScore(updatedScore);

      setLastReviewFeedback({
        word: cleanSurface(currentWord.word, currentWord.translation),
        message: formatReviewFeedbackMessage(reviewResponse),
      });

      if (nextIndex < queueLength) {
        setCurrentWordIndex(nextIndex);
        setShowAnswer(false);
        cardShownAtRef.current = Date.now();
      } else {
        setCompleted(true);
        toast.success(`Practice completed! Score: ${updatedScore}/${queueWords.length}`);
      }
    } catch (error) {
      toast.error('Failed to submit review');
    }
  };

  React.useEffect(() => {
    if (!localQueue.length || completed) {
      return;
    }

    const initialRemaining = localQueue.length - currentWordIndex - 1;
    if (initialRemaining <= FETCH_THRESHOLD) {
      ensureQueueDepth(currentWordIndex + 1);
    }
  }, [completed, currentWordIndex, ensureQueueDepth, localQueue.length]);

  const toggleDirection = () => {
    const newDirection = direction === 'fr_to_de' ? 'de_to_fr' : 'fr_to_de';
    setDirection(newDirection);
    handleRefreshQueue(newDirection);
  };

  const directionToggle = (
    <div className="flex justify-end mb-4">
      <Button
        variant="outline"
        onClick={toggleDirection}
        className="border-2 border-brutal-black shadow-brutal hover:translate-y-1 hover:shadow-none transition-all rounded-none font-bold"
      >
        <RefreshCw className="w-4 h-4 mr-2" />
        Switch to {direction === 'fr_to_de' ? 'DE -> FR' : 'FR -> DE'}
      </Button>
    </div>
  );

  if (!localQueue?.length) {
    return (
      <div className="max-w-2xl mx-auto p-4">
        <AnkiSync onSyncComplete={() => handleRefreshQueue()} />
        <div className="mt-8 text-center">
          <div className="bg-brutal-white border-4 border-brutal-black shadow-brutal p-8">
            <h1 className="text-4xl font-bold mb-4 font-heading">NO WORDS</h1>
            <p className="text-xl font-mono mb-6">
              You&apos;re all caught up.
            </p>
            <Button
              onClick={() => handleRefreshQueue()}
              loading={isLoadingDirection}
              className="bg-bauhaus-yellow text-brutal-black border-4 border-brutal-black shadow-brutal hover:translate-y-1 hover:shadow-none transition-all rounded-none font-bold text-lg px-8 py-4"
            >
              CHECK AGAIN
            </Button>
          </div>
        </div>
      </div>
    );
  }

  if (completed) {
    return (
      <div className="max-w-2xl mx-auto text-center p-4">
        <div className="bg-brutal-white border-4 border-brutal-black shadow-brutal p-8">
          <CheckCircle className="h-24 w-24 text-bauhaus-green mx-auto mb-4" />
          <h1 className="text-4xl font-bold mb-4 font-heading">COMPLETE</h1>
          <p className="text-2xl font-mono mb-8">
            Score: {score}/{finalTotal}
          </p>
          <Button
            onClick={() => window.location.href = '/dashboard'}
            className="bg-bauhaus-blue text-white border-4 border-brutal-black shadow-brutal hover:translate-y-1 hover:shadow-none transition-all rounded-none font-bold text-lg px-8 py-4"
          >
            BACK TO DASHBOARD
          </Button>
        </div>
      </div>
    );
  }

  if (!currentWord) {
    return (
      <div className="max-w-2xl mx-auto text-center p-4">
        <div className="bg-brutal-white border-4 border-brutal-black shadow-brutal p-8 animate-pulse">
          <h1 className="text-2xl font-bold font-heading">LOADING...</h1>
        </div>
      </div>
    );
  }

  const cleanedState = formatStateLabel(currentWord.stage);
  const formattedNextReview = 'Now'; // Since it's in queue

  return (
    <div className="max-w-2xl mx-auto p-4 space-y-8">
      <div className="flex justify-between items-center">
        <h1 className="text-4xl font-black font-heading tracking-tighter">PRACTICE</h1>
        <AnkiSync onSyncComplete={() => handleRefreshQueue()} />
      </div>

      {directionToggle}

      <div className="mb-8">
        <div className="flex items-center justify-between font-mono text-sm mb-2">
          <span>PROGRESS</span>
          <span>{Math.min(currentWordIndex + 1, localQueue.length)} / {localQueue.length || finalTotal}</span>
        </div>
        <div className="w-full bg-brutal-gray border-2 border-brutal-black h-4">
          <div
            className="bg-bauhaus-blue h-full transition-all duration-300 border-r-2 border-brutal-black"
            style={{
              width: `${localQueue.length
                ? Math.min(((currentWordIndex + 1) / localQueue.length) * 100, 100)
                : 0
                }%`,
            }}
          />
        </div>
      </div>

      <div className="relative group">
        <div className="absolute -inset-1 bg-brutal-black translate-x-2 translate-y-2 group-hover:translate-x-3 group-hover:translate-y-3 transition-transform"></div>
        <div className="relative bg-brutal-white border-4 border-brutal-black p-8 min-h-[400px] flex flex-col justify-between">

          <div className="space-y-4">
            <div className="flex justify-center gap-2">
              {cleanedState && (
                <span className="px-3 py-1 bg-bauhaus-yellow border-2 border-brutal-black font-bold text-xs uppercase tracking-wider">
                  {cleanedState}
                </span>
              )}
              {currentWord.scheduler === 'anki' && (
                <span className="px-3 py-1 bg-bauhaus-blue text-white border-2 border-brutal-black font-bold text-xs uppercase tracking-wider">
                  ANKI
                </span>
              )}
            </div>

            <h2 className="text-5xl font-black text-center font-heading break-words">
              {cleanSurface(currentWord.word, currentWord.translation)}
            </h2>

            <p className="text-center text-gray-500 font-mono text-sm">
              How well do you know this word?
            </p>
          </div>

          <div className="space-y-6 mt-8">
            {!showAnswer ? (
              <div className="text-center">
                <Button
                  onClick={handleShowTranslation}
                  className="w-full bg-brutal-black text-white hover:bg-bauhaus-red border-4 border-transparent hover:border-brutal-black transition-all font-bold text-xl py-6 rounded-none"
                >
                  REVEAL
                </Button>
              </div>
            ) : (
              <>
                <div className="text-center p-6 bg-brutal-gray border-2 border-brutal-black">
                  <p className="text-3xl font-bold text-brutal-black font-heading">
                    {currentWord.translation}
                  </p>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <button
                    onClick={() => handleRating(0)}
                    className="p-4 bg-white border-4 border-brutal-black hover:bg-bauhaus-red hover:text-white transition-colors font-bold text-lg"
                  >
                    AGAIN
                  </button>
                  <button
                    onClick={() => handleRating(1)}
                    className="p-4 bg-white border-4 border-brutal-black hover:bg-bauhaus-yellow hover:text-black transition-colors font-bold text-lg"
                  >
                    HARD
                  </button>
                  <button
                    onClick={() => handleRating(2)}
                    className="p-4 bg-white border-4 border-brutal-black hover:bg-bauhaus-blue hover:text-white transition-colors font-bold text-lg"
                  >
                    GOOD
                  </button>
                  <button
                    onClick={() => handleRating(3)}
                    className="p-4 bg-white border-4 border-brutal-black hover:bg-green-500 hover:text-black transition-colors font-bold text-lg"
                  >
                    EASY
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      {lastReviewFeedback && (
        <div className="border-4 border-brutal-black bg-bauhaus-yellow p-4 shadow-brutal">
          <p className="font-bold uppercase tracking-wide text-xs mb-1">
            Feedback
          </p>
          <p className="font-black text-lg">{lastReviewFeedback.word}</p>
          <p className="font-mono text-sm">{lastReviewFeedback.message}</p>
        </div>
      )}
    </div>
  );
}

export async function getServerSideProps(context: any) {
  const session = await getSession(context);

  if (!session) {
    return {
      redirect: {
        destination: '/auth/signin',
        permanent: false,
      },
    };
  }

  try {
    const rawBase =
      process.env.NEXT_PUBLIC_API_URL ||
      process.env.API_URL ||
      'http://localhost:8000/api/v1';
    const normalizedBase = rawBase.replace(/\/+$/, '');
    const baseUrl = normalizedBase.endsWith('/api/v1')
      ? normalizedBase
      : `${normalizedBase}/api/v1`;
    const directionParamRaw = Array.isArray(context.query?.direction)
      ? context.query?.direction[0]
      : context.query?.direction;
    const directionParam =
      typeof directionParamRaw === 'string' ? directionParamRaw : undefined;
    const isValidDirection = (d: string | undefined): d is PracticeDirection => d === 'fr_to_de' || d === 'de_to_fr';
    const direction = isValidDirection(directionParam) ? directionParam : 'fr_to_de';
    const headers = {
      'Authorization': `Bearer ${session.accessToken}`,
      'Content-Type': 'application/json',
    };

    const [queueRes, summaryRes] = await Promise.all([
      fetch(`${baseUrl}/progress/queue?direction=${direction}`, { headers }),
      fetch(`${baseUrl}/progress/anki/summary`, { headers }),
    ]);
    const raw = queueRes.ok ? await queueRes.json() : [];
    const queueWords = Array.isArray(raw)
      ? raw.map((item: any) => ({
        wordId: item.word_id,
        word: item.word,
        translation: (direction === 'fr_to_de' ? item.german_translation : item.french_translation) || item.english_translation || '',
        difficulty: item.difficulty_level || 1,
        scheduler: item.scheduler || undefined,
        stage: item.stage || item.queue_stage || item.stage_type || null,
      }))
      : [];

    const summary = summaryRes.ok ? await summaryRes.json() : null;
    const counters = {
      newCount: Number(summary?.stage_totals?.new ?? 0),
      learningCount: Number(summary?.stage_totals?.learning ?? 0),
      dueCount: Number(summary?.due_today ?? 0),
    };
    return {
      props: {
        queueWords,
        counters,
        direction,
      },
    };
  } catch (error) {
    console.error('Failed to fetch practice queue:', error);
    return {
      props: {
        queueWords: [],
        counters: { newCount: 0, learningCount: 0, dueCount: 0 },
        direction: 'fr_to_de',
      },
    };
  }
}
