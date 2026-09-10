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

/** The rubric's own vocabulary, in French. Unknown states print as unknown. */
const CAPABILITY_STATE_FR: Record<string, string> = {
  not_tried: 'Pas encore tenté',
  with_support: 'Fait avec aide',
  independent_once: 'Fait seul une fois',
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

export const ERRATUM_STATE_ORDER = ['open', 'repairing', 'mastered'] as const;

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

/**
 * The verdict's notice tone. The sentence itself is the server's — a page that
 * wrote its own would be free to soften «pas encore» into a pass.
 */
export function verdictTone(verdict: string | null | undefined): 'plain' | 'quiet' | 'alert' {
  if (verdict === 'verified') return 'plain';
  if (verdict === 'not_yet') return 'alert';
  return 'quiet';
}
