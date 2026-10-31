/**
 * Round 3 (owner, 2026-10-14) — the day as one sequence, with a real dose.
 *
 * «One daily sequence: the photo scene, then words, then grammar. Words and La
 * Forge are part of the day, not extras. Only after the day's quota is done can
 * the learner choose to keep going.»
 *
 * The server sends the day's four steps (`TodayEnvelope.session`, built in
 * `app/services/daily_session.py`): Szene, Wörter, Grammatik, Fertig, each
 * `done`, `next` or `todo`, with its minutes. This file turns them into what
 * Home and the hand-offs print: the programme rows, the one button («Weiter:
 * 20 Wörter · 8 Min.»), the mark's four shapes, and the Tempo sheet's rows.
 *
 * Pure: no React, no transport. Every word is here, in the three chrome
 * languages; the node tests (`day-session.test.js`) read the same functions.
 */

import type { DayMarkGroup, DayMarkGroupState, DayMarkState } from '@/components/atelier-v2/journey/day-mark';
import { dayMarkLabel } from '@/components/atelier-v2/journey/day-mark';
import type {
  ControlLanguage,
  DaySession,
  DaySessionStep,
  DaySessionStepKind,
  PaceName,
  PaceOption,
} from '@/types/daily-journey';

type Copy = {
  scene: string;
  papier: string;
  words: (n: number) => string;
  /** «10 new · 8 to review»: the deck's two halves, named apart (#279). */
  words_split: (fresh: number, due: number) => string;
  grammar: string;
  finish: string;
  minutes: (n: number) => string;
  start: string;
  next_words: (n: number) => string;
  next_grammar: string;
  next_finish: string;
  done_today: string;
  more_words: (n: number) => string;
  tempo: (pace: string) => string;
  pace: Record<PaceName, string>;
  sheet_title: string;
  sheet_row: (words: number, rules: number) => string;
  sheet_goal: (goal: string, eta: string) => string;
  sheet_note: (low: number, high: number) => string;
  sheet_apply: string;
  sheet_close: string;
  weeks: (n: number) => string;
  months: (n: string) => string;
  finish_title: string;
  tally_scene: string;
  tally_words: string;
  tally_exercises: string;
  back_home: string;
  scene_done: string;
  words_done: string;
  part_done: string;
  part_next: string;
  part_todo: string;
  plan_label: string;
};

const DE: Copy = {
  scene: 'Szene',
  papier: 'Le Papier',
  words: (n) => `${n} Wörter`,
  words_split: (fresh, due) => `${fresh} neu · ${due} zum Wiederholen`,
  grammar: 'Grammatik',
  finish: 'Fertig',
  minutes: (n) => `${n} Min.`,
  start: 'Los geht’s',
  next_words: (n) => `Weiter: ${n} Wörter`,
  next_grammar: 'Weiter: Grammatik',
  next_finish: 'Fertig für heute',
  done_today: 'Heute erledigt',
  more_words: (n) => `Noch ${n} Wörter`,
  tempo: (pace) => `Tempo: ${pace}`,
  pace: { ruhig: 'Ruhig', normal: 'Normal', schnell: 'Schnell' },
  sheet_title: 'Dein Tempo',
  sheet_row: (words, rules) => `${words} Wörter · ${rules} Regeln pro Woche`,
  sheet_goal: (goal, eta) => `${goal} in ${eta}`,
  sheet_note: (low, high) =>
    `Wörter kommen zur Wiederholung zurück. Nach 8 Wochen dauert ein Tag etwa ${low} bis ${high} Min. länger.`,
  sheet_apply: 'Übernehmen',
  sheet_close: 'Schließen',
  weeks: (n) => `≈ ${n} Wochen`,
  months: (n) => `≈ ${n} Monaten`,
  finish_title: 'Fertig für heute',
  tally_scene: 'Szene',
  tally_words: 'Wörter',
  tally_exercises: 'Übungen',
  back_home: 'Zurück zu La Une',
  scene_done: 'Szene geschafft',
  words_done: 'Wörter geschafft',
  part_done: 'erledigt',
  part_next: 'als Nächstes',
  part_todo: 'kommt noch',
  plan_label: 'Dein Tag',
};

