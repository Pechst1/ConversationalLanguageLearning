/**
 * WP-82 — Le Relevé (and «Vos sceaux») follows the one language rule.
 *
 * The Relevé's own words — section heads, line labels, states, counts, the
 * retry, the aria-labels — are chrome: up to A2 they are the learner's
 * language, from B1 French (`chromeLanguage`, `lib/language-rule.ts`). Place
 * names (Le Relevé, L’Atelier) are French in every column; a distinction's
 * title is a keepsake and stays French outside this table.
 *
 * Every table has the same keys and the same `{placeholders}` (the language
 * test proves it). `_one` / `_many` pairs are picked with `plural`.
 */

import { normalizeControlLanguage } from '@/lib/atelier-v2-copy';
import type { ControlLanguage } from '@/types/daily-journey';

export type ReleveCopy = {
  locale: string;
  retry: string;
  archive_notice: string;
  loading: string;
  failed_title: string;
  failed_body: string;
  // Le Cours
  cours_title: string;
  cours_failed: string;
  status_placement: string;
  status_placement_dated: string;
  status_declared: string;
  status_forecast: string;
  status_capped: string;
  status_no_forecast: string;
  track_words: string;
  track_words_label: string;
  track_rules: string;
  track_rules_label: string;
  // Le Registre
  registre_title: string;
  registre_failed: string;
  words_mastered: string;
  words_learning: string;
  words_due: string;
  words_gap: string;
  rules_started: string;
  rules_due: string;
  rules_gap: string;
  rules_bar: string;
  grammar_new_one: string;
  grammar_new_many: string;
  grammar_fragile_one: string;
  grammar_fragile_many: string;
  grammar_building_one: string;
  grammar_building_many: string;
  grammar_solid_one: string;
  grammar_solid_many: string;
  grammar_mastered_one: string;
  grammar_mastered_many: string;
  // La Collection
  collection_title: string;
  collection_failed: string;
  collection_empty_title: string;
  collection_empty_body: string;
  pieces_one: string;
  pieces_many: string;
  achievement_note_fallback: string;
  tier_gold: string;
  tier_silver: string;
  tier_bronze: string;
  kind_logo_token_one: string;
  kind_logo_token_many: string;
  kind_gilt_seal_one: string;
  kind_gilt_seal_many: string;
  kind_story_seal_one: string;
  kind_story_seal_many: string;
  kind_plate_semaine_one: string;
  kind_plate_semaine_many: string;
  kind_plate_chapter_one: string;
  kind_plate_chapter_many: string;
  kind_colophon_one: string;
  kind_colophon_many: string;
  note_first_scene: string;
  note_scenes_10: string;
  note_session_streak_3: string;
  note_session_streak_7: string;
  note_session_streak_30: string;
  note_first_letter: string;
  note_words_kept_50: string;
  note_first_chapter: string;
  foot_dated: string;
  foot: string;
  // Vos sceaux
  seals_title: string;
  seals_failed: string;
  seals_grid: string;
  seals_streak: string;
  seals_freeze: string;
  seals_today_earned: string;
  seals_today_done: string;
  seals_forms_one: string;
  seals_forms_many: string;
  seals_today_waiting: string;
  days_one: string;
  days_many: string;
  weekday_initials: string;
  seal_earned: string;
  seal_earned_no: string;
  seal_done: string;
  seal_relache: string;
  seal_today: string;
  seal_future: string;
  seal_missed: string;
};

