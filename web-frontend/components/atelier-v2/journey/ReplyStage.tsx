/**
 * WP-76 (latency half) — the respond step's wait has a face.
 *
 * `CharacterTyping`: while the answer is being read, the character's portrait
 * and «Marin écrit…» with three soft dots. No spinner, no «Envoi…».
 * `TypedReply`: the reply arrives as the character's speech and types in,
 * whole words at a time; the verdict card waits for it (`journey-requests`
 * `stageAttemptFeedback`). Reduced Motion shows the reply whole at once.
 */

import React, { useEffect, useState } from 'react';

import { CastPortrait } from '@/components/onboarding/Portrait';
import { useControlLanguage } from '@/components/atelier-v2/ui';
import {
  prefersReducedMotion,
  replyRevealMs,
  typedReply,
  typingLine,
} from '@/lib/journey-reply-reveal';
import type { RespondPrompt } from '@/types/daily-journey';

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

export function TypedReply({
  speaker,
  reply,
  animate,
}: {
  speaker: ReplySpeaker;
  reply: string;
  /** `true` while the verdict is held back; a settled turn shows it whole. */
  animate: boolean;
}) {
  const [total, setTotal] = useState(0);
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const ms = animate ? replyRevealMs(reply, { reducedMotion: prefersReducedMotion() }) : 0;
    setTotal(ms);
    setElapsed(0);
    if (ms <= 0) return undefined;
    const started = Date.now();
    const timer = setInterval(() => {
      const next = Date.now() - started;
      setElapsed(next);
      if (next >= ms) clearInterval(timer);
    }, TYPE_TICK_MS);
    return () => clearInterval(timer);
    // `animate` flips to false when the verdict lands; the text is complete by then.
  }, [reply, animate]);

  const shown = total > 0 ? typedReply(reply, elapsed, total) : reply;

  return (
    <div className="av2-reply" data-typing={shown.length < reply.trim().length ? 'true' : undefined}>
      {speaker && <CastPortrait characterId={speaker.id || ''} name={speaker.name} size="sm" />}
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
