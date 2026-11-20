/**
 * «L'intox express» · «Vrai ou faux», «Corrige».
 *
 * «Vrai ou faux»: the five statements one at a time, two big buttons, no timer; the story
 * stays one tap away («Relire l'article»: reading practice, not memory). After each answer
 * the verdict and its line in the learner's language; on a false statement or a miss, the
 * outlet's quote with the words that settle it lit. A running «3 sur 5».
 *
 * «Corrige»: each false statement made true. A1–A2 pick between the true value and another
 * of the same kind from the article; B1+ rewrite the statement. A miss sends the learner back
 * to the quote, never the answer; the second miss shows it.
 */

import React, { useEffect, useState } from 'react';

import { Action, ArrowRightIcon } from '@/components/atelier-v2/ui';
import { textAnswerField } from '@/components/atelier-v2/ui/Choice';

import { quoteSegments } from '../comptoir/comptoir-model';
import { RomyLine } from '../comptoir/RvComptoirParts';
import { fill } from '../revue-copy';
import { RvTranslate } from '../RvThread';
import { INTOX_FR, RUBRIQUE_LINES } from './rubriques-copy';
import { lastAnswered, scoreText, shownCard } from './rubriques-model';
import { FrLine, LeadBlock, SourceQuote, type IntoxStepProps } from './RvRubriqueParts';

/** A statement with its false words struck once it is known to be false. */
function Struck({ textFr, wrongFr }: { textFr: string; wrongFr: string | null }) {
  return (
    <>
      {quoteSegments(textFr, wrongFr).map((segment, index) =>
        segment.wrong ? (
          <s key={index} className="ct-strike">
            {segment.text}
          </s>
        ) : (
          <React.Fragment key={index}>{segment.text}</React.Fragment>
        ),
      )}
    </>
  );
}

export function RvIntoxRound(props: IntoxStepProps) {
  const { session, view, copy, rcopy, glossLanguage, pending, readOnly, onAct, onContinue, notice, footRef } = props;
  const round = view.round!;
  // The verdict stays on screen until «Phrase suivante» (a resume opens on the last one).
  const [seen, setSeen] = useState<string | null>(() => lastAnswered(view));
  const [lead, setLead] = useState(false);
  const card = shownCard(view, seen);
  const busy = readOnly || pending !== null;
  const done = round.current === null;
  const index = card ? round.cards.findIndex((row) => row.key === card.key) : 0;

  const answer = (value: 'vrai' | 'faux') => {
    if (!card) return;
    void onAct({ act: 'answer', key: card.key, value }, `answer-${value}`).then((ok) => ok && setSeen(card.key));
  };

  return (
    <>
      <div className="rv-body ct-body" data-step="round">
        <RomyLine line={RUBRIQUE_LINES.round_ask} props={props} past={round.answered > 0} />
        <p className="ct-hint rb-score" aria-live="polite">
          <span>{rcopy.round_task}</span>
          <b className="rb-score__n">{scoreText(rcopy, view)}</b>
        </p>
        <button type="button" className="rb-reread" aria-expanded={lead} onClick={() => setLead((open) => !open)}>
          {lead ? rcopy.reread_hide : rcopy.reread}
        </button>
        {lead && <LeadBlock read={view.read} props={props} voiceKey={`rb-reread-${session.id}`} />}
        {card && (
          <article className="rb-card" data-key={card.key} data-answered={card.answer ? '' : undefined} data-correct={card.correct === null ? undefined : String(card.correct)}>
            <p className="rb-card__n">
              {index + 1} / {round.total}
            </p>
            {card.answer && card.true === false ? (
              <p className="rb-line__fr rb-card__fr" lang="fr">
                <Struck textFr={card.text.fr} wrongFr={card.wrongFr} />
              </p>
            ) : (
              <FrLine text={card.text} props={props} className="rb-line__fr rb-card__fr" />
            )}
            {card.answer && (
              <div className="ct-fb rb-verdict" data-correct={card.correct ? '' : undefined} data-ct-anchor="nearest">
                <p className="ct-fb__fr">
                  {card.correct ? rcopy.verdict_right : rcopy.verdict_wrong} {card.true ? rcopy.was_true : rcopy.was_false}
                </p>
                {card.why && (
                  <p className="ct-fb__note" lang={glossLanguage === 'fr' ? 'fr' : glossLanguage}>
                    {card.why.tr ?? card.why.fr}
                  </p>
                )}
                {card.quote && <SourceQuote quote={card.quote} />}
              </div>
            )}
          </article>
        )}
        {notice}
      </div>
      {!readOnly && (
        <div className="rv-foot ct-foot" ref={footRef}>
          {card && !card.answer ? (
            <div className="ct-votes rb-votes" role="group">
              <button type="button" className="ct-vote rb-vote" lang="fr" aria-label={`${INTOX_FR.vrai} · ${rcopy.vrai}`} disabled={busy} onClick={() => answer('vrai')}>
                {INTOX_FR.vrai}
              </button>
              <button type="button" className="ct-vote rb-vote" lang="fr" aria-label={`${INTOX_FR.faux} · ${rcopy.faux}`} disabled={busy} onClick={() => answer('faux')}>
                {INTOX_FR.faux}
              </button>
            </div>
          ) : done ? (
            <Action tone="primary" disabled={pending !== null} iconAfter={<ArrowRightIcon size={18} />} onClick={onContinue}>
              {copy.continue}
            </Action>
          ) : (
            <Action tone="primary" disabled={pending !== null} iconAfter={<ArrowRightIcon size={18} />} onClick={() => setSeen(null)}>
              {rcopy.next_statement}
            </Action>
          )}
        </div>
      )}
    </>
  );
}

