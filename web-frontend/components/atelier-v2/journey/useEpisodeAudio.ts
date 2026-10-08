/**
 * WP-32 — the *écouter* stage's plumbing, and nothing else.
 *
 * The pedagogy of the radio episode lives in `story-episode-model.ts` (the
 * predict → listen → verify → retain machine) and in the component. This hook
 * owns only the awkward half: a manifest that may not exist yet, an
 * authenticated audio route a `<audio src>` cannot reach, and five different
 * ways a device can decline to make a sound.
 *
 * Three rules it keeps:
 *
 *  * **Nothing is paid for until the learner asks.** `prepare()` reads the
 *    cache first (`GET`) and only synthesizes (`POST`) when the episode has
 *    never been spoken. A learner who opens the scene and changes their mind
 *    has cost nothing.
 *  * **Every failure is a state with a sentence, never a dead end.** The four
 *    reasons a device or a provider can refuse are distinguished, because
 *    "the feature is off" and "your phone is offline" are different facts and
 *    the learner is owed the right one. In all of them the text scene is still
 *    there, which is what the component falls back to.
 *  * **It cleans up after itself.** Blob URLs are revoked and playback stops on
 *    unmount, so leaving mid-episode does not leave a character talking to an
 *    empty screen.
 *
 * Deliberately not here: pronunciation of any kind. WP-27's owner decision —
 * nothing in this app measures, scores or describes how a learner sounds —
 * applies to listening too. The audio is input; it is never a microphone.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import {
  getEpisodeAudio,
  getEpisodeAudioClip,
  synthesizeEpisodeAudio,
} from '@/services/daily-journey';
import type { EpisodeAudioClipRef, EpisodeAudioManifest } from '@/services/api';

/** Why there is no audio. Each maps to one honest sentence in the copy table. */
export type EpisodeAudioUnavailable =
  /** `ATELIER_EPISODE_AUDIO_ENABLED` is off. Not an error; not the learner's problem. */
  | 'disabled'
  /** The device cannot play audio at all (a WebView without an `Audio`). */
  | 'unsupported'
  /** No connection: the manifest and the clips are both network calls. */
  | 'offline'
  /** The provider did not answer, or answered unusably. */
  | 'failed'
  /** The scene holds no speakable line. Rare, and not a failure. */
  | 'empty';

export type EpisodeAudioState =
  | { kind: 'idle' }
  /** The manifest is being read, or the episode is being spoken for the first time. */
  | { kind: 'preparing' }
  | { kind: 'ready'; clips: EpisodeAudioClipRef[] }
  | { kind: 'playing'; clips: EpisodeAudioClipRef[]; index: number }
  /** Played to the end at least once. */
  | { kind: 'played'; clips: EpisodeAudioClipRef[] }
  | { kind: 'unavailable'; reason: EpisodeAudioUnavailable };

export type UseEpisodeAudio = {
  state: EpisodeAudioState;
  /** The clips, in playback order. Empty unless the episode is spoken. */
  clips: EpisodeAudioClipRef[];
  /** Read the cache, and synthesize only if it is empty. */
  prepare: () => void;
  /** Play from the top. */
  play: () => void;
  /** Play one line again — the replay a learner actually wants. */
  playFrom: (index: number) => void;
  stop: () => void;
  /** True while a request or a sound is in flight. */
  busy: boolean;
  /** True once the episode has been heard through at least once. */
  heard: boolean;
};

function audioSupported(): boolean {
  return typeof window !== 'undefined' && typeof window.Audio === 'function';
}

function offline(): boolean {
  return typeof navigator !== 'undefined' && navigator.onLine === false;
}

function unavailableFor(manifest: EpisodeAudioManifest): EpisodeAudioUnavailable | null {
  if (manifest.status === 'disabled') return 'disabled';
  if (manifest.status === 'empty') return 'empty';
  if (manifest.status === 'failed') return 'failed';
  return null;
}

