/**
 * The sign-in and password-reset screens, in the learner's language.
 *
 * 2026-09-24 — the one-language rule (lib/language-rule.ts). Before a session
 * exists there is no `native_language` to read, so these screens follow the
 * onboarding language (lib/onboarding-locale.ts: the stored choice, else the
 * browser's guess) exactly like sign-up does. A newcomer reads as a beginner,
 * so every word here is chrome in their language; only the brand, «L’Atelier»,
 * stays as it is.
 */

import type { OnboardingLanguage } from './onboarding-locale';

/**
 * The masthead line these screens share with the landing's nameplate. It is
 * the publication's name, not chrome, so it reads the same in every language.
 */
export const AUTH_EYEBROW = 'L’Atelier · Quotidien de français';

export type SignInErrorKey = 'email_required' | 'email_invalid' | 'password_required' | 'password_short';

export type SignInCopy = {
  screen: string;
  email: string;
  email_placeholder: string;
  password: string;
  password_placeholder: string;
  forgot: string;
  submit: string;
  pending: string;
  new_here: string;
  create_account: string;
  wrong_credentials: string;
  failed: string;
  errors: Record<SignInErrorKey, string>;
};

export type ResetCopy = {
  screen: string;
  tab_title: string;
  support_subject: string;
  email_title: string;
  email_lead: string;
  email_label: string;
  send: string;
  sending: string;
  code_title: string;
  /** `{email}` is the address the learner typed. */
  code_lead: string;
  code_label: string;
  continue: string;
  resend: string;
  password_title: string;
  new_password: string;
  new_password_placeholder: string;
  confirm: string;
  save: string;
  saving: string;
  done_title: string;
  done_lead: string;
  sign_in: string;
  /** `{code}` — development only. */
  dev_code: string;
  stuck: string;
  back_to_sign_in: string;
  errors: {
    email_required: string;
    send_failed: string;
    resent: string;
    code_digits: string;
    password_short: string;
    password_long: string;
    mismatch: string;
    code_wrong: string;
    link_expired: string;
    password_refused: string;
  };
};

export type AuthCopy = { signin: SignInCopy; reset: ResetCopy };

