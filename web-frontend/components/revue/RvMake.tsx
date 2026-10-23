/**
 * WP-119 · the `make` beat (design §3.5): RvMakePicker, RvHeadlineChoice,
 * RvQuestionDraft.
 *
 * - RvMakePicker: the plan's options as a radio list with a sub-line each; the
 *   one the conversation fits is pre-selected and marked «Ce que propose Romy»
 *   (dot + label + mark). Phase 1 sends only the headline and the reader
 *   question; an unavailable option is absent, never greyed. Built on the
 *   ChoiceList's classes (`av2-choices` / `av2-choice`): ChoiceList itself has no
 *   sub-line or badge slot yet (design §4.2's variant), so the markup is local.
 * - RvHeadlineChoice: the standard ChoiceList + FeedbackBand. The verdict and the
 *   anchor quote with its source appear only after the pick (the server keeps the
 *   answer until then). A wrong pick books no lapse; the right headline is filed.
 * - RvQuestionDraft: «Ta version» and «La question pour les lecteurs», the
 *   learner's words marked as theirs, one line of why in their language.
 *
 * Phase 2 (B1+, WIRE §6.4), offered only when `plan.make_options` lists them:
 * - RvHeadlineWrite: a TextAnswer with the word cap; the graded result is a
 *   FeedbackBand on the fact fit (a contradicted headline is not filed: write again).
 * - RvShortReport: thirty seconds out loud (`useVoiceAnswer`: record →
 *   transcribe), the transcript shown for a quick edit, then sent; a text field
 *   when there is no microphone (or it fails). Never scored on pronunciation.
 *
 * WP-119 §8.4, offered only when the story's own picture is painted:
 * - RvCaption, «La légende»: the picture printed with an empty caption line and
 *   the words it shows. Every band writes it (2026-10-23): the caption prints under
 *   the picture as they type, the picture's words are tiles that drop into it, and
 *   the rubric grades it on what the picture and the sources say (a contradicted or
 *   too short caption: write again). At A1–A2 a refused try also brings the three
 *   captions to choose from (a ChoiceList; the right one is inked in under the
 *   picture after the pick, filed as «La légende», never «Ta légende»).
 */

import React, { useEffect, useRef, useState } from 'react';

import { Action, ChoiceList, FeedbackBand, IconAction, MicIcon, ShapeToken, StopIcon, type ChoiceOption } from '@/components/atelier-v2/ui';
import { textAnswerField } from '@/components/atelier-v2/ui/Choice';
import { useVoiceAnswer } from '@/components/atelier-v2/journey/useVoiceAnswer';
import type {
  RvCaptionOffer,
  RvCaptionResult,
  RvHeadlineOption,
  RvLanguage,
  RvMakeKind,
  RvPickResult,
  RvSpan,
  RvWriteResult,
} from '@/lib/revue-types';

import { fill, type RevueCopy } from './revue-copy';
import { RvPicture } from './RvPicture';
import { ContributedText } from './RvThread';
import { captionInsert, captionUses, headlineWords, sourceDate } from './revue-model';

// ---------------------------------------------------------------------------
// RvMakePicker
// ---------------------------------------------------------------------------

export type RvMakePickerOption = { id: RvMakeKind; titleFr: string; detail: string };

