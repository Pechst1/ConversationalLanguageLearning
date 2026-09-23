/**
 * WP-82 — L'Épreuve («Plus de pratique») follows the one language rule.
 *
 * The drill loop's own words — the round names, the buttons, the verdicts, the
 * notices, the recap — are chrome: up to A2 they are the learner's language,
 * from B1 they are French (`chromeLanguage`, `lib/language-rule.ts`). The
 * exercise itself (the prompt, the options, the corrected line, the concept's
 * French title) is content and stays French whatever this table says.
 *
 * The French column is the design's publication voice, trimmed to the text
 * diet (WP-82): one line where there were two, no «plomb» metaphors in places
 * a learner has to act.
 */

import type { ControlLanguage } from '@/types/daily-journey';

import { normalizeControlLanguage } from '@/lib/atelier-v2-copy';

export type EpreuveCopy = {
  // screen
  screen_name: string;
  progress_label: string;
  close_session: string;
  run_one: string;
  run_many: string;
  finish: string;
  finish_confirm: string;
  finish_title: string;
  finish_title_partial: string;
  retour: string;
  rule: string;
  rule_try_first: string;
  rule_when: string;
  rule_pattern: string;
  rule_check: string;
  practice_fallback: string;
  session_fallback: string;
  // rounds and modes
  round_recognize: string;
  round_transform: string;
  round_sentence: string;
  round_produce: string;
  round_speak: string;
  round_conversation: string;
  mode_fill: string;
  mode_classify: string;
  mode_word_bank: string;
  // exercise furniture
  choices_label: string;
  sr_right: string;
  sr_wrong: string;
  sr_chosen: string;
  sr_spent: string;
  sr_add: string;
  setline_label: string;
  setline_hint: string;
  typecase_label: string;
  classify_label: string;
  case_count: string;
  place_here: string;
  labelfix_old: string;
  labelfix_new: string;
  transform_placeholder: string;
  sentence_instruction: string;
  speak_instruction: string;
  conversation_instruction: string;
  sentence_placeholder: string;
  speak_placeholder: string;
  conversation_placeholder: string;
  conversation_with: string;
  produce_placeholder: string;
  produce_missing: string;
  produce_words_label: string;
  words_count: string;
  words_range: string;
  words_more: string;
  // confidence + primary
  confidence_label: string;
  confidence_ask: string;
  sure: string;
  unsure: string;
  check: string;
  checking: string;
  continue: string;
  // verdicts
  verdict_correct: string;
  verdict_wrong: string;
  line_set: string;
  corrected: string;
  corrected_line: string;
  correction_n: string;
  corrections_n: string;
  task: string;
  task_default_why: string;
  unscored: string;
  skip_unscored: string;
  retry_line: string;
  retry: string;
  skip: string;
  report: string;
  notebook_added: string;
  rule_line: string;
  // second look
  relecture_pending: string;
  relecture_failed: string;
  relecture_done: string;
  relaunch: string;
  relaunching: string;
  // typed repair
  repair_label: string;
  repair_placeholder: string;
  repair_submit: string;
  repair_submitting: string;
  repair_ok: string;
  repair_no: string;
  // listen + record
  listen: string;
  listen_playing: string;
  listen_unavailable: string;
  record: string;
  record_stop: string;
  record_idle: string;
  record_recording: string;
  record_transcribing: string;
  nothing_heard: string;
  transcription_failed: string;
  mic_failed: string;
  // early mastery
  lock_kicker: string;
  lock_retired_one: string;
  lock_retired_many: string;
  lock_closed: string;
  lock_promo: string;
  // stamps + recap
  stamp_correct: string;
  recap_title: string;
  recap_ready: string;
  recap_dialog: string;
  recap_close: string;
  recap_gilt: string;
  recap_early: string;
  recap_done: string;
  tally_lines: string;
  tally_concepts: string;
  tally_errata: string;
  proof_fixed: string;
  proof_right: string;
  proof_line_set: string;
  phrase_flag: string;
  phrase_by: string;
  mint_title: string;
  mint_gilt: string;
  mint_one: string;
  mint_many: string;
  seal_label: string;
  seal_gilt: string;
  streak_one: string;
  streak_many: string;
  back_home: string;
  // recommended next
  next_review: string;
  next_mission: string;
  next_studio: string;
  next_library: string;
  next_reply: string;
  next_serial: string;
  next_feuilleton: string;
  next_rest: string;
  // system states
  resume_kicker: string;
  resume_title: string;
  resume_action: string;
  skeleton: string;
  notice_default: string;
  set_failed: string;
  // WP-83: the page's short notices (inline in the session, not toasts)
  say_review_started: string;
  say_review_unavailable: string;
  say_reported: string;
  say_report_failed: string;
  say_already_done: string;
  say_answer_first: string;
  say_token_won: string;
  say_send_failed: string;
  say_check_failed: string;
  say_finish_failed: string;
  say_open_failed: string;
  say_erratum_done: string;
  say_erratum_later: string;
  say_queue_empty: string;
};

