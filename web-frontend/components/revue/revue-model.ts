/**
 * WP-119 · Le Papier de Romy — the pure half of the components: how the thread
 * is shown (folds, the resume marker, the latest line), the column, the beat bar,
 * glosses and the learner's contribution as text segments, and how one turn's
 * result lands on the session. No React here; the node tests read it directly.
 */

import type {
  RvBeat,
  RvClaim,
  RvEvidence,
  RvGloss,
  RvOutcome,
  RvRoom,
  RvSessionView,
  RvSpan,
  RvStageMember,
  RvThreadItem,
  RvTurnResult,
} from '@/lib/revue-types';

import { fill, type RevueCopy } from './revue-copy';

// ---------------------------------------------------------------------------
// The thread as shown
// ---------------------------------------------------------------------------

/** Client-only rows the wire never sends (WIRE §2). */
export type RvDisplayItem =
  | { kind: 'item'; item: RvThreadItem; past: boolean }
  | { kind: 'claimsFolded'; id: string; claims: RvClaim[] }
  | { kind: 'resume'; id: string; label: string };

/** The day an ISO timestamp falls on, in the learner's clock (YYYY-MM-DD). */
export function localDay(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

export type DisplayOptions = {
  /** Folded claim groups the learner reopened. */
  opened?: ReadonlySet<string>;
  /** «Hier · tu reprends ici» before the first item of `today`, when older items exist. */
  resumeToday?: string | null;
  resumeLabel?: string;
};

/**
 * The thread → rows. Claims already on the table fold into one quiet line once
 * the learner has spoken after them (design §3.4); consecutive folded groups are
 * one line. Every Romy line but the latest is `past` (the small bubble).
 */
export function displayThread(items: RvThreadItem[], options: DisplayOptions = {}): RvDisplayItem[] {
  const opened = options.opened ?? new Set<string>();
  let lastMine = -1;
  let lastLine = -1;
  items.forEach((item, index) => {
    if (item.kind === 'mine') lastMine = index;
    // A guest's line is a line too: whoever spoke last is the screen's headline.
    if (item.kind === 'line' || item.kind === 'guest') lastLine = index;
  });
  let resumeAt = -1;
  if (options.resumeToday) {
    const first = items.findIndex((item) => localDay(item.at) === options.resumeToday);
    if (first > 0 && items.slice(0, first).some((item) => localDay(item.at) && localDay(item.at) < (options.resumeToday as string))) {
      resumeAt = first;
    }
  }
  const rows: RvDisplayItem[] = [];
  items.forEach((item, index) => {
    if (index === resumeAt) rows.push({ kind: 'resume', id: `resume-${item.id}`, label: options.resumeLabel ?? '' });
    if (item.kind === 'claims' && index < lastMine) {
      const previous = rows[rows.length - 1];
      if (previous && previous.kind === 'claimsFolded' && !opened.has(previous.id)) {
        previous.claims = previous.claims.concat(item.claims);
        return;
      }
      if (!opened.has(item.id)) {
        rows.push({ kind: 'claimsFolded', id: item.id, claims: item.claims.slice() });
        return;
      }
    }
    rows.push({ kind: 'item', item, past: item.kind === 'line' || item.kind === 'guest' ? index !== lastLine : false });
  });
  return rows;
}

/** «2 faits sur la table · d'après Ville de Paris, Wikipédia». */
export function foldedLabel(claims: RvClaim[], copy: RevueCopy): string {
  const names: string[] = [];
  for (const claim of claims) {
    const name = claim.source.name.replace(/\s*\(.*\)$/, '').replace(/,\s*«.*»$/, '').trim();
    if (name && !names.includes(name)) names.push(name);
  }
  const template = claims.length === 1 ? copy.facts_on_table_one : copy.facts_on_table;
  return fill(template, { n: claims.length, sources: names.join(', ') });
}

// ---------------------------------------------------------------------------
// One turn lands on the session
// ---------------------------------------------------------------------------

/** The session after a turn: new items appended (deduped by id), the rest replaced. */
export function applyTurn(view: RvSessionView, result: RvTurnResult): RvSessionView {
  const seen = new Set(view.thread.map((item) => item.id));
  const fresh = result.items.filter((item) => !seen.has(item.id));
  return {
    ...view,
    thread: view.thread.concat(fresh),
    beat: result.beat,
    room: result.room,
    plan: { ...view.plan, support: result.support },
    quickReplies: result.quickReplies,
    steerToMake: result.steerToMake,
  };
}

/** Items appended locally (a filed artefact) without a turn. */
export function appendItems(view: RvSessionView, items: RvThreadItem[]): RvSessionView {
  const seen = new Set(view.thread.map((item) => item.id));
  return { ...view, thread: view.thread.concat(items.filter((item) => !seen.has(item.id))) };
}

/** The learner's open question, as the thread shows it: their last line before an uncertainty. */
export function openQuestion(items: RvThreadItem[]): string | null {
  for (let index = items.length - 1; index >= 0; index -= 1) {
    if (items[index].kind !== 'uncertainty') continue;
    for (let back = index - 1; back >= 0; back -= 1) {
      const item = items[back];
      if (item.kind === 'mine') return item.textFr;
    }
  }
  return null;
}

// ---------------------------------------------------------------------------
// The beat bar and the column
// ---------------------------------------------------------------------------

export const BEATS: RvBeat[] = ['arrive', 'facts', 'pursue', 'make', 'close'];

export type BeatSegment = { beat: RvBeat; state: 'done' | 'active' | 'pending' };

/** Five segments; `null` (the choose state) is all pending, `ended` all done. */
export function beatSegments(beat: RvBeat | null, ended = false): BeatSegment[] {
  const at = beat ? BEATS.indexOf(beat) : -1;
  return BEATS.map((name, index) => ({
    beat: name,
    state: ended ? 'done' : index < at ? 'done' : index === at ? 'active' : 'pending',
  }));
}

/** «environ quatre échanges» — a word, never «6/7» (design §3.8). */
export function roomSentence(room: RvRoom, copy: RevueCopy): string {
  if (room.remainingTurns <= 0 || room.phase === 'boucle') return copy.column_full;
  const n = copy.numbers[room.remainingTurns] ?? String(room.remainingTurns);
  return fill(copy.column_room, { n });
}

export type ColumnModel = {
  lines: Array<{ used: boolean; last: boolean }>;
  word: string | null;
  srLabel: string;
};

export function columnModel(room: RvRoom, copy: RevueCopy): ColumnModel {
  const used = Math.max(0, Math.min(7, room.used));
  const lines = Array.from({ length: 7 }, (_, index) => ({ used: index < used, last: used > 0 && index === used - 1 }));
  const word = room.phase === 'bouclage' ? copy.column_bouclage : room.phase === 'boucle' ? copy.column_boucle : null;
  return { lines, word, srLabel: `${copy.column_label} : ${roomSentence(room, copy)}` };
}

// ---------------------------------------------------------------------------
// Glosses and contribution as segments
// ---------------------------------------------------------------------------

export type GlossSegment =
  | { kind: 'text'; text: string }
  | { kind: 'gloss'; text: string; gloss: string }
  | { kind: 'word'; text: string; gloss: string | null };

function foldText(text: string): string {
  return text.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[’‘]/g, "'");
}

