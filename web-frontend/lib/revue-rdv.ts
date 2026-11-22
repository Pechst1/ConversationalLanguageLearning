/**
 * «Papier · les rendez-vous» (owner 2026-11-21) — the typed client for the routes of
 * `app/api/v1/endpoints/revue_rendez_vous.py`: the regulars' memory (one line per session),
 * «Trois mots» (the closing round), «La une de la semaine» and «La carte de presse».
 *
 * Each route answers a bare 404 while its switch is off: the client then resolves `null`, and
 * the surfaces that asked draw nothing — the Papier is exactly as before.
 *
 * Same shape as `lib/revue-api.ts`: a transport (the app's axios client, or the dev mock),
 * snake_case bodies, every response parsed into camelCase.
 */

import { parsePicture, type RvPicture, type RvWeek, parseWeek } from './revue-types';
import type { RevueTransport } from './revue-api';

type Json = Record<string, any>;

const str = (v: unknown): string => (typeof v === 'string' ? v : '');
const strOrNull = (v: unknown): string | null => (typeof v === 'string' && v ? v : null);
const num = (v: unknown): number => (typeof v === 'number' && Number.isFinite(v) ? v : 0);
const numOrNull = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null);
const obj = (v: unknown): Json => (v && typeof v === 'object' && !Array.isArray(v) ? (v as Json) : {});
const arr = (v: unknown): Json[] => (Array.isArray(v) ? v.filter((x) => x && typeof x === 'object') : []);
function oneOf<T extends string>(v: unknown, allowed: readonly T[], fallback: T): T {
  return typeof v === 'string' && (allowed as readonly string[]).includes(v) ? (v as T) : fallback;
}

// ---------------------------------------------------------------------------
// The regulars remember
// ---------------------------------------------------------------------------

export type RvSouvenir = {
  templateId: string;
  speakerId: string;
  speakerFr: string;
  fr: string;
  en: string;
  de: string;
  aboutSessionId: string;
  fact: string;
};

export function parseSouvenir(raw: Json): RvSouvenir | null {
  const line = raw.line;
  if (!line || typeof line !== 'object') return null;
  const l = line as Json;
  if (!str(l.fr) || !str(l.speaker_id)) return null;
  return {
    templateId: str(l.template_id),
    speakerId: str(l.speaker_id),
    speakerFr: str(l.speaker_fr),
    fr: str(l.fr),
    en: str(l.en),
    de: str(l.de),
    aboutSessionId: str(l.about_session_id),
    fact: str(l.fact),
  };
}

// ---------------------------------------------------------------------------
// «Trois mots»
// ---------------------------------------------------------------------------

export type RvTmWordKey = 'a' | 'b' | 'c';
export type RvTmCueKey = '1' | '2' | '3';
export const TM_WORD_KEYS: readonly RvTmWordKey[] = ['a', 'b', 'c'];
export const TM_CUE_KEYS: readonly RvTmCueKey[] = ['1', '2', '3'];

export type RvTmWord = { key: RvTmWordKey; fr: string; bareFr: string; gloss: string | null };
export type RvTmCue = { key: RvTmCueKey; kind: 'picture' | 'gloss'; text: string | null; picture: RvPicture | null };
export type RvTmMiss = { wordKey: RvTmWordKey; cueKey: RvTmCueKey };
export type RvTmMatch = {
  tries: number;
  resolved: boolean;
  correct: boolean | null;
  misses: RvTmMiss[];
  /** word key → cue key, only once resolved. */
  solution: Partial<Record<RvTmWordKey, RvTmCueKey>> | null;
};
export type RvTmGap = {
  source: 'lead' | 'summary';
  beforeFr: string;
  afterFr: string;
  tries: number;
  resolved: boolean;
  correct: boolean | null;
  miss: { wordKey: RvTmWordKey; gloss: string } | null;
  solution: RvTmWordKey | null;
  sentenceFr: string | null;
};
export type RvTroisMots = {
  sessionId: string;
  step: 'match' | 'gap' | 'done';
  words: RvTmWord[];
  cues: RvTmCue[];
  match: RvTmMatch;
  gap: RvTmGap | null;
  keptNow: number;
};
export type RvTroisMotsResult = { round: RvTroisMots | null; error: 'pair_all' | 'unknown_key' | 'out_of_order' | null };
export type RvTroisMotsBody = { act: 'match'; pairs: Record<RvTmWordKey, RvTmCueKey> } | { act: 'gap'; word: RvTmWordKey };