const FR: EpreuveCopy = {
  screen_name: 'L’épreuve',
  progress_label: 'Progression de la séance',
  close_session: 'Fermer la séance',
  run_one: '{n} bonne réponse de suite',
  run_many: '{n} bonnes réponses de suite',
  finish: 'Terminer',
  finish_confirm: 'Arrêter ici ?',
  finish_title: 'Terminer la séance',
  finish_title_partial: 'Terminer avec ce qui est déjà fait',
  retour: 'Déjà corrigé',
  rule: 'La règle',
  rule_try_first: 'Commencez par l’exemple le plus simple.',
  rule_when: 'Quand :',
  rule_pattern: 'Le schéma :',
  rule_check: 'Le contrôle :',
  practice_fallback: 'Pratique',
  session_fallback: 'Séance du jour',
  round_recognize: 'Reconnaître',
  round_transform: 'Transformer',
  round_sentence: 'Phrase',
  round_produce: 'Paragraphe',
  round_speak: 'À l’oral',
  round_conversation: 'Conversation',
  mode_fill: 'Compléter',
  mode_classify: 'Classer',
  mode_word_bank: 'Banque de mots',
  choices_label: 'Choix',
  sr_right: 'juste',
  sr_wrong: 'faux',
  sr_chosen: 'choisi',
  sr_spent: 'déjà placé',
  sr_add: '(à ajouter)',
  setline_label: 'Votre phrase',
  setline_hint: 'Touchez les mots ci-dessous',
  typecase_label: 'Mots disponibles',
  classify_label: 'Classer',
  case_count: '{n} sortes',
  place_here: 'Placer ici',
  labelfix_old: 'Votre choix',
  labelfix_new: 'Correct',
  transform_placeholder: 'Écrivez la nouvelle phrase…',
  sentence_instruction: 'Répondez avec une phrase complète.',
  speak_instruction: 'Dites votre réponse.',
  conversation_instruction: 'Répondez au message.',
  sentence_placeholder: 'Votre phrase…',
  speak_placeholder: 'Vos mots apparaissent ici.',
  conversation_placeholder: 'Votre réponse…',
  conversation_with: 'Conversation avec {name}',
  produce_placeholder: 'Votre paragraphe…',
  produce_missing: 'La consigne est indisponible.',
  produce_words_label: 'Les mots à placer',
  words_count: '{n} mots',
  words_range: '{n} / {min}–{max} mots',
  words_more: 'encore {n}',
  confidence_label: 'Votre confiance',
  confidence_ask: 'Vous êtes…',
  sure: 'sûr·e',
  unsure: 'pas sûr·e',
  check: 'Vérifier',
  checking: 'Vérification…',
  continue: 'Continuer',
  verdict_correct: 'Bien joué !',
  verdict_wrong: 'À reprendre',
  line_set: 'Juste.',
  corrected: 'corrigé',
  corrected_line: 'Ligne corrigée',
  correction_n: 'Correction {n}',
  corrections_n: '{n} corrections',
  task: 'La consigne',
  task_default_why: 'La réponse ne suit pas encore la consigne. Relisez-la et réessayez.',
  unscored: 'Réponse enregistrée, pas encore vérifiée.',
  skip_unscored: 'Passer sans évaluation',
  retry_line: 'Réessayer la ligne',
  retry: 'Réessayer',
  skip: 'Passer cet exercice',
  report: 'Signaler cet exercice',
  notebook_added: 'Ajouté au carnet',
  rule_line: 'La règle · {title}',
  relecture_pending: 'Relecture en cours…',
  relecture_failed: 'Relecture interrompue.',
  relecture_done: 'Relecture terminée',
  relaunch: 'Relancer',
  relaunching: 'Relance…',
  repair_label: 'Recopiez la correction',
  repair_placeholder: 'Tapez la ligne corrigée…',
  repair_submit: 'Comparer',
  repair_submitting: 'Comparaison…',
  repair_ok: 'Juste.',
  repair_no: 'Pas tout à fait — reprenez la ligne.',
  listen: 'Écouter',
  listen_playing: 'Lecture…',
  listen_unavailable: 'Voix indisponible',
  record: 'Enregistrer',
  record_stop: 'Arrêter l’enregistrement',
  record_idle: 'Touchez pour parler',
  record_recording: 'Touchez pour arrêter',
  record_transcribing: 'Transcription…',
  nothing_heard: 'Je n’ai rien entendu.',
  transcription_failed: 'La transcription a échoué — réessayez, ou écrivez.',
  mic_failed: 'Le micro n’a pas pu être ouvert.',
  lock_kicker: 'Déjà maîtrisé',
  lock_retired_one: '1 exercice en moins aujourd’hui.',
  lock_retired_many: '{n} exercices en moins aujourd’hui.',
  lock_closed: 'Cette règle se ferme en avance.',
  lock_promo: 'Sans faute',
  stamp_correct: 'Juste',
  recap_title: 'Séance terminée',
  recap_ready: 'Terminé',
  recap_dialog: 'Fin de la séance',
  recap_close: 'Fermer',
  recap_gilt: 'Sans faute — sceau doré.',
  recap_early: 'Terminée en avance : tout compte.',
  recap_done: 'Tout est enregistré.',
  tally_lines: 'réponses',
  tally_concepts: 'règles',
  tally_errata: 'corrections',
  proof_fixed: 'Corrigé',
  proof_right: 'Juste',
  proof_line_set: 'juste',
  phrase_flag: 'Pour demain',
  phrase_by: 'L’Atelier',
  mint_title: 'Jetons gagnés',
  mint_gilt: 'Un sceau doré pour une séance sans faute.',
  mint_one: '1 jeton gagné.',
  mint_many: '{n} jetons gagnés.',
  seal_label: 'Sceau de l’Atelier',
  seal_gilt: 'doré',
  streak_one: '{n} jour de suite',
  streak_many: '{n} jours de suite',
  back_home: 'Retour à La Une',
  next_review: 'Réviser maintenant',
  next_mission: 'Ouvrir la lettre',
  next_studio: 'Ouvrir le studio',
  next_library: 'Continuer le livre',
  next_reply: 'Répondre',
  next_serial: 'Ouvrir le Feuilleton',
  next_feuilleton: 'Ouvrir le Feuilleton',
  next_rest: 'Retour à La Une',
  resume_kicker: 'Séance en cours',
  resume_title: 'Vous vous êtes arrêté·e en route.',
  resume_action: 'Reprendre',
  skeleton: 'Préparation de la séance…',
  notice_default: 'La séance n’a pas pu être préparée. Votre travail est enregistré.',
  set_failed: 'Cet exercice n’a pas pu être préparé. Votre travail est enregistré.',
  say_review_started: 'Relecture automatique lancée.',
  say_review_unavailable: 'La relecture automatique est indisponible.',
  say_reported: 'Exercice signalé.',
  say_report_failed: 'L’exercice n’a pas pu être signalé.',
  say_already_done: 'Cet exercice est déjà fait.',
  say_answer_first: 'Ajoutez une réponse avant de vérifier.',
  say_token_won: 'Jeton gagné.',
  say_send_failed: 'La correction n’a pas pu être envoyée.',
  say_check_failed: 'La correction n’a pas pu être vérifiée.',
  say_finish_failed: 'La séance n’a pas pu être terminée.',
  say_open_failed: 'Cette correction n’a pas pu être ouverte.',
  say_erratum_done: 'Correction reprise.',
  say_erratum_later: 'Relue. Elle reviendra bientôt.',
  say_queue_empty: 'Rien à réviser pour l’instant.',
};

