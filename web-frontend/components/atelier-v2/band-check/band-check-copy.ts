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
  /** WP-127: how the top-down ladder works, said once on the intro. */
  intro_top_down: string;
  bands_label: string;
  credited_mark: string;
  inferred_mark: string;
  missed_mark: string;
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
  /** WP-127: after a miss, the ladder steps down. */
  next_down_lead: string;
  /** WP-127: sampled vs inferred credit, said separately. */
  passed_split: string;
  inferred_note: string;
  /** WP-127: a visit's two checks are spent. */
  paused_title: string;
  paused_lead: string;
  stop_here: string;
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
  entry_lead_resume: string;
};

const FR: BandCheckCopy = {
  screen_aria: 'Vérification du lexique',
  kicker: 'Vérification du lexique · {band}',
  intro_title: 'Ces mots, vous les connaissez déjà ?',
  intro_lead:
    '{n} mots du niveau {band}. Pour chacun, choisissez le sens — ou « Je ne sais pas ». Environ deux minutes.',
  intro_fine:
    'Il faut en reconnaître {needed} sur {n} pour valider le niveau — un seuil encore à l’essai. Ses mots ne reviendront que pour une vérification légère.',
  intro_top_down:
    'On commence par le niveau le plus haut sous le vôtre. Validé, il compte pour les niveaux d’en dessous ; sinon, on descend d’un niveau. Deux vérifications au plus par visite.',
  bands_label: 'Niveaux à vérifier',
  credited_mark: 'acquis',
  inferred_mark: 'déduit',
  missed_mark: 'pas encore',
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
  next_down_lead: 'On descend d’un niveau : {band}.',
  passed_split: '{sampled} reconnus dans la vérification, {inferred} déduits du résultat.',
  inferred_note:
    'Les mots déduits ({bands}) n’ont pas été vérifiés un à un : ils reviendront pour une vérification légère, et ceux que vous ne connaissez pas retourneront dans le parcours normal.',
  paused_title: 'Assez pour aujourd’hui',
  paused_lead:
    'Deux vérifications, c’est le maximum d’une visite. Reprenez avec {band} un autre jour : ce qui est fait est gardé.',
  stop_here: 'M’arrêter ici',
  back_lexique: 'Retour au lexique',
  back_day: 'Continuer',
  failed_open: 'La vérification n’a pas pu être ouverte. Réessayez dans un instant.',
  failed_send: 'Vos réponses ne sont pas parties. Elles sont toujours là — réessayez.',
  retry: 'Réessayer',
  none_title: 'Rien à vérifier',
  none_lead: 'Les niveaux sous le vôtre sont déjà acquis.',
  entry_cta: 'Vérifier mon vocabulaire (2 min)',
  entry_lead_placement:
    'Vous connaissez sans doute déjà une partie des mots des niveaux précédents. Une vérification rapide vous évite de les réapprendre.',
  entry_lead_lexique: 'Commencez par {band} : un niveau validé compte pour ceux d’en dessous.',
  entry_lead_resume: 'Votre vérification reprend à {band}.',
};

const EN: BandCheckCopy = {
  screen_aria: 'Vocabulary check',
  kicker: 'Vocabulary check · {band}',
  intro_title: 'Do you know these words already?',
  intro_lead:
    '{n} words from level {band}. For each one, pick the meaning — or “I don’t know”. About two minutes.',
  intro_fine:
    'You need {needed} of {n} to confirm the level — a threshold still on trial. Its words then come back only for a light check.',
  intro_top_down:
    'We start with the highest level below yours. If it is confirmed, the levels below count too; if not, we go down one level. Two checks at most per visit.',
  bands_label: 'Levels to check',
  credited_mark: 'known',
  inferred_mark: 'inferred',
  missed_mark: 'not yet',
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
  next_down_lead: 'One level down: {band}.',
  passed_split: '{sampled} recognised on the check, {inferred} inferred from the result.',
  inferred_note:
    'The inferred words ({bands}) were not checked one by one: they come back for a light check, and the ones you do not know return to the normal flow.',
  paused_title: 'That’s enough for today',
  paused_lead:
    'Two checks is the most for one visit. Carry on with {band} another day — what you have done is kept.',
  stop_here: 'Stop here',
  back_lexique: 'Back to the vocabulary',
  back_day: 'Continue',
  failed_open: 'The check could not be opened. Try again in a moment.',
  failed_send: 'Your answers did not go through. They are still here — try again.',
  retry: 'Try again',
  none_title: 'Nothing to check',
  none_lead: 'The levels below yours are already known.',
  entry_cta: 'Check my vocabulary (2 min)',
  entry_lead_placement:
    'You probably know some of the words from the earlier levels already. A quick check saves you learning them again.',
  entry_lead_lexique: 'Start with {band}: a confirmed level counts for the ones below it.',
  entry_lead_resume: 'Your check picks up at {band}.',
};

const DE: BandCheckCopy = {
  screen_aria: 'Wortschatz-Check',
  kicker: 'Wortschatz-Check · {band}',
  intro_title: 'Kennen Sie diese Wörter schon?',
  intro_lead:
    '{n} Wörter aus Niveau {band}. Wählen Sie bei jedem die Bedeutung — oder „Weiß ich nicht“. Etwa zwei Minuten.',
  intro_fine:
    'Sie brauchen {needed} von {n}, um das Niveau zu bestätigen — eine Schwelle, die noch erprobt wird. Seine Wörter kommen dann nur noch zu einer kurzen Kontrolle zurück.',
  intro_top_down:
    'Wir beginnen mit dem höchsten Niveau unter Ihrem. Ist es bestätigt, zählen die Niveaus darunter mit; sonst gehen wir ein Niveau tiefer. Höchstens zwei Checks pro Besuch.',
  bands_label: 'Niveaus zum Prüfen',
  credited_mark: 'bekannt',
  inferred_mark: 'abgeleitet',
  missed_mark: 'noch nicht',
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
  next_down_lead: 'Ein Niveau tiefer: {band}.',
  passed_split: '{sampled} im Check erkannt, {inferred} aus dem Ergebnis abgeleitet.',
  inferred_note:
    'Die abgeleiteten Wörter ({bands}) wurden nicht einzeln geprüft: Sie kommen zu einer kurzen Kontrolle zurück, und die, die Sie nicht kennen, gehen zurück in den normalen Ablauf.',
  paused_title: 'Genug für heute',
  paused_lead:
    'Zwei Checks sind das Maximum für einen Besuch. Machen Sie an einem anderen Tag mit {band} weiter — was Sie gemacht haben, bleibt erhalten.',
  stop_here: 'Hier aufhören',
  back_lexique: 'Zurück zum Wortschatz',
  back_day: 'Weiter',
  failed_open: 'Der Check konnte nicht geöffnet werden. Versuchen Sie es gleich noch einmal.',
  failed_send: 'Ihre Antworten wurden nicht gesendet. Sie sind noch da — versuchen Sie es erneut.',
  retry: 'Erneut versuchen',
  none_title: 'Nichts zu prüfen',
  none_lead: 'Die Niveaus unter Ihrem sind schon bekannt.',
  entry_cta: 'Meinen Wortschatz prüfen (2 Min.)',
  entry_lead_placement:
    'Einen Teil der Wörter aus den früheren Niveaus kennen Sie wahrscheinlich schon. Ein kurzer Check erspart Ihnen, sie neu zu lernen.',
  entry_lead_lexique: 'Beginnen Sie mit {band}: Ein bestätigtes Niveau zählt für die darunter.',
  entry_lead_resume: 'Ihr Check geht bei {band} weiter.',
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
