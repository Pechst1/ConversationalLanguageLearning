/* WP-D5 · «Vos sceaux» — the streak as a collection of seals (Cahier → Relevé).
 *
 * Reached from the Home streak (`/notebook?mode=releve#sceaux`). A seven-column
 * week grid of `SealMini` discs, four weeks, then one card for today's seal
 * and the record. The number and the grid are one read of
 * `GET /analytics/streak`, so they cannot disagree. Tokens only; fits 320 px
 * without horizontal scroll (seven `minmax(0, 1fr)` columns).
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { Action, Notice, Skeleton, Surface } from '@/components/atelier-v2/ui';
import { NbSectionHead } from '@/components/cahiers/CahierV2';
import { SealMini } from '@/components/ui/Seal';
import { useChromeLanguage } from '@/lib/learner-language';
import api, { type StreakCalendar } from '@/services/api';
import type { ControlLanguage } from '@/types/daily-journey';

import { fill, plural, releveCopy, type ReleveCopy } from './releve-copy';
import { daysLabel, sealCollectionView, weekdayInitials, type SealCell } from './seal-collection-model';

function todayLine(copy: ReleveCopy, cell: SealCell | null, todayDone: boolean, formsLeft: number | null): string {
  if (cell?.kind === 'day' && cell.state === 'earned') return copy.seals_today_earned;
  if (todayDone) return copy.seals_today_done;
  if (formsLeft != null && formsLeft > 0) return plural(copy, 'seals_forms', formsLeft);
  return copy.seals_today_waiting;
}

export function SealCollectionBody({
  payload,
  formsLeft = null,
  language = 'fr',
}: {
  payload: StreakCalendar | null;
  /** WP-D1: shapes of today's mark not yet filled, when the caller knows. */
  formsLeft?: number | null;
  /** The chrome language (`useChromeLanguage`); French when the caller does not say. */
  language?: ControlLanguage;
}) {
  const copy = releveCopy(language);
  const view = useMemo(() => sealCollectionView(payload, undefined, language), [payload, language]);
  if (!view) return null;
  const today = view.today;
  return (
    <>
      <Surface className="av2-seals">
        <ol className="av2-seals__week-days" aria-hidden="true">
          {weekdayInitials(language).map((initial, index) => (
            <li key={index} className="av2-label">
              {initial}
            </li>
          ))}
        </ol>
        <ol className="av2-seals__grid" aria-label={fill(copy.seals_grid, { days: daysLabel(view.streak, language) })}>
          {view.weeks.flat().map((cell) =>
            cell.kind === 'blank' ? (
              <li key={cell.key} aria-hidden="true" />
            ) : (
              <li key={cell.key} data-date={cell.date}>
                <SealMini
                  state={cell.state}
                  variant={cell.variant}
                  no={cell.no}
                  caption={cell.caption}
                  label={cell.label}
                />
              </li>
            ),
          )}
        </ol>
      </Surface>
      <Surface className="av2-seals__today">
        {today?.kind === 'day' && (
          <SealMini state={today.state} variant={today.variant} no={today.no} caption={null} />
        )}
        <div className="av2-seals__today-body">
          <p className="av2-body">{todayLine(copy, today, view.todayDone, formsLeft)}</p>
          <p className="av2-label">
            {fill(copy.seals_streak, {
              streak: daysLabel(view.streak, language),
              longest: daysLabel(view.longest, language),
            })}
          </p>
          {view.freezeAvailable && <p className="av2-label">{copy.seals_freeze}</p>}
        </div>
      </Surface>
    </>
  );
}

export default function SealCollection() {
  const language = useChromeLanguage();
  const copy = releveCopy(language);
  const [payload, setPayload] = useState<StreakCalendar | null>(null);
  const [state, setState] = useState<'loading' | 'ready' | 'failed'>('loading');
  const alive = useRef(true);

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  const load = useCallback(async () => {
    setState('loading');
    try {
      const data = await api.getStreakData(28);
      if (!alive.current) return;
      setPayload(data);
      setState('ready');
    } catch {
      if (alive.current) setState('failed');
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <section className="nb-rv__sec" id="sceaux" aria-label={copy.seals_title}>
      <NbSectionHead t={copy.seals_title} n={null} />
      {state === 'loading' ? (
        <Skeleton height={180} radius={16} />
      ) : state === 'failed' ? (
        <Notice tone="alert" live="alert" shape="action">
          <p>{copy.seals_failed}</p>
          <Action tone="secondary" inline onClick={() => void load()}>
            {copy.retry}
          </Action>
        </Notice>
      ) : (
        <SealCollectionBody payload={payload} language={language} />
      )}
    </section>
  );
}
