/**
 * WP-75 — sign-up on one screen.
 *
 * Email, password (shown or hidden, never typed twice), an optional first name,
 * one question — «Votre français ?» — and the interface language. Everything
 * the old step two asked (motivation, level, minutes, corrections, voice,
 * topics) gets a server-side default and lives in Réglages.
 *
 * After the account exists the learner is signed in and lands in today's
 * scene, `/atelier?start=today`, never on the placement: «Nouveau» skips it
 * entirely, and the others are offered it right after their first completed
 * ending (WP-126, `/placement/offer`).
 *
 * WP-126: five plain-language starting points, A1 → C1, each with its CEFR
 * label beside the plain words. The scale ends at C1 (never «C1+»). An older
 * client's three values (`new` / `some` / `comfortable`) mean what they meant.
 */

import type { OnboardingLanguage } from './onboarding-locale';

export type StartingPoint = 'new' | 'some' | 'comfortable' | 'confident' | 'advanced';

export const STARTING_POINTS: StartingPoint[] = ['new', 'some', 'comfortable', 'confident', 'advanced'];

/** The band each answer declares — shown as a quiet label, sent as `starting_point`. */
export const STARTING_POINT_CEFR: Record<StartingPoint, string> = {
  new: 'A1',
  some: 'A2',
  comfortable: 'B1',
  confident: 'B2',
  advanced: 'C1',
};

/** «Plain words · A2»: the CEFR label is optional context, never the question. */
export function startingPointLabel(copy: SignUpCopy, point: StartingPoint): string {
  return `${copy.levels[point]} · ${STARTING_POINT_CEFR[point]}`;
}

/** Where a learner lands after sign-up, unless a deep link brought them. */
export const AFTER_SIGNUP_DESTINATION = '/atelier?start=today';

/** The path the auth helpers treat as "no destination of their own". */
const DEFAULT_DESTINATION = '/atelier';

/**
 * A learner who arrived from a deep link keeps it; everyone else goes straight
 * to the day-1 scene. Takes the already-sanitised callback URL.
 */
export function afterSignUpDestination(sanitizedCallback: string | null | undefined): string {
  if (!sanitizedCallback || sanitizedCallback === DEFAULT_DESTINATION) return AFTER_SIGNUP_DESTINATION;
  if (sanitizedCallback.startsWith('/placement')) return AFTER_SIGNUP_DESTINATION;
  return sanitizedCallback;
}

export type SignUpForm = {
  email: string;
  password: string;
  firstName: string;
  startingPoint: StartingPoint | null;
  language: OnboardingLanguage;
};

export type RegisterPayload = {
  email: string;
  password: string;
  full_name?: string;
  native_language: OnboardingLanguage;
  starting_point: StartingPoint;
};

/** Exactly the fields the backend contract names; nothing optional is invented. */
export function buildRegisterPayload(form: SignUpForm): RegisterPayload {
  const payload: RegisterPayload = {
    email: form.email.trim().toLowerCase(),
    password: form.password,
    native_language: form.language,
    starting_point: form.startingPoint ?? 'new',
  };
  const name = form.firstName.trim();
  if (name) payload.full_name = name;
  return payload;
}

export type SignUpErrorKey =
  | 'email_required'
  | 'email_invalid'
  | 'password_required'
  | 'password_short'
  | 'password_long'
  | 'starting_point_required';

export type SignUpErrors = Partial<Record<'email' | 'password' | 'startingPoint', SignUpErrorKey>>;

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
/** bcrypt reads 72 bytes and the server refuses more (WP-71); accents count double. */
export const PASSWORD_MAX_BYTES = 72;
export const PASSWORD_MIN_LENGTH = 8;

export function passwordBytes(value: string): number {
  return new TextEncoder().encode(value).length;
}

export function validateSignUp(form: SignUpForm): SignUpErrors {
  const errors: SignUpErrors = {};
  const email = form.email.trim();
  if (!email) errors.email = 'email_required';
  else if (!EMAIL_PATTERN.test(email)) errors.email = 'email_invalid';

  if (!form.password) errors.password = 'password_required';
  else if (form.password.length < PASSWORD_MIN_LENGTH) errors.password = 'password_short';
  else if (passwordBytes(form.password) > PASSWORD_MAX_BYTES) errors.password = 'password_long';

  if (!form.startingPoint) errors.startingPoint = 'starting_point_required';
  return errors;
}

