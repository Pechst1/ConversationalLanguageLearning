import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { useRouter } from 'next/router';
import toast from 'react-hot-toast';

import {
  answerSide,
  askedSide,
  asksFromLearnerSide,
  bareFrench,
  cardMeaning,
  cardTexts,
  shownFrench,
} from '@/lib/card-word';
import { useChromeLanguage } from '@/lib/learner-language';
import { handOnAfterWords } from '@/lib/day-plan';
import { daySessionCopy } from '@/lib/day-session';
import { extraWordsOffer } from '@/lib/more-words';

import { GoldPill } from '@/components/gold/GoldPill';
import MotsDuJour from '@/components/lexique/MotsDuJour';
import {
  cardMode,
  deckProgress,
  type CardMode,
} from '@/components/lexique/recall-ladder';
import {
  SWIPE_RATING,
  dragStarts,
  swipeProgress,
  swipeVerdict,
  type SwipeSide,
} from '@/components/lexique/swipe';
import {
  EMPTY_PROGRESS,
  fileCard,
  deckFoot,
  gradeAction,
  progressAfterLoad,
  remainingCards,
  reviewNotSaved,
  withoutFiled,
  type DeckLoad,
  type DeckProgress,
  deckOrdered,
  deckSlotLabel,
} from '@/components/lexique/deck-session';
import {
  fill,
  formatDate,
  formatNumber,
  lexiqueCopy,
  partOfSpeechLabel,
  plural,
  useLexCopy,
  type LexiqueCopy,
} from '@/components/lexique/lexique-copy';
import { WordBiographySheet } from '@/components/mobile';
import {
  Action,
  ArrowLeftIcon,
  ArrowRightIcon,
  AtelierV2Root,
  CrossIcon,
  IconAction,
  Notice,
  Portrait,
  ShapeToken,
  StateBlock,
  Surface,
} from '@/components/atelier-v2/ui';
import apiService, {
  DailyWordSlate,
  NewWordsPace,
  VocabularyBiography,
  VocabularyDueContext,
  VocabularyRecommendationItem,
} from '@/services/api';
import {
  REVIEW_WORD_KEY,
  clearReviewProgress,
  readReviewContextCache,
  saveResumeActivity,
  writeReviewContextCache,
} from '@/lib/pilot-resilience';
import { useArtSet } from '@/lib/art-set';
import { CastFace, drawnFaceId } from '@/components/cast/CastFace';
import { emitCameo } from '@/lib/cameo';
import { FirstStepSticker } from '@/components/onboarding/FirstStepSticker';
import { FirstDayRoute } from '@/components/onboarding/FirstDayRoute';
import { deviceStore, localDateToday, markRouteStage, onFirstDay, routeDone, type RouteStage } from '@/lib/first-steps';
import { markWordsDoneToday } from '@/lib/continue-learning';
import { cardExample, cardFaces, type MarkedExample } from '@/lib/card-example';
import { playAskedVoice, speakAskedVoice } from '@/lib/audio-session';

/* "Le Lexique" — the review session, on the Claude design system (Atelier V2).
 *
 * The design's LEXIQUE artboard, the one immersive screen of the vocabulary: a
 * round close control, one segment per card in the deck (yellow = filed, ink =
 * current, line = still to come), the "2/4" count; one card filling the screen
 * (card face on the front, yellow on the back, the 8px press), the word as the
 * one Garamond-italic headline. Tabs and masthead are hidden, as the design
 * hides them.
 *
 * Owner, 4 Nov («less taps, maybe by swiping; leave out the fill-in exercise per
 * card; show the example sentence and its translation on the other side; sleek
 * and seamless»): every card is a flip card. Tap turns it; a turned card is
 * swiped right for «Je sais» (grade 2) or left for «Encore» (grade 0), or rated
 * with the pair under it, or with ← →. The front holds the word alone; the back
 * holds the answer, the example with the word marked, and its translation. The
 * keys 1–4 still reach the whole four-grade FSRS scale. A flip card reports a
 * self-rated flashcard, which earns no gold. */

// The four grade labels carry the whole scale, in the chrome language
// (components/lexique/lexique-copy.ts); the FSRS internals are never printed.
const reviewOptions = [
  { rating: 0, label: 'deck_again', tone: 'red' },
  { rating: 1, label: 'deck_hard', tone: 'yellow' },
  { rating: 2, label: 'deck_good', tone: 'blue' },
  { rating: 3, label: 'deck_easy', tone: 'green' },
] as const;

// One card costs about twenty seconds at the deck's observed pace. The
// estimate is the unit a learner plans with; the count is the one they verify.
const SECONDS_PER_CARD = 20;

// Past this many cards the design's one-segment-per-word row no longer fits a
// 320px screen (4px minimum per segment); the same progress is then drawn as
// one filled rule with the identical count and accessible value.
const MAX_SEGMENTS = 12;

// WP-131 (owner decision 9): one session introduces at most this many new words
// (`vocabulary_pace.DRILL_SESSION_NEW_WORDS`); the server clamps it to what the
// day's allowance leaves after the journey and the throttle.
const SESSION_NEW_WORDS = 8;

// Direction is resolved server-side from the learner's stored preference.
// WP-154: `drill: 'session'` — the server keeps the batch it dealt for the
// learner's app day, so a reload mid-deck shows the rest of that batch in the
// same order, never new words in the answered cards' slots.
const reviewQueueParams = {
  limit: 50,
  due_limit: 30,
  fragile_limit: 12,
  new_limit: SESSION_NEW_WORDS,
  topic_limit: 8,
  linked_limit: 8,
  drill: 'session',
} as const;

// WP-131: «Encore N mots» — the rest of the day's allowance (Soutenu 18,
// Intensif 30) as an explicit, bounded continuation: at most one session's new
// words, plus whatever came due meanwhile; no fragile, topic or linked padding.
function moreWordsParams(n: number) {
  const words = Math.max(0, Math.min(SESSION_NEW_WORDS, Math.floor(n)));
  return {
    limit: words + 30,
    due_limit: 30,
    fragile_limit: 0,
    new_limit: words,
    topic_limit: 0,
    linked_limit: 0,
    // WP-154: appended to the day's batch, so a reload resumes the continuation.
    drill: 'more',
  } as const;
}

// The continuation's words, in the deck's chrome language (the learner's up to
// A2, French from B1).
const MORE_WORDS_COPY: Record<'one' | 'many', Record<string, { label: string; note: string }>> = {
  one: {
    fr: { label: 'Encore 1 mot', note: 'Ton rythme prévoit encore 1 mot nouveau aujourd’hui.' },
    en: { label: '1 more word', note: 'Your rhythm still has 1 new word for today.' },
    de: { label: 'Noch 1 Wort', note: 'Dein Rhythmus sieht heute noch 1 neues Wort vor.' },
  },
  many: {
    fr: { label: 'Encore {n} mots', note: 'Ton rythme prévoit encore {n} mots nouveaux aujourd’hui.' },
    en: { label: '{n} more words', note: 'Your rhythm still has {n} new words for today.' },
    de: { label: 'Noch {n} Wörter', note: 'Dein Rhythmus sieht heute noch {n} neue Wörter vor.' },
  },
};

function moreWordsCopy(language: string, n: number) {
  const table = MORE_WORDS_COPY[n === 1 ? 'one' : 'many'];
  const copy = table[language] || table.fr;
  return { label: fill(copy.label, { n }), note: fill(copy.note, { n }) };
}