/** Where each gloss's French occurs in `text` (accent- and case-insensitive, whole words). */
function glossHits(text: string, glosses: RvGloss[]): Array<{ start: number; end: number; gloss: RvGloss }> {
  const folded = foldText(text);
  const hits: Array<{ start: number; end: number; gloss: RvGloss }> = [];
  for (const gloss of glosses) {
    const needle = foldText(gloss.fr.trim());
    if (!needle) continue;
    let from = 0;
    while (from <= folded.length) {
      const at = folded.indexOf(needle, from);
      if (at < 0) break;
      const before = at === 0 ? '' : folded.charAt(at - 1);
      const after = folded.charAt(at + needle.length);
      const boundary = (ch: string) => !ch || !/[a-z0-9]/.test(ch);
      if (boundary(before) && boundary(after) && !hits.some((hit) => at < hit.end && at + needle.length > hit.start)) {
        hits.push({ start: at, end: at + needle.length, gloss });
      }
      from = at + needle.length;
    }
  }
  return hits.sort((a, b) => a.start - b.start);
}

const WORD = /[A-Za-zÀ-ÖØ-öø-ÿœŒæÆ]+(?:[-'’][A-Za-zÀ-ÖØ-öø-ÿœŒæÆ]+)*/g;

/**
 * `shown`: the gloss printed under the first occurrence of each target word
 * (ruby), the rest plain. `tap`: every word is a tap-to-gloss control, the
 * target words carrying their gloss for the word sheet. `none`: plain text.
 */
export function glossSegments(text: string, glosses: RvGloss[], mode: 'shown' | 'tap' | 'none'): GlossSegment[] {
  if (!text) return [];
  if (mode === 'none') return [{ kind: 'text', text }];
  const hits = glossHits(text, glosses);
  const out: GlossSegment[] = [];
  const pushText = (chunk: string) => {
    if (!chunk) return;
    if (mode === 'shown') {
      const last = out[out.length - 1];
      if (last && last.kind === 'text') last.text += chunk;
      else out.push({ kind: 'text', text: chunk });
      return;
    }
    let cursor = 0;
    chunk.replace(WORD, (word, offset: number) => {
      if (offset > cursor) out.push({ kind: 'text', text: chunk.slice(cursor, offset) });
      out.push({ kind: 'word', text: word, gloss: null });
      cursor = offset + word.length;
      return word;
    });
    if (cursor < chunk.length) out.push({ kind: 'text', text: chunk.slice(cursor) });
  };
  const used = new Set<string>();
  let cursor = 0;
  for (const hit of hits) {
    pushText(text.slice(cursor, hit.start));
    const surface = text.slice(hit.start, hit.end);
    if (mode === 'shown') {
      if (used.has(hit.gloss.fr)) pushText(surface);
      else out.push({ kind: 'gloss', text: surface, gloss: hit.gloss.gloss });
      used.add(hit.gloss.fr);
    } else {
      out.push({ kind: 'word', text: surface, gloss: hit.gloss.gloss });
    }
    cursor = hit.end;
  }
  pushText(text.slice(cursor));
  return out;
}

export type ContributionSegment = { text: string; mine: boolean };

/** `text` cut at the contribution spans (clamped, sorted, overlaps merged). */
export function contributionSegments(text: string, spans: RvSpan[]): ContributionSegment[] {
  const clean = spans
    .map(([start, end]) => [Math.max(0, Math.min(text.length, start)), Math.max(0, Math.min(text.length, end))] as RvSpan)
    .filter(([start, end]) => end > start)
    .sort((a, b) => a[0] - b[0]);
  const merged: RvSpan[] = [];
  for (const span of clean) {
    const last = merged[merged.length - 1];
    if (last && span[0] <= last[1]) last[1] = Math.max(last[1], span[1]);
    else merged.push([span[0], span[1]]);
  }
  const out: ContributionSegment[] = [];
  let cursor = 0;
  for (const [start, end] of merged) {
    if (start > cursor) out.push({ text: text.slice(cursor, start), mine: false });
    out.push({ text: text.slice(start, end), mine: true });
    cursor = end;
  }
  if (cursor < text.length) out.push({ text: text.slice(cursor), mine: false });
  return out;
}

// ---------------------------------------------------------------------------
// Dates, the La Une card
// ---------------------------------------------------------------------------

const MONTHS_FR = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.'];

/** «29 sept.» this year, «25 mai 2018» otherwise — a source's own date, never «cette semaine». */
export function sourceDate(iso: string, now: Date = new Date()): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || '');
  if (!match) return '';
  const [, year, month, day] = match;
  const base = `${Number(day)} ${MONTHS_FR[Number(month) - 1] ?? ''}`.trim();
  return Number(year) === now.getFullYear() ? base : `${base} ${year}`;
}

