import React from 'react';

import type { CardTexts } from '@/lib/card-word';

/* The front of a Lexique review card (/vocabulary/review): the ear button above, the word
   in the screen's one Garamond-italic headline, the hint line under it.

   What the front says comes from `cardTexts` (lib/card-word.ts) only: the word, whether
   it is the French, and, when the front is the meaning in the learner's language, the
   line that asks for the French. Walk finding #725: «school» and «forty» stood alone on
   the front, among cards that all showed their French; nothing said this card went the
   other way. The page no longer decides the front's language on its own. */
export function CardFront({
  texts,
  hint,
  listen,
}: {
  texts: Pick<CardTexts, 'prompt' | 'promptIsFrench' | 'ask'>;
  hint: string;
  /** The ear button, offered on a French front only. */
  listen: React.ReactNode;
}) {
  return (
    <div className="lx-card__middle">
      <div className="lx-card__top">{texts.promptIsFrench && listen}</div>
      {texts.ask && <p className="lx-card__ask" data-card-ask="">{texts.ask}</p>}
      <p className="av2-headline lx-card__word review-prompt-term" lang={texts.promptIsFrench ? 'fr' : undefined}>
        {texts.prompt}
      </p>
      {hint && <p className="lx-card__hint">{hint}</p>}
    </div>
  );
}
