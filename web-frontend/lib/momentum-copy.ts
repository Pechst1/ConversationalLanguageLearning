/**
 * WP-S7 — momentum's chrome: the combo, Éclair, the grammar map and the
 * mastery rewards. It follows the one language rule (`lib/language-rule.ts`):
 * the learner's language up to A2, French from B1 — the caller passes the
 * resolved chrome language. Sentence case throughout. «Éclair» and
 * «La Forge» are place names: French in every language. Rule titles are
 * content and stay French.
 */

import type { ControlLanguage } from '@/types/daily-journey';

export type MapStage = 'ghost' | 'introduced' | 'proficient' | 'held';

export type MomentumCopy = {
  combo_label_none: string;
  combo_label_one: string;
  combo_label_many: string;
  recap_best_combo_one: string;
  recap_best_combo_many: string;
  eclair_name: string;
  eclair_action: string;
  eclair_hint: string;
  eclair_pair_label: string;
  eclair_best: string;
  eclair_best_none: string;
  eclair_start: string;
  eclair_starting: string;
  eclair_failed_start: string;
  eclair_time_left: string;
  eclair_score_live: string;
  eclair_question: string;
  eclair_done_title: string;
  eclair_done_sub: string;
  eclair_new_best: string;
  eclair_again: string;
  eclair_back: string;
  eclair_locked: string;
  eclair_saving: string;
  map_title: string;
  map_label: string;
  map_counts: string;
  map_band_label: string;
  map_rule_aria: string;
  map_due: string;
  map_tested_out: string;
  map_forge: string;
  map_open_page: string;
  map_close: string;
  map_coach: string;
  map_eclair_title: string;
  map_show_all: string;
  map_show_less: string;
  stages: Record<MapStage, string>;
  test_out_token: string;
  test_out_token_sub: string;
  seal_rings_one: string;
  seal_rings_many: string;
};

const EN: MomentumCopy = {
  combo_label_none: 'No run yet',
  combo_label_one: 'One right answer in a row',
  combo_label_many: '{n} right answers in a row',
  recap_best_combo_one: 'Best run: one right answer',
  recap_best_combo_many: 'Best run: {n} in a row',
  eclair_name: 'Éclair',
  eclair_action: 'Éclair · 60 s',
  eclair_hint: 'Tell two rules apart, as many as you can in one minute.',
  eclair_pair_label: '{a} or {b}',
  eclair_best: 'Best: {n}',
  eclair_best_none: 'Not played yet',
  eclair_start: 'Start',
  eclair_starting: 'Getting the sentences…',
  eclair_failed_start: 'Éclair could not start. Try again.',
  eclair_time_left: '{s} s left',
  eclair_score_live: '{n} right',
  eclair_question: 'Which sentence is right?',
  eclair_done_title: '{n} right in one minute.',
  eclair_done_sub: '{answered} answered. Your best for this pair: {best}.',
  eclair_new_best: 'New best for this pair',
  eclair_again: 'Play again',
  eclair_back: 'Back to the rules',
  eclair_locked: 'Éclair opens once you have met two rules that are easy to mix up.',
  eclair_saving: 'Saving…',
  map_title: 'Your grammar map',
  map_label: 'Grammar map: every rule as a shape',
  map_counts: '{held} held · {proficient} proficient · {introduced} introduced',
  map_band_label: 'Level {band}',
  map_rule_aria: '{title}: {stage}',
  map_due: 'Review due',
  map_tested_out: 'Tested out',
  map_forge: 'Forge this rule',
  map_open_page: 'Open the rule’s page',
  map_close: 'Close',
  map_coach: 'Taught by {name}',
  map_eclair_title: 'Éclair',
  map_show_all: 'All levels',
  map_show_less: 'Fewer levels',
  stages: {
    ghost: 'not met yet',
    introduced: 'introduced',
    proficient: 'proficient',
    held: 'held',
  },
  test_out_token: 'A rare token for this rule',
  test_out_token_sub: 'You tested it out. It joins your collection.',
  seal_rings_one: 'One ring: a rule held today',
  seal_rings_many: '{n} rings: rules held today',
};

