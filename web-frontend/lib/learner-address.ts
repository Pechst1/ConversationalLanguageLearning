/**
 * How the app addresses the learner: one setting per language.
 *
 * German is «du», French is «tu» (owner decision, 14 Oct 2026: «always tu makes it
 * simpler»). Every French and German string the interface prints to the learner is
 * written in that form; `lib/learner-address.test.js` fails on «vous», «votre»,
 * «Sie» or «Ihr» used as the learner's address in the copy tables.
 *
 * A *character's* register is a different thing and stays story data: Gus says
 * «vous» until the third tentpole, Margaux says «tu» from the first night. The
 * cast page and the Courrier read it from the server (`character register`); it is
 * never decided by a pronoun in chrome copy.
 *
 * The server holds the same setting in `app/services/address.py`
 * (`LEARNER_ADDRESS`); the two are asserted equal in the node test.
 */

export type AddressLanguage = 'fr' | 'de';

export const LEARNER_ADDRESS: Readonly<Record<AddressLanguage, 'tu' | 'du'>> = {
  fr: 'tu',
  de: 'du',
};

/** «tu» for French, «du» for German, `null` where the language has no choice (English). */
export function learnerAddress(language: unknown): 'tu' | 'du' | null {
  const key = typeof language === 'string' ? language.trim().toLowerCase().slice(0, 2) : '';
  return key === 'fr' || key === 'de' ? LEARNER_ADDRESS[key] : null;
}
