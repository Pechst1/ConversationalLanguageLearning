/**
 * SPEED-3 — «Je connais déjà — vérifier»: the Règle step's short test-out.
 *
 * The forge's «Épreuve de la règle» in its three-item form (`short`): the
 * server picks and grades the items (`/atelier/forge/test-out`, then the
 * séance's `/attempts`), this module only turns a served item into something
 * the journey can draw and an answer into the attempt the forge expects. A
 * pass holds the unit; a fail sends the learner to the rule card, every answer
 * already counted as evidence.
 */

import type { AtelierForgeNext, AtelierForgeTestOutResult, AtelierForgeView } from '@/services/api';
import type { ControlLanguage } from '@/types/daily-journey';

/** How an item is answered here: tap an option, build from tiles, or type. */
export type TestOutInput =
  | { kind: 'choice'; options: string[] }
  | { kind: 'tiles'; tokens: string[] }
  | { kind: 'text'; sourceFr: string | null };

export type TestOutOutcome = 'running' | 'passed' | 'failed';

export type TestOutSubmission = {
  concept_id: number;
  round: AtelierForgeNext['round'];
  mode: string;
  exercise_id: string;
  answer_payload: Record<string, unknown>;
};

const strings = (value: unknown): string[] =>
  Array.isArray(value) ? value.filter((entry): entry is string => typeof entry === 'string' && entry.trim() !== '') : [];

const text = (value: unknown): string | null => (typeof value === 'string' && value.trim() ? value.trim() : null);

/** The forge view of a test-out response, or `null` (an empty `{}` is none). */
export function testOutView(forge: AtelierForgeView | Record<string, never> | null | undefined): AtelierForgeView | null {
  return forge && 'mode' in forge && forge.mode === 'test_out' ? (forge as AtelierForgeView) : null;
}

export function testOutInput(next: AtelierForgeNext): TestOutInput {
  const item = (next.item || {}) as Record<string, unknown>;
  if (next.round === 'recognize') {
    if (next.mode === 'word_bank') {
      const tokens = strings(item.tokens);
      if (tokens.length) return { kind: 'tiles', tokens };
    }
    const options = strings(item.choices).length ? strings(item.choices) : strings(item.labels);
    if (options.length) return { kind: 'choice', options };
  }
  return { kind: 'text', sourceFr: next.round === 'transform' ? text(item.source_fr) ?? text(item.source) : null };
}

/**
 * What the item asks, in the learner's language (`goal`), and the French line
 * it is about (`lineFr`: the sentence to judge or complete). A conversation
 * item's prompt is an instruction, not a French line: it is the goal.
 */
export function testOutPrompt(
  next: AtelierForgeNext,
  language: ControlLanguage,
): { goal: string | null; lineFr: string | null } {
  const item = (next.item || {}) as Record<string, unknown>;
  const l10n = (item.goal_l10n || {}) as Record<string, unknown>;
  const goal = text(l10n[language]) ?? text(item.goal_native);
  const prompt = text(item.prompt);
  if (next.round === 'recognize') {
    // A word bank's prompt is the generic «Build the sentence with the chips».
    return { goal, lineFr: next.mode === 'word_bank' ? null : prompt };
  }
  if (next.round === 'transform') return { goal: goal ?? text(item.instruction), lineFr: null };
  return { goal: goal ?? prompt ?? text(item.instruction), lineFr: null };
}

/** The attempt for one answer, as the forge séance's `/attempts` takes it. */
export function testOutSubmission(next: AtelierForgeNext, answer: string | string[]): TestOutSubmission {
  const itemId = String(next.item_id);
  let answerPayload: Record<string, unknown>;
  if (next.round === 'recognize' || next.round === 'transform') {
    answerPayload = { answers: { [itemId]: answer } };
  } else {
    answerPayload = { text: Array.isArray(answer) ? answer.join(' ') : answer };
  }
  return {
    concept_id: next.concept_id,
    round: next.round,
    mode: next.round === 'transform' ? 'rewrite' : next.mode,
    exercise_id: `forge:${next.concept_id}:${next.round}:${itemId}`,
    answer_payload: answerPayload,
  };
}

/** Is there an answer to send? */
export function testOutAnswerReady(input: TestOutInput, answer: string | string[]): boolean {
  if (input.kind === 'tiles') return Array.isArray(answer) && answer.length > 0;
  return typeof answer === 'string' && answer.trim().length > 0;
}

export function testOutOutcome(view: AtelierForgeView | null): TestOutOutcome {
  if (!view || !view.finished || !view.result) return 'running';
  return view.result.passed ? 'passed' : 'failed';
}

