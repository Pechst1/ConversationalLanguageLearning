/**
 * WP-89 «Le fil» — the respond step's conversation column.
 *
 * Presentation only; the order, the dedupe and the counts come from
 * `respond-thread.ts`. The character speaks on the left beside their face (the
 * latest line is the screen's one headline, beside the md portrait that reacts
 * to the closing verdict); the learner's own lines sit on the right in
 * Garamond italic, as if typed on the page. The thread is an ordered list with
 * a speaker label on every line.
 *
 * Under the character's name, one small red triangle per planned exchange —
 * the respond part of the mark — filled as each exchange passes. A sequence,
 * never a ring.
 */

import React from 'react';

import { Correction, ShapeToken } from '@/components/atelier-v2/ui';
import { CastPortrait } from '@/components/atelier-v2/ui/CastPortrait';
import { frenchSpacing } from '@/lib/french-typography';
import type { PortraitMood } from '@/lib/onboarding-portraits';

import type { JourneyCopy } from './journey-copy';
import { CharacterTyping, type ReplySpeaker } from './ReplyStage';
import {
  exchangeLabel,
  markSpan,
  type ExchangeProgress,
  type LearnerBubble,
  type ThreadBubble,
} from './respond-thread';

/** The exchange tokens: filled triangles for the exchanges played, ghosts for the rest. */
export function ExchangeTokens({ progress, copy }: { progress: ExchangeProgress; copy: JourneyCopy }) {
  if (progress.total < 2) return null;
  return (
    <p className="av2-thread__tokens">
      {Array.from({ length: progress.total }, (_, index) => (
        <span
          key={index}
          className="av2-thread__token"
          data-state={index < progress.played ? 'done' : index === progress.played ? 'active' : 'todo'}
        >
          <ShapeToken kind="action" size="sm" />
        </span>
      ))}
      <span className="av2-sr">{exchangeLabel(copy.exchange_of, progress)}</span>
    </p>
  );
}

function LearnerLine({
  bubble,
  copy,
  open,
  onToggle,
}: {
  bubble: LearnerBubble;
  copy: JourneyCopy;
  open: boolean;
  onToggle: (key: string) => void;
}) {
  const correction = bubble.correction;
  const noteId = `av2-thread-note-${bubble.key}`;
  // The span is a real substring by contract; if a payload breaks that, the
  // whole line carries the mark rather than the correction going missing.
  const marked = correction
    ? markSpan(bubble.text, correction.span_fr) ?? { before: '', mark: bubble.text, after: '' }
    : null;

  return (
    <>
      <p
        className="av2-fr av2-thread__mine"
        lang="fr"
        data-pending={bubble.pending ? 'true' : undefined}
      >
        {marked && correction ? (
          <>
            {marked.before}
            <button
              type="button"
              className="av2-thread__mark"
              aria-expanded={open}
              aria-controls={noteId}
              onClick={() => onToggle(bubble.key)}
            >
              {marked.mark}
              <span className="av2-sr">
                {' '}
                ({copy.thread_note_open})
              </span>
            </button>
            {marked.after}
          </>
        ) : (
          bubble.text
        )}
      </p>
      {correction && open && (
        <div className="av2-thread__note" id={noteId} role="note">
          <Correction
            label={copy.correction}
            spanFr={correction.span_fr}
            correctedFr={correction.corrected_fr}
            noteNative={correction.note_native}
          />
        </div>
      )}
    </>
  );
}

export function RespondThread({
  bubbles,
  speaker,
  mood,
  copy,
  typingKey,
  typedText,
  waiting,
  openNote,
  onToggleNote,
}: {
  bubbles: ThreadBubble[];
  speaker: ReplySpeaker;
  /** The latest face's mood: neutral mid-conversation, the verdict's at the close. */
  mood: PortraitMood;
  copy: JourneyCopy;
  /** The bubble whose words are typing in (the reply just arrived), if any. */
  typingKey: string | null;
  typedText: string;
  /** The answer is out and the reply is not back: the character is typing. */
  waiting: boolean;
  openNote: string | null;
  onToggleNote: (key: string) => void;
}) {
  const name = speaker?.name ?? '';
  return (
    <ol className="av2-thread" aria-label={copy.thread_label}>
      {bubbles.map((bubble) => {
        if (bubble.kind === 'learner') {
          return (
            <li key={bubble.key} className="av2-thread__line" data-speaker="learner">
              <span className="av2-sr">{copy.thread_you}: </span>
              <LearnerLine
                bubble={bubble}
                copy={copy}
                open={openNote === bubble.key}
                onToggle={onToggleNote}
              />
            </li>
          );
        }
        const typing = typingKey === bubble.key && typedText.length < bubble.text.length;
        const shown = typingKey === bubble.key ? typedText : bubble.text;
        const words = typing ? (
          <>
            <span aria-hidden="true">{frenchSpacing(shown)}</span>
            <span className="av2-sr">{frenchSpacing(bubble.text)}</span>
          </>
        ) : (
          frenchSpacing(bubble.text)
        );
        return (
          <li
            key={bubble.key}
            className="av2-thread__line"
            data-speaker="character"
            data-latest={bubble.latest ? 'true' : undefined}
          >
            {name && <span className="av2-sr">{name}: </span>}
            {bubble.latest ? (
              <div className="av2-speech" data-mood={mood}>
                {speaker && (
                  /* Keyed on the mood, so the closing verdict's face pops in (at-pop). */
                  <span key={mood} className="av2-speech__face">
                    <CastPortrait
                      characterId={speaker.id || ''}
                      name={speaker.name}
                      mood={mood}
                      size="md"
                      ring
                    />
                  </span>
                )}
                <div
                  className="av2-speech__bubble"
                  data-long={bubble.text.length > 48 ? 'true' : undefined}
                >
                  <h2 className="av2-headline" lang="fr">
                    {words}
                  </h2>
                </div>
              </div>
            ) : (
              <div className="av2-speech av2-speech--past" data-mood="neutral">
                {speaker && (
                  <span className="av2-speech__face">
                    <CastPortrait characterId={speaker.id || ''} name={speaker.name} size="xs" />
                  </span>
                )}
                <div className="av2-speech__bubble">
                  <p className="av2-fr av2-thread__text" lang="fr">
                    {words}
                  </p>
                </div>
              </div>
            )}
          </li>
        );
      })}
      {waiting && (
        <li className="av2-thread__line" data-speaker="character">
          <CharacterTyping speaker={speaker} />
        </li>
      )}
    </ol>
  );
}
