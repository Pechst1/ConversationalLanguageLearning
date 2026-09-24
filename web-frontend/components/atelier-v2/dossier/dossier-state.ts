/**
 * WP-35 «Votre dossier» — presentation-independent state.
 *
 * Every function is pure over the wire envelope, so the node suite exercises the
 * whole page with no DOM and the renderer carries no policy.
 *
 * Three rules that therefore live here rather than in the screen:
 *
 *  1. **A source is named, never implied.** «Niveau déclaré» and «niveau estimé
 *     (bilan)» are different sentences, and a declaration never gets a
 *     confidence — the server sends `confidence: null` for one, and nothing here
 *     invents a number to fill the gap.
 *  2. **An unknown `because.kind` prints nothing.** WP-24's rule: the server
 *     names the reason, the component writes the sentence, and a kind it has
 *     never heard of is silence rather than an invented one.
 *  3. **No journey means no line at all.** «Pas encore de scène aujourd'hui» is
 *     the honest sentence; a prospective "today's scene will pick up…" would be
 *     a promise the planner has not made.
 *
 * WP-82: every sentence is chrome, read from `dossier-copy.ts` in the chrome
 * language. Each function takes that language last and defaults to French, so
 * a caller that says nothing gets the page as it was.
 */

import type {
  DossierBecause,
  DossierCapability,
  DossierErratum,
  DossierEvidence,
  DossierLevel,
  DossierPayload,
  DossierToday,
  DossierVocabulary,
  DossierWord,
} from '@/services/api';
import type { ControlLanguage } from '@/types/daily-journey';

import { dayNumber, dossierCopy, fill, longDate, shortDate, type DossierCopy } from './dossier-copy';

export type DossierPhase =
  | { kind: 'loading' }
  /** `/state` itself failed. The model is simply unread. */
  | { kind: 'load_failed'; message: string }
  | { kind: 'ready'; dossier: DossierPayload };

/** The rubric's own vocabulary. Unknown states print as unknown.
 *  The wording is the 2026-09-15 artboard's (`Dossier.dc.html`). */
const CAPABILITY_STATE: Record<string, keyof DossierCopy> = {
  not_tried: 'cap_not_tried',
  with_support: 'cap_with_support',
  independent_once: 'cap_independent_once',
  used_again_later: 'cap_used_again_later',
  unknown: 'cap_unknown',
};

/** WP-24's three states, and nothing else. */
const ERRATUM_STATE: Record<string, keyof DossierCopy> = {
  open: 'err_open',
  repairing: 'err_repairing',
  mastered: 'err_mastered',
};

const LEVEL_SOURCE: Record<string, keyof DossierCopy> = {
  declared: 'src_declared',
  placement: 'src_placement',
  measured: 'src_measured',
};

/** WP-45. The counter labels on the artboard: an adjective, not a verdict. */
const ERRATUM_COUNTER: Record<string, keyof DossierCopy> = {
  open: 'counter_open',
  repairing: 'counter_repairing',
  mastered: 'counter_mastered',
};

export const ERRATUM_STATE_ORDER = ['open', 'repairing', 'mastered'] as const;

/* ---------------------------------------------------------------------------
   WP-45 additions.

   The wire types in `services/api.ts` predate the 2026-09-15 design; the three
   fields WP-45 added to `learner_model.py` are declared here as widenings
   rather than by editing a file this package does not own. Every one of them is
   optional, and every reader below falls back to what the page already had, so
   a server that has not shipped them yet renders the previous sentence rather
   than an empty slot.
   --------------------------------------------------------------------------- */

export type CapabilityWithFrenchTitle = DossierCapability & { title_fr?: string | null };
export type ErrataWithTotals = DossierPayload['errata'] & {
  totals?: Record<string, number> | null;
};
export type LevelWithAttempts = DossierLevel & {
  evidence_attempts_required?: number | null;
  evidence_attempts_counted?: number | null;
};

export function phaseFor(
  dossier: DossierPayload | null,
  options: { loading?: boolean; error?: string | null } = {},
): DossierPhase {
  if (options.loading) return { kind: 'loading' };
  if (options.error) return { kind: 'load_failed', message: options.error };
  if (!dossier) return { kind: 'loading' };
  return { kind: 'ready', dossier };
}

