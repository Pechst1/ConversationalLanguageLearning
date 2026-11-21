import React from 'react';

import apiService, { type FeedbackReport } from '@/services/api';

/** What a `looks_wrong` report from a verdict carries (see `looksWrongContext`). */
type LooksWrongContext = {
  surface?: string;
  step_kind?: string | null;
  outcome?: string | null;
  correction?: {
    kind?: string;
    span_fr?: string | null;
    corrected_fr?: string | null;
    notes_native?: string[];
  } | null;
  slip_note_native?: string | null;
};

function shownText(report: FeedbackReport): string {
  const context = (report.context_payload || {}) as LooksWrongContext;
  const parts: string[] = [];
  const correction = context.correction;
  if (correction?.span_fr || correction?.corrected_fr) {
    parts.push(`${correction.span_fr ?? '…'} → ${correction.corrected_fr ?? '…'}`);
  }
  for (const note of correction?.notes_native ?? []) parts.push(note);
  if (context.slip_note_native) parts.push(context.slip_note_native);
  if (report.message) parts.push(`Note: ${report.message}`);
  return parts.join(' · ') || 'No correction on screen (verdict only).';
}

/**
 * Beta: the learners' «Something here looks wrong» taps, newest first, with the exact text the
 * screen showed. The text stays here, behind the owner's role: the repository is public, so a
 * finding filed from a report names the report, never the learner's words.
 */
export function LearnerReportsSection() {
  const [reports, setReports] = React.useState<FeedbackReport[] | null>(null);
  const [loadError, setLoadError] = React.useState('');

  React.useEffect(() => {
    let alive = true;
    apiService.get<FeedbackReport[]>('/feedback/reports', { params: { category: 'looks_wrong', limit: 50 } })
      .then((result) => {
        if (alive) setReports(result ?? []);
      })
      .catch(() => {
        if (alive) setLoadError('The learner reports could not be loaded.');
      });
    return () => { alive = false; };
  }, []);

  return (
    <section className="mt-8 border border-[var(--app-ink)] bg-[var(--app-sheet)]" aria-labelledby="pilot-looks-wrong">
      <div className="border-b border-[var(--app-ink)] p-4">
        <div className="font-mono text-[10px] font-black uppercase tracking-wider text-[var(--app-blue)]">Learners</div>
        <h2 id="pilot-looks-wrong" className="mt-1 font-serif text-3xl italic">What looked wrong?</h2>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--app-ink-2)]">
          Every «Something here looks wrong» tap under a verdict, with what the screen showed. The nightly
          triage files each one as a finding that names the report id only.
        </p>
      </div>
      {loadError && <div role="alert" className="p-4 font-bold text-[var(--app-red)]">{loadError}</div>}
      {!reports && !loadError && <div className="p-4 font-mono text-xs font-black uppercase tracking-widest">Loading…</div>}
      {reports && reports.length === 0 && <p className="p-4 text-sm text-[var(--app-ink-3)]">No reports yet.</p>}
      {reports && reports.length > 0 && (
        <ul className="divide-y divide-[var(--app-paper-3)]">
          {reports.map((report) => {
            const context = (report.context_payload || {}) as LooksWrongContext;
            return (
              <li key={report.id} className="p-4 text-sm">
                <div className="font-mono text-[10px] uppercase tracking-wider text-[var(--app-ink-3)]">
                  {report.created_at.slice(0, 16).replace('T', ' ')} · {context.surface ?? report.screen ?? report.route}
                  {context.step_kind ? ` · ${context.step_kind}` : ''}
                  {context.outcome ? ` · ${context.outcome}` : ''} · {report.id.slice(0, 8)}
                </div>
                <p className="mt-1 leading-6">{shownText(report)}</p>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
