/**
 * «Papier · les rendez-vous» (2026-11-21) · the chrome of «Trois mots», «La une de la semaine»
 * and «La carte de presse», in fr, en and de.
 *
 * Two languages are at work, as in the players: the chrome (`plan.ui_language`: the mother
 * tongue below B1, French from B1) and the reasons (the gloss language, the mother tongue
 * always): a miss is explained in the mother tongue under French chrome too.
 *
 * French in every table: the features' names («Trois mots», «La une de la semaine», «Lexique»,
 * the rubriques' names), as the paper prints them. Sentence case, no exclamation marks.
 */

import type { RvLanguage } from '@/lib/revue-types';
import type { RvRubrique } from '@/lib/revue-rdv';

export const RDV_FR = {
  trois_mots: 'Trois mots',
  une_title: 'La une de la semaine',
  lexique: 'Lexique',
  carte: 'Carte de presse',
  rubriques: {
    opinion: 'Au comptoir',
    fil: 'Le fil',
    titre: 'Le titre',
    intox: "L'intox express",
    photo: 'La photo',
    micro: 'Le micro',
  } as Record<RvRubrique, string>,
  stance: { pour: 'pour', contre: 'contre', nuance: 'ça dépend' } as Record<'pour' | 'contre' | 'nuance', string>,
  toi: 'Toi',
  score: '{score} sur {total}',
};

export type RdvCopy = {
  // «Trois mots» (chrome)
  tm_task_match: string;
  tm_task_gap: string;
  tm_word_n: string;
  tm_unpaired: string;
  tm_check: string;
  tm_picture_cue: string;
  tm_try_again: string;
  tm_match_right: string;
  tm_match_shown: string;
  tm_gap_right: string;
  tm_gap_shown: string;
  tm_done: string;
  tm_failed: string;
  // the reasons (mother tongue)
  tm_miss_gloss: string;
  tm_miss_picture: string;
  tm_gap_miss: string;
  // «La une de la semaine»
  une_count: string;
  une_pieces: string;
  une_empty: string;
  une_by_you: string;
  une_rectified: string;
  une_vox: string;
  une_back: string;
  une_door: string;
  une_failed: string;
  // «La carte de presse»
  carte_since: string;
  carte_pieces: string;
  carte_none: string;
  carte_filed: string;
  carte_not_yet: string;
  // the line of a regular
  souvenir_label: string;
};

const EN: RdvCopy = {
  tm_task_match: 'Match each word to its meaning.',
  tm_task_gap: 'Which word goes in the sentence?',
  tm_word_n: 'Word {n}',
  tm_unpaired: 'not matched yet',
  tm_check: 'Check',
  tm_picture_cue: 'The picture',
  tm_try_again: 'Have another go.',
  tm_match_right: 'All three, right.',
  tm_match_shown: 'Here are the three, with their meaning.',
  tm_gap_right: 'Right: that is the story’s own sentence.',
  tm_gap_shown: 'Here is the story’s sentence.',
  tm_done: 'These three words come back tomorrow, at the top of your words.',
  tm_failed: 'The round could not be loaded. The page is all there below.',
  tm_miss_gloss: '“{word}” does not mean “{cue}”.',
  tm_miss_picture: '“{word}” is not what the picture shows.',
  tm_gap_miss: '“{word}” means “{gloss}”: it does not fit this sentence.',
  une_count: '{n} of {total} sections this week',
  une_pieces: '{n} pieces',
  une_empty: 'Nothing filed this week yet. Romy is waiting for your first piece.',
  une_by_you: 'by you',
  une_rectified: 'Your corrections',
  une_vox: 'Your opinion',
  une_back: 'Back',
  une_door: 'The week’s front page',
  une_failed: 'The front page could not be loaded.',
  carte_since: 'Since {date}',
  carte_pieces: '{n} pieces filed',
  carte_none: 'No piece filed yet.',
  carte_filed: '{n} filed',
  carte_not_yet: 'not yet',
  souvenir_label: 'A regular remembers',
};

