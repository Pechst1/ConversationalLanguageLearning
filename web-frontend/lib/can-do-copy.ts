/**
 * WP-94 «Numéro spécial» and WP-95 «Le Carnet» — their own words.
 *
 * WP-82, one language rule: every word here is chrome, written in the
 * screen's one chrome language (the learner's up to A2, French from B1 —
 * `lib/language-rule.ts`). Place names stay French in every column, like
 * «Relevé» and «Dossier»: «Le Carnet» and the special edition's masthead
 * kicker «Numéro spécial» (printed with `lang="fr"`). The can-dos' titles
 * come from the server in both languages (`title_fr`, `title_native`); the
 * learner's own quote and the scene's title are French content.
 *
 * Every table has the same keys and the same `{placeholders}` (the node test
 * proves it). No shame and no red on the fail side: the épreuve comes back.
 */

import { normalizeControlLanguage } from '@/lib/atelier-v2-copy';
import type { ControlLanguage } from '@/types/daily-journey';

export type CanDoCopyKey =
  | 'special_kicker'
  | 'special_list'
  | 'next_step'
  | 'next_step_aria'
  | 'level_band_aria'
  | 'band_all_stamped'
  | 'epreuve_seal_top'
  | 'epreuve_passed_title'
  | 'epreuve_passed_aria'
  | 'epreuve_cast_label'
  | 'epreuve_failed_title'
  | 'epreuve_failed_body'
  | 'epreuve_next'
  | 'carnet_name'
  | 'carnet_mode'
  | 'carnet_lead'
  | 'carnet_count'
  | 'carnet_count_none'
  | 'carnet_bands_label'
  | 'carnet_band_current'
  | 'carnet_band_locked'
  | 'carnet_band_locked_note'
  | 'carnet_unstamped'
  | 'carnet_stamped'
  | 'carnet_stamped_aria'
  | 'carnet_unstamped_aria'
  | 'carnet_source_epreuve'
  | 'carnet_source_authored'
  | 'carnet_try'
  | 'carnet_try_aria'
  | 'carnet_empty'
  | 'carnet_load_failed'
  | 'carnet_retry'
  | 'dossier_carnet'
  | 'dossier_carnet_hint';

type Table = Record<CanDoCopyKey, string>;

const FR: Table = {
  special_kicker: 'Numéro spécial',
  special_list: 'Aujourd’hui, montrez que vous savez : {list}',
  next_step: 'Prochaine étape : {can_do}',
  next_step_aria: 'Niveau {band}. Prochaine étape : {can_do}. Ouvrir le Carnet',
  level_band_aria: 'Votre niveau : {band}',
  band_all_stamped: 'Tout {band} est tamponné',
  epreuve_seal_top: 'Numéro spécial',
  epreuve_passed_title: '{band}, bouclé',
  epreuve_passed_aria: 'Sceau du numéro spécial · {band} bouclé',
  epreuve_cast_label: 'Toute la troupe',
  epreuve_failed_title: 'Pas encore cette fois',
  epreuve_failed_body: 'Le niveau reste ouvert, rien n’est perdu. L’épreuve revient dans une autre situation.',
  epreuve_next: 'La prochaine édition spéciale : dans 7 jours ({date})',
  carnet_name: 'Le Carnet',
  carnet_mode: 'Carnet',
  carnet_lead: 'Ce que vous savez faire en français. Chaque ligne est tamponnée la première fois que l’histoire le montre.',
  carnet_count: '{stamped} sur {total} tamponnés',
  carnet_count_none: 'Rien de tamponné pour l’instant',
  carnet_bands_label: 'Sous-niveaux',
  carnet_band_current: 'en cours',
  carnet_band_locked: 'plus tard',
  carnet_band_locked_note: '{band} s’ouvre quand {previous} est bouclé. Voici ce qui vous y attend.',
  carnet_unstamped: 'Pas encore',
  carnet_stamped: 'Tamponné',
  carnet_stamped_aria: 'Tamponné le {date}',
  carnet_unstamped_aria: 'Pas encore tamponné',
  carnet_source_epreuve: 'numéro spécial',
  carnet_source_authored: 'premier jour',
  carnet_try: 'Essayez-le pour de vrai',
  carnet_try_aria: 'Essayez-le pour de vrai : {can_do} — ouvre la Répétition',
  carnet_empty: 'Le Carnet s’ouvre avec votre première scène.',
  carnet_load_failed: 'Nous ne pouvons pas lire le Carnet pour l’instant.',
  carnet_retry: 'Réessayer',
  dossier_carnet: 'Le Carnet',
  dossier_carnet_hint: 'ce que vous savez faire, tamponné par l’histoire',
};

