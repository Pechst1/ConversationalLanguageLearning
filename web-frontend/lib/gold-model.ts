/* Package O-2 — l'or on screen: the pure part (docs/ATELIER_GOLD_ECONOMY_PLAN.md §3, §11, §16).

   Everything here reads `GET /api/v1/gold` and decides what the counter, the
   grain, the ×2 and the day's seal show. No fetching and no React, so the
   node tests read it as it is. */

import { chromeDate } from './chrome-locale';
import type { ControlLanguage } from '@/types/daily-journey';
import type { components } from '@/types/generated/api';

export type GoldView = components['schemas']['GoldView'];
export type GoldEntry = components['schemas']['GoldEntry'];
export type GoldLedgerWeek = components['schemas']['GoldLedgerWeek'];

/** One paying answer's moment: the square lifts into the pill (le grain). */
export interface GoldGrain {
  /** Increases with each grain, so the same amount twice still replays. */
  id: number;
  /** Settled and pending gold the new entries brought. */
  amount: number;
  /** R4 paid: the square splits in two, «Tu t'en souvenais.» */
  delayed: boolean;
  /** Only pending gold (a dashed square, à l'épreuve). */
  pending: boolean;
}

export const JOURNEES_PLEINES_GOAL = 5;

/* #694 — every line l'or prints is chrome: it explains a number, so it reads in
   the learner's chrome language (the plan's §3 names the unit in each: «feuille
   d'or», «gold leaf», «Blattgold»). The functions below take the language; none
   of them holds a sentence of its own. */
export type GoldCopy = {
  /** «Or +29 aujourd’hui · 19 / 20 feuilles vers la journée pleine»: what the day earned, toward what. */
  toward: (n: { settled: number; earned: number; mark: number }) => string;
  /** «Or +48 aujourd’hui · Journée pleine (4 / 5 cette semaine)». */
  full: (n: { settled: number; days: number; goal: number }) => string;
  /** The ×2 of a delayed recall. */
  remembered: string;
  sheet_title: string;
  /** «Ton livret · 40 feuilles d’or». */
  sheet_eyebrow: (balance: number) => string;
  /** The pill's accessible name. */
  pill_label: (balance: number) => string;
  /** What the live region says when a grain lands. */
  grain_said: (amount: number) => string;
  today: string;
  day_full: string;
  day_toward: (n: { earned: number; mark: number }) => string;
  week: (n: { days: number; goal: number }) => string;
  plafond_closed: string;
  plafond_half: string;
  pending: (n: number) => string;
  void_not_yet: string;
  void_already_paid: string;
  void_withdrawn: string;
  void_pulped: string;
  sheet_failed: string;
  sheet_empty: string;
  week_before: string;
  this_week: string;
};

