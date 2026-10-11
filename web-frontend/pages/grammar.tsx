import React, { useEffect, useMemo, useState } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { useRouter } from 'next/router';
import useSWR from 'swr';
import toast from 'react-hot-toast';

import PhoneProductNav from '@/components/layout/PhoneProductNav';
import {
  Action,
  ArrowRightIcon,
  AtelierV2Root,
  Chip,
  Notice,
  ProgressRule,
  ShapeToken,
  Skeleton,
  StateBlock,
  Surface,
} from '@/components/atelier-v2/ui';
import {
  CahierChips,
  CahierHead,
  CahierLiveLine,
  CahierSearch,
  CahierStyles,
  ConceptRow,
  NbBack,
  NbSectionHead,
  NotebookModeTabs,
  type CahierChip,
  type CahierMode,
  type ConceptTone,
} from '@/components/cahiers/CahierV2';
import { cahierCopy, countLabel, fill, type CahierCopy } from '@/components/cahiers/cahier-copy';
import GrammarMap from '@/components/cahiers/GrammarMap';
import { RuleCard } from '@/components/atelier-v2/rule/RuleCard';
import { XraySentence } from '@/components/atelier-v2/rule/XraySentence';
import { useChromeLanguage } from '@/lib/learner-language';
import { cardExamples, plainText, usableCard, usableXray } from '@/lib/rule-card';
import api, { AtelierErratum, GrammarNotebookDetail, GrammarNotebookItem } from '@/services/api';
import { forgeCopy } from '@/lib/forge-copy';
import {
  countStages,
  missingLine,
  stageCountsText,
  stageLabel,
  stageOf,
  type GrammarStage,
} from '@/lib/grammar-stages';
import type { components } from '@/types/generated/api';

/* WP-130 A: the unit's stage in the level's words, the band it counts for in
 * the level and the «Tenue» evidence it still lacks (see lib/grammar-stages). */
type StagedFields = Partial<
  Pick<components['schemas']['GrammarNotebookItemRead'], 'stage' | 'stage_label' | 'level_band' | 'held_missing'>
>;
type NotebookRow = GrammarNotebookItem & StagedFields;
type NotebookPage = GrammarNotebookDetail & StagedFields;

/* Map the backend grammar state (German keys from determine_state, or already
 * localized variants) to one of five learner states; fall back to mastery. */
type GrammarState = 'new' | 'building' | 'fragile' | 'solid' | 'mastered';
function grammarState(state: string | null | undefined, mastery: number): GrammarState {
  const s = String(state || '').toLowerCase();
  if (['mastered', 'gemeistert', 'acquis'].includes(s)) return 'mastered';
  if (['solid', 'gefestigt', 'solide'].includes(s)) return 'solid';
  if (['fragile', 'ausbaufähig', 'ausbaufahig'].includes(s)) return 'fragile';
  if (['building', 'in_arbeit', 'en cours', 'en_cours'].includes(s)) return 'building';
  if (['new', 'neu', 'nouveau'].includes(s)) return 'new';
  if (mastery >= 9) return 'mastered';
  if (mastery >= 7) return 'solid';
  if (mastery >= 5) return 'building';
  if (mastery > 0) return 'fragile';
  return 'new';
}

/* The design's glyph token: blue circle = en route, ink square = tenue (the
 * level's «held», WP-130 A — never a practice score), red square = fragile or
 * with an erratum due, line circle = à venir. */
function conceptTone(state: GrammarState, stage: GrammarStage, due: boolean): ConceptTone {
  if (due || state === 'fragile') return 'fragile';
  if (stage === 'held') return 'done';
  if (stage === 'practising' || stage === 'introduced') return 'progress';
  return 'new';
}

/* Three bars from the real 0–10 mastery, on the same thresholds as the state
 * fallback above: 1–4 → one bar, 5–8 → two, 9–10 → three. 0 stays on the track. */
