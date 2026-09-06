import React, { useEffect, useMemo, useState } from 'react';
import Head from 'next/head';
import { useRouter } from 'next/router';
import useSWR from 'swr';
import toast from 'react-hot-toast';

import PhoneProductNav from '@/components/layout/PhoneProductNav';
import {
  CahiersStyles,
  NcMasthead,
  NcFilingSummary,
  NcSearch,
  NcChips,
  NcLiveSum,
  NcLedgerHead,
  NcIndexRow,
  NcSkeleton,
  NcEmpty,
  NcNotice,
  NcColophon,
  NcCrumb,
  NcDueMark,
  NcSec,
  NcExample,
  NcErrRow,
  NcMarginNotes,
  NcCta,
  type NcState,
  type NcChip,
} from '@/components/cahiers/Cahiers';
import api, { AtelierErratum, GrammarNotebookDetail, GrammarNotebookItem } from '@/services/api';

/* Map the backend grammar state (German keys from determine_state, or already
 * localized variants) to the Cahiers stamp palette; fall back to mastery. */
function ncGrammarState(state: string | null | undefined, mastery: number): NcState {
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

const GRAMMAR_LEVELS = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2'];

type GrammarNotebookSurfaceProps = {
  embedded?: boolean;
};

function firstQueryValue(value: string | string[] | undefined) {
  return Array.isArray(value) ? value[0] : value;
}

export default function GrammarNotebookPage() {
  return <GrammarNotebookSurface />;
}

export function GrammarNotebookSurface({ embedded = false }: GrammarNotebookSurfaceProps) {
  const router = useRouter();
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
  } = useSWR<GrammarNotebookItem[]>(
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
    if (selectedId !== null && !concepts.some((concept) => concept.id === selectedId)) {
      setSelectedId(null);
    }
  }, [concepts, router.query.concept, router.query.review, selectedId]);

  function selectConcept(conceptId: number) {
    setSelectedId(conceptId);
    const nextQuery: Record<string, string | string[] | undefined> = { ...router.query, concept: String(conceptId) };
    delete nextQuery.review;
    router.replace({ pathname: router.pathname, query: nextQuery }, undefined, { shallow: true, scroll: false });
    if (typeof window !== 'undefined') window.scrollTo({ top: 0 });
  }

  function deselectConcept() {
    setSelectedId(null);
    const nextQuery: Record<string, string | string[] | undefined> = { ...router.query };
    delete nextQuery.concept;
    delete nextQuery.review;
    router.replace({ pathname: router.pathname, query: nextQuery }, undefined, { shallow: true, scroll: false });
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
  const hasActiveFilters = level !== 'all' || activeSearch.length > 0;

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
      toast.success('Note classée.');
    } catch (error) {
      setNotesError(true);
      toast.error('La note n’a pas pu être classée.');
    } finally {
      setSavingNotes(false);
    }
  }

  const dueCount = useMemo(() => concepts.filter((c) => (c.due_errata_count || 0) > 0).length, [concepts]);
  const shownConcepts = useMemo(
    () => (dueOnly ? concepts.filter((c) => (c.due_errata_count || 0) > 0) : concepts),
    [concepts, dueOnly],
  );
  const filtersActive = level !== 'all' || activeSearch.length > 0 || dueOnly;

  const chips: NcChip[] = [
    { l: 'Toutes', n: level === 'all' && !dueOnly ? concepts.length : null },
    { l: 'À revoir', n: dueCount },
    ...GRAMMAR_LEVELS.map((lv) => ({ l: lv } as NcChip)),
  ];
  const activeChip = dueOnly ? 1 : level === 'all' ? 0 : 2 + GRAMMAR_LEVELS.indexOf(level);
  function onChip(i: number) {
    if (i === 0) { setLevel('all'); setDueOnly(false); }
    else if (i === 1) { setDueOnly(true); }
    else { setLevel(GRAMMAR_LEVELS[i - 2] || 'all'); setDueOnly(false); }
  }

  const selectedIndex = selected ? concepts.findIndex((c) => c.id === selected.id) : -1;

  const indexView = (
    <>
      <NcFilingSummary
        items={[
          { n: concepts.length, label: 'fiches' },
          { n: dueCount, label: 'à revoir', tone: 'due' },
          { n: totals.recent, label: 'errata récents', tone: 'era' },
        ]}
      />
      <NcSearch placeholder="Chercher une règle…" value={query} onChange={setQuery} />
      <NcChips chips={chips} active={activeChip} onSelect={onChip} />
      <NcLiveSum
        text={isLoading ? 'Classement en cours…' : `${shownConcepts.length} ${shownConcepts.length === 1 ? 'fiche' : 'fiches'}${dueOnly ? ' à revoir' : ' dans ce classement'}`}
        clearable={filtersActive}
        onClear={clearFilters}
      />
      {notebookError ? (
        <NcNotice message="L’index des règles n’a pas pu être ouvert. Vos fiches sont en sûreté au bureau des archives." onRetry={() => mutateNotebook()} />
      ) : isLoading ? (
        <NcSkeleton rows={6} />
      ) : shownConcepts.length ? (
        <>
          <NcLedgerHead t="Index des règles" n={`${shownConcepts.length} de ${concepts.length}`} />
          <div className="nc-index" role="list">
            {shownConcepts.map((concept, i) => {
              const errata = (concept.due_errata_count || 0) > 0 ? concept.due_errata_count : concept.recent_errata_count;
              return (
                <NcIndexRow
                  key={concept.id}
                  no={i + 1}
                  title={concept.title_fr || concept.display_title || concept.name}
                  level={concept.level}
                  cat={concept.category_label_fr || concept.localized_category || formatCategory(concept.category)}
                  mastery={Math.round(concept.mastery || 0)}
                  state={ncGrammarState(concept.state, concept.mastery || 0)}
                  stateLabel={concept.state_label}
                  due={(concept.due_errata_count || 0) > 0}
                  errata={errata || 0}
                  onClick={() => selectConcept(concept.id)}
                />
              );
            })}
          </div>
        </>
      ) : filtersActive ? (
        <NcEmpty body="Aucune fiche ne correspond à ce filtre." action="Effacer les filtres" onAction={clearFilters} />
      ) : (
        <NcEmpty
          title="Le cahier s’ouvre à la première séance"
          body="Vos fiches de grammaire se classent ici dès que l’Atelier compose votre première page."
          action="Ouvrir l’Atelier"
          onAction={() => router.push('/atelier')}
        />
      )}
      <NcColophon />
    </>
  );

  const ficheView = selected ? (
    <GrammarFiche
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
    <>
      <NcCrumb label="Index des règles" onBack={deselectConcept} />
      <NcNotice message="Cette fiche n’a pas pu être ouverte. Votre index reste consultable." onRetry={() => mutateSelected()} />
    </>
  ) : (
    <>
      <NcCrumb label="Index des règles" onBack={deselectConcept} />
      <NcSkeleton rows={4} />
    </>
  );

  const pageContent = selectedId ? ficheView : indexView;

  if (embedded) {
    return pageContent;
  }

  return (
    <>
      <Head>
        <title>Le Cahier · Grammaire · L’Atelier</title>
      </Head>
      <CahiersStyles />
      <div className="nc">
        <div className="nc-page">
          <NcMasthead slim route="Grammaire" xlink="Vocabulaire" xlinkHref="/vocabulary" />
          {pageContent}
        </div>
      </div>
      <PhoneProductNav active="notebook" placement="embedded" />
    </>
  );
}

