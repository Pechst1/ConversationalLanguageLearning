/**
 * WP-96 «Archives du journal» — the season as a bound volume, as data.
 *
 * `GET /story-engine/archive` sends the learner's seasons → chapters → days
 * (newest chapter first, days oldest first). This module reads that payload
 * defensively (an older server sends less, or nothing), orders it the way the
 * volume prints it, and answers the small questions the page asks: which
 * chapter is open, what a chapter's digest line says, which day a margin note
 * points at, where on a page a margin note sits.
 *
 * Pure: no fetch, no React. Every rule here is pinned by `archive.test.js`.
 * It invents nothing — a day without art has no art, a chapter without a
 * digest has no digest line, a note without a cause has no link.
 */

import type { StoryEpisode, StoryPanel } from '@/types/daily-journey';

import type { SeasonPayload } from '../season/season-model';

export type ArchiveMarginNote = {
  /** The note's sentence, French: «Parce que vous avez dit à Marin « vas-y »». */
  text_fr: string;
  cause_scene_id: string | null;
  /** YYYY-MM-DD, the day the cause was said. */
  cause_date: string | null;
  character_id: string | null;
  /** Optional: the cause day's edition number, for «— Nº 4». */
  cause_edition_no?: number | null;
  /** Optional: the panel where the payback happens, when the engine knows it. */
  panel_id?: string | null;
};

export type ArchiveDay = {
  /** YYYY-MM-DD, learner-local. */
  date: string;
  journey_id: string;
  scene_id: string | null;
  title_fr: string;
  edition_no: number | null;
  image_url: string | null;
  learner_lines: string[];
  ending_fr: string | null;
  margin_notes: ArchiveMarginNote[];
  can_do_id: string | null;
  special: 'epreuve' | null;
  /** The day's speaker, when the server names one. */
  character_id: string | null;
  /** The authored first day, or an authored fallback day. */
  authored: boolean;
  /** An authored day's own page (engine days are read through `scene_id`). */
  panels: StoryPanel[] | null;
};

export type ArchiveChapter = {
  index: number;
  title_fr: string;
  digest_fr: string | null;
  closed: boolean;
  /** The days before the engine's first chapter. */
  prologue: boolean;
  days: ArchiveDay[];
};

export type ArchiveSeason = {
  number: number;
  title_fr: string;
  finished: boolean;
  /** Only the requested season carries its chapters (`?season=N`); the others are headers. */
  loaded: boolean;
  day_count: number;
  chapters: ArchiveChapter[];
};

export type ArchivePayload = {
  seasons: ArchiveSeason[];
  current: { season: number; chapter: number } | null;
};

const text = (value: unknown): string => (typeof value === 'string' ? value.trim() : '');
const textOrNull = (value: unknown): string | null => text(value) || null;
const intOrNull = (value: unknown): number | null => {
  const n = typeof value === 'number' ? value : typeof value === 'string' && value.trim() ? Number(value) : NaN;
  return Number.isFinite(n) ? Math.trunc(n) : null;
};
const list = (value: unknown): any[] => (Array.isArray(value) ? value : []);

export function normalizeMarginNote(raw: any): ArchiveMarginNote | null {
  const sentence = text(raw?.text_fr);
  if (!sentence) return null;
  return {
    text_fr: sentence,
    cause_scene_id: textOrNull(raw?.cause_scene_id),
    cause_date: textOrNull(raw?.cause_date),
    character_id: textOrNull(raw?.character_id),
    cause_edition_no: intOrNull(raw?.cause_edition_no),
    panel_id: textOrNull(raw?.panel_id),
  };
}

/** A list of margin notes from any payload field; the unusable ones dropped. */
export function marginNotes(raw: unknown): ArchiveMarginNote[] {
  return list(raw).map(normalizeMarginNote).filter((note): note is ArchiveMarginNote => Boolean(note));
}

