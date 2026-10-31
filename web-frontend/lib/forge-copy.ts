/**
 * WP-S3 — La Forge's chrome: the «Test out» action, the rung counter and the
 * test-out result. Chrome follows the one language rule (`lib/language-rule.ts`):
 * the learner's language up to A2, French from B1 — the caller passes the
 * resolved `chromeLanguage`. Sentence case throughout.
 *
 * WP-S6: the surface's name («La Forge», a place name, French in every
 * language) and its action («Forge today's rule», owner decision 1), the
 * séance's one human count and the recap's per-rule progress.
 *
 * Owner, 2026-10-18: the staircase of shapes became a level («Niveau 3», a
 * tap explains it), the rule-change card and the step line are gone, the
 * épreuve is offered in the recap, and the new formats name themselves
 * («Trouve l'erreur», «Dictée», «Rafale»…).
 */

import type { ControlLanguage } from '@/types/daily-journey';

export type ForgeRungName = 'recognise' | 'discriminate' | 'build' | 'transform' | 'produce' | 'free_use';
export type ForgeStage = 'new' | 'introduced' | 'practising' | 'held';

export type ForgeCopy = {
  surface_name: string;
  surface_action: string;
  count_of: string;
  test_out_action: string;
  test_out_hint: string;
  test_out_starting: string;
  test_out_failed_start: string;
  test_out_eyebrow: string;
  /** The rule sheet's quiet way to the épreuve. */
  sheet_test_out: string;
  /** The rule's level (a rung, 1–6), its screen-reader name and what it means. */
  level: string;
  level_label: string;
  level_explain: string;
  /** The line under a right answer. */
  level_up: string;
  run_cheer: string;
  cheer_held: string;
  /** The formats that name themselves, and their one-line hint. */
  drill_typed: string;
  drill_dictation: string;
  drill_spot: string;
  drill_mine: string;
  drill_rafale: string;
  hint_typed: string;
  hint_dictation: string;
  hint_spot: string;
  /** #300: a stretch of several wrong words says how many ({n}). */
  hint_spot_n: string;
  hint_rafale: string;
  typed_placeholder: string;
  accents_label: string;
  listen: string;
  listen_slow: string;
  spot_edit_label: string;
  spot_undo: string;
  rafale_score: string;
  rafale_perfect: string;
  rafale_time: string;
  /** A missed judgement in the recap (#358): the call made, the right one, and why. */
  rafale_miss: string;
  rafale_said: string;
  rafale_why_right: string;
  rafale_why_wrong: string;
  /** The recap's épreuve offer. */
  offer_title: string;
  offer_sub: string;
  offer_action: string;
  result_passed_title: string;
  result_passed_sub: string;
  result_failed_title: string;
  result_failed_sub: string;
  back_to_rule: string;
  recap_title: string;
  recap_rules_label: string;
  recap_change: string;
  recap_unchanged: string;
  recap_held_today: string;
  recap_tested_out: string;
  recap_next_due: string;
  recap_due_today: string;
  recap_no_due: string;
  rungs: Record<ForgeRungName, string>;
  stages: Record<ForgeStage, string>;
};

