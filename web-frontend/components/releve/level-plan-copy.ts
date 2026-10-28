/**
 * The level plan's words (Fortschritt «Le cours», 2026-10-24).
 *
 * Owner: «we always know exactly at which level the learner is currently so
 * that he also knows that exactly and knows what he has to do and how much
 * time he has to invest to advance further». The plan (`GET /progress/level`)
 * carries the numbers; this table says them.
 *
 * Chrome, so the one language rule holds (WP-82): the learner's language up to
 * A2, French from B1. German says du. Every table has the same keys and the
 * same `{placeholders}` (`level-plan.test.js` proves it); `_one` / `_many`
 * pairs are picked with `plural`. The stage words («held», «gefestigt»,
 * «tenue») and the missing evidence are `lib/grammar-stages.ts`'s, so the plan
 * names a rule's state exactly as the notebook does.
 */

import { normalizeControlLanguage } from '@/lib/atelier-v2-copy';
import type { ControlLanguage } from '@/types/daily-journey';

export type LevelPlanCopy = {
  locale: string;
  // Where you are
  percent_aria: string;
  percent_rule: string;
  next_band: string;
  top_band: string;
  evidence: string;
  ladder_label: string;
  ladder_passed: string;
  ladder_credited: string;
  ladder_start: string;
  ladder_current: string;
  ladder_ahead: string;
  ladder_goal: string;
  // What is left
  needs_title: string;
  needs_title_top: string;
  so_far: string;
  rules_label: string;
  words_label: string;
  count_value: string;
  rules_met: string;
  rules_not_met_one: string;
  rules_not_met_many: string;
  words_met: string;
  words_way_one: string;
  words_way_many: string;
  words_new_one: string;
  words_new_many: string;
  words_reading_one: string;
  words_reading_many: string;
  words_no_list: string;
  test_label: string;
  test_locked: string;
  test_ready_story: string;
  test_ready: string;
  test_failed_dated: string;
  test_failed: string;
  test_passed: string;
  test_credited: string;
  today_one: string;
  today_many: string;
  today_more: string;
  today_separator: string;
  // How long
  time_title: string;
  time_measured: string;
  time_plan: string;
  time_capped: string;
  time_none: string;
  time_unverified: string;
  time_basis_measured: string;
  time_basis_plan: string;
  time_earliest: string;
  time_cost_measured: string;
  time_cost_plan: string;
  hours_range: string;
  hours_one: string;
  hours_many: string;
  days_one: string;
  days_many: string;
  on_days_one: string;
  on_days_many: string;
  time_pace: string;
  time_change: string;
  goal_line: string;
  // Time put in
  invested_title: string;
  invested_since: string;
  invested_start: string;
  invested_parts: string;
  invested_recent: string;
  invested_none: string;
  invested_floor: string;
  duration_minutes: string;
  duration_hours: string;
  duration_hours_minutes: string;
  // Rule by rule
  list_title: string;
  row_held: string;
  row_owed: string;
  row_earliest: string;
  row_new_dated: string;
  row_new: string;
  // Each criterion on its own
  skills_title: string;
  skills_words: string;
  skills_rules: string;
  skills_working: string;
  skills_working_start: string;
  skills_list_ends: string;
  skills_all: string;
  skills_note: string;
};