const DE: MomentumCopy = {
  combo_label_none: 'Noch keine Serie',
  combo_label_one: 'Eine richtige Antwort in Folge',
  combo_label_many: '{n} richtige Antworten in Folge',
  recap_best_combo_one: 'Beste Serie: eine richtige Antwort',
  recap_best_combo_many: 'Beste Serie: {n} in Folge',
  eclair_name: 'Éclair',
  eclair_action: 'Éclair · 60 s',
  eclair_hint: 'Zwei Regeln auseinanderhalten, so viele wie möglich in einer Minute.',
  eclair_pair_label: '{a} oder {b}',
  eclair_best: 'Bestwert: {n}',
  eclair_best_none: 'Noch nicht gespielt',
  eclair_start: 'Los',
  eclair_starting: 'Die Sätze werden geholt …',
  eclair_failed_start: 'Éclair konnte nicht starten. Bitte noch einmal.',
  eclair_time_left: 'Noch {s} s',
  eclair_score_live: '{n} richtig',
  eclair_question: 'Welcher Satz ist richtig?',
  eclair_done_title: '{n} richtig in einer Minute.',
  eclair_done_sub: '{answered} beantwortet. Dein Bestwert für dieses Paar: {best}.',
  eclair_new_best: 'Neuer Bestwert für dieses Paar',
  eclair_again: 'Noch einmal',
  eclair_back: 'Zurück zu den Regeln',
  eclair_locked: 'Éclair öffnet sich, sobald du zwei leicht verwechselbare Regeln kennst.',
  eclair_saving: 'Wird gespeichert …',
  map_title: 'Deine Grammatikkarte',
  map_label: 'Grammatikkarte: jede Regel als Form',
  map_counts: '{held} gefestigt · {proficient} sicher · {introduced} eingeführt',
  map_band_label: 'Niveau {band}',
  map_rule_aria: '{title}: {stage}',
  map_due: 'Wiederholung fällig',
  map_tested_out: 'Direkt geprüft',
  map_forge: 'Diese Regel schmieden',
  map_open_page: 'Seite der Regel öffnen',
  map_close: 'Schließen',
  map_coach: 'Mit {name}',
  map_eclair_title: 'Éclair',
  map_show_all: 'Alle Niveaus',
  map_show_less: 'Weniger Niveaus',
  stages: {
    ghost: 'noch nicht kennengelernt',
    introduced: 'eingeführt',
    proficient: 'sicher',
    held: 'gefestigt',
  },
  test_out_token: 'Ein seltenes Zeichen für diese Regel',
  test_out_token_sub: 'Du hast sie direkt bestanden. Es kommt in deine Sammlung.',
  seal_rings_one: 'Ein Ring: eine Regel heute gefestigt',
  seal_rings_many: '{n} Ringe: Regeln heute gefestigt',
};

const FR: MomentumCopy = {
  combo_label_none: 'Pas encore de série',
  combo_label_one: 'Une bonne réponse d’affilée',
  combo_label_many: '{n} bonnes réponses d’affilée',
  recap_best_combo_one: 'Meilleure série : une bonne réponse',
  recap_best_combo_many: 'Meilleure série : {n} d’affilée',
  eclair_name: 'Éclair',
  eclair_action: 'Éclair · 60 s',
  eclair_hint: 'Distinguer deux règles, le plus de fois possible en une minute.',
  eclair_pair_label: '{a} ou {b}',
  eclair_best: 'Record : {n}',
  eclair_best_none: 'Pas encore joué',
  eclair_start: 'C’est parti',
  eclair_starting: 'Préparation des phrases…',
  eclair_failed_start: 'Éclair n’a pas pu démarrer. Réessayez.',
  eclair_time_left: 'Encore {s} s',
  eclair_score_live: '{n} justes',
  eclair_question: 'Quelle phrase est juste ?',
  eclair_done_title: '{n} justes en une minute.',
  eclair_done_sub: '{answered} réponses. Votre record pour cette paire : {best}.',
  eclair_new_best: 'Nouveau record pour cette paire',
  eclair_again: 'Rejouer',
  eclair_back: 'Retour aux règles',
  eclair_locked: 'Éclair s’ouvre quand vous avez découvert deux règles faciles à confondre.',
  eclair_saving: 'Enregistrement…',
  map_title: 'Votre carte de grammaire',
  map_label: 'Carte de grammaire : chaque règle est une forme',
  map_counts: '{held} tenues · {proficient} maîtrisées · {introduced} découvertes',
  map_band_label: 'Niveau {band}',
  map_rule_aria: '{title} : {stage}',
  map_due: 'Révision prévue',
  map_tested_out: 'Épreuve réussie',
  map_forge: 'Forger cette règle',
  map_open_page: 'Ouvrir la fiche',
  map_close: 'Fermer',
  map_coach: 'Avec {name}',
  map_eclair_title: 'Éclair',
  map_show_all: 'Tous les niveaux',
  map_show_less: 'Moins de niveaux',
  stages: {
    ghost: 'pas encore découverte',
    introduced: 'découverte',
    proficient: 'maîtrisée',
    held: 'tenue',
  },
  test_out_token: 'Un jeton rare pour cette règle',
  test_out_token_sub: 'Épreuve réussie. Il rejoint votre collection.',
  seal_rings_one: 'Un anneau : une règle tenue aujourd’hui',
  seal_rings_many: '{n} anneaux : des règles tenues aujourd’hui',
};

export const MOMENTUM_COPY: Record<ControlLanguage, MomentumCopy> = { en: EN, de: DE, fr: FR };

export function momentumCopy(language: ControlLanguage | string | null | undefined): MomentumCopy {
  const key = String(language || '').toLowerCase();
  return key === 'de' ? DE : key === 'fr' ? FR : EN;
}

export function fillMomentum(template: string, values: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (_match, name: string) => String(values[name] ?? ''));
}

/** «3 right answers in a row» — the combo's accessible name. */
export function comboLabel(copy: MomentumCopy, run: number): string {
  if (run <= 0) return copy.combo_label_none;
  if (run === 1) return copy.combo_label_one;
  return fillMomentum(copy.combo_label_many, { n: run });
}

export function bestComboLine(copy: MomentumCopy, best: number): string | null {
  if (!Number.isFinite(best) || best <= 0) return null;
  return best === 1 ? copy.recap_best_combo_one : fillMomentum(copy.recap_best_combo_many, { n: best });
}

export function sealRingsLabel(copy: MomentumCopy, rings: number): string | null {
  if (!Number.isFinite(rings) || rings <= 0) return null;
  return rings === 1 ? copy.seal_rings_one : fillMomentum(copy.seal_rings_many, { n: rings });
}
