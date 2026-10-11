/**
 * WP-168 · the characters a written season invented: who they are, as the server sent
 * them (`cast_rigs` on an episode: `{id, name, rig}`). Pure data, no drawing, so the
 * reader's models can register them without loading the rigs; `cast-registry` builds
 * the figure from the parameters when the stage asks (`rigs/generated.tsx`).
 *
 * A new face never takes an id the fixed cast answers to (its ids and aliases below,
 * the same table the registry uses); the fixed rig wins, as the server's own check
 * says. Its name is a seed only when no fixed cast member's name is in it.
 */
import { drawnCastIdFor } from '@/lib/cast-faces';

/** The fixed cast's rig ids (`cast-registry` RIGS; a test keeps the two equal). */
export const FIXED_RIG_IDS: readonly string[] = [
  'margaux_barman', 'lila_bonnet', 'augustin_de_roncourt', 'marin_leveque', 'romy_tremblay',
  'landlord_marchand', 'camille_marchand', 'odile_ferrand', 'user',
];

/** Short names and older ids the app and the story engine use for the same people. */
export const RIG_ALIASES: Readonly<Record<string, string>> = {
  margaux: 'margaux_barman',
  marin: 'marin_leveque',
  lila: 'lila_bonnet',
  gus: 'augustin_de_roncourt',
  augustin: 'augustin_de_roncourt',
  romy: 'romy_tremblay',
  marchand: 'landlord_marchand',
  m_marchand: 'landlord_marchand',
  camille: 'camille_marchand',
  odile: 'odile_ferrand',
  toi: 'user',
  you: 'user',
  learner: 'user',
};

export type GeneratedCastRig = { id: string; name?: string | null; rig?: unknown };
export type GeneratedSpec = { id: string; name: string; rig: unknown; key: string };

const SPECS: Record<string, GeneratedSpec> = {};
const NAMES: Record<string, string> = {};

export function foldKey(value: unknown): string {
  return String(value ?? '')
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .trim()
    .toLowerCase()
    .replace(/[\s-]+/g, '_');
}

function reserved(id: string): boolean {
  return FIXED_RIG_IDS.indexOf(id) >= 0 || Object.prototype.hasOwnProperty.call(RIG_ALIASES, id);
}

/** Register a written season's new faces; returns the ids now drawable. Never throws. */
export function registerGeneratedRigs(rows: unknown): string[] {
  if (!Array.isArray(rows)) return [];
  const ids: string[] = [];
  for (const row of rows as GeneratedCastRig[]) {
    const id = foldKey(row?.id);
    if (!/^[a-z0-9][a-z0-9_]{1,62}$/.test(id) || reserved(id)) continue;
    const name = String(row?.name || id).trim();
    SPECS[id] = { id, name, rig: row?.rig ?? null, key: JSON.stringify([name, row?.rig ?? null]) };
    if (!drawnCastIdFor(name)) {
      const first = foldKey(name.split(/\s+/)[0]);
      if (first && !reserved(first)) NAMES[first] = id;
      const full = foldKey(name);
      if (full && !reserved(full)) NAMES[full] = id;
    }
    ids.push(id);
  }
  return ids;
}

/** The registered new face with this exact id, or null. */
export function generatedSpec(id: unknown): GeneratedSpec | null {
  return SPECS[foldKey(id)] ?? null;
}

/** The id of a registered new face that `seeds` name exactly (its id or its name), else null. */
export function generatedRigId(...seeds: unknown[]): string | null {
  for (const seed of seeds) {
    const key = foldKey(seed);
    if (!key) continue;
    if (SPECS[key]) return key;
    if (NAMES[key]) return NAMES[key];
  }
  return null;
}
