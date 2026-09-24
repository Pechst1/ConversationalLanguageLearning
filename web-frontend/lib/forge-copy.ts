/**
 * WP-S3 — La Forge's chrome: the «Test out» action, the rung counter and the
 * test-out result. Chrome follows the one language rule (`lib/language-rule.ts`):
 * the learner's language up to A2, French from B1 — the caller passes the
 * resolved `chromeLanguage`. Sentence case throughout; WP-S6 redesigns it.
 */

import type { ControlLanguage } from '@/types/daily-journey';

export type ForgeRungName = 'recognise' | 'discriminate' | 'build' | 'transform' | 'produce' | 'free_use';

export type ForgeCopy = {
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
  rungs: Record<ForgeRungName, string>;
};

const EN: ForgeCopy = {
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
  rungs: {
    recognise: 'recognise',
    discriminate: 'tell apart',
    build: 'build',
    transform: 'transform',
    produce: 'produce',
    free_use: 'free use',
  },
};

const DE: ForgeCopy = {
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
  rungs: {
    recognise: 'erkennen',
    discriminate: 'unterscheiden',
    build: 'bauen',
    transform: 'umformen',
    produce: 'bilden',
    free_use: 'frei anwenden',
  },
};

const FR: ForgeCopy = {
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
  rungs: {
    recognise: 'reconnaître',
    discriminate: 'distinguer',
    build: 'construire',
    transform: 'transformer',
    produce: 'produire',
    free_use: 'emploi libre',
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
