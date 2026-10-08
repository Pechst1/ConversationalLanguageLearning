/**
 * WP-91 «Les voix» — la dictée.
 *
 * A line of today's scene is heard, never printed; the learner types what
 * they hear. The heard line is the big round play button (`HeardLine`); the
 * field below takes the learner's own spelling as the answer, so the device
 * does not autocorrect, capitalise or spell-check it. The step's one primary
 * («Vérifier») stays the step's: this component renders no second one, and
 * Enter sends only when the caller passes `onSubmit`.
 *
 * Posted as text and graded server-side like a short answer. Nothing here
 * listens to the learner.
 */

import React, { useId } from 'react';

import type { RecallPrompt } from '@/types/daily-journey';

import { DICTATION_FIELD_ATTRS, dictationReady } from './dictation-model';
import { HeardLine } from './HeardLine';
import type { JourneyCopy } from './journey-copy';

export type DictationProps = {
  prompt: Pick<RecallPrompt, 'audio_url' | 'instruction_native'>;
  copy: JourneyCopy;
  value: string;
  onChange: (next: string) => void;
  disabled?: boolean;
  /** The server said the answer was empty. */
  invalid?: boolean;
  /** Enter sends (Shift+Enter is a new line). Omit to leave sending to the step. */
  onSubmit?: () => void;
  speaker?: { id: string | null; name: string } | null;
  onUnavailable?: () => void;
};

export function Dictation({
  prompt,
  copy,
  value,
  onChange,
  disabled = false,
  invalid = false,
  onSubmit,
  speaker = null,
  onUnavailable,
}: DictationProps) {
  const fieldId = `av2-dictation-${useId().replace(/:/g, '')}`;
  return (
    <div className="av2-dictation">
      <HeardLine audioUrl={prompt.audio_url} copy={copy} speaker={speaker} onUnavailable={onUnavailable} />
      <div className="av2-field">
        <label className="av2-field__label" htmlFor={fieldId}>
          {copy.dictation_label}
        </label>
        <textarea
          id={fieldId}
          className="av2-field__control"
          lang="fr"
          rows={2}
          value={value}
          placeholder={copy.dictation_placeholder}
          disabled={disabled}
          aria-invalid={invalid || undefined}
          {...DICTATION_FIELD_ATTRS}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={(event) => {
            if (!onSubmit || event.key !== 'Enter' || event.shiftKey || event.nativeEvent.isComposing) return;
            event.preventDefault();
            if (!disabled && dictationReady(value)) onSubmit();
          }}
        />
      </div>
    </div>
  );
}

export default Dictation;
