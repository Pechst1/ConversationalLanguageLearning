/**
 * The level plan as Fortschritt prints it (2026-10-24) — a pure function.
 *
 * Owner: «we always know exactly at which level the learner is currently so
 * that he also knows that exactly and knows what he has to do and how much
 * time he has to invest to advance further».
 *
 * Every number is the server's (`GET /progress/level`, `app/services/level_plan.py`):
 * the band and its percent are the ones La Une and the Dossier print, the rules
 * and words left are the band's coverage, the days are WP-L8's estimate and the
 * rules' floor, the minutes are measured or the plan's. This file only says
 * them, in the chrome language, and never counts anything itself.
 *
 * WP-25: a declared or placed level has no in-app measure behind it. Its
 * counts are said as «so far in the app», and neither a percent, a forecast,
 * nor a goal date is drawn against it.
 * WP-94: the épreuve is promised «in the story» only when the story stages it.
 */

import { normalizeControlLanguage } from '@/lib/atelier-v2-copy';
import { daySessionCopy, etaLabel } from '@/lib/day-session';
import { missingLine, stageWord, type GrammarStage } from '@/lib/grammar-stages';
import type { LevelPlan, LevelPlanReach, LevelPlanRule } from '@/services/api';
import type { ControlLanguage, PaceName } from '@/types/daily-journey';

import { fill, levelPlanCopy, num, plural, type LevelPlanCopy } from './level-plan-copy';

export type LadderState = 'passed' | 'credited' | 'start' | 'current' | 'ahead';

export type LadderStepView = {
  band: string;
  state: LadderState;
  goal: boolean;
  /** «A1.1, passed» — the step for a screen reader. */
  label: string;
};

export type CriterionView = {
  key: 'rules' | 'words';
  label: string;
  value: string;
  have: number;
  need: number;
  met: boolean;
  notes: string[];
};

export type RuleRowView = {
  id: number;
  title: string;
  /** `fr` when the title shown is the French one (content inside the chrome). */
  lang: 'fr' | undefined;
  tone: 'held' | 'owed' | 'progress' | 'new';
  note: string;
};

export type LevelPlanView = {
  band: string;
  verified: boolean;
  headline: string;
  percent: number;
  percentLabel: string;
  percentRule: string | null;
  next: string;
  evidence: string | null;
  ladderLabel: string;
  ladder: LadderStepView[];
  needsTitle: string;
  soFar: string | null;
  criteria: CriterionView[];
  wordsNote: string | null;
  test: { label: string; value: string; ready: boolean };
  today: string | null;
  time: {
    title: string;
    estimate: string | null;
    basis: string | null;
    earliest: string | null;
    cost: string | null;
    pace: string | null;
    changePace: string;
  };
  goal: string | null;
  invested: { title: string; lines: string[] };
  rules: { title: string; rows: RuleRowView[] };
  skills: { title: string; lines: string[] } | null;
};

const LADDER_STATES: LadderState[] = ['passed', 'credited', 'start', 'current', 'ahead'];
const TODAY_NAMES = 3;

function count(value: unknown): number {
  const n = Number(value);
  return Number.isFinite(n) ? Math.max(0, Math.round(n)) : 0;
}

/** «12 Nov» / «12. Nov.» / «12 nov.» for a server day (`YYYY-MM-DD`), read at noon UTC. */
export function planDay(iso: string | null | undefined, language: unknown): string | null {
  if (!iso) return null;
  const date = new Date(`${String(iso).slice(0, 10)}T12:00:00Z`);
  if (Number.isNaN(date.getTime())) return null;
  const copy = levelPlanCopy(language);
  return date.toLocaleDateString(copy.locale, { day: 'numeric', month: 'short', timeZone: 'UTC' });
}

/** «45 min», «3 h», «3 h 20 min» (German «3 Std. 20 Min.», French «3 h 20»). */
export function planDuration(minutes: number, language: unknown): string {
  const copy = levelPlanCopy(language);
  const total = count(minutes);
  if (total < 60) return fill(copy.duration_minutes, { m: total });
  const hours = Math.floor(total / 60);
  const rest = total % 60;
  return rest ? fill(copy.duration_hours_minutes, { h: hours, m: rest }) : fill(copy.duration_hours, { h: hours });
}

/** The unit's title as the notebook names it: the chrome language's, else English, else its name. */
export function ruleTitle(rule: Pick<LevelPlanRule, 'name' | 'titles'>, language: unknown): { title: string; lang: 'fr' | undefined } {
  const lang = normalizeControlLanguage(language);
  const titles = (rule.titles || {}) as Record<string, string>;
  if (titles[lang]) return { title: titles[lang], lang: lang === 'fr' ? 'fr' : undefined };
  if (titles.en) return { title: titles.en, lang: undefined };
  return { title: String(rule.name || ''), lang: undefined };
}

