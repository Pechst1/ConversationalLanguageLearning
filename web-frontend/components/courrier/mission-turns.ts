/**
 * A mission's turns in the conversation's order, and what the composer asks
 * next (#397, review on #411).
 *
 * The order is the server's turn counter (`turn_index`), never the stored
 * time: an old thread can carry a reply stamped later than the actual latest
 * one, and the composer reads the latest assistant turn's text and branch
 * state from this list. Kept outside the page so a node test can hold it.
 */

import type { RealWorldMission } from '@/services/api';
import { crFill, type CourrierCopy } from './courrier-copy';

type Turn = NonNullable<RealWorldMission['turns']>[number];

/** The conversation's own order: by the server's turn counter. */
export function missionTurns(mission: RealWorldMission | null | undefined): Turn[] {
  return [...(mission?.turns || [])].sort((a, b) => Number(a.turn_index || 0) - Number(b.turn_index || 0));
}

/** The assistant's latest line, by turn counter. */
export function latestAssistantTurn(mission: RealWorldMission | null | undefined): Record<string, any> | undefined {
  return missionTurns(mission).filter((turn) => turn.role === 'assistant').slice(-1)[0] as Record<string, any> | undefined;
}

export function compactText(value: unknown, max = 180) {
  const text = String(value || '').replace(/\s+/g, ' ').trim();
  if (text.length <= max) return text;
  return `${text.slice(0, max - 1).trim()}...`;
}

/** What the composer asks for next, from the latest assistant turn's text and branch. */
export function currentComposerInstruction(
  mission: RealWorldMission | null,
  base: { label: string; instruction: string; placeholder: string },
  t: CourrierCopy,
): { label: string; instruction: string; placeholder: string } {
  if (!missionTurns(mission).some((turn) => turn.role === 'user')) return base;
  const latest = latestAssistantTurn(mission);
  if (!latest) {
    return base;
  }
  const assistantText = compactText(latest.text, 150);
  const branch = latest.audio_payload?.branch || {};
  const state = String(branch.state || '');
  if (state === 'understood') {
    return {
      label: t.composer_label_last,
      instruction: t.composer_instruction_last,
      placeholder: t.composer_placeholder_last,
    };
  }
  return {
    label: t.composer_label_reply,
    instruction: assistantText
      ? crFill(t.composer_instruction_quoted, { text: assistantText })
      : t.composer_instruction_reply,
    placeholder: t.composer_placeholder_reply,
  };
}

/** The server stored the learner's reply but no correspondent answered it (#397/#333). */
export function replyPending(outcome: Record<string, any> | null | undefined): boolean {
  return outcome?.reply_state === 'pending';
}

/** The server marks every learner message nobody answered on the thread itself (#590). */
export function turnReplyPending(turn: Record<string, any> | null | undefined): boolean {
  return turn?.role === 'user' && turn?.reply_state === 'pending';
}

/** #693: «Ask again» ran for this message and came back empty (the server counts each ask). */
export function turnReplyAskedAgain(turn: Record<string, any> | null | undefined): boolean {
  return turnReplyPending(turn) && Number(turn?.reply_attempts || 0) >= 2;
}
