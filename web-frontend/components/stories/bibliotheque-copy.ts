/**
 * WP-82 — La Bibliothèque follows the one language rule.
 *
 * The Bibliothèque's own words — the shelf index, a text's page, a chapter
 * session, the chapter-end sheet and the book import — are chrome: up to A2
 * they are the learner's language, from B1 they are French
 * (`chromeLanguage`, `lib/language-rule.ts`). The texts themselves (titles,
 * descriptions, chapters, the conversation, the learner's own words) are
 * content and stay as the server sent them. Place names (La bibliothèque,
 * Le Feuilleton, L’Atelier) are French in every column.
 *
 * Every table has the same keys and the same `{placeholders}` (the copy test
 * proves it). Placeholders are filled with `fill`.
 */

import type { ControlLanguage } from '@/types/daily-journey';
import { normalizeControlLanguage } from '@/lib/atelier-v2-copy';

export type BibliothequeCopy = {
  // the shelf (pages/bibliotheque.tsx)
  shelf_loading: string;
  shelf_count_one: string;
  shelf_count_many: string;
  shelf_intro: string;
  import_book: string;
  shelf_loading_sr: string;
  shelf_error_title: string;
  shelf_error_body: string;
  retry: string;
  shelf_empty_title: string;
  shelf_empty_body: string;
  shelf_empty_action: string;
  hero_aria: string;
  no_cover: string;
  on_shelf: string;
  by_author: string;
  in_progress: string;
  locked: string;
  resume_reading: string;
  start_reading: string;
  rest_aria: string;
  read_badge: string;
  // one text (pages/bibliotheque/[storyId].tsx)
  detail_aria: string;
  back_to_library: string;
  text_opening: string;
  text_not_found: string;
  text_removed: string;
  chapter_count_one: string;
  chapter_count_many: string;
  about_text: string;
  chapters: string;
  chapters_all_read: string;
  chapters_pick_up: string;
  chapters_unlock: string;
  back_to_shelf: string;
  opening: string;
  // the chapter gate (pages/bibliotheque/[storyId]/chapter/[chapterId].tsx)
  gate_aria: string;
  chapter_opening: string;
  session_opening: string;
  session_failed: string;
  back_to_text: string;
  chapter_not_found: string;
  chapter_removed: string;
  // the chapter session (StorySessionLayout)
  leave_chapter: string;
  chapter_n: string;
  conversation_aria: string;
  to_fix: string;
  nothing_to_fix: string;
  typing: string;
  suggested_words: string;
  answer_label: string;
  answer_placeholder: string;
  send: string;
  connected: string;
  connecting: string;
  aside_aria: string;
  // the chapter card (ChapterProgressCard)
  progress_heading: string;
  goals_reached: string;
  words_used: string;
  xp_earned: string;
  perfect_possible: string;
  closing: string;
  finish_chapter: string;
  goals_missing: string;
  can_close: string;
  reach_goals_one: string;
  reach_goals_many: string;
  // the chapter-end sheet (ChapterCompletionModal)
  done_story: string;
  done_perfect: string;
  done_chapter: string;
  finished_story: string;
  all_goals: string;
  reading_goes_on: string;
  perfect_bonus: string;
  achievements: string;
  new_achievement: string;
  next_chapter: string;
  see_recap: string;
  continue: string;
  return_to_text: string;
  // the import sheet (UploadBookModal)
  choose_file_first: string;
  sending: string;
  upload_done: string;
  upload_failed: string;
  upload_too_long: string;
  generic_error: string;
  file_size: string;
  drop_here: string;
  drop_hint: string;
  title_label: string;
  title_placeholder: string;
  author_label: string;
  author_placeholder: string;
  levels_label: string;
  levels_placeholder: string;
  levels_hint: string;
  whole_book: string;
  processing: string;
  import_the_book: string;
  cancel: string;
};

