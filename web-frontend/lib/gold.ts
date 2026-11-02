/* Package O-2 — l'or on screen: one store for every counter on the page.

   Read once when the first counter mounts, then again shortly after each answer
   the API client posts (`lib/gold-events.ts`). While the server says l'or is not
   on this learner's screen (`visible: false`) nothing is read again until the
   next page load, so a learner the switch leaves out costs one GET. */

import { useEffect, useSyncExternalStore } from 'react';

import apiService from '@/services/api';
import { GOLD_ANSWER_EVENT } from '@/lib/gold-events';
import { grainBetween, type GoldGrain, type GoldView } from '@/lib/gold-model';

interface GoldState {
  view: GoldView | null;
  grain: GoldGrain | null;
}

/** After an answer, wait this long: a pending verdict or a milestone written just after lands too. */
const AFTER_ANSWER_MS = 450;

let state: GoldState = { view: null, grain: null };
let started = false;
let hidden = false;
let inflight: Promise<void> | null = null;
let timer: ReturnType<typeof setTimeout> | null = null;
let grains = 0;
const seen = new Set<string>();
const listeners = new Set<() => void>();

function publish(next: GoldState) {
  state = next;
  listeners.forEach((listener) => listener());
}

export function refreshGold(): Promise<void> {
  if (hidden) return Promise.resolve();
  if (inflight) return inflight;
  inflight = apiService
    .getGold()
    .then((view) => {
      if (!view?.visible) {
        hidden = true;
        publish({ view, grain: null });
        return;
      }
      // The first read only learns what is already there; a grain is something new.
      const grain = state.view ? grainBetween(seen, view, ++grains) : null;
      (view.entries || []).forEach((entry) => seen.add(entry.id));
      publish({ view, grain: grain ?? state.grain });
    })
    .catch(() => undefined)
    .finally(() => {
      inflight = null;
    });
  return inflight;
}

function onAnswer() {
  if (hidden || !state.view) return;
  if (timer) clearTimeout(timer);
  timer = setTimeout(() => {
    timer = null;
    void refreshGold();
  }, AFTER_ANSWER_MS);
}

function start() {
  if (started || typeof window === 'undefined') return;
  started = true;
  window.addEventListener(GOLD_ANSWER_EVENT, onAnswer);
  void refreshGold();
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

const getSnapshot = () => state;
const serverSnapshot: GoldState = { view: null, grain: null };

/** The learner's gold, or `null` while unread or not on their screen. */
export function useGold(): GoldState & { visible: boolean } {
  useEffect(start, []);
  const current = useSyncExternalStore(subscribe, getSnapshot, () => serverSnapshot);
  return { ...current, visible: Boolean(current.view?.visible) };
}

let identity: string | null = null;

/** Another learner signed in (or out): the next one starts from nothing. */
export function setGoldIdentity(next: string) {
  if (identity === null || identity === next) {
    identity = next;
    return;
  }
  identity = next;
  state = { view: null, grain: null };
  hidden = false;
  seen.clear();
  listeners.forEach((listener) => listener());
  if (started && next) void refreshGold();
}
