/**
 * WP-82 — French punctuation that never wraps onto its own line.
 *
 * French sets a thin space before « ; : ! ? » and inside « ». Written with an
 * ordinary space, the browser is free to break there, so a «?» or a «»» lands
 * alone at the start of the next line. The narrow no-break space (U+202F) is
 * the typographer's answer: it looks like the thin space and never breaks.
 *
 * Applied only where French *content* is rendered (the reader, the bubbles,
 * the headlines); chrome in English or German is never passed through it.
 * Idempotent, and it leaves URLs, times («10:30») and ratios alone because it
 * only rewrites a space that is already there, or a guillemet's inside edge.
 */

/** U+202F NARROW NO-BREAK SPACE. */
export const NNBSP = ' ';

// Any ordinary or no-break space (not a newline) directly before ; : ! ? »
const SPACE_BEFORE_HIGH_PUNCT = /[   ]+([;:!?»])/g;
// Any ordinary or no-break space directly after «
const SPACE_AFTER_OPEN_QUOTE = /«[   ]+/g;
// « ! ? ; » glued to a word («Bonjour!») get their space too. «:» does not:
// a colon glued to a digit or a letter is a time («10:30») or a scheme.
const HIGH_PUNCT_GLUED = /([A-Za-zÀ-ÖØ-öø-ÿŒœ])([!?;])/g;
// A guillemet glued to its word: «Bonjour» → « Bonjour »
const OPEN_QUOTE_GLUED = /«(?=[^\s ])/g;
const CLOSE_QUOTE_GLUED = /([^\s ])»/g;

/**
 * Put a narrow no-break space before « ; : ! ? » and inside « ». Non-strings
 * come back as an empty string, so a renderer can pass a nullable field.
 */
export function frenchSpacing(text: string | null | undefined): string {
  if (typeof text !== 'string' || !text) return '';
  return text
    .replace(SPACE_BEFORE_HIGH_PUNCT, `${NNBSP}$1`)
    .replace(HIGH_PUNCT_GLUED, `$1${NNBSP}$2`)
    .replace(SPACE_AFTER_OPEN_QUOTE, `«${NNBSP}`)
    .replace(OPEN_QUOTE_GLUED, `«${NNBSP}`)
    .replace(CLOSE_QUOTE_GLUED, `$1${NNBSP}»`);
}

/** « text » — a French line between guillemets that cannot come apart. */
export function frenchQuote(text: string | null | undefined): string {
  const inner = frenchSpacing(text).trim();
  return inner ? `«${NNBSP}${inner}${NNBSP}»` : '';
}