export function capabilityStateLabel(state: string, language: ControlLanguage = 'fr'): string {
  const copy = dossierCopy(language);
  return copy[CAPABILITY_STATE[state] ?? 'cap_unknown'];
}

export function errataStateLabel(state: string, language: ControlLanguage = 'fr'): string {
  const copy = dossierCopy(language);
  return copy[ERRATUM_STATE[state] ?? 'err_open'];
}

/** «Niveau estimé (bilan) · A2.1», or the honest absence of a level. */
export function levelSentence(level: DossierLevel | null | undefined, language: ControlLanguage = 'fr'): string {
  const copy = dossierCopy(language);
  if (!level || level.available === false || !level.estimate) return copy.level_none;
  const key = LEVEL_SOURCE[level.estimate_source ?? ''];
  const source = key ? copy[key] : copy.src_fallback;
  return `${source} · ${level.estimate}`;
}

/**
 * What stands behind the level, in one sentence.
 *
 * A declaration says it has verified nothing; a placement says how sure it is
 * and on how many answers; in-app counters say they are the app's own work.
 */
export function levelBasisSentence(level: DossierLevel | null | undefined, language: ControlLanguage = 'fr'): string {
  const copy = dossierCopy(language);
  if (!level || level.available === false) return copy.level_unreadable;
  if (level.estimate_source === 'declared') return copy.basis_declared;
  if (level.estimate_source === 'placement') {
    const turns = level.placement?.graded_turns ?? 0;
    const confidence = confidenceSentence(level.confidence, language);
    const answers = turns > 0 ? fill(copy.basis_answers, { n: turns }) : copy.basis_one_test;
    return fill(copy.basis_placement, { answers, confidence });
  }
  return copy.basis_measured;
}

/**
 * WP-45. The line beside the big serif level: where it came from, and whether
 * anything has checked it. Three sentences, one per `estimate_source`.
 */
export function levelSourceLine(level: DossierLevel | null | undefined, language: ControlLanguage = 'fr'): string {
  const copy = dossierCopy(language);
  if (!level || level.available === false || !level.estimate) return copy.source_none;
  if (level.estimate_source === 'declared') return copy.source_declared;
  if (level.estimate_source === 'placement') {
    return level.placement?.taken_at
      ? fill(copy.source_placement_dated, { date: shortDate(level.placement.taken_at, language) })
      : copy.source_placement;
  }
  return copy.source_measured;
}

/**
 * WP-45 (D-5). What would move the level, with the threshold the estimator
 * actually uses rather than a number retyped into the copy.
 */
export function levelLadderSentence(
  level: LevelWithAttempts | null | undefined,
  language: ControlLanguage = 'fr',
): string {
  const copy = dossierCopy(language);
  const required = Number(level?.evidence_attempts_required ?? 40);
  if (!level || level.available === false) return copy.level_unreadable;
  if (level.estimate_source === 'measured') {
    const counted = Number(level.evidence_attempts_counted ?? 0);
    return fill(copy.ladder_measured, { counted, required });
  }
  if (level.estimate_source === 'placement') {
    const turns = level.placement?.graded_turns ?? 0;
    const basis = turns > 0 ? fill(copy.ladder_basis_answers, { n: turns }) : copy.ladder_basis_one_test;
    return fill(copy.ladder_placement, { basis, required });
  }
  return fill(copy.ladder_declared, { required });
}

/* ---------------------------------------------------------------------------
   WP-L7 / WP-L8 — the level as coverage of a sub-band, its épreuve, and the
   forecast. Every number comes from the server (`coverage`, `checkpoint`,
   `forecast` on the level); nothing here computes a level.
   --------------------------------------------------------------------------- */

/** «A1.1 · 60 %» when the server sent the coverage, else the bare band. */
export function levelHeadline(level: DossierLevel | null | undefined): string | null {
  if (!level || level.available === false || !level.estimate) return null;
  return (level.level_label || '').trim() || level.estimate;
}

