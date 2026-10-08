import React from 'react';

import {
  ALL_BANDS,
  distributionLabel,
  forgeBands,
  forgeSectionFor,
  latencyOverTarget,
  localTargetMs,
  numberLabel,
  rateLabel,
  rungLabel,
  type PilotForge,
} from '@/lib/forge-metrics';

/**
 * WP-S8 «La Forge» on the pilot control room: per-rule speed, séance health and
 * latency per rung, over the last 7 or 30 days, for every learner or one band.
 * Drawn with the page's own tokens (ink, paper, sheet, red, blue) and its own
 * type — no new font, no new colour.
 */
export function ForgeMetricsSection({ report, loadError }: { report: PilotForge | null; loadError: string }) {
  const [days, setDays] = React.useState(7);
  const [band, setBand] = React.useState(ALL_BANDS);
  const bands = forgeBands(report, days);
  const section = forgeSectionFor(report, days, bands.includes(band) ? band : ALL_BANDS);

  return (
    <section className="mt-8 border border-[var(--app-ink)] bg-[var(--app-sheet)]" aria-labelledby="pilot-forge">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--app-ink)] p-4">
        <div>
          <div className="font-mono text-[10px] font-black uppercase tracking-wider text-[var(--app-red)]">La Forge</div>
          <h2 id="pilot-forge" className="mt-1 font-serif text-3xl italic">How fast is a rule held?</h2>
        </div>
        <div className="flex flex-wrap gap-2" role="group" aria-label="Window and band">
          {[7, 30].map((value) => (
            <button
              key={value}
              type="button"
              aria-pressed={days === value}
              onClick={() => setDays(value)}
              className={`border px-3 py-1 font-mono text-[10px] font-black uppercase tracking-wider ${
                days === value ? 'border-[var(--app-ink)] bg-[var(--app-ink)] text-[var(--app-paper)]' : 'border-[var(--app-ink)]'
              }`}
            >
              {value} days
            </button>
          ))}
          {[ALL_BANDS, ...bands].map((value) => (
            <button
              key={value}
              type="button"
              aria-pressed={band === value}
              onClick={() => setBand(value)}
              className={`border px-3 py-1 font-mono text-[10px] font-black uppercase tracking-wider ${
                band === value ? 'border-[var(--app-blue)] text-[var(--app-blue)]' : 'border-[var(--app-paper-3)]'
              }`}
            >
              {value === ALL_BANDS ? 'All bands' : value}
            </button>
          ))}
        </div>
      </div>

      {loadError && <p className="p-4 text-sm text-[var(--app-red)]">{loadError}</p>}
      {!report && !loadError && <p className="p-4 text-sm text-[var(--app-ink-3)]">Loading the forge…</p>}
      {report && !section && <p className="p-4 text-sm text-[var(--app-ink-3)]">No forge activity in this window.</p>}

      {section && (
        <div className="p-4">
          <p className="mb-4 text-xs text-[var(--app-ink-3)]">
            {section.learners} {section.learners === 1 ? 'learner' : 'learners'} · last {days} days. Medians over the rules
            that reached the stage in this window; a rule held by a test-out is counted in the test-out rate, not in the speed.
          </p>

          <div className="grid gap-4 md:grid-cols-2">
            <article className="border border-[var(--app-paper-3)] p-4">
              <h3 className="font-mono text-[10px] font-black uppercase tracking-wider text-[var(--app-ink-3)]">Per rule</h3>
              <dl className="mt-2 space-y-2 text-sm">
                <Row label="Items to proficient (rung ≥ produce)" value={distributionLabel(section.rules.items_to_proficient)} />
                <Row label="Items to held" value={distributionLabel(section.rules.items_to_held)} />
                <Row label="Days to held" value={distributionLabel(section.rules.days_to_held, ' d')} />
                <Row
                  label={`Lapse after held (n = ${section.rules.lapse_after_held.returned} returned)`}
                  value={rateLabel(section.rules.lapse_after_held.rate)}
                />
                <Row
                  label={`Test-out passed (${section.rules.test_out.passed} of ${section.rules.test_out.finished})`}
                  value={rateLabel(section.rules.test_out.pass_rate)}
                />
              </dl>
            </article>

            <article className="border border-[var(--app-paper-3)] p-4">
              <h3 className="font-mono text-[10px] font-black uppercase tracking-wider text-[var(--app-ink-3)]">
                Per séance (n = {section.seances.started} started)
              </h3>
              <dl className="mt-2 space-y-2 text-sm">
                <Row label={`Completed (${section.seances.completed})`} value={rateLabel(section.seances.completion_rate)} />
                <Row label={`Abandoned (${section.seances.abandoned})`} value={rateLabel(section.seances.abandon_rate)} />
                <Row label="Still open" value={String(section.seances.still_open)} />
                <Row label="Active minutes, completed" value={distributionLabel(section.seances.active_minutes, ' min')} />
                <Row label="Items, completed (median)" value={numberLabel(section.seances.items.median)} />
              </dl>
              {Object.keys(section.seances.abandon_reasons).length > 0 && (
                <div className="mt-3 flex flex-wrap gap-2">
                  {Object.entries(section.seances.abandon_reasons).map(([reason, count]) => (
                    <span key={reason} className="border border-[var(--app-ink)] px-2 py-1 text-xs font-bold">{reason} · {count}</span>
                  ))}
                </div>
              )}
            </article>
          </div>

          <div className="mt-4 overflow-x-auto border border-[var(--app-paper-3)]">
            <table className="w-full min-w-[560px] border-collapse text-left text-sm">
              <caption className="p-3 text-left font-mono text-[10px] font-black uppercase tracking-wider text-[var(--app-ink-3)]">
                Check → verdict latency per rung (target p95: 300 ms keyed, 500 ms free production)
              </caption>
              <thead className="font-mono text-[10px] uppercase tracking-wider text-[var(--app-ink-3)]">
                <tr>
                  <th className="p-3">Rung</th><th className="p-3">n</th><th className="p-3">Local p50 / p95</th>
                  <th className="p-3">Second check p50 / p95</th><th className="p-3 text-right">Verdict changed</th>
                </tr>
              </thead>
              <tbody>
                {section.latency.by_rung.map((row) => (
                  <tr key={row.rung} className="border-t border-[var(--app-paper-3)]">
                    <td className="p-3">{rungLabel(row.rung)}</td>
                    <td className="p-3">{row.n}</td>
                    <td className={`p-3 font-black ${latencyOverTarget(row) ? 'text-[var(--app-red)]' : ''}`}>
                      {numberLabel(row.local_p50_ms, ' ms')} / {numberLabel(row.local_p95_ms, ' ms')}
                      {latencyOverTarget(row) && <span className="sr-only"> over the {localTargetMs(row.rung)} ms target</span>}
                    </td>
                    <td className="p-3">
                      {row.async_n ? `${numberLabel(row.async_p50_ms, ' ms')} / ${numberLabel(row.async_p95_ms, ' ms')}` : '—'}
                    </td>
                    <td className="p-3 text-right">{row.async_n ? `${row.verdict_changed} of ${row.async_n}` : '—'}</td>
                  </tr>
                ))}
                {section.latency.by_rung.length === 0 && (
                  <tr><td className="p-4 text-[var(--app-ink-3)]" colSpan={5}>No verdicts recorded in this window.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-3 border-t border-[var(--app-paper-3)] pt-2">
      <dt className="text-[var(--app-ink-3)]">{label}</dt>
      <dd className="text-right font-black">{value}</dd>
    </div>
  );
}
