import React from 'react';
import { motion } from 'framer-motion';
import { Target } from 'lucide-react';
import { cn } from '@/lib/utils';
import { NarrativeGoal } from '@/hooks/useStories';

interface NarrativeGoalsPanelProps {
  goals: NarrativeGoal[];
  completedGoals: string[];
}

export default function NarrativeGoalsPanel({ goals, completedGoals }: NarrativeGoalsPanelProps) {
  return (
    <div className="bg-gradient-to-br from-amber-50 to-orange-50 border-2 border-amber-300 rounded-xl p-4 shadow-lg">
      <h3 className="font-bold text-lg mb-4 flex items-center gap-2 text-amber-900">
        <Target className="h-5 w-5" />
        Chapter Goals
      </h3>
      <div className="space-y-3">
        {goals.map((goal) => {
          const isCompleted = completedGoals.includes(goal.goal_id);
          return (
            <motion.div
              key={goal.goal_id}
              animate={isCompleted ? { scale: [1, 1.05, 1] } : {}}
              transition={{ duration: 0.3 }}
              className={cn(
                'p-3 rounded-lg border-2 transition-all',
                isCompleted
                  ? 'bg-green-100 border-green-400 shadow-md'
                  : 'bg-white border-amber-200 hover:border-amber-300'
              )}
            >
              <div className="flex items-start gap-3">
                <div className="mt-0.5 flex-shrink-0">
                  {isCompleted ? (
                    <div className="w-6 h-6 bg-green-500 rounded-full flex items-center justify-center">
                      <svg
                        className="w-4 h-4 text-white"
                        fill="none"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth="2"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path d="M5 13l4 4L19 7" />
                      </svg>
                    </div>
                  ) : (
                    <div className="w-6 h-6 border-2 border-amber-400 rounded-full" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <p
                    className={cn(
                      'text-sm font-medium',
                      isCompleted ? 'line-through text-green-700' : 'text-gray-900'
                    )}
                  >
                    {goal.description}
                  </p>
                  {goal.hint && !isCompleted && (
                    <p className="text-xs text-gray-600 mt-1 italic flex items-start gap-1">
                      <span className="text-amber-600">💡</span>
                      {goal.hint}
                    </p>
                  )}
                </div>
              </div>
            </motion.div>
          );
        })}
      </div>

      {/* Progress Summary */}
      <div className="mt-4 pt-4 border-t border-amber-200">
        <div className="flex items-center justify-between text-sm">
          <span className="text-amber-900 font-medium">Progress</span>
          <span className="font-bold text-amber-700">
            {completedGoals.length} / {goals.length}
          </span>
        </div>
        <div className="mt-2 w-full bg-amber-200 rounded-full h-2 overflow-hidden">
          <div
            className="bg-gradient-to-r from-amber-500 to-orange-500 h-2 rounded-full transition-all duration-500"
            style={{ width: `${(completedGoals.length / goals.length) * 100}%` }}
          />
        </div>
      </div>
    </div>
  );
}
