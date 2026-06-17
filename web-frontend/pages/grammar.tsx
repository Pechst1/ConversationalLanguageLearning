import React, { useCallback, useEffect, useMemo, useState } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { useRouter } from 'next/router';
import useSWR from 'swr';
import { AlertCircle, ArrowRight, Loader2, Save, Search, StickyNote, X } from 'lucide-react';
import toast from 'react-hot-toast';

import EditorialMasthead from '@/components/layout/EditorialMasthead';
import { ConceptMotif } from '@/components/grammar/ConceptMotif';
import { NOTEBOOK_MODE_STORAGE_KEY, NotebookModeSwitch, RedInkRepairSlip, type NotebookMode } from '@/components/mobile';
import api, { AtelierErratum, GrammarNotebookDetail, GrammarNotebookItem } from '@/services/api';

const levels = ['all', 'A1', 'A2', 'B1', 'B2', 'C1', 'C2'];
const notebookMobileQuery = '(max-width: 640px)';

type GrammarNotebookSurfaceProps = {
  embedded?: boolean;
};

function isNotebookMobileViewport() {
  return typeof window !== 'undefined' && window.matchMedia(notebookMobileQuery).matches;
}

function firstQueryValue(value: string | string[] | undefined) {
  return Array.isArray(value) ? value[0] : value;
}

function rememberNotebookMode(mode: NotebookMode) {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(NOTEBOOK_MODE_STORAGE_KEY, mode);
  } catch {
    // Mode memory is only a convenience; route changes should still work.
  }
}

function notebookModeFromHref(href: string | null): NotebookMode | null {
  if (!href) return null;
  if (href.includes('/vocabulary')) return 'vocabulary';
  if (href.includes('/grammar')) return 'grammar';
  return null;
}

export default function GrammarNotebookPage() {
  return <GrammarNotebookSurface />;
}

