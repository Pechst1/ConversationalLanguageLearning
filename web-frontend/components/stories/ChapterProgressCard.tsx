import React from 'react';
import { CheckCircle, BookOpen, Award, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';

interface ChapterProgressCardProps {
  goalsCompleted: number;
  totalGoals: number;
  vocabularyUsed: number;
  xpEarned?: number;
  canComplete: boolean;
  onComplete: () => void;
  loading?: boolean;
}

export default function ChapterProgressCard({
  goalsCompleted,
  totalGoals,
  vocabularyUsed,
  xpEarned = 0,
  canComplete,
  onComplete,
  loading = false,
}: ChapterProgressCardProps) {
  const progressPercent = totalGoals > 0 ? (goalsCompleted / totalGoals) * 100 : 0;
  const isPerfect = goalsCompleted === totalGoals;

  return (
    <Card className="border-2 border-primary-200">
      <CardHeader>
        <CardTitle className="text-lg flex items-center gap-2">
          <CheckCircle className="h-5 w-5 text-primary-600" />
          Chapter Progress
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Goals Progress */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-gray-700">Goals Completed</span>
            <span className="text-sm font-bold text-primary-600">
              {goalsCompleted} / {totalGoals}
            </span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-3 overflow-hidden">
            <div
              className={`h-3 rounded-full transition-all duration-500 ${
                isPerfect
                  ? 'bg-gradient-to-r from-green-500 to-emerald-500'
                  : 'bg-gradient-to-r from-primary-500 to-blue-600'
              }`}
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </div>

        {/* Vocabulary Used */}
        <div className="flex items-center gap-3 p-3 bg-blue-50 rounded-lg border border-blue-200">
          <BookOpen className="h-5 w-5 text-blue-600 flex-shrink-0" />
          <div className="flex-1">
            <p className="text-xs text-blue-700 font-medium">Vocabulary Used</p>
            <p className="text-lg font-bold text-blue-900">{vocabularyUsed} words</p>
          </div>
        </div>

        {/* XP Earned */}
        {xpEarned > 0 && (
          <div className="flex items-center gap-3 p-3 bg-purple-50 rounded-lg border border-purple-200">
            <Sparkles className="h-5 w-5 text-purple-600 flex-shrink-0" />
            <div className="flex-1">
              <p className="text-xs text-purple-700 font-medium">XP Earned</p>
              <p className="text-lg font-bold text-purple-900">+{xpEarned} XP</p>
            </div>
          </div>
        )}

        {/* Perfect Completion Indicator */}
        {isPerfect && (
          <div className="flex items-center gap-2 p-3 bg-gradient-to-r from-yellow-100 to-orange-100 rounded-lg border-2 border-yellow-400">
            <Award className="h-5 w-5 text-yellow-700" />
            <span className="text-sm font-bold text-yellow-800">
              Perfect completion possible!
            </span>
          </div>
        )}

        {/* Complete Button */}
        <Button
          onClick={onComplete}
          disabled={!canComplete || loading}
          className="w-full"
          size="lg"
        >
          {loading ? 'Completing...' : canComplete ? 'Complete Chapter' : 'Complete more goals to finish'}
        </Button>

        {/* Help Text */}
        <p className="text-xs text-gray-500 text-center">
          {canComplete
            ? 'You can complete this chapter now'
            : `Complete at least ${Math.ceil(totalGoals / 2)} goals to finish`}
        </p>
      </CardContent>
    </Card>
  );
}
