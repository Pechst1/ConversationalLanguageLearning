import React from 'react';
import { CheckCircle, XCircle, Clock } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import type { SessionStats } from '@/types/learning';

interface SessionSummaryProps {
  stats: SessionStats;
  onStartNewSession: () => void;
  onReturnToDashboard: () => void;
}

export default function SessionSummary({
  stats,
  onStartNewSession,
  onReturnToDashboard,
}: SessionSummaryProps) {
  // Emit custom event when component mounts to notify other parts of the app
  React.useEffect(() => {
    // Dispatch custom event for session completion
    const event = new CustomEvent('learningSessionComplete', {
      detail: {
        stats,
        timestamp: new Date().toISOString(),
      }
    });
    window.dispatchEvent(event);
    
    // Also try to trigger page refresh for progress tab if it's open
    try {
      if (typeof window !== 'undefined' && window.localStorage) {
        window.localStorage.setItem('lastSessionComplete', new Date().toISOString());
      }
    } catch (error) {
      console.debug('Could not update localStorage:', error);
    }
  }, [stats]);

  const calculateAccuracy = () => {
    const total = stats.totalReviews;
    if (total === 0) return 0;
    const correct = stats.correctAnswers;
    return Math.round((correct / total) * 100);
  };

  const getPerformanceColor = (accuracy: number) => {
    if (accuracy >= 80) return 'text-green-600';
    if (accuracy >= 60) return 'text-yellow-600';
    return 'text-red-600';
  };

  const accuracy = calculateAccuracy();

  return (
    <Card className="w-full max-w-2xl mx-auto">
      <CardHeader className="text-center">
        <div className="mx-auto mb-4">
          <CheckCircle className="h-16 w-16 text-green-500" />
        </div>
        <CardTitle className="text-2xl font-bold text-gray-900">
          Session Complete!
        </CardTitle>
        <p className="text-gray-600 mt-2">
          Great work! Here's how you did in this session.
        </p>
      </CardHeader>
      
      <CardContent className="space-y-6">
        {/* Main Stats */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="text-center p-4 bg-blue-50 rounded-lg">
            <div className="text-2xl font-bold text-blue-600">
              {stats.totalReviews}
            </div>
            <div className="text-sm text-gray-600">Cards Reviewed</div>
          </div>
          
          <div className="text-center p-4 bg-green-50 rounded-lg">
            <div className={`text-2xl font-bold ${getPerformanceColor(accuracy)}`}>
              {accuracy}%
            </div>
            <div className="text-sm text-gray-600">Accuracy</div>
          </div>
          
          <div className="text-center p-4 bg-purple-50 rounded-lg">
            <div className="text-2xl font-bold text-purple-600">
              {stats.xpEarned || 0}
            </div>
            <div className="text-sm text-gray-600">XP Earned</div>
          </div>
        </div>

        {/* Detailed Breakdown */}
        <div className="space-y-3">
          <h3 className="font-semibold text-gray-900">Session Details</h3>
          
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
              <div className="flex items-center gap-2">
                <CheckCircle className="h-4 w-4 text-green-500" />
                <span>Correct Answers</span>
              </div>
              <span className="font-semibold text-green-600">
                {stats.correctAnswers}
              </span>
            </div>
            
            <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
              <div className="flex items-center gap-2">
                <XCircle className="h-4 w-4 text-red-500" />
                <span>Incorrect Answers</span>
              </div>
              <span className="font-semibold text-red-600">
                {stats.totalReviews - stats.correctAnswers}
              </span>
            </div>
            
            <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
              <div className="flex items-center gap-2">
                <Clock className="h-4 w-4 text-blue-500" />
                <span>Session Duration</span>
              </div>
              <span className="font-semibold text-blue-600">
                {stats.sessionDuration ? `${Math.round(stats.sessionDuration / 60)}m` : 'N/A'}
              </span>
            </div>
            
            <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
              <div className="flex items-center gap-2">
                <span>📚</span>
                <span>New Cards</span>
              </div>
              <span className="font-semibold text-gray-600">
                {stats.newCards || 0}
              </span>
            </div>
          </div>
        </div>

        {/* Progress Encouragement */}
        <div className="text-center p-4 bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg">
          <p className="text-sm text-gray-700 mb-2">
            {accuracy >= 80 
              ? 'Excellent work! You\'re mastering these words.' 
              : accuracy >= 60 
              ? 'Good progress! Keep practicing to improve.' 
              : 'Don\'t worry, learning takes time. Keep going!'}
          </p>
          <p className="text-xs text-gray-500">
            Your progress has been automatically saved and will be reflected in your statistics.
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex flex-col sm:flex-row gap-3">
          <Button 
            onClick={onStartNewSession} 
            className="flex-1"
            variant="default"
          >
            Start New Session
          </Button>
          <Button 
            onClick={onReturnToDashboard} 
            className="flex-1"
            variant="outline"
          >
            Return to Dashboard
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
