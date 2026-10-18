/**
 * Home's way onto Le mur du Mistral: a row with the objects handed over so far, shown once there
 * is at least one (components/cast/items/MurDuMistral).
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

export default MurEntry;
