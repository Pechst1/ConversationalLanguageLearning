/**
 * The one read the season page makes (WP-44).
 *
 * `GET /serial/season` is read-only on the server: it opens no thread and
 * writes no story state, which is why opening the Feuilleton tab out of
 * curiosity cannot cost a learner an episode. Errors are swallowed into `null`
 * — a tab that cannot reach the API falls back to the page it had, and never
 * to an invented season.
 */

import apiService from '@/services/api';

import type { SeasonPayload } from './season-model';

export async function getFeuilletonSeason(): Promise<SeasonPayload | null> {
  try {
    const payload = await apiService.get<SeasonPayload>('/serial/season', {
      suppressGlobalError: true,
    } as Record<string, unknown>);
    if (!payload || typeof payload !== 'object') return null;
    return {
      ...payload,
      commitments: payload.commitments || [],
      read_episodes: payload.read_episodes || [],
    };
  } catch {
    return null;
  }
}
