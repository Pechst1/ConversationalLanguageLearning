import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { useRouter } from 'next/router';
import toast from 'react-hot-toast';

import { learnerGloss } from '@/lib/glosses';
import { atelierChrome } from '@/lib/atelier-v2-copy';
import { useLearnerLanguage } from '@/lib/learner-language';
import { visualCueFor, type VisualCue } from '@/lib/visual-cues';

import MotsDuJour from '@/components/lexique/MotsDuJour';
import { WordBiographySheet } from '@/components/mobile';
import {
  Action,
  AtelierV2Root,
  Chip,
  CrossIcon,
  IconAction,
  MicIcon,
  Notice,
  Portrait,
  ShapeToken,
  StateBlock,
  StopIcon,
  Surface,
} from '@/components/atelier-v2/ui';
import { createAudioMediaRecorder, recordedAudioBlob } from '@/lib/audio-recording';
import apiService, {
  DailyWordSlate,
  VocabularyBiography,
  VocabularyDueContext,
  VocabularyRecommendationItem,
} from '@/services/api';
import { AnkiReviewResponse, ReviewResponse } from '@/types/reviews';
import {
  REVIEW_WORD_KEY,
  clearReviewProgress,
  readReviewContextCache,
  saveResumeActivity,
  writeReviewContextCache,
} from '@/lib/pilot-resilience';

/* "Le Lexique" — the review session, on the Claude design system (Atelier V2).
 *
 * This is the design's LEXIQUE artboard, the one immersive screen of the
 * vocabulary: a round close control, one segment per card in the deck (yellow
 * = filed, ink = current, line = still to come), the "2/4" count; the
 * "Mot du jour · <deck>" label; one tap-to-flip card filling the screen (card
 * face on the front, yellow on the back, the 8px press), the word as the one
 * Garamond-italic headline, a hint line printed only from real data, the
 * example sentence on the back; and the footer's 3D-press pair — "● Encore"
 * on the card face with the red dot, "■ Je sais" on ink with the yellow
 * square. Tabs and masthead are hidden, as the design hides them.
 *
 * Kept from the working deck, because the artboard is a static picture of one
 * recognition card: the four FSRS grades (Encore 0 · Dur 1 · Bien 2 · Facile 3)
 * — the pair carries 0 and 2, the two remaining grades sit under it as quiet
 * actions so the scale and the 1–4 keys are unchanged; the production, audio
 * and cloze modes with their field and microphone; the episodic anchor
 * byline; the visual cue chip; the word biography; the offline cache note; the
 * end-of-deck continuation. */

// The four French labels carry the whole scale; the English FSRS hints
// (Again/Hard/Good/Easy) were corrector internals printed on the buttons.
const reviewOptions = [
  { rating: 0, label: 'Encore', tone: 'red' },
  { rating: 1, label: 'Dur', tone: 'yellow' },
  { rating: 2, label: 'Bien', tone: 'blue' },
  { rating: 3, label: 'Facile', tone: 'green' },
] as const;

// One card costs about twenty seconds at the deck's observed pace. The
// estimate is the unit a learner plans with; the count is the one they verify.
const SECONDS_PER_CARD = 20;

// Past this many cards the design's one-segment-per-word row no longer fits a
// 320px screen (4px minimum per segment); the same progress is then drawn as
// one filled rule with the identical count and accessible value.
const MAX_SEGMENTS = 12;

// Direction is resolved server-side from the learner's stored preference.
const reviewQueueParams = {
  limit: 50,
  due_limit: 30,
  fragile_limit: 12,
  new_limit: 8,
  topic_limit: 8,
  linked_limit: 8,
} as const;

