/**
 * WP-82 — «Répétition» follows the one language rule.
 *
 * The page's own words — headings, instructions, the cap sentence, the three
 * debrief answers, buttons, pending labels, failures — are chrome: the
 * learner's language up to A2, French from B1 (`chromeLanguage`,
 * `lib/language-rule.ts`). The scene, the counterpart's lines, the brief's
 * French goal and the learner's own sentences are content and stay French.
 * Place names (Répétition, L’Atelier) are French in every column.
 *
 * Every table has the same keys and the same `{placeholders}` (the language
 * test proves it); `fill` fills them.
 */

import { normalizeControlLanguage } from '@/lib/atelier-v2-copy';
import type { ControlLanguage } from '@/types/daily-journey';

export type RehearsalCopy = {
  locale: string;
  // rehearsal-state
  cap_off: string;
  cap_spent: string;
  cap_one: string;
  cap_many: string;
  next_slot: string;
  event_date: string;
  debrief_done: string;
  debrief_done_hint: string;
  debrief_partly: string;
  debrief_partly_hint: string;
  debrief_not_yet: string;
  debrief_not_yet_hint: string;
  result_none: string;
  result_met: string;
  result_partial_one: string;
  result_partial_many: string;
  result_not_yet: string;
  // the screen
  eyebrow: string;
  you: string;
  with: string;
  counterpart_fallback: string;
  register_line: string;
  back_to_atelier: string;
  unavailable_title: string;
  disabled_title: string;
  disabled_body: string;
  preparing: string;
  prepare: string;
  later: string;
  declare_title: string;
  declare_body: string;
  declare_label: string;
  declare_placeholder: string;
  previous: string;
  retrying: string;
  retry: string;
  abandon: string;
  not_prepared_title: string;
  not_prepared_body: string;
  kept: string;
  sending: string;
  reply: string;
  stop: string;
  live_eyebrow: string;
  place_fallback: string;
  progress_label: string;
  turns_one: string;
  turns_many: string;
  answer_label: string;
  answer_placeholder: string;
  phrases_title: string;
  reveal_phrases: string;
  waiting_eyebrow: string;
  waiting_title: string;
  waiting_note_dated: string;
  waiting_note: string;
  saving: string;
  save_debrief: string;
  not_now: string;
  debrief_eyebrow: string;
  debrief_title: string;
  debrief_group: string;
  free_line_label: string;
  free_line_note: string;
  debriefed_eyebrow: string;
  done_title: string;
  noted_title: string;
  uncorrected: string;
  // the page
  load_failed: string;
  generic_failure: string;
};

