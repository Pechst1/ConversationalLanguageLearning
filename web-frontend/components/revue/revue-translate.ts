/**
 * Le Papier · «Traduire» for a line the server sent without a translation
 * (2026-10-19): Romy's `look` line and her client lines, the guests, the claims,
 * every line from B1. Fetched from `/atelier/translate` (the learner's own
 * language) on the first press, once per text: the same sentence pressed again,
 * or on a later bubble, is never asked for twice. A failed request is forgotten,
 * so the next press asks again. Kept for the page's life, keyed by language.
 */

import apiService from '@/services/api';

const ready = new Map<string, string>();
const pending = new Map<string, Promise<string>>();

const keyOf = (textFr: string, language: string) => `${language}\u0000${textFr.trim()}`;

/** A translation this page already fetched, or ''. */
export function knownTranslation(textFr: string, language: string): string {
  return ready.get(keyOf(textFr, language)) ?? '';
}

export function translateOnce(
  textFr: string,
  language: string,
  fetcher: (text: string) => Promise<string> = (text) => apiService.translateForLearner(text),
): Promise<string> {
  const key = keyOf(textFr, language);
  const done = ready.get(key);
  if (done) return Promise.resolve(done);
  const inFlight = pending.get(key);
  if (inFlight) return inFlight;
  const request = Promise.resolve()
    .then(() => fetcher(textFr.trim()))
    .then((text) => {
      const clean = (text || '').trim();
      if (clean) ready.set(key, clean);
      return clean;
    })
    .finally(() => pending.delete(key));
  pending.set(key, request);
  return request;
}
