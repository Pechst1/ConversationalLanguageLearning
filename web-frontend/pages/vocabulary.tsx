import React, { useEffect, useMemo, useState } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { ArrowRight, Loader2, X } from 'lucide-react';
import toast from 'react-hot-toast';

import PhoneProductNav from '@/components/layout/PhoneProductNav';
import { learnerGloss } from '@/lib/glosses';
import {
  CahiersStyles,
  NcMasthead,
  NcFilingSummary,
  NcSearch,
  NcChips,
  NcLiveSum,
  NcLedgerHead,
  NcWordRow,
  NcSkeleton,
  NcEmpty,
  NcNotice,
  NcColophon,
  NcCoverageTrack,
  NcMasteryMap,
  NcIcoFold,
  type NcBucket,
  type NcState,
  type NcChip,
  type NcMapTotal,
} from '@/components/cahiers/Cahiers';
import { ContextAnchor, FragilityBadge, MobileBottomSheet, WordBiographySheet } from '@/components/mobile';
import apiService, {
  CoverageTrack,
  GraphicNovelScene,
  MissionTargetVocabulary,
  RealWorldMission,
  SessionMessage,
  SessionOverview,
  VocabularyEvent,
  VocabularyDueContext,
  VocabularyBiography,
  VocabularyCoverage,
  VocabularyMasteryMap,
  VocabularyRecommendationItem,
  VocabularyWord,
  WeeklyDossier,
} from '@/services/api';
import { AnkiReviewResponse, ReviewResponse } from '@/types/reviews';

type VocabularyDetail =
  | { kind: 'queue'; item: VocabularyRecommendationItem }
  | { kind: 'deck'; item: VocabularyWord };

const vocabularyFilters = ['all', 'new', 'due', 'fragile', 'building', 'solid', 'mastered'] as const;
type VocabularyFilter = typeof vocabularyFilters[number];

type VocabularyProgressDetail = {
  word_id: number;
  state: string;
  stability?: number | null;
  difficulty?: number | null;
  scheduled_days?: number | null;
  next_review?: string | null;
  last_review?: string | null;
  reps: number;
  lapses: number;
  correct_count: number;
  incorrect_count: number;
  hint_count: number;
  proficiency_score: number;
  reviews_logged: number;
};

type DetailExample = {
  source: string;
  label: string;
  text: string;
  translation?: string | null;
  meta?: string | null;
};

type DetailTrace = {
  source: string;
  label: string;
  description: string;
  date?: string | null;
  href?: string;
};

type DetailSupport = {
  word: VocabularyWord | null;
  progress: VocabularyProgressDetail | null;
  examples: DetailExample[];
  traces: DetailTrace[];
  loading: boolean;
};

type Settled<T> =
  | { status: 'fulfilled'; value: T }
  | { status: 'rejected'; reason: unknown };

const emptyDetailSupport: DetailSupport = {
  word: null,
  progress: null,
  examples: [],
  traces: [],
  loading: false,
};

const reviewOptions = [
  { rating: 0, label: 'À revoir', hint: 'Très bientôt', tone: 'red' },
  { rating: 1, label: 'Difficile', hint: 'Garder près', tone: 'yellow' },
  { rating: 2, label: 'Correct', hint: 'Rythme normal', tone: 'blue' },
  { rating: 3, label: 'Facile', hint: 'Espacer', tone: 'black' },
] as const;

function reviewMessage(response: ReviewResponse | AnkiReviewResponse) {
  const next = 'due_at' in response ? response.due_at || response.next_review : response.next_review;
  const date = next ? new Date(next) : null;
  const label = date && !Number.isNaN(date.getTime())
    ? date.toLocaleDateString('fr-FR', { month: 'long', day: 'numeric' })
    : '';
  return label ? `Reprise le ${label}` : 'Reprise classée';
}

function queueItems(context: VocabularyDueContext | null) {
  if (!context) return [];
  const seen = new Set<number>();
  return [
    ...context.due_words,
    ...context.fragile_words,
    ...context.linked_words,
    ...context.topic_compatible_words,
    ...context.new_words,
  ].filter((item) => {
    if (seen.has(item.word_id)) return false;
    seen.add(item.word_id);
    return true;
  });
}

function ncQueueBucket(bucket?: string | null): NcBucket | null {
  if (bucket === 'due') return { id: 'due', label: 'À revoir' };
  if (bucket === 'fragile') return { id: 'fragile', label: 'Fragile' };
  if (bucket === 'new') return { id: 'new', label: 'Nouveau' };
  return null;
}

function ncDeckState(masteryState?: string | null): { state: NcState; label: string } {
  switch (masteryState) {
    case 'mastered': return { state: 'mastered', label: 'Acquis' };
    case 'solid': return { state: 'solid', label: 'Solide' };
    case 'building': return { state: 'building', label: 'En cours' };
    case 'fragile': return { state: 'fragile', label: 'Fragile' };
    case 'due': return { state: 'fragile', label: 'À revoir' };
    default: return { state: 'new', label: 'Nouveau' };
  }
}

function queueWord(item: VocabularyRecommendationItem) {
  if (item.direction === 'de_to_fr') {
    return learnerGloss(item, item.word);
  }
  return item.word || item.translations?.fr || '';
}

function queueTranslation(item: VocabularyRecommendationItem) {
  if (item.direction === 'de_to_fr') {
    return item.translations?.fr || item.word || '';
  }
  return learnerGloss(item);
}

function queueDirection(item: VocabularyRecommendationItem) {
  if (item.direction === 'fr_to_de') return 'FR → DE';
  if (item.direction === 'de_to_fr') return 'DE → FR';
  return 'Français 5000';
}

/* The registre used to read `german_translation` first and so served German to
 * every learner regardless of the language they signed up in — the exact bug
 * lib/glosses.ts was written to end. `/vocabulary/` now resolves the gloss for
 * the signed-in learner and sends it as `translation`; trust that field, and
 * only fall back for a payload that predates it. */
function deckTranslation(item: VocabularyWord) {
  return learnerGloss(item) || item.definition || '';
}

function detailWord(detail: VocabularyDetail) {
  return detail.kind === 'queue' ? queueWord(detail.item) : detail.item.word;
}

function detailTranslation(detail: VocabularyDetail) {
  return detail.kind === 'queue' ? queueTranslation(detail.item) : deckTranslation(detail.item);
}

function detailExample(detail: VocabularyDetail) {
  return detail.kind === 'queue' ? detail.item.example_sentence : detail.item.example_sentence;
}

function detailWordId(detail: VocabularyDetail) {
  return detail.kind === 'queue' ? detail.item.word_id : detail.item.id;
}

function detailFrench(detail: VocabularyDetail) {
  if (detail.kind === 'queue') {
    return detail.item.direction === 'de_to_fr'
      ? detail.item.translations?.fr || detail.item.word
      : detail.item.word || detail.item.translations?.fr || '';
  }
  return detail.item.language === 'fr'
    ? detail.item.word
    : detail.item.french_translation || detail.item.word;
}

function detailMeaningForPractice(detail: VocabularyDetail) {
  if (detail.kind === 'queue') return queueTranslation(detail.item);
  return detail.item.german_translation || detail.item.english_translation || detail.item.definition || '';
}

function parseWordQuery(value: string | string[] | undefined) {
  const raw = Array.isArray(value) ? value[0] : value;
  if (!raw) return null;
  const parsed = Number(raw);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
}

function quietConfig() {
  return { suppressGlobalError: true } as any;
}

function optionalStringField(source: unknown, key: string) {
  if (!source || typeof source !== 'object') return null;
  const value = (source as Record<string, unknown>)[key];
  return typeof value === 'string' ? value : null;
}

function formatDateLabel(value?: string | null) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

function formatShortDate(value?: string | null) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

function formatDays(value?: number | null) {
  if (value === null || value === undefined) return '';
  return `${value} ${value === 1 ? 'day' : 'days'}`;
}

function formatDecimal(value?: number | null, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(value)) return '';
  return value.toFixed(digits);
}

function formatPercent(value?: number | null) {
  if (value === null || value === undefined || Number.isNaN(value)) return '';
  const normalized = value > 1 ? value : value * 100;
  return `${Math.round(normalized)}%`;
}

function trimSnippet(value?: string | null, max = 140) {
  const text = (value || '').replace(/\s+/g, ' ').trim();
  if (!text) return '';
  return text.length > max ? `${text.slice(0, max - 3).trim()}...` : text;
}

/* Bucket keys are scheduler internals; the Cahier prints the French name of the
 * pile a word is sitting in, never the raw key. */
function humanBucket(value?: string | null) {
  const labels: Record<string, string> = {
    due: 'à revoir',
    fragile: 'fragile',
    new: 'nouveau',
    topic_compatible: 'dans le thème',
    linked: 'lié à l’épisode',
  };
  if (!value) return 'à revoir';
  return labels[value] || value.replace(/_/g, ' ');
}

function humanEvent(value?: string | null) {
  if (!value) return 'Rencontré en pratique';
  const labels: Record<string, string> = {
    seen_context: 'Vu en contexte',
    recognized: 'Reconnu',
    produced_correct: 'Produit juste',
    produced_incorrect: 'Produit puis réparé',
    missed_target: 'Cible manquée',
  };
  return labels[value] || value.replace(/_/g, ' ');
}

/* The part-of-speech column on the imported deck was written by the enrichment
 * heuristics (scripts/enrich_vocabulary.py), not by a lexical source, and it is
 * wrong often enough to notice — `élire` and `approcher` are filed as
 * adjective/noun. It is also stored as an English machine key ("noun"), and a
 * few rows hold "x" or nothing at all. So: print a French label when the value
 * is one we recognise, and print nothing when it is junk, rather than stamping
 * a guess onto the learner's page as if it were a fact. */
const PART_OF_SPEECH_LABELS: Record<string, string> = {
  noun: 'nom',
  verb: 'verbe',
  adjective: 'adjectif',
  adverb: 'adverbe',
  pronoun: 'pronom',
  preposition: 'préposition',
  determiner: 'déterminant',
  conjunction: 'conjonction',
  interjection: 'interjection',
  number: 'numéral',
};

function partOfSpeechLabel(value?: string | null) {
  const key = String(value || '').trim().toLowerCase();
  return PART_OF_SPEECH_LABELS[key] || '';
}

function plural(n: number, one: string, many: string) {
  return `${n} ${n === 1 ? one : many}`;
}

/* FSRS card states, as the Cahier says them. */
const SRS_STATE_LABELS: Record<string, string> = {
  new: 'Nouveau',
  learning: 'En apprentissage',
  review: 'En révision',
  reviewing: 'En révision',
  relearning: 'À reprendre',
};

