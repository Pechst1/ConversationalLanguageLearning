import React from 'react';
import { cn } from '@/lib/utils';

export interface MobileMastheadActionProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  active?: boolean;
  label?: string;
}

const MobileMastheadAction = React.forwardRef<HTMLButtonElement, MobileMastheadActionProps>(
  ({ active = false, label, className, children, type = 'button', ...props }, ref) => (
    <button
      ref={ref}
      className={cn('mobile-masthead-action', active && 'mobile-masthead-action-active', className)}
      type={type}
      aria-label={props['aria-label'] || label}
      {...props}
    >
      {children}
      {label && <span>{label}</span>}
      <style jsx>{`
        .mobile-masthead-action {
          --mobile-paper: var(--app-paper, var(--paper, #f1ece1));
          --mobile-ink: var(--app-ink, var(--ink, #14110d));
          --mobile-sheet: var(--app-sheet, var(--paper-2, #f8f3e8));
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 6px;
          min-width: 44px;
          min-height: 44px;
          border: 1px solid var(--mobile-ink);
          background: var(--mobile-paper);
          color: var(--mobile-ink);
          padding: 0 10px;
          font: 900 10px/1 var(--app-mono, "Inter", "Helvetica Neue", Arial, sans-serif);
          letter-spacing: .1em;
          text-transform: uppercase;
        }
        .mobile-masthead-action :global(svg) {
          width: 18px;
          height: 18px;
          flex: 0 0 auto;
        }
        .mobile-masthead-action span {
          max-width: 72px;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        .mobile-masthead-action-active,
        .mobile-masthead-action:hover:not(:disabled) {
          background: var(--mobile-ink);
          color: var(--mobile-paper);
        }
        .mobile-masthead-action:disabled {
          cursor: not-allowed;
          opacity: .45;
        }
      `}</style>
    </button>
  )
);

MobileMastheadAction.displayName = 'MobileMastheadAction';

export { MobileMastheadAction };
