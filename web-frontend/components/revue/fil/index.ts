/**
 * «Le fil» (WIRE §10, owner 2026-11-20) · the player of the assignment «Le fil», mounted
 * when the session's `mode` is `fil`. Styles: `styles/revue-fil.css` (on the comptoir's).
 */

export { RvFil } from './RvFil';
export type { RvFilProps } from './RvFil';
export { RvFilRead, RvFilOrder, RvFilWords } from './RvFilSteps';
export type { FilStepProps } from './RvFilSteps';
export { RvFilTell } from './RvFilTell';
export { RvFilPage, FilClipping } from './RvFilPage';
export { filCopy, FIL_FR, FIL_LINES, FIL_STEP_LABELS_FR } from './fil-copy';
export type { FilCopy } from './fil-copy';
export * from './fil-model';
