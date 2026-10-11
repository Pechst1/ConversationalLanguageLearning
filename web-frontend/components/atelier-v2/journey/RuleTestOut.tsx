/**
 * SPEED-3 — «Je connais déjà — vérifier», inside the Règle step.
 *
 * Three items of the forge's «Épreuve de la règle» (`short`), drawn with the
 * journey's own inputs and graded by the server, without leaving the day. The
 * parent learns the outcome: `passed` (the unit is held), `failed` (read the
 * card — the answers already counted), or `unavailable` (the check could not
 * start or broke off: read the card).
 */

import React, { useEffect, useRef, useState } from 'react';

import { Action, ChoiceList, FeedbackBand, WordTiles, textAnswerField, type ChoiceOption } from '@/components/atelier-v2/ui';
import { frenchSpacing } from '@/lib/french-typography';
import { apiService, type AtelierForgeNext, type AtelierForgeTestOutResult, type AtelierForgeView } from '@/services/api';
import type { ControlLanguage } from '@/types/daily-journey';

import {
  ruleTestOutCopy,
  testOutAnswerReady,
  testOutInput,
  testOutOutcome,
  testOutProgress,
  testOutPrompt,
  testOutSubmission,
  testOutView,
  type RuleTestOutCopy,
} from './rule-test-out';

export type RuleTestOutEnd =
  | { outcome: 'passed'; result: AtelierForgeTestOutResult }
  | { outcome: 'failed'; result: AtelierForgeTestOutResult }
  | { outcome: 'unavailable' };

type Feedback = { correct: boolean; expected: string | null };

/** One item, drawn: the goal, the French line, the input, the verdict. */
export function RuleTestOutItem({
  next,
  view,
  copy,
  language,
  answer,
  feedback,
  pending,
  onAnswer,
  onCheck,
  onNext,
}: {
  next: AtelierForgeNext;
  view: AtelierForgeView | null;
  copy: RuleTestOutCopy;
  language: ControlLanguage;
  answer: string | string[];
  feedback: Feedback | null;
  pending: boolean;
  onAnswer: (answer: string | string[]) => void;
  onCheck: () => void;
  onNext: () => void;
}) {
  const input = testOutInput(next);
  const prompt = testOutPrompt(next, language);
  const { position, length } = testOutProgress(view);
  const eyebrow = copy.eyebrow.replace('{i}', String(position)).replace('{n}', String(length));
  const locked = pending || feedback !== null;
  const last = position >= length;

  let field: React.ReactNode = null;
  if (input.kind === 'choice') {
    const chosen = typeof answer === 'string' ? answer : '';
    const options: ChoiceOption[] = input.options.map((option) => ({
      id: option,
      textFr: option,
      state:
        feedback && option === chosen ? (feedback.correct ? 'correct' : 'wrong') : option === chosen ? 'selected' : 'idle',
    }));
    field = (
      <ChoiceList
        options={options}
        selectedId={chosen || null}
        label={copy.options_label}
        disabled={locked}
        onSelect={(id) => onAnswer(id)}
        statusLabels={{ selected: copy.status_selected, correct: copy.status_correct, wrong: copy.status_wrong }}
      />
    );
  } else if (input.kind === 'tiles') {
    const placed = Array.isArray(answer) ? answer : [];
    const options: ChoiceOption[] = input.tokens.map((token, index) => ({ id: `t${index}`, textFr: token }));
    field = (
      <WordTiles
        options={options}
        placed={placed}
        label={copy.tiles_label}
        emptyHint={copy.tiles_hint}
        removeLabel={copy.tiles_remove}
        disabled={locked}
        onPlace={(id) => onAnswer([...placed, id])}
        onRemoveLast={() => onAnswer(placed.slice(0, -1))}
        verdict={feedback ? (feedback.correct ? 'correct' : 'wrong') : null}
        verdictLabel={feedback ? (feedback.correct ? copy.status_correct : copy.status_wrong) : undefined}
      />
    );
  } else {
    field = textAnswerField({
      label: copy.answer_label,
      value: typeof answer === 'string' ? answer : '',
      disabled: locked,
      rows: next.round === 'transform' ? 2 : 3,
      onChange: (value) => onAnswer(value),
    });
  }

  return (
    <section className="av2-stack av2-step" data-step="rule" data-check="item" data-round={next.round}>
      <p className="av2-label av2-label--story">{eyebrow}</p>
      {prompt.goal ? <p className="av2-body">{prompt.goal}</p> : null}
      {prompt.lineFr ? (
        <p className="av2-headline" lang="fr">
          {frenchSpacing(prompt.lineFr)}
        </p>
      ) : null}
      {input.kind === 'text' && input.sourceFr ? (
        <p className="av2-headline" lang="fr">
          {frenchSpacing(input.sourceFr)}
        </p>
      ) : null}
      {field}
      {feedback ? (
        <FeedbackBand
          tone={feedback.correct ? 'correct' : 'wrong'}
          title={feedback.correct ? copy.right : copy.not_quite}
          detail={
            !feedback.correct && feedback.expected ? (
              <span lang="fr">{copy.expected.replace('{answer}', frenchSpacing(feedback.expected))}</span>
            ) : undefined
          }
        />
      ) : null}
      {feedback ? (
        <Action tone="primary" onClick={onNext}>
          {last ? copy.finish : copy.next}
        </Action>
      ) : (
        <Action
          tone="primary"
          pending={pending}
          pendingLabel={copy.check}
          disabled={!testOutAnswerReady(input, answer)}
          onClick={onCheck}
        >
          {copy.check}
        </Action>
      )}
    </section>
  );
}

