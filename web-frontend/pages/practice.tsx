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
      <button
        onClick={toggleDirection}
        className="flex items-center gap-2 bg-white px-4 py-2 border-2 border-black font-bold text-sm uppercase shadow-[4px_4px_0px_0px_#000] hover:-translate-y-1 hover:shadow-[6px_6px_0px_0px_#000] active:translate-y-0 active:shadow-[2px_2px_0px_0px_#000] transition-all"
      >
        <RefreshCw className="w-4 h-4" />
        Switch to {direction === 'fr_to_de' ? 'DE → FR' : 'FR → DE'}
      </button>
    </div>
  );

  if (!localQueue?.length) {
    return (
      <div className="max-w-2xl mx-auto p-4 space-y-8">
        <AnkiSync onSyncComplete={() => handleRefreshQueue()} />
        <div className="mt-8 text-center bg-white border-4 border-black p-12 shadow-[12px_12px_0px_0px_#000]">
          <h1 className="text-5xl font-black mb-4 uppercase tracking-tighter">No Words</h1>
          <p className="text-xl font-bold mb-8 text-gray-600">
            You&apos;re all caught up for now. Great job!
          </p>
          <button
            onClick={() => handleRefreshQueue()}
            disabled={isLoadingDirection}
            className="bg-bauhaus-yellow text-black border-4 border-black font-black text-xl px-8 py-4 uppercase tracking-widest hover:-translate-y-2 hover:shadow-[8px_8px_0px_0px_#000] transition-all disabled:opacity-50"
          >
            {isLoadingDirection ? 'Checking...' : 'Check Again'}
          </button>
        </div>
      </div>
    );
  }

  if (completed) {
    return (
      <div className="max-w-2xl mx-auto text-center p-4">
        <div className="bg-white border-4 border-black p-12 shadow-[12px_12px_0px_0px_#000]">
          <div className="bg-bauhaus-green w-24 h-24 mx-auto mb-6 flex items-center justify-center border-4 border-black shadow-[4px_4px_0px_0px_#000]">
            <CheckCircle className="h-12 w-12 text-black" />
          </div>
          <h1 className="text-5xl font-black mb-4 uppercase tracking-tighter">Complete</h1>
          <p className="text-3xl font-black mb-2 bg-bauhaus-yellow inline-block px-4 py-1 border-2 border-black rotate-2 shadow-[4px_4px_0px_0px_#000]">
            Score: {score}/{finalTotal}
          </p>
          <p className="text-gray-600 font-bold mt-6 mb-8">Session complete. See you next time!</p>
          <button
            onClick={() => window.location.href = '/dashboard'}
            className="bg-bauhaus-blue text-white border-4 border-black font-black text-xl px-8 py-4 uppercase tracking-widest hover:-translate-y-2 hover:shadow-[8px_8px_0px_0px_#000] transition-all"
          >
            Back to Dashboard
          </button>
        </div>
      </div>
    );
  }

  if (!currentWord) {
    return (
      <div className="max-w-2xl mx-auto text-center p-4">
        <div className="bg-white border-4 border-black p-8 shadow-[8px_8px_0px_0px_#000] animate-pulse">
          <h1 className="text-2xl font-black uppercase">Loading...</h1>
        </div>
      </div>
    );
  }

  const cleanedState = formatStateLabel(currentWord.stage);

  return (
    <div className="max-w-2xl mx-auto p-4 space-y-8">
      <div className="flex justify-between items-center">
        <h1 className="text-4xl font-black uppercase tracking-tighter">Practice</h1>
        <AnkiSync onSyncComplete={() => handleRefreshQueue()} />
      </div>

      {directionToggle}

      <div className="mb-8">
        <div className="flex items-center justify-between font-bold text-sm mb-2 uppercase tracking-tight">
          <span>Progress</span>
          <span>{Math.min(currentWordIndex + 1, localQueue.length)} / {localQueue.length || finalTotal}</span>
        </div>
        <div className="w-full bg-gray-200 border-4 border-black h-6 p-0.5">
          <div
            className="bg-bauhaus-blue h-full transition-all duration-300 border-r-2 border-black"
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
        <div className="bg-white border-4 border-black p-8 min-h-[400px] flex flex-col justify-between shadow-[12px_12px_0px_0px_#000] transition-transform duration-300 group-hover:-translate-y-1 group-hover:shadow-[16px_16px_0px_0px_#000]">

          <div className="space-y-6">
            <div className="flex justify-center gap-2">
              {cleanedState && (
                <span className="px-3 py-1 bg-bauhaus-yellow border-2 border-black font-bold text-xs uppercase tracking-wider shadow-[2px_2px_0px_0px_#000]">
                  {cleanedState}
                </span>
              )}
              {currentWord.scheduler === 'anki' && (
                <span className="px-3 py-1 bg-bauhaus-blue text-white border-2 border-black font-bold text-xs uppercase tracking-wider shadow-[2px_2px_0px_0px_#000]">
                  ANKI
                </span>
              )}
            </div>

            <h2 className="text-5xl font-black text-center uppercase tracking-tight break-words py-8">
              {cleanSurface(currentWord.word, currentWord.translation)}
            </h2>

            {!showAnswer && (
              <p className="text-center text-gray-500 font-bold uppercase tracking-widest text-sm">
                How well do you know this word?
              </p>
            )}
          </div>

          <div className="space-y-6 mt-8">
            {!showAnswer ? (
              <div className="text-center">
                <button
                  onClick={handleShowTranslation}
                  className="w-full bg-black text-white hover:bg-bauhaus-red border-4 border-transparent hover:border-black transition-all font-black text-2xl py-6 uppercase tracking-widest shadow-[4px_4px_0px_0px_rgba(0,0,0,0)] hover:shadow-[8px_8px_0px_0px_#000]"
                >
                  Reveal
                </button>
              </div>
            ) : (
              <>
                <div className="text-center p-6 bg-gray-100 border-4 border-black shadow-[4px_4px_0px_0px_#000]">
                  <p className="text-3xl font-black text-black">
                    {currentWord.translation}
                  </p>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <button
                    onClick={() => handleRating(0)}
                    className="p-4 bg-white border-4 border-black hover:bg-bauhaus-red hover:text-white transition-all font-black text-lg uppercase shadow-[4px_4px_0px_0px_#000] hover:shadow-[6px_6px_0px_0px_#000] hover:-translate-y-1 active:translate-y-0 active:shadow-[2px_2px_0px_0px_#000]"
                  >
                    Again
                  </button>
                  <button
                    onClick={() => handleRating(1)}
                    className="p-4 bg-white border-4 border-black hover:bg-bauhaus-yellow hover:text-black transition-all font-black text-lg uppercase shadow-[4px_4px_0px_0px_#000] hover:shadow-[6px_6px_0px_0px_#000] hover:-translate-y-1 active:translate-y-0 active:shadow-[2px_2px_0px_0px_#000]"
                  >
                    Hard
                  </button>
                  <button
                    onClick={() => handleRating(2)}
                    className="p-4 bg-white border-4 border-black hover:bg-bauhaus-blue hover:text-white transition-all font-black text-lg uppercase shadow-[4px_4px_0px_0px_#000] hover:shadow-[6px_6px_0px_0px_#000] hover:-translate-y-1 active:translate-y-0 active:shadow-[2px_2px_0px_0px_#000]"
                  >
                    Good
                  </button>
                  <button
                    onClick={() => handleRating(3)}
                    className="p-4 bg-white border-4 border-black hover:bg-green-500 hover:text-black transition-all font-black text-lg uppercase shadow-[4px_4px_0px_0px_#000] hover:shadow-[6px_6px_0px_0px_#000] hover:-translate-y-1 active:translate-y-0 active:shadow-[2px_2px_0px_0px_#000]"
                  >
                    Easy
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      {lastReviewFeedback && (
        <div className="border-4 border-black bg-bauhaus-yellow p-4 shadow-[8px_8px_0px_0px_#000]">
          <p className="font-black uppercase tracking-widest text-xs mb-2 border-b-2 border-black pb-1 inline-block">
            Last Review
          </p>
          <div className="flex flex-col gap-1">
            <p className="font-black text-xl">{lastReviewFeedback.word}</p>
            <p className="font-medium text-sm border-l-4 border-black pl-3 py-1 bg-white/50">
              {lastReviewFeedback.message}
            </p>
          </div>
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
