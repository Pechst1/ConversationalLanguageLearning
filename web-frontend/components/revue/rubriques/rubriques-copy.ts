/**
 * «Le titre» and «L'intox express» (WIRE §11, 2026-11-20) · the players' chrome, in the
 * learner's control language (mother tongue below B1, French from B1: `plan.ui_language`),
 * like `fil-copy.ts`; the comptoir's shared words (the step label, «Voir la page», the marks'
 * kinds, «Corrige-le, Romy») are reused from `comptoir-copy.ts`.
 *
 * French in every table: the features' names and steps, what the pages print, the «Vrai» /
 * «Faux» buttons (the words the learner is learning, glossed in `aria-label`), and Romy's
 * authored lines (French with their translations, so «Traduire» needs no request).
 *
 * Sentence case, no exclamation marks in the chrome: Romy has the voice.
 */

import type { RvLanguage } from '@/lib/revue-types';

import type { ComptoirLine } from '../comptoir/comptoir-copy';

export type RubriqueCopy = {
  try_n: string;
  check: string;
  // «Le titre»
  three_task: string;
  three_proposes: string;
  three_wrong: string;
  three_right: string;
  three_shown: string;
  role: Record<'honest' | 'exaggerated' | 'off', string>;
  the_article: string;
  trap_task: string;
  trap_fine: string;
  trap_right: string;
  trap_shown: string;
  build_task_tiles: string;
  build_task_frame: string;
  build_task_free: string;
  build_avoid: string;
  subject_label: string;
  fact_label: string;
  build_send: string;
  build_label: string;
  words_count: string;
  // «L'intox express»
  round_task: string;
  reread: string;
  reread_hide: string;
  vrai: string;
  faux: string;
  score: string;
  verdict_right: string;
  verdict_wrong: string;
  was_true: string;
  was_false: string;
  wrong_words: string;
  next_statement: string;
  fix_task_pick: string;
  fix_task_write: string;
  fix_label: string;
  fix_wrong: string;
  fix_right: string;
  fix_shown: string;
  errors: Record<string, string>;
};

const FR: RubriqueCopy = {
  try_n: 'Essai {n} sur {max}',
  check: 'Vérifier',
  three_task: "Choisis le titre honnête : celui qui dit ce que dit l'article, pas plus.",
  three_proposes: '{name} propose trois titres.',
  three_wrong: "Pas celui-là. Ce titre dit ce que l'article ne dit pas :",
  three_right: "C'est le titre honnête.",
  three_shown: 'Voici le titre honnête.',
  role: { honest: 'Honnête', exaggerated: 'Il en dit trop', off: 'À côté de la nouvelle' },
  the_article: "L'article",
  trap_task: 'Touche le mot ou les mots qui en disent trop.',
  trap_fine: "Ces mots-là, l'article les dit : {words}.",
  trap_right: 'Exactement : ces mots en disent trop.',
  trap_shown: 'Voici les mots qui en disent trop.',
  build_task_tiles: 'Fais ton titre : un sujet, puis ce qui se passe.',
  build_task_frame: 'Termine le titre.',
  build_task_free: 'Écris ton titre : {n} mots au plus.',
  build_avoid: 'Sans « {avoid} »',
  subject_label: 'Le sujet',
  fact_label: 'Ce qui se passe',
  build_send: 'Envoyer mon titre',
  build_label: 'Ton titre',
  words_count: '{n} mots sur {max}',
  round_task: "Vrai ou faux ? Tu peux relire l'article quand tu veux.",
  reread: "Relire l'article",
  reread_hide: "Fermer l'article",
  vrai: 'vrai',
  faux: 'faux',
  score: '{n} sur {total}',
  verdict_right: 'Bonne réponse.',
  verdict_wrong: 'Pas tout à fait.',
  was_true: "C'est vrai.",
  was_false: "C'est faux.",
  wrong_words: 'Ce qui est faux : « {words} »',
  next_statement: 'Phrase suivante',
  fix_task_pick: 'Rends la phrase vraie : choisis les bons mots.',
  fix_task_write: 'Réécris la phrase pour qu’elle soit vraie.',
  fix_label: 'La phrase vraie',
  fix_wrong: 'Pas encore : relis la citation.',
  fix_right: "C'est juste.",
  fix_shown: 'La bonne réponse : « {right} ».',
  errors: {
    too_short: 'Encore un peu : au moins {n} mots.',
    too_long: 'Trop long pour un titre : {n} mots au plus.',
    says_too_much: 'Ton titre en dit trop, comme celui de Gus. Enlève ces mots.',
    number_not_in_claims: "Ce nombre n'est pas dans l'article.",
    nothing_changed: "Rien n'a changé : regarde les mots soulignés.",
    pick_tiles: 'Choisis un sujet et ce qui se passe.',
    pick_words: 'Touche au moins un mot.',
  },
};

