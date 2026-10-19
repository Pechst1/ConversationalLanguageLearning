/**
 * Home's way onto Le mur du Mistral, shown once there is at least one object
 * (components/cast/items/MurDuMistral): a row on the full Home, a chip in the journey Home's
 * quiet row when it has room.
 */
import Link from 'next/link';
import React from 'react';

import { ArrowRightIcon } from '@/components/atelier-v2/ui';
import { useLearnerLanguage } from '@/lib/learner-language';
import { marksFor, toCameoLang, WALL_COPY, wallText } from '@/lib/season-wall';

import { useSeasonWall } from './MurDuMistral';
import { PlotItem } from './PlotItem';

export const MUR_HREF = '/mur';

/** `className` goes on a wrapper that exists only when the row does. */
export function MurEntry({ className }: { className?: string }) {
  const lang = toCameoLang(useLearnerLanguage());
  const { wall, hooks } = useSeasonWall();
  const owned = hooks.filter((hook) => hook.owned);
  if (!owned.length) return null;
  return (
    <div className={className}>
      <Link className="av2-row" href={MUR_HREF} aria-label={`${WALL_COPY.title} · ${wallText(WALL_COPY.count, lang, { n: owned.length, total: hooks.length })}`}>
        <span className="av2-row__main">
          <span className="av2-label">{WALL_COPY.title}</span>
          <span style={{ display: 'flex', gap: 4, margin: '6px 0 4px' }} aria-hidden="true">
            {owned.slice(-5).map((hook) => (
              <PlotItem key={hook.item.id} id={hook.item.id} size={34} still css="none" marks={marksFor(hook.item, wall.marks)} />
            ))}
          </span>
          <span className="av2-label" style={{ fontWeight: 400 }}>
            {wallText(WALL_COPY.count, lang, { n: owned.length, total: hooks.length })}
          </span>
        </span>
        <ArrowRightIcon size={18} />
      </Link>
    </div>
  );
}

/**
 * The journey Home's chip. `className` goes on a wrapper only when given (the chip alone, with
 * no other chips around it); otherwise the chip sits in the existing chips row.
 */
export function MurChip({ className }: { className?: string }) {
  const lang = toCameoLang(useLearnerLanguage());
  const { wall, hooks } = useSeasonWall();
  const owned = hooks.filter((hook) => hook.owned);
  if (!owned.length) return null;
  const last = owned[owned.length - 1];
  const count = wallText(WALL_COPY.count, lang, { n: owned.length, total: hooks.length });
  const chip = (
    <Link className="av2-chip" data-chip="mur" href={MUR_HREF} aria-label={`${WALL_COPY.title} · ${count}`}>
      <PlotItem id={last.item.id} size={20} still css="none" marks={marksFor(last.item, wall.marks)} />
      <span>{WALL_COPY.title}</span>
      <span className="av2-chip__meta">{`${owned.length}/${hooks.length}`}</span>
    </Link>
  );
  return className ? <div className={className}>{chip}</div> : chip;
}

export default MurEntry;
