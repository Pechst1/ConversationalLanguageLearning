/**
 * S4 stage 4 — «Aide», the Help place in Réglages.
 *
 * A short FAQ, the feedback sheet and the contact address. Help is
 * explanatory text, so like Réglages and the legal pages it is in the
 * learner's own language at every level (en, de, fr), addressing them with
 * tu / du. Every answer describes what the app does today; when a flow
 * changes, its answer changes in the same pull request.
 *
 * Kept dependency-free so the node tests can load it.
 */

export type HelpLanguage = 'en' | 'de' | 'fr';

export type HelpQuestion = { id: string; q: string; a: string };

export type HelpCopy = {
  page_title: string;
  eyebrow: string;
  headline: string;
  lead: string;
  back: string;
  faq_label: string;
  faq: HelpQuestion[];
  feedback_label: string;
  feedback_hint: string;
  feedback_action: string;
  contact_label: string;
  contact_hint: string;
};

/** The questions, in order. Each language answers every one. */
export const HELP_QUESTION_IDS = ['address', 'password', 'language', 'level', 'data', 'feedback'] as const;

const EN: HelpCopy = {
  page_title: 'Help · L’Atelier',
  eyebrow: 'Settings',
  headline: 'Help',
  lead: 'Short answers to the questions that come up most. If yours is not here, write to us.',
  back: 'Back to Settings',
  faq_label: 'Questions',
  faq: [
    {
      id: 'address',
      q: 'Why should I confirm my address?',
      a: 'You can play without it. But a new password and a new address both go by mail, so they need an address we know reaches you. The code is in the mail we sent at sign-up; Settings can send a new one.',
    },
    {
      id: 'password',
      q: 'I forgot my password.',
      a: 'On the sign-in page, choose «Forgot your password?». We mail you a code; enter it with your new password. If your address is not confirmed yet, the code we send confirms it at the same time.',
    },
    {
      id: 'language',
      q: 'Why is the app partly in French?',
      a: 'Up to A2, the app’s own words are in your language. From B1, they are in French too: you read them every day, so they become part of the practice. Help, Settings and the legal pages stay in your language.',
    },
    {
      id: 'level',
      q: 'My level feels wrong.',
      a: 'Your level follows what you do in the scenes. In Settings, «Your dossier» shows what the app believes about you and why, and lets you disagree with it in two questions.',
    },
    {
      id: 'data',
      q: 'How do I take my data with me, or delete my account?',
      a: 'At the end of Settings: export your archives as a file, or delete the account. Deleting removes it for good.',
    },
    {
      id: 'feedback',
      q: 'Something is broken.',
      a: 'Send it with the button below. It records the screen you were on, so a short note is enough. Tick «I’d like an answer» if you want us to write back.',
    },
  ],
  feedback_label: 'Report a problem',
  feedback_hint: 'A bug, a wrong text, a slow screen or an idea.',
  feedback_action: 'Write to us',
  contact_label: 'Contact',
  contact_hint: 'For anything else, and for questions about your data.',
};

