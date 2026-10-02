/**
 * WP-119 · Le Papier de Romy — the chrome, in the learner's control language
 * (WP-82 one-language rule). Romy's French comes from the server; these are the
 * labels, buttons and notices around it. The publication words stay French in
 * every table (design §5): «Le Papier», «Semaine 40», «Fait», «Interprétation»,
 * «Prévision», «Bouclage», «Bouclé», «La suite la semaine prochaine.».
 *
 * Sentence case, no exclamation marks, no personality: Romy has the voice.
 */

import type { RvLanguage, RvMakeKind, RvTopic } from '@/lib/revue-types';

export type RevueCopy = {
  revue: string;
  revue_full: string;
  week_short: string;
  topic: Record<RvTopic, string>;
  evergreen_kicker: string;
  evergreen_topic: string;
  evergreen_label: string;
  other_subject: string;
  other_subject_title: string;
  sheet_lead: string;
  ask_placeholder: string;
  ask_send: string;
  join: string;
  resume: string;
  resume_line: string;
  resume_line_question: string;
  started_today: string;
  started_yesterday: string;
  started_on: string;
  filed_kicker: string;
  filed_kicker_short: string;
  romy_proposes: string;
  or_else: string;
  chip_label: string;
  chip_aria: string;
  exit_label: string;
  back_label: string;
  beats_label: string;
  beat_names: Record<'arrive' | 'facts' | 'pursue' | 'make' | 'close', string>;
  column_label: string;
  column_room: string;
  column_full: string;
  column_bouclage: string;
  column_boucle: string;
  numbers: string[];
  translate: string;
  translation_hide: string;
  listen_summary: string;
  listen_meta: string;
  listen_stop: string;
  romy: string;
  you: string;
  fact: string;
  interpretation: string;
  forecast: string;
  according_to: string;
  per: string;
  the_quote: string;
  opens_new_tab: string;
  uncertain: string;
  facts_on_table: string;
  facts_on_table_one: string;
  shift_simplify: string;
  shift_angle: string;
  shift_bouclage: string;
  shift_boucle: string;
  shift_resume: string;
  day_yesterday: string;
  day_earlier: string;
  glosses_off: string;
  agree_other: string;
  composer_placeholder: string;
  composer_label: string;
  send: string;
  speak: string;
  stop: string;
  transcribing: string;
  typing: string;
  make_label: string;
  make_go: string;
  /** `{n}` in a detail is filled with the option's own number (max words, seconds). */
  make_options: Record<RvMakeKind, { title: string; detail: string }>;
  /** Phase 2 · the guest (WIRE §6.2, design §3.4 #guest). `{name}` is the guest's name. */
  guest_arrives: string;
  guest_testimony: string;
  guest_disagrees: string;
  guest_asks: string;
  guest_moved: string;
  /** Phase 2 · the register note (WIRE §6.3): a French line and why, in the learner's language. */
  register_label: string;
  register_reason: Record<'vous_to_tu' | 'tu_to_vous', string>;
  /** Phase 2 · headline_write. */
  write_label: string;
  write_placeholder: string;
  write_send: string;
  write_words: string;
  write_too_long: string;
  write_supported: string;
  write_unsupported: string;
  write_contradicted: string;
  write_words_right: string;
  /** Phase 2 · short_report. */
  report_record: string;
  report_recording: string;
  report_stop: string;
  report_label: string;
  report_text_label: string;
  report_placeholder: string;
  report_send: string;
  report_again: string;
  report_no_mic: string;
  made_report: string;
  kept_word_right: string;
  /** WP-120 · the vignette. */
  vignette_label: string;
  vignettes_title: string;
  one_more_question: string;
  headline_label: string;
  headline_right: string;
  headline_wrong: string;
  status_selected: string;
  status_correct: string;
  status_wrong: string;
  continue: string;
  see_paper: string;
  question_write_label: string;
  question_write_placeholder: string;
  question_propose: string;
  your_version: string;
  reader_question: string;
  send_desk: string;
  change_word: string;
  send_edited: string;
  made_headline: string;
  made_question: string;
  contribution: string;
  for_releve: string;
  kept_count: string;
  file_revue: string;
  see_releve: string;
  filed_on: string;
  reread: string;
  hide_thread: string;
  loading: string;
  loading_line: string;
  model_down: string;
  error_title: string;
  error_body: string;
  retry: string;
  disabled_title: string;
  disabled_body: string;
  closed_notice: string;
  back_home: string;
  sous_presse: string;
  mock_badge: string;
};

