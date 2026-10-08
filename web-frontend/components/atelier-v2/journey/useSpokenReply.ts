/**
 * WP-158 slice 1 — the microphone side of «Parler» in a story reply.
 *
 * Capture (MediaRecorder; it stops itself at 30 s), transcribe through
 * `POST /audio/transcribe` with the `story_reply` surface and the turn's
 * journey and step, hand the text back. Like WP-27's `useVoiceAnswer` it never
 * submits and never grades: the respond step owns sending, and sends through the
 * same reply endpoint as a typed answer.
 *
 * There is no native recorder plugin in this app (`package.json` declares only
 * haptics, push and secure storage), so the iPhone build records through
 * WKWebView's MediaRecorder (iOS 14.3+, AAC in MP4; `lib/audio-recording.ts`
 * picks the type). Microphone permission, an incoming call mid-recording and
 * background audio are real-device checks, listed in the WP-158 PR.
 *
 * `spokenClock.now` is the one clock both the countdowns and the tests read.
 */

import { useCallback, useEffect, useRef, useState } from 'react';

import { createAudioMediaRecorder, recordedAudioBlob } from '@/lib/audio-recording';
import { apiService } from '@/services/api';

import {
  SPOKEN_EMPTY_BYTES,
  SPOKEN_IDLE,
  STORY_REPLY_SURFACE,
  failureFromResponse,
  recordingIsOver,
  spokenReplyReduce,
  type SpokenReplyEvent,
  type SpokenReplyState,
} from './spoken-reply';

/** Replaceable in tests; `Date.now` everywhere else. */
export const spokenClock = { now: (): number => Date.now() };

/** How often the countdowns repaint while one is running. */
const TICK_MS = 250;

export type SpokenReplyController = {
  state: SpokenReplyState;
  /** The clock reading the countdowns were last drawn at. */
  now: number;
  start: () => Promise<void>;
  stop: () => void;
  hold: () => void;
  markSubmitted: () => void;
  reset: () => void;
  /** Re-read the clock (the interval calls it; tests may too). */
  tick: () => void;
};

function offline(): boolean {
  return typeof navigator !== 'undefined' && navigator.onLine === false;
}

type HttpError = { response?: { status?: number; data?: { detail?: { code?: string } } } };

export function useSpokenReply(
  journeyId: string | null | undefined,
  stepId: string | null | undefined,
): SpokenReplyController {
  const [state, setState] = useState<SpokenReplyState>(SPOKEN_IDLE);
  const [now, setNow] = useState<number>(() => spokenClock.now());
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const aliveRef = useRef(true);
  const stateRef = useRef<SpokenReplyState>(SPOKEN_IDLE);
  // A reset (new turn, «Écrire») stops the recorder; what it captured is dropped,
  // never uploaded, so an abandoned sentence costs nothing.
  const cancelledRef = useRef(false);

  const send = useCallback((event: SpokenReplyEvent) => {
    if (!aliveRef.current) return;
    const next = spokenReplyReduce(stateRef.current, event);
    stateRef.current = next;
    setState(next);
  }, []);

  const release = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    recorderRef.current = null;
  }, []);

  useEffect(() => {
    aliveRef.current = true;
    return () => {
      aliveRef.current = false;
      cancelledRef.current = true;
      try {
        recorderRef.current?.stop();
      } catch {
        /* already stopped */
      }
      release();
    };
  }, [release]);

  const stop = useCallback(() => {
    send({ type: 'stop' });
    try {
      recorderRef.current?.stop();
    } catch {
      release();
      send({ type: 'fail', reason: 'failed' });
    }
  }, [release, send]);

  const tick = useCallback(() => {
    const at = spokenClock.now();
    setNow(at);
    // The 30 s cap is the recorder's own: nobody has to tap «Arrêter».
    if (recordingIsOver(stateRef.current, at)) stop();
  }, [stop]);

  const counting = state.kind === 'recording' || (state.kind === 'confirm' && !state.held);
  useEffect(() => {
    if (!counting || typeof setInterval === 'undefined') return undefined;
    const handle = setInterval(tick, TICK_MS) as unknown as { unref?: () => void };
    // Node (tests) must not be kept alive by a countdown nobody unmounts.
    handle?.unref?.();
    return () => clearInterval(handle as unknown as ReturnType<typeof setInterval>);
  }, [counting, tick]);

  const start = useCallback(async () => {
    send({ type: 'start' });
    if (!journeyId || !stepId) {
      send({ type: 'fail', reason: 'unsupported' });
      return;
    }
    if (typeof navigator === 'undefined' || !navigator.mediaDevices?.getUserMedia) {
      send({ type: 'fail', reason: 'unsupported' });
      return;
    }
    if (offline()) {
      // Transcription is a network call: say so before the sentence is spent.
      send({ type: 'fail', reason: 'offline' });
      return;
    }
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      send({ type: 'fail', reason: 'permission' });
      return;
    }
    let recorder: MediaRecorder;
    try {
      recorder = createAudioMediaRecorder(stream);
    } catch {
      stream.getTracks().forEach((track) => track.stop());
      send({ type: 'fail', reason: 'unsupported' });
      return;
    }
    streamRef.current = stream;
    recorderRef.current = recorder;
    chunksRef.current = [];
    cancelledRef.current = false;
    recorder.ondataavailable = (event: BlobEvent) => {
      if (event.data?.size) chunksRef.current.push(event.data);
    };
    recorder.onstop = () => {
      const blob = recordedAudioBlob(chunksRef.current, recorder);
      release();
      if (cancelledRef.current) return;
      if (blob.size < SPOKEN_EMPTY_BYTES) {
        send({ type: 'fail', reason: 'empty' });
        return;
      }
      if (offline()) {
        send({ type: 'fail', reason: 'offline' });
        return;
      }
      void apiService
        .transcribeAudio(blob, STORY_REPLY_SURFACE, { journeyId, stepId })
        .then((text: string) => {
          const at = spokenClock.now();
          setNow(at);
          send({ type: 'transcribed', text: String(text || ''), at });
        })
        .catch((error: HttpError) =>
          send({
            type: 'fail',
            reason: failureFromResponse(error?.response?.status, error?.response?.data?.detail?.code),
          }),
        );
    };
    try {
      recorder.start();
    } catch {
      release();
      send({ type: 'fail', reason: 'unsupported' });
      return;
    }
    const at = spokenClock.now();
    setNow(at);
    send({ type: 'recording', at });
  }, [journeyId, stepId, release, send]);

  const hold = useCallback(() => send({ type: 'hold' }), [send]);
  const markSubmitted = useCallback(() => send({ type: 'submitted' }), [send]);
  const reset = useCallback(() => {
    cancelledRef.current = true;
    try {
      recorderRef.current?.stop();
    } catch {
      /* nothing was running */
    }
    release();
    send({ type: 'reset' });
  }, [release, send]);

  return { state, now, start, stop, hold, markSubmitted, reset, tick };
}