export function testOutResult(view: AtelierForgeView | null): AtelierForgeTestOutResult | null {
  return view?.finished ? view.result ?? null : null;
}

/** «2 / 3»: the item the learner is on, counted from one. */
export function testOutProgress(view: AtelierForgeView | null): { position: number; length: number } {
  const length = Math.max(1, Number(view?.length) || 3);
  const position = Math.min(length, (Number(view?.answered) || 0) + 1);
  return { position, length };
}

// ---------------------------------------------------------------------------
// Copy — the learner's language up to A2, French from B1 (WP-82's one rule)
// ---------------------------------------------------------------------------

export type RuleTestOutCopy = {
  action: string;
  starting: string;
  eyebrow: string;
  check: string;
  next: string;
  finish: string;
  right: string;
  not_quite: string;
  expected: string;
  passed_title: string;
  passed_body: string;
  failed: string;
  unavailable: string;
  cancel: string;
  answer_label: string;
  options_label: string;
  tiles_label: string;
  tiles_hint: string;
  tiles_remove: string;
  status_selected: string;
  status_correct: string;
  status_wrong: string;
};

const EN: RuleTestOutCopy = {
  action: 'Already know this? Check in 3 items',
  starting: 'Preparing three items…',
  eyebrow: 'Quick check · {i} of {n}',
  check: 'Check',
  next: 'Next',
  finish: 'See the result',
  right: 'Right',
  not_quite: 'Not quite',
  expected: 'Expected: {answer}',
  passed_title: 'You know it. The rule is yours.',
  passed_body: 'Held from today — no need to learn it again.',
  failed: 'Not quite yet — here is the rule. Your answers still count.',
  unavailable: 'The check could not start. Here is the rule.',
  cancel: 'Back to the rule',
  answer_label: 'Your answer',
  options_label: 'Options',
  tiles_label: 'Your sentence',
  tiles_hint: 'Tap the words in order',
  tiles_remove: 'Remove the last word',
  status_selected: 'selected',
  status_correct: 'right',
  status_wrong: 'not quite',
};

const DE: RuleTestOutCopy = {
  action: 'Kenne ich schon — kurz prüfen',
  starting: 'Drei Aufgaben werden vorbereitet …',
  eyebrow: 'Kurz prüfen · {i} von {n}',
  check: 'Prüfen',
  next: 'Weiter',
  finish: 'Zum Ergebnis',
  right: 'Richtig',
  not_quite: 'Nicht ganz',
  expected: 'Erwartet: {answer}',
  passed_title: 'Sitzt. Die Regel gehört dir.',
  passed_body: 'Ab heute gefestigt — du musst sie nicht neu lernen.',
  failed: 'Noch nicht ganz — hier ist die Regel. Deine Antworten zählen trotzdem.',
  unavailable: 'Die Prüfung konnte nicht starten. Hier ist die Regel.',
  cancel: 'Zurück zur Regel',
  answer_label: 'Deine Antwort',
  options_label: 'Antworten',
  tiles_label: 'Dein Satz',
  tiles_hint: 'Tippe die Wörter der Reihe nach an',
  tiles_remove: 'Letztes Wort entfernen',
  status_selected: 'ausgewählt',
  status_correct: 'richtig',
  status_wrong: 'nicht ganz',
};

const FR: RuleTestOutCopy = {
  action: 'Je connais déjà — vérifier',
  starting: 'Trois exercices en préparation…',
  eyebrow: 'Vérification · {i} sur {n}',
  check: 'Vérifier',
  next: 'Suivant',
  finish: 'Voir le résultat',
  right: 'Juste',
  not_quite: 'Pas tout à fait',
  expected: 'Attendu : {answer}',
  passed_title: 'Vous la connaissez. La règle est acquise.',
  passed_body: 'Tenue dès aujourd’hui — inutile de la réapprendre.',
  failed: 'Pas encore tout à fait — voici la règle. Vos réponses comptent quand même.',
  unavailable: 'La vérification n’a pas pu démarrer. Voici la règle.',
  cancel: 'Retour à la règle',
  answer_label: 'Votre réponse',
  options_label: 'Choix',
  tiles_label: 'Votre phrase',
  tiles_hint: 'Touchez les mots dans l’ordre',
  tiles_remove: 'Retirer le dernier mot',
  status_selected: 'choisi',
  status_correct: 'juste',
  status_wrong: 'pas tout à fait',
};

const TABLES: Record<ControlLanguage, RuleTestOutCopy> = { en: EN, de: DE, fr: FR };

export function ruleTestOutCopy(language: ControlLanguage | null | undefined): RuleTestOutCopy {
  return TABLES[(language ?? 'en') as ControlLanguage] ?? EN;
}
