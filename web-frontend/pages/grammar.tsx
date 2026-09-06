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
import api, { AtelierErratum, GrammarNotebookDetail, GrammarNotebookItem } from '@/services/api';

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

/* The design's glyph token: blue circle = en cours, ink square = maîtrisé,
 * red square = fragile or with an erratum due, line circle = à venir. */
function conceptTone(state: GrammarState, due: boolean): ConceptTone {
  if (due || state === 'fragile') return 'fragile';
  if (state === 'mastered') return 'done';
  if (state === 'solid' || state === 'building') return 'progress';
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

function lowerFirst(value: string) {
  return value ? value.charAt(0).toLowerCase() + value.slice(1) : value;
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

/* The direct /grammar and /vocabulary routes carry the same head as the
 * /notebook shell; their pill tabs are links to the sibling registers. */
function standaloneHref(mode: CahierMode) {
  if (mode === 'grammar') return '/grammar';
  if (mode === 'vocabulary') return '/vocabulary';
  return `/notebook?mode=${mode}`;
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

  const chips: CahierChip[] = [
    { id: 'all', label: 'Tous' },
    { id: 'due', label: 'À revoir', count: dueCount },
    ...GRAMMAR_LEVELS.map((lv): CahierChip => ({ id: lv, label: lv })),
  ];
  const activeChip = dueOnly ? 'due' : level === 'all' ? 'all' : level;
  function onChip(id: string) {
    if (id === 'all') { setLevel('all'); setDueOnly(false); }
    else if (id === 'due') { setDueOnly(true); }
    else { setLevel(GRAMMAR_LEVELS.includes(id) ? id : 'all'); setDueOnly(false); }
  }

  const selectedIndex = selected ? concepts.findIndex((c) => c.id === selected.id) : -1;
  const liveText = isLoading
    ? 'Classement en cours…'
    : `${shownConcepts.length} ${shownConcepts.length === 1 ? 'fiche' : 'fiches'}${dueOnly ? ' à revoir' : ''}${totals.recent > 0 ? ` · ${totals.recent} errata ${totals.recent === 1 ? 'récent' : 'récents'}` : ''}`;

  const indexView = (
    <>
      <CahierSearch placeholder="Chercher une règle, un piège…" value={query} onChange={setQuery} />
      <CahierChips chips={chips} active={activeChip} onSelect={onChip} label="Filtrer les règles" />
      <CahierLiveLine text={liveText} clearable={filtersActive} onClear={clearFilters} />
      {notebookError ? (
        <StateBlock
          tone="error"
          title="L’index des règles n’a pas pu être ouvert"
          body="Vos fiches sont en sûreté ; réessayez dans un instant."
          action={{ label: 'Réessayer', onSelect: () => void mutateNotebook() }}
        />
      ) : isLoading ? (
        <div className="nb-list" aria-busy="true">
          {Array.from({ length: 6 }, (_, i) => <Skeleton key={i} height={68} radius={16} />)}
          <span className="av2-sr" role="status">Classement en cours</span>
        </div>
      ) : shownConcepts.length ? (
        <div className="nb-list" role="list" aria-label="Index des règles">
          {shownConcepts.map((concept) => {
            const mastery = Math.round(concept.mastery || 0);
            const due = (concept.due_errata_count || 0) > 0;
            const errata = due ? concept.due_errata_count : concept.recent_errata_count;
            const state = grammarState(concept.state, concept.mastery || 0);
            const tone = conceptTone(state, due);
            const title = concept.title_fr || concept.display_title || concept.name;
            const cat = concept.category_label_fr || concept.localized_category || formatCategory(concept.category);
            const stateLabel = lowerFirst(concept.state_label || '');
            const meta = [
              concept.level,
              cat,
              stateLabel || null,
              due ? 'à revoir' : null,
              !due && errata > 0 ? `${errata} errata` : null,
            ].filter(Boolean).join(' · ');
            return (
              <div key={concept.id} role="listitem">
                <ConceptRow
                  title={title}
                  meta={meta}
                  glyph={conceptGlyph(title, tone)}
                  tone={tone}
                  bars={masteryBars(mastery)}
                  ariaLabel={`${title}, ${concept.level} ${cat}, maîtrise ${mastery} sur 10${due ? ', à revoir' : ''}`}
                  onSelect={() => selectConcept(concept.id)}
                />
              </div>
            );
          })}
        </div>
      ) : filtersActive ? (
        <StateBlock
          tone="empty"
          title="Aucune fiche ne correspond à ce filtre"
          action={{ label: 'Effacer les filtres', onSelect: clearFilters }}
        />
      ) : (
        <StateBlock
          tone="empty"
          title="Le cahier s’ouvre à la première séance"
          body="Vos fiches de grammaire se classent ici dès que l’Atelier compose votre première page."
          action={{ label: 'Ouvrir l’Atelier', onSelect: () => router.push('/atelier') }}
        />
      )}
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
    <div className="nb-fiche">
      <NbBack label="Index des règles" onBack={deselectConcept} />
      <StateBlock
        tone="error"
        title="Cette fiche n’a pas pu être ouverte"
        body="Votre index reste consultable."
        action={{ label: 'Réessayer', onSelect: () => void mutateSelected() }}
      />
    </div>
  ) : (
    <div className="nb-fiche" aria-busy={detailLoading || undefined}>
      <NbBack label="Index des règles" onBack={deselectConcept} />
      <Skeleton height={96} radius={16} />
      <Skeleton height={140} radius={16} />
      <Skeleton height={140} radius={16} />
      <span className="av2-sr" role="status">Ouverture de la fiche</span>
    </div>
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
      <CahierStyles />
      <AtelierV2Root as="main" className="nb-page" aria-label="Le cahier · Règles">
        <CahierHead kicker={isLoading ? 'Les règles' : `${concepts.length} ${concepts.length === 1 ? 'concept' : 'concepts'} · ${totals.started} ${totals.started === 1 ? 'vu' : 'vus'}`}>
          <NotebookModeTabs active="grammar" hrefFor={standaloneHref} />
        </CahierHead>
        <div className="nb-body">{pageContent}</div>
      </AtelierV2Root>
      <PhoneProductNav active="notebook" placement="embedded" />
    </>
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
  const due = (concept.due_errata_count || 0) > 0;
  const state = grammarState(concept.state, concept.mastery || 0);
  const tone = conceptTone(state, due);
  const tokenKind = tone === 'fragile' ? 'action' : tone === 'done' ? 'done' : 'story';
  const cat = concept.category_label_fr || concept.localized_category || formatCategory(concept.category);

  return (
    <article className="nb-fiche" aria-label="Fiche de grammaire">
      <NbBack label={index ? `Index des règles · fiche ${index}` : 'Index des règles'} onBack={onBack} />
      <header className="nb-fiche__head">
        <div className="nb-fiche__tags">
          <Chip>{concept.level}</Chip>
          <Chip>{cat}</Chip>
          {due && (
            <Chip icon={<ShapeToken kind="action" size="sm" />}>À revoir</Chip>
          )}
        </div>
        <h2 className="av2-headline av2-headline--title" lang="fr">
          {concept.title_fr || concept.display_title || concept.name}
        </h2>
        <div className="nb-fiche__status">
          <ProgressRule value={mastery} max={10} label="Maîtrise" caption={`${mastery} / 10`} />
          <span className="av2-byline">
            <ShapeToken kind={tokenKind} size="sm" />
            <span className="av2-label">{concept.state_label}</span>
          </span>
          {nextReview && <span className="av2-label">Prochaine révision · {nextReview}</span>}
        </div>
      </header>

      {rule && (
        <Surface as="section" className="nb-sec" aria-label="La règle">
          <NbSectionHead t="La règle" />
          <p className="av2-fr nb-rule" lang="fr">{rule}</p>
        </Surface>
      )}

      {examples.length > 0 && (
        <Surface as="section" className="nb-sec" aria-label="Exemples d’ancrage">
          <NbSectionHead t="Exemples d’ancrage" n={`${examples.length} ${examples.length === 1 ? 'exemple' : 'exemples'}`} />
          {examples.map((ex, i) => <p key={i} className="av2-fr nb-ex" lang="fr">{ex}</p>)}
        </Surface>
      )}

      {traps.length > 0 && (
        <Surface as="section" className="nb-sec" aria-label="Pièges principaux">
          <NbSectionHead t="Pièges principaux" n={`${traps.length} ${traps.length === 1 ? 'relevé' : 'relevés'}`} />
          {traps.map((t, i) => (
            <div className="nb-trap" key={i}><ShapeToken kind="action" size="sm" /><span>{t}</span></div>
          ))}
        </Surface>
      )}

      {pattern && (
        <Surface as="section" className="nb-sec" aria-label="Motif">
          <NbSectionHead t="Motif" n={Number.isFinite(qualityScore) && qualityScore > 0 ? `gabarit vérifié · qualité ${qualityScore}/5` : null} />
          <p className="nb-motif">{pattern}</p>
        </Surface>
      )}

      {dueErrata.length > 0 && (
        <Surface as="section" className="nb-sec" aria-label="Errata à revoir">
          <NbSectionHead t="Errata à revoir" n={`${dueErrata.length} ${dueErrata.length === 1 ? 'dû' : 'dus'}`} />
          <div className="nb-err">
            {dueErrata.map((e, i) => (
              <div className="nb-err__row" key={e.id || i}>
                <ShapeToken kind="action" size="sm" />
                <span className="nb-err__q" lang="fr"><ErratumLine erratum={e} /></span>
                {formatDate(e.next_review_date || e.last_review_date) && (
                  <span className="nb-err__d">{formatDate(e.next_review_date || e.last_review_date)}</span>
                )}
              </div>
            ))}
          </div>
        </Surface>
      )}

      {recentErrata.length > 0 && (
        <Surface as="section" className="nb-sec" aria-label="Errata récents">
          <NbSectionHead t="Errata récents" n={`${recentErrata.length} ${recentErrata.length === 1 ? 'réparé' : 'réparés'}`} />
          <div className="nb-err">
            {recentErrata.map((e, i) => (
              <div className="nb-err__row" key={e.id || i}>
                <ShapeToken kind="done" size="sm" />
                <span className="nb-err__q" lang="fr"><ErratumLine erratum={e} /></span>
                {formatDate(e.last_review_date) && <span className="nb-err__d">{formatDate(e.last_review_date)}</span>}
              </div>
            ))}
          </div>
        </Surface>
      )}

      <Surface as="section" className="nb-sec" aria-label="Notes en marge">
        <NbSectionHead t="Notes en marge" />
        {notesEditing ? (
          <>
            <textarea
              className="nb-field"
              value={draftNotes}
              onChange={(event) => onNotesChange(event.target.value)}
              aria-label="Notes en marge"
              readOnly={savingNotes}
            />
            <div className="nb-notes__bar">
              <Action tone="secondary" inline pending={savingNotes} pendingLabel="Envoi…" onClick={onNotesSave}>
                Enregistrer
              </Action>
              <Action tone="quiet" inline disabled={savingNotes} onClick={onNotesCancel}>
                Annuler
              </Action>
              {notesError ? (
                <span className="nb-notes__state" data-tone="alert">Échec — note conservée ici</span>
              ) : savingNotes ? (
                <span className="nb-notes__state" data-tone="story">Classement en cours</span>
              ) : notesDirty ? (
                <span className="nb-notes__state" data-tone="story">Non enregistrée</span>
              ) : (
                <span className="nb-notes__state">Brouillon</span>
              )}
            </div>
            {notesError && (
              <Notice tone="alert" live="alert" shape="action">
                <p>La note n’a pas pu être classée. Elle reste dans la marge.</p>
                <Action tone="secondary" inline onClick={onNotesSave}>Réessayer</Action>
              </Notice>
            )}
          </>
        ) : (
          <>
            <p className="nb-notes__text" data-empty={draftNotes ? undefined : 'true'}>
              {draftNotes || 'Aucune note pour l’instant — la marge vous attend.'}
            </p>
            <div className="nb-notes__bar">
              <Action tone="secondary" inline onClick={onNotesEdit}>{draftNotes ? 'Modifier' : 'Annoter'}</Action>
              {draftNotes && <span className="nb-notes__state">Enregistrée</span>}
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
      <Link className="av2-btn av2-btn--primary nb-cta" href={`/atelier?concept_id=${concept.id}`}>
        <span>Travailler cette règle à l’Atelier</span>
        <ArrowRightIcon size={18} />
      </Link>
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