const GOLD_COPY: Record<ControlLanguage, GoldCopy> = {
  en: {
    toward: ({ settled, earned, mark }) => `Gold +${settled} today · ${earned} of ${mark} leaves toward a full day`,
    full: ({ settled, days, goal }) => `Gold +${settled} today · Full day (${days} of ${goal} this week)`,
    remembered: 'You remembered it.',
    sheet_title: 'Where your gold comes from',
    sheet_eyebrow: (balance) => `Your booklet · ${balance} gold ${balance === 1 ? 'leaf' : 'leaves'}`,
    pill_label: (balance) => `${balance} gold ${balance === 1 ? 'leaf' : 'leaves'}. Where your gold comes from`,
    grain_said: (amount) => `+${amount} gold ${amount === 1 ? 'leaf' : 'leaves'}`,
    today: 'Today',
    day_full: 'full day',
    day_toward: ({ earned, mark }) => `${earned} of ${mark} leaves toward a full day`,
    week: ({ days, goal }) => `${days} of ${goal} full days this week`,
    plafond_closed: 'Today’s ceiling reached',
    plafond_half: 'Ceiling: half rate',
    pending: (n) => `${n} still being checked`,
    void_not_yet: 'not yet',
    void_already_paid: 'already paid today',
    void_withdrawn: 'withdrawn',
    void_pulped: 'pulped',
    sheet_failed: 'The booklet won’t open right now.',
    sheet_empty: 'Nothing this week. Every right answer leaves a leaf here.',
    week_before: 'Week before',
    this_week: 'This week',
  },
  de: {
    toward: ({ settled, earned, mark }) => `Blattgold +${settled} heute · ${earned} von ${mark} Blatt bis zum vollen Tag`,
    full: ({ settled, days, goal }) => `Blattgold +${settled} heute · Voller Tag (${days} von ${goal} diese Woche)`,
    remembered: 'Du wusstest es noch.',
    sheet_title: 'Woher dein Blattgold kommt',
    sheet_eyebrow: (balance) => `Dein Heft · ${balance} Blatt Blattgold`,
    pill_label: (balance) => `${balance} Blatt Blattgold. Woher dein Blattgold kommt`,
    grain_said: (amount) => `+${amount} Blatt Blattgold`,
    today: 'Heute',
    day_full: 'voller Tag',
    day_toward: ({ earned, mark }) => `${earned} von ${mark} Blatt bis zum vollen Tag`,
    week: ({ days, goal }) => `${days} von ${goal} vollen Tagen diese Woche`,
    plafond_closed: 'Tagesgrenze erreicht',
    plafond_half: 'Grenze: halber Satz',
    pending: (n) => `${n} in Prüfung`,
    void_not_yet: 'noch nicht',
    void_already_paid: 'heute schon gezahlt',
    void_withdrawn: 'zurückgezogen',
    void_pulped: 'verworfen',
    sheet_failed: 'Das Heft lässt sich gerade nicht öffnen.',
    sheet_empty: 'Diese Woche noch nichts. Jede richtige Antwort legt hier ein Blatt ab.',
    week_before: 'Woche davor',
    this_week: 'Diese Woche',
  },
  fr: {
    toward: ({ settled, earned, mark }) => `Or +${settled} aujourd’hui · ${earned} / ${mark} feuilles vers la journée pleine`,
    full: ({ settled, days, goal }) => `Or +${settled} aujourd’hui · Journée pleine (${days} / ${goal} cette semaine)`,
    remembered: 'Tu t’en souvenais.',
    sheet_title: 'D’où vient ton or',
    sheet_eyebrow: (balance) => `Ton livret · ${balance} ${balance === 1 ? 'feuille' : 'feuilles'} d’or`,
    pill_label: (balance) => `${balance} ${balance === 1 ? 'feuille' : 'feuilles'} d’or. D’où vient ton or`,
    grain_said: (amount) => `+${amount} ${amount === 1 ? 'feuille' : 'feuilles'} d’or`,
    today: 'Aujourd’hui',
    day_full: 'journée pleine',
    day_toward: ({ earned, mark }) => `${earned} / ${mark} feuilles vers la journée pleine`,
    week: ({ days, goal }) => `semaine ${days} / ${goal}`,
    plafond_closed: 'Plafond du jour atteint',
    plafond_half: 'Plafond : demi-tarif',
    pending: (n) => `${n} à l’épreuve`,
    void_not_yet: 'pas encore',
    void_already_paid: 'déjà payé aujourd’hui',
    void_withdrawn: 'retiré',
    void_pulped: 'pilonné',
    sheet_failed: 'Le livret ne s’ouvre pas pour l’instant.',
    sheet_empty: 'Rien cette semaine. Chaque réponse juste y laisse une feuille.',
    week_before: 'Semaine d’avant',
    this_week: 'Cette semaine',
  },
};

/** L'or's words in a chrome language; English for anything unknown. */
export function goldCopy(language: unknown): GoldCopy {
  return GOLD_COPY[language as ControlLanguage] ?? GOLD_COPY.en;
}

/** The entries a view brought that `seen` did not hold, as one grain (or none). */
export function grainBetween(seen: ReadonlySet<string>, view: GoldView | null, id: number): GoldGrain | null {
  if (!view?.visible) return null;
  const fresh = (view.entries || []).filter((entry) => !seen.has(entry.id) && entry.state !== 'void' && entry.amount > 0);
  if (!fresh.length) return null;
  return {
    id,
    amount: fresh.reduce((sum, entry) => sum + entry.amount, 0),
    delayed: fresh.some((entry) => entry.delayed_recall),
    pending: fresh.every((entry) => entry.state === 'pending'),
  };
}