function ladderWord(state: LadderState, copy: LevelPlanCopy): string {
  return {
    passed: copy.ladder_passed,
    credited: copy.ladder_credited,
    start: copy.ladder_start,
    current: copy.ladder_current,
    ahead: copy.ladder_ahead,
  }[state];
}

function ladderView(plan: LevelPlan, copy: LevelPlanCopy): LadderStepView[] {
  return (plan.ladder || []).map((step) => {
    const state = (LADDER_STATES as string[]).includes(step.state) ? (step.state as LadderState) : 'ahead';
    const goal = Boolean(step.goal);
    return {
      band: step.band,
      state,
      goal,
      label: [step.band, ladderWord(state, copy), goal ? copy.ladder_goal : null].filter(Boolean).join(', '),
    };
  });
}

function criteriaView(plan: LevelPlan, language: ControlLanguage, copy: LevelPlanCopy): {
  criteria: CriterionView[];
  wordsNote: string | null;
} {
  const band = plan.band;
  const rules = plan.rules;
  const rulesNotes: string[] = [];
  if (rules.met) {
    rulesNotes.push(fill(copy.rules_met, { band }));
  } else {
    const parts: string[] = [];
    if (count(rules.practising)) parts.push(stageWord('practising', language, count(rules.practising)));
    if (count(rules.introduced)) parts.push(stageWord('introduced', language, count(rules.introduced)));
    if (count(rules.not_started)) parts.push(plural(copy, 'rules_not_met', count(rules.not_started)));
    if (parts.length) rulesNotes.push(parts.join(' · '));
  }
  const criteria: CriterionView[] = [
    {
      key: 'rules',
      label: copy.rules_label,
      value: fill(copy.count_value, { have: count(rules.held), need: count(rules.required), total: count(rules.total) }),
      have: count(rules.held),
      need: count(rules.required),
      met: Boolean(rules.met),
      notes: rulesNotes,
    },
  ];

  const words = plan.words;
  if (count(words.total) === 0) {
    // The core lexicon stops at B1: above it the rules and the épreuve decide.
    return { criteria, wordsNote: copy.words_no_list };
  }
  const wordsNotes: string[] = [];
  if (words.met) {
    wordsNotes.push(fill(copy.words_met, { band }));
  } else {
    if (count(words.on_the_way)) wordsNotes.push(plural(copy, 'words_way', count(words.on_the_way)));
    if (count(words.new_needed) && count(words.per_day)) {
      wordsNotes.push(
        plural(copy, 'words_new', count(words.new_needed), {
          days: plural(copy, 'days', Math.max(1, count(words.days_for_new))),
          per_day: count(words.per_day),
        }),
      );
    }
  }
  if (count(words.from_reading)) wordsNotes.push(plural(copy, 'words_reading', count(words.from_reading)));
  criteria.push({
    key: 'words',
    label: copy.words_label,
    value: fill(copy.count_value, {
      have: num(count(words.known), copy),
      need: num(count(words.required), copy),
      total: num(count(words.total), copy),
    }),
    have: count(words.known),
    need: count(words.required),
    met: Boolean(words.met),
    notes: wordsNotes,
  });
  return { criteria, wordsNote: null };
}

function testView(plan: LevelPlan, language: ControlLanguage, copy: LevelPlanCopy): LevelPlanView['test'] {
  const epreuve = plan.epreuve;
  let value: string;
  switch (epreuve.state) {
    case 'ready':
      value = epreuve.staged_in_story ? copy.test_ready_story : copy.test_ready;
      break;
    case 'failed': {
      const date = planDay(epreuve.retry_after, language);
      value = date ? fill(copy.test_failed_dated, { date }) : copy.test_failed;
      break;
    }
    case 'passed':
      value = copy.test_passed;
      break;
    case 'credited':
      value = copy.test_credited;
      break;
    default:
      value = copy.test_locked;
  }
  return { label: copy.test_label, value, ready: epreuve.state === 'ready' };
}

function todayView(plan: LevelPlan, language: ControlLanguage, copy: LevelPlanCopy): string | null {
  const owed = (plan.rules.items || []).filter((item) => item.owed_today);
  if (!owed.length) return null;
  // A title can hold a comma («avoir, regular and irregular participles»): the titles part on a semicolon.
  let names = owed
    .slice(0, TODAY_NAMES)
    .map((item) => ruleTitle(item, language).title)
    .join(copy.today_separator);
  if (owed.length > TODAY_NAMES) names = `${names} ${fill(copy.today_more, { n: owed.length - TODAY_NAMES })}`;
  return plural(copy, 'today', owed.length, { names });
}