export const AUTH_COPY: Record<OnboardingLanguage, AuthCopy> = {
  en: {
    signin: {
      screen: 'Sign in',
      email: 'Email',
      email_placeholder: 'you@example.com',
      password: 'Password',
      password_placeholder: 'Your password',
      forgot: 'Forgot your password?',
      submit: 'Sign in',
      pending: 'Signing in…',
      new_here: 'New here?',
      create_account: 'Create an account',
      wrong_credentials: 'Wrong email or password. Check both and try again.',
      failed: 'Sign-in didn’t go through. Try again in a moment.',
      errors: {
        email_required: 'Enter your email.',
        email_invalid: 'This email looks wrong.',
        password_required: 'Enter your password.',
        password_short: 'At least 6 characters.',
      },
    },
    reset: {
      screen: 'Forgot password',
      tab_title: 'Password',
      support_subject: 'Atelier — password',
      email_title: 'Forgot your password',
      email_lead: 'We’ll send you a six-digit code.',
      email_label: 'Email',
      send: 'Get the code',
      sending: 'Sending…',
      code_title: 'Enter the code',
      code_lead: 'If {email} has an account, the code is on its way. Valid for 15 minutes.',
      code_label: 'Code',
      continue: 'Continue',
      resend: 'Send the code again',
      password_title: 'New password',
      new_password: 'New password',
      new_password_placeholder: 'At least 8 characters',
      confirm: 'Confirm',
      save: 'Save',
      saving: 'Saving…',
      done_title: 'Done',
      done_lead: 'Sign in with your new password.',
      sign_in: 'Sign in',
      dev_code: 'Test code: {code}',
      stuck: 'Stuck?',
      back_to_sign_in: 'Back to sign in',
      errors: {
        email_required: 'Enter the email of your account.',
        send_failed: 'Sending didn’t go through. Try again.',
        resent: 'Request sent. Check your spam folder too.',
        code_digits: 'The code has six digits.',
        password_short: 'At least 8 characters.',
        password_long: 'Too long: accents and emoji count double.',
        mismatch: 'The two don’t match.',
        code_wrong: 'Wrong or expired code.',
        link_expired: 'Link expired. Ask for a code.',
        password_refused: 'Password refused: at least 8 characters, not too long.',
      },
    },
  },
  de: {
    signin: {
      screen: 'Anmelden',
      email: 'E-Mail',
      email_placeholder: 'sie@beispiel.de',
      password: 'Passwort',
      password_placeholder: 'Ihr Passwort',
      forgot: 'Passwort vergessen?',
      submit: 'Anmelden',
      pending: 'Anmeldung…',
      new_here: 'Neu hier?',
      create_account: 'Konto erstellen',
      wrong_credentials: 'E-Mail oder Passwort falsch. Prüfen Sie beides.',
      failed: 'Die Anmeldung hat nicht geklappt. Versuchen Sie es gleich noch einmal.',
      errors: {
        email_required: 'Geben Sie Ihre E-Mail ein.',
        email_invalid: 'Diese E-Mail scheint falsch.',
        password_required: 'Geben Sie Ihr Passwort ein.',
        password_short: 'Mindestens 6 Zeichen.',
      },
    },
    reset: {
      screen: 'Passwort vergessen',
      tab_title: 'Passwort',
      support_subject: 'Atelier — Passwort',
      email_title: 'Passwort vergessen',
      email_lead: 'Wir schicken Ihnen einen sechsstelligen Code.',
      email_label: 'E-Mail',
      send: 'Code anfordern',
      sending: 'Wird gesendet…',
      code_title: 'Code eingeben',
      code_lead: 'Wenn {email} ein Konto hat, kommt der Code dort an. 15 Minuten gültig.',
      code_label: 'Code',
      continue: 'Weiter',
      resend: 'Code erneut senden',
      password_title: 'Neues Passwort',
      new_password: 'Neues Passwort',
      new_password_placeholder: 'Mindestens 8 Zeichen',
      confirm: 'Bestätigen',
      save: 'Speichern',
      saving: 'Wird gespeichert…',
      done_title: 'Erledigt',
      done_lead: 'Melden Sie sich mit dem neuen Passwort an.',
      sign_in: 'Anmelden',
      dev_code: 'Testcode: {code}',
      stuck: 'Kommen Sie nicht weiter?',
      back_to_sign_in: 'Zurück zur Anmeldung',
      errors: {
        email_required: 'Geben Sie die E-Mail Ihres Kontos ein.',
        send_failed: 'Das Senden hat nicht geklappt. Versuchen Sie es erneut.',
        resent: 'Anfrage gesendet. Sehen Sie auch im Spam-Ordner nach.',
        code_digits: 'Der Code hat sechs Ziffern.',
        password_short: 'Mindestens 8 Zeichen.',
        password_long: 'Zu lang: Akzente und Emoji zählen doppelt.',
        mismatch: 'Die beiden stimmen nicht überein.',
        code_wrong: 'Code falsch oder abgelaufen.',
        link_expired: 'Link abgelaufen. Fordern Sie einen Code an.',
        password_refused: 'Passwort abgelehnt: mindestens 8 Zeichen, nicht zu lang.',
      },
    },
  },
  fr: {
    signin: {
      screen: 'Se connecter',
      email: 'Adresse e-mail',
      email_placeholder: 'vous@exemple.fr',
      password: 'Mot de passe',
      password_placeholder: 'Votre mot de passe',
      forgot: 'Mot de passe oublié ?',
      submit: 'Se connecter',
      pending: 'Connexion…',
      new_here: 'Nouveau ici ?',
      create_account: 'Créer un compte',
      wrong_credentials: 'Identifiants incorrects. Vérifiez l’adresse et le mot de passe.',
      failed: 'La connexion n’a pas abouti. Réessayez dans un instant.',
      errors: {
        email_required: 'Indiquez votre adresse',
        email_invalid: 'Adresse e-mail invalide',
        password_required: 'Indiquez votre mot de passe',
        password_short: 'Au moins 6 caractères',
      },
    },
    reset: {
      screen: 'Mot de passe oublié',
      tab_title: 'Mot de passe',
      support_subject: 'Atelier — mot de passe',
      email_title: 'Mot de passe oublié',
      email_lead: 'Nous vous envoyons un code à six chiffres.',
      email_label: 'Adresse e-mail',
      send: 'Recevoir le code',
      sending: 'Envoi…',
      code_title: 'Saisissez le code',
      code_lead: 'Si {email} a un compte, le code y arrive. Valable 15 minutes.',
      code_label: 'Code',
      continue: 'Continuer',
      resend: 'Renvoyer le code',
      password_title: 'Nouveau mot de passe',
      new_password: 'Nouveau mot de passe',
      new_password_placeholder: 'Au moins 8 caractères',
      confirm: 'Confirmer',
      save: 'Enregistrer',
      saving: 'Enregistrement…',
      done_title: 'C’est fait',
      done_lead: 'Connectez-vous avec le nouveau mot de passe.',
      sign_in: 'Se connecter',
      dev_code: 'Code de test : {code}',
      stuck: 'Bloqué ?',
      back_to_sign_in: 'Retour à la connexion',
      errors: {
        email_required: 'Indiquez l’adresse de votre compte.',
        send_failed: 'L’envoi n’a pas abouti. Réessayez.',
        resent: 'Demande envoyée. Vérifiez aussi les indésirables.',
        code_digits: 'Le code a six chiffres.',
        password_short: 'Au moins 8 caractères.',
        password_long: 'Trop long : les accents et emoji comptent double.',
        mismatch: 'Les deux ne correspondent pas.',
        code_wrong: 'Code incorrect ou expiré.',
        link_expired: 'Lien expiré. Demandez un code.',
        password_refused: 'Mot de passe refusé : 8 caractères au moins, pas trop long.',
      },
    },
  },
};

export function authCopy(language: OnboardingLanguage): AuthCopy {
  return AUTH_COPY[language] ?? AUTH_COPY.en;
}

/** «{email}» → value. Unknown holes stay visible rather than vanishing. */
export function authFill(template: string, values: Record<string, string>): string {
  return template.replace(/\{(\w+)\}/g, (hole, key: string) => (key in values ? values[key] : hole));
}

/** A yup message is a key; the page shows it in the current language. */
export function signInErrorText(copy: SignInCopy, key: unknown): string | undefined {
  if (typeof key !== 'string' || !key) return undefined;
  return (copy.errors as Record<string, string>)[key] ?? key;
}
