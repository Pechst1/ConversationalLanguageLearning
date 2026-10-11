/**
 * WP-122 B · Le Correcteur — the wire types of `/revue/correcteur/*`
 * (app/schemas/revue_correcteur.py) and their parsers (snake_case → camelCase).
 *
 * Spans are `[start, end)` character offsets inside one sentence. The draft never
 * carries its key: where the mistakes are comes back only in the result.
 */

export type CrSpan = [number, number];
export type CrOutcome = 'repaired' | 'noticed' | 'missed';
export type CrLanguage = 'fr' | 'en' | 'de';

export type CrWeekDossier = { id: string; titleFr: string; topic: string; evergreen: boolean };
export type CrWeek = { week: string; label: string; dossiers: CrWeekDossier[]; corrected: string[] };
export type CrWeekResult = { enabled: false } | { enabled: true; week: CrWeek };

export type CrUnit = { sentenceIndex: number; span: CrSpan; text: string; options: string[] | null };

export type CrDraft = {
  id: string;
  dossierId: string;
  band: string;
  kickerFr: string;
  titleFr: string;
  bylineFr: string;
  sentences: string[];
  units: CrUnit[];
  errorsCount: number;
  optionsEnabled: boolean;
  result: CrResult | null;
};

export type CrMark = { sentenceIndex: number; span: CrSpan; fixFr: string | null; picked: boolean };

export type CrSeedOutcome = {
  sentenceIndex: number;
  span: CrSpan;
  wrongFr: string;
  correctFr: string;
  grammarPoint: string;
  source: 'errata' | 'classique';
  outcome: CrOutcome;
  fixFr: string | null;
};

export type CrFalseAlarm = { sentenceIndex: number; span: CrSpan; textFr: string; fixFr: string | null };

export type CrCounts = { seeded: number; repaired: number; noticed: number; missed: number; falseAlarms: number };

export type CrResult = {
  id: string;
  dossierId: string;
  sentences: string[];
  outcomes: CrSeedOutcome[];
  falseAlarms: CrFalseAlarm[];
  counts: CrCounts;
  romyLineFr: string;
  releveHref: string;
};

export class CorrecteurError extends Error {
  status: number;
  code: string;
  constructor(status: number, code: string) {
    super(code);
    this.status = status;
    this.code = code;
  }
}

type Raw = Record<string, any>;
const obj = (value: unknown): Raw => (value && typeof value === 'object' && !Array.isArray(value) ? (value as Raw) : {});
const str = (value: unknown, fallback = ''): string => (typeof value === 'string' ? value : fallback);
const num = (value: unknown): number => (typeof value === 'number' && Number.isFinite(value) ? value : 0);
const arr = (value: unknown): unknown[] => (Array.isArray(value) ? value : []);
const span = (value: unknown): CrSpan => {
  const [start, end] = arr(value).map(num);
  return [start ?? 0, end ?? 0];
};

export function parseWeek(raw: Raw): CrWeek {
  return {
    week: str(raw.week),
    label: str(raw.label),
    dossiers: arr(raw.dossiers).map((d) => {
      const row = obj(d);
      return { id: str(row.id), titleFr: str(row.title_fr), topic: str(row.topic), evergreen: Boolean(row.evergreen) };
    }),
    corrected: arr(raw.corrected).map((id) => str(id)),
  };
}

export function parseResult(raw: Raw): CrResult {
  const counts = obj(raw.counts);
  return {
    id: str(raw.id),
    dossierId: str(raw.dossier_id),
    sentences: arr(raw.sentences).map((s) => str(s)),
    outcomes: arr(raw.outcomes).map((o) => {
      const row = obj(o);
      const outcome = str(row.outcome);
      return {
        sentenceIndex: num(row.sentence_index),
        span: span(row.span),
        wrongFr: str(row.wrong_fr),
        correctFr: str(row.correct_fr),
        grammarPoint: str(row.grammar_point),
        source: row.source === 'errata' ? 'errata' : 'classique',
        outcome: outcome === 'repaired' || outcome === 'noticed' ? outcome : 'missed',
        fixFr: typeof row.fix_fr === 'string' ? row.fix_fr : null,
      };
    }),
    falseAlarms: arr(raw.false_alarms).map((f) => {
      const row = obj(f);
      return {
        sentenceIndex: num(row.sentence_index),
        span: span(row.span),
        textFr: str(row.text_fr),
        fixFr: typeof row.fix_fr === 'string' ? row.fix_fr : null,
      };
    }),
    counts: {
      seeded: num(counts.seeded),
      repaired: num(counts.repaired),
      noticed: num(counts.noticed),
      missed: num(counts.missed),
      falseAlarms: num(counts.false_alarms),
    },
    romyLineFr: str(raw.romy_line_fr),
    releveHref: str(raw.releve_href, '/notebook?mode=releve'),
  };
}

export function parseDraft(raw: Raw): CrDraft {
  return {
    id: str(raw.id),
    dossierId: str(raw.dossier_id),
    band: str(raw.band, 'A1'),
    kickerFr: str(raw.kicker_fr),
    titleFr: str(raw.title_fr),
    bylineFr: str(raw.byline_fr),
    sentences: arr(raw.sentences).map((s) => str(s)),
    units: arr(raw.units).map((u) => {
      const row = obj(u);
      const options = Array.isArray(row.options) ? row.options.map((o: unknown) => str(o)).filter(Boolean) : null;
      return { sentenceIndex: num(row.sentence_index), span: span(row.span), text: str(row.text), options: options && options.length >= 2 ? options : null };
    }),
    errorsCount: num(raw.errors_count),
    optionsEnabled: Boolean(raw.options_enabled),
    result: raw.result ? parseResult(obj(raw.result)) : null,
  };
}

export function marksWire(marks: CrMark[]): { marks: Raw[] } {
  return {
    marks: marks.map((mark) => ({
      sentence_index: mark.sentenceIndex,
      span: [mark.span[0], mark.span[1]],
      fix_fr: mark.fixFr && mark.fixFr.trim() ? mark.fixFr.trim() : null,
      picked: mark.picked,
    })),
  };
}

/** A bare 404 «Not Found» is the flag being off; anything else keeps its detail as the code. */
export function parseCorrecteurError(status: number, data: unknown): CorrecteurError {
  const detail = str(obj(data).detail);
  if (status === 404 && (!detail || detail === 'Not Found')) return new CorrecteurError(404, 'correcteur_disabled');
  return new CorrecteurError(status, detail || `http_${status}`);
}
