import React from 'react';
import Link from 'next/link';
import { ArrowRight, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

export type ContinuationTone = 'neutral' | 'grammar' | 'vocabulary' | 'errata' | 'mission' | 'feuilleton';

export type ContinuationFocusItem = string | {
  label: React.ReactNode;
  tone?: ContinuationTone;
};

export type ContinuationAction = {
  label: React.ReactNode;
  href?: string;
  onClick?: () => void;
  disabled?: boolean;
  loading?: boolean;
  tone?: 'primary' | 'secondary' | 'quiet';
  ariaLabel?: string;
};

export interface ContinuationCardProps extends Omit<React.HTMLAttributes<HTMLElement>, 'title'> {
  eyebrow?: React.ReactNode;
  title: React.ReactNode;
  description?: React.ReactNode;
  focus?: ContinuationFocusItem[];
  actions?: ContinuationAction[];
  footer?: React.ReactNode;
  tone?: ContinuationTone;
  compact?: boolean;
}

function focusTone(item: ContinuationFocusItem, fallback: ContinuationTone) {
  return typeof item === 'string' ? fallback : item.tone || fallback;
}

function focusLabel(item: ContinuationFocusItem) {
  return typeof item === 'string' ? item : item.label;
}

function ActionContent({ action }: { action: ContinuationAction }) {
  return (
    <>
      {action.loading && <Loader2 size={13} className="spin" aria-hidden="true" />}
      <span>{action.label}</span>
      {!action.loading && <ArrowRight size={13} aria-hidden="true" />}
      <style jsx>{`
        .spin {
          animation: continuation-spin 800ms linear infinite;
        }
        @keyframes continuation-spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </>
  );
}

const ContinuationCard = React.forwardRef<HTMLElement, ContinuationCardProps>(
  (
    {
      eyebrow = 'Next best move',
      title,
      description,
      focus = [],
      actions = [],
      footer,
      tone = 'neutral',
      compact = false,
      className,
      ...props
    },
    ref,
  ) => {
    return (
      <section
        ref={ref}
        className={cn('continuation-card', `continuation-${tone}`, compact && 'compact', className)}
        aria-label="Continuation"
        {...props}
      >
        <div className="continuation-copy">
          {eyebrow && <span className="continuation-eyebrow">{eyebrow}</span>}
          <h3>{title}</h3>
          {description && <p>{description}</p>}
        </div>

        {focus.length > 0 && (
          <div className="continuation-focus" aria-label="Carried learning context">
            {focus.map((item, index) => (
              <span key={`${String(focusLabel(item))}-${index}`} className={`focus-${focusTone(item, tone)}`}>
                {focusLabel(item)}
              </span>
            ))}
          </div>
        )}

        {actions.length > 0 && (
          <div className="continuation-actions">
            {actions.map((action, index) => {
              const className = `continuation-action ${action.tone || (index === 0 ? 'primary' : 'secondary')}`;
              const key = `${String(action.label)}-${index}`;
              if (action.href && !action.disabled) {
                return (
                  <Link key={key} href={action.href} className={className} aria-label={action.ariaLabel}>
                    <ActionContent action={action} />
                  </Link>
                );
              }
              return (
                <button
                  key={key}
                  type="button"
                  className={className}
                  disabled={action.disabled || action.loading}
                  aria-label={action.ariaLabel}
                  onClick={action.onClick}
                >
                  <ActionContent action={action} />
                </button>
              );
            })}
          </div>
        )}

        {footer && <div className="continuation-footer">{footer}</div>}

        <style jsx>{`
          .continuation-card {
            --continuation-paper: var(--app-paper, var(--paper, #f1ece1));
            --continuation-sheet: var(--app-sheet, var(--paper-2, #f8f3e8));
            --continuation-ink: var(--app-ink, var(--ink, #14110d));
            --continuation-ink-2: var(--app-ink-2, var(--ink-2, #4a4538));
            --continuation-ink-3: var(--app-ink-3, var(--ink-3, #8a826f));
            --continuation-red: var(--app-red, var(--red, #d8321a));
            --continuation-blue: var(--app-blue, var(--blue, #1d3a8a));
            --continuation-yellow: var(--app-yellow, var(--yellow, #f3c318));
            display: grid;
            gap: 13px;
            border: 1px solid var(--continuation-ink);
            border-left: 5px solid var(--continuation-accent, var(--continuation-ink));
            background: var(--continuation-sheet);
            color: var(--continuation-ink);
            padding: 14px;
          }
          .continuation-grammar,
          .continuation-mission,
          .focus-grammar,
          .focus-mission {
            --continuation-accent: var(--continuation-blue);
          }
          .continuation-vocabulary,
          .continuation-feuilleton,
          .focus-vocabulary,
          .focus-feuilleton {
            --continuation-accent: var(--continuation-yellow);
          }
          .continuation-errata,
          .focus-errata {
            --continuation-accent: var(--continuation-red);
          }
          .continuation-copy {
            min-width: 0;
          }
          .continuation-eyebrow,
          .continuation-focus span,
          .continuation-footer {
            font: 900 10px/1 var(--app-mono, ui-monospace, SFMono-Regular, Menlo, monospace);
            letter-spacing: .1em;
            text-transform: uppercase;
          }
          .continuation-eyebrow {
            display: block;
            color: var(--continuation-ink-3);
          }
          .continuation-copy h3 {
            margin: 7px 0 0;
            font-size: 18px;
            line-height: 1.12;
            overflow-wrap: anywhere;
          }
          .continuation-copy p {
            margin: 7px 0 0;
            color: var(--continuation-ink-2);
            font-size: 13px;
            line-height: 1.42;
          }
          .continuation-focus {
            display: flex;
            flex-wrap: wrap;
            gap: 7px;
          }
          .continuation-focus span {
            border: 1px solid var(--continuation-ink);
            border-left: 4px solid var(--continuation-accent, var(--continuation-ink));
            background: var(--continuation-paper);
            padding: 7px 8px;
            color: var(--continuation-ink);
          }
          .continuation-actions {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(136px, 1fr));
            gap: 8px;
          }
          .continuation-action {
            min-height: 44px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 7px;
            border: 1px solid var(--continuation-ink);
            background: var(--continuation-paper);
            padding: 0 10px;
            color: var(--continuation-ink);
            font: inherit;
            font-size: 12px;
            font-weight: 900;
            line-height: 1.1;
            text-align: center;
            text-decoration: none;
            text-transform: uppercase;
          }
          .continuation-action.primary {
            background: var(--continuation-ink);
            color: var(--continuation-paper);
          }
          .continuation-action.quiet {
            background: transparent;
          }
          .continuation-action:disabled {
            opacity: .55;
          }
          .continuation-footer {
            color: var(--continuation-ink-3);
            line-height: 1.3;
          }
          .continuation-card.compact {
            gap: 10px;
            padding: 12px;
          }
          .continuation-card.compact .continuation-copy h3 {
            font-size: 16px;
          }
          @media (max-width: 520px) {
            .continuation-actions {
              grid-template-columns: 1fr;
            }
          }
        `}</style>
      </section>
    );
  }
);

ContinuationCard.displayName = 'ContinuationCard';

export { ContinuationCard };
