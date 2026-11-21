/**
 * «La photo» and «Le micro» (WIRE §12, 2026-11-21) · the players' chrome, in the learner's
 * control language (mother tongue below B1, French from B1: `plan.ui_language`), as
 * `rubriques-copy.ts`. The reasons (a miss, a refusal that explains, a slip's rule) are read
 * from the mother-tongue table (`glossLanguage`) at every level; the features' names, the
 * steps and what the pages print are French in every table.
 *
 * Sentence case, no exclamation marks in the chrome: Romy and the witness have the voice.
 */

import type { RvLanguage } from '@/lib/revue-types';

import type { ComptoirLine } from '../comptoir/comptoir-copy';

export type PhotoMicroCopy = {
  // «La photo»
  planche_task: string;
  planche_headline: string;
  picture_n: string;
  planche_wrong: string;
  planche_shows: string;
  planche_right: string;
  planche_shown: string;
  seen_task: string;
  seen_elsewhere: string;
  seen_missing: string;
  seen_right: string;
  seen_shown: string;
  legende_task: string;
  role: Record<'right' | 'wrong' | 'other', string>;
  legende_right_picked: string;
  legende_found: string;
  legende_shown: string;
  fix_task_pick: string;
  fix_task_write: string;
  fix_label: string;
  fix_wrong: string;
  fix_right: string;
  fix_shown: string;
  build_task_pick: string;
  build_task_tiles: string;
  build_task_frame: string;
  build_task_free: string;
  build_seen_label: string;
  build_fact_label: string;
  build_label: string;
  build_send: string;
  credit_label: string;
  licence_link: string;
  // «Le micro»
  prepare_task: string;
  prepare_count: string;
  prepare_send: string;
  interview_task_tiles: string;
  interview_task_frame: string;
  interview_task_free: string;
  turns_left: string;
  ask_label: string;
  ask_send: string;
  shrug_free: string;
  shrug_spent: string;
  again: string;
  hole_filled: string;
  frames_label: string;
  notes_task_pick: string;
  notes_task_write: string;
  note_label: string;
  note_wrong: string;
  note_right: string;
  note_shown: string;
  review_task: string;
  review_tiles: string;
  review_send: string;
  hint_inversion: string;
  hint_question_word: string;
  question_n: string;
  errors: Record<string, string>;
};

