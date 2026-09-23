/**
 * WP-82 — Le Lexique follows the one language rule.
 *
 * The Lexique's own words — the buttons, the deck states, the counts, the
 * empty/error/loading states, the aria-labels, the page titles — are chrome:
 * up to A2 they are the learner's language, from B1 they are French
 * (`chromeLanguage`, `lib/language-rule.ts`). The French words themselves, the
 * example sentences and the conjugation forms are content and stay French
 * whatever this table says; the gloss arrives from the server already in the
 * learner's language. Place names (Lexique, Cahier, Courrier, Feuilleton) and
 * the deck's name (Français 5000) are French in every column.
 *
 * Every table has the same keys (the language test proves it). `{n}`-style
 * placeholders are filled with `fill`.
 */

import { useControlLanguage } from '@/components/atelier-v2/ui';
import { normalizeControlLanguage } from '@/lib/atelier-v2-copy';
import type { ControlLanguage } from '@/types/daily-journey';

export type LexiqueCopy = {
  // shared
  locale: string;
  retry: string;
  next_on: string;
  filed: string;
  review_failed: string;
  flip_front: string;
  flip_back: string;
  rank: string;
  day_one: string;
  day_many: string;
  // the four FSRS grades (Cahier sheet and conjugation drill)
  grade_again: string;
  grade_again_hint: string;
  grade_hard: string;
  grade_hard_hint: string;
  grade_good: string;
  grade_good_hint: string;
  grade_easy: string;
  grade_easy_hint: string;
  ratings_group: string;
  rate_as: string;
  // the four grades as the review deck says them
  deck_again: string;
  deck_hard: string;
  deck_good: string;
  deck_easy: string;
  deck_know: string;
  // part of speech, whitelisted
  pos_noun: string;
  pos_verb: string;
  pos_adjective: string;
  pos_adverb: string;
  pos_pronoun: string;
  pos_preposition: string;
  pos_determiner: string;
  pos_conjunction: string;
  pos_interjection: string;
  pos_number: string;
  // mastery states and queue buckets
  state_new: string;
  state_due: string;
  state_fragile: string;
  state_building: string;
  state_solid: string;
  state_mastered: string;
  bucket_linked: string;
  bucket_topic: string;
  bucket_new_deck: string;
  count_fragile_one: string;
  count_fragile_many: string;
  count_new_one: string;
  count_new_many: string;
  count_due: string;
  // the registre (vocabulary.tsx)
  head_title: string;
  search_label: string;
  search_placeholder: string;
  search_clear: string;
  count_loading: string;
  cta_review_one: string;
  cta_review_many: string;
  cta_open_review: string;
  filter_group: string;
  chip_all: string;
  chip_due: string;
  chip_fragile: string;
  chip_new: string;
  chip_mastered: string;
  map_building: string;
  map_solid: string;
  filter_clear: string;
  shown_one: string;
  shown_many: string;
  searching: string;
  queue_title: string;
  queue_error_title: string;
  queue_error_body: string;
  queue_empty_title: string;
  queue_empty_filtered: string;
  queue_empty_body: string;
  queue_clear_filters: string;
  registre_title: string;
  registre_error_title: string;
  registre_error_body: string;
  registre_empty_title: string;
  registre_empty_body: string;
  atlas_title: string;
  atlas_meta: string;
  atlas_open: string;
  atlas_close: string;
  cefr_title: string;
  cefr_note: string;
  topics_title: string;
  topics_note: string;
  verbs_title: string;
  verbs_note: string;
  verbs_track: string;
  verbs_cta: string;
  map_title: string;
  map_cell: string;
  map_aria: string;
  map_note: string;
  dossier_label: string;
  dossier_fallback: string;
  dossier_repairs: string;
  dossier_reviews: string;
  dossier_seen: string;
  dossier_used: string;
  // the word sheet
  details_label: string;
  tile_rank: string;
  tile_nature: string;
  tile_level: string;
  tile_source: string;
  source_registre: string;
  anchor_label: string;
  examples_title: string;
  loading_note: string;
  example_one: string;
  example_many: string;
  examples_empty: string;
  ex_example: string;
  ex_definition: string;
  ex_usage: string;
  ex_letter_fallback: string;
  ex_scene_fallback: string;
  ex_your_turn: string;
  ex_reply: string;
  conversation: string;
  tracking_title: string;
  tracking_current: string;
  tracking_never: string;
  srs_state: string;
  srs_next: string;
  srs_next_none: string;
  srs_last: string;
  srs_last_none: string;
  srs_interval: string;
  srs_interval_none: string;
  srs_reviews: string;
  srs_lapses: string;
  srs_learning: string;
  srs_review: string;
  srs_relearning: string;
  traces_title: string;
  trace_one: string;
  trace_many: string;
  traces_empty: string;
  trace_letter: string;
  trace_scene: string;
  event_default: string;
  event_seen_context: string;
  event_recognized: string;
  event_produced_correct: string;
  event_produced_incorrect: string;
  event_missed_target: string;
  conv_prefix: string;
  conv_targeted: string;
  conv_used: string;
  conv_suggested: string;
  conv_planned: string;
  conv_passage: string;
  action_biography: string;
  action_letter: string;
  action_feuilleton: string;
  composing: string;
  ratings_note: string;
  word_open_failed: string;
  biography_failed: string;
  letter_failed: string;
  episode_failed: string;
  // the review deck (vocabulary/review.tsx)
  review_head_title: string;
  review_aria: string;
  close_review: string;
  progress_aria: string;
  opening_deck: string;
  cached_notice: string;
  deck_error_title: string;
  deck_unavailable: string;
  audio_failed: string;
  due_on: string;
  rating_fallback: string;
  anchored_with: string;
  composition: string;
  and_word: string;
  word_of_day: string;
  cards_one: string;
  cards_many: string;
  about_minutes: string;
  filed_one: string;
  filed_many: string;
  nothing_due: string;
  listen_prompt: string;
  listen: string;
  playing: string;
  listen_hint: string;
  cue_aria: string;
  input_placeholder: string;
  input_placeholder_audio: string;
  input_aria: string;
  open_story: string;
  story_title: string;
  verdict_exact: string;
  verdict_yours: string;
  reveal_first: string;
  reveal_before: string;
  done_aria: string;
  done_label: string;
  done_title: string;
  returning: string;
  refresh: string;
  // the conjugation drill (vocabulary/conjugation.tsx)
  conj_head_title: string;
  conj_title: string;
  conj_close: string;
  conj_progress: string;
  conj_loading: string;
  conj_error: string;
  conj_empty: string;
  conj_done_one: string;
  conj_done_many: string;
  conj_to_words: string;
  conj_field: string;
  conj_placeholder: string;
  conj_input_aria: string;
  conj_reveal: string;
  conj_right: string;
  conj_rate_group: string;
  // les mots du jour (MotsDuJour.tsx)
  mdj_aria: string;
  mdj_label: string;
  mdj_tripled: string;
  mdj_open: string;
  stamp_lu: string;
  stamp_retrouve: string;
  stamp_place: string;
  stamp_triple: string;
  stamps_count: string;
};