const FR: RehearsalCopy = {
  locale: 'fr-FR',
  cap_off: 'Les répétitions sont désactivées.',
  cap_spent: 'Vous avez utilisé vos répétitions de la semaine.',
  cap_one: 'Il vous reste une répétition cette semaine.',
  cap_many: 'Il vous reste {n} répétitions cette semaine.',
  next_slot: 'Prochaine répétition possible le {date}.',
  event_date: 'C’est {date}.',
  debrief_done: 'Je l’ai fait',
  debrief_done_hint: 'La conversation a eu lieu et vous avez obtenu ce que vous vouliez.',
  debrief_partly: 'En partie',
  debrief_partly_hint: 'Vous avez parlé, mais tout n’a pas abouti.',
  debrief_not_yet: 'Pas encore',
  debrief_not_yet_hint: 'Ce n’est pas arrivé. Ce n’est pas un échec : c’est une information.',
  result_none: 'Répétition terminée.',
  result_met: 'Vous avez dit tout ce qu’il fallait dire.',
  result_partial_one: 'Vous avez couvert {n} point sur {total}.',
  result_partial_many: 'Vous avez couvert {n} points sur {total}.',
  result_not_yet: 'L’essentiel n’est pas encore passé. La vraie conversation reste à faire.',
  eyebrow: 'L’Atelier · Répétition',
  you: 'Vous',
  with: 'Avec {who}',
  counterpart_fallback: 'votre interlocuteur',
  register_line: 'on dit « {register} »',
  back_to_atelier: 'Revenir à l’Atelier',
  unavailable_title: 'Page indisponible',
  disabled_title: 'Répétitions désactivées',
  disabled_body:
    'Les répétitions ne sont pas ouvertes en ce moment. Rien n’est perdu : vos séances continuent normalement.',
  preparing: 'Préparation…',
  prepare: 'Préparer la répétition',
  later: 'Plus tard',
  declare_title: 'Répétez une vraie situation',
  declare_body:
    'Dites ce qui vous attend, dans vos mots — en français ou dans votre langue. Nous en faisons une scène à répéter une fois, puis nous vous demanderons comment ça s’est passé pour de vrai.',
  declare_label: 'Ce qui vous attend',
  declare_placeholder: 'Appeler le propriétaire pour le chauffage, mardi…',
  previous: 'Dernière répétition : {goal}.',
  retrying: 'Nouvelle tentative…',
  retry: 'Réessayer',
  abandon: 'Abandonner cette répétition',
  not_prepared_title: 'Répétition non préparée',
  not_prepared_body:
    'La préparation n’a pas répondu, donc il n’y a pas de scène. Nous préférons vous le dire plutôt que d’inventer une conversation autour de votre situation.',
  kept: 'Ce que vous avez écrit est conservé :',
  sending: 'Envoi…',
  reply: 'Répondre',
  stop: 'Arrêter la répétition',
  live_eyebrow: 'Répétition · {place}',
  place_fallback: 'votre situation',
  progress_label: 'Progression de la répétition',
  turns_one: 'Encore {n} tour',
  turns_many: 'Encore {n} tours',
  answer_label: 'Votre réponse, en français',
  answer_placeholder: 'Écrivez ici…',
  phrases_title: 'Phrases utiles',
  reveal_phrases: 'Voir des phrases utiles (c’est noté comme une aide)',
  waiting_eyebrow: 'Répétition · terminée',
  waiting_title: 'À vous, pour de vrai',
  waiting_note_dated:
    'Nous vous demanderons comment ça s’est passé le jour venu. C’est cette réponse-là qui compte, pas la note de la répétition.',
  waiting_note:
    'Nous vous demanderons comment ça s’est passé quand ce sera fait. C’est cette réponse-là qui compte, pas la note de la répétition.',
  saving: 'Enregistrement…',
  save_debrief: 'Enregistrer le bilan',
  not_now: 'Pas maintenant',
  debrief_eyebrow: 'Répétition · bilan',
  debrief_title: 'Comment ça s’est passé ?',
  debrief_group: 'Comment ça s’est passé',
  free_line_label: 'Une phrase en français sur ce qui s’est passé',
  free_line_note: 'Cette phrase-là sera corrigée. Le reste ne l’est pas.',
  debriefed_eyebrow: 'Répétition · bilan enregistré',
  done_title: 'Vous l’avez fait',
  noted_title: 'C’est noté',
  uncorrected: 'Cette phrase n’a pas pu être corrigée. Elle n’est pas jugée correcte pour autant.',
  load_failed: 'La page n’a pas pu être ouverte. Réessayez dans un instant.',
  generic_failure: 'Cette action n’a pas abouti. Réessayez dans un instant.',
};

