import React from 'react';
import { cn } from '@/lib/utils';

export type FragilityLevel = 'new' | 'forming' | 'holding' | 'tender' | 'fraying' | 'due' | string;

export interface FragilityInput {
  state?: string | null;
  phase?: string | null;
  due_at?: string | null;
  next_review?: string | null;
  retrievability?: number | null;
  proficiency_score?: number | null;
  reps?: number | null;
  lapses?: number | null;
  fragility_level?: string | null;
  fragility_label?: string | null;
  fragility_reason?: string | null;
}

export interface FragilityDescriptor {
  level: FragilityLevel;
  label: string;
  reason?: string | null;
}

function parseDate(value?: string | null) {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function fragilityLabel(progress?: FragilityInput | null, now = new Date()): FragilityDescriptor {
  if (!progress) {
    return { level: 'new', label: 'New thread', reason: 'No personal reviews yet.' };
  }

  if (progress.fragility_label) {
    return {
      level: progress.fragility_level || 'forming',
      label: progress.fragility_label,
      reason: progress.fragility_reason,
    };
  }

  const state = String(progress.state || 'new').toLowerCase();
  const phase = String(progress.phase || '').toLowerCase();
  const dueAt = parseDate(progress.due_at || progress.next_review);
  const due = dueAt ? dueAt.getTime() <= now.getTime() : false;
  const reps = progress.reps || 0;
  const lapses = progress.lapses || 0;
  const retrievability = progress.retrievability;

  if (due && reps > 0) {
    return { level: 'due', label: 'Due now', reason: 'Ready for another touch.' };
  }
  if (lapses >= 3 || (typeof retrievability === 'number' && retrievability < 0.45)) {
    return { level: 'fraying', label: 'Fraying memory', reason: 'Several misses or low recall estimate.' };
  }
  if (
    phase === 'learn' ||
    phase === 'learning' ||
    phase === 'relearn' ||
    phase === 'relearning' ||
    state === 'learning' ||
    state === 'relearning' ||
    lapses > 0 ||
    (typeof retrievability === 'number' && retrievability < 0.72)
  ) {
    return { level: 'tender', label: 'Tender memory', reason: 'Useful, but still easy to lose.' };
  }
  if (state === 'mastered' || (progress.proficiency_score || 0) >= 90) {
    return { level: 'holding', label: 'Holding', reason: 'This thread is currently strong.' };
  }
  if (state === 'new' && reps === 0) {
    return { level: 'new', label: 'New thread', reason: 'Not reviewed yet.' };
  }
  return { level: 'forming', label: 'Forming', reason: 'The thread is taking shape.' };
}

export interface FragilityBadgeProps extends React.HTMLAttributes<HTMLElement> {
  progress?: FragilityInput | null;
  level?: FragilityLevel;
  label?: React.ReactNode;
  reason?: React.ReactNode;
  compact?: boolean;
  showReason?: boolean;
}

const FragilityBadge = React.forwardRef<HTMLElement, FragilityBadgeProps>(
  ({ progress, level, label, reason, compact = false, showReason = false, className, ...props }, ref) => {
    const descriptor = progress ? fragilityLabel(progress) : {
      level: level || 'forming',
      label: 'Forming',
      reason: typeof reason === 'string' ? reason : null,
    };
    const resolvedLevel = level || descriptor.level || 'forming';
    const resolvedLabel = label || descriptor.label;
    const resolvedReason = reason || descriptor.reason;

    return (
      <small
        ref={ref as React.Ref<HTMLElement>}
        className={cn('fragility-badge', `fragility-badge-${resolvedLevel}`, compact && 'compact', className)}
        {...props}
      >
        <span className="fragility-badge-mark" aria-hidden="true" />
        <strong>{resolvedLabel}</strong>
        {showReason && resolvedReason && <em>{resolvedReason}</em>}
        <style jsx>{`
          .fragility-badge {
            --fragility-paper: var(--app-paper, var(--paper, #f1ece1));
            --fragility-sheet: var(--app-sheet, var(--paper-2, #f8f3e8));
            --fragility-ink: var(--app-ink, var(--ink, #14110d));
            --fragility-ink-2: var(--app-ink-2, var(--ink-2, #4a4538));
            --fragility-blue: var(--app-blue, var(--blue, #1d3a8a));
            --fragility-red: var(--app-red, var(--red, #d8321a));
            --fragility-yellow: var(--app-yellow, var(--yellow, #f3c318));
            --fragility-green: var(--app-green, var(--green, #2e7d32));
            display: inline-grid;
            grid-template-columns: auto minmax(0, 1fr);
            gap: 3px 7px;
            align-items: center;
            max-width: 100%;
            border: 1px solid var(--fragility-ink);
            background: var(--fragility-sheet);
            padding: 7px 9px;
            color: var(--fragility-ink);
            font-style: normal;
            line-height: 1.15;
          }
          .fragility-badge.compact {
            padding: 6px 8px;
          }
          .fragility-badge-mark {
            width: 10px;
            height: 10px;
            background: var(--fragility-accent, var(--fragility-blue));
          }
          .fragility-badge strong {
            min-width: 0;
            overflow-wrap: anywhere;
            font: 900 10px/1 var(--app-mono, "Inter", "Helvetica Neue", Arial, sans-serif);
            letter-spacing: .1em;
            text-transform: uppercase;
          }
          .fragility-badge em {
            grid-column: 2;
            color: var(--fragility-ink-2);
            font-size: 11px;
            font-style: normal;
            font-weight: 650;
            line-height: 1.28;
          }
          .fragility-badge-new {
            --fragility-accent: var(--fragility-blue);
          }
          .fragility-badge-forming {
            --fragility-accent: var(--fragility-yellow);
          }
          .fragility-badge-holding {
            --fragility-accent: var(--fragility-green);
          }
          .fragility-badge-tender {
            --fragility-accent: var(--fragility-yellow);
          }
          .fragility-badge-fraying,
          .fragility-badge-due {
            --fragility-accent: var(--fragility-red);
          }
        `}</style>
      </small>
    );
  }
);

FragilityBadge.displayName = 'FragilityBadge';

export { FragilityBadge };