const EN: RubriqueCopy = {
  try_n: 'Try {n} of {max}',
  check: 'Check',
  three_task: 'Pick the honest headline: the one that says what the article says, no more.',
  three_proposes: '{name} suggests three headlines.',
  three_wrong: "Not this one. This headline says something the article doesn't:",
  three_right: "That's the honest headline.",
  three_shown: 'Here is the honest headline.',
  role: { honest: 'Honest', exaggerated: 'Says too much', off: 'Misses the news' },
  the_article: 'The article',
  trap_task: 'Tap the word or words that say too much.',
  trap_fine: 'The article does say these: {words}.',
  trap_right: 'Exactly: these words say too much.',
  trap_shown: 'These are the words that say too much.',
  build_task_tiles: 'Build your headline: a subject, then what happens.',
  build_task_frame: 'Finish the headline.',
  build_task_free: 'Write your headline: {n} words at most.',
  build_avoid: 'Without “{avoid}”',
  subject_label: 'The subject',
  fact_label: 'What happens',
  build_send: 'Send my headline',
  build_label: 'Your headline',
  words_count: '{n} of {max} words',
  round_task: 'True or false? You can reread the article whenever you like.',
  reread: 'Reread the article',
  reread_hide: 'Close the article',
  vrai: 'true',
  faux: 'false',
  score: '{n} of {total}',
  verdict_right: 'Right answer.',
  verdict_wrong: 'Not quite.',
  was_true: "It's true.",
  was_false: "It's false.",
  wrong_words: 'What is false: “{words}”',
  next_statement: 'Next statement',
  fix_task_pick: 'Make it true: pick the right words.',
  fix_task_write: 'Rewrite the statement so that it is true.',
  fix_label: 'The true statement',
  fix_wrong: 'Not yet: read the quote again.',
  fix_right: "That's right.",
  fix_shown: 'The right answer: “{right}”.',
  errors: {
    too_short: 'A little more: at least {n} words.',
    too_long: 'Too long for a headline: {n} words at most.',
    says_too_much: 'Your headline says too much, like Gus’s. Take those words out.',
    number_not_in_claims: 'That number is not in the article.',
    nothing_changed: 'Nothing changed: look at the underlined words.',
    pick_tiles: 'Pick a subject and what happens.',
    pick_words: 'Tap at least one word.',
  },
};

const DE: RubriqueCopy = {
  try_n: 'Versuch {n} von {max}',
  check: 'Prüfen',
  three_task: 'Wähle die ehrliche Schlagzeile: die, die sagt, was der Artikel sagt, nicht mehr.',
  three_proposes: '{name} schlägt drei Schlagzeilen vor.',
  three_wrong: 'Nicht diese. Diese Schlagzeile sagt etwas, das der Artikel nicht sagt:',
  three_right: 'Das ist die ehrliche Schlagzeile.',
  three_shown: 'Hier ist die ehrliche Schlagzeile.',
  role: { honest: 'Ehrlich', exaggerated: 'Sagt zu viel', off: 'Verfehlt die Nachricht' },
  the_article: 'Der Artikel',
  trap_task: 'Tippe auf das Wort oder die Wörter, die zu viel sagen.',
  trap_fine: 'Das sagt der Artikel wirklich: {words}.',
  trap_right: 'Genau: Diese Wörter sagen zu viel.',
  trap_shown: 'Das sind die Wörter, die zu viel sagen.',
  build_task_tiles: 'Bau deine Schlagzeile: ein Subjekt, dann was passiert.',
  build_task_frame: 'Beende die Schlagzeile.',
  build_task_free: 'Schreib deine Schlagzeile: höchstens {n} Wörter.',
  build_avoid: 'Ohne „{avoid}“',
  subject_label: 'Das Subjekt',
  fact_label: 'Was passiert',
  build_send: 'Meine Schlagzeile senden',
  build_label: 'Deine Schlagzeile',
  words_count: '{n} von {max} Wörtern',
  round_task: 'Richtig oder falsch? Du kannst den Artikel jederzeit noch mal lesen.',
  reread: 'Artikel noch mal lesen',
  reread_hide: 'Artikel schließen',
  vrai: 'richtig',
  faux: 'falsch',
  score: '{n} von {total}',
  verdict_right: 'Richtige Antwort.',
  verdict_wrong: 'Nicht ganz.',
  was_true: 'Das stimmt.',
  was_false: 'Das stimmt nicht.',
  wrong_words: 'Was falsch ist: „{words}“',
  next_statement: 'Nächster Satz',
  fix_task_pick: 'Mach den Satz wahr: Wähle die richtigen Wörter.',
  fix_task_write: 'Schreib den Satz so um, dass er stimmt.',
  fix_label: 'Der wahre Satz',
  fix_wrong: 'Noch nicht: Lies das Zitat noch mal.',
  fix_right: 'Das stimmt.',
  fix_shown: 'Die richtige Antwort: „{right}“.',
  errors: {
    too_short: 'Noch ein bisschen: mindestens {n} Wörter.',
    too_long: 'Zu lang für eine Schlagzeile: höchstens {n} Wörter.',
    says_too_much: 'Deine Schlagzeile sagt zu viel, wie die von Gus. Nimm diese Wörter heraus.',
    number_not_in_claims: 'Diese Zahl steht nicht im Artikel.',
    nothing_changed: 'Nichts hat sich geändert: Schau dir die unterstrichenen Wörter an.',
    pick_tiles: 'Wähle ein Subjekt und was passiert.',
    pick_words: 'Tippe auf mindestens ein Wort.',
  },
};