/** How far the day's settled gold has gilded the seal's rim toward the mark, 0–1. */
export function rimFraction(view: GoldView | null): number {
  const today = view?.visible ? view.today : null;
  if (!today || !today.mark) return 0;
  return Math.max(0, Math.min(1, today.earn_settled / today.mark));
}

/** «Gold +29 today · 19 of 20 leaves toward a full day» or «Gold +48 today · Full day (4 of 5 this week)». */
export function tirageLine(view: GoldView | null, language: unknown): string | null {
  const today = view?.visible ? view.today : null;
  if (!today) return null;
  const copy = goldCopy(language);
  const week = view?.week;
  if (today.pleine) {
    const goal = week?.journees_pleines_goal || JOURNEES_PLEINES_GOAL;
    return copy.full({ settled: today.settled, days: week?.journees_pleines ?? 1, goal });
  }
  return copy.toward({ settled: today.settled, earned: today.earn_settled, mark: today.mark });
}

/** The pill's quiet second line, when there is one: the plafond, or gold still à l'épreuve. */
export function todayNote(view: GoldView | null, language: unknown): string | null {
  const today = view?.visible ? view.today : null;
  if (!today) return null;
  const copy = goldCopy(language);
  if (today.plafond === 'closed') return copy.plafond_closed;
  if (today.plafond === 'half') return copy.plafond_half;
  if (today.pending > 0) return copy.pending(today.pending);
  return null;
}

/** The one line of an entry in «D'où vient ton or». */
export function entryLine(entry: GoldEntry): string {
  // French quotes hold the word with narrow no-break spaces («\u202fla clé\u202f»).
  const subject = entry.subject ? `«\u202f${entry.subject}\u202f» · ` : '';
  return `${subject}${entry.reason_fr || entry.entry_kind}`;
}

/** What a voided entry says instead of its amount. */
export function voidLine(entry: GoldEntry, language: unknown): string | null {
  if (entry.state !== 'void') return null;
  const copy = goldCopy(language);
  switch (entry.void_reason) {
    case 'not_yet':
      return copy.void_not_yet;
    case 'already_paid':
      return copy.void_already_paid;
    case 'withdrawn':
      return copy.void_withdrawn;
    default:
      return copy.void_pulped;
  }
}

/** Entries grouped by local day, newest day first (the ledger sends them newest first). */
export function entriesByDay(entries: readonly GoldEntry[]): { day: string; entries: GoldEntry[] }[] {
  const groups: { day: string; entries: GoldEntry[] }[] = [];
  for (const entry of entries) {
    const last = groups[groups.length - 1];
    if (last && last.day === entry.local_date) last.entries.push(entry);
    else groups.push({ day: entry.local_date, entries: [entry] });
  }
  return groups;
}

/** «Mon 2 Nov» / «Mo., 2. Nov.» / «lun. 2 nov.» for a local ISO day, without the time zone moving it. */
export function dayLabel(isoDay: string, language: unknown): string {
  return chromeDate(isoDay, language, 'weekday') ?? isoDay;
}

/** The ISO week of a UTC date («2026-W45»). */
export function isoWeekOf(date: Date): string {
  const thursday = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate()));
  thursday.setUTCDate(thursday.getUTCDate() + 3 - ((thursday.getUTCDay() + 6) % 7));
  const year = thursday.getUTCFullYear();
  const jan4 = new Date(Date.UTC(year, 0, 4));
  const week = 1 + Math.round(((thursday.getTime() - jan4.getTime()) / 86400000 - 3 + ((jan4.getUTCDay() + 6) % 7)) / 7);
  return `${year}-W${String(week).padStart(2, '0')}`;
}

/** The ISO week before `weekId` («2026-W45» → «2026-W44»). */
export function previousWeek(weekId: string): string | null {
  const match = /^(\d{4})-W(\d{2})$/.exec(weekId);
  if (!match) return null;
  const jan4 = new Date(Date.UTC(Number(match[1]), 0, 4));
  const monday = new Date(jan4);
  monday.setUTCDate(jan4.getUTCDate() - ((jan4.getUTCDay() + 6) % 7) + (Number(match[2]) - 1) * 7 - 7);
  return isoWeekOf(monday);
}
