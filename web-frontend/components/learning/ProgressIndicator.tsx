import React from 'react';

type Props = {
  xp: number;
  level?: number;
  streak?: number;
};

export default function ProgressIndicator({ xp, level = 1, streak = 0 }: Props) {
  return (
    <div className="learning-card">
      <h3 className="text-sm font-semibold text-[#0b3954] mb-3 uppercase tracking-wide">
        Fortschritt
      </h3>
      <div className="space-y-2 text-sm text-[#0b3954]">
        <div className="flex items-center justify-between">
          <span>Level</span>
          <span className="font-semibold text-lg">{level}</span>
        </div>
        <div className="flex items-center justify-between">
          <span>XP</span>
          <span className="font-semibold text-lg">{xp}</span>
        </div>
        <div className="flex items-center justify-between">
          <span>Streak</span>
          <span className="font-semibold text-lg">{streak} Tage</span>
        </div>
      </div>
    </div>
  );
}