export type SignUpCopy = {
  title: string;
  email: string;
  password: string;
  password_hint: string;
  show: string;
  hide: string;
  first_name: string;
  optional: string;
  level_question: string;
  levels: Record<StartingPoint, string>;
  language: string;
  created_sign_in: string;
  failed: string;
  errors: Record<SignUpErrorKey, string>;
};

export const SIGNUP_COPY: Record<OnboardingLanguage, SignUpCopy> = {
  en: {
    title: 'Keep your story',
    email: 'Email',
    password: 'Password',
    password_hint: 'At least 8 characters',
    show: 'Show',
    hide: 'Hide',
    first_name: 'First name',
    optional: 'optional',
    level_question: 'Your French?',
    levels: {
      new: 'New to French',
      some: 'I know some basics',
      comfortable: 'I get by day to day',
      confident: 'I talk about most things with ease',
      advanced: 'I read and argue with nuance',
    },
    language: 'App language',
    created_sign_in: 'Account created. Sign in to open your first scene.',
    failed: 'Something went wrong. Please try again.',
    errors: {
      email_required: 'Enter your email.',
      email_invalid: 'This email looks wrong.',
      password_required: 'Choose a password.',
      password_short: 'At least 8 characters.',
      password_long: 'Too long: 72 bytes at most.',
      starting_point_required: 'Pick one.',
    },
  },
  de: {
    title: 'Behalten Sie Ihre Geschichte',
    email: 'E-Mail',
    password: 'Passwort',
    password_hint: 'Mindestens 8 Zeichen',
    show: 'Zeigen',
    hide: 'Verbergen',
    first_name: 'Vorname',
    optional: 'optional',
    level_question: 'Ihr Französisch?',
    levels: {
      new: 'Neu im Französischen',
      some: 'Ich habe Grundkenntnisse',
      comfortable: 'Ich komme im Alltag zurecht',
      confident: 'Ich spreche über fast alles mühelos',
      advanced: 'Ich lese und argumentiere differenziert',
    },
    language: 'App-Sprache',
    created_sign_in: 'Konto erstellt. Melden Sie sich an, um Ihre erste Szene zu öffnen.',
    failed: 'Etwas ist schiefgelaufen. Bitte versuchen Sie es erneut.',
    errors: {
      email_required: 'Geben Sie Ihre E-Mail ein.',
      email_invalid: 'Diese E-Mail scheint falsch.',
      password_required: 'Wählen Sie ein Passwort.',
      password_short: 'Mindestens 8 Zeichen.',
      password_long: 'Zu lang: höchstens 72 Bytes.',
      starting_point_required: 'Bitte wählen.',
    },
  },
  fr: {
    title: 'Gardez votre histoire',
    email: 'Adresse e-mail',
    password: 'Mot de passe',
    password_hint: 'Au moins 8 caractères',
    show: 'Afficher',
    hide: 'Masquer',
    first_name: 'Prénom',
    optional: 'facultatif',
    level_question: 'Votre français ?',
    levels: {
      new: 'Nouveau',
      some: 'Quelques bases',
      comfortable: 'À l’aise au quotidien',
      confident: 'À l’aise sur presque tout',
      advanced: 'Je lis et j’argumente avec nuance',
    },
    language: 'Langue de l’app',
    created_sign_in: 'Compte créé. Connectez-vous pour ouvrir votre première scène.',
    failed: 'Une erreur est survenue. Réessayez.',
    errors: {
      email_required: 'Indiquez votre adresse.',
      email_invalid: 'Adresse e-mail invalide.',
      password_required: 'Choisissez un mot de passe.',
      password_short: 'Au moins 8 caractères.',
      password_long: 'Trop long : 72 octets au plus.',
      starting_point_required: 'Choisissez une réponse.',
    },
  },
};

/**
 * The sign-up's buttons and the screen's name. 2026-09-24: these are chrome,
 * so they follow the detected onboarding language like the fields above (the
 * one-language rule; before an account exists the learner reads as a beginner).
 */
export type SignUpNav = { screen: string; submit: string; pending: string; have_account: string };

export const SIGNUP_NAV: Record<OnboardingLanguage, SignUpNav> = {
  en: {
    screen: 'Create an account',
    submit: 'Create my account',
    pending: 'Creating…',
    have_account: 'I already have an account',
  },
  de: {
    screen: 'Konto erstellen',
    submit: 'Mein Konto erstellen',
    pending: 'Wird erstellt…',
    have_account: 'Ich habe schon ein Konto',
  },
  fr: {
    screen: 'Créer un compte',
    submit: 'Créer mon compte',
    pending: 'Création…',
    have_account: 'J’ai déjà un compte',
  },
};
