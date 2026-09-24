/**
 * 2026-09-24 — the placement («Bilan de niveau») explains itself in the
 * learner's declared native language, whatever the level: it is the screen
 * that measures the level, so the level cannot choose its language.
 *
 * The prompts, the learner's answers and the grader's evidence are French
 * content (`lang="fr"`); the hint under the field arrives as
 * `hint_by_language` from the server. The place name «L’Atelier» stays French.
 */

import type { ControlLanguage } from '@/types/daily-journey';

import { normalizeControlLanguage } from './atelier-v2-copy';

export type PlacementCopy = {
  screen_aria: string;
  failed_open: string;
  failed_send: string;
  failed_close: string;
  // the offer
  offer_title_tab: string;
  opening: string;
  begin: string;
  skip: string;
  offer_kicker: string;
  offer_title: string;
  offer_lead: string;
  offer_fine: string;
  // the conversation
  kicker: string;
  reading: string;
  send: string;
  stop: string;
  progress_aria: string;
  question: string;
  answer_label: string;
  answer_placeholder: string;
  // unmeasured
  unassessed_title: string;
  retry: string;
  continue_without: string;
  unassessed_lead: string;
  unassessed_fine: string;
  // the result
  result_title_tab: string;
  open_first: string;
  estimated: string;
  confidence_solid: string;
  confidence_fair: string;
  confidence_provisional: string;
  result_lead: string;
  evidence_summary: string;
  dimensions: Record<'range' | 'accuracy' | 'coherence' | 'task', string>;
};

const FR: PlacementCopy = {
  screen_aria: 'Bilan de niveau',
  failed_open: 'Le bilan n’a pas pu être ouvert. Réessayez dans un instant.',
  failed_send: 'Votre réponse n’est pas partie. Elle est toujours là — réessayez.',
  failed_close: 'Le bilan n’a pas pu être clos. Réessayez dans un instant.',
  offer_title_tab: 'Trouvons votre niveau',
  opening: 'Ouverture…',
  begin: 'Commencer le bilan',
  skip: 'Passer pour l’instant',
  offer_kicker: 'L’Atelier · Bilan de niveau',
  offer_title: 'Trouvons votre niveau',
  offer_lead: '4 à 6 questions.',
  offer_fine:
    'Sans bilan, votre niveau continue de suivre vos scènes. Vous pouvez faire ce bilan plus tard depuis les Réglages.',
  kicker: 'Bilan de niveau',
  reading: 'Lecture…',
  send: 'Envoyer',
  stop: 'Arrêter le bilan',
  progress_aria: 'Progression du bilan',
  question: 'Question {n}',
  answer_label: 'Votre réponse, en français',
  answer_placeholder: 'Écrivez ici…',
  unassessed_title: 'Niveau non évalué',
  retry: 'Refaire le bilan',
  continue_without: 'Continuer sans bilan',
  unassessed_lead:
    'La correction n’a pas répondu, donc nous n’avons rien mesuré. Nous préférons vous le dire plutôt que d’annoncer un niveau que personne n’a vérifié.',
  unassessed_fine:
    'Le niveau que vous avez indiqué à l’inscription reste en place. Vos réponses n’ont pas été perdues : elles ne portent simplement aucune note.',
  result_title_tab: 'Votre niveau estimé',
  open_first: 'Ouvrir ma première séance',
  estimated: 'Niveau estimé : {level}',
  confidence_solid: 'Estimation solide',
  confidence_fair: 'Estimation raisonnable',
  confidence_provisional: 'Estimation provisoire',
  result_lead:
    '{confidence}, sur {n} réponses corrigées. Ce niveau guide vos premières séances ; il bougera dès que vos exercices en diront davantage.',
  evidence_summary: 'Sur quoi repose cette estimation',
  dimensions: {
    range: 'Richesse du lexique',
    accuracy: 'Correction grammaticale',
    coherence: 'Cohérence du propos',
    task: 'Réponse à la consigne',
  },
};