const fr: BibliothequeCopy = {
  shelf_loading: 'Ouverture de la bibliothèque…',
  shelf_count_one: '{n} texte sur l’étagère',
  shelf_count_many: '{n} textes sur l’étagère',
  shelf_intro:
    'Les livres importés et les lectures d’à-côté vivent ici. Le feuilleton du jour reste dans Le Feuilleton.',
  import_book: 'Importer un livre',
  shelf_loading_sr: 'Chargement de la bibliothèque',
  shelf_error_title: 'L’étagère n’a pas pu être ouverte.',
  shelf_error_body: 'La liaison avec la bibliothèque a échoué. Rien n’est perdu ; réessayez dans un instant.',
  retry: 'Réessayer',
  shelf_empty_title: 'L’étagère est encore vide.',
  shelf_empty_body: 'Importez un livre et il sera découpé en courtes épisodes de lecture, rangés ici.',
  shelf_empty_action: 'Importer un premier livre',
  hero_aria: 'Texte en cours',
  no_cover: 'La couverture de ce texte n’est pas encore parue.',
  on_shelf: 'Sur l’étagère',
  by_author: 'De {author}',
  in_progress: 'En cours : {chapter}',
  locked: 'Verrouillé',
  resume_reading: 'Reprendre la lecture',
  start_reading: 'Commencer la lecture',
  rest_aria: 'Le reste de l’étagère',
  read_badge: 'Lu',
  detail_aria: 'Un texte de la bibliothèque',
  back_to_library: 'Retour à la bibliothèque',
  text_opening: 'Ouverture du texte…',
  text_not_found: 'Ce texte est introuvable.',
  text_removed: 'Il a peut-être été retiré de l’étagère.',
  chapter_count_one: '{n} chapitre',
  chapter_count_many: '{n} chapitres',
  about_text: 'À propos de ce texte',
  chapters: 'Les chapitres',
  chapters_all_read: 'Tous les chapitres sont lus.',
  chapters_pick_up: 'Reprenez là où vous vous êtes arrêté.',
  chapters_unlock: 'Les chapitres s’ouvrent au fil de la lecture.',
  back_to_shelf: 'Retour à l’étagère',
  opening: 'Ouverture…',
  gate_aria: 'Ouverture du chapitre',
  chapter_opening: 'Ouverture du chapitre…',
  session_opening: 'Ouverture de la séance…',
  session_failed: 'La séance n’a pas pu s’ouvrir.',
  back_to_text: 'Retour au texte',
  chapter_not_found: 'Ce chapitre est introuvable.',
  chapter_removed: 'Il a peut-être été retiré du texte.',
  leave_chapter: 'Quitter le chapitre',
  chapter_n: 'Chapitre {n}',
  conversation_aria: 'La conversation',
  to_fix: 'À reprendre',
  nothing_to_fix: 'Rien à reprendre.',
  typing: 'En train d’écrire…',
  suggested_words: 'Mots suggérés',
  answer_label: 'Votre réponse, en français',
  answer_placeholder: 'Écrivez en français…',
  send: 'Envoyer',
  connected: 'En liaison',
  connecting: 'Liaison en cours…',
  aside_aria: 'Le suivi du chapitre',
  progress_heading: 'Progression dans le chapitre',
  goals_reached: 'Objectifs atteints',
  words_used: 'Mots employés',
  xp_earned: 'XP gagnés',
  perfect_possible: 'Un chapitre sans faute est encore possible.',
  closing: 'Clôture…',
  finish_chapter: 'Terminer le chapitre',
  goals_missing: 'Encore quelques objectifs à atteindre',
  can_close: 'Vous pouvez clore ce chapitre dès maintenant.',
  reach_goals_one: 'Atteignez au moins {n} objectif pour le clore.',
  reach_goals_many: 'Atteignez au moins {n} objectifs pour le clore.',
  done_story: 'Texte terminé',
  done_perfect: 'Chapitre sans faute',
  done_chapter: 'Chapitre terminé',
  finished_story: 'Vous avez fini « {title} ».',
  all_goals: 'Tous les objectifs sont atteints.',
  reading_goes_on: 'La lecture continue.',
  perfect_bonus: 'Bonus sans faute compris',
  achievements: 'Distinctions débloquées',
  new_achievement: 'Nouvelle distinction',
  next_chapter: 'Chapitre suivant',
  see_recap: 'Voir le récapitulatif',
  continue: 'Continuer',
  return_to_text: 'Revenir au texte',
  choose_file_first: 'Choisissez d’abord un fichier.',
  sending: 'Envoi en cours…',
  upload_done: 'Le livre est rangé sur l’étagère.',
  upload_failed: 'La lecture du livre a échoué.',
  upload_too_long: 'Le traitement a pris trop de temps.',
  generic_error: 'Une erreur est survenue.',
  file_size: '{size} Mo',
  drop_here: 'Déposez un fichier ici',
  drop_hint: 'ou touchez pour en choisir un · TXT, PDF, EPUB, HTML (10 Mo max)',
  title_label: 'Titre (facultatif)',
  title_placeholder: 'par ex. Moby Dick',
  author_label: 'Auteur (facultatif)',
  author_placeholder: 'par ex. Herman Melville',
  levels_label: 'Niveaux visés',
  levels_placeholder: 'par ex. A1,A2,B1',
  levels_hint: 'Séparés par des virgules (A1, A2, B1, B2, C1, C2).',
  whole_book:
    'Le livre entier est traité : le texte est découpé en courtes épisodes de lecture, conservés dans votre bibliothèque.',
  processing: 'Traitement du livre',
  import_the_book: 'Importer le livre',
  cancel: 'Annuler',
};

