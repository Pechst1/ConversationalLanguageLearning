import React, { useEffect, useMemo, useState } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { useRouter } from 'next/router';
import toast from 'react-hot-toast';

import PhoneProductNav from '@/components/layout/PhoneProductNav';
import { learnerGloss } from '@/lib/glosses';
import { useChromeLanguage } from '@/lib/learner-language';
import {
  fill,
  formatDate,
  formatNumber,
  landingCounts,
  lexiqueCopy,
  nextReviewText,
  partOfSpeechLabel,
  plural,
  useLexCopy,
  type LexiqueCopy,
} from '@/components/lexique/lexique-copy';
import {
  Action,
  AtelierV2Root,
  BottomSheet,
  Chip,
  ShapeToken,
  Skeleton,
  StateBlock,
  Surface,
  WordToken,
  type ShapeKind,
} from '@/components/atelier-v2/ui';
import { FragilityBadge, WordBiographySheet } from '@/components/mobile';
import apiService, {
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

/* "Le lexique" — the registre, on the Claude design system (Atelier V2).
 *
 * The design has no artboard for the word list. It is extended from the
 * CAHIER artboard, which is the same shape of screen: a muted count line over
 * one Garamond-italic headline, the Règles / Mots pill switch, a 44px paper
 * search well, a row of pill filters (the active one on ink), then paper rows
 * (radius 16, padding 14/16) each with a 36px shape glyph, a 15px title, a 12px
 * muted meta line and three 5px progress bars on the right. Word rows reuse
 * that row exactly: the glyph is the WordToken (WP-D6 — gender as shape, the
 * article inside, colour = state; a word with no stored gender is plain), the
 * meta line prints rank · nature · state, the three bars are the mastery
 * ladder (never colour alone — the state is also printed in the meta line).
 *
 * Secondary tools — the atlas of coverage tracks, the Français 5000 mastery
 * map, the weekly dossier, the way into the conjugation drill — fold under
 * the rows as the design's paper surfaces. The word sheet is the system's
 * bottom sheet; the flip card inside it is the Lexique card at small size.
 * Every fetch, query param, filter and handoff is unchanged. The page also
 * renders embedded inside the Cahier shell (`embedded`), where it drops its
 * own masthead and tab bar. Gaps are recorded in the report. */

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

// The sheet's four FSRS grades keep their exact ratings (0–3). Each carries
// one of the design's shapes beside its label.
const reviewOptions = [
  { rating: 0, label: 'grade_again', hint: 'grade_again_hint', shape: 'action' },
  { rating: 1, label: 'grade_hard', hint: 'grade_hard_hint', shape: 'reward' },
  { rating: 2, label: 'grade_good', hint: 'grade_good_hint', shape: 'story' },
  { rating: 3, label: 'grade_easy', hint: 'grade_easy_hint', shape: 'done' },
] as const;

type MasteryState = 'new' | 'due' | 'fragile' | 'building' | 'solid' | 'mastered';

function reviewMessage(t: LexiqueCopy, response: ReviewResponse | AnkiReviewResponse) {
  const next = 'due_at' in response ? response.due_at || response.next_review : response.next_review;
  return nextReviewText(t, next);
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

function queueBucketLabel(t: LexiqueCopy, bucket?: string | null) {
  if (bucket === 'due') return t.state_due;
  if (bucket === 'fragile') return t.state_fragile;
  if (bucket === 'new') return t.state_new;
  if (bucket === 'linked') return t.bucket_linked;
  if (bucket === 'topic' || bucket === 'topic_compatible') return t.bucket_topic;
  return '';
}

function queueBucketState(bucket?: string | null): MasteryState {
  if (bucket === 'due') return 'due';
  if (bucket === 'fragile') return 'fragile';
  if (bucket === 'new') return 'new';
  return 'building';
}

function deckState(t: LexiqueCopy, masteryState?: string | null): { state: MasteryState; label: string } {
  switch (masteryState) {
    case 'mastered': return { state: 'mastered', label: t.state_mastered };
    case 'solid': return { state: 'solid', label: t.state_solid };
    case 'building': return { state: 'building', label: t.state_building };
    case 'fragile': return { state: 'fragile', label: t.state_fragile };
    case 'due': return { state: 'due', label: t.state_due };
    default: return { state: 'new', label: t.state_new };
  }
}

/* The design's four shapes, by what the state asks of the learner: ink square
   = done (mastered), blue circle = in progress (solid / building), yellow
   square = reward still being earned (new), red triangle = action (due /
   fragile). The three bars beside a row climb the same ladder. */
function stateShape(state: MasteryState): ShapeKind {
  switch (state) {
    case 'mastered': return 'done';
    case 'solid':
    case 'building': return 'story';
    case 'new': return 'reward';
    default: return 'action';
  }
}

function stateBars(state: MasteryState): number {
  switch (state) {
    case 'mastered': return 3;
    case 'solid': return 2;
    case 'building': return 1;
    case 'due':
    case 'fragile': return 1;
    default: return 0;
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
  return learnerGloss(detail.item) || detail.item.definition || '';
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

function formatDateLabel(t: LexiqueCopy, value?: string | null) {
  return formatDate(t, value, { month: 'short', day: 'numeric', year: 'numeric' });
}

function formatShortDate(t: LexiqueCopy, value?: string | null) {
  return formatDate(t, value, { month: 'short', day: 'numeric' });
}

function formatDays(t: LexiqueCopy, value?: number | null) {
  if (value === null || value === undefined) return '';
  return plural(t, 'day', value);
}

function trimSnippet(value?: string | null, max = 140) {
  const text = (value || '').replace(/\s+/g, ' ').trim();
  if (!text) return '';
  return text.length > max ? `${text.slice(0, max - 3).trim()}...` : text;
}

/* Bucket keys are scheduler internals; the Cahier prints the name of the pile
 * a word is sitting in, in the chrome language, never the raw key. */
function humanBucket(t: LexiqueCopy, value?: string | null) {
  return queueBucketLabel(t, value || 'due') || t.state_due;
}

function humanEvent(t: LexiqueCopy, value?: string | null) {
  if (!value) return t.event_default;
  const labels: Record<string, string> = {
    seen_context: t.event_seen_context,
    recognized: t.event_recognized,
    produced_correct: t.event_produced_correct,
    produced_incorrect: t.event_produced_incorrect,
    missed_target: t.event_missed_target,
  };
  return labels[value] || t.event_default;
}

/* The part-of-speech column on the imported deck was written by the enrichment
 * heuristics (scripts/enrich_vocabulary.py), not by a lexical source, and it is
 * wrong often enough to notice — `élire` and `approcher` are filed as
 * adjective/noun. Only a whitelisted key prints (PART_OF_SPEECH_LABELS in
 * components/lexique/lexique-copy.ts), as a label in the chrome language;
 * junk prints nothing rather than a guess stamped onto the page as a fact. */

/* FSRS card states, as the Cahier says them. */
function srsStateLabel(t: LexiqueCopy, value?: string | null) {
  const key = String(value || '').trim().toLowerCase();
  const labels: Record<string, string> = {
    new: t.state_new,
    learning: t.srs_learning,
    review: t.srs_review,
    reviewing: t.srs_review,
    relearning: t.srs_relearning,
  };
  return labels[key] || t.state_new;
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

function detailPartOfSpeech(t: LexiqueCopy, detail: VocabularyDetail, supportWord?: VocabularyWord | null) {
  const word = detailDeckWord(detail, supportWord);
  // An unknown value gets the same em dash as every other blank; nothing is
  // printed as a part of speech that the whitelist does not recognise.
  return partOfSpeechLabel(t, word?.part_of_speech);
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

function messageReferenceDescription(t: LexiqueCopy, message: SessionMessage, wordId: number) {
  const bits = [];
  if ((message.target_words || []).includes(wordId)) bits.push(t.conv_targeted);
  if ((message.words_used || []).includes(wordId)) bits.push(t.conv_used);
  if ((message.suggested_words_used || []).includes(wordId)) bits.push(t.conv_suggested);
  if ((message.target_details || []).some((item) => item.word_id === wordId)) bits.push(t.conv_planned);
  return bits.length ? fill(t.conv_prefix, { bits: bits.join(', ') }) : t.conv_passage;
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

function groupExamples(t: LexiqueCopy, detail: VocabularyDetail, support: DetailSupport) {
  const examples: DetailExample[] = [];
  const word = detailDeckWord(detail, support.word);
  const queueItem = detailQueueItem(detail);
  addUniqueExample(examples, {
    source: 'Français 5000',
    label: t.ex_example,
    text: detailExample(detail) || '',
    translation: queueItem?.example_translation || word?.example_translation,
  });
  addUniqueExample(examples, {
    source: 'Français 5000',
    label: t.ex_definition,
    text: word?.definition || '',
    meta: partOfSpeechLabel(t, word?.part_of_speech) || null,
  });
  addUniqueExample(examples, {
    source: 'Français 5000',
    label: t.ex_usage,
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

function srsRows(t: LexiqueCopy, detail: VocabularyDetail, support: DetailSupport) {
  const queueItem = detailQueueItem(detail);
  const progress = support.progress;
  const dueAt = queueItem?.due_at || progress?.next_review || queueItem?.next_review || null;
  const lastReview = optionalStringField(queueItem, 'last_review') || progress?.last_review || null;
  const interval = queueItem?.interval_days ?? queueItem?.scheduled_days ?? progress?.scheduled_days;
  // The scheduler's own working numbers are corrector internals. What stays is
  // the part of the record a learner can actually recognise: where the word
  // stands, when it comes back, and how often they have met it.
  return [
    { label: t.srs_state, value: srsStateLabel(t, progress?.state || queueItem?.state) },
    { label: t.srs_next, value: formatDateLabel(t, dueAt) || t.srs_next_none },
    { label: t.srs_last, value: formatDateLabel(t, lastReview) || t.srs_last_none },
    { label: t.srs_interval, value: formatDays(t, interval) || t.srs_interval_none },
    { label: t.srs_reviews, value: String(progress?.reviews_logged ?? progress?.reps ?? 0) },
    { label: t.srs_lapses, value: String(progress?.lapses ?? queueItem?.lapses ?? 0) },
  ];
}

async function fetchVocabularyUsageSupport(t: LexiqueCopy, wordId: number) {
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
          source: 'Courrier',
          label: mission.title || 'Courrier',
          description: t.trace_letter,
          date: entityDate(mission),
          href: `/missions?mission=${mission.id}`,
        });
      }
      if (target?.example_sentence) {
        addUniqueExample(examples, {
          source: 'Courrier',
          label: mission.title || t.ex_letter_fallback,
          text: target.example_sentence,
          translation: target.example_translation || target.translation,
          meta: mission.status,
        });
      }
      events.slice(0, 3).forEach((event) => {
        traces.push({
          source: 'Courrier',
          label: mission.title || 'Courrier',
          description: [humanEvent(t, event.event_type), event.reason].filter(Boolean).join(' · '),
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
          description: t.trace_scene,
          date: entityDate(scene),
          href: `/graphic-novel?scene=${scene.id}`,
        });
      }
      if (target?.example_sentence) {
        addUniqueExample(examples, {
          source: 'Feuilleton',
          label: scene.title || t.ex_scene_fallback,
          text: target.example_sentence,
          translation: target.example_translation || target.translation,
          meta: scene.status,
        });
      }
      events.slice(0, 3).forEach((event) => {
        traces.push({
          source: 'Feuilleton',
          label: scene.title || 'Feuilleton',
          description: [humanEvent(t, event.event_type), event.reason].filter(Boolean).join(' · '),
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
        source: t.conversation,
        label: session.topic || t.conversation,
        description: messageReferenceDescription(t, match, wordId),
        date: match.created_at || session.started_at,
        // No href: the conversation-session viewer went with the /learn cluster.
        // Where the word was met is still true and still worth showing; only the
        // link to a page that no longer exists is gone.
      });
      const target = (match.target_details || []).find((item) => item.word_id === wordId);
      if (target?.hint_sentence) {
        addUniqueExample(examples, {
          source: t.conversation,
          label: session.topic || t.conversation,
          text: target.hint_sentence,
          translation: target.hint_translation || target.translation,
          meta: target.familiarity || null,
        });
      } else {
        addUniqueExample(examples, {
          source: t.conversation,
          label: match.sender === 'user' ? t.ex_your_turn : t.ex_reply,
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

// ---------------------------------------------------------------------------
// Presentation primitives, extended from the design's Cahier artboard.
// ---------------------------------------------------------------------------

/* The Cahier masthead: count line, the one headline, and the Règles / Mots
   pill switch. `route` is the current register; `xlink` the sibling. */
function LxMasthead({
  count,
  route,
  xlink,
  xlinkHref,
}: {
  count: string;
  route: string;
  xlink: string;
  xlinkHref: string;
}) {
  return (
    <header className="lx-mast">
      <div className="lx-mast__main">
        {count && <p className="lx-mast__count">{count}</p>}
        {/* the one Garamond-italic headline on this screen */}
        <h1 className="av2-headline av2-headline--screen">Le lexique</h1>
      </div>
      <nav className="lx-switch" aria-label="Le cahier">
        <Link className="lx-switch__tab" href={xlinkHref}>{xlink}</Link>
        <span className="lx-switch__tab" aria-current="page">{route}</span>
      </nav>
    </header>
  );
}

function LxSearch({ value, onChange }: { value: string; onChange: (next: string) => void }) {
  const t = useLexCopy();
  return (
    <label className="lx-search">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" aria-hidden="true">
        <circle cx="11" cy="11" r="7" />
        <path d="M20 20l-3.5-3.5" />
      </svg>
      <span className="av2-sr">{t.search_label}</span>
      <input
        className="lx-search__input lx-input"
        type="search"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={t.search_placeholder}
        autoComplete="off"
        autoCapitalize="off"
      />
      {value && (
        <button type="button" className="lx-search__clear" onClick={() => onChange('')} aria-label={t.search_clear}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" aria-hidden="true">
            <path d="M6 6l12 12M18 6L6 18" />
          </svg>
        </button>
      )}
    </label>
  );
}

function LxSectionHead({ title, note, tone }: { title: string; note?: string; tone?: 'story' }) {
  return (
    <div className="lx-section-head">
      <p className={['av2-label', tone === 'story' ? 'av2-label--story' : null].filter(Boolean).join(' ')}>{title}</p>
      {note && <span className="av2-label lx-section-head__note">{note}</span>}
    </div>
  );
}

/* One design row: word token, title, meta, three bars. The token is the
   word's gender as a shape (WP-D6) in the colour of its state; the bars keep
   the mastery ladder. */
function LxWordRow({
  word,
  meta,
  state,
  stateLabel,
  gender,
  partOfSpeech,
  onSelect,
}: {
  word: string;
  meta: string;
  state: MasteryState;
  stateLabel: string;
  gender?: string | null;
  partOfSpeech?: string | null;
  onSelect: () => void;
}) {
  const bars = stateBars(state);
  const shape = stateShape(state);
  return (
    <button type="button" className="lx-row" onClick={onSelect} role="listitem">
      <WordToken word={word} gender={gender} partOfSpeech={partOfSpeech} state={state} />
      <span className="lx-row__main">
        <span className="lx-row__title">{word}</span>
        <span className="lx-row__meta">{meta}</span>
      </span>
      <span className="lx-row__bars" role="img" aria-label={stateLabel}>
        {[1, 2, 3].map((step) => (
          <i key={step} data-on={step <= bars ? shape : undefined} />
        ))}
      </span>
    </button>
  );
}

function LxSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className="lx-rows" aria-hidden="true">
      {Array.from({ length: rows }).map((_, index) => (
        <Skeleton key={index} height={64} radius={16} />
      ))}
    </div>
  );
}

/* A coverage track: label, count, and the design's progress rule. Ink for the
   whole-deck line, blue (information) for every other track. */
function LxTrack({ label, value, max, tone }: { label: string; value: number; max: number; tone?: 'ink' }) {
  const t = useLexCopy();
  const safeMax = Math.max(1, max);
  const percent = Math.min(100, Math.round((Math.max(0, value) / safeMax) * 100));
  return (
    <div className="lx-track">
      <div className="lx-track__head">
        <span className="lx-track__label">{label}</span>
        <span className="av2-label">{formatNumber(t, value)} / {formatNumber(t, max)}</span>
      </div>
      <div
        className="av2-progress__track"
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={safeMax}
        aria-valuenow={Math.min(value, safeMax)}
      >
        <div className="av2-progress__fill lx-track__fill" data-tone={tone} style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
}

type MapTotal = { id: MasteryState; label: string; n: number };

/* The Français 5000 mastery map: one cell per word by frequency rank, coloured
   by the state's shape token; the totals beneath print every state in words. */
function LxMasteryMap({ cells, totals, note }: { cells: MasteryState[]; totals: MapTotal[]; note: string }) {
  const t = useLexCopy();
  return (
    <Surface className="lx-map" aria-label={t.map_aria}>
      <div className="lx-map__grid" aria-hidden="true">
        {cells.map((state, index) => (
          <i key={index} data-state={state} />
        ))}
      </div>
      <ul className="lx-map__totals">
        {totals.map((total) => (
          <li key={total.id}>
            <ShapeToken kind={stateShape(total.id)} size="sm" className={`lx-map__token lx-map__token--${total.id}`} />
            <span>{total.label}</span>
            <strong>{formatNumber(t, total.n)}</strong>
          </li>
        ))}
      </ul>
      <p className="av2-body lx-map__note">{note}</p>
    </Surface>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

interface VocabularyPageProps {
  embedded?: boolean;
}

export default function VocabularyPage({ embedded = false }: VocabularyPageProps = {}) {
  const router = useRouter();
  // WP-82: the Lexique has no journey envelope; the profile's language and
  // CEFR estimate pick its chrome (the learner's language up to A2, French
  // from B1). The page reads the table directly; everything under its
  // AtelierV2Root reads the same language through `useLexCopy()`.
  const language = useChromeLanguage();
  const t = lexiqueCopy(language);
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
          setContextError('unavailable');
        }
        if (dossierResult.status === 'fulfilled') setWeeklyDossier(dossierResult.value);
        if (mapResult.status === 'fulfilled') setMasteryMap(mapResult.value);
        if (coverageResult.status === 'fulfilled') setCoverage(coverageResult.value);
      })
      .catch((error) => {
        console.error(error);
        if (alive) {
          setContext(null);
          setContextError('unavailable');
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
            setDeckError('unavailable');
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
      settle(fetchVocabularyUsageSupport(t, wordId)),
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
  }, [detail, t]);

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
        if (alive) toast.error(t.word_open_failed);
      });
    return () => {
      alive = false;
    };
  }, [router.isReady, router.query.word, context, deck, detail, t]);

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
        setBiographyError('unavailable');
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
      toast.success(reviewMessage(t, response));
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
      toast.error(t.review_failed);
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
      toast.error(t.letter_failed);
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
      toast.error(t.episode_failed);
    } finally {
      setAction(null);
    }
  };

  const summary = context?.summary;
  const detailExampleGroups = detail ? groupExamples(t, detail, detailSupport) : [];
  const detailSrsRows = detail ? srsRows(t, detail, detailSupport) : [];
  const detailRank = detail ? detailFrequencyRank(detail, detailSupport.word) : null;
  const detailSpeech = detail ? detailPartOfSpeech(t, detail, detailSupport.word) : '';
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

  // The filter pills carry no counts: the due count is said once, on the
  // primary (Appendix A «Mots»), and the other piles once, in the count line.
  const vocabChips: Array<{ id: VocabularyFilter; label: string }> = [
    { id: 'all', label: t.chip_all },
    { id: 'due', label: t.chip_due },
    { id: 'fragile', label: t.chip_fragile },
    { id: 'new', label: t.chip_new },
    { id: 'mastered', label: t.chip_mastered },
  ];

  const mapCells: MasteryState[] = masteryCells.slice(0, 280).map((cell) => deckState(t, cell.mastery_state).state);
  const mapTotals: MapTotal[] = masteryMap
    ? [
        { id: 'due', label: t.chip_due, n: masteryMap.summary.due || 0 },
        { id: 'fragile', label: t.chip_fragile, n: masteryMap.summary.fragile || 0 },
        { id: 'building', label: t.map_building, n: masteryMap.summary.building || 0 },
        { id: 'solid', label: t.map_solid, n: masteryMap.summary.solid || 0 },
        { id: 'mastered', label: t.chip_mastered, n: masteryMap.summary.mastered || 0 },
        { id: 'new', label: t.chip_new, n: masteryMap.summary.new || 0 },
      ]
    : [];

  // Appendix A «Mots»: the due count is said once, on the primary; the
  // masthead's count line names only the two other piles.
  const { countLine, cta } = landingCounts(t, summary, loading);

  const shownCount = plural(t, 'shown', filteredDeck.length);

  const thread = weeklyDossier?.fragile_threads?.[0] || weeklyDossier?.next_actions?.[0] || null;

  const landing = (
    <>
      {embedded && countLine && <p className="lx-mast__count">{countLine}</p>}

      {/* the one tactile 3D press on this screen: the way into the review,
          and the one place the due count is said */}
      <Link className="av2-btn av2-btn--primary lx-cta" href="/vocabulary/review">
        <ShapeToken kind="action" size="sm" />
        {cta}
      </Link>

      <LxSearch value={query} onChange={setQuery} />

      <div className="lx-chips" role="group" aria-label={t.filter_group}>
        {vocabChips.map((chip) => (
          <button
            key={chip.id}
            type="button"
            className="lx-chip"
            aria-pressed={filter === chip.id}
            onClick={() => setFilter(chip.id)}
          >
            {chip.label}
          </button>
        ))}
      </div>

      <div className="lx-livesum" aria-live="polite">
        {hasVocabularyFilters && !deckLoading && <span className="av2-sr">{shownCount}</span>}
        {hasVocabularyFilters && (
          <Action tone="quiet" inline onClick={clearVocabularyFilters}>{t.filter_clear}</Action>
        )}
      </div>

      <LxSectionHead title={t.queue_title} />
      {loading ? (
        <LxSkeleton rows={4} />
      ) : contextError ? (
        <StateBlock
          tone="error"
          title={t.queue_error_title}
          body={t.queue_error_body}
          action={{ label: t.retry, onSelect: () => setContextRetry((v) => v + 1) }}
        />
      ) : todayItems.length === 0 ? (
        <StateBlock
          tone="empty"
          title={t.queue_empty_title}
          body={hasVocabularyFilters ? t.queue_empty_filtered : t.queue_empty_body}
          action={hasVocabularyFilters ? { label: t.queue_clear_filters, onSelect: clearVocabularyFilters } : undefined}
        />
      ) : (
        <div className="lx-rows" role="list">
          {todayItems.map((item) => {
            const state = queueBucketState(item.bucket);
            const label = queueBucketLabel(t, item.bucket) || t.state_due;
            return (
              <LxWordRow
                key={`${item.word_id}-${item.bucket}`}
                word={queueWord(item)}
                meta={[queueTranslation(item), label].filter(Boolean).join(' · ')}
                state={state}
                stateLabel={label}
                // A reverse card prints the gloss, not the French word: its
                // gender would describe a word that is not on the row.
                gender={item.direction === 'de_to_fr' ? null : item.gender}
                partOfSpeech={item.direction === 'de_to_fr' ? null : item.part_of_speech}
                onSelect={() => openDetail({ kind: 'queue', item })}
              />
            );
          })}
        </div>
      )}

      <LxSectionHead
        title={t.registre_title}
        tone="story"
        note={deckLoading ? t.searching : shownCount}
      />
      {deckLoading ? (
        <LxSkeleton rows={4} />
      ) : deckError ? (
        <StateBlock
          tone="error"
          title={t.registre_error_title}
          body={t.registre_error_body}
          action={{ label: t.retry, onSelect: () => setDeckRetry((v) => v + 1) }}
        />
      ) : filteredDeck.length === 0 ? (
        <StateBlock
          tone="empty"
          title={t.registre_empty_title}
          body={t.registre_empty_body}
          action={activeVocabularySearch ? { label: t.search_clear, onSelect: () => setQuery('') } : undefined}
        />
      ) : (
        <div className="lx-rows" role="list">
          {filteredDeck.map((item) => {
            const cell = masteryByWordId.get(item.id);
            const st = deckState(t, cell?.mastery_state);
            // A word with no gloss on file simply shows none; nothing promises
            // a translation nobody is going to write.
            const meta = [
              deckTranslation(item) || '—',
              item.frequency_rank ? fill(t.rank, { n: formatNumber(t, item.frequency_rank) }) : '',
              partOfSpeechLabel(t, item.part_of_speech),
              st.label,
            ].filter(Boolean).join(' · ');
            return (
              <LxWordRow
                key={item.id}
                word={item.word}
                meta={meta}
                state={st.state}
                stateLabel={st.label}
                gender={item.gender}
                partOfSpeech={item.part_of_speech}
                onSelect={() => openDetail({ kind: 'deck', item })}
              />
            );
          })}
        </div>
      )}

      {coverage && (
        <section className="lx-atlas" aria-label={t.atlas_title}>
          <button
            type="button"
            className="lx-fold"
            aria-expanded={atlasOpen}
            onClick={() => setAtlasOpen((open) => !open)}
          >
            <span className="lx-fold__main">
              <span className="lx-row__title">{t.atlas_title}</span>
              <span className="lx-row__meta">
                {fill(t.atlas_meta, {
                  nailed: formatNumber(t, cefrTotals.nailed),
                  total: formatNumber(t, cefrTotals.total || 5000),
                })}
              </span>
            </span>
            <span className="av2-label lx-fold__toggle">{atlasOpen ? t.atlas_close : t.atlas_open}</span>
          </button>
          {atlasOpen && (
            <div className="av2-stack lx-atlas__body">
              <LxSectionHead title={t.cefr_title} note={t.cefr_note} />
              <Surface className="av2-stack">
                {(coverage.cefr_bar || []).map((band, i) => (
                  <LxTrack
                    key={band.band}
                    label={band.band}
                    value={band.nailed || 0}
                    max={band.total || Math.max(1, Math.round((band.nailed || 0) / Math.max(0.01, (band.percent || 0) / 100)))}
                    tone={i === 0 ? 'ink' : undefined}
                  />
                ))}
              </Surface>
              {topicCats.length > 0 && (
                <>
                  <LxSectionHead title={t.topics_title} tone="story" note={fill(t.topics_note, { n: topicCats.length })} />
                  <Surface className="av2-stack">
                    {topicCats.map((track) => (
                      <LxTrack key={track.id} label={track.label} value={track.nailed || 0} max={track.total || 1} />
                    ))}
                  </Surface>
                </>
              )}
              {(coverage.verb_tracks || []).length > 0 && (
                <>
                  <LxSectionHead title={t.verbs_title} tone="story" note={t.verbs_note} />
                  <Surface className="av2-stack">
                    <LxTrack label={t.verbs_track} value={verbSummary.nailed || 0} max={verbSummary.total || 1} tone="ink" />
                    {/* The verbs block is where a learner is already looking
                        at their conjugation standing, so the way into the
                        drill belongs here. */}
                    <Link className="av2-btn av2-btn--secondary" href="/vocabulary/conjugation">
                      {t.verbs_cta}
                    </Link>
                  </Surface>
                </>
              )}
              {masteryMap && mapCells.length > 0 && (
                <>
                  <LxSectionHead title={t.map_title} note={t.map_cell} />
                  <LxMasteryMap
                    cells={mapCells}
                    totals={mapTotals}
                    note={fill(t.map_note, { n: mapCells.length })}
                  />
                </>
              )}
            </div>
          )}
        </section>
      )}

      {weeklyDossier && (
        <Surface as="section" shape="hero" className="lx-dossier" aria-label={t.dossier_label}>
          <p className="av2-label">{t.dossier_label}</p>
          {/* Sans, not Garamond: «Le lexique» is the one headline on this screen. */}
          <h2 className="lx-dossier__title">{weeklyDossier.headline || t.dossier_fallback}</h2>
          <dl className="lx-dossier__stats">
            <div><dt className="av2-label">{t.dossier_repairs}</dt><dd>{weeklyDossier.stats.repairs_filed ?? 0}</dd></div>
            <div><dt className="av2-label">{t.dossier_reviews}</dt><dd>{weeklyDossier.stats.vocabulary_reviews ?? 0}</dd></div>
            <div><dt className="av2-label">{t.dossier_seen}</dt><dd>{weeklyDossier.stats.words_seen ?? 0}</dd></div>
            <div><dt className="av2-label">{t.dossier_used}</dt><dd>{weeklyDossier.stats.words_produced ?? 0}</dd></div>
          </dl>
          {thread && (
            <div className="lx-dossier__thread">
              <ShapeToken kind="action" size="sm" />
              <span>
                <b>{thread.title}</b>
                {thread.subtitle && <em className="av2-body">{thread.subtitle}</em>}
              </span>
            </div>
          )}
        </Surface>
      )}
    </>
  );

  /* The two faces used to be stamped "LE MOT" / "LA RÉPONSE" in tracked caps;
     the design's sentence-case side labels replace them. */
  const practiceCard = detail && (
    <div
      className="lx-card lx-card--mini"
      data-face={practiceRevealed ? 'back' : 'front'}
      role="button"
      tabIndex={0}
      aria-pressed={practiceRevealed}
      aria-label={practiceRevealed ? t.flip_back : t.flip_front}
      onClick={() => setPracticeRevealed((current) => !current)}
      onKeyDown={(event) => {
        if (event.key === ' ' || event.key === 'Enter') {
          event.preventDefault();
          setPracticeRevealed((current) => !current);
        }
      }}
    >
      <div className="lx-card__top">
        <span>{practiceRevealed ? t.flip_back : t.flip_front}</span>
        <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true"><path d="M7 0L14 14H0Z" fill="currentColor" /></svg>
      </div>
      <p className="av2-headline lx-card__word">
        {practiceRevealed
          ? detailTranslation(detail) || detailMeaningForPractice(detail) || detailFrench(detail)
          : detailWord(detail)}
      </p>
      {practiceRevealed && detailExample(detail) && (
        <p className="av2-fr lx-card__example">« {detailExample(detail)} »</p>
      )}
    </div>
  );

  const content = (
    <>
      {!embedded && (
        <LxMasthead count={countLine} route="Vocabulaire" xlink="Grammaire" xlinkHref="/grammar" />
      )}
      <div className="lx-body">{landing}</div>

      {detail && (
        <BottomSheet open={Boolean(detail)} title={detailWord(detail)} eyebrow="Français 5000" onClose={closeDetail}>
          <div className="av2-stack lx-sheet">
            <div className="lx-meta" aria-label={t.details_label}>
              <Surface shape="tile"><span className="av2-label">{t.tile_rank}</span><strong>{detailRank ? `#${formatNumber(t, detailRank)}` : '—'}</strong></Surface>
              <Surface shape="tile"><span className="av2-label">{t.tile_nature}</span><strong>{detailSpeech || '—'}</strong></Surface>
              <Surface shape="tile"><span className="av2-label">{t.tile_level}</span><strong>{detailLevel ? `N${detailLevel}` : '—'}</strong></Surface>
              <Surface shape="tile"><span className="av2-label">{t.tile_source}</span><strong>{detail.kind === 'queue' ? humanBucket(t, detail.item.bucket) : t.source_registre}</strong></Surface>
            </div>
            <FragilityBadge
              progress={detail.kind === 'queue' ? detail.item : detailSupport.progress}
              showReason
            />

            {practiceCard}

            <Surface className="lx-anchor">
              <p className="av2-label">{t.anchor_label}</p>
              <p className="av2-fr lx-anchor__text">
                « {detailExample(detail) || [detailFrench(detail), detailTranslation(detail)].filter(Boolean).join(' — ')} »
              </p>
            </Surface>

            <section className="lx-block" aria-label={t.examples_title}>
              <LxSectionHead
                title={t.examples_title}
                note={detailSupport.loading
                  ? t.loading_note
                  : plural(t, 'example', detailExampleGroups.reduce((count, group) => count + group.entries.length, 0))}
              />
              {detailExampleGroups.length > 0 ? (
                <div className="av2-stack">
                  {detailExampleGroups.map((group) => (
                    <Surface as="article" key={group.source} className="lx-group">
                      <div className="lx-group__head">
                        <strong>{group.source}</strong>
                        <Chip tone="quiet">{group.entries.length}</Chip>
                      </div>
                      {group.entries.map((entry) => (
                        <div key={`${group.source}-${entry.label}-${entry.text}`} className="lx-entry">
                          <span className="av2-label av2-label--story">{entry.label}</span>
                          <p className="av2-fr lx-entry__text">{entry.text}</p>
                          {entry.translation && <p className="av2-body">{entry.translation}</p>}
                          {entry.meta && <p className="av2-label">{entry.meta}</p>}
                        </div>
                      ))}
                    </Surface>
                  ))}
                </div>
              ) : (
                <p className="av2-body lx-placeholder">{t.examples_empty}</p>
              )}
            </section>

            <section className="lx-block" aria-label={t.tracking_title}>
              <LxSectionHead
                title={t.tracking_title}
                note={detailSupport.loading ? t.loading_note : detailSupport.progress ? t.tracking_current : t.tracking_never}
              />
              <div className="lx-meta lx-meta--srs">
                {detailSrsRows.map((row) => (
                  <Surface shape="tile" key={row.label}>
                    <span className="av2-label">{row.label}</span>
                    <strong>{row.value}</strong>
                  </Surface>
                ))}
              </div>
            </section>

            <section className="lx-block" aria-label={t.traces_title}>
              <LxSectionHead
                title={t.traces_title}
                note={detailSupport.loading ? t.loading_note : plural(t, 'trace', detailSupport.traces.length)}
              />
              {detailSupport.traces.length > 0 ? (
                <div className="lx-rows">
                  {detailSupport.traces.map((trace) => {
                    const body = (
                      <>
                        <span className="lx-row__main">
                          <span className="av2-label av2-label--story">{trace.source}</span>
                          <span className="lx-row__title">{trace.label}</span>
                          <span className="lx-row__meta">{[trace.description, formatShortDate(t, trace.date)].filter(Boolean).join(' · ')}</span>
                        </span>
                      </>
                    );
                    return trace.href ? (
                      <Link key={traceKey(trace)} href={trace.href} className="lx-row">{body}</Link>
                    ) : (
                      <div key={traceKey(trace)} className="lx-row">{body}</div>
                    );
                  })}
                </div>
              ) : (
                <p className="av2-body lx-placeholder">{t.traces_empty}</p>
              )}
            </section>

            <div className="lx-actions">
              <Action tone="secondary" onClick={openBiography} icon={<ShapeToken kind="story" size="sm" />}>
                {t.action_biography}
              </Action>
              <Action
                tone="secondary"
                pending={action === 'mission'}
                pendingLabel={t.composing}
                disabled={action !== null}
                onClick={createMission}
                icon={<ShapeToken kind="action" size="sm" />}
              >
                {t.action_letter}
              </Action>
              <Action
                tone="secondary"
                pending={action === 'feuilleton'}
                pendingLabel={t.composing}
                disabled={action !== null}
                onClick={createFeuilleton}
                icon={<ShapeToken kind="story" size="sm" />}
              >
                {t.action_feuilleton}
              </Action>
            </div>

            <div className="lx-ratings" role="group" aria-label={t.ratings_group}>
              {!practiceRevealed && <p className="av2-label lx-ratings__note">{t.ratings_note}</p>}
              {reviewOptions.map((option) => (
                <Action
                  key={option.rating}
                  tone="secondary"
                  pending={reviewing}
                  pendingLabel={t[option.label]}
                  disabled={!practiceRevealed}
                  onClick={() => review(option.rating)}
                  icon={<ShapeToken kind={option.shape} size="sm" />}
                  title={t[option.hint]}
                >
                  {t[option.label]}
                  <span className="av2-sr"> · {t[option.hint]}</span>
                </Action>
              ))}
            </div>
          </div>
        </BottomSheet>
      )}

      <WordBiographySheet
        open={Boolean(biographyWordId)}
        biography={biography}
        loading={biographyLoading}
        error={biographyError ? t.biography_failed : null}
        onClose={() => setBiographyWordId(null)}
      />
    </>
  );

  return (
    <>
      {!embedded && (
        <Head>
          <title>{t.head_title}</title>
        </Head>
      )}
      {embedded ? (
        <AtelierV2Root as="div" language={language} className="lx-page lx-page--embedded" aria-label="Le lexique">
          {content}
        </AtelierV2Root>
      ) : (
        <AtelierV2Root as="main" language={language} className="lx-page" aria-label="Le lexique">
          {content}
        </AtelierV2Root>
      )}
      {!embedded && <PhoneProductNav active="notebook" placement="embedded" />}

      <style jsx global>{`
        .av2.lx-page {
          display: block;
          width: 100%;
          max-width: 720px;
          margin: 0 auto;
          min-height: 100vh;
          padding: 0 0 calc(24px + var(--av2-safe-bottom));
        }
        .av2.lx-page--embedded { min-height: auto; background: transparent; padding-bottom: 8px; }
        .av2 .lx-body { display: flex; flex-direction: column; gap: 12px; min-width: 0; padding: 16px var(--av2-gutter) 0; }
        .av2.lx-page--embedded .lx-body { padding: 8px 0 0; }

        /* Masthead — the Cahier artboard: count over headline, pill switch. */
        .av2 .lx-mast {
          display: flex;
          align-items: flex-end;
          justify-content: space-between;
          gap: 12px;
          min-width: 0;
          padding: calc(18px + env(safe-area-inset-top, 0px)) var(--av2-gutter) 0;
        }
        .av2 .lx-mast__main { min-width: 0; }
        .av2 .lx-mast__count { margin: 0 0 3px; font-size: var(--av2-t-label); font-weight: 600; color: var(--av2-muted); overflow-wrap: anywhere; }
        .av2 .lx-switch { display: flex; flex: none; padding: 3px; border-radius: var(--av2-r-pill); background: var(--av2-line); }
        .av2 .lx-switch__tab {
          position: relative;
          display: inline-flex;
          align-items: center;
          min-height: 30px;
          padding: 0 13px;
          border: 0;
          border-radius: var(--av2-r-pill);
          background: transparent;
          color: var(--av2-muted);
          font-size: var(--av2-t-meta);
          font-weight: 700;
          text-decoration: none;
        }
        .av2 .lx-switch__tab[aria-current='page'] { background: var(--av2-ink); color: var(--av2-on-ink); }
        /* The pill stays 30px as drawn; the tap target around it is the floor. */
        .av2 .lx-switch__tab::after {
          content: '';
          position: absolute;
          left: 0;
          right: 0;
          top: 50%;
          height: var(--av2-tap);
          transform: translateY(-50%);
        }
        .av2 .lx-cta { margin-top: 2px; }

        /* Search well: 44px, radius 14, card face. */
        .av2 .lx-search {
          display: flex;
          align-items: center;
          gap: 10px;
          min-height: var(--av2-tap);
          padding: 0 14px;
          border-radius: 14px;
          background: var(--av2-card);
          color: var(--av2-muted);
          cursor: text;
        }
        .av2 .lx-search svg { flex: none; }
        .av2 .lx-search__input { flex: 1 1 auto; min-width: 0; padding: 0; background: transparent; color: var(--av2-ink); font-family: inherit; font-size: var(--av2-t-body-lg); }
        .av2 .lx-search__input::placeholder { color: var(--av2-muted); opacity: 1; }
        .av2 .lx-search__input::-webkit-search-cancel-button { display: none; }
        .av2 .lx-search__clear {
          position: relative;
          display: grid;
          place-items: center;
          flex: none;
          width: 32px;
          height: 32px;
          margin-right: -6px;
          border: 0;
          border-radius: var(--av2-r-pill);
          background: var(--av2-line);
          color: var(--av2-ink);
          cursor: pointer;
        }
        /* The disc stays 32px as drawn; the tap target around it is the floor. */
        .av2 .lx-search__clear::after {
          content: '';
          position: absolute;
          left: 50%;
          top: 50%;
          width: var(--av2-tap);
          height: var(--av2-tap);
          transform: translate(-50%, -50%);
        }
        /* globals.css puts an !important 1px ruled border on every input. */
        .av2 .lx-input {
          border: 0 !important;
          border-radius: 0 !important;
          box-shadow: none !important;
          background-color: transparent;
          min-height: var(--av2-tap);
          outline: 0;
        }
        .av2 .lx-input:focus { box-shadow: none !important; }
        .av2 .lx-search:focus-within { outline: 2px solid var(--av2-blue); outline-offset: 0; }

        /* Filter pills, the active one on ink. The row wraps rather than
           scrolling sideways, so a 320px screen shows every pill. */
        .av2 .lx-chips { display: flex; flex-wrap: wrap; gap: 6px; min-width: 0; }
        .av2 .lx-chip {
          display: inline-flex;
          flex: none;
          align-items: center;
          gap: 6px;
          min-height: var(--av2-tap);
          padding: 0 13px;
          border: 0;
          border-radius: var(--av2-r-pill);
          background: var(--av2-card);
          color: var(--av2-ink);
          font-family: inherit;
          font-size: var(--av2-t-meta);
          font-weight: 700;
          cursor: pointer;
        }
        .av2 .lx-chip[aria-pressed='true'] { background: var(--av2-ink); color: var(--av2-on-ink); }
        .av2 .lx-livesum { display: flex; align-items: center; justify-content: flex-end; gap: 10px; min-width: 0; }
        /* Out of the flow while it has nothing to say (no gap), still live. */
        .av2 .lx-livesum:empty { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
        .av2 .lx-section-head { display: flex; flex-wrap: wrap; align-items: baseline; justify-content: space-between; gap: 4px 12px; min-width: 0; margin-top: 8px; }
        .av2 .lx-section-head > * { min-width: 0; overflow-wrap: anywhere; }
        .av2 .lx-section-head__note { font-weight: 400; }

        /* Rows — the Cahier artboard's concept row, verbatim. */
        .av2 .lx-rows { display: flex; flex-direction: column; gap: 8px; min-width: 0; }
        .av2 .lx-row {
          display: flex;
          align-items: center;
          gap: 14px;
          width: 100%;
          min-width: 0;
          min-height: var(--av2-tap);
          padding: 14px 16px;
          border: 0;
          border-radius: var(--av2-r-card);
          background: var(--av2-card);
          color: var(--av2-ink);
          font-family: inherit;
          text-align: left;
          text-decoration: none;
          cursor: pointer;
          transition: transform var(--av2-press-dur);
        }
        .av2 .lx-row:active { transform: scale(0.985); }
        .av2 .lx-row__main { display: flex; flex-direction: column; gap: 3px; flex: 1 1 auto; min-width: 0; }
        .av2 .lx-row__title { font-size: var(--av2-t-body); font-weight: 600; line-height: 1.2; overflow-wrap: anywhere; }
        .av2 .lx-row__meta { font-size: var(--av2-t-meta); color: var(--av2-muted); line-height: 1.3; overflow-wrap: anywhere; }
        .av2 .lx-row__bars { display: flex; flex: none; gap: 3px; width: 34px; }
        .av2 .lx-row__bars i { flex: 1 1 0; height: 5px; border-radius: 3px; background: var(--av2-line); }
        .av2 .lx-row__bars i[data-on='done'] { background: var(--av2-ink); }
        .av2 .lx-row__bars i[data-on='story'] { background: var(--av2-blue); }
        .av2 .lx-row__bars i[data-on='reward'] { background: var(--av2-yellow); }
        .av2 .lx-row__bars i[data-on='action'] { background: var(--av2-red); }

        /* Atlas fold and tracks. */
        .av2 .lx-atlas { display: flex; flex-direction: column; gap: 10px; margin-top: 8px; min-width: 0; }
        .av2 .lx-fold {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          width: 100%;
          min-height: var(--av2-tap);
          padding: 14px 16px;
          border: 0;
          border-radius: var(--av2-r-tile);
          background: var(--av2-card);
          color: var(--av2-ink);
          font-family: inherit;
          text-align: left;
          cursor: pointer;
        }
        .av2 .lx-fold__main { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
        .av2 .lx-fold__toggle { flex: none; }
        .av2 .lx-atlas__body { gap: 10px; }
        .av2 .lx-track { display: flex; flex-direction: column; gap: 6px; min-width: 0; }
        .av2 .lx-track__head { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; min-width: 0; }
        .av2 .lx-track__label { min-width: 0; font-size: var(--av2-t-label); font-weight: 600; overflow-wrap: anywhere; }
        .av2 .lx-track__fill { background: var(--av2-blue); }
        .av2 .lx-track__fill[data-tone='ink'] { background: var(--av2-ink); }
        .av2 .lx-map { display: flex; flex-direction: column; gap: 12px; }
        .av2 .lx-map__grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(8px, 1fr));
          gap: 3px;
          max-height: 140px;
          overflow: hidden;
        }
        .av2 .lx-map__grid i { display: block; aspect-ratio: 1; min-width: 8px; border-radius: 2px; background: var(--av2-line); }
        .av2 .lx-map__grid i[data-state='due'], .av2 .lx-map__grid i[data-state='fragile'] { background: var(--av2-red); }
        .av2 .lx-map__grid i[data-state='fragile'] { opacity: 0.55; }
        .av2 .lx-map__grid i[data-state='building'] { background: var(--av2-blue); opacity: 0.55; }
        .av2 .lx-map__grid i[data-state='solid'] { background: var(--av2-blue); }
        .av2 .lx-map__grid i[data-state='mastered'] { background: var(--av2-ink); }
        .av2 .lx-map__grid i[data-state='new'] { background: var(--av2-yellow); opacity: 0.6; }
        .av2 .lx-map__totals { list-style: none; margin: 0; padding: 0; display: flex; flex-wrap: wrap; gap: 8px 14px; }
        .av2 .lx-map__totals li { display: inline-flex; align-items: center; gap: 6px; font-size: var(--av2-t-meta); color: var(--av2-muted); }
        .av2 .lx-map__totals strong { color: var(--av2-ink); }
        .av2 .lx-map__token--fragile, .av2 .lx-map__token--building, .av2 .lx-map__token--new { opacity: 0.6; }
        .av2 .lx-map__note { font-size: var(--av2-t-meta); color: var(--av2-muted); }

        /* Weekly dossier. */
        .av2 .lx-dossier { display: flex; flex-direction: column; gap: 10px; min-width: 0; padding: 18px; margin-top: 8px; }
        .av2 .lx-dossier__title { margin: 0; font-family: var(--av2-sans); font-size: var(--av2-t-title); font-weight: 700; line-height: 1.2; color: var(--av2-ink); overflow-wrap: anywhere; }
        .av2 .lx-dossier__stats { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; margin: 4px 0 0; }
        .av2 .lx-dossier__stats div { min-width: 0; padding: 10px 12px; border-radius: var(--av2-r-tile); background: var(--av2-paper); }
        .av2 .lx-dossier__stats dd { margin: 4px 0 0; font-size: var(--av2-t-title); font-weight: 700; line-height: 1; }
        .av2 .lx-dossier__thread { display: flex; align-items: flex-start; gap: 8px; min-width: 0; }
        .av2 .lx-dossier__thread .av2-shape { margin-top: 5px; }
        .av2 .lx-dossier__thread span { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
        .av2 .lx-dossier__thread b { font-size: var(--av2-t-body); font-weight: 600; overflow-wrap: anywhere; }
        .av2 .lx-dossier__thread em { font-style: normal; }

        /* Word sheet. */
        .av2 .lx-sheet { gap: 14px; }
        .av2 .lx-meta { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; min-width: 0; }
        .av2 .lx-meta > * { min-width: 0; }
        .av2 .lx-meta .av2-label { overflow-wrap: anywhere; }
        .av2 .lx-meta strong { display: block; margin-top: 4px; font-size: var(--av2-t-body-lg); font-weight: 700; line-height: 1.2; overflow-wrap: anywhere; }
        .av2 .lx-anchor { display: flex; flex-direction: column; gap: 6px; min-width: 0; }
        .av2 .lx-anchor__text { margin: 0; font-size: var(--av2-t-option); color: var(--av2-ink); overflow-wrap: anywhere; }
        .av2 .lx-block { display: flex; flex-direction: column; gap: 8px; min-width: 0; }
        .av2 .lx-block .lx-section-head { margin-top: 0; }
        .av2 .lx-group { display: flex; flex-direction: column; gap: 10px; }
        .av2 .lx-group__head { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
        .av2 .lx-group__head strong { min-width: 0; font-size: var(--av2-t-body); overflow-wrap: anywhere; }
        .av2 .lx-entry { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
        .av2 .lx-entry + .lx-entry { padding-top: 10px; border-top: 1px solid var(--av2-line); }
        .av2 .lx-entry__text { margin: 0; font-size: var(--av2-t-action); color: var(--av2-ink); overflow-wrap: anywhere; }
        .av2 .lx-placeholder { margin: 0; color: var(--av2-muted); }
        .av2 .lx-actions { display: flex; flex-direction: column; gap: 8px; min-width: 0; }
        .av2 .lx-ratings { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; min-width: 0; }
        .av2 .lx-ratings__note { grid-column: 1 / -1; }
        .av2 .lx-ratings .av2-btn { width: auto; }

        /* The Lexique card at small size, inside the sheet. */
        .av2 .lx-card {
          --lx-card-face: var(--av2-card);
          --lx-card-fg: var(--av2-ink);
          --lx-card-shadow: var(--av2-line-2);
          display: flex;
          flex-direction: column;
          justify-content: space-between;
          gap: 14px;
          min-height: 11rem;
          min-width: 0;
          padding: 20px 20px 22px;
          border: 0;
          border-radius: var(--av2-r-vocab);
          background: var(--lx-card-face);
          color: var(--lx-card-fg);
          box-shadow: 0 var(--av2-press-lg) 0 var(--lx-card-shadow);
          margin-bottom: var(--av2-press-lg);
          text-align: left;
          cursor: pointer;
          user-select: none;
          -webkit-user-select: none;
          transition: background 0.25s, color 0.25s, transform var(--av2-press-dur), box-shadow var(--av2-press-dur);
        }
        .av2 .lx-card:active { transform: translateY(4px); box-shadow: 0 4px 0 var(--lx-card-shadow); }
        .av2 .lx-card[data-face='back'] {
          --lx-card-face: var(--av2-yellow);
          --lx-card-fg: var(--av2-on-yellow);
          --lx-card-shadow: var(--av2-yellow-deep);
        }
        .av2 .lx-card__top { display: flex; align-items: center; justify-content: space-between; gap: 10px; font-size: var(--av2-t-label); font-weight: 700; opacity: 0.85; }
        .av2 .lx-card__word { font-size: var(--av2-t-screen); line-height: 1; color: inherit; overflow-wrap: anywhere; hyphens: auto; }
        .av2 .lx-card__example { margin: 0; font-size: var(--av2-t-action); line-height: 1.35; opacity: 0.9; color: inherit; overflow-wrap: anywhere; }

        @media (min-width: 560px) {
          .av2 .lx-meta { grid-template-columns: repeat(4, minmax(0, 1fr)); }
          .av2 .lx-actions { flex-direction: row; }
          .av2 .lx-actions .av2-btn { flex: 1 1 0; width: auto; }
        }
        @media (max-width: 360px) {
          .av2 .lx-dossier__stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
          .av2 .lx-ratings { grid-template-columns: minmax(0, 1fr); }
          .av2 .lx-mast { flex-direction: column; align-items: flex-start; }
        }
      `}</style>
    </>
  );
}