function expectedOf(next: AtelierForgeNext, correction: Record<string, any> | undefined): string | null {
  const item = (next.item || {}) as Record<string, unknown>;
  if (next.round === 'conversation' || next.round === 'sentence') return null;
  const value = item.correct_answer ?? item.expected_answer ?? correction?.corrected_answer;
  return typeof value === 'string' && value.trim() ? value.trim() : null;
}

/**
 * The check itself: starts the short épreuve on mount, serves its items, and
 * reports the end. `onCancel` returns to the card without waiting.
 */
export function RuleTestOut({
  conceptId,
  language,
  onEnd,
  onCancel,
}: {
  conceptId: number;
  language: ControlLanguage;
  onEnd: (end: RuleTestOutEnd) => void;
  onCancel: () => void;
}) {
  const copy = ruleTestOutCopy(language);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [view, setView] = useState<AtelierForgeView | null>(null);
  const [shown, setShown] = useState<AtelierForgeNext | null>(null);
  const [answer, setAnswer] = useState<string | string[]>('');
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [pending, setPending] = useState(false);
  const ended = useRef(false);

  const end = (value: RuleTestOutEnd) => {
    if (ended.current) return;
    ended.current = true;
    onEnd(value);
  };

  useEffect(() => {
    let live = true;
    apiService
      .startForgeTestOut(conceptId, { short: true, source: 'journey' })
      .then((started) => {
        if (!live) return;
        const forge = testOutView(started.forge);
        if (!forge?.next) {
          end({ outcome: 'unavailable' });
          return;
        }
        setSessionId(started.session_id);
        setView(forge);
        setShown(forge.next);
      })
      .catch(() => {
        if (live) end({ outcome: 'unavailable' });
      });
    return () => {
      live = false;
    };
    // The check starts once per mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conceptId]);

  const check = async () => {
    if (!sessionId || !shown || pending) return;
    setPending(true);
    try {
      const input = testOutInput(shown);
      // Tiles are placed by id (a bank may hold «,» twice); the forge takes the words.
      const given =
        input.kind === 'tiles' && Array.isArray(answer)
          ? answer.map((id) => input.tokens[Number(id.slice(1))] ?? '').filter(Boolean)
          : answer;
      const response = await apiService.submitAtelierAttempt(sessionId, testOutSubmission(shown, given));
      const forge = testOutView(response.forge);
      setView(forge);
      setFeedback({ correct: response.verdict === 'correct', expected: expectedOf(shown, response.correction) });
    } catch {
      end({ outcome: 'unavailable' });
    } finally {
      setPending(false);
    }
  };

  const advance = () => {
    const outcome = testOutOutcome(view);
    if (outcome !== 'running' && view?.result) {
      end({ outcome, result: view.result });
      return;
    }
    if (!view?.next) {
      end({ outcome: 'unavailable' });
      return;
    }
    setShown(view.next);
    setAnswer('');
    setFeedback(null);
  };

  if (!shown) {
    return (
      <section className="av2-stack av2-step" data-step="rule" data-check="starting" aria-busy="true">
        <p className="av2-body">{copy.starting}</p>
        <Action tone="quiet" onClick={onCancel}>
          {copy.cancel}
        </Action>
      </section>
    );
  }
  return (
    <RuleTestOutItem
      next={shown}
      view={view}
      copy={copy}
      language={language}
      answer={answer}
      feedback={feedback}
      pending={pending}
      onAnswer={setAnswer}
      onCheck={check}
      onNext={advance}
    />
  );
}
