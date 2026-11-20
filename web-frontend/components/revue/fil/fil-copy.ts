/**
 * «Le fil» (WIRE §10, owner 2026-11-20) · the player's chrome, in the learner's
 * control language (mother tongue below B1, French from B1: `plan.ui_language`), like
 * `comptoir-copy.ts`, whose shared words (the step label, «Voir la page», the marks'
 * kinds, «Corrige-le, Romy») the player reuses.
 *
 * French in every table: the feature's name and its steps, what the page prints
 * («Le fil de Romy», «Toi»), and Romy's authored lines (French with their
 * translations, `FIL_LINES`, so «Traduire» needs no request).
 *
 * Sentence case, no exclamation marks in the chrome: Romy has the voice.
 */

import type { RvLanguage } from '@/lib/revue-types';

import type { ComptoirLine } from '../comptoir/comptoir-copy';

export type FilCopy = {
  order_task: string;
  move_up: string;
  move_down: string;
  order_check: string;
  /** «{a} comes after {b}.»: the first strip out of place, by the strips' own names. */
  order_hint: string;
  order_right: string;
  order_shown: string;
  /** «Try 1 of 2». */
  try_n: string;
  words_task_place: string;
  words_task_choose: string;
  words_check: string;
  slot_empty: string;
  /** What a sequence word does, by where it fits. */
  role: Record<'first' | 'middle' | 'last', string>;
  /** The same, as it reads after «a word that…» (German puts the verb last). */
  needs: Record<'first' | 'middle' | 'last', string>;
  /** ««enfin» means “finally”: it closes the story. This dispatch needs a word that opens it.» */
  miss: string;
  miss_no_gloss: string;
  words_right: string;
  words_shown: string;
  tell_task_tiles: string;
  tell_task_frames: string;
  tell_task_free: string;
  sentence_n: string;
  word_label: string;
  event_label: string;
  tell_send: string;
  tell_placeholder: string;
  /** B1+: «2 of 2 sequence words». */
  connectors_count: string;
  errors: Record<string, string>;
};

const FR: FilCopy = {
  order_task: "Remets les dépêches dans l'ordre : touche une dépêche puis une autre pour les échanger, ou utilise les flèches.",
  move_up: 'Monter',
  move_down: 'Descendre',
  order_check: "Vérifier l'ordre",
  order_hint: '{a} vient après {b}.',
  order_right: "C'est le bon ordre.",
  order_shown: "Voici le bon ordre.",
  try_n: 'Essai {n} sur {max}',
  words_task_place: 'Mets un mot sur chaque dépêche : touche une dépêche, puis un mot.',
  words_task_choose: 'Choisis le mot qui va avec chaque dépêche.',
  words_check: 'Vérifier les mots',
  slot_empty: 'un mot ?',
  role: { first: "ouvre l'histoire", middle: "relie le milieu de l'histoire", last: "ferme l'histoire" },
  needs: { first: "ouvre l'histoire", middle: "relie le milieu de l'histoire", last: "ferme l'histoire" },
  miss: '« {word} » veut dire « {gloss} » : ce mot {role}. Ici, il faut un mot qui {needs}.',
  miss_no_gloss: '« {word} » {role}. Ici, il faut un mot qui {needs}.',
  words_right: 'Ce sont les bons mots.',
  words_shown: 'Voici les bons mots.',
  tell_task_tiles: 'Fais deux phrases : à chaque fois, un mot puis ce qui s’est passé.',
  tell_task_frames: 'Termine les deux phrases.',
  tell_task_free: 'Raconte l’histoire en deux phrases, avec au moins {n} de ces mots.',
  sentence_n: 'Phrase {n}',
  word_label: 'Le mot',
  event_label: 'Ce qui s’est passé',
  tell_send: 'Raconter',
  tell_placeholder: 'Tout d’abord…',
  connectors_count: '{n} mot(s) du fil sur {min}',
  errors: {
    tell_order: '{a} vient après {b} : échange-les.',
    tell_same: 'Choisis deux moments différents.',
    tell_last_first: '« {word} » ferme une histoire : il ne peut pas l’ouvrir.',
    tell_starts_middle: '« {word} » relie le milieu : commence avec un mot qui ouvre l’histoire.',
    tell_first_second: '« {word} » ouvre une histoire : ta deuxième phrase a besoin d’un autre mot.',
    tell_pick_all: 'Choisis un mot et un moment pour chaque phrase.',
    pick_all: 'Mets un mot sur chaque dépêche.',
    too_short: 'Encore un peu : au moins {n} mots.',
    need_connectors: 'Utilise au moins {n} mots du fil.',
    nothing_changed: 'Rien n’a changé : regarde les mots soulignés.',
  },
};

