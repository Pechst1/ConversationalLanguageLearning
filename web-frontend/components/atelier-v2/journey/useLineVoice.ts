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
 *     manifest, or the journey's line-audio route: `journeyLineResolver`). It
 *     may return a bare URL, or `{ url, release }` when the URL is this hook's
 *     to revoke once the line has been said;
 *  3. the device's own French voice (`speechSynthesis`, a fr-FR voice picked
 *     explicitly, the same one per character), free and offline. The iOS
 *     WebView has it too.
 *
 * `useAutoSpeak` is the «Les personnages parlent à voix haute» half: a reply
 * says itself once as it arrives, when the learner has that setting on.
 *
 * Deliberately not here: pronunciation of any kind (WP-27 owner decision).
 */

import { useCallback, useEffect, useRef, useState } from 'react';

import { voicesAloud } from '@/lib/voice-preference';

import { pickFrenchVoice, speechSafetyMs, type ResolvedClip } from './line-audio';
import { autoplayKey, shouldAutoplay } from './voice-autoplay';

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
  /**
   * WP-116 phase 4: how far through the speaking line we are, 0…1, or null when
   * nothing speaks. Read it on animation frames (the drawn mouth follows it).
   * A clip reports its playback position; the device voice its word boundaries,
   * else the time elapsed against the line's expected length.
   */
  progress?: () => number | null;
};

export type LineVoiceOptions = {
  /**
   * A server clip for a line without `audio_url`; `null` means "use the device
   * voice". A `{ url, release }` is released when the line ends or is stopped.
   */
  resolve?: (line: VoiceLine) => Promise<string | ResolvedClip | null>;
};

/** Device speech rate: a touch under natural, for A1 ears. */
const DEVICE_RATE = 0.95;

function deviceSpeechAvailable(): boolean {
  return typeof window !== 'undefined' && 'speechSynthesis' in window && 'SpeechSynthesisUtterance' in window;
}

function deviceVoices(): SpeechSynthesisVoice[] {
  try {
    return deviceSpeechAvailable() ? window.speechSynthesis.getVoices() : [];
  } catch {
    return [];
  }
}

