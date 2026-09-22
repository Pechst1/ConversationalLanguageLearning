/**
 * Control-language chrome for the daily journey (WP-07 functional).
 *
 * Only the app's own labels live here. Every learner-facing sentence about the
 * scene, the task or the correction comes from the server's `*_native` /
 * `*_fr` fields — this file never invents content.
 *
 * Deliberately plain: the acceptance test is that a first-time learner finishes
 * the scene without having to learn the words "La Une", "Épreuve" or "Relevé".
 *
 * WP-01 owns `lib/atelier-v2-copy.ts` and should absorb this table when the
 * Claude Design system lands; the keys are the contract, not the strings.
 */

import type { ControlLanguage } from '@/types/daily-journey';

export type JourneyCopyKey =
  | 'today_eyebrow'
  | 'start'
  | 'resume'
  | 'preparing_title'
  | 'preparing_body'
  | 'preparing_retry'
  | 'unavailable_title'
  | 'unavailable_body'
  | 'unavailable_retry'
  | 'legacy_resume_title'
  | 'legacy_resume_body'
  | 'legacy_resume_action'
  | 'objective'
  | 'scene_continue'
  | 'answer_label'
  | 'answer_placeholder'
  | 'send'
  | 'sending'
  | 'check'
  | 'continue'
  | 'help'
  | 'help_hint'
  | 'help_translation'
  | 'help_solution'
  | 'help_suggested_response'
  | 'help_shown'
  | 'assistance_used'
  | 'record'
  | 'stop_recording'
  | 'transcribing'
  | 'voice_failed'
  | 'voice_retry'
  | 'use_text'
  | 'use_voice'
  | 'speak'
  | 'voice_hint'
  | 'voice_transcript_label'
  | 'voice_transcript_hint'
  | 'voice_permission'
  | 'voice_unsupported'
  | 'voice_offline'
  | 'voice_empty'
  | 'empty_answer'
  | 'still_grading'
  | 'try_grading_again'
  | 'retrying'
  | 'reconciled'
  | 'transport_error'
  | 'retry'
  | 'offline_cached'
  | 'offline_empty'
  | 'pending_sync'
  | 'syncing'
  | 'stale_from_earlier_day'
  | 'correct'
  | 'supported'
  | 'wrong'
  | 'correction'
  | 'reply_authored_note'
  | 'progress_label'
  | 'time_left'
  | 'time_unknown'
  | 'finish_early'
  | 'pause'
  | 'paused_title'
  | 'paused_body'
  | 'awaiting_finish_title'
  | 'awaiting_finish_body'
  | 'awaiting_finish_action'
  | 'finished_title'
  | 'finished_partial_title'
  | 'finished_partial_body'
  | 'practiced'
  | 'capability_shown'
  | 'capability_state_not_tried'
  | 'capability_state_with_support'
  | 'capability_state_independent_once'
  | 'capability_state_used_again_later'
  // WP-33 — register and pragmatics. The dimension is scored by the same
  // rubric as the three capabilities above, so it reuses their state labels
  // and adds only the honest fourth answer: not assessed.
  | 'capability_register'
  | 'capability_state_not_evaluated'
  | 'correction_register'
  // WP-36 — the character asks for the repair before it corrects. The question
  // itself is the character's French line and arrives on the wire; these are
  // only the labels the app puts around it.
  | 'correction_self_repair'
  | 'self_repair_hint'
  | 'evidence_recognized'
  | 'evidence_produced_supported'
  | 'evidence_produced_independent'
  | 'evidence_not_yet'
  | 'evidence_unscored'
  | 'next_focus'
  | 'duration_not_measured'
  | 'more_practice'
  | 'more_practice_note'
  // WP-16 / D-0: the recap's pointer into the «Plus de pratique» drill loop
  // for one target the scene actually practised.
  | 'practice_this'
  | 'done_today'
  | 'done_review'
  | 'nothing_offered'
  // WP-32 «Écouter d'abord» — the four-stage listening cycle. Chrome only:
  // the two guesses, the lines and the phrase to retain are French content
  // derived from the scene itself, and are not translated.
  | 'listen_first_label'
  | 'listen_first_hint'
  | 'listen_first_on'
  | 'listen_first_off'
  | 'radio_stage_predire'
  | 'radio_stage_ecouter'
  | 'radio_stage_verifier'
  | 'radio_stage_retenir'
  | 'radio_predire_body'
  | 'radio_predire_native'
  | 'radio_guess_label'
  | 'radio_guess_selected'
  | 'radio_listen_action'
  | 'radio_ecouter_body'
  | 'radio_words_hidden'
  | 'radio_preparing'
  | 'radio_play'
  | 'radio_replay'
  | 'radio_stop'
  | 'radio_playing'
  | 'radio_verify_action'
  | 'radio_verifier_body'
  | 'radio_reveal'
  | 'radio_reveal_all'
  | 'radio_guess_confirmed'
  | 'radio_guess_other'
  | 'radio_guess_unresolved'
  | 'radio_evidence_label'
  | 'radio_retenir_body'
  | 'radio_retain_none'
  | 'radio_truncated'
  | 'radio_audio_disabled'
  | 'radio_audio_failed'
  | 'radio_audio_offline'
  | 'radio_audio_unsupported'
  | 'radio_audio_empty'
  | 'radio_read_instead'
  // -- WP-66: day shapes and the three formats brought in from the Séance ----
  | 'word_bank_spare_chips'
  | 'transform_source_label'
  | 'classify_label'
  | 'listen_first_day'
  | 'chapter_recap_label'
  | 'register_label'
  | 'letter_from'
  | 'letter_reply_label';