function normalizeDay(raw: any): ArchiveDay | null {
  const journeyId = text(raw?.journey_id);
  const sceneId = textOrNull(raw?.scene_id);
  const date = text(raw?.date);
  if (!journeyId && !sceneId && !date) return null;
  return {
    date,
    journey_id: journeyId,
    scene_id: sceneId,
    title_fr: text(raw?.title_fr),
    edition_no: intOrNull(raw?.edition_no),
    image_url: textOrNull(raw?.image_url),
    learner_lines: list(raw?.learner_lines).map(text).filter(Boolean),
    ending_fr: textOrNull(raw?.ending_fr),
    margin_notes: marginNotes(raw?.margin_notes),
    can_do_id: textOrNull(raw?.can_do_id),
    special: raw?.special === 'epreuve' ? 'epreuve' : null,
    character_id: textOrNull(raw?.character_id),
    authored: Boolean(raw?.authored),
    panels: normalizePanels(raw?.panels),
  };
}

/** An authored day's page in the reader's panel shape; `null` when it has none. */
function normalizePanels(raw: unknown): StoryPanel[] | null {
  const panels = list(raw)
    .map((panel: any, order: number): StoryPanel | null => {
      const id = text(panel?.id) || `p${order}`;
      const dialogue = list(panel?.dialogue)
        .map((line: any) => ({
          character_id: text(line?.character_id),
          character_name: textOrNull(line?.character_name),
          text_fr: text(line?.text_fr),
        }))
        .filter((line) => line.text_fr);
      const narration = text(panel?.narration_fr);
      if (!dialogue.length && !narration) return null;
      const image = textOrNull(panel?.image_url);
      return {
        id,
        index: intOrNull(panel?.index) ?? order,
        narration_fr: narration,
        dialogue,
        image_url: image,
        image_status: image ? 'panel_art' : 'unavailable',
      };
    })
    .filter((panel): panel is StoryPanel => Boolean(panel));
  return panels.length ? panels : null;
}

/** Days print oldest first; a day without a date keeps its place after the dated ones. */
function byDate(a: ArchiveDay, b: ArchiveDay): number {
  if (a.date && b.date && a.date !== b.date) return a.date < b.date ? -1 : 1;
  if (a.date && !b.date) return -1;
  if (!a.date && b.date) return 1;
  return (a.edition_no ?? 0) - (b.edition_no ?? 0);
}

/**
 * The payload as the volume prints it: seasons newest first, chapters newest
 * first, days oldest first, empty chapters kept only when they are the one
 * being written. Whatever order the server used, this is the order read.
 */
export function normalizeArchive(raw: unknown): ArchivePayload {
  const payload = (raw && typeof raw === 'object' ? raw : {}) as Record<string, any>;
  const currentRaw = payload.current;
  const current =
    currentRaw && intOrNull(currentRaw.season) !== null
      ? { season: intOrNull(currentRaw.season) as number, chapter: intOrNull(currentRaw.chapter) ?? -1 }
      : null;
  const seasons = list(payload.seasons)
    .map((season: any): ArchiveSeason => {
      const number = intOrNull(season?.number) ?? 1;
      const chapters = list(season?.chapters)
        .map((chapter: any): ArchiveChapter => ({
          index: intOrNull(chapter?.index) ?? 0,
          title_fr: text(chapter?.title_fr),
          digest_fr: textOrNull(chapter?.digest_fr),
          closed: Boolean(chapter?.closed),
          prologue: Boolean(chapter?.prologue),
          days: list(chapter?.days)
            .map(normalizeDay)
            .filter((day): day is ArchiveDay => Boolean(day))
            .sort(byDate),
        }))
        .filter(
          (chapter) =>
            chapter.days.length > 0
            || (current !== null && current.season === number && current.chapter === chapter.index),
        )
        .sort((a, b) => b.index - a.index);
      const loaded = season?.loaded === undefined ? true : Boolean(season.loaded);
      const dayCount = intOrNull(season?.day_count) ?? chapters.reduce((sum, chapter) => sum + chapter.days.length, 0);
      return {
        number,
        title_fr: text(season?.title_fr),
        finished: Boolean(season?.finished),
        loaded,
        day_count: loaded ? Math.max(dayCount, chapters.reduce((sum, chapter) => sum + chapter.days.length, 0)) : dayCount,
        chapters,
      };
    })
    // A header-only season (not loaded) is still a volume on the shelf.
    .filter((season) => season.chapters.length > 0 || (!season.loaded && season.day_count > 0))
    .sort((a, b) => b.number - a.number);
  return { seasons, current };
}

