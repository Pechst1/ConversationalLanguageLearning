import Head from 'next/head';
import Link from 'next/link';
import React from 'react';
import { AlertTriangle, ArrowLeft, CircleDollarSign, ShieldCheck } from 'lucide-react';

import apiService from '@/services/api';

type CostRow = {
  user_id: string;
  user_email?: string | null;
  week_start: string;
  scene_count: number;
  episode_count: number;
  total_usd: number;
};

type JourneyLedger = {
  day: string;
  sample: {
    journeys: number;
    learners: number;
    events: number;
    minimum_for_rates: number;
    insufficient_data: boolean;
  };
  funnel: {
    denominator: number;
    created: number;
    started: number;
    completed: number;
    ended_early: number;
    still_open: number;
    completion_rate: number | null;
    early_stop_rate: number | null;
  };
  step_drop_off: {
    denominator: number;
    by_ordinal: Array<{ ordinal: number; journeys_completing_step: number; share_of_started: number | null }>;
    by_kind: Record<string, number>;
  };
  help: { denominator: number; events: number; journeys_using_help: number; by_kind: Record<string, number> };
  active_duration: {
    denominator: number;
    measured: number;
    unmeasurable: number;
    seconds: { min: number | null; p50: number | null; p90: number | null; max: number | null };
    idle_excluded_seconds: number;
    away_excluded_seconds: number;
  };
  provider_wait: {
    events_with_measurement: number;
    events_without_measurement: number;
    total_seconds: number;
    median_ms: number | null;
    preparation_seconds: number;
  };
  reliability: {
    denominator: number;
    duplicate_requests_collapsed: number;
    generation_fallbacks: number;
    provider_failures: number;
    resume_conflicts: number;
  };
  cost: {
    events_with_known_cost: number;
    events_with_unknown_cost: number;
    known_cost_usd: number;
    coverage: number | null;
  };
};

type PilotDaily = { day: string; journey: JourneyLedger };

type PilotOperations = {
  window: { weeks: number; start_date: string; end_date: string };
  costs: {
    total_usd: number;
    tracked_learners: number;
    average_usd_per_tracked_learner: number;
    weekly_guardrail_usd_per_learner: number;
    rows_over_guardrail: number;
    weekly_rows: CostRow[];
  };
  content_health: {
    active_exercise_sets: number;
    retired_exercise_sets: number;
    atelier_quality_reports: number;
    feedback_reports: number;
    feedback_by_category: Record<string, number>;
  };
  generation: { serial_scenes: number };
};

function money(value: number) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(value || 0);
}

/** A rate the server declined to compute stays "n/a"; it never renders as 0%. */
function share(value: number | null) {
  return value === null || value === undefined ? 'n/a' : `${Math.round(value * 100)}%`;
}

function secondsLabel(value: number | null) {
  return value === null || value === undefined ? 'unknown' : `${value}s`;
}