function srsStateLabel(value?: string | null) {
  const key = String(value || '').trim().toLowerCase();
  return SRS_STATE_LABELS[key] || 'Nouveau';
}

function detailQueueItem(detail: VocabularyDetail) {
  return detail.kind === 'queue' ? detail.item : null;
}

function detailDeckWord(detail: VocabularyDetail, supportWord?: VocabularyWord | null) {
  return detail.kind === 'deck' ? detail.item : supportWord || null;
}

function detailFrequencyRank(detail: VocabularyDetail, supportWord?: VocabularyWord | null) {
  const word = detailDeckWord(detail, supportWord);
  return word?.frequency_rank || null;
}

function detailPartOfSpeech(detail: VocabularyDetail, supportWord?: VocabularyWord | null) {
  const word = detailDeckWord(detail, supportWord);
  // Was `|| 'French'`, which printed "French" under the heading "part of
  // speech". An unknown value gets the same em dash as every other blank.
  return partOfSpeechLabel(word?.part_of_speech);
}

function detailDifficulty(detail: VocabularyDetail, supportWord?: VocabularyWord | null) {
  const word = detailDeckWord(detail, supportWord);
  return word?.difficulty_level || null;
}

function addUniqueExample(examples: DetailExample[], next: DetailExample) {
  const text = trimSnippet(next.text, 260);
  if (!text) return;
  const duplicate = examples.some((item) => item.source === next.source && trimSnippet(item.text, 260) === text);
  if (!duplicate) {
    examples.push({ ...next, text });
  }
}

function targetVocabularyForWord(items: MissionTargetVocabulary[] | undefined, wordId: number) {
  return (items || []).find((item) => item.word_id === wordId) || null;
}

function entityTargetsWord(
  entity: Pick<RealWorldMission | GraphicNovelScene, 'target_vocabulary_ids' | 'target_vocabulary'>,
  wordId: number,
) {
  return (entity.target_vocabulary_ids || []).includes(wordId)
    || Boolean(targetVocabularyForWord(entity.target_vocabulary, wordId));
}

function vocabularyEventsFromRecord(record: Record<string, any> | undefined | null): VocabularyEvent[] {
  const correction = record?.correction || record?.correction_payload;
  const events = correction?.vocabulary_events;
  return Array.isArray(events) ? events : [];
}

function messageReferencesWord(message: SessionMessage, wordId: number) {
  return (message.target_words || []).includes(wordId)
    || (message.words_used || []).includes(wordId)
    || (message.suggested_words_used || []).includes(wordId)
    || (message.target_details || []).some((item) => item.word_id === wordId)
    || (message.learning_focus || []).some((item) => Number(item.metadata?.word_id) === wordId);
}

function messageReferenceDescription(message: SessionMessage, wordId: number) {
  const bits = [];
  if ((message.target_words || []).includes(wordId)) bits.push('visé');
  if ((message.words_used || []).includes(wordId)) bits.push('employé');
  if ((message.suggested_words_used || []).includes(wordId)) bits.push('suggéré');
  if ((message.target_details || []).some((item) => item.word_id === wordId)) bits.push('prévu');
  return bits.length ? `En conversation : ${bits.join(', ')}` : 'Passage de conversation';
}

function entityDate(entity: Pick<RealWorldMission | GraphicNovelScene, 'completed_at' | 'started_at' | 'created_at'>) {
  return entity.completed_at || entity.started_at || entity.created_at || null;
}

function traceKey(trace: DetailTrace) {
  return [trace.source, trace.label, trace.description, trace.date].filter(Boolean).join('|');
}

function settle<T>(promise: Promise<T>): Promise<Settled<T>> {
  return promise.then(
    (value) => ({ status: 'fulfilled', value }),
    (reason) => ({ status: 'rejected', reason }),
  );
}

function groupExamples(detail: VocabularyDetail, support: DetailSupport) {
  const examples: DetailExample[] = [];
  const word = detailDeckWord(detail, support.word);
  const queueItem = detailQueueItem(detail);
  addUniqueExample(examples, {
    source: 'Français 5000',
    label: 'Exemple',
    text: detailExample(detail) || '',
    translation: queueItem?.example_translation || word?.example_translation,
  });
  addUniqueExample(examples, {
    source: 'Français 5000',
    label: 'Définition',
    text: word?.definition || '',
    meta: word?.part_of_speech || null,
  });
  addUniqueExample(examples, {
    source: 'Français 5000',
    label: 'Notes d’usage',
    text: word?.usage_notes || '',
  });
  support.examples.forEach((item) => addUniqueExample(examples, item));

  const groups = new Map<string, DetailExample[]>();
  examples.forEach((item) => {
    const current = groups.get(item.source) || [];
    current.push(item);
    groups.set(item.source, current);
  });
  return Array.from(groups.entries()).map(([source, entries]) => ({ source, entries }));
}

function srsRows(detail: VocabularyDetail, support: DetailSupport) {
  const queueItem = detailQueueItem(detail);
  const progress = support.progress;
  const dueAt = queueItem?.due_at || progress?.next_review || queueItem?.next_review || null;
  const lastReview = optionalStringField(queueItem, 'last_review') || progress?.last_review || null;
  const interval = queueItem?.interval_days ?? queueItem?.scheduled_days ?? progress?.scheduled_days;
  // The scheduler's own working numbers — stability, difficulty,
  // retrievability, priority score, the scheduler's name — are corrector
  // internals. They told the learner nothing they could act on and read as a
  // debug panel bolted to the bottom of a notebook page. What stays is the part
  // of the record a learner can actually recognise: where the word stands, when
  // it comes back, and how often they have met it.
  return [
    { label: 'État', value: srsStateLabel(progress?.state || queueItem?.state) },
    { label: 'Prochaine reprise', value: formatDateLabel(dueAt) || 'Non programmée' },
    { label: 'Dernière reprise', value: formatDateLabel(lastReview) || 'Jamais revu' },
    { label: 'Intervalle', value: formatDays(interval) || 'Carte neuve' },
    { label: 'Reprises', value: String(progress?.reviews_logged ?? progress?.reps ?? 0) },
    { label: 'Oublis', value: String(progress?.lapses ?? queueItem?.lapses ?? 0) },
  ];
}

async function fetchVocabularyUsageSupport(wordId: number) {
  const examples: DetailExample[] = [];
  const traces: DetailTrace[] = [];

  const [missionsResult, feuilletonResult, sessionsResult] = await Promise.all([
    settle(apiService.getMissionsToday()),
    settle(apiService.getGraphicNovelToday()),
    settle(apiService.getSessions({ limit: 6, offset: 0 })),
  ]);

  if (missionsResult.status === 'fulfilled') {
    const missionItems = [
      missionsResult.value.active_mission,
      missionsResult.value.weekly_mission,
      missionsResult.value.post_session_recommendation,
      ...(missionsResult.value.recent_completed || []),
    ].filter(Boolean) as RealWorldMission[];

    missionItems.forEach((mission) => {
      const target = targetVocabularyForWord(mission.target_vocabulary, wordId);
      const events = [
        ...(mission.attempts || []).flatMap((item) => vocabularyEventsFromRecord(item)),
        ...(mission.turns || []).flatMap((item) => vocabularyEventsFromRecord(item)),
      ].filter((event) => event.word_id === wordId);

      if (entityTargetsWord(mission, wordId)) {
        traces.push({
          source: 'Mission',
          label: mission.title || 'Mission',
          description: `Targeted in ${humanBucket(mission.status)} mission`,
          date: entityDate(mission),
          href: `/missions?mission=${mission.id}`,
        });
      }
      if (target?.example_sentence) {
        addUniqueExample(examples, {
          source: 'Mission',
          label: mission.title || 'Consigne de mission',
          text: target.example_sentence,
          translation: target.example_translation || target.translation,
          meta: mission.status,
        });
      }
      events.slice(0, 3).forEach((event) => {
        traces.push({
          source: 'Mission',
          label: mission.title || 'Mission',
          description: [humanEvent(event.event_type), event.reason].filter(Boolean).join(' · '),
          date: entityDate(mission),
          href: `/missions?mission=${mission.id}`,
        });
      });
    });
  }

  if (feuilletonResult.status === 'fulfilled') {
    const sceneItems = [
      feuilletonResult.value.active_scene,
      feuilletonResult.value.available_scene,
      ...(feuilletonResult.value.recent_completed || []),
    ].filter(Boolean) as GraphicNovelScene[];

    sceneItems.forEach((scene) => {
      const target = targetVocabularyForWord(scene.target_vocabulary, wordId);
      const events = (scene.attempts || [])
        .flatMap((item) => vocabularyEventsFromRecord(item))
        .filter((event) => event.word_id === wordId);

      if (entityTargetsWord(scene, wordId)) {
        traces.push({
          source: 'Feuilleton',
          label: scene.title || 'Feuilleton',
          description: `Targeted in ${humanBucket(scene.status)} scene`,
          date: entityDate(scene),
          href: `/graphic-novel?scene=${scene.id}`,
        });
      }
      if (target?.example_sentence) {
        addUniqueExample(examples, {
          source: 'Feuilleton',
          label: scene.title || 'Scène du feuilleton',
          text: target.example_sentence,
          translation: target.example_translation || target.translation,
          meta: scene.status,
        });
      }
      events.slice(0, 3).forEach((event) => {
        traces.push({
          source: 'Feuilleton',
          label: scene.title || 'Feuilleton',
          description: [humanEvent(event.event_type), event.reason].filter(Boolean).join(' · '),
          date: entityDate(scene),
          href: `/graphic-novel?scene=${scene.id}`,
        });
      });
    });
  }

  if (sessionsResult.status === 'fulfilled') {
    const sessions = (sessionsResult.value || []) as SessionOverview[];
    const messageResults = await Promise.all(
      sessions.slice(0, 5).map((session) => settle(apiService.getSessionMessages(session.id, { limit: 12, offset: 0 }))),
    );
    messageResults.forEach((result, index) => {
      if (result.status !== 'fulfilled') return;
      const session = sessions[index];
      const match = result.value.items.find((message) => messageReferencesWord(message, wordId));
      if (!match) return;
      traces.push({
        source: 'Séance',
        label: session.topic || 'Conversation',
        description: messageReferenceDescription(match, wordId),
        date: match.created_at || session.started_at,
        href: `/learn/session/${session.id}`,
      });
      const target = (match.target_details || []).find((item) => item.word_id === wordId);
      if (target?.hint_sentence) {
        addUniqueExample(examples, {
          source: 'Séance',
          label: session.topic || 'Conversation',
          text: target.hint_sentence,
          translation: target.hint_translation || target.translation,
          meta: target.familiarity || null,
        });
      } else {
        addUniqueExample(examples, {
          source: 'Séance',
          label: match.sender === 'user' ? 'Votre tour' : 'La réponse',
          text: trimSnippet(match.content, 180),
          meta: session.topic || null,
        });
      }
    });
  }

  const seen = new Set<string>();
  return {
    examples,
    traces: traces.filter((trace) => {
      const key = traceKey(trace);
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    }).slice(0, 8),
  };
}