const FR: RevueCopy = {
  revue: 'Le Papier',
  revue_full: 'Le Papier de Romy',
  week_short: 'sem. {n}',
  topic: { food: 'cuisine', culture: 'culture', city: 'ville', sport: 'sport', nature: 'nature', work: 'travail', politics: 'politique' },
  evergreen_kicker: 'Le Papier · hors actualité',
  evergreen_topic: 'un classique de saison',
  evergreen_label: 'Hors actualité · un classique de saison',
  other_subject: 'Autre sujet ?',
  other_subject_title: 'Autre sujet ?',
  sheet_lead: 'Romy a préparé {n} sujets cette semaine.',
  ask_placeholder: 'Autre chose ? Un sujet, un mot…',
  ask_send: 'Demander à Romy',
  join: 'Rejoindre Romy',
  resume: 'Reprendre avec Romy',
  resume_line: '{when} · tu en étais à « {what} ».',
  resume_line_question: '{when} · ta question attend.',
  started_today: "Commencée aujourd'hui",
  started_yesterday: 'Commencée hier',
  started_on: 'Commencée le {date}',
  filed_kicker: 'Revue bouclée · {week}',
  filed_kicker_short: 'Revue bouclée',
  romy_proposes: 'Ce que Romy te propose',
  or_else: 'Ou bien',
  chip_label: 'Le Papier',
  chip_aria: 'Le Papier de Romy, semaine {n}',
  exit_label: 'Quitter la Revue — Romy garde tes notes',
  back_label: 'Retour à La Une',
  beats_label: 'Le Papier',
  beat_names: { arrive: 'Arrivée', facts: 'Les faits', pursue: 'La suite', make: 'Le papier', close: 'Bouclé' },
  column_label: 'La colonne',
  column_room: 'De la place pour environ {n} échanges.',
  column_full: 'La colonne est pleine.',
  column_bouclage: 'Bouclage',
  column_boucle: 'Bouclé',
  numbers: ['zéro', 'un', 'deux', 'trois', 'quatre', 'cinq', 'six', 'sept', 'huit', 'neuf', 'dix', 'onze', 'douze'],
  translate: 'Traduire',
  translation_hide: 'Masquer',
  listen_summary: 'Écouter le résumé',
  listen_meta: 'Romy · {s} s',
  listen_stop: 'Arrêter',
  romy: 'Romy',
  you: 'Toi',
  fact: 'Fait',
  interpretation: 'Interprétation',
  forecast: 'Prévision',
  according_to: "D'après {source}, {date}",
  per: 'selon {who}',
  the_quote: 'La citation',
  opens_new_tab: "D'après {source}, {date}, s'ouvre dans un nouvel onglet",
  uncertain: 'Les sources ne le disent pas',
  facts_on_table: '{n} faits sur la table · d’après {sources}',
  facts_on_table_one: '1 fait sur la table · d’après {sources}',
  shift_simplify: 'Plus simple · gloses affichées',
  shift_angle: 'Autre angle · {angle}',
  shift_bouclage: 'Bouclage',
  shift_boucle: 'Bouclé',
  shift_resume: '{when} · tu reprends ici',
  day_yesterday: 'Hier',
  day_earlier: 'Plus tôt',
  glosses_off: 'Gloses',
  agree_other: 'Répondre autrement',
  composer_placeholder: 'Ta question à Romy…',
  composer_label: 'Ta réponse à Romy',
  send: 'Envoyer',
  speak: 'Parler',
  stop: 'Arrêter',
  transcribing: 'Transcription…',
  typing: 'Romy cherche dans ses notes',
  make_label: 'Ce qu’on fait de tout ça',
  make_go: "C'est parti",
  make_options: {
    reader_question: { title: 'Écrire la question des lecteurs', detail: 'Ta question, en bon français.' },
    headline_choice: { title: 'Choisir le titre', detail: 'Trois titres, un seul dit vrai.' },
    headline_write: { title: 'Écrire le titre', detail: '{n} mots au plus, et vrai.' },
    short_report: { title: 'Raconter en {n} secondes', detail: 'À voix haute, comme à la radio.' },
  },
  guest_arrives: '{name} arrive.',
  guest_testimony: 'témoignage',
  guest_disagrees: 'pas d’accord',
  guest_asks: 'une question',
  guest_moved: '{name} a changé d’avis',
  register_label: 'Le registre',
  register_reason: {
    vous_to_tu: 'Romy te tutoie : tu peux la tutoyer aussi.',
    tu_to_vous: 'Ici, on se vouvoie : dis « vous ».',
  },
  write_label: 'Ton titre',
  write_placeholder: 'Court, et vrai…',
  write_send: 'Proposer le titre',
  write_words: '{n} mots sur {max} au plus',
  write_too_long: 'Trop long : {max} mots au plus.',
  write_supported: 'Les sources le disent.',
  write_unsupported: 'Les sources ne le disent pas tout à fait, mais Romy le garde.',
  write_contradicted: 'Les sources disent autre chose. Réécris-le.',
  write_words_right: 'Bien employé : {words}',
  report_record: 'Enregistrer · {n} s',
  report_recording: 'Romy t’écoute',
  report_stop: 'Arrêter',
  report_label: 'Ton reportage',
  report_text_label: 'Ton reportage, par écrit',
  report_placeholder: 'Ce que tu vois, ce que tu entends…',
  report_send: 'Envoyer à Romy',
  report_again: 'Recommencer',
  report_no_mic: 'Pas de micro ici : écris ton reportage.',
  made_report: 'Ton reportage',
  kept_word_right: 'bien employé',
  vignette_label: 'Ta vignette · {week}',
  vignettes_title: 'Tes vignettes',
  one_more_question: 'Encore une question',
  headline_label: 'Le titre',
  headline_right: "C'est notre titre.",
  headline_wrong: 'Pas celui-là : les sources disent autre chose.',
  status_selected: 'choisi',
  status_correct: 'juste',
  status_wrong: 'à revoir',
  continue: 'Continuer',
  see_paper: 'Voir le papier',
  question_write_label: 'Ta question pour les lecteurs',
  question_write_placeholder: 'Écris-la comme elle te vient…',
  question_propose: 'Demander à Romy',
  your_version: 'Ta version',
  reader_question: 'La question pour les lecteurs',
  send_desk: "On l'envoie à la rédaction",
  change_word: 'Je change un mot',
  send_edited: "On l'envoie à la rédaction",
  made_headline: 'Ton titre',
  made_question: 'Ta question pour les lecteurs',
  contribution: 'toi',
  for_releve: 'Pour ton Relevé',
  kept_count: '{w} mots · {c} faits',
  file_revue: 'Classer la Revue',
  see_releve: 'Voir dans le Relevé',
  filed_on: 'Revue bouclée le {date}',
  reread: 'Relire la conversation',
  hide_thread: 'Masquer la conversation',
  loading: 'Chargement de la Revue',
  loading_line: 'Romy rassemble ses notes',
  model_down: 'La conversation ne répond pas pour le moment. Les faits et le titre restent là ; tes notes sont gardées.',
  error_title: 'Le Papier ne répond pas',
  error_body: 'Rien n’est perdu : réessaie dans un instant.',
  retry: 'Réessayer',
  disabled_title: 'Pas de Revue pour le moment',
  disabled_body: 'Romy revient avec un sujet bientôt.',
  closed_notice: 'Cette Revue est bouclée.',
  back_home: 'Retour à La Une',
  sous_presse: 'sous presse',
  mock_badge: 'Maquette (dev)',
};