export function useEpisodeAudio({
  sceneId,
  enabled,
}: {
  sceneId: string | null;
  /** The learner's «Écouter d'abord» choice. False means: never call anything. */
  enabled: boolean;
}): UseEpisodeAudio {
  const [state, setState] = useState<EpisodeAudioState>({ kind: 'idle' });
  const [heard, setHeard] = useState(false);
  const alive = useRef(true);
  const element = useRef<HTMLAudioElement | null>(null);
  /** clip id → object URL. One fetch per line per visit, at most. */
  const urls = useRef<Map<string, string>>(new Map());
  /** Guards a double tap on «Écouter» from starting two synthesis calls. */
  const inFlight = useRef(false);
  /**
   * Which playback run owns the player.
   *
   * `stop()` and a second `playFrom()` both bump it, and the loop checks it
   * between lines. Without this a stopped episode kept talking: the loop was
   * only bound to unmount, so pausing the element simply let the *next* line
   * start a moment later.
   */
  const run = useRef(0);

  useEffect(() => {
    alive.current = true;
    // Captured here rather than read in the cleanup: the lint rule is right
    // that a ref may point elsewhere by then, and these two are the ones that
    // must be released for *this* mount.
    const player = element;
    const held = urls.current;
    return () => {
      alive.current = false;
      run.current += 1;
      if (player.current) {
        player.current.pause();
        player.current.src = '';
      }
      held.forEach((url) => URL.revokeObjectURL(url));
      held.clear();
    };
  }, []);

  // A different scene is a different episode: drop everything rather than let
  // yesterday's voices play under today's words.
  useEffect(() => {
    setState({ kind: 'idle' });
    setHeard(false);
    inFlight.current = false;
    run.current += 1;
    const player = element.current;
    if (player) player.pause();
    urls.current.forEach((url) => URL.revokeObjectURL(url));
    urls.current.clear();
  }, [sceneId]);

  const clipUrl = useCallback(
    async (clip: EpisodeAudioClipRef): Promise<string> => {
      const cached = urls.current.get(clip.id);
      if (cached) return cached;
      const blob = await getEpisodeAudioClip(String(sceneId), clip.id);
      const url = URL.createObjectURL(blob);
      urls.current.set(clip.id, url);
      return url;
    },
    [sceneId],
  );

  const prepare = useCallback(() => {
    if (!enabled || !sceneId) return;
    if (inFlight.current) return;
    if (!audioSupported()) {
      setState({ kind: 'unavailable', reason: 'unsupported' });
      return;
    }
    if (offline()) {
      setState({ kind: 'unavailable', reason: 'offline' });
      return;
    }
    inFlight.current = true;
    setState({ kind: 'preparing' });
    void (async () => {
      try {
        let manifest = await getEpisodeAudio(sceneId);
        // `absent` is the only status worth paying for; every other one is
        // already an answer.
        if (manifest.status === 'absent') {
          manifest = await synthesizeEpisodeAudio(sceneId);
        }
        if (!alive.current) return;
        const reason = unavailableFor(manifest);
        if (reason) {
          setState({ kind: 'unavailable', reason });
          return;
        }
        if (!manifest.clips.length) {
          setState({ kind: 'unavailable', reason: 'empty' });
          return;
        }
        setState({ kind: 'ready', clips: [...manifest.clips].sort((a, b) => a.ordinal - b.ordinal) });
      } catch {
        if (!alive.current) return;
        // A transport error the learner can act on is offline; anything else is
        // the provider's or ours, and says so.
        setState({ kind: 'unavailable', reason: offline() ? 'offline' : 'failed' });
      } finally {
        inFlight.current = false;
      }
    })();
  }, [enabled, sceneId]);

  const stop = useCallback(() => {
    run.current += 1;
    const player = element.current;
    if (player) player.pause();
    setState((current) =>
      current.kind === 'playing'
        ? heard
          ? { kind: 'played', clips: current.clips }
          : { kind: 'ready', clips: current.clips }
        : current,
    );
  }, [heard]);

  const playFrom = useCallback(
    (start: number) => {
      setState((current) => {
        const clips =
          current.kind === 'ready' || current.kind === 'playing' || current.kind === 'played'
            ? current.clips
            : [];
        if (!clips.length) return current;
        const from = Math.min(Math.max(0, start), clips.length - 1);

        run.current += 1;
        const token = run.current;
        const live = () => alive.current && run.current === token;

        void (async () => {
          if (!element.current) element.current = new Audio();
          const player = element.current;
          for (let index = from; index < clips.length; index += 1) {
            if (!live()) return;
            let url: string;
            try {
              url = await clipUrl(clips[index]);
            } catch {
              if (live()) {
                setState({ kind: 'unavailable', reason: offline() ? 'offline' : 'failed' });
              }
              return;
            }
            if (!live()) return;
            setState({ kind: 'playing', clips, index });
            const finished = await new Promise<boolean>((resolve) => {
              player.onended = () => resolve(true);
              // A browser that refuses to start (autoplay policy, decode error)
              // must not leave the stage stuck on «lecture en cours».
              player.onerror = () => resolve(false);
              player.src = url;
              const started = player.play();
              if (started && typeof started.catch === 'function') {
                started.catch(() => resolve(false));
              }
            });
            player.onended = null;
            player.onerror = null;
            if (!finished) {
              // A `stop()` pauses the element, which also resolves `false` on
              // some browsers. A superseded run says nothing: the state it would
              // write belongs to whoever owns the player now.
              if (live()) setState({ kind: 'unavailable', reason: 'failed' });
              return;
            }
            // A stop() between two lines takes the playback with it.
            if (!live()) return;
          }
          if (!live()) return;
          setHeard(true);
          setState({ kind: 'played', clips });
        })();

        return { kind: 'playing', clips, index: from };
      });
    },
    [clipUrl],
  );

  const play = useCallback(() => playFrom(0), [playFrom]);

  const clips = useMemo(
    () =>
      state.kind === 'ready' || state.kind === 'playing' || state.kind === 'played'
        ? state.clips
        : [],
    [state],
  );

  return {
    state,
    clips,
    prepare,
    play,
    playFrom,
    stop,
    busy: state.kind === 'preparing' || state.kind === 'playing',
    heard,
  };
}

export default useEpisodeAudio;
