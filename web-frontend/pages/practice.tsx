import React from 'react';
import { getSession } from 'next-auth/react';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card';
import apiService from '@/services/api';
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

const FETCH_THRESHOLD = 3;
const FETCH_LIMIT = 10;

export default function PracticePage({ queueWords, counters }: PracticeProps) {
  const [currentWordIndex, setCurrentWordIndex] = React.useState(0);
  const [showAnswer, setShowAnswer] = React.useState(false);
  const [score, setScore] = React.useState(0);
  const [completed, setCompleted] = React.useState(false);
  const [counts, setCounts] = React.useState(counters);
  const [localQueue, setLocalQueue] = React.useState(queueWords);
  const [isFetchingMore, setIsFetchingMore] = React.useState(false);
  const [finalTotal, setFinalTotal] = React.useState(queueWords.length);

  const queueRef = React.useRef(localQueue);

  React.useEffect(() => {
    queueRef.current = localQueue;
  }, [localQueue]);

  React.useEffect(() => {
    setCounts(counters);
  }, [counters]);

  const currentWord = localQueue[currentWordIndex];

  const applySummary = React.useCallback((summary: any) => {
    if (!summary) return;
    setCounts({
      newCount: Number(summary?.stage_totals?.new ?? summary?.new ?? 0),
      learningCount: Number(summary?.stage_totals?.learning ?? summary?.learning ?? 0),
      dueCount: Number(summary?.due_today ?? summary?.due ?? 0),
    });
  }, []);

  const decrementStageCount = React.useCallback((stage?: string) => {
    if (!stage) return;
    const normalized = stage.toLowerCase();
    const key =
      normalized.includes('new')
        ? 'newCount'
        : normalized.includes('learn')
        ? 'learningCount'
        : normalized.includes('due')
        ? 'dueCount'
        : null;
    if (!key) return;
    setCounts((prev) => ({
      ...prev,
      [key]: Math.max(0, (prev?.[key as keyof typeof prev] as number) - 1),
    }));
  }, []);

  const refreshSummary = React.useCallback(async () => {
    try {
      const summary = await apiService.getAnkiSummary();
      applySummary(summary);
    } catch (error) {
      console.error('Failed to refresh Anki summary', error);
    }
  }, [applySummary]);

  const mapQueueItem = React.useCallback((item: any): PracticeWord => ({
    wordId: item.word_id,
    word: item.word,
    translation: item.english_translation || '',
    difficulty: item.difficulty_level || 1,
    scheduler: item.scheduler || undefined,
    stage: item.stage || item.queue_stage || item.stage_type || undefined,
  }), []);

  const loadMoreItems = React.useCallback(async () => {
    if (isFetchingMore) {
      return queueRef.current.length;
    }

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

  const handleRating = async (rating: number) => {
    if (!currentWord) {
      return;
    }

    const updatedScore = score + (rating >= 2 ? 1 : 0);

    try {
      const isAnki = currentWord.scheduler && currentWord.scheduler.toLowerCase() === 'anki';
      const reviewResult = isAnki
        ? await apiService.submitAnkiReview({ word_id: currentWord.wordId, rating })
        : await apiService.submitReview({ word_id: currentWord.wordId, rating });

      setScore((prev) => prev + (rating >= 2 ? 1 : 0));

      if (reviewResult?.summary || reviewResult?.stage_totals) {
        applySummary(reviewResult.summary ?? reviewResult);
      } else {
        decrementStageCount(currentWord.stage);
        await refreshSummary();
      }

      const nextIndex = currentWordIndex + 1;
      const queueLength = await ensureQueueDepth(nextIndex);

      if (nextIndex < queueLength) {
        setCurrentWordIndex(nextIndex);
        setShowAnswer(false);
      } else {
        setCompleted(true);
        const totalItems = Math.max(queueLength, nextIndex);
        setFinalTotal(totalItems);
        toast.success(`Practice completed! Score: ${updatedScore}/${totalItems}`);
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
        </CardHeader>
        <CardContent className="space-y-6">
          {!showAnswer ? (
            <div className="text-center">
              <Button onClick={() => setShowAnswer(true)} className="w-full">
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
