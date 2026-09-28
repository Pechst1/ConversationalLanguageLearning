/**
 * WP-91 «Les voix» — one character line, spoken on request.
 *
 * The shared seam between the reader (WP-90), the conversation thread, the
 * Courrier and word help: every surface that shows a character's French asks
 * this hook to say it. One line speaks at a time; tapping the speaking line
 * again stops it.
 *
 * Sources, best first:
 *  1. `audio_url` on the line (a cached clip from the server);
 *  2. `resolve(line)` — a caller-supplied fetch of a server clip (the episode
 *     manifest, or the journey's line-audio route);
 *  3. the device's own French voice (`speechSynthesis`), free and offline.
 *
 * Deliberately not here: pronunciation of any kind (WP-27 owner decision).
 */

import { useCallback, useEffect, useRef, useState } from 'react';

export type VoiceLine = {
  /** Stable per line on screen; the speaking state is keyed on it. */
  key: string;
  text_fr: string;
  character_id?: string | null;
  audio_url?: string | null;
};

export type LineVoice = {
  speak: (line: VoiceLine) => void;
  stop: () => void;
  /** The key of the line being spoken, or null. */
  speakingKey: string | null;
  /** False when the device can make no sound at all (no audio, no speech). */
  supported: boolean;
};

export type LineVoiceOptions = {
  /** A server clip for a line without `audio_url`; `null` means "use the device voice". */
  resolve?: (line: VoiceLine) => Promise<string | null>;
};

function deviceSpeechAvailable(): boolean {
  return typeof window !== 'undefined' && 'speechSynthesis' in window && 'SpeechSynthesisUtterance' in window;
}

export function useLineVoice(options: LineVoiceOptions = {}): LineVoice {
  const [speakingKey, setSpeakingKey] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const tokenRef = useRef(0);
  const resolveRef = useRef(options.resolve);
  resolveRef.current = options.resolve;

  const stop = useCallback(() => {
    tokenRef.current += 1;
    audioRef.current?.pause();
    audioRef.current = null;
    if (deviceSpeechAvailable()) window.speechSynthesis.cancel();
    setSpeakingKey(null);
  }, []);

  const speakWithDevice = useCallback((line: VoiceLine, token: number) => {
    if (!deviceSpeechAvailable()) {
      setSpeakingKey(null);
      return;
    }
    const utterance = new SpeechSynthesisUtterance(line.text_fr);
    utterance.lang = 'fr-FR';
    utterance.onend = () => {
      if (tokenRef.current === token) setSpeakingKey(null);
    };
    utterance.onerror = utterance.onend;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
  }, []);

  const speak = useCallback(
    (line: VoiceLine) => {
      if (speakingKey === line.key) {
        stop();
        return;
      }
      stop();
      const token = tokenRef.current;
      setSpeakingKey(line.key);
      void (async () => {
        let url = line.audio_url || null;
        if (!url && resolveRef.current) {
          try {
            url = await resolveRef.current(line);
          } catch {
            url = null;
          }
        }
        if (tokenRef.current !== token) return;
        if (!url) {
          speakWithDevice(line, token);
          return;
        }
        const audio = new Audio(url);
        audioRef.current = audio;
        audio.onended = () => {
          if (tokenRef.current === token) setSpeakingKey(null);
        };
        audio.play().catch(() => {
          if (tokenRef.current === token) speakWithDevice(line, token);
        });
      })();
    },
    [speakingKey, speakWithDevice, stop],
  );

  useEffect(() => stop, [stop]);

  const supported = typeof window === 'undefined' ? true : typeof Audio !== 'undefined' || deviceSpeechAvailable();
  return { speak, stop, speakingKey, supported };
}