export function GrammarNotebookSurface({ embedded = false }: GrammarNotebookSurfaceProps) {
  const router = useRouter();
  const [level, setLevel] = useState('all');
  const [query, setQuery] = useState('');
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [draftNotes, setDraftNotes] = useState('');
  const [savingNotes, setSavingNotes] = useState(false);
  const locale = typeof router.query.locale === 'string' ? router.query.locale : 'en';

  const notebookParams = useMemo(
    () => ({
      limit: 500,
      level: level === 'all' ? undefined : level,
      q: query.trim() || undefined,
      locale,
    }),
    [level, query, locale]
  );

  const {
    data: concepts = [],
    error: notebookError,
    isLoading,
    mutate: mutateNotebook,
  } = useSWR<GrammarNotebookItem[]>(
    ['/grammar/notebook', notebookParams],
    async () => api.getGrammarNotebook(notebookParams)
  );

  useEffect(() => {
    if (!concepts.length) {
      setSelectedId(null);
      return;
    }
    const rawQueryConcept = firstQueryValue(router.query.concept) || firstQueryValue(router.query.review);
    const queryConceptId = Number(rawQueryConcept);
    if (Number.isFinite(queryConceptId) && concepts.some((concept) => concept.id === queryConceptId)) {
      if (selectedId !== queryConceptId) setSelectedId(queryConceptId);
      return;
    }
    if (isNotebookMobileViewport()) {
      if (selectedId !== null) setSelectedId(null);
      return;
    }
    if (!selectedId || !concepts.some((concept) => concept.id === selectedId)) {
      const firstId = concepts[0].id;
      setSelectedId(firstId);
    }
  }, [concepts, router.query.concept, router.query.review, selectedId]);

  function selectConcept(conceptId: number) {
    if (selectedId === conceptId && isNotebookMobileViewport()) {
      const nextQuery: Record<string, string | string[] | undefined> = { ...router.query };
      delete nextQuery.concept;
      delete nextQuery.review;
      setSelectedId(null);
      router.replace({ pathname: router.pathname, query: nextQuery }, undefined, { shallow: true });
      return;
    }

    setSelectedId(conceptId);
    const nextQuery: Record<string, string | string[] | undefined> = { ...router.query, concept: String(conceptId) };
    delete nextQuery.review;
    router.replace({ pathname: router.pathname, query: nextQuery }, undefined, { shallow: true });
  }

  const {
    data: selected,
    error: selectedError,
    isLoading: detailLoading,
    mutate: mutateSelected,
  } = useSWR<GrammarNotebookDetail | null>(
    selectedId ? ['/grammar/notebook/detail', selectedId, locale] : null,
    async () => (selectedId ? api.getGrammarNotebookConcept(selectedId, { locale }) : null)
  );

  useEffect(() => {
    setDraftNotes(selected?.personal_notes || '');
  }, [selected?.id, selected?.personal_notes]);

  const totals = useMemo(() => {
    return concepts.reduce(
      (acc, concept) => {
        acc.due += concept.due_errata_count || 0;
        acc.recent += concept.recent_errata_count || 0;
        if ((concept.mastery || 0) > 0) acc.started += 1;
        return acc;
      },
      { due: 0, recent: 0, started: 0 }
    );
  }, [concepts]);
  const activeSearch = query.trim();
  const hasActiveFilters = level !== 'all' || activeSearch.length > 0;

  function clearFilters() {
    setLevel('all');
    setQuery('');
  }

  async function saveNotes() {
    if (!selected) return;
    setSavingNotes(true);
    try {
      const updated = await api.updateGrammarNotebookNotes(selected.id, { notes: draftNotes });
      await mutateSelected(updated, false);
      await mutateNotebook();
      toast.success('Notes saved.');
    } catch (error) {
      toast.error('Notes could not be saved.');
    } finally {
      setSavingNotes(false);
    }
  }

  const handleNotebookModeSwitch = useCallback(
    (event: React.MouseEvent<HTMLElement>) => {
      const target = event.target instanceof Element ? event.target : null;
      const anchor = target?.closest('a[href]');
      const mode = notebookModeFromHref(anchor?.getAttribute('href') || null);
      if (!mode) return;

      event.preventDefault();
      rememberNotebookMode(mode);

      const nextQuery: Record<string, string | string[] | undefined> = { mode };
      if (mode === 'grammar') {
        const concept = firstQueryValue(router.query.concept) || firstQueryValue(router.query.review);
        if (concept) nextQuery.concept = concept;
      }
      void router.push({ pathname: '/notebook', query: nextQuery });
    },
    [router]
  );

  const pageContent = (
    <>
      {!embedded && (
        <EditorialMasthead
          active="notebook"
          mobileAction={<Link className="notebook-mobile-action" href="/notebook?mode=vocabulary">Words</Link>}
        />
      )}

      <div className="notebook-spread py-8">
        {!embedded && (
          <header className="notebook-title mb-7">
            <div>
              <div className="notebook-eyebrow">Reference Layer</div>
              <h1>Grammar Notebook</h1>
            </div>
            <Link className="notebook-practice" href="/atelier">
              Back to Atelier <ArrowRight className="h-4 w-4" />
            </Link>
          </header>
        )}
        {!embedded && (
          <NotebookModeSwitch
            active="grammar"
            grammarMeta={`${concepts.length || 0} concepts`}
            vocabularyMeta="French 5000"
            className="notebook-mode-inline"
            onClickCapture={handleNotebookModeSwitch}
          />
        )}

        <section className="notebook-stats mb-7 grid gap-5 md:grid-cols-4">
          <NotebookStat label="Concepts" value={concepts.length} />
          <NotebookStat label="Started" value={totals.started} />
          <NotebookStat label="Due Errata" value={totals.due} accent="red" />
          <NotebookStat label="Recent Errata" value={totals.recent} accent="blue" />
        </section>

        <section className="notebook-shell grid gap-6 lg:grid-cols-[390px_minmax(0,1fr)]">
          <aside className="notebook-index h-fit border-2 border-black bg-[#f7f1e6]">
            <div className="notebook-controls border-b-2 border-black p-4">
              <div className="notebook-search mb-4 flex items-center gap-3 border-2 border-black bg-[#eee7da] px-3 py-2">
                <Search className="h-4 w-4 shrink-0" />
                <input
                  type="search"
                  aria-label="Search notebook concepts"
                  autoComplete="off"
                  className="min-w-0 flex-1 border-0 bg-transparent p-0 text-sm outline-none focus:translate-x-0 focus:translate-y-0"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Search rules, traps, IDs"
                />
                {activeSearch && (
                  <button
                    type="button"
                    className="notebook-search-clear"
                    onClick={() => setQuery('')}
                    aria-label="Clear search"
                  >
                    <X className="h-4 w-4" />
                  </button>
                )}
              </div>
              <div className="notebook-levels flex flex-wrap gap-2">
                {levels.map((item) => (
                  <button
                    key={item}
                    type="button"
                    onClick={() => setLevel(item)}
                    aria-pressed={level === item}
                    className={`border-2 border-black px-3 py-2 text-xs font-black uppercase tracking-[0.12em] ${
                      level === item ? 'bg-black text-white' : 'bg-[#f7f1e6]'
                    }`}
                  >
                    {item === 'all' ? 'All' : item}
                  </button>
                ))}
              </div>
              <div className="notebook-filter-summary" aria-live="polite">
                <span>{isLoading ? 'Searching notebook' : `${concepts.length} ${concepts.length === 1 ? 'concept' : 'concepts'}`}</span>
                {hasActiveFilters && (
                  <button type="button" onClick={clearFilters}>
                    Clear filters
                  </button>
                )}
              </div>
            </div>

            <div className="notebook-list max-h-[calc(100vh-250px)] overflow-y-auto">
              {notebookError ? (
                <ErrorBlock
                  title="Could not load notebook"
                  body="We could not sync your concepts. Check the connection and try again."
                  actionLabel="Retry"
                  onAction={() => mutateNotebook()}
                />
              ) : isLoading ? (
                <LoadingBlock label="Loading notebook" />
              ) : concepts.length ? (
                concepts.map((concept) => {
                  const active = concept.id === selectedId;
                  return (
                    <React.Fragment key={concept.id}>
                      <ConceptIndexRow
                        concept={concept}
                        active={active}
                        onSelect={() => selectConcept(concept.id)}
                      />
                      {active && (
                        <div className="notebook-mobile-detail">
                          {selectedError ? (
                            <ErrorBlock
                              title="Concept offline"
                              body="This concept detail could not be loaded. Your list is still available."
                              actionLabel="Retry detail"
                              onAction={() => mutateSelected()}
                            />
                          ) : detailLoading || !selected ? (
                            <div className="notebook-detail-loading border-2 border-black bg-[#f7f1e6] p-5">
                              <Loader2 className="mb-3 h-5 w-5 animate-spin" />
                              <div className="text-xs font-black uppercase tracking-[0.16em]">Loading concept</div>
                              <div className="notebook-mobile-loading-list" aria-hidden="true">
                                <span />
                                <span />
                                <span />
                              </div>
                            </div>
                          ) : (
                            <ConceptNotebookDetail
                              concept={selected}
                              draftNotes={draftNotes}
                              onNotesChange={setDraftNotes}
                              onSaveNotes={saveNotes}
                              savingNotes={savingNotes}
                            />
                          )}
                        </div>
                      )}
                    </React.Fragment>
                  );
                })
              ) : (
                <EmptyBlock
                  title="No concepts found"
                  body="Try another level or search term."
                  action={
                    hasActiveFilters ? (
                      <button type="button" className="notebook-empty-clear hidden" onClick={clearFilters}>
                        Clear filters
                      </button>
                    ) : undefined
                  }
                />
              )}
            </div>
          </aside>

          <section className="notebook-desktop-detail min-w-0">
            {detailLoading || (selectedId && !selected) ? (
              <div className="border-2 border-black bg-[#f7f1e6] p-8">
                <Loader2 className="mb-3 h-5 w-5 animate-spin" />
                <div className="text-xs font-black uppercase tracking-[0.16em]">Loading concept</div>
              </div>
            ) : selected ? (
              <ConceptNotebookDetail
                concept={selected}
                draftNotes={draftNotes}
                onNotesChange={setDraftNotes}
                onSaveNotes={saveNotes}
                savingNotes={savingNotes}
              />
            ) : (
              <EmptyBlock title="No concept selected" body="The notebook is empty for this filter." />
            )}
          </section>
        </section>
      </div>
    </>
  );

  return (
    <>
      {!embedded && (
        <Head>
          <title>Grammar Notebook · Atelier</title>
        </Head>
      )}
      <NotebookStyles />
      {embedded ? (
        <div className="notebook-page notebook-page-embedded min-h-screen bg-[#f1ece1] text-[#14110d]">{pageContent}</div>
      ) : (
        <main className="notebook-page min-h-screen bg-[#f1ece1] text-[#14110d]">{pageContent}</main>
      )}
    </>
  );
}