const EN: RevueCopy = {
  ...FR,
  week_short: 'wk {n}',
  topic: { food: 'food', culture: 'culture', city: 'city', sport: 'sport', nature: 'nature', work: 'work', politics: 'politics' },
  evergreen_kicker: 'Le Papier · not news',
  evergreen_topic: 'a seasonal classic',
  evergreen_label: 'Not news · a seasonal classic',
  other_subject: 'Another story?',
  other_subject_title: 'Another story?',
  sheet_lead: 'Romy has {n} stories this week.',
  ask_placeholder: 'Something else? A topic, a word…',
  ask_send: 'Ask Romy',
  join: 'Join Romy',
  resume: 'Pick up with Romy',
  resume_line: '{when} · you were on «{what}».',
  resume_line_question: '{when} · your question is waiting.',
  started_today: 'Started today',
  started_yesterday: 'Started yesterday',
  started_on: 'Started {date}',
  filed_kicker: 'Revue filed · {week}',
  filed_kicker_short: 'Revue filed',
  romy_proposes: 'Romy suggests',
  or_else: 'Or',
  chip_label: 'Le Papier',
  chip_aria: "Romy's Revue, week {n}",
  exit_label: 'Leave the Revue — Romy keeps your notes',
  back_label: 'Back to La Une',
  beat_names: { arrive: 'Arrive', facts: 'Facts', pursue: 'Follow up', make: 'Make', close: 'Filed' },
  column_label: 'The column',
  column_room: 'Room for about {n} exchanges.',
  column_full: 'The column is full.',
  numbers: ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve'],
  translate: 'Translate',
  translation_hide: 'Hide',
  listen_summary: 'Hear the summary',
  listen_stop: 'Stop',
  you: 'You',
  according_to: 'From {source}, {date}',
  per: 'according to {who}',
  the_quote: 'The quote',
  opens_new_tab: 'From {source}, {date}, opens in a new tab',
  uncertain: "The sources don't say",
  facts_on_table: '{n} facts on the table · from {sources}',
  facts_on_table_one: '1 fact on the table · from {sources}',
  shift_simplify: 'Simpler · glosses shown',
  shift_angle: 'New angle · {angle}',
  shift_resume: '{when} · you pick up here',
  day_yesterday: 'Yesterday',
  day_earlier: 'Earlier',
  glosses_off: 'Glosses',
  agree_other: 'Answer another way',
  composer_placeholder: 'Your question for Romy…',
  composer_label: 'Your reply to Romy',
  send: 'Send',
  speak: 'Speak',
  stop: 'Stop',
  transcribing: 'Transcribing…',
  typing: 'Romy is checking her notes',
  make_label: 'What we make of it',
  make_go: "Let's go",
  make_options: {
    reader_question: { title: 'Write the readers’ question', detail: 'Your question, in good French.' },
    headline_choice: { title: 'Pick the headline', detail: 'Three headlines, only one is true.' },
    headline_write: { title: 'Write the headline', detail: '{n} words at most, and true.' },
    short_report: { title: 'Tell it in {n} seconds', detail: 'Out loud, like on the radio.' },
  },
  guest_arrives: '{name} joins.',
  guest_testimony: 'testimony',
  guest_disagrees: 'disagrees',
  guest_asks: 'a question',
  guest_moved: '{name} changed their mind',
  register_label: 'Register',
  register_reason: {
    vous_to_tu: 'Romy says «tu» to you: you can say «tu» to her too.',
    tu_to_vous: 'Here you say «vous»: you are not on first-name terms.',
  },
  write_label: 'Your headline',
  write_placeholder: 'Short, and true…',
  write_send: 'Suggest the headline',
  write_words: '{n} of {max} words at most',
  write_too_long: 'Too long: {max} words at most.',
  write_supported: 'The sources say so.',
  write_unsupported: "The sources don't quite say so, but Romy keeps it.",
  write_contradicted: 'The sources say otherwise. Write it again.',
  write_words_right: 'Used well: {words}',
  report_record: 'Record · {n} s',
  report_recording: 'Romy is listening',
  report_stop: 'Stop',
  report_label: 'Your report',
  report_text_label: 'Your report, in writing',
  report_placeholder: 'What you see, what you hear…',
  report_send: 'Send to Romy',
  report_again: 'Start again',
  report_no_mic: 'No microphone here: write your report.',
  made_report: 'Your report',
  kept_word_right: 'used well',
  vignette_label: 'Your vignette · {week}',
  vignettes_title: 'Your vignettes',
  one_more_question: 'One more question',
  headline_label: 'The headline',
  headline_right: 'That is our headline.',
  headline_wrong: 'Not that one: the sources say otherwise.',
  status_selected: 'selected',
  status_correct: 'right',
  status_wrong: 'to review',
  continue: 'Continue',
  see_paper: 'See the piece',
  question_write_label: 'Your question for the readers',
  question_write_placeholder: 'Write it the way it comes, any language…',
  question_propose: 'Ask Romy',
  your_version: 'Your version',
  reader_question: 'The question for the readers',
  send_desk: 'Send it to the desk',
  change_word: 'Change a word',
  send_edited: 'Send it to the desk',
  made_headline: 'Your headline',
  made_question: 'Your question for the readers',
  contribution: 'you',
  for_releve: 'For your Relevé',
  kept_count: '{w} words · {c} facts',
  file_revue: 'File the Revue',
  see_releve: 'See it in the Relevé',
  filed_on: 'Revue filed on {date}',
  reread: 'Reread the conversation',
  hide_thread: 'Hide the conversation',
  loading: 'Loading the Revue',
  loading_line: 'Romy is gathering her notes',
  model_down: "The conversation isn't answering right now. The facts and the headline stay; your notes are kept.",
  error_title: 'The Revue is not answering',
  error_body: 'Nothing is lost: try again in a moment.',
  retry: 'Try again',
  disabled_title: 'No Revue right now',
  disabled_body: 'Romy will be back with a story soon.',
  closed_notice: 'This Revue is filed.',
  back_home: 'Back to La Une',
  sous_presse: 'sous presse',
  mock_badge: 'Mock (dev)',
};

