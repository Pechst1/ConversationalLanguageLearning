import React from 'react';
import { cn } from '@/lib/utils';

export interface MobileChipProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  active?: boolean;
  tone?: 'ink' | 'blue' | 'red' | 'yellow';
}

const MobileChip = React.forwardRef<HTMLButtonElement, MobileChipProps>(
  ({ active = false, tone = 'ink', className, children, type = 'button', ...props }, ref) => (
    <button
      ref={ref}
      className={cn('mobile-chip', active && 'mobile-chip-active', `mobile-chip-${tone}`, className)}
      type={type}
      {...props}
    >
      {children}
      <style jsx>{`
        .mobile-chip {
          --mobile-paper: var(--app-paper, var(--paper, #f1ece1));
          --mobile-ink: var(--app-ink, var(--ink, #14110d));
          --mobile-blue: var(--app-blue, var(--blue, #1d3a8a));
          --mobile-red: var(--app-red, var(--red, #d8321a));
          --mobile-yellow: var(--app-yellow, var(--yellow, #f3c318));
          display: inline-flex;
          align-items: center;
          justify-content: center;
          min-height: 36px;
          min-width: 0;
          border: 1px solid var(--chip-border, var(--mobile-ink));
          background: var(--mobile-paper);
          color: var(--chip-color, var(--mobile-ink));
          padding: 0 12px;
          font: 900 10px/1 var(--app-mono, "Inter", "Helvetica Neue", Arial, sans-serif);
          letter-spacing: .1em;
          text-transform: uppercase;
          transition: background .14s ease, color .14s ease, border-color .14s ease;
        }
        .mobile-chip-blue {
          --chip-border: var(--mobile-blue);
          --chip-color: var(--mobile-blue);
        }
        .mobile-chip-red {
          --chip-border: var(--mobile-red);
          --chip-color: var(--mobile-red);
        }
        .mobile-chip-yellow {
          --chip-border: var(--mobile-yellow);
          --chip-color: var(--mobile-ink);
        }
        .mobile-chip-active,
        .mobile-chip:hover:not(:disabled) {
          background: var(--chip-border, var(--mobile-ink));
          color: var(--mobile-paper);
        }
        .mobile-chip-yellow.mobile-chip-active,
        .mobile-chip-yellow:hover:not(:disabled) {
          color: var(--mobile-ink);
        }
        .mobile-chip:disabled {
          cursor: not-allowed;
          opacity: .45;
        }
      `}</style>
    </button>
  )
);

MobileChip.displayName = 'MobileChip';

export { MobileChip };
