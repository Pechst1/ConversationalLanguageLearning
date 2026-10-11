/**
 * WP-91 «Les voix» — a line to hear: the big round play button of listen_tap
 * and dictation.
 *
 * The Bauhaus red triangle, turned forward, is «play»; the ink square is
 * «stop». With a speaker the face is the button and the triangle its badge.
 * The clip is the journey's authenticated line audio, so it is fetched with
 * the session (`loadRecallClip`, cached for the session: a replay costs
 * nothing) and played from an object URL revoked when it ends. A clip that
 * cannot be played says so in one sentence and calls `onUnavailable`, so the
 * step can fall back to reading.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';

import { CastPortrait } from '@/components/atelier-v2/ui/CastPortrait';
import { loadRecallClip } from '@/services/daily-journey';

import {
  heardActionLabel,
  heardNext,
  heardSource,
  type HeardEvent,
  type HeardState,
} from './dictation-model';
import type { JourneyCopy } from './journey-copy';

export type HeardLineProps = {
  audioUrl: string | null | undefined;
  copy: JourneyCopy;
  /** Who says the line, when the prompt knows: their face is the button. */
  speaker?: { id: string | null; name: string } | null;
  disabled?: boolean;
  /** The clip could not be played (the step may fall back to reading). */
  onUnavailable?: () => void;
  /** Heard to the end at least once. */
  onHeard?: () => void;
};

export function HeardLine({ audioUrl, copy, speaker = null, disabled = false, onUnavailable, onHeard }: HeardLineProps) {
  const [state, setState] = useState<HeardState>('idle');
  const stateRef = useRef<HeardState>('idle');
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const urlRef = useRef<string | null>(null);
  const runRef = useRef(0);
  const callbacks = useRef({ onUnavailable, onHeard });
  callbacks.current = { onUnavailable, onHeard };

  const send = useCallback((event: HeardEvent) => {
    const next = heardNext(stateRef.current, event);
    stateRef.current = next;
    setState(next);
    return next;
  }, []);

  const release = useCallback(() => {
    const audio = audioRef.current;
    audioRef.current = null;
    if (audio) {
      audio.onended = null;
      audio.onerror = null;
      audio.pause();
    }
    if (urlRef.current) URL.revokeObjectURL(urlRef.current);
    urlRef.current = null;
  }, []);

  // A new line is a new listen; leaving stops the sound and frees the URL.
  useEffect(() => {
    runRef.current += 1;
    release();
    stateRef.current = 'idle';
    setState('idle');
  }, [audioUrl, release]);
  useEffect(
    () => () => {
      runRef.current += 1;
      release();
    },
    [release],
  );

  const fail = useCallback(() => {
    release();
    send('failed');
    callbacks.current.onUnavailable?.();
  }, [release, send]);

  const play = useCallback(async () => {
    if (stateRef.current === 'playing' || stateRef.current === 'loading') {
      runRef.current += 1;
      release();
      send('stop');
      return;
    }
    const source = heardSource(audioUrl);
    if (source.kind === 'none' || typeof Audio === 'undefined') {
      fail();
      return;
    }
    const run = ++runRef.current;
    send('play');
    let url: string;
    if (source.kind === 'clip') {
      const blob = await loadRecallClip(audioUrl);
      if (runRef.current !== run) return;
      if (!blob) {
        fail();
        return;
      }
      url = URL.createObjectURL(blob);
      urlRef.current = url;
    } else {
      url = source.url;
    }
    const audio = new Audio(url);
    audioRef.current = audio;
    audio.onended = () => {
      if (runRef.current !== run) return;
      release();
      send('ended');
      callbacks.current.onHeard?.();
    };
    audio.onerror = () => {
      if (runRef.current === run) fail();
    };
    try {
      await audio.play();
      if (runRef.current === run) send('loaded');
    } catch {
      if (runRef.current === run) fail();
    }
  }, [audioUrl, fail, release, send]);

  const label = heardActionLabel(state, copy);
  const face = Boolean(speaker && (speaker.id || speaker.name));
  return (
    <div className="av2-heard">
      <button
        type="button"
        className="av2-heard__play"
        data-state={state}
        data-face={face ? 'true' : undefined}
        aria-label={label}
        disabled={disabled}
        onClick={() => void play()}
      >
        {face && speaker && (
          <CastPortrait characterId={speaker.id || ''} name={speaker.name} size="md" ring={state === 'playing'} />
        )}
        <span className="av2-heard__glyph" aria-hidden="true" />
      </button>
      <div className="av2-heard__text">
        <p className="av2-heard__label" aria-hidden="true">
          {label}
        </p>
        {state === 'unavailable' && (
          <p className="av2-heard__status" role="status">
            {copy.dictation_unavailable}
          </p>
        )}
      </div>
    </div>
  );
}

export default HeardLine;