const DE: RevueCopy = {
  ...FR,
  week_short: 'KW {n}',
  topic: { food: 'Essen', culture: 'Kultur', city: 'Stadt', sport: 'Sport', nature: 'Natur', work: 'Arbeit', politics: 'Politik' },
  evergreen_kicker: 'Le Papier · zeitlos',
  evergreen_topic: 'ein Klassiker der Saison',
  evergreen_label: 'Keine Nachricht · ein Klassiker der Saison',
  other_subject: 'Anderes Thema?',
  other_subject_title: 'Anderes Thema?',
  sheet_lead: 'Romy hat diese Woche {n} Themen.',
  ask_placeholder: 'Etwas anderes? Ein Thema, ein Wort…',
  ask_send: 'Romy fragen',
  join: 'Zu Romy',
  resume: 'Mit Romy weitermachen',
  resume_line: '{when} · du warst bei „{what}“.',
  resume_line_question: '{when} · deine Frage wartet.',
  started_today: 'Heute begonnen',
  started_yesterday: 'Gestern begonnen',
  started_on: 'Begonnen am {date}',
  filed_kicker: 'Revue abgelegt · {week}',
  filed_kicker_short: 'Revue abgelegt',
  romy_proposes: 'Romys Vorschlag',
  or_else: 'Oder',
  chip_label: 'Le Papier',
  chip_aria: 'Romys Revue, Woche {n}',
  exit_label: 'Revue verlassen — Romy behält deine Notizen',
  back_label: 'Zurück zu La Une',
  beat_names: { arrive: 'Ankommen', facts: 'Fakten', pursue: 'Nachfragen', make: 'Machen', close: 'Fertig' },
  column_label: 'Die Spalte',
  column_room: 'Platz für etwa {n} Wechsel.',
  column_full: 'Die Spalte ist voll.',
  numbers: ['null', 'einen', 'zwei', 'drei', 'vier', 'fünf', 'sechs', 'sieben', 'acht', 'neun', 'zehn', 'elf', 'zwölf'],
  translate: 'Übersetzen',
  translation_hide: 'Ausblenden',
  listen_summary: 'Zusammenfassung hören',
  listen_stop: 'Stopp',
  you: 'Du',
  according_to: 'Laut {source}, {date}',
  per: 'laut {who}',
  the_quote: 'Das Zitat',
  opens_new_tab: 'Laut {source}, {date}, öffnet in neuem Tab',
  uncertain: 'Die Quellen sagen es nicht',
  facts_on_table: '{n} Fakten auf dem Tisch · laut {sources}',
  facts_on_table_one: '1 Fakt auf dem Tisch · laut {sources}',
  shift_simplify: 'Einfacher · Glossen an',
  shift_angle: 'Neuer Blickwinkel · {angle}',
  shift_resume: '{when} · hier geht es weiter',
  day_yesterday: 'Gestern',
  day_earlier: 'Früher',
  glosses_off: 'Glossen',
  agree_other: 'Anders antworten',
  composer_placeholder: 'Deine Frage an Romy…',
  composer_label: 'Deine Antwort an Romy',
  send: 'Senden',
  speak: 'Sprechen',
  stop: 'Stopp',
  transcribing: 'Wird transkribiert…',
  typing: 'Romy sieht in ihren Notizen nach',
  make_label: 'Was wir daraus machen',
  make_go: 'Los geht’s',
  make_options: {
    reader_question: { title: 'Die Leserfrage schreiben', detail: 'Deine Frage, in gutem Französisch.' },
    headline_choice: { title: 'Die Schlagzeile wählen', detail: 'Drei Schlagzeilen, nur eine stimmt.' },
    headline_write: { title: 'Die Schlagzeile schreiben', detail: 'Höchstens {n} Wörter, und wahr.' },
    short_report: { title: 'In {n} Sekunden erzählen', detail: 'Laut, wie im Radio.' },
  },
  guest_arrives: '{name} kommt dazu.',
  guest_testimony: 'Zeugnis',
  guest_disagrees: 'widerspricht',
  guest_asks: 'eine Frage',
  guest_moved: '{name} hat die Meinung geändert',
  register_label: 'Das Register',
  register_reason: {
    vous_to_tu: 'Romy duzt dich: du kannst sie auch duzen.',
    tu_to_vous: 'Hier siezt man sich: sag „vous“.',
  },
  write_label: 'Deine Schlagzeile',
  write_placeholder: 'Kurz, und wahr…',
  write_send: 'Schlagzeile vorschlagen',
  write_words: '{n} von höchstens {max} Wörtern',
  write_too_long: 'Zu lang: höchstens {max} Wörter.',
  write_supported: 'Die Quellen sagen es.',
  write_unsupported: 'Die Quellen sagen es nicht ganz, aber Romy behält sie.',
  write_contradicted: 'Die Quellen sagen etwas anderes. Schreib sie neu.',
  write_words_right: 'Gut verwendet: {words}',
  report_record: 'Aufnehmen · {n} s',
  report_recording: 'Romy hört zu',
  report_stop: 'Stopp',
  report_label: 'Deine Reportage',
  report_text_label: 'Deine Reportage, schriftlich',
  report_placeholder: 'Was du siehst, was du hörst…',
  report_send: 'An Romy schicken',
  report_again: 'Neu anfangen',
  report_no_mic: 'Hier gibt es kein Mikrofon: schreib deine Reportage.',
  made_report: 'Deine Reportage',
  kept_word_right: 'gut verwendet',
  vignette_label: 'Deine Vignette · {week}',
  vignettes_title: 'Deine Vignetten',
  one_more_question: 'Noch eine Frage',
  headline_label: 'Die Schlagzeile',
  headline_right: 'Das ist unsere Schlagzeile.',
  headline_wrong: 'Nicht diese: Die Quellen sagen etwas anderes.',
  status_selected: 'gewählt',
  status_correct: 'richtig',
  status_wrong: 'noch einmal',
  continue: 'Weiter',
  see_paper: 'Den Artikel ansehen',
  question_write_label: 'Deine Frage für die Leser',
  question_write_placeholder: 'Schreib sie, wie sie kommt, gern auf Deutsch…',
  question_propose: 'Romy fragen',
  your_version: 'Deine Version',
  reader_question: 'Die Frage für die Leser',
  send_desk: 'An die Redaktion schicken',
  change_word: 'Ein Wort ändern',
  send_edited: 'An die Redaktion schicken',
  made_headline: 'Deine Schlagzeile',
  made_question: 'Deine Frage für die Leser',
  contribution: 'du',
  for_releve: 'Für dein Relevé',
  kept_count: '{w} Wörter · {c} Fakten',
  file_revue: 'Revue ablegen',
  see_releve: 'Im Relevé ansehen',
  filed_on: 'Revue abgelegt am {date}',
  reread: 'Gespräch nachlesen',
  hide_thread: 'Gespräch ausblenden',
  loading: 'Revue wird geladen',
  loading_line: 'Romy sammelt ihre Notizen',
  model_down: 'Das Gespräch antwortet gerade nicht. Die Fakten und die Schlagzeile bleiben; deine Notizen sind gespeichert.',
  error_title: 'Die Revue antwortet nicht',
  error_body: 'Nichts ist verloren: versuch es gleich noch einmal.',
  retry: 'Noch einmal',
  disabled_title: 'Gerade keine Revue',
  disabled_body: 'Romy kommt bald mit einem Thema zurück.',
  closed_notice: 'Diese Revue ist abgelegt.',
  back_home: 'Zurück zu La Une',
  sous_presse: 'sous presse',
  mock_badge: 'Attrappe (dev)',
};