const FR: PhotoMicroCopy = {
  planche_task: 'Laquelle va avec ce titre ?',
  planche_headline: 'Le titre du jour',
  picture_n: 'Image {n}',
  planche_wrong: 'Pas celle-là.',
  planche_shows: 'Sur cette image, on voit : {things}.',
  planche_right: 'Oui, c’est elle.',
  planche_shown: 'Voici l’image qui va avec le titre.',
  seen_task: 'Qu’est-ce qu’on voit sur cette image ? Touche tout ce qui y est.',
  seen_elsewhere: 'Ça, c’est sur une autre image : {words}.',
  seen_missing: 'Il en manque encore {n}.',
  seen_right: 'Exactement.',
  seen_shown: 'Voici ce qu’on voit sur cette image.',
  legende_task: 'Une de ces légendes contient une erreur. Laquelle ?',
  role: { right: 'Juste', wrong: 'Une erreur', other: 'Une autre image' },
  legende_right_picked: 'Pas celle-là : cette légende est juste.',
  legende_found: 'Bien vu : c’est celle-là.',
  legende_shown: 'Voici la légende avec l’erreur.',
  fix_task_pick: 'Qu’est-ce qui est juste ? Choisis.',
  fix_task_write: 'Réécris la légende pour qu’elle soit juste.',
  fix_label: 'La légende juste',
  fix_wrong: 'Pas encore : relis l’article.',
  fix_right: 'C’est juste.',
  fix_shown: 'La bonne réponse : « {right} ».',
  build_task_pick: 'Choisis une image pour ta légende.',
  build_task_tiles: 'Choisis ce qu’on voit, puis une info.',
  build_task_frame: 'Termine la légende : ce qu’on voit, puis l’info.',
  build_task_free: 'Deux phrases : ce qu’on voit, puis la nouvelle.',
  build_seen_label: 'Ce qu’on voit',
  build_fact_label: 'L’info',
  build_label: 'Ta légende',
  build_send: 'Envoyer ma légende',
  credit_label: 'Crédit',
  licence_link: 'Licence',
  prepare_task: 'Romy a des trous dans ses notes. Choisis les trois questions que tu vas poser.',
  prepare_count: '{n} sur {max}',
  prepare_send: 'Préparer l’interview',
  interview_task_tiles: 'Choisis ta question.',
  interview_task_frame: 'Commence par un début de question, puis termine-la.',
  interview_task_free: 'Écris ta question.',
  turns_left: 'Question {n} sur {max}',
  ask_label: 'Ta question',
  ask_send: 'Poser la question',
  shrug_free: 'Pas de réponse : ta question ne compte pas, essaie autrement.',
  shrug_spent: 'Pas de réponse, et la question compte.',
  again: 'Tu as déjà cette réponse.',
  hole_filled: 'Note remplie : {hole}',
  frames_label: 'Débuts de question',
  notes_task_pick: 'Remplis les notes de Romy avec ce que tu as entendu.',
  notes_task_write: 'Remplis les notes de Romy : écris ce que tu as entendu.',
  note_label: 'Ta note',
  note_wrong: 'Pas encore : relis la réponse.',
  note_right: 'C’est noté.',
  note_shown: 'Dans la réponse : « {value} ».',
  review_task: 'Relis tes questions avant que Romy les imprime.',
  review_tiles: 'Tes questions sont justes.',
  review_send: 'Donner à Romy',
  hint_inversion: 'Question {n} : à l’écrit, après un mot interrogatif, on inverse le sujet ou on dit « est-ce que ».',
  hint_question_word: 'Question {n} : le mot interrogatif ne va pas avec ce que tu voulais savoir.',
  question_n: 'Question {n}',
  errors: {
    too_short: 'Encore un peu : au moins {n} mots.',
    too_long: 'Trop long : {n} mots au plus.',
    not_a_question: 'Pose une question : un mot interrogatif, « est-ce que » ou un point d’interrogation.',
    pick_three: 'Choisis trois questions.',
    keep_questions: 'Garde tes {n} questions, chacune avec son « ? ».',
    two_sentences: 'Deux phrases : ce qu’on voit, puis la nouvelle.',
    name_what_you_see: 'Dis ce qu’on voit sur l’image : un mot de la liste.',
    say_the_news: 'La deuxième phrase donne la nouvelle de l’article.',
    wrong_fact: 'Attention : c’est l’erreur de la légende, pas l’info juste.',
    number_not_in_claims: 'Ce nombre n’est pas dans l’article.',
    nothing_changed: 'Rien n’a changé : regarde les mots soulignés.',
    pick_tiles: 'Choisis ce qu’on voit et une info.',
    pick_picture: 'Choisis une image.',
    pick_words: 'Touche au moins un mot.',
  },
};

