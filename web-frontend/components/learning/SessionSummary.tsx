import React from 'react';
import { CheckCircle, XCircle, Clock, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import type { SessionStats } from '@/types/learning';

interface SessionSummaryProps {
  stats?: SessionStats | null | undefined;
  onStartNewSession: () => void;
  onReturnToDashboard: () => void;
}

// Enhanced stats validation and normalization
const validateAndNormalizeStats = (rawStats: any): SessionStats => {
  // Handle completely invalid or missing stats
  if (!rawStats || typeof rawStats !== 'object') {
    console.warn('[SessionSummary] Invalid or missing stats object, using defaults:', rawStats);
    return {
      totalReviews: 0,
      correctAnswers: 0,
      xpEarned: 0,
      sessionDuration: 0,
      newCards: 0,
      reviewedCards: 0,
    };
  }

  // Comprehensive stats normalization with multiple fallback fields
  const totalReviews = [
    rawStats.totalReviews,
    rawStats.words_reviewed,
    rawStats.words_practiced,
    rawStats.cards_reviewed,
    rawStats.total_cards,
    0
  ].find(val => typeof val === 'number' && !isNaN(val)) || 0;

  const correctAnswers = [
    rawStats.correctAnswers,
    rawStats.correct_responses,
    rawStats.correct_answers,
    rawStats.successful_reviews,
    Math.max(0, totalReviews - (rawStats.incorrect_responses || rawStats.wrong_answers || 0)),
    0
  ].find(val => typeof val === 'number' && !isNaN(val)) || 0;

  const xpEarned = [
    rawStats.xpEarned,
    rawStats.xp_earned,
    rawStats.experience_points,
    rawStats.points,
    0
  ].find(val => typeof val === 'number' && !isNaN(val)) || 0;

  const sessionDuration = [
    rawStats.sessionDuration,
    rawStats.session_duration,
    rawStats.duration,
    rawStats.time_spent,
    undefined
  ].find(val => typeof val === 'number' && !isNaN(val));

  const newCards = [
    rawStats.newCards,
    rawStats.new_cards,
    rawStats.new_words_introduced,
    rawStats.new_words,
    0
  ].find(val => typeof val === 'number' && !isNaN(val)) || 0;

  const reviewedCards = [
    rawStats.reviewedCards,
    rawStats.reviewed_cards,
    rawStats.cards_reviewed,
    totalReviews,
    0
  ].find(val => typeof val === 'number' && !isNaN(val)) || 0;

  // Validate logical consistency
  const validatedCorrectAnswers = Math.min(Math.max(0, correctAnswers), totalReviews);
  const validatedXpEarned = Math.max(0, xpEarned);
  const validatedNewCards = Math.max(0, newCards);
  const validatedReviewedCards = Math.max(0, reviewedCards);

  return {
    totalReviews: Math.max(0, totalReviews),
    correctAnswers: validatedCorrectAnswers,
    xpEarned: validatedXpEarned,
    sessionDuration,
    newCards: validatedNewCards,
    reviewedCards: validatedReviewedCards,
    // Preserve additional properties if they exist
    ...(rawStats.wordsLearned && { wordsLearned: rawStats.wordsLearned }),
    ...(rawStats.difficultyBreakdown && { difficultyBreakdown: rawStats.difficultyBreakdown }),
  };
};

export default function SessionSummary({
  stats: rawStats,
  onStartNewSession,
  onReturnToDashboard,
}: SessionSummaryProps) {
  // Enhanced stats normalization
  const stats = React.useMemo(() => {
    const normalized = validateAndNormalizeStats(rawStats);
    
    if (process.env.NODE_ENV === 'development') {
      console.log('[SessionSummary] Stats normalization:', { 
        raw: rawStats, 
        normalized 
      });
    }
    
    return normalized;
  }, [rawStats]);

  // Calculate derived values
  const accuracy = React.useMemo(() => {
    if (stats.totalReviews === 0) return 0;
    return Math.round((stats.correctAnswers / stats.totalReviews) * 100);
  }, [stats.totalReviews, stats.correctAnswers]);

  const incorrectAnswers = React.useMemo(() => {
    return Math.max(0, stats.totalReviews - stats.correctAnswers);
  }, [stats.totalReviews, stats.correctAnswers]);

  const sessionDurationMinutes = React.useMemo(() => {
    return stats.sessionDuration ? Math.round(stats.sessionDuration / 60) : null;
  }, [stats.sessionDuration]);

  // Enhanced event dispatch with error handling
  React.useEffect(() => {
    const dispatchSessionCompleteEvent = () => {
      try {
        // Only dispatch if we have valid stats
        if (stats && typeof stats === 'object') {
          const event = new CustomEvent('learningSessionComplete', {
            detail: {
              stats,
              normalizedStats: stats,
              timestamp: new Date().toISOString(),
              accuracy,
              sessionId: rawStats?.sessionId || undefined,
            }
          });
          
          window.dispatchEvent(event);
          
          console.log('[SessionSummary] Session completion event dispatched successfully:', {
            totalReviews: stats.totalReviews,
            correctAnswers: stats.correctAnswers,
            accuracy,
            xpEarned: stats.xpEarned
          });
          
          // Update localStorage for persistence
          if (typeof window !== 'undefined' && window.localStorage) {
            window.localStorage.setItem('lastSessionComplete', JSON.stringify({
              timestamp: new Date().toISOString(),
              stats,
              accuracy
            }));
          }
        } else {
          console.warn('[SessionSummary] Skipping event dispatch due to invalid stats');
        }
      } catch (error) {
        console.error('[SessionSummary] Error dispatching session completion event:', error);
      }
    };

    // Dispatch event after a short delay to ensure other components are ready
    const timeoutId = setTimeout(dispatchSessionCompleteEvent, 100);
    
    return () => clearTimeout(timeoutId);
  }, [stats, accuracy, rawStats]);

  const getPerformanceColor = React.useCallback((acc: number) => {
    if (acc >= 90) return 'text-emerald-600';
    if (acc >= 80) return 'text-green-600';
    if (acc >= 70) return 'text-yellow-600';
    if (acc >= 60) return 'text-orange-600';
    return 'text-red-600';
  }, []);

  const getPerformanceMessage = React.useCallback((acc: number, total: number) => {
    if (total === 0) {
      return 'Ready to start your learning journey? Every step counts!';
    }
    if (acc >= 90) return 'Outstanding! You\'ve truly mastered these concepts.';
    if (acc >= 80) return 'Excellent work! You\'re showing great understanding.';
    if (acc >= 70) return 'Good progress! You\'re on the right track.';
    if (acc >= 60) return 'Keep going! Practice makes perfect.';
    return 'Learning takes time, and you\'re making important progress!';
  }, []);

  const getPerformanceIcon = React.useCallback((acc: number) => {
    if (acc >= 80) return <CheckCircle className="h-16 w-16 text-green-500" />;
    if (acc >= 60) return <Clock className="h-16 w-16 text-yellow-500" />;
    return <AlertCircle className="h-16 w-16 text-blue-500" />;
  }, []);

  return (
    <Card className="w-full max-w-2xl mx-auto shadow-lg">
      <CardHeader className="text-center">
        <div className="mx-auto mb-4">
          {getPerformanceIcon(accuracy)}
        </div>
        <CardTitle className="text-2xl font-bold text-gray-900">
          Session Complete!
        </CardTitle>
        <p className="text-gray-600 mt-2">
          {getPerformanceMessage(accuracy, stats.totalReviews)}
        </p>
      </CardHeader>
      
      <CardContent className="space-y-6">
        {/* Main Stats */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="text-center p-4 bg-blue-50 rounded-lg border border-blue-100">
            <div className="text-2xl font-bold text-blue-600">
              {stats.totalReviews}
            </div>
            <div className="text-sm text-gray-600">Cards Reviewed</div>
          </div>
          
          <div className="text-center p-4 bg-green-50 rounded-lg border border-green-100">
            <div className={`text-2xl font-bold ${getPerformanceColor(accuracy)}`}>
              {accuracy}%
            </div>
            <div className="text-sm text-gray-600">Accuracy</div>
          </div>
          
          <div className="text-center p-4 bg-purple-50 rounded-lg border border-purple-100">
            <div className="text-2xl font-bold text-purple-600">
              {stats.xpEarned}
            </div>
            <div className="text-sm text-gray-600">XP Earned</div>
          </div>
        </div>

        {/* Detailed Breakdown */}
        {stats.totalReviews > 0 && (
          <div className="space-y-3">
            <h3 className="font-semibold text-gray-900">Session Details</h3>
            
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg border border-gray-100">
                <div className="flex items-center gap-2">
                  <CheckCircle className="h-4 w-4 text-green-500" />
                  <span>Correct</span>
                </div>
                <span className="font-semibold text-green-600">
                  {stats.correctAnswers}
                </span>
              </div>
              
              <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg border border-gray-100">
                <div className="flex items-center gap-2">
                  <XCircle className="h-4 w-4 text-red-500" />
                  <span>Incorrect</span>
                </div>
                <span className="font-semibold text-red-600">
                  {incorrectAnswers}
                </span>
              </div>
              
              <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg border border-gray-100">
                <div className="flex items-center gap-2">
                  <Clock className="h-4 w-4 text-blue-500" />
                  <span>Duration</span>
                </div>
                <span className="font-semibold text-blue-600">
                  {sessionDurationMinutes ? `${sessionDurationMinutes}m` : 'N/A'}
                </span>
              </div>
              
              <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg border border-gray-100">
                <div className="flex items-center gap-2">
                  <span>📚</span>
                  <span>New Words</span>
                </div>
                <span className="font-semibold text-gray-600">
                  {stats.newCards}
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Progress Encouragement */}
        <div className="text-center p-4 bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg border border-blue-100">
          <p className="text-sm text-gray-700 mb-2">
            {getPerformanceMessage(accuracy, stats.totalReviews)}
          </p>
          <p className="text-xs text-gray-500">
            Your progress has been automatically saved and will be reflected in your statistics.
          </p>
        </div>

        {/* Debug Information (Development Only) */}
        {process.env.NODE_ENV === 'development' && (
          <details className="text-xs text-gray-500 bg-gray-50 p-3 rounded border">
            <summary className="cursor-pointer font-semibold mb-2">Debug Information</summary>
            <div className="space-y-2 font-mono">
              <div><strong>Raw Stats:</strong> {JSON.stringify(rawStats, null, 2)}</div>
              <div><strong>Normalized:</strong> {JSON.stringify(stats, null, 2)}</div>
              <div><strong>Calculated Accuracy:</strong> {accuracy}%</div>
            </div>
          </details>
        )}

        {/* Action Buttons */}
        <div className="flex flex-col sm:flex-row gap-3 pt-4">
          <Button 
            onClick={onStartNewSession} 
            className="flex-1"
            variant="default"
            size="lg"
          >
            Start New Session
          </Button>
          <Button 
            onClick={onReturnToDashboard} 
            className="flex-1"
            variant="outline"
            size="lg"
          >
            Return to Dashboard
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}