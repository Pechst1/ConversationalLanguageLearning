/**
 * Which language a line the story writer produced is really in, for the two lines of a scene's
 * ending a learner reads as given: the French line (`story_outcome.callback_fr`) and the line in
 * their own language under it (`summary_native`).
 *
 * Round 3 (walk 17 Nov, `walk2-integration-a1.md`): the A1 learner's German ending read «Lila
 * behält das im Kopf und reste avec toi dans l’attente des prochaines nouvelles.», and day 4's
 * French line was German with a French subject: «Tu hast gesagt, dass dir kalt ist; Marin hat eine
 * Suppe und eine Wärmflasche gebracht.» Both are the writer model's text, stored as written. A
 * learner never reads a sentence that changes language halfway: such a line is left out (the
 * card keeps its other line), never patched.
 *
 * Words quoted in «…» or “…” are the story's own and do not count.
 */

const QUOTED = /«[^»]*»|“[^”]*”|„[^“”]*[“”]|"[^"]*"/g;

const words = (text: string) =>
  text
    .replace(QUOTED, ' ')
    .toLowerCase()
    .replace(/[’`]/g, "'")
    .split(/[^a-zà-öø-ÿœæ']+/)
    .filter(Boolean);

/** Words of German or English that French never writes. */
const GERMAN = new Set(['und', 'ist', 'hast', 'hat', 'dass', 'nicht', 'eine', 'einen', 'einem', 'einer', 'der', 'die', 'das', 'dir', 'dich', 'ich', 'wir', 'mit', 'auf', 'für', 'auch', 'bist', 'möchtest', 'willst', 'gesagt', 'gebracht', 'behält', 'kopf', 'heute', 'morgen', 'zu']);
const ENGLISH = new Set(['the', 'and', 'you', 'your', 'is', 'has', 'have', 'with', 'said', 'will', 'of', 'to', 'it', 'that']);
/** Words of French that German and English never write, and no place of the story is named with («Chez Maître Vasseur»). */
const FRENCH = new Set(['tu', 'toi', 'moi', 'avec', 'dans', 'je', 'suis', 'très', 'attente', "l'attente", 'prochaines', 'nouvelles', "c'est", "qu'il", "qu'elle", "j'ai"]);

const count = (list: string[], set: Set<string>) => list.filter((w) => set.has(w)).length;

/** Whether a line reads as German or English rather than French (two or more of their words). */
export function readsAsForeign(text: string): boolean {
  const list = words(text);
  return count(list, GERMAN) >= 2 || count(list, ENGLISH) >= 2;
}

/** Whether a German or English line has French in it outside quotation marks. */
export function mixesFrenchIn(text: string): boolean {
  return readsAsForeign(text) && count(words(text), FRENCH) > 0;
}

/** The French line of an ending, or `''` when it is not French. */
export function frenchOrNothing(text: string | null | undefined): string {
  const t = String(text ?? '').trim();
  return t && !readsAsForeign(t) ? t : '';
}

/** The learner's-language line of an ending, or `''` when French runs into it. */
export function nativeOrNothing(text: string | null | undefined): string {
  const t = String(text ?? '').trim();
  return t && !mixesFrenchIn(t) ? t : '';
}
