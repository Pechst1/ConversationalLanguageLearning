/**
 * Le Quartier · today's Papier on the Morris column (`REVUE_QUARTIER_AFFICHE_ENABLED`).
 *
 * One of the column's four poster slots carries today's edition: the masthead «Le Papier», the
 * date, the day's headline in our French (the server's `offer.affiche`), and a «lu» stamp once
 * today's Papier is filed. It is printed like the Papier's own front page (`styles/revue-papier.css`):
 * the house serif italic for the masthead and the headline, a thick rule over a hairline under the
 * masthead, the tracked sans capitals of the dateline, red only as the kicker's ink and the stamp's.
 * A tap on it (or «Lire» on the card that shows when you stand by the column) opens the Papier.
 *
 * The model is pure, and the page reads it without the engine (tested in `affiche.test.js`);
 * `affiche-art.ts` draws it on the street's atlas.
 */
import type { Words } from './memory';

/** The spot the poster hangs on: a tap on it opens `route`. */
export const AFFICHE_SPOT = 'affiche:papier';

/** The longest line the headline is set in, in characters, and how many lines it may take. */
export const HEADLINE_LINE_CHARS = 15;
export const HEADLINE_MAX_LINES = 6;

export interface Affiche {
  /** «dimanche 22 novembre» */
  date: string;
  /** the headline, in our French */
  headline: string;
  /** the headline set in lines at the default measure (the print sets it at the measure that reads largest) */
  lines: string[];
  /** today's Papier is filed: the «lu» stamp */
  done: boolean;
  /** where a tap takes you: the Papier, resumed when one is in progress */
  route: string;
}

/** What an object that opens an app route says on its card (French, and the learner's language). */
export interface Opens {
  route: string;
  label: Words;
}

const DAYS = ['dimanche', 'lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi'];
const MONTHS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre'];

/** «dimanche 22 novembre», «samedi 1er novembre». */
export function frenchDate(day: Date): string {
  const n = day.getDate();
  return `${DAYS[day.getDay()]} ${n === 1 ? '1er' : n} ${MONTHS[day.getMonth()]}`;
}

/**
 * The headline's units: words of one or two letters («à», «de», «l’») stay with the word after
 * them, as a typesetter keeps them, and a lone mark («:», «?») with the word before it.
 */
function words(text: string): string[] {
  const raw = text.replace(/\s+/g, ' ').trim().split(' ').filter(Boolean);
  const out: string[] = [];
  let carry = '';
  raw.forEach((w, i) => {
    if (!/[A-Za-zÀ-ÿ0-9]/.test(w) && out.length && !carry) {
      out[out.length - 1] += `\u00a0${w}`;
      return;
    }
    const word = carry ? `${carry}\u00a0${w}` : w;
    carry = '';
    if (w.replace(/[’']$/, '').length <= 2 && /^[A-Za-zÀ-ÿ]/.test(w) && i < raw.length - 1) carry = word;
    else out.push(word);
  });
  if (carry) out.push(carry);
  return out;
}

function greedy(items: string[], width: number): string[] {
  const lines: string[] = [];
  let line = '';
  for (const w of items) {
    const next = line ? `${line} ${w}` : w;
    if (line && next.length > width) {
      lines.push(line);
      line = w;
    } else line = next;
  }
  if (line) lines.push(line);
  return lines;
}

/** `items` broken into exactly `count` lines of at most `width`, the lines as even as they can be. */
function balanced(items: string[], width: number, count: number): string[] | null {
  const n = items.length;
  const len = (i: number, j: number) => items.slice(i, j).join(' ').length;
  // best[k][j]: the least cost of setting items[0..j) in k lines
  const best: number[][] = Array.from({ length: count + 1 }, () => new Array(n + 1).fill(Infinity));
  const from: number[][] = Array.from({ length: count + 1 }, () => new Array(n + 1).fill(-1));
  best[0][0] = 0;
  for (let k = 1; k <= count; k++) {
    for (let j = 1; j <= n; j++) {
      for (let i = j - 1; i >= 0; i--) {
        const l = len(i, j);
        if (l > width) break;
        const cost = best[k - 1][i] + (width - l) ** 2;
        if (cost < best[k][j]) {
          best[k][j] = cost;
          from[k][j] = i;
        }
      }
    }
  }
  if (!Number.isFinite(best[count][n])) return null;
  const lines: string[] = [];
  for (let k = count, j = n; k > 0; k--) {
    const i = from[k][j];
    lines.unshift(items.slice(i, j).join(' '));
    j = i;
  }
  return lines;
}

/**
 * The headline set in lines of at most `width` characters (a longer word stands alone), as few as
 * fit and as even as they can be, at most `maxLines`: past them the last line ends on «…».
 */
export function wrapHeadline(text: string, width = HEADLINE_LINE_CHARS, maxLines = HEADLINE_MAX_LINES): string[] {
  const items = words(text);
  if (!items.length) return [];
  const measure = Math.max(width, ...items.map((w) => w.length));
  const lines = greedy(items, measure);
  const plain = (l: string) => l.replace(/\u00a0/g, ' ');
  if (lines.length > maxLines) {
    const kept = lines.slice(0, maxLines);
    kept[maxLines - 1] = `${kept[maxLines - 1].replace(/[\s\u00a0,;:.]+$/, '')}…`;
    return kept.map(plain);
  }
  return (balanced(items, measure, lines.length) ?? lines).map(plain);
}

/** The poster's card on the street: what it is, and the route it opens. */
export function afficheOpens(affiche: Affiche): Opens {
  return {
    route: affiche.route,
    label: affiche.done
      ? { fr: 'Le Papier du jour · lu', en: 'Today’s Papier · read', de: 'Der Papier von heute · gelesen' }
      : { fr: 'Le Papier du jour', en: 'Today’s Papier', de: 'Der Papier von heute' },
  };
}

/** The route a tap opens: a spot that opens one, while you are free to walk; else `null`. */
export function routeOfHit(hit: { kind: string; opens?: string } | null | undefined, free: boolean): string | null {
  if (!free || !hit || hit.kind !== 'spot') return null;
  return typeof hit.opens === 'string' && hit.opens ? hit.opens : null;
}

/** The nearest spot that opens a route within `reach` metres of your feet (its card shows), else `null`. */
export function openingNear<T extends { pos: { x: number; z: number }; enabled: boolean; opens?: Opens }>(
  spots: readonly T[],
  feet: { x: number; z: number },
  reach: number,
): T | null {
  let best: T | null = null;
  let bestD = reach;
  for (const s of spots) {
    if (!s.enabled || !s.opens) continue;
    const d = Math.hypot(s.pos.x - feet.x, s.pos.z - feet.z);
    if (d <= bestD) {
      best = s;
      bestD = d;
    }
  }
  return best;
}

