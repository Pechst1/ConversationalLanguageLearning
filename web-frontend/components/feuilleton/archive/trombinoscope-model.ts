/**
 * WP-97 «Le trombinoscope» — one character's card, as data.
 *
 * The cast payload (`GET /serial/threads/current/cast`) gained the engine's
 * own relationship: `trust` (0..5, and it can fall), `known_about_you`
 * (what they witnessed), `register` and `tu_since`. `closeness` — a count
 * that only ever went up — is retired from the screen.
 *
 * Read defensively: the new fields may sit on the member or under
 * `relationship`, and an older server sends none of them. Absent trust is
 * «no exchange yet», never a meter at zero.
 */

import { archiveCopy, archiveDate, faFill } from './archive-copy';

export type KnownFact = { text_fr: string; date: string | null; scene_id: string | null };

export type TrustMark = 'filled' | 'empty';

type MemberLike = {
  name?: string | null;
  trust?: unknown;
  register?: unknown;
  tu_since?: unknown;
  known_about_you?: unknown;
  relationship?: {
    trust?: unknown;
    register?: unknown;
    tu_since?: unknown;
    known_about_you?: unknown;
  } | null;
} & Record<string, any>;

const pick = (member: MemberLike | null | undefined, key: 'trust' | 'register' | 'tu_since' | 'known_about_you') =>
  member?.[key] !== undefined && member?.[key] !== null ? member[key] : member?.relationship?.[key];

/** 0..5, or `null` when the server has not measured it (an older payload, or no exchange). */
export function castTrust(member: MemberLike | null | undefined): number | null {
  const raw = pick(member, 'trust');
  if (raw === null || raw === undefined || raw === '') return null;
  const n = Number(raw);
  if (!Number.isFinite(n)) return null;
  return Math.max(0, Math.min(5, Math.round(n)));
}

/** The five marks: filled up to the trust, outlined after. `null` draws no meter. */
export function trustMarks(trust: number | null | undefined): TrustMark[] | null {
  if (trust === null || trust === undefined || !Number.isFinite(Number(trust))) return null;
  const n = Math.max(0, Math.min(5, Math.round(Number(trust))));
  return [0, 1, 2, 3, 4].map((index) => (index < n ? 'filled' : 'empty'));
}

/** «tu» or «vous», and since when the «tu» was accepted. */
export function castRegister(member: MemberLike | null | undefined): { register: 'tu' | 'vous'; since: string | null } {
  const register = String(pick(member, 'register') || '').trim().toLowerCase() === 'tu' ? 'tu' : 'vous';
  const since = pick(member, 'tu_since') as { date?: unknown } | null | undefined;
  const date = register === 'tu' && since && typeof since.date === 'string' && since.date.trim() ? since.date.trim() : null;
  return { register, since: date };
}

/** «tu depuis le 12 sept.» / «tu» / «vous», in the chrome language. */
export function registerLine(member: MemberLike | null | undefined, language?: unknown): string {
  const t = archiveCopy(language);
  const { register, since } = castRegister(member);
  if (register === 'vous') return t.register_vous;
  const date = archiveDate(since, language);
  return date ? faFill(t.register_tu_since, { date }) : t.register_tu;
}

/** «Ce qu'ils savent de vous»: at most five, the newest first, each dated. */
export function knownAboutYou(member: MemberLike | null | undefined, max = 5): KnownFact[] {
  const raw = pick(member, 'known_about_you');
  const facts: KnownFact[] = (Array.isArray(raw) ? raw : [])
    .map((entry: any) => ({
      text_fr: typeof entry?.text_fr === 'string' ? entry.text_fr.trim() : '',
      date: typeof entry?.date === 'string' && entry.date.trim() ? entry.date.trim() : null,
      scene_id: typeof entry?.scene_id === 'string' && entry.scene_id.trim() ? entry.scene_id.trim() : null,
    }))
    .filter((fact) => fact.text_fr);
  return facts
    .map((fact, order) => ({ fact, order }))
    .sort((a, b) => {
      if (a.fact.date && b.fact.date && a.fact.date !== b.fact.date) return a.fact.date < b.fact.date ? 1 : -1;
      if (a.fact.date && !b.fact.date) return -1;
      if (!a.fact.date && b.fact.date) return 1;
      return a.order - b.order;
    })
    .slice(0, Math.max(0, max))
    .map((entry) => entry.fact);
}