const EN: Table = {
  special_kicker: 'Numéro spécial',
  special_list: 'Today, show that you can: {list}',
  next_step: 'Next step: {can_do}',
  next_step_aria: 'Level {band}. Next step: {can_do}. Open the Carnet',
  level_band_aria: 'Your level: {band}',
  band_all_stamped: 'All of {band} is stamped',
  epreuve_seal_top: 'Numéro spécial',
  epreuve_passed_title: '{band}, closed',
  epreuve_passed_aria: 'Special edition seal · {band} closed',
  epreuve_cast_label: 'The whole cast',
  epreuve_failed_title: 'Not this time',
  epreuve_failed_body: 'The level stays open and nothing is lost. The test comes back in another situation.',
  epreuve_next: 'The next special edition: in 7 days ({date})',
  carnet_name: 'Le Carnet',
  carnet_mode: 'Carnet',
  carnet_lead: 'What you can do in French. Each line is stamped the first time the story shows it.',
  carnet_count: '{stamped} of {total} stamped',
  carnet_count_none: 'Nothing stamped yet',
  carnet_bands_label: 'Sub-levels',
  carnet_band_current: 'current',
  carnet_band_locked: 'later',
  carnet_band_locked_note: '{band} opens once {previous} is closed. Here is what waits there.',
  carnet_unstamped: 'Not yet',
  carnet_stamped: 'Stamped',
  carnet_stamped_aria: 'Stamped on {date}',
  carnet_unstamped_aria: 'Not stamped yet',
  carnet_source_epreuve: 'special edition',
  carnet_source_authored: 'first day',
  carnet_try: 'Try it for real',
  carnet_try_aria: 'Try it for real: {can_do} — opens Répétition',
  carnet_empty: 'The Carnet opens with your first scene.',
  carnet_load_failed: 'We can’t read the Carnet right now.',
  carnet_retry: 'Try again',
  dossier_carnet: 'Le Carnet',
  dossier_carnet_hint: 'what you can do, stamped by the story',
};

const DE: Table = {
  special_kicker: 'Numéro spécial',
  special_list: 'Heute zeigen Sie, was Sie können: {list}',
  next_step: 'Nächster Schritt: {can_do}',
  next_step_aria: 'Niveau {band}. Nächster Schritt: {can_do}. Carnet öffnen',
  level_band_aria: 'Ihr Niveau: {band}',
  band_all_stamped: 'Ganz {band} ist gestempelt',
  epreuve_seal_top: 'Numéro spécial',
  epreuve_passed_title: '{band}, abgeschlossen',
  epreuve_passed_aria: 'Siegel der Sonderausgabe · {band} abgeschlossen',
  epreuve_cast_label: 'Die ganze Truppe',
  epreuve_failed_title: 'Diesmal noch nicht',
  epreuve_failed_body: 'Das Niveau bleibt offen, nichts geht verloren. Die Prüfung kommt in einer anderen Situation wieder.',
  epreuve_next: 'Die nächste Sonderausgabe: in 7 Tagen ({date})',
  carnet_name: 'Le Carnet',
  carnet_mode: 'Carnet',
  carnet_lead: 'Was Sie auf Französisch können. Jede Zeile wird gestempelt, sobald die Geschichte es zeigt.',
  carnet_count: '{stamped} von {total} gestempelt',
  carnet_count_none: 'Noch nichts gestempelt',
  carnet_bands_label: 'Teilstufen',
  carnet_band_current: 'aktuell',
  carnet_band_locked: 'später',
  carnet_band_locked_note: '{band} öffnet sich, wenn {previous} abgeschlossen ist. Das erwartet Sie dort.',
  carnet_unstamped: 'Noch nicht',
  carnet_stamped: 'Gestempelt',
  carnet_stamped_aria: 'Gestempelt am {date}',
  carnet_unstamped_aria: 'Noch nicht gestempelt',
  carnet_source_epreuve: 'Sonderausgabe',
  carnet_source_authored: 'erster Tag',
  carnet_try: 'Im echten Leben ausprobieren',
  carnet_try_aria: 'Im echten Leben ausprobieren: {can_do} — öffnet Répétition',
  carnet_empty: 'Das Carnet beginnt mit Ihrer ersten Szene.',
  carnet_load_failed: 'Wir können das Carnet gerade nicht lesen.',
  carnet_retry: 'Erneut versuchen',
  dossier_carnet: 'Le Carnet',
  dossier_carnet_hint: 'was Sie können, von der Geschichte gestempelt',
};

const TABLES: Record<ControlLanguage, Table> = { en: EN, de: DE, fr: FR };

/** The WP-94/95 copy table for a chrome language (regional tags and nulls normalised). */
export function canDoCopy(language: unknown): Table {
  return TABLES[normalizeControlLanguage(language)];
}

export const CAN_DO_COPY_TABLES = TABLES;

export function fill(template: string, values: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (match, key: string) => (key in values ? String(values[key]) : match));
}
