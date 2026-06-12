import React from 'react';
import { cn } from '@/lib/utils';

export interface MobileSheetProps extends Omit<React.HTMLAttributes<HTMLElement>, 'title'> {
  as?: 'section' | 'article' | 'div';
  eyebrow?: React.ReactNode;
  title?: React.ReactNode;
  description?: React.ReactNode;
  action?: React.ReactNode;
  inset?: boolean;
}

const MobileSheet = React.forwardRef<HTMLElement, MobileSheetProps>(
  (
    {
      as: Component = 'section',
      eyebrow,
      title,
      description,
      action,
      inset = true,
      className,
      children,
      ...props
    },
    ref
  ) => (
    <Component
      ref={ref as React.Ref<HTMLDivElement>}
      className={cn('mobile-sheet', inset && 'mobile-sheet-inset', className)}
      {...props}
    >
      {(eyebrow || title || description || action) && (
        <header className="mobile-sheet-head">
          <div className="mobile-sheet-copy">
            {eyebrow && <p className="mobile-sheet-eyebrow">{eyebrow}</p>}
            {title && <h2 className="mobile-sheet-title">{title}</h2>}
            {description && <p className="mobile-sheet-description">{description}</p>}
          </div>
          {action && <div className="mobile-sheet-action">{action}</div>}
        </header>
      )}
      <div className="mobile-sheet-body">{children}</div>
      <style jsx>{`
        .mobile-sheet {
          --mobile-paper: var(--app-paper, var(--paper, #f1ece1));
          --mobile-sheet: var(--app-sheet, var(--paper-2, #f8f3e8));
          --mobile-ink: var(--app-ink, var(--ink, #14110d));
          --mobile-ink-2: var(--app-ink-2, var(--ink-2, #4a4538));
          --mobile-ink-3: var(--app-ink-3, var(--ink-3, #8a826f));
          box-sizing: border-box;
          width: 100%;
          border: 1px solid var(--mobile-ink);
          background: var(--mobile-sheet);
          color: var(--mobile-ink);
        }
        .mobile-sheet-inset {
          margin: 0 16px;
        }
        .mobile-sheet-head {
          display: grid;
          grid-template-columns: minmax(0, 1fr) auto;
          gap: 14px;
          align-items: start;
          border-bottom: 1px solid var(--mobile-ink);
          padding: 13px 14px 12px;
        }
        .mobile-sheet-copy {
          min-width: 0;
        }
        .mobile-sheet-eyebrow {
          margin: 0 0 5px;
          color: var(--mobile-ink-3);
          font: 900 10px/1 var(--app-mono, "Inter", "Helvetica Neue", Arial, sans-serif);
          letter-spacing: .12em;
          text-transform: uppercase;
        }
        .mobile-sheet-title {
          margin: 0;
          color: var(--mobile-ink);
          font-family: var(--app-serif, "EB Garamond", Garamond, "Times New Roman", serif);
          font-size: 24px;
          font-style: italic;
          font-weight: 500;
          letter-spacing: 0;
          line-height: 1.05;
        }
        .mobile-sheet-description {
          margin: 7px 0 0;
          color: var(--mobile-ink-2);
          font-size: 13px;
          line-height: 1.4;
        }
        .mobile-sheet-action {
          display: flex;
          align-items: center;
          justify-content: flex-end;
        }
        .mobile-sheet-body {
          padding: 14px;
        }
      `}</style>
    </Component>
  )
);

MobileSheet.displayName = 'MobileSheet';

export { MobileSheet };