const EN: RehearsalCopy = {
  locale: 'en-GB',
  cap_off: 'Rehearsals are turned off.',
  cap_spent: 'You’ve used this week’s rehearsals.',
  cap_one: 'You have one rehearsal left this week.',
  cap_many: 'You have {n} rehearsals left this week.',
  next_slot: 'Next rehearsal possible on {date}.',
  event_date: 'It’s on {date}.',
  debrief_done: 'I did it',
  debrief_done_hint: 'The conversation happened and you got what you wanted.',
  debrief_partly: 'Partly',
  debrief_partly_hint: 'You spoke, but not everything worked out.',
  debrief_not_yet: 'Not yet',
  debrief_not_yet_hint: 'It hasn’t happened. That’s not a failure: it’s information.',
  result_none: 'Rehearsal finished.',
  result_met: 'You said everything you needed to say.',
  result_partial_one: 'You covered {n} point of {total}.',
  result_partial_many: 'You covered {n} points of {total}.',
  result_not_yet: 'The key points didn’t come across yet. The real conversation is still ahead.',
  eyebrow: 'L’Atelier · Répétition',
  you: 'You',
  with: 'With {who}',
  counterpart_fallback: 'the other person',
  register_line: 'say “{register}”',
  back_to_atelier: 'Back to L’Atelier',
  unavailable_title: 'Page unavailable',
  disabled_title: 'Rehearsals turned off',
  disabled_body: 'Rehearsals aren’t open right now. Nothing is lost: your sessions carry on as usual.',
  preparing: 'Preparing…',
  prepare: 'Prepare the rehearsal',
  later: 'Later',
  declare_title: 'Rehearse a real situation',
  declare_body:
    'Tell us what’s coming up, in your own words — in French or in your language. We turn it into a scene to rehearse once, then ask you how it went for real.',
  declare_label: 'What’s coming up',
  declare_placeholder: 'Call the landlord about the heating, Tuesday…',
  previous: 'Last rehearsal: {goal}.',
  retrying: 'Trying again…',
  retry: 'Try again',
  abandon: 'Drop this rehearsal',
  not_prepared_title: 'Rehearsal not prepared',
  not_prepared_body:
    'The preparation didn’t respond, so there is no scene. We’d rather tell you than invent a conversation around your situation.',
  kept: 'What you wrote is kept:',
  sending: 'Sending…',
  reply: 'Reply',
  stop: 'Stop the rehearsal',
  live_eyebrow: 'Répétition · {place}',
  place_fallback: 'your situation',
  progress_label: 'Rehearsal progress',
  turns_one: '{n} turn left',
  turns_many: '{n} turns left',
  answer_label: 'Your answer, in French',
  answer_placeholder: 'Write here…',
  phrases_title: 'Useful phrases',
  reveal_phrases: 'See useful phrases (this counts as help)',
  waiting_eyebrow: 'Répétition · finished',
  waiting_title: 'Your turn, for real',
  waiting_note_dated:
    'We’ll ask you how it went on the day. That answer is what counts, not the rehearsal score.',
  waiting_note:
    'We’ll ask you how it went once it’s done. That answer is what counts, not the rehearsal score.',
  saving: 'Saving…',
  save_debrief: 'Save how it went',
  not_now: 'Not now',
  debrief_eyebrow: 'Répétition · debrief',
  debrief_title: 'How did it go?',
  debrief_group: 'How it went',
  free_line_label: 'One sentence in French about what happened',
  free_line_note: 'This sentence will be corrected. The rest won’t be.',
  debriefed_eyebrow: 'Répétition · debrief saved',
  done_title: 'You did it',
  noted_title: 'Noted',
  uncorrected: 'This sentence couldn’t be corrected. That doesn’t mean it counts as correct.',
  load_failed: 'The page could not be opened. Please try again in a moment.',
  generic_failure: 'That didn’t work. Please try again in a moment.',
};

