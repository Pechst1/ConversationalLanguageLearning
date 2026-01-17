import React from 'react';

interface ProgressBarProps {
  value: number; // 0-100
  height?: string;
  showLabel?: boolean;
}

export default function ProgressBar({ value, height = 'h-2', showLabel = false }: ProgressBarProps) {
  const percentage = Math.min(Math.max(value, 0), 100);

  return (
    <div className="w-full">
      <div className={`w-full bg-gray-200 rounded-full overflow-hidden ${height}`} role="progressbar" aria-valuenow={percentage} aria-valuemin={0} aria-valuemax={100}>
        <div
          className="h-full bg-gradient-to-r from-primary-500 to-primary-600 transition-all duration-500 ease-out"
          style={{ width: `${percentage}%` }}
        />
      </div>
      {showLabel && (
        <p className="text-xs text-gray-600 mt-1 text-right">{Math.round(percentage)}% complete</p>
      )}
    </div>
  );
}
