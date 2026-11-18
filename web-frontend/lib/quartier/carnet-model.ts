/**
 * Le Quartier · ton carnet, as data (P12 stage 5): the notebook reads the story.
 *
 * Observed 17 Nov: after seven played days the carnet said «Personne encore. Entre au Mistral.»,
 * listed the places of Le Papier as the learner's places, and labelled a day «Épisode 1». The
 * quarter only knew what it had itself seen on this phone.
 *
 * Now each section is fed from what the app already knows, without new storage:
 * - **Les gens**: the people the learner has met in the story (the Feuilleton's trombinoscope,
 *   `GET /serial/threads/current/cast`), each with their register and the newest thing they know
 *   about the learner; the quarter's own line on how they see you is kept for those met here too.
 * - **Ce que tu as fait**: the learner's choices, the very lines the quarter's end card lists
 *   (`Memory.journal`), each under the day's edition number («Nº 8», `episodeLabel`), never a
 *   season page's number.
 * - **Les lieux**: the places of the played days (the archive's days carry their place), and the
 *   places the learner has walked into here.
 * - **Dans le journal**: Le Papier's places, in a section of their own, only while the news
 *   feature is on.
 * An empty section says what will fill it.
 */
import { castRegister, knownAboutYou } from '@/components/feuilleton/archive/trombinoscope-model';

import { NAMES, NOTES, regardWords, replyEffects } from './agency';
import { editionKey, eligible } from './memory';
import type { CastId, Memory, Value, Words } from './memory';
import { PLACE_NAMES, episodeLabel } from './story';
import { WORLD } from './world';
import type { WorldPlace } from './world';

/** A member of the cast as the trombinoscope's endpoint sends it (read defensively). */
export interface CarnetCastMember {
  id: string;
  name?: string | null;
  register?: unknown;
  tu_since?: unknown;
  known_about_you?: unknown;
  relationship?: Record<string, unknown> | null;
}

/** A played day, as the archive files it. */
export interface CarnetDay {
  date?: string | null;
  edition_no?: number | null;
  title_fr?: string | null;
  location_id?: string | null;
  location_name?: string | null;
  /** the cards chosen on a season page played as a page (the archive's `choices`) */
  choices?: Array<{ turn_id: string; reply_id: string; label_fr?: string | null }> | null;
}

/** What the app knows of the learner's story; each part `null` when it could not be read. */
export interface CarnetStory {
  cast: CarnetCastMember[] | null;
  days: CarnetDay[] | null;
  /** Le Papier is switched on for this learner */
  news: boolean;
}

export interface CarnetPerson {
  who: string;
  name: string;
  register: 'tu' | 'vous' | null;
  /** the newest thing they know about you (French: the story's own words) */
  knows: string | null;
  /** how they see you, from what happened in the quarter (met here only) */
  regard: Words | null;
  notes: Words[];
  /** a regard to draw the face with (0 when the quarter never met them) */
  mood: number;
}

export interface CarnetDid {
  words: Words;
  /** «Nº 8», «En te promenant», a place's name; null when the day's number is not known */
  label: string | null;
}

export interface CarnetPlace {
  id: string;
  name: Words;
  why: Words | null;
  tag: 'known' | 'noticed' | 'later' | 'building' | 'discover';
  /** the editions set there, newest first («Nº 8») */
  editions: string[];
}

export interface CarnetModel {
  people: CarnetPerson[];
  did: CarnetDid[];
  places: CarnetPlace[];
  /** Le Papier's places; `null`: the section is not shown (the news is off) */
  news: CarnetPlace[] | null;
  /** what will fill each section while it is empty */
  empty: { people: Words; did: Words; places: Words; news: Words };
}

const w = (fr: string, en: string, de: string): Words => ({ fr, en, de });

export const CARNET_EMPTY = {
  people: w(
    'Personne encore. Les gens que tu rencontres dans l’histoire viendront ici.',
    'Nobody yet. The people you meet in the story will appear here.',
    'Noch niemand. Die Leute, die du in der Geschichte triffst, erscheinen hier.',
  ),
  did: w(
    'Rien encore. Ce que tu choisis dans une scène viendra ici.',
    'Nothing yet. What you choose in a scene will appear here.',
    'Noch nichts. Was du in einer Szene entscheidest, erscheint hier.',
  ),
  places: w(
    'Aucun lieu encore. Les lieux de tes épisodes viendront ici.',
    'No places yet. The places of your episodes will appear here.',
    'Noch keine Orte. Die Orte deiner Folgen erscheinen hier.',
  ),
  news: w(
    'Rien encore. Les lieux du Papier viendront ici.',
    'Nothing yet. The places in Le Papier will appear here.',
    'Noch nichts. Die Orte aus Le Papier erscheinen hier.',
  ),
};

export { editionKey };

const WALKED: Words = w('En te promenant', 'Out walking', 'Beim Spazieren');

/** The label of a day in the carnet: its edition, a walk, or a visit to a place or a room. Never a season page's number. */
export function dayLabel(day: string, state: Record<string, Value>): string | null {
  const n = state[editionKey(day)];
  if (typeof n === 'number') return episodeLabel(n);
  if (day === 'roam') return WALKED.fr;
  const m = /^(visit|room)\.(.+)$/.exec(day);
  return m ? WORLD.places.find((p) => p.id === m[2])?.name.fr ?? null : null;
}

