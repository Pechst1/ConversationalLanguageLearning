import React, { useCallback, useEffect, useState } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { useRouter } from 'next/router';

import EditorialMasthead from '@/components/layout/EditorialMasthead';
import { NOTEBOOK_MODE_STORAGE_KEY, NotebookModeSwitch, type NotebookMode } from '@/components/mobile';
import { Button } from '@/components/ui/Button';
import { ExerciseShell } from '@/components/ui/ExerciseShell';
import { FeedbackSheet } from '@/components/ui/FeedbackSheet';
import { ProgressBar } from '@/components/ui/ProgressBar';
import { pulseAppHaptic } from '@/lib/haptics';
import { STORY_FEATURE_VISIBLE } from '@/lib/launch-flags';
import api, { type CEFRProgress, type GraphicNovelToday, type LibraryBook, type LibraryEpisode } from '@/services/api';

import { GrammarNotebookSurface } from './grammar';
import VocabularyPage from './vocabulary';

type NotebookQuery = Record<string, string | string[] | undefined>;
type LibraryExerciseKind = 'comprehension' | 'vocabulary' | 'grammar' | 'production';
type LibraryExerciseStep = {
  id: string;
  kind: LibraryExerciseKind;
  eyebrow: string;
  title: string;
  prompt: string;
  target?: string;
  evidence?: string;
  explanation?: string;
  criteria?: string[];
  inputMode: 'line' | 'paragraph';
};
type LibraryExerciseFeedback = {
  status: 'correct' | 'wrong';
  title: string;
  explanation: string;
  repair?: string;
  rule?: string;
};

function firstQueryValue(value: string | string[] | undefined) {
  return Array.isArray(value) ? value[0] : value;
}