const EN: EpreuveCopy = {
  screen_name: 'Practice',
  progress_label: 'Practice progress',
  close_session: 'Close practice',
  run_one: '{n} right answer in a row',
  run_many: '{n} right answers in a row',
  finish: 'Finish',
  finish_confirm: 'Stop here?',
  finish_title: 'Finish practice',
  finish_title_partial: 'Finish with what is done',
  retour: 'Fixed before',
  rule: 'The rule',
  rule_try_first: 'Start with the simplest example.',
  rule_when: 'When:',
  rule_pattern: 'Pattern:',
  rule_check: 'Check:',
  practice_fallback: 'Practice',
  session_fallback: 'Today’s practice',
  round_recognize: 'Recognize',
  round_transform: 'Transform',
  round_sentence: 'Sentence',
  round_produce: 'Paragraph',
  round_speak: 'Speaking',
  round_conversation: 'Conversation',
  mode_fill: 'Fill in',
  mode_classify: 'Sort',
  mode_word_bank: 'Word bank',
  choices_label: 'Choices',
  sr_right: 'right',
  sr_wrong: 'wrong',
  sr_chosen: 'chosen',
  sr_spent: 'already placed',
  sr_add: '(to add)',
  setline_label: 'Your sentence',
  setline_hint: 'Tap the words below',
  typecase_label: 'Available words',
  classify_label: 'Sort',
  case_count: '{n} kinds',
  place_here: 'Put here',
  labelfix_old: 'Your choice',
  labelfix_new: 'Correct',
  transform_placeholder: 'Write the new sentence…',
  sentence_instruction: 'Answer with a full sentence.',
  speak_instruction: 'Say your answer.',
  conversation_instruction: 'Reply to the message.',
  sentence_placeholder: 'Your sentence…',
  speak_placeholder: 'Your words appear here.',
  conversation_placeholder: 'Your reply…',
  conversation_with: 'Conversation with {name}',
  produce_placeholder: 'Your paragraph…',
  produce_missing: 'The task is unavailable.',
  produce_words_label: 'Words to use',
  words_count: '{n} words',
  words_range: '{n} / {min}–{max} words',
  words_more: '{n} more',
  confidence_label: 'Your confidence',
  confidence_ask: 'Are you…',
  sure: 'sure',
  unsure: 'not sure',
  check: 'Check',
  checking: 'Checking…',
  continue: 'Continue',
  verdict_correct: 'Well done!',
  verdict_wrong: 'Not yet',
  line_set: 'Right.',
  corrected: 'corrected',
  corrected_line: 'Corrected line',
  correction_n: 'Correction {n}',
  corrections_n: '{n} corrections',
  task: 'The task',
  task_default_why: 'The answer does not follow the task yet. Read it again and retry.',
  unscored: 'Answer saved, not checked yet.',
  skip_unscored: 'Skip without a check',
  retry_line: 'Try the line again',
  retry: 'Try again',
  skip: 'Skip this exercise',
  report: 'Report this exercise',
  notebook_added: 'Added to your notebook',
  rule_line: 'The rule · {title}',
  relecture_pending: 'Second check running…',
  relecture_failed: 'The second check stopped.',
  relecture_done: 'Second check done',
  relaunch: 'Run again',
  relaunching: 'Running…',
  repair_label: 'Copy the correction',
  repair_placeholder: 'Type the corrected line…',
  repair_submit: 'Compare',
  repair_submitting: 'Comparing…',
  repair_ok: 'Right.',
  repair_no: 'Not quite — try the line again.',
  listen: 'Listen',
  listen_playing: 'Playing…',
  listen_unavailable: 'Voice unavailable',
  record: 'Record',
  record_stop: 'Stop recording',
  record_idle: 'Tap to speak',
  record_recording: 'Tap to stop',
  record_transcribing: 'Transcribing…',
  nothing_heard: 'I heard nothing.',
  transcription_failed: 'The transcription failed — try again, or type.',
  mic_failed: 'The microphone could not be opened.',
  lock_kicker: 'Already mastered',
  lock_retired_one: '1 exercise fewer today.',
  lock_retired_many: '{n} exercises fewer today.',
  lock_closed: 'This rule closes early.',
  lock_promo: 'No mistakes',
  stamp_correct: 'Right',
  recap_title: 'Practice done',
  recap_ready: 'Done',
  recap_dialog: 'End of practice',
  recap_close: 'Close',
  recap_gilt: 'No mistakes — a gold seal.',
  recap_early: 'Finished early: everything counts.',
  recap_done: 'Everything is saved.',
  tally_lines: 'answers',
  tally_concepts: 'rules',
  tally_errata: 'corrections',
  proof_fixed: 'Corrected',
  proof_right: 'Right',
  proof_line_set: 'right',
  phrase_flag: 'For tomorrow',
  phrase_by: 'L’Atelier',
  mint_title: 'Tokens earned',
  mint_gilt: 'A gold seal for a session without mistakes.',
  mint_one: '1 token earned.',
  mint_many: '{n} tokens earned.',
  seal_label: 'Atelier seal',
  seal_gilt: 'gold',
  streak_one: '{n} day in a row',
  streak_many: '{n} days in a row',
  back_home: 'Back to La Une',
  next_review: 'Review now',
  next_mission: 'Open the letter',
  next_studio: 'Open the studio',
  next_library: 'Continue the book',
  next_reply: 'Reply',
  next_serial: 'Open the Feuilleton',
  next_feuilleton: 'Open the Feuilleton',
  next_rest: 'Back to La Une',
  resume_kicker: 'In progress',
  resume_title: 'You stopped halfway.',
  resume_action: 'Resume',
  skeleton: 'Preparing your practice…',
  notice_default: 'The practice could not be prepared. Your work is saved.',
  set_failed: 'This exercise could not be prepared. Your work is saved.',
  say_review_started: 'Second check started.',
  say_review_unavailable: 'The second check is unavailable.',
  say_reported: 'Exercise reported.',
  say_report_failed: 'The exercise could not be reported.',
  say_already_done: 'This exercise is already done.',
  say_answer_first: 'Add an answer before you check.',
  say_token_won: 'Token earned.',
  say_send_failed: 'The correction could not be sent.',
  say_check_failed: 'The correction could not be checked.',
  say_finish_failed: 'The practice could not be finished.',
  say_open_failed: 'This correction could not be opened.',
  say_erratum_done: 'Correction done.',
  say_erratum_later: 'Checked. It will come back soon.',
  say_queue_empty: 'Nothing to review right now.',
};