const DE: RehearsalCopy = {
  locale: 'de-DE',
  cap_off: 'Proben sind deaktiviert.',
  cap_spent: 'Sie haben Ihre Proben für diese Woche genutzt.',
  cap_one: 'Sie haben diese Woche noch eine Probe.',
  cap_many: 'Sie haben diese Woche noch {n} Proben.',
  next_slot: 'Nächste Probe möglich am {date}.',
  event_date: 'Es ist am {date}.',
  debrief_done: 'Ich habe es geschafft',
  debrief_done_hint: 'Das Gespräch hat stattgefunden und Sie haben erreicht, was Sie wollten.',
  debrief_partly: 'Teilweise',
  debrief_partly_hint: 'Sie haben gesprochen, aber nicht alles hat geklappt.',
  debrief_not_yet: 'Noch nicht',
  debrief_not_yet_hint: 'Es ist noch nicht passiert. Das ist kein Misserfolg, sondern eine Information.',
  result_none: 'Probe beendet.',
  result_met: 'Sie haben alles gesagt, was zu sagen war.',
  result_partial_one: 'Sie haben {n} von {total} Punkten abgedeckt.',
  result_partial_many: 'Sie haben {n} von {total} Punkten abgedeckt.',
  result_not_yet: 'Das Wesentliche ist noch nicht angekommen. Das echte Gespräch steht noch bevor.',
  eyebrow: 'L’Atelier · Répétition',
  you: 'Sie',
  with: 'Mit {who}',
  counterpart_fallback: 'Ihrem Gegenüber',
  register_line: 'man sagt „{register}“',
  back_to_atelier: 'Zurück zum Atelier',
  unavailable_title: 'Seite nicht verfügbar',
  disabled_title: 'Proben deaktiviert',
  disabled_body: 'Proben sind gerade nicht verfügbar. Nichts geht verloren: Ihre Übungen laufen normal weiter.',
  preparing: 'Wird vorbereitet…',
  prepare: 'Probe vorbereiten',
  later: 'Später',
  declare_title: 'Proben Sie eine echte Situation',
  declare_body:
    'Beschreiben Sie, was Ihnen bevorsteht, in Ihren Worten — auf Französisch oder in Ihrer Sprache. Wir machen daraus eine Szene zum einmaligen Proben und fragen Sie danach, wie es wirklich gelaufen ist.',
  declare_label: 'Was Ihnen bevorsteht',
  declare_placeholder: 'Den Vermieter wegen der Heizung anrufen, Dienstag…',
  previous: 'Letzte Probe: {goal}.',
  retrying: 'Neuer Versuch…',
  retry: 'Erneut versuchen',
  abandon: 'Diese Probe abbrechen',
  not_prepared_title: 'Probe nicht vorbereitet',
  not_prepared_body:
    'Die Vorbereitung hat nicht geantwortet, daher gibt es keine Szene. Wir sagen Ihnen das lieber, als ein Gespräch über Ihre Situation zu erfinden.',
  kept: 'Was Sie geschrieben haben, bleibt erhalten:',
  sending: 'Wird gesendet…',
  reply: 'Antworten',
  stop: 'Probe beenden',
  live_eyebrow: 'Répétition · {place}',
  place_fallback: 'Ihre Situation',
  progress_label: 'Fortschritt der Probe',
  turns_one: 'Noch {n} Runde',
  turns_many: 'Noch {n} Runden',
  answer_label: 'Ihre Antwort, auf Französisch',
  answer_placeholder: 'Hier schreiben…',
  phrases_title: 'Nützliche Sätze',
  reveal_phrases: 'Nützliche Sätze ansehen (zählt als Hilfe)',
  waiting_eyebrow: 'Répétition · beendet',
  waiting_title: 'Jetzt sind Sie dran, ganz echt',
  waiting_note_dated:
    'Wir fragen Sie am Tag selbst, wie es gelaufen ist. Diese Antwort zählt, nicht die Bewertung der Probe.',
  waiting_note:
    'Wir fragen Sie, wie es gelaufen ist, sobald es erledigt ist. Diese Antwort zählt, nicht die Bewertung der Probe.',
  saving: 'Wird gespeichert…',
  save_debrief: 'Rückblick speichern',
  not_now: 'Nicht jetzt',
  debrief_eyebrow: 'Répétition · Rückblick',
  debrief_title: 'Wie ist es gelaufen?',
  debrief_group: 'Wie es gelaufen ist',
  free_line_label: 'Ein Satz auf Französisch darüber, was passiert ist',
  free_line_note: 'Dieser Satz wird korrigiert. Der Rest nicht.',
  debriefed_eyebrow: 'Répétition · Rückblick gespeichert',
  done_title: 'Sie haben es geschafft',
  noted_title: 'Notiert',
  uncorrected: 'Dieser Satz konnte nicht korrigiert werden. Das heißt nicht, dass er als richtig gilt.',
  load_failed: 'Die Seite konnte nicht geöffnet werden. Bitte versuchen Sie es gleich noch einmal.',
  generic_failure: 'Das hat nicht geklappt. Bitte versuchen Sie es gleich noch einmal.',
};

export const REHEARSAL_COPY: Record<ControlLanguage, RehearsalCopy> = { en: EN, de: DE, fr: FR };

/** The Répétition copy table for a chrome language (regional tags and nulls normalised). */
export function rehearsalCopy(language: unknown): RehearsalCopy {
  return REHEARSAL_COPY[normalizeControlLanguage(language)];
}

/** `{n}`-style placeholders filled in. */
export function fill(template: string, values: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (match, key: string) => (key in values ? String(values[key]) : match));
}