const FR: Copy = {
  scene: 'Scène',
  papier: 'Le Papier',
  words: (n) => `${n} mots`,
  words_split: (fresh, due) => `${fresh} nouveaux · ${due} à revoir`,
  grammar: 'Grammaire',
  finish: 'Fin',
  minutes: (n) => `${n} min`,
  start: 'C’est parti',
  next_words: (n) => `Suite : ${n} mots`,
  next_grammar: 'Suite : grammaire',
  next_finish: 'Fini pour aujourd’hui',
  done_today: 'Fait aujourd’hui',
  more_words: (n) => `Encore ${n} mots`,
  tempo: (pace) => `Rythme : ${pace}`,
  pace: { ruhig: 'Calme', normal: 'Normal', schnell: 'Rapide' },
  sheet_title: 'Ton rythme',
  sheet_row: (words, rules) => `${words} mots · ${rules} règles par semaine`,
  sheet_goal: (goal, eta) => `${goal} dans ${eta}`,
  sheet_note: (low, high) =>
    `Les mots reviennent en révision. Dans 8 semaines, une journée prend environ ${low} à ${high} min de plus.`,
  sheet_apply: 'Valider',
  sheet_close: 'Fermer',
  weeks: (n) => `≈ ${n} semaines`,
  months: (n) => `≈ ${n} mois`,
  finish_title: 'Fini pour aujourd’hui',
  tally_scene: 'Scène',
  tally_words: 'Mots',
  tally_exercises: 'Exercices',
  back_home: 'Retour à La Une',
  scene_done: 'Scène terminée',
  words_done: 'Mots terminés',
  part_done: 'fait',
  part_next: 'à suivre',
  part_todo: 'à venir',
  plan_label: 'Ta journée',
};

const EN: Copy = {
  scene: 'Scene',
  papier: 'Le Papier',
  words: (n) => `${n} words`,
  words_split: (fresh, due) => `${fresh} new · ${due} to review`,
  grammar: 'Grammar',
  finish: 'Done',
  minutes: (n) => `${n} min`,
  start: 'Let’s go',
  next_words: (n) => `Next: ${n} words`,
  next_grammar: 'Next: grammar',
  next_finish: 'Done for today',
  done_today: 'Done today',
  more_words: (n) => `${n} more words`,
  tempo: (pace) => `Pace: ${pace}`,
  pace: { ruhig: 'Easy', normal: 'Normal', schnell: 'Fast' },
  sheet_title: 'Your pace',
  sheet_row: (words, rules) => `${words} words · ${rules} rules a week`,
  sheet_goal: (goal, eta) => `${goal} in ${eta}`,
  sheet_note: (low, high) =>
    `Words come back for review. In 8 weeks a day takes about ${low} to ${high} min longer.`,
  sheet_apply: 'Use this pace',
  sheet_close: 'Close',
  weeks: (n) => `≈ ${n} weeks`,
  months: (n) => `≈ ${n} months`,
  finish_title: 'Done for today',
  tally_scene: 'Scene',
  tally_words: 'Words',
  tally_exercises: 'Exercises',
  back_home: 'Back to La Une',
  scene_done: 'Scene done',
  words_done: 'Words done',
  part_done: 'done',
  part_next: 'next',
  part_todo: 'to come',
  plan_label: 'Your day',
};

const TABLE: Record<ControlLanguage, Copy> = { de: DE, fr: FR, en: EN };

export function daySessionCopy(language: ControlLanguage | null | undefined): Copy {
  return TABLE[(language || 'en') as ControlLanguage] ?? EN;
}

export type DaySessionCopy = Copy;

/** The step → the mark's group: the logo's four shapes are the day's four steps. */
export const SESSION_GROUP: Record<DaySessionStepKind, DayMarkGroup> = {
  scene: 'scene',
  words: 'recall',
  grammar: 'respond',
  finish: 'resolution',
};

/** The shape each step is drawn with (blue story, yellow reward, red action, ink done). */
export const SESSION_SHAPE: Record<DaySessionStepKind, 'story' | 'reward' | 'action' | 'done'> = {
  scene: 'story',
  words: 'reward',
  grammar: 'action',
  finish: 'done',
};

export type SessionRow = {
  kind: DaySessionStepKind;
  state: DaySessionStep['state'];
  label: string;
  /** «8 Min.» while the step is still to do; empty once done, and for Fertig. */
  meta: string;
  shape: (typeof SESSION_SHAPE)[DaySessionStepKind];
};

/**
 * What the words step spends: its minutes, and when the deck holds both new
 * words and reviews, how it splits («10 neu · 8 zum Wiederholen · 5 Min.»), so
 * the count above it is never read as new words alone.
 */
function wordsMeta(step: DaySessionStep, copy: Copy): string {
  const fresh = Number(step.new_left || 0);
  const due = Number(step.reviews || 0);
  const parts = [fresh > 0 && due > 0 ? copy.words_split(fresh, due) : '', step.minutes > 0 ? copy.minutes(step.minutes) : ''];
  return parts.filter(Boolean).join(' · ');
}

/** Home's programme: one row per step, with the minutes it still costs. */
export function sessionRows(
  session: DaySession,
  language: ControlLanguage,
  options: { papier?: boolean } = {},
): SessionRow[] {
  const copy = daySessionCopy(language);
  return session.steps.map((step) => {
    const label =
      step.kind === 'scene'
        ? options.papier
          ? copy.papier
          : copy.scene
        : step.kind === 'words'
          ? copy.words(Number(step.count || 0))
          : step.kind === 'grammar'
            ? copy.grammar
            : copy.finish;
    const meta =
      step.state === 'done' ? '' : step.kind === 'words' ? wordsMeta(step, copy) : step.minutes > 0 ? copy.minutes(step.minutes) : '';
    return { kind: step.kind, state: step.state, label, meta, shape: SESSION_SHAPE[step.kind] };
  });
}

