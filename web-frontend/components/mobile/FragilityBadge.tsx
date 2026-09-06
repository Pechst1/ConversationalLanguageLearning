import React from 'react';
import { cn } from '@/lib/utils';
import { ShapeToken, type ShapeKind } from '@/components/atelier-v2/ui';

/* The fragility badge, on the Claude design system (Atelier V2).
 *
 * The descriptor logic below is unchanged: it is the client mirror of
 * `_fragility_for_progress` in app/api/v1/endpoints/vocabulary.py — same six
 * levels, same French copy. Only the presentation moved: the ruled 1px box and
 * the tracked mono caps became a paper chip carrying one Bauhaus shape token
 * next to the label. The label is always printed, so the shape never carries
 * the state alone. The chip is only styled inside an `.av2` scope; every
 * consumer (the Cahier's word sheet, the word biography) renders under one. */

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

// The client mirror of _fragility_for_progress in app/api/v1/endpoints/vocabulary.py:
// same six levels, same French copy. Keep the two in step.
export function fragilityLabel(progress?: FragilityInput | null, now = new Date()): FragilityDescriptor {
  if (!progress) {
    return { level: 'new', label: 'Nouveau', reason: 'Pas encore révisé par vous.' };
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
    return { level: 'due', label: 'À revoir', reason: 'Prêt pour une reprise.' };
  }
  if (lapses >= 3 || (typeof retrievability === 'number' && retrievability < 0.45)) {
    return { level: 'fraying', label: 'Mémoire qui s’effrite', reason: 'Plusieurs oublis, ou un rappel estimé faible.' };
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
    return { level: 'tender', label: 'Mémoire fragile', reason: 'Utile, mais encore facile à perdre.' };
  }
  if (state === 'mastered' || (progress.proficiency_score || 0) >= 90) {
    return { level: 'holding', label: 'Tient', reason: 'Ce fil tient bien pour l’instant.' };
  }
  if (state === 'new' && reps === 0) {
    return { level: 'new', label: 'Nouveau', reason: 'Pas encore révisé.' };
  }
  return { level: 'forming', label: 'En formation', reason: 'Le fil se dessine.' };
}

/* The design's four shapes, by what the state asks of the learner:
 * red triangle = action (due / fraying), yellow square = still being earned
 * (forming / tender), ink square = done (holding), blue circle = information
 * (new — nothing is known yet). */
function shapeFor(level: FragilityLevel): ShapeKind {
  switch (level) {
    case 'due':
    case 'fraying':
      return 'action';
    case 'holding':
      return 'done';
    case 'new':
      return 'story';
    default:
      return 'reward';
  }
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
      label: 'En formation',
      reason: typeof reason === 'string' ? reason : null,
    };
    const resolvedLevel = level || descriptor.level || 'forming';
    const resolvedLabel = label || descriptor.label;
    const resolvedReason = reason || descriptor.reason;

    return (
      <small
        ref={ref as React.Ref<HTMLElement>}
        className={cn('fragility-badge lx-fragility', compact && 'lx-fragility--compact', className)}
        data-level={resolvedLevel}
        {...props}
      >
        <ShapeToken kind={shapeFor(resolvedLevel)} size="sm" className="lx-fragility__mark" />
        <strong className="lx-fragility__label">{resolvedLabel}</strong>
        {showReason && resolvedReason && <em className="lx-fragility__reason">{resolvedReason}</em>}
        <style jsx global>{`
          .av2 .lx-fragility {
            display: inline-grid;
            grid-template-columns: auto minmax(0, 1fr);
            gap: 3px 8px;
            align-items: center;
            max-width: 100%;
            min-height: 2rem;
            padding: 0.375rem 0.75rem;
            border: 0;
            border-radius: var(--av2-r-pill);
            background: var(--av2-card);
            color: var(--av2-ink);
            font-family: var(--av2-sans);
            font-style: normal;
            font-size: var(--av2-t-label);
            line-height: 1.3;
          }
          .av2 .lx-fragility--compact {
            padding: 0.25rem 0.625rem;
          }
          .av2 .lx-fragility__mark {
            margin-top: 1px;
          }
          .av2 .lx-fragility__label {
            min-width: 0;
            overflow-wrap: anywhere;
            font-weight: 700;
          }
          .av2 .lx-fragility__reason {
            grid-column: 2;
            color: var(--av2-ink-2);
            font-size: var(--av2-t-meta);
            font-style: normal;
            font-weight: 400;
            line-height: 1.35;
            overflow-wrap: anywhere;
          }
        `}</style>
      </small>
    );
  }
);

FragilityBadge.displayName = 'FragilityBadge';

export { FragilityBadge };
