// What the browser walk (e2e/lib/learner-walk.mjs) decides about a visit to La Forge, kept
// out of the walk so the unit tests can run it and scripts/loop/red_green.py can prove it:
// whether a visit that stopped changing has ended or is stuck. (The selectors with which
// the walk answers each La Forge step stay in e2e/lib/driver.mjs, as on main.)
//
// Plain ES module with no imports: the walk runs under bare node.

/** Quarter-seconds of an unchanged screen after which a visit to La Forge counts as over (10 s). */
export const FORGE_VISIT_QUIET = 40;

/**
 * A walk's visit to La Forge (`/atelier?mode=forge`) has no recap to reach; it ends when the
 * screen stops changing. That is a good end when the séance has nothing left, and a stall when
 * the screen is a La Forge exercise the walk had no way past (it used to end both the same,
 * silently, and the unanswerable step turned up days later in a grammar step).
 *
 * @param {{forgeExercise?: boolean, pending?: boolean, text?: string}} screen a driver snapshot
 * @param {number} quiet quarter-seconds the screen has not changed
 * @returns {null | {stalled: boolean, detail: string}} null while the visit goes on
 */
export function forgeVisitEnd(screen, quiet) {
  if (quiet <= FORGE_VISIT_QUIET) return null;
  // An exercise the server is still working on (pending) is waiting, not stuck.
  const stalled = Boolean(screen.forgeExercise) && !screen.pending;
  const text = (screen.text || '').slice(0, 140);
  return { stalled, detail: `stuck for ${(quiet * 0.25).toFixed(0)}s on «${text}»` };
}
