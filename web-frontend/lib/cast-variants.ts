/**
 * WP-116 · how the drawn cast looks for this learner. Today that is Camille, whose
 * look follows the learner's T1 Day B choice (`headline.cast_variants`). Before the
 * choice there is no entry, and Camille's drawn face is not shown.
 */
const STORAGE_KEY = 'atelier.castVariants';
let memory: Record<string, string> = {};

function read(): Record<string, string> {
  if (typeof window === 'undefined') return memory;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? { ...JSON.parse(raw), ...memory } : memory;
  } catch {
    return memory;
  }
}

/** Remember what the server says (the headline carries it on every `/today`). */
export function rememberCastVariants(variants: Record<string, string> | null | undefined): void {
  if (!variants || typeof variants !== 'object') return;
  const clean: Record<string, string> = {};
  Object.keys(variants).forEach((id) => {
    const value = variants[id];
    if (typeof value === 'string' && value) clean[id] = value;
  });
  if (!Object.keys(clean).length) return;
  memory = { ...memory, ...clean };
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...read(), ...clean }));
  } catch {
    /* storage refused: memory still holds it for this session */
  }
}

export function castVariant(id: string): string | null {
  return read()[id] ?? null;
}

/** Characters who must not be drawn until the learner has chosen their look. */
export const NEEDS_VARIANT = new Set(['camille_marchand']);
