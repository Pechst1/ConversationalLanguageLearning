/**
 * Ton personnage — the learner's own drawn character, for every screen that shows it.
 *
 * Like `useLearnerProfile` it never blocks a render: it starts empty (so the server and the
 * first client render agree), settles on the copy cached in `localStorage` by the last load,
 * then on one coalesced `GET /avatar`. A save writes the cache too, so the Cahier's disc and
 * the profile show the new character the moment the editor closes.
 *
 * `rewards` lists every item an achievement unlocks, locked or not, with the learner's
 * progress towards it; `unlocked` the ones they may wear.
 *
 * The cache key is under `pilot:`, so sign-out and an account switch sweep it with the other
 * learner caches (`clearPilotResilience`) and a second account never starts from this one's.
 */

import { useCallback, useEffect, useState } from 'react';

import apiService, { type AvatarRewardState, type AvatarStatePayload } from '@/services/api';

import type { AvatarConfig } from './avatar';
import { normalizeAvatar, readAvatar } from './avatar';
import { oncePerLoad } from './once-per-load';

export const AVATAR_STORAGE_KEY = 'pilot:avatar:v1';

export type AvatarLoad = 'loading' | 'ready' | 'failed';

export interface LearnerAvatarState {
  avatar: AvatarConfig | null;
  unlocked: string[];
  rewards: AvatarRewardState[];
  /** `ready` once the server answered; a cached character may show before that */
  load: AvatarLoad;
}

type Cached = { avatar: AvatarConfig | null; unlocked: string[] };

const EMPTY: LearnerAvatarState = { avatar: null, unlocked: [], rewards: [], load: 'loading' };

/** What the server sent, as the hook's state. */
export function avatarStateFrom(payload: AvatarStatePayload | null | undefined): LearnerAvatarState {
  const unlocked = Array.isArray(payload?.unlocked) ? payload!.unlocked.filter((item) => typeof item === 'string') : [];
  return {
    avatar: readAvatar(payload?.avatar),
    unlocked,
    rewards: Array.isArray(payload?.rewards) ? payload!.rewards : [],
    load: 'ready',
  };
}

/** Persist the character and the items held. Safe in private mode. */
export function rememberAvatar(state: Cached): void {
  try {
    window.localStorage.setItem(AVATAR_STORAGE_KEY, JSON.stringify({ avatar: state.avatar, unlocked: state.unlocked }));
  } catch {
    // Storage can be denied outright; the character is simply fetched again.
  }
}

/** The cached character, for a quick first paint. Never throws. */
export function readCachedAvatar(): Cached | null {
  try {
    const raw = window.localStorage.getItem(AVATAR_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object') return null;
    return {
      avatar: readAvatar(parsed.avatar),
      unlocked: Array.isArray(parsed.unlocked) ? parsed.unlocked.filter((item: unknown) => typeof item === 'string') : [],
    };
  } catch {
    return null;
  }
}

export type AvatarSaveResult =
  | { ok: true; state: LearnerAvatarState }
  /** the server refused an item not earned yet */
  | { ok: false; reason: 'locked'; item: string | null }
  | { ok: false; reason: 'failed' };

/** Read a refused save: the server names a locked item in a 403's detail. */
export function saveFailure(error: unknown): Exclude<AvatarSaveResult, { ok: true }> {
  const response = (error as { response?: { status?: number; data?: { detail?: unknown } } })?.response;
  const detail = response?.data?.detail as { code?: unknown; item?: unknown } | undefined;
  if (response?.status === 403 && detail && detail.code === 'avatar_item_locked') {
    return { ok: false, reason: 'locked', item: typeof detail.item === 'string' ? detail.item : null };
  }
  return { ok: false, reason: 'failed' };
}

/* Every mounted hook hears a save, so the disc in a header and the profile below it agree. */
const listeners = new Set<(state: LearnerAvatarState) => void>();
/* Saves so far this page load: a read that started before the latest one is out of date. */
let saves = 0;

/**
 * One coalesced `GET /avatar`, or `null` when a save landed while it was in flight (the save's
 * answer is newer). The coalescing key moves on with each save, so a read shared from before
 * it can never be handed to a screen that mounts after it.
 */
export async function fetchLearnerAvatar(): Promise<LearnerAvatarState | null> {
  const generation = saves;
  const payload = await oncePerLoad(`avatar:${generation}`, () => apiService.getAvatar());
  return generation === saves ? avatarStateFrom(payload) : null;
}

/** Save the whole record (only the ids the editor knows, items held or not checked here). */
export async function saveLearnerAvatar(config: AvatarConfig): Promise<AvatarSaveResult> {
  try {
    const payload = await apiService.saveAvatar({ ...normalizeAvatar(config) });
    const state = avatarStateFrom(payload);
    saves += 1;
    rememberAvatar(state);
    listeners.forEach((listener) => listener(state));
    return { ok: true, state };
  } catch (error) {
    return saveFailure(error);
  }
}

export function useLearnerAvatar(): LearnerAvatarState & { reload: () => void } {
  const [state, setState] = useState<LearnerAvatarState>(EMPTY);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let alive = true;
    const cached = readCachedAvatar();
    if (cached) setState((current) => (current.load === 'ready' ? current : { ...current, ...cached }));
    void (async () => {
      try {
        const next = await fetchLearnerAvatar();
        if (!alive || !next) return;
        rememberAvatar(next);
        setState(next);
      } catch {
        // Offline or signed out: the cached character stays, and the screen says it could not load.
        // A save that answered meanwhile is the learner's character; it stays as it is.
        if (alive) setState((current) => (current.load === 'ready' ? current : { ...current, load: 'failed' }));
      }
    })();
    const listener = (next: LearnerAvatarState) => {
      if (alive) setState(next);
    };
    listeners.add(listener);
    return () => {
      alive = false;
      listeners.delete(listener);
    };
  }, [attempt]);

  const reload = useCallback(() => {
    setState((current) => ({ ...current, load: 'loading' }));
    setAttempt((n) => n + 1);
  }, []);

  return { ...state, reload };
}
