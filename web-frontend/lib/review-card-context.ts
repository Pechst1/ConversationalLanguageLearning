// The quoted context line on a word card's back (/vocabulary/review).
//
// #398: a card with no example sentence used to print «word - gloss» in the example's
// quotation marks («lampe - lamp»), which is neither a sentence nor an example. The
// headword and its meaning already sit on the card; with nothing to quote, the card
// quotes nothing.

export interface CardContextInput {
  mode: string;
  french: string;
  meaning: string;
  example: string;
}

export function cardContextText({ mode, meaning, example }: CardContextInput): string {
  if (mode === 'audio') return [meaning, example].filter(Boolean).join(' · ');
  return example;
}
