import React from 'react';
import { getSession } from 'next-auth/react';
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
}

interface PracticeProps {
  queueWords: PracticeWord[];
  counters: {
    newCount: number;
    learningCount: number;
    dueCount: number;
  };
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

  const currentWord = queueWords[currentWordIndex];

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

      if (currentWordIndex < queueWords.length - 1) {
        setCurrentWordIndex(currentWordIndex + 1);
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

  if (!queueWords?.length) {
    return (
      <div className="max-w-2xl mx-auto text-center">
        <Card>
          <CardContent className="p-8">
            <h1 className="text-2xl font-bold mb-4">No words to practice</h1>
            <p className="text-gray-600 mb-6">
              Great job! You&apos;re all caught up with your vocabulary practice.
            </p>
            <Button onClick={() => window.location.reload()}>Check Again</Button>
          </CardContent>
        </Card>
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
              Final Score: {score}/{queueWords.length}
            </p>
            <Button onClick={() => window.location.href = '/dashboard'}>Back to Dashboard</Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto">
      <div className="mb-8">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-gray-900">Vocabulary Practice</h1>
          <div className="text-sm text-gray-600">
            {currentWordIndex + 1} of {queueWords.length}
          </div>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2 mt-4">
          <div 
            className="bg-primary-600 h-2 rounded-full transition-all duration-300"
            style={{ width: `${((currentWordIndex + 1) / queueWords.length) * 100}%` }}
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
    const headers = {
      'Authorization': `Bearer ${session.accessToken}`,
      'Content-Type': 'application/json',
    };

    const [queueRes, summaryRes] = await Promise.all([
      fetch(`${baseUrl}/progress/queue`, { headers }),
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
      },
    };
  } catch (error) {
    console.error('Failed to fetch practice queue:', error);
    return {
      props: {
        queueWords: [],
        counters: { newCount: 0, learningCount: 0, dueCount: 0 },
      },
    };
  }
}