const EN: PhotoMicroCopy = {
  planche_task: 'Which one goes with this headline?',
  planche_headline: 'Today’s headline',
  picture_n: 'Picture {n}',
  planche_wrong: 'Not that one.',
  planche_shows: 'This picture shows: {things}.',
  planche_right: 'Yes, that’s the one.',
  planche_shown: 'Here is the picture that goes with the headline.',
  seen_task: 'What can you see in this picture? Tap everything that is in it.',
  seen_elsewhere: 'That is in another picture: {words}.',
  seen_missing: '{n} still missing.',
  seen_right: 'Exactly.',
  seen_shown: 'Here is what this picture shows.',
  legende_task: 'One of these captions has a mistake. Which one?',
  role: { right: 'Correct', wrong: 'A mistake', other: 'Another picture' },
  legende_right_picked: 'Not that one: this caption is correct.',
  legende_found: 'Well spotted: that’s the one.',
  legende_shown: 'Here is the caption with the mistake.',
  fix_task_pick: 'What is right? Pick.',
  fix_task_write: 'Rewrite the caption so that it is right.',
  fix_label: 'The right caption',
  fix_wrong: 'Not yet: read the article again.',
  fix_right: 'That’s right.',
  fix_shown: 'The right answer: “{right}”.',
  build_task_pick: 'Pick a picture for your caption.',
  build_task_tiles: 'Pick what you can see, then a fact.',
  build_task_frame: 'Finish the caption: what you see, then the news.',
  build_task_free: 'Two sentences: what you see, then the news.',
  build_seen_label: 'What you can see',
  build_fact_label: 'The fact',
  build_label: 'Your caption',
  build_send: 'Send my caption',
  credit_label: 'Credit',
  licence_link: 'Licence',
  prepare_task: 'Romy has gaps in her notes. Pick the three questions you will ask.',
  prepare_count: '{n} of {max}',
  prepare_send: 'Prepare the interview',
  interview_task_tiles: 'Pick your question.',
  interview_task_frame: 'Start with a question opener, then finish it.',
  interview_task_free: 'Write your question.',
  turns_left: 'Question {n} of {max}',
  ask_label: 'Your question',
  ask_send: 'Ask',
  shrug_free: 'No answer: this question doesn’t count, try another way.',
  shrug_spent: 'No answer, and the question counts.',
  again: 'You already have that answer.',
  hole_filled: 'Note filled: {hole}',
  frames_label: 'Question openers',
  notes_task_pick: 'Fill in Romy’s notes with what you heard.',
  notes_task_write: 'Fill in Romy’s notes: write what you heard.',
  note_label: 'Your note',
  note_wrong: 'Not yet: read the answer again.',
  note_right: 'Noted.',
  note_shown: 'In the answer: “{value}”.',
  review_task: 'Reread your questions before Romy prints them.',
  review_tiles: 'Your questions are correct.',
  review_send: 'Give them to Romy',
  hint_inversion: 'Question {n}: in writing, after a question word, invert the subject or use “est-ce que”.',
  hint_question_word: 'Question {n}: the question word doesn’t fit what you wanted to know.',
  question_n: 'Question {n}',
  errors: {
    too_short: 'A little more: at least {n} words.',
    too_long: 'Too long: {n} words at most.',
    not_a_question: 'Ask a question: a question word, “est-ce que” or a question mark.',
    pick_three: 'Pick three questions.',
    keep_questions: 'Keep your {n} questions, each with its “?”.',
    two_sentences: 'Two sentences: what you see, then the news.',
    name_what_you_see: 'Say what the picture shows: a word from the list.',
    say_the_news: 'The second sentence gives the article’s news.',
    wrong_fact: 'Careful: that is the caption’s mistake, not the right fact.',
    number_not_in_claims: 'That number is not in the article.',
    nothing_changed: 'Nothing changed: look at the underlined words.',
    pick_tiles: 'Pick what you can see and a fact.',
    pick_picture: 'Pick a picture.',
    pick_words: 'Tap at least one word.',
  },
};

