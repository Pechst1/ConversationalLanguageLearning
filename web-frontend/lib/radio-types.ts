/**
 * WP-122 A · La Radio — the wire of `/revue/radio/*`, parsed.
 *
 * The server answers snake_case (`app/schemas/revue_radio.py`); the client reads
 * camelCase. Parsing is defensive: a line without text is dropped, an unknown role
 * reads as `claim`, an unknown audio state as `unavailable` (the page then shows the
 * text at once — silence is a state, never half a bulletin).
 */

export type RadioLanguage = 'en' | 'de' | 'fr';
export type RadioLineRole = 'lede' | 'claim' | 'uncertainty' | 'guest' | 'signoff';
export type RadioAudio = 'ready' | 'unavailable' | 'text_only';
export type RadioDicteeOutcome = 'met' | 'partially_met' | 'not_yet';

export type RadioItem = { dossierId: string; titleFr: string; topic: string; evergreen: boolean };

export type RadioWeek = {
  week: string;
  current: RadioItem | null;
  queue: RadioItem[];
  heard: string[];
  heardToday: boolean;
  /** La Une's chip: an unheard bulletin, and none heard today. */
  chip: boolean;
  seconds: number | null;
};

export type RadioWeekResult = { enabled: false } | { enabled: true; week: RadioWeek };

export type RadioLine = {
  index: number;
  speaker: string;
  speakerName: string;
  role: RadioLineRole;
  textFr: string;
  clipUrl: string | null;
  claimId: string | null;
};

export type RadioBulletin = {
  dossierId: string;
  titleFr: string;
  topic: string;
  band: string;
  week: string;
  seconds: number;
  audio: RadioAudio;
  guestId: string;
  lines: RadioLine[];
  dictee: { lineIndex: number; words: number };
  stage: { plateUrl: string | null; placeFr: string };
};

export type RadioDicteeResult = { outcome: RadioDicteeOutcome; expectedFr: string; note: string | null };

export class RadioError extends Error {
  readonly status: number;

  constructor(status: number) {
    super(`radio request failed (${status})`);
    this.status = status;
  }
}

type Json = Record<string, unknown>;
const record = (value: unknown): Json => (value && typeof value === 'object' && !Array.isArray(value) ? (value as Json) : {});
const text = (value: unknown): string => (typeof value === 'string' ? value : '');
const textOrNull = (value: unknown): string | null => (typeof value === 'string' && value.trim() ? value : null);
const num = (value: unknown, fallback = 0): number => (typeof value === 'number' && Number.isFinite(value) ? value : fallback);

const ROLES: RadioLineRole[] = ['lede', 'claim', 'uncertainty', 'guest', 'signoff'];
const OUTCOMES: RadioDicteeOutcome[] = ['met', 'partially_met', 'not_yet'];

export function parseItem(raw: unknown): RadioItem | null {
  const row = record(raw);
  const dossierId = text(row.dossier_id);
  if (!dossierId) return null;
  return { dossierId, titleFr: text(row.title_fr), topic: text(row.topic), evergreen: row.evergreen === true };
}

export function parseRadioWeek(raw: unknown): RadioWeek {
  const row = record(raw);
  const queue = Array.isArray(row.queue) ? (row.queue.map(parseItem).filter(Boolean) as RadioItem[]) : [];
  const seconds = typeof row.seconds === 'number' && Number.isFinite(row.seconds) ? row.seconds : null;
  return {
    week: text(row.week),
    current: parseItem(row.current),
    queue,
    heard: Array.isArray(row.heard) ? row.heard.filter((id): id is string => typeof id === 'string') : [],
    heardToday: row.heard_today === true,
    chip: row.chip === true,
    seconds,
  };
}

export function parseLine(raw: unknown): RadioLine | null {
  const row = record(raw);
  const textFr = text(row.text_fr).trim();
  if (!textFr) return null;
  const role = ROLES.includes(row.role as RadioLineRole) ? (row.role as RadioLineRole) : 'claim';
  const speaker = text(row.speaker) || 'romy_tremblay';
  return {
    index: num(row.index),
    speaker,
    speakerName: text(row.speaker_name) || speaker.split('_')[0],
    role,
    textFr,
    clipUrl: textOrNull(row.clip_url),
    claimId: textOrNull(row.claim_id),
  };
}

export function parseBulletin(raw: unknown): RadioBulletin {
  const row = record(raw);
  const lines = Array.isArray(row.lines) ? (row.lines.map(parseLine).filter(Boolean) as RadioLine[]) : [];
  const audio: RadioAudio = row.audio === 'ready' || row.audio === 'text_only' ? row.audio : 'unavailable';
  // Ready means every line has its clip; anything less is silence, not half a bulletin.
  const playable = audio === 'ready' && lines.length > 0 && lines.every((line) => line.clipUrl);
  const dictee = record(row.dictee);
  const stage = record(row.stage);
  return {
    dossierId: text(row.dossier_id),
    titleFr: text(row.title_fr),
    topic: text(row.topic),
    band: text(row.band) || 'A1',
    week: text(row.week),
    seconds: num(row.seconds),
    audio: playable ? 'ready' : audio === 'ready' ? 'unavailable' : audio,
    guestId: text(row.guest_id),
    lines,
    dictee: { lineIndex: num(dictee.line_index, -1), words: num(dictee.words) },
    stage: { plateUrl: textOrNull(stage.plate_url), placeFr: text(stage.place_fr) },
  };
}

export function parseDicteeResult(raw: unknown): RadioDicteeResult {
  const row = record(raw);
  const outcome = OUTCOMES.includes(row.outcome as RadioDicteeOutcome) ? (row.outcome as RadioDicteeOutcome) : 'not_yet';
  return { outcome, expectedFr: text(row.expected_fr), note: textOrNull(row.note) };
}
