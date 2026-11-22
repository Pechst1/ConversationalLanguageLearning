/**
 * «Papier · la voix» (2026-11-22) · the chrome of the heard paper, in fr, en and de: the lead's
 * reading, a regular's line before it is read, «La dictée de Romy».
 *
 * The chrome is `plan.ui_language` (the mother tongue below B1, French from B1); the dictée's
 * explanations (the grader's note, the marks' kinds) are in the mother tongue always, as Romy's
 * marks are. French in every table: the feature's name, as the paper prints it.
 */

import type { RvLanguage } from '@/lib/revue-types';

export const VOIX_FR = {
  dictee_title: 'La dictée de Romy',
};

export type VoixCopy = {
  lead_listen: string;
  lead_stop: string;
  lead_by: string;
  line_listen: string;
  line_read: string;
  line_playing: string;
  face_replay: string;
  dictee_offer: string;
  dictee_start: string;
  dictee_task: string;
  dictee_hear: string;
  dictee_again: string;
  dictee_field: string;
  dictee_placeholder: string;
  dictee_check: string;
  dictee_marked: string;
  dictee_try: string;
  dictee_met: string;
  dictee_accents: string;
  dictee_shown: string;
  dictee_close: string;
  dictee_failed: string;
};

const fr: VoixCopy = {
  lead_listen: 'Écouter le chapeau',
  lead_stop: 'Arrêter',
  lead_by: 'lu par la rédaction',
  line_listen: 'Écouter',
  line_read: 'Lire',
  line_playing: 'On écoute…',
  face_replay: '{name} : réécouter',
  dictee_offer: 'Une phrase du chapeau, à l’oreille. Facultatif.',
  dictee_start: 'Faire la dictée',
  dictee_task: 'Écoute la phrase, puis écris-la. Le chapeau est caché pendant la dictée.',
  dictee_hear: 'Écouter la phrase',
  dictee_again: 'Réécouter',
  dictee_field: 'Ta phrase',
  dictee_placeholder: 'Écris ce que tu entends…',
  dictee_check: 'Rendre la copie',
  dictee_marked: 'Romy a souligné ce qu’il faut revoir.',
  dictee_try: 'Réécoute et corrige. Essai {n} sur {max}.',
  dictee_met: 'Juste, mot pour mot.',
  dictee_accents: 'Les mots sont justes ; regarde les accents.',
  dictee_shown: 'La phrase du chapeau :',
  dictee_close: 'Fermer la dictée',
  dictee_failed: 'La copie n’est pas partie. Réessaie.',
};

const en: VoixCopy = {
  lead_listen: 'Hear the lead',
  lead_stop: 'Stop',
  lead_by: 'read by the newsroom',
  line_listen: 'Listen',
  line_read: 'Read',
  line_playing: 'Listening…',
  face_replay: '{name}: hear again',
  dictee_offer: 'One sentence of the lead, by ear. Optional.',
  dictee_start: 'Take the dictation',
  dictee_task: 'Listen to the sentence, then write it down. The lead is hidden meanwhile.',
  dictee_hear: 'Hear the sentence',
  dictee_again: 'Hear it again',
  dictee_field: 'Your sentence',
  dictee_placeholder: 'Write what you hear…',
  dictee_check: 'Hand it in',
  dictee_marked: 'Romy has underlined what to look at again.',
  dictee_try: 'Listen again and fix it. Try {n} of {max}.',
  dictee_met: 'Right, word for word.',
  dictee_accents: 'The words are right; check the accents.',
  dictee_shown: 'The sentence from the lead:',
  dictee_close: 'Close the dictation',
  dictee_failed: 'It did not go through. Try again.',
};

const de: VoixCopy = {
  lead_listen: 'Vorspann anhören',
  lead_stop: 'Anhalten',
  lead_by: 'gelesen von der Redaktion',
  line_listen: 'Anhören',
  line_read: 'Lesen',
  line_playing: 'Hör zu…',
  face_replay: '{name}: noch einmal hören',
  dictee_offer: 'Ein Satz aus dem Vorspann, nach Gehör. Freiwillig.',
  dictee_start: 'Diktat schreiben',
  dictee_task: 'Hör dir den Satz an und schreib ihn auf. Der Vorspann ist so lange verdeckt.',
  dictee_hear: 'Satz anhören',
  dictee_again: 'Noch einmal hören',
  dictee_field: 'Dein Satz',
  dictee_placeholder: 'Schreib, was du hörst…',
  dictee_check: 'Abgeben',
  dictee_marked: 'Romy hat unterstrichen, was du dir noch einmal ansehen solltest.',
  dictee_try: 'Hör noch einmal hin und verbessere. Versuch {n} von {max}.',
  dictee_met: 'Richtig, Wort für Wort.',
  dictee_accents: 'Die Wörter stimmen; achte auf die Akzente.',
  dictee_shown: 'Der Satz aus dem Vorspann:',
  dictee_close: 'Diktat schließen',
  dictee_failed: 'Das hat nicht geklappt. Versuch es noch einmal.',
};

const TABLES: Record<RvLanguage, VoixCopy> = { fr, en, de };

export function voixCopy(language: RvLanguage | string | null | undefined): VoixCopy {
  return TABLES[(language as RvLanguage) ?? 'en'] ?? en;
}

export function fillVoix(template: string, vars: Record<string, string>): string {
  return template.replace(/\{(\w+)\}/g, (_, key: string) => vars[key] ?? '');
}

export const VOIX_COPIES = TABLES;
