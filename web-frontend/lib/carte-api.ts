/**
 * WP-120 phase C · La Carte — the client for `GET /revue/carte`.
 *
 * Same shape as `lib/revue-api.ts`: a transport-agnostic client (`createCarteClient`)
 * and the app's authenticated, quiet axios transport. A 404 means the Revue flag is
 * off: `{ enabled: false }`, and the page says so instead of failing.
 */

import {
  CarteError,
  parseCarteReview,
  parseCarteReviewGrade,
  parseCarteView,
  parseRelectureOffer,
  parseRelecturePair,
  type CarteResult,
  type CarteReview,
  type CarteReviewAnswer,
  type CarteReviewGrade,
  type RelectureOffer,
  type RelecturePair,
} from './carte-types';

export const CARTE_URL = '/revue/carte';
export const CARTE_REVIEW_URL = (placeId: string) => `/revue/carte/review/${encodeURIComponent(placeId)}`;
export const RELECTURE_URL = '/revue/relecture';

export type CarteTransport = {
  get: (url: string) => Promise<unknown>;
  post?: (url: string, body: unknown) => Promise<unknown>;
};

export type CarteClient = {
  carte: () => Promise<CarteResult>;
  /** WP-121 A.3: the due words of one place and the items to pose. */
  review: (placeId: string) => Promise<CarteReview>;
  grade: (placeId: string, answer: CarteReviewAnswer) => Promise<CarteReviewGrade>;
  /** WP-121 B: the oldest Papier to re-read, the answer, the stored pair. */
  relectureOffer: () => Promise<RelectureOffer | null>;
  relectureAnswer: (sessionId: string, answerFr: string, mode?: 'text' | 'voice') => Promise<RelecturePair>;
  relecturePair: (sessionId: string) => Promise<RelecturePair | null>;
};

function statusOf(error: unknown): number {
  return Number((error as { response?: { status?: number } } | null)?.response?.status) || 0;
}

export function createCarteClient(transport: CarteTransport): CarteClient {
  const post = async (url: string, body: unknown) => {
    if (!transport.post) throw new CarteError(0);
    try {
      return await transport.post(url, body);
    } catch (error) {
      throw new CarteError(statusOf(error));
    }
  };
  const get = async (url: string) => {
    try {
      return await transport.get(url);
    } catch (error) {
      throw new CarteError(statusOf(error));
    }
  };
  return {
    async review(placeId) {
      return parseCarteReview(await get(CARTE_REVIEW_URL(placeId)));
    },
    async grade(placeId, answer) {
      const body = { item_id: answer.itemId, tile_ids: answer.tileIds ?? null, text: answer.text ?? null, assisted: Boolean(answer.assisted) };
      return parseCarteReviewGrade(await post(`${CARTE_REVIEW_URL(placeId)}/grade`, body));
    },
    async relectureOffer() {
      const body = (await get(`${RELECTURE_URL}/offer`)) as { offer?: unknown } | null;
      return parseRelectureOffer(body?.offer);
    },
    async relectureAnswer(sessionId, answerFr, mode = 'text') {
      const pair = parseRelecturePair(await post(`${RELECTURE_URL}/${encodeURIComponent(sessionId)}`, { answer_fr: answerFr, mode }));
      if (!pair) throw new CarteError(0);
      return pair;
    },
    async relecturePair(sessionId) {
      try {
        return parseRelecturePair(await transport.get(`${RELECTURE_URL}/${encodeURIComponent(sessionId)}`));
      } catch (error) {
        if (statusOf(error) === 404) return null;
        throw new CarteError(statusOf(error));
      }
    },
    async carte() {
      try {
        return { enabled: true, view: parseCarteView(await transport.get(CARTE_URL)) };
      } catch (error) {
        const status = Number((error as { response?: { status?: number } } | null)?.response?.status) || 0;
        if (status === 404) return { enabled: false };
        throw new CarteError(status);
      }
    },
  };
}

/** The app's authenticated client, with the global error toasts off. */
export function httpCarteTransport(): CarteTransport {
  // Required lazily so the pure client (and its node tests) never load axios.
  const { apiService } = require('@/services/api') as typeof import('@/services/api');
  const quiet = { suppressGlobalError: true } as Record<string, unknown>;
  return { get: (url) => apiService.get(url, quiet), post: (url, body) => apiService.post(url, body, quiet) };
}

let http: CarteClient | null = null;

export function carteClient(): CarteClient {
  if (!http) http = createCarteClient(httpCarteTransport());
  return http;
}