const EN: ForgeCopy = {
  surface_name: 'La Forge',
  surface_action: 'Forge today’s rule',
  count_of: '{n} of {total}',
  test_out_action: 'Test out this rule',
  test_out_hint: 'Five items, one of them your own sentence. Pass, and the rule is yours.',
  test_out_starting: 'Preparing the test…',
  test_out_failed_start: 'The test could not start. Try again.',
  test_out_eyebrow: 'Test out',
  sheet_test_out: 'Know it already? Take the test',
  level: 'Level {n}',
  level_label: 'Your level on this rule: {n} of 6. Tap to see how it works.',
  level_explain: 'Your level on this rule, from 1 to 6. Right: up one. Wrong: down one, and the rule comes back soon.',
  level_up: 'Level {n} ↑',
  run_cheer: '{n} in a row',
  cheer_held: 'The rule is yours!',
  drill_typed: 'Type it',
  drill_dictation: 'Dictation',
  drill_spot: 'Find the mistake',
  drill_mine: 'Your sentence',
  drill_rafale: 'Rapid fire',
  hint_typed: 'Type the missing form.',
  hint_dictation: 'Listen, then build what you hear.',
  hint_spot: 'Tap the wrong word and fix it.',
  hint_spot_n: 'Tap the {n} wrong words and fix them.',
  hint_rafale: 'Right or wrong? Four sentences, as fast as you can.',
  typed_placeholder: 'Type here',
  accents_label: 'Accents',
  listen: 'Listen',
  listen_slow: 'Slower',
  spot_edit_label: 'Fix “{word}”',
  spot_undo: 'Undo',
  rafale_score: '{correct} of {total} right',
  rafale_perfect: 'Four out of four!',
  rafale_time: 'in {s} s',
  rafale_miss: 'Missed',
  rafale_said: 'You said “{said}” · the right call is “{right}”',
  rafale_why_right: 'Nothing to fix here: this sentence already follows the rule.',
  rafale_why_wrong: 'This sentence breaks the rule. The right form:',
  offer_title: 'Ready for the test?',
  offer_sub: '{n} questions. Pass, and the rule is yours.',
  offer_action: 'Take the test',
  result_passed_title: 'The rule is yours.',
  result_passed_sub: '{correct} of {total} right, your own sentence included. It counts as held from today.',
  result_failed_title: 'Not yet. The forge takes it from here.',
  result_failed_sub: '{correct} of {total} right. Your practice picks up at level {level}.',
  back_to_rule: 'Back to the rule',
  recap_title: 'Today’s rules, forged.',
  recap_rules_label: 'Your rules today',
  recap_change: '{from} → {to}',
  recap_unchanged: 'Still {stage}',
  recap_held_today: 'Held from today',
  recap_tested_out: 'Tested out: held',
  recap_next_due: 'Next review {date}',
  recap_due_today: 'Next review today',
  recap_no_due: 'No review planned yet',
  rungs: {
    recognise: 'recognise',
    discriminate: 'tell apart',
    build: 'build',
    transform: 'transform',
    produce: 'produce',
    free_use: 'free use',
  },
  stages: {
    new: 'new',
    introduced: 'introduced',
    practising: 'practising',
    held: 'held',
  },
};