const EN: LevelPlanCopy = {
  locale: 'en-GB',
  percent_aria: 'Level {band}: {percent} %',
  percent_rule: 'Covering its rules and words takes {band} to 90 %; its level test adds the last 10 %.',
  next_band: 'Next level: {band}',
  top_band: 'The top of the ladder.',
  evidence: 'L’Atelier measures your level after {required} marked answers within two weeks; {counted} so far.',
  ladder_label: 'Your levels',
  ladder_passed: 'passed',
  ladder_credited: 'credited',
  ladder_start: 'below your starting level',
  ladder_current: 'you are here',
  ladder_ahead: 'ahead',
  ladder_goal: 'goal',
  needs_title: 'To move up to {band}',
  needs_title_top: 'To complete {band}',
  so_far: 'So far in the app:',
  rules_label: 'Rules held',
  words_label: 'Words known',
  count_value: '{have} of {need} needed · {total} in the level',
  rules_met: 'Enough rules held for {band}.',
  rules_not_met_one: '{n} not met yet',
  rules_not_met_many: '{n} not met yet',
  words_met: 'Enough words known for {band}.',
  words_way_one: '{n} more is on its way in your reviews.',
  words_way_many: '{n} more are on their way in your reviews.',
  words_new_one: '{n} still to meet: about {days} at {per_day} new words a day.',
  words_new_many: '{n} still to meet: about {days} at {per_day} new words a day.',
  words_reading_one: '{n} known from reading.',
  words_reading_many: '{n} known from reading.',
  words_no_list: 'Above B1 the core word list ends: the rules and the level test decide.',
  test_label: 'Level test',
  test_locked: 'once the rules and the words are covered',
  test_ready_story: 'ready: it comes up in the story',
  test_ready: 'ready: everything it asks for is covered',
  test_failed_dated: 'retake from {date}',
  test_failed: 'retake after a week of consolidation',
  test_passed: 'passed',
  test_credited: 'credited',
  today_one: 'Today 1 rule can take a step towards “held”: {names}.',
  today_many: 'Today {n} rules can take a step towards “held”: {names}.',
  today_more: 'and {n} more',
  today_separator: '; ',
  time_title: 'How long',
  time_measured: 'Estimate: {low} to {high} days at your pace, between {from} and {to}.',
  time_plan: 'Estimate from your plan: {low} to {high} days, between {from} and {to}.',
  time_capped: 'Estimate: more than two years at this pace.',
  time_none: 'No estimate yet.',
  time_unverified: 'A time to the next level comes once L’Atelier has measured yours.',
  time_basis_measured: 'Measured on your last two weeks.',
  time_basis_plan: 'From {required} active days on, it is measured on your own practice ({active} so far).',
  time_earliest:
    'Not before {date}, however much you practise: a rule is held after two unaided uses a week apart and one successful review two weeks after you met it.',
  time_cost_measured: 'At your {minutes} minutes a day (your average over two weeks), that is about {hours} of practice.',
  time_cost_plan: 'At the {minutes} minutes a day your plan takes, that is about {hours} of practice.',
  hours_range: '{low} to {high} hours',
  hours_one: '{n} hour',
  hours_many: '{n} hours',
  days_one: '{n} day',
  days_many: '{n} days',
  on_days_one: 'on {n} day',
  on_days_many: 'on {n} days',
  time_pace: 'Your pace: {pace} · {words} new words a day · {rules} new rules a week',
  time_change: 'Change pace',
  goal_line: 'Your goal {band}: {words} words and {rules} rules to go, in {eta} at your pace.',
  invested_title: 'Time put in',
  invested_since: '{time} at {band} since {date}, {days}.',
  invested_start: '{time} since you started, {days}.',
  invested_parts: 'Scenes {scenes} · La Forge {forge} · Words {words}',
  invested_recent: 'Lately: {minutes} minutes a day on average.',
  invested_none: 'No practice time measured yet at {band}.',
  invested_floor: 'Time in Le Courrier and Le Papier is not counted yet.',
  duration_minutes: '{m} min',
  duration_hours: '{h} h',
  duration_hours_minutes: '{h} h {m} min',
  list_title: 'The rules of {band} ({n})',
  row_held: 'held since {date}',
  row_owed: 'can take a step today',
  row_earliest: 'held on {date} at the earliest',
  row_new_dated: 'not met yet · arrives around {date} at your pace',
  row_new: 'not met yet',
  skills_title: 'Rules and words, each on its own',
  skills_words: 'Words',
  skills_rules: 'Rules',
  skills_working: '{what}: {covered} covered, {percent} % of {working}.',
  skills_working_start: '{what}: {percent} % of {working}.',
  skills_list_ends: '{what}: {covered} covered; the core word list ends there.',
  skills_all: '{what}: covered up to {covered}.',
  skills_note: 'Your level moves up once both are covered and its level test is passed.',
};

