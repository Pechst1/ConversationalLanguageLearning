import React, { useCallback, useEffect, useMemo, useState } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { ArrowLeft, Check, History, Loader2, RotateCcw } from 'lucide-react';
import toast from 'react-hot-toast';

import EditorialMasthead from '@/components/layout/EditorialMasthead';
import { ContinuationCard, FragilityBadge, WordBiographySheet } from '@/components/mobile';
import apiService, {
  VocabularyBiography,
  VocabularyDueContext,
  VocabularyRecommendationItem,
} from '@/services/api';
import { AnkiReviewResponse, ReviewResponse } from '@/types/reviews';

const reviewOptions = [
  { rating: 0, label: 'Again', hint: 'Bring it back soon', tone: 'red' },
  { rating: 1, label: 'Hard', hint: 'Keep it close', tone: 'yellow' },
  { rating: 2, label: 'Good', hint: 'Normal review', tone: 'blue' },
  { rating: 3, label: 'Easy', hint: 'Push it out', tone: 'black' },
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

function hrefWithQuery(path: string, pairs: Array<[string, string | number | null | undefined]>) {
  const params = new URLSearchParams();
  pairs.forEach(([key, value]) => {
    if (value === null || value === undefined) return;
    const text = String(value).trim();
    if (!text) return;
    params.append(key, text);
  });
  const query = params.toString();
  return query ? `${path}?${query}` : path;
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
  const ratingCopy = lastRating !== null ? `Last card marked ${ratingToneLabel(lastRating)}.` : 'No words are waiting in this queue.';
  const focus = [
    word ? { label: `Word · ${word}`, tone: 'vocabulary' as const } : null,
    lastRating !== null ? { label: `Rated · ${ratingToneLabel(lastRating)}`, tone: 'neutral' as const } : null,
  ].filter(Boolean) as Array<{ label: string; tone: 'vocabulary' | 'neutral' }>;

  return (
    <section className="review-done">
      <Check size={28} />
      <ContinuationCard
        tone="vocabulary"
        eyebrow="French 5000"
        title="Carry the freshest word into context"
        description={`${ratingCopy} Return to the Atelier path and let today's recommendation advance.`}
        focus={focus}
        actions={[
          { label: 'Complete and return', onClick: onReturn, loading: returning, tone: 'primary' },
          { label: 'Use in mission', href: hrefWithQuery('/missions', [['vocabulary_id', wordId]]), disabled: !wordId },
          { label: 'Read in Feuilleton', href: hrefWithQuery('/graphic-novel', [['vocabulary_id', wordId]]), disabled: !wordId },
          { label: 'Refresh queue', onClick: onRefresh, tone: 'quiet' },
        ]}
        footer="The card is scheduled; Atelier owns the next step."
      />
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
  const [reviewedIds, setReviewedIds] = useState<Set<number>>(() => new Set());
  const [lastRating, setLastRating] = useState<number | null>(null);
  const [lastReviewedItem, setLastReviewedItem] = useState<VocabularyRecommendationItem | null>(null);
  const [biographyOpen, setBiographyOpen] = useState(false);
  const [biography, setBiography] = useState<VocabularyBiography | null>(null);
  const [biographyLoading, setBiographyLoading] = useState(false);
  const [biographyError, setBiographyError] = useState<string | null>(null);

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
    } catch (error) {
      console.error(error);
      setLoadError('Vocabulary review is unavailable right now.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadQueue();
  }, [loadQueue]);

  const refreshQueueSummary = useCallback(async () => {
    try {
      const next = await apiService.getVocabularyDueContext(reviewQueueParams);
      setContext(next);
    } catch (error) {
      console.error(error);
      toast('Review saved. Atelier will refresh the count when you return.');
    }
  }, []);

  const allItems = useMemo(() => queueItems(context), [context]);
  const remainingItems = useMemo(
    () => allItems.filter((item) => !reviewedIds.has(item.word_id)),
    [allItems, reviewedIds],
  );
  const current = remainingItems[0] || null;
  const completed = reviewedIds.size;
  const total = remainingItems.length + completed;
  const progress = total ? Math.round((completed / total) * 100) : 0;

  useEffect(() => {
    setBiographyOpen(false);
    setBiography(null);
    setBiographyError(null);
    setBiographyLoading(false);
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
      setBiographyError('Could not load this word thread.');
    } finally {
      setBiographyLoading(false);
    }
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
      await refreshQueueSummary();
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

  const summary = context?.summary;
  const prompt = current ? queueWord(current) : '';
  const answer = current ? queueTranslation(current) : '';
  const french = current ? queueFrench(current) : '';
  const meaning = current ? queueMeaning(current) : '';
  const example = current ? queueExample(current) : '';
  const exampleTranslation = current ? queueExampleTranslation(current) : '';
  const contextText = example || (current ? `${french} - ${meaning}` : '');

  return (
    <>
      <Head>
        <title>Vocabulary Review</title>
      </Head>
      <EditorialMasthead
        active="studio"
        mobileAction={<Link className="review-mobile-action" href="/atelier">Today</Link>}
      />
      <main className="vocab-review-page">
        <header className="review-hero">
          <Link href="/atelier" className="review-back"><ArrowLeft size={15} /> Back to today</Link>
          <div className="review-kicker">ATELIER PATH</div>
          <h1>Vocabulary review</h1>
          <p>Clear the FSRS cards from today&apos;s Review step, then return to Atelier for the next recommendation.</p>
          <div className="review-stats">
            <span><strong>{summary?.due || 0}</strong> due</span>
            <span><strong>{summary?.fragile || 0}</strong> fragile</span>
            <span><strong>{summary?.new || 0}</strong> new</span>
          </div>
          <Link href="/vocabulary" className="review-deck-link">Open notebook deck</Link>
        </header>

        <section className="review-progress" aria-label="Vocabulary review progress">
          <div>
            <strong>{completed} / {total || 0}</strong>
            <span>{remainingItems.length ? `${remainingItems.length} waiting` : 'queue clear'}</span>
          </div>
          <div className="review-progress-bar" aria-label={`${progress}% complete`}>
            <span style={{ width: `${progress}%` }} />
          </div>
        </section>

        {loading && (
          <section className="review-state">
            <Loader2 className="spin" size={22} />
            <strong>Loading today&apos;s vocabulary session.</strong>
          </section>
        )}

        {!loading && loadError && (
          <section className="review-state error">
            <strong>{loadError}</strong>
            <button type="button" onClick={loadQueue}><RotateCcw size={14} /> Retry</button>
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
                    <h2 className="text-4xl font-black mb-2">{prompt}</h2>
                    {example && (
                      <div className="review-example mt-2 text-stone-600 text-left border-l-4 border-[var(--yellow)] bg-[var(--paper)] p-3">
                        <p className="text-lg italic font-serif">&quot;{example}&quot;</p>
                        {exampleTranslation && <em className="text-sm font-sans block mt-1 text-[var(--ink-2)]">{exampleTranslation}</em>}
                      </div>
                    )}
                  </div>
                  
                  <div className="vocab-card-hint-text">Tap card to reveal answer</div>
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
                    >
                      <History size={13} />
                      History
                    </button>
                  </div>
                  
                  <div className="review-answer-container w-full flex-1 flex flex-col justify-center my-4">
                    <span className="vocab-card-face-label">ANSWER</span>
                    <strong className="text-3xl font-black block my-2">{answer || meaning || french}</strong>
                    {contextText && contextText !== example && (
                      <div className="mt-4 p-3 bg-stone-100 border border-black/10 text-left text-sm max-h-[140px] overflow-y-auto">
                        <strong>Context Anchor:</strong>
                        <p className="italic font-serif mt-1">&quot;{contextText}&quot;</p>
                      </div>
                    )}
                  </div>

                  <div className="review-meta w-full flex gap-2 justify-center items-center flex-wrap pt-2 border-t border-black/15">
                    <FragilityBadge progress={current} compact />
                    <span className="text-[10px] uppercase font-mono px-2 py-0.5 border border-black/20">{current.scheduler || 'fsrs'}</span>
                    <span className="text-[10px] uppercase font-mono px-2 py-0.5 border border-black/20">{current.bucket}</span>
                    <span className="text-[10px] uppercase font-mono px-2 py-0.5 border border-black/20">{Math.round(current.proficiency_score || 0)}%</span>
                  </div>
                  
                  <div className="vocab-card-hint-text">Tap card to flip back</div>
                </div>
                
              </div>
            </div>

            <div className="review-ratings mt-6" aria-label="Vocabulary rating">
              {reviewOptions.map((option) => (
                <button
                  key={option.rating}
                  type="button"
                  className={option.tone}
                  disabled={reviewing || !revealed}
                  onClick={() => submitRating(option.rating)}
                >
                  <strong>{option.label}</strong>
                  <span>{option.hint}</span>
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
        action={biography ? <Link href={`/vocabulary?word=${biography.word.id}`}>Deck</Link> : undefined}
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
          padding: 20px clamp(20px, 4vw, 48px) 112px;
          background: var(--paper);
          color: var(--ink);
        }
        .review-mobile-action,
        .review-back,
        .review-kicker,
        .review-stats span,
        .review-progress span,
        .review-card-head,
        .review-prompt span,
        .review-answer span,
        .review-meta {
          font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
          font-size: 11px;
          font-weight: 900;
          letter-spacing: .1em;
          text-transform: uppercase;
        }
        .review-mobile-action,
        .review-back {
          color: var(--ink);
          text-decoration: none;
        }
        .review-back {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          margin-bottom: 22px;
          color: var(--blue);
        }
        .review-deck-link {
          display: inline-flex;
          margin-top: 14px;
          color: var(--ink-3);
          font-size: 12px;
          font-weight: 850;
          text-decoration: underline;
          text-underline-offset: 4px;
        }
        .review-deck-link:hover {
          color: var(--blue);
        }
        .review-hero {
          border-bottom: 1px solid var(--ink);
          padding-bottom: 20px;
        }
        .review-kicker {
          color: var(--ink-3);
        }
        .review-hero h1,
        .review-card h2,
        .review-done h2 {
          margin: 8px 0 0;
          font-family: "EB Garamond", Garamond, serif;
          font-size: clamp(48px, 14vw, 92px);
          font-style: italic;
          font-weight: 500;
          line-height: .9;
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
          display: grid;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: 16px;
          margin-top: 20px;
        }
        .review-stats span {
          border-top: 1px solid var(--ink);
          padding-top: 8px;
        }
        .review-stats strong {
          display: block;
          font-family: var(--app-sans, "Inter", sans-serif);
          font-size: 32px;
          line-height: 1;
        }
        .review-progress {
          display: grid;
          gap: 10px;
          margin-top: 18px;
          border: 1px solid var(--ink);
          background: var(--sheet);
          padding: 13px 14px;
        }
        .review-progress div:first-child {
          display: flex;
          justify-content: space-between;
          gap: 16px;
          align-items: baseline;
        }
        .review-progress strong {
          font-size: 20px;
        }
        .review-progress span {
          color: var(--ink-3);
          font-size: 10px;
        }
        .review-progress-bar {
          height: 9px;
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
          margin-top: 18px;
          display: flex;
          flex-direction: column;
        }
        .vocab-flashcard-perspective {
          perspective: 1000px;
          width: 100%;
          min-height: 380px;
        }
        .vocab-flashcard-inner {
          position: relative;
          width: 100%;
          height: 100%;
          min-height: 380px;
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
          min-height: 380px;
          backface-visibility: hidden;
          border: 4px solid var(--ink);
          padding: 24px;
          display: flex;
          flex-direction: column;
          box-shadow: 6px 6px 0px 0px var(--ink);
        }
        .vocab-flashcard-front {
          background: var(--sheet);
        }
        .vocab-flashcard-back {
          background: var(--yellow);
          transform: rotateY(180deg);
        }
        .vocab-card-face-label {
          font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
          font-size: 10px;
          font-weight: 900;
          letter-spacing: .1em;
          text-transform: uppercase;
          color: var(--ink-3);
        }
        .vocab-card-hint-text {
          align-self: center;
          font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
          font-size: 9px;
          font-weight: 800;
          letter-spacing: .05em;
          text-transform: uppercase;
          color: var(--ink-3);
          opacity: 0.8;
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
          color: var(--ink-3);
        }
        .review-card-head em {
          color: var(--blue);
          font-style: normal;
        }
        .review-prompt {
          border-top: 1px solid var(--ink);
          padding-top: 18px;
        }
        .review-prompt span,
        .review-answer span {
          color: var(--ink-3);
        }
        .review-card h2 {
          margin: 12px 0 0;
          color: var(--ink);
          font-family: var(--app-sans, "Inter", sans-serif);
          font-size: clamp(42px, 13vw, 74px);
          font-style: normal;
          font-weight: 950;
          line-height: .92;
          letter-spacing: 0;
          overflow-wrap: anywhere;
        }
        .review-prompt-top {
          display: flex;
          justify-content: space-between;
          gap: 12px;
          align-items: center;
        }
        .review-history-button {
          display: inline-flex;
          min-height: 32px;
          align-items: center;
          justify-content: center;
          gap: 6px;
          border: 1px solid var(--ink);
          background: var(--paper);
          padding: 0 9px;
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
          border-left: 4px solid var(--yellow);
          background: var(--paper);
          padding: 12px 14px;
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
          margin: 7px 0 0;
          color: var(--ink);
          font-family: var(--app-serif, "EB Garamond", Garamond, serif);
          font-size: 24px;
          font-style: italic;
          line-height: 1.22;
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
          margin-top: 7px;
          color: var(--ink-2);
          font-style: normal;
          line-height: 1.35;
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
        .review-answer strong {
          display: block;
          margin-top: 6px;
          font-size: 24px;
          line-height: 1.15;
          overflow-wrap: anywhere;
        }
        .review-meta {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
          align-items: center;
          color: var(--ink-3);
        }
        .review-meta span {
          border: 1px solid var(--ink);
          background: var(--paper);
          padding: 7px 9px;
        }
        .review-ratings {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 8px;
        }
        .review-ratings button {
          min-height: 82px;
          border: 1px solid var(--ink);
          background: var(--paper);
          padding: 10px 12px;
          color: var(--ink);
          text-align: left;
        }
        .review-ratings button:disabled {
          opacity: .48;
        }
        .review-ratings strong,
        .review-ratings span {
          display: block;
        }
        .review-ratings strong {
          font-size: 17px;
          line-height: 1.1;
        }
        .review-ratings span {
          margin-top: 5px;
          color: var(--ink-3);
          font-size: 13px;
        }
        .review-ratings .red {
          border-left: 4px solid var(--red);
        }
        .review-ratings .yellow {
          border-left: 4px solid var(--yellow);
        }
        .review-ratings .blue {
          border-left: 4px solid var(--blue);
        }
        .review-ratings .black {
          background: var(--ink);
          color: var(--paper);
        }
        .review-ratings .black span {
          color: rgba(248, 243, 232, .72);
        }
        .review-state,
        .review-done {
          display: grid;
          place-items: center;
          gap: 12px;
          min-height: 280px;
          padding: 24px;
          text-align: center;
        }
        .review-state.error {
          border-left: 5px solid var(--red);
        }
        .review-state button,
        .review-state a {
          min-height: 46px;
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
        .review-done :global(.continuation-card) {
          width: min(100%, 560px);
          text-align: left;
        }
        .spin {
          animation: spin 800ms linear infinite;
        }
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
        @media (max-width: 760px) {
          .vocab-review-page {
            padding: 18px 20px calc(104px + env(safe-area-inset-bottom));
          }
          .review-hero h1,
          .review-done h2 {
            font-size: clamp(52px, 18vw, 88px);
          }
          .review-card h2 {
            font-size: clamp(40px, 12vw, 64px);
          }
          .review-ratings {
            position: sticky;
            bottom: calc(72px + env(safe-area-inset-bottom));
            z-index: 10;
            margin: 0 -16px -16px;
            border-top: 1px solid var(--ink);
            background: var(--paper);
            padding: 10px 16px calc(10px + env(safe-area-inset-bottom));
          }
        }
      `}</style>
    </>
  );
}
