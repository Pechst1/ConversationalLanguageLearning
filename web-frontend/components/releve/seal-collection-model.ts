/**
 * WP-D5 · «Vos sceaux» — the streak calendar as a grid, as a pure function.
 *
 * Everything is the server's (`GET /analytics/streak`): the number and the
 * days come from the same rows, so this file never counts a streak itself.
 * It only lays the days out as weeks (Monday first, seven columns) and names
 * each cell for a screen reader. Days before the learner's first recorded day
 * are blank cells, never «missed».
 */

import { isSealVariant, sealForEdition, type SealMiniState, type SealVariant } from '@/components/ui/Seal';
import type { StreakCalendar, StreakCalendarDay } from '@/services/api';

export const SEAL_GRID_WEEKS = 4;
export const WEEKDAY_INITIALS = ['L', 'M', 'M', 'J', 'V', 'S', 'D'] as const;

export type SealCell =
  | { kind: 'blank'; key: string }
  | {
      kind: 'day';
      key: string;
      date: string;
      state: SealMiniState;
      variant: SealVariant;
      no: number | null;
      caption: string;
      label: string;
      isToday: boolean;
    };

export type SealCollectionView = {
  streak: number;
  longest: number;
  todayDone: boolean;
  freezeAvailable: boolean;
  weeks: SealCell[][];
  today: SealCell | null;
};

function parseDay(value: string): Date | null {
  const parsed = new Date(`${value}T12:00:00Z`);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function isoDay(date: Date): string {
  return date.toISOString().slice(0, 10);
}

function addDays(date: Date, days: number): Date {
  const next = new Date(date.getTime());
  next.setUTCDate(next.getUTCDate() + days);
  return next;
}

function mondayOf(date: Date): Date {
  const weekday = (date.getUTCDay() + 6) % 7; // Monday = 0
  return addDays(date, -weekday);
}

function longDate(date: Date): string {
  try {
    return new Intl.DateTimeFormat('fr-FR', {
      weekday: 'long',
      day: 'numeric',
      month: 'long',
      timeZone: 'UTC',
    }).format(date);
  } catch {
    return isoDay(date);
  }
}

const STATE_WORDS: Record<Exclude<SealMiniState, 'empty'>, string> = {
  earned: 'sceau',
  done: 'journée faite',
  relache: 'jour de relâche',
  today: 'aujourd’hui, le sceau attend',
  future: 'à venir',
  missed: 'pas de séance',
};

function cellFor(day: StreakCalendarDay, date: Date): SealCell {
  let state: SealMiniState;
  if (day.state === 'completed') state = day.sealed ? 'earned' : 'done';
  else if (day.state === 'relache') state = 'relache';
  else if (day.state === 'today') state = 'today';
  else if (day.state === 'future') state = 'future';
  else state = 'missed';

  const no = state === 'earned' && typeof day.edition_no === 'number' ? day.edition_no : null;
  const variant: SealVariant = isSealVariant(day.seal_variant)
    ? day.seal_variant
    : no != null
      ? sealForEdition(no).variant
      : 'quad';
  const words = state === 'earned' && no != null ? `sceau Nº ${no}` : STATE_WORDS[state as Exclude<SealMiniState, 'empty'>];
  return {
    kind: 'day',
    key: day.date,
    date: day.date,
    state,
    variant,
    no,
    caption: String(date.getUTCDate()),
    label: `${longDate(date)} · ${words}`,
    isToday: Boolean(day.is_today),
  };
}

export function sealCollectionView(
  payload: StreakCalendar | null | undefined,
  weeks: number = SEAL_GRID_WEEKS,
): SealCollectionView | null {
  if (!payload || !Array.isArray(payload.calendar)) return null;
  const byDate = new Map<string, StreakCalendarDay>();
  for (const day of payload.calendar) byDate.set(day.date, day);

  const todayEntry = payload.calendar.find((day) => day.is_today);
  const todayDate = parseDay(payload.today || todayEntry?.date || '');
  if (!todayDate) return null;

  const firstMonday = addDays(mondayOf(todayDate), -7 * (Math.max(1, weeks) - 1));
  const grid: SealCell[][] = [];
  let todayCell: SealCell | null = null;
  for (let week = 0; week < Math.max(1, weeks); week += 1) {
    const row: SealCell[] = [];
    for (let weekday = 0; weekday < 7; weekday += 1) {
      const date = addDays(firstMonday, week * 7 + weekday);
      const key = isoDay(date);
      const day = byDate.get(key);
      const cell = day ? cellFor(day, date) : ({ kind: 'blank', key } as SealCell);
      if (cell.kind === 'day' && cell.isToday) todayCell = cell;
      row.push(cell);
    }
    // A week wholly before the learner's first day is not drawn.
    if (row.some((cell) => cell.kind === 'day')) grid.push(row);
  }

  return {
    streak: Math.max(0, Number(payload.current_streak) || 0),
    longest: Math.max(0, Number(payload.longest_streak) || 0),
    todayDone: Boolean(payload.today_done),
    freezeAvailable: Boolean(payload.freeze_available),
    weeks: grid,
    today: todayCell,
  };
}

export function daysLabel(n: number): string {
  return n === 1 ? '1 jour' : `${n} jours`;
}