/** Every filed day, in reading order across the whole archive. */
export function archiveDays(payload: ArchivePayload | null | undefined): ArchiveDay[] {
  if (!payload) return [];
  return [...payload.seasons]
    .sort((a, b) => a.number - b.number)
    .flatMap((season) => [...season.chapters].sort((a, b) => a.index - b.index).flatMap((chapter) => chapter.days));
}

export function archiveIsEmpty(payload: ArchivePayload | null | undefined): boolean {
  return archiveDays(payload).length === 0;
}

/** The pages filed in one season (the kicker's count) — the header's count when not loaded. */
export function seasonPageCount(season: ArchiveSeason | null | undefined): number {
  if (!season) return 0;
  const counted = season.chapters.reduce((sum, chapter) => sum + chapter.days.length, 0);
  return season.loaded ? counted : Math.max(counted, season.day_count);
}

/** A season fetched on its own (`?season=N`) folded into the volume already held. */
export function mergeArchiveSeason(payload: ArchivePayload, fetched: ArchivePayload, number: number): ArchivePayload {
  const incoming = fetched.seasons.find((season) => season.number === number && season.loaded);
  if (!incoming) return payload;
  return {
    ...payload,
    seasons: payload.seasons.map((season) => (season.number === number ? incoming : season)),
  };
}

/**
 * The page a filed day rereads without the engine: an authored day's own
 * panels. Engine days (`scene_id`) are fetched instead; `null` when neither.
 */
export function archiveDayEpisode(day: ArchiveDay | null | undefined): StoryEpisode | null {
  if (!day || !day.panels || !day.panels.length) return null;
  const id = `archive:${day.journey_id || day.date}`;
  return {
    id,
    scene_id: id,
    serial_thread_id: '',
    serial_episode_id: null,
    journey_id: day.journey_id,
    title_fr: day.title_fr,
    status: 'completed',
    chapter: null,
    panel_index: 0,
    panels: day.panels,
    resolution: null,
  };
}

/** A stable key for a chapter's fold. */
export function chapterKey(season: Pick<ArchiveSeason, 'number'>, chapter: Pick<ArchiveChapter, 'index'>): string {
  return `s${season.number}c${chapter.index}`;
}

/**
 * The chapters open on arrival: the one being written (the payload's
 * `current`), else the newest chapter of the newest unfinished season. A
 * closed chapter folds shut — its digest line is its summary. A finished
 * season opens nothing: it is a bound tome until the learner opens it.
 */
export function defaultOpenChapters(payload: ArchivePayload | null | undefined): string[] {
  if (!payload) return [];
  const open: string[] = [];
  const current = payload.current;
  if (current) {
    const season = payload.seasons.find((entry) => entry.number === current.season);
    const chapter = season?.chapters.find((entry) => entry.index === current.chapter);
    if (season && chapter && !season.finished) open.push(chapterKey(season, chapter));
  }
  if (!open.length) {
    const season = payload.seasons.find((entry) => !entry.finished);
    const chapter = season?.chapters[0];
    if (season && chapter) open.push(chapterKey(season, chapter));
  }
  return open;
}

/** True when this chapter is the one the story is in now. */
export function chapterIsCurrent(
  payload: ArchivePayload | null | undefined,
  season: ArchiveSeason,
  chapter: ArchiveChapter,
): boolean {
  const current = payload?.current;
  return Boolean(current && current.season === season.number && current.chapter === chapter.index && !chapter.closed);
}

/**
 * The digest line «question → résolution», in its two halves. A digest the
 * server wrote without an arrow is one sentence: all of it is the question's
 * side, and nothing is claimed about a resolution.
 */
export function digestParts(digest: unknown): { question: string; resolution: string } | null {
  const line = text(digest);
  if (!line) return null;
  const match = line.split(/\s*(?:→|->)\s*/);
  if (match.length < 2) return { question: line, resolution: '' };
  return { question: match[0], resolution: match.slice(1).join(' → ') };
}

/** The in-surface route of one filed day. */
export function archiveDayHref(day: Pick<ArchiveDay, 'date' | 'journey_id' | 'scene_id'>): string {
  const params = new URLSearchParams();
  if (day.date) params.set('day', day.date);
  if (day.journey_id) params.set('journey', day.journey_id);
  else if (day.scene_id) params.set('cause', day.scene_id);
  return `/graphic-novel?${params.toString()}`;
}