const DE: LevelPlanCopy = {
  locale: 'de-DE',
  percent_aria: 'Niveau {band}: {percent} %',
  percent_rule: 'Mit seinen Regeln und Wörtern kommst du bei {band} auf 90 %; die Niveauprüfung bringt die letzten 10 %.',
  next_band: 'Nächstes Niveau: {band}',
  top_band: 'Das Ende der Leiter.',
  evidence: 'L’Atelier misst dein Niveau nach {required} korrigierten Antworten innerhalb von zwei Wochen; bisher {counted}.',
  ladder_label: 'Deine Niveaus',
  ladder_passed: 'bestanden',
  ladder_credited: 'anerkannt',
  ladder_start: 'unter deinem Startniveau',
  ladder_current: 'du bist hier',
  ladder_ahead: 'kommt noch',
  ladder_goal: 'Ziel',
  needs_title: 'Was dir bis {band} noch fehlt',
  needs_title_top: 'Was dir für {band} noch fehlt',
  so_far: 'Bisher in der App:',
  rules_label: 'Gefestigte Regeln',
  words_label: 'Bekannte Wörter',
  count_value: '{have} von {need} nötigen · {total} im Niveau',
  rules_met: 'Genug Regeln gefestigt für {band}.',
  rules_not_met_one: '{n} noch nicht kennengelernt',
  rules_not_met_many: '{n} noch nicht kennengelernt',
  words_met: 'Genug Wörter bekannt für {band}.',
  words_way_one: '{n} weiteres ist in deinen Wiederholungen unterwegs.',
  words_way_many: '{n} weitere sind in deinen Wiederholungen unterwegs.',
  words_new_one: '{n} lernst du noch neu kennen: etwa {days} bei {per_day} neuen Wörtern am Tag.',
  words_new_many: '{n} lernst du noch neu kennen: etwa {days} bei {per_day} neuen Wörtern am Tag.',
  words_reading_one: '{n} kennst du vom Lesen.',
  words_reading_many: '{n} kennst du vom Lesen.',
  words_no_list: 'Ab B2 endet die Grundwortliste: Es entscheiden die Regeln und die Niveauprüfung.',
  test_label: 'Niveauprüfung',
  test_locked: 'sobald Regeln und Wörter abgedeckt sind',
  test_ready_story: 'bereit: sie kommt in der Geschichte',
  test_ready: 'bereit: alles, was sie verlangt, ist abgedeckt',
  test_failed_dated: 'Wiederholung ab dem {date}',
  test_failed: 'Wiederholung nach einer Woche Festigung',
  test_passed: 'bestanden',
  test_credited: 'anerkannt',
  today_one: 'Heute kann 1 Regel einen Schritt Richtung „gefestigt“ machen: {names}.',
  today_many: 'Heute können {n} Regeln einen Schritt Richtung „gefestigt“ machen: {names}.',
  today_more: 'und {n} weitere',
  today_separator: '; ',
  time_title: 'Wie lange',
  time_measured: 'Schätzung: {low} bis {high} Tage bei deinem Tempo, zwischen dem {from} und dem {to}.',
  time_plan: 'Schätzung nach deinem Plan: {low} bis {high} Tage, zwischen dem {from} und dem {to}.',
  time_capped: 'Schätzung: mehr als zwei Jahre bei diesem Tempo.',
  time_none: 'Noch keine Schätzung.',
  time_unverified: 'Eine Zeit bis zur nächsten Stufe gibt es, sobald L’Atelier deine Stufe gemessen hat.',
  time_basis_measured: 'Gemessen an deinen letzten zwei Wochen.',
  time_basis_plan: 'Ab {required} aktiven Tagen wird sie an deiner eigenen Übung gemessen (bisher {active}).',
  time_earliest:
    'Nicht vor dem {date}, egal wie viel du übst: Eine Regel ist gefestigt nach zwei freien Verwendungen im Abstand von einer Woche und einer gelungenen Wiederholung zwei Wochen nach dem Kennenlernen.',
  time_cost_measured:
    'Bei deinen {minutes} Minuten am Tag (dein Schnitt der letzten zwei Wochen) sind das etwa {hours} Übung.',
  time_cost_plan: 'Bei den {minutes} Minuten am Tag, die dein Plan braucht, sind das etwa {hours} Übung.',
  hours_range: '{low} bis {high} Stunden',
  hours_one: '{n} Stunde',
  hours_many: '{n} Stunden',
  days_one: '{n} Tag',
  days_many: '{n} Tage',
  on_days_one: 'an {n} Tag',
  on_days_many: 'an {n} Tagen',
  time_pace: 'Dein Tempo: {pace} · {words} neue Wörter am Tag · {rules} neue Regeln pro Woche',
  time_change: 'Tempo ändern',
  goal_line: 'Dein Ziel {band}: noch {words} Wörter und {rules} Regeln, bei deinem Tempo in {eta}.',
  invested_title: 'Bisher investiert',
  invested_since: '{time} bei {band} seit dem {date}, {days}.',
  invested_start: '{time} seit deinem Start, {days}.',
  invested_parts: 'Szenen {scenes} · La Forge {forge} · Wörter {words}',
  invested_recent: 'Zuletzt im Schnitt {minutes} Minuten am Tag.',
  invested_none: 'Bei {band} ist noch keine Übungszeit gemessen.',
  invested_floor: 'Zeit im Courrier und in Le Papier wird noch nicht gezählt.',
  duration_minutes: '{m} Min.',
  duration_hours: '{h} Std.',
  duration_hours_minutes: '{h} Std. {m} Min.',
  list_title: 'Die Regeln von {band} ({n})',
  row_held: 'gefestigt seit dem {date}',
  row_owed: 'kann heute einen Schritt machen',
  row_earliest: 'frühestens am {date} gefestigt',
  row_new_dated: 'noch nicht kennengelernt · kommt bei deinem Tempo etwa ab dem {date}',
  row_new: 'noch nicht kennengelernt',
  skills_title: 'Regeln und Wörter, jedes für sich',
  skills_words: 'Wörter',
  skills_rules: 'Regeln',
  skills_working: '{what}: {covered} abgedeckt, {percent} % von {working}.',
  skills_working_start: '{what}: {percent} % von {working}.',
  skills_list_ends: '{what}: {covered} abgedeckt; dort endet die Grundwortliste.',
  skills_all: '{what}: bis {covered} abgedeckt.',
  skills_note: 'Dein Niveau steigt, sobald beides abgedeckt und die Niveauprüfung bestanden ist.',
};