function NotebookStyles() {
  return (
    <style jsx global>{`
      .notebook-page {
        --paper: #f1ece1;
        --paper-2: #e8e0cf;
        --paper-3: #d8cdb6;
        --sheet: #f8f3e8;
        --ink: #14110d;
        --ink-2: #4a4538;
        --ink-3: #8a826f;
        --red: #d8321a;
        --blue: #1d3a8a;
        --yellow: #f3c318;
        --serif: "EB Garamond", Garamond, "Times New Roman", serif;
        --grotesk: "Inter", "Helvetica Neue", Arial, sans-serif;
        font-family: var(--grotesk);
      }
      .notebook-page * { box-sizing: border-box; }
      .notebook-page-embedded {
        min-height: auto;
        background: transparent;
      }
      .notebook-spread {
        box-sizing: border-box;
        width: min(1320px, 100%);
        margin: 0 auto;
        padding-left: clamp(22px, 4vw, 48px);
        padding-right: clamp(22px, 4vw, 48px);
      }
      .notebook-page-embedded .notebook-spread {
        width: 100%;
        padding: 0;
      }
      .notebook-mobile-detail { display: none; }
      .notebook-mobile-practice-cta,
      .notebook-row-chevron {
        display: none;
      }
      .notebook-masthead { border-bottom: 1px solid var(--ink); }
      .notebook-masthead-inner {
        min-height: 58px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 24px;
      }
      .notebook-brand {
        display: inline-flex;
        align-items: center;
        gap: 12px;
        color: var(--ink);
        text-decoration: none;
        font-size: 22px;
        font-weight: 900;
        letter-spacing: -0.03em;
      }
      .notebook-nav {
        display: flex;
        align-items: center;
        gap: 20px;
      }
      .notebook-nav a,
      .notebook-eyebrow,
      .notebook-practice {
        font-size: 10px;
        letter-spacing: 0.13em;
        text-transform: uppercase;
        font-weight: 900;
        text-decoration: none;
      }
      .notebook-nav a {
        color: var(--ink-3);
        border-bottom: 2px solid transparent;
        padding-bottom: 3px;
      }
      .notebook-nav a.active,
      .notebook-nav a:hover {
        color: var(--ink);
        border-color: var(--ink);
      }
      .notebook-title {
        display: flex;
        align-items: end;
        justify-content: space-between;
        gap: 24px;
        border-bottom: 4px solid var(--ink);
        padding-bottom: 20px;
      }
      .notebook-mode-inline {
        margin: -12px 0 24px;
      }
      .notebook-title h1 {
        margin: 8px 0 0;
        font-family: var(--serif);
        font-size: clamp(30px, 4.2vw, 46px);
        line-height: 1;
        letter-spacing: 0;
        font-style: italic;
        font-weight: 700;
      }
      .notebook-eyebrow { color: var(--ink-2); }
      .notebook-practice {
        min-height: 42px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 9px;
        padding: 0 18px;
        border: 1px solid var(--ink);
        background: var(--ink);
        color: var(--paper);
      }
      .notebook-practice:hover {
        background: var(--blue);
        border-color: var(--blue);
      }
      .notebook-mobile-action {
        display: inline-grid;
        min-width: 58px;
        height: 58px;
        place-items: center;
        border: 1px solid var(--ink);
        color: var(--ink);
        text-decoration: none;
        font-size: 12px;
        font-weight: 900;
        text-transform: uppercase;
      }
      @media (max-width: 760px) {
        .notebook-masthead-inner,
        .notebook-title {
          align-items: flex-start;
          flex-direction: column;
        }
        .notebook-nav { flex-wrap: wrap; }
        .notebook-practice { width: 100%; }
      }
      @media (max-width: 640px) {
        .notebook-page {
          overflow-x: hidden;
        }
        .notebook-spread {
          padding: 0 0 calc(134px + env(safe-area-inset-bottom));
        }
        .notebook-masthead-inner,
        .notebook-title {
          align-items: flex-start;
          flex-direction: column;
        }
        .notebook-title {
          gap: 12px;
          margin: 0;
          border-bottom: 0;
          padding: 16px 16px 0;
        }
        .notebook-mode-inline {
          width: calc(100% - 32px);
          margin: 0 16px 14px;
        }
        .notebook-title h1 {
          margin-top: 4px;
          font-size: 34px;
          line-height: 0.95;
        }
        .notebook-eyebrow,
        .notebook-practice {
          letter-spacing: 0.1em;
        }
        .notebook-nav { flex-wrap: wrap; }
        .notebook-practice {
          display: none;
        }
        .notebook-stats {
          display: grid;
          grid-template-columns: repeat(3, minmax(92px, 1fr));
          gap: 18px;
          margin: 0;
          overflow-x: auto;
          overscroll-behavior-x: contain;
          border-bottom: 1px solid var(--ink);
          padding: 12px 16px 14px;
          scrollbar-width: none;
        }
        .notebook-stat:nth-child(4) {
          display: none;
        }
        .notebook-stats::-webkit-scrollbar { display: none; }
        .notebook-stat {
          min-width: 92px;
          border-top-width: 1px;
          padding-top: 7px;
        }
        .notebook-stat-value {
          font-size: 25px;
          line-height: 1;
        }
        .notebook-stat-label {
          margin-top: 4px;
          font-size: 9px;
          letter-spacing: 0.1em;
          line-height: 1.2;
        }
        .notebook-shell {
          display: block;
        }
        .notebook-index {
          border: 0;
          background: transparent;
        }
        .notebook-controls {
          position: sticky;
          top: 0;
          z-index: 5;
          border-bottom-width: 1px;
          background: var(--paper);
          padding: 10px 16px 12px;
          box-shadow: 0 8px 18px rgba(20, 17, 13, 0.08);
        }
        .notebook-search {
          margin-bottom: 9px;
          border-width: 1px;
          min-height: 44px;
          padding: 6px 10px;
          transition: border-color .16s ease, background .16s ease, box-shadow .16s ease;
        }
        .notebook-search:focus-within {
          border-color: var(--blue);
          background: #fbf6ea;
          box-shadow: inset 3px 0 0 var(--blue);
        }
        .notebook-search input {
          min-height: 30px;
          font-size: 16px;
        }
        .notebook-search-clear {
          display: inline-flex;
          width: 30px;
          height: 30px;
          flex: 0 0 auto;
          align-items: center;
          justify-content: center;
          border: 1px solid var(--ink);
          background: var(--paper);
          color: var(--ink);
        }
        .notebook-levels {
          flex-wrap: nowrap;
          margin: 0 -16px;
          overflow-x: auto;
          padding: 0 16px 2px;
          scrollbar-width: none;
        }
        .notebook-levels::-webkit-scrollbar { display: none; }
        .notebook-levels button {
          flex: 0 0 auto;
          min-height: 36px;
          border-width: 1px;
          padding: 0 13px;
          border-radius: 0;
          letter-spacing: 0;
          text-transform: none;
        }
        .notebook-filter-summary {
          display: flex;
          min-height: 28px;
          align-items: center;
          justify-content: space-between;
          gap: 10px;
          padding-top: 8px;
          font-size: 11px;
          font-weight: 900;
          letter-spacing: 0;
          text-transform: none;
          color: var(--ink-2);
        }
        .notebook-filter-summary button,
        .notebook-empty-clear {
          min-height: 30px;
          border: 1px solid var(--ink);
          background: transparent;
          padding: 0 10px;
          color: var(--ink);
          font-size: 11px;
          font-weight: 900;
          letter-spacing: 0;
          text-transform: none;
        }
        .notebook-filter-summary button {
          flex: 0 0 auto;
        }
        .notebook-empty-clear {
          display: inline-flex !important;
          align-items: center;
          justify-content: center;
        }
        .notebook-list {
          max-height: none;
          overflow: visible;
          padding-bottom: 18px;
        }
        .notebook-loading-block {
          border-bottom: 1px solid var(--ink);
          background: #fbf6ea;
          margin: 0 16px;
          padding: 14px;
        }
        .notebook-list-skeleton,
        .notebook-mobile-loading-list {
          display: grid;
          gap: 8px;
          margin-top: 14px;
        }
        .notebook-list-skeleton span,
        .notebook-mobile-loading-list span {
          display: block;
          height: 12px;
          overflow: hidden;
          border: 1px solid rgba(20, 17, 13, 0.18);
          background: linear-gradient(90deg, #e8e0cf, #fbf6ea, #e8e0cf);
          background-size: 220% 100%;
          animation: notebook-shimmer 1.2s ease-in-out infinite;
        }
        .notebook-list-skeleton span:nth-child(2),
        .notebook-mobile-loading-list span:nth-child(2) {
          width: 78%;
        }
        .notebook-list-skeleton span:nth-child(3),
        .notebook-mobile-loading-list span:nth-child(3) {
          width: 58%;
        }
        .notebook-empty-state {
          margin: 12px 16px;
          border-width: 1px;
          padding: 16px;
        }
        .notebook-empty-action {
          margin-top: 12px;
        }
        .notebook-desktop-detail {
          display: none;
        }
        .notebook-mobile-detail {
          display: block;
          border-bottom: 1px solid var(--ink);
          background: var(--sheet);
          padding: 0 16px 18px;
        }
        .notebook-concept-row {
          grid-template-columns: minmax(0, 1fr) auto;
          gap: 10px;
          min-height: 60px;
          align-items: center;
          padding: 12px 16px;
          color: var(--ink) !important;
          background: transparent !important;
        }
        .notebook-concept-row[data-active='true'] {
          background: #f8f3e8 !important;
          box-shadow: inset 4px 0 0 var(--ink);
        }
        .notebook-concept-row:focus-visible,
        .notebook-levels button:focus-visible,
        .notebook-filter-summary button:focus-visible,
        .notebook-empty-clear:focus-visible,
        .notebook-search-clear:focus-visible,
        .notebook-save-notes:focus-visible {
          outline: 2px solid var(--blue);
          outline-offset: 2px;
        }
        .notebook-concept-motif {
          display: none;
        }
        .notebook-concept-row > .min-w-0 {
          display: flex;
          min-width: 0;
          flex-direction: column;
        }
        .notebook-row-head {
          order: 2;
          margin-top: 6px;
          align-items: center;
          overflow: hidden;
          white-space: nowrap;
        }
        .notebook-row-title {
          order: 1;
        }
        .notebook-row-kicker,
        .notebook-row-meta {
          font-size: 12px;
          letter-spacing: 0;
          text-transform: none;
        }
        .notebook-row-title {
          font-size: 15px;
          line-height: 1.3;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        .notebook-row-meta {
          display: none;
          order: 3;
          justify-content: flex-start;
          gap: 8px;
          margin-top: 0;
          overflow: hidden;
          white-space: nowrap;
        }
        .notebook-row-meta span {
          min-width: 0;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .notebook-row-badge {
          border: 1px solid var(--red);
          background: #f5dad5 !important;
          color: var(--red) !important;
          padding: 1px 5px;
          font-size: 9px;
          line-height: 1.4;
          letter-spacing: 0.08em;
        }
        .notebook-row-chevron {
          display: block;
          color: var(--ink-3);
        }
        .notebook-detail {
          gap: 14px;
          max-width: 100%;
        }
        .notebook-mobile-practice-cta {
          position: sticky;
          bottom: env(safe-area-inset-bottom);
          z-index: 6;
          display: flex;
          min-height: 56px;
          align-items: center;
          justify-content: center;
          gap: 9px;
          margin: 0 -16px 14px;
          border-top: 1px solid var(--ink);
          border-bottom: 0;
          background: var(--ink);
          color: var(--paper);
          font-size: 12px;
          font-weight: 900;
          letter-spacing: 0;
          text-decoration: none;
        }
        .notebook-reference-card,
        .notebook-mistakes-card,
        .notebook-practice-card,
        .notebook-erratum-card {
          border-width: 1px;
          border-radius: 0;
          background: var(--sheet) !important;
          box-shadow: none;
          max-width: 100%;
        }
        .notebook-detail-loading {
          min-height: 156px;
          border-width: 1px;
          background: #fbf6ea;
        }
        .notebook-detail-hero {
          grid-template-columns: minmax(0, 1fr);
          gap: 14px;
          border-bottom-width: 1px;
          padding: 12px 0 16px;
        }
        .notebook-detail-motif {
          display: none;
        }
        .notebook-detail-tags {
          gap: 6px;
          margin-bottom: 14px;
          font-size: 10px;
          letter-spacing: 0.1em;
        }
        .notebook-detail-tags span {
          border-width: 1px;
          border-radius: 999px;
          padding: 3px 9px 4px;
        }
        .notebook-detail-title {
          font-family: var(--serif);
          font-size: 32px;
          font-style: italic;
          font-weight: 500;
          line-height: 1.02;
          overflow-wrap: anywhere;
        }
        .notebook-detail-meta {
          grid-template-columns: 1fr;
          gap: 8px;
          margin-top: 12px;
        }
        .notebook-detail-meta > div {
          border-top-width: 1px;
          padding-top: 6px;
        }
        .notebook-detail-meta div {
          min-width: 0;
        }
        .notebook-detail-meta [class*="text-lg"] {
          font-size: 13px;
          line-height: 1.15;
          overflow-wrap: anywhere;
        }
        .notebook-reference-main,
        .notebook-side-panel,
        .notebook-mistakes-grid,
        .notebook-practice-card {
          padding: 14px 0;
        }
        .notebook-reference-main {
          gap: 14px;
          border-bottom-width: 1px;
        }
        .notebook-reference-main > .grid {
          gap: 12px;
        }
        .notebook-reference-section {
          border-top: 1px solid var(--ink);
          padding: 14px 0;
        }
        .notebook-reference-section:first-child {
          border-top: 0;
          padding-top: 0;
        }
        .notebook-reference-section h3,
        .notebook-xray h3,
        .notebook-notes > div:first-child,
        .notebook-mistakes-card > div:first-child,
        .notebook-practice-card > div:first-child {
          margin-bottom: 8px;
          font-size: 10px;
          letter-spacing: 0.1em;
        }
        .notebook-reference-section [class*="text-xl"],
        .notebook-reference-section .text-base {
          font-size: 15px;
          line-height: 1.45;
        }
        .notebook-reference-section [class*="font-mono"] {
          overflow-wrap: anywhere;
          font-size: 12px;
        }
        .notebook-reference-section p,
        .notebook-reference-section li,
        .notebook-xray p,
        .notebook-erratum-card p {
          overflow-wrap: anywhere;
        }
        .notebook-side-panel {
          gap: 12px;
        }
        .notebook-xray {
          border-left-width: 3px;
          padding: 11px;
        }
        .notebook-xray .font-serif.text-3xl {
          margin-bottom: 12px;
          font-size: 22px;
          line-height: 1.1;
        }
        .notebook-xray .font-serif.text-xl {
          font-size: 17px;
        }
        .notebook-notes-input {
          min-height: 96px;
          padding: 10px;
          font-size: 14px;
        }
        .notebook-notes {
          border: 1px solid rgba(20, 17, 13, 0.3);
          background: #fbf6ea;
          padding: 11px;
          transition: border-color .16s ease, box-shadow .16s ease;
        }
        .notebook-notes[data-focused='true'] {
          border-color: var(--blue);
          box-shadow: inset 3px 0 0 var(--blue);
        }
        .notebook-notes[data-dirty='true'] {
          border-color: var(--red);
        }
        .notebook-notes-status {
          margin-left: auto;
          border: 1px solid currentColor;
          padding: 3px 6px;
          color: var(--ink-2);
          font-size: 9px;
          letter-spacing: 0.08em;
          line-height: 1;
          white-space: nowrap;
        }
        .notebook-notes[data-dirty='true'] .notebook-notes-status {
          color: var(--red);
        }
        .notebook-notes[data-focused='true'] .notebook-notes-status,
        .notebook-notes[data-saving='true'] .notebook-notes-status {
          color: var(--blue);
        }
        .notebook-save-notes {
          min-height: 38px;
          width: 100%;
          justify-content: center;
          padding: 0 12px;
          letter-spacing: 0.1em;
        }
        .notebook-notes[data-dirty='true'] .notebook-save-notes,
        .notebook-notes[data-focused='true'] .notebook-save-notes {
          background: var(--blue);
        }
        .notebook-followup {
          gap: 14px;
        }
        .notebook-mistakes-card > div:first-child {
          border-bottom-width: 1px;
          padding: 10px 12px;
        }
        .notebook-mistakes-grid {
          grid-template-columns: 1fr;
          gap: 12px;
        }
        .notebook-erratum-card {
          padding: 12px;
        }
        .notebook-erratum-card .font-serif.text-xl {
          font-size: 18px;
        }
        .notebook-practice-card {
          display: none;
        }
        @keyframes notebook-shimmer {
          0% { background-position: 120% 0; }
          100% { background-position: -120% 0; }
        }
      }
    `}</style>
  );
}

