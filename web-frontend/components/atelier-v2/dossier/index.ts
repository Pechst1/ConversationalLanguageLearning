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
  capabilityEvidenceRef,
  capabilityEvidenceSentence,
  capabilityStateLabel,
  capabilityTitle,
  claimableErrata,
  claimableWords,
  confidenceSentence,
  errataCounters,
  errataStateLabel,
  errataTotalSentence,
  evidenceSentence,
  frenchDate,
  frenchDayNumber,
  frenchShortDate,
  levelBasisSentence,
  levelLadderSentence,
  levelSentence,
  levelSourceLine,
  noJourneySentence,
  phaseFor,
  rulesSpeedSentence,
  verdictTone,
  verifiedSentence,
  vocabularyCount,
  vocabularyRuleSentence,
  vocabularySentence,
  vocabularyUnitSentence,
} from './dossier-state';
export { DOSSIER_COPY, dossierCopy } from './dossier-copy';
export type { DossierCopy } from './dossier-copy';
export type {
  CapabilityWithFrenchTitle,
  DossierPhase,
  ErrataWithTotals,
  LevelWithAttempts,
  LevelWithRulesSpeed,
  RulesSpeed,
} from './dossier-state';
