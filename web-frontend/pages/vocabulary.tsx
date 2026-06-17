import React, { useEffect, useMemo, useState } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { ArrowRight, Loader2, Search, X } from 'lucide-react';
import toast from 'react-hot-toast';

import EditorialMasthead from '@/components/layout/EditorialMasthead';
import { ContextAnchor, FragilityBadge, MobileBottomSheet, NotebookModeSwitch, WordBiographySheet } from '@/components/mobile';
import apiService, {
  GraphicNovelScene,
  MissionTargetVocabulary,
  RealWorldMission,
  SessionMessage,
  SessionOverview,
  VocabularyEvent,
  VocabularyDueContext,
  VocabularyBiography,
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
  { rating: 0, label: 'Again', hint: 'Bring it back soon', tone: 'red' },
  { rating: 1, label: 'Hard', hint: 'Keep it close', tone: 'yellow' },
  { rating: 2, label: 'Good', hint: 'Normal review', tone: 'blue' },
  { rating: 3, label: 'Easy', hint: 'Push it out', tone: 'black' },
] as const;

function reviewMessage(response: ReviewResponse | AnkiReviewResponse) {
  const next = 'due_at' in response ? response.due_at || response.next_review : response.next_review;
  const date = next ? new Date(next) : null;
  const label = date && !Number.isNaN(date.getTime())
    ? date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
    : '';
  return label ? `Scheduled for ${label}` : 'Review saved';
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

function queueWord(item: VocabularyRecommendationItem) {
  if (item.direction === 'de_to_fr') {
    return item.translations?.de || item.translations?.en || item.word;
  }
  return item.word || item.translations?.fr || '';
}

function queueTranslation(item: VocabularyRecommendationItem) {
  if (item.direction === 'de_to_fr') {
    return item.translations?.fr || item.word || '';
  }
  return item.translations?.de || item.translations?.en || '';
}

function queueDirection(item: VocabularyRecommendationItem) {
  if (item.direction === 'fr_to_de') return 'FR -> DE';
  if (item.direction === 'de_to_fr') return 'DE -> FR';
  return 'French 5000';
}

function deckTranslation(item: VocabularyWord) {
  return item.german_translation || item.english_translation || item.french_translation || item.definition || '';
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

function humanBucket(value?: string | null) {
  if (!value) return 'review';
  if (value === 'topic_compatible') return 'topic compatible';
  return value.replace(/_/g, ' ');
}

function humanEvent(value?: string | null) {
  if (!value) return 'Seen in practice';
  const labels: Record<string, string> = {
    seen_context: 'Seen in context',
    recognized: 'Recognized',
    produced_correct: 'Produced correctly',
    produced_incorrect: 'Produced with correction',
    missed_target: 'Missed target',
  };
  return labels[value] || value.replace(/_/g, ' ');
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
  return word?.part_of_speech || 'French';
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
  if ((message.target_words || []).includes(wordId)) bits.push('targeted');
  if ((message.words_used || []).includes(wordId)) bits.push('used');
  if ((message.suggested_words_used || []).includes(wordId)) bits.push('suggested');
  if ((message.target_details || []).some((item) => item.word_id === wordId)) bits.push('planned');
  return bits.length ? `Conversation ${bits.join(' / ')}` : 'Conversation context';
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
    source: 'French 5000',
    label: 'Example',
    text: detailExample(detail) || '',
    translation: queueItem?.example_translation || word?.example_translation,
  });
  addUniqueExample(examples, {
    source: 'French 5000',
    label: 'Definition',
    text: word?.definition || '',
    meta: word?.part_of_speech || null,
  });
  addUniqueExample(examples, {
    source: 'French 5000',
    label: 'Usage notes',
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
  return [
    { label: 'State', value: [progress?.state || queueItem?.state || 'new', queueItem?.phase].filter(Boolean).join(' / ') },
    { label: 'Scheduler', value: queueItem?.scheduler || 'fsrs' },
    { label: 'Due', value: formatDateLabel(dueAt) || 'Not scheduled' },
    { label: 'Last review', value: formatDateLabel(lastReview) || 'Not reviewed' },
    { label: 'Interval', value: formatDays(interval) || 'New card' },
    { label: 'Proficiency', value: `${progress?.proficiency_score ?? queueItem?.proficiency_score ?? 0}/100` },
    { label: 'Reviews', value: String(progress?.reviews_logged ?? progress?.reps ?? 0) },
    { label: 'Lapses', value: String(progress?.lapses ?? queueItem?.lapses ?? 0) },
    { label: 'Stability', value: formatDecimal(queueItem?.stability ?? progress?.stability) || '--' },
    { label: 'Difficulty', value: formatDecimal(queueItem?.difficulty ?? progress?.difficulty) || '--' },
    { label: 'Retrievability', value: formatPercent(queueItem?.retrievability) || '--' },
    { label: 'Priority', value: formatDecimal(queueItem?.priority_score, 1) || '--' },
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
          label: mission.title || 'Mission prompt',
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
          label: scene.title || 'Scene context',
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
        source: 'Session',
        label: session.topic || 'Conversation',
        description: messageReferenceDescription(match, wordId),
        date: match.created_at || session.started_at,
        href: `/learn/session/${session.id}`,
      });
      const target = (match.target_details || []).find((item) => item.word_id === wordId);
      if (target?.hint_sentence) {
        addUniqueExample(examples, {
          source: 'Session',
          label: session.topic || 'Conversation',
          text: target.hint_sentence,
          translation: target.hint_translation || target.translation,
          meta: target.familiarity || null,
        });
      } else {
        addUniqueExample(examples, {
          source: 'Session',
          label: `${match.sender} turn`,
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

function VocabularyNotebookState({
  title,
  body,
  loading = false,
  tone = 'empty',
  actionLabel,
  onAction,
}: {
  title: string;
  body: string;
  loading?: boolean;
  tone?: 'empty' | 'error';
  actionLabel?: string;
  onAction?: () => void;
}) {
  return (
    <div className={`vocab-empty vocab-state ${tone === 'error' ? 'error' : ''}`}>
      <div className="vocab-state-head">
        {loading ? <Loader2 className="animate-spin" size={16} /> : null}
        <strong>{title}</strong>
      </div>
      <p>{body}</p>
      {actionLabel && onAction && (
        <button type="button" onClick={onAction}>
          {actionLabel}
        </button>
      )}
      {loading && (
        <div className="vocab-state-skeleton" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
      )}
    </div>
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
  const [biographyWordId, setBiographyWordId] = useState<number | null>(null);
  const [biography, setBiography] = useState<VocabularyBiography | null>(null);
  const [biographyLoading, setBiographyLoading] = useState(false);
  const [biographyError, setBiographyError] = useState<string | null>(null);

  const refreshNotebookMirror = async () => {
    const [dossierResult, mapResult] = await Promise.all([
      settle(apiService.getWeeklyDossier({ period_days: 7 })),
      settle(apiService.getVocabularyMasteryMap({ limit: 5000, direction: 'fr_to_de' })),
    ]);
    if (dossierResult.status === 'fulfilled') setWeeklyDossier(dossierResult.value);
    if (mapResult.status === 'fulfilled') setMasteryMap(mapResult.value);
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
    ])
      .then(([contextResult, dossierResult, mapResult]) => {
        if (!alive) return;
        if (contextResult.status === 'fulfilled') {
          setContext(contextResult.value);
          setContextError(null);
        } else {
          setContext(null);
          setContextError('Could not load vocabulary notebook.');
        }
        if (dossierResult.status === 'fulfilled') setWeeklyDossier(dossierResult.value);
        if (mapResult.status === 'fulfilled') setMasteryMap(mapResult.value);
      })
      .catch((error) => {
        console.error(error);
        if (alive) {
          setContext(null);
          setContextError('Could not load vocabulary notebook.');
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
            setDeckError('Could not search the vocabulary deck.');
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
        if (alive) toast.error('Could not open linked vocabulary word.');
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
        setBiographyError('Could not load this word biography.');
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
      toast.error('Could not save vocabulary review.');
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
      toast.error('Could not create a vocabulary mission.');
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
      toast.error('Could not create a vocabulary Feuilleton.');
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
  const activeFilterLabel = filter === 'all' ? 'all states' : humanBucket(filter);

  function clearVocabularyFilters() {
    setFilter('all');
    setQuery('');
  }

  return (
    <>
      {!embedded && (
        <>
          <Head>
            <title>Vocabulary Notebook</title>
          </Head>
          <EditorialMasthead active="notebook" mobileAction={<Link className="vocab-mobile-action" href="/grammar">Rules</Link>} />
        </>
      )}
      <main className={`vocab-page ${embedded ? 'embedded' : ''}`}>
        {!embedded && (
          <>
            <header className="vocab-hero">
              <div className="vocab-kicker">REFERENCE LAYER</div>
              <h1>Vocabulary Notebook</h1>
              <div className="vocab-stats" aria-label="Vocabulary summary">
                <span><strong>{summary?.due || 0}</strong> due</span>
                <span><strong>{summary?.fragile || 0}</strong> fragile</span>
                <span><strong>{summary?.new || 0}</strong> new</span>
              </div>
              <Link className="vocab-review-link" href="/vocabulary/review">Atelier review path</Link>
            </header>
            <NotebookModeSwitch
              active="vocabulary"
              grammarMeta="Rules and traps"
              vocabularyMeta={`${summary?.due || 0} due · ${summary?.new || 0} new`}
              className="vocab-mode-switch"
            />
          </>
        )}

        <section className="vocab-weekly-dossier" aria-label="Weekly vocabulary dossier">
          <div>
            <span>Weekly dossier</span>
            <h2>{weeklyDossier?.headline || 'Semaine — assembling your vocabulary ledger.'}</h2>
          </div>
          <dl>
            <div>
              <dt>repairs</dt>
              <dd>{weeklyDossier?.stats.repairs_filed ?? 0}</dd>
            </div>
            <div>
              <dt>reviews</dt>
              <dd>{weeklyDossier?.stats.vocabulary_reviews ?? 0}</dd>
            </div>
            <div>
              <dt>seen</dt>
              <dd>{weeklyDossier?.stats.words_seen ?? 0}</dd>
            </div>
            <div>
              <dt>used</dt>
              <dd>{weeklyDossier?.stats.words_produced ?? 0}</dd>
            </div>
          </dl>
          <div className="vocab-weekly-threads">
            {(weeklyDossier?.fragile_threads.length ? weeklyDossier.fragile_threads : weeklyDossier?.next_actions || []).slice(0, 3).map((thread) => (
              <article key={`${thread.title}-${thread.tone}`}>
                <strong>{thread.title}</strong>
                {thread.subtitle && <em>{thread.subtitle}</em>}
              </article>
            ))}
          </div>
        </section>

        <section className="vocab-mastery-map" aria-label="French 5000 mastery map">
          <div className="vocab-section-head compact">
            <span>{masteryMap?.deck_label || 'French 5000'} map</span>
            <em>{masteryMap ? `${masteryMap.summary.total} cells` : 'loading'}</em>
          </div>
          <div className="vocab-map-grid" aria-hidden="true">
            {masteryCells.map((cell) => (
              <span
                key={cell.word_id}
                className={`vocab-map-cell ${cell.mastery_state}`}
                title={`${cell.word}${cell.frequency_rank ? ` #${cell.frequency_rank}` : ''}: ${cell.mastery_state}`}
              />
            ))}
          </div>
          <div className="vocab-map-legend">
            {(['new', 'due', 'fragile', 'building', 'solid', 'mastered'] as const).map((state) => (
              <span key={state}>
                <i className={state} />
                {state} {masteryMap?.summary[state] ?? 0}
              </span>
            ))}
          </div>
        </section>

        <section className="vocab-controls" aria-label="Vocabulary search and filters">
          <div className="vocab-search">
            <Search size={20} />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search French 5000"
              aria-label="Search vocabulary"
            />
            {activeVocabularySearch && (
              <button
                type="button"
                className="vocab-search-clear"
                onClick={() => setQuery('')}
                aria-label="Clear search"
              >
                <X size={16} />
              </button>
            )}
          </div>

          <nav className="vocab-tabs" aria-label="Vocabulary filters">
            {vocabularyFilters.map((item) => (
              <button key={item} className={filter === item ? 'active' : ''} type="button" onClick={() => setFilter(item)}>
                {item}
              </button>
            ))}
          </nav>

          <div className="vocab-filter-summary" aria-live="polite">
            <span>
              {loading || deckLoading
                ? 'Searching notebook'
                : `${todayItems.length} path ${todayItems.length === 1 ? 'card' : 'cards'} · ${filteredDeck.length} deck in ${activeFilterLabel}`}
            </span>
            {hasVocabularyFilters && (
              <button type="button" onClick={clearVocabularyFilters}>
                Clear filters
              </button>
            )}
          </div>
        </section>

        <section className="vocab-section-head">
          <span>Path review preview</span>
          <em>{todayItems.length} cards</em>
        </section>
        <div className="vocab-card-stack" aria-busy={loading}>
          {loading && <VocabularyNotebookState loading title="Loading notebook" body="Syncing today's words." />}
          {!loading && contextError && (
            <VocabularyNotebookState
              tone="error"
              title="Could not load notebook"
              body="We could not sync your words. Check the connection and try again."
              actionLabel="Retry"
              onAction={() => setContextRetry((value) => value + 1)}
            />
          )}
          {!loading && !contextError && todayItems.length === 0 && (
            <VocabularyNotebookState
              title="No words found"
              body={hasVocabularyFilters ? 'Try another filter or search term.' : 'No path cards are waiting here.'}
              actionLabel={hasVocabularyFilters ? 'Clear filters' : undefined}
              onAction={hasVocabularyFilters ? clearVocabularyFilters : undefined}
            />
          )}
          {todayItems.map((item) => (
            <button key={`${item.word_id}-${item.bucket}`} type="button" className="vocab-row queue-row" onClick={() => openDetail({ kind: 'queue', item })}>
              <span className={`vocab-dot ${item.bucket}`} />
              <span>
                <strong>{queueWord(item)}</strong>
                <em>{queueTranslation(item)} · {item.bucket}</em>
              </span>
              <FragilityBadge progress={item} compact />
              <b>{queueDirection(item)}</b>
            </button>
          ))}
        </div>

        <section className="vocab-section-head deck">
          <span>Deck browser</span>
          <em>{deckLoading ? 'searching' : `${filteredDeck.length} shown`}</em>
        </section>
        <div className="vocab-card-stack deck-list">
          {deckLoading && <VocabularyNotebookState loading title="Searching notebook" body="Checking French 5000." />}
          {!deckLoading && deckError && (
            <VocabularyNotebookState
              tone="error"
              title="Could not search deck"
              body="We could not sync the deck browser. Check the connection and try again."
              actionLabel="Retry"
              onAction={() => setDeckRetry((value) => value + 1)}
            />
          )}
          {!deckLoading && !deckError && filteredDeck.length === 0 && (
            <VocabularyNotebookState
              title="No words found"
              body="Try another search term."
              actionLabel={activeVocabularySearch ? 'Clear search' : undefined}
              onAction={activeVocabularySearch ? () => setQuery('') : undefined}
            />
          )}
          {filteredDeck.map((item) => (
            <button key={item.id} type="button" className="vocab-row deck-row" onClick={() => openDetail({ kind: 'deck', item })}>
              <span className="vocab-rank">{item.frequency_rank || '--'}</span>
              <span>
                <strong>{item.word}</strong>
                <em>
                  {deckTranslation(item) || 'translation pending'}
                  {masteryByWordId.get(item.id)
                    ? ` · ${humanBucket(masteryByWordId.get(item.id)?.mastery_state)} · ${Math.round(masteryByWordId.get(item.id)?.proficiency_score || 0)}%`
                    : ''}
                </em>
              </span>
              <b>{masteryByWordId.get(item.id)?.mastery_state || item.part_of_speech || 'FR'}</b>
            </button>
          ))}
        </div>
      </main>

      {detail && (
        <MobileBottomSheet
          ariaLabel={`Review ${detailWord(detail)}`}
          onClose={closeDetail}
          eyebrow="French 5000"
          title={detailWord(detail)}
          closeLabel="Close vocabulary detail"
          closeContent={<X size={18} />}
          sheetClassName="vocab-detail-sheet"
        >
            <div className="vocab-detail-meta" aria-label="Vocabulary details">
              <span>
                <strong>{detailRank ? `#${detailRank}` : '--'}</strong>
                <em>frequency rank</em>
              </span>
              <span>
                <strong>{detailSpeech}</strong>
                <em>part of speech</em>
              </span>
              <span>
                <strong>{detailLevel ? `L${detailLevel}` : '--'}</strong>
                <em>difficulty</em>
              </span>
              <span>
                <strong>{detail.kind === 'queue' ? humanBucket(detail.item.bucket) : 'deck'}</strong>
                <em>source</em>
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
                  <span className="vocab-card-face-label">PROMPT</span>
                  <p className="vocab-card-face-word">{detailWord(detail)}</p>
                  <div className="vocab-card-hint-text">Tap card to flip</div>
                </div>
                
                {/* BACK FACE */}
                <div className="vocab-flashcard-back">
                  <span className="vocab-card-face-label">ANSWER</span>
                  <p className="vocab-card-face-word">
                    {detailTranslation(detail) || detailMeaningForPractice(detail) || detailFrench(detail)}
                  </p>
                  <div className="vocab-card-hint-text">Tap card to flip back</div>
                </div>
                
              </div>
            </div>
            <ContextAnchor
              className="vocab-answer"
              label="Context anchor"
              text={detailExample(detail) || `${detailFrench(detail)} — ${detailTranslation(detail) || 'translation pending'}`}
              quote
            />
            <section className="vocab-detail-block">
              <div className="vocab-detail-block-head">
                <span>Examples by source</span>
                <em>{detailSupport.loading ? 'refreshing' : `${detailExampleGroups.reduce((count, group) => count + group.entries.length, 0)} notes`}</em>
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
                <p className="vocab-placeholder">Recent context will appear after use.</p>
              )}
            </section>
            <section className="vocab-detail-block">
              <div className="vocab-detail-block-head">
                <span>Progress / SRS</span>
                <em>{detailSupport.loading ? 'loading' : detailSupport.progress ? 'live' : 'new'}</em>
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
                <span>Recent traces</span>
                <em>{detailSupport.loading ? 'checking' : `${detailSupport.traces.length} found`}</em>
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
                <p className="vocab-placeholder">Recent context will appear after use.</p>
              )}
            </section>
            <div className="vocab-context-actions">
              <button type="button" onClick={openBiography}>
                Word biography
              </button>
              <button type="button" disabled={action !== null} onClick={createMission}>
                {action === 'mission' ? <Loader2 size={14} className="spin" /> : null}
                Use in mission
              </button>
              <button type="button" disabled={action !== null} onClick={createFeuilleton}>
                {action === 'feuilleton' ? <Loader2 size={14} className="spin" /> : null}
                Read in Feuilleton <ArrowRight size={13} />
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
          --paper: #f1ece1;
          --paper-2: #e8e0cf;
          --sheet: #f8f3e8;
          --ink: #14110d;
          --ink-2: #4a4538;
          --ink-3: #8a826f;
          --red: #d8321a;
          --blue: #1d3a8a;
          --yellow: #f3c318;
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
          background: #f08a78;
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
          background: #f08a78;
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
          border: 1px dashed rgba(20, 17, 13, .42);
          background: var(--paper-2);
        }
        :global(.vocab-state.error) {
          border-style: solid;
          border-left: 4px solid var(--red);
          background: #fbf6ea;
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
          border: 1px solid rgba(20, 17, 13, .18);
          background: linear-gradient(90deg, #e8e0cf, #fbf6ea, #e8e0cf);
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
          --paper: #f1ece1;
          --paper-2: #e8e0cf;
          --sheet: #f8f3e8;
          --ink: #14110d;
          --ink-2: #4a4538;
          --ink-3: #8a826f;
          --red: #d8321a;
          --blue: #1d3a8a;
          --yellow: #f3c318;
          position: fixed;
          inset: 0;
          z-index: 120;
        }
        .vocab-detail-scrim {
          position: absolute;
          inset: 0;
          border: 0;
          background: rgba(20, 17, 13, .42);
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
          box-shadow: 0 -20px 40px rgba(20, 17, 13, .18);
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
          box-shadow: 4px 4px 0px 0px var(--ink);
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
          border-top: 1px solid rgba(20, 17, 13, .18);
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
            box-shadow: 0 8px 18px rgba(20, 17, 13, .08);
          }
          .vocab-search {
            min-height: 44px;
            grid-template-columns: 16px minmax(0, 1fr) auto;
            gap: 10px;
            margin: 0 0 9px;
            background: #eee7da;
            padding: 6px 10px;
            transition: border-color .16s ease, background .16s ease, box-shadow .16s ease;
          }
          .vocab-search:focus-within {
            border-color: var(--blue);
            background: #fbf6ea;
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
          border: 1px solid #14110d;
          color: #14110d;
          text-decoration: none;
          font-size: 12px;
          font-weight: 900;
          text-transform: uppercase;
        }
      `}</style>
    </>
  );
}