const EN: LexiqueCopy = {
  locale: 'en-GB',
  retry: 'Try again',
  next_on: 'Next review {date}',
  filed: 'Review saved',
  review_failed: 'The review couldn’t be saved.',
  flip_front: 'Tap to turn',
  flip_back: 'Meaning · tap to go back',
  rank: 'rank {n}',
  day_one: '{n} day',
  day_many: '{n} days',
  grade_again: 'Again',
  grade_again_hint: 'Very soon',
  grade_hard: 'Hard',
  grade_hard_hint: 'Keep it close',
  grade_good: 'Good',
  grade_good_hint: 'Normal pace',
  grade_easy: 'Easy',
  grade_easy_hint: 'Space it out',
  ratings_group: 'Rate the card',
  rate_as: 'Rate: {label}',
  deck_again: 'Again',
  deck_hard: 'Hard',
  deck_good: 'Good',
  deck_easy: 'Easy',
  deck_know: 'I know it',
  pos_noun: 'noun',
  pos_verb: 'verb',
  pos_adjective: 'adjective',
  pos_adverb: 'adverb',
  pos_pronoun: 'pronoun',
  pos_preposition: 'preposition',
  pos_determiner: 'determiner',
  pos_conjunction: 'conjunction',
  pos_interjection: 'interjection',
  pos_number: 'number',
  state_new: 'New',
  state_due: 'To review',
  state_fragile: 'Fragile',
  state_building: 'Learning',
  state_solid: 'Solid',
  state_mastered: 'Known',
  bucket_linked: 'Related word',
  bucket_topic: 'On topic',
  bucket_new_deck: 'Today’s new words',
  count_fragile_one: '{n} fragile',
  count_fragile_many: '{n} fragile',
  count_new_one: '{n} new',
  count_new_many: '{n} new',
  count_due: '{n} to review',
  head_title: 'Cahier · Lexique · L’Atelier',
  search_label: 'Search for a word',
  search_placeholder: 'Search for a word…',
  search_clear: 'Clear the search',
  count_loading: 'Opening…',
  cta_review_one: 'Review · {n} word',
  cta_review_many: 'Review · {n} words',
  cta_open_review: 'Open the review',
  filter_group: 'Filter the words',
  chip_all: 'All',
  chip_due: 'To review',
  chip_fragile: 'Fragile',
  chip_new: 'New',
  chip_mastered: 'Known',
  map_building: 'Learning',
  map_solid: 'Solid',
  filter_clear: 'Clear',
  shown_one: '{n} word shown',
  shown_many: '{n} words shown',
  searching: 'Searching…',
  queue_title: 'Today’s queue',
  queue_error_title: 'The word list couldn’t be opened.',
  queue_error_body: 'Grammar is still available.',
  queue_empty_title: 'Nothing in the queue',
  queue_empty_filtered: 'No word matches this filter.',
  queue_empty_body: 'Your word list is below.',
  queue_clear_filters: 'Clear the filters',
  registre_title: 'Word list · Français 5000',
  registre_error_title: 'The word list isn’t responding.',
  registre_error_body: 'Try again in a moment.',
  registre_empty_title: 'No words found',
  registre_empty_body: 'Try another search.',
  atlas_title: 'Word atlas',
  atlas_meta: '{nailed} of {total} words known',
  atlas_open: 'Show',
  atlas_close: 'Hide',
  cefr_title: 'CEFR coverage',
  cefr_note: 'words known per level',
  topics_title: 'By topic',
  topics_note: '{n} in progress',
  verbs_title: 'Verbs and structures',
  verbs_note: 'conjugation',
  verbs_track: 'Verbs',
  verbs_cta: 'Practise irregular forms',
  map_title: 'Mastery map · Français 5000',
  map_cell: '1 square = 1 word',
  map_aria: 'Mastery map',
  map_note: 'The first {n} words by frequency.',
  dossier_label: 'This week',
  dossier_fallback: 'Your word list is growing.',
  dossier_repairs: 'Fixes',
  dossier_reviews: 'Reviews',
  dossier_seen: 'Seen',
  dossier_used: 'Used',
  details_label: 'Word details',
  tile_rank: 'Frequency rank',
  tile_nature: 'Part of speech',
  tile_level: 'Difficulty',
  tile_source: 'Source',
  source_registre: 'word list',
  anchor_label: 'Anchor sentence',
  examples_title: 'Examples by source',
  loading_note: 'loading',
  example_one: '{n} example',
  example_many: '{n} examples',
  examples_empty: 'No examples yet.',
  ex_example: 'Example',
  ex_definition: 'Definition',
  ex_usage: 'Usage notes',
  ex_letter_fallback: 'Letter prompt',
  ex_scene_fallback: 'Feuilleton scene',
  ex_your_turn: 'Your turn',
  ex_reply: 'The reply',
  conversation: 'Conversation',
  tracking_title: 'Progress',
  tracking_current: 'up to date',
  tracking_never: 'never reviewed',
  srs_state: 'Status',
  srs_next: 'Next review',
  srs_next_none: 'Not scheduled',
  srs_last: 'Last review',
  srs_last_none: 'Never reviewed',
  srs_interval: 'Interval',
  srs_interval_none: 'New card',
  srs_reviews: 'Reviews',
  srs_lapses: 'Lapses',
  srs_learning: 'Learning',
  srs_review: 'In review',
  srs_relearning: 'Relearning',
  traces_title: 'Recent traces',
  trace_one: '{n} trace',
  trace_many: '{n} traces',
  traces_empty: 'This word hasn’t come up yet.',
  trace_letter: 'Targeted in a letter',
  trace_scene: 'Targeted in a scene',
  event_default: 'Met in practice',
  event_seen_context: 'Seen in context',
  event_recognized: 'Recognised',
  event_produced_correct: 'Used correctly',
  event_produced_incorrect: 'Used, then fixed',
  event_missed_target: 'Missed',
  conv_prefix: 'In conversation: {bits}',
  conv_targeted: 'targeted',
  conv_used: 'used',
  conv_suggested: 'suggested',
  conv_planned: 'planned',
  conv_passage: 'Conversation passage',
  action_biography: 'The word’s story',
  action_letter: 'Use it in a letter',
  action_feuilleton: 'Read it in the Feuilleton',
  composing: 'Writing…',
  ratings_note: 'Turn the card before you rate it.',
  word_open_failed: 'This word couldn’t be opened.',
  biography_failed: 'This word’s story couldn’t be opened.',
  letter_failed: 'The letter couldn’t be written.',
  episode_failed: 'The episode couldn’t be written.',
  review_head_title: 'Lexique · Review · L’Atelier',
  review_aria: 'Lexique — review',
  close_review: 'Leave the review',
  progress_aria: 'Review progress',
  opening_deck: 'Opening the deck…',
  cached_notice: 'Earlier edition · updating…',
  deck_error_title: 'Deck unavailable',
  deck_unavailable: 'The review is unavailable.',
  audio_failed: 'Playback failed.',
  due_on: 'Due {date}',
  rating_fallback: 'Saved',
  anchored_with: 'From your story with {name}',
  composition: 'Including {list}.',
  and_word: 'and',
  word_of_day: 'Word of the day',
  cards_one: '{n} card',
  cards_many: '{n} cards',
  about_minutes: 'about {n} min',
  filed_one: '{n} card saved',
  filed_many: '{n} cards saved',
  nothing_due: 'Nothing to review today',
  listen_prompt: 'Listen to the French word',
  listen: 'Listen',
  playing: 'Playing…',
  listen_hint: 'Listen · answer',
  cue_aria: 'Visual hint: {label}',
  input_placeholder: 'Write the French word',
  input_placeholder_audio: 'Write what you heard',
  input_aria: 'Write the French answer',
  open_story: 'Open the story of {word}',
  story_title: 'The word’s story',
  verdict_exact: 'Exactly right',
  verdict_yours: 'You wrote: {answer}',
  reveal_first: 'Show the answer',
  reveal_before: 'Show the answer before rating',
  done_aria: 'End of the review',
  done_label: 'Spaced review',
  done_title: 'Deck cleared',
  returning: 'Going back…',
  refresh: 'Refresh',
  conj_head_title: 'Cahier · Conjugation · L’Atelier',
  conj_title: 'Irregular forms',
  conj_close: 'Back to the word list',
  conj_progress: '{n}% of the round',
  conj_loading: 'Getting the drill ready.',
  conj_error: 'The conjugation drill isn’t responding right now.',
  conj_empty: 'No irregular forms waiting.',
  conj_done_one: '{n} form practised this round.',
  conj_done_many: '{n} forms practised this round.',
  conj_to_words: 'Review vocabulary',
  conj_field: 'The conjugated form',
  conj_placeholder: 'Write the form',
  conj_input_aria: 'Write the conjugated form',
  conj_reveal: 'Show the table',
  conj_right: 'Right',
  conj_rate_group: 'Rate this form',
  mdj_aria: 'Lexique — words of the day',
  mdj_label: 'Lexique · words of the day',
  mdj_tripled: 'All three stamps',
  mdj_open: 'Open the Lexique review',
  stamp_lu: 'Read',
  stamp_retrouve: 'Recalled',
  stamp_place: 'Used',
  stamp_triple: 'Triple',
  stamps_count: '{n} of 3',
};

