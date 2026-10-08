/**
 * WP-121 · Le Palais de mémoire and La Relecture as pure functions.
 *
 * - `clusterDue`: a cluster's due words are the sum of its pins' (A.2: clusters sum).
 * - The review «ici» (A.3) walks the server's items in order. The format of each
 *   item is the server's choice (`app/services/revue/carte.py`): a matching grid per
 *   four due words, then one rebuild per word left (a word bank with one spare chip,
 *   an unscramble when no spare exists, a dictation when the line has a clip).
 *   `reviewAfter` moves on after a grade; the review is done after the last item or as
 *   soon as the server says nothing is left at the place.
 * - `relectureSegments`: the rubric's spans as underlined segments with their flag.
 */

import type {
  CartePin,
  CarteReview,
  CarteReviewGrade,
  CarteReviewItem,
  CarteReviewWord,
  RelectureFlag,
  RelectureSpan,
} from '@/lib/carte-types';

import type { Cluster } from './carte-model';

export function clusterDue(cluster: Pick<Cluster<CartePin>, 'members'>): number {
  return cluster.members.reduce((sum, member) => sum + (member.item.dueWords || 0), 0);
}

export type ReviewProgress = {
  /** The item being posed (0-based). */
  index: number;
  /** progressId → right on this review. */
  results: Record<string, boolean>;
  /** Due words left at the place after the last grade (`null` before any). */
  remaining: number | null;
  done: boolean;
};

export function reviewStart(review: Pick<CarteReview, 'items'>): ReviewProgress {
  return { index: 0, results: {}, remaining: null, done: review.items.length === 0 };
}

/** Record a grade; the caller moves on with `reviewNext` once the verdict was seen. */
export function reviewGraded(progress: ReviewProgress, grade: Pick<CarteReviewGrade, 'results' | 'remaining'>): ReviewProgress {
  const results = { ...progress.results };
  for (const result of grade.results) results[result.progressId] = result.correct;
  return { ...progress, results, remaining: grade.remaining };
}

export function reviewNext(progress: ReviewProgress, review: Pick<CarteReview, 'items'>): ReviewProgress {
  const index = progress.index + 1;
  const done = index >= review.items.length || progress.remaining === 0;
  return { ...progress, index: done ? progress.index : index, done };
}

/** The word whose line the stage shows for an item: its first word. */
export function itemSpeaker(review: Pick<CarteReview, 'words'>, item: Pick<CarteReviewItem, 'progressIds'> | null): CarteReviewWord | null {
  if (!item) return review.words[0] ?? null;
  return review.words.find((word) => word.progressId === item.progressIds[0]) ?? review.words[0] ?? null;
}

/** Was every word of the item right (the verdict line under the format)? */
export function itemVerdict(progress: ReviewProgress, item: Pick<CarteReviewItem, 'progressIds'>): 'correct' | 'wrong' | null {
  const known = item.progressIds.filter((id) => id in progress.results);
  if (known.length === 0) return null;
  return known.every((id) => progress.results[id]) ? 'correct' : 'wrong';
}

export type RelectureSegment = { text: string; flag: RelectureFlag | null };

export function relectureSegments(text: string, spans: readonly RelectureSpan[]): RelectureSegment[] {
  const clean = [...spans]
    .map((s) => ({ start: Math.max(0, s.start), end: Math.min(text.length, s.end), flag: s.flag }))
    .filter((s) => s.end > s.start)
    .sort((a, b) => a.start - b.start);
  const out: RelectureSegment[] = [];
  let at = 0;
  for (const span of clean) {
    if (span.start < at) continue;
    if (span.start > at) out.push({ text: text.slice(at, span.start), flag: null });
    out.push({ text: text.slice(span.start, span.end), flag: span.flag });
    at = span.end;
  }
  if (at < text.length) out.push({ text: text.slice(at), flag: null });
  return out;
}

/** The pin card's Relecture row, or null: «Relire ta question» / «Relue le 14 nov.». */
export function relectureAction(pin: Pick<CartePin, 'relecture' | 'questionFr'>): { kind: 'open'; headline: boolean } | { kind: 'read'; at: string | null } | null {
  if (!pin.relecture) return null;
  if (pin.relecture.state === 'read') return { kind: 'read', at: pin.relecture.readAt };
  return { kind: 'open', headline: !pin.questionFr };
}