function NotebookStat({ label, value, accent }: { label: string; value: number; accent?: 'red' | 'blue' }) {
  const color = accent === 'red' ? '#e3341c' : accent === 'blue' ? '#1f4696' : '#11110f';
  return (
    <div className="notebook-stat border-t-2 border-black pt-3">
      <div className="notebook-stat-value text-5xl font-black leading-none" style={{ color }}>{value}</div>
      <div className="notebook-stat-label mt-2 text-xs font-black uppercase tracking-[0.16em]">{label}</div>
    </div>
  );
}

function ConceptIndexRow({ concept, active, onSelect }: { concept: GrammarNotebookItem; active: boolean; onSelect: () => void }) {
  const errataCount = (concept.due_errata_count || 0) + (concept.recent_errata_count || 0);
  return (
    <button
      onClick={onSelect}
      aria-expanded={active}
      data-active={active ? 'true' : 'false'}
      className={`notebook-concept-row grid w-full grid-cols-[58px_minmax(0,1fr)] gap-3 border-b border-black/20 p-4 text-left transition ${
        active ? 'bg-black text-[#f7f1e6]' : 'bg-[#f7f1e6] hover:bg-[#eee7da]'
      }`}
    >
      <div className={`notebook-concept-motif flex h-12 w-12 items-center justify-center border-2 ${active ? 'border-[#f7f1e6]' : 'border-black'}`}>
        <ConceptMotif
          concept={{ category: concept.category, external_id: concept.external_id, atelier_blueprint: { visual_motif: concept.motif } }}
          size={42}
        />
      </div>
      <div className="min-w-0">
        <div className="notebook-row-head flex items-start justify-between gap-2">
          <div className="notebook-row-kicker truncate text-xs font-black uppercase tracking-[0.16em] opacity-70">
            {concept.level} · {formatCategory(concept.category)}
          </div>
          {concept.due_errata_count > 0 && (
            <span className="notebook-row-badge shrink-0 bg-[#e3341c] px-2 py-1 text-[10px] font-black uppercase tracking-[0.12em] text-white">
              due {concept.due_errata_count}
            </span>
          )}
        </div>
        <div className="notebook-row-title mt-1 text-lg font-black leading-tight">{concept.display_title || concept.name}</div>
        <div className="notebook-row-meta mt-2 flex items-center justify-between gap-3 text-xs uppercase tracking-[0.1em] opacity-75">
          <span>{concept.state_label}</span>
          <span>{Math.round(concept.mastery || 0)} mastery</span>
          {errataCount > 0 && <span>{errataCount} slips</span>}
        </div>
      </div>
      <ArrowRight className="notebook-row-chevron h-4 w-4" aria-hidden="true" />
    </button>
  );
}