const DE: LexiqueCopy = {
  locale: 'de-DE',
  retry: 'Erneut versuchen',
  next_on: 'Nächste Wiederholung am {date}',
  filed: 'Wiederholung gespeichert',
  review_failed: 'Die Wiederholung konnte nicht gespeichert werden.',
  flip_front: 'Tippen zum Umdrehen',
  flip_back: 'Bedeutung · tippen zum Zurückdrehen',
  rank: 'Rang {n}',
  day_one: '{n} Tag',
  day_many: '{n} Tage',
  grade_again: 'Nochmal',
  grade_again_hint: 'Sehr bald',
  grade_hard: 'Schwer',
  grade_hard_hint: 'Nah dranbleiben',
  grade_good: 'Gut',
  grade_good_hint: 'Normaler Rhythmus',
  grade_easy: 'Leicht',
  grade_easy_hint: 'Mehr Abstand',
  ratings_group: 'Karte bewerten',
  rate_as: 'Bewerten: {label}',
  deck_again: 'Nochmal',
  deck_hard: 'Schwer',
  deck_good: 'Gut',
  deck_easy: 'Leicht',
  deck_know: 'Weiß ich',
  pos_noun: 'Nomen',
  pos_verb: 'Verb',
  pos_adjective: 'Adjektiv',
  pos_adverb: 'Adverb',
  pos_pronoun: 'Pronomen',
  pos_preposition: 'Präposition',
  pos_determiner: 'Artikelwort',
  pos_conjunction: 'Konjunktion',
  pos_interjection: 'Interjektion',
  pos_number: 'Zahlwort',
  state_new: 'Neu',
  state_due: 'Fällig',
  state_fragile: 'Wackelig',
  state_building: 'Im Aufbau',
  state_solid: 'Sicher',
  state_mastered: 'Gelernt',
  bucket_linked: 'Verwandtes Wort',
  bucket_topic: 'Zum Thema',
  bucket_new_deck: 'Neue Wörter von heute',
  count_fragile_one: '{n} wackelig',
  count_fragile_many: '{n} wackelig',
  count_new_one: '{n} neu',
  count_new_many: '{n} neu',
  count_due: '{n} fällig',
  head_title: 'Cahier · Lexique · L’Atelier',
  search_label: 'Wort suchen',
  search_placeholder: 'Wort suchen…',
  search_clear: 'Suche löschen',
  count_loading: 'Wird geöffnet…',
  cta_review_one: 'Wiederholen · {n} Wort',
  cta_review_many: 'Wiederholen · {n} Wörter',
  cta_open_review: 'Wiederholung öffnen',
  filter_group: 'Wörter filtern',
  chip_all: 'Alle',
  chip_due: 'Fällig',
  chip_fragile: 'Wackelig',
  chip_new: 'Neu',
  chip_mastered: 'Gelernt',
  map_building: 'Im Aufbau',
  map_solid: 'Sicher',
  filter_clear: 'Löschen',
  shown_one: '{n} Wort angezeigt',
  shown_many: '{n} Wörter angezeigt',
  searching: 'Suche…',
  queue_title: 'Heute dran',
  queue_error_title: 'Die Wortliste konnte nicht geöffnet werden.',
  queue_error_body: 'Die Grammatik bleibt verfügbar.',
  queue_empty_title: 'Heute nichts dran',
  queue_empty_filtered: 'Kein Wort passt zu diesem Filter.',
  queue_empty_body: 'Deine Wortliste steht weiter unten.',
  queue_clear_filters: 'Filter löschen',
  registre_title: 'Wortliste · Français 5000',
  registre_error_title: 'Die Wortliste antwortet nicht.',
  registre_error_body: 'Versuch es gleich noch einmal.',
  registre_empty_title: 'Keine Wörter gefunden',
  registre_empty_body: 'Versuch einen anderen Suchbegriff.',
  atlas_title: 'Wortatlas',
  atlas_meta: '{nailed} von {total} Wörtern sicher',
  atlas_open: 'Anzeigen',
  atlas_close: 'Ausblenden',
  cefr_title: 'GER-Abdeckung',
  cefr_note: 'sichere Wörter pro Niveau',
  topics_title: 'Nach Thema',
  topics_note: '{n} in Arbeit',
  verbs_title: 'Verben und Strukturen',
  verbs_note: 'Konjugation',
  verbs_track: 'Verben',
  verbs_cta: 'Unregelmäßige Formen üben',
  map_title: 'Lernkarte · Français 5000',
  map_cell: '1 Feld = 1 Wort',
  map_aria: 'Lernkarte',
  map_note: 'Die ersten {n} Wörter nach Häufigkeit.',
  dossier_label: 'Diese Woche',
  dossier_fallback: 'Deine Wortliste wächst.',
  dossier_repairs: 'Korrekturen',
  dossier_reviews: 'Wiederholungen',
  dossier_seen: 'Gesehen',
  dossier_used: 'Verwendet',
  details_label: 'Wortdetails',
  tile_rank: 'Häufigkeitsrang',
  tile_nature: 'Wortart',
  tile_level: 'Schwierigkeit',
  tile_source: 'Herkunft',
  source_registre: 'Wortliste',
  anchor_label: 'Ankersatz',
  examples_title: 'Beispiele nach Quelle',
  loading_note: 'lädt',
  example_one: '{n} Beispiel',
  example_many: '{n} Beispiele',
  examples_empty: 'Noch keine Beispiele.',
  ex_example: 'Beispiel',
  ex_definition: 'Definition',
  ex_usage: 'Verwendung',
  ex_letter_fallback: 'Briefaufgabe',
  ex_scene_fallback: 'Feuilleton-Szene',
  ex_your_turn: 'Du',
  ex_reply: 'Die Antwort',
  conversation: 'Gespräch',
  tracking_title: 'Fortschritt',
  tracking_current: 'aktuell',
  tracking_never: 'noch nie wiederholt',
  srs_state: 'Stand',
  srs_next: 'Nächste Wiederholung',
  srs_next_none: 'Nicht geplant',
  srs_last: 'Letzte Wiederholung',
  srs_last_none: 'Noch nie wiederholt',
  srs_interval: 'Abstand',
  srs_interval_none: 'Neue Karte',
  srs_reviews: 'Wiederholungen',
  srs_lapses: 'Vergessen',
  srs_learning: 'In der Lernphase',
  srs_review: 'In Wiederholung',
  srs_relearning: 'Neu lernen',
  traces_title: 'Letzte Spuren',
  trace_one: '{n} Spur',
  trace_many: '{n} Spuren',
  traces_empty: 'Dieses Wort ist noch nirgends aufgetaucht.',
  trace_letter: 'In einem Brief geübt',
  trace_scene: 'In einer Szene geübt',
  event_default: 'In der Übung getroffen',
  event_seen_context: 'Im Kontext gesehen',
  event_recognized: 'Erkannt',
  event_produced_correct: 'Richtig verwendet',
  event_produced_incorrect: 'Verwendet, dann korrigiert',
  event_missed_target: 'Verpasst',
  conv_prefix: 'Im Gespräch: {bits}',
  conv_targeted: 'geübt',
  conv_used: 'verwendet',
  conv_suggested: 'vorgeschlagen',
  conv_planned: 'geplant',
  conv_passage: 'Gesprächsausschnitt',
  action_biography: 'Die Geschichte des Worts',
  action_letter: 'In einem Brief verwenden',
  action_feuilleton: 'Im Feuilleton lesen',
  composing: 'Wird geschrieben…',
  ratings_note: 'Dreh die Karte um, bevor du sie bewertest.',
  word_open_failed: 'Dieses Wort konnte nicht geöffnet werden.',
  biography_failed: 'Die Geschichte dieses Worts konnte nicht geöffnet werden.',
  letter_failed: 'Der Brief konnte nicht geschrieben werden.',
  episode_failed: 'Die Folge konnte nicht geschrieben werden.',
  review_head_title: 'Lexique · Wiederholung · L’Atelier',
  review_aria: 'Lexique — Wiederholung',
  close_review: 'Wiederholung verlassen',
  progress_aria: 'Fortschritt der Wiederholung',
  opening_deck: 'Stapel wird geöffnet…',
  cached_notice: 'Frühere Ausgabe · wird aktualisiert…',
  deck_error_title: 'Stapel nicht verfügbar',
  deck_unavailable: 'Die Wiederholung ist nicht verfügbar.',
  audio_failed: 'Die Wiedergabe ist fehlgeschlagen.',
  due_on: 'Fällig am {date}',
  rating_fallback: 'Gespeichert',
  anchored_with: 'Aus deiner Geschichte mit {name}',
  composition: 'Davon {list}.',
  and_word: 'und',
  word_of_day: 'Wort des Tages',
  cards_one: '{n} Karte',
  cards_many: '{n} Karten',
  about_minutes: 'etwa {n} Min.',
  filed_one: '{n} Karte gespeichert',
  filed_many: '{n} Karten gespeichert',
  nothing_due: 'Heute nichts zu wiederholen',
  listen_prompt: 'Hör dir das französische Wort an',
  listen: 'Anhören',
  playing: 'Spielt…',
  listen_hint: 'Anhören · antworten',
  cue_aria: 'Bildhinweis: {label}',
  input_placeholder: 'Schreib das französische Wort',
  input_placeholder_audio: 'Schreib, was du gehört hast',
  input_aria: 'Französische Antwort schreiben',
  open_story: 'Geschichte von {word} öffnen',
  story_title: 'Die Geschichte des Worts',
  verdict_exact: 'Genau richtig',
  verdict_yours: 'Du hast geschrieben: {answer}',
  reveal_first: 'Antwort zeigen',
  reveal_before: 'Erst die Antwort zeigen, dann bewerten',
  done_aria: 'Ende der Wiederholung',
  done_label: 'Verteilte Wiederholung',
  done_title: 'Stapel geschafft',
  returning: 'Zurück…',
  refresh: 'Aktualisieren',
  conj_head_title: 'Cahier · Konjugation · L’Atelier',
  conj_title: 'Unregelmäßige Formen',
  conj_close: 'Zurück zur Wortliste',
  conj_progress: '{n} % der Runde',
  conj_loading: 'Die Übung wird vorbereitet.',
  conj_error: 'Die Konjugationsübung antwortet gerade nicht.',
  conj_empty: 'Keine unregelmäßigen Formen offen.',
  conj_done_one: '{n} Form in dieser Runde geübt.',
  conj_done_many: '{n} Formen in dieser Runde geübt.',
  conj_to_words: 'Vokabeln wiederholen',
  conj_field: 'Die konjugierte Form',
  conj_placeholder: 'Schreib die Form',
  conj_input_aria: 'Schreib die konjugierte Form',
  conj_reveal: 'Tabelle zeigen',
  conj_right: 'Richtig',
  conj_rate_group: 'Diese Form bewerten',
  mdj_aria: 'Lexique — Wörter des Tages',
  mdj_label: 'Lexique · Wörter des Tages',
  mdj_tripled: 'Alle drei Stempel',
  mdj_open: 'Lexique-Wiederholung öffnen',
  stamp_lu: 'Gelesen',
  stamp_retrouve: 'Erinnert',
  stamp_place: 'Verwendet',
  stamp_triple: 'Dreifach',
  stamps_count: '{n} von 3',
};

