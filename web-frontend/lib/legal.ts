/**
 * WP-72 — the privacy policy, the terms and the sign-up consent line.
 *
 * The text is `lib/legal-content.json`, a byte-identical copy of the API's
 * canonical `app/data/legal/legal_content.json` (the API serves the same words
 * at `/privacy` and `/terms` for App Store Connect). Edit the canonical file and
 * run `node scripts/sync-legal-content.mjs`; tests fail on drift.
 *
 * Legal and explanatory text is in the learner's language (en/de/fr), never in
 * the publication's French chrome alone: a learner must be able to read what
 * they accept.
 */
import content from './legal-content.json';

export type LegalLanguage = 'en' | 'de' | 'fr';
export type LegalDocumentKind = 'privacy' | 'terms';

export type LegalSection = { h: string; p: string[] };
export type LegalDocument = { title: string; lead: string; sections: LegalSection[] };

export const LEGAL_LANGUAGES: LegalLanguage[] = ['en', 'de', 'fr'];
export const LEGAL_VERSION: string = content.version;
export const LEGAL_OPERATOR: string = content.operator;
export const LEGAL_CONTACT: string = content.contact_email;

/** First supported base language among the candidates, else English. */
export function resolveLegalLanguage(...candidates: unknown[]): LegalLanguage {
  for (const candidate of candidates) {
    if (typeof candidate !== 'string' || !candidate.trim()) continue;
    const base = candidate.trim().toLowerCase().replace('_', '-').split('-')[0];
    if ((LEGAL_LANGUAGES as string[]).includes(base)) return base as LegalLanguage;
  }
  return 'en';
}

export function legalDocument(kind: LegalDocumentKind, language: LegalLanguage): LegalDocument {
  return content.documents[kind][language] as LegalDocument;
}

export function legalLabels(language: LegalLanguage) {
  return content.labels[language];
}

/** A paragraph split around `{contact}` so the page can render a mailto link. */
export type LegalTextPart = { kind: 'text'; value: string } | { kind: 'contact'; value: string };

export function legalTextParts(text: string): LegalTextPart[] {
  const filled = text.split('{operator}').join(LEGAL_OPERATOR);
  const pieces = filled.split('{contact}');
  const parts: LegalTextPart[] = [];
  pieces.forEach((piece, index) => {
    if (piece) parts.push({ kind: 'text', value: piece });
    if (index < pieces.length - 1) parts.push({ kind: 'contact', value: LEGAL_CONTACT });
  });
  return parts;
}

/**
 * The one consent line on sign-up (Apple 5.1.1 / 5.1.2): who processes the
 * learner's answers and voice, and that creating the account accepts both
 * documents. `terms`/`privacy` are the link labels the page renders inline.
 */
export const SIGNUP_CONSENT: Record<
  LegalLanguage,
  { ai: string; accept: string; terms: string; and: string; privacy: string; end: string }
> = {
  en: {
    ai: 'Your answers and your voice are processed by OpenAI to correct you and reply.',
    accept: 'Creating an account accepts the',
    terms: 'terms',
    and: 'and the',
    privacy: 'privacy policy',
    end: '.',
  },
  de: {
    ai: 'Ihre Antworten und Ihre Stimme werden von OpenAI verarbeitet, um Sie zu korrigieren und zu antworten.',
    accept: 'Mit dem Konto akzeptieren Sie die',
    terms: 'Nutzungsbedingungen',
    and: 'und die',
    privacy: 'Datenschutzerklärung',
    end: '.',
  },
  fr: {
    ai: 'Vos réponses et votre voix sont traitées par OpenAI pour vous corriger et vous répondre.',
    accept: 'Créer un compte vaut acceptation des',
    terms: 'conditions',
    and: 'et de la',
    privacy: 'politique de confidentialité',
    end: '.',
  },
};

/** Réglages → Données rows. Hints stay under six words (Appendix A). */
export const SETTINGS_LEGAL_COPY: Record<
  LegalLanguage,
  { privacy: string; privacy_hint: string; terms: string; terms_hint: string; open: string }
> = {
  en: {
    privacy: 'Privacy policy',
    privacy_hint: 'What we keep, and why.',
    terms: 'Terms of use',
    terms_hint: 'The rules of the service.',
    open: 'Read',
  },
  de: {
    privacy: 'Datenschutz',
    privacy_hint: 'Was wir speichern, und warum.',
    terms: 'Nutzungsbedingungen',
    terms_hint: 'Die Regeln des Dienstes.',
    open: 'Lesen',
  },
  fr: {
    privacy: 'Confidentialité',
    privacy_hint: 'Ce que nous gardons, et pourquoi.',
    terms: 'Conditions d’utilisation',
    terms_hint: 'Les règles du service.',
    open: 'Lire',
  },
};

/** Query for an in-app legal link that keeps the reader's language. */
export function legalHref(kind: LegalDocumentKind, language: LegalLanguage) {
  return { pathname: `/${kind}`, query: { lang: language } };
}