const DE: HelpCopy = {
  page_title: 'Hilfe · L’Atelier',
  eyebrow: 'Einstellungen',
  headline: 'Hilfe',
  lead: 'Kurze Antworten auf die häufigsten Fragen. Wenn deine nicht dabei ist, schreib uns.',
  back: 'Zurück zu den Einstellungen',
  faq_label: 'Fragen',
  faq: [
    {
      id: 'address',
      q: 'Warum soll ich meine Adresse bestätigen?',
      a: 'Spielen kannst du auch ohne. Aber ein neues Passwort und eine neue Adresse kommen per Mail, dafür brauchen wir eine Adresse, die dich sicher erreicht. Der Code steht in der Mail von der Anmeldung; in den Einstellungen kannst du einen neuen anfordern.',
    },
    {
      id: 'password',
      q: 'Ich habe mein Passwort vergessen.',
      a: 'Wähle auf der Anmeldeseite «Passwort vergessen?». Wir schicken dir einen Code; gib ihn mit deinem neuen Passwort ein. Ist deine Adresse noch nicht bestätigt, bestätigt dieser Code sie gleich mit.',
    },
    {
      id: 'language',
      q: 'Warum ist die App teilweise auf Französisch?',
      a: 'Bis A2 sind die Wörter der App in deiner Sprache. Ab B1 sind sie auch auf Französisch: Du liest sie jeden Tag, so werden sie Teil der Übung. Hilfe, Einstellungen und die rechtlichen Seiten bleiben in deiner Sprache.',
    },
    {
      id: 'level',
      q: 'Mein Niveau stimmt nicht.',
      a: 'Dein Niveau folgt dem, was du in den Szenen tust. In den Einstellungen zeigt «Dein Dossier», was die App über dich annimmt und warum, und dort kannst du mit zwei Fragen widersprechen.',
    },
    {
      id: 'data',
      q: 'Wie nehme ich meine Daten mit oder lösche mein Konto?',
      a: 'Ganz unten in den Einstellungen: Exportiere deine Archive als Datei oder lösche das Konto. Gelöscht ist es endgültig.',
    },
    {
      id: 'feedback',
      q: 'Etwas funktioniert nicht.',
      a: 'Schick es mit dem Knopf unten. Er merkt sich die Seite, auf der du warst, eine kurze Notiz reicht also. Wähle «Ich möchte eine Antwort», wenn wir dir zurückschreiben sollen.',
    },
  ],
  feedback_label: 'Ein Problem melden',
  feedback_hint: 'Ein Fehler, ein falscher Text, eine langsame Seite oder eine Idee.',
  feedback_action: 'Schreib uns',
  contact_label: 'Kontakt',
  contact_hint: 'Für alles andere und für Fragen zu deinen Daten.',
};

const FR: HelpCopy = {
  page_title: 'Aide · L’Atelier',
  eyebrow: 'Réglages',
  headline: 'Aide',
  lead: 'Des réponses courtes aux questions les plus fréquentes. Si la tienne n’y est pas, écris-nous.',
  back: 'Retour aux réglages',
  faq_label: 'Questions',
  faq: [
    {
      id: 'address',
      q: 'Pourquoi confirmer mon adresse ?',
      a: 'Tu peux jouer sans. Mais un nouveau mot de passe et une nouvelle adresse passent par e-mail : il faut une adresse dont on sait qu’elle te joint. Le code est dans l’e-mail reçu à l’inscription ; les réglages peuvent t’en renvoyer un.',
    },
    {
      id: 'password',
      q: 'J’ai oublié mon mot de passe.',
      a: 'Sur la page de connexion, choisis « Mot de passe oublié ? ». On t’envoie un code ; saisis-le avec ton nouveau mot de passe. Si ton adresse n’est pas encore confirmée, ce code la confirme en même temps.',
    },
    {
      id: 'language',
      q: 'Pourquoi l’application est-elle en partie en français ?',
      a: 'Jusqu’à A2, les mots de l’application sont dans ta langue. À partir de B1, ils passent aussi en français : tu les lis chaque jour, ils font partie de l’entraînement. L’aide, les réglages et les pages juridiques restent dans ta langue.',
    },
    {
      id: 'level',
      q: 'Mon niveau ne me semble pas juste.',
      a: 'Ton niveau suit ce que tu fais dans les scènes. Dans les réglages, « Ton dossier » montre ce que l’application pense de toi et pourquoi, et te laisse le contester en deux questions.',
    },
    {
      id: 'data',
      q: 'Comment récupérer mes données ou supprimer mon compte ?',
      a: 'Tout en bas des réglages : exporte tes archives dans un fichier, ou supprime le compte. La suppression est définitive.',
    },
    {
      id: 'feedback',
      q: 'Quelque chose ne marche pas.',
      a: 'Envoie-le avec le bouton ci-dessous. Il note l’écran où tu étais, une courte note suffit donc. Choisis « Je veux une réponse » si tu veux qu’on t’écrive.',
    },
  ],
  feedback_label: 'Signaler un problème',
  feedback_hint: 'Un bogue, un texte faux, un écran lent ou une idée.',
  feedback_action: 'Écris-nous',
  contact_label: 'Contact',
  contact_hint: 'Pour tout le reste, et pour les questions sur tes données.',
};

export const HELP_COPY: Record<HelpLanguage, HelpCopy> = { en: EN, de: DE, fr: FR };

export function helpCopy(language: unknown): HelpCopy {
  const base = typeof language === 'string' ? language.trim().toLowerCase().replace('_', '-').split('-')[0] : '';
  return HELP_COPY[(base === 'de' || base === 'fr' ? base : 'en') as HelpLanguage];
}