const FR: LexiqueCopy = {
  locale: 'fr-FR',
  retry: 'Réessayer',
  next_on: 'Reprise le {date}',
  filed: 'Reprise classée',
  review_failed: 'La reprise n’a pas pu être classée.',
  flip_front: 'Touche pour retourner',
  flip_back: 'Sens · touche pour revenir',
  rank: 'rang {n}',
  day_one: '{n} jour',
  day_many: '{n} jours',
  grade_again: 'À revoir',
  grade_again_hint: 'Très bientôt',
  grade_hard: 'Difficile',
  grade_hard_hint: 'Garder près',
  grade_good: 'Correct',
  grade_good_hint: 'Rythme normal',
  grade_easy: 'Facile',
  grade_easy_hint: 'Espacer',
  ratings_group: 'Classer la carte',
  rate_as: 'Noter : {label}',
  deck_again: 'Encore',
  deck_hard: 'Dur',
  deck_good: 'Bien',
  deck_easy: 'Facile',
  deck_know: 'Je sais',
  pos_noun: 'nom',
  pos_verb: 'verbe',
  pos_adjective: 'adjectif',
  pos_adverb: 'adverbe',
  pos_pronoun: 'pronom',
  pos_preposition: 'préposition',
  pos_determiner: 'déterminant',
  pos_conjunction: 'conjonction',
  pos_interjection: 'interjection',
  pos_number: 'numéral',
  state_new: 'Nouveau',
  state_due: 'À revoir',
  state_fragile: 'Fragile',
  state_building: 'En cours',
  state_solid: 'Solide',
  state_mastered: 'Acquis',
  bucket_linked: 'Mot voisin',
  bucket_topic: 'Du thème',
  bucket_new_deck: 'La pioche du jour',
  count_fragile_one: '{n} fragile',
  count_fragile_many: '{n} fragiles',
  count_new_one: '{n} nouveau',
  count_new_many: '{n} nouveaux',
  count_due: '{n} à revoir',
  head_title: 'Le Cahier · Lexique · L’Atelier',
  search_label: 'Chercher un mot',
  search_placeholder: 'Chercher un mot…',
  search_clear: 'Effacer la recherche',
  count_loading: 'Ouverture du registre…',
  cta_review_one: 'Réviser · {n} mot',
  cta_review_many: 'Réviser · {n} mots',
  cta_open_review: 'Ouvrir la révision',
  filter_group: 'Filtrer le registre',
  chip_all: 'Tous',
  chip_due: 'À revoir',
  chip_fragile: 'Fragiles',
  chip_new: 'Nouveaux',
  chip_mastered: 'Acquis',
  map_building: 'En cours',
  map_solid: 'Solides',
  filter_clear: 'Effacer',
  shown_one: '{n} mot affiché',
  shown_many: '{n} mots affichés',
  searching: 'Recherche…',
  queue_title: 'File du jour',
  queue_error_title: 'Le registre des mots n’a pas pu être ouvert.',
  queue_error_body: 'La grammaire reste consultable.',
  queue_empty_title: 'Aucune carte en file',
  queue_empty_filtered: 'Aucun mot ne correspond à ce filtre.',
  queue_empty_body: 'Le registre vous attend plus bas.',
  queue_clear_filters: 'Effacer les filtres',
  registre_title: 'Registre des mots — Français 5000',
  registre_error_title: 'Le registre des mots ne répond pas.',
  registre_error_body: 'Réessayez dans un instant.',
  registre_empty_title: 'Aucun mot au registre',
  registre_empty_body: 'Essayez un autre terme de recherche.',
  atlas_title: 'Atlas des acquis',
  atlas_meta: '{nailed} mots tenus sur {total}',
  atlas_open: 'Déplier',
  atlas_close: 'Replier',
  cefr_title: 'Couverture CECR',
  cefr_note: 'mots tenus par niveau',
  topics_title: 'Pistes par domaine',
  topics_note: '{n} en cours',
  verbs_title: 'Verbes et structures',
  verbs_note: 'conjugaison',
  verbs_track: 'Verbes',
  verbs_cta: 'Reprendre les formes irrégulières',
  map_title: 'Carte de maîtrise — Français 5000',
  map_cell: '1 case = 1 mot',
  map_aria: 'Carte de maîtrise',
  map_note: 'Les {n} premiers mots par fréquence.',
  dossier_label: 'Dossier de la semaine',
  dossier_fallback: 'Le registre s’épaissit.',
  dossier_repairs: 'Réparations',
  dossier_reviews: 'Révisions',
  dossier_seen: 'Vus',
  dossier_used: 'Employés',
  details_label: 'Détails du mot',
  tile_rank: 'Rang de fréquence',
  tile_nature: 'Nature',
  tile_level: 'Difficulté',
  tile_source: 'Provenance',
  source_registre: 'registre',
  anchor_label: 'Phrase d’ancrage',
  examples_title: 'Exemples par source',
  loading_note: 'en cours',
  example_one: '{n} relevé',
  example_many: '{n} relevés',
  examples_empty: 'Aucun exemple au dossier pour l’instant.',
  ex_example: 'Exemple',
  ex_definition: 'Définition',
  ex_usage: 'Notes d’usage',
  ex_letter_fallback: 'Consigne de la lettre',
  ex_scene_fallback: 'Scène du feuilleton',
  ex_your_turn: 'Votre tour',
  ex_reply: 'La réponse',
  conversation: 'Conversation',
  tracking_title: 'Le suivi',
  tracking_current: 'à jour',
  tracking_never: 'jamais revu',
  srs_state: 'État',
  srs_next: 'Prochaine reprise',
  srs_next_none: 'Non programmée',
  srs_last: 'Dernière reprise',
  srs_last_none: 'Jamais revu',
  srs_interval: 'Intervalle',
  srs_interval_none: 'Carte neuve',
  srs_reviews: 'Reprises',
  srs_lapses: 'Oublis',
  srs_learning: 'En apprentissage',
  srs_review: 'En révision',
  srs_relearning: 'À reprendre',
  traces_title: 'Traces récentes',
  trace_one: '{n} trace',
  trace_many: '{n} traces',
  traces_empty: 'Ce mot n’a pas encore laissé de trace.',
  trace_letter: 'Visé dans une lettre',
  trace_scene: 'Visé dans une scène',
  event_default: 'Rencontré en pratique',
  event_seen_context: 'Vu en contexte',
  event_recognized: 'Reconnu',
  event_produced_correct: 'Produit juste',
  event_produced_incorrect: 'Produit puis réparé',
  event_missed_target: 'Cible manquée',
  conv_prefix: 'En conversation : {bits}',
  conv_targeted: 'visé',
  conv_used: 'employé',
  conv_suggested: 'suggéré',
  conv_planned: 'prévu',
  conv_passage: 'Passage de conversation',
  action_biography: 'La biographie du mot',
  action_letter: 'Le mettre dans une lettre',
  action_feuilleton: 'Le lire au Feuilleton',
  composing: 'Composition…',
  ratings_note: 'Retournez la carte avant de la classer.',
  word_open_failed: 'Ce mot n’a pas pu être ouvert.',
  biography_failed: 'La biographie de ce mot n’a pas pu être ouverte.',
  letter_failed: 'La lettre n’a pas pu être composée.',
  episode_failed: 'L’épisode n’a pas pu être composé.',
  review_head_title: 'Le Lexique · Révision · L’Atelier',
  review_aria: 'Le Lexique — révision',
  close_review: 'Quitter la révision',
  progress_aria: 'Progression de la révision',
  opening_deck: 'Ouverture du paquet…',
  cached_notice: 'Édition précédente · mise à jour en cours…',
  deck_error_title: 'Paquet indisponible',
  deck_unavailable: 'La révision est indisponible.',
  audio_failed: 'La lecture audio a échoué.',
  due_on: 'Échéance {date}',
  rating_fallback: 'Classée',
  anchored_with: 'Ancré dans votre histoire avec {name}',
  composition: 'Dont {list}.',
  and_word: 'et',
  word_of_day: 'Mot du jour',
  cards_one: '{n} carte',
  cards_many: '{n} cartes',
  about_minutes: 'environ {n} min',
  filed_one: '{n} carte classée',
  filed_many: '{n} cartes classées',
  nothing_due: 'Rien à revoir aujourd’hui',
  listen_prompt: 'Écoutez le mot français',
  listen: 'Écouter',
  playing: 'Lecture…',
  listen_hint: 'Écouter · répondre',
  cue_aria: 'Indice visuel : {label}',
  input_placeholder: 'Écrivez la réponse française',
  input_placeholder_audio: 'Écrivez ce que vous avez entendu',
  input_aria: 'Écrire la réponse française',
  open_story: 'Ouvrir l’histoire du mot {word}',
  story_title: 'L’histoire du mot',
  verdict_exact: 'Réponse exacte',
  verdict_yours: 'Votre réponse : {answer}',
  reveal_first: 'Révéler la réponse',
  reveal_before: 'Révéler la réponse avant de noter',
  done_aria: 'Fin de la révision',
  done_label: 'Révision espacée',
  done_title: 'Paquet vidé',
  returning: 'Retour…',
  refresh: 'Actualiser',
  conj_head_title: 'Le Cahier · Conjugaison · L’Atelier',
  conj_title: 'Les formes irrégulières',
  conj_close: 'Revenir au registre',
  conj_progress: '{n}% du tour',
  conj_loading: 'L’exercice se prépare.',
  conj_error: 'L’exercice de conjugaison ne répond pas pour l’instant.',
  conj_empty: 'Aucune forme irrégulière en attente.',
  conj_done_one: '{n} forme reprise ce tour.',
  conj_done_many: '{n} formes reprises ce tour.',
  conj_to_words: 'Reprendre le vocabulaire',
  conj_field: 'La forme conjuguée',
  conj_placeholder: 'Écrivez la forme',
  conj_input_aria: 'Écrivez la forme conjuguée',
  conj_reveal: 'Voir le tableau',
  conj_right: 'Juste',
  conj_rate_group: 'Classement de la forme',
  mdj_aria: 'Le Lexique — les mots du jour',
  mdj_label: 'Le Lexique · les mots du jour',
  mdj_tripled: 'Édition triplée',
  mdj_open: 'Ouvrir la révision du lexique',
  stamp_lu: 'Lu',
  stamp_retrouve: 'Retrouvé',
  stamp_place: 'Placé',
  stamp_triple: 'Triplé',
  stamps_count: '{n} sur 3',
};