function ConceptNotebookDetail({
  concept,
  draftNotes,
  onNotesChange,
  onSaveNotes,
  savingNotes,
}: {
  concept: GrammarNotebookDetail;
  draftNotes: string;
  onNotesChange: (value: string) => void;
  onSaveNotes: () => void;
  savingNotes: boolean;
}) {
  const blueprint = concept.atelier_blueprint || {};
  const pedagogy = blueprint.pedagogy || {};
  const xray = blueprint.sentence_xray || {};
  const examples = arrayFrom(pedagogy.micro_examples || pedagogy.anchor_examples);
  const traps = arrayFrom(pedagogy.main_traps);
  const contrastNotes = arrayFrom(pedagogy.contrast_notes || pedagogy.contrast_rules);
  const allMistakes = [...(concept.due_errata || []), ...(concept.recent_errata || [])];
  const displayTitle = concept.display_title || concept.name;
  const notesDirty = draftNotes !== (concept.personal_notes || '');

  return (
    <div className="notebook-detail space-y-6">
      <article className="notebook-reference-card border-2 border-black bg-[#f7f1e6]">
        <div className="notebook-detail-hero grid gap-5 border-b-2 border-black p-5 md:grid-cols-[140px_minmax(0,1fr)]">
          <div className="notebook-detail-motif flex h-32 w-32 items-center justify-center border-2 border-black bg-[#eee7da]">
            <ConceptMotif concept={{ category: concept.category, external_id: concept.external_id, atelier_blueprint: blueprint }} size={116} />
          </div>
          <div className="min-w-0">
            <div className="notebook-detail-tags mb-2 flex flex-wrap gap-2 text-xs font-black uppercase tracking-[0.16em]">
              <span className="border-2 border-black px-2 py-1">{concept.level}</span>
              <span className="border-2 border-black px-2 py-1">{formatCategory(concept.category)}</span>
              {concept.is_foundation && <span className="border-2 border-black bg-[#f1c40f] px-2 py-1">Foundation</span>}
            </div>
            <h2 className="notebook-detail-title text-4xl font-black leading-[1] sm:text-6xl">{displayTitle}</h2>
            <div className="notebook-detail-meta mt-5 grid gap-4 sm:grid-cols-3">
              <MiniMeta label="Mastery" value={`${Math.round(concept.mastery || 0)}/10`} />
              <MiniMeta label="State" value={concept.state_label} />
              <MiniMeta label="Next Review" value={formatDate(concept.next_review) || 'Not scheduled'} />
            </div>
          </div>
        </div>

        <div className="grid gap-0 lg:grid-cols-[minmax(0,1.2fr)_minmax(340px,0.8fr)]">
          <section className="notebook-reference-main space-y-6 border-b-2 border-black p-5 lg:border-b-0 lg:border-r-2">
            <ReferenceSection title="Rule">
              <p className="text-xl font-bold leading-relaxed">{pedagogy.core_rule}</p>
            </ReferenceSection>

            <div className="grid gap-5 md:grid-cols-2">
              <ReferenceSection title="When">
                <p>{pedagogy.when_to_use}</p>
              </ReferenceSection>
              <ReferenceSection title="Pattern">
                <p className="font-mono text-sm">{pedagogy.pattern}</p>
              </ReferenceSection>
            </div>

            <ReferenceSection title="Contrast">
              {contrastNotes.length ? (
                <ul className="space-y-2">
                  {contrastNotes.map((note) => (
                    <li key={note} className="border-l-4 border-[#1f4696] pl-3">{note}</li>
                  ))}
                </ul>
              ) : (
                <QualityGap />
              )}
            </ReferenceSection>

            <div className="grid gap-5 md:grid-cols-2">
              <ReferenceSection title="Traps">
                {traps.length ? <ChipList items={traps} accent="red" /> : <QualityGap />}
              </ReferenceSection>
              <ReferenceSection title="Examples">
                {examples.length ? (
                  <div className="space-y-2 font-serif text-xl italic leading-relaxed">
                    {examples.slice(0, 5).map((example) => <p key={example}>{example}</p>)}
                  </div>
                ) : (
                  <QualityGap />
                )}
              </ReferenceSection>
            </div>
          </section>

          <section className="notebook-side-panel space-y-6 p-5">
            <SentenceXRay xray={xray} />
            <NotesBlock
              value={draftNotes}
              dirty={notesDirty}
              onChange={onNotesChange}
              onSave={onSaveNotes}
              saving={savingNotes}
            />
          </section>
        </div>
      </article>

      <section className="notebook-followup grid gap-6">
        <article className="notebook-mistakes-card border-2 border-black bg-[#f7f1e6]">
          <div className="flex items-center justify-between border-b-2 border-black p-4">
            <div className="text-xs font-black uppercase tracking-[0.18em]">Your Mistakes</div>
            <div className="text-xs font-black uppercase tracking-[0.18em]">{allMistakes.length}</div>
          </div>
          <div className="notebook-mistakes-grid grid gap-4 p-5 md:grid-cols-2">
            {allMistakes.length ? (
              allMistakes.map((erratum, index) => (
                <ErratumCard key={`${erratum.id || index}-${index}`} erratum={erratum} due={index < (concept.due_errata?.length || 0)} />
              ))
            ) : (
              <EmptyBlock title="No linked mistakes yet" body="Mistakes from Atelier will appear here once this concept is practiced." />
            )}
          </div>
        </article>
      </section>
    </div>
  );
}