export function useLineVoice(options: LineVoiceOptions = {}): LineVoice {
  const [speakingKey, setSpeakingKey] = useState<string | null>(null);
  const speakingRef = useRef<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const releaseRef = useRef<(() => void) | null>(null);
  const safetyRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const tokenRef = useRef(0);
  // WP-116 phase 4: where the speaking line is, for the drawn mouth.
  const clockRef = useRef<{ started: number; expectMs: number; chars: number; boundary: number } | null>(null);
  const resolveRef = useRef(options.resolve);
  resolveRef.current = options.resolve;

  const setSpeaking = useCallback((key: string | null) => {
    speakingRef.current = key;
    if (!key) clockRef.current = null;
    setSpeakingKey(key);
  }, []);

  const progress = useCallback((): number | null => {
    if (!speakingRef.current) return null;
    const audio = audioRef.current;
    if (audio && Number.isFinite(audio.duration) && audio.duration > 0) {
      return Math.min(1, audio.currentTime / audio.duration);
    }
    const clock = clockRef.current;
    if (!clock) return null;
    const elapsed = (Date.now() - clock.started) / clock.expectMs;
    // Word boundaries from the device voice, when it sends them, keep time honest.
    const said = clock.chars > 0 && clock.boundary > 0 ? clock.boundary / clock.chars : 0;
    return Math.min(0.999, Math.max(elapsed, said));
  }, []);

  // Some engines (Chrome, the iOS WebView on a cold start) list their voices
  // only after `voiceschanged`; ask once so the first tap finds fr-FR.
  useEffect(() => {
    if (!deviceSpeechAvailable()) return undefined;
    const synth = window.speechSynthesis;
    const load = () => void deviceVoices();
    load();
    synth.addEventListener?.('voiceschanged', load);
    return () => synth.removeEventListener?.('voiceschanged', load);
  }, []);

  /** Let go of the current sound: the element, its URL, the safety timer. */
  const releaseCurrent = useCallback(() => {
    if (safetyRef.current) clearTimeout(safetyRef.current);
    safetyRef.current = null;
    const audio = audioRef.current;
    audioRef.current = null;
    if (audio) {
      audio.onended = null;
      audio.onerror = null;
      audio.pause();
    }
    const release = releaseRef.current;
    releaseRef.current = null;
    release?.();
  }, []);

  const stop = useCallback(() => {
    tokenRef.current += 1;
    releaseCurrent();
    if (deviceSpeechAvailable()) window.speechSynthesis.cancel();
    setSpeaking(null);
  }, [releaseCurrent, setSpeaking]);

  const finish = useCallback(
    (token: number) => {
      if (tokenRef.current !== token) return;
      releaseCurrent();
      setSpeaking(null);
    },
    [releaseCurrent, setSpeaking],
  );

  const speakWithDevice = useCallback(
    (line: VoiceLine, token: number) => {
      if (!deviceSpeechAvailable() || !line.text_fr.trim()) {
        finish(token);
        return;
      }
      const utterance = new SpeechSynthesisUtterance(line.text_fr);
      utterance.lang = 'fr-FR';
      utterance.rate = DEVICE_RATE;
      const voice = pickFrenchVoice(deviceVoices(), line.character_id);
      if (voice) utterance.voice = voice;
      utterance.onend = () => finish(token);
      utterance.onerror = () => finish(token);
      const text = line.text_fr;
      clockRef.current = { started: Date.now(), expectMs: Math.max(600, text.length * 70 / DEVICE_RATE), chars: text.length, boundary: 0 };
      utterance.onboundary = (event: SpeechSynthesisEvent) => {
        if (clockRef.current && tokenRef.current === token) clockRef.current.boundary = event.charIndex;
      };
      // A blocked or silent engine never fires `end`: the ring comes down anyway.
      safetyRef.current = setTimeout(() => finish(token), speechSafetyMs(line.text_fr));
      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(utterance);
    },
    [finish],
  );

  const speak = useCallback(
    (line: VoiceLine) => {
      if (speakingRef.current === line.key) {
        stop();
        return;
      }
      stop();
      const token = tokenRef.current;
      setSpeaking(line.key);
      void (async () => {
        let url = line.audio_url || null;
        let release: (() => void) | null = null;
        if (!url && resolveRef.current) {
          try {
            const resolved = await resolveRef.current(line);
            if (typeof resolved === 'string') url = resolved || null;
            else if (resolved) {
              url = resolved.url || null;
              release = resolved.release ?? null;
            }
          } catch {
            url = null;
          }
        }
        if (tokenRef.current !== token) {
          release?.();
          return;
        }
        if (!url || typeof Audio === 'undefined') {
          release?.();
          speakWithDevice(line, token);
          return;
        }
        releaseRef.current = release;
        const audio = new Audio(url);
        audioRef.current = audio;
        audio.onended = () => finish(token);
        audio.onerror = () => {
          if (tokenRef.current !== token) return;
          releaseCurrent();
          speakWithDevice(line, token);
        };
        audio.play().catch(() => {
          if (tokenRef.current !== token) return;
          releaseCurrent();
          speakWithDevice(line, token);
        });
      })();
    },
    [finish, releaseCurrent, setSpeaking, speakWithDevice, stop],
  );

  // Leaving the screen stops the voice and revokes whatever it held.
  useEffect(() => stop, [stop]);

  const supported = typeof window === 'undefined' ? true : typeof Audio !== 'undefined' || deviceSpeechAvailable();
  return { speak, stop, speakingKey, supported, progress };
}

/**
 * «Les personnages parlent à voix haute»: say `line` once, unasked, when
 * `ready` (the reply has finished typing in) and the setting is on. Never twice
 * for the same line in a session (`voice-autoplay.ts`). `scope` separates
 * lines that share a key on different steps (pass the step id).
 */
export function useAutoSpeak(
  voice: LineVoice | null | undefined,
  line: VoiceLine | null,
  ready: boolean,
  scope?: string | null,
): void {
  const key = line ? autoplayKey(scope, line.key, line.text_fr) : null;
  const lineRef = useRef(line);
  lineRef.current = line;
  const speak = voice?.speak;
  const supported = Boolean(voice?.supported);
  useEffect(() => {
    const current = lineRef.current;
    if (!speak || !supported || !current) return;
    if (shouldAutoplay({ enabled: voicesAloud(), ready, key })) speak(current);
  }, [key, ready, speak, supported]);
}
