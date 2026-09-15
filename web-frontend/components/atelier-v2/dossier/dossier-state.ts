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
 *     names the reason, the component writes the French, and a kind it has never
 *     heard of is silence rather than invented French.
 *  3. **No journey means no line at all.** «Pas encore de scène aujourd'hui» is
 *     the honest sentence; a prospective "today's scene will pick up…" would be
 *     a promise the planner has not made.
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

export type DossierPhase =
  | { kind: 'loading' }
  /** `/state` itself failed. The model is simply unread. */
  | { kind: 'load_failed'; message: string }
  | { kind: 'ready'; dossier: DossierPayload };

/** The rubric's own vocabulary, in French. Unknown states print as unknown.
 *  The wording is the 2026-09-15 artboard's (`Dossier.dc.html`). */
const CAPABILITY_STATE_FR: Record<string, string> = {
  not_tried: 'Pas encore tenté',
  with_support: 'Avec de l’aide',
  independent_once: 'Seul, une fois',
  used_again_later: 'Refait un autre jour',
  unknown: 'Aide non enregistrée',
};

/** WP-24's three states, and nothing else. */
const ERRATUM_STATE_FR: Record<string, string> = {
  open: 'À reprendre',
  repairing: 'En cours de reprise',
  mastered: 'Acquis',
};

const LEVEL_SOURCE_FR: Record<string, string> = {
  declared: 'Niveau déclaré',
  placement: 'Niveau estimé (bilan)',
  measured: 'Niveau mesuré dans l’application',
};

/** WP-45. The counter labels on the artboard: an adjective, not a verdict. */
const ERRATUM_COUNTER_FR: Record<string, string> = {
  open: 'ouvertes',
  repairing: 'en réparation',
  mastered: 'maîtrisées',
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

export function capabilityStateLabel(state: string): string {
  return CAPABILITY_STATE_FR[state] ?? CAPABILITY_STATE_FR.unknown;
}

export function errataStateLabel(state: string): string {
  return ERRATUM_STATE_FR[state] ?? ERRATUM_STATE_FR.open;
}

/** «Niveau estimé (bilan) · A2.1», or the honest absence of a level. */
export function levelSentence(level: DossierLevel | null | undefined): string {
  if (!level || level.available === false || !level.estimate) {
    return 'Niveau non évalué pour l’instant.';
  }
  const source = LEVEL_SOURCE_FR[level.estimate_source ?? ''] ?? 'Niveau estimé';
  return `${source} · ${level.estimate}`;
}

/**
 * What stands behind the level, in one sentence.
 *
 * A declaration says it has verified nothing; a placement says how sure it is
 * and on how many answers; in-app counters say they are the app's own work.
 */
export function levelBasisSentence(level: DossierLevel | null | undefined): string {
  if (!level || level.available === false) {
    return 'Nous ne pouvons pas lire cette estimation pour l’instant.';
  }
  if (level.estimate_source === 'declared') {
    return 'Vous nous l’avez indiqué à l’inscription. Nous n’avons encore rien vérifié.';
  }
  if (level.estimate_source === 'placement') {
    const turns = level.placement?.graded_turns ?? 0;
    const confidence = confidenceSentence(level.confidence);
    const answers = turns > 0 ? `${turns} réponses corrigées` : 'un bilan corrigé';
    return `Mesuré par le bilan de niveau, sur ${answers}. ${confidence}`;
  }
  return 'Calculé sur votre travail dans l’application : mots et notions acquis, score récent, taux d’erreur.';
}

/**
 * WP-45. The line beside the big serif level: where it came from, and whether
 * anything has checked it. Three sentences, one per `estimate_source`.
 */
export function levelSourceLine(level: DossierLevel | null | undefined): string {
  if (!level || level.available === false || !level.estimate) {
    return 'rien de mesuré pour l’instant';
  }
  if (level.estimate_source === 'declared') return 'déclaré à l’inscription · non vérifié';
  if (level.estimate_source === 'placement') {
    const when = level.placement?.taken_at ? ` du ${frenchShortDate(level.placement.taken_at)}` : '';
    return `estimé (bilan${when}) · non vérifié`;
  }
  return 'mesuré sur vos réponses en séance';
}

/**
 * WP-45 (D-5). What would move the level, with the threshold the estimator
 * actually uses rather than a number retyped into French.
 */
export function levelLadderSentence(level: LevelWithAttempts | null | undefined): string {
  const required = Number(level?.evidence_attempts_required ?? 40);
  if (!level || level.available === false) {
    return 'Nous ne pouvons pas lire cette estimation pour l’instant.';
  }
  if (level.estimate_source === 'measured') {
    const counted = Number(level.evidence_attempts_counted ?? 0);
    return `Mesuré sur ${counted} réponses corrigées en séance, ${required} au minimum.`;
  }
  if (level.estimate_source === 'placement') {
    const turns = level.placement?.graded_turns ?? 0;
    const basis = turns > 0 ? `sur ${turns} réponses corrigées` : 'sur un bilan corrigé';
    return `Estimé par le bilan, ${basis}. Il deviendra « mesuré » après ${required} réponses en séance.`;
  }
  return `Le niveau devient « estimé » après le bilan, et « mesuré » après ${required} réponses en séance.`;
}

/** The capability's name on a French screen. Falls back, never invents. */
export function capabilityTitle(capability: CapabilityWithFrenchTitle): string {
  const french = (capability.title_fr || '').trim();
  return french || capability.title;
}

/**
 * The evidence reference on a capability row: «séance du 12 sept.», or
 * «séances des 12 et 14 sept.» for a capability that was refait un autre jour,
 * or an em dash when nothing has been observed. Never a date nobody recorded.
 */
export function capabilityEvidenceRef(capability: DossierCapability): string {
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
    return sameMonth
      ? `séances des ${frenchDayNumber(first)} et ${frenchShortDate(last)}`
      : `séances des ${frenchShortDate(first)} et ${frenchShortDate(last)}`;
  }
  return `séance du ${frenchShortDate(days[days.length - 1])}`;
}