function weekly(value: unknown, copy: LevelPlanCopy): string {
  const n = Math.round(Number(value || 0) * 10) / 10;
  return Number.isInteger(n) ? String(n) : n.toLocaleString(copy.locale);
}

function projected(plan: LevelPlan, days: number, language: unknown): string | null {
  const start = new Date(plan.generated_at);
  if (Number.isNaN(start.getTime())) return null;
  return planDay(new Date(start.getTime() + days * 86_400_000).toISOString(), language);
}

function timeView(plan: LevelPlan, language: ControlLanguage, copy: LevelPlanCopy, verified: boolean): LevelPlanView['time'] {
  const time = plan.time;
  const pace = daySessionCopy(language).pace[time.pace as PaceName];
  const view: LevelPlanView['time'] = {
    title: copy.time_title,
    estimate: null,
    basis: null,
    earliest: null,
    cost: null,
    pace: pace
      ? fill(copy.time_pace, { pace, words: count(time.words_per_day), rules: weekly(time.rules_per_week, copy) })
      : null,
    changePace: copy.time_change,
  };
  // WP-25: no forecast against a level the app has not measured; say when one comes.
  if (!verified) {
    view.estimate = copy.time_unverified;
    return view;
  }

  const range = Array.isArray(time.range_days) && time.range_days.length === 2 ? time.range_days : null;
  if (time.status === 'none' || !range) {
    view.estimate = copy.time_none;
  } else if (time.capped) {
    view.estimate = copy.time_capped;
  } else {
    const [low, high] = range.map(count);
    const dates = time.dates || [];
    view.estimate = fill(time.status === 'measured' ? copy.time_measured : copy.time_plan, {
      low,
      high,
      from: planDay(dates[0], language) || projected(plan, low, language) || '',
      to: planDay(dates[1], language) || projected(plan, high, language) || '',
    });
  }
  if (time.status === 'measured') view.basis = copy.time_basis_measured;
  else if (time.status === 'plan') {
    view.basis = fill(copy.time_basis_plan, { required: count(time.active_days_required), active: count(time.active_days) });
  }
  const earliest = planDay(time.earliest_on, language);
  if (earliest && range && !time.capped) view.earliest = fill(copy.time_earliest, { date: earliest });
  const hours = Array.isArray(time.hours) && time.hours.length === 2 ? time.hours.map(count) : null;
  if (hours && count(time.minutes_per_day) && !time.capped) {
    view.cost = fill(time.minutes_source === 'measured' ? copy.time_cost_measured : copy.time_cost_plan, {
      minutes: count(time.minutes_per_day),
      hours: hours[0] === hours[1] ? plural(copy, 'hours', hours[0]) : fill(copy.hours_range, { low: hours[0], high: hours[1] }),
    });
  }
  return view;
}

function goalView(plan: LevelPlan, language: ControlLanguage, copy: LevelPlanCopy, verified: boolean): string | null {
  const goal = plan.goal;
  // The next band is the estimate above; the goal line is for a goal further up.
  if (!verified || !goal || count(goal.bands_left) < 2) return null;
  const words = count(goal.words_left);
  const rules = count(goal.units_left);
  if (!words && !rules) return null;
  return fill(copy.goal_line, {
    band: goal.band,
    words: num(words, copy),
    rules: num(rules, copy),
    eta: etaLabel(Number(goal.weeks || 0), language),
  });
}

function investedView(plan: LevelPlan, language: ControlLanguage, copy: LevelPlanCopy): LevelPlanView['invested'] {
  const invested = plan.invested;
  const lines: string[] = [];
  const minutes = count(invested.band_minutes);
  if (minutes > 0) {
    const days = plural(copy, 'on_days', count(invested.band_days));
    const time = planDuration(minutes, language);
    const since = planDay(invested.band_since, language);
    lines.push(
      since
        ? fill(copy.invested_since, { time, band: plan.band, date: since, days })
        : fill(copy.invested_start, { time, days }),
    );
    lines.push(
      fill(copy.invested_parts, {
        scenes: planDuration(count(invested.scenes_minutes), language),
        forge: planDuration(count(invested.forge_minutes), language),
        words: planDuration(count(invested.words_minutes), language),
      }),
    );
  } else {
    lines.push(fill(copy.invested_none, { band: plan.band }));
  }
  if (Number(invested.recent_minutes_per_day || 0) >= 1) {
    lines.push(fill(copy.invested_recent, { minutes: count(invested.recent_minutes_per_day) }));
  }
  // The Courrier and Le Papier keep no clock yet: the total is a floor.
  lines.push(copy.invested_floor);
  return { title: copy.invested_title, lines };
}