// WP-L6 «Encore 5 minutes» (after the day's Seal): reviews only — no new
// words — and a deck of about five minutes at the deck's own pace. It never
// touches the story; the streak is marked at most once a day on the server.
const ENCORE_CARDS = Math.round((5 * 60) / SECONDS_PER_CARD);
const encoreQueueParams = {
  limit: ENCORE_CARDS,
  due_limit: ENCORE_CARDS,
  fragile_limit: ENCORE_CARDS,
  new_limit: 0,
  topic_limit: 0,
  linked_limit: 0,
} as const;

/**
 * Round 3 (owner, 2026-10-14): the words are the day's second step. `?day=1`
 * is the day's deck — all of today's new words at the learner's pace (Normal
 * 20, Schnell 40) and the reviews due, in bounded decks one after the other
 * until the dose is met, then «Weiter: Grammatik». `?more=5` is «Noch 5 neue
 * Wörter» after the day: new words past the pace, the learner's own choice.
 * Owner, 2 Nov: the tap raises today's cap on the server first
 * (`POST /vocabulary/new-words/more`); the deck only deals what the cap holds.
 */
const DAY_DECK_NEW_WORDS = 50;
const dayQueueParams = {
  limit: 100,
  due_limit: 100,
  fragile_limit: 0,
  new_limit: DAY_DECK_NEW_WORDS,
  topic_limit: 0,
  linked_limit: 0,
  drill: 'session',
} as const;

function dayMoreParams(n: number) {
  const words = Math.max(0, Math.min(DAY_DECK_NEW_WORDS, Math.floor(n)));
  return { ...moreWordsParams(SESSION_NEW_WORDS), limit: words + 30, new_limit: words };
}

function extraWordsParams(n: number) {
  const words = Math.max(1, Math.min(20, Math.floor(n)));
  return { ...moreWordsParams(SESSION_NEW_WORDS), limit: words + 30, new_limit: words };
}

// Owner request, 2 Nov: «Noch 5 neue Wörter» at the end of the day's deck (and of
// each continuation), with one line on how much sooner that pace reaches the goal.
function ExtraWordsOffer({
  pace,
  language,
  pending,
  onSelect,
}: {
  pace: NewWordsPace | null;
  language: ReturnType<typeof useChromeLanguage>;
  pending: boolean;
  onSelect: () => void;
}) {
  const offer = extraWordsOffer(pace, language);
  if (!offer) return null;
  return (
    <div className="lx-done__quiet" data-extra-words="">
      <p className="av2-body" data-goal-line="">{offer.line}</p>
      <Action tone="quiet" inline pending={pending} pendingLabel={offer.label} onClick={onSelect}>
        {offer.label}
      </Action>
    </div>
  );
}

function daySessionMode(): { kind: 'day' } | { kind: 'more'; words: number } | null {
  if (typeof window === 'undefined') return null;
  const query = new URLSearchParams(window.location.search);
  if (query.get('day') === '1') return { kind: 'day' };
  const more = Number(query.get('more') || 0);
  if (Number.isFinite(more) && more > 0) return { kind: 'more', words: more };
  return null;
}

