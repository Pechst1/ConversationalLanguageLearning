import React, { useEffect, useMemo, useState } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { useRouter } from 'next/router';
import useSWR from 'swr';
import { AlertCircle, ArrowRight, Loader2, Save, Search, StickyNote } from 'lucide-react';
import toast from 'react-hot-toast';

import EditorialMasthead from '@/components/layout/EditorialMasthead';
import { ConceptMotif } from '@/components/grammar/ConceptMotif';
import { Button } from '@/components/ui/Button';
import api, { AtelierErratum, GrammarNotebookDetail, GrammarNotebookItem } from '@/services/api';

const levels = ['all', 'A1', 'A2', 'B1', 'B2', 'C1', 'C2'];

export default function GrammarNotebookPage() {
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
    const queryConceptId = Number(router.query.concept);
    if (Number.isFinite(queryConceptId) && concepts.some((concept) => concept.id === queryConceptId)) {
      if (selectedId !== queryConceptId) setSelectedId(queryConceptId);
      return;
    }
    if (!selectedId || !concepts.some((concept) => concept.id === selectedId)) {
      const firstId = concepts[0].id;
      setSelectedId(firstId);
    }
  }, [concepts, router.query.concept, selectedId]);

  function selectConcept(conceptId: number) {
    setSelectedId(conceptId);
    router.replace({ pathname: '/grammar', query: { ...router.query, concept: conceptId } }, undefined, { shallow: true });
  }

  const {
    data: selected,
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

  return (
    <>
      <Head>
        <title>Grammar Notebook · Atelier</title>
      </Head>
      <NotebookStyles />

      <main className="notebook-page min-h-screen bg-[#f1ece1] text-[#14110d]">
        <EditorialMasthead active="notebook" />

        <div className="notebook-spread py-8">
          <header className="notebook-title mb-7">
            <div>
              <div className="notebook-eyebrow">Reference Layer</div>
              <h1>Grammar Notebook</h1>
            </div>
            <Link className="notebook-practice" href="/atelier">
              Practice in Atelier <ArrowRight className="h-4 w-4" />
            </Link>
          </header>

          <section className="mb-7 grid gap-5 md:grid-cols-4">
            <NotebookStat label="Concepts" value={concepts.length} />
            <NotebookStat label="Started" value={totals.started} />
            <NotebookStat label="Due Errata" value={totals.due} accent="red" />
            <NotebookStat label="Recent Errata" value={totals.recent} accent="blue" />
          </section>

          <section className="grid gap-6 lg:grid-cols-[390px_minmax(0,1fr)]">
            <aside className="h-fit border-2 border-black bg-[#f7f1e6]">
              <div className="border-b-2 border-black p-4">
                <div className="mb-4 flex items-center gap-3 border-2 border-black bg-[#eee7da] px-3 py-2">
                  <Search className="h-4 w-4 shrink-0" />
                  <input
                    className="min-w-0 flex-1 border-0 bg-transparent p-0 text-sm outline-none focus:translate-x-0 focus:translate-y-0"
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    placeholder="Search rules, traps, IDs"
                  />
                </div>
                <div className="flex flex-wrap gap-2">
                  {levels.map((item) => (
                    <button
                      key={item}
                      onClick={() => setLevel(item)}
                      className={`border-2 border-black px-3 py-2 text-xs font-black uppercase tracking-[0.12em] ${
                        level === item ? 'bg-black text-white' : 'bg-[#f7f1e6]'
                      }`}
                    >
                      {item}
                    </button>
                  ))}
                </div>
              </div>

              <div className="max-h-[calc(100vh-250px)] overflow-y-auto">
                {isLoading ? (
                  <LoadingBlock label="Loading notebook" />
                ) : concepts.length ? (
                  concepts.map((concept) => (
                    <ConceptIndexRow
                      key={concept.id}
                      concept={concept}
                      active={concept.id === selectedId}
                      onSelect={() => selectConcept(concept.id)}
                    />
                  ))
                ) : (
                  <EmptyBlock title="No concepts found" body="Try another level or search term." />
                )}
              </div>
            </aside>

            <section className="min-w-0">
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
      </main>
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
      .notebook-spread {
        width: min(1320px, 100%);
        margin: 0 auto;
        padding-left: clamp(22px, 4vw, 48px);
        padding-right: clamp(22px, 4vw, 48px);
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
      @media (max-width: 760px) {
        .notebook-masthead-inner,
        .notebook-title {
          align-items: flex-start;
          flex-direction: column;
        }
        .notebook-nav { flex-wrap: wrap; }
        .notebook-practice { width: 100%; }
      }
    `}</style>
  );
}

function NotebookStat({ label, value, accent }: { label: string; value: number; accent?: 'red' | 'blue' }) {
  const color = accent === 'red' ? '#e3341c' : accent === 'blue' ? '#1f4696' : '#11110f';
  return (
    <div className="border-t-2 border-black pt-3">
      <div className="text-5xl font-black leading-none" style={{ color }}>{value}</div>
      <div className="mt-2 text-xs font-black uppercase tracking-[0.16em]">{label}</div>
    </div>
  );
}

function ConceptIndexRow({ concept, active, onSelect }: { concept: GrammarNotebookItem; active: boolean; onSelect: () => void }) {
  const errataCount = (concept.due_errata_count || 0) + (concept.recent_errata_count || 0);
  return (
    <button
      onClick={onSelect}
      className={`grid w-full grid-cols-[58px_minmax(0,1fr)] gap-3 border-b border-black/20 p-4 text-left transition ${
        active ? 'bg-black text-[#f7f1e6]' : 'bg-[#f7f1e6] hover:bg-[#eee7da]'
      }`}
    >
      <div className={`flex h-12 w-12 items-center justify-center border-2 ${active ? 'border-[#f7f1e6]' : 'border-black'}`}>
        <ConceptMotif
          concept={{ category: concept.category, external_id: concept.external_id, atelier_blueprint: { visual_motif: concept.motif } }}
          size={42}
        />
      </div>
      <div className="min-w-0">
        <div className="flex items-start justify-between gap-2">
          <div className="truncate text-xs font-black uppercase tracking-[0.16em] opacity-70">
            {concept.level} · {formatCategory(concept.category)}
          </div>
          {concept.due_errata_count > 0 && (
            <span className="shrink-0 bg-[#e3341c] px-2 py-1 text-[10px] font-black uppercase tracking-[0.12em] text-white">
              due {concept.due_errata_count}
            </span>
          )}
        </div>
        <div className="mt-1 text-lg font-black leading-tight">{concept.display_title || concept.name}</div>
        <div className="mt-2 flex items-center justify-between gap-3 text-xs uppercase tracking-[0.1em] opacity-75">
          <span>{concept.state_label}</span>
          <span>{Math.round(concept.mastery || 0)} mastery</span>
          {errataCount > 0 && <span>{errataCount} slips</span>}
        </div>
      </div>
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

  return (
    <div className="space-y-6">
      <article className="border-2 border-black bg-[#f7f1e6]">
        <div className="grid gap-5 border-b-2 border-black p-5 md:grid-cols-[140px_minmax(0,1fr)]">
          <div className="flex h-32 w-32 items-center justify-center border-2 border-black bg-[#eee7da]">
            <ConceptMotif concept={{ category: concept.category, external_id: concept.external_id, atelier_blueprint: blueprint }} size={116} />
          </div>
          <div className="min-w-0">
            <div className="mb-2 flex flex-wrap gap-2 text-xs font-black uppercase tracking-[0.16em]">
              <span className="border-2 border-black px-2 py-1">{concept.level}</span>
              <span className="border-2 border-black px-2 py-1">{formatCategory(concept.category)}</span>
              {concept.is_foundation && <span className="border-2 border-black bg-[#f1c40f] px-2 py-1">Foundation</span>}
            </div>
            <h2 className="text-4xl font-black leading-[1] sm:text-6xl">{displayTitle}</h2>
            <div className="mt-5 grid gap-4 sm:grid-cols-3">
              <MiniMeta label="Mastery" value={`${Math.round(concept.mastery || 0)}/10`} />
              <MiniMeta label="State" value={concept.state_label} />
              <MiniMeta label="Next Review" value={formatDate(concept.next_review) || 'Not scheduled'} />
            </div>
          </div>
        </div>

        <div className="grid gap-0 lg:grid-cols-[minmax(0,1.2fr)_minmax(340px,0.8fr)]">
          <section className="space-y-6 border-b-2 border-black p-5 lg:border-b-0 lg:border-r-2">
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

          <section className="space-y-6 p-5">
            <SentenceXRay xray={xray} />
            <NotesBlock value={draftNotes} onChange={onNotesChange} onSave={onSaveNotes} saving={savingNotes} />
          </section>
        </div>
      </article>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
        <article className="border-2 border-black bg-[#f7f1e6]">
          <div className="flex items-center justify-between border-b-2 border-black p-4">
            <div className="text-xs font-black uppercase tracking-[0.18em]">Your Mistakes</div>
            <div className="text-xs font-black uppercase tracking-[0.18em]">{allMistakes.length}</div>
          </div>
          <div className="grid gap-4 p-5 md:grid-cols-2">
            {allMistakes.length ? (
              allMistakes.map((erratum, index) => (
                <ErratumCard key={`${erratum.id || index}-${index}`} erratum={erratum} due={index < (concept.due_errata?.length || 0)} />
              ))
            ) : (
              <EmptyBlock title="No linked mistakes yet" body="Mistakes from Atelier will appear here once this concept is practiced." />
            )}
          </div>
        </article>

        <article className="h-fit border-2 border-black bg-[#f7f1e6] p-5">
          <div className="mb-4 text-xs font-black uppercase tracking-[0.18em]">Practice Link</div>
          <p className="mb-5 text-sm leading-relaxed text-[#625d55]">
            {concept.due_errata_count > 0
              ? 'This rule has due errata and should be pulled back into Atelier.'
              : 'This rule is available as a reference while future sessions continue scheduling it.'}
          </p>
          <Link href={`/atelier?concept_id=${concept.id}`}>
            <Button rightIcon={<ArrowRight className="h-4 w-4" />} className="w-full justify-center">
              Practice this concept
            </Button>
          </Link>
          <Link href={`/missions?concept_id=${concept.id}`}>
            <Button rightIcon={<ArrowRight className="h-4 w-4" />} className="mt-3 w-full justify-center">
              Use in a mission
            </Button>
          </Link>
          <Link href={`/graphic-novel?concept_id=${concept.id}`}>
            <Button rightIcon={<ArrowRight className="h-4 w-4" />} className="mt-3 w-full justify-center">
              See in Feuilleton
            </Button>
          </Link>
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
    <section>
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
    <section className="border-l-4 border-[#1f4696] bg-[#eee7da] p-4">
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
  onChange,
  onSave,
  saving,
}: {
  value: string;
  onChange: (value: string) => void;
  onSave: () => void;
  saving: boolean;
}) {
  return (
    <section>
      <div className="mb-3 flex items-center gap-2 text-xs font-black uppercase tracking-[0.18em]">
        <StickyNote className="h-4 w-4" />
        Personal Notes
      </div>
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="min-h-[180px] w-full resize-y border-2 border-black bg-[#f7f1e6] p-4 text-base leading-relaxed outline-none focus:translate-x-0 focus:translate-y-0"
        placeholder="Your notes for this rule."
      />
      <button
        onClick={onSave}
        disabled={saving}
        className="mt-3 inline-flex items-center gap-2 border-2 border-black bg-black px-4 py-3 text-xs font-black uppercase tracking-[0.16em] text-white disabled:opacity-60"
      >
        {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
        Save Notes
      </button>
    </section>
  );
}

function ErratumCard({ erratum, due }: { erratum: AtelierErratum; due: boolean }) {
  return (
    <article className="relative border-2 border-black bg-[#fbf6ea] p-4 shadow-[5px_5px_0_#11110f]">
      <div className="mb-4 flex items-start justify-between gap-3">
        <span className={`px-2 py-1 text-xs font-black uppercase tracking-[0.12em] text-white ${due ? 'bg-[#e3341c]' : 'bg-[#1f4696]'}`}>
          {erratum.display_label || erratum.error_category || 'Mistake'}
        </span>
        <span className="font-mono text-xs font-black uppercase">{due ? 'Due' : 'Recent'}</span>
      </div>
      {erratum.learner_text && (
        <div className="mb-3">
          <div className="mb-1 text-[11px] font-black uppercase tracking-[0.14em] text-[#625d55]">You wrote</div>
          <p className="font-serif text-xl italic leading-snug text-[#e3341c] line-through">{erratum.learner_text}</p>
        </div>
      )}
      {erratum.corrected_target && (
        <div className="mb-3">
          <div className="mb-1 text-[11px] font-black uppercase tracking-[0.14em] text-[#625d55]">Correction</div>
          <p className="inline bg-[#f7e3a0] font-serif text-xl italic leading-snug">{erratum.corrected_target}</p>
        </div>
      )}
      <div className="border-l-4 border-[#1f4696] pl-3 text-sm leading-relaxed">
        {erratum.why_wrong && <p><strong>Why.</strong> {erratum.why_wrong}</p>}
        {erratum.repair_hint && <p><strong>Repair.</strong> {erratum.repair_hint}</p>}
      </div>
      <div className="mt-4 flex flex-wrap gap-3 border-t border-black/20 pt-3 text-[11px] font-black uppercase tracking-[0.12em] text-[#625d55]">
        {erratum.occurrences != null && <span>{erratum.occurrences} seen</span>}
        {erratum.next_review_date && <span>Next {formatDate(erratum.next_review_date)}</span>}
        {erratum.source_type && <span>{erratum.source_type}</span>}
        {erratum.id && (
          <Link
            className="text-[#1f4696]"
            href={`/missions?erratum_id=${erratum.id}${erratum.concept_id ? `&concept_id=${erratum.concept_id}` : ''}`}
          >
            Repair in mission
          </Link>
        )}
      </div>
    </article>
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
    <div className="flex items-center gap-3 p-5 text-xs font-black uppercase tracking-[0.16em]">
      <Loader2 className="h-4 w-4 animate-spin" />
      {label}
    </div>
  );
}

function EmptyBlock({ title, body }: { title: string; body: string }) {
  return (
    <div className="border-2 border-dashed border-black/40 bg-[#eee7da] p-6">
      <div className="mb-2 flex items-center gap-2 text-xs font-black uppercase tracking-[0.16em]">
        <AlertCircle className="h-4 w-4" />
        {title}
      </div>
      <p className="text-sm leading-relaxed text-[#625d55]">{body}</p>
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
