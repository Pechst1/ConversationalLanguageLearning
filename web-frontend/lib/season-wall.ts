/**
 * Le mur du Mistral · the season's objects on the café's wall, in the order the story gave them.
 *
 * The season ends on a wall: in the finale, Odile's Polaroids hang framed at Le Mistral. This is
 * the learner's own, from the first object on. `GET /serial/season/wall` says how far the
 * learner has read (every tentpole up to it has been handed over) and which choices the objects
 * show; the device adds what it was handed itself, so the wall never loses an object it saw land.
 * Hooks still to come show only their part number: nothing is spoiled.
 *
 * Pure model and copy; the screen is components/cast/items/MurDuMistral.tsx.
 */
import type { ItemMarks } from '@/components/cast/items/PlotItem';
import type { CameoLang, CameoLine } from './cameo';
import { itemKey, SEASON_ITEMS } from './season-items';
import type { SeasonItem } from './season-items';

export type SeasonWall = {
  season_id: string | null;
  /** the furthest part read; `null` once the season is over (every object) */
  through: number | null;
  /** a tentpole (`t3`) → the first page of it the learner read */
  pages: Record<string, string>;
  marks: ItemMarks;
};

export type WallHook = {
  item: SeasonItem;
  /** the part of the season it belongs to (`t3` → 3) */
  number: number;
  owned: boolean;
  /** the page to reread it from, when the server knows it */
  page: string | null;
};

export const EMPTY_WALL: SeasonWall = { season_id: null, through: 0, pages: {}, marks: {} };

function number(item: SeasonItem): number {
  return Number(item.segment.slice(1)) || 0;
}

/** Every object of the learner's season, in order, each owned or still an empty hook. */
export function wallHooks(wall: SeasonWall | null, deviceItems: readonly string[] = []): WallHook[] {
  const fromDevice = SEASON_ITEMS.find((item) => deviceItems.includes(itemKey(item)))?.season;
  const season = wall?.season_id || fromDevice || null;
  if (!season) return [];
  return SEASON_ITEMS.filter((item) => item.season === season)
    .map((item) => {
      const n = number(item);
      const reached = wall?.season_id === season && (wall.through === null || n <= (wall.through ?? 0));
      return { item, number: n, owned: reached || deviceItems.includes(itemKey(item)), page: wall?.pages?.[item.segment] ?? null };
    })
    .sort((a, b) => a.number - b.number);
}

/** The marks that belong to this object (the Polaroid shows where it went, the petition your promise). */
export function marksFor(item: SeasonItem, marks: ItemMarks | null | undefined): ItemMarks {
  if (!marks) return {};
  if (item.id === 'polaroid' && marks['s1.fire_photo']) return { 's1.fire_photo': marks['s1.fire_photo'] };
  if (item.id === 'petition' && marks['s1.promise_gus']) return { 's1.promise_gus': marks['s1.promise_gus'] };
  return {};
}

const L = (fr: string, de: string, en: string): CameoLine => ({ fr, de, en });

/** What the mark means, said plainly under the object; `null` when it shows none. */
export function markLine(item: SeasonItem, marks: ItemMarks | null | undefined): CameoLine | null {
  const own = marksFor(item, marks);
  switch (own['s1.fire_photo'] ?? own['s1.promise_gus']) {
    case 'wall':
      return L(
        'Tu l’as remise au mur. Lundi, tout le quartier le saura.',
        'Du hast es wieder an die Wand gehängt. Am Montag weiß es das ganze Viertel.',
        'You put it back on the wall. By Monday, the whole neighbourhood will know.',
      );
    case 'margaux':
      return L(
        'Tu l’as rendue à Margaux. Elle dort sous le plateau de la caisse.',
        'Du hast es Margaux zurückgegeben. Es liegt unter dem Kasseneinsatz.',
        'You gave it back to Margaux. It sleeps under the till tray.',
      );
    case 'yes':
      return L('Gus a noté ta promesse.', 'Gus hat sich dein Versprechen notiert.', 'Gus made a note of your promise.');
    case 'half':
      return L(
        '« J’essaie », a noté Gus, avec un point d’interrogation.',
        '„Ich versuch’s“, hat Gus notiert, mit Fragezeichen.',
        '“I’ll try,” Gus noted, with a question mark.',
      );
    default:
      return null;
  }
}

export const WALL_COPY = {
  title: 'Le mur du Mistral',
  deck: L(
    'Les objets que la saison t’a confiés, dans l’ordre.',
    'Die Gegenstände, die dir die Staffel anvertraut hat, der Reihe nach.',
    'The objects the season has handed you, in order.',
  ),
  empty: L(
    'Le mur attend son premier objet : il arrive après la première page de la saison.',
    'Die Wand wartet auf ihren ersten Gegenstand: Er kommt nach der ersten Seite der Staffel.',
    'The wall is waiting for its first object: it comes after the season’s first page.',
  ),
  to_come: L('Partie {n}, à venir', 'Teil {n}, kommt noch', 'Part {n}, still to come'),
  count: L('{n} objets sur {total}', '{n} von {total} Gegenständen', '{n} of {total} objects'),
  replay: L('Revoir la remise', 'Nochmal ansehen', 'Watch it again'),
  reread: L('Relire la page', 'Seite lesen', 'Reread the page'),
  close: L('Fermer', 'Schließen', 'Close'),
  back: L('Retour', 'Zurück', 'Back'),
};

export function wallText(line: CameoLine, lang: CameoLang, fill: Record<string, string | number> = {}): string {
  const text = line[lang] || line.en;
  return text.replace(/\{(\w+)\}/g, (_, key: string) => String(fill[key] ?? ''));
}

export function toCameoLang(value: string | null | undefined): CameoLang {
  return value === 'de' || value === 'fr' ? value : 'en';
}

/** The page a past part is reread from. */
export function rereadHref(page: string): string {
  return `/graphic-novel?scene=${encodeURIComponent(page)}`;
}
