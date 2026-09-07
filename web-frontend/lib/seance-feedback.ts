/** Server assessment is authoritative; an empty error list is not a pass. */
export function seanceAssessment(correction: Record<string, any> | null): 'correct' | 'needs_work' | 'unavailable' | 'pending' {
  if (!correction) return 'pending';
  const status = correction.ai_review?.status;
  const checked = correction.assessment_status === 'checked';
  if (!checked && ['pending', 'queued', 'reviewing'].includes(status)) return 'pending';
  const legacyUnchecked = typeof correction.corrected_answer === 'string' && correction.correction_debug?.fallback_used;
  if (correction.assessment_status === 'unavailable' || legacyUnchecked || (!checked && ['failed', 'error'].includes(status))) return 'unavailable';
  if (!['correct', 'accepted'].includes(correction.verdict)) return 'needs_work';
  if (correction.errata?.length || correction.missing_targets?.length || correction.lexical_gaps?.length) return 'needs_work';
  return 'correct';
}