/** «Commencée hier» / «Started yesterday», from the session's start. */
export function startedWhen(startedAt: string, copy: RevueCopy, now: Date = new Date()): string {
  const day = localDay(startedAt);
  if (!day) return copy.started_today;
  const today = localDay(now.toISOString());
  const yesterday = localDay(new Date(now.getTime() - 86400000).toISOString());
  if (day === today) return copy.started_today;
  if (day === yesterday) return copy.started_yesterday;
  return fill(copy.started_on, { date: sourceDate(day, now) });
}

export function wordCount(text: string): number {
  return text.split(/\s+/).filter((token) => /[A-Za-zÀ-ÖØ-öø-ÿœŒ0-9]/.test(token)).length;
}

/** What La Une's Revue card prints besides its title, kicker and controls. */
export type UneCardParts = { showWeek: boolean; showPlace: boolean; showTopic: boolean };

/**
 * WP-81's 25 words on Home: the masthead takes up to 7 (date + streak), so the
 * card has 18. Title, kicker and the controls always print; the place goes
 * first, then the week label, then the topic, until the card fits.
 */
export function uneCardParts(
  parts: { title: string; kicker: string; week: string; place: string; topic: string; fixed: string[] },
  budget = 18,
): UneCardParts {
  const base = wordCount(parts.title) + wordCount(parts.kicker) + parts.fixed.reduce((sum, text) => sum + wordCount(text), 0);
  const show: UneCardParts = { showWeek: true, showPlace: true, showTopic: true };
  const total = () =>
    base + (show.showWeek ? wordCount(parts.week) : 0) + (show.showPlace ? wordCount(parts.place) : 0) + (show.showTopic ? wordCount(parts.topic) : 0);
  for (const drop of ['showPlace', 'showWeek', 'showTopic'] as const) {
    if (total() <= budget) break;
    show[drop] = false;
  }
  return show;
}