function MiniMeta({ label, value }: { label: string; value: string }) {
  return (
    <div className="border-t-2 border-black pt-2">
      <div className="text-xs font-black uppercase tracking-[0.16em] text-[#625d55]">{label}</div>
      <div className="mt-1 text-lg font-black">{value}</div>
    </div>
  );
}

function ReferenceSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="notebook-reference-section">
      <h3 className="mb-3 text-xs font-black uppercase tracking-[0.18em]">{title}</h3>
      <div className="text-base leading-relaxed">{children}</div>
    </section>
  );
}

function SentenceXRay({ xray }: { xray: Record<string, any> }) {
  const sentence = xray?.sentence;
  const marks = Array.isArray(xray?.marks) ? xray.marks : [];
  const explanation = xray?.explanation;
  return (
    <section className="notebook-xray border-l-4 border-[#1f4696] bg-[#eee7da] p-4">
      <h3 className="mb-4 text-xs font-black uppercase tracking-[0.18em]">Sentence X-Ray</h3>
      {sentence ? (
        <>
          <p className="mb-5 font-serif text-3xl italic leading-tight">{renderMarkedSentence(sentence, marks)}</p>
          {explanation && <p className="mb-5 max-w-prose text-sm leading-relaxed text-[#3f3b35]">{explanation}</p>}
          <div className="space-y-3">
            {marks.map((mark: Record<string, any>, index: number) => (
              <div key={`${mark.token || mark.role || index}-${index}`} className="grid gap-2 border-t border-black/20 pt-3 sm:grid-cols-[120px_minmax(0,1fr)]">
                <div className="font-mono text-xs font-black uppercase tracking-[0.14em]" style={{ color: xrayColor(mark.color || 'blue') }}>
                  {mark.role || 'mark'}
                </div>
                <div>
                  <div className="font-serif text-xl italic">{mark.token}</div>
                  <p className="mt-1 text-sm leading-relaxed text-[#625d55]">{mark.explanation}</p>
                </div>
              </div>
            ))}
          </div>
        </>
      ) : (
        <p>No X-Ray prepared yet.</p>
      )}
    </section>
  );
}

