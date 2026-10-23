/**
 * «Au comptoir» (WP-119-AU-COMPTOIR §5) · the player's chrome, in the learner's
 * control language (WP-82 one-language rule), like `revue-copy.ts` — whose
 * shared words (Traduire, Continuer, Classer le Papier, the × label) it reuses.
 *
 * French in every table: what the learner says (Oui ! · d'accord · Pour), what
 * the page prints (POUR · CONTRE · ÇA DÉPEND, «La question du jour», «Dans le
 * journal · corrigé par toi», «L'intox du jour», «Le micro-trottoir de Romy»)
 * and the feature's own name, «Au comptoir». Romy's authored lines are French
 * with their translations (`COMPTOIR_LINES`), so «Traduire» needs no request.
 *
 * Sentence case, no exclamation marks, no personality: Romy has the voice.
 */

import type { RvComptoirMarkKind, RvComptoirProof, RvLanguage } from '@/lib/revue-types';

export type ComptoirCopy = {
  steps_label: string;
  step_value: string;
  give_opinion: string;
  see_page: string;
  /** Under «Lire»'s press until the gut vote is in. */
  read_hint: string;
  takes_hint: string;
  takes_hint_intox: string;
  react_hint: string;
  listen: string;
  intox_pick_hint: string;
  intox_not_this: string;
  intox_fix_label: string;
  intox_fix_placeholder: string;
  /** Under the learner's own typed line (B1, word for word the right one). */
  intox_your_line: string;
  /** Under the right line when the learner picked it or Romy says it (2026-10-23 copy honesty). */
  intox_right_line: string;
  intox_wrong_answer: string;
  side_label: string;
  a1_reason_label: string;
  a1_pick_hint: string;
  phrase_label: string;
  bank_label: string;
  reason_label: string;
  reason_placeholder: string;
  answer_to: string;
  opinion_placeholder: string;
  write_hint: string;
  /** Romy's marks (2026-10-23): the kind of slip under each mark, never the answer. */
  mark_kinds: Record<RvComptoirMarkKind, string>;
  fix_label: string;
  fix_placeholder: string;
  fix_send: string;
  /** «Essai 1 sur 2». */
  fix_try: string;
  /** After one try: Romy corrects what is left. */
  fix_romy: string;
  your_reply: string;
  reply_label: string;
  reply_placeholder: string;
  act_failed: string;
  page_words: string;
  vote_aria: string;
};

const FR: ComptoirCopy = {
  steps_label: 'Les étapes',
  step_value: '{n} sur {total} · {name}',
  give_opinion: 'Donner mon avis',
  see_page: 'Voir la page',
  read_hint: 'Réponds à la question pour aller au comptoir.',
  takes_hint: '{n} avis',
  takes_hint_intox: '{n} avis · 1 intox cachée',
  react_hint: 'D’accord ou pas ? Réagis à chacun.',
  listen: 'Écouter',
  intox_pick_hint: 'Touche la phrase fausse.',
  intox_not_this: 'pas celle-ci',
  intox_fix_label: 'Écris ta correction',
  intox_fix_placeholder: 'C’est faux, c’est…, pas…',
  intox_your_line: 'Ta réplique. Nouvelle tournure : « C’est faux, c’est…, pas… »',
  intox_right_line: 'La bonne réplique. Nouvelle tournure : « C’est faux, c’est…, pas… »',
  intox_wrong_answer: 'Pas tout à fait : la bonne réponse, c’est « {right} ».',
  side_label: 'Ton camp',
  a1_reason_label: 'Pourquoi ?',
  a1_pick_hint: 'Choisis une raison.',
  phrase_label: 'Phrase du jour',
  bank_label: 'Des mots pour t’aider',
  reason_label: 'Ta raison',
  reason_placeholder: 'ta raison, en français',
  answer_to: 'Réponds à {name}',
  opinion_placeholder: 'Ton avis, en français',
  write_hint: 'Écris ou dis ta raison.',
  mark_kinds: {
    accord: 'accord',
    conjugaison: 'conjugaison',
    genre: 'genre',
    orthographe: 'orthographe',
    mot: 'mot',
    ordre: 'ordre des mots',
    manque: 'il manque un mot',
  },
  fix_label: 'Corrige ta phrase',
  fix_placeholder: 'Ta phrase corrigée…',
  fix_send: 'Renvoyer',
  fix_try: 'Essai {n} sur {max}',
  fix_romy: 'Corrige-le, Romy',
  your_reply: 'Ta réponse',
  reply_label: 'Ta réponse, en une phrase',
  reply_placeholder: 'Ta réponse…',
  act_failed: 'Ça n’est pas passé. Réessaie.',
  page_words: 'Tes mots',
  vote_aria: 'Le vote : {pour} pour, {nuance} ça dépend, {contre} contre',
};

