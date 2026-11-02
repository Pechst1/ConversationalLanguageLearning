/* Package O-2 — an answer was posted, l'or may have moved.

   `services/api.ts` calls `noteGoldRequest` after every successful request; the
   gold store (`lib/gold.ts`) listens. A window event keeps the API client free
   of the store (and the store free of the client's interceptors). */

export const GOLD_ANSWER_EVENT = 'atelier:gold-answer';

/** The answer routes that can mint: the journey, La Forge, the word deck, the Courrier. */
const ANSWER_ROUTES = [
  /\/daily-journeys\/[^/]+\/(steps\/[^/]+\/attempts|advance|finish|retry)$/,
  /\/atelier\/(sessions\/[^/]+\/attempts|attempts\/[^/]+\/(repair|ai-review)|forge\/)/,
  /\/anki\/review$/,
  /\/missions\/[^/]+\/(submit|complete)/,
];

export function isGoldAnswerRequest(method: string | undefined, url: string | undefined): boolean {
  if (String(method || '').toLowerCase() !== 'post' || !url) return false;
  const path = url.split('?')[0];
  return ANSWER_ROUTES.some((route) => route.test(path));
}

export function noteGoldRequest(method: string | undefined, url: string | undefined): void {
  if (typeof window === 'undefined' || !isGoldAnswerRequest(method, url)) return;
  window.dispatchEvent(new Event(GOLD_ANSWER_EVENT));
}
