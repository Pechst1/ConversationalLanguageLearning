/**
 * Round 3 (owner, 2026-10-14) — the day as one sequence, on La Une.
 *
 * `DaySessionPlan`: the programme — Szene · Wörter · Grammatik · Fertig as path
 * nodes with the minutes each still costs — and one quiet «Tempo: Normal».
 * `DaySessionNext`: the one button once the scene is done («Weiter: 20 Wörter
 * · 8 Min.»), and after the day the one optional extra («Noch 10 Wörter»).
 * `TempoSheet`: Ruhig / Normal / Schnell, what each holds and costs today, and
 * when it reaches the goal.
 *
 * Presentation and the sheet's own two calls only; the rows and labels come
 * from `lib/day-session.ts`.
 */

import React from 'react';

import { Action, ArrowRightIcon, BottomSheet, CheckIcon, ShapeToken } from '@/components/atelier-v2/ui';
import {
  daySessionCopy,
  paceNote,
  paceRows,
  type SessionRow,
} from '@/lib/day-session';
import { apiService } from '@/services/api';
import type { ControlLanguage, PaceName, PaceOptions } from '@/types/daily-journey';

export function DaySessionPlan({
  rows,
  language,
  tempoLabel,
  onTempo,
}: {
  rows: SessionRow[];
  language: ControlLanguage;
  tempoLabel?: string | null;
  onTempo?: (() => void) | null;
}) {
  const copy = daySessionCopy(language);
  const stateWord = { done: copy.part_done, next: copy.part_next, todo: copy.part_todo };
  return (
    <div className="av2-stack" style={{ gap: 6 }}>
      <ol className="av2-programme" aria-label={copy.plan_label} data-day-session="">
        {rows.map((row) => (
          <li key={row.kind} className="av2-programme__act" data-part={row.kind} data-state={row.state}>
            <span className="av2-programme__node">
              <ShapeToken kind={row.shape} />
              {row.state === 'done' && (
                <span className="av2-programme__check" aria-hidden="true">
                  <CheckIcon size={8} />
                </span>
              )}
            </span>
            <span className="av2-programme__name">
              {row.label}
              <span className="av2-sr"> — {stateWord[row.state]}</span>
            </span>
            <span className="av2-programme__min">{row.meta}</span>
          </li>
        ))}
      </ol>
      {tempoLabel && onTempo && (
        <div style={{ display: 'flex', justifyContent: 'center' }}>
          <button type="button" className="av2-btn av2-btn--quiet av2-btn--inline" onClick={onTempo} data-tempo="">
            {tempoLabel}
          </button>
        </div>
      )}
    </div>
  );
}

export function DaySessionNext({
  next,
  more,
  onNavigate,
}: {
  next: { label: string; meta: string; href: string; kind: string } | null;
  more: { label: string; meta: string; href: string } | null;
  onNavigate: (href: string) => void;
}) {
  if (!next && !more) return null;
  return (
    <div className="av2-session-next" data-session-next={next?.kind ?? 'more'}>
      {next ? (
        <Action tone="primary" onClick={() => onNavigate(next.href)} iconAfter={<ArrowRightIcon size={18} />}>
          {next.label}
          {next.meta ? <span className="av2-btn__meta">· {next.meta}</span> : null}
        </Action>
      ) : more ? (
        <Action tone="secondary" onClick={() => onNavigate(more.href)} data-more-words="">
          {more.label}
          <span className="av2-btn__meta">· {more.meta}</span>
        </Action>
      ) : null}
    </div>
  );
}

export function TempoSheet({
  open,
  language,
  onClose,
  onChanged,
}: {
  open: boolean;
  language: ControlLanguage;
  onClose: () => void;
  /** The pace was switched: Home reads the day again. */
  onChanged?: (pace: PaceName) => void;
}) {
  const copy = daySessionCopy(language);
  const [options, setOptions] = React.useState<PaceOptions | null>(null);
  const [picked, setPicked] = React.useState<PaceName | null>(null);
  const [saving, setSaving] = React.useState(false);
  const [failed, setFailed] = React.useState(false);

  React.useEffect(() => {
    if (!open) return;
    let live = true;
    setFailed(false);
    apiService
      .getDaySessionPace()
      .then((body) => {
        if (!live) return;
        setOptions(body);
        setPicked(body.current);
      })
      .catch(() => live && setFailed(true));
    return () => {
      live = false;
    };
  }, [open]);

  const apply = async () => {
    if (!picked || !options) return;
    if (picked === options.current && options.chosen) {
      onClose();
      return;
    }
    setSaving(true);
    try {
      const body = await apiService.setDaySessionPace(picked);
      setOptions(body);
      onChanged?.(picked);
      onClose();
    } catch {
      setFailed(true);
    } finally {
      setSaving(false);
    }
  };

  const rows = options ? paceRows(options.options, options.goal, language) : [];
  return (
    <BottomSheet open={open} onClose={onClose} title={copy.sheet_title}>
      <div className="av2-stack" data-tempo-sheet="">
        {rows.length > 0 && (
          <ul className="av2-pace-list" role="radiogroup" aria-label={copy.sheet_title}>
            {rows.map((row) => (
              <li key={row.pace}>
                <button
                  type="button"
                  role="radio"
                  aria-checked={picked === row.pace}
                  data-state={picked === row.pace ? 'selected' : undefined}
                  className="av2-choice av2-pace"
                  onClick={() => setPicked(row.pace)}
                  data-pace={row.pace}
                >
                  <span className="av2-pace__name">{row.name}</span>
                  <span className="av2-pace__facts">{row.detail}</span>
                  <span className="av2-pace__min">{row.minutes}</span>
                  <span className="av2-pace__eta">{row.goal}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
        {options && <p className="av2-body av2-pace-note">{paceNote(options.options, language)}</p>}
        {failed && !options && <p className="av2-body">…</p>}
        <Action tone="primary" disabled={!options || !picked} pending={saving} pendingLabel="…" onClick={() => void apply()}>
          {copy.sheet_apply}
        </Action>
      </div>
    </BottomSheet>
  );
}