const TABLES: Record<ControlLanguage, LexiqueCopy> = { en: EN, de: DE, fr: FR };

/** The Lexique copy table for a chrome language (regional tags and nulls normalised). */
export function lexiqueCopy(language: unknown): LexiqueCopy {
  return TABLES[normalizeControlLanguage(language)];
}

/** The copy table of the surrounding `AtelierV2Root` (its `language` prop). */
export function useLexCopy(): LexiqueCopy {
  return lexiqueCopy(useControlLanguage());
}

/** `{n}`-style placeholders filled in. */
export function fill(template: string, values: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (match, key: string) => (key in values ? String(values[key]) : match));
}

type PluralKey = {
  [K in keyof LexiqueCopy]: K extends `${infer Stem}_one` ? Stem : never;
}[keyof LexiqueCopy];

/** «3 words», «1 Wort»: the `_one` / `_many` pair of a key, with `{n}` filled. */
export function plural(copy: LexiqueCopy, stem: PluralKey, n: number): string {
  const key = `${stem}_${n === 1 ? 'one' : 'many'}` as keyof LexiqueCopy;
  return fill(copy[key], { n: formatNumber(copy, n) });
}

/** A count in the chrome language's digits («2 140», «2,140», «2.140»). */
export function formatNumber(copy: LexiqueCopy, n: number): string {
  return new Intl.NumberFormat(copy.locale).format(n);
}

