/**
 * WP-119 · RvComposer — the reply field with the red icon (design §3.4 #voice).
 *
 * The red icon is the mic while the field is empty and the send arrow once text
 * is typed; recording turns it ink with a stop square. The transcript lands in
 * the field for the learner to check (never auto-sent). Voice is the existing
 * WP-27 hook (`useVoiceAnswer`: capture → transcribe, no pronunciation scoring).
 *
 * Local rather than extracted from `RespondStepView`: that step's composer is a
 * field + press layout bound to the journey controller's draft recovery, and its
 * tests drive it through a shallow tree walk — extracting it would have touched
 * the journey under another lease. Same classes, same look.
 */

import React, { useEffect, useRef, useState } from 'react';

import { IconAction, MicIcon, SendIcon, StopIcon } from '@/components/atelier-v2/ui';
import { textAnswerField } from '@/components/atelier-v2/ui/Choice';
import { useVoiceAnswer } from '@/components/atelier-v2/journey/useVoiceAnswer';

import type { RevueCopy } from './revue-copy';

export type RvComposerProps = {
  onSend: (text: string, mode: 'text' | 'voice') => void;
  disabled?: boolean;
  placeholder?: string;
  label?: string;
  initial?: string;
  copy: RevueCopy;
  autoFocus?: boolean;
};

export function RvComposer({ onSend, disabled = false, placeholder, label, initial = '', copy, autoFocus = false }: RvComposerProps) {
  const [text, setText] = useState(initial);
  const [mode, setMode] = useState<'text' | 'voice'>('text');
  const voice = useVoiceAnswer();
  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  const state = voice.state;

  useEffect(() => {
    if (state.kind === 'transcript') {
      setText(state.text);
      setMode('voice');
    }
  }, [state]);

  useEffect(() => {
    if (autoFocus) inputRef.current?.focus();
  }, [autoFocus]);

  const send = () => {
    const value = text.trim();
    if (!value || disabled) return;
    onSend(value, mode);
    setText('');
    setMode('text');
    voice.reset();
  };

  const voiceAvailable = typeof navigator === 'undefined' || Boolean(navigator.mediaDevices?.getUserMedia);
  const empty = !text.trim();

  return (
    <form
      className="rv-composer"
      onSubmit={(event) => {
        event.preventDefault();
        send();
      }}
      onKeyDown={(event) => {
        if (event.key === 'Enter' && !event.shiftKey && (event.target as HTMLElement).tagName === 'TEXTAREA') {
          event.preventDefault();
          send();
        }
      }}
    >
      {textAnswerField({
        label: label ?? copy.composer_label,
        value: text,
        rows: 1,
        disabled: disabled || state.kind === 'recording' || state.kind === 'transcribing',
        placeholder: state.kind === 'transcribing' ? copy.transcribing : placeholder ?? copy.composer_placeholder,
        onChange: (value) => {
          setText(value);
          if (!value) setMode('text');
        },
        inputRef,
      })}
      {state.kind === 'recording' ? (
        <IconAction label={copy.stop} tone="recording" onClick={() => voice.stop()}>
          <StopIcon size={18} />
        </IconAction>
      ) : empty && voiceAvailable ? (
        <IconAction label={copy.speak} tone="action" pending={state.kind === 'transcribing'} disabled={disabled} onClick={() => void voice.start()}>
          <MicIcon size={18} />
        </IconAction>
      ) : (
        <IconAction label={copy.send} tone="action" type="submit" disabled={disabled || empty}>
          <SendIcon size={18} />
        </IconAction>
      )}
    </form>
  );
}

export default RvComposer;
