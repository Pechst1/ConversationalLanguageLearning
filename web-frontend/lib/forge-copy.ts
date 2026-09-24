/**
 * WP-S3 — La Forge's chrome: the «Test out» action, the rung counter and the
 * test-out result. Chrome follows the one language rule (`lib/language-rule.ts`):
 * the learner's language up to A2, French from B1 — the caller passes the
 * resolved `chromeLanguage`. Sentence case throughout.
 *
 * WP-S6: the surface's name («La Forge», a place name, French in every
 * language) and its action («Forge today's rule», owner decision 1), the
 * séance's one human count, the rule's staircase, the rule-change card and
 * the recap's per-rule progress.
 */

import type { ControlLanguage } from '@/types/daily-journey';

export type ForgeRungName = 'recognise' | 'discriminate' | 'build' | 'transform' | 'produce' | 'free_use';
export type ForgeStage = 'new' | 'introduced' | 'practising' | 'held';

export type ForgeCopy = {
  surface_name: string;
  surface_action: string;
  count_of: string;
  stair_label: string;
  next_rule: string;
  coach_label: string;
  test_out_action: string;
  test_out_hint: string;
  test_out_starting: string;
  test_out_failed_start: string;
  test_out_eyebrow: string;
  step_of: string;
  reprise: string;
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
  stair_label: 'The rule’s staircase: step {n} of 6, {rung}',
  next_rule: 'Next rule',
  coach_label: 'With {name}',
  test_out_action: 'Test out this rule',
  test_out_hint: 'Five items, one of them your own sentence. Pass, and the rule is yours.',
  test_out_starting: 'Preparing the test…',
  test_out_failed_start: 'The test could not start. Try again.',
  test_out_eyebrow: 'Test out',
  step_of: 'Step {n} of 6 · {rung}',
  reprise: 'Again, in a new sentence',
  result_passed_title: 'The rule is yours.',
  result_passed_sub: '{correct} of {total} right, your own sentence included. It counts as held from today.',
  result_failed_title: 'Not yet. The forge takes it from here.',
  result_failed_sub: '{correct} of {total} right. Your practice starts at the “{rung}” step.',
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
    practising: 'proficient',
    held: 'held',
  },
};

const DE: ForgeCopy = {
  surface_name: 'La Forge',
  surface_action: 'Regel des Tages schmieden',
  count_of: '{n} von {total}',
  stair_label: 'Die Treppe der Regel: Stufe {n} von 6, {rung}',
  next_rule: 'Nächste Regel',
  coach_label: 'Mit {name}',
  test_out_action: 'Diese Regel direkt prüfen',
  test_out_hint: 'Fünf Aufgaben, eine davon ein eigener Satz. Bestanden, und die Regel sitzt.',
  test_out_starting: 'Die Prüfung wird vorbereitet …',
  test_out_failed_start: 'Die Prüfung konnte nicht starten. Bitte noch einmal.',
  test_out_eyebrow: 'Regelprüfung',
  step_of: 'Stufe {n} von 6 · {rung}',
  reprise: 'Noch einmal, in einem neuen Satz',
  result_passed_title: 'Die Regel sitzt.',
  result_passed_sub: '{correct} von {total} richtig, der eigene Satz inklusive. Ab heute gilt sie als gefestigt.',
  result_failed_title: 'Noch nicht. Die Schmiede übernimmt.',
  result_failed_sub: '{correct} von {total} richtig. Dein Training beginnt auf der Stufe „{rung}“.',
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
    practising: 'sicher',
    held: 'gefestigt',
  },
};

const FR: ForgeCopy = {
  surface_name: 'La Forge',
  surface_action: 'Forger la règle du jour',
  count_of: '{n} sur {total}',
  stair_label: 'L’escalier de la règle : marche {n} sur 6, {rung}',
  next_rule: 'Règle suivante',
  coach_label: 'Avec {name}',
  test_out_action: 'Passer l’épreuve de la règle',
  test_out_hint: 'Cinq exercices, dont une phrase à vous. Réussie, la règle est acquise.',
  test_out_starting: 'Préparation de l’épreuve…',
  test_out_failed_start: 'L’épreuve n’a pas pu démarrer. Réessayez.',
  test_out_eyebrow: 'Épreuve de la règle',
  step_of: 'Marche {n} sur 6 · {rung}',
  reprise: 'Encore une fois, dans une nouvelle phrase',
  result_passed_title: 'La règle est acquise.',
  result_passed_sub: '{correct} sur {total}, votre phrase comprise. Elle est tenue dès aujourd’hui.',
  result_failed_title: 'Pas encore. La forge prend le relais.',
  result_failed_sub: '{correct} sur {total}. Votre entraînement commence à la marche « {rung} ».',
  back_to_rule: 'Retour à la règle',
  recap_title: 'Les règles du jour sont forgées.',
  recap_rules_label: 'Vos règles du jour',
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
    practising: 'maîtrisée',
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

export function forgeRungLabel(copy: ForgeCopy, rungName: string | null | undefined): string {
  const key = String(rungName || '') as ForgeRungName;
  return copy.rungs[key] || copy.rungs.recognise;
}

/** A life stage's word (`practising` reads «proficient»); unknown → «new». */
export function forgeStageLabel(copy: ForgeCopy, stage: string | null | undefined): string {
  const key = String(stage || '') as ForgeStage;
  return copy.stages[key] || copy.stages.new;
}
