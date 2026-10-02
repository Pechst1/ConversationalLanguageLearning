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
 */

import React, { useState } from 'react';

import { Action, ChoiceList, FeedbackBand, ShapeToken, type ChoiceOption } from '@/components/atelier-v2/ui';
import { textAnswerField } from '@/components/atelier-v2/ui/Choice';
import type { RvHeadlineOption, RvMakeKind, RvPickResult, RvSpan } from '@/lib/revue-types';

import { fill, type RevueCopy } from './revue-copy';
import { ContributedText } from './RvThread';
import { sourceDate } from './revue-model';

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