type CopyTable = Record<JourneyCopyKey, string>;

const EN: CopyTable = {
  today_eyebrow: 'Today',
  start: 'Start today',
  resume: 'Continue today',
  preparing_title: 'Getting today ready',
  preparing_body: 'Your scene is being prepared. This usually takes a moment.',
  preparing_retry: 'Check again',
  unavailable_title: "Today's scene could not be prepared",
  unavailable_body: 'Nothing was lost. You can try again, or use the rest of the day.',
  unavailable_retry: 'Try again',
  legacy_resume_title: 'Unfinished practice session',
  legacy_resume_body: 'You still have an older practice session open. It is kept separately.',
  legacy_resume_action: 'Open that session',
  objective: 'What you need to do',
  scene_continue: 'Continue',
  answer_label: 'Your answer',
  answer_placeholder: 'Write your answer in French',
  send: 'Send',
  sending: 'Sending…',
  check: 'Check',
  continue: 'Continue',
  help: 'Help',
  help_hint: 'Hint',
  help_translation: 'Translation',
  help_solution: 'Show the answer',
  help_suggested_response: 'Suggest a reply',
  help_shown: 'Help shown',
  assistance_used: 'Help already used',
  record: 'Record',
  stop_recording: 'Stop',
  transcribing: 'Transcribing…',
  voice_failed: 'That recording could not be transcribed. Your turn is still open.',
  voice_retry: 'Record again',
  use_text: 'Type instead',
  use_voice: 'Speak instead',
  speak: 'Speak',
  voice_hint: 'Say your answer out loud. We turn it into text — nothing here judges your pronunciation.',
  voice_transcript_label: 'What we heard',
  voice_transcript_hint: 'Correct anything we got wrong, then send.',
  voice_permission: 'The microphone is not allowed. You can answer in writing; to speak, allow the microphone in your device settings.',
  voice_unsupported: 'This device cannot record here. Answer in writing.',
  voice_offline: 'Without a connection there is no transcription. Answer in writing, or try again later.',
  voice_empty: 'Nothing was recorded. Your turn is still open.',
  empty_answer: 'Write something first.',
  still_grading: 'Still being checked. Nothing was scored yet.',
  try_grading_again: 'Check again',
  retrying: 'Still working — retrying the same request.',
  reconciled: 'This scene moved on. It has been refreshed for you.',
  transport_error: 'That did not reach the server. Your answer was kept.',
  retry: 'Try again',
  offline_cached: 'You are offline. This is your saved copy — nothing on it has been checked.',
  offline_empty: 'You are offline, and there is nothing saved to show yet.',
  pending_sync: 'Something you did has not reached the server yet. It is kept on this device.',
  syncing: 'Sending to the server…',
  stale_from_earlier_day: 'This was saved on an earlier day.',
  correct: 'Correct',
  supported: 'Correct, with help',
  wrong: 'Not yet',
  correction: 'One thing to fix',
  reply_authored_note: 'Written reply from the script',
  progress_label: 'Progress in today’s scene',
  time_left: 'left',
  time_unknown: 'Time not measured',
  finish_early: 'Stop here',
  pause: 'Pause',
  paused_title: 'Paused',
  paused_body: 'Everything you finished is saved. Pick up where you left off.',
  awaiting_finish_title: 'Every step is done',
  awaiting_finish_body:
    'Today’s scene is not saved as finished yet. Finishing it records what you did.',
  awaiting_finish_action: 'Finish today',
  finished_title: 'Scene finished',
  finished_partial_title: 'Stopped part-way',
  finished_partial_body: 'Only the part you finished was recorded.',
  practiced: 'What you practised',
  capability_shown: 'What you can now do',
  capability_state_not_tried: 'not tried yet',
  capability_state_with_support: 'with help',
  capability_state_independent_once: 'on your own, once',
  capability_state_used_again_later: 'used again later',
  capability_register: 'Speaking to the right person the right way',
  capability_state_not_evaluated: 'not assessed',
  correction_register: 'Who you are speaking to',
  correction_self_repair: 'The form you were just asked about',
  self_repair_hint: 'Say it again with the form you mean.',
  evidence_recognized: 'recognised',
  evidence_produced_supported: 'used, with help',
  evidence_produced_independent: 'used on your own',
  evidence_not_yet: 'not yet',
  evidence_unscored: 'not checked',
  next_focus: 'Worth another look',
  duration_not_measured: 'Duration is not measured yet.',
  more_practice: 'More practice',
  more_practice_note: 'Optional. It does not reopen today’s scene.',
  practice_this: 'Practise this',
  done_today: 'Today’s scene is done.',
  done_review: 'Look again',
  nothing_offered: 'No scene is available right now.',
  listen_first_label: 'Listen first',
  listen_first_hint: 'Guess what happens, listen without the text, then check. Harder, and the part that trains listening.',
  listen_first_on: 'Listen first',
  listen_first_off: 'Read instead',
  radio_stage_predire: 'Guess',
  radio_stage_ecouter: 'Listen',
  radio_stage_verifier: 'Check',
  radio_stage_retenir: 'Keep',
  radio_predire_native: 'You hear the scene first without the text. The text comes afterwards, line by line.',
  radio_predire_body: 'Before you listen: how do you think this ends? There is no penalty for guessing wrong — guessing is what makes the listening work.',
  radio_guess_label: 'Your guess',
  radio_guess_selected: 'chosen',
  radio_listen_action: 'Listen',
  radio_ecouter_body: 'The words stay hidden. You can replay any line as often as you like.',
  radio_words_hidden: 'Text hidden',
  radio_preparing: 'Preparing the audio',
  radio_play: 'Play the episode',
  radio_replay: 'Play again',
  radio_stop: 'Stop',
  radio_playing: 'Playing',
  radio_verify_action: 'Check my guess',
  radio_verifier_body: 'Tap a line to see what was said.',
  radio_reveal: 'Show this line',
  radio_reveal_all: 'Show every line',
  radio_guess_confirmed: 'Your guess held.',
  radio_guess_other: 'It went the other way.',
  radio_guess_unresolved: 'The scene does not settle it either way, so neither guess is wrong.',
  radio_evidence_label: 'What settles it',
  radio_retenir_body: 'One thing to listen for tomorrow:',
  radio_retain_none: 'Nothing to single out in this episode.',
  radio_truncated: 'A long episode: only the first part was recorded.',
  radio_audio_disabled: 'Audio is not switched on for this account. The scene is here to read.',
  radio_audio_failed: 'The audio could not be prepared. The scene is here to read, and nothing is lost.',
  radio_audio_offline: 'Without a connection there is no audio. Read the scene, or try again later.',
  radio_audio_unsupported: 'This device will not play audio. The scene is here to read.',
  radio_audio_empty: 'This scene has nothing to say aloud. Read it instead.',
  radio_read_instead: 'Read the scene',
  word_bank_spare_chips: 'Not every word belongs in the answer.',
  transform_source_label: 'The sentence to rewrite',
  classify_label: 'Choose one',
  listen_first_day: 'Listen first — the text comes after.',
  chapter_recap_label: 'Where the chapter leaves things',
  register_label: 'How you addressed them',
  letter_from: 'Letter from {name}',
  letter_reply_label: 'Your reply',
};

