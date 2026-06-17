import React from 'react';
import { cn } from '@/lib/utils';

export interface ProgressBarProps extends React.HTMLAttributes<HTMLDivElement> {
  value: number;
  max?: number;
  label?: string;
}

export function ProgressBar({ value, max = 100, label, className, ...props }: ProgressBarProps) {
  const pct = max > 0 ? Math.max(0, Math.min(100, Math.round((value / max) * 100))) : 0;
  return (
    <div
      className={cn('atelier-progress-bar', className)}
      role="progressbar"
      aria-label={label}
      aria-valuenow={pct}
      aria-valuemin={0}
      aria-valuemax={100}
      {...props}
    >
      <span style={{ width: `${pct}%` }} />
    </div>
  );
}
