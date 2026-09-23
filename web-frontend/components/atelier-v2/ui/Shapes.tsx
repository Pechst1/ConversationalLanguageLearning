/**
 * The Bauhaus shape vocabulary (WP-01).
 *
 * The design's masthead mark is four shapes — an ink square, a blue circle, a
 * yellow square and a red triangle — and its system statement says those four
 * "become the app's playful vocabulary: progress tokens, path nodes, tab
 * icons." So they are a component, not a decoration: everywhere this system
 * needs a non-verbal token it uses one of these four, in its semantic colour.
 *
 * The four colours are the four meanings, and they are used consistently:
 *
 *   ink square      done
 *   blue circle     story / information / in progress
 *   yellow square   reward
 *   red triangle    action / attention
 *
 * Colour alone is never the message. Every caller pairs a shape with a word;
 * these components take `title` so the shape itself can carry an accessible
 * name when it is the only thing in a control.
 */

import React from 'react';

export type ShapeKind = 'done' | 'story' | 'reward' | 'action';

const SHAPE_CLASS: Record<ShapeKind, string> = {
  done: 'av2-shape--square',
  story: 'av2-shape--circle',
  reward: 'av2-shape--reward',
  action: 'av2-shape--triangle',
};

export type ShapeTokenProps = {
  kind: ShapeKind;
  size?: 'sm' | 'md' | 'lg';
  /** Accessible name. Omit for a shape that only repeats adjacent text. */
  title?: string;
  className?: string;
};

export function ShapeToken({ kind, size = 'md', title, className }: ShapeTokenProps) {
  const classes = [
    'av2-shape',
    SHAPE_CLASS[kind],
    size === 'sm' ? 'av2-shape--sm' : null,
    size === 'lg' ? 'av2-shape--lg' : null,
    className,
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <span
      className={classes}
      role={title ? 'img' : undefined}
      aria-label={title || undefined}
      aria-hidden={title ? undefined : true}
    />
  );
}

/** WP-D1: one part of the day, as the mark draws it. */
export type MarkPartState = 'done' | 'active' | 'todo' | 'absent';

/**
 * WP-D1: the day's four parts — scene (blue circle), recall (yellow square),
 * respond (red triangle), resolution (ink square).
 */
export type MarkProgress = {
  scene: MarkPartState;
  recall: MarkPartState;
  respond: MarkPartState;
  resolution: MarkPartState;
};

type MarkPart = keyof MarkProgress;

/**
 * A part that is not done is the same solid shape in `--av2-line` — a ghost.
 * Never an outline and never an ink stroke (owner, 2026-09-22).
 */
function partFill(part: MarkPart, colour: string, progress: MarkProgress | undefined): string {
  if (!progress) return colour;
  return progress[part] === 'done' ? colour : 'var(--av2-line)';
}

/**
 * The masthead mark: all four shapes, 28×28, exactly as drawn in the design.
 *
 * WP-D1: with `progress` it is the day's only gauge. Each shape fills in its
 * own colour when its part is done, and pops (`av2-pop`) the moment it does —
 * never on first paint, and never under Reduce Motion. Pass the day's label
 * («Aujourd’hui : 2 sur 4 — …») as `title` so the state is never colour alone.
 */
export function AtelierMark({
  size = 26,
  title,
  progress,
}: {
  size?: number;
  title?: string;
  progress?: MarkProgress;
}) {
  const popping = useMarkPops(progress);
  const partProps = (part: MarkPart) =>
    progress
      ? {
          'data-part': part,
          'data-state': progress[part],
          className: popping.includes(part) ? 'av2-mark__pop' : undefined,
        }
      : {};

  return (
    <svg
      className="av2-mark"
      width={size}
      height={size}
      viewBox="0 0 28 28"
      role={title ? 'img' : undefined}
      aria-label={title || undefined}
      aria-hidden={title ? undefined : true}
      data-progress={progress ? 'day' : undefined}
    >
      <rect x="0" y="0" width="11" height="11" rx="2" fill={partFill('resolution', 'var(--av2-ink)', progress)} {...partProps('resolution')} />
      <circle cx="22" cy="6" r="6" fill={partFill('scene', 'var(--av2-blue)', progress)} {...partProps('scene')} />
      <rect x="0" y="17" width="11" height="11" rx="2" fill={partFill('recall', 'var(--av2-yellow)', progress)} {...partProps('recall')} />
      <path d="M17 28L23 16L28 28H17Z" fill={partFill('respond', 'var(--av2-red)', progress)} {...partProps('respond')} />
    </svg>
  );
}