const DE: CopyTable = {
  today_eyebrow: 'Heute',
  start: 'Heute starten',
  resume: 'Heute fortsetzen',
  preparing_title: 'Heute wird vorbereitet',
  preparing_body: 'Deine Szene wird gerade vorbereitet. Das dauert meist nur einen Moment.',
  preparing_retry: 'Erneut prüfen',
  unavailable_title: 'Die heutige Szene konnte nicht vorbereitet werden',
  unavailable_body: 'Nichts ist verloren. Versuche es erneut oder nutze den Rest des Tages.',
  unavailable_retry: 'Erneut versuchen',
  legacy_resume_title: 'Offene ältere Übung',
  legacy_resume_body: 'Du hast noch eine ältere Übung offen. Sie wird getrennt geführt.',
  legacy_resume_action: 'Diese Übung öffnen',
  objective: 'Deine Aufgabe',
  scene_continue: 'Weiter',
  answer_label: 'Deine Antwort',
  answer_placeholder: 'Schreibe deine Antwort auf Französisch',
  send: 'Senden',
  sending: 'Wird gesendet…',
  check: 'Prüfen',
  continue: 'Weiter',
  help: 'Hilfe',
  help_hint: 'Tipp',
  help_translation: 'Übersetzung',
  help_solution: 'Lösung zeigen',
  help_suggested_response: 'Antwort vorschlagen',
  help_shown: 'Hilfe angezeigt',
  assistance_used: 'Hilfe bereits genutzt',
  record: 'Aufnehmen',
  stop_recording: 'Stopp',
  transcribing: 'Wird transkribiert…',
  voice_failed: 'Die Aufnahme konnte nicht transkribiert werden. Du bist weiterhin dran.',
  voice_retry: 'Neu aufnehmen',
  use_text: 'Lieber tippen',
  use_voice: 'Lieber sprechen',
  speak: 'Sprechen',
  voice_hint: 'Sag deine Antwort laut. Wir schreiben sie mit — deine Aussprache wird hier nicht bewertet.',
  voice_transcript_label: 'Das haben wir gehört',
  voice_transcript_hint: 'Korrigiere, was falsch verstanden wurde, und schick es ab.',
  voice_permission: 'Das Mikrofon ist nicht erlaubt. Du kannst schriftlich antworten; zum Sprechen erlaube das Mikrofon in den Geräteeinstellungen.',
  voice_unsupported: 'Dieses Gerät kann hier nicht aufnehmen. Antworte schriftlich.',
  voice_offline: 'Ohne Verbindung gibt es keine Transkription. Antworte schriftlich oder versuche es später.',
  voice_empty: 'Es wurde nichts aufgenommen. Du bist weiterhin dran.',
  empty_answer: 'Schreibe zuerst etwas.',
  still_grading: 'Wird noch geprüft. Es wurde noch nichts bewertet.',
  try_grading_again: 'Erneut prüfen',
  retrying: 'Läuft noch — dieselbe Anfrage wird wiederholt.',
  reconciled: 'Diese Szene hat sich geändert. Sie wurde für dich aktualisiert.',
  transport_error: 'Das kam nicht beim Server an. Deine Antwort blieb erhalten.',
  retry: 'Erneut versuchen',
  offline_cached: 'Du bist offline. Das ist deine gespeicherte Kopie — nichts darin wurde geprüft.',
  offline_empty: 'Du bist offline, und es ist noch nichts gespeichert.',
  pending_sync: 'Etwas hat den Server noch nicht erreicht. Es bleibt auf diesem Gerät.',
  syncing: 'Wird an den Server gesendet…',
  stale_from_earlier_day: 'Das wurde an einem früheren Tag gespeichert.',
  correct: 'Richtig',
  supported: 'Richtig, mit Hilfe',
  wrong: 'Noch nicht',
  correction: 'Eine Sache zum Korrigieren',
  reply_authored_note: 'Vorgeschriebene Antwort aus dem Skript',
  progress_label: 'Fortschritt in der heutigen Szene',
  time_left: 'übrig',
  time_unknown: 'Zeit nicht gemessen',
  finish_early: 'Hier aufhören',
  pause: 'Pause',
  paused_title: 'Pausiert',
  paused_body: 'Alles Erledigte ist gespeichert. Mach dort weiter, wo du aufgehört hast.',
  awaiting_finish_title: 'Alle Schritte sind erledigt',
  awaiting_finish_body:
    'Die heutige Szene ist noch nicht als beendet gespeichert. Beim Beenden wird erfasst, was du gemacht hast.',
  awaiting_finish_action: 'Heute abschließen',
  finished_title: 'Szene beendet',
  finished_partial_title: 'Vorzeitig beendet',
  finished_partial_body: 'Nur der erledigte Teil wurde erfasst.',
  practiced: 'Das hast du geübt',
  capability_shown: 'Das kannst du jetzt',
  capability_state_not_tried: 'noch nicht versucht',
  capability_state_with_support: 'mit Hilfe',
  capability_state_independent_once: 'einmal selbständig',
  capability_state_used_again_later: 'später erneut genutzt',
  capability_register: 'Die passende Anrede treffen',
  capability_state_not_evaluated: 'nicht bewertet',
  correction_register: 'Mit wem du sprichst',
  correction_self_repair: 'Die Form, nach der eben gefragt wurde',
  self_repair_hint: 'Sag es noch einmal mit der Form, die du meinst.',
  evidence_recognized: 'erkannt',
  evidence_produced_supported: 'mit Hilfe benutzt',
  evidence_produced_independent: 'selbständig benutzt',
  evidence_not_yet: 'noch nicht',
  evidence_unscored: 'nicht geprüft',
  next_focus: 'Noch einmal ansehen',
  duration_not_measured: 'Die Dauer wird noch nicht gemessen.',
  more_practice: 'Mehr üben',
  more_practice_note: 'Optional. Die heutige Szene wird dadurch nicht neu geöffnet.',
  practice_this: 'Das üben',
  done_today: 'Die heutige Szene ist erledigt.',
  done_review: 'Noch einmal ansehen',
  nothing_offered: 'Gerade ist keine Szene verfügbar.',
  listen_first_label: 'Zuerst hören',
  listen_first_hint: 'Rate, wie es ausgeht, hör ohne Text zu, prüfe dann nach. Schwerer — und genau der Teil, der Hörverstehen übt.',
  listen_first_on: 'Zuerst hören',
  listen_first_off: 'Lieber lesen',
  radio_stage_predire: 'Raten',
  radio_stage_ecouter: 'Hören',
  radio_stage_verifier: 'Prüfen',
  radio_stage_retenir: 'Merken',
  radio_predire_native: 'Du hörst die Szene zuerst ohne Text. Der Text erscheint danach, Zeile für Zeile.',
  radio_predire_body: 'Bevor du hörst: Wie geht das aus? Falsch raten kostet nichts — das Raten ist es, was das Hören wirken lässt.',
  radio_guess_label: 'Deine Vermutung',
  radio_guess_selected: 'gewählt',
  radio_listen_action: 'Hören',
  radio_ecouter_body: 'Der Text bleibt verdeckt. Jede Zeile kannst du so oft abspielen, wie du willst.',
  radio_words_hidden: 'Text verdeckt',
  radio_preparing: 'Audio wird vorbereitet',
  radio_play: 'Folge abspielen',
  radio_replay: 'Nochmal abspielen',
  radio_stop: 'Stopp',
  radio_playing: 'Läuft',
  radio_verify_action: 'Vermutung prüfen',
  radio_verifier_body: 'Tippe auf eine Zeile, um zu sehen, was gesagt wurde.',
  radio_reveal: 'Diese Zeile zeigen',
  radio_reveal_all: 'Alle Zeilen zeigen',
  radio_guess_confirmed: 'Deine Vermutung hat gestimmt.',
  radio_guess_other: 'Es kam anders.',
  radio_guess_unresolved: 'Die Szene entscheidet es nicht — also ist keine der beiden Vermutungen falsch.',
  radio_evidence_label: 'Woran man es sieht',
  radio_retenir_body: 'Eine Sache, auf die du morgen hören kannst:',
  radio_retain_none: 'In dieser Folge gibt es nichts hervorzuheben.',
  radio_truncated: 'Lange Folge: nur der erste Teil wurde aufgenommen.',
  radio_audio_disabled: 'Audio ist für dieses Konto nicht eingeschaltet. Die Szene steht zum Lesen bereit.',
  radio_audio_failed: 'Das Audio konnte nicht vorbereitet werden. Die Szene steht zum Lesen bereit, nichts ist verloren.',
  radio_audio_offline: 'Ohne Verbindung gibt es kein Audio. Lies die Szene oder versuche es später.',
  radio_audio_unsupported: 'Dieses Gerät spielt kein Audio ab. Die Szene steht zum Lesen bereit.',
  radio_audio_empty: 'In dieser Szene gibt es nichts vorzulesen. Lies sie stattdessen.',
  radio_read_instead: 'Szene lesen',
  word_bank_spare_chips: 'Nicht jedes Wort gehört in die Antwort.',
  transform_source_label: 'Der Satz, den du umschreibst',
  classify_label: 'Wähle eins',
  listen_first_day: 'Erst hören — den Text gibt es danach.',
  chapter_recap_label: 'Wo das Kapitel endet',
  register_label: 'Wie du sie angesprochen hast',
  letter_from: 'Brief von {name}',
  letter_reply_label: 'Deine Antwort',
};