const EN: FilCopy = {
  order_task: 'Put the dispatches back in order: tap one dispatch, then another, to swap them, or use the arrows.',
  move_up: 'Move up',
  move_down: 'Move down',
  order_check: 'Check the order',
  order_hint: '{a} comes after {b}.',
  order_right: "That's the right order.",
  order_shown: 'Here is the right order.',
  try_n: 'Try {n} of {max}',
  words_task_place: 'Put a word on each dispatch: tap a dispatch, then a word.',
  words_task_choose: 'Pick the word that fits each dispatch.',
  words_check: 'Check the words',
  slot_empty: 'a word?',
  role: { first: 'opens the story', middle: 'links the middle of the story', last: 'closes the story' },
  needs: { first: 'opens the story', middle: 'links the middle of the story', last: 'closes the story' },
  miss: '«{word}» means “{gloss}”: it {role}. This dispatch needs a word that {needs}.',
  miss_no_gloss: '«{word}» {role}. This dispatch needs a word that {needs}.',
  words_right: 'Those are the right words.',
  words_shown: 'Here are the right words.',
  tell_task_tiles: 'Build two sentences: each time, a word, then what happened.',
  tell_task_frames: 'Finish the two sentences.',
  tell_task_free: 'Tell the story in two sentences, with at least {n} of these words.',
  sentence_n: 'Sentence {n}',
  word_label: 'The word',
  event_label: 'What happened',
  tell_send: 'Send my story',
  tell_placeholder: 'Tout d’abord…',
  connectors_count: '{n} of {min} sequence words',
  errors: {
    tell_order: '{a} comes after {b}: swap them.',
    tell_same: 'Pick two different moments.',
    tell_last_first: '«{word}» closes a story: it can’t open yours.',
    tell_starts_middle: '«{word}» links the middle: start with a word that opens the story.',
    tell_first_second: '«{word}» opens a story: your second sentence needs another word.',
    tell_pick_all: 'Pick a word and a moment for each sentence.',
    pick_all: 'Put a word on each dispatch.',
    too_short: 'A little more: at least {n} words.',
    need_connectors: 'Use at least {n} sequence words.',
    nothing_changed: 'Nothing changed: look at the underlined words.',
  },
};