export function sessionStep(session: DaySession | null | undefined, kind: DaySessionStepKind): DaySessionStep | null {
  return session?.steps.find((step) => step.kind === kind) ?? null;
}

/**
 * The one button once the scene is done: the next step, its label and where it
 * goes. `null` while the scene is next (the journey card's own press starts it)
 * and once the day is done.
 */
export function sessionNextAction(
  session: DaySession | null | undefined,
  language: ControlLanguage,
): { kind: DaySessionStepKind; label: string; meta: string; href: string } | null {
  if (!session || session.done || !session.next_kind || session.next_kind === 'scene') return null;
  const step = sessionStep(session, session.next_kind);
  if (!step || !step.href) return null;
  const copy = daySessionCopy(language);
  const label =
    step.kind === 'words'
      ? copy.next_words(Number(step.count || 0))
      : step.kind === 'grammar'
        ? copy.next_grammar
        : copy.next_finish;
  const meta = step.kind === 'words' ? wordsMeta(step, copy) : step.minutes > 0 ? copy.minutes(step.minutes) : '';
  return { kind: step.kind, label, meta, href: step.href };
}

/** After the day, the one optional extra: «Noch 10 Wörter · 4 Min.». */
export function sessionMore(
  session: DaySession | null | undefined,
  language: ControlLanguage,
): { label: string; meta: string; href: string } | null {
  if (!session || !session.done || !session.more_words) return null;
  const copy = daySessionCopy(language);
  return {
    label: copy.more_words(session.more_words),
    meta: copy.minutes(session.more_minutes),
    href: session.more_href,
  };
}

/**
 * #396: what Home's day chip (the streak number and its «done» mark) says. The
 * server's streak counts today from the first practice, which the day's words
 * already are, so the chip went 19 → 20 while the grammar step was still to do.
 * With the day's session in hand the chip counts today only once the session is
 * done (the Done step); until then it shows the chain as it stood this morning.
 * Without a session (no journey today) the server's own flag stands.
 */
export function homeDayChip(
  days: number,
  practiceDone: boolean,
  session: DaySession | null | undefined,
): { streak: number; dayDone: boolean } {
  const count = Number.isFinite(days) && days > 0 ? Math.round(days) : 0;
  if (!session) return { streak: count, dayDone: practiceDone };
  const dayDone = Boolean(session.done);
  // The server counted today for the practice so far: take it back until the day is done.
  const streak = practiceDone && !dayDone ? Math.max(0, count - 1) : count;
  return { streak, dayDone };
}

/** The mark's four shapes fill in with the day's four steps. */
export function sessionMarkState(session: DaySession, language: ControlLanguage): DayMarkState {
  const groups = {} as Record<DayMarkGroup, DayMarkGroupState>;
  for (const step of session.steps) {
    groups[SESSION_GROUP[step.kind]] = step.state === 'next' ? 'active' : step.state;
  }
  const done = session.steps.filter((step) => step.state === 'done').length;
  return { groups, done, total: session.steps.length, label: dayMarkLabel(groups, language) };
}

/** «≈ 10 Wochen» under three months, «≈ 2½ Monaten» from there. */
export function etaLabel(weeks: number, language: ControlLanguage): string {
  const copy = daySessionCopy(language);
  if (!Number.isFinite(weeks) || weeks <= 0) return copy.weeks(0);
  if (weeks < 12) return copy.weeks(Math.max(1, Math.round(weeks)));
  const months = Math.round((weeks / 4.345) * 2) / 2;
  const whole = Math.floor(months);
  const text = months - whole >= 0.5 ? (whole > 0 ? `${whole}½` : '½') : `${whole}`;
  return copy.months(text);
}

export type PaceRow = {
  pace: PaceName;
  name: string;
  detail: string;
  minutes: string;
  goal: string;
};

/** The Tempo sheet's rows: name, what it holds, minutes today, and when it reaches the goal. */
export function paceRows(options: PaceOption[], goal: string, language: ControlLanguage): PaceRow[] {
  const copy = daySessionCopy(language);
  const level = goal.slice(0, 2).toUpperCase();
  return options.map((option) => ({
    pace: option.pace,
    name: copy.pace[option.pace],
    detail: copy.sheet_row(option.words, option.rules_per_week),
    minutes: `≈ ${copy.minutes(option.minutes_today)}`,
    goal: copy.sheet_goal(level, etaLabel(option.goal_weeks, language)),
  }));
}

/** «Nach 8 Wochen dauert ein Tag etwa 2 bis 8 Min. länger.» */
export function paceNote(options: PaceOption[], language: ControlLanguage): string {
  const growth = options.map((option) => Math.max(0, option.minutes_week_8 - option.minutes_today));
  const low = growth.length ? Math.min(...growth) : 0;
  const high = growth.length ? Math.max(...growth) : 0;
  return daySessionCopy(language).sheet_note(low, high);
}

