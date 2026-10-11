/**
 * WP-158 slice 1 — «Parler» beside the story reply's text field, and the one
 * line to repeat once the conversation is closed.
 *
 * Both are views over state the respond step owns (`useSpokenReply`): the
 * control never sends anything itself. It lives in the reply step, never inside
 * the stage — PanelStage's layout, figures and props are untouched.
 *
 * Reduced Motion: nothing here moves. The countdowns are words that change
 * once a second, not a bar that sweeps. Sound: the control only records; the
 * character's answer speaks as it already does (WP-91, «Les personnages parlent
 * à voix haute», the iOS ringer switch through the ambient audio session), and
 * the line to repeat speaks only when tapped.
 */

import React from 'react';

import { Action, MicIcon, Notice, StopIcon, Surface } from '@/components/atelier-v2/ui';
import { frenchSpacing } from '@/lib/french-typography';

import type { JourneyCopy } from './journey-copy';
import {
  SPOKEN_FAILURE_COPY_KEY,
  confirmSecondsLeft,
  recordingSecondsLeft,
  withSeconds,
  type SpokenReplyState,
} from './spoken-reply';
import type { LineVoice } from './useLineVoice';

export type SpokenReplyControlProps = {
  state: SpokenReplyState;
  now: number;
  copy: JourneyCopy;
  /** The turn is busy elsewhere (sending, waiting for the reply). */
  disabled: boolean;
  onStart: () => void;
  onStop: () => void;
};

/** Which of the control's states is on screen — the tests read it. */
export function spokenPhase(state: SpokenReplyState): string {
  return state.kind;
}

/**
 * What «Parler» says while it works — under the text field. The transcript
 * itself is not drawn here: it is in the reply's own text field, editable,
 * where the learner would have typed it.
 */
export function SpokenReplyStatus({ state, now, copy }: Pick<SpokenReplyControlProps, 'state' | 'now' | 'copy'>) {
  const table = copy as Record<string, string>;
  const confirmLeft = confirmSecondsLeft(state, now);
  const failure =
    state.kind === 'error' ? table[SPOKEN_FAILURE_COPY_KEY[state.reason]] || copy.voice_failed : null;
  if (state.kind === 'idle' || state.kind === 'transcribing') return null;
  return (
    <div className="av2-stack av2-spoken" data-spoken={spokenPhase(state)}>
      {state.kind === 'confirm' && (
        <div role="status" aria-live="polite">
          <p className="av2-label">{copy.spoken_confirm}</p>
          <p className="av2-body">
            {confirmLeft !== null
              ? withSeconds(copy.spoken_confirm_countdown, confirmLeft)
              : copy.voice_transcript_hint}
          </p>
        </div>
      )}
      {state.kind === 'submitted' && (
        <p className="av2-sr" role="status">
          {copy.spoken_sent}
        </p>
      )}
      {state.kind === 'recording' && (
        <p className="av2-body" role="status" aria-live="polite">
          {withSeconds(copy.spoken_listening, recordingSecondsLeft(state, now))}
        </p>
      )}
      {failure && (
        <Notice shape="action">
          <p>{failure}</p>
        </Notice>
      )}
    </div>
  );
}

/**
 * The «Parler» button, beside «Envoyer» in the reply's action row. Absent once
 * the reply is sent, and once the server has refused this turn's spoken
 * attempts (the cost ceiling): the field is the way on.
 */
export function SpokenReplyButton({ state, copy, disabled, onStart, onStop }: SpokenReplyControlProps) {
  const recording = state.kind === 'recording';
  if (state.kind === 'submitted') return null;
  if (state.kind === 'error' && state.reason === 'ceiling') return null;
  return (
    <Action
      tone="secondary"
      data-spoken-button={spokenPhase(state)}
      disabled={disabled && !recording}
      pending={state.kind === 'transcribing'}
      pendingLabel={copy.transcribing}
      icon={recording ? <StopIcon size={18} /> : <MicIcon size={18} />}
      aria-pressed={recording || undefined}
      onClick={recording ? onStop : onStart}
    >
      {recording ? copy.stop_recording : state.kind === 'confirm' ? copy.voice_retry : copy.speak}
    </Action>
  );
}

export type RepeatLineProps = {
  line: string;
  copy: JourneyCopy;
  voice: LineVoice;
  stepId: string;
};

/**
 * The recap's one useful line: heard on a tap (never by itself), then said once
 * aloud by the learner. Nothing listens to that — no recording, no score.
 */
export function RepeatLine({ line, copy, voice, stepId }: RepeatLineProps) {
  const key = `${stepId}:repeat`;
  const speaking = voice.speakingKey === key;
  return (
    <Surface className="av2-stack av2-repeat" data-repeat="">
      <p className="av2-label av2-label--story">{copy.repeat_title}</p>
      <p className="av2-fr av2-body av2-body--lg" lang="fr">
        {frenchSpacing(line)}
      </p>
      <p className="av2-body">{copy.repeat_hint}</p>
      {voice.supported && (
        <Action
          tone="secondary"
          inline
          aria-pressed={speaking || undefined}
          onClick={() =>
            speaking ? voice.stop() : voice.speak({ key, text_fr: line, character_id: 'narrator' })
          }
        >
          {speaking ? copy.stop_recording : copy.repeat_listen}
        </Action>
      )}
    </Surface>
  );
}