function parseRound(raw: Json): RvTroisMots {
  const match = obj(raw.match);
  const gap = raw.gap && typeof raw.gap === 'object' ? (raw.gap as Json) : null;
  const solution = match.solution && typeof match.solution === 'object' ? (match.solution as Json) : null;
  return {
    sessionId: str(raw.session_id),
    step: oneOf(raw.step, ['match', 'gap', 'done'] as const, 'match'),
    words: arr(raw.words).map((w) => ({
      key: oneOf(w.key, TM_WORD_KEYS, 'a'),
      fr: str(w.fr),
      bareFr: str(w.bare_fr) || str(w.fr),
      gloss: strOrNull(w.gloss),
    })),
    cues: arr(raw.cues).map((c) => ({
      key: oneOf(c.key, TM_CUE_KEYS, '1'),
      kind: oneOf(c.kind, ['picture', 'gloss'] as const, 'gloss'),
      text: strOrNull(c.text),
      picture: c.picture && typeof c.picture === 'object' ? parsePicture(c.picture as Json) : null,
    })),
    match: {
      tries: num(match.tries),
      resolved: match.resolved === true,
      correct: typeof match.correct === 'boolean' ? match.correct : null,
      misses: arr(match.misses).map((m) => ({ wordKey: oneOf(m.word_key, TM_WORD_KEYS, 'a'), cueKey: oneOf(m.cue_key, TM_CUE_KEYS, '1') })),
      solution: solution
        ? Object.fromEntries(
            TM_WORD_KEYS.filter((k) => typeof solution[k] === 'string').map((k) => [k, oneOf(solution[k], TM_CUE_KEYS, '1')]),
          )
        : null,
    },
    gap: gap
      ? {
          source: oneOf(gap.source, ['lead', 'summary'] as const, 'lead'),
          beforeFr: str(gap.before_fr),
          afterFr: str(gap.after_fr),
          tries: num(gap.tries),
          resolved: gap.resolved === true,
          correct: typeof gap.correct === 'boolean' ? gap.correct : null,
          miss: gap.miss && typeof gap.miss === 'object' ? { wordKey: oneOf((gap.miss as Json).word_key, TM_WORD_KEYS, 'a'), gloss: str((gap.miss as Json).gloss) } : null,
          solution: gap.solution ? oneOf(gap.solution, TM_WORD_KEYS, 'a') : null,
          sentenceFr: strOrNull(gap.sentence_fr),
        }
      : null,
    keptNow: num(raw.kept_now),
  };
}

export function parseTroisMotsResult(raw: Json): RvTroisMotsResult {
  return {
    round: raw.round && typeof raw.round === 'object' ? parseRound(raw.round as Json) : null,
    error: raw.error ? oneOf(raw.error, ['pair_all', 'unknown_key', 'out_of_order'] as const, 'out_of_order') : null,
  };
}

export function troisMotsBodyWire(body: RvTroisMotsBody): Json {
  return body.act === 'match' ? { act: 'match', pairs: { ...body.pairs } } : { act: 'gap', word: body.word };
}

// ---------------------------------------------------------------------------
// «La une de la semaine», «La carte de presse»
// ---------------------------------------------------------------------------

export type RvRubrique = 'opinion' | 'fil' | 'titre' | 'intox' | 'photo' | 'micro';
export const RV_RUBRIQUES: readonly RvRubrique[] = ['opinion', 'fil', 'titre', 'intox', 'photo', 'micro'];
export type RvUneRole = 'headline' | 'caption' | 'quote' | 'vox' | 'brief' | 'rectificatif';

export type RvUneItem = {
  sessionId: string;
  rubrique: RvRubrique;
  role: RvUneRole;
  storyTitleFr: string;
  textFr: string;
  score: number | null;
  total: number | null;
  correctionsFr: string[];
  stance: 'pour' | 'contre' | 'nuance' | null;
  picture: RvPicture | null;
  filedOn: string;
  filedWeekdayFr: string;
};
export type RvUneSemaine = {
  week: RvWeek;
  datelineFr: string;
  items: RvUneItem[];
  lexique: string[];
  rubriquesFiled: number;
  rubriquesTotal: number;
  pieces: number;
  dueToday: boolean;
};
export type RvCarteDePresse = {
  rubriques: { rubrique: RvRubrique; pieces: number; firstOn: string | null }[];
  pieces: number;
  since: string | null;
};