/** The three counters, in the artboard's order, from the true totals. */
export function errataCounters(
  errata: ErrataWithTotals | null | undefined,
): Array<{ state: string; count: number; label: string }> {
  // `totals` counts every erratum; `counts` counts only the rows this payload
  // carries, which stops at ERRATA_PER_STATE. Prefer the former, and say the
  // latter rather than nothing when an older server sends no totals.
  const source = errata?.totals ?? errata?.counts ?? {};
  return ERRATUM_STATE_ORDER.map((state) => ({
    state,
    count: Number(source[state] ?? 0),
    label: ERRATUM_COUNTER_FR[state],
  }));
}

/** «6 fautes notées en tout.» — the denominator the three counters divide. */
export function errataTotalSentence(errata: ErrataWithTotals | null | undefined): string {
  const total = errataCounters(errata).reduce((sum, item) => sum + item.count, 0);
  if (total === 0) return 'Aucune faute notée pour l’instant.';
  if (total === 1) return 'Une faute notée en tout.';
  return `${total} fautes notées en tout.`;
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
): string {
  const known = vocabulary?.known;
  if (!known) return 'Nous ne pouvons pas chiffrer votre stock de mots pour l’instant.';
  const nailed = Number(known.nailed_words);
  const acquired = nailed === 1 ? '1 acquis par vos révisions' : `${nailed} acquis par vos révisions`;
  return `mots supposés connus à votre niveau · ${acquired}`;
}

/** Confidence as words. A missing confidence is said, never drawn as zero. */
export function confidenceSentence(confidence: number | null | undefined): string {
  if (confidence === null || confidence === undefined) {
    return 'Aucune confiance chiffrée : rien n’a été mesuré.';
  }
  const percent = Math.round(confidence * 100);
  if (confidence >= 0.7) return `Confiance élevée (${percent} %).`;
  if (confidence >= 0.45) return `Confiance moyenne (${percent} %).`;
  return `Confiance faible (${percent} %).`;
}

/** «Vérifié dans l'application» vs «pas encore vérifié». */
export function verifiedSentence(level: DossierLevel | null | undefined): string {
  if (level?.verified) return 'Vérifié par vos compteurs dans l’application.';
  return 'Vos compteurs dans l’application sont encore à zéro : ce niveau reste une estimation.';
}

/** One dated line per number: «Séance du 5 septembre», «Bilan du 10 septembre». */
export function evidenceSentence(evidence: DossierEvidence | null | undefined): string | null {
  if (!evidence) return null;
  const when = evidence.on ? frenchDate(evidence.on) : null;
  switch (evidence.kind) {
    case 'journey':
      return when ? `Séance du ${when}` : 'Séance du jour';
    case 'placement':
      return when ? `Bilan du ${when}` : 'Bilan de niveau';
    case 'declaration':
      return when ? `Déclaré à l’inscription, le ${when}` : 'Déclaré à l’inscription';
    case 'in_app_counters':
      return when ? `Compteurs arrêtés le ${when}` : 'Compteurs de l’application';
    case 'erratum':
      return when ? `${evidence.detail ?? 'Relevé'} · ${when}` : (evidence.detail ?? 'Relevé');
    case 'vocabulary_schedule':
      return when ? `Prochaine révision le ${when}` : 'Dans votre file de révision';
    default:
      return when;
  }
}