/** A date in the chrome language, or '' for a missing/invalid one. */
export function formatDate(
  copy: LexiqueCopy,
  value: string | null | undefined,
  options: Intl.DateTimeFormatOptions = { day: 'numeric', month: 'long' },
): string {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleDateString(copy.locale, options);
}

/** «Reprise le 3 octobre» / «Next review 3 October» after a card is filed. */
export function nextReviewText(copy: LexiqueCopy, value: string | null | undefined): string {
  const label = formatDate(copy, value);
  return label ? fill(copy.next_on, { date: label }) : copy.filed;
}

type DueSummary = { due?: number | null; due_total?: number | null; fragile?: number | null; new?: number | null };

/**
 * Appendix A «Mots»: the Lexique landing used to print the due count five
 * times. It is said once now, on the one primary («Review · 7 words»); the
 * masthead's count line names only the other piles.
 */
export function landingCounts(
  copy: LexiqueCopy,
  summary: DueSummary | null | undefined,
  loading = false,
): { due: number; countLine: string; cta: string } {
  const due = Math.max(0, Number(summary?.due_total ?? summary?.due ?? 0) || 0);
  const fragile = Math.max(0, Number(summary?.fragile ?? 0) || 0);
  const fresh = Math.max(0, Number(summary?.new ?? 0) || 0);
  const countLine = loading
    ? copy.count_loading
    : [
        fragile ? plural(copy, 'count_fragile', fragile) : '',
        fresh ? plural(copy, 'count_new', fresh) : '',
      ].filter(Boolean).join(' · ');
  return { due, countLine, cta: due > 0 ? plural(copy, 'cta_review', due) : copy.cta_open_review };
}

/* The part-of-speech column on the imported deck is a heuristic guess stored
 * as an English machine key (sometimes "x" or nothing). Only a key on this
 * whitelist prints, as a label in the chrome language; anything else prints
 * nothing rather than stamping a guess onto the page as a fact. */
export const PART_OF_SPEECH_LABELS: Record<string, keyof LexiqueCopy> = {
  noun: 'pos_noun',
  verb: 'pos_verb',
  adjective: 'pos_adjective',
  adverb: 'pos_adverb',
  pronoun: 'pos_pronoun',
  preposition: 'pos_preposition',
  determiner: 'pos_determiner',
  conjunction: 'pos_conjunction',
  interjection: 'pos_interjection',
  number: 'pos_number',
};

export function partOfSpeechLabel(copy: LexiqueCopy, value?: string | null): string {
  const key = PART_OF_SPEECH_LABELS[String(value || '').trim().toLowerCase()];
  return key ? copy[key] : '';
}