function renderMarkedSentence(sentence: string, marks: Array<Record<string, any>>) {
  const ranges: Array<{ start: number; end: number; mark: Record<string, any> }> = [];
  const occupied: Array<[number, number]> = [];
  marks.forEach((mark) => {
    const token = String(mark.token || '').replace(/\.\.\./g, '');
    if (!token) return;
    const start = sentence.indexOf(token);
    if (start < 0) return;
    const end = start + token.length;
    if (occupied.some(([left, right]) => start < right && end > left)) return;
    occupied.push([start, end]);
    ranges.push({ start, end, mark });
  });
  ranges.sort((a, b) => a.start - b.start);
  if (!ranges.length) return sentence;
  const nodes: React.ReactNode[] = [];
  let cursor = 0;
  ranges.forEach((range, index) => {
    if (range.start > cursor) nodes.push(sentence.slice(cursor, range.start));
    nodes.push(
      <span
        key={`${range.mark.role || 'mark'}-${index}`}
        className="xray-mark"
        style={{
          textDecorationLine: 'underline',
          textDecorationThickness: '3px',
          textDecorationColor: xrayColor(range.mark.color),
          textUnderlineOffset: '8px',
        }}
      >
        {sentence.slice(range.start, range.end)}
      </span>
    );
    cursor = range.end;
  });
  if (cursor < sentence.length) nodes.push(sentence.slice(cursor));
  return nodes;
}

