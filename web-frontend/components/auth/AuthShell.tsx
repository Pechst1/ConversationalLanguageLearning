/**
 * The signed-out shell, on the av2 design system.
 *
 * The landing and the three auth screens were the last learner-facing surfaces
 * still speaking the pre-av2 language — tracked caps, hard ink boxes, English
 * chrome — which meant every learner met a different product before they met
 * the real one. Drawn on the canvas "L'Atelier — écrans hors système" and
 * implemented here; the pieces live in one file because these four screens are
 * the only things that use them.
 *
 * Every value comes from `styles/atelier-v2.css`. Nothing here invents a colour,
 * a radius or a size.
 */

import React from 'react';
import Link from 'next/link';

import { AtelierV2Root } from '@/components/atelier-v2/ui';

/** The four-shape mark, at the two sizes these screens use. */
export function AtelierMark({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 28 28" aria-hidden="true" className="auth-mark">
      <rect x="0" y="0" width="11" height="11" rx="2" fill="var(--av2-ink)" />
      <circle cx="22" cy="6" r="6" fill="var(--av2-blue)" />
      <rect x="0" y="17" width="11" height="11" rx="2" fill="var(--av2-yellow)" />
      <path d="M17 28L23 16L28 28H17Z" fill="var(--av2-red)" />
    </svg>
  );
}

/** Mark plus one quiet line — the masthead these screens carry instead of a header. */
export function AuthEyebrow({ children }: { children: React.ReactNode }) {
  return (
    <div className="auth-eyebrow">
      <AtelierMark />
      <span className="av2-label">{children}</span>
    </div>
  );
}

/**
 * The screen. A single column that never exceeds the phone shell, with the
 * safe-area insets the native build needs and the bottom action held at the
 * end of the flow rather than pinned, so a software keyboard cannot cover it.
 */
export function AuthScreen({
  children,
  label,
}: {
  children: React.ReactNode;
  label: string;
}) {
  return (
    <AtelierV2Root as="main" className="auth-v2" aria-label={label}>
      <div className="auth-v2__column">{children}</div>
      <AuthShellStyles />
    </AtelierV2Root>
  );
}

/** Pushes what follows to the foot of the screen. */
export function AuthSpacer() {
  return <div className="auth-spacer" aria-hidden="true" />;
}

export type AuthFieldProps = {
  id: string;
  label: string;
  error?: string;
  hint?: string;
} & React.InputHTMLAttributes<HTMLInputElement>;

/**
 * One field. The control is `.av2-field__control`, which carries the 16px floor
 * — below it iOS zooms the viewport on focus and never zooms back (WP-20 D-16),
 * which is the defect this whole screen family came from.
 */
export const AuthField = React.forwardRef<HTMLInputElement, AuthFieldProps>(
  function AuthField({ id, label, error, hint, ...rest }, ref) {
    const describedBy = [error ? `${id}-error` : null, hint ? `${id}-hint` : null]
      .filter(Boolean)
      .join(' ');
    return (
      <div className="auth-field">
        <label className="av2-field" htmlFor={id}>
          <span className="av2-field__label">{label}</span>
          <input
            {...rest}
            id={id}
            ref={ref}
            className="av2-field__control auth-field__control"
            aria-invalid={error ? true : undefined}
            aria-describedby={describedBy || undefined}
          />
        </label>
        {hint && (
          <p className="av2-label auth-field__hint" id={`${id}-hint`}>
            {hint}
          </p>
        )}
        {error && (
          <p className="auth-field__error" id={`${id}-error`}>
            {error}
          </p>
        )}
      </div>
    );
  },
);

/**
 * A stated fact, not a verdict on the learner: the alert tone is for something
 * that went wrong, the done tone for something that worked.
 */
export function AuthNotice({
  tone = 'alert',
  children,
}: {
  tone?: 'alert' | 'done';
  children: React.ReactNode;
}) {
  return (
    <div className="auth-notice" data-tone={tone} role={tone === 'alert' ? 'alert' : 'status'}>
      <span className="auth-notice__mark" aria-hidden="true" />
      <p>{children}</p>
    </div>
  );
}

/** The quiet line at the foot of a screen: a sentence with one link in it. */
export function AuthFootLink({
  children,
  href,
  label,
}: {
  children?: React.ReactNode;
  href: React.ComponentProps<typeof Link>['href'];
  label: string;
}) {
  return (
    <p className="auth-foot">
      {children}
      <Link className="auth-foot__link" href={href}>
        {label}
      </Link>
    </p>
  );
}