function FixItem({ item, props }: { item: NonNullable<IntoxStepProps['view']['fix']>['items'][number]; props: IntoxStepProps }) {
  const { view, rcopy, copy, glossLanguage, pending, readOnly, onAct } = props;
  const fix = view.fix!;
  const last = item.attempts[item.attempts.length - 1] ?? null;
  // After a miss the field keeps the learner's sentence to edit (seen at 375 px: it was emptied).
  const [text, setText] = useState(last ?? '');
  useEffect(() => setText(item.attempts[item.attempts.length - 1] ?? ''), [item.tries, item.attempts]);
  const busy = readOnly || pending !== null;
  return (
    <section className="ct-frame rb-fix" data-key={item.key} data-resolved={item.resolved ? '' : undefined} aria-label={rcopy.fix_label}>
      <p className="rb-line__fr" lang="fr">
        <Struck textFr={item.text.fr} wrongFr={item.wrongFr} />
      </p>
      <SourceQuote quote={item.quote} />
      {!item.resolved && fix.input === 'pick' && (
        <div className="ct-opts" role="group" aria-label={rcopy.fix_task_pick}>
          {item.options.map((option) => (
            <button
              key={option}
              type="button"
              className="ct-opt"
              lang="fr"
              data-state={item.attempts.includes(option) ? 'no' : undefined}
              aria-pressed={item.attempts.includes(option)}
              disabled={busy || item.attempts.includes(option)}
              onClick={() => void onAct({ act: 'fix', key: item.key, value: option }, `fix-${item.key}`)}
            >
              {option}
            </button>
          ))}
        </div>
      )}
      {!item.resolved && fix.input === 'write' && (
        <>
          {textAnswerField({ label: rcopy.fix_label, value: text, rows: 2, disabled: busy, onChange: setText })}
          <Action tone="secondary" pending={pending === `fix-${item.key}`} pendingLabel={rcopy.check} disabled={busy || !text.trim()} onClick={() => void onAct({ act: 'fix', key: item.key, text }, `fix-${item.key}`)}>
            {rcopy.check}
          </Action>
        </>
      )}
      {!item.resolved && item.tries > 0 && (
        <p className="ct-why" data-ct-anchor="nearest">
          {fix.input === 'write' && last ? <span lang="fr">« {last} » · </span> : null}
          {rcopy.fix_wrong} {fill(rcopy.try_n, { n: String(item.tries + 1), max: String(item.maxTries) })}
        </p>
      )}
      {item.resolved && (
        <div className="ct-fb" data-correct={item.correct ? '' : undefined} data-ct-anchor="nearest">
          {item.fixed && (
            <p className="ct-fb__fr" lang="fr">
              {item.fixed.fr}
            </p>
          )}
          <p className="ct-fb__note">{item.correct ? rcopy.fix_right : fill(rcopy.fix_shown, { right: item.rightFr ?? '' })}</p>
          {item.fixed && <RvTranslate textFr={item.fixed.fr} translation={item.fixed.tr} glossLanguage={glossLanguage} copy={copy} />}
        </div>
      )}
    </section>
  );
}

export function RvIntoxFix(props: IntoxStepProps) {
  const { view, ccopy, rcopy, pending, readOnly, onContinue, notice, footRef } = props;
  const fix = view.fix!;
  const done = fix.items.every((item) => item.resolved);
  return (
    <>
      <div className="rv-body ct-body" data-step="fix" data-input={fix.input}>
        <RomyLine line={RUBRIQUE_LINES.fix_ask} props={props} />
        <p className="ct-hint">{fix.input === 'pick' ? rcopy.fix_task_pick : rcopy.fix_task_write}</p>
        <p className="ct-frame__k">
          {ccopy.phrase_label} · <span lang="fr">{fix.phrase.fr}</span>
        </p>
        {fix.items.map((item) => (
          <FixItem key={item.key} item={item} props={props} />
        ))}
        {notice}
      </div>
      {!readOnly && done && (
        <div className="rv-foot ct-foot" ref={footRef}>
          <Action tone="primary" pending={pending === 'close'} pendingLabel={ccopy.see_page} disabled={pending !== null} onClick={onContinue}>
            {ccopy.see_page}
          </Action>
        </div>
      )}
    </>
  );
}