/** The week number of an ISO week («2026-W40» → 40). */
export function weekNumber(iso: string): string {
  const match = /W(\d{1,2})$/.exec(iso || '');
  return match ? String(Number(match[1])) : '';
}

// ---------------------------------------------------------------------------
// Phase 2 · the guest on stage, fallback notices, the rubric's words
// ---------------------------------------------------------------------------

const ROMY = 'romy_tremblay';

/**
 * The stage's cast with every guest who has spoken: a guest stands right after
 * Romy (WIRE §6.2, «the stage lists the guest beside Romy from their entrance
 * on»). The session view already lists them on resume; a turn result carries no
 * stage, so the guest a turn brings is added here from the thread.
 */
export function castWithGuests(cast: RvStageMember[], thread: RvThreadItem[]): RvStageMember[] {
  const out = cast.slice();
  const present = new Set(out.map((member) => member.id));
  for (const item of thread) {
    if (item.kind !== 'guest' || !item.castId || present.has(item.castId)) continue;
    present.add(item.castId);
    const romyAt = out.findIndex((member) => member.id === ROMY);
    // After Romy and any guest already standing beside her, before Toi.
    let at = romyAt + 1;
    while (at < out.length && out[at].id !== 'user' && out[at].id !== ROMY) at += 1;
    out.splice(romyAt >= 0 ? at : out.length, 0, { id: item.castId, hold: null });
  }
  return out;
}

/** Who spoke last (Romy or a guest): the one in front on the stage. */
export function lastSpeaker(thread: RvThreadItem[]): string {
  for (let index = thread.length - 1; index >= 0; index -= 1) {
    const item = thread[index];
    if (item.kind === 'guest') return item.castId;
    if (item.kind === 'line' || item.kind === 'summary') return item.speaker || ROMY;
  }
  return ROMY;
}

/** The guest a batch of new items brings on stage (`move: enter`), or null. */
export function enteringGuest(items: RvThreadItem[]): string | null {
  const enter = items.find((item) => item.kind === 'guest' && item.move === 'enter');
  return enter && enter.kind === 'guest' ? enter.castId : null;
}

/**
 * The items that carry the quiet «la conversation ne répond pas» notice: a line
 * (Romy's or a guest's) whose authored text stands in because the model is down
 * (`reason: model_down`) — once per learner turn, on the first such line.
 */
export function modelDownNotices(items: RvThreadItem[]): Set<string> {
  const out = new Set<string>();
  let turn = '';
  let noticed = '';
  for (const item of items) {
    if (item.kind === 'mine') turn = item.id;
    if ((item.kind === 'line' || item.kind === 'guest') && item.reason === 'model_down' && noticed !== `t:${turn}`) {
      out.add(item.id);
      noticed = `t:${turn}`;
    }
  }
  return out;
}

/** The column as the head shows it: a `budget` line means the column is full, whatever the room says. */
export function shownRoom(room: RvRoom, thread: RvThreadItem[]): RvRoom {
  const last = [...thread].reverse().find((item) => item.kind === 'line');
  if (last && last.kind === 'line' && last.reason === 'budget' && room.phase !== 'boucle') {
    return { ...room, phase: 'boucle', used: 7, remainingTurns: 0 };
  }
  return room;
}

export type WordOutcomes = Record<string, RvOutcome>;

const OUTCOME_RANK: Record<RvOutcome, number> = { unscored: 0, incorrect: 1, correct: 2 };

/**
 * The words' outcomes across the session's evidence: a word used correctly once
 * stays correct (the rubric's credit, WIRE §6.3). A correct use the can-do
 * catalogue does not know is already sent as `unscored`, so it never counts here.
 */
export function mergeWordOutcomes(current: WordOutcomes, evidence: Pick<RvEvidence, 'words'> | null | undefined): WordOutcomes {
  if (!evidence || !evidence.words.length) return current;
  const next: WordOutcomes = { ...current };
  for (const word of evidence.words) {
    const key = foldText(word.fr.trim());
    if (!key) continue;
    const before = next[key];
    if (!before || OUTCOME_RANK[word.outcome] > OUTCOME_RANK[before]) next[key] = word.outcome;
  }
  return next;
}

export function wordOutcome(outcomes: WordOutcomes, fr: string): RvOutcome | null {
  return outcomes[foldText(fr.trim())] ?? null;
}

/** «{n} mots sur {max} au plus»: the words of a written headline. */
export function headlineWords(text: string): number {
  return wordCount(text);
}
