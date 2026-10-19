/**
 * «Au comptoir» (WP-119-AU-COMPTOIR §5) · the player's pure parts, node-tested
 * (comptoir.test.js): which screen shows and when the learner may go on, the
 * step dots, the takes revealed one at a time, the A1 sentence built from tiles,
 * the word diff that marks Romy's red pen, the vote tally, the liar's quote with
 * its wrong part struck.
 *
 * The server owns the state (`RvComptoirView.step`); the client only holds a
 * finished screen on screen until its one main button is pressed: a vote moves
 * the server to `takes`, but «Lire» stays until «Au comptoir →». The shown step
 * is never ahead of the server's.
 */

import type { RvComptoirCast, RvComptoirStep, RvComptoirView, RvComptoirVotes, RvStance } from '@/lib/revue-types';

const ORDER: RvComptoirStep[] = ['read', 'takes', 'intox', 'opinion', 'page'];

/** The steps' names, French in every chrome (the publication's words, like «Bouclage»). */
export const STEP_LABELS_FR: Record<RvComptoirStep, string> = {
  read: 'Lire',
  takes: 'Les avis',
  intox: "L'intox",
  opinion: 'Ton avis',
  page: 'La page',
};

/** The stance tags, printed as the page prints them (French in every chrome). */
export const STANCE_TAGS_FR: Record<RvStance, string> = { pour: 'POUR', contre: 'CONTRE', nuance: 'ÇA DÉPEND' };
/** The side chips of «Ton avis», the learner's own French. */
export const SIDE_LABELS_FR: Record<RvStance, string> = { pour: 'Pour', contre: 'Contre', nuance: 'Ça dépend' };
/** The gut vote of «Lire»: «Oui !» (pour), «Non.» (contre), «Bof…» (nuance). */
export const GUT_VOTES_FR: Array<{ value: RvStance; fr: string }> = [
  { value: 'pour', fr: 'Oui !' },
  { value: 'contre', fr: 'Non.' },
  { value: 'nuance', fr: 'Bof…' },
];
/** The reactions under each take, the learner's own French. */
export const REACTIONS_FR: Array<{ value: 'agree' | 'disagree'; fr: string }> = [
  { value: 'agree', fr: "d'accord" },
  { value: 'disagree', fr: "pas d'accord" },
];

/** Every regular argues at Le Mistral's counter: the band over «Les avis». */
export const COUNTER_PLATE = '/assets/serial/locations/le_mistral-counter.webp';

export function stepOrder(step: RvComptoirStep): number {
  return ORDER.indexOf(step);
}

/**
 * The screen a visit opens on: the server's step, except «La page» before the
 * close was asked for — the opinion screen holds «Voir la page», which closes.
 */
export function openingStep(view: Pick<RvComptoirView, 'step'>, closed: boolean): RvComptoirStep {
  if (closed) return 'page';
  return view.step === 'page' ? 'opinion' : view.step;
}

/** The shown step, never ahead of the server's (a refused act re-renders from the view). */
export function clampStep(view: Pick<RvComptoirView, 'step'>, shown: RvComptoirStep, closed: boolean): RvComptoirStep {
  const latest = openingStep(view, closed);
  return stepOrder(shown) > stepOrder(latest) ? latest : shown;
}

/** The screen's one required act is done: its main button is enabled. */
export function stepDone(view: RvComptoirView, shown: RvComptoirStep): boolean {
  switch (shown) {
    case 'read':
      return view.vote !== null;
    case 'takes':
      return view.cast.length > 0 && view.cast.every((member) => member.reaction !== null);
    case 'intox':
      return Boolean(view.intox?.fix);
    case 'opinion':
      return Boolean(view.opinion?.comeback);
    default:
      return true;
  }
}

