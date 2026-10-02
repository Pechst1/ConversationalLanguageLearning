/**
 * WP-119 phase 1 · Le Papier de Romy — the public surface of components/revue.
 * Wire types: `@/lib/revue-types`; client: `@/lib/revue-api`; dev mock:
 * `@/lib/revue-mock` (`/revue?mock=1`, never in production). Styles:
 * `styles/revue.css` (imported from `pages/_app.tsx`).
 */

export { RvEncounter } from './RvEncounter';
export type { RvEncounterProps } from './RvEncounter';
export { RvSessionHead, RvColumn } from './RvSessionHead';
export type { RvSessionHeadProps } from './RvSessionHead';
export { RvStage, stageCast } from './RvStage';
export type { RvStageProps } from './RvStage';
export {
  RvThread,
  RvNarration,
  RvListen,
  RvLine,
  RvGlossText,
  RvClaim,
  RvSourceLine,
  RvUncertainty,
  RvShift,
  RvQuickReplies,
  RvContribution,
  RvMadeCard,
  RvTyping,
  ContributedText,
  shiftLabel,
} from './RvThread';
export type { RvThreadProps, RvLineProps, RvGlossTextProps, RvWordEvent } from './RvThread';
export { RvMakePicker, RvHeadlineChoice, RvQuestionDraft } from './RvMake';
export type { RvMakePickerOption, RvHeadlineChoiceProps, RvQuestionDraftProps } from './RvMake';
export { RvDispatch, RvKept } from './RvClose';
export type { RvDispatchProps } from './RvClose';
export { RvComposer } from './RvComposer';
export type { RvComposerProps } from './RvComposer';
export { RvUneCard } from './RvUneCard';
export type { RvUneCardProps, RvUneCardState } from './RvUneCard';
export { RvSubjectSheet, RvAltRows, RvAsk } from './RvSubjectSheet';
export type { RvSubjectSheetProps } from './RvSubjectSheet';
export { RvChooser } from './RvChooser';
export type { RvChooserProps } from './RvChooser';
export { revueHomeChip, revueUneState } from './revue-home';
export type { RevueHomeChip } from './revue-home';
export { revueCopy, fill, ROMY_CLIENT_LINES } from './revue-copy';
export type { RevueCopy } from './revue-copy';