type CoverageTotals = { nailed: number; total: number };

function sumCoverage(items: Array<{ nailed?: number; total?: number }>): CoverageTotals {
  return items.reduce<CoverageTotals>(
    (totals, item) => ({
      nailed: totals.nailed + Number(item.nailed || 0),
      total: totals.total + Number(item.total || 0),
    }),
    { nailed: 0, total: 0 }
  );
}

interface VocabularyPageProps {
  embedded?: boolean;
}

export default function VocabularyPage({ embedded = false }: VocabularyPageProps = {}) {
  const router = useRouter();
  const [context, setContext] = useState<VocabularyDueContext | null>(null);
  const [deck, setDeck] = useState<VocabularyWord[]>([]);
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState<VocabularyFilter>('all');
  const [detail, setDetail] = useState<VocabularyDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [deckLoading, setDeckLoading] = useState(true);
  const [contextError, setContextError] = useState<string | null>(null);
  const [deckError, setDeckError] = useState<string | null>(null);
  const [contextRetry, setContextRetry] = useState(0);
  const [deckRetry, setDeckRetry] = useState(0);
  const [reviewing, setReviewing] = useState(false);
  const [action, setAction] = useState<'mission' | 'feuilleton' | null>(null);
  const [practiceRevealed, setPracticeRevealed] = useState(false);
  const [detailSupport, setDetailSupport] = useState<DetailSupport>(emptyDetailSupport);
  const [weeklyDossier, setWeeklyDossier] = useState<WeeklyDossier | null>(null);
  const [masteryMap, setMasteryMap] = useState<VocabularyMasteryMap | null>(null);
  const [coverage, setCoverage] = useState<VocabularyCoverage | null>(null);
  const [atlasOpen, setAtlasOpen] = useState(false);
  const [biographyWordId, setBiographyWordId] = useState<number | null>(null);
  const [biography, setBiography] = useState<VocabularyBiography | null>(null);
  const [biographyLoading, setBiographyLoading] = useState(false);
  const [biographyError, setBiographyError] = useState<string | null>(null);

  const refreshNotebookMirror = async () => {
    const [dossierResult, mapResult, coverageResult] = await Promise.all([
      settle(apiService.getWeeklyDossier({ period_days: 7 })),
      settle(apiService.getVocabularyMasteryMap({ limit: 5000, direction: 'fr_to_de' })),
      settle(apiService.getVocabularyCoverage()),
    ]);
    if (dossierResult.status === 'fulfilled') setWeeklyDossier(dossierResult.value);
    if (mapResult.status === 'fulfilled') setMasteryMap(mapResult.value);
    if (coverageResult.status === 'fulfilled') setCoverage(coverageResult.value);
  };

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setContextError(null);
    Promise.all([
      settle(apiService.getVocabularyDueContext({
        limit: 18,
        due_limit: 6,
        fragile_limit: 6,
        new_limit: 6,
        topic_limit: 4,
        linked_limit: 4,
        direction: 'fr_to_de',
      })),
      settle(apiService.getWeeklyDossier({ period_days: 7 })),
      settle(apiService.getVocabularyMasteryMap({ limit: 5000, direction: 'fr_to_de' })),
      settle(apiService.getVocabularyCoverage()),
    ])
      .then(([contextResult, dossierResult, mapResult, coverageResult]) => {
        if (!alive) return;
        if (contextResult.status === 'fulfilled') {
          setContext(contextResult.value);
          setContextError(null);
        } else {
          setContext(null);
          setContextError('Le cahier de vocabulaire n’a pas pu être ouvert.');
        }
        if (dossierResult.status === 'fulfilled') setWeeklyDossier(dossierResult.value);
        if (mapResult.status === 'fulfilled') setMasteryMap(mapResult.value);
        if (coverageResult.status === 'fulfilled') setCoverage(coverageResult.value);
      })
      .catch((error) => {
        console.error(error);
        if (alive) {
          setContext(null);
          setContextError('Le cahier de vocabulaire n’a pas pu être ouvert.');
        }
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [contextRetry]);

  useEffect(() => {
    let alive = true;
    const search = query.trim();
    const timeout = window.setTimeout(() => {
      setDeckLoading(true);
      setDeckError(null);
      apiService.getVocabulary({
        language: 'fr',
        limit: 80,
        offset: 0,
        search: search || undefined,
      })
        .then((nextDeck) => {
          if (!alive) return;
          setDeck(nextDeck.items || []);
        })
        .catch((error) => {
          console.error(error);
          if (alive) {
            setDeck([]);
            setDeckError('Le registre des mots n’a pas répondu.');
          }
        })
        .finally(() => {
          if (alive) setDeckLoading(false);
        });
    }, search ? 220 : 0);
    return () => {
      alive = false;
      window.clearTimeout(timeout);
    };
  }, [query, deckRetry]);

  useEffect(() => {
    setPracticeRevealed(false);
  }, [detail]);

  const todayItems = useMemo(() => {
    const items = queueItems(context);
    if (filter === 'all') return items;
    if (filter === 'due' || filter === 'fragile' || filter === 'new') {
      return items.filter((item) => item.bucket === filter);
    }
    return [];
  }, [context, filter]);

  const masteryCells = useMemo(() => masteryMap?.cells || [], [masteryMap]);
  const masteryByWordId = useMemo(() => {
    return new Map(masteryCells.map((cell) => [cell.word_id, cell]));
  }, [masteryCells]);

  const filteredDeck = useMemo(() => {
    return deck
      .filter((item) => {
        if (filter === 'all') return true;
        const state = masteryByWordId.get(item.id)?.mastery_state;
        return state === filter;
      })
      .slice(0, 36);
  }, [deck, filter, masteryByWordId]);

  useEffect(() => {
    if (!detail) {
      setDetailSupport(emptyDetailSupport);
      return;
    }

    let alive = true;
    const wordId = detailWordId(detail);
    const baseWord = detail.kind === 'deck' ? detail.item : null;
    setDetailSupport({
      word: baseWord,
      progress: null,
      examples: [],
      traces: [],
      loading: true,
    });

    Promise.all([
      settle(apiService.get<VocabularyProgressDetail>(`/progress/${wordId}`, quietConfig())),
      settle(baseWord ? Promise.resolve(baseWord) : apiService.getVocabularyItem(wordId)),
      settle(fetchVocabularyUsageSupport(wordId)),
    ])
      .then(([progressResult, wordResult, usageResult]) => {
        if (!alive) return;
        setDetailSupport({
          word: wordResult.status === 'fulfilled' ? wordResult.value : baseWord,
          progress: progressResult.status === 'fulfilled' ? progressResult.value : null,
          examples: usageResult.status === 'fulfilled' ? usageResult.value.examples : [],
          traces: usageResult.status === 'fulfilled' ? usageResult.value.traces : [],
          loading: false,
        });
      })
      .catch((error) => {
        console.error(error);
        if (alive) {
          setDetailSupport((current) => ({ ...current, loading: false }));
        }
      });

    return () => {
      alive = false;
    };
  }, [detail]);

  useEffect(() => {
    if (!router.isReady) return;
    const wordId = parseWordQuery(router.query.word);
    if (!wordId) return;
    if (detail && detailWordId(detail) === wordId) return;

    const queueMatch = queueItems(context).find((item) => item.word_id === wordId);
    if (queueMatch) {
      setDetail({ kind: 'queue', item: queueMatch });
      return;
    }

    const deckMatch = deck.find((item) => item.id === wordId);
    if (deckMatch) {
      setDetail({ kind: 'deck', item: deckMatch });
      return;
    }

    let alive = true;
    apiService.getVocabularyItem(wordId)
      .then((item) => {
        if (alive) setDetail({ kind: 'deck', item });
      })
      .catch((error) => {
        console.error(error);
        if (alive) toast.error('Ce mot n’a pas pu être ouvert.');
      });
    return () => {
      alive = false;
    };
  }, [router.isReady, router.query.word, context, deck, detail]);

  useEffect(() => {
    if (!biographyWordId) {
      setBiography(null);
      setBiographyError(null);
      setBiographyLoading(false);
      return;
    }

    let alive = true;
    setBiographyLoading(true);
    setBiographyError(null);
    apiService.getVocabularyBiography(biographyWordId)
      .then((nextBiography) => {
        if (!alive) return;
        setBiography(nextBiography);
      })
      .catch((error) => {
        console.error(error);
        if (!alive) return;
        setBiography(null);
        setBiographyError('La biographie de ce mot n’a pas pu être ouverte.');
      })
      .finally(() => {
        if (alive) setBiographyLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [biographyWordId]);

  const openDetail = (nextDetail: VocabularyDetail) => {
    setDetail(nextDetail);
    const wordId = detailWordId(nextDetail);
    if (parseWordQuery(router.query.word) === wordId) return;
    void router.replace(
      { pathname: router.pathname, query: { ...router.query, word: String(wordId) } },
      undefined,
      { shallow: true, scroll: false },
    );
  };

  const closeDetail = () => {
    setDetail(null);
    setBiographyWordId(null);
    const nextQuery = { ...router.query };
    delete nextQuery.word;
    void router.replace(
      { pathname: router.pathname, query: nextQuery },
      undefined,
      { shallow: true, scroll: false },
    );
  };

  const openBiography = () => {
    if (!detail) return;
    setBiographyWordId(detailWordId(detail));
  };

  const review = async (rating: number) => {
    if (!detail) return;
    setReviewing(true);
    try {
      const response = await apiService.submitAnkiReview({ word_id: detailWordId(detail), rating });
      toast.success(reviewMessage(response));
      closeDetail();
      const nextContext = await apiService.getVocabularyDueContext({
        limit: 18,
        due_limit: 6,
        fragile_limit: 6,
        new_limit: 6,
        direction: 'fr_to_de',
      });
      setContext(nextContext);
      await refreshNotebookMirror();
    } catch (error) {
      console.error(error);
      toast.error('La reprise n’a pas pu être classée.');
    } finally {
      setReviewing(false);
    }
  };

  const createMission = async () => {
    if (!detail) return;
    setAction('mission');
    try {
      const mission = await apiService.createMission({
        mission_type: 'message',
        cadence: 'ad_hoc',
        preferred_vocabulary_ids: [detailWordId(detail)],
        use_news: false,
      });
      await router.push(`/missions?mission=${mission.id}`);
    } catch (error) {
      console.error(error);
      toast.error('La mission n’a pas pu être composée.');
    } finally {
      setAction(null);
    }
  };

  const createFeuilleton = async () => {
    if (!detail) return;
    setAction('feuilleton');
    try {
      const scene = await apiService.createGraphicNovelScene({
        cadence: 'ad_hoc',
        target_vocabulary_ids: [detailWordId(detail)],
        use_news: true,
        panel_count: 4,
        story_quality: 'standard',
        experience_mode: 'study',
        render_mode: 'panels',
        image_quality: 'low',
        force_new: true,
      });
      await router.push(`/graphic-novel?scene=${scene.id}`);
    } catch (error) {
      console.error(error);
      toast.error('L’épisode n’a pas pu être composé.');
    } finally {
      setAction(null);
    }
  };

  const summary = context?.summary;
  const detailExampleGroups = detail ? groupExamples(detail, detailSupport) : [];
  const detailSrsRows = detail ? srsRows(detail, detailSupport) : [];
  const detailRank = detail ? detailFrequencyRank(detail, detailSupport.word) : null;
  const detailSpeech = detail ? detailPartOfSpeech(detail, detailSupport.word) : '';
  const detailLevel = detail ? detailDifficulty(detail, detailSupport.word) : null;
  const activeVocabularySearch = query.trim();
  const hasVocabularyFilters = filter !== 'all' || activeVocabularySearch.length > 0;
  const cefrTotals = coverage ? sumCoverage(coverage.cefr_bar || []) : { nailed: 0, total: 0 };
  const topicCats = (coverage?.categories || [])
    .filter((track) => !['uncategorized', 'adjectives_adverbs', 'function_words'].includes(track.id))
    .slice(0, 6);
  const verbSummary = sumCoverage(coverage?.verb_tracks || []);

  function clearVocabularyFilters() {
    setFilter('all');
    setQuery('');
  }

  const vocabChipFilters: VocabularyFilter[] = ['all', 'due', 'fragile', 'new', 'mastered'];
  const vocabChips: NcChip[] = [
    { l: 'Tous', n: null },
    { l: 'À revoir', n: summary?.due ?? null },
    { l: 'Fragiles', n: summary?.fragile ?? null },
    { l: 'Nouveaux', n: summary?.new ?? null },
    { l: 'Acquis', n: null },
  ];
  const activeVocabChip = Math.max(0, vocabChipFilters.indexOf(filter));

  const ncMapCellClasses = masteryCells.slice(0, 280).map((cell) => (cell.mastery_state === 'new' ? '' : cell.mastery_state));
  const ncMapTotals: NcMapTotal[] = masteryMap
    ? [
        { id: 'due', label: 'À revoir', n: masteryMap.summary.due || 0 },
        { id: 'fragile', label: 'Fragiles', n: masteryMap.summary.fragile || 0 },
        { id: 'building', label: 'En cours', n: masteryMap.summary.building || 0 },
        { id: 'solid', label: 'Solides', n: masteryMap.summary.solid || 0 },
        { id: 'mastered', label: 'Acquis', n: masteryMap.summary.mastered || 0 },
        { id: '', label: 'Nouveaux', n: masteryMap.summary.new || 0 },
      ]
    : [];

  const filterFr = (value: VocabularyFilter): string => {
    switch (value) {
      case 'due': return 'à revoir';
      case 'fragile': return 'fragiles';
      case 'new': return 'nouveaux';
      case 'building': return 'en cours';
      case 'solid': return 'solides';
      case 'mastered': return 'acquis';
      default: return 'tout le registre';
    }
  };

  const landing = (
    <>
      <NcFilingSummary
        items={[
          { n: summary?.due ?? 0, label: 'à revoir', tone: 'due' },
          { n: summary?.fragile ?? 0, label: 'fragiles', tone: 'due' },
          { n: summary?.new ?? 0, label: 'nouveaux' },
        ]}
      />
      <NcSearch placeholder="Chercher un mot…" value={query} onChange={setQuery} />
      <NcChips
        chips={vocabChips}
        active={activeVocabChip}
        onSelect={(i) => setFilter(vocabChipFilters[i] || 'all')}
      />
      <NcLiveSum
        text={loading || deckLoading
          ? 'Registre en cours…'
          : `${todayItems.length} ${todayItems.length === 1 ? 'carte' : 'cartes'} en file · ${filteredDeck.length} au registre (${filterFr(filter)})`}
        clearable={hasVocabularyFilters}
        onClear={clearVocabularyFilters}
      />

      <NcLedgerHead t="File du jour — à revoir" n={`${todayItems.length} ${todayItems.length === 1 ? 'carte' : 'cartes'}`} />
      {loading ? (
        <NcSkeleton rows={4} />
      ) : contextError ? (
        <NcNotice message="Le registre des mots n’a pas pu être ouvert. La grammaire reste consultable." onRetry={() => setContextRetry((v) => v + 1)} />
      ) : todayItems.length === 0 ? (
        <NcEmpty
          title="Aucune carte en file"
          body={hasVocabularyFilters ? 'Aucun mot ne correspond à ce filtre.' : 'La file du jour est vide — le registre vous attend plus bas.'}
          action={hasVocabularyFilters ? 'Effacer les filtres' : undefined}
          onAction={hasVocabularyFilters ? clearVocabularyFilters : undefined}
        />
      ) : (
        <div className="nc-index" role="list">
          {todayItems.map((item) => (
            <NcWordRow
              key={`${item.word_id}-${item.bucket}`}
              word={queueWord(item)}
              tr={queueTranslation(item)}
              bucket={ncQueueBucket(item.bucket)}
              onClick={() => openDetail({ kind: 'queue', item })}
            />
          ))}
        </div>
      )}

      <NcLedgerHead t="Registre des mots — Français 5000" tone="blue" n={deckLoading ? 'recherche…' : `${filteredDeck.length} affichés`} />
      {deckLoading ? (
        <NcSkeleton rows={4} file={false} />
      ) : deckError ? (
        <NcNotice tone="blue" message="Le registre des mots ne répond pas. Réessayez dans un instant." onRetry={() => setDeckRetry((v) => v + 1)} />
      ) : filteredDeck.length === 0 ? (
        <NcEmpty
          title="Aucun mot au registre"
          body="Essayez un autre terme de recherche."
          action={activeVocabularySearch ? 'Effacer la recherche' : undefined}
          onAction={activeVocabularySearch ? () => setQuery('') : undefined}
        />
      ) : (
        <div className="nc-index" role="list">
          {filteredDeck.map((item) => {
            const cell = masteryByWordId.get(item.id);
            const st = ncDeckState(cell?.mastery_state);
            return (
              <NcWordRow
                key={item.id}
                rank={item.frequency_rank || null}
                word={item.word}
                // "traduction à venir" promised a translation nothing was
                // going to write. A word with no gloss on file simply shows
                // none.
                tr={deckTranslation(item) || '—'}
                pos={partOfSpeechLabel(item.part_of_speech) || null}
                state={st.state}
                stateLabel={st.label}
                onClick={() => openDetail({ kind: 'deck', item })}
              />
            );
          })}
        </div>
      )}

      {coverage && (
        <>
          <button type="button" className="nc-fold" aria-expanded={atlasOpen} onClick={() => setAtlasOpen((open) => !open)}>
            <span>
              <span className="t">Atlas des acquis</span>
              <span className="s" style={{ display: 'block' }}>
                {cefrTotals.nailed} mots tenus sur {cefrTotals.total || 5000} · carte {atlasOpen ? 'dépliée' : 'pliée'}
              </span>
            </span>
            <span className="chev">{atlasOpen ? 'Replier' : 'Déplier'} <NcIcoFold open={atlasOpen} /></span>
          </button>
          {atlasOpen && (
            <>
              <NcLedgerHead t="Couverture CECR" n="mots tenus / bande" />
              {(coverage.cefr_bar || []).map((band, i) => (
                <NcCoverageTrack
                  key={band.band}
                  lab={band.band}
                  val={band.nailed || 0}
                  max={band.total || Math.max(1, Math.round((band.nailed || 0) / Math.max(0.01, (band.percent || 0) / 100)))}
                  tone={i === 0 ? 'ink' : ''}
                />
              ))}
              {topicCats.length > 0 && (
                <>
                  <NcLedgerHead t="Pistes par domaine" tone="blue" n={`${topicCats.length} en cours`} />
                  {topicCats.map((track) => (
                    <NcCoverageTrack key={track.id} lab={track.label} val={track.nailed || 0} max={track.total || 1} />
                  ))}
                </>
              )}
              {(coverage.verb_tracks || []).length > 0 && (
                <>
                  <NcLedgerHead t="Verbes & structures" tone="blue" n="conjugaison" />
                  <NcCoverageTrack lab="Verbes" val={verbSummary.nailed || 0} max={verbSummary.total || 1} tone="ink" />
                  {/* /vocabulary/conjugation had no inbound link anywhere in the
                    * app: the drill ran, scheduled itself and was unreachable.
                    * The verbs block is where a learner is already looking at
                    * their conjugation standing, so the way in belongs here. */}
                  <Link className="vocab-review-link" href="/vocabulary/conjugation">
                    Reprendre les formes irrégulières →
                  </Link>
                </>
              )}
              {masteryMap && ncMapCellClasses.length > 0 && (
                <>
                  <NcLedgerHead t="Carte de maîtrise — Français 5000" n="1 case = 1 mot" />
                  <NcMasteryMap
                    cells={ncMapCellClasses}
                    totals={ncMapTotals}
                    note={`Les ${ncMapCellClasses.length} premières cases par rang de fréquence — la carte entière se parcourt par bandes, jamais imposée à la lecture.`}
                  />
                </>
              )}
            </>
          )}
        </>
      )}

      {weeklyDossier && (
        <div className="nc-dossier">
          <div className="k">Dossier de la semaine</div>
          <h3>{weeklyDossier.headline || 'Le registre s’épaissit.'}</h3>
          <dl>
            <div><dt>Réparations</dt><dd>{weeklyDossier.stats.repairs_filed ?? 0}</dd></div>
            <div><dt>Révisions</dt><dd>{weeklyDossier.stats.vocabulary_reviews ?? 0}</dd></div>
            <div><dt>Vus</dt><dd>{weeklyDossier.stats.words_seen ?? 0}</dd></div>
            <div><dt>Employés</dt><dd>{weeklyDossier.stats.words_produced ?? 0}</dd></div>
          </dl>
          {(weeklyDossier.fragile_threads?.[0] || weeklyDossier.next_actions?.[0]) && (
            <div className="thread">
              <b>{(weeklyDossier.fragile_threads?.[0] || weeklyDossier.next_actions?.[0])!.title}</b>
              {(weeklyDossier.fragile_threads?.[0] || weeklyDossier.next_actions?.[0])!.subtitle && (
                <em>{(weeklyDossier.fragile_threads?.[0] || weeklyDossier.next_actions?.[0])!.subtitle}</em>
              )}
            </div>
          )}
        </div>
      )}

      <NcColophon />
    </>
  );

  return (
    <>
      {!embedded && (
        <Head>
          <title>Le Cahier · Lexique · L’Atelier</title>
        </Head>
      )}
      <CahiersStyles />
      <main className={`vocab-page ${embedded ? 'embedded' : ''}`}>
        <div className="nc nc-flow">
          <div className="nc-page">
            {!embedded && <NcMasthead slim route="Vocabulaire" xlink="Grammaire" xlinkHref="/grammar" />}
            {landing}
          </div>
        </div>
      </main>
      {!embedded && <PhoneProductNav active="notebook" placement="embedded" />}

      {detail && (
        <MobileBottomSheet
          ariaLabel={`Fiche du mot ${detailWord(detail)}`}
          onClose={closeDetail}
          eyebrow="Français 5000"
          title={detailWord(detail)}
          closeLabel="Fermer la fiche du mot"
          closeContent={<X size={18} />}
          sheetClassName="vocab-detail-sheet"
        >
            <div className="vocab-detail-meta" aria-label="Détails du mot">
              <span>
                <strong>{detailRank ? `#${detailRank}` : '—'}</strong>
                <em>rang de fréquence</em>
              </span>
              <span>
                <strong>{detailSpeech || '—'}</strong>
                <em>nature</em>
              </span>
              <span>
                <strong>{detailLevel ? `N${detailLevel}` : '—'}</strong>
                <em>difficulté</em>
              </span>
              <span>
                <strong>{detail.kind === 'queue' ? humanBucket(detail.item.bucket) : 'registre'}</strong>
                <em>provenance</em>
              </span>
            </div>
            <div className="vocab-fragility-strip">
              <FragilityBadge
                progress={detail.kind === 'queue' ? detail.item : detailSupport.progress}
                showReason
              />
            </div>
            <div 
              className="vocab-flashcard-perspective cursor-pointer select-none"
              onClick={() => setPracticeRevealed((current) => !current)}
            >
              <div className={`vocab-flashcard-inner ${practiceRevealed ? 'flipped' : ''}`}>
                
                {/* FRONT FACE */}
                <div className="vocab-flashcard-front">
                  <span className="vocab-card-face-label">LE MOT</span>
                  <p className="vocab-card-face-word">{detailWord(detail)}</p>
                  <div className="vocab-card-hint-text">Touchez la carte pour retourner</div>
                </div>

                {/* BACK FACE */}
                <div className="vocab-flashcard-back">
                  <span className="vocab-card-face-label">LA RÉPONSE</span>
                  <p className="vocab-card-face-word">
                    {detailTranslation(detail) || detailMeaningForPractice(detail) || detailFrench(detail)}
                  </p>
                  <div className="vocab-card-hint-text">Touchez pour revenir au mot</div>
                </div>
                
              </div>
            </div>
            <ContextAnchor
              className="vocab-answer"
              label="Phrase d’ancrage"
              text={detailExample(detail) || [detailFrench(detail), detailTranslation(detail)].filter(Boolean).join(' — ')}
              quote
            />
            <section className="vocab-detail-block">
              <div className="vocab-detail-block-head">
                <span>Exemples par source</span>
                <em>
                  {detailSupport.loading
                    ? 'en cours'
                    : plural(detailExampleGroups.reduce((count, group) => count + group.entries.length, 0), 'relevé', 'relevés')}
                </em>
              </div>
              {detailExampleGroups.length > 0 ? (
                <div className="vocab-source-groups">
                  {detailExampleGroups.map((group) => (
                    <article key={group.source} className="vocab-source-group">
                      <div className="vocab-source-title">
                        <strong>{group.source}</strong>
                        <span>{group.entries.length}</span>
                      </div>
                      {group.entries.map((entry) => (
                        <div key={`${group.source}-${entry.label}-${entry.text}`} className="vocab-context-entry">
                          <b>{entry.label}</b>
                          <p>{entry.text}</p>
                          {entry.translation && <em>{entry.translation}</em>}
                          {entry.meta && <small>{entry.meta}</small>}
                        </div>
                      ))}
                    </article>
                  ))}
                </div>
              ) : (
                <p className="vocab-placeholder">Aucun exemple au dossier pour l’instant.</p>
              )}
            </section>
            <section className="vocab-detail-block">
              <div className="vocab-detail-block-head">
                <span>Le suivi</span>
                <em>{detailSupport.loading ? 'en cours' : detailSupport.progress ? 'à jour' : 'jamais revu'}</em>
              </div>
              <div className="vocab-srs-grid">
                {detailSrsRows.map((row) => (
                  <div key={row.label}>
                    <span>{row.label}</span>
                    <strong>{row.value}</strong>
                  </div>
                ))}
              </div>
            </section>
            <section className="vocab-detail-block">
              <div className="vocab-detail-block-head">
                <span>Traces récentes</span>
                <em>
                  {detailSupport.loading
                    ? 'en cours'
                    : plural(detailSupport.traces.length, 'trace', 'traces')}
                </em>
              </div>
              {detailSupport.traces.length > 0 ? (
                <div className="vocab-trace-list">
                  {detailSupport.traces.map((trace) => (
                    <Link key={traceKey(trace)} href={trace.href || '#'} className={!trace.href ? 'disabled' : ''}>
                      <span>{trace.source}</span>
                      <strong>{trace.label}</strong>
                      <em>{[trace.description, formatShortDate(trace.date)].filter(Boolean).join(' · ')}</em>
                    </Link>
                  ))}
                </div>
              ) : (
                <p className="vocab-placeholder">Ce mot n’a pas encore laissé de trace.</p>
              )}
            </section>
            <div className="vocab-context-actions">
              <button type="button" onClick={openBiography}>
                La biographie du mot
              </button>
              <button type="button" disabled={action !== null} onClick={createMission}>
                {action === 'mission' ? <Loader2 size={14} className="spin" /> : null}
                Le mettre en mission
              </button>
              <button type="button" disabled={action !== null} onClick={createFeuilleton}>
                {action === 'feuilleton' ? <Loader2 size={14} className="spin" /> : null}
                Le lire au Feuilleton <ArrowRight size={13} />
              </button>
            </div>
            <div className="vocab-ratings">
              {reviewOptions.map((option) => (
                <button key={option.rating} type="button" className={option.tone} disabled={reviewing || !practiceRevealed} onClick={() => review(option.rating)}>
                  <strong>{option.label}</strong>
                  <span>{option.hint}</span>
                </button>
              ))}
            </div>
        </MobileBottomSheet>
      )}

      <WordBiographySheet
        open={Boolean(biographyWordId)}
        biography={biography}
        loading={biographyLoading}
        error={biographyError}
        onClose={() => setBiographyWordId(null)}
      />

      <style jsx>{`
        .vocab-page {
          --paper: var(--app-paper);
          --paper-2: var(--app-paper-2);
          --sheet: var(--app-sheet);
          --ink: var(--app-ink);
          --ink-2: var(--app-ink-2);
          --ink-3: var(--app-ink-3);
          --red: var(--app-red);
          --blue: var(--app-blue);
          --yellow: var(--app-yellow);
          min-height: 100vh;
          padding: 24px clamp(20px, 4vw, 48px) 112px;
          background: var(--paper);
          color: var(--ink);
        }
        .vocab-page.embedded {
          min-height: auto;
          padding: 0;
          background: transparent;
        }
        .vocab-hero {
          border-bottom: 1px solid var(--ink);
          padding-bottom: 20px;
        }
        .vocab-kicker,
        .coverage-atlas-head span,
        .coverage-axis-title span,
        .coverage-axis-title a,
        .coverage-tile em,
        .coverage-cefr-band span,
        .coverage-cefr-band em,
        .vocab-weekly-dossier span,
        .vocab-weekly-dossier dt,
        .vocab-map-legend,
        .vocab-section-head span,
        .vocab-tabs button,
        .vocab-answer span,
        .vocab-detail-sheet header span,
        .vocab-detail-meta em,
        .vocab-detail-block-head span,
        .vocab-source-title span,
        .vocab-context-entry b,
        .vocab-srs-grid span,
        .vocab-trace-list span {
          font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
          font-size: 11px;
          font-weight: 900;
          letter-spacing: .12em;
          text-transform: uppercase;
        }
        h1,
        .vocab-detail-sheet h2 {
          margin: 8px 0 0;
          font-family: "EB Garamond", Garamond, serif;
          font-size: clamp(46px, 10vw, 82px);
          font-style: italic;
          line-height: .95;
          letter-spacing: 0;
        }
        .vocab-stats {
          display: grid;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: 24px;
          margin-top: 22px;
        }
        .vocab-review-link {
          display: inline-flex;
          min-height: 28px;
          align-items: center;
          justify-content: center;
          margin-top: 14px;
          border: 0;
          border-bottom: 1px solid currentColor;
          background: transparent;
          padding: 0;
          color: var(--ink-3);
          font-size: 12px;
          font-weight: 850;
          letter-spacing: 0;
          text-decoration: none;
          text-transform: none;
        }
        .vocab-review-link:hover {
          color: var(--blue);
        }
        .vocab-stats span {
          border-top: 1px solid var(--ink);
          padding-top: 8px;
          color: var(--ink);
          font-weight: 900;
          text-transform: uppercase;
        }
        .vocab-stats strong {
          display: block;
          font-size: 32px;
          line-height: 1;
        }
        .vocab-mode-switch {
          margin-top: 18px;
        }
        .vocab-coverage-atlas {
          display: grid;
          gap: 16px;
          margin-top: 18px;
          border: 1px solid var(--ink);
          background: var(--sheet);
          padding: 18px 16px;
        }
        .atlas-hero {
          display: flex;
          align-items: center;
          gap: 16px;
        }
        .atlas-hero-body {
          display: grid;
          gap: 1px;
        }
        .atlas-hero-body span {
          font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
          font-size: 10px;
          font-weight: 900;
          letter-spacing: .12em;
          text-transform: uppercase;
          color: var(--ink-3);
        }
        .atlas-hero-body strong {
          font-family: "EB Garamond", Garamond, serif;
          font-style: italic;
          font-size: 32px;
          line-height: 1;
          font-weight: 650;
        }
        .atlas-hero-body em {
          font-size: 12px;
          color: var(--ink-2);
          font-style: normal;
        }
        .atlas-momentum {
          margin-left: auto;
          align-self: flex-start;
          font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
          font-size: 10px;
          font-weight: 900;
          letter-spacing: .08em;
          text-transform: uppercase;
          color: var(--blue);
        }
        .atlas-block {
          display: grid;
          gap: 9px;
        }
        .atlas-axis-title {
          font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
          font-size: 10px;
          font-weight: 900;
          letter-spacing: .12em;
          text-transform: uppercase;
          color: var(--ink-3);
        }
        .atlas-active {
          display: flex;
          align-items: center;
          gap: 14px;
          border: 1px solid var(--ink);
          background: var(--paper);
          padding: 14px;
          text-decoration: none;
          color: var(--ink);
        }
        .atlas-active-body {
          flex: 1;
          display: grid;
          gap: 2px;
        }
        .atlas-active-body strong {
          font-family: "EB Garamond", Garamond, serif;
          font-style: italic;
          font-size: 19px;
          font-weight: 650;
        }
        .atlas-active-body em {
          font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
          font-size: 10px;
          font-weight: 900;
          letter-spacing: .08em;
          text-transform: uppercase;
          color: var(--ink-3);
          font-style: normal;
        }
        .atlas-next {
          display: grid;
          gap: 0;
          border: 1px solid var(--paper-2);
        }
        .atlas-next-row {
          display: flex;
          align-items: baseline;
          justify-content: space-between;
          padding: 11px 12px;
          border-bottom: 1px solid var(--paper-2);
          text-decoration: none;
          color: var(--ink);
          background: var(--paper);
        }
        .atlas-next-row:last-child { border-bottom: 0; }
        .atlas-next-row span {
          font-family: "EB Garamond", Garamond, serif;
          font-style: italic;
          font-size: 16px;
        }
        .atlas-next-row em {
          font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
          font-size: 10px;
          font-weight: 900;
          color: var(--ink-3);
          font-style: normal;
        }
        .atlas-fulltoggle {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          justify-self: start;
          min-height: 38px;
          padding: 0 14px;
          border: 1px solid var(--ink);
          background: transparent;
          color: var(--ink);
          font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
          font-size: 10px;
          font-weight: 900;
          letter-spacing: .1em;
          text-transform: uppercase;
          cursor: pointer;
        }
        .atlas-full {
          display: grid;
          gap: 10px;
          border-top: 1px solid var(--paper-2);
          padding-top: 14px;
        }
        .coverage-atlas-head,
        .coverage-axis-title {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 16px;
        }
        .coverage-atlas-head h2 {
          margin: 5px 0 0;
          font-family: "EB Garamond", Garamond, serif;
          font-size: clamp(24px, 6vw, 36px);
          font-style: italic;
          font-weight: 650;
          line-height: 1;
          letter-spacing: 0;
        }
        .coverage-atlas-head p {
          margin: 5px 0 0;
          color: var(--ink-2);
          font-size: 13px;
          line-height: 1.25;
        }
        .coverage-cta {
          display: inline-flex;
          min-height: 38px;
          align-items: center;
          justify-content: center;
          gap: 8px;
          border: 1px solid var(--ink);
          background: var(--ink);
          padding: 0 14px;
          color: var(--sheet);
          font-size: 13px;
          font-weight: 900;
          text-decoration: none;
          white-space: nowrap;
        }
        .coverage-summary-grid {
          display: grid;
          grid-template-columns: repeat(4, minmax(0, 1fr));
          gap: 8px;
        }
        .coverage-summary-card {
          display: grid;
          gap: 5px;
          min-height: 82px;
          border: 1px solid var(--ink);
          background: var(--paper);
          padding: 10px;
          color: var(--ink);
          text-decoration: none;
        }
        .coverage-summary-card span,
        .coverage-summary-card em {
          color: var(--ink-3);
          font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
          font-size: 10px;
          font-style: normal;
          font-weight: 900;
          letter-spacing: .08em;
          text-transform: uppercase;
        }
        .coverage-summary-card strong {
          font-size: 19px;
          line-height: 1;
        }
        .coverage-cefr-strip {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(76px, 1fr));
          gap: 8px;
        }
        .coverage-cefr-band,
        .coverage-tile {
          display: grid;
          min-height: 74px;
          align-content: space-between;
          gap: 6px;
          border: 1px solid var(--ink);
          background: var(--paper);
          padding: 10px;
        }
        .coverage-cefr-band strong,
        .coverage-tile strong {
          font-size: 20px;
          line-height: 1;
        }
        .coverage-tile strong {
          display: flex;
          gap: 4px;
          align-items: baseline;
        }
        .coverage-tile strong span {
          color: var(--ink-3);
          font-size: 14px;
        }
        .coverage-bar {
          height: 7px;
          overflow: hidden;
          border: 1px solid var(--ink);
          background: var(--paper-2);
        }
        .coverage-bar i {
          display: block;
          height: 100%;
          background: var(--blue);
        }
        .coverage-topic-panel {
          display: grid;
          gap: 8px;
        }
        .coverage-tile-grid {
          display: grid;
          grid-template-columns: repeat(4, minmax(0, 1fr));
          gap: 8px;
        }
        .coverage-tile {
          color: inherit;
          text-decoration: none;
        }
        .coverage-tile.compact {
          min-height: 86px;
        }
        .coverage-tile-label {
          font-weight: 900;
          line-height: 1.1;
        }
        .coverage-tile small {
          min-width: 0;
          overflow: hidden;
          color: var(--ink-3);
          font-size: 11px;
          line-height: 1.2;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        .coverage-topic-empty {
          border: 1px dashed var(--ink-3);
          padding: 10px;
          color: var(--ink-2);
          font-size: 13px;
          line-height: 1.3;
        }
        .vocab-weekly-dossier,
        .vocab-mastery-map {
          margin-top: 18px;
          border: 1px solid var(--ink);
          background: var(--sheet);
          padding: 14px;
        }
        .vocab-weekly-dossier {
          display: grid;
          gap: 14px;
        }
        .vocab-weekly-dossier span {
          color: var(--ink-3);
        }
        .vocab-weekly-dossier h2 {
          margin: 5px 0 0;
          font-family: "EB Garamond", Garamond, serif;
          font-size: clamp(25px, 7vw, 40px);
          font-style: italic;
          font-weight: 650;
          line-height: 1.03;
          letter-spacing: 0;
        }
        .vocab-weekly-dossier dl {
          display: grid;
          grid-template-columns: repeat(4, minmax(0, 1fr));
          margin: 0;
          border: 1px solid var(--ink);
          background: var(--paper);
        }
        .vocab-weekly-dossier dl div {
          min-width: 0;
          border-right: 1px solid var(--ink);
          padding: 9px 10px;
        }
        .vocab-weekly-dossier dl div:last-child {
          border-right: 0;
        }
        .vocab-weekly-dossier dt {
          color: var(--ink-3);
        }
        .vocab-weekly-dossier dd {
          margin: 4px 0 0;
          font-size: 24px;
          font-weight: 950;
          line-height: 1;
        }
        .vocab-weekly-threads {
          display: grid;
          gap: 8px;
        }
        .vocab-weekly-threads article {
          border-left: 4px solid var(--red);
          background: var(--paper);
          padding: 9px 11px;
        }
        .vocab-weekly-threads strong,
        .vocab-weekly-threads em {
          display: block;
        }
        .vocab-weekly-threads em {
          margin-top: 3px;
          color: var(--ink-3);
          font-style: normal;
          font-weight: 750;
          line-height: 1.25;
        }
        .vocab-section-head.compact {
          margin: 0 0 10px;
        }
        .vocab-map-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(6px, 1fr));
          gap: 3px;
          max-height: 140px;
          overflow: hidden;
          border: 1px solid var(--ink);
          background: var(--paper);
          padding: 8px;
        }
        .vocab-map-cell {
          display: block;
          aspect-ratio: 1;
          min-width: 6px;
          background: var(--paper-2);
        }
        .vocab-map-cell.due {
          background: var(--red);
        }
        .vocab-map-cell.fragile {
          background: color-mix(in srgb, var(--app-red) 45%, var(--app-paper));
        }
        .vocab-map-cell.building {
          background: var(--yellow);
        }
        .vocab-map-cell.solid {
          background: var(--blue);
        }
        .vocab-map-cell.mastered {
          background: var(--ink);
        }
        .vocab-map-legend {
          display: flex;
          flex-wrap: wrap;
          gap: 7px 12px;
          margin-top: 10px;
          color: var(--ink-3);
          font-size: 10px;
        }
        .vocab-map-legend span {
          display: inline-flex;
          align-items: center;
          gap: 5px;
        }
        .vocab-map-legend i {
          width: 9px;
          height: 9px;
          border: 1px solid var(--ink);
          background: var(--paper-2);
        }
        .vocab-map-legend i.due {
          background: var(--red);
        }
        .vocab-map-legend i.fragile {
          background: color-mix(in srgb, var(--app-red) 45%, var(--app-paper));
        }
        .vocab-map-legend i.building {
          background: var(--yellow);
        }
        .vocab-map-legend i.solid {
          background: var(--blue);
        }
        .vocab-map-legend i.mastered {
          background: var(--ink);
        }
        .vocab-controls {
          margin-top: 18px;
        }
        .vocab-search {
          display: grid;
          grid-template-columns: 28px minmax(0, 1fr) auto;
          align-items: center;
          gap: 12px;
          border: 1px solid var(--ink);
          background: var(--paper-2);
          padding: 10px 14px;
        }
        .vocab-search input {
          min-width: 0;
          border: 1px solid var(--ink);
          background: var(--paper);
          padding: 8px 10px;
          color: var(--ink);
          font: inherit;
          font-size: 18px;
          outline: 0;
        }
        .vocab-search-clear {
          display: inline-flex;
          width: 34px;
          height: 34px;
          flex: 0 0 auto;
          align-items: center;
          justify-content: center;
          border: 1px solid var(--ink);
          background: var(--paper);
          color: var(--ink);
        }
        .vocab-tabs {
          display: flex;
          flex-wrap: wrap;
          gap: 10px;
          margin-top: 12px;
        }
        .vocab-tabs button {
          min-height: 44px;
          border: 1px solid var(--ink);
          background: var(--paper);
          padding: 0 18px;
          color: var(--ink);
        }
        .vocab-tabs button.active {
          background: var(--ink);
          color: var(--paper);
        }
        .vocab-filter-summary {
          display: flex;
          min-height: 32px;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          margin-top: 8px;
          color: var(--ink-2);
          font-size: 12px;
          font-weight: 850;
        }
        .vocab-filter-summary button,
        :global(.vocab-state button) {
          min-height: 30px;
          border: 1px solid var(--ink);
          background: transparent;
          padding: 0 10px;
          color: var(--ink);
          font: inherit;
          font-size: 11px;
          font-weight: 900;
        }
        .vocab-section-head {
          display: flex;
          justify-content: space-between;
          align-items: baseline;
          gap: 16px;
          margin-top: 26px;
          margin-bottom: 10px;
        }
        .vocab-section-head em {
          color: var(--ink-3);
          font-size: 13px;
          font-style: normal;
          font-weight: 850;
        }
        .vocab-card-stack {
          border: 1px solid var(--ink);
          background: var(--sheet);
        }
        .vocab-row {
          display: grid;
          width: 100%;
          align-items: center;
          gap: 12px;
          min-height: 68px;
          border: 0;
          border-bottom: 1px solid var(--ink);
          background: transparent;
          padding: 12px 16px;
          color: var(--ink);
          text-align: left;
        }
        .queue-row {
          grid-template-columns: 16px minmax(0, 1fr) auto;
        }
        .deck-row {
          grid-template-columns: 42px minmax(0, 1fr) auto;
        }
        .queue-row :global(.fragility-badge) {
          grid-column: 3;
          grid-row: 1 / span 2;
          justify-self: end;
          max-width: 126px;
        }
        .queue-row b {
          grid-column: 2;
          justify-self: start;
          margin-top: -6px;
        }
        .vocab-row:last-child {
          border-bottom: 0;
        }
        .vocab-row strong {
          display: block;
          font-size: 18px;
          font-weight: 900;
          line-height: 1.2;
          overflow-wrap: anywhere;
        }
        .vocab-row em {
          display: block;
          margin-top: 3px;
          color: var(--ink-3);
          font-size: 13px;
          font-style: normal;
          font-weight: 700;
          line-height: 1.3;
          overflow-wrap: anywhere;
        }
        .vocab-row b {
          color: var(--blue);
          font-size: 12px;
          line-height: 1.1;
          text-align: right;
        }
        .queue-row b {
          text-align: left;
        }
        .vocab-dot {
          width: 9px;
          height: 9px;
          border-radius: 50%;
          background: var(--red);
        }
        .vocab-dot.fragile {
          background: var(--blue);
        }
        .vocab-dot.new {
          background: var(--yellow);
          border: 1px solid var(--ink);
        }
        .vocab-rank {
          display: inline-grid;
          min-width: 26px;
          min-height: 22px;
          place-items: center;
          border: 1px solid var(--ink);
          font-size: 11px;
          font-weight: 900;
        }
        :global(.vocab-empty) {
          padding: 18px 16px;
          color: var(--ink-3);
          font-weight: 800;
        }
        :global(.vocab-state) {
          display: grid;
          grid-column: 1 / -1;
          gap: 8px;
          min-height: 128px;
          align-content: center;
          border: 1px dashed color-mix(in srgb, var(--app-ink) 42%, transparent);
          background: var(--paper-2);
        }
        :global(.vocab-state.error) {
          border-style: solid;
          border-left: 4px solid var(--red);
          background: var(--app-sheet);
        }
        :global(.vocab-state-head) {
          display: flex;
          align-items: center;
          gap: 8px;
          color: var(--ink);
          font-size: 11px;
          font-weight: 900;
          letter-spacing: .12em;
          text-transform: uppercase;
        }
        :global(.vocab-state p) {
          margin: 0;
          color: var(--ink-2);
          font-size: 14px;
          font-weight: 750;
          line-height: 1.35;
        }
        :global(.vocab-state-skeleton) {
          display: grid;
          gap: 8px;
          margin-top: 4px;
        }
        :global(.vocab-state-skeleton span) {
          display: block;
          height: 12px;
          border: 1px solid color-mix(in srgb, var(--app-ink) 18%, transparent);
          background: linear-gradient(90deg, var(--app-paper-2), var(--app-sheet), var(--app-paper-2));
          background-size: 220% 100%;
          animation: vocab-shimmer 1.2s ease-in-out infinite;
        }
        :global(.vocab-state-skeleton span:nth-child(2)) {
          width: 78%;
        }
        :global(.vocab-state-skeleton span:nth-child(3)) {
          width: 58%;
        }
        .vocab-detail-layer {
          --paper: var(--app-paper);
          --paper-2: var(--app-paper-2);
          --sheet: var(--app-sheet);
          --ink: var(--app-ink);
          --ink-2: var(--app-ink-2);
          --ink-3: var(--app-ink-3);
          --red: var(--app-red);
          --blue: var(--app-blue);
          --yellow: var(--app-yellow);
          position: fixed;
          inset: 0;
          z-index: 120;
        }
        .vocab-detail-scrim {
          position: absolute;
          inset: 0;
          border: 0;
          background: color-mix(in srgb, var(--app-ink) 42%, transparent);
        }
        .vocab-detail-sheet {
          position: absolute;
          right: 0;
          bottom: 0;
          left: 0;
          max-height: 86vh;
          overflow: auto;
          border-top: 1px solid var(--ink);
          background: var(--paper);
          padding: 12px 20px calc(20px + env(safe-area-inset-bottom));
          box-shadow: 0 -20px 40px color-mix(in srgb, var(--app-ink) 18%, transparent);
        }
        .vocab-grabber {
          width: 48px;
          height: 4px;
          margin: 0 auto 16px;
          border-radius: 999px;
          background: var(--ink-3);
        }
        .vocab-detail-sheet header {
          display: flex;
          justify-content: space-between;
          gap: 18px;
          border-bottom: 1px solid var(--ink);
          padding-bottom: 14px;
        }
        .vocab-detail-sheet h2 {
          font-size: clamp(40px, 11vw, 70px);
          overflow-wrap: anywhere;
        }
        .vocab-detail-meta {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 1px;
          margin-top: 12px;
          border: 1px solid var(--ink);
          background: var(--ink);
        }
        .vocab-detail-meta span {
          display: grid;
          gap: 4px;
          min-width: 0;
          background: var(--sheet);
          padding: 10px 12px;
        }
        .vocab-detail-meta strong {
          min-width: 0;
          font-size: 18px;
          line-height: 1.1;
          overflow-wrap: anywhere;
        }
        .vocab-detail-meta em {
          color: var(--ink-3);
          font-size: 9px;
          font-style: normal;
          letter-spacing: .08em;
        }
        .vocab-fragility-strip {
          border: 1px solid var(--ink);
          border-top: 0;
          background: var(--paper);
          padding: 10px 12px;
        }
        .vocab-fragility-strip :global(.fragility-badge) {
          width: 100%;
        }
        .vocab-detail-sheet header button {
          display: inline-grid;
          width: 44px;
          height: 44px;
          place-items: center;
          border: 1px solid var(--ink);
          background: var(--sheet);
          color: var(--ink);
        }
        .vocab-practice-tabs {
          display: grid;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          margin-top: 14px;
          border: 1px solid var(--ink);
        }
        .vocab-practice-tabs button {
          min-height: 42px;
          border: 0;
          border-right: 1px solid var(--ink);
          background: var(--sheet);
          color: var(--ink);
          font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
          font-size: 10px;
          font-weight: 900;
          letter-spacing: .08em;
          text-transform: uppercase;
        }
        .vocab-practice-tabs button:last-child {
          border-right: 0;
        }
        .vocab-practice-tabs button.active {
          background: var(--ink);
          color: var(--paper);
        }
        .vocab-flashcard-perspective {
          perspective: 1000px;
          width: 100%;
          height: 190px;
          margin-top: 14px;
        }
        .vocab-flashcard-inner {
          position: relative;
          width: 100%;
          height: 100%;
          transition: transform 0.6s cubic-bezier(0.4, 0, 0.2, 1);
          transform-style: preserve-3d;
        }
        .vocab-flashcard-inner.flipped {
          transform: rotateY(180deg);
        }
        .vocab-flashcard-front,
        .vocab-flashcard-back {
          position: absolute;
          width: 100%;
          height: 100%;
          backface-visibility: hidden;
          border: 4px solid var(--ink);
          padding: 20px;
          display: flex;
          flex-direction: column;
          justify-content: center;
          align-items: center;
          text-align: center;
        }
        .vocab-flashcard-front {
          background: var(--sheet);
        }
        .vocab-flashcard-back {
          background: var(--yellow);
          transform: rotateY(180deg);
        }
        .vocab-card-face-label {
          position: absolute;
          top: 10px;
          left: 12px;
          font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
          font-size: 10px;
          font-weight: 900;
          letter-spacing: .1em;
          text-transform: uppercase;
          color: var(--ink-3);
        }
        .vocab-card-face-word {
          font-family: "EB Garamond", Garamond, serif;
          font-size: 28px;
          font-style: italic;
          font-weight: 700;
          line-height: 1.1;
          color: var(--ink);
          max-width: 90%;
          overflow-wrap: anywhere;
        }
        .vocab-card-hint-text {
          position: absolute;
          bottom: 10px;
          font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
          font-size: 9px;
          font-weight: 800;
          letter-spacing: .05em;
          text-transform: uppercase;
          color: var(--ink-3);
          opacity: 0.8;
        }
        .vocab-detail-sheet blockquote {
          margin-top: 14px;
          border-left: 4px solid var(--blue);
          background: var(--sheet);
          padding: 12px 14px;
        }
        .vocab-detail-sheet blockquote {
          margin-bottom: 0;
          font-family: "EB Garamond", Garamond, serif;
          font-size: 22px;
          font-style: italic;
          line-height: 1.3;
        }
        .vocab-detail-block {
          margin-top: 14px;
          border: 1px solid var(--ink);
          background: var(--sheet);
        }
        .vocab-detail-block-head {
          display: flex;
          align-items: baseline;
          justify-content: space-between;
          gap: 12px;
          border-bottom: 1px solid var(--ink);
          padding: 10px 12px;
        }
        .vocab-detail-block-head em {
          color: var(--ink-3);
          font-size: 12px;
          font-style: normal;
          font-weight: 850;
        }
        .vocab-source-groups,
        .vocab-trace-list {
          display: grid;
          gap: 1px;
          background: var(--ink);
        }
        .vocab-source-group,
        .vocab-trace-list a {
          min-width: 0;
          background: var(--sheet);
        }
        .vocab-source-title {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          padding: 10px 12px 0;
        }
        .vocab-source-title strong {
          font-size: 15px;
          overflow-wrap: anywhere;
        }
        .vocab-source-title span {
          display: inline-grid;
          min-width: 24px;
          height: 24px;
          place-items: center;
          border: 1px solid var(--ink);
          font-size: 10px;
          letter-spacing: 0;
        }
        .vocab-context-entry {
          padding: 10px 12px 12px;
        }
        .vocab-context-entry + .vocab-context-entry {
          border-top: 1px solid color-mix(in srgb, var(--app-ink) 18%, transparent);
        }
        .vocab-context-entry b {
          display: block;
          color: var(--blue);
          font-size: 10px;
          letter-spacing: .08em;
        }
        .vocab-context-entry p {
          margin: 5px 0 0;
          color: var(--ink);
          font-size: 17px;
          font-weight: 800;
          line-height: 1.28;
          overflow-wrap: anywhere;
        }
        .vocab-context-entry em,
        .vocab-context-entry small {
          display: block;
          margin-top: 5px;
          color: var(--ink-3);
          font-size: 13px;
          font-style: normal;
          font-weight: 750;
          line-height: 1.25;
          overflow-wrap: anywhere;
        }
        .vocab-srs-grid {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 1px;
          background: var(--ink);
        }
        .vocab-srs-grid div {
          min-width: 0;
          background: var(--sheet);
          padding: 10px 12px;
        }
        .vocab-srs-grid span {
          display: block;
          color: var(--ink-3);
          font-size: 9px;
          letter-spacing: .08em;
        }
        .vocab-srs-grid strong {
          display: block;
          margin-top: 5px;
          font-size: 15px;
          line-height: 1.2;
          overflow-wrap: anywhere;
        }
        .vocab-trace-list a {
          display: grid;
          gap: 3px;
          padding: 10px 12px;
          color: var(--ink);
          text-decoration: none;
        }
        .vocab-trace-list a.disabled {
          pointer-events: none;
        }
        .vocab-trace-list span {
          color: var(--blue);
          font-size: 9px;
          letter-spacing: .08em;
        }
        .vocab-trace-list strong {
          font-size: 15px;
          line-height: 1.2;
          overflow-wrap: anywhere;
        }
        .vocab-trace-list em,
        .vocab-placeholder {
          color: var(--ink-3);
          font-size: 13px;
          font-style: normal;
          font-weight: 750;
          line-height: 1.3;
        }
        .vocab-placeholder {
          margin: 0;
          padding: 12px;
        }
        .vocab-context-actions,
        .vocab-ratings {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 8px;
          margin-top: 14px;
        }
        .vocab-context-actions button,
        .vocab-ratings button {
          display: inline-flex;
          min-height: 56px;
          align-items: center;
          justify-content: center;
          gap: 6px;
          border: 1px solid var(--ink);
          background: var(--sheet);
          color: var(--ink);
          padding: 8px;
          text-align: left;
          font-weight: 900;
        }
        .vocab-ratings button {
          display: block;
          text-align: left;
        }
        .vocab-ratings strong,
        .vocab-ratings span {
          display: block;
        }
        .vocab-ratings span {
          margin-top: 4px;
          color: var(--ink-3);
          font-size: 12px;
        }
        .vocab-ratings .red {
          border-color: var(--red);
          box-shadow: inset 4px 0 0 var(--red);
        }
        .vocab-ratings .yellow {
          box-shadow: inset 4px 0 0 var(--yellow);
        }
        .vocab-ratings .blue {
          border-color: var(--blue);
          box-shadow: inset 4px 0 0 var(--blue);
        }
        .vocab-ratings .black {
          background: var(--ink);
          color: var(--paper);
        }
        .vocab-ratings button:disabled {
          cursor: not-allowed;
          opacity: .45;
        }
        .spin {
          animation: spin .7s linear infinite;
        }
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
        @keyframes vocab-shimmer {
          0% { background-position: 120% 0; }
          100% { background-position: -120% 0; }
        }
        @media (max-width: 640px) {
          .vocab-page {
            overflow-x: hidden;
            padding: 0 0 calc(134px + env(safe-area-inset-bottom));
          }
          .vocab-hero {
            border-bottom: 0;
            padding: 16px 16px 0;
          }
          .vocab-kicker {
            letter-spacing: .1em;
          }
          h1,
          .vocab-detail-sheet h2 {
            margin-top: 4px;
            font-size: 34px;
            line-height: .95;
          }
          .vocab-mode-switch {
            width: calc(100% - 32px);
            margin: 14px 16px;
          }
          .vocab-stats {
            grid-template-columns: repeat(3, minmax(92px, 1fr));
            gap: 18px;
            margin: 12px -16px 0;
            overflow-x: auto;
            overscroll-behavior-x: contain;
            border-bottom: 1px solid var(--ink);
            padding: 12px 16px 14px;
            scrollbar-width: none;
          }
          .vocab-stats::-webkit-scrollbar {
            display: none;
          }
          .vocab-stats span {
            min-width: 92px;
            padding-top: 7px;
            font-size: 9px;
            letter-spacing: .1em;
            line-height: 1.2;
          }
          .vocab-stats strong {
            font-size: 25px;
          }
          .vocab-review-link {
            margin-top: 10px;
            min-height: 30px;
            padding: 0;
            border: 0;
            color: var(--ink-3);
            letter-spacing: 0;
            text-transform: none;
          }
          .vocab-coverage-atlas {
            margin: 12px 16px 16px;
            padding: 12px;
          }
          .coverage-atlas-head {
            display: grid;
            gap: 12px;
          }
          .coverage-atlas-head h2 {
            font-size: 28px;
          }
          .coverage-cta {
            width: 100%;
          }
          .coverage-summary-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
          }
          .coverage-summary-card {
            min-height: 72px;
            padding: 9px;
          }
          .coverage-cefr-strip {
            grid-template-columns: repeat(3, minmax(0, 1fr));
          }
          .coverage-tile-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
          }
          .coverage-cefr-band,
          .coverage-tile {
            min-height: 72px;
          }
          .vocab-weekly-dossier,
          .vocab-mastery-map {
            display: none;
          }
          .vocab-controls {
            position: sticky;
            top: 0;
            z-index: 5;
            margin-top: 0;
            border-bottom: 1px solid var(--ink);
            background: var(--paper);
            padding: 10px 16px 12px;
            box-shadow: 0 8px 18px color-mix(in srgb, var(--app-ink) 8%, transparent);
          }
          .vocab-search {
            min-height: 44px;
            grid-template-columns: 16px minmax(0, 1fr) auto;
            gap: 10px;
            margin: 0 0 9px;
            background: var(--app-paper-2);
            padding: 6px 10px;
            transition: border-color .16s ease, background .16s ease, box-shadow .16s ease;
          }
          .vocab-search:focus-within {
            border-color: var(--blue);
            background: var(--app-sheet);
            box-shadow: inset 3px 0 0 var(--blue);
          }
          .vocab-search input {
            min-height: 30px;
            border: 0;
            background: transparent;
            padding: 0;
            font-size: 16px;
          }
          .vocab-search-clear {
            width: 30px;
            height: 30px;
          }
          .vocab-tabs {
            flex-wrap: nowrap;
            gap: 8px;
            margin: 0 -16px;
            overflow-x: auto;
            padding: 0 16px 2px;
            scrollbar-width: none;
          }
          .vocab-tabs::-webkit-scrollbar {
            display: none;
          }
          .vocab-tabs button {
            flex: 0 0 auto;
            min-height: 36px;
            padding: 0 13px;
            letter-spacing: 0;
            text-transform: none;
          }
          .vocab-filter-summary {
            min-height: 28px;
            margin-top: 0;
            padding-top: 8px;
            font-size: 11px;
          }
          .vocab-filter-summary button,
          :global(.vocab-state button) {
            flex: 0 0 auto;
            min-height: 30px;
            font-size: 11px;
            letter-spacing: 0;
            text-transform: none;
          }
          .vocab-section-head {
            margin: 14px 16px 8px;
          }
          .vocab-section-head.deck {
            margin-top: 22px;
          }
          .vocab-card-stack {
            border: 0;
            background: transparent;
          }
          .vocab-row {
            min-height: 60px;
            gap: 10px;
            border-bottom: 1px solid var(--ink);
            padding: 12px 16px;
            background: transparent;
          }
          .queue-row {
            grid-template-columns: minmax(0, 1fr) auto;
          }
          .deck-row {
            grid-template-columns: 42px minmax(0, 1fr) auto;
          }
          .queue-row .vocab-dot {
            display: none;
          }
          .queue-row :global(.fragility-badge) {
            grid-column: 2;
            grid-row: 1;
            max-width: 112px;
          }
          .queue-row b {
            display: none;
          }
          .vocab-row strong {
            font-size: 15px;
            line-height: 1.3;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
          }
          .vocab-row em {
            font-size: 12px;
            line-height: 1.25;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
          }
          .vocab-row b {
            font-size: 11px;
          }
          .vocab-rank {
            min-width: 30px;
            min-height: 24px;
          }
          :global(.vocab-state) {
            margin: 12px 16px;
            min-height: 126px;
            padding: 16px;
          }
          :global(.vocab-state-head) {
            font-size: 10px;
            letter-spacing: .1em;
          }
        }
        @media (min-width: 761px) {
          .vocab-page {
            max-width: 1180px;
            margin: 0 auto;
            padding-bottom: 64px;
          }
          .vocab-card-stack {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
          }
          .vocab-row:nth-child(odd) {
            border-right: 1px solid var(--ink);
          }
          .vocab-detail-sheet {
            left: auto;
            width: min(560px, 100vw);
            max-height: 100vh;
            border-top: 0;
            border-left: 1px solid var(--ink);
            padding: 16px 22px 22px;
          }
          .vocab-grabber {
            display: none;
          }
          .vocab-detail-meta,
          .vocab-srs-grid {
            grid-template-columns: repeat(4, minmax(0, 1fr));
          }
        }
      `}</style>
      <style jsx global>{`
        .vocab-mobile-action {
          display: inline-grid;
          min-width: 58px;
          height: 58px;
          place-items: center;
          border: 1px solid var(--app-ink);
          color: var(--app-ink);
          text-decoration: none;
          font-size: 12px;
          font-weight: 900;
          text-transform: uppercase;
        }
      `}</style>
    </>
  );
}