const DE: PhotoMicroCopy = {
  planche_task: 'Welches Bild passt zu dieser Schlagzeile?',
  planche_headline: 'Die Schlagzeile des Tages',
  picture_n: 'Bild {n}',
  planche_wrong: 'Nicht dieses.',
  planche_shows: 'Auf diesem Bild sieht man: {things}.',
  planche_right: 'Ja, das ist es.',
  planche_shown: 'Hier ist das Bild, das zur Schlagzeile passt.',
  seen_task: 'Was sieht man auf diesem Bild? Tippe alles an, was darauf ist.',
  seen_elsewhere: 'Das ist auf einem anderen Bild: {words}.',
  seen_missing: 'Es fehlen noch {n}.',
  seen_right: 'Genau.',
  seen_shown: 'Das sieht man auf diesem Bild.',
  legende_task: 'Eine dieser Bildunterschriften hat einen Fehler. Welche?',
  role: { right: 'Richtig', wrong: 'Ein Fehler', other: 'Ein anderes Bild' },
  legende_right_picked: 'Nicht diese: Diese Bildunterschrift stimmt.',
  legende_found: 'Gut gesehen: Das ist sie.',
  legende_shown: 'Hier ist die Bildunterschrift mit dem Fehler.',
  fix_task_pick: 'Was stimmt? Wähle.',
  fix_task_write: 'Schreib die Bildunterschrift so um, dass sie stimmt.',
  fix_label: 'Die richtige Bildunterschrift',
  fix_wrong: 'Noch nicht: Lies den Artikel noch mal.',
  fix_right: 'Das stimmt.',
  fix_shown: 'Die richtige Antwort: „{right}“.',
  build_task_pick: 'Wähle ein Bild für deine Bildunterschrift.',
  build_task_tiles: 'Wähle, was man sieht, dann eine Info.',
  build_task_frame: 'Beende die Bildunterschrift: was man sieht, dann die Nachricht.',
  build_task_free: 'Zwei Sätze: was man sieht, dann die Nachricht.',
  build_seen_label: 'Was man sieht',
  build_fact_label: 'Die Info',
  build_label: 'Deine Bildunterschrift',
  build_send: 'Meine Bildunterschrift senden',
  credit_label: 'Bildnachweis',
  licence_link: 'Lizenz',
  prepare_task: 'Romy hat Lücken in ihren Notizen. Wähle die drei Fragen, die du stellst.',
  prepare_count: '{n} von {max}',
  prepare_send: 'Interview vorbereiten',
  interview_task_tiles: 'Wähle deine Frage.',
  interview_task_frame: 'Fang mit einem Fragebeginn an und beende die Frage.',
  interview_task_free: 'Schreib deine Frage.',
  turns_left: 'Frage {n} von {max}',
  ask_label: 'Deine Frage',
  ask_send: 'Frage stellen',
  shrug_free: 'Keine Antwort: Diese Frage zählt nicht, versuch es anders.',
  shrug_spent: 'Keine Antwort, und die Frage zählt.',
  again: 'Diese Antwort hast du schon.',
  hole_filled: 'Notiz ergänzt: {hole}',
  frames_label: 'Fragebeginne',
  notes_task_pick: 'Ergänze Romys Notizen mit dem, was du gehört hast.',
  notes_task_write: 'Ergänze Romys Notizen: Schreib, was du gehört hast.',
  note_label: 'Deine Notiz',
  note_wrong: 'Noch nicht: Lies die Antwort noch mal.',
  note_right: 'Notiert.',
  note_shown: 'In der Antwort: „{value}“.',
  review_task: 'Lies deine Fragen noch mal, bevor Romy sie druckt.',
  review_tiles: 'Deine Fragen sind richtig.',
  review_send: 'Romy geben',
  hint_inversion: 'Frage {n}: Schriftlich stellt man nach einem Fragewort das Subjekt um oder sagt „est-ce que“.',
  hint_question_word: 'Frage {n}: Das Fragewort passt nicht zu dem, was du wissen wolltest.',
  question_n: 'Frage {n}',
  errors: {
    too_short: 'Noch ein bisschen: mindestens {n} Wörter.',
    too_long: 'Zu lang: höchstens {n} Wörter.',
    not_a_question: 'Stell eine Frage: ein Fragewort, „est-ce que“ oder ein Fragezeichen.',
    pick_three: 'Wähle drei Fragen.',
    keep_questions: 'Behalte deine {n} Fragen, jede mit ihrem „?“.',
    two_sentences: 'Zwei Sätze: was man sieht, dann die Nachricht.',
    name_what_you_see: 'Sag, was man auf dem Bild sieht: ein Wort aus der Liste.',
    say_the_news: 'Der zweite Satz gibt die Nachricht des Artikels.',
    wrong_fact: 'Achtung: Das ist der Fehler der Bildunterschrift, nicht die richtige Info.',
    number_not_in_claims: 'Diese Zahl steht nicht im Artikel.',
    nothing_changed: 'Nichts hat sich geändert: Schau dir die unterstrichenen Wörter an.',
    pick_tiles: 'Wähle, was man sieht, und eine Info.',
    pick_picture: 'Wähle ein Bild.',
    pick_words: 'Tippe auf mindestens ein Wort.',
  },
};

const TABLES: Record<RvLanguage, PhotoMicroCopy> = { fr: FR, en: EN, de: DE };

