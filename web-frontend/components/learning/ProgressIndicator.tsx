import React from 'react';

type Props = {
  xp: number;
  level?: number;
  streak?: number;
};

export default function ProgressIndicator({ xp, level = 1, streak = 0 }: Props) {
  return (
    <div className="mt-6 learning-card">
      <h3 className="text-sm font-semibold text-gray-700 mb-3">Fortschritt</h3>
      <div className="space-y-2 text-sm">
        <div className="flex items-center justify-between">
          <span>Level</span>
          <span className="font-medium">{level}</span>
        </div>
        <div className="flex items-center justify-between">
          <span>XP</span>
          <span className="font-medium">{xp}</span>
        </div>
        <div className="flex items-center justify-between">
          <span>Streak</span>
          <span className="font-medium">{streak} Tage</span>
        </div>
      </div>
    </div>
  );
}
