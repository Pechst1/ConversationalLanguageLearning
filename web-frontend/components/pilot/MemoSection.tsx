import React from 'react';

import apiService from '@/services/api';

export type MemoRow = {
  id: string;
  surface: string;
  item: string;
  answer: string;
  outcome: string;
  edits: number;
  state: 'candidate' | 'confirmed';
  confirmation: string | null;
  hits: number;
  created_at: string | null;
  confirmed_at: string | null;
};

export type PilotMemos = { candidate: MemoRow[]; confirmed: MemoRow[] };

/**
 * Package V stage 4 · the memo of judged answers. A candidate is one model reading; a
 * confirmed memo was agreed by a second, independent reading and settles the same answer
 * with no model call. Revoking one takes back every answer it settled. Page tokens only.
 */
export function MemoSection() {
  const [memos, setMemos] = React.useState<PilotMemos | null>(null);
  const [error, setError] = React.useState('');
  const [busy, setBusy] = React.useState<string | null>(null);

  const load = React.useCallback(() => {
    apiService.get<PilotMemos>('/analytics/pilot-memos')
      .then((result) => { setMemos(result ?? null); setError(''); })
      .catch(() => setError('The memos could not be loaded.'));
  }, []);
  React.useEffect(load, [load]);

  const revoke = (memo: MemoRow) => {
    if (typeof window !== 'undefined' && !window.confirm(`Revoke «${memo.answer}»? Every answer it settled (${memo.hits}) is taken back.`)) return;
    setBusy(memo.id);
    apiService.post(`/analytics/pilot-memos/${memo.id}/revoke`, { reason: 'revoked on pilot-ops' })
      .then(load)
      .catch(() => setError('The memo could not be revoked.'))
      .finally(() => setBusy(null));
  };

  return (
    <section className="mt-8 border border-[var(--app-ink)] bg-[var(--app-sheet)]" aria-labelledby="pilot-memos" data-section="pilot-memos">
      <div className="border-b border-[var(--app-ink)] p-4">
        <div className="font-mono text-[10px] font-black uppercase tracking-wider text-[var(--app-blue)]">Judge</div>
        <h2 id="pilot-memos" className="mt-1 font-serif text-3xl italic">Remembered answers</h2>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--app-ink-2)]">
          A confirmed answer is settled without a model call, the same way for every learner. Revoke one that is wrong.
        </p>
      </div>
      {error && <div role="alert" className="p-4 font-bold text-[var(--app-red)]">{error}</div>}
      {!memos && !error && <div className="p-4 font-mono text-xs uppercase tracking-widest">Loading the memos…</div>}
      {memos && (['confirmed', 'candidate'] as const).map((state) => (
        <div key={state} className="overflow-x-auto border-t border-[var(--app-paper-3)]">
          <div className="px-4 pt-4 font-mono text-[10px] font-black uppercase tracking-wider text-[var(--app-ink-3)]">
            {state === 'confirmed' ? 'Confirmed' : 'Candidates'} · {memos[state].length}
          </div>
          <table className="w-full min-w-[620px] border-collapse text-left text-sm">
            <thead className="font-mono text-[10px] uppercase tracking-wider text-[var(--app-ink-3)]">
              <tr>
                <th className="p-3">Surface</th><th className="p-3">Item</th><th className="p-3">Answer</th>
                <th className="p-3">Verdict</th><th className="p-3">Check</th><th className="p-3 text-right">Settled</th>
                {state === 'confirmed' && <th className="p-3" />}
              </tr>
            </thead>
            <tbody>
              {memos[state].map((memo) => (
                <tr key={memo.id} className="border-t border-[var(--app-paper-3)]" data-memo={memo.id}>
                  <td className="p-3 font-mono text-xs">{memo.surface}</td>
                  <td className="p-3 text-xs">{memo.item}</td>
                  <td className="p-3" lang="fr">{memo.answer}</td>
                  <td className="p-3">{memo.outcome}{memo.edits ? ` · ${memo.edits} edits` : ''}</td>
                  <td className="p-3 font-mono text-xs">{memo.confirmation ?? '·'}</td>
                  <td className="p-3 text-right font-black">{memo.hits}</td>
                  {state === 'confirmed' && (
                    <td className="p-3 text-right">
                      <button
                        type="button"
                        className="border border-[var(--app-red)] px-2 py-1 text-xs font-bold text-[var(--app-red)] disabled:opacity-50"
                        disabled={busy === memo.id}
                        onClick={() => revoke(memo)}
                      >
                        Revoke
                      </button>
                    </td>
                  )}
                </tr>
              ))}
              {memos[state].length === 0 && (
                <tr><td className="p-4 text-[var(--app-ink-3)]" colSpan={7}>None.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      ))}
    </section>
  );
}