const TABLES: Record<RvLanguage, RevueCopy> = { fr: FR, en: EN, de: DE };

export function revueCopy(language: unknown): RevueCopy {
  const key = String(language || '').toLowerCase().slice(0, 2);
  return TABLES[(key === 'de' || key === 'fr' ? key : 'en') as RvLanguage];
}

/** `{name}` placeholders filled in. */
export function fill(template: string, values: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (match, key: string) => (key in values ? String(values[key]) : match));
}

/** Romy's few client-side lines (French, her voice) — the server writes every other one. */
export const ROMY_CLIENT_LINES = {
  /** The model is down: she keeps what exists (design §3.7 #model-down). */
  model_down:
    'Ma connexion lâche, ici. Je te laisse mes notes : on choisit le titre ensemble, et ta question, je la garde pour la semaine prochaine.',
  write_question: "Écris-la comme elle te vient. Même dans ta langue : je t'aide pour le français.",
  propose: 'Je te propose ça :',
  headline_ask: 'Mon titre. Lequel dit vrai ?',
  /** Phase 2: when the learner picks an option other than the one Romy's intro asked for. */
  headline_write_ask: 'Ton titre, alors. Court, et vrai.',
  report_ask: 'Trente secondes, comme à la radio : tu racontes ce que tu vois ?',
  resume: 'Te revoilà. On reprend où on en était.',
} as const;

/** The guests' names (WIRE §6.2 `cast_id`), the same in every language. An unknown id keeps its first part. */
export const GUEST_NAMES: Record<string, string> = {
  margaux_barman: 'Margaux',
  lila_bonnet: 'Lila',
  camille_marchand: 'Camille',
  landlord_marchand: 'M. Marchand',
  marin_leveque: 'Marin',
  augustin_de_roncourt: 'Gus',
};

export function guestName(castId: string): string {
  if (GUEST_NAMES[castId]) return GUEST_NAMES[castId];
  const first = castId.split('_')[0] || castId;
  return first.charAt(0).toUpperCase() + first.slice(1);
}

/** The register note's French line (WIRE §6.3 `register_note`; the server sends a code, the client words it). */
export const REGISTER_LINES_FR: Record<'vous_to_tu' | 'tu_to_vous', string> = {
  vous_to_tu: 'Avec Romy, on se tutoie.',
  tu_to_vous: 'Ici, on se vouvoie.',
};
