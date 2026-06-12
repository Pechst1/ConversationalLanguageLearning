import React from 'react';
import { cn } from '@/lib/utils';

export interface FeedbackSlipProps extends Omit<React.HTMLAttributes<HTMLDivElement>, 'title'> {
  tone?: 'neutral' | 'correct' | 'error' | 'warning';
  label?: React.ReactNode;
  stamp?: React.ReactNode;
  title?: React.ReactNode;
  action?: React.ReactNode;
}

const FeedbackSlip = React.forwardRef<HTMLDivElement, FeedbackSlipProps>(
  (
    {
      tone = 'neutral',
      label = 'Feedback',
      stamp,
      title,
      action,
      className,
      children,
      ...props
    },
    ref
  ) => (
    <div ref={ref} className={cn('feedback-slip', `feedback-slip-${tone}`, className)} {...props}>
      <header className="feedback-slip-head">
        <span className="feedback-slip-mark" aria-hidden="true" />
        <strong>{label}</strong>
        {stamp && <em>{stamp}</em>}
      </header>
      <div className="feedback-slip-body">
        {title && <p className="feedback-slip-title">{title}</p>}
        <div className="feedback-slip-content">{children}</div>
        {action && <div className="feedback-slip-action">{action}</div>}
      </div>
      <style jsx>{`
        .feedback-slip {
          --mobile-paper: var(--app-paper, var(--paper, #f1ece1));
          --mobile-sheet: var(--app-sheet, var(--paper-2, #f8f3e8));
          --mobile-ink: var(--app-ink, var(--ink, #14110d));
          --mobile-ink-2: var(--app-ink-2, var(--ink-2, #4a4538));
          --mobile-ink-3: var(--app-ink-3, var(--ink-3, #8a826f));
          --mobile-blue: var(--app-blue, var(--blue, #1d3a8a));
          --mobile-red: var(--app-red, var(--red, #d8321a));
          --mobile-yellow: var(--app-yellow, var(--yellow, #f3c318));
          border: 1px solid var(--mobile-ink);
          background: var(--slip-bg, var(--mobile-sheet));
          color: var(--mobile-ink);
          animation: feedback-slip-reveal 180ms ease-out both;
        }
        .feedback-slip-correct {
          --slip-accent: var(--mobile-blue);
        }
        .feedback-slip-error {
          --slip-accent: var(--mobile-red);
        }
        .feedback-slip-warning {
          --slip-accent: var(--mobile-yellow);
        }
        .feedback-slip-neutral {
          --slip-accent: var(--mobile-ink);
        }
        .feedback-slip-head {
          display: flex;
          align-items: center;
          gap: 8px;
          min-height: 36px;
          border-bottom: 1px solid var(--mobile-ink);
          padding: 8px 11px;
        }
        .feedback-slip-head strong {
          color: var(--mobile-ink);
          font: 900 10px/1 var(--app-mono, "Inter", "Helvetica Neue", Arial, sans-serif);
          letter-spacing: .12em;
          text-transform: uppercase;
        }
        .feedback-slip-head em {
          margin-left: auto;
          color: var(--mobile-ink-3);
          font-size: 11px;
          font-style: normal;
          line-height: 1;
        }
        .feedback-slip-mark {
          width: 10px;
          height: 10px;
          background: var(--slip-accent);
        }
        .feedback-slip-body {
          padding: 12px;
        }
        .feedback-slip-title {
          margin: 0 0 6px;
          font-weight: 800;
          line-height: 1.25;
        }
        .feedback-slip-content {
          color: var(--mobile-ink-2);
          font-size: 13px;
          line-height: 1.42;
        }
        .feedback-slip-content :global(p) {
          margin: 0;
        }
        .feedback-slip-content :global(p + p) {
          margin-top: 7px;
        }
        .feedback-slip-action {
          margin-top: 12px;
          border-top: 1px solid color-mix(in srgb, var(--mobile-ink) 22%, transparent);
          padding-top: 10px;
        }
        @keyframes feedback-slip-reveal {
          from {
            opacity: 0;
            transform: translateY(8px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
      `}</style>
    </div>
  )
);

FeedbackSlip.displayName = 'FeedbackSlip';

export { FeedbackSlip };
