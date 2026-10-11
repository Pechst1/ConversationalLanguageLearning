/**
 * WP-27 — the microphone side of the voice-first respond beat.
 *
 * Capture, transcribe, hand the text back. It never submits, never grades and
 * never says anything about how the sentence sounded (owner decision: **no
 * pronunciation scoring, ever**). The daily-journey controller keeps its own
 * unrelated voice fields; this hook lives beside it so the respond step can be
 * voice-first without reopening `useDailyJourney.ts`, which is under a
 * concurrent lease.
 */

import { useCallback, useEffect, useRef, useState } from 'react';

import { createAudioMediaRecorder, recordedAudioBlob } from '@/lib/audio-recording';
import { apiService } from '@/services/api';

import {
  IDLE,
  voiceAnswerReduce,
  type VoiceAnswerEvent,
  type VoiceAnswerState,
} from './voice-answer';

/** Under this many bytes the microphone captured nothing worth transcribing. */
const EMPTY_RECORDING_BYTES = 1200;

export type VoiceAnswerController = {
  state: VoiceAnswerState;
  start: () => Promise<void>;
  stop: () => void;
  reset: () => void;
};

function offline(): boolean {
  return typeof navigator !== 'undefined' && navigator.onLine === false;
}

export function useVoiceAnswer(): VoiceAnswerController {
  const [state, setState] = useState<VoiceAnswerState>(IDLE);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const aliveRef = useRef(true);

  const send = useCallback((event: VoiceAnswerEvent) => {
    if (!aliveRef.current) return;
    setState((current) => voiceAnswerReduce(current, event));
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
      try {
        recorderRef.current?.stop();
      } catch {
        /* already stopped */
      }
      release();
    };
  }, [release]);

  const start = useCallback(async () => {
    send({ type: 'start' });
    if (typeof navigator === 'undefined' || !navigator.mediaDevices?.getUserMedia) {
      send({ type: 'fail', reason: 'unsupported' });
      return;
    }
    if (offline()) {
      // Transcription is a network call. Saying so before recording is honest;
      // recording first and failing after would waste the learner's sentence.
      send({ type: 'fail', reason: 'offline' });
      return;
    }
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      // Denied at the OS prompt, or no input device. Either way the text path
      // is the answer, and the caller switches to it.
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
    recorder.ondataavailable = (event: BlobEvent) => {
      if (event.data?.size) chunksRef.current.push(event.data);
    };
    recorder.onstop = () => {
      const blob = recordedAudioBlob(chunksRef.current, recorder);
      release();
      if (blob.size < EMPTY_RECORDING_BYTES) {
        send({ type: 'fail', reason: 'empty' });
        return;
      }
      if (offline()) {
        send({ type: 'fail', reason: 'offline' });
        return;
      }
      void apiService
        .transcribeAudio(blob, 'journey_respond')
        .then((text: string) => send({ type: 'transcribed', text: String(text || '') }))
        .catch(() => send({ type: 'fail', reason: 'failed' }));
    };
    try {
      recorder.start();
    } catch {
      release();
      send({ type: 'fail', reason: 'unsupported' });
      return;
    }
    send({ type: 'recording' });
  }, [release, send]);

  const stop = useCallback(() => {
    send({ type: 'stop' });
    try {
      recorderRef.current?.stop();
    } catch {
      release();
      send({ type: 'fail', reason: 'failed' });
    }
  }, [release, send]);

  const reset = useCallback(() => {
    try {
      recorderRef.current?.stop();
    } catch {
      /* nothing was running */
    }
    release();
    send({ type: 'reset' });
  }, [release, send]);

  return { state, start, stop, reset };
}
