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
  | 'nothing_offered';

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
  nothing_offered: 'No scene is available right now.',
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
  nothing_offered: 'Gerade ist keine Szene verfügbar.',
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
  nothing_offered: 'Aucune scène n’est disponible pour le moment.',
};

const TABLES: Record<ControlLanguage, CopyTable> = { en: EN, de: DE, fr: FR };

export function journeyCopy(language: ControlLanguage | null | undefined): CopyTable {
  return TABLES[(language ?? 'en') as ControlLanguage] ?? EN;
}

export type JourneyCopy = CopyTable;