/** The Dossier's breakdown: units held, words known, the épreuve — each x / y. */
export function coverageRows(
  level: DossierLevel | null | undefined,
  language: ControlLanguage = 'fr',
): Array<{ key: string; label: string; value: string }> {
  const copy = dossierCopy(language);
  const coverage = level?.coverage;
  if (!level || level.available === false || !coverage) return [];
  const rows: Array<{ key: string; label: string; value: string }> = [];
  if (coverage.units && coverage.units.total > 0) {
    rows.push({
      key: 'units',
      label: copy.row_units,
      value: fill(copy.row_value, {
        have: coverage.units.held,
        required: coverage.units.required,
        total: coverage.units.total,
      }),
    });
  }
  if (coverage.words && coverage.words.total > 0) {
    rows.push({
      key: 'words',
      label: copy.row_words,
      value: fill(copy.row_value, {
        have: coverage.words.known,
        required: coverage.words.required,
        total: coverage.words.total,
      }),
    });
  }
  rows.push({ key: 'checkpoint', label: copy.row_checkpoint, value: checkpointLabel(level.checkpoint, language) });
  return rows;
}

/** What the numbers above mean — the rule, stated once. */
export function coverageRuleSentence(
  level: DossierLevel | null | undefined,
  language: ControlLanguage = 'fr',
): string | null {
  const coverage = level?.coverage;
  if (!coverage) return null;
  return fill(dossierCopy(language).coverage_rule, { band: coverage.band });
}

export function checkpointLabel(
  checkpoint: DossierLevel['checkpoint'],
  language: ControlLanguage = 'fr',
): string {
  const copy = dossierCopy(language);
  switch (checkpoint?.state) {
    case 'ready':
      return copy.cp_ready;
    case 'failed':
      return checkpoint.retry_after
        ? fill(copy.cp_failed_dated, { date: shortDate(checkpoint.retry_after, language) })
        : copy.cp_failed;
    case 'passed':
      return copy.cp_passed;
    case 'credited':
      return copy.cp_credited;
    default:
      return copy.cp_locked;
  }
}

function spanWords(
  days: number[] | undefined,
  months: number[] | undefined,
  copy: DossierCopy,
): string | null {
  if (!Array.isArray(days) || days.length < 2) return null;
  const [low, high] = days.map(Number);
  if (!Number.isFinite(low) || !Number.isFinite(high)) return null;
  if (high < 60 || !Array.isArray(months) || months.length < 2) {
    return low === high ? fill(copy.span_days, { n: low }) : fill(copy.span_days_range, { low, high });
  }
  const lowM = Math.max(1, Math.floor(Number(months[0])));
  const highM = Math.max(lowM, Math.ceil(Number(months[1])));
  return lowM === highM
    ? fill(copy.span_months, { n: lowM })
    : fill(copy.span_months_range, { low: lowM, high: highM });
}

/**
 * WP-L8. The forecast in one sentence, always as an estimate: the rhythm's
 * prior before seven active days, the learner's own pace after, and never a
 * date dressed as a promise.
 */
export function forecastSentence(
  level: DossierLevel | null | undefined,
  language: ControlLanguage = 'fr',
): string | null {
  const copy = dossierCopy(language);
  const forecast = level?.forecast;
  if (!level || level.available === false || !forecast) return null;
  const target = forecast.target || level.next_level;
  if (!target) return null;
  if (forecast.capped) return fill(copy.forecast_capped, { target });
  const span = spanWords(forecast.range_days, forecast.range_months, copy);
  if (!span) return null;
  if (forecast.status === 'prior') return fill(copy.forecast_prior, { target, span });
  return fill(copy.forecast_measured, { target, span });
}

/** The capability's name, from the French title the payload sends (content).
 *  Falls back, never invents. */
export function capabilityTitle(capability: CapabilityWithFrenchTitle): string {
  const french = (capability.title_fr || '').trim();
  return french || capability.title;
}

/**
 * The evidence reference on a capability row: «séance du 12 sept.», or
 * «séances des 12 et 14 sept.» for a capability that was refait un autre jour,
 * or an em dash when nothing has been observed. Never a date nobody recorded.
 */
