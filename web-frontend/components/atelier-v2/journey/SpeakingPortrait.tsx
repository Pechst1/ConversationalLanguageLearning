/**
 * WP-91 «Les voix» — the face is the play button.
 *
 * A cast portrait that speaks its line when tapped, its ring pulsing in the
 * character's accent while it talks (a still ring under Reduce Motion — the
 * styles are in `styles/atelier-v2-voices.css`). Used wherever a character's
 * French is on screen (reader captions, the conversation thread, the
 * Courrier). Without a voice it renders the plain portrait, never a dead
 * button. The tap target is at least 44px, whatever the face's size.
 */

import React from 'react';

import { CastPortrait, type CastPortraitProps } from '@/components/atelier-v2/ui/CastPortrait';

import { useMouth } from '@/components/cast/useMouth';

import type { LineVoice, VoiceLine } from './useLineVoice';

export type SpeakingPortraitProps = Omit<CastPortraitProps, 'ring'> & {
  line: VoiceLine;
  voice: LineVoice | null | undefined;
  /** «Écouter Margaux» — in the learner's language, from the caller's copy table. */
  label: string;
  /** Keep the accent ring when silent (the thread's latest face has one). */
  ring?: boolean;
};

export function SpeakingPortrait({ line, voice, label, ring = false, ...portrait }: SpeakingPortraitProps) {
  // WP-116 phase 4: in the drawn set the face's mouth follows the voice.
  const mouth = useMouth(voice, line.key, line.text_fr);
  if (!voice || !voice.supported || !line.text_fr.trim()) {
    return <CastPortrait {...portrait} ring={ring} />;
  }
  const speaking = voice.speakingKey === line.key;
  return (
    <button
      type="button"
      className="av2-speaking-portrait"
      data-size={portrait.size ?? 'md'}
      data-speaking={speaking ? 'true' : undefined}
      aria-label={label}
      aria-pressed={speaking}
      onClick={() => voice.speak(line)}
    >
      <CastPortrait {...portrait} ring={ring || speaking} mouth={mouth} />
    </button>
  );
}
