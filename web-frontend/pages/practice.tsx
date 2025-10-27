import React from 'react';
import { getSession } from 'next-auth/react';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card';
import apiService from '@/services/api';
import { CheckCircle, XCircle } from 'lucide-react';
import toast from 'react-hot-toast';

interface PracticeProps {
  queueWords: {
    id: number;
    text: string;
    translation: string;
    difficulty: number;
  }[];
}

export default function PracticePage({ queueWords }: PracticeProps) {
  const [currentWordIndex, setCurrentWordIndex] = React.useState(0);
  const [showAnswer, setShowAnswer] = React.useState(false);
  const [score, setScore] = React.useState(0);
  const [completed, setCompleted] = React.useState(false);

  const currentWord = queueWords[currentWordIndex];

  const handleRating = async (rating: number) => {
    try {
      await apiService.submitReview({
        word_id: currentWord.id,
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
    }
  };

  if (!queueWords?.length) {
    return (
      <div className="max-w-2xl mx-auto text-center">
        <Card>
          <CardContent className="p-8">
            <h1 className="text-2xl font-bold mb-4">No words to practice</h1>
            <p className="text-gray-600 mb-6">
              Great job! You're all caught up with your vocabulary practice.
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
            {currentWord.text}
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
                    Didn't Know
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
    const baseUrl = process.env.API_URL || 'http://localhost:8000';
    const headers = {
      'Authorization': `Bearer ${session.accessToken}`,
      'Content-Type': 'application/json',
    };

    const response = await fetch(`${baseUrl}/api/v1/progress/queue`, { headers });
    const queueWords = response.ok ? await response.json() : [];

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