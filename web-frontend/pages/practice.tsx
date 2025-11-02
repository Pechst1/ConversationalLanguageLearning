import React from 'react';
import { getSession } from 'next-auth/react';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card';
import apiService from '@/services/api';
import { CheckCircle, XCircle, RotateCcw } from 'lucide-react';
import toast from 'react-hot-toast';

interface PracticeWord {
  wordId: number;
  word: string;
  translation: string;
  difficulty: number;
}

interface PracticeProps {
  queueWords: PracticeWord[];
}

type LanguageDirection = 'french-to-german' | 'german-to-french';

export default function PracticePage({ queueWords }: PracticeProps) {
  const [currentWordIndex, setCurrentWordIndex] = React.useState(0);
  const [showAnswer, setShowAnswer] = React.useState(false);
  const [score, setScore] = React.useState(0);
  const [completed, setCompleted] = React.useState(false);
  const [languageDirection, setLanguageDirection] = React.useState<LanguageDirection>('french-to-german');

  const currentWord = queueWords[currentWordIndex];

  // Determine what to show based on language direction
  const getCardContent = () => {
    if (!currentWord) return { front: '', back: '' };
    
    if (languageDirection === 'french-to-german') {
      return {
        front: currentWord.word, // French word
        back: currentWord.translation, // German translation
        frontLanguage: 'Französisch',
        backLanguage: 'Deutsch'
      };
    } else {
      return {
        front: currentWord.translation, // German word
        back: currentWord.word, // French translation
        frontLanguage: 'Deutsch',
        backLanguage: 'Französisch'
      };
    }
  };

  const handleRating = async (rating: number) => {
    try {
      // Ensure wordId is properly parsed as integer
      const wordId = parseInt(String(currentWord.wordId), 10);
      if (!Number.isFinite(wordId)) {
        toast.error('Invalid word ID');
        return;
      }

      await apiService.submitReview({
        word_id: wordId,
        rating,
      });

      if (rating >= 2) {
        setScore(score + 1);
      }

      if (currentWordIndex < queueWords.length - 1) {
        setCurrentWordIndex(currentWordIndex + 1);
        setShowAnswer(false);
      } else {
        setCompleted(true);
        toast.success(`Practice completed! Score: ${score + (rating >= 2 ? 1 : 0)}/${queueWords.length}`);
      }
    } catch (error) {
      toast.error('Failed to submit review');
      console.error('Review submission error:', error);
    }
  };

  const resetCard = () => {
    setShowAnswer(false);
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
            <div className="space-y-3">
              <Button onClick={() => window.location.href = '/dashboard'} className="w-full">
                Back to Dashboard
              </Button>
              <Button 
                variant="outline" 
                onClick={() => {
                  setCompleted(false);
                  setCurrentWordIndex(0);
                  setScore(0);
                  setShowAnswer(false);
                }} 
                className="w-full"
              >
                Practice Again
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  const cardContent = getCardContent();

  return (
    <div className="max-w-2xl mx-auto">
      <div className="mb-8">
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-2xl font-bold text-gray-900">Vocabulary Practice</h1>
          <div className="text-sm text-gray-600">
            {currentWordIndex + 1} of {queueWords.length}
          </div>
        </div>
        
        {/* Language Direction Selector */}
        <div className="flex items-center justify-center mb-4">
          <div className="bg-gray-100 rounded-lg p-1 flex">
            <Button
              variant={languageDirection === 'french-to-german' ? 'default' : 'ghost'}
              size="sm"
              onClick={() => {
                setLanguageDirection('french-to-german');
                setShowAnswer(false);
              }}
              className="text-sm"
            >
              Französisch → Deutsch
            </Button>
            <Button
              variant={languageDirection === 'german-to-french' ? 'default' : 'ghost'}
              size="sm"
              onClick={() => {
                setLanguageDirection('german-to-french');
                setShowAnswer(false);
              }}
              className="text-sm"
            >
              Deutsch → Französisch
            </Button>
          </div>
        </div>
        
        <div className="w-full bg-gray-200 rounded-full h-2">
          <div 
            className="bg-primary-600 h-2 rounded-full transition-all duration-300"
            style={{ width: `${((currentWordIndex + 1) / queueWords.length) * 100}%` }}
          />
        </div>
      </div>

      <Card className="min-h-[400px]">
        <CardHeader className="text-center">
          <CardTitle className="text-lg text-gray-600 mb-2">
            {cardContent.frontLanguage}
          </CardTitle>
          <CardDescription className="text-3xl font-bold text-gray-900">
            {showAnswer ? (
              <div className="space-y-4">
                <div className="text-2xl text-gray-700">
                  {cardContent.front}
                </div>
                <div className="border-t pt-4">
                  <div className="text-lg text-gray-600 mb-2">
                    {cardContent.backLanguage}
                  </div>
                  <div className="text-3xl font-bold text-gray-900">
                    {cardContent.back}
                  </div>
                </div>
              </div>
            ) : (
              cardContent.front
            )}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {!showAnswer ? (
            <div className="text-center space-y-3">
              <p className="text-gray-600 mb-4">
                How well do you know this word?
              </p>
              <div className="flex gap-3 justify-center">
                <Button onClick={() => setShowAnswer(true)} className="flex-1 max-w-xs">
                  Show Translation
                </Button>
                <Button 
                  variant="outline" 
                  onClick={resetCard}
                  size="icon"
                  title="Reset card"
                >
                  <RotateCcw className="h-4 w-4" />
                </Button>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <p className="text-center text-gray-600 mb-4">
                How well did you remember this word?
              </p>
              
              <div className="grid grid-cols-2 gap-3">
                <Button 
                  variant="outline" 
                  onClick={() => handleRating(0)}
                  className="border-red-300 text-red-600 hover:bg-red-50 p-4 h-auto flex flex-col gap-2"
                >
                  <XCircle className="h-5 w-5" />
                  <span className="font-semibold">Didn&apos;t Know</span>
                  <span className="text-xs opacity-75">Show again soon</span>
                </Button>
                <Button 
                  variant="outline" 
                  onClick={() => handleRating(1)}
                  className="border-yellow-300 text-yellow-600 hover:bg-yellow-50 p-4 h-auto flex flex-col gap-2"
                >
                  <span className="font-semibold">Hard</span>
                  <span className="text-xs opacity-75">Show again later</span>
                </Button>
                <Button 
                  variant="outline" 
                  onClick={() => handleRating(2)}
                  className="border-green-300 text-green-600 hover:bg-green-50 p-4 h-auto flex flex-col gap-2"
                >
                  <span className="font-semibold">Good</span>
                  <span className="text-xs opacity-75">Show again much later</span>
                </Button>
                <Button 
                  variant="outline" 
                  onClick={() => handleRating(3)}
                  className="border-blue-300 text-blue-600 hover:bg-blue-50 p-4 h-auto flex flex-col gap-2"
                >
                  <CheckCircle className="h-5 w-5" />
                  <span className="font-semibold">Easy</span>
                  <span className="text-xs opacity-75">Wait much longer</span>
                </Button>
              </div>
              
              <div className="text-center pt-4">
                <Button 
                  variant="ghost" 
                  onClick={resetCard}
                  size="sm"
                  className="text-gray-500"
                >
                  <RotateCcw className="h-4 w-4 mr-2" />
                  See question again
                </Button>
              </div>
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

    const response = await fetch(`${baseUrl}/progress/queue`, { headers });
    const raw = response.ok ? await response.json() : [];
    const queueWords = Array.isArray(raw)
      ? raw.map((item: any) => {
          // Ensure proper integer parsing for wordId
          const wordId = parseInt(String(item.word_id || item.id), 10);
          return {
            wordId: Number.isFinite(wordId) ? wordId : 0,
            word: String(item.word || ''),
            translation: String(item.english_translation || item.german_translation || item.translation || ''),
            difficulty: parseInt(String(item.difficulty_level || item.difficulty), 10) || 1,
          };
        })
      : [];

    return {
      props: {
        queueWords,
      },
    };
  } catch (error) {
    console.error('Failed to fetch practice queue:', error);
    return {
      props: {
        queueWords: [],
      },
    };
  }
}
