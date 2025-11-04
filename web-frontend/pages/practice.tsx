import React from 'react';
import { getSession } from 'next-auth/react';
import { format, formatDistanceToNow } from 'date-fns';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card';
import apiService from '@/services/api';
import { CheckCircle, Clock3, CircleDot, Type, XCircle } from 'lucide-react';
import toast from 'react-hot-toast';

interface PracticeWord {
  wordId: number;
  word: string;
  translation: string;
  difficulty: number;
  scheduler?: 'anki' | 'fsrs' | string;
  language?: string;
  partOfSpeech?: string;
  state: string;
  nextReview?: string | null;
  scheduledDays?: number | null;
  isNew?: boolean;
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

const directionOptions: { value: PracticeDirection; label: string }[] = [
  { value: 'fr_to_de', label: 'Französisch → Deutsch' },
  { value: 'de_to_fr', label: 'Deutsch → Französisch' },
];

function isValidDirection(value: unknown): value is PracticeDirection {
  return value === 'fr_to_de' || value === 'de_to_fr';
}

function mapQueueItem(item: any): PracticeWord {
  return {
    wordId: item.word_id,
    word: item.word,
    translation: item.english_translation || '',
    difficulty: item.difficulty_level || 1,
    scheduler: item.scheduler || undefined,
  };
}

export default function PracticePage({
  queueWords,
  counters,
  direction: initialDirection = 'fr_to_de',
}: PracticeProps) {
  const router = useRouter();
  const [currentWordIndex, setCurrentWordIndex] = React.useState(0);
  const [showAnswer, setShowAnswer] = React.useState(false);
  const [score, setScore] = React.useState(0);
  const [completed, setCompleted] = React.useState(false);
  const [counts] = React.useState(counters);
  const [selectedDirection, setSelectedDirection] = React.useState<PracticeDirection>(
    initialDirection,
  );
  const [words, setWords] = React.useState(queueWords);
  const [isLoadingDirection, setIsLoadingDirection] = React.useState(false);
  const [pendingDirection, setPendingDirection] = React.useState<PracticeDirection | null>(
    null,
  );

  const fetchQueue = React.useCallback(async (direction: PracticeDirection) => {
    const freshQueue = await apiService.getProgressQueue({ direction });
    return Array.isArray(freshQueue) ? freshQueue.map(mapQueueItem) : [];
  }, []);

  const currentWord = queueWords[currentWordIndex];
  const nextReviewDate = currentWord?.nextReview ? new Date(currentWord.nextReview) : null;
  const formattedNextReview = nextReviewDate
    ? formatDistanceToNow(nextReviewDate, { addSuffix: true })
    : 'Not scheduled';
  const exactNextReview = nextReviewDate ? format(nextReviewDate, 'PPpp') : undefined;
  const cleanedState = currentWord?.state
    ? currentWord.state.replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase())
    : undefined;
  const cleanedPartOfSpeech = currentWord?.partOfSpeech
    ? currentWord.partOfSpeech
        .replace(/_/g, ' ')
        .toLowerCase()
        .replace(/\b\w/g, (char) => char.toUpperCase())
    : undefined;

  const handleRating = async (rating: number) => {
    if (!currentWord) {
      toast.error('No word available to review');
      return;
    }
    try {
      if (currentWord.scheduler && currentWord.scheduler.toLowerCase() === 'anki') {
        await apiService.submitAnkiReview({ word_id: currentWord.wordId, rating });
      } else {
        await apiService.submitReview({ word_id: currentWord.wordId, rating });
      }

      if (rating >= 2) {
        setScore(score + 1);
      }

      if (currentWordIndex < words.length - 1) {
        setCurrentWordIndex(currentWordIndex + 1);
        setShowAnswer(false);
      } else {
        setCompleted(true);
        toast.success(`Practice completed! Score: ${score + (rating >= 2 ? 1 : 0)}/${words.length}`);
      }
    } catch (error) {
      toast.error('Failed to submit review');
    }
  };

  if (!words?.length) {
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
      <div className="max-w-2xl mx-auto">
        {directionToggle}
        <div className="text-center">
          <Card>
            <CardContent className="p-8">
              <CheckCircle className="h-16 w-16 text-green-500 mx-auto mb-4" />
              <h1 className="text-2xl font-bold mb-4">Practice Complete!</h1>
              <p className="text-gray-600 mb-6">
                Final Score: {score}/{words.length}
              </p>
              <Button onClick={() => window.location.href = '/dashboard'}>Back to Dashboard</Button>
            </CardContent>
          </Card>
        </div>
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
            {currentWordIndex + 1} of {words.length}
          </div>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2 mt-4">
          <div
            className="bg-primary-600 h-2 rounded-full transition-all duration-300"
            style={{ width: `${((currentWordIndex + 1) / words.length) * 100}%` }}
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
          language: item.language || undefined,
          partOfSpeech: item.part_of_speech || undefined,
          state: item.state || 'unknown',
          nextReview: item.next_review || null,
          scheduledDays: item.scheduled_days ?? null,
          isNew: item.is_new ?? undefined,
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
