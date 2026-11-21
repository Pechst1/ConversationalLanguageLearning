/**
 * Owner, 2026-11-13: one voice per level of the hierarchy. A La Forge prompt such as
 *
 *   À la gare, ton amie te dit : « Le train part dans dix minutes ! » Réponds-lui en
 *   disant ce que tu dois faire.
 *
 * was set whole in large Garamond italic: four lines of display type, tiring to read.
 * Only the quoted line is speech; the situation before it and the instruction after it
 * are prose. This cuts the prompt at its quote (« … », “ … ”, „ … “, " … ") so the
 * screen sets each in its own voice. Null when there is no quoted line, or when the
 * quote is the whole prompt: that prompt keeps today's single headline.
 *
 * Pure: pinned by lib/prompt-parts.test.js.
 */

export type PromptParts = { situation: string; quote: string; instruction: string };

const PAIRS: Array<[string, string]> = [
  ['«', '»'],
  ['“', '”'],
  ['„', '“'],
  ['"', '"'],
];

export function promptParts(prompt: unknown): PromptParts | null {
  const text = String(prompt ?? '').replace(/\s+/g, ' ').trim();
  if (!text) return null;
  let best: { open: number; close: number; width: number } | null = null;
  for (const [open, close] of PAIRS) {
    const start = text.indexOf(open);
    if (start < 0) continue;
    const end = text.indexOf(close, start + open.length);
    if (end < 0) continue;
    if (!best || start < best.open) best = { open: start, close: end, width: open.length };
  }
  if (!best) return null;
  const quote = text.slice(best.open + best.width, best.close).trim();
  const situation = text.slice(0, best.open).trim();
  const instruction = text.slice(best.close + 1).trim();
  // A short quoted word inside a sentence («le mot « chat »») is not a line said.
  if (quote.split(/\s+/).length < 3) return null;
  if (!situation && !instruction) return null;
  return { situation, quote, instruction };
}