/** The parts that turned `done` since the last render — never on the first one. */
function useMarkPops(progress: MarkProgress | undefined): MarkPart[] {
  const key = progress
    ? `${progress.scene}|${progress.recall}|${progress.respond}|${progress.resolution}`
    : '';
  const previous = React.useRef(key);
  const [popping, setPopping] = React.useState<MarkPart[]>([]);
  React.useEffect(() => {
    const before = previous.current.split('|');
    previous.current = key;
    if (!key || before.length !== 4) return undefined;
    const now = key.split('|');
    const parts: MarkPart[] = ['scene', 'recall', 'respond', 'resolution'];
    const fresh = parts.filter((_, i) => now[i] === 'done' && before[i] !== 'done');
    if (fresh.length === 0) return undefined;
    setPopping(fresh);
    const timer = window.setTimeout(() => setPopping([]), 400);
    return () => window.clearTimeout(timer);
  }, [key]);
  return popping;
}

// ---------------------------------------------------------------------------
// Icons. Deliberately local and tiny rather than another icon dependency: the
// design draws each of these as a 2–3px stroke path, and matching that matters
// more than breadth. `currentColor` throughout, so they invert with the face.
// ---------------------------------------------------------------------------

type IconProps = { size?: number; className?: string };

function Icon({
  size = 18,
  className,
  stroke = 2.4,
  children,
  viewBox = '0 0 24 24',
}: IconProps & { stroke?: number; children: React.ReactNode; viewBox?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox={viewBox}
      fill="none"
      stroke="currentColor"
      strokeWidth={stroke}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      className={className}
    >
      {children}
    </svg>
  );
}

export const CheckIcon = (p: IconProps) => (
  <Icon {...p} stroke={3}>
    <path d="M4.5 12.5l5 5 10-11" />
  </Icon>
);

export const CrossIcon = (p: IconProps) => (
  <Icon {...p} stroke={2.6}>
    <path d="M6 6l12 12M18 6L6 18" />
  </Icon>
);

export const ArrowRightIcon = (p: IconProps) => (
  <Icon {...p} stroke={2.8}>
    <path d="M4 12h15M13 6l6 6-6 6" />
  </Icon>
);

export const ArrowLeftIcon = (p: IconProps) => (
  <Icon {...p} stroke={2.8}>
    <path d="M20 12H5M11 6l-6 6 6 6" />
  </Icon>
);

/** The settings affordance: the design's thin 1.8px gear. */
export const GearIcon = (p: IconProps) => (
  <Icon {...p} stroke={1.8}>
    <circle cx="12" cy="12" r="3.2" />
    <path d="M12 2.8v3M12 18.2v3M2.8 12h3M18.2 12h3M5.5 5.5l2.1 2.1M16.4 16.4l2.1 2.1M18.5 5.5l-2.1 2.1M7.6 16.4l-2.1 2.1" />
  </Icon>
);

/**
 * The in-flight token: a small square that pops while a request runs. The
 * same mark `Action` uses, exposed so a composition outside `Action` (the
 * reader's own buttons) shows the same thing.
 */
export const SpinnerToken = () => <span className="av2-btn__spinner" aria-hidden="true" />;

export const MicIcon = (p: IconProps) => (
  <Icon {...p}>
    <rect x="9" y="3" width="6" height="11" rx="3" />
    <path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
  </Icon>
);

export const StopIcon = (p: IconProps) => (
  <Icon {...p}>
    <rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor" />
  </Icon>
);

export const SendIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M4 12h15M13 6l6 6-6 6" />
  </Icon>
);

/** The "not yet" mark for the feedback badge — a dash, not a cross-out. */
export const RepairIcon = (p: IconProps) => (
  <Icon {...p} stroke={3}>
    <path d="M6 12h12" />
  </Icon>
);

/** Grading that has not happened. An open circle, never a verdict glyph. */
export const PendingIcon = (p: IconProps) => (
  <Icon {...p} stroke={2.6}>
    <circle cx="12" cy="12" r="7" />
  </Icon>
);

export const LockIcon = (p: IconProps) => (
  <Icon {...p} stroke={2}>
    <rect x="4" y="10" width="16" height="11" rx="3" />
    <path d="M8 10V7a4 4 0 0 1 8 0v3" />
  </Icon>
);