const FR: ReleveCopy = {
  locale: 'fr-FR',
  retry: 'Réessayer',
  archive_notice: 'Avis du bureau des archives',
  loading: 'Le relevé sort de presse',
  failed_title: 'Le relevé n’a pas pu être tiré',
  failed_body: 'Vos chiffres restent au bureau, rien n’est perdu.',
  cours_title: 'Le cours',
  cours_failed: 'Le niveau n’a pas pu être relevé.',
  status_placement: 'Niveau estimé (placement). L’Atelier le vérifie au fil des séances.',
  status_placement_dated: 'Niveau estimé (placement), {date}. L’Atelier le vérifie au fil des séances.',
  status_declared: 'Niveau que vous avez indiqué. L’Atelier le vérifie au fil des séances.',
  status_forecast: 'Estimation : {low} à {high} jours à ce rythme.',
  status_capped: 'Estimation : plus de deux ans à ce rythme.',
  status_no_forecast: 'Prévisions après sept jours actifs.',
  track_words: 'Mots',
  track_words_label: 'Mots vérifiés',
  track_rules: 'Règles',
  track_rules_label: 'Règles vérifiées',
  registre_title: 'Le registre',
  registre_failed: 'Le registre n’a pas pu être ouvert.',
  words_mastered: 'Mots acquis',
  words_learning: 'Mots en cours',
  words_due: 'Mots à revoir aujourd’hui',
  words_gap: 'Le compte des mots n’a pas suivi cette fois-ci.',
  rules_started: 'Règles engagées',
  rules_due: 'Règles à revoir aujourd’hui',
  rules_gap: 'Le compte des règles n’a pas suivi cette fois-ci.',
  rules_bar: 'Règles : {list}',
  grammar_new_one: 'nouvelle',
  grammar_new_many: 'nouvelles',
  grammar_fragile_one: 'fragile',
  grammar_fragile_many: 'fragiles',
  grammar_building_one: 'en cours',
  grammar_building_many: 'en cours',
  grammar_solid_one: 'solide',
  grammar_solid_many: 'solides',
  grammar_mastered_one: 'maîtrisée',
  grammar_mastered_many: 'maîtrisées',
  collection_title: 'La collection',
  collection_failed: 'La collection n’a pas pu être sortie de sa boîte.',
  collection_empty_title: 'Rien d’accroché encore',
  collection_empty_body: 'La collection commence avec la première édition bouclée.',
  pieces_one: '{n} pièce',
  pieces_many: '{n} pièces',
  achievement_note_fallback: 'Décernée au fil des séances.',
  tier_gold: 'or',
  tier_silver: 'argent',
  tier_bronze: 'bronze',
  kind_logo_token_one: 'vignette',
  kind_logo_token_many: 'vignettes',
  kind_gilt_seal_one: 'sceau doré',
  kind_gilt_seal_many: 'sceaux dorés',
  kind_story_seal_one: 'sceau de feuilleton',
  kind_story_seal_many: 'sceaux de feuilleton',
  kind_plate_semaine_one: 'planche de la semaine',
  kind_plate_semaine_many: 'planches de la semaine',
  kind_plate_chapter_one: 'planche de chapitre',
  kind_plate_chapter_many: 'planches de chapitre',
  kind_colophon_one: 'colophon',
  kind_colophon_many: 'colophons',
  note_first_scene: 'La première journée bouclée.',
  note_scenes_10: 'Dix journées bouclées.',
  note_session_streak_3: 'Trois jours d’affilée à l’Atelier.',
  note_session_streak_7: 'Sept jours d’affilée à l’Atelier.',
  note_session_streak_30: 'Trente jours d’affilée à l’Atelier.',
  note_first_letter: 'Une première réponse au Courrier.',
  note_words_kept_50: 'Cinquante mots dans votre Lexique.',
  note_first_chapter: 'Le premier chapitre du feuilleton s’est refermé.',
  foot_dated: 'Le Relevé · arrêté au {date}',
  foot: 'Le Relevé · vos chiffres, rien d’autre',
  seals_title: 'Vos sceaux',
  seals_failed: 'Les sceaux n’ont pas pu être relevés.',
  seals_grid: 'Vos sceaux · série de {days}',
  seals_streak: 'Série · {streak} · record · {longest}',
  seals_freeze: 'Un jour de relâche en réserve.',
  seals_today_earned: 'Le sceau du jour est rangé.',
  seals_today_done: 'Journée faite. Le sceau se presse en bouclant la scène.',
  seals_forms_one: 'Le sceau du jour : encore {n} forme.',
  seals_forms_many: 'Le sceau du jour : encore {n} formes.',
  seals_today_waiting: 'Le sceau du jour attend sa scène.',
  days_one: '{n} jour',
  days_many: '{n} jours',
  weekday_initials: 'L M M J V S D',
  seal_earned: 'sceau',
  seal_earned_no: 'sceau Nº {no}',
  seal_done: 'journée faite',
  seal_relache: 'jour de relâche',
  seal_today: 'aujourd’hui, le sceau attend',
  seal_future: 'à venir',
  seal_missed: 'pas de séance',
};

