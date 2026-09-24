/**
 * WP-82 — the repair card («Reprise de langue») follows the one language rule.
 *
 * The card's own words — its labels, the send button, the verdict, close —
 * are chrome: the learner's language up to A2, French from B1
 * (`chromeLanguage`, `lib/language-rule.ts`). The prompt, the learner's
 * earlier sentence and the target answer are content and stay French; the
 * stored erratum halves keep whatever language the corrector filed them in.
 *
 * Every table has the same keys (the language test proves it).
 */

import { normalizeControlLanguage } from '@/lib/atelier-v2-copy';
import type { ControlLanguage } from '@/types/daily-journey';

export type ErrataCopy = {
  task: string;
  memorised: string;
  why: string;
  hint: string;
  answer: string;
  send: string;
  sending: string;
  repaired: string;
  not_yet: string;
  target: string;
  done: string;
  close: string;
};

const FR: ErrataCopy = {
  task: 'Tâche de reprise',
  memorised: 'Erreur mémorisée',
  why: 'Pourquoi :',
  hint: 'À reprendre :',
  answer: 'Votre reprise',
  send: 'Envoyer la reprise',
  sending: 'Envoi…',
  repaired: 'Repris',
  not_yet: 'Pas encore',
  target: 'Réponse visée',
  done: 'Terminé',
  close: 'Fermer',
};

const EN: ErrataCopy = {
  task: 'Repair task',
  memorised: 'Your earlier mistake',
  why: 'Why:',
  hint: 'To fix:',
  answer: 'Your correction',
  send: 'Send correction',
  sending: 'Sending…',
  repaired: 'Fixed',
  not_yet: 'Not yet',
  target: 'Target answer',
  done: 'Done',
  close: 'Close',
};

const DE: ErrataCopy = {
  task: 'Korrekturaufgabe',
  memorised: 'Ihr früherer Fehler',
  why: 'Warum:',
  hint: 'Zu korrigieren:',
  answer: 'Ihre Korrektur',
  send: 'Korrektur senden',
  sending: 'Wird gesendet…',
  repaired: 'Korrigiert',
  not_yet: 'Noch nicht',
  target: 'Zielantwort',
  done: 'Fertig',
  close: 'Schließen',
};

export const ERRATA_COPY: Record<ControlLanguage, ErrataCopy> = { en: EN, de: DE, fr: FR };

/** The repair card's copy table for a chrome language. */
export function errataCopy(language: unknown): ErrataCopy {
  return ERRATA_COPY[normalizeControlLanguage(language)];
}
