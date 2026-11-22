/** «Papier · la voix» (2026-11-22, `REVUE_VOIX_ENABLED`): the lead read aloud, the counter heard first, the dictée. */
export { VoixProvider, VoixScope, useVoixClient, useVoixScope, useVoixSession, useVxReplay, useVxVeil, hadGesture } from './VoixContext';
export type { VoixScopeValue, VoixSession, VxLineHandle } from './VoixContext';
export { VxFace, VxLeadListen, VxVeil, useSpokenShare } from './VxParts';
export { VxDictee, VxDicteeSlot } from './VxDictee';
export { voixCopy, fillVoix, VOIX_FR, VOIX_COPIES } from './voix-copy';
export type { VoixCopy } from './voix-copy';
export { findLine, heardKey, isVeiled, lineForm, mayAutoplay, pendingLines, veilLines } from './voix-model';
