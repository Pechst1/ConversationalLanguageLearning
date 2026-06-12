import React, { useCallback, useEffect, useState } from 'react';
import Head from 'next/head';
import { useRouter } from 'next/router';

import EditorialMasthead from '@/components/layout/EditorialMasthead';
import { NOTEBOOK_MODE_STORAGE_KEY, NotebookModeSwitch, type NotebookMode } from '@/components/mobile';

import { GrammarNotebookSurface } from './grammar';
import VocabularyPage from './vocabulary';

type NotebookQuery = Record<string, string | string[] | undefined>;

function firstQueryValue(value: string | string[] | undefined) {
  return Array.isArray(value) ? value[0] : value;
}

function storedNotebookMode(): NotebookMode {
  if (typeof window === 'undefined') return 'grammar';
  try {
    return window.localStorage.getItem(NOTEBOOK_MODE_STORAGE_KEY) === 'vocabulary' ? 'vocabulary' : 'grammar';
  } catch {
    return 'grammar';
  }
}

function rememberNotebookMode(mode: NotebookMode) {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(NOTEBOOK_MODE_STORAGE_KEY, mode);
  } catch {
    // Persisting the mode is a convenience; the notebook still works without it.
  }
}

function notebookModeFromQuery(query: NotebookQuery): NotebookMode | null {
  const explicitMode = firstQueryValue(query.mode);
  if (explicitMode === 'grammar' || explicitMode === 'vocabulary') return explicitMode;
  if (firstQueryValue(query.word)) return 'vocabulary';
  if (firstQueryValue(query.concept) || firstQueryValue(query.review)) return 'grammar';
  return null;
}

function notebookModeFromHref(href: string | null): NotebookMode | null {
  if (!href) return null;
  if (href.includes('/vocabulary')) return 'vocabulary';
  if (href.includes('/grammar')) return 'grammar';
  return null;
}

function queryForMode(query: NotebookQuery, mode: NotebookMode): NotebookQuery {
  const nextQuery: NotebookQuery = { mode };
  const locale = firstQueryValue(query.locale);
  if (locale) nextQuery.locale = locale;

  if (mode === 'grammar') {
    const concept = firstQueryValue(query.concept) || firstQueryValue(query.review);
    if (concept) nextQuery.concept = concept;
  } else {
    const word = firstQueryValue(query.word);
    if (word) nextQuery.word = word;
  }

  return nextQuery;
}

export default function NotebookEntryPage() {
  const router = useRouter();
  const [mode, setMode] = useState<NotebookMode>('grammar');
  const queryConcept = router.query.concept;
  const queryMode = router.query.mode;
  const queryReview = router.query.review;
  const queryWord = router.query.word;

  useEffect(() => {
    if (!router.isReady) return;
    const nextMode = notebookModeFromQuery({
      concept: queryConcept,
      mode: queryMode,
      review: queryReview,
      word: queryWord,
    }) || storedNotebookMode();
    setMode(nextMode);
    rememberNotebookMode(nextMode);
  }, [queryConcept, queryMode, queryReview, queryWord, router.isReady]);

  const switchMode = useCallback(
    (nextMode: NotebookMode) => {
      setMode(nextMode);
      rememberNotebookMode(nextMode);
      if (!router.isReady) return;
      void router.push(
        { pathname: '/notebook', query: queryForMode(router.query, nextMode) },
        undefined,
        { shallow: true, scroll: false }
      );
    },
    [router]
  );

  const handleModeSwitchClick = useCallback(
    (event: React.MouseEvent<HTMLElement>) => {
      const target = event.target instanceof Element ? event.target : null;
      const anchor = target?.closest('a[href]');
      const nextMode = notebookModeFromHref(anchor?.getAttribute('href') || null);
      if (!nextMode) return;
      event.preventDefault();
      switchMode(nextMode);
    },
    [switchMode]
  );

  return (
    <>
      <Head>
        <title>{`${mode === 'grammar' ? 'Grammar Notebook' : 'Vocabulary Notebook'} · Atelier`}</title>
      </Head>
      <EditorialMasthead active="notebook" />
      <div className="notebook-shell-page">
        <div className="notebook-shell-spread">
          <header className="notebook-shell-title">
            <div>
              <div className="notebook-shell-eyebrow">Reference Layer</div>
              <h1>Notebook</h1>
            </div>
          </header>

          <NotebookModeSwitch
            active={mode}
            grammarMeta="Rules and weak spots"
            vocabularyMeta="French 5000"
            className="notebook-shell-switch"
            onClickCapture={handleModeSwitchClick}
          />

          <section className="notebook-shell-content" data-mode={mode}>
            {mode === 'grammar' ? (
              <GrammarNotebookSurface embedded />
            ) : (
              <div className="notebook-embedded-vocabulary">
                <VocabularyPage embedded />
              </div>
            )}
          </section>
        </div>
      </div>
      <style jsx global>{`
        .notebook-shell-page {
          --paper: #f1ece1;
          --sheet: #f8f3e8;
          --ink: #14110d;
          --ink-2: #4a4538;
          --ink-3: #8a826f;
          min-height: 100vh;
          background: var(--paper);
          color: var(--ink);
        }
        .notebook-shell-spread {
          box-sizing: border-box;
          width: min(1320px, 100%);
          margin: 0 auto;
          padding: 28px clamp(22px, 4vw, 48px) 124px;
        }
        .notebook-shell-title {
          display: flex;
          align-items: end;
          justify-content: space-between;
          gap: 24px;
          border-bottom: 4px solid var(--ink);
          padding-bottom: 20px;
        }
        .notebook-shell-eyebrow {
          color: var(--ink-2);
          font: 900 11px/1 var(--app-mono, "Inter", "Helvetica Neue", Arial, sans-serif);
          letter-spacing: .13em;
          text-transform: uppercase;
        }
        .notebook-shell-title h1 {
          margin: 8px 0 0;
          font-family: var(--app-serif, "EB Garamond", Garamond, serif);
          font-size: clamp(42px, 8vw, 74px);
          font-style: italic;
          font-weight: 700;
          letter-spacing: 0;
          line-height: .92;
        }
        .notebook-shell-switch {
          margin: 18px 0 24px;
        }
        .notebook-shell-content {
          min-width: 0;
        }
        .notebook-embedded-vocabulary .vocab-page {
          min-height: auto;
          padding: 0;
          background: transparent;
        }
        @media (max-width: 640px) {
          .notebook-shell-spread {
            padding: 16px 0 calc(134px + env(safe-area-inset-bottom));
          }
          .notebook-shell-title {
            border-bottom: 0;
            padding: 0 16px 12px;
          }
          .notebook-shell-title h1 {
            font-size: 38px;
          }
          .notebook-shell-switch {
            width: calc(100% - 32px);
            max-width: calc(100% - 32px);
            margin: 0 16px 14px;
          }
          .notebook-shell-page .notebook-mode-switch.notebook-shell-switch {
            width: calc(100% - 32px);
            max-width: calc(100% - 32px);
            margin: 0 16px 14px;
          }
        }
      `}</style>
    </>
  );
}
