/**
 * The archive's reads (WP-96). All GETs: opening the Feuilleton tab, a
 * chapter, a planche or the trombinoscope writes nothing and starts nothing.
 *
 * `GET /story-engine/archive` is the volume. A server that predates it (404)
 * or cannot answer falls back to the season projection (`/serial/season`),
 * printed as one chapter — never to an invented page. `null` means neither
 * answered, and the page says so.
 */

import apiService, { type SerialCastMember } from '@/services/api';
import type { StoryEpisode } from '@/types/daily-journey';

import { getFeuilletonSeason } from '../season/season-api';

import { archiveFromSeason, normalizeArchive, type ArchivePayload } from './archive-model';

const SILENT = { suppressGlobalError: true } as Record<string, unknown>;

export async function getStoryArchive(season?: number | null): Promise<ArchivePayload | null> {
  try {
    const query = season ? `?season=${encodeURIComponent(String(season))}` : '';
    const raw = await apiService.get<unknown>(`/story-engine/archive${query}`, SILENT);
    return normalizeArchive(raw);
  } catch {
    if (season) return null;
    return archiveFromSeason(await getFeuilletonSeason());
  }
}

export async function getArchiveEpisode(sceneId: string): Promise<StoryEpisode | null> {
  try {
    return await apiService.getStoryEpisode(sceneId);
  } catch {
    return null;
  }
}

export async function getTrombinoscope(): Promise<SerialCastMember[] | null> {
  try {
    const payload = await apiService.getSerialCast();
    return payload.cast || [];
  } catch {
    return null;
  }
}
