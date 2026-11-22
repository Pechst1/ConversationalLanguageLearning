/**
 * «Papier · la voix» (2026-11-22, `REVUE_VOIX_ENABLED`) — the typed client for the routes of
 * `app/api/v1/endpoints/revue_voix.py`: what the session may speak, one line spoken, the dictée.
 *
 * Every route answers a bare 404 while the switch is off: `manifest` then resolves `null` and the
 * players are exactly as before (the ▶ chips read with the device's voice).
 *
 * A line's bytes come from the journey's own clip route (`GET /daily-journeys/line-audio/{id}`),
 * through `createLineAudioResolver` — the scene's resolver, with a cache of its own so a `disabled`
 * here never silences the journey's lines.
 */

import {
  createLineAudioCache,
  createLineAudioResolver,
  type LineAudioCache,
  type ResolvedClip,
} from '@/components/atelier-v2/journey/line-audio';

import type { RevueTransport } from './revue-api';
import type { RvComptoirMarkKind } from './revue-types';

type Json = Record<string, any>;

const str = (v: unknown): string => (typeof v === 'string' ? v : '');
const strOrNull = (v: unknown): string | null => (typeof v === 'string' && v ? v : null);
const num = (v: unknown): number => (typeof v === 'number' && Number.isFinite(v) ? v : 0);
const obj = (v: unknown): Json => (v && typeof v === 'object' && !Array.isArray(v) ? (v as Json) : {});
const arr = (v: unknown): Json[] => (Array.isArray(v) ? v.filter((x) => x && typeof x === 'object') : []);

export type VxLineKind = 'lead' | 'take' | 'reply' | 'last_word';
export type VxLine = { kind: VxLineKind; speakerId: string; textFr: string };
export type VxDictee = { textFr: string; words: number; maxTries: number };
export type VxManifest = {
  /** `ready`: clips can be made, lines are heard before they are read; `device`: the text at once. */
  audio: 'ready' | 'device';
  newsreaderId: string;
  lines: VxLine[];
  dictee: VxDictee | null;
};
export type VxMark = { spanFr: string; start: number; kind: RvComptoirMarkKind; why?: string };
export type VxDicteeResult = {
  outcome: 'met' | 'partially_met' | 'not_yet';
  attempt: number;
  maxTries: number;
  resolved: boolean;
  answerFr: string;
  marks: VxMark[];
  expectedFr: string | null;
  note: string | null;
};

const KINDS: readonly VxLineKind[] = ['lead', 'take', 'reply', 'last_word'];
const MARK_KINDS: readonly RvComptoirMarkKind[] = ['accord', 'conjugaison', 'genre', 'orthographe', 'mot', 'ordre', 'manque'];

export function parseVoixManifest(raw: Json): VxManifest {
  const dictee = obj(raw.dictee);
  return {
    audio: raw.audio === 'ready' ? 'ready' : 'device',
    newsreaderId: str(raw.newsreader_id) || 'narrator',
    lines: arr(raw.lines)
      .filter((line) => KINDS.includes(line.kind) && str(line.text_fr))
      .map((line) => ({ kind: line.kind as VxLineKind, speakerId: str(line.speaker_id), textFr: str(line.text_fr) })),
    dictee: str(dictee.text_fr) ? { textFr: str(dictee.text_fr), words: num(dictee.words), maxTries: num(dictee.max_tries) || 2 } : null,
  };
}

export function parseDicteeResult(raw: Json): VxDicteeResult {
  const outcome = raw.outcome === 'met' || raw.outcome === 'partially_met' ? raw.outcome : 'not_yet';
  return {
    outcome,
    attempt: num(raw.attempt) || 1,
    maxTries: num(raw.max_tries) || 2,
    resolved: Boolean(raw.resolved),
    answerFr: str(raw.answer_fr),
    marks: arr(raw.marks)
      .filter((mark) => MARK_KINDS.includes(mark.kind) && str(mark.span_fr))
      .map((mark) => ({ spanFr: str(mark.span_fr), start: num(mark.start), kind: mark.kind as RvComptoirMarkKind })),
    expectedFr: strOrNull(raw.expected_fr),
    note: strOrNull(raw.note),
  };
}

/** The transport, plus the clip's bytes (the journey's authenticated clip route, or the mock's). */
export type VoixTransport = RevueTransport & { clip?: (clipId: string) => Promise<Blob> };

export type VoixClient = {
  /** What the session may speak, or null while the switch is off. */
  manifest: (sessionId: string) => Promise<VxManifest | null>;
  /** `useLineVoice`'s `resolve` for one session: a clip, or null (the device's voice). */
  resolver: (sessionId: string) => (line: { text_fr: string; character_id?: string | null }) => Promise<ResolvedClip | null>;
  dictee: (sessionId: string, text: string, attempt: number) => Promise<VxDicteeResult>;
};

const statusOf = (error: unknown): number => Number((error as { response?: { status?: number } } | null)?.response?.status) || 0;
const sessionPath = (id: string) => `/revue/sessions/${encodeURIComponent(id)}/voix`;

export function createVoixClient(transport: VoixTransport, cache: LineAudioCache = createLineAudioCache()): VoixClient {
  const fetchClip =
    transport.clip ??
    ((clipId: string) => {
      // Required lazily so the pure client (and its node tests) never load axios.
      const { apiService } = require('@/services/api') as typeof import('@/services/api');
      return apiService.getDailyJourneyLineAudio(clipId);
    });
  const resolvers = new Map<string, ReturnType<typeof createLineAudioResolver>>();
  return {
    async manifest(sessionId) {
      try {
        return parseVoixManifest(obj(await transport.get(sessionPath(sessionId))));
      } catch (error) {
        if (statusOf(error) === 404) return null; // the switch is off: the paper is as before
        throw error;
      }
    },
    resolver(sessionId) {
      let resolve = resolvers.get(sessionId);
      if (!resolve) {
        resolve = createLineAudioResolver(
          {
            request: async (body) => obj(await transport.post(`${sessionPath(sessionId)}/line`, body)) as never,
            fetchClip,
          },
          { cache },
        );
        resolvers.set(sessionId, resolve);
      }
      return resolve;
    },
    dictee: async (sessionId, text, attempt) =>
      parseDicteeResult(obj(await transport.post(`${sessionPath(sessionId)}/dictee`, { text, attempt }))),
  };
}

let http: VoixClient | null = null;

/** The real client, one per page load. */
export function voixClient(): VoixClient {
  if (!http) {
    const { httpRevueTransport } = require('./revue-api') as typeof import('./revue-api');
    http = createVoixClient(httpRevueTransport());
  }
  return http;
}
