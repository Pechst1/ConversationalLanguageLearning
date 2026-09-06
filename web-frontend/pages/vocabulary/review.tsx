import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { useRouter } from 'next/router';
import {
  ArrowDown,
  BookOpen,
  Briefcase,
  CalendarDays,
  Check,
  HeartPulse,
  History,
  Home,
  Landmark,
  Loader2,
  MapPin,
  MessageCircle,
  Mic,
  Palette,
  RotateCcw,
  Shapes,
  Shirt,
  Square,
  Train,
  Utensils,
  Users,
  Volume2,
  type LucideIcon,
} from 'lucide-react';
import toast from 'react-hot-toast';

import { learnerGloss } from '@/lib/glosses';

import EditorialMasthead from '@/components/layout/EditorialMasthead';
import MotsDuJour from '@/components/lexique/MotsDuJour';
import { WordBiographySheet } from '@/components/mobile';
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

type ReviewVisualCue = {
  label: string;
  caption: string;
  tone: string;
  Icon: LucideIcon;
};

// The badge is a memory hook, not a dictionary entry: it names a scene the
// word belongs to. Both lines are French publication copy — they used to read
// "WORD / MEMORY CUE", "TIME / when", the last English left on the card. The
// caption no longer echoes `part_of_speech` either: that column comes from a
// heuristic import (scripts/enrich_vocabulary.py) and is wrong often enough
// that printing it made the card assert something false.
function wordVisualCue(item: VocabularyRecommendationItem): ReviewVisualCue {
  const signal = foldedSignal([
    queueFrench(item),
    queueWord(item),
    queueMeaning(item),
    queueTranslation(item),
    ...(item.topic_tags || []),
  ].filter(Boolean).join(' '));

  if (hasSignal(signal, ['abaisser', 'baisse', 'reduire', 'reduction', 'senken', 'lower', 'down'])) {
    return { label: 'Baisse', caption: 'mouvement', tone: 'blue', Icon: ArrowDown };
  }
  if (hasSignal(signal, ['famille', 'ami', 'soeur', 'frere', 'mere', 'pere', 'person', 'schwester', 'freund'])) {
    return { label: 'Gens', caption: 'relation', tone: 'red', Icon: Users };
  }
  if (hasSignal(signal, ['cafe', 'vin', 'restaurant', 'manger', 'boire', 'pain', 'food', 'essen', 'trinken'])) {
    return { label: 'Table', caption: 'repas', tone: 'yellow', Icon: Utensils };
  }
  if (hasSignal(signal, ['heure', 'jour', 'semaine', 'temps', 'week', 'time', 'morgen', 'gestern'])) {
    return { label: 'Temps', caption: 'quand', tone: 'blue', Icon: CalendarDays };
  }
  if (hasSignal(signal, ['train', 'gare', 'metro', 'bus', 'voiture', 'voyage', 'reise', 'transport'])) {
    return { label: 'Trajet', caption: 'mouvement', tone: 'green', Icon: Train };
  }
  if (hasSignal(signal, ['maison', 'appartement', 'porte', 'fenetre', 'home', 'haus', 'wohnung'])) {
    return { label: 'Maison', caption: 'lieu', tone: 'yellow', Icon: Home };
  }
  if (hasSignal(signal, ['ville', 'rue', 'hotel', 'bureau', 'place', 'street', 'stadt', 'office'])) {
    return { label: 'Ville', caption: 'où', tone: 'blue', Icon: MapPin };
  }
  if (hasSignal(signal, ['travail', 'argent', 'prix', 'client', 'job', 'work', 'geld'])) {
    return { label: 'Travail', caption: 'pratique', tone: 'green', Icon: Briefcase };
  }
  if (hasSignal(signal, ['sante', 'douleur', 'malade', 'corps', 'health', 'arzt', 'krank'])) {
    return { label: 'Corps', caption: 'santé', tone: 'red', Icon: HeartPulse };
  }
  if (hasSignal(signal, ['ecole', 'cours', 'livre', 'apprendre', 'question', 'learn', 'schule'])) {
    return { label: 'Étude', caption: 'savoir', tone: 'blue', Icon: BookOpen };
  }
  if (hasSignal(signal, ['dire', 'parler', 'demander', 'message', 'lettre', 'sagen', 'sprechen'])) {
    return { label: 'Parole', caption: 'message', tone: 'green', Icon: MessageCircle };
  }
  if (hasSignal(signal, ['loi', 'etat', 'gouvernement', 'politique', 'law', 'recht'])) {
    return { label: 'Cité', caption: 'institutions', tone: 'red', Icon: Landmark };
  }
  if (hasSignal(signal, ['film', 'musique', 'jeu', 'art', 'danser', 'music'])) {
    return { label: 'Culture', caption: 'loisir', tone: 'yellow', Icon: Palette };
  }
  if (hasSignal(signal, ['robe', 'chemise', 'pantalon', 'chaussure', 'kleid', 'schuh'])) {
    return { label: 'Habits', caption: 'objet', tone: 'green', Icon: Shirt };
  }
  return { label: 'Mot', caption: 'à retenir', tone: 'neutral', Icon: Shapes };
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

function ReviewPortrait({ item }: { item: VocabularyRecommendationItem }) {
  const [failed, setFailed] = useState(false);
  const anchor = item.episodic_anchor;
  if (!anchor) return null;
  const name = anchor.character_name || 'Le Feuilleton';
  return (
    <span
      className="review-cast-chip"
      title={`Ancré dans votre histoire avec ${name}`}
      style={anchor.accent_colour ? { '--cast-accent': anchor.accent_colour } as React.CSSProperties : undefined}
    >
      {anchor.portrait_url && !failed ? (
        /* eslint-disable-next-line @next/next/no-img-element */
        <img src={anchor.portrait_url} alt="" onError={() => setFailed(true)} />
      ) : <span className="review-cast-initial">{name.slice(0, 1).toUpperCase()}</span>}
      <em>{name}</em>
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
      <section className="review-done">
        <Check size={28} />
        <div>
          <span>Révision espacée</span>
          <h2>Paquet vidé</h2>
          {(word || ratingCopy) && <p>{[word, ratingCopy].filter(Boolean).join(' · ')}</p>}
        </div>
        <div className="review-done-actions">
          <button type="button" onClick={onReturn} disabled={returning}>
            {returning ? 'Retour…' : 'L’Atelier'}
          </button>
          <button type="button" onClick={onRefresh}>Actualiser</button>
          {wordId && <Link href={`/vocabulary?word=${wordId}`}>Le Cahier</Link>}
        </div>
      </section>
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
  // The bucket split used to be four stacked counters over a single card. It
  // is one quiet sentence now, and only when it actually says something the
  // headline count does not.
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
        toast('Aucune parole détectée.');
      }
    } catch (error) {
      console.error(error);
      toast.error('La transcription a échoué.');
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
      toast.error('L’enregistrement vocal n’est pas disponible dans ce navigateur.');
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
      toast.error('Le micro n’a pas pu être ouvert.');
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
  // order as the four buttons, so the hand learns one scale.
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
  const visualCue = current ? wordVisualCue(current) : null;
  const VisualIcon = visualCue?.Icon || Shapes;
  const visibleExample = mode === 'audio' ? '' : example;
  const contextText = mode === 'audio'
    ? [meaning, example].filter(Boolean).join(' · ')
    : example || (current ? `${french} - ${meaning}` : '');
  const typedMatches = normalizeAnswer(typedAnswer) === normalizeAnswer(answer);

  return (
    <>
      <Head>
        <title>Le Lexique · Révision · L’Atelier</title>
      </Head>
      <EditorialMasthead
        active="studio"
      />
      <main className="vocab-review-page">
        {/* One dateline, one count, one hairline of progress. Everything else
            the deck knows about itself stays below the rule, in prose. */}
        <header className="review-hero">
          <div className="review-kicker">Le Lexique</div>
          <h1>Révision</h1>
          <p className="review-tally">
            {loading ? (
              <em>Ouverture du paquet…</em>
            ) : loadError ? (
              <em>Paquet indisponible</em>
            ) : sessionRemaining ? (
              <>
                <strong>{sessionRemaining}</strong>
                <span>
                  {sessionRemaining > 1 ? 'cartes' : 'carte'}
                  {minutesLeft ? ` · environ ${minutesLeft} min` : ''}
                </span>
              </>
            ) : completed ? (
              <em>{completed} carte{completed > 1 ? 's' : ''} classée{completed > 1 ? 's' : ''}</em>
            ) : (
              <em>Rien à revoir aujourd’hui</em>
            )}
          </p>
          <div
            className="review-progress-bar"
            role="progressbar"
            aria-label="Progression de la révision"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={progress}
          >
            <span style={{ width: `${progress}%` }} />
          </div>
          {!loading && !loadError && deckComposition && (
            <p className="review-composition">{deckComposition}</p>
          )}
        </header>

        {cachedContextAt && (
          <p className="review-cache-note">Édition précédente · mise à jour en cours…</p>
        )}

        {loading && (
          <section className="review-state">
            <Loader2 className="spin" size={22} />
            <strong>Chargement</strong>
          </section>
        )}

        {!loading && loadError && (
          <section className="review-state error">
            <strong>{loadError}</strong>
            <button type="button" onClick={() => void loadQueue()} aria-label="Réessayer la révision"><RotateCcw size={14} /> Réessayer</button>
          </section>
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
          <div className="review-card-container">
            <div
              className="vocab-flashcard-perspective cursor-pointer select-none"
              role="button"
              tabIndex={0}
              aria-pressed={revealed}
              aria-label={revealed ? 'Masquer la réponse' : 'Révéler la réponse'}
              onClick={() => setRevealed((value) => !value)}
            >
              <div className={`vocab-flashcard-inner ${revealed ? 'flipped' : ''}`}>

                {/* FRONT FACE */}
                <div className="vocab-flashcard-front">
                  {/* The direction chip belongs to the card, and prints once:
                      one mark on the left, one on the right, never three. */}
                  <div className="review-card-head w-full">
                    <span>{queueDirection(current)}</span>
                    {/* Empty when the card came from the journal rather than a
                        directional deck; the due label keeps the right edge. */}
                    {currentSlateEntry
                      ? <span className="review-slate-tag">Mot du jour</span>
                      : <em>{formatDueLabel(current)}</em>}
                  </div>
                  {current.recommendation_reason?.text && (
                    <p className="review-why">{current.recommendation_reason.text}</p>
                  )}
                  <ReviewPortrait item={current} />

                  <div className="review-prompt w-full flex-1 flex flex-col justify-center my-4">
                    {mode === 'audio' ? (
                      <div className="review-audio-prompt">
                        <h2>{prompt}</h2>
                        <div className="review-audio-actions" onClick={(event) => event.stopPropagation()}>
                          <button type="button" disabled={audioPlaying} onClick={playAudioPrompt}>
                            {audioPlaying ? <Loader2 className="spin" size={17} /> : <Volume2 size={17} />}
                            {audioPlaying ? 'Lecture…' : 'Écouter'}
                          </button>
                          <button
                            type="button"
                            className={recording ? 'recording' : ''}
                            disabled={transcribing}
                            onClick={recording ? stopRecording : startRecording}
                          >
                            {transcribing ? <Loader2 className="spin" size={17} /> : recording ? <Square size={17} /> : <Mic size={17} />}
                            {transcribing ? 'Transcription…' : recording ? 'Arrêter' : 'Enregistrer'}
                          </button>
                        </div>
                        <span>Écouter · répondre</span>
                      </div>
                    ) : (
                      <>
                        {visualCue && (
                          <div className={`review-visual-cue ${visualCue.tone}`} aria-label={`Indice visuel : ${visualCue.label}`}>
                            <VisualIcon size={31} />
                            <span>{visualCue.label}</span>
                            <em>{visualCue.caption}</em>
                          </div>
                        )}
                        <h2 className="review-prompt-term">{prompt}</h2>
                      </>
                    )}
                    {mode !== 'recognition' && (
                      <input
                        className="review-type-input"
                        value={typedAnswer}
                        onChange={(event) => setTypedAnswer(event.target.value)}
                        onClick={(event) => event.stopPropagation()}
                        placeholder={mode === 'audio' ? 'Écrivez ce que vous avez entendu' : 'Écrivez la réponse française'}
                        aria-label="Écrire la réponse française"
                      />
                    )}
                  </div>

                  <div className="vocab-card-hint-text">Taper pour révéler</div>
                </div>

                {/* BACK FACE */}
                <div className="vocab-flashcard-back">
                  {/* The back face inherits the direction from the front; only
                      the word's own thread is offered here. */}
                  <div className="review-card-head w-full relative flex justify-end items-center">
                    <button
                      type="button"
                      className="review-history-button"
                      onClick={(e) => {
                        e.stopPropagation();
                        openBiography();
                      }}
                      aria-label={`Ouvrir l’histoire du mot ${french || prompt}`}
                      title="L’histoire du mot"
                    >
                      <History size={13} />
                    </button>
                  </div>

                  <div className="review-answer-container w-full flex-1 flex flex-col">
                    <strong className="review-answer-word">{answer || meaning || french}</strong>
                    {mode !== 'recognition' && typedAnswer && (
                      <small className={typedMatches ? 'review-type-result match' : 'review-type-result miss'}>
                        {typedMatches ? 'Réponse exacte' : `Votre réponse : ${typedAnswer}`}
                      </small>
                    )}
                    {visibleExample && (
                      <div className="review-example">
                        <p>&quot;{visibleExample}&quot;</p>
                        {exampleTranslation && <em>{exampleTranslation}</em>}
                      </div>
                    )}
                    {contextText && contextText !== example && !visibleExample && (
                      <div className="review-context-anchor">
                        <p>&quot;{contextText}&quot;</p>
                      </div>
                    )}
                    {currentSlateEntry?.anchor && (
                      <div className="review-slate-anchor">
                        <em>{currentSlateEntry.anchor}</em>
                      </div>
                    )}
                  </div>
                </div>

              </div>
            </div>

            <div className="review-ratings mt-6" aria-label="Noter la carte">
              {reviewOptions.map((option) => (
                <button
                  key={option.rating}
                  type="button"
                  className={option.tone}
                  disabled={reviewing}
                  onClick={() => handleRatingClick(option.rating)}
                  title={revealed ? `Noter : ${option.label}` : 'Révéler la réponse'}
                  aria-label={revealed ? `Noter : ${option.label}` : 'Révéler la réponse avant de noter'}
                >
                  <strong>{option.label}</strong>
                </button>
              ))}
            </div>
          </div>
        )}
      </main>

      <WordBiographySheet
        open={biographyOpen}
        biography={biography}
        loading={biographyLoading}
        error={biographyError}
        onClose={() => setBiographyOpen(false)}
        action={biography ? <Link href={`/vocabulary?word=${biography.word.id}`}>Cahier</Link> : undefined}
      />

      <style jsx>{`
        .vocab-review-page {
          --paper: var(--app-paper);
          --paper-2: var(--app-paper-2);
          --paper-3: var(--app-paper-3);
          --sheet: var(--app-sheet);
          --ink: var(--app-ink);
          --ink-2: var(--app-ink-2);
          --ink-3: var(--app-ink-3);
          --red: var(--app-red);
          --blue: var(--app-blue);
          --yellow: var(--app-yellow);
          min-height: 100vh;
          width: min(100%, 640px);
          margin: 0 auto;
          padding: 22px clamp(20px, 4vw, 32px) 112px;
          background: var(--paper);
          color: var(--ink);
        }
        .review-why { width: 100%; margin: 10px 0 0; color: var(--ink-3); font: italic 12px/1.35 var(--serif); }
        .review-cache-note { margin: 10px 0 0; color: var(--ink-3); font: italic 12px/1.4 var(--serif); }
        .review-cast-chip { display: inline-flex; align-items: center; gap: 6px; align-self: flex-start; margin-top: 8px; color: var(--ink-2); font: 11px/1 var(--serif); }
        .review-cast-chip img, .review-cast-chip { --chip-size: 24px; }
        .review-cast-chip > img { width: var(--chip-size); height: var(--chip-size); border: 1px solid var(--ink); background: var(--cast-accent, var(--paper-2)); object-fit: cover; object-position: top center; }
        .review-cast-initial { width: var(--chip-size); height: var(--chip-size); display: grid; place-items: center; border: 1px solid var(--ink); background: var(--cast-accent, var(--paper-2)); font: 900 9px/1 var(--mono); }
        .review-cast-chip em { font-style: italic; }
        .review-kicker,
        .review-card-head,
        .review-prompt span,
        .review-answer span {
          font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
          font-size: 11px;
          font-weight: 900;
          letter-spacing: .1em;
          text-transform: uppercase;
        }
        .review-hero {
          border-bottom: 1px solid var(--ink);
          padding-bottom: 18px;
        }
        .review-kicker {
          color: var(--ink-3);
        }
        .review-hero h1,
        .review-done h2 {
          margin: 6px 0 0;
          color: var(--ink);
          font-family: "EB Garamond", Garamond, serif;
          font-size: clamp(32px, 8vw, 46px);
          font-style: italic;
          font-weight: 500;
          line-height: .94;
          letter-spacing: 0;
        }
        .review-done p {
          margin: 14px 0 0;
          max-width: 640px;
          color: var(--ink-2);
          font-size: 18px;
          line-height: 1.35;
        }
        /* The single status line: how much is left, and what that costs.
           No box, no second brand — it reads as a standfirst. */
        .review-tally {
          display: flex;
          align-items: baseline;
          gap: 9px;
          margin: 12px 0 0;
          color: var(--ink-2);
          font-family: var(--app-serif, "EB Garamond", Garamond, serif);
          font-size: 16px;
          line-height: 1.2;
        }
        .review-tally strong {
          color: var(--ink);
          font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
          font-size: 21px;
          font-weight: 900;
          line-height: 1;
        }
        .review-tally span {
          color: var(--ink-2);
          font-style: italic;
        }
        .review-tally em {
          color: var(--ink-3);
          font-style: italic;
        }
        /* A hairline, not a gauge: resume state without a second counter. */
        .review-progress-bar {
          height: 2px;
          margin-top: 14px;
          background: var(--paper-3);
        }
        .review-progress-bar span {
          display: block;
          height: 100%;
          background: var(--ink);
          transition: width 180ms ease;
        }
        /* The bucket split, once, as prose — never as a row of chips. */
        .review-composition {
          margin: 10px 0 0;
          color: var(--ink-3);
          font-family: var(--app-serif, "EB Garamond", Garamond, serif);
          font-size: 13px;
          font-style: italic;
          line-height: 1.4;
        }
        .review-card-container {
          margin-top: 24px;
          display: flex;
          flex-direction: column;
        }
        .vocab-flashcard-perspective {
          perspective: 1000px;
          width: 100%;
          min-height: 320px;
        }
        .vocab-flashcard-inner {
          position: relative;
          width: 100%;
          height: 100%;
          min-height: 320px;
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
          min-height: 320px;
          backface-visibility: hidden;
          border: 2px solid var(--ink);
          padding: 26px 28px;
          display: flex;
          flex-direction: column;
        }
        .vocab-flashcard-front {
          background: var(--app-sheet);
        }
        .vocab-flashcard-back {
          background: var(--app-sheet);
          transform: rotateY(180deg);
          overflow: hidden;
        }
        .vocab-card-hint-text {
          align-self: center;
          font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
          font-size: 9px;
          font-weight: 800;
          letter-spacing: .05em;
          text-transform: uppercase;
          color: var(--ink-3);
          opacity: 0.82;
          margin-top: auto;
        }
        .review-state,
        .review-done {
          margin-top: 18px;
          border: 1px solid var(--ink);
          background: var(--sheet);
        }
        .review-card-head {
          display: flex;
          justify-content: space-between;
          gap: 14px;
          color: var(--ink-2);
        }
        .review-card-head em {
          color: var(--ink-3);
          font-style: normal;
        }
        .review-slate-tag {
          border: 1px solid var(--app-blue);
          color: var(--app-blue);
          padding: 2px 6px 1px;
          font-size: 9px;
          font-weight: 900;
          letter-spacing: .12em;
          text-transform: uppercase;
          white-space: nowrap;
        }
        .review-slate-anchor {
          margin-top: 12px;
          font-family: var(--app-serif);
          font-style: italic;
          font-size: 13px;
          color: var(--ink-3);
          text-align: left;
        }
        .review-prompt {
          border-top: 1px solid var(--ink);
          padding-top: 20px;
          min-height: 166px;
          align-items: stretch;
        }
        .review-prompt-term {
          margin: 0;
          color: var(--ink);
          font-family: "EB Garamond", Garamond, serif;
          font-size: clamp(42px, 12vw, 62px);
          font-style: italic;
          font-weight: 600;
          line-height: 1;
          letter-spacing: 0;
          overflow-wrap: anywhere;
          text-shadow: none;
          text-align: center;
        }
        .review-visual-cue {
          width: min(164px, 100%);
          margin: 0 auto 16px;
          display: grid;
          justify-items: center;
          gap: 4px;
          border: 1px solid var(--ink);
          background: var(--paper);
          padding: 10px 12px;
        }
        .review-visual-cue svg {
          color: var(--blue);
          stroke-width: 2.2;
        }
        .review-prompt .review-visual-cue span {
          color: var(--ink);
          font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
          font-size: 10px;
          font-weight: 900;
          letter-spacing: .08em;
          text-transform: uppercase;
        }
        .review-visual-cue em {
          margin: 0;
          color: var(--ink-3);
          font-size: 11px;
          font-style: normal;
        }
        .review-visual-cue.red svg {
          color: var(--red);
        }
        .review-visual-cue.yellow svg {
          color: var(--yellow);
        }
        .review-visual-cue.green svg {
          color: var(--app-green);
        }
        .review-visual-cue.neutral svg {
          color: var(--ink-3);
        }
        .review-prompt span,
        .review-answer span {
          color: var(--ink-3);
        }
        .review-prompt-top {
          display: flex;
          justify-content: space-between;
          gap: 12px;
          align-items: center;
        }
        .review-history-button {
          /* 44px is the smallest reliable thumb target; it was 32. */
          display: inline-flex;
          width: 44px;
          height: 44px;
          align-items: center;
          justify-content: center;
          border: 1px solid var(--ink);
          background: var(--paper);
          padding: 0;
          color: var(--blue);
          font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
          font-size: 10px;
          font-weight: 900;
          letter-spacing: .1em;
          line-height: 1;
          text-transform: uppercase;
        }
        .review-history-button:disabled {
          opacity: .55;
        }
        .review-example {
          margin-top: 12px;
          border-left: 4px solid var(--blue);
          background: var(--paper);
          padding: 10px 12px;
          color: var(--ink);
          text-align: left;
        }
        .review-example.empty {
          border-left-color: var(--ink-3);
        }
        .review-example span {
          display: block;
          color: var(--ink-3);
          font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
          font-size: 11px;
          font-weight: 900;
          letter-spacing: .1em;
          text-transform: uppercase;
        }
        .review-example p {
          margin: 0;
          color: var(--ink);
          font-family: var(--app-serif, "EB Garamond", Garamond, serif);
          font-size: clamp(18px, 5vw, 20px);
          font-style: italic;
          line-height: 1.18;
        }
        .review-example.empty p {
          color: var(--ink-3);
          font-family: var(--app-sans, "Inter", sans-serif);
          font-size: 15px;
          font-style: normal;
          font-weight: 800;
        }
        .review-example em {
          display: block;
          margin-top: 6px;
          color: var(--ink-2);
          font-size: 12px;
          font-style: normal;
          line-height: 1.25;
        }
        .review-context-anchor {
          max-height: 140px;
          overflow-y: auto;
          margin-top: 16px;
          border: 1px solid color-mix(in srgb, var(--app-ink) 20%, transparent);
          background: color-mix(in srgb, var(--app-sheet) 72%, transparent);
          padding: 12px 14px;
          color: var(--ink);
          text-align: left;
          font-size: 14px;
        }
        .review-context-anchor strong {
          font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
          font-size: 10px;
          font-weight: 900;
          letter-spacing: .1em;
          text-transform: uppercase;
        }
        .review-context-anchor p {
          margin: 6px 0 0;
          font-family: var(--app-serif, "EB Garamond", Garamond, serif);
          font-size: 17px;
          font-style: italic;
          line-height: 1.25;
        }
        .review-audio-prompt {
          display: grid;
          justify-items: center;
          gap: 12px;
        }
        .review-audio-prompt h2 {
          margin: 0;
          color: var(--ink);
          font-family: var(--app-sans, "Inter", sans-serif);
          font-size: clamp(28px, 9vw, 42px);
          font-style: normal;
          font-weight: 950;
          line-height: .96;
          letter-spacing: 0;
          text-align: center;
        }
        .review-audio-prompt span {
          color: var(--ink-3);
          font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
          font-size: 10px;
          font-weight: 900;
          letter-spacing: .08em;
          text-transform: uppercase;
          text-align: center;
        }
        .review-audio-actions {
          display: flex;
          flex-wrap: wrap;
          justify-content: center;
          gap: 10px;
        }
        .review-audio-actions button {
          display: inline-flex;
          min-width: 118px;
          min-height: 44px;
          align-items: center;
          justify-content: center;
          gap: 8px;
          border: 2px solid var(--ink);
          background: var(--yellow);
          color: var(--ink);
          font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
          font-size: 11px;
          font-weight: 950;
          letter-spacing: .08em;
          text-transform: uppercase;
        }
        .review-audio-actions button.recording {
          background: var(--red);
          color: var(--paper);
        }
        .review-audio-actions button:disabled {
          cursor: wait;
          opacity: .65;
        }
        .review-type-input {
          width: min(100%, 420px);
          min-height: 44px;
          margin: 14px auto 0;
          border: 2px solid var(--ink);
          background: var(--sheet);
          padding: 0 14px;
          color: var(--ink);
          font-size: 18px;
          font-weight: 850;
          text-align: center;
          outline: none;
        }
        .review-type-input:focus {
          border-color: var(--blue);
          box-shadow: inset 4px 0 0 var(--blue);
        }
        .review-type-result {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          min-height: 28px;
          margin: 6px auto 0;
          border: 1px solid var(--ink);
          padding: 4px 8px;
          font-size: 12px;
          font-weight: 900;
        }
        .review-type-result.match {
          border-color: var(--blue);
          color: var(--blue);
        }
        .review-type-result.miss {
          border-color: var(--red);
          color: var(--red);
        }
        .reveal-answer {
          min-height: 56px;
          border: 1px solid var(--ink);
          background: var(--ink);
          color: var(--paper);
          font: inherit;
          font-weight: 900;
          letter-spacing: .12em;
          text-transform: uppercase;
        }
        .review-answer {
          border-left: 4px solid var(--blue);
          background: var(--paper);
          padding: 12px 14px;
        }
        .review-answer strong,
        .review-answer-word {
          display: block;
          margin: 0;
          color: var(--ink);
          font-family: "EB Garamond", Garamond, serif;
          font-size: clamp(34px, 10vw, 54px);
          font-style: italic;
          font-weight: 600;
          line-height: 1;
          overflow-wrap: anywhere;
          text-align: center;
        }
        .review-answer-container {
          min-height: 0;
          margin: 12px 0 0;
          justify-content: center;
          overflow-y: auto;
          scrollbar-width: thin;
        }
        .vocab-flashcard-back .review-answer-word {
          font-size: clamp(30px, 8vw, 46px);
          line-height: .98;
        }
        .review-ratings {
          display: grid;
          grid-template-columns: repeat(4, minmax(0, 1fr));
          gap: 10px;
          margin-top: 18px;
        }
        .review-ratings button {
          min-height: 48px;
          border: 2px solid var(--ink);
          background: var(--paper);
          padding: 0 8px;
          color: var(--ink);
          text-align: center;
          border-radius: 10px;
        }
        .review-ratings button:disabled {
          cursor: wait;
          opacity: .55;
        }
        .review-ratings strong,
        .review-ratings span {
          display: block;
        }
        .review-ratings strong {
          font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
          font-size: 13px;
          line-height: 1.1;
          letter-spacing: .04em;
          text-transform: uppercase;
        }
        .review-ratings span {
          margin-top: 5px;
          color: var(--ink-3);
          font-size: 13px;
        }
        .review-ratings .red {
          border-color: var(--red);
          color: var(--red);
        }
        .review-ratings .yellow {
          border-color: var(--yellow);
        }
        .review-ratings .blue {
          border-color: var(--blue);
          color: var(--blue);
        }
        .review-ratings .green {
          border-color: var(--app-green);
          color: var(--app-green);
        }
        .review-state,
        .review-done {
          display: grid;
          place-items: center;
          gap: 12px;
          min-height: 150px;
          margin-top: 22px;
          padding: 18px;
          text-align: center;
        }
        .review-state.error {
          border-left: 4px solid var(--red);
        }
        .review-state button,
        .review-state a {
          min-height: 42px;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
          border: 1px solid var(--ink);
          background: var(--paper);
          padding: 0 14px;
          color: var(--ink);
          font: inherit;
          font-weight: 900;
          text-decoration: none;
        }
        .review-done span {
          color: var(--ink-3);
          font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
          font-size: 11px;
          font-weight: 900;
          letter-spacing: .1em;
          text-transform: uppercase;
        }
        .review-done p {
          margin: 6px 0 0;
          color: var(--ink-2);
        }
        .review-done-actions {
          display: flex;
          flex-wrap: wrap;
          justify-content: center;
          gap: 8px;
        }
        .spin {
          animation: spin 800ms linear infinite;
        }
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
        @media (max-width: 760px) {
          .vocab-review-page {
            padding: 20px 28px calc(104px + env(safe-area-inset-bottom));
          }
          .review-hero h1,
          .review-done h2 {
            font-size: clamp(34px, 10vw, 42px);
          }
          .review-ratings {
            position: sticky;
            bottom: calc(72px + env(safe-area-inset-bottom));
            z-index: 10;
            margin: 18px -8px -8px;
            background: var(--paper);
            padding: 8px 0 calc(8px + env(safe-area-inset-bottom));
          }
          .review-ratings button {
            min-height: 44px;
            border-radius: 9px;
            font-size: 12px;
          }
        }
      `}</style>
    </>
  );
}
