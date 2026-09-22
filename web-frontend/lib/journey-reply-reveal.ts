/**
 * WP-76 (latency half) — reply first, verdict second.
 *
 * Framework-free so the node harness can drive the whole sequence with a fake
 * clock and a slow fake transport:
 *
 *   submitting → (the character is typing: portrait + «Marin écrit…»)
 *   replying   → the reply types in; the verdict card is not on screen yet
 *   graded     → the verdict joins the reply
 *
 * Why the reply is not streamed from the server (decision, 2026-09-22): on
 * the story engine the character's reply and the verdict come out of ONE actor
 * call and are accepted or refused TOGETHER by the critic (gendered address,
 * invented learner choices, reply/state contradictions). A streamed reply
 * would show words the critic may still refuse, and the retry writes a
 * different reply. So the server hands back the reviewed reply with the
 * verdict, and the client stages them: words first, judgement second. The
 * wait itself is given a face instead of a spinner.
 */

import type { AttemptResult, ControlLanguage, StepKind } from '@/types/daily-journey';

/** Per-character pace of the typed reply. */
export const REPLY_CHAR_MS = 24;
/** A short reply still reads as typed, not as a flash. */
export const REPLY_REVEAL_MIN_MS = 500;
/** A long reply never holds the verdict back for more than this. */
export const REPLY_REVEAL_MAX_MS = 1_800;
/** The beat between the last typed word and the verdict card. */
export const VERDICT_BEAT_MS = 250;

export type RevealOptions = { reducedMotion?: boolean };

/** How long the reply types in. `0` means "show it whole, at once". */
export function replyRevealMs(reply: string | null | undefined, options: RevealOptions = {}): number {
  const text = (reply ?? '').trim();
  if (!text || options.reducedMotion) return 0;
  return Math.min(REPLY_REVEAL_MAX_MS, Math.max(REPLY_REVEAL_MIN_MS, text.length * REPLY_CHAR_MS));
}

/** When the verdict may join the reply, counted from the result's arrival. */
export function verdictDelayMs(reply: string | null | undefined, options: RevealOptions = {}): number {
  const typing = replyRevealMs(reply, options);
  return typing === 0 ? 0 : typing + VERDICT_BEAT_MS;
}

/**
 * The part of the reply on screen `elapsedMs` into the reveal, whole words
 * only — a half-typed French word reads as a misspelling. The first word is
 * on screen at once, so the learner sees words the instant the result lands.
 */
export function typedReply(reply: string, elapsedMs: number, totalMs: number): string {
  const text = reply.trim();
  if (!text || totalMs <= 0 || elapsedMs >= totalMs) return text;
  const chars = Math.max(1, Math.floor((Math.max(0, elapsedMs) / totalMs) * text.length));
  // Always to the end of the word the cursor is in (the first word at once).
  const cut = text.indexOf(' ', chars);
  return text.slice(0, cut === -1 ? text.length : cut);
}

/** Only a real respond reply is staged; a recall verdict is immediate. */
export function stagesReplyFirst(result: AttemptResult | null | undefined, stepKind: StepKind | null | undefined): boolean {
  if (!result || stepKind !== 'respond') return false;
  if (result.pending || result.task_outcome === 'unscored') return false;
  return Boolean((result.character_reply_fr ?? '').trim());
}

// ---------------------------------------------------------------------------
// The sequencer
// ---------------------------------------------------------------------------

export type RevealStage<F> = (feedback: F) => void;

export type ReplySequencer = {
  /**
   * Show `replying` now and `graded` after the reveal. Returns a cancel that
   * a newer result (or an unmount) calls so a stale verdict can never land.
   */
  stage: <F>(replying: F, graded: F, delayMs: number, apply: RevealStage<F>) => () => void;
  cancel: () => void;
};

export type SequencerTimers = {
  setTimer?: (fn: () => void, ms: number) => unknown;
  clearTimer?: (handle: unknown) => void;
};

export function createReplySequencer(timers: SequencerTimers = {}): ReplySequencer {
  const setTimer = timers.setTimer ?? ((fn, ms) => setTimeout(fn, ms));
  const clearTimer = timers.clearTimer ?? ((handle) => clearTimeout(handle as never));
  let pending: unknown = null;
  const cancel = () => {
    if (pending !== null) clearTimer(pending);
    pending = null;
  };
  return {
    stage(replying, graded, delayMs, apply) {
      cancel();
      if (delayMs <= 0) {
        apply(graded);
        return cancel;
      }
      apply(replying);
      pending = setTimer(() => {
        pending = null;
        apply(graded);
      }, delayMs);
      return cancel;
    },
    cancel,
  };
}

// ---------------------------------------------------------------------------
// Copy — the learner's language, one short line each
// ---------------------------------------------------------------------------

const TYPING: Record<ControlLanguage, string> = {
  fr: '{name} écrit…',
  en: '{name} is typing…',
  de: '{name} schreibt…',
};

const TYPING_NAMELESS: Record<ControlLanguage, string> = {
  fr: 'Réponse en cours…',
  en: 'A reply is on its way…',
  de: 'Die Antwort kommt…',
};

const PLACE_WAKES: Record<ControlLanguage, string> = {
  fr: '{place} s’anime…',
  en: '{place} comes to life…',
  de: '{place} erwacht…',
};

const CHARACTER_ARRIVES: Record<ControlLanguage, string> = {
  fr: '{name} arrive…',
  en: '{name} is on the way…',
  de: '{name} kommt gleich…',
};

const SCENE_PREPARES: Record<ControlLanguage, string> = {
  fr: 'La scène se prépare…',
  en: 'Your scene is being set…',
  de: 'Deine Szene wird vorbereitet…',
};

function lang(language: ControlLanguage | string | null | undefined): ControlLanguage {
  return language === 'fr' || language === 'de' ? language : 'en';
}

/** «Marin écrit…» — the respond step's wait, said by the character. */
export function typingLine(name: string | null | undefined, language: ControlLanguage | string | null | undefined): string {
  const who = (name ?? '').trim();
  const table = lang(language);
  return who ? TYPING[table].replace('{name}', who) : TYPING_NAMELESS[table];
}

/**
 * «Le Mistral s’anime…» — the day's scene is being prepared. The place when
 * the descriptor names one (the story engine often ships an empty one), then
 * the character, then a plain line. Never a bare spinner.
 */
export function preparingLine(
  place: string | null | undefined,
  character: string | null | undefined,
  language: ControlLanguage | string | null | undefined,
): string {
  const table = lang(language);
  const where = (place ?? '').trim();
  if (where) return PLACE_WAKES[table].replace('{place}', where);
  const who = (character ?? '').trim();
  if (who) return CHARACTER_ARRIVES[table].replace('{name}', who);
  return SCENE_PREPARES[table];
}

/** `prefers-reduced-motion`, safely false outside a browser. */
export function prefersReducedMotion(): boolean {
  try {
    return Boolean(
      typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches,
    );
  } catch {
    return false;
  }
}