/** The screen after `shown` in this session's dots (four when the band has no intox). */
export function nextStep(view: Pick<RvComptoirView, 'steps'>, shown: RvComptoirStep): RvComptoirStep | null {
  const at = view.steps.indexOf(shown);
  return at >= 0 ? view.steps[at + 1] ?? null : null;
}

export type StepDot = { step: RvComptoirStep; state: 'done' | 'active' | 'pending' };

export function stepDots(steps: RvComptoirStep[], shown: RvComptoirStep, closed: boolean): StepDot[] {
  const at = steps.indexOf(shown);
  return steps.map((step, index) => ({
    step,
    state: closed && shown === 'page' ? 'done' : index < at ? 'done' : index === at ? 'active' : 'pending',
  }));
}

/** «Les avis»: the first take shows at once; each reaction (in seat order) reveals the next. */
export function revealedTakes(cast: Pick<RvComptoirCast, 'reaction'>[]): number {
  let shown = 1;
  for (const member of cast) {
    if (!member.reaction) break;
    shown += 1;
  }
  return Math.min(cast.length, shown);
}

// ---------------------------------------------------------------------------
// «Ton avis»
// ---------------------------------------------------------------------------

/** A1's openers, as the server builds them (comptoir_loop.A1_OPENERS). */
export const A1_OPENERS: Record<RvStance, string> = { pour: 'Je suis pour', contre: 'Je suis contre', nuance: 'Ça dépend' };

/** «parce que» + the reason, elided before a vowel («parce qu'il»), as the server does. */
export function parceQue(reason: string): string {
  const body = reason.trim();
  return /^[aeiouyàâäéèêëîïôöûü]/i.test(body) ? `parce qu'${body}` : `parce que ${body}`;
}

/** A1's sentence from the tiles, correct by construction: «Je suis pour, parce que sa voix est belle.» */
export function a1Sentence(stance: RvStance, reason: string | null): string {
  const opener = A1_OPENERS[stance];
  const body = (reason ?? '').trim().replace(/[\s.!…]+$/, '');
  return body ? `${opener}, ${parceQue(body)}.` : `${opener}, parce que…`;
}

/** A word from the bank, added where the learner's reason ends. */
export function insertWord(text: string, word: string): string {
  const head = text.replace(/\s+$/, '');
  return head ? `${head} ${word}` : word;
}

/** The text the learner still has to fill in a B1 prefill («C'est …, pas …»). */
export function hasBlank(text: string): boolean {
  return text.includes('…');
}

// ---------------------------------------------------------------------------
// Romy's red pen: the words she changed
// ---------------------------------------------------------------------------

export type DiffSegment = { text: string; changed: boolean };