function reviewMessage(response: ReviewResponse | AnkiReviewResponse) {
  const next = 'due_at' in response ? response.due_at || response.next_review : response.next_review;
  const date = next ? new Date(next) : null;
  const label = date && !Number.isNaN(date.getTime())
    ? date.toLocaleDateString('fr-FR', { day: 'numeric', month: 'long' })
    : '';
  return label ? `Reprogrammé pour le ${label}` : 'Révision classée';
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

// A card direction reads "<asked side>_to_<answer side>". Only the first half
// matters here: `de_to_fr`/`en_to_fr` ask from the learner's side, everything
// else asks from the target language. The page used to name `de_to_fr`
// explicitly, so an English learner's cards fell through to the wrong branch.
function asksFromLearnerSide(item: VocabularyRecommendationItem) {
  const [from, to] = String(item.direction || '').split('_to_');
  return Boolean(from && to && from !== 'fr');
}

function queueWord(item: VocabularyRecommendationItem) {
  if (asksFromLearnerSide(item)) {
    return learnerGloss(item, item.word);
  }
  return item.word || item.translations?.fr || '';
}

function queueTranslation(item: VocabularyRecommendationItem) {
  if (asksFromLearnerSide(item)) {
    return item.translations?.fr || item.word || '';
  }
  return learnerGloss(item);
}

function queueFrench(item: VocabularyRecommendationItem) {
  return item.translations?.fr || item.word || '';
}

function queueMeaning(item: VocabularyRecommendationItem) {
  return learnerGloss(item);
}

function queueExample(item: VocabularyRecommendationItem) {
  return item.example_sentence?.trim() || '';
}

function queueExampleTranslation(item: VocabularyRecommendationItem) {
  return item.example_translation?.trim() || '';
}

// Any `xx_to_yy` pair prints as the two codes with a typographic arrow. Cards
// captured from the journal (missions, feuilleton, atelier) carry no direction
// at all: they used to print "Registre", a word naming nothing the learner can
// see. They now print no chip.
function queueDirection(item: VocabularyRecommendationItem) {
  const [from, to] = String(item.direction || '').split('_to_');
  if (!from || !to) return '';
  return `${from.toUpperCase()} → ${to.toUpperCase()}`;
}

/* The design's hint line reads "verbe · 1er groupe · rang 2 140". Each part
 * is printed only when the payload actually carries it. The part-of-speech
 * column comes from a heuristic import and holds English keys (and sometimes
 * "x"), so only a value we recognise prints, as a French label — never the raw
 * key, never a guess. The frequency rank is read only if the queue item
 * carries one; nothing is invented to fill the slot. */
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

function optionalRank(item: VocabularyRecommendationItem) {
  const value = (item as unknown as { frequency_rank?: unknown }).frequency_rank;
  return typeof value === 'number' && value > 0 ? value : null;
}

function formatRank(rank: number) {
  return `rang ${new Intl.NumberFormat('fr-FR').format(rank)}`;
}

function cardHint(item: VocabularyRecommendationItem) {
  const rank = optionalRank(item);
  return [partOfSpeechLabel(item.part_of_speech), rank ? formatRank(rank) : '']
    .filter(Boolean)
    .join(' · ');
}

// Articles a learner may or may not type in front of a noun: the card asks for
// the word, not for the determiner, so "radiateur" grades the same as
// "le radiateur".
const LEADING_ARTICLE = /^(?:l|le|la|les|un|une|des|du|de la|de l|d|au|aux|a l)\s+/;

function normalizeAnswer(value: string) {
  return value
    // Ligatures fold first: NFD leaves œ and æ intact and the character class
    // below then eats them, so "cœur" and "coeur" used to compare unequal.
    .toLowerCase()
    .replace(/œ/g, 'oe')
    .replace(/æ/g, 'ae')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    // Every apostrophe variant (straight, curly, the ‘ iOS inserts) collapses
    // to a space here, so "l’ami" and "l'ami" fold to the same string.
    .replace(/[^A-Za-z0-9À-ÿ]+/g, ' ')
    .trim()
    .replace(LEADING_ARTICLE, '')
    .trim();
}

function foldedSignal(value: string) {
  return value
    .toLowerCase()
    .replace(/œ/g, 'oe')
    .replace(/æ/g, 'ae')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '');
}

// Signals are matched on whole tokens. Substring matching used to fire the
// "verb" rule on the tag `verbs` and on the word `adverbe`, which is how
// "exemplaire" — a noun the Anki import had tagged as a verb — ended up
// captioned as an action.
function hasSignal(signal: string, words: string[]) {
  const tokens = new Set(signal.split(/[^a-z0-9]+/).filter(Boolean));
  return words.some((word) => tokens.has(word));
}

// The badge is a memory hook, not a dictionary entry: it names a scene the
// word belongs to. It used to read "WORD / MEMORY CUE" in English and was then
// rewritten in French — which still left the one card whose job is teaching
// French vocabulary carrying two French words a beginner cannot read. The scene
// name explains the word, so it follows the learner's language now; the table of
// cues, their shapes and their matching signals lives in `lib/visual-cues.ts`
// (WP-21). It is drawn with one of the design's four shapes rather than a
// pictogram set, and the caption still does not echo `part_of_speech`: the hint
// line prints that column, whitelisted, in its own slot.
function wordVisualCue(item: VocabularyRecommendationItem, language: string): VisualCue {
  const signal = foldedSignal([
    queueFrench(item),
    queueWord(item),
    queueMeaning(item),
    queueTranslation(item),
    ...(item.topic_tags || []),
  ].filter(Boolean).join(' '));

  return visualCueFor(signal, hasSignal, language);
}

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function clozePrompt(item: VocabularyRecommendationItem) {
  const french = queueFrench(item);
  const example = queueExample(item);
  if (!french || !example) return example;
  const boundary = 'A-Za-z0-9À-ÖØ-öø-ÿ';
  const pattern = new RegExp(`(^|[^${boundary}])(${escapeRegExp(french)})(?=$|[^${boundary}])`, 'i');
  return example.replace(pattern, '$1_____');
}

// True only when the sentence actually loses the word. The example is often
// inflected ("final" against "la séance finale"), and the un-blanked sentence
// was printed as the prompt with the answer still in it.
function clozeIsBlanked(item: VocabularyRecommendationItem) {
  const prompt = clozePrompt(item);
  return Boolean(prompt) && prompt.includes('_____');
}

function cardMode(item: VocabularyRecommendationItem | null): 'recognition' | 'production' | 'audio' | 'cloze' {
  if (!item) return 'recognition';
  if ((item.proficiency_score || 0) >= 90 && item.example_sentence && clozeIsBlanked(item)) return 'cloze';
  if ((item.proficiency_score || 0) >= 72 && item.bucket !== 'new') return 'audio';
  if ((item.proficiency_score || 0) >= 55 && item.bucket !== 'new') return 'production';
  return 'recognition';
}

// Bucket keys are corrector internals; the card prints their French name.
const bucketLabels: Record<string, string> = {
  due: 'À revoir',
  fragile: 'Fragile',
  new: 'La pioche du jour',
  linked: 'Mot voisin',
  topic: 'Du thème',
  topic_compatible: 'Du thème',
};

