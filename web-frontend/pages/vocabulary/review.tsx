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

import EditorialMasthead from '@/components/layout/EditorialMasthead';
import { WordBiographySheet } from '@/components/mobile';
import apiService, {
  VocabularyBiography,
  VocabularyDueContext,
  VocabularyRecommendationItem,
} from '@/services/api';
import { AnkiReviewResponse, ReviewResponse } from '@/types/reviews';

const reviewOptions = [
  { rating: 0, label: 'Encore', hint: 'Again', tone: 'red' },
  { rating: 1, label: 'Dur', hint: 'Hard', tone: 'yellow' },
  { rating: 2, label: 'Bien', hint: 'Good', tone: 'blue' },
  { rating: 3, label: 'Facile', hint: 'Easy', tone: 'green' },
] as const;

const reviewQueueParams = {
  limit: 50,
  due_limit: 30,
  fragile_limit: 12,
  new_limit: 8,
  topic_limit: 8,
  linked_limit: 8,
  direction: 'fr_to_de',
} as const;

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

function queueFrench(item: VocabularyRecommendationItem) {
  return item.translations?.fr || item.word || '';
}

function queueMeaning(item: VocabularyRecommendationItem) {
  return item.translations?.de || item.translations?.en || '';
}

function queueExample(item: VocabularyRecommendationItem) {
  return item.example_sentence?.trim() || '';
}

function queueExampleTranslation(item: VocabularyRecommendationItem) {
  return item.example_translation?.trim() || '';
}

function queueDirection(item: VocabularyRecommendationItem) {
  if (item.direction === 'fr_to_de') return 'FR -> DE';
  if (item.direction === 'de_to_fr') return 'DE -> FR';
  return 'French 5000';
}

function normalizeAnswer(value: string) {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^A-Za-z0-9À-ÿ]+/g, ' ')
    .trim()
    .toLowerCase();
}

function foldedSignal(value: string) {
  return value
    .toLowerCase()
    .replace(/œ/g, 'oe')
    .replace(/æ/g, 'ae')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '');
}

function hasSignal(signal: string, words: string[]) {
  return words.some((word) => signal.includes(word));
}

type ReviewVisualCue = {
  label: string;
  caption: string;
  tone: string;
  Icon: LucideIcon;
};

function wordVisualCue(item: VocabularyRecommendationItem): ReviewVisualCue {
  const signal = foldedSignal([
    queueFrench(item),
    queueWord(item),
    queueMeaning(item),
    queueTranslation(item),
    item.part_of_speech || '',
    ...(item.topic_tags || []),
  ].filter(Boolean).join(' '));

  if (hasSignal(signal, ['abaisser', 'baisse', 'reduire', 'reduction', 'senken', 'lower', 'down'])) {
    return { label: 'lower', caption: 'movement', tone: 'blue', Icon: ArrowDown };
  }
  if (hasSignal(signal, ['famille', 'ami', 'soeur', 'frere', 'mere', 'pere', 'person', 'schwester', 'freund'])) {
    return { label: 'people', caption: 'relation', tone: 'red', Icon: Users };
  }
  if (hasSignal(signal, ['cafe', 'vin', 'restaurant', 'manger', 'boire', 'pain', 'food', 'essen', 'trinken'])) {
    return { label: 'food', caption: 'table', tone: 'yellow', Icon: Utensils };
  }
  if (hasSignal(signal, ['heure', 'jour', 'semaine', 'temps', 'week', 'time', 'morgen', 'gestern'])) {
    return { label: 'time', caption: 'when', tone: 'blue', Icon: CalendarDays };
  }
  if (hasSignal(signal, ['train', 'gare', 'metro', 'bus', 'voiture', 'voyage', 'reise', 'transport'])) {
    return { label: 'travel', caption: 'movement', tone: 'green', Icon: Train };
  }
  if (hasSignal(signal, ['maison', 'appartement', 'porte', 'fenetre', 'home', 'haus', 'wohnung'])) {
    return { label: 'home', caption: 'place', tone: 'yellow', Icon: Home };
  }
  if (hasSignal(signal, ['ville', 'rue', 'hotel', 'bureau', 'place', 'street', 'stadt', 'office'])) {
    return { label: 'place', caption: 'where', tone: 'blue', Icon: MapPin };
  }
  if (hasSignal(signal, ['travail', 'argent', 'prix', 'client', 'job', 'work', 'geld'])) {
    return { label: 'work', caption: 'practical', tone: 'green', Icon: Briefcase };
  }
  if (hasSignal(signal, ['sante', 'douleur', 'malade', 'corps', 'health', 'arzt', 'krank'])) {
    return { label: 'body', caption: 'health', tone: 'red', Icon: HeartPulse };
  }
  if (hasSignal(signal, ['ecole', 'cours', 'livre', 'apprendre', 'question', 'learn', 'schule'])) {
    return { label: 'study', caption: 'knowledge', tone: 'blue', Icon: BookOpen };
  }
  if (hasSignal(signal, ['dire', 'parler', 'demander', 'message', 'lettre', 'sagen', 'sprechen'])) {
    return { label: 'speech', caption: 'message', tone: 'green', Icon: MessageCircle };
  }
  if (hasSignal(signal, ['loi', 'etat', 'gouvernement', 'politique', 'law', 'recht'])) {
    return { label: 'society', caption: 'systems', tone: 'red', Icon: Landmark };
  }
  if (hasSignal(signal, ['film', 'musique', 'jeu', 'art', 'danser', 'music'])) {
    return { label: 'culture', caption: 'leisure', tone: 'yellow', Icon: Palette };
  }
  if (hasSignal(signal, ['robe', 'chemise', 'pantalon', 'chaussure', 'kleid', 'schuh'])) {
    return { label: 'clothing', caption: 'object', tone: 'green', Icon: Shirt };
  }
  if (hasSignal(signal, ['verb', 'verbe'])) {
    return { label: 'action', caption: 'verb', tone: 'blue', Icon: Shapes };
  }
  return { label: 'word', caption: item.part_of_speech || 'memory cue', tone: 'neutral', Icon: Shapes };
}

