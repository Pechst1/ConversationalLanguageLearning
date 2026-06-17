import React from 'react';
import { cn } from '@/lib/utils';

export interface StickyCTAProps extends Omit<React.HTMLAttributes<HTMLDivElement>, 'title'> {
  eyebrow?: React.ReactNode;
  title?: React.ReactNode;
  description?: React.ReactNode;
  primary?: React.ReactNode;
  secondary?: React.ReactNode;
}

const StickyCTA = React.forwardRef<HTMLDivElement, StickyCTAProps>(
  ({ eyebrow, title, description, primary, secondary, className, children, ...props }, ref) => (
    <div ref={ref} className={cn('sticky-cta', className)} {...props}>
      <div className="sticky-cta-copy">
        {eyebrow && <p className="sticky-cta-eyebrow">{eyebrow}</p>}
        {title && <strong className="sticky-cta-title">{title}</strong>}
        {description && <p className="sticky-cta-description">{description}</p>}
        {children}
      </div>
      {(primary || secondary) && (
        <div className="sticky-cta-actions">
          {secondary}
          {primary}
        </div>
      )}
      <style jsx>{`
        .sticky-cta {
          --mobile-paper: var(--app-paper, var(--paper, #f1ece1));
          --mobile-sheet: var(--app-sheet, var(--paper-2, #f8f3e8));
          --mobile-ink: var(--app-ink, var(--ink, #14110d));
          --mobile-ink-2: var(--app-ink-2, var(--ink-2, #4a4538));
          --mobile-ink-3: var(--app-ink-3, var(--ink-3, #8a826f));
          position: sticky;
          bottom: 0;
          z-index: 30;
          display: grid;
          grid-template-columns: minmax(0, 1fr);
          gap: 12px;
          border-top: 1px solid var(--mobile-ink);
          background: var(--mobile-paper);
          color: var(--mobile-ink);
          padding: 13px 16px calc(13px + env(safe-area-inset-bottom));
        }
        .sticky-cta-copy {
          min-width: 0;
        }
        .sticky-cta-eyebrow,
        .sticky-cta-description {
          margin: 0;
        }
        .sticky-cta-eyebrow {
          color: var(--mobile-ink-3);
          font: 900 10px/1 var(--app-mono, "Inter", "Helvetica Neue", Arial, sans-serif);
          letter-spacing: .12em;
          text-transform: uppercase;
        }
        .sticky-cta-title {
          display: block;
          margin-top: 4px;
          overflow-wrap: anywhere;
          font-size: 15px;
          line-height: 1.2;
        }
        .sticky-cta-description {
          margin-top: 5px;
          color: var(--mobile-ink-2);
          font-size: 12px;
          line-height: 1.35;
        }
        .sticky-cta-actions {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 8px;
        }
        .sticky-cta-actions :global(button),
        .sticky-cta-actions :global(a) {
          min-width: 0;
        }
      `}</style>
    </div>
  )
);

StickyCTA.displayName = 'StickyCTA';

export { StickyCTA };
