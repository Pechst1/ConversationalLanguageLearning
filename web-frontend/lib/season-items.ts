/**
 * Les objets de la saison · one drawn object for each part of a season.
 *
 * Every tentpole of «La clé d'Odile» turns on a thing you can hold: the key with the cicada on
 * the first night, Odile's calendar upstairs, Gus's petition at the town hall, the Polaroid, the
 * letter from Berlin, the black notebook, Gus's bicycle chain, and the envelope behind the
 * radiator. When the learner has read the first page of a new part, the person that object
 * belongs to walks in holding it (see `decideCameo`'s `chapter`), and the gap days that follow
 * carry it on.
 *
 * Nothing here says more than the page the learner has just read: the object is handed over
 * after the scene, never before it.
 *
 * Pure data; the drawings are in components/cast/items.
 */
import type { CameoLine, CameoMood } from './cameo';

export type SeasonItemId =
  | 'cle_cigale'
  | 'calendrier'
  | 'petition'
  | 'polaroid'
  | 'lettre_berlin'
  | 'carnet_noir'
  | 'chaine'
  | 'enveloppe';

export type SeasonPart = {
  season_id: string;
  segment: string;
  kind?: 'tentpole' | 'gap' | null;
  day_in_segment?: number | null;
};

export type SeasonItem = {
  id: SeasonItemId;
  season: string;
  /** the tentpole that hands it over */
  segment: string;
  /** what it is called, with its article */
  name: CameoLine;
  /** who walks in holding it */
  carrier: string;
  mood: CameoMood;
  /** what they say as they hand it over */
  line: CameoLine;
};

const L = (fr: string, de: string, en: string): CameoLine => ({ fr, de, en });

export const SEASON_ITEMS: readonly SeasonItem[] = [
  {
    id: 'cle_cigale',
    season: 's1',
    segment: 't1',
    name: L('la clé à la cigale', 'der Schlüssel mit der Zikade', 'the key with the cicada'),
    carrier: 'margaux_barman',
    mood: 'emue',
    line: L('Cette cigale… je la connais. Garde-la.', 'Diese Zikade… die kenne ich. Behalt sie.', 'That cicada… I know it. Keep it.'),
  },
  {
    id: 'calendrier',
    season: 's1',
    segment: 't2',
    name: L('le calendrier d’Odile', 'Odiles Kalender', 'Odile’s calendar'),
    carrier: 'lila_bonnet',
    mood: 'surprise',
    line: L('« Dimanche : M. »… C’est qui, M. ?', '„Sonntag: M.“… Wer ist M.?', '“Sunday: M.”… Who is M.?'),
  },
  {
    id: 'petition',
    season: 's1',
    segment: 't3',
    name: L('la pétition', 'die Petition', 'the petition'),
    carrier: 'augustin_de_roncourt',
    mood: 'ravie',
    line: L('Cent quatre-vingt-sept signatures. Et la mienne !', 'Hundertsiebenundachtzig Unterschriften. Und meine!', 'One hundred and eighty-seven signatures. And mine!'),
  },
  {
    id: 'polaroid',
    season: 's1',
    segment: 't4',
    name: L('le Polaroid', 'das Polaroid', 'the Polaroid'),
    carrier: 'romy_tremblay',
    mood: 'surprise',
    line: L('Une photo ne ment pas. Regarde bien.', 'Ein Foto lügt nicht. Schau genau hin.', 'A photo doesn’t lie. Look closely.'),
  },
  {
    id: 'lettre_berlin',
    season: 's1',
    segment: 't5',
    name: L('la lettre de Berlin', 'der Brief aus Berlin', 'the letter from Berlin'),
    carrier: 'lila_bonnet',
    mood: 'emue',
    line: L('Un an à Berlin. Maintenant, tu sais.', 'Ein Jahr in Berlin. Jetzt weißt du es.', 'A year in Berlin. Now you know.'),
  },
  {
    id: 'carnet_noir',
    season: 's1',
    segment: 't6',
    name: L('le carnet noir', 'das schwarze Notizbuch', 'the black notebook'),
    carrier: 'landlord_marchand',
    mood: 'emue',
    line: L('Elle écrivait tout. Même pour moi.', 'Sie schrieb alles auf. Sogar für mich.', 'She wrote everything down. Even for me.'),
  },
  {
    id: 'chaine',
    season: 's1',
    segment: 't7',
    name: L('la chaîne de Gus', 'Gus’ Kette', 'Gus’s chain'),
    carrier: 'augustin_de_roncourt',
    mood: 'fachee',
    line: L('Moi, je ne bouge pas d’ici. Jamais.', 'Ich gehe hier nicht weg. Niemals.', 'I’m not moving from here. Ever.'),
  },
  {
    id: 'enveloppe',
    season: 's1',
    segment: 't8',
    name: L('l’enveloppe d’Odile', 'Odiles Umschlag', 'Odile’s envelope'),
    carrier: 'marin_leveque',
    mood: 'emue',
    line: L('Tu vois ? Il fallait taper sur le radiateur.', 'Siehst du? Man musste gegen die Heizung hauen.', 'See? You had to hit the radiator.'),
  },
];

/** `t3` → 3, `g3` → 3, anything else → null. */
function partNumber(segment: string): number | null {
  const match = /^[tg](\d+)$/.exec(segment);
  return match ? Number(match[1]) : null;
}

/** The object a tentpole hands over (only the tentpole itself: a gap only carries it). */
export function itemHandedIn(part: SeasonPart | null | undefined): SeasonItem | null {
  if (!part || !/^t\d+$/.test(part.segment)) return null;
  return SEASON_ITEMS.find((item) => item.season === part.season_id && item.segment === part.segment) ?? null;
}

/** The object this part of the season is about: the tentpole's own, or the one a gap carries on. */
export function itemForPart(part: SeasonPart | null | undefined): SeasonItem | null {
  if (!part) return null;
  const n = partNumber(part.segment);
  if (n === null) return null;
  return SEASON_ITEMS.find((item) => item.season === part.season_id && item.segment === `t${n}`) ?? null;
}

/** A stable name for a handed-over object, as the device remembers it. */
export function itemKey(item: Pick<SeasonItem, 'season' | 'id'>): string {
  return `${item.season}.${item.id}`;
}

export function seasonItem(id: string | null | undefined): SeasonItem | null {
  if (!id) return null;
  return SEASON_ITEMS.find((item) => item.id === id) ?? null;
}
