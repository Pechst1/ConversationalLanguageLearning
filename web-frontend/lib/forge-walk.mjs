// What the browser walk (e2e/lib/learner-walk.mjs) knows about La Forge, kept out of the
// walk so the unit tests can run it and scripts/loop/red_green.py can prove it:
//
// - the selectors with which the walk answers each La Forge step, checked against the
//   components that render them by components/epreuve/forge-word-bank-walk.test.js;
// - the decision whether a visit to La Forge that stopped changing has ended or is stuck.
//
// Plain ES module with no imports: the walk runs under bare node.

/**
 * La Forge «Copy the correction»: after a miss on a whole line the way on is the corrected
 * line, retyped, then «Compare» (components/epreuve/Epreuve.tsx EpRepair); «Continue»
 * waits for it. The correction to copy is the line printed in the card above (EpLineFix).
 */
export const FORGE_REPAIR = {
  open: '.ep-repair:not([data-status="ok"])',
  field: 'input.ep-repair__input:not([disabled])',
  submit: 'button.ep-repair__submit:not([disabled])',
  correction: '.ep-galley .ep-linefix__new',
};

/**
 * La Forge «Trouve l'erreur» / «Ta phrase» (components/epreuve/ForgeDrills.tsx ForgeSpot):
 * the sentence's words are buttons; a tapped word opens in a field that holds it,
 * selected, and what is typed replaces it.
 */
export const FORGE_SPOT = {
  word: 'button.forge-spot__word:not([disabled])',
  edited: 'button.forge-spot__word[data-edited="true"]',
  field: 'input.forge-spot__input',
};

/**
 * La Forge «Correct the sentence» (components/epreuve/ForgeFollowUp.tsx): after a right
 * «Needs fixing» the learner corrects the sentence, with tiles (A1) or in a field, and
 * checks it with the follow-up's own button; the verdict sheet and its «Continue» wait
 * for it.
 */
export const FORGE_FOLLOW = {
  open: '.ep-follow[data-outcome="open"]',
  quote: '.ep-follow__quote',
  field: 'textarea.ep-follow__input',
  check: '.ep-follow__actions button.ep-bar:not([disabled])',
};

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
