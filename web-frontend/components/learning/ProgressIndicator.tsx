import React from 'react';

type Props = {
  xp: number;
  level?: number;
  streak?: number;
};

export default function ProgressIndicator({ xp, level = 1, streak = 0 }: Props) {
  const metrics = [
    { label: 'Level', value: String(level) },
    { label: 'XP', value: String(xp) },
    { label: 'Streak', value: `${streak}d` },
  ];

  return (
    <div className="flex flex-wrap items-center gap-4 rounded-full border border-stone-200 bg-white/90 px-4 py-3 text-stone-600 shadow-sm">
      {metrics.map((metric) => (
        <div key={metric.label} className="min-w-[72px]">
          <div className="text-[11px] font-medium uppercase tracking-[0.18em] text-stone-400">
            {metric.label}
          </div>
          <div className="mt-1 text-lg font-semibold text-stone-900">{metric.value}</div>
        </div>
      ))}
      <div className="ml-auto hidden text-xs text-stone-400 sm:block">
        Quiet progress, one turn at a time
      </div>
    </div>
  );
}
