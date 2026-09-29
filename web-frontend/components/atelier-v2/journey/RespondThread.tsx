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
 *
 * WP-91 «Les voix»: every character face in the column is the play button for
 * its own line (the step's server clip when `journeyId`/`stepId` are given,
 * the device's French voice otherwise), and the reply that just typed in says
 * itself once when «Les personnages parlent à voix haute» is on.
 */

import React from 'react';

import { ShapeToken } from '@/components/atelier-v2/ui';
import { frenchSpacing } from '@/lib/french-typography';
import type { PortraitMood } from '@/lib/onboarding-portraits';

import type { JourneyCopy } from './journey-copy';
import { CharacterTyping, type ReplySpeaker } from './ReplyStage';
import { SpeakingPortrait } from './SpeakingPortrait';
import { useAutoSpeak, type LineVoice, type VoiceLine } from './useLineVoice';
import { listenLabel, useStepVoice } from './useStepVoice';
import { replyFinishedTyping } from './voice-autoplay';
import {
  exchangeLabel,
  markSpan,
  printedFix,
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

/**
 * WP-103 T6. The learner's own line, and — always visible under it — the
 * corrected form in small green Garamond («ta place»). The slip in the line
 * itself is only marked (a dotted red underline, nothing to tap); the corrected
 * form is the control that opens the one-line explanation. The owner's test
 * showed why: a mark that must be tapped to find out there is a correction at
 * all goes unread.
 */
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
  const fix = printedFix(correction);
  const noteId = `av2-thread-note-${bubble.key}`;
  // The span is a real substring by contract; a payload that breaks that just
  // leaves the line unmarked — the corrected form under it still says it all.
  const marked = correction ? markSpan(bubble.text, correction.span_fr) : null;
  const explained = Boolean(fix && fix.notes.length > 0);

  return (
    <>
      <p
        className="av2-fr av2-thread__mine"
        lang="fr"
        data-pending={bubble.pending ? 'true' : undefined}
      >
        {marked ? (
          <>
            {marked.before}
            <span className="av2-thread__slip">{marked.mark}</span>
            {marked.after}
          </>
        ) : (
          bubble.text
        )}
      </p>
      {fix && (
        <div className="av2-thread__fix" data-open={open ? 'true' : undefined}>
          {explained ? (
            <button
              type="button"
              className="av2-thread__fixbtn"
              aria-expanded={open}
              aria-controls={noteId}
              onClick={() => onToggle(bubble.key)}
            >
              <span className="av2-sr">{copy.thread_fix_sr}: </span>
              <span aria-hidden="true">→ </span>
              <span className="av2-thread__fixed" lang="fr">
                {fix.fixed}
              </span>
              <span className="av2-sr"> ({open ? copy.thread_note_close : copy.thread_note_open})</span>
            </button>
          ) : (
            <p className="av2-thread__fixline">
              <span className="av2-sr">{copy.thread_fix_sr}: </span>
              <span aria-hidden="true">→ </span>
              <span className="av2-thread__fixed" lang="fr">
                {fix.fixed}
              </span>
            </p>
          )}
          {open && explained && (
            <div className="av2-thread__note" id={noteId} role="note">
              {fix.notes.map((note, index) => (
                <p key={index}>{note}</p>
              ))}
            </div>
          )}
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
  journeyId = null,
  stepId = null,
  voice: sharedVoice = null,
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
  /** WP-91: the day and the step, so a face speaks with the server's clip. */
  journeyId?: string | null;
  stepId?: string | null;
  /** WP-91: a voice the screen already holds (otherwise the thread makes one). */
  voice?: LineVoice | null;
}) {
  const name = speaker?.name ?? '';
  const voice = useStepVoice(journeyId, stepId, sharedVoice);
  const lineFor = (bubble: { key: string; text: string }): VoiceLine => ({
    key: `${stepId ?? ''}:${bubble.key}`,
    text_fr: bubble.text,
    character_id: speaker?.id ?? null,
  });
  // The reply that just arrived speaks once, when its words have typed in.
  const typingBubble = typingKey
    ? bubbles.find((bubble) => bubble.kind === 'character' && bubble.key === typingKey) ?? null
    : null;
  useAutoSpeak(
    voice,
    typingBubble ? lineFor(typingBubble) : null,
    Boolean(typingBubble && replyFinishedTyping(typingBubble.text, typedText)),
    stepId,
  );
  const label = listenLabel(copy, name);
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
                    <SpeakingPortrait
                      line={lineFor(bubble)}
                      voice={voice}
                      label={label}
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
                    <SpeakingPortrait
                      line={lineFor(bubble)}
                      voice={voice}
                      label={label}
                      characterId={speaker.id || ''}
                      name={speaker.name}
                      size="xs"
                    />
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