/** Where a margin note leads: the cause day in the archive. `null` without a cause. */
export function marginNoteHref(note: ArchiveMarginNote): string | null {
  if (!note.cause_date && !note.cause_scene_id) return null;
  const params = new URLSearchParams();
  if (note.cause_date) params.set('day', note.cause_date);
  if (note.cause_scene_id) params.set('cause', note.cause_scene_id);
  return `/graphic-novel?${params.toString()}`;
}

/**
 * The filed day a route (or a margin note) names. A journey id or a scene id
 * is an identity and wins; a date alone picks that date's day (the last one,
 * when a date filed two).
 */
export function findArchiveDay(
  payload: ArchivePayload | null | undefined,
  query: { date?: string | null; journeyId?: string | null; sceneId?: string | null },
): ArchiveDay | null {
  const days = archiveDays(payload);
  if (query.journeyId) {
    const hit = days.find((day) => day.journey_id === query.journeyId);
    if (hit) return hit;
  }
  if (query.sceneId) {
    const hit = days.find((day) => day.scene_id === query.sceneId);
    if (hit) return hit;
  }
  if (query.date) {
    const hits = days.filter((day) => day.date === query.date);
    if (hits.length) return hits[hits.length - 1];
  }
  return null;
}

/** The edition number a margin note's «— Nº N» prints: the note's own, else the cause day's. */
export function marginNoteEdition(note: ArchiveMarginNote, payload?: ArchivePayload | null): number | null {
  if (typeof note.cause_edition_no === 'number') return note.cause_edition_no;
  const day = findArchiveDay(payload, { sceneId: note.cause_scene_id, date: note.cause_date });
  return day?.edition_no ?? null;
}

type PanelLike = {
  id: string;
  index?: number;
  dialogue?: Array<{ character_id?: string | null }> | null;
};

/**
 * Where each margin note sits on a page. The engine's `panel_id` wins; else
 * the first panel where the note's character speaks (the payback is theirs to
 * say); else the page's end. A note is placed once.
 */
export function placeMarginNotes(
  panels: PanelLike[] | null | undefined,
  notes: ArchiveMarginNote[] | null | undefined,
): { byPanel: Record<string, ArchiveMarginNote[]>; end: ArchiveMarginNote[] } {
  const byPanel: Record<string, ArchiveMarginNote[]> = {};
  const end: ArchiveMarginNote[] = [];
  const ordered = [...(panels || [])].sort((a, b) => (a.index ?? 0) - (b.index ?? 0));
  const ids = new Set(ordered.map((panel) => String(panel.id)));
  for (const note of notes || []) {
    let target: string | null = note.panel_id && ids.has(note.panel_id) ? note.panel_id : null;
    if (!target && note.character_id) {
      const who = note.character_id.toLowerCase();
      const panel = ordered.find((entry) =>
        (entry.dialogue || []).some((line) => String(line?.character_id || '').toLowerCase() === who),
      );
      target = panel ? String(panel.id) : null;
    }
    if (target) (byPanel[target] ||= []).push(note);
    else end.push(note);
  }
  return { byPanel, end };
}

/**
 * An older server has no archive: the season projection (`GET /serial/season`)
 * still knows the read scenes, so the volume prints them as one chapter rather
 * than failing. It has no dates, replies or endings — and says none.
 */
export function archiveFromSeason(season: SeasonPayload | null | undefined): ArchivePayload | null {
  if (!season) return null;
  const days: ArchiveDay[] = (season.read_episodes || [])
    .filter((episode) => text(episode?.scene_id))
    .map((episode) => ({
      date: '',
      journey_id: '',
      scene_id: episode.scene_id,
      title_fr: text(episode.title_fr),
      edition_no: intOrNull(episode.number),
      image_url: textOrNull(episode.image_url),
      learner_lines: [],
      ending_fr: null,
      margin_notes: [],
      can_do_id: null,
      special: null,
      character_id: null,
      authored: false,
      panels: null,
    }));
  const number = intOrNull(season.season_number) ?? 1;
  const chapterIndex = intOrNull(season.chapter?.number) ?? 1;
  return normalizeArchive({
    seasons: [
      {
        number,
        title_fr: '',
        finished: false,
        chapters: [{ index: chapterIndex, title_fr: text(season.chapter?.title_fr), digest_fr: null, closed: false, prologue: false, days }],
      },
    ],
    current: { season: number, chapter: chapterIndex },
  });
}
