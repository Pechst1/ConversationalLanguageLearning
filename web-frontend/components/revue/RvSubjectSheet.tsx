/**
 * WP-119 · «Autre sujet ?» (design §3.1 #sheet / #ask-miss) and the pieces the
 * chooser shares: the alternative rows and the «Autre chose ?» field.
 *
 * Rows are hairline-separated so the stories read as one list, not cards; the
 * circle is the story shape, never a press. A free request goes to
 * `POST /revue/match`: a match opens that story; a miss gets Romy's own line in
 * the sheet, in French, with the learner's request on the right — no error tint,
 * an absence is not a failure.
 */

import React, { useState } from 'react';

import { ArrowRightIcon, BottomSheet, CastPortrait, IconAction, ShapeToken } from '@/components/atelier-v2/ui';
import type { RvMatchResult, RvStoryCard, RvWeek } from '@/lib/revue-types';

import { fill, type RevueCopy } from './revue-copy';

export function RvAltRows({ stories, onPick, copy }: { stories: RvStoryCard[]; onPick: (dossierId: string) => void; copy: RevueCopy }) {
  if (!stories.length) return null;
  return (
    <ul className="rv-alts">
      {stories.map((story) => (
        <li key={story.dossierId}>
          <button type="button" className="rv-alt" data-dossier={story.dossierId} onClick={() => onPick(story.dossierId)}>
            <ShapeToken kind="story" size="sm" />
            <span className="rv-alt__t" lang="fr">
              {story.titleFr}
              <span className="rv-alt__m">
                <span lang="fr">{story.placeFr}</span> · {story.evergreen ? copy.evergreen_topic : copy.topic[story.topic]}
              </span>
            </span>
            <ArrowRightIcon size={18} />
          </button>
        </li>
      ))}
    </ul>
  );
}

/** «Autre chose ?»: the learner's request, Romy's answer on a miss. */
export function RvAsk({
  onAsk,
  onPick,
  copy,
}: {
  onAsk: (text: string) => Promise<RvMatchResult>;
  onPick: (dossierId: string) => void;
  copy: RevueCopy;
}) {
  const [text, setText] = useState('');
  const [asked, setAsked] = useState<string | null>(null);
  const [romy, setRomy] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    const value = text.trim();
    if (!value || busy) return;
    setBusy(true);
    try {
      const result = await onAsk(value);
      if (result.match) {
        onPick(result.match);
        return;
      }
      setAsked(value);
      setRomy(result.romyLineFr);
      setText('');
    } catch {
      setAsked(value);
      setRomy(null);
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      {asked && (
        <p className="rv-ask__mine" lang="fr">
          {asked}
        </p>
      )}
      {romy && (
        <div className="av2-speech av2-speech--past" data-mood="neutral" role="status">
          <span className="av2-speech__face" aria-hidden="true">
            <CastPortrait characterId="romy_tremblay" name="Romy" size="sm" ring />
          </span>
          <div className="av2-speech__bubble">
            <span className="rv-who">{copy.romy}</span>
            <p className="av2-thread__text av2-fr" lang="fr">
              {romy}
            </p>
          </div>
        </div>
      )}
      <form
        className="rv-ask"
        onSubmit={(event) => {
          event.preventDefault();
          void submit();
        }}
      >
        <input
          className="av2-field__control"
          type="text"
          lang="fr"
          autoCorrect="off"
          autoCapitalize="off"
          spellCheck={false}
          maxLength={300}
          value={text}
          placeholder={copy.ask_placeholder}
          aria-label={copy.ask_placeholder}
          onChange={(event) => setText(event.target.value)}
        />
        <IconAction label={copy.ask_send} pressable type="submit" pending={busy} disabled={!text.trim()}>
          <ArrowRightIcon size={18} />
        </IconAction>
      </form>
    </>
  );
}

export type RvSubjectSheetProps = {
  open: boolean;
  week: RvWeek;
  alternatives: RvStoryCard[];
  onPick: (dossierId: string) => void;
  onAsk: (text: string) => Promise<RvMatchResult>;
  onClose: () => void;
  copy: RevueCopy;
};

export function RvSubjectSheet({ open, week, alternatives, onPick, onAsk, onClose, copy }: RvSubjectSheetProps) {
  return (
    <BottomSheet open={open} title={copy.other_subject_title} eyebrow={<span className="rv-kicker">{`${copy.revue} · ${week.label.toLowerCase()}`}</span>} onClose={onClose}>
      <div className="rv-sheet">
        <p className="av2-body">{fill(copy.sheet_lead, { n: alternatives.length + 1 })}</p>
        <RvAltRows stories={alternatives} onPick={onPick} copy={copy} />
        <RvAsk onAsk={onAsk} onPick={onPick} copy={copy} />
      </div>
    </BottomSheet>
  );
}

export default RvSubjectSheet;