const en: BibliothequeCopy = {
  shelf_loading: 'Opening the Bibliothèque…',
  shelf_count_one: '{n} text on the shelf',
  shelf_count_many: '{n} texts on the shelf',
  shelf_intro: 'Imported books and side reading live here. Today’s episode stays in Le Feuilleton.',
  import_book: 'Import a book',
  shelf_loading_sr: 'Loading the Bibliothèque',
  shelf_error_title: 'The shelf could not be opened.',
  shelf_error_body: 'We couldn’t reach the Bibliothèque. Nothing is lost; try again in a moment.',
  retry: 'Try again',
  shelf_empty_title: 'The shelf is still empty.',
  shelf_empty_body: 'Import a book and it will be cut into short reading episodes, kept here.',
  shelf_empty_action: 'Import a first book',
  hero_aria: 'Text in progress',
  no_cover: 'This text’s cover isn’t out yet.',
  on_shelf: 'On the shelf',
  by_author: 'By {author}',
  in_progress: 'In progress: {chapter}',
  locked: 'Locked',
  resume_reading: 'Resume reading',
  start_reading: 'Start reading',
  rest_aria: 'The rest of the shelf',
  read_badge: 'Read',
  detail_aria: 'A text from the Bibliothèque',
  back_to_library: 'Back to the Bibliothèque',
  text_opening: 'Opening the text…',
  text_not_found: 'This text can’t be found.',
  text_removed: 'It may have been taken off the shelf.',
  chapter_count_one: '{n} chapter',
  chapter_count_many: '{n} chapters',
  about_text: 'About this text',
  chapters: 'Chapters',
  chapters_all_read: 'All chapters are read.',
  chapters_pick_up: 'Pick up where you left off.',
  chapters_unlock: 'Chapters open as you read.',
  back_to_shelf: 'Back to the shelf',
  opening: 'Opening…',
  gate_aria: 'Opening the chapter',
  chapter_opening: 'Opening the chapter…',
  session_opening: 'Opening the session…',
  session_failed: 'The session couldn’t open.',
  back_to_text: 'Back to the text',
  chapter_not_found: 'This chapter can’t be found.',
  chapter_removed: 'It may have been removed from the text.',
  leave_chapter: 'Leave the chapter',
  chapter_n: 'Chapter {n}',
  conversation_aria: 'The conversation',
  to_fix: 'To fix',
  nothing_to_fix: 'Nothing to fix.',
  typing: 'Typing…',
  suggested_words: 'Suggested words',
  answer_label: 'Your answer, in French',
  answer_placeholder: 'Write in French…',
  send: 'Send',
  connected: 'Connected',
  connecting: 'Connecting…',
  aside_aria: 'Chapter progress',
  progress_heading: 'Progress in this chapter',
  goals_reached: 'Goals reached',
  words_used: 'Words used',
  xp_earned: 'XP earned',
  perfect_possible: 'A perfect chapter is still possible.',
  closing: 'Closing…',
  finish_chapter: 'Finish the chapter',
  goals_missing: 'A few more goals to reach',
  can_close: 'You can close this chapter now.',
  reach_goals_one: 'Reach at least {n} goal to close it.',
  reach_goals_many: 'Reach at least {n} goals to close it.',
  done_story: 'Text finished',
  done_perfect: 'Perfect chapter',
  done_chapter: 'Chapter finished',
  finished_story: 'You finished “{title}”.',
  all_goals: 'Every goal is reached.',
  reading_goes_on: 'The reading goes on.',
  perfect_bonus: 'Perfect bonus included',
  achievements: 'Achievements unlocked',
  new_achievement: 'New achievement',
  next_chapter: 'Next chapter',
  see_recap: 'See the summary',
  continue: 'Continue',
  return_to_text: 'Back to the text',
  choose_file_first: 'Choose a file first.',
  sending: 'Uploading…',
  upload_done: 'The book is on the shelf.',
  upload_failed: 'The book couldn’t be read.',
  upload_too_long: 'Processing took too long.',
  generic_error: 'Something went wrong.',
  file_size: '{size} MB',
  drop_here: 'Drop a file here',
  drop_hint: 'or tap to choose one · TXT, PDF, EPUB, HTML (10 MB max)',
  title_label: 'Title (optional)',
  title_placeholder: 'e.g. Moby Dick',
  author_label: 'Author (optional)',
  author_placeholder: 'e.g. Herman Melville',
  levels_label: 'Target levels',
  levels_placeholder: 'e.g. A1,A2,B1',
  levels_hint: 'Separated by commas (A1, A2, B1, B2, C1, C2).',
  whole_book:
    'The whole book is processed: the text is cut into short reading episodes, kept in your Bibliothèque.',
  processing: 'Processing the book',
  import_the_book: 'Import the book',
  cancel: 'Cancel',
};