/* ---------- La fiche de grammaire ---------- */
function grammarErrHtml(erratum: AtelierErratum): string {
  const learner = escapeHtml(erratum.learner_text || '');
  const target = escapeHtml(erratum.corrected_target || erratum.display_label || 'corrigé');
  if (learner) return `« <s>${learner}</s> » → <b>${target}</b>`;
  return `<b>${target}</b>`;
}

function GrammarFiche({
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
  concept: GrammarNotebookDetail;
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
  const quality = (concept.blueprint_quality || {}) as Record<string, any>;
  const rule = concept.core_rule || pedagogy.core_rule || '';
  const examples = (concept.anchor_examples?.length ? concept.anchor_examples : arrayFrom(pedagogy.micro_examples || pedagogy.anchor_examples)).slice(0, 3);
  const traps = concept.main_traps?.length ? concept.main_traps : arrayFrom(pedagogy.main_traps);
  const pattern = pedagogy.pattern || '';
  const dueErrata = concept.due_errata || [];
  const recentErrata = concept.recent_errata || [];
  const mastery = Math.round(concept.mastery || 0);
  const nextReview = formatDate(concept.next_review);
  const qualityScore = Number(quality.score ?? quality.quality_score);

  return (
    <>
      <NcCrumb label="Index des règles" index={index ? `Fiche Nº ${String(index).padStart(2, '0')}` : null} onBack={onBack} />
      <header className="nc-entryhead">
        <div className="tags">
          <span className="nc-tagchip lvl"><i />{concept.level}</span>
          <span className="nc-tagchip cat"><i />{concept.category_label_fr || concept.localized_category || formatCategory(concept.category)}</span>
          {(concept.due_errata_count || 0) > 0 && <NcDueMark />}
        </div>
        <h2>{concept.title_fr || concept.display_title || concept.name}</h2>
        <div className="row2">
          <span className="bigpips" aria-label={`Maîtrise ${mastery} sur 10`}>
            {Array.from({ length: 10 }, (_, i) => <i key={i} className={i < mastery ? 'on' : ''} />)}
          </span>
          <span>{concept.state_label}</span>
          {nextReview && <span className="nxt">Prochaine révision · {nextReview}</span>}
        </div>
      </header>

      {rule && (
        <NcSec kick="La règle">
          <p className="nc-rulebox">{rule}</p>
        </NcSec>
      )}

      {examples.length > 0 && (
        <NcSec kick="Exemples d’ancrage" tone="blue" ct={`${examples.length} ${examples.length === 1 ? 'fiche' : 'fiches'}`}>
          {examples.map((ex, i) => <NcExample key={i} fr={escapeHtml(ex)} />)}
        </NcSec>
      )}

      {traps.length > 0 && (
        <NcSec kick="Pièges principaux" ct={`${traps.length} ${traps.length === 1 ? 'relevé' : 'relevés'}`}>
          {traps.map((t, i) => (
            <div className="nc-trap" key={i}><i /><span>{t}</span></div>
          ))}
        </NcSec>
      )}

      {pattern && (
        <NcSec kick="Motif" tone="mut">
          <div className="nc-motif">
            {pattern}
            {Number.isFinite(qualityScore) && qualityScore > 0 && (
              <div className="bp"><span>Gabarit d’exercice</span><b>Vérifié · qualité {qualityScore}/5</b></div>
            )}
          </div>
        </NcSec>
      )}

      {dueErrata.length > 0 && (
        <NcSec kick="Errata — à revoir" ct={`${dueErrata.length} ${dueErrata.length === 1 ? 'du' : 'dus'}`}>
          {dueErrata.map((e, i) => <NcErrRow key={e.id || i} q={grammarErrHtml(e)} d={formatDate(e.next_review_date || e.last_review_date)} />)}
        </NcSec>
      )}

      {recentErrata.length > 0 && (
        <NcSec kick="Errata récents" tone="mut" ct={`${recentErrata.length} ${recentErrata.length === 1 ? 'réparé' : 'réparés'}`}>
          {recentErrata.map((e, i) => <NcErrRow key={e.id || i} recent q={grammarErrHtml(e)} d={formatDate(e.last_review_date)} />)}
        </NcSec>
      )}

      <NcSec kick="Notes en marge" tone="blue">
        <NcMarginNotes
          editing={notesEditing}
          value={draftNotes}
          dirty={notesDirty}
          saving={savingNotes}
          error={notesError}
          onValueChange={onNotesChange}
          onEdit={onNotesEdit}
          onCancel={onNotesCancel}
          onSave={onNotesSave}
          onRetry={onNotesSave}
        />
      </NcSec>

      {/* The handoff has to carry the rule you are reading. Without
        * `concept_id` the Atelier composes the generic séance from the
        * scheduler, so "travailler cette règle" opened a page about something
        * else; /atelier reads this query and posts it as
        * `preferred_concept_id`, which seats the concept as the fragile one. */}
      <NcCta href={`/atelier?concept_id=${concept.id}`}>Travailler cette règle à l’Atelier</NcCta>
      {/* `exercise_tags` are generator keys ("si", "future", "imperative") —
        * internal inventory, and in English. They steer generation; they are
        * not something to print on the learner's fiche. */}
      <NcColophon />
    </>
  );
}

function escapeHtml(value: string): string {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
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