/** A segmented choice — the same control Réglages uses. */
export function AuthSegments<T extends string>({
  legend,
  options,
  value,
  onSelect,
  compact = false,
}: {
  legend: string;
  options: Array<{ value: T; label: string }>;
  value: T;
  onSelect: (next: T) => void;
  /** Short labels (numbers, CEFR codes) take a tighter wrap floor so a row of
      them does not spill one lonely cell onto a second line. */
  compact?: boolean;
}) {
  return (
    <div className="auth-seg" data-compact={compact ? 'true' : undefined} role="group" aria-label={legend}>
      <span className="av2-field__label">{legend}</span>
      <div className="auth-seg__row">
        {options.map((option) => (
          <button
            key={option.value}
            type="button"
            className="auth-seg__btn"
            data-active={option.value === value ? 'true' : 'false'}
            aria-pressed={option.value === value}
            onClick={() => onSelect(option.value)}
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  );
}

/** A column of single-choice rows, for the questions that shape day one. */
export function AuthChoices<T extends string>({
  legend,
  options,
  value,
  onSelect,
}: {
  legend: string;
  options: Array<{ value: T; label: string }>;
  value: T | null;
  onSelect: (next: T) => void;
}) {
  return (
    <div className="auth-choices" role="radiogroup" aria-label={legend}>
      <span className="av2-field__label">{legend}</span>
      <div className="auth-choices__list">
        {options.map((option) => (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={option.value === value}
            className="auth-choice"
            data-active={option.value === value ? 'true' : 'false'}
            onClick={() => onSelect(option.value)}
          >
            <span className="auth-choice__dot" aria-hidden="true" />
            <span>{option.label}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

/** Honest progress: the step you are on, out of the steps there are. */
export function AuthSteps({ step, total }: { step: number; total: number }) {
  return (
    <div className="auth-steps">
      <div
        className="auth-steps__bars"
        role="progressbar"
        aria-valuemin={1}
        aria-valuemax={total}
        aria-valuenow={step}
        aria-label="Progression"
      >
        {Array.from({ length: total }, (_, index) => (
          <i key={index} data-on={index < step ? 'true' : 'false'} />
        ))}
      </div>
      <span className="av2-label">
        {step} / {total}
      </span>
    </div>
  );
}

export function AuthShellStyles() {
  return (
    <style jsx global>{`
      body {
        background: var(--av2-paper);
      }
      .av2.auth-v2 {
        display: flex;
        justify-content: center;
        min-height: 100vh;
        min-height: 100dvh;
        padding: calc(28px + env(safe-area-inset-top, 0px)) var(--av2-gutter)
          calc(24px + env(safe-area-inset-bottom, 0px));
        background: var(--av2-paper);
      }
      .av2 .auth-v2__column {
        display: flex;
        flex-direction: column;
        gap: 16px;
        width: 100%;
        max-width: 430px;
        min-width: 0;
      }
      .av2 .auth-spacer {
        flex: 1 1 auto;
        min-height: 18px;
      }
      .av2 .auth-eyebrow {
        display: flex;
        align-items: center;
        gap: 10px;
        min-width: 0;
      }
      .av2 .auth-mark {
        flex: none;
      }
      .av2 .auth-field {
        display: flex;
        flex-direction: column;
        gap: 6px;
        min-width: 0;
      }
      /* An input, not the textarea the shared control was written for. */
      .av2 input.auth-field__control {
        min-height: 3.25rem;
        resize: none;
      }
      .av2 .auth-field__hint {
        margin: 0;
        font-weight: 400;
      }
      .av2 .auth-field__error {
        margin: 0;
        font-size: var(--av2-t-label);
        font-weight: 600;
        line-height: 1.4;
        color: var(--av2-red);
        overflow-wrap: anywhere;
      }
      .av2 .auth-notice {
        display: flex;
        align-items: flex-start;
        gap: 10px;
        padding: 14px 16px;
        border-radius: var(--av2-r-card);
        background: var(--av2-tint-wrong);
      }
      .av2 .auth-notice[data-tone='done'] {
        background: var(--av2-tint-correct);
      }
      .av2 .auth-notice p {
        margin: 0;
        font-size: var(--av2-t-label);
        line-height: 1.45;
        color: var(--av2-ink);
        overflow-wrap: anywhere;
      }
      .av2 .auth-notice__mark {
        flex: none;
        width: 18px;
        height: 18px;
        margin-top: 2px;
        border-radius: 4px;
        background: var(--av2-red);
      }
      .av2 .auth-notice[data-tone='done'] .auth-notice__mark {
        border-radius: var(--av2-r-pill);
        background: var(--av2-green);
      }
      .av2 .auth-foot {
        display: flex;
        align-items: center;
        justify-content: center;
        flex-wrap: wrap;
        gap: 6px;
        min-height: var(--av2-tap);
        margin: 0;
        font-size: var(--av2-t-label);
        font-weight: 600;
        color: var(--av2-ink-2);
        text-align: center;
      }
      .av2 .auth-foot__link {
        color: var(--av2-ink);
        text-decoration: underline;
        text-underline-offset: 3px;
      }
      .av2 .auth-seg,
      .av2 .auth-choices {
        display: flex;
        flex-direction: column;
        gap: 8px;
        min-width: 0;
      }
      /* The row wraps rather than squeezing: with six interface languages,
         equal-width cells break words mid-syllable ("Franç / ais"). Cells keep
         a readable floor and spill onto a second line instead. */
      .av2 .auth-seg__row {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        min-width: 0;
      }
      .av2 .auth-seg[data-compact='true'] .auth-seg__btn {
        flex: 1 1 3.25rem;
      }
      .av2 .auth-seg__btn {
        flex: 1 1 5.5rem;
        min-width: 0;
        min-height: max(2.5rem, var(--av2-tap));
        padding: 0 6px;
        border: 0;
        border-radius: 12px;
        background: var(--av2-card);
        color: var(--av2-ink);
        box-shadow: 0 var(--av2-press-sm) 0 var(--av2-line-2);
        font-family: inherit;
        font-size: var(--av2-t-label);
        font-weight: 700;
        line-height: 1.2;
        cursor: pointer;
        overflow-wrap: break-word;
        transition: transform var(--av2-press-dur), box-shadow var(--av2-press-dur);
      }
      .av2 .auth-seg__btn[data-active='true'] {
        background: var(--av2-ink);
        color: var(--av2-on-ink);
        box-shadow: 0 var(--av2-press-sm) 0 var(--av2-ink-deep);
      }
      .av2 .auth-seg__btn:active,
      .av2 .auth-choice:active {
        transform: translateY(var(--av2-press-sm));
        box-shadow: 0 0 0 transparent;
      }
      .av2 .auth-choices__list {
        display: flex;
        flex-direction: column;
        gap: 8px;
      }
      .av2 .auth-choice {
        display: flex;
        align-items: center;
        gap: 12px;
        min-height: var(--av2-tap);
        padding: 10px 14px;
        border: 2px solid transparent;
        border-radius: var(--av2-r-card);
        background: var(--av2-card);
        color: var(--av2-ink);
        box-shadow: 0 var(--av2-press-sm) 0 var(--av2-line-2);
        font-family: inherit;
        font-size: var(--av2-t-body);
        font-weight: 600;
        line-height: 1.3;
        text-align: left;
        cursor: pointer;
        transition: transform var(--av2-press-dur), box-shadow var(--av2-press-dur);
      }
      .av2 .auth-choice[data-active='true'] {
        border-color: var(--av2-blue);
      }
      .av2 .auth-choice__dot {
        flex: none;
        width: 18px;
        height: 18px;
        border-radius: var(--av2-r-pill);
        box-shadow: inset 0 0 0 2px var(--av2-line-2);
      }
      .av2 .auth-choice[data-active='true'] .auth-choice__dot {
        background: var(--av2-blue);
        box-shadow: inset 0 0 0 2px var(--av2-blue);
      }
      .av2 .auth-steps {
        display: flex;
        align-items: center;
        gap: 10px;
      }
      .av2 .auth-steps__bars {
        display: flex;
        flex: 1 1 auto;
        gap: 4px;
      }
      .av2 .auth-steps__bars i {
        flex: 1 1 0;
        height: 4px;
        border-radius: 2px;
        background: var(--av2-line);
      }
      .av2 .auth-steps__bars i[data-on='true'] {
        background: var(--av2-blue);
      }
    `}</style>
  );
}