const EN: ReleveCopy = {
  locale: 'en-GB',
  retry: 'Try again',
  archive_notice: 'Notice',
  loading: 'Loading your Relevé',
  failed_title: 'Your Relevé could not be loaded',
  failed_body: 'Your numbers are safe; nothing is lost.',
  cours_title: 'Your course',
  cours_failed: 'Your level could not be loaded.',
  status_placement: 'Estimated level (placement test). L’Atelier checks it as you practise.',
  status_placement_dated: 'Estimated level (placement test), {date}. L’Atelier checks it as you practise.',
  status_declared: 'The level you told us. L’Atelier checks it as you practise.',
  status_forecast: 'Estimate: {low} to {high} days at this pace.',
  status_capped: 'Estimate: more than two years at this pace.',
  status_no_forecast: 'Forecast after seven active days.',
  track_words: 'Words',
  track_words_label: 'Verified words',
  track_rules: 'Rules',
  track_rules_label: 'Verified rules',
  registre_title: 'Your record',
  registre_failed: 'Your record could not be loaded.',
  words_mastered: 'Words learned',
  words_learning: 'Words in progress',
  words_due: 'Words to review today',
  words_gap: 'The word count did not load this time.',
  rules_started: 'Rules started',
  rules_due: 'Rules to review today',
  rules_gap: 'The rule count did not load this time.',
  rules_bar: 'Rules: {list}',
  grammar_new_one: 'new',
  grammar_new_many: 'new',
  grammar_fragile_one: 'shaky',
  grammar_fragile_many: 'shaky',
  grammar_building_one: 'in progress',
  grammar_building_many: 'in progress',
  grammar_solid_one: 'solid',
  grammar_solid_many: 'solid',
  grammar_mastered_one: 'mastered',
  grammar_mastered_many: 'mastered',
  collection_title: 'Your collection',
  collection_failed: 'Your collection could not be loaded.',
  collection_empty_title: 'Nothing here yet',
  collection_empty_body: 'Your collection starts with your first finished edition.',
  pieces_one: '{n} piece',
  pieces_many: '{n} pieces',
  achievement_note_fallback: 'Earned as you practised.',
  tier_gold: 'gold',
  tier_silver: 'silver',
  tier_bronze: 'bronze',
  kind_logo_token_one: 'vignette',
  kind_logo_token_many: 'vignettes',
  kind_gilt_seal_one: 'gilded seal',
  kind_gilt_seal_many: 'gilded seals',
  kind_story_seal_one: 'story seal',
  kind_story_seal_many: 'story seals',
  kind_plate_semaine_one: 'plate of the week',
  kind_plate_semaine_many: 'plates of the week',
  kind_plate_chapter_one: 'chapter plate',
  kind_plate_chapter_many: 'chapter plates',
  kind_colophon_one: 'colophon',
  kind_colophon_many: 'colophons',
  note_first_scene: 'Your first day finished.',
  note_scenes_10: 'Ten days finished.',
  note_session_streak_3: 'Three days in a row at L’Atelier.',
  note_session_streak_7: 'Seven days in a row at L’Atelier.',
  note_session_streak_30: 'Thirty days in a row at L’Atelier.',
  note_first_letter: 'Your first reply in the Courrier.',
  note_words_kept_50: 'Fifty words in your Lexique.',
  note_first_chapter: 'The first chapter of the Feuilleton has closed.',
  foot_dated: 'Le Relevé · as of {date}',
  foot: 'Le Relevé · your numbers, nothing else',
  seals_title: 'Your seals',
  seals_failed: 'Your seals could not be loaded.',
  seals_grid: 'Your seals · streak of {days}',
  seals_streak: 'Streak · {streak} · best · {longest}',
  seals_freeze: 'One rest day in reserve.',
  seals_today_earned: 'Today’s seal is in your collection.',
  seals_today_done: 'Day done. Finish the scene to press the seal.',
  seals_forms_one: 'Today’s seal: {n} shape to go.',
  seals_forms_many: 'Today’s seal: {n} shapes to go.',
  seals_today_waiting: 'Today’s seal is waiting for its scene.',
  days_one: '{n} day',
  days_many: '{n} days',
  weekday_initials: 'M T W T F S S',
  seal_earned: 'seal',
  seal_earned_no: 'seal No. {no}',
  seal_done: 'day done',
  seal_relache: 'rest day',
  seal_today: 'today, the seal is waiting',
  seal_future: 'upcoming',
  seal_missed: 'no session',
};