export default function PilotOperationsPage() {
  const [data, setData] = React.useState<PilotOperations | null>(null);
  const [journey, setJourney] = React.useState<JourneyLedger | null>(null);
  const [journeyError, setJourneyError] = React.useState('');
  const [error, setError] = React.useState('');

  React.useEffect(() => {
    let alive = true;
    apiService.getPilotOperations(4)
      .then((result) => {
        if (alive) setData(result as PilotOperations);
      })
      .catch((requestError: any) => {
        if (!alive) return;
        setError(requestError?.response?.status === 403
          ? 'This dashboard is restricted to pilot administrators.'
          : 'Pilot operations data could not be loaded.');
      });
    // The daily-journey ledger is a separate day-scoped report; a failure here
    // must not blank the cost guardrails above.
    apiService.get<PilotDaily>('/analytics/pilot-daily')
      .then((result) => {
        if (alive) setJourney(result?.journey ?? null);
      })
      .catch(() => {
        if (alive) setJourneyError('The daily-journey ledger could not be loaded.');
      });
    return () => { alive = false; };
  }, []);

  return (
    <>
      <Head><title>Pilot operations · Feuilleton</title></Head>
      <main className="min-h-screen bg-[var(--app-paper)] px-4 py-6 pb-24 text-[var(--app-ink)]">
        <div className="mx-auto max-w-5xl">
          <Link href="/settings" className="inline-flex items-center gap-2 text-xs font-black uppercase tracking-[0.12em]">
            <ArrowLeft size={15} /> Settings
          </Link>
          <header className="mt-5 border-b-4 border-double border-[var(--app-ink)] pb-5">
            <div className="text-xs font-black uppercase tracking-[0.18em] text-[var(--app-red)]">Pilot control room</div>
            <h1 className="mt-1 font-serif text-5xl italic">Cost & content health</h1>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-[var(--app-ink-2)]">
              The two guardrails that decide whether the first test period is sustainable and trustworthy.
            </p>
          </header>

          {error && <div role="alert" className="mt-6 border-2 border-[var(--app-red)] p-4 font-bold text-[var(--app-red)]">{error}</div>}
          {!data && !error && <div className="mt-8 font-mono text-sm font-black uppercase tracking-widest">Loading the ledger…</div>}

          {data && (
            <>
              <section className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <Metric icon={CircleDollarSign} label="Generation spend" value={money(data.costs.total_usd)} />
                <Metric label="Avg / learner" value={money(data.costs.average_usd_per_tracked_learner)} />
                <Metric icon={ShieldCheck} label="Healthy exercise sets" value={String(data.content_health.active_exercise_sets)} />
                <Metric icon={AlertTriangle} label="Retired automatically" value={String(data.content_health.retired_exercise_sets)} />
              </section>

              <section className="mt-8 border border-[var(--app-ink)] bg-[var(--app-sheet)]">
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--app-ink)] p-4">
                  <h2 className="font-serif text-3xl italic">Weekly learner cost</h2>
                  <span className={`border px-3 py-1 font-mono text-[10px] font-black uppercase tracking-wider ${
                    data.costs.rows_over_guardrail ? 'border-[var(--app-red)] text-[var(--app-red)]' : 'border-[var(--app-blue)] text-[var(--app-blue)]'
                  }`}>
                    {data.costs.rows_over_guardrail
                      ? `${data.costs.rows_over_guardrail} over guardrail`
                      : `Within ${money(data.costs.weekly_guardrail_usd_per_learner)} guardrail`}
                  </span>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[620px] border-collapse text-left text-sm">
                    <thead className="font-mono text-[10px] uppercase tracking-wider text-[var(--app-ink-3)]">
                      <tr><th className="p-3">Week</th><th className="p-3">Learner</th><th className="p-3">Scenes</th><th className="p-3">Episodes</th><th className="p-3 text-right">Cost</th></tr>
                    </thead>
                    <tbody>
                      {data.costs.weekly_rows.map((row) => (
                        <tr key={`${row.user_id}:${row.week_start}`} className="border-t border-[var(--app-paper-3)]">
                          <td className="p-3 font-mono text-xs">{row.week_start}</td>
                          <td className="p-3">{row.user_email || row.user_id.slice(0, 8)}</td>
                          <td className="p-3">{row.scene_count}</td>
                          <td className="p-3">{row.episode_count}</td>
                          <td className="p-3 text-right font-black">{money(row.total_usd)}</td>
                        </tr>
                      ))}
                      {data.costs.weekly_rows.length === 0 && (
                        <tr><td className="p-5 text-[var(--app-ink-3)]" colSpan={5}>No generation spend recorded in this window.</td></tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </section>

              <section className="mt-8 grid gap-4 md:grid-cols-2">
                <article className="border border-[var(--app-ink)] bg-[var(--app-sheet)] p-5">
                  <div className="font-mono text-[10px] font-black uppercase tracking-wider text-[var(--app-blue)]">Quality flywheel</div>
                  <h2 className="mt-1 font-serif text-3xl italic">Generated exercise health</h2>
                  <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
                    <Health label="Learner reports" value={data.content_health.atelier_quality_reports} />
                    <Health label="Retired sets" value={data.content_health.retired_exercise_sets} />
                    <Health label="Active sets" value={data.content_health.active_exercise_sets} />
                    <Health label="Serial scenes" value={data.generation.serial_scenes} />
                  </dl>
                </article>
                <article className="border border-[var(--app-ink)] bg-[var(--app-sheet)] p-5">
                  <div className="font-mono text-[10px] font-black uppercase tracking-wider text-[var(--app-red)]">Pilot voice</div>
                  <h2 className="mt-1 font-serif text-3xl italic">Feedback reports</h2>
                  <p className="mt-3 text-4xl font-black">{data.content_health.feedback_reports}</p>
                  <div className="mt-4 flex flex-wrap gap-2">
                    {Object.entries(data.content_health.feedback_by_category).map(([label, count]) => (
                      <span key={label} className="border border-[var(--app-ink)] px-2 py-1 text-xs font-bold">{label} · {count}</span>
                    ))}
                  </div>
                </article>
              </section>

              <JourneySection ledger={journey} loadError={journeyError} />
            </>
          )}
        </div>
      </main>
    </>
  );
}

