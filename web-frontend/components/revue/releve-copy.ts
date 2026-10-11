/**
 * WP-119 phase 3 · the words of «Le Papier» in Le Relevé and of the Papier
 * inside the journey player. The Revue's shared words (claim kinds, «D'après …»,
 * the made labels, «Continuer») stay in `revue-copy.ts`; only what is new lives
 * here, in the three chrome languages.
 */


export type ReleveCopy = {
  /** The section head (owner decision §12.1: the chrome label is «Le Papier»). */
  section_title: string;
  clippings_one: string;
  clippings_other: string;
  words_one: string;
  words_other: string;
  facts_one: string;
  facts_other: string;
  /** Phase 2: what the learner told Margaux. */
  made_tell_margaux: string;
  second: string;
  show: string;
  hide: string;
  words_label: string;
  claims_label: string;
  /** The journey player's Revue-day mount. */
  papier_loading: string;
  papier_error: string;
  /** WP-121 A.4: «N mots t'attendent sur la carte» → /carte (when the map has due words). */
  carte_due_one: string;
  carte_due_other: string;
};

const FR: ReleveCopy = {
  section_title: 'Le Papier',
  clippings_one: '{n} coupure',
  clippings_other: '{n} coupures',
  words_one: '{n} mot',
  words_other: '{n} mots',
  facts_one: '{n} fait',
  facts_other: '{n} faits',
  made_tell_margaux: 'Ce que tu as dit à Margaux',
  second: 'Deuxième Papier',
  show: 'Déplier',
  hide: 'Replier',
  words_label: 'Les mots',
  claims_label: 'Les faits et leurs sources',
  papier_loading: 'Romy rassemble ses notes',
  papier_error: "Le Papier ne répond pas pour le moment. Ta journée est faite ; il t'attend sur La Une.",
  carte_due_one: '1 mot t’attend sur la carte',
  carte_due_other: '{n} mots t’attendent sur la carte',
};

const EN: ReleveCopy = {
  section_title: 'Le Papier',
  clippings_one: '{n} clipping',
  clippings_other: '{n} clippings',
  words_one: '{n} word',
  words_other: '{n} words',
  facts_one: '{n} fact',
  facts_other: '{n} facts',
  made_tell_margaux: 'What you told Margaux',
  second: 'Second Papier',
  show: 'Open',
  hide: 'Close',
  words_label: 'The words',
  claims_label: 'The facts and their sources',
  papier_loading: 'Romy is gathering her notes',
  papier_error: "Le Papier isn't answering right now. Your day is done; it waits for you on La Une.",
  carte_due_one: '1 word is waiting for you on the map',
  carte_due_other: '{n} words are waiting for you on the map',
};

const DE: ReleveCopy = {
  section_title: 'Le Papier',
  clippings_one: '{n} Ausschnitt',
  clippings_other: '{n} Ausschnitte',
  words_one: '{n} Wort',
  words_other: '{n} Wörter',
  facts_one: '{n} Fakt',
  facts_other: '{n} Fakten',
  made_tell_margaux: 'Was du Margaux erzählt hast',
  second: 'Zweites Papier',
  show: 'Aufklappen',
  hide: 'Zuklappen',
  words_label: 'Die Wörter',
  claims_label: 'Die Fakten und ihre Quellen',
  papier_loading: 'Romy sammelt ihre Notizen',
  papier_error: 'Le Papier antwortet gerade nicht. Dein Tag ist geschafft; er wartet auf La Une auf dich.',
  carte_due_one: '1 Wort wartet auf der Karte auf dich',
  carte_due_other: '{n} Wörter warten auf der Karte auf dich',
};

export function releveCopy(language: unknown): ReleveCopy {
  return language === 'en' ? EN : language === 'de' ? DE : FR;
}

export function count(copy: ReleveCopy, stem: 'clippings' | 'words' | 'facts' | 'carte_due', n: number): string {
  const template = n === 1 ? copy[`${stem}_one`] : copy[`${stem}_other`];
  return template.replace('{n}', String(n));
}

