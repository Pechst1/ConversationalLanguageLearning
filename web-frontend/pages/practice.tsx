import React from 'react';
import { getSession } from 'next-auth/react';
import { format, formatDistanceToNow } from 'date-fns';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card';
import apiService from '@/services/api';
import { AnkiReviewResponse, ReviewResponse } from '@/types/reviews';
import { CheckCircle, XCircle } from 'lucide-react';
import toast from 'react-hot-toast';

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

export default function PracticePage({ queueWords, counters }: PracticeProps) {
  const [currentWordIndex, setCurrentWordIndex] = React.useState(0);
  const [showAnswer, setShowAnswer] = React.useState(false);
  const [score, setScore] = React.useState(0);
  const [completed, setCompleted] = React.useState(false);
  const [counts] = React.useState(counters);
  const [lastReviewFeedback, setLastReviewFeedback] = React.useState<{
    word: string;
    message: string;
  } | null>(null);

  const cardShownAtRef = React.useRef<number>(Date.now());

    setIsFetchingMore(true);
    let updatedLength = queueRef.current.length;
    try {
      const raw = await apiService.getProgressQueue({ limit: FETCH_LIMIT });
      if (!Array.isArray(raw) || !raw.length) {
        return updatedLength;
      }

      setLocalQueue((prev) => {
        const existingIds = new Set(prev.map((item) => item.wordId));
        const mapped = raw
          .map(mapQueueItem)
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
  }, [isFetchingMore, mapQueueItem]);

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

  if (!localQueue?.length) {
    return (
      <div className="max-w-2xl mx-auto">
        {directionToggle}
        <div className="text-center">
          <Card>
            <CardContent className="p-8">
              <h1 className="text-2xl font-bold mb-4">No words to practice</h1>
              <p className="text-gray-600 mb-6">
                Great job! You&apos;re all caught up with your vocabulary practice.
              </p>
              <Button onClick={handleRefreshQueue} loading={isLoadingDirection}>
                Check Again
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  if (completed) {
    return (
      <div className="max-w-2xl mx-auto text-center">
        <Card>
          <CardContent className="p-8">
            <CheckCircle className="h-16 w-16 text-green-500 mx-auto mb-4" />
            <h1 className="text-2xl font-bold mb-4">Practice Complete!</h1>
            <p className="text-gray-600 mb-6">
              Final Score: {score}/{finalTotal}
            </p>
            <Button onClick={() => window.location.href = '/dashboard'}>Back to Dashboard</Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!currentWord) {
    return (
      <div className="max-w-2xl mx-auto text-center">
        <Card>
          <CardContent className="p-8 space-y-4">
            <h1 className="text-2xl font-bold">Loading next word...</h1>
            <p className="text-gray-600">Fetching more practice items for you.</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto">
      {directionToggle}

      <div className="mb-8">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-gray-900">Vocabulary Practice</h1>
          <div className="text-sm text-gray-600">
            {Math.min(currentWordIndex + 1, localQueue.length)} of {localQueue.length || finalTotal}
          </div>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2 mt-4">
          <div
            className="bg-primary-600 h-2 rounded-full transition-all duration-300"
            style={{
              width: `${
                localQueue.length
                  ? Math.min(((currentWordIndex + 1) / localQueue.length) * 100, 100)
                  : 0
              }%`,
            }}
          />
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-center text-3xl font-bold">
            {cleanSurface(currentWord.word, currentWord.translation)}
          </CardTitle>
          <CardDescription className="text-center">
            How well do you know this word?
          </CardDescription>
          {(cleanedState || cleanedPartOfSpeech || formattedNextReview) && (
            <div className="practice-meta" role="list" aria-label="Word scheduling metadata">
              {cleanedState && (
                <span
                  role="listitem"
                  className="practice-chip practice-chip--state"
                  aria-label={`Scheduling state: ${cleanedState}`}
                  title={`Scheduling state: ${cleanedState}`}
                >
                  <CircleDot aria-hidden="true" className="practice-chip__icon" />
                  <span className="sr-only">Scheduling state:</span>
                  <span aria-hidden="true">{cleanedState}</span>
                </span>
              )}
              {cleanedPartOfSpeech && (
                <span
                  role="listitem"
                  className="practice-chip practice-chip--pos"
                  aria-label={`Part of speech: ${cleanedPartOfSpeech}`}
                  title={`Part of speech: ${cleanedPartOfSpeech}`}
                >
                  <Type aria-hidden="true" className="practice-chip__icon" />
                  <span className="sr-only">Part of speech:</span>
                  <span aria-hidden="true">{cleanedPartOfSpeech}</span>
                </span>
              )}
              <span
                role="listitem"
                className="practice-chip practice-chip--review"
                aria-label={`Next review ${formattedNextReview}`}
                title={
                  exactNextReview
                    ? `Next review ${formattedNextReview} (${exactNextReview})`
                    : `Next review ${formattedNextReview}`
                }
              >
                <Clock3 aria-hidden="true" className="practice-chip__icon" />
                <span className="sr-only">Next review:</span>
                <span aria-hidden="true">{formattedNextReview}</span>
              </span>
            </div>
          )}
        </CardHeader>
        <CardContent className="space-y-6">
          {!showAnswer ? (
            <div className="text-center">
              <Button onClick={handleShowTranslation} className="w-full">
                Show Translation
              </Button>
            </div>
          ) : (
            <>
              <div className="text-center p-4 bg-gray-50 rounded-lg">
                <p className="text-xl font-semibold text-gray-900">
                  {currentWord.translation}
                </p>
              </div>
              
              <div className="space-y-3">
                <p className="text-center text-gray-600 mb-4">
                  How well did you remember this word?
                </p>
                
                <div className="grid grid-cols-2 gap-3">
                  <Button
                    variant="outline"
                    onClick={() => handleRating(0)}
                    className="border-red-300 text-red-600 hover:bg-red-50"
                  >
                    <XCircle className="mr-2 h-4 w-4" />
                    Didn&apos;t Know
                  </Button>
                  <Button 
                    variant="outline" 
                    onClick={() => handleRating(1)}
                    className="border-yellow-300 text-yellow-600 hover:bg-yellow-50"
                  >
                    Hard
                  </Button>
                  <Button 
                    variant="outline" 
                    onClick={() => handleRating(2)}
                    className="border-green-300 text-green-600 hover:bg-green-50"
                  >
                    Good
                  </Button>
                  <Button 
                    variant="outline" 
                    onClick={() => handleRating(3)}
                    className="border-blue-300 text-blue-600 hover:bg-blue-50"
                  >
                    <CheckCircle className="mr-2 h-4 w-4" />
                    Easy
                  </Button>
                </div>
                <div className="mt-4 flex items-center justify-center gap-4 text-sm">
                  <span className="text-blue-700">
                    New (Blue): <span className="font-semibold">{counts.newCount}</span>
                  </span>
                  <span className="text-red-700">
                    Learning (Red): <span className="font-semibold">{counts.learningCount}</span>
                  </span>
                  <span className="text-green-700">
                    Due (Green): <span className="font-semibold">{counts.dueCount}</span>
                  </span>
                </div>
              </div>
            </>
          )}
          {lastReviewFeedback && (
            <div className="rounded-lg border border-blue-200 bg-blue-50 p-4 text-sm text-blue-900">
              <p className="text-xs font-semibold uppercase tracking-wide text-blue-700">
                Spaced repetition feedback
              </p>
              <p className="mt-1 font-semibold">{lastReviewFeedback.word}</p>
              <p className="mt-1 text-sm font-normal">{lastReviewFeedback.message}</p>
            </div>
          )}
        </CardContent>
      </Card>
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
          translation: item.english_translation || '',
          difficulty: item.difficulty_level || 1,
          scheduler: item.scheduler || undefined,
          stage: item.stage || item.queue_stage || item.stage_type || undefined,
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