export function RvMakePicker({
  options,
  recommended,
  value,
  onChange,
  copy,
}: {
  options: RvMakePickerOption[];
  recommended: RvMakeKind;
  value: RvMakeKind | null;
  onChange: (kind: RvMakeKind) => void;
  copy: RevueCopy;
}) {
  return (
    <ul className="av2-choices rv-make" role="radiogroup" aria-label={copy.make_label}>
      {options.map((option) => {
        const selected = option.id === value;
        return (
          <li key={option.id}>
            <button
              type="button"
              role="radio"
              aria-checked={selected}
              className="av2-choice"
              data-state={selected ? 'selected' : 'idle'}
              data-make={option.id}
              onClick={() => onChange(option.id)}
            >
              <span className="av2-choice__dot" aria-hidden="true" />
              <span className="rv-make__t">
                {option.titleFr}
                <span className="rv-make__sub">{option.detail}</span>
                {option.id === recommended && (
                  <span className="rv-make__pick">
                    <ShapeToken kind="story" size="sm" />
                    {copy.romy_proposes}
                  </span>
                )}
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}

// ---------------------------------------------------------------------------
// RvHeadlineChoice
// ---------------------------------------------------------------------------

export type RvHeadlineChoiceProps = {
  options: RvHeadlineOption[];
  /** The server's answer to the pick; null until the learner has picked. */
  result: RvPickResult | null;
  picked: string | null;
  pending?: boolean;
  onPick: (optionId: string) => void;
  copy: RevueCopy;
  now?: Date;
};

export function RvHeadlineChoice({ options, result, picked, pending = false, onPick, copy, now }: RvHeadlineChoiceProps) {
  const choices: ChoiceOption[] = options.map((option) => ({
    id: option.id,
    textFr: option.textFr,
    state: result
      ? option.id === result.answerId
        ? 'correct'
        : option.id === picked
          ? 'wrong'
          : 'idle'
      : undefined,
  }));
  const source = result?.evidence.source;
  const name = source ? source.name.replace(/\s*\(.*\)$/, '') : '';
  return (
    <div className="rv-headline" data-answered={result ? '' : undefined}>
      <ChoiceList
        options={choices}
        selectedId={picked}
        label={copy.headline_label}
        disabled={pending || Boolean(result)}
        onSelect={onPick}
        statusLabels={{ selected: copy.status_selected, correct: copy.status_correct, wrong: copy.status_wrong }}
      />
      {result && (
        <div style={{ marginTop: 12 }}>
          <FeedbackBand
            tone={result.correct ? 'correct' : 'wrong'}
            title={result.correct ? copy.headline_right : copy.headline_wrong}
            detail={
              <span className="rv-evidence" data-evidence="">
                {fill(copy.according_to, { source: name, date: sourceDate(source?.publishedAt ?? '', now) })} :{' '}
                <q lang="fr">{result.evidence.quote}</q>
              </span>
            }
          />
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// RvQuestionDraft
// ---------------------------------------------------------------------------

export type RvQuestionDraftProps = {
  learnerFr: string;
  proposalFr: string;
  contribution: RvSpan[];
  whyNative?: string | null;
  glossLanguage?: string;
  pending?: boolean;
  onSend: (textFr: string) => void;
  copy: RevueCopy;
};

export function RvQuestionDraft({ learnerFr, proposalFr, contribution, whyNative = null, glossLanguage = 'en', pending = false, onSend, copy }: RvQuestionDraftProps) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(proposalFr);
  return (
    <div className="rv-draft">
      <div className="rv-draft__pane" data-who="you">
        <p className="av2-label">{copy.your_version}</p>
        <p className="rv-draft__fr" lang="fr">
          {learnerFr}
        </p>
      </div>
      <div className="rv-draft__pane" data-who="romy">
        <p className="av2-label av2-label--story">{copy.reader_question}</p>
        {editing ? (
          textAnswerField({ label: copy.reader_question, value: text, rows: 2, onChange: setText, disabled: pending })
        ) : (
          <p className="rv-draft__fr" lang="fr">
            <ContributedText text={proposalFr} spans={contribution} label={copy.contribution} />
          </p>
        )}
        {whyNative && !editing && (
          <p className="rv-draft__why" lang={glossLanguage}>
            {whyNative}
          </p>
        )}
      </div>
      <Action tone="primary" pending={pending} pendingLabel={copy.send_desk} disabled={!text.trim()} onClick={() => onSend(editing ? text.trim() : proposalFr)}>
        {copy.send_desk}
      </Action>
      {!editing && (
        <Action tone="secondary" disabled={pending} onClick={() => setEditing(true)}>
          {copy.change_word}
        </Action>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// RvHeadlineWrite (phase 2, B1+)
// ---------------------------------------------------------------------------

export type RvHeadlineWriteProps = {
  maxWords: number;
  /** The server's grading of the last headline sent; null before the first. */
  result: RvWriteResult | null;
  pending?: boolean;
  onSend: (textFr: string) => void;
  copy: RevueCopy;
  initial?: string;
};

/** The FeedbackBand a graded headline gets: the fact fit, in the learner's language. */
export function writeFeedback(result: RvWriteResult, copy: RevueCopy): { tone: 'correct' | 'wrong' | 'neutral'; title: string; detail: string | null } {
  const right = result.evidence.words.filter((word) => word.outcome === 'correct').map((word) => word.fr);
  const detail = right.length ? fill(copy.write_words_right, { words: right.join(', ') }) : null;
  if (!result.accepted || result.evidence.factFit === 'contradicted') return { tone: 'wrong', title: copy.write_contradicted, detail };
  if (result.evidence.factFit === 'supported') return { tone: 'correct', title: copy.write_supported, detail };
  return { tone: 'neutral', title: copy.write_unsupported, detail };
}

export function RvHeadlineWrite({ maxWords, result, pending = false, onSend, copy, initial = '' }: RvHeadlineWriteProps) {
  const [text, setText] = useState(initial);
  const accepted = Boolean(result?.accepted);
  const shown = accepted && result?.made ? result.made.textFr : text;
  const words = headlineWords(shown);
  const tooLong = words > maxWords;
  const feedback = result ? writeFeedback(result, copy) : null;
  const countId = 'rv-write-count';
  return (
    <div className="rv-write" data-accepted={accepted ? '' : undefined}>
      {textAnswerField({
        label: copy.write_label,
        value: shown,
        rows: 2,
        placeholder: copy.write_placeholder,
        disabled: pending || accepted,
        invalid: tooLong,
        describedBy: countId,
        onChange: setText,
      })}
      <p className="rv-write__count" id={countId} data-over={tooLong ? '' : undefined}>
        {tooLong ? fill(copy.write_too_long, { max: maxWords }) : fill(copy.write_words, { n: words, max: maxWords })}
      </p>
      {feedback && (
        <FeedbackBand
          tone={feedback.tone}
          title={feedback.title}
          detail={feedback.detail ? <span className="rv-evidence">{feedback.detail}</span> : undefined}
        />
      )}
      {!accepted && (
        <Action tone="primary" pending={pending} pendingLabel={copy.write_send} disabled={!text.trim() || tooLong} onClick={() => onSend(text.trim())}>
          {copy.write_send}
        </Action>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// RvShortReport (phase 2, B1+)
// ---------------------------------------------------------------------------

export type RvShortReportProps = {
  seconds: number;
  pending?: boolean;
  onSend: (transcript: string, mode: 'voice' | 'text') => void;
  copy: RevueCopy;
  /** Whether a microphone path exists; default: `navigator.mediaDevices.getUserMedia`. */
  voice?: boolean;
};

export function RvShortReport({ seconds, pending = false, onSend, copy, voice: voiceProp }: RvShortReportProps) {
  const voice = useVoiceAnswer();
  const state = voice.state;
  const [text, setText] = useState('');
  const [mode, setMode] = useState<'voice' | 'text'>('voice');
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const hasMic =
    voiceProp ?? (typeof navigator !== 'undefined' && Boolean((navigator as Navigator).mediaDevices?.getUserMedia));
  const micGone = state.kind === 'failed' && (state.reason === 'permission' || state.reason === 'unsupported');
  // Any failure keeps the turn: the text path takes over (WP-27, never a dead end).
  const textOnly = !hasMic || state.kind === 'failed';

  useEffect(() => {
    if (state.kind === 'transcript') {
      setText(state.text);
      setMode('voice');
    }
    if (state.kind === 'recording') {
      // Thirty seconds, then the recorder stops by itself.
      timer.current = setTimeout(() => voice.stop(), seconds * 1000);
    }
    return () => {
      if (timer.current) clearTimeout(timer.current);
      timer.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.kind]);

  const send = () => {
    const value = text.trim();
    if (!value || pending) return;
    onSend(value, textOnly ? 'text' : mode);
  };

  if (textOnly) {
    return (
      <div className="rv-report" data-mode="text">
        {(!hasMic || micGone) && <p className="rv-report__note">{copy.report_no_mic}</p>}
        {textAnswerField({
          label: copy.report_text_label,
          value: text,
          rows: 4,
          placeholder: copy.report_placeholder,
          disabled: pending,
          onChange: (value) => {
            setText(value);
            setMode('text');
          },
        })}
        <Action tone="primary" pending={pending} pendingLabel={copy.report_send} disabled={!text.trim()} onClick={send}>
          {copy.report_send}
        </Action>
      </div>
    );
  }

  if (state.kind === 'recording') {
    return (
      <div className="rv-report" data-mode="recording">
        <div className="rv-report__live" role="status">
          <span className="rv-report__bar" aria-hidden="true">
            <i style={{ animationDuration: `${seconds}s` }} />
          </span>
          <span className="rv-report__label">{copy.report_recording}</span>
          <IconAction label={copy.report_stop} tone="recording" onClick={() => voice.stop()}>
            <StopIcon size={18} />
          </IconAction>
        </div>
      </div>
    );
  }

  if (state.kind === 'transcript' || (state.kind === 'idle' && text)) {
    return (
      <div className="rv-report" data-mode="transcript">
        {textAnswerField({ label: copy.report_label, value: text, rows: 4, disabled: pending, onChange: setText })}
        <Action tone="primary" pending={pending} pendingLabel={copy.report_send} disabled={!text.trim()} onClick={send}>
          {copy.report_send}
        </Action>
        <Action
          tone="secondary"
          disabled={pending}
          onClick={() => {
            setText('');
            voice.reset();
          }}
        >
          {copy.report_again}
        </Action>
      </div>
    );
  }

  return (
    <div className="rv-report" data-mode={state.kind === 'transcribing' ? 'transcribing' : 'idle'}>
      <Action tone="primary" pending={state.kind === 'transcribing' || pending} pendingLabel={copy.transcribing} onClick={() => void voice.start()}>
        <span className="rv-report__go">
          <MicIcon size={18} />
          {fill(copy.report_record, { n: seconds })}
        </span>
      </Action>
    </div>
  );
}

// ---------------------------------------------------------------------------
// RvCaption (WP-119 §8.4 «La légende»)
// ---------------------------------------------------------------------------

export type RvCaptionProps = {
  offer: RvCaptionOffer;
  /** The server's answer: the pick's verdict, or the written caption's grading; null before. */
  result: RvCaptionResult | null;
  /** The caption picked (choice), printed grey until the answer arrives. */
  picked: string | null;
  pending?: boolean;
  onPick: (optionId: string) => void;
  onWrite: (textFr: string) => void;
  /** The plan's gloss support: a picture word carries its gloss unless `none`. */
  glosses?: 'shown' | 'tap' | 'none';
  glossLanguage?: RvLanguage;
  copy: RevueCopy;
};

type Feedback = { tone: 'correct' | 'wrong' | 'neutral'; title: string; detail: string | null };

/** The FeedbackBand a caption gets: the pick's verdict, or a written caption's fact fit. */
export function captionFeedback(result: RvCaptionResult, copy: RevueCopy): Feedback {
  if (result.format === 'choice') {
    return { tone: result.correct ? 'correct' : 'wrong', title: result.correct ? copy.caption_right : copy.caption_wrong, detail: null };
  }
  const right = (result.evidence?.words ?? []).filter((word) => word.outcome === 'correct').map((word) => word.fr);
  const detail = right.length ? fill(copy.write_words_right, { words: right.join(', ') }) : null;
  const fit = result.evidence?.factFit;
  // Refused and not contradicted: under the band's words.
  if (!result.accepted && fit !== 'contradicted') return { tone: 'wrong', title: copy.caption_too_short, detail };
  if (!result.accepted || fit === 'contradicted') return { tone: 'wrong', title: copy.caption_contradicted, detail };
  if (fit === 'supported') return { tone: 'correct', title: copy.caption_supported, detail };
  return { tone: 'neutral', title: copy.caption_unsupported, detail };
}

/**
 * What prints under the picture: the filed caption, else the draft (the pick on its way, or
 * what is typed). `options`: the captions to choose from (the offer's, or a refused try's).
 */
export function captionShown(
  offer: Pick<RvCaptionOffer, 'format' | 'options'>,
  result: RvCaptionResult | null,
  picked: string | null,
  text: string,
  options: RvHeadlineOption[] = offer.options,
): { captionFr: string | null; contribution: RvSpan[]; draft: boolean } {
  if (result?.accepted && result.made) return { captionFr: result.made.textFr, contribution: result.made.contribution, draft: false };
  const option = picked ? options.find((row) => row.id === picked) : null;
  if (option) return { captionFr: option.textFr, contribution: [], draft: true };
  if (offer.format === 'write') return { captionFr: text.trim() || null, contribution: [], draft: true };
  return { captionFr: null, contribution: [], draft: true };
}

export function RvCaption({ offer, result, picked, pending = false, onPick, onWrite, glosses = 'tap', glossLanguage = 'en', copy }: RvCaptionProps) {
  const [text, setText] = useState('');
  // The captions to choose from: a refused try's, else the last ones seen (the offer's on a resume).
  const [seen, setSeen] = useState<RvHeadlineOption[]>(offer.options);
  const fallback = result?.options.length ? result.options : seen;
  useEffect(() => {
    if (result?.options.length) setSeen(result.options);
  }, [result]);
  const field = useRef<HTMLTextAreaElement | null>(null);
  const filed = Boolean(result?.accepted && result.made);
  const shown = captionShown(offer, result, picked, text, fallback);
  const feedback = result ? captionFeedback(result, copy) : null;
  // A pick (only offered after a refused try) turns the screen to the choice.
  const write = offer.format === 'write' && picked === null && result?.format !== 'choice';
  const words = headlineWords(text);
  const tooLong = words > offer.maxWords;
  const countId = 'rv-caption-count';

  const tiles = offer.words.length > 0 && (
    <div className="rv-caption__words">
      <p className="rv-caption__k">{copy.caption_words}</p>
      <ul className="rv-caption__list">
        {offer.words.map((word) => {
          const gloss = glosses !== 'none' && word.gloss ? word.gloss : null;
          const body = (
            <>
              <span className="rv-caption__fr" lang="fr">
                {word.fr}
              </span>
              {gloss && (
                <small className="rv-caption__gloss" lang={glossLanguage}>
                  {gloss}
                </small>
              )}
            </>
          );
          if (!write) {
            return (
              <li key={word.fr} className="rv-caption__word" data-word="">
                {body}
              </li>
            );
          }
          const used = captionUses(filed && result?.made ? result.made.textFr : text, word.fr);
          return (
            <li key={word.fr}>
              <button
                type="button"
                className="av2-tile rv-caption__word"
                data-state={used ? 'placed' : undefined}
                aria-label={used ? `${word.fr}, ${copy.caption_word_used}` : fill(copy.caption_word_add, { word: word.fr })}
                disabled={pending || filed || used}
                onClick={() => {
                  setText((current) => captionInsert(current, word.fr));
                  field.current?.focus();
                }}
              >
                {body}
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );

  if (!write) {
    const choices: ChoiceOption[] = fallback.map((option) => ({
      id: option.id,
      textFr: option.textFr,
      state: result
        ? option.id === result.answerId
          ? 'correct'
          : option.id === picked
            ? 'wrong'
            : 'idle'
        : undefined,
    }));
    return (
      <div className="rv-caption" data-format="choice" data-answered={result ? '' : undefined}>
        <RvPicture url={offer.pictureUrl} captionFr={shown.captionFr} contribution={shown.contribution} draft={shown.draft} copy={copy} />
        {tiles}
        <ChoiceList
          options={choices}
          selectedId={picked}
          label={copy.caption_label}
          disabled={pending || Boolean(result)}
          onSelect={onPick}
          statusLabels={{ selected: copy.status_selected, correct: copy.status_correct, wrong: copy.status_wrong }}
        />
        {feedback && <FeedbackBand tone={feedback.tone} title={feedback.title} />}
      </div>
    );
  }

  return (
    <div className="rv-caption" data-format="write" data-accepted={filed ? '' : undefined}>
      <RvPicture url={offer.pictureUrl} captionFr={shown.captionFr} contribution={shown.contribution} draft={shown.draft} copy={copy} />
      {tiles}
      {!filed && (
        <>
          {textAnswerField({
            label: copy.caption_write_label,
            value: text,
            rows: 2,
            placeholder: copy.caption_placeholder,
            disabled: pending,
            invalid: tooLong,
            describedBy: countId,
            onChange: setText,
            inputRef: field,
          })}
          <p className="rv-write__count" id={countId} data-over={tooLong ? '' : undefined}>
            {tooLong ? fill(copy.write_too_long, { max: offer.maxWords }) : fill(copy.write_words, { n: words, max: offer.maxWords })}
          </p>
        </>
      )}
      {feedback && (
        <FeedbackBand
          tone={feedback.tone}
          title={feedback.title}
          detail={feedback.detail ? <span className="rv-evidence">{feedback.detail}</span> : undefined}
        />
      )}
      {!filed && (
        <Action tone="primary" pending={pending} pendingLabel={copy.caption_send} disabled={!text.trim() || tooLong} onClick={() => onWrite(text.trim())}>
          {copy.caption_send}
        </Action>
      )}
      {!filed && fallback.length > 0 && (
        <div className="rv-caption__or">
          <ChoiceList
            options={fallback.map((option) => ({ id: option.id, textFr: option.textFr }))}
            selectedId={null}
            label={copy.caption_or_pick}
            disabled={pending}
            onSelect={onPick}
            statusLabels={{ selected: copy.status_selected, correct: copy.status_correct, wrong: copy.status_wrong }}
          />
        </div>
      )}
    </div>
  );
}
