/**
 * A line of the scene is not a note about it (#263).
 *
 * The live walk of 21 Oct printed under a picture: «Le Mistral à nous 40 × 1 000 €
 * Margaux Mme Diallo le petit Augustin (!) Marin — il dira oui en pleurant M. M. :
 * oui, si Margaux reste.» — the director's scratch note, a prediction of what a
 * character will say included. The server now drops such a line before it is stored
 * (`app/services/sentence_line.py`, `is_planning_note`); this mirror keeps the ones
 * stored earlier out of the reader. Keep the two shapes lists the same.
 */

const FLAG = /\((?:!|\?|!!|\?\?)\)/;
const AMOUNT = /\d[\d\s  .,]*\s*[×✕]\s*\d/;
const INITIALS_TAG = /(?:\b[A-ZÀ-ÖØ-Þ]\.\s?){2,}:/;
const LABEL = /^\s*(?:note|nb|n\.b\.|todo|plan|idée|idee|rappel)\s*[:\-–—]/i;

export function isPlanningNote(text: string | null | undefined): boolean {
  const flat = String(text ?? '').replace(/\s+/g, ' ').trim();
  if (!flat) return false;
  return FLAG.test(flat) || AMOUNT.test(flat) || INITIALS_TAG.test(flat) || LABEL.test(flat);
}
