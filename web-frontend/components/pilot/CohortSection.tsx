import React from 'react';

export type CohortCell = { returned: number; due: number; rate: number | null; display: string };

export type CohortLearnerRow = {
  user_id: string;
  email: string;
  synthetic: boolean;
  signup_date: string;
  timezone: string;
  returns: Record<string, boolean | null>;
  days_started: number;
  days_completed: number;
  days_abandoned?: number;
  finished_first_day?: boolean | null;
  median_active_minutes: number | null;
  median_story_words?: number | null;
  median_own_words?: number | null;
  stops: Array<{ date: string; after_step: string }>;
};

export type CohortRow = {
  week_start: string;
  learners: number;
  returns: Record<string, CohortCell>;
  days_started: number;
  days_completed: number;
  finished_first_day?: CohortCell;
  median_active_minutes: number | null;
  median_story_words?: number | null;
  median_own_words?: number | null;
  stops: Array<{ after_step: string; days: number }>;
  learner_rows: CohortLearnerRow[];
};

export type PilotCohorts = {
  today: string;
  weeks: number;
  return_days: number[];
  min_learners_for_rate: number;
  include_synthetic: boolean;
  synthetic_excluded: number;
  cohorts: CohortRow[];
};

function returnMark(value: boolean | null | undefined): string {
  if (value === true) return 'yes';
  if (value === false) return 'no';
  return '·';
}

function minutes(value: number | null | undefined): string {
  return value === null || value === undefined ? 'unknown' : `${value}`;
}

/**
 * S6 · who came back, per sign-up week, read from the ledger (not from a walk).
 * Under the minimum a cell shows counts only. Drawn with the page's own tokens.
 */
export function CohortSection({ report, loadError }: { report: PilotCohorts | null; loadError: string }) {
  const [open, setOpen] = React.useState<string | null>(null);
  const days = report?.return_days ?? [1, 3, 7, 14, 30];

  return (
    <section className="mt-8 border border-[var(--app-ink)] bg-[var(--app-sheet)]" aria-labelledby="pilot-cohorts">
      <div className="border-b border-[var(--app-ink)] p-4">
        <div className="font-mono text-[10px] font-black uppercase tracking-wider text-[var(--app-blue)]">Learners</div>
        <h2 id="pilot-cohorts" className="mt-1 font-serif text-3xl italic">Who came back?</h2>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--app-ink-2)]">
          Whether the first day was finished, then return on day {days.join(', ')} after sign-up, in each
          learner&apos;s own days. Story words are the French read or heard, own words the French
          the learner wrote or said in judged answers, each a median over active days.
          {report && ` Under ${report.min_learners_for_rate} learners a cell shows counts, not a percentage.`}
          {report && report.synthetic_excluded > 0 && ` ${report.synthetic_excluded} walk or test account(s) left out.`}
        </p>
      </div>
      {loadError && <div role="alert" className="p-4 font-bold text-[var(--app-red)]">{loadError}</div>}
      {!report && !loadError && <div className="p-4 font-mono text-xs font-black uppercase tracking-widest">Loading…</div>}
      {report && (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[1040px] border-collapse text-left text-sm">
            <thead className="font-mono text-[10px] uppercase tracking-wider text-[var(--app-ink-3)]">
              <tr>
                <th className="p-3">Sign-up week</th>
                <th className="p-3">Learners</th>
                <th className="p-3">Finished first day</th>
                {days.map((day) => <th key={day} className="p-3">Day {day}</th>)}
                <th className="p-3">Days done / started</th>
                <th className="p-3">Median min / day</th>
                <th className="p-3">Story words / day</th>
                <th className="p-3">Own words / day</th>
                <th className="p-3">Unfinished days stopped after</th>
              </tr>
            </thead>
            <tbody>
              {report.cohorts.map((row) => (
                <React.Fragment key={row.week_start}>
                  <tr className="border-t border-[var(--app-paper-3)]">
                    <td className="p-3 font-mono text-xs">
                      <button
                        type="button"
                        aria-expanded={open === row.week_start}
                        onClick={() => setOpen(open === row.week_start ? null : row.week_start)}
                        className="underline"
                      >
                        {row.week_start}
                      </button>
                    </td>
                    <td className="p-3">{row.learners}</td>
                    <td className="p-3">{row.finished_first_day?.display ?? '·'}</td>
                    {days.map((day) => <td key={day} className="p-3">{row.returns[`d${day}`]?.display ?? '·'}</td>)}
                    <td className="p-3">{row.days_completed} of {row.days_started}</td>
                    <td className="p-3">{minutes(row.median_active_minutes)}</td>
                    <td className="p-3">{minutes(row.median_story_words)}</td>
                    <td className="p-3">{minutes(row.median_own_words)}</td>
                    <td className="p-3">
                      {row.stops.length ? row.stops.map((stop) => `${stop.after_step} (${stop.days})`).join(', ') : 'none'}
                    </td>
                  </tr>
                  {open === row.week_start && row.learner_rows.map((learner) => (
                    <tr key={learner.user_id} className="border-t border-dotted border-[var(--app-paper-3)] text-xs text-[var(--app-ink-2)]">
                      <td className="p-3 pl-6 font-mono">{learner.signup_date}</td>
                      <td className="p-3">{learner.email}{learner.synthetic ? ' (synthetic)' : ''}</td>
                      <td className="p-3">{returnMark(learner.finished_first_day)}</td>
                      {days.map((day) => <td key={day} className="p-3">{returnMark(learner.returns[`d${day}`])}</td>)}
                      <td className="p-3">{learner.days_completed} of {learner.days_started}</td>
                      <td className="p-3">{minutes(learner.median_active_minutes)}</td>
                      <td className="p-3">{minutes(learner.median_story_words)}</td>
                      <td className="p-3">{minutes(learner.median_own_words)}</td>
                      <td className="p-3">{learner.stops.map((stop) => `${stop.date}: ${stop.after_step}`).join(', ') || 'none'}</td>
                    </tr>
                  ))}
                </React.Fragment>
              ))}
              {report.cohorts.length === 0 && (
                <tr><td className="p-5 text-[var(--app-ink-3)]" colSpan={days.length + 8}>No sign-ups in the last {report.weeks} weeks.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