const DE: RdvCopy = {
  tm_task_match: 'Ordne jedem Wort seine Bedeutung zu.',
  tm_task_gap: 'Welches Wort gehört in den Satz?',
  tm_word_n: 'Wort {n}',
  tm_unpaired: 'noch nicht zugeordnet',
  tm_check: 'Prüfen',
  tm_picture_cue: 'Das Bild',
  tm_try_again: 'Versuch es noch einmal.',
  tm_match_right: 'Alle drei richtig.',
  tm_match_shown: 'Hier sind die drei, mit ihrer Bedeutung.',
  tm_gap_right: 'Richtig: Das ist der Satz aus dem Artikel.',
  tm_gap_shown: 'Hier ist der Satz aus dem Artikel.',
  tm_done: 'Diese drei Wörter kommen morgen wieder, ganz oben bei deinen Wörtern.',
  tm_failed: 'Die Runde konnte nicht geladen werden. Die Seite steht unten vollständig.',
  tm_miss_gloss: '„{word}“ bedeutet nicht „{cue}“.',
  tm_miss_picture: '„{word}“ ist nicht das, was das Bild zeigt.',
  tm_gap_miss: '„{word}“ bedeutet „{gloss}“: Es passt nicht in diesen Satz.',
  une_count: '{n} von {total} Rubriken diese Woche',
  une_pieces: '{n} Artikel',
  une_empty: 'Diese Woche ist noch nichts abgelegt. Romy wartet auf deinen ersten Artikel.',
  une_by_you: 'von dir',
  une_rectified: 'Deine Korrekturen',
  une_vox: 'Deine Meinung',
  une_back: 'Zurück',
  une_door: 'Die Titelseite der Woche',
  une_failed: 'Die Titelseite konnte nicht geladen werden.',
  carte_since: 'Seit {date}',
  carte_pieces: '{n} Artikel abgelegt',
  carte_none: 'Noch kein Artikel abgelegt.',
  carte_filed: '{n} abgelegt',
  carte_not_yet: 'noch nicht',
  souvenir_label: 'Ein Stammgast erinnert sich',
};

const FR: RdvCopy = {
  tm_task_match: 'Relie chaque mot à son sens.',
  tm_task_gap: 'Quel mot va dans la phrase ?',
  tm_word_n: 'Mot {n}',
  tm_unpaired: 'pas encore relié',
  tm_check: 'Vérifier',
  tm_picture_cue: "L'image",
  tm_try_again: 'Essaie encore une fois.',
  tm_match_right: 'Les trois, justes.',
  tm_match_shown: 'Voici les trois, avec leur sens.',
  tm_gap_right: "Juste : c'est la phrase de l'article.",
  tm_gap_shown: "Voici la phrase de l'article.",
  tm_done: 'Ces trois mots reviennent demain, en tête de tes mots.',
  tm_failed: "La manche n'a pas pu être chargée. La page est là, en dessous.",
  tm_miss_gloss: '« {word} » ne veut pas dire « {cue} ».',
  tm_miss_picture: "« {word} » n'est pas ce que montre l'image.",
  tm_gap_miss: '« {word} » veut dire « {gloss} » : il ne va pas dans cette phrase.',
  une_count: '{n} rubriques sur {total} cette semaine',
  une_pieces: '{n} papiers',
  une_empty: "Rien de classé cette semaine. Romy attend ton premier papier.",
  une_by_you: 'par toi',
  une_rectified: 'Tes corrections',
  une_vox: 'Ton avis',
  une_back: 'Retour',
  une_door: 'La une de la semaine',
  une_failed: "La une n'a pas pu être chargée.",
  carte_since: 'Depuis le {date}',
  carte_pieces: '{n} papiers classés',
  carte_none: 'Aucun papier classé pour le moment.',
  carte_filed: '{n} classés',
  carte_not_yet: 'pas encore',
  souvenir_label: 'Un habitué se souvient',
};

const TABLES: Record<RvLanguage, RdvCopy> = { en: EN, de: DE, fr: FR };

export function rdvCopy(language: RvLanguage | string | null | undefined): RdvCopy {
  return TABLES[(language === 'de' || language === 'fr' ? language : 'en') as RvLanguage];
}

/** «{word}» → the value; unknown slots are left as they are. */
export function fillRdv(template: string, vars: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (whole, key: string) => (key in vars ? String(vars[key]) : whole));
}

const MONTHS: Record<RvLanguage, string[]> = {
  fr: ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre'],
  en: ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'],
  de: ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember'],
};

/** An ISO date as the chrome says it: «16 novembre 2026», «16 November 2026», «16. November 2026». */
export function dayLabel(iso: string, language: RvLanguage): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!match) return iso;
  const [, year, month, day] = match;
  const d = Number(day);
  const name = MONTHS[language][Number(month) - 1] ?? '';
  if (language === 'fr') return `${d === 1 ? '1er' : d} ${name} ${year}`;
  if (language === 'de') return `${d}. ${name} ${year}`;
  return `${d} ${name} ${year}`;
}