const de: BibliothequeCopy = {
  shelf_loading: 'Die Bibliothèque wird geöffnet…',
  shelf_count_one: '{n} Text im Regal',
  shelf_count_many: '{n} Texte im Regal',
  shelf_intro:
    'Hier stehen importierte Bücher und Lektüre für nebenbei. Die Folge des Tages bleibt im Feuilleton.',
  import_book: 'Buch importieren',
  shelf_loading_sr: 'Die Bibliothèque wird geladen',
  shelf_error_title: 'Das Regal konnte nicht geöffnet werden.',
  shelf_error_body:
    'Die Verbindung zur Bibliothèque ist fehlgeschlagen. Nichts ist verloren; versuchen Sie es gleich noch einmal.',
  retry: 'Erneut versuchen',
  shelf_empty_title: 'Das Regal ist noch leer.',
  shelf_empty_body: 'Importieren Sie ein Buch – es wird in kurze Leseepisoden geteilt und hier abgelegt.',
  shelf_empty_action: 'Erstes Buch importieren',
  hero_aria: 'Aktueller Text',
  no_cover: 'Das Cover dieses Textes ist noch nicht erschienen.',
  on_shelf: 'Im Regal',
  by_author: 'Von {author}',
  in_progress: 'Aktuell: {chapter}',
  locked: 'Gesperrt',
  resume_reading: 'Weiterlesen',
  start_reading: 'Lesen beginnen',
  rest_aria: 'Der Rest des Regals',
  read_badge: 'Gelesen',
  detail_aria: 'Ein Text aus der Bibliothèque',
  back_to_library: 'Zurück zur Bibliothèque',
  text_opening: 'Der Text wird geöffnet…',
  text_not_found: 'Dieser Text wurde nicht gefunden.',
  text_removed: 'Vielleicht wurde er aus dem Regal genommen.',
  chapter_count_one: '{n} Kapitel',
  chapter_count_many: '{n} Kapitel',
  about_text: 'Über diesen Text',
  chapters: 'Die Kapitel',
  chapters_all_read: 'Alle Kapitel sind gelesen.',
  chapters_pick_up: 'Machen Sie dort weiter, wo Sie aufgehört haben.',
  chapters_unlock: 'Die Kapitel öffnen sich beim Lesen.',
  back_to_shelf: 'Zurück zum Regal',
  opening: 'Wird geöffnet…',
  gate_aria: 'Das Kapitel wird geöffnet',
  chapter_opening: 'Das Kapitel wird geöffnet…',
  session_opening: 'Die Sitzung wird geöffnet…',
  session_failed: 'Die Sitzung konnte nicht geöffnet werden.',
  back_to_text: 'Zurück zum Text',
  chapter_not_found: 'Dieses Kapitel wurde nicht gefunden.',
  chapter_removed: 'Vielleicht wurde es aus dem Text entfernt.',
  leave_chapter: 'Kapitel verlassen',
  chapter_n: 'Kapitel {n}',
  conversation_aria: 'Das Gespräch',
  to_fix: 'Zu verbessern',
  nothing_to_fix: 'Nichts zu verbessern.',
  typing: 'Schreibt…',
  suggested_words: 'Vorgeschlagene Wörter',
  answer_label: 'Ihre Antwort, auf Französisch',
  answer_placeholder: 'Schreiben Sie auf Französisch…',
  send: 'Senden',
  connected: 'Verbunden',
  connecting: 'Verbindung wird hergestellt…',
  aside_aria: 'Fortschritt im Kapitel',
  progress_heading: 'Fortschritt im Kapitel',
  goals_reached: 'Erreichte Ziele',
  words_used: 'Verwendete Wörter',
  xp_earned: 'Erhaltene XP',
  perfect_possible: 'Ein fehlerfreies Kapitel ist noch möglich.',
  closing: 'Wird abgeschlossen…',
  finish_chapter: 'Kapitel abschließen',
  goals_missing: 'Noch ein paar Ziele zu erreichen',
  can_close: 'Sie können dieses Kapitel jetzt abschließen.',
  reach_goals_one: 'Erreichen Sie mindestens {n} Ziel, um es abzuschließen.',
  reach_goals_many: 'Erreichen Sie mindestens {n} Ziele, um es abzuschließen.',
  done_story: 'Text beendet',
  done_perfect: 'Fehlerfreies Kapitel',
  done_chapter: 'Kapitel beendet',
  finished_story: 'Sie haben „{title}“ beendet.',
  all_goals: 'Alle Ziele sind erreicht.',
  reading_goes_on: 'Die Lektüre geht weiter.',
  perfect_bonus: 'Bonus für ein fehlerfreies Kapitel inklusive',
  achievements: 'Freigeschaltete Auszeichnungen',
  new_achievement: 'Neue Auszeichnung',
  next_chapter: 'Nächstes Kapitel',
  see_recap: 'Zusammenfassung ansehen',
  continue: 'Weiter',
  return_to_text: 'Zurück zum Text',
  choose_file_first: 'Wählen Sie zuerst eine Datei.',
  sending: 'Wird hochgeladen…',
  upload_done: 'Das Buch steht im Regal.',
  upload_failed: 'Das Buch konnte nicht gelesen werden.',
  upload_too_long: 'Die Verarbeitung hat zu lange gedauert.',
  generic_error: 'Ein Fehler ist aufgetreten.',
  file_size: '{size} MB',
  drop_here: 'Datei hier ablegen',
  drop_hint: 'oder tippen, um eine auszuwählen · TXT, PDF, EPUB, HTML (max. 10 MB)',
  title_label: 'Titel (optional)',
  title_placeholder: 'z. B. Moby Dick',
  author_label: 'Autor (optional)',
  author_placeholder: 'z. B. Herman Melville',
  levels_label: 'Zielniveaus',
  levels_placeholder: 'z. B. A1,A2,B1',
  levels_hint: 'Durch Kommas getrennt (A1, A2, B1, B2, C1, C2).',
  whole_book:
    'Das ganze Buch wird verarbeitet: Der Text wird in kurze Leseepisoden geteilt und in Ihrer Bibliothèque abgelegt.',
  processing: 'Das Buch wird verarbeitet',
  import_the_book: 'Buch importieren',
  cancel: 'Abbrechen',
};

export const BIBLIOTHEQUE_COPY: Record<ControlLanguage, BibliothequeCopy> = { en, de, fr };

export function bibliothequeCopy(language: unknown): BibliothequeCopy {
  return BIBLIOTHEQUE_COPY[normalizeControlLanguage(language)];
}

/** `fill('{n} textes', { n: 3 })` → `3 textes`. Unknown holes are left as written. */
export function fill(template: string, values: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (hole, key: string) =>
    key in values ? String(values[key]) : hole,
  );
}
