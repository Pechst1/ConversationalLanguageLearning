/** Server assessment is authoritative; an empty error list is not a pass. */
export function seanceAssessment(correction: Record<string, any> | null): 'correct' | 'needs_work' | 'unavailable' | 'pending' {
  if (!correction) return 'pending';
  const status = correction.ai_review?.status;
  // WP-S1: a provisional verdict (free production, graded locally while the
  // model's reading runs in the background) is shown at once — it never
  // blocks the learner behind a «pending» screen.
  const checked = correction.assessment_status === 'checked' || correction.assessment_status === 'provisional';
  if (!checked && ['pending', 'queued', 'reviewing'].includes(status)) return 'pending';
  const legacyUnchecked = typeof correction.corrected_answer === 'string' && correction.correction_debug?.fallback_used
    && correction.assessment_status !== 'provisional';
  if (correction.assessment_status === 'unavailable' || legacyUnchecked || (!checked && ['failed', 'error'].includes(status))) return 'unavailable';
  if (!['correct', 'accepted'].includes(correction.verdict)) return 'needs_work';
  if (correction.errata?.length || correction.missing_targets?.length || correction.lexical_gaps?.length) return 'needs_work';
  return 'correct';
}

/**
 * Does this correction settle the answer? Only a verdict the server has
 * checked does: a provisional local check (its model reading still running),
 * an unchecked answer and a pending one neither extend nor break the run.
 */
export function runOutcome(correction: Record<string, any> | null | undefined): 'extends' | 'breaks' | 'skips' {
  if (!correction) return 'skips';
  if (correction.assessment_status === 'provisional') return 'skips';
  const assessment = seanceAssessment(correction);
  if (assessment === 'unavailable' || assessment === 'pending') return 'skips';
  if (assessment === 'correct') return 'extends';
  // A task-compliance note alone (the line was fine, the task asked more) is
  // not a wrong answer; any other erratum is.
  const errata: any[] = Array.isArray(correction.errata) ? correction.errata : [];
  const substantive = errata.filter((item) => String(item?.task_error_type || '') !== 'task_compliance');
  if (!substantive.length && ['correct', 'accepted'].includes(correction.verdict)) return 'extends';
  return 'breaks';
}

/** The header's run of consecutive correct answers, newest last. */
export function correctRunFrom(corrections: Array<Record<string, any> | null | undefined>): number {
  let run = 0;
  for (let index = corrections.length - 1; index >= 0; index -= 1) {
    const outcome = runOutcome(corrections[index]);
    if (outcome === 'breaks') break;
    if (outcome === 'extends') run += 1;
  }
  return run;
}

/**
 * The quiet «second check» note: only when the model's reading, landing after
 * the local verdict, changed it. `better` when it now passes, `worse` when not.
 */
export function secondCheckChange(correction: Record<string, any> | null | undefined): 'better' | 'worse' | null {
  const check = correction?.second_check;
  if (!check || check.status !== 'complete' || !check.verdict_changed) return null;
  return ['correct', 'accepted'].includes(String(check.verdict || correction?.verdict || '')) ? 'better' : 'worse';
}