function masteryBars(mastery: number): number {
  if (mastery >= 9) return 3;
  if (mastery >= 5) return 2;
  if (mastery >= 1) return 1;
  return 0;
}

function conceptGlyph(title: string, tone: ConceptTone): string {
  if (tone === 'new') return '';
  const letters = title.replace(/[^A-Za-z\u00C0-\u024F]+/g, '');
  if (!letters) return '·';
  return letters.charAt(0).toUpperCase() + letters.slice(1, 2).toLowerCase();
}

// The scale runs A1.1 … C1.2 (content program D4: C2 is out of scope).
const GRAMMAR_LEVELS = ['A1', 'A2', 'B1', 'B2', 'C1'];
const SUB_BANDS = ['A1.1', 'A1.2', 'A2.1', 'A2.2', 'B1.1', 'B1.2', 'B2.1', 'B2.2', 'C1.1', 'C1.2'];

/* F-1: the register grouped by sub-band (v2: the unit's own; v1: its level),
   lowest first; within a band the server's teaching order is kept. */
type ConceptGroup = { band: string; concepts: NotebookRow[] };
function groupBySubBand(concepts: NotebookRow[]): ConceptGroup[] {
  const groups: ConceptGroup[] = [];
  concepts.forEach((concept) => {
    // WP-130 A: the band the unit counts for in the level (v1 included).
    const band = String(concept.level_band || concept.sub_band || concept.level || '').trim() || '—';
    const group = groups.find((item) => item.band === band);
    if (group) group.concepts.push(concept);
    else groups.push({ band, concepts: [concept] });
  });
  const rank = (band: string) => {
    const exact = SUB_BANDS.indexOf(band);
    if (exact >= 0) return exact * 2;
    const level = SUB_BANDS.findIndex((item) => item.startsWith(band));
    return level >= 0 ? level * 2 + 1 : SUB_BANDS.length * 2;
  };
  return groups
    .map((group, index) => ({ group, index }))
    .sort((a, b) => rank(a.group.band) - rank(b.group.band) || a.index - b.index)
    .map(({ group }) => group);
}

type GrammarNotebookSurfaceProps = {
  embedded?: boolean;
};

function firstQueryValue(value: string | string[] | undefined) {
  return Array.isArray(value) ? value[0] : value;
}

export default function GrammarNotebookPage() {
  return <GrammarNotebookSurface />;
}

/* The direct /grammar and /vocabulary routes carry the same head as the
 * /notebook shell; their pill tabs are links to the sibling registers. */
function standaloneHref(mode: CahierMode) {
  if (mode === 'grammar') return '/grammar';
  if (mode === 'vocabulary') return '/vocabulary';
  return `/notebook?mode=${mode}`;
}