const DE: ForgeCopy = {
  surface_name: 'La Forge',
  surface_action: 'Regel des Tages schmieden',
  count_of: '{n} von {total}',
  test_out_action: 'Diese Regel direkt prüfen',
  test_out_hint: 'Fünf Aufgaben, eine davon ein eigener Satz. Bestanden, und die Regel sitzt.',
  test_out_starting: 'Die Prüfung wird vorbereitet …',
  test_out_failed_start: 'Die Prüfung konnte nicht starten. Bitte noch einmal.',
  test_out_eyebrow: 'Regelprüfung',
  sheet_test_out: 'Kannst du sie schon? Direkt prüfen',
  level: 'Stufe {n}',
  level_label: 'Deine Stufe bei dieser Regel: {n} von 6. Tippen für die Erklärung.',
  level_explain: 'Deine Stufe bei dieser Regel, von 1 bis 6. Richtig: eine hoch. Falsch: eine runter, und die Regel kommt bald wieder.',
  level_up: 'Stufe {n} ↑',
  run_cheer: '{n} in Folge',
  cheer_held: 'Die Regel sitzt!',
  drill_typed: 'Eintippen',
  drill_dictation: 'Diktat',
  drill_spot: 'Finde den Fehler',
  drill_mine: 'Dein Satz',
  drill_rafale: 'Schnellrunde',
  hint_typed: 'Tipp die fehlende Form ein.',
  hint_dictation: 'Hör zu und bau, was du hörst.',
  hint_spot: 'Tipp auf das falsche Wort und korrigiere es.',
  hint_spot_n: 'Tipp auf die {n} falschen Wörter und korrigiere sie.',
  hint_rafale: 'Richtig oder falsch? Vier Sätze, so schnell du kannst.',
  typed_placeholder: 'Hier eintippen',
  accents_label: 'Akzente',
  listen: 'Anhören',
  listen_slow: 'Langsamer',
  spot_edit_label: '„{word}“ korrigieren',
  spot_undo: 'Zurück',
  rafale_score: '{correct} von {total} richtig',
  rafale_perfect: 'Vier von vier!',
  rafale_time: 'in {s} s',
  rafale_miss: 'Verpasst',
  rafale_said: 'Du hast „{said}“ gewählt · richtig ist „{right}“',
  rafale_why_right: 'Hier ist nichts zu korrigieren: Der Satz folgt der Regel schon.',
  rafale_why_wrong: 'Dieser Satz verstößt gegen die Regel. Richtig heißt es:',
  offer_title: 'Bereit für die Prüfung?',
  offer_sub: '{n} Fragen. Bestanden, und die Regel sitzt.',
  offer_action: 'Prüfung starten',
  result_passed_title: 'Die Regel sitzt.',
  result_passed_sub: '{correct} von {total} richtig, der eigene Satz inklusive. Ab heute gilt sie als gefestigt.',
  result_failed_title: 'Noch nicht. Die Schmiede übernimmt.',
  result_failed_sub: '{correct} von {total} richtig. Dein Training geht auf Stufe {level} weiter.',
  back_to_rule: 'Zurück zur Regel',
  recap_title: 'Die Regeln von heute sind geschmiedet.',
  recap_rules_label: 'Deine Regeln heute',
  recap_change: '{from} → {to}',
  recap_unchanged: 'Weiterhin {stage}',
  recap_held_today: 'Ab heute gefestigt',
  recap_tested_out: 'Direkt geprüft: gefestigt',
  recap_next_due: 'Nächste Wiederholung {date}',
  recap_due_today: 'Nächste Wiederholung heute',
  recap_no_due: 'Noch keine Wiederholung geplant',
  rungs: {
    recognise: 'erkennen',
    discriminate: 'unterscheiden',
    build: 'bauen',
    transform: 'umformen',
    produce: 'bilden',
    free_use: 'frei anwenden',
  },
  stages: {
    new: 'neu',
    introduced: 'eingeführt',
    practising: 'in Übung',
    held: 'gefestigt',
  },
};

