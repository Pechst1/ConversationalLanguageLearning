/**
 * WP-35 «Votre dossier» — public surface.
 *
 * The screen renders `dossier-state.ts`; every sentence worth testing is a pure
 * function there, which is what the node suite exercises.
 */

export { DossierScreen } from './DossierScreen';
export type { DossierScreenProps } from './DossierScreen';

export {
  ERRATUM_STATE_ORDER,
  NO_JOURNEY_FR,
  becauseSentence,
  capabilityEvidenceSentence,
  capabilityStateLabel,
  claimableErrata,
  claimableWords,
  confidenceSentence,
  errataStateLabel,
  evidenceSentence,
  frenchDate,
  levelBasisSentence,
  levelSentence,
  phaseFor,
  verdictTone,
  verifiedSentence,
  vocabularyRuleSentence,
  vocabularySentence,
} from './dossier-state';
export type { DossierPhase } from './dossier-state';