const FR: LevelPlanCopy = {
  locale: 'fr-FR',
  percent_aria: 'Niveau {band} : {percent} %',
  percent_rule: 'Couvrir ses règles et ses mots mène {band} à 90 % ; l’épreuve donne les 10 % restants.',
  next_band: 'Niveau suivant : {band}',
  top_band: 'Le haut de l’échelle.',
  evidence: 'L’Atelier mesure ton niveau après {required} réponses corrigées en deux semaines ; {counted} pour l’instant.',
  ladder_label: 'Tes niveaux',
  ladder_passed: 'réussi',
  ladder_credited: 'validé',
  ladder_start: 'sous ton niveau de départ',
  ladder_current: 'tu es ici',
  ladder_ahead: 'à venir',
  ladder_goal: 'objectif',
  needs_title: 'Pour passer à {band}',
  needs_title_top: 'Pour boucler {band}',
  so_far: 'Dans l’application, pour l’instant :',
  rules_label: 'Règles tenues',
  words_label: 'Mots connus',
  count_value: '{have} sur {need} nécessaires · {total} au niveau',
  rules_met: 'Assez de règles tenues pour {band}.',
  rules_not_met_one: '{n} pas encore découverte',
  rules_not_met_many: '{n} pas encore découvertes',
  words_met: 'Assez de mots connus pour {band}.',
  words_way_one: '{n} de plus est en route dans tes révisions.',
  words_way_many: '{n} de plus sont en route dans tes révisions.',
  words_new_one: '{n} reste à découvrir : environ {days} à {per_day} mots nouveaux par jour.',
  words_new_many: '{n} restent à découvrir : environ {days} à {per_day} mots nouveaux par jour.',
  words_reading_one: '{n} connu par la lecture.',
  words_reading_many: '{n} connus par la lecture.',
  words_no_list: 'Au-delà de B1, la liste des mots essentiels s’arrête : les règles et l’épreuve décident.',
  test_label: 'Épreuve',
  test_locked: 'quand les règles et les mots seront couverts',
  test_ready_story: 'prête : elle arrive dans l’histoire',
  test_ready: 'prête : tout ce qu’elle demande est couvert',
  test_failed_dated: 'à repasser à partir du {date}',
  test_failed: 'à repasser après une semaine de consolidation',
  test_passed: 'réussie',
  test_credited: 'validée',
  today_one: 'Aujourd’hui, 1 règle peut avancer vers «\u00a0tenue\u00a0» : {names}.',
  today_many: 'Aujourd’hui, {n} règles peuvent avancer vers «\u00a0tenue\u00a0» : {names}.',
  today_more: 'et {n} autres',
  today_separator: ' ; ',
  time_title: 'Combien de temps',
  time_measured: 'Estimation : {low} à {high} jours à ton rythme, entre le {from} et le {to}.',
  time_plan: 'Estimation d’après ton plan : {low} à {high} jours, entre le {from} et le {to}.',
  time_capped: 'Estimation : plus de deux ans à ce rythme.',
  time_none: 'Pas encore d’estimation.',
  time_unverified: 'Une durée jusqu’au niveau suivant viendra dès que L’Atelier aura mesuré le tien.',
  time_basis_measured: 'Mesurée sur tes deux dernières semaines.',
  time_basis_plan: 'À partir de {required} jours actifs, elle est mesurée sur ta propre pratique ({active} pour l’instant).',
  time_earliest:
    'Pas avant le {date}, quel que soit ton entraînement : une règle est tenue après deux emplois libres à une semaine d’écart et un rappel réussi deux semaines après sa découverte.',
  time_cost_measured:
    'À tes {minutes} minutes par jour (ta moyenne sur deux semaines), cela fait environ {hours} de pratique.',
  time_cost_plan: 'Aux {minutes} minutes par jour que demande ton plan, cela fait environ {hours} de pratique.',
  hours_range: '{low} à {high} heures',
  hours_one: '{n} heure',
  hours_many: '{n} heures',
  days_one: '{n} jour',
  days_many: '{n} jours',
  on_days_one: 'sur {n} jour',
  on_days_many: 'sur {n} jours',
  time_pace: 'Ton rythme : {pace} · {words} mots nouveaux par jour · {rules} règles nouvelles par semaine',
  time_change: 'Changer de rythme',
  goal_line: 'Ton objectif {band} : encore {words} mots et {rules} règles, dans {eta} à ton rythme.',
  invested_title: 'Temps investi',
  invested_since: '{time} à {band} depuis le {date}, {days}.',
  invested_start: '{time} depuis tes débuts, {days}.',
  invested_parts: 'Scènes {scenes} · La Forge {forge} · Mots {words}',
  invested_recent: 'Ces derniers temps : {minutes} minutes par jour en moyenne.',
  invested_none: 'Pas encore de temps de pratique mesuré à {band}.',
  invested_floor: 'Le temps passé au Courrier et dans Le Papier n’est pas encore compté.',
  duration_minutes: '{m} min',
  duration_hours: '{h} h',
  duration_hours_minutes: '{h} h {m}',
  list_title: 'Les règles de {band} ({n})',
  row_held: 'tenue depuis le {date}',
  row_owed: 'peut avancer aujourd’hui',
  row_earliest: 'tenue au plus tôt le {date}',
  row_new_dated: 'pas encore découverte · arrive vers le {date} à ton rythme',
  row_new: 'pas encore découverte',
  skills_title: 'Règles et mots, chacun de son côté',
  skills_words: 'Mots',
  skills_rules: 'Règles',
  skills_working: '{what} : {covered} couvert, {percent} % de {working}.',
  skills_working_start: '{what} : {percent} % de {working}.',
  skills_list_ends: '{what} : {covered} couvert ; la liste des mots essentiels s’arrête là.',
  skills_all: '{what} : couverts jusqu’à {covered}.',
  skills_note: 'Ton niveau avance quand les deux sont couverts et l’épreuve réussie.',
};