export function photoMicroCopy(language: RvLanguage | string | null | undefined): PhotoMicroCopy {
  return TABLES[(language as RvLanguage) in TABLES ? (language as RvLanguage) : 'fr'];
}

/** The refusals that explain: said from the mother-tongue table, at every level. */
export const PM_REASON_CODES = new Set([
  'not_a_question',
  'keep_questions',
  'two_sentences',
  'name_what_you_see',
  'say_the_news',
  'wrong_fact',
  'number_not_in_claims',
  'nothing_changed',
]);

/** The features' French, the same in every chrome. */
export const PHOTO_FR = {
  name: 'La photo',
  press: 'À la planche',
  page_kicker: 'La photo de Romy',
  byline: 'Romy Tremblay, avec toi',
} as const;

export const MICRO_FR = {
  name: 'Le micro',
  press: 'Préparer l’interview',
  page_kicker: 'L’interview',
  notes: 'Les notes de Romy',
  q: 'Q.',
  a: 'R.',
  shrug: '…',
} as const;

/** The dots' names. */
export const PHOTO_STEP_LABELS_FR: Record<string, string> = {
  read: 'Lire',
  planche: 'La planche',
  legende: 'La légende',
  build: 'À toi',
  page: 'La page',
};
export const MICRO_STEP_LABELS_FR: Record<string, string> = {
  read: 'Lire',
  prepare: 'Prépare tes questions',
  interview: 'L’interview',
  notes: 'Tes notes',
  review: 'Relis tes questions',
  page: 'La page',
};

/** Romy's authored lines, French with their translations. */
export const PM_LINES: Record<
  'planche_ask' | 'seen_ask' | 'legende_ask' | 'fix_ask' | 'build_ask' | 'prepare_ask' | 'interview_ask' | 'notes_ask' | 'review_ask',
  ComptoirLine
> = {
  planche_ask: {
    fr: 'J’ai plusieurs images pour l’article. Laquelle va avec le titre ?',
    en: 'I have several pictures for the article. Which one goes with the headline?',
    de: 'Ich habe mehrere Bilder für den Artikel. Welches passt zur Schlagzeile?',
  },
  seen_ask: {
    fr: 'Bien. Qu’est-ce qu’on voit dessus ?',
    en: 'Good. What can we see in it?',
    de: 'Gut. Was sieht man darauf?',
  },
  legende_ask: {
    fr: 'Trois légendes pour cette image. Une contient une erreur. Trouve-la.',
    en: 'Three captions for this picture. One has a mistake. Find it.',
    de: 'Drei Bildunterschriften für dieses Bild. Eine hat einen Fehler. Finde sie.',
  },
  fix_ask: {
    fr: 'Qu’est-ce qui est faux dans cette légende ?',
    en: 'What is wrong in this caption?',
    de: 'Was ist an dieser Bildunterschrift falsch?',
  },
  build_ask: {
    fr: 'À toi : choisis une image et écris sa légende.',
    en: 'Your turn: pick a picture and write its caption.',
    de: 'Du bist dran: Wähle ein Bild und schreib die Bildunterschrift.',
  },
  prepare_ask: {
    fr: 'Il me manque des infos. Tu vas interviewer quelqu’un qui était là.',
    en: 'I’m missing some facts. You’re going to interview someone who was there.',
    de: 'Mir fehlen ein paar Infos. Du interviewst jemanden, der dabei war.',
  },
  interview_ask: {
    fr: 'Le micro est à toi. Une question à la fois.',
    en: 'The microphone is yours. One question at a time.',
    de: 'Das Mikro gehört dir. Eine Frage nach der anderen.',
  },
  notes_ask: {
    fr: 'Super. Maintenant, on remplit mes notes.',
    en: 'Great. Now let’s fill in my notes.',
    de: 'Super. Jetzt füllen wir meine Notizen aus.',
  },
  review_ask: {
    fr: 'Avant d’imprimer, relis tes questions.',
    en: 'Before we print, reread your questions.',
    de: 'Bevor wir drucken, lies deine Fragen noch mal.',
  },
};
