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
import api, { type StreakCalendar } from '@/services/api';

import { WEEKDAY_INITIALS, daysLabel, sealCollectionView, type SealCell } from './seal-collection-model';

function todayLine(cell: SealCell | null, todayDone: boolean, formsLeft: number | null): string {
  if (cell?.kind === 'day' && cell.state === 'earned') return 'Le sceau du jour est rangé.';
  if (todayDone) return 'Journée faite. Le sceau se presse en bouclant la scène.';
  if (formsLeft != null && formsLeft > 0) {
    return formsLeft === 1 ? 'Le sceau du jour : encore 1 forme.' : `Le sceau du jour : encore ${formsLeft} formes.`;
  }
  return 'Le sceau du jour attend sa scène.';
}

export function SealCollectionBody({
  payload,
  formsLeft = null,
}: {
  payload: StreakCalendar | null;
  /** WP-D1: shapes of today's mark not yet filled, when the caller knows. */
  formsLeft?: number | null;
}) {
  const view = useMemo(() => sealCollectionView(payload), [payload]);
  if (!view) return null;
  const today = view.today;
  return (
    <>
      <Surface className="av2-seals">
        <ol className="av2-seals__week-days" aria-hidden="true">
          {WEEKDAY_INITIALS.map((initial, index) => (
            <li key={index} className="av2-label">
              {initial}
            </li>
          ))}
        </ol>
        <ol className="av2-seals__grid" aria-label={`Vos sceaux · série de ${daysLabel(view.streak)}`}>
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
          <p className="av2-body">{todayLine(today, view.todayDone, formsLeft)}</p>
          <p className="av2-label">
            {`Série · ${daysLabel(view.streak)} · record · ${daysLabel(view.longest)}`}
          </p>
          {view.freezeAvailable && <p className="av2-label">Un jour de relâche en réserve.</p>}
        </div>
      </Surface>
    </>
  );
}

export default function SealCollection() {
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
    <section className="nb-rv__sec" id="sceaux" aria-label="Vos sceaux">
      <NbSectionHead t="Vos sceaux" n={null} />
      {state === 'loading' ? (
        <Skeleton height={180} radius={16} />
      ) : state === 'failed' ? (
        <Notice tone="alert" live="alert" shape="action">
          <p>Les sceaux n’ont pas pu être relevés.</p>
          <Action tone="secondary" inline onClick={() => void load()}>
            Réessayer
          </Action>
        </Notice>
      ) : (
        <SealCollectionBody payload={payload} />
      )}
    </section>
  );
}
