/**
 * «Le fil» · the player's pure model (node-tested): the shown step never ahead of the
 * server's, moving the strips without drag, the reasons said in the learner's language
 * (built from the strips' own names and the words' own glosses, never the solution), the
 * A1 sentence as the server will build it, the sequence words a free telling uses.
 */

import { fill } from '../revue-copy';
import type { RvFilConnector, RvFilError, RvFilMiss, RvFilStep, RvFilStrip, RvFilView } from '@/lib/revue-fil-types';
import type { RvLanguage } from '@/lib/revue-types';

import type { FilCopy } from './fil-copy';

const ORDER: RvFilStep[] = ['read', 'order', 'words', 'tell', 'page'];

export function stepOrder(step: RvFilStep): number {
  return ORDER.indexOf(step);
}

/** The screen a visit opens on: the server's step, «Raconter» until the close is asked for. */
export function openingStep(view: Pick<RvFilView, 'step'>, closed: boolean): RvFilStep {
  if (closed) return 'page';
  return view.step === 'page' ? 'tell' : view.step;
}

/** The shown step, never ahead of the server's. */
export function clampStep(view: Pick<RvFilView, 'step'>, shown: RvFilStep, closed: boolean): RvFilStep {
  const latest = openingStep(view, closed);
  return stepOrder(shown) > stepOrder(latest) ? latest : shown;
}

export function nextStep(shown: RvFilStep): RvFilStep | null {
  return ORDER[stepOrder(shown) + 1] ?? null;
}

/** The learner's arrangement with the strips at `a` and `b` swapped. */
export function swap(order: string[], a: number, b: number): string[] {
  if (a === b || a < 0 || b < 0 || a >= order.length || b >= order.length) return order;
  const next = [...order];
  [next[a], next[b]] = [next[b], next[a]];
  return next;
}

/** The strip at `index` one place up (`-1`) or down (`1`). */
export function move(order: string[], index: number, delta: -1 | 1): string[] {
  return swap(order, index, index + delta);
}

/** What the reason calls a strip: its name in the chrome language, else its first words in French. */
export function stripName(strip: Pick<RvFilStrip, 'label' | 'text'> | undefined, chrome: RvLanguage): string {
  if (!strip) return '';
  if (strip.label) {
    const name = chrome === 'fr' ? strip.label.fr : strip.label.tr || strip.label.fr;
    if (name) return name;
  }
  const words = strip.text.fr.split(/\s+/).slice(0, 5).join(' ').replace(/[.,;:!?…]+$/, '');
  return `« ${words}… »`;
}

function capital(text: string): string {
  return text ? text[0].toUpperCase() + text.slice(1) : text;
}

/** «The first session comes after the creation.»: one pair, never the order. */
export function orderHintText(copy: FilCopy, strips: RvFilStrip[], hint: { key: string; afterKey: string }, chrome: RvLanguage): string {
  const of = (key: string) => strips.find((strip) => strip.key === key);
  return capital(fill(copy.order_hint, { a: stripName(of(hint.key), chrome), b: stripName(of(hint.afterKey), chrome) }));
}

/** A misplaced sequence word: what it means (its gloss) and what the strip needs. */
export function missText(copy: FilCopy, miss: RvFilMiss): string {
  const vars = { word: miss.fr, gloss: miss.tr ?? '', role: copy.role[miss.role], needs: copy.needs[miss.needs] };
  return fill(miss.tr ? copy.miss : copy.miss_no_gloss, vars);
}

/** A1's two sentences, as the server builds them: «D'abord, … . Enfin, … .» */
export function a1Telling(first: RvFilConnector | null, firstTile: string | null, second: RvFilConnector | null, secondTile: string | null): string {
  const one = first && firstTile ? `${capital(first.fr)}, ${firstTile.replace(/[\s.!…]+$/, '')}.` : '';
  const two = second && secondTile ? `${capital(second.fr)}, ${secondTile.replace(/[\s.!…]+$/, '')}.` : '';
  return [one, two].filter(Boolean).join(' ');
}

const fold = (text: string) =>
  text
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[’`]/g, "'");

/** The distinct sequence words `text` uses («tout d'abord» once, not also «d'abord»). */
export function connectorsUsed(text: string, connectors: Pick<RvFilConnector, 'fr'>[]): string[] {
  const folded = ` ${fold(text)} `;
  const seen = connectors
    .map((connector) => fold(connector.fr))
    .filter((word, index, all) => all.indexOf(word) === index)
    .filter((word) => new RegExp(`(^|[^a-z'-])${word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}(?=$|[^a-z'-])`).test(folded));
  return seen.filter((word) => !seen.some((other) => other !== word && other.includes(word)));
}

export function wordCount(text: string): number {
  return (text.match(/[A-Za-zÀ-ÖØ-öø-ÿŒœ0-9]+(?:['’-][A-Za-zÀ-ÖØ-öø-ÿŒœ0-9]+)*/g) ?? []).length;
}

/** Why an act was not recorded, in the chrome language. */
export function errorText(copy: FilCopy, error: RvFilError, view: RvFilView): string {
  const template = copy.errors[error.code] ?? copy.errors.pick_all;
  const tiles = view.tell?.tiles ?? [];
  const tileName = (key: string | null) => {
    const tile = tiles.find((row) => row.key === key);
    return tile ? `« ${tile.text.fr} »` : '';
  };
  const word = [...(view.tell?.connectors ?? []), ...(view.words?.connectors ?? [])].find((row) => row.id === error.key)?.fr ?? '';
  return capital(fill(template, { a: tileName(error.key), b: tileName(error.afterKey), word, n: String(error.count ?? '') }));
}

/** The words placed (A1) or chosen (A2+) on every strip: «Vérifier» is enabled. */
export function allPicked(picks: Array<string | null>): picks is string[] {
  return picks.length === 4 && picks.every(Boolean);
}