export function parseUne(raw: Json): RvUneSemaine {
  return {
    week: parseWeek(obj(raw.week)),
    datelineFr: str(raw.dateline_fr),
    items: arr(raw.items).map((i) => ({
      sessionId: str(i.session_id),
      rubrique: oneOf(i.rubrique, RV_RUBRIQUES, 'opinion'),
      role: oneOf(i.role, ['headline', 'caption', 'quote', 'vox', 'brief', 'rectificatif'] as const, 'brief'),
      storyTitleFr: str(i.story_title_fr),
      textFr: str(i.text_fr),
      score: numOrNull(i.score),
      total: numOrNull(i.total),
      correctionsFr: (Array.isArray(i.corrections_fr) ? i.corrections_fr : []).filter((x: unknown) => typeof x === 'string' && x),
      stance: i.stance ? oneOf(i.stance, ['pour', 'contre', 'nuance'] as const, 'nuance') : null,
      picture: i.picture && typeof i.picture === 'object' ? parsePicture(i.picture as Json) : null,
      filedOn: str(i.filed_on),
      filedWeekdayFr: str(i.filed_weekday_fr),
    })),
    lexique: (Array.isArray(raw.lexique) ? raw.lexique : []).filter((x: unknown) => typeof x === 'string' && x),
    rubriquesFiled: num(raw.rubriques_filed),
    rubriquesTotal: num(raw.rubriques_total) || 6,
    pieces: num(raw.pieces),
    dueToday: raw.due_today === true,
  };
}

export function parseCarteDePresse(raw: Json): RvCarteDePresse {
  return {
    rubriques: arr(raw.rubriques).map((r) => ({ rubrique: oneOf(r.rubrique, RV_RUBRIQUES, 'opinion'), pieces: num(r.pieces), firstOn: strOrNull(r.first_on) })),
    pieces: num(raw.pieces),
    since: strOrNull(raw.since),
  };
}

// ---------------------------------------------------------------------------
// The client
// ---------------------------------------------------------------------------

export type RdvClient = {
  /** The session's line, or null (no memory, or the switch is off). */
  souvenir: (sessionId: string) => Promise<RvSouvenir | null>;
  /** The closed session's round, or null (no round, or the switch is off). */
  troisMots: (sessionId: string) => Promise<RvTroisMotsResult | null>;
  troisMotsAct: (sessionId: string, body: RvTroisMotsBody) => Promise<RvTroisMotsResult>;
  /** The week's front page (default: this week), or null while the switch is off. */
  une: (week?: string) => Promise<RvUneSemaine | null>;
  carteDePresse: () => Promise<RvCarteDePresse | null>;
};

const statusOf = (error: unknown): number => Number((error as { response?: { status?: number } } | null)?.response?.status) || 0;

async function orNull<T>(load: () => Promise<T>): Promise<T | null> {
  try {
    return await load();
  } catch (error) {
    if (statusOf(error) === 404) return null; // the switch is off: nothing to draw
    throw error;
  }
}

const sessionPath = (id: string) => `/revue/sessions/${encodeURIComponent(id)}`;

export function createRdvClient(transport: RevueTransport): RdvClient {
  return {
    souvenir: (id) => orNull(async () => parseSouvenir(obj(await transport.get(`${sessionPath(id)}/souvenir`)))).then((x) => x ?? null),
    troisMots: (id) => orNull(async () => parseTroisMotsResult(obj(await transport.get(`${sessionPath(id)}/trois-mots`)))),
    troisMotsAct: async (id, body) => parseTroisMotsResult(obj(await transport.post(`${sessionPath(id)}/trois-mots`, troisMotsBodyWire(body)))),
    une: (week) => orNull(async () => parseUne(obj(await transport.get(`/revue/une${week ? `?week=${encodeURIComponent(week)}` : ''}`)))),
    carteDePresse: () => orNull(async () => parseCarteDePresse(obj(await transport.get('/revue/carte-de-presse')))),
  };
}

let http: RdvClient | null = null;

/** The real client, one per page load (lazily: the pure parsers never load axios). */
export function rdvClient(): RdvClient {
  if (!http) {
    const { httpRevueTransport } = require('./revue-api') as typeof import('./revue-api');
    http = createRdvClient(httpRevueTransport());
  }
  return http;
}