function cardMode(item: VocabularyRecommendationItem | null): 'recognition' | 'production' | 'audio' | 'cloze' {
  if (!item) return 'recognition';
  if ((item.proficiency_score || 0) >= 90 && item.example_sentence) return 'cloze';
  if ((item.proficiency_score || 0) >= 72 && item.bucket !== 'new') return 'audio';
  if ((item.proficiency_score || 0) >= 55 && item.bucket !== 'new') return 'production';
  return 'recognition';
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

function formatDueLabel(item: VocabularyRecommendationItem) {
  const raw = item.due_at || item.next_review;
  if (!raw) return item.bucket === 'new' ? 'new pick' : item.bucket;
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) return item.bucket;
  return `due ${date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}`;
}

function ratingToneLabel(rating: number) {
  return reviewOptions.find((item) => item.rating === rating)?.label || 'Review';
}

function decrementSummaryCount(value: number | undefined) {
  return Math.max(0, Number(value || 0) - 1);
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

function VocabularyReviewContinuation({
  lastItem,
  lastRating,
  onRefresh,
  onReturn,
  returning,
}: {
  lastItem: VocabularyRecommendationItem | null;
  lastRating: number | null;
  onRefresh: () => void;
  onReturn: () => void;
  returning: boolean;
}) {
  const wordId = lastItem?.word_id || null;
  const word = lastItem ? queueFrench(lastItem) || queueWord(lastItem) : '';
  const ratingCopy = lastRating !== null ? ratingToneLabel(lastRating) : '';

  return (
    <section className="review-done">
      <Check size={28} />
      <div>
        <span>Révision espacée</span>
        <h2>Queue claire</h2>
        {(word || ratingCopy) && <p>{[word, ratingCopy].filter(Boolean).join(' · ')}</p>}
      </div>
      <div className="review-done-actions">
        <button type="button" onClick={onReturn} disabled={returning}>
          {returning ? 'Retour...' : 'Atelier'}
        </button>
        <button type="button" onClick={onRefresh}>Actualiser</button>
        {wordId && <Link href={`/vocabulary?word=${wordId}`}>Notebook</Link>}
      </div>
    </section>
  );
}

export default function VocabularyReviewPage() {
  const router = useRouter();
  const [context, setContext] = useState<VocabularyDueContext | null>(null);
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
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const recordingStreamRef = useRef<MediaStream | null>(null);
  const recordingWordIdRef = useRef<number | null>(null);
  const activeWordIdRef = useRef<number | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const loadQueue = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const next = await apiService.getVocabularyDueContext(reviewQueueParams);
      setContext(next);
      setReviewedIds(new Set());
      setLastRating(null);
      setLastReviewedItem(null);
      setRevealed(false);
      setTypedAnswer('');
    } catch (error) {
      console.error(error);
      setLoadError('Review unavailable');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadQueue();
  }, [loadQueue]);

  const allItems = useMemo(() => queueItems(context), [context]);
  const remainingItems = useMemo(
    () => allItems.filter((item) => !reviewedIds.has(item.word_id)),
    [allItems, reviewedIds],
  );
  const current = remainingItems[0] || null;
  const completed = reviewedIds.size;
  const total = remainingItems.length + completed;
  const sessionRemaining = remainingItems.length;
  const remainingSummary = useMemo(() => ({
    due: remainingItems.filter((item) => item.bucket === 'due').length,
    fragile: remainingItems.filter((item) => item.bucket === 'fragile').length,
    new: remainingItems.filter((item) => item.bucket === 'new').length,
  }), [remainingItems]);
  const progress = total ? Math.round((completed / total) * 100) : 0;

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
      setBiographyError('Could not load this word thread.');
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
        toast.error('Could not play the audio prompt.');
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
        toast('No speech detected.');
      }
    } catch (error) {
      console.error(error);
      toast.error('Could not transcribe the recording.');
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
      toast.error('Voice recording is not available in this browser.');
      return;
    }
    try {
      const wordId = current.word_id;
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (activeWordIdRef.current !== wordId) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }
      const recorder = new MediaRecorder(stream);
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
        const audioBlob = new Blob(chunksRef.current, { type: 'audio/webm' });
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
      toast.error('Microphone access failed.');
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
      toast.error('Could not save vocabulary review.');
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

  const mode = cardMode(current);
  const prompt = current
    ? mode === 'audio'
      ? 'Listen to the French word'
      : mode === 'production'
      ? queueMeaning(current)
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
        <title>Vocabulary Review</title>
      </Head>
      <EditorialMasthead
        active="studio"
      />
      <main className="vocab-review-page">
        <header className="review-hero">
          <div className="review-title-row">
            <div>
              <div className="review-kicker">VOCABULAIRE</div>
              <h1>Révision</h1>
            </div>
            <div className="review-due-mark">
              <strong>{sessionRemaining}</strong>
              <span>restantes</span>
            </div>
          </div>
          <div className="review-progress" aria-label="Vocabulary review progress">
            <div>
              <strong>{completed} / {total || 0}</strong>
              <span>{sessionRemaining ? `${sessionRemaining} en attente` : 'clair'}</span>
            </div>
            <div className="review-progress-bar" aria-label={`${progress}% complete`}>
              <span style={{ width: `${progress}%` }} />
            </div>
          </div>
          <div className="review-stats">
            <span>{remainingSummary.due} due</span>
            <span>{remainingSummary.fragile} fragile</span>
            <span>{remainingSummary.new} new</span>
          </div>
        </header>

        {loading && (
          <section className="review-state">
            <Loader2 className="spin" size={22} />
            <strong>Chargement</strong>
          </section>
        )}

        {!loading && loadError && (
          <section className="review-state error">
            <strong>{loadError}</strong>
            <button type="button" onClick={loadQueue} aria-label="Retry vocabulary review"><RotateCcw size={14} /> Retry</button>
          </section>
        )}

        {!loading && !loadError && !current && (
          <VocabularyReviewContinuation
            lastItem={lastReviewedItem}
            lastRating={lastRating}
            onRefresh={loadQueue}
            onReturn={returnToAtelier}
            returning={returning}
          />
        )}

        {!loading && !loadError && current && (
          <div className="review-card-container">
            <div
              className="vocab-flashcard-perspective cursor-pointer select-none"
              onClick={() => setRevealed((value) => !value)}
            >
              <div className={`vocab-flashcard-inner ${revealed ? 'flipped' : ''}`}>

                {/* FRONT FACE */}
                <div className="vocab-flashcard-front">
                  <div className="review-card-head w-full">
                    <span>{queueDirection(current)}</span>
                    <em>{formatDueLabel(current)}</em>
                  </div>

                  <div className="review-prompt w-full flex-1 flex flex-col justify-center my-4">
                    {mode === 'audio' ? (
                      <div className="review-audio-prompt">
                        <h2>{prompt}</h2>
                        <div className="review-audio-actions" onClick={(event) => event.stopPropagation()}>
                          <button type="button" disabled={audioPlaying} onClick={playAudioPrompt}>
                            {audioPlaying ? <Loader2 className="spin" size={17} /> : <Volume2 size={17} />}
                            {audioPlaying ? 'Playing' : 'Play'}
                          </button>
                          <button
                            type="button"
                            className={recording ? 'recording' : ''}
                            disabled={transcribing}
                            onClick={recording ? stopRecording : startRecording}
                          >
                            {transcribing ? <Loader2 className="spin" size={17} /> : recording ? <Square size={17} /> : <Mic size={17} />}
                            {transcribing ? 'Transcribing' : recording ? 'Stop' : 'Record'}
                          </button>
                        </div>
                        <span>Écouter · répondre</span>
                      </div>
                    ) : (
                      <>
                        {visualCue && (
                          <div className={`review-visual-cue ${visualCue.tone}`} aria-label={`${visualCue.label} visual cue`}>
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
                        placeholder={mode === 'audio' ? 'Type what you heard' : 'Type the French answer'}
                        aria-label="Type the French answer"
                      />
                    )}
                  </div>

                  <div className="vocab-card-hint-text">Taper pour révéler</div>
                </div>

                {/* BACK FACE */}
                <div className="vocab-flashcard-back">
                  <div className="review-card-head w-full relative flex justify-between items-center">
                    <span>{queueDirection(current)}</span>
                    <button
                      type="button"
                      className="review-history-button"
                      onClick={(e) => {
                        e.stopPropagation();
                        openBiography();
                      }}
                      aria-label={`Open word biography for ${prompt}`}
                      title="History"
                    >
                      <History size={13} />
                    </button>
                  </div>

                  <div className="review-answer-container w-full flex-1 flex flex-col">
                    <strong className="review-answer-word">{answer || meaning || french}</strong>
                    {mode !== 'recognition' && typedAnswer && (
                      <small className={typedMatches ? 'review-type-result match' : 'review-type-result miss'}>
                        {typedMatches ? 'Typed answer matches' : `You typed: ${typedAnswer}`}
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
                  </div>
                </div>

              </div>
            </div>

            <div className="review-ratings mt-6" aria-label="Vocabulary rating">
              {reviewOptions.map((option) => (
                <button
                  key={option.rating}
                  type="button"
                  className={option.tone}
                  disabled={reviewing}
                  onClick={() => handleRatingClick(option.rating)}
                  title={revealed ? option.hint : 'Reveal answer'}
                  aria-label={revealed ? `Rate ${option.hint}` : 'Reveal answer before rating'}
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
        action={biography ? <Link href={`/vocabulary?word=${biography.word.id}`}>Notebook</Link> : undefined}
      />

      <style jsx>{`
        .vocab-review-page {
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
          width: min(100%, 640px);
          margin: 0 auto;
          padding: 22px clamp(20px, 4vw, 32px) 112px;
          background: var(--paper);
          color: var(--ink);
        }
        .review-kicker,
        .review-stats span,
        .review-progress span,
        .review-card-head,
        .review-prompt span,
        .review-answer span {
          font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
          font-size: 11px;
          font-weight: 900;
          letter-spacing: .1em;
          text-transform: uppercase;
        }
        .review-title-row {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 18px;
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
        .review-hero p,
        .review-done p {
          margin: 14px 0 0;
          max-width: 640px;
          color: var(--ink-2);
          font-size: 18px;
          line-height: 1.35;
        }
        .review-stats {
          display: flex;
          flex-wrap: wrap;
          gap: 10px 16px;
          margin-top: 12px;
          color: var(--ink-3);
        }
        .review-stats span {
          padding: 0;
        }
        .review-due-mark {
          min-width: 76px;
          border: 1px solid var(--ink);
          background: var(--sheet);
          padding: 8px 10px;
          text-align: center;
        }
        .review-due-mark strong {
          display: block;
          font-size: 25px;
          line-height: 1;
        }
        .review-due-mark span {
          display: block;
          margin-top: 3px;
          color: var(--ink-3);
          font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
          font-size: 9px;
          font-weight: 900;
          letter-spacing: .08em;
          text-transform: uppercase;
        }
        .review-progress {
          display: grid;
          gap: 7px;
          margin-top: 16px;
          border: 1px solid var(--ink);
          background: var(--sheet);
          padding: 10px 12px;
        }
        .review-progress div:first-child {
          display: flex;
          justify-content: space-between;
          gap: 16px;
          align-items: baseline;
        }
        .review-progress strong {
          font-size: 17px;
        }
        .review-progress span {
          color: var(--ink-3);
          font-size: 10px;
        }
        .review-progress-bar {
          height: 8px;
          border: 1px solid var(--ink);
          background: var(--paper);
        }
        .review-progress-bar span {
          display: block;
          height: 100%;
          background: var(--yellow);
          transition: width 180ms ease;
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
          box-shadow: 8px 8px 0px 0px var(--ink);
        }
        .vocab-flashcard-front {
          background: #fbfaf6;
        }
        .vocab-flashcard-back {
          background: #fbfaf6;
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
          box-shadow: 4px 4px 0 var(--ink);
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
          color: #23845d;
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
          display: inline-flex;
          width: 32px;
          height: 32px;
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
          border: 1px solid rgba(20, 17, 13, .2);
          background: rgba(248, 243, 232, .72);
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
          box-shadow: 3px 3px 0 var(--ink);
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
          border-color: #23845d;
          color: #23845d;
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
          .review-title-row {
            align-items: end;
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