function xrayColor(value?: string | null) {
  const token = String(value || '').toLowerCase();
  if (token === 'red') return '#e3341c';
  if (token === 'blue') return '#1f4696';
  if (token === 'yellow') return '#d8aa13';
  return '#11110f';
}

function NotesBlock({
  value,
  dirty,
  onChange,
  onSave,
  saving,
}: {
  value: string;
  dirty: boolean;
  onChange: (value: string) => void;
  onSave: () => void;
  saving: boolean;
}) {
  const [focused, setFocused] = useState(false);
  const status = saving ? 'Saving...' : focused ? 'Editing' : dirty ? 'Unsaved changes' : 'Saved';

  return (
    <section
      className="notebook-notes"
      data-dirty={dirty ? 'true' : 'false'}
      data-focused={focused ? 'true' : 'false'}
      data-saving={saving ? 'true' : 'false'}
    >
      <div className="mb-3 flex items-center gap-2 text-xs font-black uppercase tracking-[0.18em]">
        <StickyNote className="h-4 w-4" />
        Personal Notes
        <span className="notebook-notes-status" aria-live="polite">
          {status}
        </span>
      </div>
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        aria-label="Personal notes"
        className="notebook-notes-input min-h-[180px] w-full resize-y border-2 border-black bg-[#f7f1e6] p-4 text-base leading-relaxed outline-none focus:translate-x-0 focus:translate-y-0"
        placeholder="Your notes for this rule."
      />
      <button
        onClick={onSave}
        disabled={saving}
        className="notebook-save-notes mt-3 inline-flex items-center gap-2 border-2 border-black bg-black px-4 py-3 text-xs font-black uppercase tracking-[0.16em] text-white disabled:opacity-60"
      >
        {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
        Save Notes
      </button>
    </section>
  );
}

function ErratumCard({ erratum, due }: { erratum: AtelierErratum; due: boolean }) {
  return (
    <RedInkRepairSlip
      className="notebook-erratum-card"
      label={erratum.display_label || erratum.error_category || 'Mistake'}
      stamp={due ? 'Due' : 'Recent'}
      learnerText={erratum.learner_text || undefined}
      correctedText={erratum.corrected_target || undefined}
      why={erratum.why_wrong}
      repair={erratum.repair_hint}
      source={[
        erratum.occurrences != null ? `${erratum.occurrences} seen` : null,
        erratum.next_review_date ? `Next ${formatDate(erratum.next_review_date)}` : null,
        erratum.source_type,
      ].filter(Boolean).join(' · ')}
      action={erratum.id && (
        <Link
          className="text-[#1f4696]"
          href={`/missions?erratum_id=${erratum.id}${erratum.concept_id ? `&concept_id=${erratum.concept_id}` : ''}`}
        >
          Repair in mission
        </Link>
      )}
    />
  );
}

function QualityGap() {
  return (
    <p className="border-l-4 border-[#e3341c] pl-3 text-sm leading-relaxed text-[#625d55]">
      This concept needs a regenerated blueprint before it can be shown here.
    </p>
  );
}

function ChipList({ items, accent }: { items: string[]; accent?: 'red' | 'blue' }) {
  if (!items.length) return null;
  const color = accent === 'red' ? '#e3341c' : '#1f4696';
  return (
    <div className="flex flex-wrap gap-2">
      {items.slice(0, 6).map((item) => (
        <span key={item} className="border-2 border-black bg-[#eee7da] px-2 py-1 text-xs font-bold" style={{ borderLeftColor: color, borderLeftWidth: 6 }}>
          {item}
        </span>
      ))}
    </div>
  );
}

function LoadingBlock({ label }: { label: string }) {
  return (
    <div className="notebook-loading-block p-5">
      <div className="flex items-center gap-3 text-xs font-black uppercase tracking-[0.16em]">
        <Loader2 className="h-4 w-4 animate-spin" />
        {label}
      </div>
      <div className="notebook-list-skeleton" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
    </div>
  );
}

function EmptyBlock({ title, body, action }: { title: string; body: string; action?: React.ReactNode }) {
  return (
    <div className="notebook-empty-state border-2 border-dashed border-black/40 bg-[#eee7da] p-6">
      <div className="mb-2 flex items-center gap-2 text-xs font-black uppercase tracking-[0.16em]">
        <AlertCircle className="h-4 w-4" />
        {title}
      </div>
      <p className="text-sm leading-relaxed text-[#625d55]">{body}</p>
      {action && <div className="notebook-empty-action">{action}</div>}
    </div>
  );
}

function ErrorBlock({
  title,
  body,
  actionLabel,
  onAction,
}: {
  title: string;
  body: string;
  actionLabel: string;
  onAction: () => void;
}) {
  return (
    <div className="notebook-empty-state notebook-error-state border-2 border-black bg-[#fbf6ea] p-6">
      <div className="mb-2 flex items-center gap-2 text-xs font-black uppercase tracking-[0.16em] text-[#d8321a]">
        <AlertCircle className="h-4 w-4" />
        {title}
      </div>
      <p className="text-sm leading-relaxed text-[#625d55]">{body}</p>
      <div className="notebook-empty-action">
        <button type="button" className="notebook-empty-clear" onClick={onAction}>
          {actionLabel}
        </button>
      </div>
    </div>
  );
}

function arrayFrom(value: any): string[] {
  if (Array.isArray(value)) return value.map((item) => String(item).trim()).filter(Boolean);
  if (typeof value === 'string') {
    return value
      .split(/[;|]/)
      .map((item) => item.trim())
      .filter(Boolean);
  }
  return [];
}

function formatDate(value?: string | null) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

function formatCategory(value?: string | null) {
  const raw = String(value || '').trim();
  if (!raw) return 'Grammar';
  const map: Record<string, string> = {
    ALLGEMEIN: 'General',
    Allgemein: 'General',
    SATZBAU: 'Syntax',
    Satzbau: 'Syntax',
    VERBEN: 'Verbs',
    Verben: 'Verbs',
    PRONOMEN: 'Pronouns',
    Pronomen: 'Pronouns',
  };
  return map[raw] || raw;
}