const EN: ComptoirCopy = {
  steps_label: 'Steps',
  step_value: '{n} of {total} · {name}',
  give_opinion: 'Give my opinion',
  see_page: 'See the page',
  read_hint: 'Answer the question to go to the counter.',
  takes_hint: '{n} opinions',
  takes_hint_intox: '{n} opinions · 1 false claim hidden',
  react_hint: 'Agree or not? React to each one.',
  listen: 'Listen',
  intox_pick_hint: 'Tap the false sentence.',
  intox_not_this: 'not this one',
  intox_fix_label: 'Write your correction',
  intox_fix_placeholder: 'C’est faux, c’est…, pas…',
  intox_your_line: 'Your line. New phrase: «C’est faux, c’est…, pas…»',
  intox_right_line: 'The right line. New phrase: «C’est faux, c’est…, pas…»',
  intox_wrong_answer: 'Not quite: the right answer is «{right}».',
  side_label: 'Your side',
  a1_reason_label: 'Why?',
  a1_pick_hint: 'Pick a reason.',
  phrase_label: 'Phrase of the day',
  bank_label: 'Words to help you',
  reason_label: 'Your reason',
  reason_placeholder: 'your reason, in French',
  answer_to: 'Answer {name}',
  opinion_placeholder: 'Your opinion, in French',
  write_hint: 'Write or say your reason.',
  mark_kinds: {
    accord: 'agreement',
    conjugaison: 'verb form',
    genre: 'gender',
    orthographe: 'spelling',
    mot: 'word choice',
    ordre: 'word order',
    manque: 'a word is missing',
  },
  fix_label: 'Fix your sentence',
  fix_placeholder: 'Your corrected sentence…',
  fix_send: 'Send again',
  fix_try: 'Try {n} of {max}',
  fix_romy: 'Let Romy fix it',
  your_reply: 'Your reply',
  reply_label: 'Your reply, in one sentence',
  reply_placeholder: 'Your reply…',
  act_failed: 'That didn’t go through. Try again.',
  page_words: 'Your words',
  vote_aria: 'The vote: {pour} for, {nuance} it depends, {contre} against',
};

const DE: ComptoirCopy = {
  steps_label: 'Schritte',
  step_value: '{n} von {total} · {name}',
  give_opinion: 'Meine Meinung sagen',
  see_page: 'Die Seite ansehen',
  read_hint: 'Beantworte die Frage, dann geht es an die Theke.',
  takes_hint: '{n} Meinungen',
  takes_hint_intox: '{n} Meinungen · 1 Falschmeldung versteckt',
  react_hint: 'Einverstanden oder nicht? Reagiere auf jede Meinung.',
  listen: 'Anhören',
  intox_pick_hint: 'Tippe auf den falschen Satz.',
  intox_not_this: 'nicht dieser',
  intox_fix_label: 'Schreib deine Korrektur',
  intox_fix_placeholder: 'C’est faux, c’est…, pas…',
  intox_your_line: 'Dein Satz. Neue Wendung: «C’est faux, c’est…, pas…»',
  intox_right_line: 'Der richtige Satz. Neue Wendung: «C’est faux, c’est…, pas…»',
  intox_wrong_answer: 'Nicht ganz: Richtig ist «{right}».',
  side_label: 'Deine Seite',
  a1_reason_label: 'Warum?',
  a1_pick_hint: 'Wähle einen Grund.',
  phrase_label: 'Satz des Tages',
  bank_label: 'Wörter, die dir helfen',
  reason_label: 'Dein Grund',
  reason_placeholder: 'dein Grund, auf Französisch',
  answer_to: 'Antworte {name}',
  opinion_placeholder: 'Deine Meinung, auf Französisch',
  write_hint: 'Schreib oder sag deinen Grund.',
  mark_kinds: {
    accord: 'Angleichung',
    conjugaison: 'Verbform',
    genre: 'Genus',
    orthographe: 'Rechtschreibung',
    mot: 'Wortwahl',
    ordre: 'Wortstellung',
    manque: 'ein Wort fehlt',
  },
  fix_label: 'Korrigiere deinen Satz',
  fix_placeholder: 'Dein korrigierter Satz…',
  fix_send: 'Erneut senden',
  fix_try: 'Versuch {n} von {max}',
  fix_romy: 'Romy soll es korrigieren',
  your_reply: 'Deine Antwort',
  reply_label: 'Deine Antwort, in einem Satz',
  reply_placeholder: 'Deine Antwort…',
  act_failed: 'Das hat nicht geklappt. Versuch es noch einmal.',
  page_words: 'Deine Wörter',
  vote_aria: 'Die Abstimmung: {pour} dafür, {nuance} kommt drauf an, {contre} dagegen',
};

