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
  dispatch: 'Dépêche',
  stamp_vrai: 'Vrai',
  stamp_intox: 'Intox',
  lexique: 'Lexique',
  photo_credit_rule: 'Photo',
  in_article: "Dans l'article",
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
};

export const PAPIER_COPY: Record<RvLanguage, PapierCopy> = { fr: FR, de: DE, en: EN };

export function papierCopy(language: unknown): PapierCopy {
  const key = String(language || '').toLowerCase().slice(0, 2);
  return key === 'de' ? DE : key === 'fr' ? FR : EN;
}
