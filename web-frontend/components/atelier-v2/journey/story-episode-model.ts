/**
 * Story-engine episode → reader stages (WP-14E, frontend side).
 *
 * `GET /story-engine/episodes` is a read-only projection of the canonical daily
 * story (ENGINE-FRONTEND-CONTRACT.md). This module turns one such episode into
 * the paged reader's stage list so the existing immersive reader renders it
 * unchanged. Pure: no fetch, no React, unit-tested with `node --test`.
 *
 * Rules kept here, not in the component:
 *   * every stage comes from a server panel; nothing is synthesised;
 *   * a panel with no art is `missing`, never a placeholder illustration;
 *   * reused location art is `setting_reference` and is labelled as such —
 *     it is not claimed to be a newly generated illustration;
 *   * the generated ending is exposed only when the server exposes it
 *     (`resolution` is null until the exchange actually settles).
 */

import type { StoryEpisode, StoryPanel } from '@/types/daily-journey';
import {
  readerCharacterKey,
  type ReaderLine,
  type ReaderStage,
} from '@/components/feuilleton/reader/panel-model';

/**
 * One dialogue line as the engine actually sends it.
 *
 * `character_name` was ratified additively on 2026-09-06 (ENGINE-FRONTEND-
 * CONTRACT.md, "Verified in a browser"): it is the display name from the
 * owning thread's world bible, or `null` when the thread has none. The shared
 * `StoryPanel` type in `@/types/daily-journey` is owned by the engine side and
 * does not carry the field yet, so it is read structurally here — which is also
 * what an older server, sending no such field, needs.
 */
type StoryDialogueLine = StoryPanel['dialogue'][number] & {
  character_name?: string | null;
};

const CHARACTER_NAMES: Record<string, string> = {
  romy: 'Romy',
  marin: 'Marin',
  lila: 'Lila',
  gus: 'Gus',
  margaux: 'Margaux',
  marchand: 'Monsieur Marchand',
  toi: 'Vous',
  learner: 'Vous',
  you: 'Vous',
};

/**
 * The name to print above a line.
 *
 * The server's own `character_name` wins whenever it sent one: it comes from
 * the thread's world bible and is the only source that knows a generated cast.
 * Only when the field is absent or null does the local table stand in, and an
 * id it does not know keeps its own spelling — which is how a generated id such
 * as `marin_leveque` used to reach the reader as "Marin_leveque".
 */
export function storyCharacterName(
  characterId: string | null | undefined,
  characterName?: string | null,
): string {
  const given = String(characterName ?? '').trim();
  if (given) return given;
  const id = String(characterId || '').trim();
  if (!id) return '';
  const key = id.toLowerCase();
  if (CHARACTER_NAMES[key]) return CHARACTER_NAMES[key];
  return id.charAt(0).toUpperCase() + id.slice(1);
}

function panelLines(panel: StoryPanel): ReaderLine[] {
  return ((panel.dialogue || []) as StoryDialogueLine[])
    .filter((line) => line && String(line.text_fr || '').trim())
    .map((line, index) => ({
      key: `${panel.id}-l${index}`,
      who: storyCharacterName(line.character_id, line.character_name),
      fr: String(line.text_fr).trim(),
      en: '',
      // The visual accent stays keyed to the canonical id, so a renamed
      // character keeps its colour; the display name is only a fallback seed.
      character: readerCharacterKey(line.character_id) || readerCharacterKey(line.character_name) || '',
    }));
}

/** The reader's stage list for one story-engine episode, in panel order. */
export function buildStoryStages(episode: StoryEpisode | null | undefined): ReaderStage[] {
  if (!episode) return [];
  const panels = [...(episode.panels || [])].sort((a, b) => a.index - b.index);
  const stages: ReaderStage[] = panels.map((panel, ordinal) => {
    const lines = panelLines(panel);
    const character = lines.map((line) => line.character).find(Boolean) || '';
    return {
      kind: 'panel',
      key: `panel:${panel.id}`,
      ordinal: ordinal + 1,
      panelId: panel.id,
      panelIndex: panel.index,
      title: '',
      beat: '',
      imageUrl: panel.image_status === 'setting_reference' && panel.image_url ? panel.image_url : '',
      artStatus: panel.image_status === 'setting_reference' && panel.image_url ? 'ready' : 'missing',
      character,
      lines,
      caption: String(panel.narration_fr || '').trim(),
      tasks: [],
    };
  });

  // The ending exists only once the server says the exchange has settled.
  if (episode.resolution && (episode.resolution.text_fr || episode.resolution.summary_native)) {
    stages.push({
      kind: 'resolution',
      key: `resolution:${episode.id}`,
      ordinal: stages.length + 1,
      character: 'toi',
      hookQuestion: String(episode.resolution.text_fr || '').trim(),
      hookBeat: String(episode.resolution.summary_native || '').trim(),
      tasks: [],
    });
  }
  return stages;
}

/** Which panels reuse setting art, so the reader can say so. */
export function storyUsesSettingArt(episode: StoryEpisode | null | undefined): boolean {
  return Boolean(episode?.panels?.some((panel) => panel.image_status === 'setting_reference' && panel.image_url));
}

/** The saved server position, clamped to the panels the episode actually has. */
export function storyStartIndex(episode: StoryEpisode | null | undefined, stageCount: number): number {
  if (!episode || stageCount <= 0) return 0;
  const saved = Number(episode.panel_index);
  if (!Number.isFinite(saved) || saved < 0) return 0;
  return Math.min(Math.floor(saved), stageCount - 1);
}

/** The reader's eyebrow: chapter title when the engine has one. */
export function storyEpisodeLabel(episode: StoryEpisode | null | undefined): string {
  if (!episode) return '';
  const chapter = episode.chapter?.title_fr ? String(episode.chapter.title_fr).trim() : '';
  return chapter || 'Le feuilleton';
}