/** «Séance du 5 septembre», with the journey named for anyone who asks. */
export function capabilityEvidenceSentence(
  row: DossierCapability['evidence'][number] | undefined,
): string | null {
  if (!row) return null;
  const when = row.on ? frenchDate(row.on) : null;
  const modality = row.modality === 'voice' ? 'à l’oral' : 'à l’écrit';
  if (!when) return null;
  return `Séance du ${when}, ${modality}`;
}

/**
 * Why today's scene is today's scene.
 *
 * Returns `null` for an unknown kind, for a missing label, and — deliberately —
 * whenever there is no journey: the plan that would justify a line does not
 * exist yet.
 */
export function becauseSentence(today: DossierToday | null | undefined): string | null {
  if (!today?.has_journey) return null;
  const because: DossierBecause | null | undefined = today.because;
  if (!because || because.kind !== 'erratum') return null;
  const label = (because.label || '').trim();
  if (!label) return null;
  const example = (because.example || '').trim();
  return example
    ? `Cette scène reprend une faute notée : ${label} (${example}).`
    : `Cette scène reprend une faute notée : ${label}.`;
}

/** What the page says when there is no scene today. Never a promise. */
export const NO_JOURNEY_FR = 'Pas encore de scène aujourd’hui.';

/** «1 240 mots supposés connus», split into evidence and assumption. */
export function vocabularySentence(vocabulary: DossierVocabulary | null | undefined): string {
  const known = vocabulary?.known;
  if (!known) {
    return 'Nous ne pouvons pas chiffrer votre stock de mots pour l’instant.';
  }
  return `${known.known_lemmas} mots supposés connus : ${known.nailed_words} acquis par vos révisions, ${known.core_words} supposés par votre niveau.`;
}

/** The rule behind the count, so the number is inspectable rather than magic. */
export function vocabularyRuleSentence(
  vocabulary: DossierVocabulary | null | undefined,
): string {
  const rule = vocabulary?.nailed_rule?.retrievability;
  const percent = rule ? Math.round(rule * 100) : 90;
  return `Un mot compte comme acquis quand nous estimons que vous le retrouveriez à ${percent} % aujourd’hui.`;
}

/** Words the learner may push back on. A nailed word has nothing to claim. */
export function claimableWords(vocabulary: DossierVocabulary | null | undefined): DossierWord[] {
  return (vocabulary?.words ?? []).filter((word) => word.claimable);
}

export function claimableErrata(errata: DossierErratum[] | undefined): DossierErratum[] {
  return (errata ?? []).filter((item) => item.claimable);
}

/** French long date from an ISO day, with no timezone arithmetic. */
export function frenchDate(iso: string): string {
  const [year, month, day] = iso.slice(0, 10).split('-').map((part) => Number(part));
  if (!year || !month || !day) return iso;
  const months = [
    'janvier',
    'février',
    'mars',
    'avril',
    'mai',
    'juin',
    'juillet',
    'août',
    'septembre',
    'octobre',
    'novembre',
    'décembre',
  ];
  const first = day === 1 ? '1er' : String(day);
  return `${first} ${months[month - 1]}`;
}

/** The day alone: «12», «1er». Used when the month is printed by its partner. */
export function frenchDayNumber(iso: string): string {
  const day = Number(iso.slice(8, 10));
  if (!day) return iso;
  return day === 1 ? '1er' : String(day);
}

/**
 * WP-45. The short dated reference the artboard prints beside a capability:
 * «12 sept.». Abbreviations are the French conventional ones — «mars», «mai»,
 * «juin» and «août» are never abbreviated, because they are not longer spelt
 * out than cut short.
 */
export function frenchShortDate(iso: string): string {
  const month = Number(iso.slice(5, 7));
  const day = frenchDayNumber(iso);
  const months = [
    'janv.',
    'févr.',
    'mars',
    'avr.',
    'mai',
    'juin',
    'juill.',
    'août',
    'sept.',
    'oct.',
    'nov.',
    'déc.',
  ];
  if (!month || !months[month - 1] || day === iso) return iso;
  return `${day} ${months[month - 1]}`;
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