export function capabilityEvidenceRef(capability: DossierCapability, language: ControlLanguage = 'fr'): string {
  const copy = dossierCopy(language);
  const days = Array.from(
    new Set((capability.evidence || []).map((item) => item.on).filter(Boolean)),
  ).sort();
  if (days.length === 0) return '—';
  if (capability.state === 'used_again_later' && days.length >= 2) {
    const first = days[0] as string;
    const last = days[days.length - 1] as string;
    // The month is printed once when both fall in it, and twice when they do
    // not — «des 30 août et 2 sept.» is a fortnight, «des 12 et 14 sept.» is
    // two days, and collapsing the second into the first would say the wrong
    // thing about how far apart the two uses were.
    const sameMonth = first.slice(0, 7) === last.slice(0, 7);
    return fill(copy.evref_two, {
      first: sameMonth ? dayNumber(first, language) : shortDate(first, language),
      last: shortDate(last, language),
    });
  }
  return fill(copy.evref_one, { date: shortDate(days[days.length - 1] as string, language) });
}

/** The three counters, in the artboard's order, from the true totals. */
export function errataCounters(
  errata: ErrataWithTotals | null | undefined,
  language: ControlLanguage = 'fr',
): Array<{ state: string; count: number; label: string }> {
  const copy = dossierCopy(language);
  // `totals` counts every erratum; `counts` counts only the rows this payload
  // carries, which stops at ERRATA_PER_STATE. Prefer the former, and say the
  // latter rather than nothing when an older server sends no totals.
  const source = errata?.totals ?? errata?.counts ?? {};
  return ERRATUM_STATE_ORDER.map((state) => ({
    state,
    count: Number(source[state] ?? 0),
    label: copy[ERRATUM_COUNTER[state]],
  }));
}

/** «6 fautes notées en tout.» — the denominator the three counters divide. */
export function errataTotalSentence(
  errata: ErrataWithTotals | null | undefined,
  language: ControlLanguage = 'fr',
): string {
  const copy = dossierCopy(language);
  const total = errataCounters(errata, language).reduce((sum, item) => sum + item.count, 0);
  if (total === 0) return copy.errata_total_none;
  if (total === 1) return copy.errata_total_one;
  return fill(copy.errata_total_many, { n: total });
}

/**
 * WP-45. The vocabulary block as the artboard draws it: one big number, then a
 * sentence that gives it both a unit and its two halves.
 */
export function vocabularyCount(vocabulary: DossierVocabulary | null | undefined): number | null {
  const known = vocabulary?.known;
  return known ? Number(known.known_lemmas) : null;
}

export function vocabularyUnitSentence(
  vocabulary: DossierVocabulary | null | undefined,
  language: ControlLanguage = 'fr',
): string {
  const copy = dossierCopy(language);
  const known = vocabulary?.known;
  if (!known) return copy.vocab_unreadable;
  const acquired = fill(copy.vocab_acquired, { n: Number(known.nailed_words) });
  return fill(copy.vocab_unit, { acquired });
}

/** Confidence as words. A missing confidence is said, never drawn as zero. */
export function confidenceSentence(
  confidence: number | null | undefined,
  language: ControlLanguage = 'fr',
): string {
  const copy = dossierCopy(language);
  if (confidence === null || confidence === undefined) return copy.confidence_none;
  const percent = Math.round(confidence * 100);
  if (confidence >= 0.7) return fill(copy.confidence_high, { percent });
  if (confidence >= 0.45) return fill(copy.confidence_medium, { percent });
  return fill(copy.confidence_low, { percent });
}

/** «Vérifié dans l'application» vs «pas encore vérifié». */
export function verifiedSentence(level: DossierLevel | null | undefined, language: ControlLanguage = 'fr'): string {
  const copy = dossierCopy(language);
  return level?.verified ? copy.verified_yes : copy.verified_no;
}

/** One dated line per number: «Séance du 5 septembre», «Bilan du 10 septembre». */
export function evidenceSentence(
  evidence: DossierEvidence | null | undefined,
  language: ControlLanguage = 'fr',
): string | null {
  if (!evidence) return null;
  const copy = dossierCopy(language);
  const when = evidence.on ? longDate(evidence.on, language) : null;
  const dated = (withDate: string, without: string) => (when ? fill(withDate, { date: when }) : without);
  switch (evidence.kind) {
    case 'journey':
      return dated(copy.ev_journey_dated, copy.ev_journey);
    case 'placement':
      return dated(copy.ev_placement_dated, copy.ev_placement);
    case 'declaration':
      return dated(copy.ev_declaration_dated, copy.ev_declaration);
    case 'in_app_counters':
      return dated(copy.ev_counters_dated, copy.ev_counters);
    case 'erratum':
      return when ? `${evidence.detail ?? copy.ev_erratum} · ${when}` : (evidence.detail ?? copy.ev_erratum);
    case 'vocabulary_schedule':
      return dated(copy.ev_schedule_dated, copy.ev_schedule);
    default:
      return when;
  }
}