const DE: FilCopy = {
  order_task: 'Bring die Meldungen wieder in die richtige Reihenfolge: Tippe eine Meldung und dann eine andere, um sie zu tauschen, oder nutze die Pfeile.',
  move_up: 'Nach oben',
  move_down: 'Nach unten',
  order_check: 'Reihenfolge prüfen',
  order_hint: 'Erst {b}, dann {a}.',
  order_right: 'Das ist die richtige Reihenfolge.',
  order_shown: 'Hier ist die richtige Reihenfolge.',
  try_n: 'Versuch {n} von {max}',
  words_task_place: 'Setze ein Wort auf jede Meldung: Tippe eine Meldung, dann ein Wort.',
  words_task_choose: 'Wähle das Wort, das zu jeder Meldung passt.',
  words_check: 'Wörter prüfen',
  slot_empty: 'ein Wort?',
  role: { first: 'eröffnet die Geschichte', middle: 'verbindet die Mitte der Geschichte', last: 'schließt die Geschichte ab' },
  needs: { first: 'die Geschichte eröffnet', middle: 'die Mitte der Geschichte verbindet', last: 'die Geschichte abschließt' },
  miss: '«{word}» heißt „{gloss}“: Es {role}. Diese Meldung braucht ein Wort, das {needs}.',
  miss_no_gloss: '«{word}» {role}. Diese Meldung braucht ein Wort, das {needs}.',
  words_right: 'Das sind die richtigen Wörter.',
  words_shown: 'Hier sind die richtigen Wörter.',
  tell_task_tiles: 'Bilde zwei Sätze: jedes Mal ein Wort, dann was passiert ist.',
  tell_task_frames: 'Beende die zwei Sätze.',
  tell_task_free: 'Erzähl die Geschichte in zwei Sätzen, mit mindestens {n} dieser Wörter.',
  sentence_n: 'Satz {n}',
  word_label: 'Das Wort',
  event_label: 'Was passiert ist',
  tell_send: 'Meine Geschichte senden',
  tell_placeholder: 'Tout d’abord…',
  connectors_count: '{n} von {min} Verbindungswörtern',
  errors: {
    tell_order: '{a} kommt nach {b}: Tausche sie.',
    tell_same: 'Wähle zwei verschiedene Momente.',
    tell_last_first: '«{word}» schließt eine Geschichte ab: Es kann deine nicht eröffnen.',
    tell_starts_middle: '«{word}» verbindet die Mitte: Beginne mit einem Wort, das die Geschichte eröffnet.',
    tell_first_second: '«{word}» eröffnet eine Geschichte: Dein zweiter Satz braucht ein anderes Wort.',
    tell_pick_all: 'Wähle für jeden Satz ein Wort und einen Moment.',
    pick_all: 'Setze ein Wort auf jede Meldung.',
    too_short: 'Noch ein bisschen: mindestens {n} Wörter.',
    need_connectors: 'Verwende mindestens {n} Verbindungswörter.',
    nothing_changed: 'Nichts hat sich geändert: Schau dir die unterstrichenen Wörter an.',
  },
};

const TABLES: Record<RvLanguage, FilCopy> = { fr: FR, en: EN, de: DE };

export function filCopy(language: RvLanguage | string | null | undefined): FilCopy {
  return TABLES[(language as RvLanguage) in TABLES ? (language as RvLanguage) : 'fr'];
}

/** The feature's French, the same in every chrome. */
export const FIL_FR = {
  name: 'Le fil',
  /** «Lire»'s press. */
  press: 'Au fil',
  page_kicker: 'Le fil de Romy',
  you: 'Toi',
  tell_label: 'Ton récit',
} as const;

/** The dots' names (only spoken by the dots' label). */
export const FIL_STEP_LABELS_FR: Record<string, string> = {
  read: 'Lire',
  order: 'Remettre en ordre',
  words: 'Les mots du fil',
  tell: 'Raconter',
  page: 'La page',
};

/** Romy's authored lines on the client, French with their translations. */
export const FIL_LINES: Record<'order_ask' | 'words_ask' | 'tell_ask', ComptoirLine> = {
  order_ask: {
    fr: 'Les dépêches sont tombées dans le désordre. Tu peux les remettre dans l’ordre ?',
    en: 'The dispatches came in out of order. Can you put them back in order?',
    de: 'Die Meldungen sind durcheinander gekommen. Kannst du sie wieder ordnen?',
  },
  words_ask: {
    fr: 'Maintenant, les petits mots qui tiennent le fil.',
    en: 'Now, the little words that hold the wire together.',
    de: 'Jetzt die kleinen Wörter, die den Faden zusammenhalten.',
  },
  tell_ask: {
    fr: 'À toi : raconte-moi l’histoire en deux phrases.',
    en: 'Your turn: tell me the story in two sentences.',
    de: 'Du bist dran: Erzähl mir die Geschichte in zwei Sätzen.',
  },
};
