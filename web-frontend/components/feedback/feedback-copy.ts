/**
 * The pilot feedback panel's words, by the one-language rule
 * (lib/language-rule.ts): the learner's language up to A2, French from B1.
 * It used to be English for everyone, which was an island on every screen.
 */

import type { FeedbackCategory } from '@/services/api';
import type { ControlLanguage } from '@/types/daily-journey';

export type FeedbackCopy = {
  eyebrow: string;
  title: string;
  dialog: string;
  close: string;
  note: string;
  note_placeholder: string;
  send: string;
  sending: string;
  sent: string;
  failed: string;
  categories: Record<FeedbackCategory, string>;
};

export const FEEDBACK_COPY: Record<ControlLanguage, FeedbackCopy> = {
  en: {
    eyebrow: 'Feedback',
    title: 'What is off?',
    dialog: 'Send feedback',
    close: 'Close feedback',
    note: 'Note',
    note_placeholder: 'Optional detail',
    send: 'Send',
    sending: 'Sending',
    sent: 'Feedback sent.',
    failed: 'Could not send feedback.',
    categories: {
      bug: 'Bug',
      broken_link: 'Broken link',
      content: 'Text/content',
      layout: 'Layout',
      slow_loading: 'Slow/loading',
      suggestion: 'Suggestion',
      other: 'Other',
    },
  },
  de: {
    eyebrow: 'Feedback',
    title: 'Was stimmt nicht?',
    dialog: 'Feedback senden',
    close: 'Feedback schließen',
    note: 'Notiz',
    note_placeholder: 'Details (optional)',
    send: 'Senden',
    sending: 'Wird gesendet',
    sent: 'Feedback gesendet.',
    failed: 'Feedback konnte nicht gesendet werden.',
    categories: {
      bug: 'Fehler',
      broken_link: 'Defekter Link',
      content: 'Text/Inhalt',
      layout: 'Layout',
      slow_loading: 'Langsam/Laden',
      suggestion: 'Vorschlag',
      other: 'Anderes',
    },
  },
  fr: {
    eyebrow: 'Avis',
    title: 'Qu’est-ce qui cloche ?',
    dialog: 'Envoyer un avis',
    close: 'Fermer l’avis',
    note: 'Note',
    note_placeholder: 'Détail facultatif',
    send: 'Envoyer',
    sending: 'Envoi',
    sent: 'Avis envoyé.',
    failed: 'L’avis n’a pas pu être envoyé.',
    categories: {
      bug: 'Bogue',
      broken_link: 'Lien cassé',
      content: 'Texte/contenu',
      layout: 'Mise en page',
      slow_loading: 'Lenteur/chargement',
      suggestion: 'Suggestion',
      other: 'Autre',
    },
  },
};

export const FEEDBACK_CATEGORIES: FeedbackCategory[] = [
  'bug',
  'broken_link',
  'content',
  'layout',
  'slow_loading',
  'suggestion',
  'other',
];

export function feedbackCopy(language: unknown): FeedbackCopy {
  return FEEDBACK_COPY[language as ControlLanguage] ?? FEEDBACK_COPY.en;
}