const DE: ReleveCopy = {
  locale: 'de-DE',
  retry: 'Erneut versuchen',
  archive_notice: 'Hinweis',
  loading: 'Ihr Relevé wird geladen',
  failed_title: 'Ihr Relevé konnte nicht geladen werden',
  failed_body: 'Ihre Zahlen sind sicher, nichts ist verloren.',
  cours_title: 'Ihr Kurs',
  cours_failed: 'Ihr Niveau konnte nicht geladen werden.',
  status_placement: 'Geschätztes Niveau (Einstufungstest). L’Atelier prüft es im Lauf Ihrer Übungen.',
  status_placement_dated: 'Geschätztes Niveau (Einstufungstest), {date}. L’Atelier prüft es im Lauf Ihrer Übungen.',
  status_declared: 'Das Niveau, das Sie angegeben haben. L’Atelier prüft es im Lauf Ihrer Übungen.',
  status_forecast: 'Schätzung: {low} bis {high} Tage bei diesem Tempo.',
  status_capped: 'Schätzung: mehr als zwei Jahre bei diesem Tempo.',
  status_no_forecast: 'Prognose nach sieben aktiven Tagen.',
  track_words: 'Wörter',
  track_words_label: 'Geprüfte Wörter',
  track_rules: 'Regeln',
  track_rules_label: 'Geprüfte Regeln',
  registre_title: 'Ihre Übersicht',
  registre_failed: 'Ihre Übersicht konnte nicht geladen werden.',
  words_mastered: 'Gelernte Wörter',
  words_learning: 'Wörter in Arbeit',
  words_due: 'Heute zu wiederholende Wörter',
  words_gap: 'Die Wortzahl wurde diesmal nicht geladen.',
  rules_started: 'Begonnene Regeln',
  rules_due: 'Heute zu wiederholende Regeln',
  rules_gap: 'Die Regelzahl wurde diesmal nicht geladen.',
  rules_bar: 'Regeln: {list}',
  grammar_new_one: 'neu',
  grammar_new_many: 'neu',
  grammar_fragile_one: 'wackelig',
  grammar_fragile_many: 'wackelig',
  grammar_building_one: 'in Arbeit',
  grammar_building_many: 'in Arbeit',
  grammar_solid_one: 'sicher',
  grammar_solid_many: 'sicher',
  grammar_mastered_one: 'beherrscht',
  grammar_mastered_many: 'beherrscht',
  collection_title: 'Ihre Sammlung',
  collection_failed: 'Ihre Sammlung konnte nicht geladen werden.',
  collection_empty_title: 'Noch nichts hier',
  collection_empty_body: 'Ihre Sammlung beginnt mit der ersten abgeschlossenen Ausgabe.',
  pieces_one: '{n} Stück',
  pieces_many: '{n} Stücke',
  achievement_note_fallback: 'Im Lauf Ihrer Übungen verdient.',
  tier_gold: 'Gold',
  tier_silver: 'Silber',
  tier_bronze: 'Bronze',
  kind_logo_token_one: 'Vignette',
  kind_logo_token_many: 'Vignetten',
  kind_gilt_seal_one: 'Goldsiegel',
  kind_gilt_seal_many: 'Goldsiegel',
  kind_story_seal_one: 'Feuilleton-Siegel',
  kind_story_seal_many: 'Feuilleton-Siegel',
  kind_plate_semaine_one: 'Wochentafel',
  kind_plate_semaine_many: 'Wochentafeln',
  kind_plate_chapter_one: 'Kapiteltafel',
  kind_plate_chapter_many: 'Kapiteltafeln',
  kind_colophon_one: 'Kolophon',
  kind_colophon_many: 'Kolophone',
  note_first_scene: 'Der erste Tag abgeschlossen.',
  note_scenes_10: 'Zehn Tage abgeschlossen.',
  note_session_streak_3: 'Drei Tage in Folge im Atelier.',
  note_session_streak_7: 'Sieben Tage in Folge im Atelier.',
  note_session_streak_30: 'Dreißig Tage in Folge im Atelier.',
  note_first_letter: 'Eine erste Antwort im Courrier.',
  note_words_kept_50: 'Fünfzig Wörter in Ihrem Lexique.',
  note_first_chapter: 'Das erste Kapitel des Feuilleton ist abgeschlossen.',
  foot_dated: 'Le Relevé · Stand {date}',
  foot: 'Le Relevé · Ihre Zahlen, sonst nichts',
  seals_title: 'Ihre Siegel',
  seals_failed: 'Ihre Siegel konnten nicht geladen werden.',
  seals_grid: 'Ihre Siegel · Serie: {days}',
  seals_streak: 'Serie · {streak} · Rekord · {longest}',
  seals_freeze: 'Ein Ruhetag in Reserve.',
  seals_today_earned: 'Das Siegel von heute ist gesammelt.',
  seals_today_done: 'Tag geschafft. Beenden Sie die Szene, um das Siegel zu prägen.',
  seals_forms_one: 'Siegel von heute: noch {n} Form.',
  seals_forms_many: 'Siegel von heute: noch {n} Formen.',
  seals_today_waiting: 'Das Siegel von heute wartet auf seine Szene.',
  days_one: '{n} Tag',
  days_many: '{n} Tage',
  weekday_initials: 'M D M D F S S',
  seal_earned: 'Siegel',
  seal_earned_no: 'Siegel Nr. {no}',
  seal_done: 'Tag geschafft',
  seal_relache: 'Ruhetag',
  seal_today: 'heute, das Siegel wartet',
  seal_future: 'kommt noch',
  seal_missed: 'keine Übung',
};

export const RELEVE_COPY: Record<ControlLanguage, ReleveCopy> = { en: EN, de: DE, fr: FR };

/** The Relevé copy table for a chrome language (regional tags and nulls normalised). */
export function releveCopy(language: unknown): ReleveCopy {
  return RELEVE_COPY[normalizeControlLanguage(language)];
}

/** `{n}`-style placeholders filled in. */
export function fill(template: string, values: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (match, key: string) => (key in values ? String(values[key]) : match));
}

type PluralStem = {
  [K in keyof ReleveCopy]: K extends `${infer Stem}_one` ? Stem : never;
}[keyof ReleveCopy];

/** The `_one` / `_many` entry for `n`, `{n}` filled. */
export function plural(copy: ReleveCopy, stem: PluralStem, n: number): string {
  return fill(copy[`${stem}_${n === 1 ? 'one' : 'many'}` as keyof ReleveCopy], { n });
}
