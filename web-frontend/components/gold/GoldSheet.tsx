/* Package O-2 — «D'où vient ton or» (docs/ATELIER_GOLD_ECONOMY_PLAN.md §3, §16).

   One week of the ledger, day by day, each entry on one line with its reason
   («Rappel écrit · rappel différé ×2»): a filled square when printed (settled),
   a dashed one while à l'épreuve (pending), a faded dashed one when pulped. */

import React, { useEffect, useState } from 'react';

import { BottomSheet, useControlLanguage } from '@/components/atelier-v2/ui';
import apiService from '@/services/api';
import {
  dayLabel,
  entriesByDay,
  entryLine,
  goldCopy,
  previousWeek,
  todayNote,
  voidLine,
  type GoldLedgerWeek,
  type GoldView,
} from '@/lib/gold-model';

import { GoldGlyph } from './GoldGlyph';

export function GoldSheet({ open, onClose, view }: { open: boolean; onClose: () => void; view: GoldView }) {
  const language = useControlLanguage();
  const copy = goldCopy(language);
  const thisWeek = view.week?.week_id ?? null;
  const [week, setWeek] = useState<string | null>(thisWeek);
  const [ledger, setLedger] = useState<GoldLedgerWeek | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (open) setWeek(thisWeek);
  }, [open, thisWeek]);

  useEffect(() => {
    if (!open) return undefined;
    let live = true;
    setFailed(false);
    apiService
      .getGoldLedger(week ?? undefined)
      .then((body) => live && setLedger(body))
      .catch(() => live && setFailed(true));
    return () => {
      live = false;
    };
    // `view.balance` re-reads the open sheet after a new grain.
  }, [open, week, view.balance]);

  const today = view.today;
  const note = todayNote(view, language);
  const groups = ledger?.visible && ledger.week_id === week ? entriesByDay(ledger.entries || []) : [];
  const earlier = week ? previousWeek(week) : null;

  return (
    <BottomSheet
      open={open}
      onClose={onClose}
      title={copy.sheet_title}
      eyebrow={copy.sheet_eyebrow(view.balance ?? 0)}
    >
      <div className="av2-gold-sheet">
        {today && week === thisWeek && (
          <p className="av2-gold-sheet__today">
            {copy.today} <strong>+{today.settled}</strong>
            {' · '}
            {today.pleine ? copy.day_full : copy.day_toward({ earned: today.earn_settled, mark: today.mark })}
            {view.week ? ` · ${copy.week({ days: view.week.journees_pleines, goal: view.week.journees_pleines_goal })}` : ''}
            {note ? <span className="av2-gold-sheet__note"> · {note}</span> : null}
          </p>
        )}
        {failed && <p className="av2-gold-sheet__empty">{copy.sheet_failed}</p>}
        {!failed && ledger && groups.length === 0 && (
          <p className="av2-gold-sheet__empty">{copy.sheet_empty}</p>
        )}
        {groups.map((group) => (
          <section key={group.day} className="av2-gold-sheet__day">
            <h3 className="av2-label">{dayLabel(group.day, language)}</h3>
            <ul className="av2-gold-sheet__list">
              {group.entries.map((entry) => {
                const pulped = voidLine(entry, language);
                return (
                  <li key={entry.id} className="av2-gold-entry" data-state={entry.state}>
                    <GoldGlyph state={entry.state === 'settled' ? 'settled' : entry.state === 'void' ? 'void' : 'pending'} />
                    <span className="av2-gold-entry__why">{entryLine(entry)}</span>
                    <span className="av2-gold-entry__n">{pulped ?? `+${entry.amount}`}</span>
                  </li>
                );
              })}
            </ul>
          </section>
        ))}
        <div className="av2-gold-sheet__weeks">
          {earlier && (
            <button type="button" className="av2-btn av2-btn--quiet av2-btn--inline" onClick={() => setWeek(earlier)}>
              {copy.week_before}
            </button>
          )}
          {week !== thisWeek && (
            <button type="button" className="av2-btn av2-btn--quiet av2-btn--inline" onClick={() => setWeek(thisWeek)}>
              {copy.this_week}
            </button>
          )}
        </div>
      </div>
    </BottomSheet>
  );
}
