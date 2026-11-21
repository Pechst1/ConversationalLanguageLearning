/**
 * «Le bilan» on Home — a calm card, after the week closes (the learner's Monday).
 *
 * `GET /bilan/card` names the last closed week when it had a played day. The card shows
 * until the learner opens that week's bilan (the page marks it seen) or says «not now».
 * The switch off (a 404), an error, an empty week: nothing at all — Home is as it was.
 * Not a second press bar: a Surface with a quiet link row, like Home's entries.
 */

import React from 'react';
import Link from 'next/link';

import { ArrowRightIcon, Surface } from '@/components/atelier-v2/ui';
import { bilanClient, bilanHref } from '@/lib/bilan-api';
import type { BilanCard, BilanLanguage } from '@/lib/bilan-types';
import { useChromeLanguage } from '@/lib/learner-language';
import { oncePerLoad } from '@/lib/once-per-load';

import { bilanCopy, normalizeBilanLanguage, type BilanCopy } from './bilan-copy';
import { browserSeenStore, cardLines, cardWeek, markBilanSeen } from './bilan-model';

export function BilanCardView({
  card,
  language,
  copy,
  onDismiss,
}: {
  card: BilanCard;
  language: BilanLanguage;
  copy: BilanCopy;
  onDismiss?: () => void;
}) {
  const lines = cardLines(card, language, copy);
  return (
    <Surface as="section" className="bl-card" aria-label={copy.page_title}>
      <p className="av2-label av2-label--story bl-card__kicker">{copy.page_title}</p>
      <p className="av2-headline av2-headline--rule bl-card__title">{lines.title}</p>
      <p className="av2-body bl-card__meta">{lines.meta}</p>
      <div className="bl-card__actions">
        <Link className="av2-row bl-card__open" href={bilanHref(card.weekStart)}>
          <span className="av2-row__main av2-label">{copy.card_open}</span>
          <ArrowRightIcon size={18} />
        </Link>
        {onDismiss && (
          <button type="button" className="bl-card__dismiss" onClick={onDismiss}>
            {copy.card_dismiss}
          </button>
        )}
      </div>
    </Surface>
  );
}

/** `className` goes on a wrapper that exists only when the card does. */
export function BilanHomeCard({ className }: { className?: string }) {
  const language = normalizeBilanLanguage(useChromeLanguage());
  const copy = bilanCopy(language);
  const [card, setCard] = React.useState<BilanCard | null>(null);
  const [week, setWeek] = React.useState<string | null>(null);

  React.useEffect(() => {
    let alive = true;
    oncePerLoad('bilan/card', () => bilanClient().card())
      .then((result) => {
        if (!alive || !result.enabled) return;
        const shown = cardWeek(result.card, browserSeenStore());
        setCard(result.card);
        setWeek(shown);
      })
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, []);

  if (!card || !week) return null;
  return (
    <div className={className}>
      <BilanCardView
        card={card}
        language={language}
        copy={copy}
        onDismiss={() => {
          markBilanSeen(week, browserSeenStore());
          setWeek(null);
        }}
      />
    </div>
  );
}

export default BilanHomeCard;