const WORD = /[A-Za-zÀ-ÖØ-öø-ÿŒœ0-9]+(?:['’-][A-Za-zÀ-ÖØ-öø-ÿŒœ0-9]+)*/g;

type Token = { text: string; word: boolean };

function tokens(text: string): Token[] {
  const out: Token[] = [];
  let last = 0;
  text.replace(WORD, (match, offset: number) => {
    if (offset > last) out.push({ text: text.slice(last, offset), word: false });
    out.push({ text: match, word: true });
    last = offset + match.length;
    return match;
  });
  if (last < text.length) out.push({ text: text.slice(last), word: false });
  return out;
}

const fold = (word: string) =>
  word
    .normalize('NFC')
    .replace(/’/g, "'")
    .toLowerCase();

/**
 * `after` (Romy's edit) cut into runs, the words that are not in `before` (the
 * learner's sentence) marked: «sa voix est très beau» → «… très **belle**». A
 * longest common subsequence over the words, case-folded; punctuation is never
 * marked. Adjacent changed words (and the spaces between them) make one run.
 */
export function wordDiff(before: string, after: string): DiffSegment[] {
  const a = tokens(before).filter((token) => token.word).map((token) => fold(token.text));
  const bTokens = tokens(after);
  const b = bTokens.filter((token) => token.word).map((token) => fold(token.text));
  // LCS table (the sentences are a line or two: a quadratic table is fine).
  const rows = a.length + 1;
  const cols = b.length + 1;
  const table: number[] = new Array(rows * cols).fill(0);
  for (let i = a.length - 1; i >= 0; i -= 1) {
    for (let j = b.length - 1; j >= 0; j -= 1) {
      table[i * cols + j] = a[i] === b[j] ? table[(i + 1) * cols + j + 1] + 1 : Math.max(table[(i + 1) * cols + j], table[i * cols + j + 1]);
    }
  }
  const kept = new Set<number>();
  let i = 0;
  let j = 0;
  while (i < a.length && j < b.length) {
    if (a[i] === b[j]) {
      kept.add(j);
      i += 1;
      j += 1;
    } else if (table[(i + 1) * cols + j] >= table[i * cols + j + 1]) {
      i += 1;
    } else {
      j += 1;
    }
  }
  const out: DiffSegment[] = [];
  const push = (text: string, changed: boolean) => {
    const previous = out[out.length - 1];
    if (previous && previous.changed === changed) previous.text += text;
    else out.push({ text, changed });
  };
  let wordIndex = 0;
  bTokens.forEach((token, index) => {
    if (token.word) {
      push(token.text, !kept.has(wordIndex));
      wordIndex += 1;
      return;
    }
    // A space between two changed words joins their run; anything else is plain.
    const previous = out[out.length - 1];
    const nextWord = bTokens.slice(index + 1).find((t) => t.word);
    const joins = previous?.changed && /^\s+$/.test(token.text) && nextWord !== undefined && !kept.has(wordIndex);
    push(token.text, Boolean(joins));
  });
  return out;
}

/** Romy changed something (the label says «corrigé», else «relu»). */
export function edited(before: string, after: string): boolean {
  return wordDiff(before, after).some((segment) => segment.changed);
}

// ---------------------------------------------------------------------------
// «La page»
// ---------------------------------------------------------------------------

export type TallyRow = { stance: RvStance; count: number; share: number };

/** The vote bar, in the page's order: pour, ça dépend, contre (empty sides kept, at zero). */
export function voteTally(votes: RvComptoirVotes): TallyRow[] {
  const order: RvStance[] = ['pour', 'nuance', 'contre'];
  const total = order.reduce((sum, stance) => sum + Math.max(0, votes[stance] || 0), 0);
  return order.map((stance) => {
    const count = Math.max(0, votes[stance] || 0);
    return { stance, count, share: total ? count / total : 0 };
  });
}

/** The tally the page will print, from the view: the three regulars and the learner. */
export function viewVotes(view: Pick<RvComptoirView, 'cast' | 'opinion' | 'vote'>): RvComptoirVotes {
  const votes: RvComptoirVotes = { pour: 0, contre: 0, nuance: 0 };
  for (const member of view.cast) votes[member.stance] += 1;
  const mine = view.opinion?.stance ?? view.vote;
  if (mine) votes[mine] += 1;
  return votes;
}

export type QuoteSegment = { text: string; wrong: boolean };

/** The liar's compact quote with the false part marked (struck once the intox is resolved). */
export function quoteSegments(quote: string, wrong: string | null): QuoteSegment[] {
  if (!wrong) return [{ text: quote, wrong: false }];
  const at = fold(quote).indexOf(fold(wrong));
  if (at < 0) return [{ text: quote, wrong: false }];
  return [
    { text: quote.slice(0, at), wrong: false },
    { text: quote.slice(at, at + wrong.length), wrong: true },
    { text: quote.slice(at + wrong.length), wrong: false },
  ].filter((segment) => segment.text);
}

/** The name a regular goes by at the counter («Gus»), from the view's cast. */
export function castName(view: Pick<RvComptoirView, 'cast'>, castId: string): string {
  return view.cast.find((member) => member.id === castId)?.nameFr ?? castId.split('_')[0];
}
