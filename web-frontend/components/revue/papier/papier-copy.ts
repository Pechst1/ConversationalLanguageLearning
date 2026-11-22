/**
 * «Papier · la belle édition» (2026-11-21) · the paper objects' words.
 *
 * What the paper PRINTS stays French in every chrome, as the pages already do (`PAPIER_FR`):
 * the masthead, the dateline, «Édition du jour», «Dépêche», the stamps «VRAI» / «INTOX»,
 * «Lexique», the bylines. What the interface SAYS — a label for a screen reader, the tag of a
 * refused headline, the note that a tapped word may stand — is in the learner's control
 * language (`papierCopy`: mother tongue below B1, French from B1), with every key in fr, de
 * and en (papier.test.js).
 */

import type { RvLanguage } from '@/lib/revue-types';

export const PAPIER_FR = {
  masthead: 'Le Papier',
  edition_today: 'Édition du jour',
  /** «Papier · le choix»: the front page's section line, and the word at the foot of each story. */
  choix_section: 'À la une',
  choix_read: 'Lire →',
  dispatch: 'Dépêche',
  stamp_vrai: 'Vrai',
  stamp_intox: 'Intox',
  lexique: 'Lexique',
  photo_credit_rule: 'Photo',
  in_article: "Dans l'article",
  // «La photo», «Le micro», the rendez-vous (round 3)
  contact_sheet: 'Planche contact',
  legende_by: 'Légende · par toi',
  shrug: '{name} hausse les épaules.',
  transcript_q: 'Q.',
  transcript_a: 'R.',
  edition_week: 'Édition de la semaine',
  by_you: 'Par toi',
  checked_by_you: 'Vérifié par toi',
  interview_by_you: 'Propos recueillis par toi',
  stagiaire: 'Stagiaire · Le Papier',
  carte: 'Carte de presse',
  trois_mots: 'Trois mots',
  cutting_from: "Extrait de l'article",
} as const;

export type PapierCopy = {
  /** The masthead's label for a screen reader: «Le Papier, Paris, vendredi 21 novembre, Nº 47». */
  masthead_aria: string;
  /** A stamped slip, for a screen reader. */
  stamp_vrai_aria: string;
  stamp_intox_aria: string;
  /** The grease-pencil loop around the headline the learner picked. */
  your_pick: string;
  /** The tag on a refused headline proof, beside its reason. */
  refused: string;
  /** The tag on the honest headline once settled. */
  kept: string;
  /** A tapped word of «Le piège» the article does say: the proofreader's «stet». */
  stet: string;
  /** A word of «Le piège» struck out with the delete mark. */
  deleatur: string;
  /** A dispatch picked up to swap (said once, politely). */
  lifted: string;
  /** The dispatches joined into one wire. */
  tape_joined: string;
  /** Romy's margin note on a slip, for a screen reader. */
  margin_note: string;
  /** The set's one translation toggle (strips, proofs, statements). */
  translate_all: string;
  translate_all_hide: string;
  /** The kicker over the learner's own headline on «La page». */
  page_kicker_mine: string;
  /** «La photo»: the sheet of the story's pictures, for a screen reader. */
  contact_sheet_aria: string;
  /** A frame of the sheet, for a screen reader. */
  frame_aria: string;
  /** The learner's caption under the print as they write it. */
  legend_live: string;
  /** Nothing written yet under the print. */
  legend_empty: string;
  /** «Le micro»: Romy's notebook page, for a screen reader. */
  notebook_aria: string;
  /** The interview set as a transcript, for a screen reader. */
  transcript_aria: string;
  /** A question chosen in the notebook: its number in the interview. */
  question_n: string;
  /** «La carte de presse»: a rubrique's stamped box, filed / not yet. */
};

const FR: PapierCopy = {
  masthead_aria: 'Le Papier, {dateline}',
  stamp_vrai_aria: 'Tampon : vrai',
  stamp_intox_aria: 'Tampon : intox',
  your_pick: 'Ton choix',
  refused: 'Refusé',
  kept: 'Retenu',
  stet: "À garder : l'article le dit",
  deleatur: 'À supprimer',
  lifted: 'Dépêche {n} soulevée : touche une autre dépêche pour les échanger.',
  tape_joined: 'Les dépêches forment un seul fil.',
  margin_note: 'Note de Romy',
  translate_all: 'Tout traduire',
  translate_all_hide: 'Masquer les traductions',
  page_kicker_mine: 'Ton titre',
  contact_sheet_aria: 'Planche contact : les images de l’article',
  frame_aria: 'Image {n}',
  legend_live: 'Ta légende',
  legend_empty: 'Ta légende s’écrit ici.',
  notebook_aria: 'Le carnet de Romy',
  transcript_aria: 'L’interview, question par question',
  question_n: 'Question {n}',
};

const DE: PapierCopy = {
  masthead_aria: 'Le Papier, {dateline}',
  stamp_vrai_aria: 'Stempel: wahr',
  stamp_intox_aria: 'Stempel: Falschmeldung',
  your_pick: 'Deine Wahl',
  refused: 'Abgelehnt',
  kept: 'Genommen',
  stet: 'Bleibt stehen: Das sagt der Artikel',
  deleatur: 'Streichen',
  lifted: 'Meldung {n} angehoben: Tippe eine andere Meldung, um sie zu tauschen.',
  tape_joined: 'Die Meldungen ergeben einen Faden.',
  margin_note: 'Romys Randnotiz',
  translate_all: 'Alles übersetzen',
  translate_all_hide: 'Übersetzungen ausblenden',
  page_kicker_mine: 'Dein Titel',
  contact_sheet_aria: 'Kontaktbogen: die Bilder des Artikels',
  frame_aria: 'Bild {n}',
  legend_live: 'Deine Bildunterschrift',
  legend_empty: 'Hier entsteht deine Bildunterschrift.',
  notebook_aria: 'Romys Notizbuch',
  transcript_aria: 'Das Interview, Frage für Frage',
  question_n: 'Frage {n}',
};

const EN: PapierCopy = {
  masthead_aria: 'Le Papier, {dateline}',
  stamp_vrai_aria: 'Stamp: true',
  stamp_intox_aria: 'Stamp: fake news',
  your_pick: 'Your pick',
  refused: 'Rejected',
  kept: 'Kept',
  stet: 'Let it stand: the article says this',
  deleatur: 'Delete',
  lifted: 'Dispatch {n} picked up: tap another dispatch to swap them.',
  tape_joined: 'The dispatches make one wire.',
  margin_note: "Romy's margin note",
  translate_all: 'Translate all',
  translate_all_hide: 'Hide translations',
  page_kicker_mine: 'Your headline',
  contact_sheet_aria: 'Contact sheet: the story’s pictures',
  frame_aria: 'Frame {n}',
  legend_live: 'Your caption',
  legend_empty: 'Your caption appears here.',
  notebook_aria: 'Romy’s notebook',
  transcript_aria: 'The interview, question by question',
  question_n: 'Question {n}',
};

export const PAPIER_COPY: Record<RvLanguage, PapierCopy> = { fr: FR, de: DE, en: EN };

export function papierCopy(language: unknown): PapierCopy {
  const key = String(language || '').toLowerCase().slice(0, 2);
  return key === 'de' ? DE : key === 'fr' ? FR : EN;
}
