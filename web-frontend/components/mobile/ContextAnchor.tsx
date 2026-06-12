import React from 'react';
import { cn } from '@/lib/utils';

export interface ContextAnchorProps extends Omit<React.HTMLAttributes<HTMLElement>, 'title'> {
  as?: 'aside' | 'article' | 'div';
  label?: React.ReactNode;
  title?: React.ReactNode;
  text?: React.ReactNode;
  translation?: React.ReactNode;
  meta?: React.ReactNode;
  compact?: boolean;
  quote?: boolean;
  tone?: 'blue' | 'red' | 'yellow' | 'green';
}

const ContextAnchor = React.forwardRef<HTMLElement, ContextAnchorProps>(
  (
    {
      as: Component = 'aside',
      label = 'Context',
      title,
      text,
      translation,
      meta,
      compact = false,
      quote = false,
      tone = 'blue',
      className,
      children,
      ...props
    },
    ref
  ) => {
    if (!title && !text && !translation && !children) return null;
    const AnchorComponent = Component as React.ElementType;

    return (
      <AnchorComponent
        ref={ref}
        className={cn('context-anchor', `context-anchor-${tone}`, compact && 'compact', quote && 'quote', className)}
        {...props}
      >
        {label && <span className="context-anchor-label">{label}</span>}
        {title && <strong>{title}</strong>}
        {text && <p>{text}</p>}
        {translation && <em>{translation}</em>}
        {meta && <small>{meta}</small>}
        {children}
        <style jsx>{`
          .context-anchor {
            --anchor-paper: var(--app-paper, var(--paper, #f1ece1));
            --anchor-sheet: var(--app-sheet, var(--paper-2, #f8f3e8));
            --anchor-ink: var(--app-ink, var(--ink, #14110d));
            --anchor-ink-2: var(--app-ink-2, var(--ink-2, #4a4538));
            --anchor-ink-3: var(--app-ink-3, var(--ink-3, #8a826f));
            --anchor-blue: var(--app-blue, var(--blue, #1d3a8a));
            --anchor-red: var(--app-red, var(--red, #d8321a));
            --anchor-yellow: var(--app-yellow, var(--yellow, #f3c318));
            --anchor-green: var(--app-green, var(--green, #2e7d32));
            display: block;
            min-width: 0;
            margin-top: var(--anchor-offset, 14px);
            border: 1px solid var(--anchor-ink);
            border-left: 4px solid var(--anchor-accent, var(--anchor-blue));
            background: var(--anchor-sheet);
            padding: 12px 14px;
            color: var(--anchor-ink);
          }
          .context-anchor-blue {
            --anchor-accent: var(--anchor-blue);
          }
          .context-anchor-red {
            --anchor-accent: var(--anchor-red);
          }
          .context-anchor-yellow {
            --anchor-accent: var(--anchor-yellow);
          }
          .context-anchor-green {
            --anchor-accent: var(--anchor-green);
          }
          .context-anchor.compact {
            --anchor-offset: 0;
            padding: 10px 12px;
          }
          .context-anchor-label {
            display: block;
            color: var(--anchor-ink-3);
            font: 900 10px/1 var(--app-mono, "Inter", "Helvetica Neue", Arial, sans-serif);
            letter-spacing: .1em;
            text-transform: uppercase;
          }
          .context-anchor strong {
            display: block;
            margin-top: 6px;
            color: var(--anchor-ink);
            font-size: 14px;
            line-height: 1.2;
            overflow-wrap: anywhere;
          }
          .context-anchor p {
            margin: 8px 0 0;
            color: var(--anchor-ink);
            font-size: 17px;
            font-weight: 800;
            line-height: 1.28;
            overflow-wrap: anywhere;
          }
          .context-anchor.quote p {
            font-family: var(--app-serif, "EB Garamond", Garamond, "Times New Roman", serif);
            font-size: 22px;
            font-style: italic;
            font-weight: 500;
            line-height: 1.25;
          }
          .context-anchor.compact.quote p {
            font-size: 18px;
          }
          .context-anchor em,
          .context-anchor small {
            display: block;
            margin-top: 6px;
            color: var(--anchor-ink-3);
            font-size: 12px;
            font-style: normal;
            font-weight: 750;
            line-height: 1.35;
            overflow-wrap: anywhere;
          }
          .context-anchor small {
            color: var(--anchor-ink-2);
          }
        `}</style>
      </AnchorComponent>
    );
  }
);

ContextAnchor.displayName = 'ContextAnchor';

export { ContextAnchor };
