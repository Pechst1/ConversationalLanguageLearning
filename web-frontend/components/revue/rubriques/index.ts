/**
 * «Le titre» and «L'intox express» (WIRE §11, 2026-11-20) · the player of both
 * assignments, mounted when the session's `mode` is `titre` or `intox`. Styles:
 * `styles/revue-rubriques.css` (on the comptoir's and the fil's).
 */

export { RvRubrique } from './RvRubrique';
export type { RvRubriqueProps } from './RvRubrique';
export { RvTitreThree, RvTitreTrap, RvTitreBuild } from './RvTitreSteps';
export { RvIntoxRound, RvIntoxFix } from './RvIntoxSteps';
export { RvRubriquePage, TitreClipping, IntoxClipping } from './RvRubriquePages';
export { RvRubriqueRead, SourceQuote } from './RvRubriqueParts';
export type { RubriqueStepProps, TitreStepProps, IntoxStepProps } from './RvRubriqueParts';
export { rubriqueCopy, TITRE_FR, INTOX_FR, TITRE_STEP_LABELS_FR, INTOX_STEP_LABELS_FR, RUBRIQUE_LINES } from './rubriques-copy';
export type { RubriqueCopy } from './rubriques-copy';
export * from './rubriques-model';
// «La photo» and «Le micro» (WIRE §12, 2026-11-21): the same player, their screens.
export { RvPhotoPlanche, RvPhotoLegende, RvPhotoBuild } from './RvPhotoSteps';
export { RvMicroPrepare, RvMicroInterview, RvMicroNotes, RvMicroReview } from './RvMicroSteps';
export { PhotoClipping, MicroClipping } from './RvRubriquePages';
export { ProofBlock, ProofFoot } from './RvProofBlock';
export { photoMicroCopy, PHOTO_FR, MICRO_FR, PHOTO_STEP_LABELS_FR, MICRO_STEP_LABELS_FR, PM_LINES } from './photo-micro-copy';
export * from './photo-micro-model';
