import React from 'react';
import { cn } from '@/lib/utils';

export interface MobileRowProps extends Omit<React.HTMLAttributes<HTMLDivElement>, 'title'> {
  leading?: React.ReactNode;
  kicker?: React.ReactNode;
  title?: React.ReactNode;
  description?: React.ReactNode;
  meta?: React.ReactNode;
  trailing?: React.ReactNode;
  selected?: boolean;
}

const MobileRow = React.forwardRef<HTMLDivElement, MobileRowProps>(
  (
    {
      leading,
      kicker,
      title,
      description,
      meta,
      trailing,
      selected = false,
      className,
      children,
      ...props
    },
    ref
  ) => (
    <div
      ref={ref}
      className={cn('mobile-row', selected && 'mobile-row-selected', className)}
      {...props}
    >
      {leading && <div className="mobile-row-leading">{leading}</div>}
      <div className="mobile-row-main">
        {(kicker || meta) && (
          <div className="mobile-row-meta-line">
            {kicker && <span>{kicker}</span>}
            {meta && <span>{meta}</span>}
          </div>
        )}
        {title && <strong className="mobile-row-title">{title}</strong>}
        {description && <p className="mobile-row-description">{description}</p>}
        {children}
      </div>
      {trailing && <div className="mobile-row-trailing">{trailing}</div>}
      <style jsx>{`
        .mobile-row {
          --mobile-paper: var(--app-paper, var(--paper, #f1ece1));
          --mobile-sheet: var(--app-sheet, var(--paper-2, #f8f3e8));
          --mobile-ink: var(--app-ink, var(--ink, #14110d));
          --mobile-ink-2: var(--app-ink-2, var(--ink-2, #4a4538));
          --mobile-ink-3: var(--app-ink-3, var(--ink-3, #8a826f));
          display: grid;
          grid-template-columns: auto minmax(0, 1fr) auto;
          gap: 11px;
          align-items: center;
          min-height: 60px;
          border-top: 1px solid color-mix(in srgb, var(--mobile-ink) 22%, transparent);
          background: transparent;
          color: var(--mobile-ink);
          padding: 10px 14px;
        }
        .mobile-row:first-child {
          border-top-color: transparent;
        }
        .mobile-row-selected {
          background: var(--mobile-paper);
        }
        .mobile-row-leading,
        .mobile-row-trailing {
          display: flex;
          align-items: center;
          justify-content: center;
          color: var(--mobile-ink);
        }
        .mobile-row-main {
          min-width: 0;
        }
        .mobile-row-meta-line {
          display: flex;
          justify-content: space-between;
          gap: 10px;
          margin-bottom: 4px;
          color: var(--mobile-ink-3);
          font: 900 10px/1 var(--app-mono, "Inter", "Helvetica Neue", Arial, sans-serif);
          letter-spacing: .08em;
          text-transform: uppercase;
        }
        .mobile-row-meta-line span {
          min-width: 0;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        .mobile-row-title {
          display: block;
          overflow-wrap: anywhere;
          font-size: 14px;
          line-height: 1.2;
        }
        .mobile-row-description {
          margin: 4px 0 0;
          color: var(--mobile-ink-2);
          font-size: 12px;
          line-height: 1.35;
        }
      `}</style>
    </div>
  )
);

MobileRow.displayName = 'MobileRow';

export { MobileRow };