const FR: CopyTable = {
  today_eyebrow: 'Aujourd’hui',
  start: 'Commencer',
  resume: 'Reprendre',
  preparing_title: 'Préparation en cours',
  preparing_body: 'Votre scène se prépare. Cela prend généralement un instant.',
  preparing_retry: 'Vérifier à nouveau',
  unavailable_title: 'La scène du jour n’a pas pu être préparée',
  unavailable_body: 'Rien n’est perdu. Réessayez, ou continuez avec le reste de la journée.',
  unavailable_retry: 'Réessayer',
  legacy_resume_title: 'Séance précédente non terminée',
  legacy_resume_body: 'Une séance plus ancienne est encore ouverte. Elle reste séparée.',
  legacy_resume_action: 'Ouvrir cette séance',
  objective: 'Ce que vous devez faire',
  scene_continue: 'Continuer',
  answer_label: 'Votre réponse',
  answer_placeholder: 'Écrivez votre réponse en français',
  send: 'Envoyer',
  sending: 'Envoi…',
  check: 'Vérifier',
  continue: 'Continuer',
  help: 'Aide',
  help_hint: 'Indice',
  help_translation: 'Traduction',
  help_solution: 'Montrer la réponse',
  help_suggested_response: 'Proposer une réponse',
  help_shown: 'Aide affichée',
  assistance_used: 'Aide déjà utilisée',
  record: 'Enregistrer',
  stop_recording: 'Arrêter',
  transcribing: 'Transcription…',
  voice_failed: 'Cet enregistrement n’a pas pu être transcrit. C’est toujours votre tour.',
  voice_retry: 'Réenregistrer',
  use_text: 'Écrire plutôt',
  use_voice: 'Parler plutôt',
  speak: 'Parler',
  voice_hint: 'Dites votre réponse à voix haute. Nous la transcrivons — rien ici ne juge votre prononciation.',
  voice_transcript_label: 'Ce que nous avons entendu',
  voice_transcript_hint: 'Corrigez ce qui a été mal compris, puis envoyez.',
  voice_permission: 'Le micro n’est pas autorisé. Vous pouvez répondre par écrit ; pour parler, autorisez le micro dans les réglages de l’appareil.',
  voice_unsupported: 'Cet appareil ne peut pas enregistrer ici. Répondez par écrit.',
  voice_offline: 'Sans connexion, pas de transcription. Répondez par écrit, ou réessayez plus tard.',
  voice_empty: 'Rien n’a été enregistré. C’est toujours votre tour.',
  empty_answer: 'Écrivez d’abord quelque chose.',
  still_grading: 'Toujours en cours de vérification. Rien n’a encore été évalué.',
  try_grading_again: 'Vérifier à nouveau',
  retrying: 'Toujours en cours — la même requête est relancée.',
  reconciled: 'Cette scène a changé. Elle a été actualisée pour vous.',
  transport_error: 'Le serveur n’a pas reçu cela. Votre réponse est conservée.',
  retry: 'Réessayer',
  offline_cached: 'Vous êtes hors ligne. Ceci est votre copie enregistrée — rien n’y a été corrigé.',
  offline_empty: 'Vous êtes hors ligne, et rien n’est encore enregistré.',
  pending_sync: 'Quelque chose n’est pas encore arrivé au serveur. C’est gardé sur cet appareil.',
  syncing: 'Envoi au serveur…',
  stale_from_earlier_day: 'Ceci a été enregistré un jour précédent.',
  correct: 'Correct',
  supported: 'Correct, avec aide',
  wrong: 'Pas encore',
  correction: 'Une chose à corriger',
  reply_authored_note: 'Réponse écrite, tirée du scénario',
  progress_label: 'Progression dans la scène du jour',
  time_left: 'restant',
  time_unknown: 'Durée non mesurée',
  finish_early: 'Arrêter ici',
  pause: 'Pause',
  paused_title: 'En pause',
  paused_body: 'Tout ce qui est terminé est enregistré. Reprenez où vous en étiez.',
  awaiting_finish_title: 'Toutes les étapes sont faites',
  awaiting_finish_body:
    'La scène du jour n’est pas encore enregistrée comme terminée. La terminer enregistre ce que vous avez fait.',
  awaiting_finish_action: 'Terminer la journée',
  finished_title: 'Scène terminée',
  finished_partial_title: 'Arrêtée en cours',
  finished_partial_body: 'Seule la partie terminée a été enregistrée.',
  practiced: 'Ce que vous avez travaillé',
  capability_shown: 'Ce que vous savez faire',
  capability_state_not_tried: 'pas encore essayé',
  capability_state_with_support: 'avec aide',
  capability_state_independent_once: 'seul, une fois',
  capability_state_used_again_later: 'réutilisé plus tard',
  capability_register: 'S’adresser comme il faut',
  capability_state_not_evaluated: 'non évalué',
  correction_register: 'À qui vous parlez',
  correction_self_repair: 'La forme qu’on venait de vous demander',
  self_repair_hint: 'Redites-le avec la forme que vous visez.',
  evidence_recognized: 'reconnu',
  evidence_produced_supported: 'utilisé avec aide',
  evidence_produced_independent: 'utilisé seul',
  evidence_not_yet: 'pas encore',
  evidence_unscored: 'non évalué',
  next_focus: 'À revoir',
  duration_not_measured: 'La durée n’est pas encore mesurée.',
  more_practice: 'Plus d’exercices',
  more_practice_note: 'Facultatif. Cela ne rouvre pas la scène du jour.',
  practice_this: 'Retravailler',
  done_today: 'La scène du jour est terminée.',
  done_review: 'Revoir',
  nothing_offered: 'Aucune scène n’est disponible pour le moment.',
  listen_first_label: 'Écouter d’abord',
  listen_first_hint: 'Devinez ce qui arrive, écoutez sans le texte, puis vérifiez. Plus difficile — et c’est cette partie-là qui travaille l’écoute.',
  listen_first_on: 'Écouter d’abord',
  listen_first_off: 'Lire plutôt',
  radio_stage_predire: 'Prédire',
  radio_stage_ecouter: 'Écouter',
  radio_stage_verifier: 'Vérifier',
  radio_stage_retenir: 'Retenir',
  radio_predire_native: 'Vous écoutez la scène sans le texte. Le texte vient après, réplique par réplique.',
  radio_predire_body: 'Avant d’écouter : à votre avis, comment cela se termine ? Se tromper ne coûte rien — c’est le fait de prédire qui fait travailler l’écoute.',
  radio_guess_label: 'Votre prédiction',
  radio_guess_selected: 'choisi',
  radio_listen_action: 'Écouter',
  radio_ecouter_body: 'Le texte reste caché. Vous pouvez réécouter chaque réplique autant de fois que vous voulez.',
  radio_words_hidden: 'Texte caché',
  radio_preparing: 'Préparation de l’audio',
  radio_play: 'Écouter l’épisode',
  radio_replay: 'Réécouter',
  radio_stop: 'Arrêter',
  radio_playing: 'Lecture en cours',
  radio_verify_action: 'Vérifier ma prédiction',
  radio_verifier_body: 'Touchez une réplique pour voir ce qui a été dit.',
  radio_reveal: 'Afficher cette réplique',
  radio_reveal_all: 'Afficher toutes les répliques',
  radio_guess_confirmed: 'Votre prédiction se vérifie.',
  radio_guess_other: 'Cela s’est passé autrement.',
  radio_guess_unresolved: 'La scène ne tranche pas : aucune des deux prédictions n’est fausse.',
  radio_evidence_label: 'Ce qui le montre',
  radio_retenir_body: 'Une chose à écouter demain :',
  radio_retain_none: 'Rien à retenir en particulier dans cet épisode.',
  radio_truncated: 'Épisode long : seule la première partie a été enregistrée.',
  radio_audio_disabled: 'L’audio n’est pas activé sur ce compte. La scène est là, à lire.',
  radio_audio_failed: 'L’audio n’a pas pu être préparé. La scène est là, à lire : rien n’est perdu.',
  radio_audio_offline: 'Sans connexion, pas d’audio. Lisez la scène, ou réessayez plus tard.',
  radio_audio_unsupported: 'Cet appareil ne lit pas l’audio. La scène est là, à lire.',
  radio_audio_empty: 'Cette scène n’a rien à dire à voix haute. Lisez-la.',
  radio_read_instead: 'Lire la scène',
  word_bank_spare_chips: 'Tous les mots ne servent pas.',
  transform_source_label: 'La phrase à réécrire',
  classify_label: 'Choisissez',
  listen_first_day: 'On écoute d’abord — le texte vient après.',
  chapter_recap_label: 'Où en est le chapitre',
  register_label: 'Comment vous vous êtes adressé à elle ou lui',
  letter_from: 'Lettre de {name}',
  letter_reply_label: 'Votre réponse',
};