const FR: ForgeCopy = {
  surface_name: 'La Forge',
  surface_action: 'Forger la règle du jour',
  count_of: '{n} sur {total}',
  test_out_action: 'Passer l’épreuve de la règle',
  test_out_hint: 'Cinq exercices, dont une phrase à toi. Réussie, la règle est acquise.',
  test_out_starting: 'Préparation de l’épreuve…',
  test_out_failed_start: 'L’épreuve n’a pas pu démarrer. Réessaie.',
  test_out_eyebrow: 'Épreuve de la règle',
  sheet_test_out: 'Tu la connais déjà ? Passe l’épreuve',
  level: 'Niveau {n}',
  level_label: 'Ton niveau sur cette règle : {n} sur 6. Touche pour l’explication.',
  level_explain: 'Ton niveau sur cette règle, de 1 à 6. Juste : un de plus. Faux : un de moins, et la règle revient bientôt.',
  level_up: 'Niveau {n} ↑',
  run_cheer: '{n} d’affilée',
  cheer_held: 'Règle acquise !',
  drill_typed: 'Tape la forme',
  drill_dictation: 'Dictée',
  drill_spot: 'Trouve l’erreur',
  drill_mine: 'Ta phrase',
  drill_rafale: 'Rafale',
  hint_typed: 'Tape la forme qui manque.',
  hint_dictation: 'Écoute, puis construis ce que tu entends.',
  hint_spot: 'Touche le mot faux et corrige-le.',
  hint_spot_n: 'Touche les {n} mots faux et corrige-les.',
  hint_rafale: 'Juste ou faux ? Quatre phrases, le plus vite possible.',
  typed_placeholder: 'Tape ici',
  accents_label: 'Accents',
  listen: 'Écouter',
  listen_slow: 'Plus lent',
  spot_edit_label: 'Corriger « {word} »',
  spot_undo: 'Annuler',
  rafale_score: '{correct} sur {total}',
  rafale_perfect: 'Quatre sur quatre !',
  rafale_time: 'en {s} s',
  rafale_miss: 'Manquée',
  rafale_said: 'Tu as dit « {said} » · la bonne réponse est « {right} »',
  rafale_why_right: 'Rien à corriger ici : la phrase suit déjà la règle.',
  rafale_why_wrong: 'Cette phrase enfreint la règle. La bonne forme :',
  offer_title: 'Prêt pour l’épreuve ?',
  offer_sub: '{n} questions. Réussie, la règle est acquise.',
  offer_action: 'Passer l’épreuve',
  result_passed_title: 'La règle est acquise.',
  result_passed_sub: '{correct} sur {total}, ta phrase comprise. Elle est tenue dès aujourd’hui.',
  result_failed_title: 'Pas encore. La forge prend le relais.',
  result_failed_sub: '{correct} sur {total}. Ton entraînement reprend au niveau {level}.',
  back_to_rule: 'Retour à la règle',
  recap_title: 'Les règles du jour sont forgées.',
  recap_rules_label: 'Tes règles du jour',
  recap_change: '{from} → {to}',
  recap_unchanged: 'Toujours {stage}',
  recap_held_today: 'Tenue dès aujourd’hui',
  recap_tested_out: 'Épreuve réussie : tenue',
  recap_next_due: 'Prochaine révision {date}',
  recap_due_today: 'Prochaine révision aujourd’hui',
  recap_no_due: 'Pas encore de révision prévue',
  rungs: {
    recognise: 'reconnaître',
    discriminate: 'distinguer',
    build: 'construire',
    transform: 'transformer',
    produce: 'produire',
    free_use: 'emploi libre',
  },
  stages: {
    new: 'nouvelle',
    introduced: 'découverte',
    practising: 'en route',
    held: 'tenue',
  },
};

export const FORGE_COPY: Record<ControlLanguage, ForgeCopy> = { en: EN, de: DE, fr: FR };

export function forgeCopy(language: ControlLanguage | string | null | undefined): ForgeCopy {
  const key = String(language || '').toLowerCase();
  return key === 'de' ? DE : key === 'fr' ? FR : EN;
}

/** «{n}» style placeholders. */
export function fillForge(template: string, values: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (_match, name: string) => String(values[name] ?? ''));
}

/** The spot hint for an item that needs ``fixWords`` words fixed (one: the plain hint). */
export function spotHint(copy: ForgeCopy, fixWords: unknown): string {
  const n = Number(fixWords);
  return Number.isInteger(n) && n > 1 ? fillForge(copy.hint_spot_n, { n }) : copy.hint_spot;
}

export function forgeRungLabel(copy: ForgeCopy, rungName: string | null | undefined): string {
  const key = String(rungName || '') as ForgeRungName;
  return copy.rungs[key] || copy.rungs.recognise;
}

/**
 * A life stage's word, the grammar map's own (`lib/grammar-stages.ts`): a rule
 * not held is never «mastered» beside an épreuve that would make it so.
 * Unknown → «new».
 */
export function forgeStageLabel(copy: ForgeCopy, stage: string | null | undefined): string {
  const key = String(stage || '') as ForgeStage;
  return copy.stages[key] || copy.stages.new;
}
