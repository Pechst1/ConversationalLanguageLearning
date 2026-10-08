/**
 * WP-99 «Le facteur et les dépêches» — where a tapped push lands.
 *
 * Three kinds of push, three destinations:
 *
 *   · the morning «Dépêche» (a character's line about today) → today's scene,
 *     `/atelier?start=today`, which resumes or opens the day;
 *   · «Le facteur est passé» (a letter arrived) → that letter in the Courrier;
 *   · «Dernier jour pour répondre à …» (a deadline tomorrow) → that letter.
 *
 * The server sends a `route`; this is the one place that decides whether to
 * trust it, and what to do when it is missing or too vague (a letter push
 * that only says `/missions`). Pure — shared by the native listener
 * (`native-push.ts`) and pinned by `push-deep-link.test.js`. The service
 * worker (`public/sw.js`) keeps its own copy of the same small table.
 */

export const TODAY_SCENE_ROUTE = '/atelier?start=today';

export type PushKind = 'depeche' | 'letter' | 'deadline' | 'other';

const DEPECHE_KINDS = new Set(['morning_teaser', 'morning_depeche', 'depeche', 'morning_edition', 'streak_reminder']);
const LETTER_KINDS = new Set(['letter_arrived', 'letter', 'facteur', 'courrier', 'le_facteur']);
const DEADLINE_KINDS = new Set(['letter_deadline', 'deadline', 'dernier_jour', 'mission_deadline']);

/** Which of the three a payload's `kind` is; anything else is `other`. */
export function pushKindOf(kind: unknown): PushKind {
  const key = typeof kind === 'string' ? kind.trim().toLowerCase() : '';
  if (DEPECHE_KINDS.has(key)) return 'depeche';
  if (LETTER_KINDS.has(key)) return 'letter';
  if (DEADLINE_KINDS.has(key)) return 'deadline';
  return 'other';
}

/**
 * An in-app path, or `null`. Never another origin (`//host`, `https:`), never
 * a script URL, never a backslash trick — a push payload is data.
 */
export function safeInAppRoute(route: unknown): string | null {
  if (typeof route !== 'string') return null;
  const value = route.trim();
  if (!value.startsWith('/') || value.startsWith('//') || value.includes('\\')) return null;
  if (/^\/+[a-z][a-z0-9+.-]*:/i.test(value)) return null;
  return value;
}

function missionIdOf(data: Record<string, unknown>): string | null {
  for (const key of ['mission_id', 'letter_id', 'mission']) {
    const raw = data[key];
    if ((typeof raw === 'string' && raw.trim()) || (typeof raw === 'number' && Number.isFinite(raw))) {
      return String(raw).trim();
    }
  }
  return null;
}

/**
 * Where a tapped notification opens, or `null` for "stay where you are".
 *
 * A letter or deadline push opens *the* letter when the payload names it,
 * even if its route only says «the Courrier»; a Dépêche always lands on the
 * day (its own `/atelier…` route when it sent one). Any other push keeps the
 * server's route when it is a safe in-app path.
 */
export function pushDeepLink(data: Record<string, unknown> | null | undefined): string | null {
  const payload = data && typeof data === 'object' ? data : {};
  const route = safeInAppRoute(payload.route);
  switch (pushKindOf(payload.kind)) {
    case 'depeche':
      return route && route.startsWith('/atelier') ? route : TODAY_SCENE_ROUTE;
    case 'letter':
    case 'deadline': {
      if (route && /[?&]mission=/.test(route)) return route;
      const id = missionIdOf(payload);
      if (id) return `/missions?mission=${encodeURIComponent(id)}`;
      return route ?? '/missions';
    }
    default:
      return route;
  }
}

/** The portrait a push carries — `image_url` (WP-99) or the older `image` — as an in-app or https URL. */
export function pushImageOf(data: Record<string, unknown> | null | undefined): string | null {
  for (const key of ['image_url', 'image']) {
    const raw = data?.[key];
    if (typeof raw !== 'string') continue;
    const value = raw.trim();
    if (safeInAppRoute(value) || /^https:\/\//i.test(value)) return value;
  }
  return null;
}