/** «Séance du 5 septembre», with the journey named for anyone who asks. */
export function capabilityEvidenceSentence(
  row: DossierCapability['evidence'][number] | undefined,
  language: ControlLanguage = 'fr',
): string | null {
  if (!row) return null;
  const copy = dossierCopy(language);
  const when = row.on ? longDate(row.on, language) : null;
  const modality = row.modality === 'voice' ? copy.modality_voice : copy.modality_written;
  if (!when) return null;
  return fill(copy.cap_evidence, { date: when, modality });
}

/**
 * Why today's scene is today's scene.
 *
 * Returns `null` for an unknown kind, for a missing label, and — deliberately —
 * whenever there is no journey: the plan that would justify a line does not
 * exist yet.
 */
export function becauseSentence(
  today: DossierToday | null | undefined,
  language: ControlLanguage = 'fr',
): string | null {
  if (!today?.has_journey) return null;
  const because: DossierBecause | null | undefined = today.because;
  if (!because || because.kind !== 'erratum') return null;
  const label = (because.label || '').trim();
  if (!label) return null;
  const copy = dossierCopy(language);
  const example = (because.example || '').trim();
  return example ? fill(copy.because_example, { label, example }) : fill(copy.because, { label });
}

/** What the page says when there is no scene today. Never a promise. */
export function noJourneySentence(language: ControlLanguage = 'fr'): string {
  return dossierCopy(language).no_journey;
}
export const NO_JOURNEY_FR = noJourneySentence('fr');

/** «1 240 mots supposés connus», split into evidence and assumption. */
export function vocabularySentence(
  vocabulary: DossierVocabulary | null | undefined,
  language: ControlLanguage = 'fr',
): string {
  const copy = dossierCopy(language);
  const known = vocabulary?.known;
  if (!known) return copy.vocab_unreadable;
  return fill(copy.vocab_sentence, {
    known: known.known_lemmas,
    nailed: known.nailed_words,
    core: known.core_words,
  });
}

/** The rule behind the count, so the number is inspectable rather than magic. */
export function vocabularyRuleSentence(
  vocabulary: DossierVocabulary | null | undefined,
  language: ControlLanguage = 'fr',
): string {
  const rule = vocabulary?.nailed_rule?.retrievability;
  const percent = rule ? Math.round(rule * 100) : 90;
  return fill(dossierCopy(language).vocab_rule, { percent });
}

/** Words the learner may push back on. A nailed word has nothing to claim. */
export function claimableWords(vocabulary: DossierVocabulary | null | undefined): DossierWord[] {
  return (vocabulary?.words ?? []).filter((word) => word.claimable);
}

export function claimableErrata(errata: DossierErratum[] | undefined): DossierErratum[] {
  return (errata ?? []).filter((item) => item.claimable);
}

/** French long date from an ISO day («5 septembre», «1er janvier»). */
export function frenchDate(iso: string): string {
  return longDate(iso, 'fr');
}

/** The day alone: «12», «1er». Used when the month is printed by its partner. */
export function frenchDayNumber(iso: string): string {
  return dayNumber(iso, 'fr');
}

/**
 * WP-45. The short dated reference the artboard prints beside a capability:
 * «12 sept.». Abbreviations are the French conventional ones — «mars», «mai»,
 * «juin» and «août» are never abbreviated.
 */
export function frenchShortDate(iso: string): string {
  return shortDate(iso, 'fr');
}

/**
 * The verdict's notice tone. The sentence itself is the server's — a page that
 * wrote its own would be free to soften «pas encore» into a pass.
 */
export function verdictTone(verdict: string | null | undefined): 'plain' | 'quiet' | 'alert' {
  if (verdict === 'verified') return 'plain';
  if (verdict === 'not_yet') return 'alert';
  return 'quiet';
}