/** The built place a story location is (its own id, or the place that stages it), if any. */
function worldPlaceOf(location: string): WorldPlace | null {
  return WORLD.places.find((p) => p.id === location || (p.stages ?? []).includes(location)) ?? null;
}

/** A card chosen on a page, as the carnet says it: the quarter's own line for it, else the card. */
export function choiceWords(turnId: string, replyId: string, label: string | null): Words | null {
  const line = replyEffects(turnId, replyId, true).find((e) => e.kind === 'journal');
  if (line && line.kind === 'journal') return line.words;
  const card = label?.trim();
  return card ? w(`Tu as choisi : « ${card} »`, `You chose: “${card}”`, `Du hast gewählt: „${card}“`) : null;
}

const knownCast = (id: string): id is CastId => Object.prototype.hasOwnProperty.call(NAMES, id);

export function carnetOf(memory: Memory, story: CarnetStory | null, world: Record<string, Value> = {}): CarnetModel {
  const state = { ...memory.state(), ...world };
  const notes = eligible(NOTES, state);
  const metHere = memory.met();

  /* ---- the people: the story's, then anyone met only here -------------------------------- */
  const people: CarnetPerson[] = [];
  const here = (who: string) => {
    if (!knownCast(who) || !metHere.includes(who)) return { regard: null, notes: [] as Words[], mood: 0 };
    const r = memory.regard(who);
    return { regard: regardWords(who, r), notes: notes.filter((n) => n.who === who).slice(0, 2).map((n) => n.say), mood: r };
  };
  for (const member of story?.cast ?? []) {
    if (!member || typeof member.id !== 'string' || !member.id) continue;
    const name = (typeof member.name === 'string' && member.name.trim()) || (knownCast(member.id) ? NAMES[member.id] : '');
    if (!name || people.some((p) => p.who === member.id)) continue;
    people.push({
      who: member.id,
      name,
      register: castRegister(member).register,
      knows: knownAboutYou(member, 1)[0]?.text_fr ?? null,
      ...here(member.id),
    });
  }
  for (const who of metHere) {
    if (people.some((p) => p.who === who)) continue;
    people.push({ who, name: NAMES[who], register: null, knows: null, ...here(who) });
  }

  /* ---- what you did: the end card's lines, under the day's own number --------------------- */
  const did: CarnetDid[] = memory.journal().map((j) => ({ words: j.words, label: dayLabel(j.day, state) }));
  // round 2: the days played as pages too (observed 17 Nov: only day 1, played here, was listed).
  // The page reader keeps its choices on the server (the archive's `choices`), never in this
  // phone's memory: each card chosen is the line the quarter's end card says for it, else «Tu as
  // choisi : …», under the day's number, once.
  const byEdition = [...(story?.days ?? [])].sort((a, b) => (b.edition_no ?? 0) - (a.edition_no ?? 0));
  for (const day of byEdition) {
    const label = episodeLabel(day.edition_no);
    for (const c of day.choices ?? []) {
      const words = choiceWords(c.turn_id, c.reply_id, c.label_fr ?? null);
      if (!words || did.some((d) => d.words.fr === words.fr && (d.label === label || !d.label || !label))) continue;
      did.push({ words, label });
    }
  }
  const edition = (d: CarnetDid) => Number(/^Nº (\d+)$/.exec(d.label ?? '')?.[1] ?? Infinity);
  did.sort((a, b) => edition(b) - edition(a));
  did.splice(14);

  /* ---- the places of the played days, then the ones walked into here ---------------------- */
  const places: CarnetPlace[] = [];
  const add = (id: string, name: Words, why: Words | null, edition: string | null) => {
    const found = places.find((p) => p.id === id);
    if (found) {
      if (edition && !found.editions.includes(edition)) found.editions.push(edition);
      return;
    }
    places.push({ id, name, why, tag: 'known', editions: edition ? [edition] : [] });
  };
  const days = [...(story?.days ?? [])].sort((a, b) => (b.edition_no ?? 0) - (a.edition_no ?? 0) || String(b.date ?? '').localeCompare(String(a.date ?? '')));
  for (const day of days) {
    const location = day.location_id?.trim();
    const named = day.location_name?.trim();
    if (!location && !named) continue;
    // the place the quarter has for it (Le Mistral is the quai's; the stairwell its room), else the story's name
    const found = location ? worldPlaceOf(location) : null;
    const built = found && found.kind !== 'news' ? found : null;
    const own = location ? PLACE_NAMES[location] : undefined;
    const name = built?.name ?? own ?? (named ? w(named, named, named) : null);
    if (!name) continue;
    add(built?.id ?? location ?? (named as string), name, built?.why ?? null, episodeLabel(day.edition_no));
  }
  const been = memory.places();
  for (const p of WORLD.places) {
    if (p.kind === 'news' || been[p.id] !== 'visited') continue;
    add(p.id, p.name, p.why, null);
  }

  /* ---- Le Papier's places, in their own section, only with the news on --------------------- */
  const news = story?.news
    ? WORLD.places
        .filter((p) => p.kind === 'news' && (p.status !== 'locked' || been[p.id]))
        .map<CarnetPlace>((p) => ({
          id: p.id,
          name: p.name,
          why: p.why,
          tag: been[p.id] === 'visited' ? 'known' : p.status === 'en_chantier' ? 'building' : been[p.id] === 'noticed' ? 'noticed' : 'discover',
          editions: [],
        }))
    : null;

  return { people, did, places, news, empty: CARNET_EMPTY };
}