function formatDueLabel(item: VocabularyRecommendationItem) {
  const fallback = bucketLabels[item.bucket] || 'À revoir';
  if (item.bucket === 'new') return bucketLabels.new;
  const raw = item.due_at || item.next_review;
  const date = raw ? new Date(raw) : null;
  if (!date || Number.isNaN(date.getTime())) return fallback;
  return `Échéance ${date.toLocaleDateString('fr-FR', { day: 'numeric', month: 'long' })}`;
}

function ratingToneLabel(rating: number) {
  return reviewOptions.find((item) => item.rating === rating)?.label || 'Classée';
}

function decrementSummaryCount(value: number | undefined) {
  return Math.max(0, Number(value || 0) - 1);
}

/* The episodic anchor: the character this word was met with, as the design's
   portrait byline. The server portrait is used when it loads; otherwise the
   initial on the character's accent, exactly as the Feuilleton draws it. */
function ReviewPortrait({ item }: { item: VocabularyRecommendationItem }) {
  const [failed, setFailed] = useState(false);
  const anchor = item.episodic_anchor;
  if (!anchor) return null;
  const name = anchor.character_name || 'Le Feuilleton';
  return (
    <span className="av2-byline lx-cast" title={`Ancré dans votre histoire avec ${name}`}>
      {anchor.portrait_url && !failed ? (
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
}: {
  lastItem: VocabularyRecommendationItem | null;
  lastRating: number | null;
  slate: DailyWordSlate | null;
  onRefresh: () => void;
  onReturn: () => void;
  returning: boolean;
}) {
  const wordId = lastItem?.word_id || null;
  const word = lastItem ? queueFrench(lastItem) || queueWord(lastItem) : '';
  const ratingCopy = lastRating !== null ? ratingToneLabel(lastRating) : '';

  return (
    <>
      <Surface as="section" shape="hero" className="lx-done" aria-label="Fin de la révision">
        <ShapeToken kind="done" size="lg" />
        <p className="av2-label">Révision espacée</p>
        {/* the one Garamond-italic headline once the deck is empty */}
        <h2 className="av2-headline av2-headline--screen">Paquet vidé</h2>
        {(word || ratingCopy) && (
          <p className="av2-body av2-body--lg">{[word, ratingCopy].filter(Boolean).join(' · ')}</p>
        )}
        <div className="lx-done__actions">
          {/* the one tactile 3D press on the empty deck */}
          <Action tone="done" pending={returning} pendingLabel="Retour…" onClick={onReturn}>
            L’Atelier
          </Action>
          <div className="lx-done__quiet">
            <Action tone="quiet" inline onClick={onRefresh}>Actualiser</Action>
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
  const [reviewing, setReviewing] = useState(false);
  const [returning, setReturning] = useState(false);
  const [revealed, setRevealed] = useState(false);
  const [typedAnswer, setTypedAnswer] = useState('');
  const [audioPlaying, setAudioPlaying] = useState(false);
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  // Le Lexique has no journey envelope, so the learner's language comes from the
  // profile rather than a `control_language` field. Only the failure copy below
  // uses it: the deck's chrome stays French.
  const learnerLanguage = useLearnerLanguage();
  const chrome = atelierChrome(learnerLanguage);
  const [reviewedIds, setReviewedIds] = useState<Set<number>>(() => new Set());
  const [lastRating, setLastRating] = useState<number | null>(null);
  const [lastReviewedItem, setLastReviewedItem] = useState<VocabularyRecommendationItem | null>(null);
  const [biographyOpen, setBiographyOpen] = useState(false);
  const [biography, setBiography] = useState<VocabularyBiography | null>(null);
  const [biographyLoading, setBiographyLoading] = useState(false);
  const [biographyError, setBiographyError] = useState<string | null>(null);
  const [resumeWordId, setResumeWordId] = useState<number | null>(null);
  const [cachedContextAt, setCachedContextAt] = useState<string | null>(null);
  const visibleCacheRef = useRef(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const recordingStreamRef = useRef<MediaStream | null>(null);
  const recordingWordIdRef = useRef<number | null>(null);
  const activeWordIdRef = useRef<number | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const loadQueue = useCallback(async () => {
    setLoading(!visibleCacheRef.current);
    setLoadError(null);
    try {
      const [next, slate] = await Promise.all([
        apiService.getVocabularyDueContext(reviewQueueParams),
        apiService.getWordsOfTheDay().catch(() => null),
      ]);
      setWordSlate(slate);
      setContext(next);
      writeReviewContextCache(next, slate);
      visibleCacheRef.current = false;
      setCachedContextAt(null);
      setReviewedIds(new Set());
      setLastRating(null);
      setLastReviewedItem(null);
      setRevealed(false);
      setTypedAnswer('');
    } catch (error) {
      console.error(error);
      if (!visibleCacheRef.current) setLoadError('La révision est indisponible.');
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
    void loadQueue();
  }, [loadQueue]);

  // "Les mots du jour" ride to the front of the deck: the day's slate words
  // are the retrieval half of the read → retrieve → produce loop.
  const slateById = useMemo(() => {
    const map = new Map<number, NonNullable<DailyWordSlate['words']>[number]>();
    for (const entry of wordSlate?.words || []) map.set(entry.word_id, entry);
    return map;
  }, [wordSlate]);
  const allItems = useMemo(() => {
    const items = queueItems(context);
    const ordered = slateById.size === 0 ? items : [
      ...items.filter((item) => slateById.has(item.word_id)),
      ...items.filter((item) => !slateById.has(item.word_id)),
    ];
    if (!resumeWordId) return ordered;
    return [
      ...ordered.filter((item) => item.word_id === resumeWordId),
      ...ordered.filter((item) => item.word_id !== resumeWordId),
    ];
  }, [context, resumeWordId, slateById]);
  const remainingItems = useMemo(
    () => allItems.filter((item) => !reviewedIds.has(item.word_id)),
    [allItems, reviewedIds],
  );
  const current = remainingItems[0] || null;
  const currentSlateEntry = current ? slateById.get(current.word_id) || null : null;
  const completed = reviewedIds.size;
  const total = remainingItems.length + completed;
  const sessionRemaining = remainingItems.length;
  const remainingSummary = useMemo(() => ({
    due: remainingItems.filter((item) => item.bucket === 'due').length,
    fragile: remainingItems.filter((item) => item.bucket === 'fragile').length,
    new: remainingItems.filter((item) => item.bucket === 'new').length,
  }), [remainingItems]);
  const progress = total ? Math.round((completed / total) * 100) : 0;
  const minutesLeft = sessionRemaining
    ? Math.max(1, Math.round((sessionRemaining * SECONDS_PER_CARD) / 60))
    : 0;
  // The bucket split is one quiet sentence, and only when it actually says
  // something the headline count does not.
  const deckComposition = useMemo(() => {
    const parts: string[] = [];
    if (remainingSummary.due) parts.push(`${remainingSummary.due} à revoir`);
    if (remainingSummary.fragile) {
      parts.push(`${remainingSummary.fragile} fragile${remainingSummary.fragile > 1 ? 's' : ''}`);
    }
    if (remainingSummary.new) {
      parts.push(`${remainingSummary.new} nouveau${remainingSummary.new > 1 ? 'x' : ''}`);
    }
    if (parts.length < 2) return '';
    return `Dont ${parts.slice(0, -1).join(', ')} et ${parts[parts.length - 1]}.`;
  }, [remainingSummary]);

  useEffect(() => {
    if (current) {
      window.localStorage.setItem(REVIEW_WORD_KEY, String(current.word_id));
      setResumeWordId(current.word_id);
      saveResumeActivity({ href: '/vocabulary/review', kind: 'review', entityId: current.word_id });
    } else if (!loading && context) {
      // The deck is done: drop the resume card *and* the cached queue, or the
      // next visit paints the finished deck again from localStorage before the
      // network can correct it.
      clearReviewProgress();
      setResumeWordId(null);
      setCachedContextAt(null);
    }
  }, [context, current, loading]);

  const stopRecordingTracks = useCallback(() => {
    recordingStreamRef.current?.getTracks().forEach((track) => track.stop());
    recordingStreamRef.current = null;
  }, []);

  const cancelActiveRecording = useCallback(() => {
    recordingWordIdRef.current = null;
    const recorder = mediaRecorderRef.current;
    if (recorder && recorder.state !== 'inactive') {
      recorder.stop();
    }
    mediaRecorderRef.current = null;
    stopRecordingTracks();
    setRecording(false);
  }, [stopRecordingTracks]);

  useEffect(() => {
    activeWordIdRef.current = current?.word_id || null;
    cancelActiveRecording();
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }
    setBiographyOpen(false);
    setBiography(null);
    setBiographyError(null);
    setBiographyLoading(false);
    setTypedAnswer('');
    setAudioPlaying(false);
    setRecording(false);
    setTranscribing(false);
  }, [current?.word_id, cancelActiveRecording]);

  useEffect(() => () => cancelActiveRecording(), [cancelActiveRecording]);

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
      setBiographyError('L’histoire de ce mot est indisponible.');
    } finally {
      setBiographyLoading(false);
    }
  };

  const playAudioPrompt = async (event: React.MouseEvent<HTMLButtonElement>) => {
    event.stopPropagation();
    if (!current || audioPlaying) return;
    const text = queueFrench(current);
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
      await player.play();
    } catch (error) {
      console.error(error);
      if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = 'fr-FR';
        utterance.onend = () => setAudioPlaying(false);
        utterance.onerror = () => setAudioPlaying(false);
        window.speechSynthesis.cancel();
        window.speechSynthesis.speak(utterance);
      } else {
        setAudioPlaying(false);
        toast.error('La lecture audio a échoué.');
      }
    }
  };

  const transcribeReviewAudio = async (blob: Blob, wordId: number) => {
    if (activeWordIdRef.current !== wordId) return;
    setTranscribing(true);
    try {
      const transcript = await apiService.transcribeAudio(blob);
      if (activeWordIdRef.current !== wordId) {
        return;
      }
      if (transcript.trim()) {
        setTypedAnswer(transcript.trim());
      } else {
        toast(chrome.transcription_empty);
      }
    } catch (error) {
      console.error(error);
      toast.error(chrome.transcription_failed);
    } finally {
      if (activeWordIdRef.current === wordId) {
        setTranscribing(false);
      }
    }
  };

  const startRecording = async (event: React.MouseEvent<HTMLButtonElement>) => {
    event.stopPropagation();
    if (!current || recording || transcribing) return;
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      toast.error(chrome.mic_unavailable);
      return;
    }
    try {
      const wordId = current.word_id;
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (activeWordIdRef.current !== wordId) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }
      const recorder = createAudioMediaRecorder(stream);
      mediaRecorderRef.current = recorder;
      recordingStreamRef.current = stream;
      recordingWordIdRef.current = wordId;
      chunksRef.current = [];
      recorder.ondataavailable = (recorderEvent) => {
        if (recorderEvent.data.size > 0) {
          chunksRef.current.push(recorderEvent.data);
        }
      };
      recorder.onstop = () => {
        const stoppedWordId = recordingWordIdRef.current;
        recordingWordIdRef.current = null;
        const audioBlob = recordedAudioBlob(chunksRef.current, recorder);
        stopRecordingTracks();
        setRecording(false);
        if (stoppedWordId === wordId && activeWordIdRef.current === wordId) {
          void transcribeReviewAudio(audioBlob, wordId);
        }
      };
      recorder.start();
      setRecording(true);
    } catch (error) {
      console.error(error);
      toast.error(chrome.mic_open_failed);
    }
  };

  const stopRecording = (event: React.MouseEvent<HTMLButtonElement>) => {
    event.stopPropagation();
    const recorder = mediaRecorderRef.current;
    if (!recorder || !recording || recorder.state === 'inactive') return;
    recorder.stop();
  };

  const submitRating = async (rating: number) => {
    if (!current || reviewing) return;
    setReviewing(true);
    try {
      const response = await apiService.submitAnkiReview({ word_id: current.word_id, rating });
      toast.success(reviewMessage(response));
      setReviewedIds((prev) => new Set(prev).add(current.word_id));
      setLastRating(rating);
      setLastReviewedItem(current);
      setContext((prev) => optimisticallyDecrementSummary(prev, current));
      setRevealed(false);
      setTypedAnswer('');
    } catch (error) {
      console.error(error);
      toast.error('La révision n’a pas pu être classée.');
    } finally {
      setReviewing(false);
    }
  };

  const returnToAtelier = async () => {
    setReturning(true);
    await router.push('/atelier');
  };

  // A grade pressed on an unturned card turns it first; it never files blind.
  const handleRatingClick = (rating: number) => {
    if (reviewing) return;
    if (!revealed) {
      setRevealed(true);
      return;
    }
    void submitRating(rating);
  };

  // The deck was tap-only: nothing revealed a card or filed it from a
  // keyboard. Space/Enter turns the card, 1-4 file it once turned — the same
  // order as the four grades, so the hand learns one scale.
  useEffect(() => {
    if (!current) return undefined;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      const target = event.target as HTMLElement | null;
      const typing = Boolean(target?.closest('input, textarea, [contenteditable="true"]'));
      if (typing) {
        // Enter in the answer field turns the card; it never files it blind.
        if (event.key === 'Enter' && !revealed) {
          event.preventDefault();
          setRevealed(true);
        }
        return;
      }
      if (event.key === ' ' || event.key === 'Enter') {
        // Buttons handle their own Space/Enter; the shortcut is for the page.
        if (target?.closest('button, a, [role="dialog"]')) return;
        event.preventDefault();
        setRevealed((value) => !value);
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

  const mode = cardMode(current);
  const prompt = current
    ? mode === 'audio'
      ? 'Écoutez le mot français'
      : mode === 'production'
      ? queueMeaning(current) || queueFrench(current)
      : mode === 'cloze'
        ? clozePrompt(current)
        : queueWord(current)
    : '';
  const answer = current ? (mode === 'recognition' ? queueTranslation(current) : queueFrench(current)) : '';
  const french = current ? queueFrench(current) : '';
  const meaning = current ? queueMeaning(current) : '';
  const example = current ? queueExample(current) : '';
  const exampleTranslation = current ? queueExampleTranslation(current) : '';
  const visualCue = current ? wordVisualCue(current, learnerLanguage) : null;
  const visibleExample = mode === 'audio' ? '' : example;
  const contextText = mode === 'audio'
    ? [meaning, example].filter(Boolean).join(' · ')
    : example || (current ? `${french} - ${meaning}` : '');
  const typedMatches = normalizeAnswer(typedAnswer) === normalizeAnswer(answer);
  const hint = current ? cardHint(current) : '';
  const direction = current ? queueDirection(current) : '';

  // "Mot du jour · French 5000": the tag half is the deck the card came from,
  // printed only when the payload names one.
  const kicker = current
    ? [
        currentSlateEntry ? 'Mot du jour' : formatDueLabel(current),
        current.deck_name || '',
      ].filter(Boolean).join(' · ')
    : '';

  // One segment per card in the deck: yellow = filed, ink = current, line =
  // still to come. Beyond MAX_SEGMENTS the same value is one filled rule.
  const dots = allItems.map((item) => ({
    id: item.word_id,
    state: reviewedIds.has(item.word_id) ? 'done' : item.word_id === current?.word_id ? 'current' : 'pending',
  }));
  const countLabel = total ? `${completed}/${total}` : '';
  const progressCaption = sessionRemaining
    ? `${sessionRemaining} ${sessionRemaining > 1 ? 'cartes' : 'carte'}${minutesLeft ? ` · environ ${minutesLeft} min` : ''}`
    : completed
      ? `${completed} carte${completed > 1 ? 's' : ''} classée${completed > 1 ? 's' : ''}`
      : 'Rien à revoir aujourd’hui';

  return (
    <>
      <Head>
        <title>Le Lexique · Révision · L’Atelier</title>
      </Head>
      <AtelierV2Root as="main" className="lx-review" aria-label="Le Lexique — révision">
        <div className="av2-screen lx-review__screen">
          {/* The screen's own name, in every state including the loading and
              empty ones. The design draws no title here, so it is announced
              rather than printed (WP-20 D-11). */}
          <h1 className="av2-sr">Le Lexique — révision</h1>
          {/* The design's Lexique header: round close, one segment per word,
              the count. No masthead and no tabs on this immersive screen. */}
          <header className="av2-session__head lx-review__head">
            <IconAction label="Quitter la révision" onClick={() => void returnToAtelier()} pending={returning}>
              <CrossIcon size={16} />
            </IconAction>
            <div className="av2-progress">
              {total > 0 && total <= MAX_SEGMENTS ? (
                <div
                  className="av2-progress__segments lx-dots"
                  role="progressbar"
                  aria-label="Progression de la révision"
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
                  aria-label="Progression de la révision"
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={progress}
                  aria-valuetext={loading ? 'Ouverture du paquet…' : progressCaption}
                >
                  <div className="av2-progress__fill lx-rule__fill" style={{ width: `${progress}%` }} />
                </div>
              )}
              {countLabel && <span className="av2-progress__count">{countLabel}</span>}
            </div>
          </header>

          <div className="av2-screen__body lx-review__body">
            {cachedContextAt && (
              <Notice tone="quiet" shape="story">
                <p>Édition précédente · mise à jour en cours…</p>
              </Notice>
            )}

            {loading && (
              <StateBlock tone="loading" title="Ouverture du paquet…" body="Le paquet du jour arrive." />
            )}

            {!loading && loadError && (
              <StateBlock
                tone="error"
                title="Paquet indisponible"
                body={loadError}
                action={{ label: 'Réessayer', onSelect: () => void loadQueue() }}
              />
            )}

            {!loading && !loadError && !current && (
              <VocabularyReviewContinuation
                lastItem={lastReviewedItem}
                lastRating={lastRating}
                slate={wordSlate}
                onRefresh={loadQueue}
                onReturn={returnToAtelier}
                returning={returning}
              />
            )}

            {!loading && !loadError && current && (
              <>
                <div className="lx-review__kicker">
                  <p className="av2-label">{kicker}</p>
                  {direction && <span className="av2-label lx-review__direction">{direction}</span>}
                </div>
                {deckComposition && <p className="av2-body lx-review__composition">{deckComposition}</p>}
                {current.recommendation_reason?.text && (
                  <p className="av2-body lx-review__why">{current.recommendation_reason.text}</p>
                )}

                {/* The tap-to-flip card. It holds a field and two audio
                    controls in the production/audio modes, so it is a region
                    with its own flip control rather than one big button;
                    Space/Enter on the page and a tap anywhere on the card
                    still turn it. */}
                <div
                  className="lx-card"
                  data-face={revealed ? 'back' : 'front'}
                  data-mode={mode}
                  role="button"
                  tabIndex={0}
                  aria-pressed={revealed}
                  aria-label={revealed ? 'Sens · touche pour revenir' : 'Touche pour retourner'}
                  onClick={() => setRevealed((value) => !value)}
                  onKeyDown={(event) => {
                    if (event.target !== event.currentTarget) return;
                    if (event.key === ' ' || event.key === 'Enter') {
                      event.preventDefault();
                      setRevealed((value) => !value);
                    }
                  }}
                >
                  <div className="lx-card__top">
                    <span>{revealed ? 'Sens · touche pour revenir' : 'Touche pour retourner'}</span>
                    <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
                      <path d="M7 0L14 14H0Z" fill="currentColor" />
                    </svg>
                  </div>

                  {!revealed ? (
                    <div className="lx-card__middle">
                      <div className="lx-card__marks">
                        <ReviewPortrait item={current} />
                        {visualCue && mode !== 'audio' && (
                          <Chip
                            className="review-visual-cue lx-cue"
                            icon={<ShapeToken kind={visualCue.shape} size="sm" />}
                            aria-label={`Indice visuel : ${visualCue.label}`}
                          >
                            {visualCue.label} · {visualCue.caption}
                          </Chip>
                        )}
                      </div>
                      {mode === 'audio' ? (
                        <>
                          <p className="av2-headline lx-card__word lx-card__word--sans">{prompt}</p>
                          <div className="lx-card__audio" onClick={(event) => event.stopPropagation()}>
                            <Action
                              tone="secondary"
                              inline
                              pending={audioPlaying}
                              pendingLabel="Lecture…"
                              onClick={playAudioPrompt}
                              icon={<ShapeToken kind="story" size="sm" />}
                            >
                              Écouter
                            </Action>
                            <IconAction
                              label={transcribing ? chrome.transcribing : recording ? chrome.record_stop : chrome.record_start}
                              tone={recording ? 'recording' : 'action'}
                              pressable
                              pending={transcribing}
                              onClick={recording ? stopRecording : startRecording}
                            >
                              {recording ? <StopIcon size={18} /> : <MicIcon size={18} />}
                            </IconAction>
                          </div>
                          <p className="lx-card__hint">Écouter · répondre</p>
                        </>
                      ) : (
                        <>
                          {/* the one Garamond-italic headline on this screen */}
                          <p className="av2-headline lx-card__word review-prompt-term">{prompt}</p>
                          {hint && <p className="lx-card__hint">{hint}</p>}
                        </>
                      )}
                      {mode !== 'recognition' && (
                        <input
                          className="av2-field__control lx-input lx-card__input"
                          lang="fr"
                          value={typedAnswer}
                          onChange={(event) => setTypedAnswer(event.target.value)}
                          onClick={(event) => event.stopPropagation()}
                          placeholder={mode === 'audio' ? 'Écrivez ce que vous avez entendu' : 'Écrivez la réponse française'}
                          aria-label="Écrire la réponse française"
                          autoComplete="off"
                          autoCapitalize="off"
                        />
                      )}
                    </div>
                  ) : (
                    <div className="lx-card__middle review-answer-container">
                      <div className="lx-card__marks">
                        <IconAction
                          className="lx-card__history"
                          label={`Ouvrir l’histoire du mot ${french || prompt}`}
                          onClick={(event) => {
                            event.stopPropagation();
                            void openBiography();
                          }}
                        >
                          <ShapeToken kind="story" size="sm" title="L’histoire du mot" />
                        </IconAction>
                      </div>
                      <p className="av2-headline lx-card__word review-answer-word">{answer || meaning || french}</p>
                      {mode !== 'recognition' && typedAnswer && (
                        <p className="lx-card__hint lx-card__verdict" data-match={typedMatches ? 'true' : 'false'}>
                          <ShapeToken kind={typedMatches ? 'done' : 'action'} size="sm" />
                          {typedMatches ? 'Réponse exacte' : `Votre réponse : ${typedAnswer}`}
                        </p>
                      )}
                      {mode !== 'recognition' && meaning && meaning !== answer && (
                        <p className="lx-card__hint">{meaning}</p>
                      )}
                      {hint && mode === 'recognition' && <p className="lx-card__hint">{hint}</p>}
                    </div>
                  )}

                  <div className="lx-card__bottom">
                    {revealed && visibleExample && (
                      <p className="av2-fr lx-card__example">
                        « {visibleExample} »
                        {exampleTranslation && <span className="lx-card__example-tr">{exampleTranslation}</span>}
                      </p>
                    )}
                    {revealed && contextText && contextText !== example && !visibleExample && (
                      <p className="av2-fr lx-card__example review-context-anchor">« {contextText} »</p>
                    )}
                    {revealed && currentSlateEntry?.anchor && (
                      <p className="av2-fr lx-card__example lx-card__anchor">{currentSlateEntry.anchor}</p>
                    )}
                  </div>
                </div>

                {/* The footer's 3D-press pair, exactly as the artboard draws
                    it: "● Encore" on the card face, "■ Je sais" on ink. Encore
                    files grade 0 and Je sais grade 2 (Bien); Dur (1) and
                    Facile (3) stay reachable underneath as quiet actions, so
                    the four-grade FSRS scale is unchanged. */}
                <div className="lx-review__foot" aria-label="Noter la carte">
                  <div className="lx-review__pair">
                    <button
                      type="button"
                      className="av2-btn lx-rate"
                      disabled={reviewing}
                      onClick={() => handleRatingClick(0)}
                      title={revealed ? 'Noter : Encore' : 'Révéler la réponse'}
                      aria-label={revealed ? 'Noter : Encore' : 'Révéler la réponse avant de noter'}
                    >
                      <span className="av2-shape av2-shape--dot lx-rate__dot" aria-hidden="true" />
                      Encore
                    </button>
                    <button
                      type="button"
                      className="av2-btn av2-btn--done lx-rate"
                      disabled={reviewing}
                      onClick={() => handleRatingClick(2)}
                      title={revealed ? 'Noter : Bien' : 'Révéler la réponse'}
                      aria-label={revealed ? 'Noter : Bien' : 'Révéler la réponse avant de noter'}
                    >
                      <ShapeToken kind="reward" size="sm" />
                      Je sais
                    </button>
                  </div>
                  <div className="lx-review__grades">
                    {reviewOptions.map((option) => (
                      option.rating === 1 || option.rating === 3 ? (
                        <Action
                          key={option.rating}
                          tone="quiet"
                          inline
                          disabled={reviewing}
                          onClick={() => handleRatingClick(option.rating)}
                          title={revealed ? `Noter : ${option.label}` : 'Révéler la réponse'}
                          aria-label={revealed ? `Noter : ${option.label}` : 'Révéler la réponse avant de noter'}
                        >
                          {option.label}
                        </Action>
                      ) : null
                    ))}
                  </div>
                </div>
              </>
            )}
          </div>
        </div>

        <WordBiographySheet
          open={biographyOpen}
          biography={biography}
          loading={biographyLoading}
          error={biographyError}
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
          max-width: 720px;
          margin: 0 auto;
          padding: 0;
        }
        .av2 .lx-review__screen { min-height: 100vh; min-height: 100dvh; }
        .av2 .lx-review__head { padding-top: calc(12px + env(safe-area-inset-top, 0px)); }
        .av2 .lx-review__body { flex: 1 1 auto; gap: 12px; padding-bottom: calc(14px + var(--av2-safe-bottom)); }
        /* Design: filed = yellow (reward), current = ink, pending = line. */
        .av2 .lx-dot[data-state='done'] { background: var(--av2-yellow); }
        .av2 .lx-dot[data-state='current'] { background: var(--av2-ink); }
        .av2 .lx-dot[data-state='pending'] { background: var(--av2-line); }
        .av2 .lx-rule__fill { background: var(--av2-yellow); }
        .av2 .lx-review__kicker { display: flex; align-items: center; justify-content: space-between; gap: 10px; min-width: 0; }
        .av2 .lx-review__direction { flex: none; font-weight: 600; }
        .av2 .lx-review__composition, .av2 .lx-review__why { margin-top: -4px; }
        .av2 .lx-review__why { font-family: var(--av2-serif); font-style: italic; }

        /* The card: radius 28, padding 26/24, the 8px press. Front on the card
           face, back on yellow, 0.25s colour swap. */
        .av2 .lx-card {
          --lx-card-face: var(--av2-card);
          --lx-card-fg: var(--av2-ink);
          --lx-card-shadow: var(--av2-line-2);
          position: relative;
          display: flex;
          flex: 1 1 auto;
          flex-direction: column;
          justify-content: space-between;
          gap: 16px;
          min-height: 22rem;
          min-width: 0;
          padding: 26px 24px;
          border: 0;
          border-radius: var(--av2-r-vocab);
          background: var(--lx-card-face);
          color: var(--lx-card-fg);
          box-shadow: 0 var(--av2-press-lg) 0 var(--lx-card-shadow);
          text-align: left;
          cursor: pointer;
          user-select: none;
          -webkit-user-select: none;
          transition: background 0.25s, color 0.25s, transform var(--av2-press-dur), box-shadow var(--av2-press-dur);
        }
        .av2 .lx-card:active {
          transform: translateY(4px);
          box-shadow: 0 4px 0 var(--lx-card-shadow);
        }
        .av2 .lx-card[data-face='back'] {
          --lx-card-face: var(--av2-yellow);
          --lx-card-fg: var(--av2-on-yellow);
          --lx-card-shadow: var(--av2-yellow-deep);
        }
        .av2 .lx-card__top {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 10px;
          font-size: var(--av2-t-label);
          font-weight: 700;
          opacity: 0.85;
        }
        .av2 .lx-card__middle { display: flex; flex-direction: column; gap: 14px; min-width: 0; }
        .av2 .lx-card__marks { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; min-height: 0; }
        .av2 .lx-card__marks:empty { display: none; }
        .av2 .lx-card__word {
          font-size: 2.875rem; /* design 46px */
          line-height: 1;
          color: inherit;
        }
        .av2 .lx-card__word--sans {
          font-family: var(--av2-sans);
          font-style: normal;
          font-weight: 700;
          font-size: var(--av2-t-title);
          line-height: 1.15;
        }
        .av2 .lx-card__hint {
          display: flex;
          align-items: center;
          gap: 6px;
          margin: 0;
          font-size: var(--av2-t-body);
          line-height: 1.4;
          opacity: 0.9;
          overflow-wrap: anywhere;
        }
        .av2 .lx-card__verdict { font-weight: 700; }
        .av2 .lx-card__bottom { min-width: 0; }
        .av2 .lx-card__bottom:empty { display: none; }
        .av2 .lx-card__example {
          margin: 0;
          font-size: var(--av2-t-action); /* design 17px */
          line-height: 1.35;
          opacity: 0.9;
          color: inherit;
          text-wrap: pretty;
        }
        .av2 .lx-card__example + .lx-card__example { margin-top: 8px; }
        .av2 .lx-card__example-tr {
          display: block;
          margin-top: 4px;
          font-family: var(--av2-sans);
          font-style: normal;
          font-size: var(--av2-t-label);
          line-height: 1.35;
        }
        .av2 .lx-card__audio { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
        /* The cast chip and the cue chip sit on the card face, so they take the
           paper ground instead of the card's own colour. */
        .av2 .lx-cast { gap: 6px; }
        .av2 .lx-cast .av2-label { color: inherit; opacity: 0.85; }
        .av2 .lx-cast__portrait { width: 22px; height: 22px; border-radius: var(--av2-r-pill); object-fit: cover; object-position: top center; background: var(--av2-line); }
        .av2 .lx-cue { background: var(--av2-paper); color: var(--av2-ink); }
        .av2 .lx-card__history { background: var(--av2-paper); }
        /* globals.css puts an !important 1px ruled border on every input; the
           design's field is a paper well with a 2px focus edge. */
        .av2 .lx-input {
          border: 2px solid transparent !important;
          border-radius: var(--av2-r-card) !important;
          box-shadow: none !important;
          background-color: var(--av2-paper);
          color: var(--av2-ink);
          min-height: max(var(--av2-tap), 3rem);
          cursor: text;
        }
        .av2 .lx-input:focus { border-color: var(--av2-blue) !important; box-shadow: none !important; outline: 0; }
        .av2 .lx-card__input { max-width: 26rem; }

        /* The footer pair: two 56px presses, 10px apart, then the two
           remaining grades as quiet actions. */
        .av2 .lx-review__foot { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
        .av2 .lx-review__pair { display: flex; gap: 10px; min-width: 0; }
        .av2 .lx-rate { flex: 1 1 0; width: auto; font-size: var(--av2-t-body-lg); }
        .av2 .lx-rate__dot { background: var(--av2-red); width: 12px; height: 12px; }
        .av2 .lx-review__grades { display: flex; justify-content: center; gap: 12px; min-width: 0; }

        /* The empty deck. */
        .av2 .lx-done { display: flex; flex-direction: column; gap: 8px; padding: 22px 20px; }
        .av2 .lx-done__actions { display: flex; flex-direction: column; gap: 6px; margin-top: 10px; min-width: 0; }
        .av2 .lx-done__quiet { display: flex; flex-wrap: wrap; justify-content: center; gap: 8px; }

        @media (max-width: 360px) {
          .av2 .lx-card { padding: 20px 18px; min-height: 18rem; }
          .av2 .lx-card__word { font-size: var(--av2-t-screen); }
          .av2 .lx-review__pair { flex-direction: column; }
        }
      `}</style>
    </>
  );
}
