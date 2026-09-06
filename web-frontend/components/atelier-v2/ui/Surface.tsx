/**
 * Surfaces and progress (WP-01).
 *
 * The design replaces the old ruled boxes with rounded 16–24px surfaces; the
 * radius carries the meaning of the surface rather than a border does. Radii
 * come straight from the artboards: tile 18, card 16, episode 22, hero 24,
 * vocabulary card 28.
 */

import React from 'react';

import { ShapeToken, type ShapeKind } from './Shapes';

export type SurfaceTone = 'paper' | 'blue' | 'ink' | 'red' | 'reward' | 'outline';
export type SurfaceShape = 'card' | 'tile' | 'episode' | 'hero' | 'flush';

const TONE_CLASS: Record<SurfaceTone, string | null> = {
  paper: null,
  blue: 'av2-surface--blue',
  ink: 'av2-surface--ink',
  red: 'av2-surface--red',
  reward: 'av2-surface--reward',
  outline: 'av2-surface--outline',
};

const SHAPE_CLASS: Record<SurfaceShape, string | null> = {
  card: null,
  tile: 'av2-surface--tile',
  episode: 'av2-surface--episode',
  hero: 'av2-surface--hero',
  flush: 'av2-surface--flush',
};

export type SurfaceProps = {
  as?: 'div' | 'section' | 'article' | 'li';
  tone?: SurfaceTone;
  shape?: SurfaceShape;
  className?: string;
  children: React.ReactNode;
} & Omit<React.HTMLAttributes<HTMLElement>, 'children' | 'className'>;

export function Surface({
  as: Tag = 'div',
  tone = 'paper',
  shape = 'card',
  className,
  children,
  ...rest
}: SurfaceProps) {
  const classes = ['av2-surface', TONE_CLASS[tone], SHAPE_CLASS[shape], className]
    .filter(Boolean)
    .join(' ');
  return (
    <Tag className={classes} {...rest}>
      {children}
    </Tag>
  );
}

/** A vertical rhythm container. Exists so no caller hand-rolls a flex column. */
export function Stack({
  className,
  children,
  ...rest
}: { className?: string; children: React.ReactNode } & React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={['av2-stack', className].filter(Boolean).join(' ')} {...rest}>
      {children}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Progress
// ---------------------------------------------------------------------------

export type ProgressRuleProps = {
  /** Steps resolved. Always real plan data — never a demo value. */
  value: number;
  /** Steps planned. `0` renders the track alone, with no fill and no number. */
  max: number;
  /** Accessible name, in the learner's control language. */
  label: string;
  /** Optional trailing text, e.g. "2 of 5". */
  caption?: string;
};

/**
 * The blue progress rule from the design's session header.
 *
 * Blue because the design assigns blue to story and information; progress
 * through the day's scene is information, not an action or a reward.
 *
 * When `max` is 0 the plan is not known yet. The bar renders empty and the
 * accessible value is omitted entirely rather than reported as 0% — "we do not
 * know" and "you have done none of it" are different facts.
 */
export function ProgressRule({ value, max, label, caption }: ProgressRuleProps) {
  const known = max > 0;
  const safeValue = known ? Math.min(Math.max(value, 0), max) : 0;
  const percent = known ? Math.round((safeValue / max) * 100) : 0;

  return (
    <div className="av2-progress">
      <div
        className="av2-progress__track"
        role="progressbar"
        aria-label={label}
        aria-valuemin={known ? 0 : undefined}
        aria-valuemax={known ? max : undefined}
        aria-valuenow={known ? safeValue : undefined}
        aria-valuetext={caption || undefined}
      >
        <div className="av2-progress__fill" style={{ width: `${percent}%` }} />
      </div>
      {caption && <span className="av2-progress__count">{caption}</span>}
    </div>
  );
}

export type StepSegment = {
  id: string;
  state: 'done' | 'active' | 'pending' | 'skipped';
};

export type StepProgressProps = {
  steps: StepSegment[];
  label: string;
  caption?: string;
};

/**
 * One segment per real planned step.
 *
 * This is how the day's shape is shown without a fabricated counter: there are
 * exactly as many segments as the server planned steps, so it cannot claim a
 * number the plan does not contain. With no plan it renders nothing at all.
 */
export function StepProgress({ steps, label, caption }: StepProgressProps) {
  if (steps.length === 0) return null;
  const done = steps.filter((s) => s.state === 'done' || s.state === 'skipped').length;

  return (
    <div className="av2-progress">
      <div
        className="av2-progress__segments"
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={steps.length}
        aria-valuenow={done}
        aria-valuetext={caption || undefined}
      >
        {steps.map((step) => (
          <span
            key={step.id}
            className="av2-progress__segment"
            data-state={step.state}
          />
        ))}
      </div>
      {caption && <span className="av2-progress__count">{caption}</span>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Row — the list item used by the Feuilleton episode list and the Cahier
// ---------------------------------------------------------------------------

export type RowProps = {
  eyebrow?: React.ReactNode;
  title: React.ReactNode;
  lead?: React.ReactNode;
  /** Trailing badge. `done` renders the ink check; `locked` the dashed lock. */
  badge?: React.ReactNode;
  onSelect?: () => void;
  className?: string;
  disabled?: boolean;
};

export function Row({ eyebrow, title, lead, badge, onSelect, className, disabled }: RowProps) {
  const body = (
    <>
      {lead}
      <span className="av2-row__main">
        {eyebrow && <span className="av2-label">{eyebrow}</span>}
        <span className="av2-headline av2-headline--rule" style={{ display: 'block' }}>
          {title}
        </span>
      </span>
      {badge}
    </>
  );

  const classes = ['av2-row', className].filter(Boolean).join(' ');

  if (!onSelect) return <div className={classes}>{body}</div>;
  return (
    <button type="button" className={classes} onClick={onSelect} disabled={disabled}>
      {body}
    </button>
  );
}

/** The ink check badge from the design's read-episode rows. */
export function DoneBadge({ label }: { label: string }) {
  return (
    <span className="av2-row__badge" role="img" aria-label={label}>
      <ShapeToken kind="done" size="sm" />
    </span>
  );
}

/** A shape token with its meaning spelled out. Colour is never alone. */
export function StatusToken({ kind, label }: { kind: ShapeKind; label: string }) {
  return (
    <span className="av2-byline">
      <ShapeToken kind={kind} size="sm" />
      <span className="av2-label">{label}</span>
    </span>
  );
}