const DE: EpreuveCopy = {
  screen_name: 'Übung',
  progress_label: 'Fortschritt der Übung',
  close_session: 'Übung schließen',
  run_one: '{n} richtige Antwort in Folge',
  run_many: '{n} richtige Antworten in Folge',
  finish: 'Beenden',
  finish_confirm: 'Hier aufhören?',
  finish_title: 'Übung beenden',
  finish_title_partial: 'Mit dem Erledigten beenden',
  retour: 'Schon korrigiert',
  rule: 'Die Regel',
  rule_try_first: 'Fang mit dem einfachsten Beispiel an.',
  rule_when: 'Wann:',
  rule_pattern: 'Muster:',
  rule_check: 'Prüfen:',
  practice_fallback: 'Übung',
  session_fallback: 'Heutige Übung',
  round_recognize: 'Erkennen',
  round_transform: 'Umformen',
  round_sentence: 'Satz',
  round_produce: 'Absatz',
  round_speak: 'Sprechen',
  round_conversation: 'Gespräch',
  mode_fill: 'Ergänzen',
  mode_classify: 'Zuordnen',
  mode_word_bank: 'Wortbank',
  choices_label: 'Auswahl',
  sr_right: 'richtig',
  sr_wrong: 'falsch',
  sr_chosen: 'gewählt',
  sr_spent: 'schon gesetzt',
  sr_add: '(ergänzen)',
  setline_label: 'Dein Satz',
  setline_hint: 'Tippe die Wörter unten an',
  typecase_label: 'Verfügbare Wörter',
  classify_label: 'Zuordnen',
  case_count: '{n} Arten',
  place_here: 'Hierhin',
  labelfix_old: 'Deine Wahl',
  labelfix_new: 'Richtig',
  transform_placeholder: 'Schreib den neuen Satz…',
  sentence_instruction: 'Antworte mit einem ganzen Satz.',
  speak_instruction: 'Sprich deine Antwort.',
  conversation_instruction: 'Antworte auf die Nachricht.',
  sentence_placeholder: 'Dein Satz…',
  speak_placeholder: 'Deine Wörter erscheinen hier.',
  conversation_placeholder: 'Deine Antwort…',
  conversation_with: 'Gespräch mit {name}',
  produce_placeholder: 'Dein Absatz…',
  produce_missing: 'Die Aufgabe ist nicht verfügbar.',
  produce_words_label: 'Wörter zum Einbauen',
  words_count: '{n} Wörter',
  words_range: '{n} / {min}–{max} Wörter',
  words_more: 'noch {n}',
  confidence_label: 'Wie sicher bist du?',
  confidence_ask: 'Du bist…',
  sure: 'sicher',
  unsure: 'unsicher',
  check: 'Prüfen',
  checking: 'Wird geprüft…',
  continue: 'Weiter',
  verdict_correct: 'Gut gemacht!',
  verdict_wrong: 'Noch nicht',
  line_set: 'Richtig.',
  corrected: 'korrigiert',
  corrected_line: 'Korrigierte Zeile',
  correction_n: 'Korrektur {n}',
  corrections_n: '{n} Korrekturen',
  task: 'Die Aufgabe',
  task_default_why: 'Die Antwort erfüllt die Aufgabe noch nicht. Lies sie noch einmal und versuch es erneut.',
  unscored: 'Antwort gespeichert, noch nicht geprüft.',
  skip_unscored: 'Ohne Prüfung weiter',
  retry_line: 'Zeile neu versuchen',
  retry: 'Erneut versuchen',
  skip: 'Übung überspringen',
  report: 'Übung melden',
  notebook_added: 'Ins Heft übernommen',
  rule_line: 'Die Regel · {title}',
  relecture_pending: 'Zweite Prüfung läuft…',
  relecture_failed: 'Die zweite Prüfung brach ab.',
  relecture_done: 'Zweite Prüfung fertig',
  relaunch: 'Neu starten',
  relaunching: 'Läuft…',
  repair_label: 'Schreib die Korrektur ab',
  repair_placeholder: 'Tippe die korrigierte Zeile…',
  repair_submit: 'Vergleichen',
  repair_submitting: 'Wird verglichen…',
  repair_ok: 'Richtig.',
  repair_no: 'Nicht ganz — versuch die Zeile noch einmal.',
  listen: 'Anhören',
  listen_playing: 'Wird abgespielt…',
  listen_unavailable: 'Stimme nicht verfügbar',
  record: 'Aufnehmen',
  record_stop: 'Aufnahme stoppen',
  record_idle: 'Zum Sprechen tippen',
  record_recording: 'Zum Stoppen tippen',
  record_transcribing: 'Wird transkribiert…',
  nothing_heard: 'Ich habe nichts gehört.',
  transcription_failed: 'Die Transkription schlug fehl — versuch es erneut oder tippe.',
  mic_failed: 'Das Mikrofon ließ sich nicht öffnen.',
  lock_kicker: 'Schon gemeistert',
  lock_retired_one: 'Heute 1 Übung weniger.',
  lock_retired_many: 'Heute {n} Übungen weniger.',
  lock_closed: 'Diese Regel ist früher fertig.',
  lock_promo: 'Fehlerfrei',
  stamp_correct: 'Richtig',
  recap_title: 'Übung geschafft',
  recap_ready: 'Fertig',
  recap_dialog: 'Ende der Übung',
  recap_close: 'Schließen',
  recap_gilt: 'Fehlerfrei — ein goldenes Siegel.',
  recap_early: 'Früher beendet: alles zählt.',
  recap_done: 'Alles ist gespeichert.',
  tally_lines: 'Antworten',
  tally_concepts: 'Regeln',
  tally_errata: 'Korrekturen',
  proof_fixed: 'Korrigiert',
  proof_right: 'Richtig',
  proof_line_set: 'richtig',
  phrase_flag: 'Für morgen',
  phrase_by: 'L’Atelier',
  mint_title: 'Marken verdient',
  mint_gilt: 'Ein goldenes Siegel für eine fehlerfreie Übung.',
  mint_one: '1 Marke verdient.',
  mint_many: '{n} Marken verdient.',
  seal_label: 'Siegel des Ateliers',
  seal_gilt: 'golden',
  streak_one: '{n} Tag in Folge',
  streak_many: '{n} Tage in Folge',
  back_home: 'Zurück zu La Une',
  next_review: 'Jetzt wiederholen',
  next_mission: 'Brief öffnen',
  next_studio: 'Studio öffnen',
  next_library: 'Buch weiterlesen',
  next_reply: 'Antworten',
  next_serial: 'Feuilleton öffnen',
  next_feuilleton: 'Feuilleton öffnen',
  next_rest: 'Zurück zu La Une',
  resume_kicker: 'Läuft',
  resume_title: 'Du hast mittendrin aufgehört.',
  resume_action: 'Fortsetzen',
  skeleton: 'Deine Übung wird vorbereitet…',
  notice_default: 'Die Übung ließ sich nicht vorbereiten. Deine Arbeit ist gespeichert.',
  set_failed: 'Diese Übung ließ sich nicht vorbereiten. Deine Arbeit ist gespeichert.',
  say_review_started: 'Zweite Prüfung gestartet.',
  say_review_unavailable: 'Die zweite Prüfung ist nicht verfügbar.',
  say_reported: 'Übung gemeldet.',
  say_report_failed: 'Die Übung ließ sich nicht melden.',
  say_already_done: 'Diese Übung ist schon erledigt.',
  say_answer_first: 'Gib eine Antwort ein, bevor du prüfst.',
  say_token_won: 'Marke verdient.',
  say_send_failed: 'Die Korrektur ließ sich nicht senden.',
  say_check_failed: 'Die Korrektur ließ sich nicht prüfen.',
  say_finish_failed: 'Die Übung ließ sich nicht beenden.',
  say_open_failed: 'Diese Korrektur ließ sich nicht öffnen.',
  say_erratum_done: 'Korrektur erledigt.',
  say_erratum_later: 'Geprüft. Sie kommt bald wieder.',
  say_queue_empty: 'Gerade gibt es nichts zu wiederholen.',
};

const TABLES: Record<ControlLanguage, EpreuveCopy> = { en: EN, de: DE, fr: FR };

/** The Épreuve's chrome in the language `chromeLanguage()` resolved. */
export function epreuveCopy(language: unknown): EpreuveCopy {
  return TABLES[normalizeControlLanguage(language)];
}

/** `{n}`-style placeholders filled in. */
export function fill(template: string, values: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (match, key: string) => (key in values ? String(values[key]) : match));
}

/** «3 / 20–40 words · 17 more», in the chrome language. */
export function wordRangeText(copy: EpreuveCopy, count: number, minWords?: unknown, maxWords?: unknown): string {
  const min = Number(minWords);
  const max = Number(maxWords);
  if (Number.isFinite(min) && Number.isFinite(max) && min > 0 && max >= min) {
    const remaining = Math.max(0, Math.round(min) - count);
    const range = fill(copy.words_range, { n: count, min: Math.round(min), max: Math.round(max) });
    return remaining > 0 ? `${range} · ${fill(copy.words_more, { n: remaining })}` : range;
  }
  return fill(copy.words_count, { n: count });
}

export default epreuveCopy;
