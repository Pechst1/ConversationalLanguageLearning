/**
 * WP-91 «Les voix» — the face is the play button.
 *
 * A cast portrait that speaks its line when tapped, its ring pulsing in the
 * character's accent while it talks. Used wherever a character's French is on
 * screen (reader captions, the conversation thread, the Courrier). Without a
 * voice it renders the plain portrait, never a dead button.
 */

import { CastPortrait, type CastPortraitProps } from '@/components/atelier-v2/ui/CastPortrait';

import type { LineVoice, VoiceLine } from './useLineVoice';

export type SpeakingPortraitProps = Omit<CastPortraitProps, 'ring'> & {
  line: VoiceLine;
  voice: LineVoice | null | undefined;
  /** «Écouter Margaux» — in the learner's language, from the caller's copy table. */
  label: string;
};

export function SpeakingPortrait({ line, voice, label, ...portrait }: SpeakingPortraitProps) {
  if (!voice || !voice.supported || !line.text_fr.trim()) {
    return <CastPortrait {...portrait} />;
  }
  const speaking = voice.speakingKey === line.key;
  return (
    <button
      type="button"
      className="av2-speaking-portrait"
      data-speaking={speaking ? 'true' : undefined}
      aria-label={label}
      aria-pressed={speaking}
      onClick={() => voice.speak(line)}
    >
      <CastPortrait {...portrait} ring={speaking} />
    </button>
  );
}
