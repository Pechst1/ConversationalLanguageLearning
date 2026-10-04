/**
 * SPEED-1 «Vérification du lexique» — the chrome, in the learner's declared
 * native language.
 *
 * Like the placement, the check measures what the learner already knows, so
 * the level cannot choose its language: the chrome follows `native_language`
 * (`useLearnerLanguage()`), and so do the meaning options the server sends.
 * The French word on screen is content (`lang="fr"`).
 *
 * «Je ne sais pas» is a real answer. No string here treats it as a failure,
 * and a check that does not pass says honestly what happens next: the words
 * arrive in the normal flow, nothing is lost.
 */

import { normalizeControlLanguage } from '@/lib/atelier-v2-copy';
import type { ControlLanguage } from '@/types/daily-journey';

export type BandCheckCopy = {
  screen_aria: string;
  kicker: string;
  // intro
  intro_title: string;
  intro_lead: string;
  intro_fine: string;
  bands_label: string;
  credited_mark: string;
  begin: string;
  opening: string;
  later: string;
  // the run
  dont_know: string;
  options_label: string;
  progress_aria: string;
  progress_caption: string;
  undo: string;
  keys_hint: string;
  sending: string;
  status_selected: string;
  status_correct: string;
  status_wrong: string;
  // the result
  passed_title: string;
  passed_title_one: string;
  passed_none_title: string;
  passed_lead: string;
  passed_none_lead: string;
  score_line: string;
  passed_missed_note: string;
  failed_title: string;
  failed_lead: string;
  next_band: string;
  next_anyway: string;
  back_lexique: string;
  back_day: string;
  // states
  failed_open: string;
  failed_send: string;
  retry: string;
  none_title: string;
  none_lead: string;
  // entry points
  entry_cta: string;
  entry_lead_placement: string;
  entry_lead_lexique: string;
};

const FR: BandCheckCopy = {
  screen_aria: 'Vérification du lexique',
  kicker: 'Vérification du lexique · {band}',
  intro_title: 'Ces mots, vous les connaissez déjà ?',
  intro_lead:
    '{n} mots du niveau {band}. Pour chacun, choisissez le sens — ou « Je ne sais pas ». Environ deux minutes.',
  intro_fine:
    'Si vous en reconnaissez au moins {pct} %, tout le niveau compte comme acquis : ses mots ne reviendront que pour une vérification légère.',
  bands_label: 'Niveaux à vérifier',
  credited_mark: 'acquis',
  begin: 'Commencer',
  opening: 'Ouverture…',
  later: 'Plus tard',
  dont_know: 'Je ne sais pas',
  options_label: 'Le sens de ce mot',
  progress_aria: 'Progression de la vérification',
  progress_caption: '{n} / {total}',
  undo: 'Mot précédent',
  keys_hint: 'Touches 1 à 4 · 0 pour « Je ne sais pas »',
  sending: 'Lecture…',
  status_selected: 'choisi',
  status_correct: 'juste',
  status_wrong: 'à revoir',
  passed_title: '{n} mots déjà acquis',
  passed_title_one: '1 mot déjà acquis',
  passed_none_title: 'Niveau {band} validé',
  passed_lead: 'Ils reviendront pour une vérification légère dans les semaines qui viennent.',
  passed_none_lead: 'Vous aviez déjà tous ses mots dans vos cartes.',
  score_line: '{correct} sur {total} reconnus.',
  passed_missed_note: 'Les mots que vous n’avez pas reconnus restent dans le parcours normal.',
  failed_title: '{correct} sur {total} reconnus',
  failed_lead:
    'Pas assez pour valider {band} d’un coup — il en fallait {needed}. Ces mots viendront dans le parcours normal, à leur rythme ; rien n’est perdu.',
  next_band: 'Vérifier {band}',
  next_anyway: 'Vérifier {band} quand même',
  back_lexique: 'Retour au lexique',
  back_day: 'Continuer',
  failed_open: 'La vérification n’a pas pu être ouverte. Réessayez dans un instant.',
  failed_send: 'Vos réponses ne sont pas parties. Elles sont toujours là — réessayez.',
  retry: 'Réessayer',
  none_title: 'Rien à vérifier',
  none_lead: 'Les niveaux sous le vôtre sont déjà acquis.',
  entry_cta: 'Vérifier mon vocabulaire (2 min par niveau)',
  entry_lead_placement:
    'Vous connaissez sans doute déjà une partie des mots des niveaux précédents. Une vérification rapide vous évite de les réapprendre.',
  entry_lead_lexique: 'Niveaux {bands} : vérifiez les mots que vous connaissez déjà.',
};

