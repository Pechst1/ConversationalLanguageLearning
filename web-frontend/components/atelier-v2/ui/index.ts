/**
 * Atelier V2 design system — WP-01 public surface.
 *
 * Translated from `docs/design-reference/claude/Atelier App.dc.html`. The
 * stylesheet that goes with these components is `styles/atelier-v2.css`; it is
 * scoped entirely under `.av2`, which `AtelierV2Root` applies.
 */

export { AtelierV2Root, useAtelierCopy, useControlLanguage } from './AtelierV2Root';
export type { AtelierV2RootProps } from './AtelierV2Root';

export {
  AtelierMark,
  ShapeToken,
  ArrowRightIcon,
  CheckIcon,
  CrossIcon,
  LockIcon,
  MicIcon,
  PendingIcon,
  RepairIcon,
  SendIcon,
  StopIcon,
} from './Shapes';
export type { ShapeKind, ShapeTokenProps } from './Shapes';

export { Action, Chip, IconAction } from './Action';
export type { ActionProps, ActionTone, ChipProps, IconActionProps } from './Action';

export {
  DoneBadge,
  ProgressRule,
  Row,
  Stack,
  StatusToken,
  StepProgress,
  Surface,
} from './Surface';
export type {
  ProgressRuleProps,
  RowProps,
  StepProgressProps,
  StepSegment,
  SurfaceProps,
  SurfaceShape,
  SurfaceTone,
} from './Surface';

export { ChoiceList, TextAnswer, WordTiles, textAnswerField } from './Choice';
export type {
  ChoiceListProps,
  ChoiceOption,
  ChoiceState,
  TextAnswerProps,
  WordTilesProps,
} from './Choice';

export {
  Artwork,
  Byline,
  Correction,
  FeedbackBand,
  Notice,
  Portrait,
  characterAccent,
} from './Feedback';
export type {
  ArtworkProps,
  CorrectionProps,
  FeedbackBandProps,
  FeedbackTone,
  NoticeProps,
  PortraitProps,
} from './Feedback';

export { BottomSheet, Dialog } from './Sheet';
export type { BottomSheetProps, DialogProps } from './Sheet';

export { Skeleton, StateBlock, TabBar } from './States';
export type { StateBlockProps, TabDefinition, TabKey } from './States';