function JourneySection({ ledger, loadError }: { ledger: JourneyLedger | null; loadError: string }) {
  return (
    <section className="mt-8 border border-[var(--app-ink)] bg-[var(--app-sheet)]">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--app-ink)] p-4">
        <div>
          <div className="font-mono text-[10px] font-black uppercase tracking-wider text-[var(--app-blue)]">
            Daily journey {ledger ? `· ${ledger.day}` : ''}
          </div>
          <h2 className="mt-1 font-serif text-3xl italic">Did the five minutes actually happen?</h2>
        </div>
        {ledger && (
          <span className="border border-[var(--app-ink)] px-3 py-1 font-mono text-[10px] font-black uppercase tracking-wider">
            n = {ledger.funnel.started} started · {ledger.sample.learners} learners
          </span>
        )}
      </div>

      {loadError && <p className="p-4 text-sm text-[var(--app-red)]">{loadError}</p>}
      {!ledger && !loadError && <p className="p-4 text-sm text-[var(--app-ink-3)]">Loading the day…</p>}

      {ledger && (
        <div className="p-4">
          {ledger.sample.insufficient_data && (
            <p className="mb-4 border-2 border-[var(--app-ink)] p-3 text-sm">
              <strong>Insufficient data.</strong> {ledger.funnel.started} started {ledger.funnel.started === 1 ? 'journey' : 'journeys'}
              {' '}on this day; {ledger.sample.minimum_for_rates} are needed before a rate means anything. Raw counts are shown, rates are withheld.
            </p>
          )}

          <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Health label={`Started (of ${ledger.funnel.created} created)`} value={ledger.funnel.started} />
            <Health label={`Completed · ${share(ledger.funnel.completion_rate)}`} value={ledger.funnel.completed} />
            <Health label={`Ended early · ${share(ledger.funnel.early_stop_rate)}`} value={ledger.funnel.ended_early} />
            <Health label="Still open" value={ledger.funnel.still_open} />
          </dl>

          <div className="mt-6 grid gap-4 md:grid-cols-2">
            <article className="border border-[var(--app-paper-3)] p-4">
              <h3 className="font-mono text-[10px] font-black uppercase tracking-wider text-[var(--app-ink-3)]">
                Measured active seconds
              </h3>
              {ledger.active_duration.measured > 0 ? (
                <>
                  <p className="mt-2 text-3xl font-black">{secondsLabel(ledger.active_duration.seconds.p50)}</p>
                  <p className="mt-1 text-xs text-[var(--app-ink-3)]">
                    median · p90 {secondsLabel(ledger.active_duration.seconds.p90)} · max {secondsLabel(ledger.active_duration.seconds.max)}
                  </p>
                </>
              ) : (
                <p className="mt-2 text-sm">No journey on this day could be measured. Reported as unknown, not as zero.</p>
              )}
              <p className="mt-3 text-xs text-[var(--app-ink-3)]">
                measured {ledger.active_duration.measured}/{ledger.active_duration.denominator} finished ·
                {' '}{ledger.active_duration.unmeasurable} unmeasurable · idle excluded {ledger.active_duration.idle_excluded_seconds}s ·
                {' '}away {ledger.active_duration.away_excluded_seconds}s. Server-measured; client timings are diagnostic only.
              </p>
            </article>

            <article className="border border-[var(--app-paper-3)] p-4">
              <h3 className="font-mono text-[10px] font-black uppercase tracking-wider text-[var(--app-ink-3)]">
                Waiting on the provider
              </h3>
              <p className="mt-2 text-3xl font-black">{ledger.provider_wait.total_seconds}s</p>
              <p className="mt-1 text-xs text-[var(--app-ink-3)]">
                median {ledger.provider_wait.median_ms === null ? 'unknown' : `${ledger.provider_wait.median_ms}ms`} ·
                {' '}plan preparation {ledger.provider_wait.preparation_seconds}s ·
                {' '}{ledger.provider_wait.events_with_measurement} of{' '}
                {ledger.provider_wait.events_with_measurement + ledger.provider_wait.events_without_measurement} events measured
              </p>
              <p className="mt-3 text-xs text-[var(--app-ink-3)]">
                This time is subtracted from active seconds, so a slow model never reads as a slow learner.
              </p>
            </article>
          </div>

          <div className="mt-6 grid gap-4 md:grid-cols-3">
            <article className="border border-[var(--app-paper-3)] p-4">
              <h3 className="font-mono text-[10px] font-black uppercase tracking-wider text-[var(--app-ink-3)]">
                Step drop-off (n={ledger.step_drop_off.denominator})
              </h3>
              <ul className="mt-2 space-y-1 text-sm">
                {ledger.step_drop_off.by_ordinal.map((row) => (
                  <li key={row.ordinal} className="flex justify-between">
                    <span>Step {row.ordinal + 1}</span>
                    <span className="font-black">{row.journeys_completing_step} · {share(row.share_of_started)}</span>
                  </li>
                ))}
                {ledger.step_drop_off.by_ordinal.length === 0 && (
                  <li className="text-[var(--app-ink-3)]">No step completions recorded.</li>
                )}
              </ul>
            </article>

            <article className="border border-[var(--app-paper-3)] p-4">
              <h3 className="font-mono text-[10px] font-black uppercase tracking-wider text-[var(--app-ink-3)]">
                Help used (n={ledger.help.denominator})
              </h3>
              <p className="mt-2 text-3xl font-black">{ledger.help.events}</p>
              <p className="mt-1 text-xs text-[var(--app-ink-3)]">in {ledger.help.journeys_using_help} journeys</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {Object.entries(ledger.help.by_kind).map(([kind, count]) => (
                  <span key={kind} className="border border-[var(--app-ink)] px-2 py-1 text-xs font-bold">{kind} · {count}</span>
                ))}
              </div>
            </article>

            <article className="border border-[var(--app-paper-3)] p-4">
              <h3 className="font-mono text-[10px] font-black uppercase tracking-wider text-[var(--app-ink-3)]">
                Retries & failures (n={ledger.reliability.denominator})
              </h3>
              <dl className="mt-2 space-y-1 text-sm">
                <Line label="Duplicate requests collapsed" value={ledger.reliability.duplicate_requests_collapsed} />
                <Line label="Generation fallbacks" value={ledger.reliability.generation_fallbacks} />
                <Line label="Provider failures" value={ledger.reliability.provider_failures} />
                <Line label="Resume conflicts" value={ledger.reliability.resume_conflicts} />
              </dl>
            </article>
          </div>

          <p className="mt-6 border-t border-[var(--app-paper-3)] pt-3 text-xs text-[var(--app-ink-3)]">
            Cost coverage: {ledger.cost.events_with_known_cost} events with a known cost ({money(ledger.cost.known_cost_usd)}),
            {' '}{ledger.cost.events_with_unknown_cost} with none recorded ({share(ledger.cost.coverage)} coverage).
            An unknown cost is unknown, not zero.
          </p>
        </div>
      )}
    </section>
  );
}

function Line({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex justify-between gap-3">
      <dt className="text-[var(--app-ink-3)]">{label}</dt>
      <dd className="font-black">{value}</dd>
    </div>
  );
}

function Metric({ icon: Icon, label, value }: { icon?: React.ElementType; label: string; value: string }) {
  return (
    <div className="border-2 border-[var(--app-ink)] bg-[var(--app-sheet)] p-4">
      <div className="flex items-center gap-2 font-mono text-[10px] font-black uppercase tracking-wider text-[var(--app-ink-3)]">
        {Icon && <Icon size={15} />} {label}
      </div>
      <div className="mt-2 text-3xl font-black">{value}</div>
    </div>
  );
}

function Health({ label, value }: { label: string; value: number }) {
  return (
    <div className="border-t border-[var(--app-paper-3)] pt-2">
      <dt className="text-xs text-[var(--app-ink-3)]">{label}</dt>
      <dd className="mt-1 text-2xl font-black">{value}</dd>
    </div>
  );
}
