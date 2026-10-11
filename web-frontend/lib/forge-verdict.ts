/**
 * WP-103 T9 — La Forge's free production: «Je relis…», and a verdict is never
 * reversed.
 *
 * The owner's test: «Right / Well done!», then ten seconds later «3
 * corrections». The instant local check was shown as a verdict before the model
 * had read the line. The rule that comes out of it:
 *
 *   * Locally, only an exact (or normalised) match to an accepted answer may say
 *     «Right» — the server marks that with `local_status: "right"`.
 *   * Anything else is not a verdict yet: the grading character's face says
 *     «Je relis…» until the model's verdict arrives.
 *   * A verdict shown is final. The server never contradicts a shown «right»,
 *     and if a payload ever does, the device keeps what the learner was shown.
 *
 * Read defensively: an older server sends no `local_status`; its provisional
 * verdict is then treated as unchecked (the safe side: «Je relis…», never a
 * «Right» that may flip).
 */

export type ProductionPhase =
  /** A provisional verdict that is a real match: shown as «Right», final. */
  | 'right'
  /** The model has not read it: no verdict yet, «Je relis…». */
  | 'checking'
  /** The model could not read it (failed): the answer is saved, not checked. */
  | 'unavailable'
  /** A checked verdict: show it. */
  | 'settled';

export type LocalStatus = 'right' | 'checking';

/** The server's local verdict: on the correction, or on its forge block. */
export function localStatusOf(correction: Record<string, any> | null | undefined): LocalStatus | null {
  const raw = correction?.local_status ?? correction?.forge?.local_status;
  return raw === 'right' || raw === 'checking' ? raw : null;
}

const PENDING = ['pending', 'queued', 'reviewing'];
const FAILED = ['failed', 'error'];

export function productionPhase(correction: Record<string, any> | null | undefined): ProductionPhase {
  if (!correction) return 'settled';
  const provisional = correction.assessment_status === 'provisional';
  const status = String(correction.ai_review?.status || '');
  if (!provisional) {
    // A checked verdict is settled; an unchecked one still waiting on the model is not.
    if (correction.assessment_status === 'checked') return 'settled';
    return PENDING.includes(status) ? 'checking' : 'settled';
  }
  if (localStatusOf(correction) === 'right') return 'right';
  if (FAILED.includes(status)) return 'unavailable';
  return 'checking';
}

/** True while the model's verdict is still to come (the poll keeps asking). */
export function reviewIsPending(correction: Record<string, any> | null | undefined): boolean {
  if (!correction) return false;
  if (PENDING.includes(String(correction.ai_review?.status || ''))) return true;
  return productionPhase(correction) === 'checking';
}

function verdictIsRight(correction: Record<string, any>): boolean {
  if (!['correct', 'accepted'].includes(String(correction.verdict || ''))) return false;
  const errata: any[] = Array.isArray(correction.errata) ? correction.errata : [];
  const lacking = Array.isArray(correction.missing_targets) ? correction.missing_targets : [];
  const gaps = Array.isArray(correction.lexical_gaps) ? correction.lexical_gaps : [];
  return !errata.length && !lacking.length && !gaps.length;
}

/**
 * The correction to show once a newer one has arrived: the newer one — unless
 * the learner was already shown «Right», in which case what they were shown
 * stands (the model's late reading is kept for the record, not for the screen).
 */
export function settleShownCorrection(
  previous: Record<string, any> | null | undefined,
  next: Record<string, any>,
): Record<string, any> {
  if (!previous) return next;
  // Once frozen, it stays frozen: every later arrival is the same late reading.
  if (previous.verdict_frozen) return previous;
  if (productionPhase(previous) !== 'right') return next;
  if (productionPhase(next) === 'right' || verdictIsRight(next)) return next;
  return {
    ...previous,
    // The poll can stop: the answer is settled as it was shown.
    assessment_status: 'checked',
    ai_review: { ...(previous.ai_review || {}), ...(next.ai_review || {}), status: 'complete' },
    second_check: undefined,
    verdict_frozen: true,
  };
}

/** Whether the answer shown now is a verdict (`right`, `settled`) or a wait. */
export function showsVerdict(phase: ProductionPhase): boolean {
  return phase === 'right' || phase === 'settled';
}
