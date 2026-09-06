/**
 * One place that decides which translation the client renders.
 *
 * Every surface used to read `translations.de` first and fall back to `.en`,
 * which served German to learners who had chosen English at signup. The server
 * now resolves the gloss for the signed-in learner (app/services/glosses.py) and
 * sends it as `translation`, so the client's job is to trust that field and only
 * fall back when a payload predates the resolution.
 *
 * The fallback deliberately has no language preference of its own: it takes
 * whatever gloss exists, because guessing a second time is how the original bug
 * happened.
 */

type GlossMap = Record<string, string | null | undefined> | null | undefined;

export type GlossCarrier = {
  translation?: string | null;
  translations?: GlossMap;
};

const FALLBACK_ORDER = ['en', 'de', 'fr'] as const;

export function glossFromMap(translations: GlossMap): string {
  if (!translations) return '';
  for (const code of FALLBACK_ORDER) {
    const value = String(translations[code] ?? '').trim();
    if (value) return value;
  }
  // A language the client does not know about is still better than nothing.
  for (const value of Object.values(translations)) {
    const text = String(value ?? '').trim();
    if (text) return text;
  }
  return '';
}

/** The learner-facing translation of a word, or `fallback` when there is none. */
export function learnerGloss(item: GlossCarrier | null | undefined, fallback = ''): string {
  if (!item) return fallback;
  const resolved = String(item.translation ?? '').trim();
  if (resolved) return resolved;
  return glossFromMap(item.translations) || fallback;
}
