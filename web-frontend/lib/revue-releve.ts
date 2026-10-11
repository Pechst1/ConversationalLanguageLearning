/**
 * WP-119 phase 3 · «Le Papier» in Le Relevé — the typed client for
 * `GET /revue/releve` and its parser.
 *
 * The wire is snake_case, newest first; the client is camelCase
 * (`RvReleveEntryData`, design §4 `RvReleveSection` / `RvReleveEntry`). The
 * transport is the Revue's own (`lib/revue-api.ts`: the app's authenticated
 * axios client with the global toasts off), so a failure is a `RevueError`.
 * A 404 means the Revue is switched off: `{ enabled: false, entries: [] }`,
 * and the Relevé simply draws no section.
 */

import { httpRevueTransport, REVUE_BASE, type RevueTransport } from './revue-api';
import {
  parseRevueError,
  RevueError,
  type RvClaim,
  type RvClaimKind,
  type RvSource,
} from './revue-types';

/** What was made: the four make kinds, plus phase 2's «tell Margaux». */
export type RvReleveMadeKind = 'headline_choice' | 'reader_question' | 'headline_write' | 'short_report' | 'tell_margaux';

export type RvReleveWord = { fr: string; gloss: string; claimId: string; used: boolean };

export type RvReleveEntryData = {
  sessionId: string;
  /** The ISO week («2026-W40») or, in daily mode, the ISO date («2026-10-03»). */
  period: string;
  periodLabel: string;
  /** The close's local day, `YYYY-MM-DD` (empty when the wire had none). */
  date: string;
  closedAt: string;
  titleFr: string;
  headlineFr: string | null;
  made: { kind: RvReleveMadeKind; textFr: string } | null;
  claims: RvClaim[];
  words: RvReleveWord[];
  sources: RvSource[];
  /** A second Papier in the same period. */
  second: boolean;
};

export type RvReleveResult = { enabled: boolean; entries: RvReleveEntryData[] };

const MADE_KINDS: readonly RvReleveMadeKind[] = ['headline_choice', 'reader_question', 'headline_write', 'short_report', 'tell_margaux'];
const CLAIM_KINDS: readonly RvClaimKind[] = ['fact', 'interpretation', 'forecast'];

type Raw = Record<string, unknown>;
const obj = (value: unknown): Raw => (value && typeof value === 'object' && !Array.isArray(value) ? (value as Raw) : {});
const arr = (value: unknown): unknown[] => (Array.isArray(value) ? value : []);
const str = (value: unknown): string => (typeof value === 'string' ? value : '');
const strOrNull = (value: unknown): string | null => (typeof value === 'string' && value.trim() ? value : null);

function parseSource(raw: unknown): RvSource {
  const s = obj(raw);
  return { id: str(s.id), name: str(s.name), url: str(s.url), publishedAt: str(s.published_at) };
}

function parseClaim(raw: unknown): RvClaim | null {
  const c = obj(raw);
  const fr = str(c.fr);
  if (!fr) return null;
  const kind = (CLAIM_KINDS as readonly unknown[]).includes(c.kind) ? (c.kind as RvClaimKind) : 'fact';
  return {
    id: str(c.id),
    kind,
    fr,
    quote: str(c.quote),
    attributedTo: strOrNull(c.attributed_to),
    source: parseSource(c.source),
  };
}

function parseWord(raw: unknown): RvReleveWord | null {
  const w = obj(raw);
  const fr = str(w.fr);
  if (!fr) return null;
  return { fr, gloss: str(w.gloss), claimId: str(w.claim_id), used: w.used === true };
}

/** The local calendar day of an ISO datetime (`YYYY-MM-DD`). */
function localDay(iso: string): string {
  if (!iso) return '';
  const at = new Date(iso);
  if (Number.isNaN(at.getTime())) return /^\d{4}-\d{2}-\d{2}/.exec(iso)?.[0] ?? '';
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${at.getFullYear()}-${pad(at.getMonth() + 1)}-${pad(at.getDate())}`;
}

export function parseReleveEntry(raw: unknown): RvReleveEntryData | null {
  const e = obj(raw);
  const sessionId = str(e.session_id);
  const period = str(e.period);
  if (!sessionId || !period) return null;
  const madeRaw = obj(e.made);
  const madeText = str(madeRaw.text_fr);
  const made =
    madeText && (MADE_KINDS as readonly unknown[]).includes(madeRaw.kind)
      ? { kind: madeRaw.kind as RvReleveMadeKind, textFr: madeText }
      : null;
  const closedAt = str(e.closed_at);
  return {
    sessionId,
    period,
    periodLabel: str(e.period_label) || period,
    date: localDay(closedAt),
    closedAt,
    titleFr: str(e.title_fr),
    headlineFr: strOrNull(e.headline_fr),
    made,
    claims: arr(e.claims).map(parseClaim).filter((c): c is RvClaim => c !== null),
    words: arr(e.words).map(parseWord).filter((w): w is RvReleveWord => w !== null),
    sources: arr(e.sources).map(parseSource).filter((s) => Boolean(s.name)),
    second: e.second === true,
  };
}

/** `GET /revue/releve` → newest first, malformed entries dropped. */
export function parseReleve(raw: unknown): RvReleveEntryData[] {
  return arr(obj(raw).entries)
    .map(parseReleveEntry)
    .filter((entry): entry is RvReleveEntryData => entry !== null);
}

/** The anchor of one entry: `/notebook?mode=releve#revue-2026-W40`. */
export function releveAnchor(period: string): string {
  return `revue-${period}`;
}

export type ReleveClient = { releve: () => Promise<RvReleveResult> };

export function createReleveClient(transport: RevueTransport): ReleveClient {
  return {
    async releve() {
      try {
        return { enabled: true, entries: parseReleve(await transport.get(`${REVUE_BASE}/releve`)) };
      } catch (error) {
        const failure =
          error instanceof RevueError
            ? error
            : (() => {
                const response = (error as { response?: { status?: number; data?: unknown } } | null)?.response;
                return response ? parseRevueError(Number(response.status) || 0, response.data) : new RevueError(0, 'network');
              })();
        // The flag is off: a bare 404. The Relevé draws no Papier section.
        if (failure.code === 'revue_disabled') return { enabled: false, entries: [] };
        throw failure;
      }
    },
  };
}

let http: ReleveClient | null = null;

/** The real client, one per page load. */
export function revueReleveClient(): ReleveClient {
  if (!http) http = createReleveClient(httpRevueTransport());
  return http;
}