function isEncore(): boolean {
  if (typeof window === 'undefined') return false;
  return new URLSearchParams(window.location.search).get('encore') === '1';
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

// The card's word, on either side, is `lib/card-word.ts`'s: a French noun always
// carries its article there (owner request, 1 Nov). Nothing here prints the bare lemma.
function queueExample(item: VocabularyRecommendationItem) {
  return item.example_sentence?.trim() || '';
}

function queueExampleTranslation(item: VocabularyRecommendationItem) {
  return item.example_translation?.trim() || '';
}

/* The design's hint line reads "verbe · 1er groupe · rang 2 140". Each part
 * is printed only when the payload actually carries it. The part-of-speech
 * column comes from a heuristic import and holds English keys (and sometimes
 * "x"), so only a value on the whitelist prints (PART_OF_SPEECH_LABELS in
 * components/lexique/lexique-copy.ts), as a label in the chrome language —
 * never the raw key, never a guess. The frequency rank is read only if the
 * queue item carries one; nothing is invented to fill the slot. */
function optionalRank(item: VocabularyRecommendationItem) {
  const value = (item as unknown as { frequency_rank?: unknown }).frequency_rank;
  return typeof value === 'number' && value > 0 ? value : null;
}

function cardHint(t: LexiqueCopy, item: VocabularyRecommendationItem) {
  const rank = optionalRank(item);
  return [partOfSpeechLabel(t, item.part_of_speech), rank ? fill(t.rank, { n: formatNumber(t, rank) }) : '']
    .filter(Boolean)
    .join(' · ');
}

// Off the input path: work that need not run before the next card is painted.
function afterPaint(task: () => void) {
  if (typeof window === 'undefined') return;
  const idle = (window as Window & { requestIdleCallback?: (cb: () => void, opts?: { timeout: number }) => number }).requestIdleCallback;
  if (typeof idle === 'function') idle(task, { timeout: 400 });
  else window.setTimeout(task, 0);
}

function prefersReducedMotion() {
  return typeof window !== 'undefined' && Boolean(window.matchMedia?.('(prefers-reduced-motion: reduce)').matches);
}

// The card's speaker (no icon of the set draws one): a cone and one wave, in the ink.
function SpeakerIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M4 9.5h3.5L12 5.5v13l-4.5-4H4z" fill="currentColor" />
      <path d="M15.5 8.5a5 5 0 0 1 0 7M18 6a8.5 8.5 0 0 1 0 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

/* The example with the card's word marked (lib/card-example.ts cuts it). */
function MarkedSentence({ marked }: { marked: MarkedExample }) {
  return (
    <>
      {marked.before}
      {marked.word && <mark className="lx-card__mark">{marked.word}</mark>}
      {marked.after}
    </>
  );
}

function ratingToneLabel(t: LexiqueCopy, rating: number) {
  const option = reviewOptions.find((item) => item.rating === rating);
  return option ? t[option.label] : t.rating_fallback;
}

function decrementSummaryCount(value: number | undefined) {
  return Math.max(0, Number(value || 0) - 1);
}

/* The episodic anchor: the character this word was met with, as the design's
   portrait byline. The server portrait is used when it loads; otherwise the
   initial on the character's accent, exactly as the Feuilleton draws it. */
function ReviewPortrait({ item }: { item: VocabularyRecommendationItem }) {
  const t = useLexCopy();
  const [failed, setFailed] = useState(false);
  // WP-116: the drawn art set shows the character's rig beside the word.
  const artSet = useArtSet();
  const anchor = item.episodic_anchor;
  if (!anchor) return null;
  const name = anchor.character_name || 'Le Feuilleton';
  const drawn = artSet === 'drawn' && drawnFaceId(anchor.character_name) !== null;
  return (
    <span className="av2-byline lx-cast" title={fill(t.anchored_with, { name })}>
      {drawn ? (
        <span className="lx-cast__portrait lx-cast__portrait--drawn"><CastFace seeds={[anchor.character_name]} size={22} /></span>
      ) : anchor.portrait_url && !failed ? (
        /* eslint-disable-next-line @next/next/no-img-element */
        <img
          className="lx-cast__portrait"
          src={anchor.portrait_url}
          alt=""
          onError={() => setFailed(true)}
          style={anchor.accent_colour ? { background: anchor.accent_colour } : undefined}
        />
      ) : <Portrait name={name} size="sm" />}
      <span className="av2-label">{name}</span>
    </span>
  );
}

function optimisticallyDecrementSummary(
  context: VocabularyDueContext | null,
  item: VocabularyRecommendationItem,
) {
  if (!context) return context;

  const summary = { ...context.summary };
  switch (item.bucket) {
    case 'due':
      summary.due = decrementSummaryCount(summary.due);
      summary.total = decrementSummaryCount(summary.total);
      break;
    case 'fragile':
      summary.fragile = decrementSummaryCount(summary.fragile);
      summary.total = decrementSummaryCount(summary.total);
      break;
    case 'new':
      summary.new = decrementSummaryCount(summary.new);
      summary.total = decrementSummaryCount(summary.total);
      break;
    case 'linked':
      summary.linked = decrementSummaryCount(summary.linked);
      break;
    case 'topic':
    case 'topic_compatible':
      summary.topic_compatible = decrementSummaryCount(summary.topic_compatible);
      break;
    default:
      break;
  }

  return { ...context, summary };
}

// The end of the deck: what was just filed, and the day's slate showing how
// far its three stamps have come. "Queue claire" was half English; the notebook
// is called le Cahier everywhere else in the journal.
function VocabularyReviewContinuation({
  lastItem,
  lastRating,
  slate,
  onRefresh,
  onReturn,
  returning,
  more,
}: {
  lastItem: VocabularyRecommendationItem | null;
  lastRating: number | null;
  slate: DailyWordSlate | null;
  onRefresh: () => void;
  onReturn: () => void;
  returning: boolean;
  /** WP-131: the day's allowance still holds new words — «Encore N mots». */
  more?: { label: string; note: string; onSelect: () => void } | null;
}) {
  const t = useLexCopy();
  const wordId = lastItem?.word_id || null;
  const word = lastItem ? shownFrench(lastItem) || askedSide(lastItem) : '';
  const ratingCopy = lastRating !== null ? ratingToneLabel(t, lastRating) : '';
  // «5 more minutes» after the Seal on a day nothing is due yet (day 1): no card
  // was answered, so «Deck cleared» would be a claim. Say what is true.
  const nothingDue = !lastItem && isEncore();
  // Les apparitions: a cleared deck gets the curtain call.
  useEffect(() => {
    if (lastItem) emitCameo({ type: 'finale' });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <>
      <Surface as="section" shape="hero" className="lx-done" aria-label={t.done_aria}>
        <ShapeToken kind="done" size="lg" />
        <p className="av2-label">{t.done_label}</p>
        {/* the one Garamond-italic headline once the deck is empty */}
        <h2 className="av2-headline av2-headline--screen">
          {nothingDue ? t.encore_empty_title : t.done_title}
        </h2>
        {nothingDue && <p className="av2-body av2-body--lg">{t.encore_empty_body}</p>}
        {(word || ratingCopy) && (
          <p className="av2-body av2-body--lg">{[word, ratingCopy].filter(Boolean).join(' · ')}</p>
        )}
        {more && <p className="av2-body">{more.note}</p>}
        <div className="lx-done__actions">
          {/* the one tactile 3D press on the empty deck */}
          <Action tone="done" pending={returning} pendingLabel={t.returning} onClick={onReturn}>
            {/* WP-109: the front page is «La Une». */}
            La Une
          </Action>
          <div className="lx-done__quiet">
            {more && (
              <Action tone="quiet" inline onClick={more.onSelect}>{more.label}</Action>
            )}
            <Action tone="quiet" inline onClick={onRefresh}>{t.refresh}</Action>
            {wordId && (
              <Link className="av2-btn av2-btn--quiet av2-btn--inline" href={`/vocabulary?word=${wordId}`}>
                Le Cahier
              </Link>
            )}
          </div>
        </div>
      </Surface>
      <MotsDuJour slate={slate} href="/vocabulary" />
    </>
  );
}

export default function VocabularyReviewPage() {
  const router = useRouter();
  const [context, setContext] = useState<VocabularyDueContext | null>(null);
  const [wordSlate, setWordSlate] = useState<DailyWordSlate | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [returning, setReturning] = useState(false);
  const [revealed, setRevealed] = useState(false);
  const [audioPlaying, setAudioPlaying] = useState(false);
  // Le Lexique has no journey envelope, so the learner's language and level
  // come from the profile rather than a `control_language` field. WP-82: the
  // deck's chrome — buttons, states, the failure toasts, the visual cue's
  // scene name — is the learner's language up to A2 and French from B1; the
  // words and their examples stay French.
  const language = useChromeLanguage();
  const t = lexiqueCopy(language);
  // What this sitting has filed. WP-115b «successive relearning»: a card answered
  // wrong comes back at the end of the session, until it is right once.
  const [deck, setDeck] = useState<DeckProgress>(EMPTY_PROGRESS);
  const deckRef = useRef(deck);
  deckRef.current = deck;
  // The deck and slate as last loaded: a review's reply can land after the
  // fresh deck replaced the cached one this render's closure still holds.
  const contextRef = useRef(context);
  contextRef.current = context;
  const wordSlateRef = useRef(wordSlate);
  wordSlateRef.current = wordSlate;
  const [lastRating, setLastRating] = useState<number | null>(null);
  const [lastReviewedItem, setLastReviewedItem] = useState<VocabularyRecommendationItem | null>(null);
  const [biographyOpen, setBiographyOpen] = useState(false);
  const [biography, setBiography] = useState<VocabularyBiography | null>(null);
  const [biographyLoading, setBiographyLoading] = useState(false);
  const [biographyError, setBiographyError] = useState<string | null>(null);
  const [resumeWordId, setResumeWordId] = useState<number | null>(null);
  const [cachedContextAt, setCachedContextAt] = useState<string | null>(null);
  const visibleCacheRef = useRef(false);
  // Deferred device writes (afterPaint) belong to the deck they were taken from: a
  // fresh deck or a finished one bumps this, and a write from before it is dropped.
  const cacheGenRef = useRef(0);
  const deferCacheWrite = useCallback((task: () => void) => {
    const gen = cacheGenRef.current;
    afterPaint(() => {
      if (cacheGenRef.current === gen) task();
    });
  }, []);

  // `revalidate` is the server's copy of the deck already on screen (the cached
  // one): what the learner filed meanwhile stays filed and the card stays turned.
  const loadQueue = useCallback(async (moreWords?: number, load: DeckLoad = 'new-deck') => {
    setLoading(!visibleCacheRef.current);
    setLoadError(null);
    try {
      const mode = daySessionMode();
      const params = isEncore()
        ? encoreQueueParams
        : mode?.kind === 'day'
          ? moreWords
            ? dayMoreParams(moreWords)
            : dayQueueParams
          : mode?.kind === 'more' && !moreWords
            ? extraWordsParams(mode.words)
            : moreWords
              ? moreWordsParams(moreWords)
              : reviewQueueParams;
      const [next, slate] = await Promise.all([
        apiService.getVocabularyDueContext(params),
        apiService.getWordsOfTheDay().catch(() => null),
      ]);
      setWordSlate(slate);
      setContext(next);
      cacheGenRef.current += 1;
      writeReviewContextCache(load === 'revalidate' ? withoutFiled(next, deckRef.current.filed) : next, slate);
      visibleCacheRef.current = false;
      setCachedContextAt(null);
      setDeck((prev) => progressAfterLoad(prev, load));
      if (load === 'new-deck') {
        setLastRating(null);
        setLastReviewedItem(null);
        setRevealed(false);
      }
    } catch (error) {
      console.error(error);
      if (!visibleCacheRef.current) setLoadError('unavailable');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const cached = readReviewContextCache<VocabularyDueContext, DailyWordSlate>();
    if (cached) {
      visibleCacheRef.current = true;
      setContext(cached.context);
      setWordSlate(cached.wordSlate);
      setCachedContextAt(cached.cachedAt);
      setLoading(false);
    }
    const stored = Number(window.localStorage.getItem(REVIEW_WORD_KEY) || 0);
    if (stored) setResumeWordId(stored);
    void loadQueue(undefined, 'revalidate');
  }, [loadQueue]);

  // "Les mots du jour" ride to the front of the deck: the day's slate words
  // are the retrieval half of the read → retrieve → produce loop.
  const slateById = useMemo(() => {
    const map = new Map<number, NonNullable<DailyWordSlate['words']>[number]>();
    for (const entry of wordSlate?.words || []) map.set(entry.word_id, entry);
    return map;
  }, [wordSlate]);
  const slateIds = useMemo(() => new Set(slateById.keys()), [slateById]);
  const allItems = useMemo(() => {
    // The deck's order is the server's (`deck_order`, app/services/deck_order.py):
    // the due reviews in the scheduler's order, then the new words, today's scene
    // words mixed in for at most a third of them (owner request, 2 Nov).
    const ordered = deckOrdered(queueItems(context), context?.deck_order);
    if (!resumeWordId) return ordered;
    return [
      ...ordered.filter((item) => item.word_id === resumeWordId),
      ...ordered.filter((item) => item.word_id !== resumeWordId),
    ];
  }, [context, resumeWordId]);
  const remainingItems = useMemo(() => remainingCards(allItems, deck), [allItems, deck]);
  const current = remainingItems[0] || null;
  /* GENTLE-ONBOARDING: an emptied deck on the first day ticks the words off,
     the last stage of story → La Forge → words. `null` on any other day. */
  const [firstDayDone, setFirstDayDone] = useState<RouteStage[] | null>(null);
  const deckEmpty = !loading && !loadError && !current;
  useEffect(() => {
    if (!deckEmpty) return;
    const store = deviceStore();
    const localDate = localDateToday();
    // CONTINUE: Home's one button moves past the words once the deck is done today.
    markWordsDoneToday(store, localDate);
    if (!onFirstDay(store, localDate)) return;
    markRouteStage(store, 'words', localDate);
    setFirstDayDone(routeDone(store));
  }, [deckEmpty]);
  const currentSlateEntry = current ? slateById.get(current.word_id) || null : null;
  // #88: a fixed total for the sitting (the deck plus anything filed from it), and a
  // card asked again is not done until it is answered right.
  const { done: completed, total } = deckProgress(
    [...allItems.map((item) => item.word_id), ...Array.from(deck.filed)],
    deck.filed,
    deck.again,
  );
  const sessionRemaining = remainingItems.length;
  const percent = total ? Math.round((completed / total) * 100) : 0;
  const minutesLeft = sessionRemaining
    ? Math.max(1, Math.round((sessionRemaining * SECONDS_PER_CARD) / 60))
    : 0;

  // WP-131: the day's allowance still holds new words after this deck. Offered
  // once the deck is done, never in «Encore 5 minutes» (review only), and at most
  // one session's worth at a time; the server stays the judge of the room.
  // Round 3: in the day's deck the dose goes on by itself, deck after deck,
  // until today's new words are met; then the day moves on to its next step.
  const daySession = useMemo(() => daySessionMode(), []);
  const dayLeft = daySession?.kind === 'day' ? Number(context?.new_words_left_today || 0) : 0;
  const [dayNext, setDayNext] = useState<{ label: string; meta: string; href: string } | null>(null);
  const [dayMarked, setDayMarked] = useState(false);
  // The day deck's end waits for the day's next step; only a failed read falls
  // back to the plain continuation (and its curtain call, which belongs to «Fertig»).
  const [dayFallback, setDayFallback] = useState(false);
  useEffect(() => {
    if (!deckEmpty || daySession?.kind !== 'day') return;
    if (Number.isFinite(dayLeft) && dayLeft > 0) {
      void loadQueue(dayLeft);
      return;
    }
    if (dayMarked) return;
    setDayMarked(true);
    apiService
      .markDaySessionWordsDone()
      .then((session) => {
        // Issue 143: the hand-on is the plan's, with the word step applied as finished.
        const next = handOnAfterWords(session, language, 'finished');
        const step = next ? { label: next.label, meta: next.meta, href: next.href } : null;
        setDayNext(step);
        if (!step) setDayFallback(true);
      })
      .catch(() => setDayFallback(true));
  }, [deckEmpty, daySession, dayLeft, dayMarked, language, loadQueue]);

  // Owner request, 2 Nov: «Noch 5 neue Wörter» once the day's deck is through (and
  // after each continuation): the server raises today's cap, then the deck deals
  // the five. The offer carries the server's line on how much sooner that pace
  // covers the goal's words.
  const [newWordsPace, setNewWordsPace] = useState<NewWordsPace | null>(null);
  const [addingWords, setAddingWords] = useState(false);
  const offersExtra = deckEmpty && (daySession?.kind === 'day' ? Boolean(dayNext) : daySession?.kind === 'more');
  useEffect(() => {
    if (!offersExtra) return;
    let live = true;
    apiService
      .getNewWordsPace()
      .then((body) => live && setNewWordsPace(body))
      .catch(() => live && setNewWordsPace(null));
    return () => {
      live = false;
    };
  }, [offersExtra]);
  const addExtraWords = useCallback(async () => {
    setAddingWords(true);
    try {
      // The deck deals the step the button promised; the answer's `step`
      // is the next tap's (0 once the pool is empty).
      const promised = newWordsPace?.step || 0;
      const body = await apiService.addExtraNewWords();
      setNewWordsPace(body);
      await loadQueue(promised || body.step);
    } catch (error) {
      console.error(error);
      toast.error(t.deck_unavailable);
    } finally {
      setAddingWords(false);
    }
  }, [loadQueue, newWordsPace, t]);

  const moreWords = useMemo(() => {
    const left = Number(context?.new_words_left_today || 0);
    if (isEncore() || daySession || !Number.isFinite(left) || left <= 0) return null;
    const n = Math.min(SESSION_NEW_WORDS, Math.floor(left));
    return { ...moreWordsCopy(language, n), onSelect: () => void loadQueue(n) };
  }, [context, daySession, language, loadQueue]);

  useEffect(() => {
    if (current) {
      // Off the input path (owner, 4 Nov: the lag after a grade). The resume word is
      // only read when the deck opens, so it no longer re-sorts the deck per card.
      const wordId = current.word_id;
      deferCacheWrite(() => {
        window.localStorage.setItem(REVIEW_WORD_KEY, String(wordId));
        saveResumeActivity({ href: '/vocabulary/review', kind: 'review', entityId: wordId });
      });
    } else if (!loading && context) {
      // The deck is done: drop the resume card *and* the cached queue, or the
      // next visit paints the finished deck again from localStorage before the
      // network can correct it. A write still pending from the last card is dropped.
      cacheGenRef.current += 1;
      clearReviewProgress();
      setResumeWordId(null);
      setCachedContextAt(null);
    }
  }, [context, current, loading, deferCacheWrite]);
  // Another card is never shown already turned, and never with the last one's sound.
  useEffect(() => {
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }
    setRevealed(false);
    setBiographyOpen(false);
    setBiography(null);
    setBiographyError(null);
    setBiographyLoading(false);
    setAudioPlaying(false);
  }, [current?.word_id]);

  const openBiography = async () => {
    if (!current) return;
    setBiographyOpen(true);
    setBiographyLoading(true);
    setBiographyError(null);
    try {
      const next = await apiService.getVocabularyBiography(current.word_id);
      setBiography(next);
    } catch (error) {
      console.error(error);
      setBiographyError('unavailable');
    } finally {
      setBiographyLoading(false);
    }
  };

  const playAudioPrompt = async (event: React.MouseEvent<HTMLButtonElement>) => {
    event.stopPropagation();
    if (!current || audioPlaying) return;
    const text = bareFrench(current);
    if (!text) return;
    setAudioPlaying(true);
    try {
      const audio = await apiService.synthesizeSpeech(text);
      const blob = new Blob([audio], { type: 'audio/mpeg' });
      const url = URL.createObjectURL(blob);
      const player = new Audio(url);
      player.onended = () => {
        URL.revokeObjectURL(url);
        setAudioPlaying(false);
      };
      player.onerror = () => {
        URL.revokeObjectURL(url);
        setAudioPlaying(false);
      };
      await playAskedVoice(player);
    } catch (error) {
      console.error(error);
      if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = 'fr-FR';
        utterance.onend = () => setAudioPlaying(false);
        utterance.onerror = () => setAudioPlaying(false);
        speakAskedVoice(utterance);
      } else {
        setAudioPlaying(false);
        toast.error(t.audio_failed);
      }
    }
  };

  // Owner, 1 Nov («Weiß ich» left the card on screen): the card is filed the moment it
  // is graded, before the server answers. Owner, 4 Nov («it lags a bit after deciding»):
  // nothing else runs on that tap — the device cache is written once the next card is
  // painted, and a filed card no longer pops a toast of its own.
  const fileGrade = (rating: number, wrong: boolean) => {
    if (!current) return;
    const item = current;
    const filed = fileCard(deckRef.current, item.word_id, wrong);
    deckRef.current = filed;
    setDeck((prev) => fileCard(prev, item.word_id, wrong));
    setLastRating(rating);
    setLastReviewedItem(item);
    setContext((prev) => optimisticallyDecrementSummary(prev, item));
    setRevealed(false);
    // A deck reopened later starts after this card, not on it.
    const snapshot = contextRef.current;
    const slate = wordSlateRef.current;
    if (snapshot) deferCacheWrite(() => writeReviewContextCache(withoutFiled(snapshot, filed.filed), slate));
    // A flip card is self-rated: it reports a flashcard, which earns no gold
    // (owner decision, 4 Nov — gold is for typed, spoken or selected words).
    apiService
      .submitAnkiReview({ word_id: item.word_id, rating, format: 'flashcard' as const })
      .then((response) => {
        if (response.note_native) toast(response.note_native);
        emitCameo({ type: 'answer', correct: !wrong });
      })
      .catch((error) => {
        console.error(error);
        toast.error(t.review_failed);
        setDeck((prev) => reviewNotSaved(prev, item.word_id));
      });
  };

  const returnToAtelier = async () => {
    setReturning(true);
    await router.push('/atelier');
  };

  /* The swipe (owner, 4 Nov). The drag moves the card through its style, never through
     React state, so a finger's every move costs no render. A filed card leaves as a copy
     of itself flying off to its side while the next card is already in place under it. */
  const stageRef = useRef<HTMLDivElement | null>(null);
  const cardRef = useRef<HTMLDivElement | null>(null);
  const dragRef = useRef<{ id: number; x: number; y: number; t: number; dx: number; vx: number; dragging: boolean } | null>(null);
  const suppressClickRef = useRef(false);

  const setDragVisual = (dx: number) => {
    const card = cardRef.current;
    if (!card) return;
    card.style.transform = dx ? `translateX(${dx}px) rotate(${(dx / 22).toFixed(2)}deg)` : '';
    if (dx) card.style.setProperty('--lx-swipe', swipeProgress(dx, card.offsetWidth).toFixed(3));
    else card.style.removeProperty('--lx-swipe');
  };

  const flyAway = (side: SwipeSide) => {
    const card = cardRef.current;
    const stage = stageRef.current;
    if (!card || !stage) return;
    const from = card.style.transform || 'none';
    setDragVisual(0);
    if (prefersReducedMotion() || typeof card.animate !== 'function') return;
    const ghost = card.cloneNode(true) as HTMLDivElement;
    for (const name of ['role', 'tabindex', 'aria-pressed', 'aria-label']) ghost.removeAttribute(name);
    ghost.setAttribute('aria-hidden', 'true');
    ghost.setAttribute('inert', '');
    ghost.setAttribute('data-ghost', side);
    ghost.removeAttribute('data-dragging');
    Object.assign(ghost.style, {
      position: 'absolute',
      top: `${card.offsetTop}px`,
      left: `${card.offsetLeft}px`,
      width: `${card.offsetWidth}px`,
      height: `${card.offsetHeight}px`,
      margin: '0',
      pointerEvents: 'none',
      zIndex: '3',
    });
    ghost.style.setProperty('--lx-swipe', side === 'know' ? '1' : '-1');
    stage.appendChild(ghost);
    const dir = side === 'know' ? 1 : -1;
    const flight = ghost.animate(
      [
        { transform: from, opacity: 1 },
        { transform: `translateX(${dir * 120}%) rotate(${dir * 18}deg)`, opacity: 0 },
      ],
      { duration: 280, easing: 'cubic-bezier(0.3, 0.5, 0.4, 1)', fill: 'forwards' },
    );
    const remove = () => ghost.remove();
    flight.onfinish = remove;
    flight.oncancel = remove;
  };

  // Every grade goes through here (the swipe, the two buttons, the keys ← → and 1–4):
  // an unturned card is turned first; a turned card flies off and is filed.
  const handleRatingClick = (rating: number) => {
    if (!current) return;
    const action = gradeAction({ revealed, rating, graded: false, typedMatches: false });
    if (action.kind === 'reveal') {
      setRevealed(true);
      return;
    }
    flyAway(action.wrong ? 'again' : 'know');
    fileGrade(action.rating, action.wrong);
  };

  const onCardPointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    suppressClickRef.current = false;
    if (!revealed || (event.pointerType === 'mouse' && event.button !== 0)) return;
    if ((event.target as HTMLElement | null)?.closest('button, a')) return;
    dragRef.current = { id: event.pointerId, x: event.clientX, y: event.clientY, t: event.timeStamp, dx: 0, vx: 0, dragging: false };
  };

  const onCardPointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    const drag = dragRef.current;
    if (!drag || drag.id !== event.pointerId) return;
    const dx = event.clientX - drag.x;
    const dy = event.clientY - drag.y;
    if (!drag.dragging) {
      const start = dragStarts(dx, dy);
      if (start === 'scroll') dragRef.current = null;
      if (start !== 'drag') return;
      drag.dragging = true;
      event.currentTarget.setPointerCapture?.(event.pointerId);
      event.currentTarget.setAttribute('data-dragging', '');
    }
    const elapsed = Math.max(1, event.timeStamp - drag.t);
    drag.vx = (dx - drag.dx) / elapsed;
    drag.dx = dx;
    drag.t = event.timeStamp;
    setDragVisual(dx);
  };

  const onCardPointerEnd = (event: React.PointerEvent<HTMLDivElement>) => {
    const drag = dragRef.current;
    if (!drag || drag.id !== event.pointerId) return;
    dragRef.current = null;
    if (!drag.dragging) return;
    event.currentTarget.removeAttribute('data-dragging');
    // The release of a drag is not a tap: it never turns the card back.
    suppressClickRef.current = true;
    // A finger that stopped before letting go is no flick, however fast it came.
    const velocity = event.timeStamp - drag.t > 80 ? 0 : drag.vx;
    const side = event.type === 'pointercancel'
      ? null
      : swipeVerdict({ dx: drag.dx, velocity, width: event.currentTarget.offsetWidth });
    if (side) handleRatingClick(SWIPE_RATING[side]);
    else setDragVisual(0);
  };

  // Space/Enter turns the card; ← and → file «Encore» and «Je sais» once it is
  // turned; 1–4 still reach the four grades of the scale.
  useEffect(() => {
    if (!current) return undefined;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      const target = event.target as HTMLElement | null;
      if (target?.closest('input, textarea, [contenteditable="true"]')) return;
      if (event.key === ' ' || event.key === 'Enter') {
        // Buttons handle their own Space/Enter; the shortcut is for the page.
        if (target?.closest('button, a, [role="dialog"]')) return;
        event.preventDefault();
        setRevealed((value) => !value);
        return;
      }
      if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') {
        if (target?.closest('[role="dialog"]')) return;
        event.preventDefault();
        handleRatingClick(SWIPE_RATING[event.key === 'ArrowRight' ? 'know' : 'again']);
        return;
      }
      const rating = ['1', '2', '3', '4'].indexOf(event.key);
      if (rating >= 0 && revealed) {
        event.preventDefault();
        handleRatingClick(rating);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  });

  // Owner, 4 Nov: no fill-in on the card any more. Every rung of the ladder is a flip
  // card: the French asked (recognition, audio) or its meaning asked (production and
  // the line rungs), the other side on the back with the example and its translation.
  const ladderMode = cardMode(current);
  const mode: CardMode = ladderMode === 'recognition' || ladderMode === 'audio' ? 'recognition' : 'production';
  const { prompt, answer } = cardTexts({ item: current, mode, cue: null, listenPrompt: t.listen_prompt });
  const french = current ? bareFrench(current) : '';
  const meaning = current ? cardMeaning(current) : '';
  const promptIsFrench = current ? mode === 'recognition' && !asksFromLearnerSide(current) : false;
  // A card with no example sentence quotes nothing, never «lampe - lamp» (walk finding 398).
  const example = current ? cardExample({ french, meaning, example: queueExample(current) }) : '';
  const exampleTranslation = current ? queueExampleTranslation(current) : '';
  // The front holds the word alone; the example and its translation are on the back.
  const faces = cardFaces({ mode, french, meaning, example, exampleTranslation, promptIsFrench });
  const foot = deckFoot({ revealed, graded: false });
  const hint = current ? cardHint(t, current) : '';

  // "Mot du jour · French 5000": the tag half is the deck the card came from,
  // printed only when the payload names one.
  // An Anki path («Französisch 5000::1. FR → DE») is a filing system, not a
  // name: only its first segment is printed.
  const deckLabel = String(current?.deck_name || '').split('::')[0].trim();
  const kicker = current
    ? [
        deckSlotLabel(t, current, slateIds),
        deckLabel,
      ].filter(Boolean).join(' · ')
    : '';

  // One segment per card in the deck: yellow = filed, ink = current, line =
  // still to come. Beyond MAX_SEGMENTS the same value is one filled rule.
  const dots = allItems.map((item) => ({
    id: item.word_id,
    state: deck.filed.has(item.word_id) ? 'done' : item.word_id === current?.word_id ? 'current' : 'pending',
  }));
  const countLabel = total ? `${completed}/${total}` : '';
  const progressCaption = sessionRemaining
    ? [plural(t, 'cards', sessionRemaining), minutesLeft ? fill(t.about_minutes, { n: minutesLeft }) : '']
      .filter(Boolean)
      .join(' · ')
    : completed
      ? plural(t, 'filed', completed)
      : t.nothing_due;

  const listenButton = (
    <IconAction
      className="lx-card__icon"
      label={t.listen_word}
      pending={audioPlaying}
      onClick={(event) => void playAudioPrompt(event)}
    >
      <SpeakerIcon />
    </IconAction>
  );

  return (
    <>
      <Head>
        <title>{t.review_head_title}</title>
      </Head>
      <AtelierV2Root as="main" language={language} className="lx-review" aria-label={t.review_aria}>
        <div className="av2-screen lx-review__screen">
          {/* The screen's own name, in every state including the loading and
              empty ones. The design draws no title here, so it is announced
              rather than printed (WP-20 D-11). */}
          <h1 className="av2-sr">{t.review_aria}</h1>
          {/* The design's Lexique header: round close, one segment per word,
              the count. No masthead and no tabs on this immersive screen. */}
          <header className="av2-session__head lx-review__head">
            <IconAction label={t.close_review} onClick={() => void returnToAtelier()} pending={returning}>
              <CrossIcon size={16} />
            </IconAction>
            <div className="av2-progress">
              {total > 0 && total <= MAX_SEGMENTS ? (
                <div
                  className="av2-progress__segments lx-dots"
                  role="progressbar"
                  aria-label={t.progress_aria}
                  aria-valuemin={0}
                  aria-valuemax={total}
                  aria-valuenow={completed}
                  aria-valuetext={progressCaption}
                >
                  {dots.map((dot) => (
                    <span key={dot.id} className="av2-progress__segment lx-dot" data-state={dot.state} />
                  ))}
                </div>
              ) : (
                <div
                  className="av2-progress__track lx-rule"
                  role="progressbar"
                  aria-label={t.progress_aria}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={percent}
                  aria-valuetext={loading ? t.opening_deck : progressCaption}
                >
                  <div className="av2-progress__fill lx-rule__fill" style={{ width: `${percent}%` }} />
                </div>
              )}
              {countLabel && <span className="av2-progress__count">{countLabel}</span>}
            </div>
            {/* O-2: each word typed back right is a feuille d'or (only where the switch shows it). */}
            <GoldPill />
          </header>

          <div className="av2-screen__body lx-review__body">
            {cachedContextAt && (
              <Notice tone="quiet" shape="story">
                <p>{t.cached_notice}</p>
              </Notice>
            )}

            {loading && <StateBlock tone="loading" title={t.opening_deck} />}

            {!loading && loadError && (
              <StateBlock
                tone="error"
                title={t.deck_error_title}
                body={t.deck_unavailable}
                action={{ label: t.retry, onSelect: () => void loadQueue() }}
              />
            )}

            {!loading && !loadError && !current && firstDayDone && !daySession && (
              // GENTLE-ONBOARDING: the words were the first day's last stage.
              <FirstDayRoute
                language={language}
                done={firstDayDone}
                forgeHref={null}
                onNavigate={(href) => { void router.push(href); }}
              />
            )}

            {!loading && !loadError && !current && daySession?.kind === 'day' && !dayNext && !dayFallback && (
              // The day's deck is through and the page is asking for what comes next (the next
              // dose, or the day's next step). Until the answer it says so: an empty page with
              // only the count, «33/33», offered nothing to tap (main's walk, run 43073091897).
              <StateBlock tone="loading" title={dayLeft > 0 ? t.opening_deck : daySessionCopy(language).words_done} />
            )}

            {!loading && !loadError && !current && dayNext && (
              // Round 3: the day's words are done; the day goes on.
              <Surface as="section" shape="hero" className="lx-done" data-day-next="">
                <ShapeToken kind="reward" size="lg" />
                <h2 className="av2-headline av2-headline--screen">{daySessionCopy(language).words_done}</h2>
                <div className="lx-done__actions">
                  <Action tone="primary" onClick={() => void router.push(dayNext.href)}>
                    {dayNext.label}
                    {dayNext.meta ? <span className="av2-btn__meta">· {dayNext.meta}</span> : null}
                  </Action>
                  <ExtraWordsOffer
                    pace={newWordsPace}
                    language={language}
                    pending={addingWords}
                    onSelect={() => void addExtraWords()}
                  />
                </div>
              </Surface>
            )}

            {!loading && !loadError && !current && !dayNext && (daySession?.kind !== 'day' || dayFallback) && (
              <VocabularyReviewContinuation
                lastItem={lastReviewedItem}
                lastRating={lastRating}
                slate={wordSlate}
                onRefresh={() => void loadQueue()}
                onReturn={returnToAtelier}
                returning={returning}
                more={moreWords}
              />
            )}

            {!loading && !loadError && !current && daySession?.kind === 'more' && (
              <ExtraWordsOffer
                pace={newWordsPace}
                language={language}
                pending={addingWords}
                onSelect={() => void addExtraWords()}
              />
            )}

            {!loading && !loadError && current && (
              <>
                {/* GENTLE-ONBOARDING: the first deck says what the Lexique is. */}
                <FirstStepSticker stepKey="words" language={language} />
                {kicker && <p className="av2-label lx-review__kicker">{kicker}</p>}

                {/* The card. Tap (or Space/Enter) turns it; a turned card is swiped:
                    right «Je sais», left «Encore». The deck shows behind it while
                    more cards are left. */}
                <div className="lx-stage" ref={stageRef} data-more={sessionRemaining > 1 ? 'true' : 'false'}>
                  <div
                    key={current.word_id}
                    ref={cardRef}
                    className="lx-card"
                    data-face={revealed ? 'back' : 'front'}
                    data-mode={mode}
                    role="button"
                    tabIndex={0}
                    aria-pressed={revealed}
                    aria-label={revealed ? t.flip_back : t.flip_front}
                    onClick={() => {
                      if (suppressClickRef.current) {
                        suppressClickRef.current = false;
                        return;
                      }
                      setRevealed((value) => !value);
                    }}
                    onKeyDown={(event) => {
                      if (event.target !== event.currentTarget) return;
                      if (event.key === ' ' || event.key === 'Enter') {
                        event.preventDefault();
                        event.stopPropagation();
                        setRevealed((value) => !value);
                      }
                    }}
                    onPointerDown={onCardPointerDown}
                    onPointerMove={onCardPointerMove}
                    onPointerUp={onCardPointerEnd}
                    onPointerCancel={onCardPointerEnd}
                  >
                    {revealed && (
                      <>
                        <span className="lx-stamp lx-stamp--again" aria-hidden="true">{t.deck_again}</span>
                        <span className="lx-stamp lx-stamp--know" aria-hidden="true">{t.deck_know}</span>
                      </>
                    )}

                    {!revealed ? (
                      <div className="lx-card__middle">
                        <div className="lx-card__top">
                          {promptIsFrench && listenButton}
                        </div>
                        {/* the one Garamond-italic headline on this screen */}
                        <p
                          className="av2-headline lx-card__word review-prompt-term"
                          lang={promptIsFrench ? 'fr' : undefined}
                        >
                          {prompt}
                        </p>
                        {hint && <p className="lx-card__hint">{hint}</p>}
                      </div>
                    ) : (
                      <div className="lx-card__middle review-answer-container">
                        <div className="lx-card__top">
                          <ReviewPortrait item={current} />
                          <span className="lx-card__tools">
                            {listenButton}
                            <IconAction
                              className="lx-card__icon lx-card__history"
                              label={fill(t.open_story, { word: shownFrench(current) || prompt })}
                              onClick={(event) => {
                                event.stopPropagation();
                                void openBiography();
                              }}
                            >
                              <ShapeToken kind="story" size="sm" title={t.story_title} />
                            </IconAction>
                          </span>
                        </div>
                        <p className="lx-card__asked" lang={promptIsFrench ? 'fr' : undefined}>{prompt}</p>
                        <p
                          className="av2-headline lx-card__word review-answer-word"
                          lang={promptIsFrench ? undefined : 'fr'}
                        >
                          {answer || meaning || shownFrench(current)}
                        </p>
                      </div>
                    )}

                    <div className="lx-card__bottom">
                      {revealed && faces.backExample && (
                        <div className="lx-card__example-block">
                          <p className="av2-fr lx-card__example" lang="fr">
                            <MarkedSentence marked={faces.backExample} />
                          </p>
                          {faces.backTranslation && (
                            <p className="lx-card__example-tr">{faces.backTranslation}</p>
                          )}
                        </div>
                      )}
                      {revealed && !faces.backExample && currentSlateEntry?.anchor && (
                        <p className="av2-fr lx-card__example lx-card__anchor review-context-anchor">{currentSlateEntry.anchor}</p>
                      )}
                      <p className="lx-card__cta" aria-hidden="true">{revealed ? t.swipe_hint : t.flip_front}</p>
                    </div>
                  </div>
                </div>

                {/* The foot: one button turns the card (owner, 1 Nov: an unturned card
                    offers no grade); a turned card has the pair the swipe stands for. */}
                {foot === 'turn' ? (
                  <div className="lx-review__foot" data-foot="turn">
                    <button
                      type="button"
                      className="av2-btn av2-btn--primary lx-turn"
                      title={t.reveal_before}
                      onClick={() => setRevealed(true)}
                    >
                      {t.reveal_first}
                    </button>
                  </div>
                ) : (
                  <div className="lx-review__foot" role="group" aria-label={t.ratings_group} data-foot="grades">
                    <div className="lx-review__pair">
                      <button
                        type="button"
                        className="av2-btn lx-rate lx-rate--again"
                        onClick={() => handleRatingClick(0)}
                        title={fill(t.rate_as, { label: t.deck_again })}
                        aria-label={fill(t.rate_as, { label: t.deck_again })}
                      >
                        <ArrowLeftIcon size={18} />
                        {t.deck_again}
                      </button>
                      <button
                        type="button"
                        className="av2-btn av2-btn--done lx-rate lx-rate--know"
                        onClick={() => handleRatingClick(2)}
                        title={fill(t.rate_as, { label: t.deck_good })}
                        aria-label={fill(t.rate_as, { label: t.deck_good })}
                      >
                        {t.deck_know}
                        <ArrowRightIcon size={18} />
                      </button>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>

        <WordBiographySheet
          open={biographyOpen}
          biography={biography}
          loading={biographyLoading}
          error={biographyError ? t.biography_failed : null}
          onClose={() => setBiographyOpen(false)}
          action={biography ? <Link href={`/vocabulary?word=${biography.word.id}`}>Le Cahier</Link> : undefined}
        />
      </AtelierV2Root>

      <style jsx global>{`
        body { background: var(--app-paper); }
        /* The immersive screen: the card fills the viewport between the
           header and the footer, exactly as the artboard lays it out. */
        .av2.lx-review {
          display: block;
          min-height: 100vh;
          min-height: 100dvh;
          width: 100%;
          max-width: 720px;
          margin: 0 auto;
          padding: 0;
        }
        .av2 .lx-review__screen { width: 100%; min-height: 100vh; min-height: 100dvh; }
        .av2 .lx-review__head { padding-top: calc(12px + env(safe-area-inset-top, 0px)); }
        .av2 .lx-review__body { flex: 1 1 auto; gap: 14px; padding-bottom: calc(14px + var(--av2-safe-bottom)); }
        /* Design: filed = yellow (reward), current = ink, pending = line. */
        .av2 .lx-dot { transition: background 0.15s; }
        .av2 .lx-dot[data-state='done'] { background: var(--av2-yellow); }
        .av2 .lx-dot[data-state='current'] { background: var(--av2-ink); }
        .av2 .lx-dot[data-state='pending'] { background: var(--av2-line); }
        .av2 .lx-rule__fill { background: var(--av2-yellow); }
        .av2 .lx-review__kicker { margin: 0; min-width: 0; overflow-wrap: anywhere; opacity: 0.8; }

        /* The stage holds the card, the deck's next card peeking under it, and
           the copy of a filed card on its way out. */
        .av2 .lx-stage {
          position: relative;
          display: flex;
          flex: 1 1 auto;
          flex-direction: column;
          min-width: 0;
          padding-bottom: 6px;
        }
        .av2 .lx-stage[data-more='true']::before {
          content: '';
          position: absolute;
          left: 14px;
          right: 14px;
          top: 14px;
          bottom: -4px;
          border-radius: var(--av2-r-vocab);
          background: var(--av2-card);
          box-shadow: 0 var(--av2-press) 0 var(--av2-line-2);
          opacity: 0.7;
        }

        /* The card: radius 28, padding 26/24, the 8px press. Front on the card
           face, back on yellow — swapped at once, the turn is the motion. */
        .av2 .lx-card {
          --lx-card-face: var(--av2-card);
          --lx-card-fg: var(--av2-ink);
          --lx-card-shadow: var(--av2-line-2);
          position: relative;
          z-index: 1;
          display: flex;
          flex: 1 1 auto;
          flex-direction: column;
          justify-content: space-between;
          gap: 18px;
          min-height: 22rem;
          min-width: 0;
          padding: 22px 24px 18px;
          border: 0;
          border-radius: var(--av2-r-vocab);
          background: var(--lx-card-face);
          color: var(--lx-card-fg);
          box-shadow: 0 var(--av2-press-lg) 0 var(--lx-card-shadow);
          text-align: left;
          cursor: pointer;
          user-select: none;
          -webkit-user-select: none;
          -webkit-tap-highlight-color: transparent;
          touch-action: pan-y;
          will-change: transform;
          transition: transform 0.24s cubic-bezier(0.2, 0.8, 0.2, 1);
          animation: lx-rise 0.2s cubic-bezier(0.2, 0.8, 0.2, 1);
        }
        .av2 .lx-card[data-face='back'] {
          --lx-card-face: var(--av2-yellow);
          --lx-card-fg: var(--av2-on-yellow);
          --lx-card-shadow: var(--av2-yellow-deep);
          cursor: grab;
          animation: lx-turn 0.26s cubic-bezier(0.2, 0.8, 0.2, 1);
        }
        .av2 .lx-card[data-dragging] { transition: none; cursor: grabbing; }
        .av2 .lx-card:focus-visible { outline: 3px solid var(--av2-focus); outline-offset: 3px; }
        @keyframes lx-rise {
          from { transform: translateY(12px) scale(0.96); opacity: 0.5; }
          to { transform: none; opacity: 1; }
        }
        @keyframes lx-turn {
          from { transform: perspective(1200px) rotateY(-85deg); }
          to { transform: perspective(1200px) rotateY(0deg); }
        }

        /* The stamps a drag fades in: «Encore» to the left, «Je sais» to the right. */
        .av2 .lx-stamp {
          position: absolute;
          top: 20px;
          z-index: 2;
          padding: 4px 12px;
          border: 3px solid currentColor;
          border-radius: var(--av2-r-button);
          background: var(--av2-card);
          font-size: var(--av2-t-body-lg);
          font-weight: 800;
          pointer-events: none;
          opacity: 0;
        }
        .av2 .lx-stamp--know {
          left: 20px;
          color: var(--av2-green-deep);
          transform: rotate(-10deg);
          opacity: clamp(0, var(--lx-swipe, 0), 1);
        }
        .av2 .lx-stamp--again {
          right: 20px;
          color: var(--av2-red-deep);
          transform: rotate(10deg);
          opacity: clamp(0, calc(var(--lx-swipe, 0) * -1), 1);
        }

        .av2 .lx-card__top {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 10px;
          min-height: 40px;
        }
        .av2 .lx-card__top > :only-child:not(.lx-cast) { margin-left: auto; }
        .av2 .lx-card__tools { display: flex; gap: 6px; margin-left: auto; }
        .av2 .lx-card__icon { background: var(--av2-paper); color: var(--av2-ink); }
        /* The word sits in the middle of the card, the tools above it, the
           example and the hint line below. */
        .av2 .lx-card__middle { display: flex; flex: 1 1 auto; flex-direction: column; gap: 10px; min-width: 0; }
        .av2 .lx-card__middle > .lx-card__top + * { margin-top: auto; }
        .av2 .lx-card__middle > :last-child { margin-bottom: auto; }
        .av2 .lx-card__word {
          margin: 0;
          font-size: 2.875rem; /* design 46px */
          line-height: 1.05;
          color: inherit;
          /* A long French word breaks inside the card instead of pushing the
             320px screen sideways. */
          overflow-wrap: anywhere;
          hyphens: auto;
        }
        .av2 .lx-card__asked {
          margin: 0 0 -4px;
          font-size: var(--av2-t-body);
          line-height: 1.35;
          opacity: 0.75;
          overflow-wrap: anywhere;
        }
        .av2 .lx-card__hint {
          margin: 0;
          font-size: var(--av2-t-body);
          line-height: 1.4;
          opacity: 0.7;
          overflow-wrap: anywhere;
        }
        .av2 .lx-card__bottom { display: flex; flex-direction: column; gap: 14px; min-width: 0; }
        .av2 .lx-card__example-block {
          padding-top: 14px;
          border-top: 2px solid currentColor;
          border-top-color: color-mix(in srgb, currentColor 18%, transparent);
        }
        .av2 .lx-card__example {
          margin: 0;
          font-size: var(--av2-t-action); /* design 17px */
          line-height: 1.4;
          color: inherit;
          text-wrap: pretty;
          overflow-wrap: anywhere;
        }
        .av2 .lx-card__mark {
          background: none;
          color: inherit;
          font-weight: 700;
          text-decoration: underline;
          text-decoration-thickness: 2px;
          text-underline-offset: 3px;
        }
        .av2 .lx-card__example-tr {
          margin: 6px 0 0;
          font-family: var(--av2-sans);
          font-style: normal;
          font-size: var(--av2-t-body);
          line-height: 1.4;
          opacity: 0.75;
          overflow-wrap: anywhere;
        }
        .av2 .lx-card__cta {
          margin: 0;
          text-align: center;
          font-size: var(--av2-t-label);
          font-weight: 600;
          opacity: 0.55;
        }
        .av2 .lx-cast { gap: 6px; min-width: 0; }
        .av2 .lx-cast .av2-label { color: inherit; opacity: 0.85; }
        .av2 .lx-cast__portrait--drawn { display: inline-block; overflow: hidden; background: var(--av2-card); }
        .av2 .lx-cast__portrait { width: 22px; height: 22px; border-radius: var(--av2-r-pill); object-fit: cover; object-position: top center; background: var(--av2-line); }

        /* The foot: one 56px press to turn the card, then the pair the swipe
           stands for, at the same height so nothing jumps. */
        .av2 .lx-review__foot { display: flex; flex-direction: column; min-width: 0; }
        .av2 .lx-review__pair { display: flex; gap: 10px; min-width: 0; }
        .av2 .lx-rate { flex: 1 1 0; width: auto; gap: 8px; font-size: var(--av2-t-body-lg); }
        .av2 .lx-rate--again { color: var(--av2-red-deep); }
        .av2 .lx-turn { width: 100%; font-size: var(--av2-t-body-lg); }

        /* The empty deck. */
        .av2 .lx-done { display: flex; flex-direction: column; gap: 8px; min-width: 0; padding: 22px 20px; overflow-wrap: anywhere; }
        .av2 .lx-done__actions { display: flex; flex-direction: column; gap: 6px; margin-top: 10px; min-width: 0; }
        .av2 .lx-done__quiet { display: flex; flex-wrap: wrap; justify-content: center; gap: 8px; }

        @media (max-width: 360px) {
          .av2 .lx-card { padding: 18px 18px 16px; min-height: 18rem; }
          .av2 .lx-card__word { font-size: var(--av2-t-screen); }
        }
        @media (prefers-reduced-motion: reduce) {
          .av2 .lx-card, .av2 .lx-card[data-face='back'] { animation: none; transition: none; }
        }
      `}</style>
    </>
  );
}