const EN: PlacementCopy = {
  screen_aria: 'Level check',
  failed_open: 'The level check could not be opened. Try again in a moment.',
  failed_send: 'Your answer did not go through. It is still here — try again.',
  failed_close: 'The level check could not be closed. Try again in a moment.',
  offer_title_tab: 'Let’s find your level',
  opening: 'Opening…',
  begin: 'Start the level check',
  skip: 'Not now',
  offer_kicker: 'L’Atelier · Level check',
  offer_title: 'Let’s find your level',
  offer_lead: '4 to 6 questions.',
  offer_fine:
    'Without a check, your level keeps following your scenes. You can take it later from Réglages.',
  kicker: 'Level check',
  reading: 'Reading…',
  send: 'Send',
  stop: 'Stop the check',
  progress_aria: 'Level check progress',
  question: 'Question {n}',
  answer_label: 'Your answer, in French',
  answer_placeholder: 'Write here…',
  unassessed_title: 'Level not measured',
  retry: 'Take the check again',
  continue_without: 'Carry on without it',
  unassessed_lead:
    'The marking did not answer, so we measured nothing. We would rather tell you than announce a level nobody checked.',
  unassessed_fine:
    'The level you gave when you signed up stays in place. Your answers are not lost: they simply carry no mark.',
  result_title_tab: 'Your estimated level',
  open_first: 'Open my first session',
  estimated: 'Estimated level: {level}',
  confidence_solid: 'A solid estimate',
  confidence_fair: 'A fair estimate',
  confidence_provisional: 'A provisional estimate',
  result_lead:
    '{confidence}, from {n} marked answers. This level guides your first sessions; it will move as soon as your exercises say more.',
  evidence_summary: 'What this estimate rests on',
  dimensions: {
    range: 'Range of vocabulary',
    accuracy: 'Grammatical accuracy',
    coherence: 'Coherence',
    task: 'Answering the task',
  },
};

const DE: PlacementCopy = {
  screen_aria: 'Einstufung',
  failed_open: 'Die Einstufung konnte nicht geöffnet werden. Versuchen Sie es gleich noch einmal.',
  failed_send: 'Ihre Antwort wurde nicht gesendet. Sie ist noch da — versuchen Sie es erneut.',
  failed_close: 'Die Einstufung konnte nicht abgeschlossen werden. Versuchen Sie es gleich noch einmal.',
  offer_title_tab: 'Finden wir Ihr Niveau',
  opening: 'Wird geöffnet…',
  begin: 'Einstufung starten',
  skip: 'Jetzt nicht',
  offer_kicker: 'L’Atelier · Einstufung',
  offer_title: 'Finden wir Ihr Niveau',
  offer_lead: '4 bis 6 Fragen.',
  offer_fine:
    'Ohne Einstufung folgt Ihr Niveau weiter Ihren Szenen. Sie können sie später in den Réglages machen.',
  kicker: 'Einstufung',
  reading: 'Wird gelesen…',
  send: 'Senden',
  stop: 'Einstufung beenden',
  progress_aria: 'Fortschritt der Einstufung',
  question: 'Frage {n}',
  answer_label: 'Ihre Antwort, auf Französisch',
  answer_placeholder: 'Hier schreiben…',
  unassessed_title: 'Niveau nicht gemessen',
  retry: 'Einstufung wiederholen',
  continue_without: 'Ohne Einstufung weiter',
  unassessed_lead:
    'Die Korrektur hat nicht geantwortet, also haben wir nichts gemessen. Wir sagen Ihnen das lieber, als ein Niveau zu nennen, das niemand geprüft hat.',
  unassessed_fine:
    'Das Niveau, das Sie bei der Anmeldung angegeben haben, bleibt bestehen. Ihre Antworten sind nicht verloren: Sie tragen nur keine Note.',
  result_title_tab: 'Ihr geschätztes Niveau',
  open_first: 'Meine erste Sitzung öffnen',
  estimated: 'Geschätztes Niveau: {level}',
  confidence_solid: 'Eine solide Schätzung',
  confidence_fair: 'Eine brauchbare Schätzung',
  confidence_provisional: 'Eine vorläufige Schätzung',
  result_lead:
    '{confidence}, aus {n} korrigierten Antworten. Dieses Niveau leitet Ihre ersten Sitzungen; es ändert sich, sobald Ihre Übungen mehr verraten.',
  evidence_summary: 'Worauf diese Schätzung beruht',
  dimensions: {
    range: 'Wortschatz',
    accuracy: 'Grammatische Richtigkeit',
    coherence: 'Zusammenhang',
    task: 'Erfüllung der Aufgabe',
  },
};

const TABLES: Record<ControlLanguage, PlacementCopy> = { en: EN, de: DE, fr: FR };

export function placementCopy(language: unknown): PlacementCopy {
  return TABLES[normalizeControlLanguage(language)];
}

export function placementFill(template: string, values: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (match, key) => (key in values ? String(values[key]) : match));
}

/** Turned into a sentence rather than a percentage: a learner reads words. */
export function placementConfidenceLabel(confidence: number, copy: PlacementCopy): string {
  if (confidence >= 0.75) return copy.confidence_solid;
  if (confidence >= 0.55) return copy.confidence_fair;
  return copy.confidence_provisional;
}

export default placementCopy;
