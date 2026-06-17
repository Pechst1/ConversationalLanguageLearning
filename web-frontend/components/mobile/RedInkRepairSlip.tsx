import React from 'react';
import { Check } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface RedInkRepairSlipProps extends Omit<React.HTMLAttributes<HTMLElement>, 'title'> {
  label?: React.ReactNode;
  stamp?: React.ReactNode;
  slipNumber?: React.ReactNode;
  learnerText?: React.ReactNode;
  correctedText?: React.ReactNode;
  why?: React.ReactNode;
  repair?: React.ReactNode;
  source?: React.ReactNode;
  meta?: React.ReactNode;
  action?: React.ReactNode;
  compact?: boolean;
  filed?: boolean;
}

const RedInkRepairSlip = React.forwardRef<HTMLElement, RedInkRepairSlipProps>(
  (
    {
      label = 'Red ink repair',
      stamp,
      slipNumber,
      learnerText,
      correctedText,
      why,
      repair,
      source,
      meta,
      action,
      compact = false,
      filed = false,
      className,
      ...props
    },
    ref,
  ) => {
    const hasBody = learnerText || correctedText || why || repair;
    return (
      <article
        ref={ref}
        className={cn('red-ink-repair-slip', compact && 'compact', filed && 'filed', className)}
        aria-label="Red ink repair"
        {...props}
      >
        <header className="repair-slip-head">
          <span className="repair-slip-label">{label}</span>
          {slipNumber && <span className="repair-slip-number">{slipNumber}</span>}
          {stamp && <span className="repair-slip-stamp">{stamp}</span>}
        </header>

        {source && <div className="repair-slip-source">{source}</div>}

        {hasBody && (
          <div className="repair-slip-body">
            {learnerText && (
              <section>
                <span>You wrote</span>
                <p className="wrong">{learnerText}</p>
              </section>
            )}
            {correctedText && (
              <section>
                <span>Corrected</span>
                <p className="right">{correctedText}</p>
              </section>
            )}
            {(why || repair) && (
              <div className="repair-slip-why">
                {why && <p><strong>Why.</strong> {why}</p>}
                {repair && <p><strong>Repair.</strong> {repair}</p>}
              </div>
            )}
          </div>
        )}

        {filed && (
          <div className="repair-slip-filed" aria-live="polite">
            <Check size={14} aria-hidden="true" />
            <strong>Corrected. Filed.</strong>
            <span>This slip leaves today and returns on schedule.</span>
          </div>
        )}

        {(meta || action) && (
          <footer className="repair-slip-footer">
            {meta && <span>{meta}</span>}
            {action && <div>{action}</div>}
          </footer>
        )}

        <style jsx>{`
          .red-ink-repair-slip {
            --repair-paper: var(--app-paper, var(--paper, #f1ece1));
            --repair-sheet: var(--app-sheet, var(--paper-2, #f8f3e8));
            --repair-ink: var(--app-ink, var(--ink, #14110d));
            --repair-ink-2: var(--app-ink-2, var(--ink-2, #4a4538));
            --repair-ink-3: var(--app-ink-3, var(--ink-3, #8a826f));
            --repair-red: var(--app-red, var(--red, #d8321a));
            --repair-blue: var(--app-blue, var(--blue, #1d3a8a));
            --repair-yellow: var(--app-yellow, var(--yellow, #f3c318));
            display: grid;
            gap: 12px;
            border: 1px solid var(--repair-ink);
            border-left: 5px solid var(--repair-red);
            background: var(--repair-sheet);
            color: var(--repair-ink);
            padding: 14px;
            box-shadow: 4px 4px 0 color-mix(in srgb, var(--repair-ink) 92%, transparent);
          }
          .red-ink-repair-slip.compact {
            gap: 9px;
            padding: 11px 12px;
            box-shadow: none;
          }
          .red-ink-repair-slip.filed {
            border-left-color: var(--repair-blue);
          }
          .repair-slip-head,
          .repair-slip-footer {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 10px;
          }
          .repair-slip-label,
          .repair-slip-number,
          .repair-slip-stamp,
          .repair-slip-source,
          .repair-slip-body section span,
          .repair-slip-footer {
            font: 900 10px/1 var(--app-mono, ui-monospace, SFMono-Regular, Menlo, monospace);
            letter-spacing: .11em;
            text-transform: uppercase;
          }
          .repair-slip-label {
            color: var(--repair-ink);
            overflow-wrap: anywhere;
          }
          .repair-slip-number,
          .repair-slip-stamp,
          .repair-slip-source,
          .repair-slip-footer {
            color: var(--repair-ink-3);
          }
          .repair-slip-stamp {
            border: 1px solid var(--repair-ink);
            background: var(--repair-paper);
            padding: 5px 7px;
            color: var(--repair-red);
          }
          .repair-slip-source {
            border-top: 1px solid color-mix(in srgb, var(--repair-ink) 18%, transparent);
            padding-top: 8px;
            line-height: 1.35;
          }
          .repair-slip-body {
            display: grid;
            gap: 11px;
          }
          .repair-slip-body section span {
            display: block;
            margin-bottom: 5px;
            color: var(--repair-ink-3);
          }
          .repair-slip-body p {
            margin: 0;
            overflow-wrap: anywhere;
          }
          .wrong,
          .right {
            font-family: var(--app-serif, "EB Garamond", Garamond, "Times New Roman", serif);
            font-size: 21px;
            font-style: italic;
            line-height: 1.25;
          }
          .wrong {
            color: var(--repair-red);
            text-decoration: line-through;
            text-decoration-thickness: 2px;
          }
          .right {
            display: inline;
            background: linear-gradient(transparent 62%, color-mix(in srgb, var(--repair-yellow) 48%, transparent) 62%);
            color: var(--repair-ink);
          }
          .repair-slip-why {
            border-left: 4px solid var(--repair-blue);
            padding-left: 10px;
            color: var(--repair-ink-2);
            font-size: 13px;
            line-height: 1.42;
          }
          .repair-slip-why p + p {
            margin-top: 6px;
          }
          .repair-slip-filed {
            display: grid;
            grid-template-columns: auto minmax(0, 1fr);
            gap: 4px 8px;
            align-items: center;
            border: 1px solid var(--repair-ink);
            background: var(--repair-paper);
            padding: 10px;
            color: var(--repair-ink);
            animation: filed-reveal 180ms ease-out both;
          }
          .repair-slip-filed svg {
            color: var(--repair-blue);
          }
          .repair-slip-filed strong {
            font-size: 14px;
            line-height: 1.1;
          }
          .repair-slip-filed span {
            grid-column: 2;
            color: var(--repair-ink-3);
            font-size: 12px;
            font-weight: 800;
            line-height: 1.3;
          }
          .repair-slip-footer {
            border-top: 1px solid color-mix(in srgb, var(--repair-ink) 18%, transparent);
            padding-top: 9px;
            line-height: 1.3;
          }
          .repair-slip-footer > div {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            justify-content: flex-end;
          }
          .repair-slip-footer :global(a),
          .repair-slip-footer :global(button) {
            min-height: 34px;
          }
          @keyframes filed-reveal {
            from {
              opacity: 0;
              transform: translateY(7px);
            }
            to {
              opacity: 1;
              transform: translateY(0);
            }
          }
        `}</style>
      </article>
    );
  }
);

RedInkRepairSlip.displayName = 'RedInkRepairSlip';

export { RedInkRepairSlip };
