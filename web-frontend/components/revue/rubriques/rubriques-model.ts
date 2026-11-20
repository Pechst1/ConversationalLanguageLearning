/**
 * «Le titre» and «L'intox express» · the players' pure model (node-tested): the shown step
 * never ahead of the server's, the trap's taps, the A1 headline as the server builds it, the
 * words a quote lights, the reasons said in the learner's language (never the solution).
 */

import type { RvIntoxView, RvRubriqueError, RvTitreView } from '@/lib/revue-rubriques-types';

import { quoteSegments, type QuoteSegment } from '../comptoir/comptoir-model';
import { fill } from '../revue-copy';
import type { RubriqueCopy } from './rubriques-copy';

type Steps = { step: string; steps: readonly string[] };

/** The screen before «La page»: it holds «Voir la page» (the close). */
function lastPlayable(view: Steps): string {
  const at = view.steps.indexOf('page');
  return at > 0 ? view.steps[at - 1] : view.steps[view.steps.length - 1];
}

export function stepOrder(view: Steps, step: string): number {
  return view.steps.indexOf(step);
}

/** The screen a visit opens on: the server's step, the last one until the close is asked for. */
export function openingStep(view: Steps, closed: boolean): string {
  if (closed) return 'page';
  return view.step === 'page' ? lastPlayable(view) : view.step;
}

/** The shown step, never ahead of the server's. */
export function clampStep(view: Steps, shown: string, closed: boolean): string {
  const latest = openingStep(view, closed);
  return stepOrder(view, shown) > stepOrder(view, latest) || stepOrder(view, shown) < 0 ? latest : shown;
}

export function nextStep(view: Steps, shown: string): string | null {
  return view.steps[stepOrder(view, shown) + 1] ?? null;
}

/** The trap's taps: a word on, or off again. */
export function toggle(picked: number[], index: number): number[] {
  return picked.includes(index) ? picked.filter((i) => i !== index) : [...picked, index].sort((a, b) => a - b);
}

/** A1's headline, as the server builds it: a subject tile, then a fact tile, no final stop. */
export function a1Headline(subject: string | null, fact: string | null): string {
  const clean = (text: string) => text.trim().replace(/[\s.]+$/, '');
  return subject && fact ? `${clean(subject)} ${clean(fact)}` : '';
}

export function wordCount(text: string): number {
  return (text.match(/[A-Za-zÀ-ÖØ-öø-ÿŒœ0-9]+(?:['’-][A-Za-zÀ-ÖØ-öø-ÿŒœ0-9]+)*/g) ?? []).length;
}

const fold = (text: string) =>
  text
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[’`]/g, "'");

/** The headline says the words that said too much: the client says so before sending. */
export function saysTooMuch(text: string, avoid: string): boolean {
  return Boolean(avoid) && fold(text).includes(fold(avoid));
}

/** A quote with the words that settle it lit (`wrong: true` marks them). */
export function settledSegments(quote: string, settles: string): QuoteSegment[] {
  return quoteSegments(quote, settles || null);
}

/** The tapped words the claims do say, by their French. */
export function fineWords(view: Pick<RvTitreView, 'trap'>): string {
  const trap = view.trap;
  if (!trap) return '';
  return trap.fine.map((index) => trap.words.find((word) => word.index === index)?.fr ?? '').filter(Boolean).join(', ');
}

/** «3 sur 5» in the chrome language. */
export function scoreText(copy: RubriqueCopy, view: Pick<RvIntoxView, 'round'>): string {
  const round = view.round;
  return fill(copy.score, { n: String(round?.score ?? 0), total: String(round?.total ?? 5) });
}

/** The last statement answered (its verdict is what a resume shows first), or null. */
export function lastAnswered(view: Pick<RvIntoxView, 'round'>): string | null {
  const answered = (view.round?.cards ?? []).filter((card) => card.answer);
  return answered.length ? answered[answered.length - 1].key : null;
}

/** The card to show in the round: the one just answered (`seen`), else the current one. */
export function shownCard(view: Pick<RvIntoxView, 'round'>, seen: string | null) {
  const round = view.round;
  if (!round) return null;
  if (seen) {
    const card = round.cards.find((row) => row.key === seen);
    if (card) return card;
  }
  return round.cards.find((row) => row.key === round.current) ?? round.cards[round.cards.length - 1] ?? null;
}

/** The refusals that explain (a reason, said in the mother tongue as the counter's whys);
 * the others are instructions (lengths, «tap a word»), said in the chrome language. */
const REASON_CODES = new Set(['says_too_much', 'number_not_in_claims', 'nothing_changed']);

/** The table a refusal is said from: `reasons` (the mother tongue) for a reason, else `chrome`. */
export function refusalCopy(code: string, chrome: RubriqueCopy, reasons: RubriqueCopy): RubriqueCopy {
  return REASON_CODES.has(code) ? reasons : chrome;
}

/** Why an act was not recorded, in the table it is given (`refusalCopy`). */
export function errorText(copy: RubriqueCopy, error: RvRubriqueError, avoid = ''): string {
  const template = copy.errors[error.code] ?? copy.errors.too_short;
  return fill(template, { n: String(error.count ?? ''), avoid });
}
