/**
 * WP-76 (latency half) — the respond step's wait has a face.
 *
 * `CharacterTyping`: while the answer is being read, the character's portrait
 * and «Marin écrit…» with three soft dots. No spinner, no «Envoi…».
 * `TypedReply`: the reply arrives as the character's speech and types in,
 * whole words at a time; the verdict card waits for it (`journey-requests`
 * `stageAttemptFeedback`). Reduced Motion shows the reply whole at once.
 * WP-91: the face is the play button, and a reply that has typed in says
 * itself once when «Les personnages parlent à voix haute» is on.
 */

import React, { useEffect, useRef, useState } from 'react';

import { CastPortrait } from '@/components/atelier-v2/ui/CastPortrait';
import { useControlLanguage } from '@/components/atelier-v2/ui';
import {
  prefersReducedMotion,
  replyRevealMs,
  typedReply,
  typingLine,
} from '@/lib/journey-reply-reveal';
import type { RespondPrompt } from '@/types/daily-journey';

import { journeyCopy } from './journey-copy';
import { SpeakingPortrait } from './SpeakingPortrait';
import { useAutoSpeak, type LineVoice, type VoiceLine } from './useLineVoice';
import { listenLabel, useStepVoice } from './useStepVoice';
import { replyFinishedTyping } from './voice-autoplay';

export type ReplySpeaker = { id: string | null; name: string } | null;

/** Who answers on a respond step: a letter day's correspondent, else the character. */
export function respondSpeaker(prompt: RespondPrompt): ReplySpeaker {
  const letter = prompt.letter;
  if (letter?.correspondent_name) {
    return { id: letter.correspondent_id || null, name: letter.correspondent_name };
  }
  return prompt.character_name
    ? { id: prompt.character_id || null, name: prompt.character_name }
    : null;
}

/** A frame's worth of typing without re-rendering 60 times a second. */
const TYPE_TICK_MS = 60;

export function CharacterTyping({ speaker }: { speaker: ReplySpeaker }) {
  const language = useControlLanguage();
  const line = typingLine(speaker?.name, language);
  return (
    <div className="av2-reply av2-reply--typing" role="status" aria-live="polite">
      {speaker && <CastPortrait characterId={speaker.id || ''} name={speaker.name} size="sm" />}
      <p className="av2-reply__typing">
        <span>{line}</span>
        <span className="av2-reply__dots" aria-hidden="true">
          <i />
          <i />
          <i />
        </span>
      </p>
    </div>
  );
}

/**
 * The reply as it types in, whole words at a time; `animate` false (a settled
 * turn, Reduced Motion) shows it whole. Shared by the reply row and the bubble.
 */
export function useTypedText(reply: string, animate: boolean): string {
  // Computed in render, so the first paint already shows only the first word.
  const total = animate ? replyRevealMs(reply, { reducedMotion: prefersReducedMotion() }) : 0;
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    setElapsed(0);
    if (total <= 0) return undefined;
    const started = Date.now();
    const timer = setInterval(() => {
      const next = Date.now() - started;
      setElapsed(next);
      if (next >= total) clearInterval(timer);
    }, TYPE_TICK_MS);
    return () => clearInterval(timer);
    // `animate` flips to false when the verdict lands; the text is complete by then.
  }, [reply, total]);

  return total > 0 ? typedReply(reply, elapsed, total) : reply;
}

export function TypedReply({
  speaker,
  reply,
  animate,
  journeyId = null,
  stepId = null,
  voice: sharedVoice = null,
}: {
  speaker: ReplySpeaker;
  reply: string;
  /** `true` while the verdict is held back; a settled turn shows it whole. */
  animate: boolean;
  /** WP-91: the day and the step, so the face speaks with the server's clip. */
  journeyId?: string | null;
  stepId?: string | null;
  voice?: LineVoice | null;
}) {
  const shown = useTypedText(reply, animate);
  const language = useControlLanguage();
  const voice = useStepVoice(journeyId, stepId, sharedVoice);
  const line: VoiceLine = { key: `${stepId ?? ''}:reply`, text_fr: reply, character_id: speaker?.id ?? null };
  // Only a reply that arrived on this screen (it typed in) speaks by itself; a
  // settled one, repainted after a reload, waits for a tap. Remembered, because
  // the verdict can land in the same frame the last word does.
  const arrived = useRef(false);
  if (animate) arrived.current = true;
  useAutoSpeak(voice, arrived.current ? line : null, replyFinishedTyping(reply, shown), stepId);

  return (
    <div className="av2-reply" data-typing={shown.length < reply.trim().length ? 'true' : undefined}>
      {speaker && (
        <SpeakingPortrait
          line={line}
          voice={voice}
          label={listenLabel(journeyCopy(language), speaker.name)}
          characterId={speaker.id || ''}
          name={speaker.name}
          size="sm"
        />
      )}
      <div className="av2-reply__body">
        {speaker && <p className="av2-label">{speaker.name}</p>}
        <p className="av2-fr av2-body av2-body--lg av2-reply__text" lang="fr">
          <span aria-hidden="true">{shown}</span>
          <span className="av2-reply__sr">{reply}</span>
        </p>
      </div>
    </div>
  );
}

const SMILES: Record<'fr' | 'en' | 'de', string> = {
  fr: '{name} vous sourit',
  en: '{name} smiles at you',
  de: '{name} lächelt Sie an',
};

/** WP-D2: the line under a correct verdict, in the learner's chrome language. */
export function smileLine(name: string | null | undefined, language: string | null | undefined): string | null {
  const who = String(name || '').trim();
  if (!who) return null;
  return SMILES[language === 'fr' || language === 'de' ? language : 'en'].replace('{name}', who);
}

/**
 * WP-D2: «Marin vous sourit ↑» under the verdict band on a correct answer. The
 * arrow is decoration; the sentence carries the meaning. The face is already in
 * the band and in the bubble, so this line has none.
 */
export function CharacterSmiles({ speaker }: { speaker: ReplySpeaker }) {
  const language = useControlLanguage();
  const line = smileLine(speaker?.name, language);
  if (!line) return null;
  return (
    <p className="av2-label av2-smiles" data-mood="happy">
      {line} <span aria-hidden="true">↑</span>
    </p>
  );
}

const ENDING_WRITES: Record<'fr' | 'en' | 'de', string> = {
  fr: 'La suite s’écrit…',
  en: 'What happens next is being written…',
  de: 'Wie es weitergeht, wird gerade geschrieben…',
};

/** WP-87: the language of the "…" line while the story lane writes the ending. */
export function endingLine(language: string | null | undefined): string {
  return ENDING_WRITES[language === 'fr' || language === 'de' ? language : 'en'];
}

/**
 * WP-87: the resolution step while the story lane is still writing its ending —
 * the character's face and a short "…" line, never a spinner. The hook polls the
 * journey meanwhile; the server heals a dead lane with the authored ending.
 */
export function StoryWriting({ speaker }: { speaker: ReplySpeaker }) {
  const language = useControlLanguage();
  return (
    <div className="av2-reply av2-reply--typing" role="status" aria-live="polite">
      {speaker && <CastPortrait characterId={speaker.id || ''} name={speaker.name} size="sm" />}
      <p className="av2-reply__typing">
        <span>{endingLine(language)}</span>
        <span className="av2-reply__dots" aria-hidden="true">
          <i />
          <i />
          <i />
        </span>
      </p>
    </div>
  );
}