function ruleRows(plan: LevelPlan, language: ControlLanguage, copy: LevelPlanCopy, today: Date): RuleRowView[] {
  return (plan.rules.items || []).map((item) => {
    const { title, lang } = ruleTitle(item, language);
    const stage = String(item.stage || 'new') as GrammarStage;
    if (stage === 'held') {
      const date = planDay(item.held_on, language);
      return { id: item.id, title, lang, tone: 'held', note: date ? fill(copy.row_held, { date }) : stageWord('held', language) };
    }
    if (stage === 'new') {
      const date = planDay(item.introduce_from, language);
      return { id: item.id, title, lang, tone: 'new', note: date ? fill(copy.row_new_dated, { date }) : copy.row_new };
    }
    const parts = [item.owed_today ? copy.row_owed : stageWord(stage, language)];
    const missing = missingLine(item.missing as Parameters<typeof missingLine>[0], language, today);
    if (missing) parts.push(missing);
    const earliest = planDay(item.earliest_held_on, language);
    if (earliest) parts.push(fill(copy.row_earliest, { date: earliest }));
    return { id: item.id, title, lang, tone: item.owed_today ? 'owed' : 'progress', note: parts.join(' · ') };
  });
}

function skillsView(plan: LevelPlan, copy: LevelPlanCopy, verified: boolean): LevelPlanView['skills'] {
  if (!verified) return null;
  const line = (what: string, reach: LevelPlanReach | undefined) => {
    if (!reach) return null;
    const percent = count(reach.percent);
    if (reach.list_ends && reach.covered) return fill(copy.skills_list_ends, { what, covered: reach.covered });
    if (reach.working && reach.covered) {
      return fill(copy.skills_working, { what, covered: reach.covered, percent, working: reach.working });
    }
    if (reach.working) return fill(copy.skills_working_start, { what, percent, working: reach.working });
    if (reach.covered) return fill(copy.skills_all, { what, covered: reach.covered });
    return null;
  };
  const skills = plan.skills || {};
  const lines = [line(copy.skills_words, skills.words), line(copy.skills_rules, skills.rules)].filter(
    (value): value is string => Boolean(value),
  );
  if (!lines.length) return null;
  return { title: copy.skills_title, lines: [...lines, copy.skills_note] };
}

/** The plan, said: everything Fortschritt's «Le cours» prints from `GET /progress/level`. */
export function levelPlanView(plan: LevelPlan, language: unknown, today: Date = new Date()): LevelPlanView {
  const lang = normalizeControlLanguage(language);
  const copy = levelPlanCopy(lang);
  const verified = Boolean(plan.verified);
  const percent = Math.max(0, Math.min(100, count(plan.percent)));
  const { criteria, wordsNote } = criteriaView(plan, lang, copy);
  const evidence = plan.evidence;
  return {
    band: plan.band,
    verified,
    // «A1.1 · 42 %», the label La Une and the Dossier print; the band alone when unmeasured.
    headline: verified ? plan.label || `${plan.band} · ${percent} %` : plan.band,
    percent,
    percentLabel: fill(copy.percent_aria, { band: plan.band, percent }),
    percentRule: verified && percent < 100 ? fill(copy.percent_rule, { band: plan.band }) : null,
    next: plan.next_band ? fill(copy.next_band, { band: plan.next_band }) : copy.top_band,
    evidence:
      !verified && evidence
        ? fill(copy.evidence, { required: count(evidence.attempts_required), counted: count(evidence.attempts_counted) })
        : null,
    ladderLabel: copy.ladder_label,
    ladder: ladderView(plan, copy),
    needsTitle: plan.next_band
      ? fill(copy.needs_title, { band: plan.next_band })
      : fill(copy.needs_title_top, { band: plan.band }),
    soFar: verified ? null : copy.so_far,
    criteria,
    wordsNote,
    test: testView(plan, lang, copy),
    today: todayView(plan, lang, copy),
    time: timeView(plan, lang, copy, verified),
    goal: goalView(plan, lang, copy, verified),
    invested: investedView(plan, lang, copy),
    rules: {
      title: fill(copy.list_title, { band: plan.band, n: (plan.rules.items || []).length }),
      rows: ruleRows(plan, lang, copy, today),
    },
    skills: skillsView(plan, copy, verified),
  };
}