const EN: BandCheckCopy = {
  screen_aria: 'Vocabulary check',
  kicker: 'Vocabulary check · {band}',
  intro_title: 'Do you know these words already?',
  intro_lead:
    '{n} words from level {band}. For each one, pick the meaning — or “I don’t know”. About two minutes.',
  intro_fine:
    'If you recognise at least {pct} %, the whole level counts as known: its words come back only for a light check.',
  bands_label: 'Levels to check',
  credited_mark: 'known',
  begin: 'Start',
  opening: 'Opening…',
  later: 'Later',
  dont_know: 'I don’t know',
  options_label: 'The meaning of this word',
  progress_aria: 'Check progress',
  progress_caption: '{n} / {total}',
  undo: 'Previous word',
  keys_hint: 'Keys 1 to 4 · 0 for “I don’t know”',
  sending: 'Reading…',
  status_selected: 'chosen',
  status_correct: 'right',
  status_wrong: 'to review',
  passed_title: '{n} words already known',
  passed_title_one: '1 word already known',
  passed_none_title: 'Level {band} confirmed',
  passed_lead: 'They will come back for a light check over the next few weeks.',
  passed_none_lead: 'You already had all of its words on your cards.',
  score_line: '{correct} of {total} recognised.',
  passed_missed_note: 'The words you did not recognise stay in the normal flow.',
  failed_title: '{correct} of {total} recognised',
  failed_lead:
    'Not quite enough to confirm {band} in one go — it needed {needed}. These words will come in the normal flow, at their own pace; nothing is lost.',
  next_band: 'Check {band}',
  next_anyway: 'Check {band} anyway',
  back_lexique: 'Back to the vocabulary',
  back_day: 'Continue',
  failed_open: 'The check could not be opened. Try again in a moment.',
  failed_send: 'Your answers did not go through. They are still here — try again.',
  retry: 'Try again',
  none_title: 'Nothing to check',
  none_lead: 'The levels below yours are already known.',
  entry_cta: 'Check my vocabulary (2 min per level)',
  entry_lead_placement:
    'You probably know some of the words from the earlier levels already. A quick check saves you learning them again.',
  entry_lead_lexique: 'Levels {bands}: check the words you already know.',
};

const DE: BandCheckCopy = {
  screen_aria: 'Wortschatz-Check',
  kicker: 'Wortschatz-Check · {band}',
  intro_title: 'Kennen Sie diese Wörter schon?',
  intro_lead:
    '{n} Wörter aus Niveau {band}. Wählen Sie bei jedem die Bedeutung — oder „Weiß ich nicht“. Etwa zwei Minuten.',
  intro_fine:
    'Wenn Sie mindestens {pct} % erkennen, gilt das ganze Niveau als bekannt: Seine Wörter kommen nur noch zu einer kurzen Kontrolle zurück.',
  bands_label: 'Niveaus zum Prüfen',
  credited_mark: 'bekannt',
  begin: 'Starten',
  opening: 'Wird geöffnet…',
  later: 'Später',
  dont_know: 'Weiß ich nicht',
  options_label: 'Die Bedeutung dieses Wortes',
  progress_aria: 'Fortschritt des Checks',
  progress_caption: '{n} / {total}',
  undo: 'Voriges Wort',
  keys_hint: 'Tasten 1 bis 4 · 0 für „Weiß ich nicht“',
  sending: 'Wird gelesen…',
  status_selected: 'gewählt',
  status_correct: 'richtig',
  status_wrong: 'noch üben',
  passed_title: '{n} Wörter schon bekannt',
  passed_title_one: '1 Wort schon bekannt',
  passed_none_title: 'Niveau {band} bestätigt',
  passed_lead: 'Sie kommen in den nächsten Wochen zu einer kurzen Kontrolle zurück.',
  passed_none_lead: 'Sie hatten alle seine Wörter schon in Ihren Karten.',
  score_line: '{correct} von {total} erkannt.',
  passed_missed_note: 'Die Wörter, die Sie nicht erkannt haben, bleiben im normalen Ablauf.',
  failed_title: '{correct} von {total} erkannt',
  failed_lead:
    'Nicht ganz genug, um {band} auf einmal zu bestätigen — nötig waren {needed}. Diese Wörter kommen im normalen Ablauf, in ihrem Tempo; nichts geht verloren.',
  next_band: '{band} prüfen',
  next_anyway: '{band} trotzdem prüfen',
  back_lexique: 'Zurück zum Wortschatz',
  back_day: 'Weiter',
  failed_open: 'Der Check konnte nicht geöffnet werden. Versuchen Sie es gleich noch einmal.',
  failed_send: 'Ihre Antworten wurden nicht gesendet. Sie sind noch da — versuchen Sie es erneut.',
  retry: 'Erneut versuchen',
  none_title: 'Nichts zu prüfen',
  none_lead: 'Die Niveaus unter Ihrem sind schon bekannt.',
  entry_cta: 'Meinen Wortschatz prüfen (2 Min. pro Niveau)',
  entry_lead_placement:
    'Einen Teil der Wörter aus den früheren Niveaus kennen Sie wahrscheinlich schon. Ein kurzer Check erspart Ihnen, sie neu zu lernen.',
  entry_lead_lexique: 'Niveaus {bands}: Prüfen Sie die Wörter, die Sie schon kennen.',
};

const TABLES: Record<ControlLanguage, BandCheckCopy> = { en: EN, de: DE, fr: FR };

export function bandCheckCopy(language: unknown): BandCheckCopy {
  return TABLES[normalizeControlLanguage(language)];
}

export function bandCheckFill(template: string, values: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (match, key: string) =>
    key in values ? String(values[key]) : match,
  );
}

/** The passed headline, with the singular and the «nothing new to card» case. */
export function passedTitle(copy: BandCheckCopy, credited: number, band: string): string {
  if (credited <= 0) return bandCheckFill(copy.passed_none_title, { band });
  if (credited === 1) return copy.passed_title_one;
  return bandCheckFill(copy.passed_title, { n: credited });
}