export function GrammarNotebookSurface({ embedded = false }: GrammarNotebookSurfaceProps) {
  const router = useRouter();
  // WP-82: the Cahier's chrome is the learner's language up to A2, French from
  // B1. The rule text, examples, traps and French titles stay French.
  const language = useChromeLanguage();
  const t = cahierCopy(language);
  const [level, setLevel] = useState('all');
  const [query, setQuery] = useState('');
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [dueOnly, setDueOnly] = useState(false);
  const [draftNotes, setDraftNotes] = useState('');
  const [savingNotes, setSavingNotes] = useState(false);
  const [notesEditing, setNotesEditing] = useState(false);
  const [notesError, setNotesError] = useState(false);
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
  } = useSWR<NotebookRow[]>(
    ['/grammar/notebook', notebookParams],
    async () => api.getGrammarNotebook(notebookParams)
  );

  // Phone-first drill-down: the index leads; a concept opens its fiche only
  // when the row is tapped or a deep-link query names it.
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
    // F-1: «Compare with» links name the partner by catalogue id (`?unit=FR2_…`).
    const queryUnit = firstQueryValue(router.query.unit);
    const unit = queryUnit ? concepts.find((concept) => concept.external_id === queryUnit) : undefined;
    if (unit) {
      if (selectedId !== unit.id) setSelectedId(unit.id);
      return;
    }
    if (selectedId !== null && !concepts.some((concept) => concept.id === selectedId)) {
      setSelectedId(null);
    }
  }, [concepts, router.query.concept, router.query.review, router.query.unit, selectedId]);

  function selectConcept(conceptId: number) {
    setSelectedId(conceptId);
    const nextQuery: Record<string, string | string[] | undefined> = { ...router.query, concept: String(conceptId) };
    delete nextQuery.review;
    delete nextQuery.unit;
    router.replace({ pathname: router.pathname, query: nextQuery }, undefined, { shallow: true, scroll: false });
    if (typeof window !== 'undefined') window.scrollTo({ top: 0 });
  }

  function deselectConcept() {
    setSelectedId(null);
    const nextQuery: Record<string, string | string[] | undefined> = { ...router.query };
    delete nextQuery.concept;
    delete nextQuery.review;
    delete nextQuery.unit;
    router.replace({ pathname: router.pathname, query: nextQuery }, undefined, { shallow: true, scroll: false });
  }

  const {
    data: selected,
    error: selectedError,
    isLoading: detailLoading,
    mutate: mutateSelected,
  } = useSWR<NotebookPage | null>(
    selectedId ? ['/grammar/notebook/detail', selectedId, locale] : null,
    async () => (selectedId ? api.getGrammarNotebookConcept(selectedId, { locale }) : null)
  );

  useEffect(() => {
    setDraftNotes(selected?.personal_notes || '');
    setNotesEditing(false);
    setNotesError(false);
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

  function clearFilters() {
    setLevel('all');
    setQuery('');
    setDueOnly(false);
  }

  async function saveNotes() {
    if (!selected) return;
    setSavingNotes(true);
    setNotesError(false);
    try {
      const updated = await api.updateGrammarNotebookNotes(selected.id, { notes: draftNotes });
      await mutateSelected(updated, false);
      await mutateNotebook();
      setNotesEditing(false);
      toast.success(t.notes.toast_saved);
    } catch (error) {
      setNotesError(true);
      toast.error(t.notes.toast_failed);
    } finally {
      setSavingNotes(false);
    }
  }

  const dueCount = useMemo(() => concepts.filter((c) => (c.due_errata_count || 0) > 0).length, [concepts]);
  const shownConcepts = useMemo(
    () => (dueOnly ? concepts.filter((c) => (c.due_errata_count || 0) > 0) : concepts),
    [concepts, dueOnly],
  );
  const shownGroups = useMemo(() => groupBySubBand(shownConcepts), [shownConcepts]);
  const orderedConcepts = useMemo(
    () => groupBySubBand(concepts).reduce<NotebookRow[]>((all, group) => all.concat(group.concepts), []),
    [concepts],
  );
  const filtersActive = level !== 'all' || activeSearch.length > 0 || dueOnly;

  const chips: CahierChip[] = [
    { id: 'all', label: t.grammar.chip_all },
    { id: 'due', label: t.grammar.chip_due, count: dueCount },
    ...GRAMMAR_LEVELS.map((lv): CahierChip => ({ id: lv, label: lv })),
  ];
  const activeChip = dueOnly ? 'due' : level === 'all' ? 'all' : level;
  function onChip(id: string) {
    if (id === 'all') { setLevel('all'); setDueOnly(false); }
    else if (id === 'due') { setDueOnly(true); }
    else { setLevel(GRAMMAR_LEVELS.includes(id) ? id : 'all'); setDueOnly(false); }
  }

  const selectedIndex = selected ? orderedConcepts.findIndex((c) => c.id === selected.id) : -1;
  const liveText = isLoading
    ? t.grammar.live_loading
    : [
        countLabel(t.grammar, dueOnly ? 'sheets_due' : 'sheets', shownConcepts.length),
        totals.recent > 0 ? countLabel(t.grammar, 'recent_errata', totals.recent) : null,
      ].filter(Boolean).join(' · ');

  const indexView = (
    <>
      {/* WP-S7: the syllabus as the four shapes, above the register. */}
      <GrammarMap language={language} onOpenPage={selectConcept} />
      <CahierSearch placeholder={t.grammar.search} value={query} onChange={setQuery} />
      <CahierChips chips={chips} active={activeChip} onSelect={onChip} label={t.grammar.filter_label} />
      <CahierLiveLine text={liveText} clearable={filtersActive} onClear={clearFilters} />
      {notebookError ? (
        <StateBlock
          tone="error"
          title={t.grammar.index_failed_title}
          body={t.grammar.index_failed_body}
          action={{ label: t.cahier.retry, onSelect: () => void mutateNotebook() }}
        />
      ) : isLoading ? (
        <div className="nb-list" aria-busy="true">
          {Array.from({ length: 6 }, (_, i) => <Skeleton key={i} height={68} radius={16} />)}
          <span className="av2-sr" role="status">{t.grammar.loading}</span>
        </div>
      ) : shownConcepts.length ? (
        <div className="nb-list" aria-label={t.grammar.index_label}>
          {shownGroups.map((group) => {
          // WP-130 A: the band's units in the level's words («A1.1 · 6 en route · 0 tenue»),
          // counted over the whole band (the due chip filters here, a level chip
          // keeps whole bands); a search returns part of a band, so it shows no counts.
          const bandRows = concepts.filter((c) => String(c.level_band || c.sub_band || c.level || '').trim() === group.band);
          const bandLine = activeSearch
            ? group.band
            : `${group.band} · ${stageCountsText(countStages(bandRows), language)}`;
          return (
          <div className="nb-band" key={group.band} role="group" aria-label={bandLine}>
          <p className="nb-band__label" aria-hidden="true">{bandLine}</p>
          <div className="nb-band__rows" role="list">
          {group.concepts.map((concept) => {
            const mastery = Math.round(concept.mastery || 0);
            const due = (concept.due_errata_count || 0) > 0;
            const errata = due ? concept.due_errata_count : concept.recent_errata_count;
            const state = grammarState(concept.state, concept.mastery || 0);
            const stage = stageOf(concept);
            const tone = conceptTone(state, stage, due);
            const title = concept.title_fr || concept.display_title || concept.name;
            const cat = concept.category_label_fr || concept.localized_category || formatCategory(concept.category);
            // The status word is chrome: the learner's language, never the server's French.
            // WP-130 A: the stage the level counts, the score only as practice.
            const stateLabel = stageLabel(concept, language);
            const meta = [
              concept.level,
              cat,
              stateLabel || null,
              due ? t.grammar.meta_due : null,
              !due && errata > 0 ? fill(errata === 1 ? t.grammar.meta_errata_one : t.grammar.meta_errata, { n: errata }) : null,
            ].filter(Boolean).join(' · ');
            return (
              <div key={concept.id} role="listitem">
                <ConceptRow
                  title={title}
                  meta={meta}
                  glyph={conceptGlyph(title, tone)}
                  tone={tone}
                  bars={masteryBars(mastery)}
                  ariaLabel={fill(due ? t.grammar.row_aria_due : t.grammar.row_aria, { title, level: concept.level, category: cat, mastery })}
                  onSelect={() => selectConcept(concept.id)}
                />
              </div>
            );
          })}
          </div>
          </div>
          );
          })}
        </div>
      ) : filtersActive ? (
        <StateBlock
          tone="empty"
          title={t.grammar.empty_filtered}
          action={{ label: t.cahier.clear_filters, onSelect: clearFilters }}
        />
      ) : (
        <StateBlock
          tone="empty"
          title={t.grammar.empty_title}
          body={t.grammar.empty_body}
          action={{ label: t.grammar.open_atelier, onSelect: () => router.push('/atelier') }}
        />
      )}
    </>
  );

  const ficheView = selected ? (
    <GrammarFiche
      t={t}
      language={language}
      concept={selected}
      index={selectedIndex >= 0 ? selectedIndex + 1 : null}
      onBack={deselectConcept}
      notesEditing={notesEditing}
      draftNotes={draftNotes}
      notesDirty={draftNotes !== (selected.personal_notes || '')}
      savingNotes={savingNotes}
      notesError={notesError}
      onNotesChange={setDraftNotes}
      onNotesEdit={() => { setNotesEditing(true); setNotesError(false); }}
      onNotesCancel={() => { setDraftNotes(selected.personal_notes || ''); setNotesEditing(false); setNotesError(false); }}
      onNotesSave={saveNotes}
    />
  ) : selectedError ? (
    <div className="nb-fiche">
      <NbBack label={t.grammar.index_label} onBack={deselectConcept} />
      <StateBlock
        tone="error"
        title={t.grammar.fiche_failed_title}
        body={t.grammar.fiche_failed_body}
        action={{ label: t.cahier.retry, onSelect: () => void mutateSelected() }}
      />
    </div>
  ) : (
    <div className="nb-fiche" aria-busy={detailLoading || undefined}>
      <NbBack label={t.grammar.index_label} onBack={deselectConcept} />
      <Skeleton height={96} radius={16} />
      <Skeleton height={140} radius={16} />
      <Skeleton height={140} radius={16} />
      <span className="av2-sr" role="status">{t.grammar.fiche_loading}</span>
    </div>
  );

  const pageContent = (
    <>
      <GrammarUnitStyles />
      {selectedId ? ficheView : indexView}
    </>
  );

  if (embedded) {
    return pageContent;
  }

  return (
    <>
      <Head>
        <title>{t.grammar.page_title}</title>
      </Head>
      <CahierStyles />
      <AtelierV2Root as="main" language={language} className="nb-page" aria-label={t.grammar.page_label}>
        <CahierHead kicker={isLoading ? t.grammar.kicker_loading : `${countLabel(t.cahier, 'concepts', concepts.length)} · ${stageCountsText(countStages(concepts), language)}`}>
          <NotebookModeTabs active="grammar" hrefFor={standaloneHref} />
        </CahierHead>
        <div className="nb-body">{pageContent}</div>
      </AtelierV2Root>
      <PhoneProductNav active="notebook" placement="embedded" />
    </>
  );
}

/* F-1: the register's sub-band heads and the unit page's card. Tokens only. */
function GrammarUnitStyles() {
  return (
    <style jsx global>{`
      .av2 .nb-band { display: flex; flex-direction: column; gap: 8px; min-width: 0; }
      .av2 .nb-band + .nb-band { margin-top: 10px; }
      .av2 .nb-band__label {
        margin: 0;
        font-size: var(--av2-t-meta);
        font-weight: 700;
        color: var(--av2-muted);
        font-variant-numeric: tabular-nums;
      }
      .av2 .nb-band__rows { display: flex; flex-direction: column; gap: 8px; }
      .av2 .nb-unit-card { min-width: 0; }
      .av2 .nb-unit-card > .rc[data-variant='inline'] { padding: 16px; }
    `}</style>
  );
}

/* ---------- La fiche de grammaire ---------- */
function ErratumLine({ erratum }: { erratum: AtelierErratum }) {
  const learner = erratum.learner_text || '';
  const target = erratum.corrected_target || erratum.display_label || 'corrigé';
  if (learner) {
    return (
      <>
        « <s>{learner}</s> » <span aria-hidden="true">→</span> <b>{target}</b>
      </>
    );
  }
  return <b>{target}</b>;
}

function GrammarFiche({
  t,
  language,
  concept,
  index,
  onBack,
  notesEditing,
  draftNotes,
  notesDirty,
  savingNotes,
  notesError,
  onNotesChange,
  onNotesEdit,
  onNotesCancel,
  onNotesSave,
}: {
  t: CahierCopy;
  language: string;
  concept: NotebookPage;
  index: number | null;
  onBack: () => void;
  notesEditing: boolean;
  draftNotes: string;
  notesDirty: boolean;
  savingNotes: boolean;
  notesError: boolean;
  onNotesChange: (value: string) => void;
  onNotesEdit: () => void;
  onNotesCancel: () => void;
  onNotesSave: () => void;
}) {
  const blueprint = concept.atelier_blueprint || {};
  const pedagogy = (blueprint.pedagogy || {}) as Record<string, any>;
  // F-1: the authored card is the unit's explanation. When there is one it
  // replaces the catalogue's English rule, motif and traps (the card has its
  // own, reviewed, in the learner's language); the anchors stay, minus the
  // sentences the card already shows.
  const cardLanguage = useChromeLanguage(concept.level);
  const card = usableCard(concept.rule_card) ? concept.rule_card : null;
  const xray = usableXray(concept.xray) ? concept.xray : null;
  const cardSentences = card
    ? [card.example.fr, ...cardExamples(card).map((item) => item.fr)].map((value) => plainText(value).trim().toLowerCase())
    : [];
  const rule = card ? '' : concept.core_rule || pedagogy.core_rule || '';
  const examples = (concept.anchor_examples?.length ? concept.anchor_examples : arrayFrom(pedagogy.micro_examples || pedagogy.anchor_examples))
    .filter((example) => cardSentences.indexOf(plainText(example).trim().toLowerCase()) < 0)
    .slice(0, 3);
  const traps = card?.traps?.length ? [] : concept.main_traps?.length ? concept.main_traps : arrayFrom(pedagogy.main_traps);
  const pattern = card?.pattern ? '' : pedagogy.pattern || '';
  const dueErrata = concept.due_errata || [];
  const recentErrata = concept.recent_errata || [];
  const mastery = Math.round(concept.mastery || 0);
  const nextReview = formatDate(concept.next_review, t.cahier.locale);
  const due = (concept.due_errata_count || 0) > 0;
  const state = grammarState(concept.state, concept.mastery || 0);
  const stage = stageOf(concept);
  const tone = conceptTone(state, stage, due);
  // WP-130 A: what the unit still needs to be held, said plainly (no praise).
  const missing = missingLine(concept.held_missing, language);
  const tokenKind = tone === 'fragile' ? 'action' : tone === 'done' ? 'done' : 'story';
  const cat = concept.category_label_fr || concept.localized_category || formatCategory(concept.category);
  // WP-S3 — «Épreuve de la règle», open for every rule from day one (owner,
  // 2026-09-24). Its chrome follows the language rule (learner's language to A2).
  const router = useRouter();
  const forgeChrome = forgeCopy(useChromeLanguage(concept.level));
  const [testOutPending, setTestOutPending] = useState(false);
  const startTestOut = async () => {
    if (testOutPending) return;
    setTestOutPending(true);
    try {
      const started = await api.startForgeTestOut(concept.id);
      await router.push(`/atelier?testout=${started.session_id}`);
    } catch (error) {
      console.error(error);
      toast.error(forgeChrome.test_out_failed_start);
      setTestOutPending(false);
    }
  };

  return (
    <article className="nb-fiche" aria-label={t.grammar.fiche_label}>
      <NbBack label={index ? fill(t.grammar.index_back_n, { n: index }) : t.grammar.index_label} onBack={onBack} />
      <header className="nb-fiche__head">
        <div className="nb-fiche__tags">
          <Chip>{concept.level}</Chip>
          <Chip>{cat}</Chip>
          {due && (
            <Chip icon={<ShapeToken kind="action" size="sm" />}>{t.grammar.chip_due}</Chip>
          )}
        </div>
        <h2 className="av2-headline av2-headline--title" lang="fr">
          {concept.title_fr || concept.display_title || concept.name}
        </h2>
        <div className="nb-fiche__status">
          <ProgressRule value={mastery} max={10} label={t.grammar.mastery} caption={`${mastery} / 10`} />
          <span className="av2-byline">
            <ShapeToken kind={tokenKind} size="sm" />
            <span className="av2-label">{stageLabel(concept, language)}</span>
          </span>
          {missing && <span className="av2-label nb-fiche__missing">{missing}</span>}
          {nextReview && <span className="av2-label">{fill(t.grammar.next_review, { date: nextReview })}</span>}
        </div>
      </header>

      {card && (
        <section className="nb-unit-card" aria-label={t.grammar.sec_rule}>
          <RuleCard card={card} language={cardLanguage} variant="inline" defaultOpen />
        </section>
      )}

      {xray && (
        <Surface as="section" className="nb-sec nb-xray">
          <XraySentence xray={xray} language={cardLanguage} />
        </Surface>
      )}

      {rule && (
        <Surface as="section" className="nb-sec" aria-label={t.grammar.sec_rule}>
          <NbSectionHead t={t.grammar.sec_rule} />
          <p className="av2-fr nb-rule" lang="fr">{rule}</p>
        </Surface>
      )}

      {examples.length > 0 && (
        <Surface as="section" className="nb-sec" aria-label={t.grammar.sec_examples}>
          <NbSectionHead t={t.grammar.sec_examples} n={countLabel(t.grammar, 'examples', examples.length)} />
          {examples.map((ex, i) => <p key={i} className="av2-fr nb-ex" lang="fr">{ex}</p>)}
        </Surface>
      )}

      {traps.length > 0 && (
        <Surface as="section" className="nb-sec" aria-label={t.grammar.sec_traps}>
          <NbSectionHead t={t.grammar.sec_traps} n={countLabel(t.grammar, 'traps', traps.length)} />
          {traps.map((trap, i) => (
            <div className="nb-trap" key={i}><ShapeToken kind="action" size="sm" /><span>{trap}</span></div>
          ))}
        </Surface>
      )}

      {pattern && (
        <Surface as="section" className="nb-sec" aria-label={t.grammar.sec_pattern}>
          <NbSectionHead t={t.grammar.sec_pattern} n={null} />
          <p className="nb-motif">{pattern}</p>
        </Surface>
      )}

      {dueErrata.length > 0 && (
        <Surface as="section" className="nb-sec" aria-label={t.grammar.sec_due_errata}>
          <NbSectionHead t={t.grammar.sec_due_errata} n={countLabel(t.grammar, 'due', dueErrata.length)} />
          <div className="nb-err">
            {dueErrata.map((e, i) => (
              <div className="nb-err__row" key={e.id || i}>
                <ShapeToken kind="action" size="sm" />
                <span className="nb-err__q" lang="fr"><ErratumLine erratum={e} /></span>
                {formatDate(e.next_review_date || e.last_review_date, t.cahier.locale) && (
                  <span className="nb-err__d">{formatDate(e.next_review_date || e.last_review_date, t.cahier.locale)}</span>
                )}
              </div>
            ))}
          </div>
        </Surface>
      )}

      {recentErrata.length > 0 && (
        <Surface as="section" className="nb-sec" aria-label={t.grammar.sec_recent_errata}>
          <NbSectionHead t={t.grammar.sec_recent_errata} n={countLabel(t.grammar, 'repaired', recentErrata.length)} />
          <div className="nb-err">
            {recentErrata.map((e, i) => (
              <div className="nb-err__row" key={e.id || i}>
                <ShapeToken kind="done" size="sm" />
                <span className="nb-err__q" lang="fr"><ErratumLine erratum={e} /></span>
                {formatDate(e.last_review_date, t.cahier.locale) && <span className="nb-err__d">{formatDate(e.last_review_date, t.cahier.locale)}</span>}
              </div>
            ))}
          </div>
        </Surface>
      )}

      <Surface as="section" className="nb-sec" aria-label={t.notes.title}>
        <NbSectionHead t={t.notes.title} />
        {notesEditing ? (
          <>
            <textarea
              className="nb-field"
              value={draftNotes}
              onChange={(event) => onNotesChange(event.target.value)}
              aria-label={t.notes.title}
              readOnly={savingNotes}
            />
            <div className="nb-notes__bar">
              <Action tone="secondary" inline pending={savingNotes} pendingLabel={t.notes.sending} onClick={onNotesSave}>
                {t.notes.save}
              </Action>
              <Action tone="quiet" inline disabled={savingNotes} onClick={onNotesCancel}>
                {t.notes.cancel}
              </Action>
              {notesError ? (
                <span className="nb-notes__state" data-tone="alert">{t.notes.state_failed}</span>
              ) : savingNotes ? (
                <span className="nb-notes__state" data-tone="story">{t.notes.state_saving}</span>
              ) : notesDirty ? (
                <span className="nb-notes__state" data-tone="story">{t.notes.state_dirty}</span>
              ) : (
                <span className="nb-notes__state">{t.notes.state_draft}</span>
              )}
            </div>
            {notesError && (
              <Notice tone="alert" live="alert" shape="action">
                <p>{t.notes.failed}</p>
                <Action tone="secondary" inline onClick={onNotesSave}>{t.cahier.retry}</Action>
              </Notice>
            )}
          </>
        ) : (
          <>
            <p className="nb-notes__text" data-empty={draftNotes ? undefined : 'true'}>
              {draftNotes || t.notes.empty}
            </p>
            <div className="nb-notes__bar">
              <Action tone="secondary" inline onClick={onNotesEdit}>{draftNotes ? t.notes.edit : t.notes.annotate}</Action>
              {draftNotes && <span className="nb-notes__state">{t.notes.saved}</span>}
            </div>
          </>
        )}
      </Surface>

      {/* The handoff has to carry the rule you are reading. Without
        * `concept_id` the Atelier composes the generic séance from the
        * scheduler, so "travailler cette règle" opened a page about something
        * else; /atelier reads this query and posts it as
        * `preferred_concept_id`, which seats the concept as the fragile one.
        * This is the screen's one 3D-press action. */}
      <Link className="av2-btn av2-btn--primary nb-cta" href={`/atelier?mode=practice&concept=${concept.id}`}>
        <span>{t.grammar.cta}</span>
        <ArrowRightIcon size={18} />
      </Link>
      <div className="nb-testout">
        <Action tone="secondary" inline pending={testOutPending} pendingLabel={forgeChrome.test_out_starting} onClick={startTestOut}>
          {forgeChrome.test_out_action}
        </Action>
        <p className="nb-testout__hint">{forgeChrome.test_out_hint}</p>
      </div>
      {/* `exercise_tags` are generator keys ("si", "future", "imperative") —
        * internal inventory, and in English. They steer generation; they are
        * not something to print on the learner's fiche. */}
    </article>
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

function formatDate(value?: string | null, locale?: string) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString(locale, { month: 'short', day: 'numeric' });
}

/* Last-resort category label. `category_label_fr` covers the whole live catalog,
 * so this only fires for a row the catalog has not localised — and when it does,
 * the Cahier still has to speak French. The old map translated the German
 * legacy keys into English ("Verben" → "Verbs"), which put English category
 * chips on a French page. */
function formatCategory(value?: string | null) {
  const raw = String(value || '').trim();
  if (!raw) return 'Grammaire';
  const map: Record<string, string> = {
    ALLGEMEIN: 'Généralités',
    Allgemein: 'Généralités',
    SATZBAU: 'Syntaxe',
    Satzbau: 'Syntaxe',
    VERBEN: 'Verbes',
    Verben: 'Verbes',
    PRONOMEN: 'Pronoms',
    Pronomen: 'Pronoms',
    Agreement: 'Accord',
    Articles: 'Articles',
    Conditionals: 'Conditionnelles',
    Negation: 'Négation',
    Pronouns: 'Pronoms',
    Prepositions: 'Prépositions',
    Questions: 'Interrogation',
    Syntax: 'Syntaxe',
    Tenses: 'Temps',
    Verbs: 'Verbes',
  };
  return map[raw] || raw;
}
