/**
 * WP-82 — Home's load and start errors follow the one language rule.
 *
 * The page records *what* went wrong (`kind`) when the request fails and says
 * it at render time, in the chrome language of the screen that shows it: the
 * learner's language up to A2, French from B1. Sentence case, no tracked caps.
 */

import type { ControlLanguage } from '@/types/daily-journey';

import { normalizeControlLanguage } from './atelier-v2-copy';

export type AtelierErrorKind =
  | 'offline'
  | 'slow_load'
  | 'slow_session'
  | 'down_load'
  | 'down_session'
  | 'failed_load'
  | 'failed_session'
  | 'confirm_needed';

export type AtelierErrorNotice = { kind: AtelierErrorKind };

type Text = { label: string; message: string };

const FR: Record<AtelierErrorKind, Text> = {
  offline: { label: 'Hors ligne', message: 'Vérifiez la connexion, puis réessayez.' },
  slow_load: { label: 'Encore un instant', message: 'L’Atelier répond lentement. Réessayez.' },
  slow_session: { label: 'Encore un instant', message: 'La séance est peut-être déjà prête. Réessayez.' },
  down_load: { label: 'Pas encore prêt', message: 'La page du jour n’a pas pu être chargée. Réessayez.' },
  down_session: { label: 'Pas encore prête', message: 'La séance n’a pas pu être préparée. Réessayez.' },
  failed_load: { label: 'Indisponible', message: 'L’Atelier ne répond pas. Réessayez dans un instant.' },
  failed_session: { label: 'Pas démarrée', message: 'La séance n’a pas démarré. Réessayez.' },
  confirm_needed: { label: 'À confirmer', message: 'La séance en cours n’a pas pu être confirmée. Réessayez pour garder votre travail.' },
};

const EN: Record<AtelierErrorKind, Text> = {
  offline: { label: 'Offline', message: 'Check your connection, then try again.' },
  slow_load: { label: 'One moment', message: 'The Atelier is answering slowly. Try again.' },
  slow_session: { label: 'One moment', message: 'Your practice may already be ready. Try again.' },
  down_load: { label: 'Not ready yet', message: 'Today’s page could not be loaded. Try again.' },
  down_session: { label: 'Not ready yet', message: 'Your practice could not be prepared. Try again.' },
  failed_load: { label: 'Unavailable', message: 'The Atelier is not answering. Try again in a moment.' },
  failed_session: { label: 'Not started', message: 'Your practice did not start. Try again.' },
  confirm_needed: { label: 'Needs a check', message: 'Your open practice could not be confirmed. Try again to keep your work.' },
};

const DE: Record<AtelierErrorKind, Text> = {
  offline: { label: 'Offline', message: 'Prüfe die Verbindung und versuch es erneut.' },
  slow_load: { label: 'Einen Moment', message: 'Das Atelier antwortet langsam. Versuch es erneut.' },
  slow_session: { label: 'Einen Moment', message: 'Deine Übung ist vielleicht schon bereit. Versuch es erneut.' },
  down_load: { label: 'Noch nicht bereit', message: 'Die heutige Seite ließ sich nicht laden. Versuch es erneut.' },
  down_session: { label: 'Noch nicht bereit', message: 'Deine Übung ließ sich nicht vorbereiten. Versuch es erneut.' },
  failed_load: { label: 'Nicht verfügbar', message: 'Das Atelier antwortet nicht. Versuch es gleich noch einmal.' },
  failed_session: { label: 'Nicht gestartet', message: 'Deine Übung ist nicht gestartet. Versuch es erneut.' },
  confirm_needed: { label: 'Bitte bestätigen', message: 'Deine offene Übung ließ sich nicht bestätigen. Versuch es erneut, damit nichts verloren geht.' },
};

const TABLES: Record<ControlLanguage, Record<AtelierErrorKind, Text>> = { en: EN, de: DE, fr: FR };

/** The notice's words in the screen's chrome language. */
export function atelierErrorText(notice: AtelierErrorNotice, language: unknown): Text {
  return TABLES[normalizeControlLanguage(language)][notice.kind];
}
