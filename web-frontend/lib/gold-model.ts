/* Package O-2 — l'or on screen: the pure part (docs/ATELIER_GOLD_ECONOMY_PLAN.md §3, §11, §16).

   Everything here reads `GET /api/v1/gold` and decides what the counter, the
   grain, the ×2 and the day's seal show. No fetching and no React, so the
   node tests read it as it is. */

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

export const GOLD_REMEMBERED_FR = 'Tu t’en souvenais.';
export const GOLD_SHEET_TITLE_FR = 'D’où vient ton or';
export const JOURNEES_PLEINES_GOAL = 5;

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

/** «Or +48 · Journée pleine (4 / 5)» or «Or +12 · 12 / 20 vers la journée pleine». */
export function tirageLine(view: GoldView | null): string | null {
  const today = view?.visible ? view.today : null;
  if (!today) return null;
  const week = view?.week;
  if (today.pleine) {
    const goal = week?.journees_pleines_goal || JOURNEES_PLEINES_GOAL;
    return `Or +${today.settled} · Journée pleine (${week?.journees_pleines ?? 1} / ${goal})`;
  }
  return `Or +${today.settled} · ${today.earn_settled} / ${today.mark} vers la journée pleine`;
}

/** The pill's quiet second line, when there is one: the plafond, or gold still à l'épreuve. */
export function todayNote(view: GoldView | null): string | null {
  const today = view?.visible ? view.today : null;
  if (!today) return null;
  if (today.plafond === 'closed') return 'Plafond du jour atteint';
  if (today.plafond === 'half') return 'Plafond : demi-tarif';
  if (today.pending > 0) return `${today.pending} à l’épreuve`;
  return null;
}

/** The one line of an entry in «D'où vient ton or». */
export function entryLine(entry: GoldEntry): string {
  // French quotes hold the word with narrow no-break spaces («\u202fla clé\u202f»).
  const subject = entry.subject ? `«\u202f${entry.subject}\u202f» · ` : '';
  return `${subject}${entry.reason_fr || entry.entry_kind}`;
}

/** What a voided entry says instead of its amount. */
export function voidLine(entry: GoldEntry): string | null {
  if (entry.state !== 'void') return null;
  switch (entry.void_reason) {
    case 'not_yet':
      return 'pas encore';
    case 'already_paid':
      return 'déjà payé aujourd’hui';
    case 'withdrawn':
      return 'retiré';
    default:
      return 'pilonné';
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

/** «lun. 2 nov.» for a local ISO day, without the time zone moving it. */
export function dayLabel(isoDay: string): string {
  const [y, m, d] = isoDay.split('-').map(Number);
  if (!y || !m || !d) return isoDay;
  const date = new Date(Date.UTC(y, m - 1, d));
  return new Intl.DateTimeFormat('fr-FR', { weekday: 'short', day: 'numeric', month: 'short', timeZone: 'UTC' }).format(date);
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
