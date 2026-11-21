/**
 * «Le bilan» — the wire shapes of `GET /bilan` and `GET /bilan/card`, and pure parsers
 * (no axios, so node tests read them directly). The server computes everything; the
 * client only checks the shape and drops what it cannot read.
 */

export type BilanLanguage = 'en' | 'de' | 'fr';

export type BilanDay = { date: string; played: boolean; future: boolean };
export type BilanLine = { textFr: string; date: string; source: string };
export type BilanWord = { word: string; gloss: string };
export type BilanWords = { newCount: number; reviewedCount: number; heldCount: number; shown: BilanWord[] };
export type BilanRule = {
  conceptId: number;
  title: string;
  titleFr: string;
  fromStage: string;
  fromLabel: string | null;
  stage: string;
  stageLabel: string | null;
};
export type BilanDecision = { date: string; labelFr: string; kind: 'choice' | 'promise' | 'resolved' };
export type BilanStory = {
  episodes: { date: string; titleFr: string }[];
  decisions: BilanDecision[];
  nextFr: string | null;
};
export type BilanWeekRef = { weekStart: string; daysPlayed: number };

export type Bilan = {
  weekStart: string;
  weekEnd: string;
  timezone: string;
  isCurrent: boolean;
  closed: boolean;
  language: BilanLanguage;
  level: string;
  days: BilanDay[];
  daysPlayed: number;
  lines: BilanLine[];
  words: BilanWords;
  rules: BilanRule[];
  story: BilanStory;
  weeks: BilanWeekRef[];
  previousWeekStart: string | null;
  nextWeekStart: string | null;
};

export type BilanCard = { weekStart: string | null; daysPlayed: number };

export type BilanResult = { enabled: false } | { enabled: true; bilan: Bilan };
export type BilanCardResult = { enabled: false } | { enabled: true; card: BilanCard };

export class BilanError extends Error {
  status: number;
  code: 'bilan_disabled' | 'unauthorized' | 'network' | 'server';
  constructor(status: number, code: BilanError['code']) {
    super(code);
    this.status = status;
    this.code = code;
  }
}

export function parseBilanError(status: number): BilanError {
  if (status === 404) return new BilanError(status, 'bilan_disabled');
  if (status === 401 || status === 403) return new BilanError(status, 'unauthorized');
  if (!status) return new BilanError(0, 'network');
  return new BilanError(status, 'server');
}

const obj = (value: unknown): Record<string, any> =>
  value && typeof value === 'object' && !Array.isArray(value) ? (value as Record<string, any>) : {};
const list = (value: unknown): unknown[] => (Array.isArray(value) ? value : []);
const str = (value: unknown): string => (typeof value === 'string' ? value : '');
const strOrNull = (value: unknown): string | null => (typeof value === 'string' && value.trim() ? value : null);
const num = (value: unknown): number => (typeof value === 'number' && Number.isFinite(value) ? value : 0);
const ISO_DAY = /^\d{4}-\d{2}-\d{2}$/;

export function parseBilan(raw: unknown): Bilan {
  const body = obj(raw);
  if (!ISO_DAY.test(str(body.week_start))) throw new BilanError(200, 'server');
  const words = obj(body.words);
  const story = obj(body.story);
  const language = str(body.language);
  return {
    weekStart: str(body.week_start),
    weekEnd: str(body.week_end),
    timezone: str(body.timezone),
    isCurrent: body.is_current === true,
    closed: body.closed === true,
    language: language === 'de' || language === 'fr' ? language : 'en',
    level: str(body.level),
    days: list(body.days)
      .map(obj)
      .filter((day) => ISO_DAY.test(str(day.date)))
      .map((day) => ({ date: str(day.date), played: day.played === true, future: day.future === true })),
    daysPlayed: num(body.days_played),
    lines: list(body.lines)
      .map(obj)
      .filter((line) => str(line.text_fr).trim())
      .map((line) => ({ textFr: str(line.text_fr), date: str(line.date), source: str(line.source) })),
    words: {
      newCount: num(words.new_count),
      reviewedCount: num(words.reviewed_count),
      heldCount: num(words.held_count),
      shown: list(words.shown)
        .map(obj)
        .filter((word) => str(word.word) && str(word.gloss))
        .map((word) => ({ word: str(word.word), gloss: str(word.gloss) })),
    },
    rules: list(body.rules)
      .map(obj)
      .filter((rule) => str(rule.title) || str(rule.title_fr))
      .map((rule) => ({
        conceptId: num(rule.concept_id),
        title: str(rule.title) || str(rule.title_fr),
        titleFr: str(rule.title_fr),
        fromStage: str(rule.from_stage),
        fromLabel: strOrNull(rule.from_label),
        stage: str(rule.stage),
        stageLabel: strOrNull(rule.stage_label),
      })),
    story: {
      episodes: list(story.episodes)
        .map(obj)
        .filter((row) => str(row.title_fr))
        .map((row) => ({ date: str(row.date), titleFr: str(row.title_fr) })),
      decisions: list(story.decisions)
        .map(obj)
        .filter((row) => str(row.label_fr))
        .map((row) => ({
          date: str(row.date),
          labelFr: str(row.label_fr),
          kind: row.kind === 'promise' || row.kind === 'resolved' ? row.kind : ('choice' as const),
        })),
      nextFr: strOrNull(story.next_fr),
    },
    weeks: list(body.weeks)
      .map(obj)
      .filter((row) => ISO_DAY.test(str(row.week_start)))
      .map((row) => ({ weekStart: str(row.week_start), daysPlayed: num(row.days_played) })),
    previousWeekStart: ISO_DAY.test(str(body.previous_week_start)) ? str(body.previous_week_start) : null,
    nextWeekStart: ISO_DAY.test(str(body.next_week_start)) ? str(body.next_week_start) : null,
  };
}

export function parseBilanCard(raw: unknown): BilanCard {
  const body = obj(raw);
  return {
    weekStart: ISO_DAY.test(str(body.week_start)) ? str(body.week_start) : null,
    daysPlayed: num(body.days_played),
  };
}
