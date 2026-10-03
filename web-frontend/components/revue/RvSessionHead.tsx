/**
 * WP-119 · RvSessionHead (× · five beats · the column) and RvColumn.
 *
 * The × leaves for La Une with no confirm: the state is append-only, nothing is
 * lost («Quitter la Revue — Romy garde tes notes»). After the close — and on a
 * read-only replay (`back`) — it is a back arrow. `back` switches only the icon and
 * its label: a read-only replay of an active session keeps its real beat bar
 * (`ended` alone fills it). `pursue` is the open part of the route, so its segment
 * is double width.
 *
 * RvColumn (design §3.8): seven short lines inked as the room is used, never a
 * number or a clock. The word shows only at 80 % («Bouclage», the last inked line
 * red) and at 100 % («Bouclé»). A tap shows one line for 3 s; screen readers get
 * that sentence as the label.
 */

import React, { useEffect, useState } from 'react';

import { ArrowLeftIcon, CrossIcon, IconAction } from '@/components/atelier-v2/ui';
import type { RvBeat, RvRoom } from '@/lib/revue-types';

import type { RevueCopy } from './revue-copy';
import { beatSegments, columnModel, roomSentence } from './revue-model';

export function RvColumn({ room, copy }: { room: RvRoom; copy: RevueCopy }) {
  const model = columnModel(room, copy);
  const [tip, setTip] = useState(false);
  useEffect(() => {
    if (!tip) return undefined;
    const timer = window.setTimeout(() => setTip(false), 3000);
    return () => window.clearTimeout(timer);
  }, [tip]);
  return (
    <button type="button" className="rv-col" data-phase={room.phase} aria-label={model.srLabel} onClick={() => setTip(true)}>
      <span className="rv-col__glyph" aria-hidden="true">
        {model.lines.map((line, index) => (
          <i key={index} data-used={line.used ? '' : undefined} data-last={line.last ? '' : undefined} />
        ))}
      </span>
      {model.word && <span aria-hidden="true">{model.word}</span>}
      {tip && (
        <span className="rv-col__tip" role="status">
          {roomSentence(room, copy)}
        </span>
      )}
    </button>
  );
}

export type RvSessionHeadProps = {
  beat: RvBeat | null;
  room: RvRoom;
  onExit: () => void;
  /** The session is closed: every beat is filled. */
  ended?: boolean;
  /** The × becomes a back arrow (and its label «Retour»); the beats are untouched. Defaults to `ended`. */
  back?: boolean;
  copy: RevueCopy;
};

export function RvSessionHead({ beat, room, onExit, ended = false, back = ended, copy }: RvSessionHeadProps) {
  const segments = beatSegments(beat, ended);
  const at = segments.findIndex((segment) => segment.state === 'active');
  return (
    <div className="rv-head">
      <IconAction label={back ? copy.back_label : copy.exit_label} onClick={onExit}>
        {back ? <ArrowLeftIcon size={18} /> : <CrossIcon size={16} />}
      </IconAction>
      <ol
        className="rv-head__beats"
        role="progressbar"
        aria-label={copy.beats_label}
        aria-valuemin={0}
        aria-valuemax={segments.length}
        aria-valuenow={ended ? segments.length : Math.max(0, at)}
        aria-valuetext={beat ? copy.beat_names[beat] : undefined}
      >
        {segments.map((segment) => (
          <li key={segment.beat} className="av2-progress__segment" data-beat={segment.beat} data-state={segment.state} />
        ))}
      </ol>
      <RvColumn room={room} copy={copy} />
    </div>
  );
}

export default RvSessionHead;