function storedNotebookMode(): NotebookMode {
  if (typeof window === 'undefined') return 'grammar';
  try {
    const stored = window.localStorage.getItem(NOTEBOOK_MODE_STORAGE_KEY);
    if (stored === 'vocabulary') return 'vocabulary';
    if (STORY_FEATURE_VISIBLE && stored === 'library') return 'library';
    return 'grammar';
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
  if (STORY_FEATURE_VISIBLE && explicitMode === 'library') return 'library';
  if (STORY_FEATURE_VISIBLE && firstQueryValue(query.book)) return 'library';
  if (firstQueryValue(query.word)) return 'vocabulary';
  if (firstQueryValue(query.concept) || firstQueryValue(query.review)) return 'grammar';
  return null;
}

function notebookModeFromHref(href: string | null): NotebookMode | null {
  if (!href) return null;
  if (STORY_FEATURE_VISIBLE && (href.includes('mode=library') || href.includes('/bibliotheque') || href.includes('/stories'))) return 'library';
  if (href.includes('/vocabulary')) return 'vocabulary';
  if (href.includes('/grammar')) return 'grammar';
  return null;
}

function queryForMode(query: NotebookQuery, requestedMode: NotebookMode): NotebookQuery {
  const mode = !STORY_FEATURE_VISIBLE && requestedMode === 'library' ? 'grammar' : requestedMode;
  const nextQuery: NotebookQuery = { mode };
  const locale = firstQueryValue(query.locale);
  if (locale) nextQuery.locale = locale;

  if (mode === 'grammar') {
    const concept = firstQueryValue(query.concept) || firstQueryValue(query.review);
    if (concept) nextQuery.concept = concept;
  } else {
    if (mode === 'library') {
      const book = firstQueryValue(query.book);
      const episode = firstQueryValue(query.episode);
      if (book) nextQuery.book = book;
      if (episode) nextQuery.episode = episode;
      return nextQuery;
    }
    const word = firstQueryValue(query.word);
    if (word) nextQuery.word = word;
  }

  return nextQuery;
}

export default function NotebookEntryPage() {
  const router = useRouter();
  const [mode, setMode] = useState<NotebookMode>('grammar');
  const [cefr, setCefr] = useState<CEFRProgress | null>(null);
  const [feuilletonToday, setFeuilletonToday] = useState<GraphicNovelToday | null>(null);
  const queryConcept = router.query.concept;
  const queryMode = router.query.mode;
  const queryReview = router.query.review;
  const queryWord = router.query.word;
  const queryBook = router.query.book;
  const queryEpisode = router.query.episode;

  useEffect(() => {
    if (!router.isReady) return;
    const nextMode = notebookModeFromQuery({
      book: queryBook,
      concept: queryConcept,
      episode: queryEpisode,
      mode: queryMode,
      review: queryReview,
      word: queryWord,
    }) || storedNotebookMode();
    setMode(nextMode);
    rememberNotebookMode(nextMode);
  }, [queryBook, queryConcept, queryEpisode, queryMode, queryReview, queryWord, router.isReady]);

  useEffect(() => {
    let cancelled = false;
    api.getCefrProgress()
      .then((payload) => {
        if (!cancelled) setCefr(payload);
      })
      .catch(() => {
        if (!cancelled) setCefr(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    api.getGraphicNovelToday()
      .then((payload) => {
        if (!cancelled) setFeuilletonToday(payload);
      })
      .catch(() => {
        if (!cancelled) setFeuilletonToday(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const switchMode = useCallback(
    (nextMode: NotebookMode) => {
      const resolvedMode = !STORY_FEATURE_VISIBLE && nextMode === 'library' ? 'grammar' : nextMode;
      if (resolvedMode !== mode) pulseAppHaptic('selection');
      setMode(resolvedMode);
      rememberNotebookMode(resolvedMode);
      if (!router.isReady) return;
      void router.push(
        { pathname: '/notebook', query: queryForMode(router.query, resolvedMode) },
        undefined,
        { shallow: true, scroll: false }
      );
    },
    [mode, router]
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

  const visibleMode = !STORY_FEATURE_VISIBLE && mode === 'library' ? 'grammar' : mode;

  return (
    <>
      <Head>
        <title>{`${visibleMode === 'grammar' ? 'Grammar Notebook' : visibleMode === 'vocabulary' ? 'Vocabulary Notebook' : 'Library Notebook'} · Atelier`}</title>
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

          <NotebookProgression cefr={cefr} />
          <NotebookArchiveLead feuilleton={feuilletonToday} />

          <NotebookModeSwitch
            active={visibleMode}
            grammarMeta="Rules and weak spots"
            vocabularyMeta="French 5000"
            libraryMeta={STORY_FEATURE_VISIBLE ? 'Books and episodes' : undefined}
            className="notebook-shell-switch"
            onClickCapture={handleModeSwitchClick}
          />

          <section key={visibleMode} className="notebook-shell-content" data-mode={visibleMode}>
            {visibleMode === 'grammar' ? (
              <GrammarNotebookSurface embedded />
            ) : visibleMode === 'vocabulary' ? (
              <div className="notebook-embedded-vocabulary">
                <VocabularyPage embedded />
              </div>
            ) : (
              <LibraryNotebookSurface
                bookId={firstQueryValue(queryBook)}
                episodeIndex={firstQueryValue(queryEpisode)}
              />
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
        .notebook-progression {
          margin: 18px 0 0;
          border: 2px solid var(--ink);
          background: var(--sheet);
          padding: 16px;
          display: grid;
          grid-template-columns: minmax(190px, .8fr) repeat(3, minmax(0, 1fr));
          gap: 14px;
          align-items: center;
        }
        .notebook-progression span {
          font: 900 10px/1 var(--app-mono, "Inter", "Helvetica Neue", Arial, sans-serif);
          letter-spacing: .13em;
          text-transform: uppercase;
          color: var(--ink-3);
        }
        .notebook-progression strong {
          display: block;
          margin-top: 5px;
          font-size: 24px;
          line-height: 1;
        }
        .notebook-progression small {
          display: block;
          margin-top: 5px;
          color: var(--ink-2);
          line-height: 1.25;
        }
        .progression-row {
          display: grid;
          gap: 6px;
        }
        .progression-row i {
          display: block;
          height: 10px;
          border: 1px solid var(--ink);
          background: var(--paper);
        }
        .progression-row em {
          display: block;
          height: 100%;
          background: #1d3a8a;
        }
        .progression-row b {
          font-size: 12px;
          line-height: 1;
        }
        .notebook-archive-lead {
          margin: 16px 0 18px;
          display: grid;
          grid-template-columns: minmax(0, 1fr) minmax(260px, 380px);
          gap: 12px;
          align-items: stretch;
        }
        .feuilleton-lead-card {
          min-width: 0;
          display: grid;
          grid-template-columns: 86px minmax(0, 1fr) auto;
          gap: 14px;
          align-items: center;
          border: 2px solid var(--ink);
          background: var(--sheet);
          color: var(--ink);
          padding: 12px;
          text-decoration: none;
        }
        .lead-panel-image,
        .lead-imprint {
          width: 86px;
          aspect-ratio: 1;
          border: 1px solid var(--ink);
          background: var(--paper);
        }
        .lead-panel-image {
          display: block;
          background-position: center;
          background-size: cover;
        }
        .lead-imprint {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 7px;
          padding: 12px;
          align-items: end;
        }
        .lead-imprint i {
          display: block;
          border: 1.5px solid var(--ink);
          background: #1d3a8a;
        }
        .lead-imprint i:nth-child(1) {
          height: 48px;
        }
        .lead-imprint i:nth-child(2) {
          height: 64px;
          background: #e3341c;
        }
        .lead-imprint i:nth-child(3) {
          height: 36px;
          background: #f3c318;
        }
        .lead-copy {
          min-width: 0;
          display: grid;
          gap: 5px;
        }
        .lead-copy em,
        .archive-quick-links a {
          font: 900 10px/1 var(--app-mono, "Inter", "Helvetica Neue", Arial, sans-serif);
          letter-spacing: .12em;
          text-transform: uppercase;
        }
        .lead-copy em {
          color: var(--ink-3);
          font-style: normal;
        }
        .lead-copy strong {
          min-width: 0;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
          font-size: 20px;
          line-height: 1.05;
        }
        .lead-copy small {
          color: var(--ink-2);
          line-height: 1.32;
        }
        .feuilleton-lead-card b {
          font-size: 24px;
          line-height: 1;
        }
        .archive-quick-links {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          border: 1px solid var(--ink);
          background: var(--ink);
          gap: 1px;
        }
        .archive-quick-links a {
          min-height: 44px;
          display: grid;
          place-items: center;
          background: var(--sheet);
          color: var(--ink);
          text-decoration: none;
        }
        .notebook-shell-content {
          min-width: 0;
          transform-origin: 50% 0;
        }
        @media (prefers-reduced-motion: no-preference) {
          .notebook-shell-content {
            animation: notebook-page-turn .28s cubic-bezier(.2, .8, .2, 1) both;
          }
          .feuilleton-lead-card,
          .archive-quick-links a,
          .library-book-row {
            transition: transform .16s ease, box-shadow .16s ease, background-color .16s ease;
          }
          .feuilleton-lead-card:hover,
          .archive-quick-links a:hover,
          .library-book-row:hover {
            transform: translate(-2px, -2px);
            box-shadow: 4px 4px 0 var(--ink);
          }
        }
        @keyframes notebook-page-turn {
          from {
            opacity: .62;
            transform: translateY(10px) rotateX(2deg);
          }
          to {
            opacity: 1;
            transform: translateY(0) rotateX(0);
          }
        }
        .notebook-embedded-vocabulary .vocab-page {
          min-height: auto;
          padding: 0;
          background: transparent;
        }
        .library-notebook {
          display: grid;
          gap: 18px;
        }
        .library-grid {
          display: grid;
          grid-template-columns: minmax(260px, 380px) minmax(0, 1fr);
          gap: 22px;
          align-items: start;
        }
        .library-list {
          display: grid;
          gap: 10px;
        }
        .library-book-row {
          display: grid;
          grid-template-columns: 42px 1fr 48px;
          gap: 8px 12px;
          align-items: center;
          border: 1px solid var(--ink);
          background: var(--sheet);
          color: var(--ink);
          padding: 12px;
          text-decoration: none;
        }
        .library-book-row.active {
          box-shadow: 5px 5px 0 var(--ink);
          background: #fffaf0;
        }
        .library-book-row span,
        .library-book-row b {
          font: 900 11px/1 var(--app-mono, "Inter", "Helvetica Neue", Arial, sans-serif);
          letter-spacing: .08em;
          text-transform: uppercase;
        }
        .library-book-row strong,
        .library-book-row em {
          min-width: 0;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        .library-book-row strong {
          font-size: 15px;
        }
        .library-book-row em {
          grid-column: 2 / 4;
          color: var(--ink-3);
          font-size: 12px;
          font-style: normal;
        }
        .library-reader {
          border-left: 4px solid var(--ink);
          padding-left: 20px;
        }
        .library-reader header span,
        .library-exercises h3,
        .library-exercises article span {
          font: 900 10px/1 var(--app-mono, "Inter", "Helvetica Neue", Arial, sans-serif);
          letter-spacing: .13em;
          text-transform: uppercase;
          color: var(--ink-3);
        }
        .library-reader h2 {
          margin: 7px 0 0;
          font-family: var(--app-serif, "EB Garamond", Garamond, serif);
          font-size: clamp(30px, 4vw, 48px);
          font-style: italic;
          line-height: .98;
        }
        .library-reader header p {
          margin: 8px 0 0;
          color: var(--ink-2);
          font-size: 13px;
        }
        .library-passage {
          margin-top: 18px;
          max-width: 72ch;
          color: var(--ink);
          font-family: var(--app-serif, "EB Garamond", Garamond, serif);
          font-size: 20px;
          line-height: 1.5;
        }
        .library-passage p {
          margin: 0 0 14px;
        }
        .library-exercises {
          margin-top: 22px;
          display: grid;
          gap: 10px;
        }
        .library-exercises > div {
          display: grid;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: 10px;
        }
        .library-exercises article {
          border: 1px solid var(--ink);
          background: var(--sheet);
          padding: 12px;
        }
        .library-exercises article p {
          margin: 8px 0 0;
          font-size: 13px;
          line-height: 1.35;
        }
        .library-complete {
          margin-top: 16px;
          min-height: 44px;
          border: 1.5px solid var(--ink);
          background: var(--ink);
          color: var(--sheet);
          padding: 0 16px;
          font: 900 11px/1 var(--app-mono, "Inter", "Helvetica Neue", Arial, sans-serif);
          letter-spacing: .12em;
          text-transform: uppercase;
          cursor: pointer;
        }
        .library-runner {
          margin-top: 24px;
        }
        .library-do-mode {
          background: var(--sheet);
        }
        .library-do-mode :global(.atelier-progress-bar) {
          width: 150px;
        }
        .library-runner-stage {
          display: grid;
          gap: 10px;
        }
        .library-runner-stage > span,
        .library-runner-complete > span {
          font: 900 10px/1 var(--app-mono, "Inter", "Helvetica Neue", Arial, sans-serif);
          letter-spacing: .13em;
          text-transform: uppercase;
          color: var(--ink-3);
        }
        .library-runner-stage p {
          margin: 0;
          color: var(--ink);
          font-size: 18px;
          font-weight: 800;
          line-height: 1.3;
        }
        .library-runner-stage blockquote {
          margin: 0;
          border-left: 4px solid #1d3a8a;
          background: var(--paper);
          padding: 10px 12px;
          color: var(--ink-2);
          font-size: 14px;
          line-height: 1.42;
        }
        .library-runner-stage ul {
          margin: 0;
          padding-left: 18px;
          color: var(--ink-2);
          font-size: 13px;
          line-height: 1.4;
        }
        .library-runner-input,
        .library-runner-textarea {
          width: 100%;
          border: 1px solid var(--ink) !important;
          background: var(--paper);
          padding: 12px 14px;
          box-shadow: 4px 4px 0 var(--ink) !important;
          color: var(--ink);
          outline: none;
        }
        .library-runner-textarea {
          min-height: 110px;
          resize: vertical;
          font-family: var(--app-serif, "EB Garamond", Garamond, serif);
          font-size: 20px;
          line-height: 1.35;
        }
        .library-runner-action {
          display: flex;
          justify-content: flex-end;
        }
        .library-runner-complete {
          border: 1px solid var(--ink);
          background: var(--sheet);
          padding: 16px;
          display: grid;
          gap: 8px;
        }
        .library-runner-complete strong {
          font-size: 22px;
          line-height: 1.05;
        }
        .library-runner-complete p {
          margin: 0;
          color: var(--ink-2);
          line-height: 1.4;
        }
        .library-runner-complete :global(button) {
          justify-self: start;
          margin-top: 4px;
        }
        .library-state,
        .library-empty {
          border: 1px solid var(--ink);
          background: var(--sheet);
          padding: 18px;
        }
        .library-empty h2 {
          margin: 0;
          font-family: var(--app-serif, "EB Garamond", Garamond, serif);
          font-size: 34px;
          font-style: italic;
        }
        .library-empty p {
          margin: 8px 0 14px;
          color: var(--ink-2);
        }
        .library-empty a {
          color: var(--blue, #1d3a8a);
          font-weight: 900;
          text-transform: uppercase;
          text-decoration: none;
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
          .notebook-progression {
            margin: 0 16px 14px;
            grid-template-columns: 1fr;
          }
          .notebook-archive-lead {
            margin: 0 16px 14px;
            grid-template-columns: 1fr;
          }
          .feuilleton-lead-card {
            grid-template-columns: 64px minmax(0, 1fr) auto;
          }
          .lead-panel-image,
          .lead-imprint {
            width: 64px;
          }
          .lead-copy strong {
            white-space: normal;
            font-size: 17px;
          }
          .library-notebook {
            padding: 0 16px;
          }
          .library-grid,
          .library-exercises > div {
            grid-template-columns: 1fr;
          }
          .library-reader {
            border-left: 0;
            padding-left: 0;
          }
          .library-do-mode :global(header) {
            align-items: stretch;
          }
          .library-do-mode :global(.atelier-progress-bar) {
            width: 100%;
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

function NotebookProgression({ cefr }: { cefr: CEFRProgress | null }) {
  if (!cefr) return null;
  const breakdown = cefr.breakdown || {};
  const forecast = cefr.forecast || null;
  const forecastText = forecast?.status === 'available' && Array.isArray(forecast.range_days)
    ? `${forecast.range_days[0]}-${forecast.range_days[1]} days`
    : forecast?.message || 'Forecast unlocks after 7 active days';
  return (
    <section className="notebook-progression">
      <div>
        <span>Progression</span>
        <strong>{cefr.estimate} → {cefr.target}</strong>
        <small>{forecastText}</small>
      </div>
      <ProgressionRow label="Words" metric={breakdown.vocabulary} />
      <ProgressionRow label="Concepts" metric={breakdown.grammar} />
      <ProgressionRow label="Score" metric={breakdown.score} />
    </section>
  );
}

function ProgressionRow({ label, metric }: { label: string; metric: any }) {
  const current = Number(metric?.current || 0);
  const target = Number(metric?.target || 0);
  const pct = target > 0 ? Math.max(0, Math.min(100, Math.round((current / target) * 100))) : 0;
  return (
    <div className="progression-row">
      <span>{label}</span>
      <i><em style={{ width: `${pct}%` }} /></i>
      <b>{current}/{target}</b>
    </div>
  );
}

function NotebookArchiveLead({ feuilleton }: { feuilleton: GraphicNovelToday | null }) {
  const scene = feuilleton?.active_scene || feuilleton?.available_scene || feuilleton?.recent_completed?.[0] || null;
  const panelImage = scene?.panels?.find((panel) => panel.image_url)?.image_url || null;
  const href = scene ? `/graphic-novel?scene=${encodeURIComponent(scene.id)}` : '/graphic-novel';
  const eyebrow = scene?.status === 'completed'
    ? 'Latest Feuilleton'
    : scene?.status === 'in_progress'
      ? 'Feuilleton in progress'
      : 'Today in the serial';

  return (
    <section className="notebook-archive-lead" aria-label="Notebook archive lead">
      <Link className="feuilleton-lead-card" href={href} onClick={() => pulseAppHaptic('selection')}>
        {panelImage ? (
          <span
            className="lead-panel-image"
            style={{ backgroundImage: `url("${panelImage.replace(/"/g, '%22')}")` }}
            aria-hidden="true"
          />
        ) : (
          <span className="lead-imprint" aria-hidden="true">
            <i />
            <i />
            <i />
          </span>
        )}
        <span className="lead-copy">
          <em>{eyebrow}</em>
          <strong>{scene?.title || 'Open the Feuilleton'}</strong>
          <small>{scene?.brief || 'A fresh scene waits beside today’s notes.'}</small>
        </span>
        <b aria-hidden="true">→</b>
      </Link>
      <nav className="archive-quick-links" aria-label="Archive shortcuts">
        <Link href="/serial">Serial archive</Link>
        <Link href="/almanac" onClick={() => pulseAppHaptic('selection')}>Seals</Link>
        <Link href="/missions">Past missions</Link>
        {STORY_FEATURE_VISIBLE && (
          <Link href="/bibliotheque" onClick={() => pulseAppHaptic('selection')}>Uploads</Link>
        )}
      </nav>
    </section>
  );
}

function normalizeLibraryAnswer(value: unknown) {
  return String(value || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[’`]/g, "'")
    .replace(/[.!?;:,«»]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase();
}

function libraryWordCount(value: string) {
  return value.trim().split(/\s+/).filter(Boolean).length;
}

function excerpt(value: unknown, maxLength = 180) {
  const text = String(value || '').replace(/\s+/g, ' ').trim();
  if (text.length <= maxLength) return text;
  return `${text.slice(0, maxLength - 1).trim()}...`;
}

function libraryExerciseSteps(payload: Record<string, any> | null | undefined): LibraryExerciseStep[] {
  const comprehension = Array.isArray(payload?.comprehension) ? payload.comprehension : [];
  const vocabulary = Array.isArray(payload?.vocabulary) ? payload.vocabulary : [];
  const grammar = Array.isArray(payload?.grammar) ? payload.grammar : [];
  const production = payload?.production && typeof payload.production === 'object' ? payload.production : null;
  return [
    ...comprehension.slice(0, 2).map((item: any, index: number): LibraryExerciseStep => ({
      id: `comprehension-${index}`,
      kind: 'comprehension',
      eyebrow: 'Comprehension',
      title: `Find the proof ${index + 1}`,
      prompt: String(item.question || 'Answer from the passage.'),
      target: String(item.answer || ''),
      evidence: String(item.evidence || ''),
      inputMode: 'paragraph',
    })),
    ...vocabulary.slice(0, 2).map((item: any, index: number): LibraryExerciseStep => ({
      id: `vocabulary-${index}`,
      kind: 'vocabulary',
      eyebrow: 'Vocabulary',
      title: String(item.word || `Word ${index + 1}`),
      prompt: `Which passage word fits this cue? ${item.gloss_hint || 'Use the context sentence.'}`,
      target: String(item.word || ''),
      evidence: String(item.context_sentence || ''),
      inputMode: 'line',
    })),
    ...grammar.slice(0, 1).map((item: any, index: number): LibraryExerciseStep => ({
      id: `grammar-${index}`,
      kind: 'grammar',
      eyebrow: 'Grammar in the passage',
      title: String(item.pattern || 'Pattern'),
      prompt: String(item.prompt || 'Find the pattern in the passage.'),
      target: String(item.answer || ''),
      explanation: String(item.explanation || ''),
      inputMode: 'paragraph',
    })),
    ...(production ? [{
      id: 'production-0',
      kind: 'production' as const,
      eyebrow: 'Production',
      title: 'Write from the passage',
      prompt: String(production.prompt || 'Write a short response grounded in the passage.'),
      target: String(production.example_answer || ''),
      criteria: Array.isArray(production.success_criteria) ? production.success_criteria.map((item: any) => String(item || '').trim()).filter(Boolean) : [],
      inputMode: 'paragraph' as const,
    }] : []),
  ];
}

function libraryExerciseFeedback(step: LibraryExerciseStep, answer: string): LibraryExerciseFeedback {
  const normalizedAnswer = normalizeLibraryAnswer(answer);
  const normalizedTarget = normalizeLibraryAnswer(step.target);
  const targetTokens = normalizedTarget.split(' ').filter((token) => token.length > 3);
  const overlap = targetTokens.filter((token) => normalizedAnswer.includes(token)).length;
  const enoughWriting = step.kind === 'production' ? libraryWordCount(answer) >= 8 : libraryWordCount(answer) >= 2;
  const exact = Boolean(normalizedTarget) && normalizedAnswer === normalizedTarget;
  const close = step.kind === 'vocabulary'
    ? exact
    : exact || (enoughWriting && overlap >= Math.min(2, Math.max(1, targetTokens.length)));
  if (close || (step.kind === 'production' && enoughWriting)) {
    return {
      status: 'correct',
      title: step.kind === 'production' ? 'Ready to file' : 'Grounded in the passage',
      explanation: step.kind === 'production'
        ? 'The answer is long enough to carry the episode forward. Keep one detail from the passage visible.'
        : 'Good. The answer connects to the generated passage evidence.',
      rule: step.evidence ? `Evidence: ${excerpt(step.evidence)}` : undefined,
    };
  }
  return {
    status: 'wrong',
    title: 'Use the passage as proof',
    explanation: step.kind === 'vocabulary'
      ? 'Look back at the context sentence and copy the word that matches the cue.'
      : 'Add one concrete detail from the passage before moving on.',
    repair: step.target ? `Target: ${excerpt(step.target)}` : undefined,
    rule: step.evidence ? `Evidence: ${excerpt(step.evidence)}` : step.explanation || undefined,
  };
}

function LibraryNotebookSurface({
  bookId,
  episodeIndex,
}: {
  bookId?: string;
  episodeIndex?: string;
}) {
  const [books, setBooks] = useState<LibraryBook[]>([]);
  const [selectedBook, setSelectedBook] = useState<LibraryBook | null>(null);
  const [episode, setEpisode] = useState<LibraryEpisode | null>(null);
  const [loading, setLoading] = useState(true);
  const [episodeLoading, setEpisodeLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function markEpisodeComplete() {
    if (!selectedBook || !episode) return;
    const updated = await api.completeLibraryEpisode(selectedBook.id, episode.order_index);
    setSelectedBook(updated);
    setBooks((prev) => prev.map((item) => item.id === updated.id ? updated : item));
    setEpisode((prev) => prev ? { ...prev, is_completed: true } : prev);
    pulseAppHaptic('complete');
  }

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    api.getLibraryBooks()
      .then((rows) => {
        if (cancelled) return;
        setBooks(rows || []);
      })
      .catch(() => {
        if (!cancelled) setError('Could not load your library.');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    const fallback = books.find((book) => book.status === 'ready') || books[0] || null;
    const targetId = bookId || fallback?.id;
    if (!targetId) {
      setSelectedBook(null);
      setEpisode(null);
      return;
    }
    setEpisodeLoading(true);
    api.getLibraryBook(targetId)
      .then((book) => {
        if (cancelled) return;
        setSelectedBook(book);
        const requested = Number(episodeIndex);
        const index = Number.isFinite(requested)
          ? requested
          : Number(book.current_episode_index || 0);
        return api.getLibraryEpisode(book.id, Math.max(0, index));
      })
      .then((payload) => {
        if (!cancelled && payload) setEpisode(payload);
      })
      .catch(() => {
        if (!cancelled) setEpisode(null);
      })
      .finally(() => {
        if (!cancelled) setEpisodeLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [bookId, books, episodeIndex]);

  return (
    <div className="library-notebook">
      {error && <div className="library-state">{error}</div>}
      {loading && <div className="library-state">Loading library</div>}

      {!loading && !books.length && (
        <section className="library-empty">
          <h2>Library</h2>
          <p>Your uploaded books will appear here as reading episodes.</p>
          <Link href="/bibliotheque">Open uploads</Link>
        </section>
      )}

      {!!books.length && (
        <div className="library-grid">
          <section className="library-list" aria-label="Uploaded books">
            {books.map((book) => (
              <Link
                key={book.id}
                className={`library-book-row ${selectedBook?.id === book.id ? 'active' : ''}`}
                href={`/notebook?mode=library&book=${book.id}&episode=${book.current_episode_index || 0}`}
                onClick={() => pulseAppHaptic('selection')}
              >
                <span>{book.target_level}</span>
                <strong>{book.title}</strong>
                <em>{book.author || book.source_filename || 'Uploaded text'}</em>
                <b>{book.completion_percentage}%</b>
              </Link>
            ))}
          </section>

          <section className="library-reader" aria-label="Selected reading episode">
            {episodeLoading && <div className="library-state">Loading episode</div>}
            {!episodeLoading && selectedBook && episode && (
              <>
                <header>
                  <span>{selectedBook.title}</span>
                  <h2>{episode.title}</h2>
                  <p>Episode {episode.order_index + 1} of {selectedBook.total_episodes || 1} · {episode.est_reading_minutes} min · {episode.word_count} words</p>
                </header>
                <article className="library-passage">
                  {(episode.passage_text || '').split(/\n{2,}/).filter(Boolean).slice(0, 8).map((paragraph, index) => (
                    <p key={`${episode.id}-${index}`}>{paragraph}</p>
                  ))}
                </article>
                <LibraryExercisePreview payload={episode.exercise_payload} />
                <LibraryEpisodeExerciseRunner
                  episode={episode}
                  completed={episode.is_completed}
                  onComplete={markEpisodeComplete}
                />
              </>
            )}
          </section>
        </div>
      )}
    </div>
  );
}

function LibraryEpisodeExerciseRunner({
  episode,
  completed,
  onComplete,
}: {
  episode: LibraryEpisode;
  completed: boolean;
  onComplete: () => Promise<void>;
}) {
  const steps = libraryExerciseSteps(episode.exercise_payload);
  const [stepIndex, setStepIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [feedback, setFeedback] = useState<LibraryExerciseFeedback | null>(null);
  const [finishing, setFinishing] = useState(false);
  const activeStep = steps[Math.min(stepIndex, Math.max(0, steps.length - 1))];
  const answer = activeStep ? answers[activeStep.id] || '' : '';
  const allChecked = stepIndex >= steps.length;

  useEffect(() => {
    setStepIndex(0);
    setAnswers({});
    setFeedback(null);
  }, [episode.id]);

  if (!steps.length) return null;
  if (!activeStep) return null;

  async function finishEpisode() {
    setFinishing(true);
    try {
      await onComplete();
    } finally {
      setFinishing(false);
    }
  }

  if (completed) {
    return (
      <section className="library-runner library-runner-complete" aria-label="Episode exercises complete">
        <span>Exercises filed</span>
        <strong>Episode {episode.order_index + 1} is complete.</strong>
        <p>The passage, vocabulary, and production prompt are saved in your library progress.</p>
      </section>
    );
  }

  if (allChecked) {
    return (
      <section className="library-runner library-runner-complete" aria-label="Episode ready to complete">
        <span>Feedback moment</span>
        <strong>Ready to continue {episode.title}</strong>
        <p>You read the passage, checked the generated prompts, and wrote from the episode.</p>
        <Button loading={finishing} rightIcon={<span aria-hidden="true">→</span>} onClick={finishEpisode}>
          Complete episode
        </Button>
      </section>
    );
  }

  function checkAnswer() {
    if (!activeStep || !answer.trim()) return;
    const nextFeedback = libraryExerciseFeedback(activeStep, answer);
    setFeedback(nextFeedback);
    pulseAppHaptic(nextFeedback.status === 'correct' ? 'correct' : 'repair');
  }

  function nextStep() {
    pulseAppHaptic('selection');
    setFeedback(null);
    setStepIndex((current) => current + 1);
  }

  return (
    <ExerciseShell
      className="library-runner library-do-mode"
      eyebrow={`Episode exercise ${stepIndex + 1} of ${steps.length}`}
      title={activeStep.title}
      action={<ProgressBar value={stepIndex} max={steps.length} label="Episode exercise progress" />}
    >
      <div className="library-runner-stage">
        <span>{activeStep.eyebrow}</span>
        <p>{activeStep.prompt}</p>
        {activeStep.evidence && <blockquote>{excerpt(activeStep.evidence, 260)}</blockquote>}
        {!!activeStep.criteria?.length && (
          <ul>
            {activeStep.criteria.slice(0, 4).map((item) => <li key={item}>{item}</li>)}
          </ul>
        )}
      </div>
      {activeStep.inputMode === 'line' ? (
        <input
          className="library-runner-input"
          value={answer}
          onChange={(event) => {
            setAnswers((current) => ({ ...current, [activeStep.id]: event.target.value }));
            setFeedback(null);
          }}
          placeholder="Answer from the passage"
        />
      ) : (
        <textarea
          className="library-runner-textarea"
          value={answer}
          onChange={(event) => {
            setAnswers((current) => ({ ...current, [activeStep.id]: event.target.value }));
            setFeedback(null);
          }}
          placeholder="Write your answer in French"
        />
      )}
      {feedback && (
        <FeedbackSheet
          status={feedback.status}
          title={feedback.title}
          explanation={feedback.explanation}
          repair={feedback.repair}
          rule={feedback.rule}
          onTryAgain={feedback.status === 'wrong' ? () => setFeedback(null) : undefined}
          onNext={nextStep}
        />
      )}
      {!feedback && (
        <div className="library-runner-action">
          <Button disabled={!answer.trim()} onClick={checkAnswer}>
            Check
          </Button>
        </div>
      )}
    </ExerciseShell>
  );
}

function LibraryExercisePreview({ payload }: { payload: Record<string, any> }) {
  const comprehension = Array.isArray(payload?.comprehension) ? payload.comprehension.slice(0, 2) : [];
  const vocabulary = Array.isArray(payload?.vocabulary) ? payload.vocabulary.slice(0, 5) : [];
  const production = payload?.production || null;
  return (
    <section className="library-exercises" aria-label="Episode exercises">
      <h3>Episode prompts</h3>
      <div>
        {comprehension.map((item: any, index: number) => (
          <article key={`comp-${index}`}>
            <span>Comprehension</span>
            <p>{item.question}</p>
          </article>
        ))}
        {!!vocabulary.length && (
          <article>
            <span>Vocabulary</span>
            <p>{vocabulary.map((item: any) => item.word).filter(Boolean).join(', ')}</p>
          </article>
        )}
        {production?.prompt && (
          <article>
            <span>Production</span>
            <p>{production.prompt}</p>
          </article>
        )}
      </div>
    </section>
  );
}