const TABLES: Record<RvLanguage, ComptoirCopy> = { fr: FR, en: EN, de: DE };

export function comptoirCopy(language: RvLanguage | string | null | undefined): ComptoirCopy {
  return TABLES[(language as RvLanguage) in TABLES ? (language as RvLanguage) : 'fr'];
}

/** The page's French, the same in every chrome (publication words). */
export const COMPTOIR_FR = {
  /** The feature's name, on the presses that lead to the counter. */
  press: 'Au comptoir',
  question_kicker: 'La question du jour',
  /** Over the learner's sentence once settled, by how it reached print (2026-10-23). */
  in_paper: 'Dans le journal',
  in_paper_read: 'Dans le journal · relu par Romy',
  in_paper_mine: 'Dans le journal · corrigé par toi',
  in_paper_fixed: 'Dans le journal · corrigé par Romy',
  in_paper_as_written: 'Dans le journal · tel que tu l’as écrit',
  /** While Romy's marks wait: nothing is printed yet. */
  proof_marked: 'Les corrections de Romy',
  page_kicker: 'Le micro-trottoir de Romy',
  page_intox: "L'intox du jour.",
  you: 'Toi',
  you_by: 'Toi, au comptoir',
  /** The page's credit when Romy corrected what the tries left. */
  you_by_corrected: 'Toi, au comptoir · corrigé par Romy',
} as const;

/**
 * The kicker over the printed sentence: «relu par Romy» only when her check found nothing,
 * «corrigé par toi» when the learner fixed her marks, «corrigé par Romy» when she fixed what
 * the tries left, «tel que tu l'as écrit» when no check ran. A1's tiles: plain «Dans le journal».
 */
export function inPaperLabel(proof: RvComptoirProof, tiles: boolean): string {
  if (tiles) return COMPTOIR_FR.in_paper;
  switch (proof) {
    case 'clean':
      return COMPTOIR_FR.in_paper_read;
    case 'fixed':
      return COMPTOIR_FR.in_paper_mine;
    case 'corrected':
      return COMPTOIR_FR.in_paper_fixed;
    case 'marked':
      return COMPTOIR_FR.proof_marked;
    default:
      return COMPTOIR_FR.in_paper_as_written;
  }
}

export type ComptoirLine = { fr: string; en: string; de: string };

/** Romy's authored lines on the client, French with their translations. `{name}`: a regular's name. */
export const COMPTOIR_LINES: Record<'intox_ask' | 'intox_wrong' | 'intox_found' | 'intox_reveal' | 'opinion_ask' | 'proof_marked', ComptoirLine> = {
  intox_ask: {
    fr: "Attends… quelqu'un a dit un truc faux. Qui ?",
    en: 'Wait… someone said something false. Who?',
    de: 'Moment… jemand hat etwas Falsches gesagt. Wer?',
  },
  intox_wrong: { fr: 'Non, relis bien.', en: 'No, read it again carefully.', de: 'Nein, lies noch mal genau.' },
  intox_found: { fr: 'Bien vu !', en: 'Well spotted!', de: 'Gut erkannt!' },
  intox_reveal: { fr: "C'était {name}.", en: 'It was {name}.', de: 'Es war {name}.' },
  opinion_ask: {
    fr: 'Et toi ? Il me manque une voix pour mon micro-trottoir.',
    en: "And you? I'm one voice short for my vox pop.",
    de: 'Und du? Mir fehlt noch eine Stimme für meine Straßenumfrage.',
  },
  proof_marked: {
    fr: 'Presque ! Regarde les mots soulignés et corrige-les.',
    en: 'Almost! Look at the underlined words and fix them.',
    de: 'Fast! Schau dir die unterstrichenen Wörter an und korrigiere sie.',
  },
};

/** A line in French and in the learner's gloss language (null for French). */
export function lineIn(line: ComptoirLine, language: RvLanguage, vars: Record<string, string> = {}): { fr: string; tr: string | null } {
  const put = (text: string) => text.replace(/\{(\w+)\}/g, (_, key: string) => vars[key] ?? `{${key}}`);
  return { fr: put(line.fr), tr: language === 'fr' ? null : put(line[language]) };
}
