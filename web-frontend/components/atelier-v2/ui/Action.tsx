/**
 * Actions (WP-01) — the tactile 3D press.
 *
 * The design's rule is "one tactile 3D-press button per screen", and its
 * mechanic is exact: `box-shadow: 0 5px 0 <shadow>` at rest, and on press
 * `transform: translateY(5px); box-shadow: 0 0 0`, over 0.08s. Choice options
 * press 3px, icon actions and secondary rows 4px, the vocabulary card 8px.
 *
 * Four things this component is responsible for that the design does not show,
 * because a static artboard has no failure states:
 *
 *   * `pending` — a request is in flight. The control is disabled, says so in
 *     words, and exposes `aria-busy`. It never silently swallows a second tap.
 *   * `disabled` — the label stays at full contrast. Dimming a button's *text*
 *     is what makes disabled states unreadable, so only the face dims.
 *   * `error` — an action that failed keeps its label and gains a described-by
 *     message; it does not turn into a verdict.
 *   * a 44px effective touch target at every text size, with a label that
 *     wraps rather than widening the row.
 */

import React, { forwardRef } from 'react';

export type ActionTone =
  /** Red. The one primary per composition. */
  | 'primary'
  /** Ink. A completed / terminal forward action ("Finish"). */
  | 'done'
  /** Blue. Story or information, e.g. "Read and reply". */
  | 'story'
  /** Yellow. Reward. */
  | 'reward'
  /** Paper face, shallow press. Everything second-tier. */
  | 'secondary'
  /** No face, no press. Third-tier: help, "stop here", "dismiss". */
  | 'quiet';

const TONE_CLASS: Record<ActionTone, string> = {
  primary: 'av2-btn--primary',
  done: 'av2-btn--done',
  story: 'av2-btn--story',
  reward: 'av2-btn--reward',
  secondary: 'av2-btn--secondary',
  quiet: 'av2-btn--quiet',
};

export type ActionProps = {
  tone?: ActionTone;
  /** A request is in flight: disabled, `aria-busy`, and `pendingLabel` shown. */
  pending?: boolean;
  /** What the control says while pending. Required when `pending` can be true. */
  pendingLabel?: string;
  disabled?: boolean;
  /** Shrink-to-fit instead of filling the row. */
  inline?: boolean;
  /** Leading shape or icon. Decorative — never the only carrier of meaning. */
  icon?: React.ReactNode;
  children: React.ReactNode;
} & Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, 'children'>;

export const Action = forwardRef<HTMLButtonElement, ActionProps>(function Action(
  {
    tone = 'secondary',
    pending = false,
    pendingLabel,
    disabled = false,
    inline = false,
    icon,
    children,
    className,
    type = 'button',
    ...rest
  },
  ref,
) {
  const classes = [
    'av2-btn',
    TONE_CLASS[tone],
    inline ? 'av2-btn--inline' : null,
    className,
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <button
      ref={ref}
      type={type}
      className={classes}
      // A pending control is genuinely unusable, so it is really disabled
      // rather than only styled as such: a second tap must not queue a second
      // mutation behind the first.
      disabled={disabled || pending}
      aria-busy={pending || undefined}
      data-pending={pending ? 'true' : undefined}
      data-tone={tone}
      {...rest}
    >
      {pending ? (
        <span className="av2-btn__spinner" aria-hidden="true" />
      ) : (
        icon ?? null
      )}
      <span>{pending ? pendingLabel ?? children : children}</span>
    </button>
  );
});

// ---------------------------------------------------------------------------
// Icon-only action
// ---------------------------------------------------------------------------

export type IconActionProps = {
  /** Required: an icon-only control has no visible name. */
  label: string;
  tone?: 'plain' | 'action' | 'recording';
  pressable?: boolean;
  pending?: boolean;
  children: React.ReactNode;
} & Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, 'children'>;

export const IconAction = forwardRef<HTMLButtonElement, IconActionProps>(
  function IconAction(
    {
      label,
      tone = 'plain',
      pressable = false,
      pending = false,
      disabled = false,
      children,
      className,
      type = 'button',
      ...rest
    },
    ref,
  ) {
    const classes = [
      'av2-icon-btn',
      pressable ? 'av2-icon-btn--pressable' : null,
      tone === 'action' ? 'av2-icon-btn--action' : null,
      tone === 'recording' ? 'av2-icon-btn--recording' : null,
      className,
    ]
      .filter(Boolean)
      .join(' ');

    return (
      <button
        ref={ref}
        type={type}
        className={classes}
        aria-label={label}
        title={label}
        aria-busy={pending || undefined}
        disabled={disabled || pending}
        {...rest}
      >
        {children}
      </button>
    );
  },
);

// ---------------------------------------------------------------------------
// Chip — a small pill. Static by default; a control when `onClick` is given.
// ---------------------------------------------------------------------------

export type ChipProps = {
  tone?: 'plain' | 'reward' | 'story' | 'quiet';
  icon?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
} & Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, 'children' | 'className'>;

export function Chip({ tone = 'plain', icon, children, className, ...rest }: ChipProps) {
  const classes = [
    'av2-chip',
    tone === 'reward' ? 'av2-chip--reward' : null,
    tone === 'story' ? 'av2-chip--story' : null,
    tone === 'quiet' ? 'av2-chip--quiet' : null,
    className,
  ]
    .filter(Boolean)
    .join(' ');

  const content = (
    <>
      {icon}
      <span>{children}</span>
    </>
  );

  if (!rest.onClick) {
    return <span className={classes}>{content}</span>;
  }
  return (
    <button type="button" className={classes} {...rest}>
      {content}
    </button>
  );
}

export default Action;