const TABLES: Record<RvLanguage, RubriqueCopy> = { fr: FR, en: EN, de: DE };

export function rubriqueCopy(language: RvLanguage | string | null | undefined): RubriqueCopy {
  return TABLES[(language as RvLanguage) in TABLES ? (language as RvLanguage) : 'fr'];
}

/** The features' French, the same in every chrome. */
export const TITRE_FR = {
  name: 'Le titre',
  press: 'Aux titres',
  page_kicker: 'Le titre de Romy',
  byline: 'Romy Tremblay, avec toi',
  honest: 'Le titre honnête',
} as const;

export const INTOX_FR = {
  name: "L'intox express",
  press: 'Vrai ou faux',
  page_kicker: "L'intox express de Romy",
  vrai: 'Vrai',
  faux: 'Faux',
  score: '{n} sur {total}',
  fixed: 'Corrigé par toi',
  you: 'Toi',
  was: 'On disait',
} as const;

/** The dots' names (only spoken by the dots' label). */
export const TITRE_STEP_LABELS_FR: Record<string, string> = {
  read: 'Lire',
  three: 'Trois titres',
  trap: 'Le piège',
  build: 'À toi',
  page: 'La page',
};
export const INTOX_STEP_LABELS_FR: Record<string, string> = {
  read: 'Lire',
  round: 'Vrai ou faux',
  fix: 'Corrige',
  page: 'La page',
};

/** Romy's authored lines on the client, French with their translations. */
export const RUBRIQUE_LINES: Record<'three_ask' | 'trap_ask' | 'build_ask' | 'round_ask' | 'fix_ask', ComptoirLine> = {
  three_ask: {
    fr: 'Gus a encore trois idées de titres. Un seul est honnête. Lequel ?',
    en: 'Gus has three headline ideas again. Only one is honest. Which one?',
    de: 'Gus hat wieder drei Ideen für Schlagzeilen. Nur eine ist ehrlich. Welche?',
  },
  trap_ask: {
    fr: 'Et ce titre-là, qu’est-ce qui cloche ? Montre-moi les mots.',
    en: "And this headline, what's wrong with it? Show me the words.",
    de: 'Und diese Schlagzeile, was stimmt da nicht? Zeig mir die Wörter.',
  },
  build_ask: {
    fr: 'À toi : un titre qui dit vrai.',
    en: 'Your turn: a headline that tells the truth.',
    de: 'Du bist dran: eine Schlagzeile, die die Wahrheit sagt.',
  },
  round_ask: {
    fr: 'Cinq phrases sur l’article. Vrai ou faux ?',
    en: 'Five statements about the article. True or false?',
    de: 'Fünf Sätze über den Artikel. Richtig oder falsch?',
  },
  fix_ask: {
    fr: 'Deux intox. Corrige-les pour le journal.',
    en: 'Two fakes. Correct them for the paper.',
    de: 'Zwei Falschmeldungen. Korrigiere sie für die Zeitung.',
  },
};
