import React from 'react';

interface DifficultyBadgeProps {
  level: string;
}

const difficultyConfig: Record<string, { label: string; color: string; bgColor: string }> = {
  A1: { label: 'Beginner', color: 'text-green-700', bgColor: 'bg-green-100' },
  A2: { label: 'Elementary', color: 'text-green-700', bgColor: 'bg-green-200' },
  B1: { label: 'Intermediate', color: 'text-blue-700', bgColor: 'bg-blue-100' },
  B2: { label: 'Upper Int.', color: 'text-blue-700', bgColor: 'bg-blue-200' },
  C1: { label: 'Advanced', color: 'text-purple-700', bgColor: 'bg-purple-100' },
  C2: { label: 'Proficient', color: 'text-purple-700', bgColor: 'bg-purple-200' },
};

export default function DifficultyBadge({ level }: DifficultyBadgeProps) {
  const config = difficultyConfig[level] || difficultyConfig.B1;

  return (
    <div className={`inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-bold ${config.bgColor} ${config.color}`}>
      <span>{level}</span>
      <span className="text-[10px] font-normal opacity-75">• {config.label}</span>
    </div>
  );
}
