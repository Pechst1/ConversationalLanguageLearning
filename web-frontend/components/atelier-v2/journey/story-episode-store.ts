/**
 * WP-90 «La planche» — the day's story episode, held above the step.
 *
 * The scene step used to own its episode lookup and its panel-art poll, so the
 * poll died the moment the learner left the step: the drawings that arrived a
 * minute after commit were never seen again that day. The journey controller
 * (`useDailyJourney`) now drives the lookup and the poll; this module is the
 * cache both it and the steps read, keyed by journey id.
 *
 * Deliberately tiny and transport-free: the caller passes the fetcher, so the
 * node suite can drive it without a network and without React.
 */

import { useEffect, useState } from 'react';

import type { StoryEpisode } from '@/types/daily-journey';

export type StoryEpisodeEntry =
  | { kind: 'loading' }
  | { kind: 'none' }
  | { kind: 'episode'; episode: StoryEpisode };

export type StoryEpisodeFetcher = (journeyId: string) => Promise<StoryEpisode | null>;

const entries = new Map<string, StoryEpisodeEntry>();
const inflight = new Map<string, Promise<StoryEpisodeEntry>>();
const listeners = new Set<() => void>();

function emit() {
  listeners.forEach((listener) => listener());
}

export function getStoryEpisodeEntry(journeyId: string | null | undefined): StoryEpisodeEntry | undefined {
  return journeyId ? entries.get(journeyId) : undefined;
}

export function setStoryEpisodeEntry(journeyId: string, entry: StoryEpisodeEntry): void {
  if (!journeyId) return;
  entries.set(journeyId, entry);
  emit();
}

/** Forget everything (tests; a signed-out learner). */
export function clearStoryEpisodes(): void {
  entries.clear();
  inflight.clear();
  emit();
}

/**
 * Read the episode for a journey. One request per journey at a time: a second
 * caller while one is in flight awaits the first. A cached episode is kept
 * while a re-read is in flight, so a poll never flashes the reader back to a
 * loading state; a failed re-read keeps what was there.
 */
export function loadStoryEpisode(
  journeyId: string,
  fetcher: StoryEpisodeFetcher,
): Promise<StoryEpisodeEntry> {
  if (!journeyId) return Promise.resolve({ kind: 'none' });
  const running = inflight.get(journeyId);
  if (running) return running;
  const before = entries.get(journeyId);
  if (!before) setStoryEpisodeEntry(journeyId, { kind: 'loading' });
  const request = Promise.resolve()
    .then(() => fetcher(journeyId))
    .then(
      (episode): StoryEpisodeEntry =>
        episode && episode.panels?.length ? { kind: 'episode', episode } : { kind: 'none' },
      // The projection is optional. A failed lookup is not a failed scene —
      // and a failed re-read is not a reason to drop the episode on screen.
      (): StoryEpisodeEntry => (before && before.kind === 'episode' ? before : { kind: 'none' }),
    )
    .then((entry) => {
      inflight.delete(journeyId);
      setStoryEpisodeEntry(journeyId, entry);
      return entry;
    });
  inflight.set(journeyId, request);
  return request;
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/**
 * The cached entry for a journey; `undefined` until someone asks for it.
 * Plain state + a subscription (not `useSyncExternalStore`), so the journey's
 * node harness — which fakes the classic hooks — drives it like any other.
 * Server rendering has no cache: the step renders its plain scene.
 */
export function useStoryEpisodeEntry(journeyId: string | null | undefined): StoryEpisodeEntry | undefined {
  const [entry, setEntry] = useState<StoryEpisodeEntry | undefined>(() =>
    typeof window === 'undefined' ? undefined : getStoryEpisodeEntry(journeyId),
  );
  useEffect(() => {
    const read = () => setEntry(getStoryEpisodeEntry(journeyId));
    read();
    return subscribe(read);
  }, [journeyId]);
  return entry;
}
