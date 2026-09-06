import React from 'react';
import Link from 'next/link';
import { STORY_FEATURE_VISIBLE } from '@/lib/launch-flags';
import { cn } from '@/lib/utils';

export type NotebookMode = 'grammar' | 'vocabulary' | 'library' | 'progress';

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

/* The link-based mode switch for the direct /grammar and /vocabulary routes.
 * Drawn as the Cahier design's segmented pill: `--av2-line` container, radius
 * 999, 3px padding, an ink face with paper text for the active mode. It carries
 * the `av2` class itself so the tokens resolve wherever it is rendered. */
const NotebookModeSwitch = React.forwardRef<HTMLElement, NotebookModeSwitchProps>(
  ({ active, grammarMeta, vocabularyMeta, libraryMeta, className, ...props }, ref) => (
    <nav
      ref={ref}
      className={cn('av2', 'notebook-mode-switch', STORY_FEATURE_VISIBLE && 'with-library', className)}
      aria-label="Rubriques du cahier"
      data-active-mode={active}
      {...props}
    >
      <Link
        href="/grammar"
        aria-current={active === 'grammar' ? 'page' : undefined}
        className={active === 'grammar' ? 'active' : ''}
        onClick={() => rememberNotebookMode('grammar')}
      >
        <span>Règles</span>
        {grammarMeta && <em>{grammarMeta}</em>}
      </Link>
      <Link
        href="/vocabulary"
        aria-current={active === 'vocabulary' ? 'page' : undefined}
        className={active === 'vocabulary' ? 'active' : ''}
        onClick={() => rememberNotebookMode('vocabulary')}
      >
        <span>Mots</span>
        {vocabularyMeta && <em>{vocabularyMeta}</em>}
      </Link>
      {STORY_FEATURE_VISIBLE && (
        <Link
          href="/notebook?mode=library"
          aria-current={active === 'library' ? 'page' : undefined}
          className={active === 'library' ? 'active' : ''}
          onClick={() => rememberNotebookMode('library')}
        >
          <span>Livres</span>
          {libraryMeta && <em>{libraryMeta}</em>}
        </Link>
      )}
      <style jsx global>{`
        .av2.notebook-mode-switch {
          display: flex;
          width: 100%;
          padding: 3px;
          border-radius: var(--av2-r-pill);
          background: var(--av2-line);
        }
        .av2.notebook-mode-switch a {
          flex: 1 1 0;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          gap: 2px;
          min-width: 0;
          min-height: var(--av2-tap);
          padding: 4px 0.8125rem;
          border-radius: var(--av2-r-pill);
          color: var(--av2-ink);
          text-decoration: none;
        }
        .av2.notebook-mode-switch a.active {
          background: var(--av2-ink);
          color: var(--av2-on-ink);
        }
        .av2.notebook-mode-switch span,
        .av2.notebook-mode-switch em {
          display: block;
          max-width: 100%;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        .av2.notebook-mode-switch span {
          font-size: var(--av2-t-meta);
          font-weight: 700;
          line-height: 1.2;
        }
        .av2.notebook-mode-switch em {
          font-size: var(--av2-t-meta);
          font-style: normal;
          font-weight: 400;
          line-height: 1.2;
          color: var(--av2-muted);
        }
        .av2.notebook-mode-switch a.active em {
          color: inherit;
        }
      `}</style>
    </nav>
  )
);

NotebookModeSwitch.displayName = 'NotebookModeSwitch';

export { NotebookModeSwitch, STORAGE_KEY as NOTEBOOK_MODE_STORAGE_KEY };
