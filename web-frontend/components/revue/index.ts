/**
 * WP-119 phases 1–2 · Le Papier de Romy — the public surface of components/revue
 * (and WP-120's RvVignette, which La Carte and the Relevé import from here).
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
  madeLabel,
  RvGuestEntrance,
  RvGuestLine,
  RvModelDownNotice,
  RvRegisterNote,
} from './RvThread';
export type { RvThreadProps, RvLineProps, RvGlossTextProps, RvWordEvent, RvGuestLineProps } from './RvThread';
export { RvMakePicker, RvHeadlineChoice, RvQuestionDraft, RvHeadlineWrite, RvShortReport, writeFeedback } from './RvMake';
export type { RvMakePickerOption, RvHeadlineChoiceProps, RvQuestionDraftProps, RvHeadlineWriteProps, RvShortReportProps } from './RvMake';
export { RvDispatch, RvKept, RvCloseVignette } from './RvClose';
export { RvVignette } from './RvVignette';
export type { RvVignetteProps } from './RvVignette';
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
export { revueCopy, fill, guestName, ROMY_CLIENT_LINES, GUEST_NAMES, REGISTER_LINES_FR } from './revue-copy';
export type { RevueCopy } from './revue-copy';
