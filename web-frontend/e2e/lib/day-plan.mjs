// A day is played to its end: every step the day plan listed (`TodayEnvelope.session`,
// built in app/services/daily_session.py: scene, grammar, words, finish) was played, and
// the day ended at /fertig or at a recap the server's plan agreed was the last screen.
// Pure, so the node test can feed it the plans the walk meets.

/** «Suite : grammaire», «Weiter: 20 Wörter», «Next: grammar»: a step of the day handing on. */
export const HAND_ON = /^\s*(Suite\s?:|Weiter:|Next:)/;

/**
 * plan: the first session the day's page received; last: the latest; played: the step
 * kinds the walk was seen on; dayEnd: how the walk ended the day (null: it never did).
 * Returns { ok, detail }.
 */
export function dayPlanVerdict({ plan, last, played, dayEnd }) {
  if (!plan) return { ok: false, detail: 'the page never received a day plan (GET /daily-journeys/today with a session)' };
  const owed = plan.steps.filter((step) => step.state !== 'done').map((step) => step.kind);
  const missing = owed.filter((kind) => !played.has(kind));
  const problems = [];
  if (missing.length) problems.push(`not played: ${missing.join(', ')}`);
  if (!dayEnd) problems.push('the day never reached /fertig or its last recap');
  if (!last || !last.done) problems.push(`the server's plan is not done (next: ${last ? last.next_kind : 'unknown'})`);
  return {
    ok: problems.length === 0,
    detail: `${problems.join('; ')} — planned ${plan.steps.map((s) => `${s.kind}:${s.state}`).join(' > ')}; played ${[...played].join(', ') || 'nothing'}; ended ${dayEnd || 'nowhere'}`,
  };
}
