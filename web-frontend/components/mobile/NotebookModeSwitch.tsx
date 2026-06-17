import React from 'react';
import Link from 'next/link';
import { cn } from '@/lib/utils';

export type NotebookMode = 'grammar' | 'vocabulary' | 'library';

export interface NotebookModeSwitchProps extends React.HTMLAttributes<HTMLElement> {
  active: NotebookMode;
  grammarMeta?: React.ReactNode;
  vocabularyMeta?: React.ReactNode;
  libraryMeta?: React.ReactNode;
}

const STORAGE_KEY = 'atelier:notebook-mode';

function rememberNotebookMode(mode: NotebookMode) {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(STORAGE_KEY, mode);
  } catch {
    // Remembering the last notebook mode is a convenience; navigation should still work.
  }
}

const NotebookModeSwitch = React.forwardRef<HTMLElement, NotebookModeSwitchProps>(
  ({ active, grammarMeta, vocabularyMeta, libraryMeta, className, ...props }, ref) => (
    <nav
      ref={ref}
      className={cn('notebook-mode-switch', className)}
      aria-label="Notebook mode"
      data-active-mode={active}
      {...props}
    >
      <Link
        href="/grammar"
        aria-current={active === 'grammar' ? 'page' : undefined}
        className={active === 'grammar' ? 'active' : ''}
        onClick={() => rememberNotebookMode('grammar')}
      >
        <span>Grammar</span>
        {grammarMeta && <em>{grammarMeta}</em>}
      </Link>
      <Link
        href="/vocabulary"
        aria-current={active === 'vocabulary' ? 'page' : undefined}
        className={active === 'vocabulary' ? 'active' : ''}
        onClick={() => rememberNotebookMode('vocabulary')}
      >
        <span>Vocabulary</span>
        {vocabularyMeta && <em>{vocabularyMeta}</em>}
      </Link>
      <Link
        href="/notebook?mode=library"
        aria-current={active === 'library' ? 'page' : undefined}
        className={active === 'library' ? 'active' : ''}
        onClick={() => rememberNotebookMode('library')}
      >
        <span>Library</span>
        {libraryMeta && <em>{libraryMeta}</em>}
      </Link>
      <style jsx>{`
        .notebook-mode-switch {
          --switch-paper: var(--app-paper, var(--paper, #f1ece1));
          --switch-sheet: var(--app-sheet, var(--sheet, #f8f3e8));
          --switch-ink: var(--app-ink, var(--ink, #14110d));
          --switch-ink-3: var(--app-ink-3, var(--ink-3, #8a826f));
          --switch-blue: var(--app-blue, var(--blue, #1d3a8a));
          --switch-yellow: var(--app-yellow, var(--yellow, #f3c318));
          display: grid;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: 0;
          width: 100%;
          border: 1px solid var(--switch-ink);
          background: var(--switch-ink);
        }
        .notebook-mode-switch :global(a) {
          display: grid;
          min-width: 0;
          min-height: 54px;
          align-content: center;
          gap: 5px;
          background: var(--switch-sheet);
          color: var(--switch-ink);
          padding: 10px 12px;
          text-decoration: none;
        }
        .notebook-mode-switch :global(a + a) {
          border-left: 1px solid var(--switch-ink);
        }
        .notebook-mode-switch :global(a.active) {
          background: var(--switch-ink);
          color: var(--switch-paper);
        }
        .notebook-mode-switch :global(a.active:nth-child(2)) {
          box-shadow: inset 0 4px 0 var(--switch-yellow);
        }
        .notebook-mode-switch :global(a.active:first-child) {
          box-shadow: inset 0 4px 0 var(--switch-blue);
        }
        .notebook-mode-switch :global(a.active:last-child) {
          box-shadow: inset 0 4px 0 var(--switch-blue), inset 0 -4px 0 var(--switch-yellow);
        }
        .notebook-mode-switch span,
        .notebook-mode-switch em {
          display: block;
          min-width: 0;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        .notebook-mode-switch span {
          font: 900 12px/1 var(--app-mono, "Inter", "Helvetica Neue", Arial, sans-serif);
          letter-spacing: .11em;
          text-transform: uppercase;
        }
        .notebook-mode-switch em {
          color: var(--switch-ink-3);
          font-size: 12px;
          font-style: normal;
          font-weight: 750;
          line-height: 1.2;
        }
        .notebook-mode-switch :global(a.active) em {
          color: color-mix(in srgb, var(--switch-paper) 70%, transparent);
        }
      `}</style>
    </nav>
  )
);

NotebookModeSwitch.displayName = 'NotebookModeSwitch';

export { NotebookModeSwitch, STORAGE_KEY as NOTEBOOK_MODE_STORAGE_KEY };