export const LEVEL_PLAN_COPY: Record<ControlLanguage, LevelPlanCopy> = { en: EN, de: DE, fr: FR };

/** The level plan's copy for a chrome language (regional tags and nulls normalised). */
export function levelPlanCopy(language: unknown): LevelPlanCopy {
  return LEVEL_PLAN_COPY[normalizeControlLanguage(language)];
}

/** `{n}`-style placeholders filled in. */
export function fill(template: string, values: Record<string, string | number>): string {
  const filled = template.replace(/\{(\w+)\}/g, (match, key: string) => (key in values ? String(values[key]) : match));
  // A sentence that ends on an abbreviated day («18 déc.», «18. Dez.») keeps one full stop.
  return filled.replace(/\.\.$/, '.');
}

type PluralStem = {
  [K in keyof LevelPlanCopy]: K extends `${infer Stem}_one` ? Stem : never;
}[keyof LevelPlanCopy];

/** The `_one` / `_many` entry for `n`, `{n}` filled (French puts 0 and 1 in the singular). */
export function plural(
  copy: LevelPlanCopy,
  stem: PluralStem,
  n: number,
  values: Record<string, string | number> = {},
): string {
  const one = copy.locale.startsWith('fr') ? n <= 1 : n === 1;
  return fill(copy[`${stem}_${one ? 'one' : 'many'}` as keyof LevelPlanCopy], { n: num(n, copy), ...values });
}

/** «1,240» / «1.240» / «1 240»: a count as the chrome language writes it. */
export function num(n: number, copy: LevelPlanCopy): string {
  return n.toLocaleString(copy.locale);
}
