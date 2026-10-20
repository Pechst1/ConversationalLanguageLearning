/**
 * Les appels — hold to talk.
 *
 * Press: the recorder starts (it stops itself at 30 s). Let go: the recording is
 * transcribed on the `appel` surface, booked against the call, and the text is
 * handed back. Like WP-158's `useSpokenReply` it never grades and never submits by
 * itself: the call screen sends the text as the learner's line.
 */

import { useCallback, useEffect, useRef, useState } from 'react';

import { APPEL_SURFACE } from '@/lib/appels-api';
import { createAudioMediaRecorder, recordedAudioBlob } from '@/lib/audio-recording';
import { apiService } from '@/services/api';

/** Below this the recording is a tap, not a sentence. */
const EMPTY_BYTES = 1200;
const MAX_MS = 30_000;

export type RecorderPhase = 'idle' | 'recording' | 'transcribing';
export type RecorderFailure = 'unsupported' | 'permission' | 'empty' | 'failed' | 'ceiling';

export type CallRecorder = {
  phase: RecorderPhase;
  failure: RecorderFailure | null;
  start: () => Promise<void>;
  stop: () => void;
  cancel: () => void;
};

type HttpError = { response?: { status?: number } };

export function useCallRecorder(callId: string | null, onText: (text: string) => void): CallRecorder {
  const [phase, setPhase] = useState<RecorderPhase>('idle');
  const [failure, setFailure] = useState<RecorderFailure | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const cancelledRef = useRef(false);
  const capRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Let go before the microphone opened: stop as soon as it does.
  const stopSoonRef = useRef(false);
  const onTextRef = useRef(onText);
  onTextRef.current = onText;

  const release = useCallback(() => {
    if (capRef.current) clearTimeout(capRef.current);
    capRef.current = null;
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    recorderRef.current = null;
  }, []);

  useEffect(
    () => () => {
      cancelledRef.current = true;
      try {
        recorderRef.current?.stop();
      } catch {
        /* already stopped */
      }
      release();
    },
    [release],
  );

  const stop = useCallback(() => {
    if (!recorderRef.current) {
      stopSoonRef.current = true;
      return;
    }
    try {
      recorderRef.current?.stop();
    } catch {
      release();
      setPhase('idle');
    }
  }, [release]);

  const start = useCallback(async () => {
    if (!callId || phase !== 'idle') return;
    setFailure(null);
    stopSoonRef.current = false;
    if (typeof navigator === 'undefined' || !navigator.mediaDevices?.getUserMedia) {
      setFailure('unsupported');
      return;
    }
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      setFailure('permission');
      return;
    }
    let recorder: MediaRecorder;
    try {
      recorder = createAudioMediaRecorder(stream);
    } catch {
      stream.getTracks().forEach((track) => track.stop());
      setFailure('unsupported');
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
      if (cancelledRef.current) {
        setPhase('idle');
        return;
      }
      if (blob.size < EMPTY_BYTES) {
        setPhase('idle');
        setFailure('empty');
        return;
      }
      setPhase('transcribing');
      void apiService
        .transcribeAudio(blob, APPEL_SURFACE, { callId })
        .then((text: string) => {
          setPhase('idle');
          const said = String(text || '').trim();
          if (said) onTextRef.current(said);
          else setFailure('empty');
        })
        .catch((error: HttpError) => {
          setPhase('idle');
          setFailure(error?.response?.status === 429 ? 'ceiling' : 'failed');
        });
    };
    try {
      recorder.start();
    } catch {
      release();
      setFailure('unsupported');
      return;
    }
    setPhase('recording');
    capRef.current = setTimeout(() => stop(), MAX_MS);
    if (stopSoonRef.current) stop();
  }, [callId, phase, release, stop]);

  const cancel = useCallback(() => {
    cancelledRef.current = true;
    stop();
  }, [stop]);

  return { phase, failure, start, stop, cancel };
}
