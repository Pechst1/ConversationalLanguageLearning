/**
 * Which activity a cold start returns to — WP-20, fixing WP-19's defect D-1.
 *
 * `pilot:resume:v1` holds exactly one activity, and `pages/atelier.tsx` writes
 * it for every unfinished **legacy** practice session. Nothing wrote it for the
 * V2 daily journey, so a learner who was killed mid-scene came back to the
 * legacy Séance three times out of three: the stored activity was the only
 * candidate, and it was the older one.
 *
 * The rule this module encodes is the D-0 order of play, no more:
 *
 *   **When the journey envelope is enabled and a journey for today is still
 *   open, the journey is where a cold start lands.** Otherwise the stored
 *   activity is used exactly as before.
 *
 * Two properties worth keeping in mind while reading it:
 *
 *   1. **The mark is a fact about today, not a promise.** It carries the
 *      learner-local date the envelope reported and the journey id, and it is
 *      ignored once either goes stale. A journey that finished, was ended early
 *      or belongs to a previous day never wins, because "resume your scene"
 *      after the scene is over would be a lie — the same rule the morning push
 *      already applies (`serial_notifications.daily_journey_morning_copy`).
 *   2. **It never invents a destination.** The href is the journey shell on the
 *      Atelier route and nothing else; a corrupt or foreign value is discarded
 *      rather than navigated to.
 *
 * It lives under the `pilot:` prefix so the existing sign-out sweep
 * (`clearPilotResilience`) already clears it, and so a second account can never
 * inherit the first account's resume target.
 */

import {
  readResumeActivity,
  safeReadJson,
  safeRemove,
  safeWriteJson,
  type StorageLike,
} from '@/lib/pilot-resilience';
import type { JourneyStatus } from '@/types/daily-journey';

export const JOURNEY_RESUME_KEY = 'pilot:journey-resume:v1';

/** The only destination this module will ever produce. */
export const JOURNEY_RESUME_HREF = '/atelier?view=journey';

/**
 * A journey older than this is not "today's scene" under any timezone, so the
 * mark is dropped rather than trusted. Matches `journey-recovery`'s own window.
 */
export const JOURNEY_RESUME_MAX_AGE_MS = 48 * 60 * 60 * 1000;

/** The statuses a learner can still return *into*. */
const OPEN_STATUSES: readonly JourneyStatus[] = ['preparing', 'active', 'paused'];

export function journeyIsOpen(status: JourneyStatus | null | undefined): boolean {
  return !!status && OPEN_STATUSES.indexOf(status) >= 0;
}

export type JourneyResumeMark = {
  href: string;
  journeyId: string | null;
  /** The learner-local date the envelope reported when the mark was written. */
  localDate: string | null;
  status: JourneyStatus;
  updatedAt: string;
};

export function markJourneyResume(
  mark: Omit<JourneyResumeMark, 'href' | 'updatedAt'>,
  storage?: StorageLike | null,
) {
  safeWriteJson(
    JOURNEY_RESUME_KEY,
    { ...mark, href: JOURNEY_RESUME_HREF, updatedAt: new Date().toISOString() },
    storage,
  );
}

export function clearJourneyResume(storage?: StorageLike | null) {
  safeRemove(JOURNEY_RESUME_KEY, storage);
}

/**
 * The mark, or `null` when there is nothing honest to resume.
 *
 * `now` is injectable so the node suite can drive the midnight rollover without
 * a clock stub.
 */
export function readJourneyResume(
  now: Date = new Date(),
  storage?: StorageLike | null,
): JourneyResumeMark | null {
  const value = safeReadJson<JourneyResumeMark | null>(JOURNEY_RESUME_KEY, null, storage);
  if (!value || typeof value !== 'object') return null;
  if (value.href !== JOURNEY_RESUME_HREF) return null;
  if (!journeyIsOpen(value.status)) return null;
  const written = Date.parse(String(value.updatedAt || ''));
  if (!Number.isFinite(written)) return null;
  if (now.getTime() - written > JOURNEY_RESUME_MAX_AGE_MS) return null;
  return value;
}

/**
 * The href a cold start should land on, or `null` to stay where it is.
 *
 * This is the whole of D-1's fix: an open journey outranks the stored legacy
 * activity, and everything else behaves exactly as `readResumeActivity` did.
 */
export function resolveResumeHref(
  now: Date = new Date(),
  storage?: StorageLike | null,
): string | null {
  const journey = readJourneyResume(now, storage);
  if (journey) return journey.href;
  return readResumeActivity(storage)?.href ?? null;
}

// ---------------------------------------------------------------------------
// Where a resume may redirect at all (2026-09-24 walkthrough)
// ---------------------------------------------------------------------------

/**
 * The only URLs a bare app launch opens on: the root and Home. Anything else —
 * `/settings`, `/dossier`, `/notebook`, `/missions?…` — is a destination the
 * learner (or a link) chose, and a resume guess must never replace it.
 */
const LAUNCH_PATHS: readonly string[] = ['/', '/atelier'];

function normalizeLaunchPath(pathname: string): string {
  let path = pathname || '/';
  // A static export may be served as `/atelier.html` or `/index.html`.
  path = path.replace(/\/index(\.html)?$/, '/').replace(/\.html$/, '');
  if (path.length > 1) path = path.replace(/\/+$/, '');
  return path || '/';
}

/**
 * True when `launchUrl` — the URL the app was actually opened at, read from
 * `window.location`, not from the router — is a bare launch that a resume may
 * take over.
 *
 * The router's `pathname` is not enough: a static host that falls back to
 * `index.html` for an unknown path reports `/` for a load of `/settings`, which
 * is how a direct visit to Réglages used to be hijacked into the running
 * journey. A query string also counts as a choice (`?view=journey`,
 * `?mode=practice`, `?section=…`), so only the bare route resumes.
 */
export function launchMayResume(launchUrl: string | null | undefined): boolean {
  if (typeof launchUrl !== 'string' || !launchUrl.startsWith('/')) return false;
  const [pathAndQuery] = launchUrl.split('#');
  const queryAt = pathAndQuery.indexOf('?');
  const pathname = queryAt >= 0 ? pathAndQuery.slice(0, queryAt) : pathAndQuery;
  const query = queryAt >= 0 ? pathAndQuery.slice(queryAt + 1) : '';
  if (query.trim()) return false;
  return LAUNCH_PATHS.indexOf(normalizeLaunchPath(pathname)) >= 0;
}

/**
 * The href a cold start should land on, given where it was opened — or `null`
 * to leave the learner exactly where they asked to be.
 *
 * `_app` calls this once per app launch, never on a later in-app navigation:
 * tapping Home while a journey is open shows Home.
 */
export function resolveLaunchResumeHref(
  launchUrl: string | null | undefined,
  now: Date = new Date(),
  storage?: StorageLike | null,
): string | null {
  if (!launchMayResume(launchUrl)) return null;
  const href = resolveResumeHref(now, storage);
  if (!href || href === launchUrl) return null;
  return href;
}