const TABLES: Record<ControlLanguage, CopyTable> = { en: EN, de: DE, fr: FR };

/**
 * WP-43 — one chrome language per screen (WP-39 D-3).
 *
 * The app's chrome is French on every screen; the learner's language is for
 * what is *said to* them about the scene — instructions, hints, explanations,
 * verdicts. These keys are chrome: labels, buttons and stage names that sit
 * beside French rows on the same screen. They read French for every control
 * language; everything else in the table keeps the learner's language.
 */
export const CHROME_KEYS: readonly JourneyCopyKey[] = [
  'today_eyebrow',
  'start',
  'resume',
  'continue',
  'scene_continue',
  'done_review',
  // The four help chips are buttons beside a French answer box; the help they
  // open still speaks the learner's language.
  'help_hint',
  'help_translation',
  'help_solution',
  'help_suggested_response',
  'send',
  'sending',
  'check',
  'help',
  'retry',
  'finish_early',
  'pause',
  'time_left',
  'progress_label',
  'awaiting_finish_action',
  'more_practice',
  'practice_this',
  'speak',
  'use_text',
  'use_voice',
  'record',
  'stop_recording',
  'answer_label',
  'objective',
  'preparing_retry',
  'unavailable_retry',
  'try_grading_again',
  'legacy_resume_action',
  'listen_first_label',
  'listen_first_on',
  'listen_first_off',
  'radio_stage_predire',
  'radio_stage_ecouter',
  'radio_stage_verifier',
  'radio_stage_retenir',
  'radio_guess_label',
  'radio_listen_action',
  'radio_play',
  'radio_replay',
  'radio_stop',
  'radio_verify_action',
  'radio_reveal',
  'radio_reveal_all',
  'radio_read_instead',
  // WP-66. These are stage labels and captions beside French rows, so they
  // read French on every control language — the *content* they label (the
  // instruction, the recap, the register reason) keeps the learner's language.
  'transform_source_label',
  'classify_label',
  'chapter_recap_label',
  'register_label',
  'letter_reply_label',
];

const CHROME_FR: Partial<CopyTable> = Object.fromEntries(
  CHROME_KEYS.map((key) => [key, FR[key]]),
) as Partial<CopyTable>;

/**
 * WP-69 (L6/L7) — status cards speak one language.
 *
 * «Heute wird vorbereitet» above a «Vérifier à nouveau» button was two
 * languages in one card. Preparing / unavailable / load-failed cards carry no
 * French content, so the whole card — eyebrow, title, body and its button —
 * reads in the learner's language (WP-82: status in the learner's language up
 * to A2). Scene cards keep the French chrome of {@link journeyCopy}.
 */
export function journeyStatusCopy(language: ControlLanguage | null | undefined): CopyTable {
  return TABLES[(language ?? 'en') as ControlLanguage] ?? EN;
}

export function journeyCopy(language: ControlLanguage | null | undefined): CopyTable {
  const table = TABLES[(language ?? 'en') as ControlLanguage] ?? EN;
  return { ...table, ...CHROME_FR };
}

export type JourneyCopy = CopyTable;
