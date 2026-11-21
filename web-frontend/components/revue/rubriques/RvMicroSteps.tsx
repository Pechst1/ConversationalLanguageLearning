/**
 * «Le micro» (WIRE §12, 2026-11-21) · «Prépare tes questions», «L'interview», «Tes notes»,
 * «Relis tes questions».
 *
 * «Prépare»: Romy's notes with their holes («Combien ? ___»); the learner chooses the three to
 * go after. «L'interview»: the witness (a regular who was there, in character) and three turns:
 * A1 picks a question tile, A2 starts from a question opener and finishes it, B1+ write. Each
 * question and the witness's line print as an exchange; a shrug says, in the mother tongue,
 * whether the turn counted; the form of a question is never judged here. «Tes notes»: each hole
 * filled from the witness's line (A1–A2 pick, B1+ type), two tries. «Relis tes questions»: the
 * questions, the app's rule for a slip it saw (never the corrected question), Romy's marks, the
 * fix first.
 */

import React, { useEffect, useState } from 'react';

import { Action, ArrowRightIcon, CastPortrait } from '@/components/atelier-v2/ui';
import { textAnswerField } from '@/components/atelier-v2/ui/Choice';
import type { RvMicroView } from '@/lib/revue-rubriques-types';

import { ComptoirBubble, MineLine, RomyLine } from '../comptoir/RvComptoirParts';
import { fill } from '../revue-copy';
import { MICRO_FR, photoMicroCopy, PM_LINES } from './photo-micro-copy';
import { turnNumber } from './photo-micro-model';
import { ProofBlock, ProofFoot } from './RvProofBlock';
import { FrLine, type RubriqueStepProps } from './RvRubriqueParts';

export type MicroStepProps = RubriqueStepProps & { view: RvMicroView };

function Continue({ props }: { props: MicroStepProps }) {
  const { copy, pending, onContinue } = props;
  return (
    <Action tone="primary" disabled={pending !== null} iconAfter={<ArrowRightIcon size={18} />} onClick={onContinue}>
      {copy.continue}
    </Action>
  );
}

/** The witness's line, in their bubble (the counter's), every word tappable, «Traduire», ▶. */
function Witness({ props, id, name, line }: { props: MicroStepProps; id: string; name: string; line: { fr: string; tr: string | null } }) {
  return (
    <ComptoirBubble
      castId={id}
      name={name}
      textFr={line.fr}
      translation={line.tr}
      glosses={props.glosses}
      glossLanguage={props.glossLanguage}
      voice={props.voice}
      voiceKey={`pm-${id}-${line.fr}`}
      copy={props.copy}
      ccopy={props.ccopy}
      onWord={props.wordFor(id, name)}
    />
  );
}

// ---------------------------------------------------------------------------
// «Prépare tes questions»
// ---------------------------------------------------------------------------

export function RvMicroPrepare(props: MicroStepProps) {
  const { view, chrome, glossLanguage, pending, readOnly, onAct, notice, footRef } = props;
  const pm = photoMicroCopy(chrome);
  const prepare = view.prepare!;
  const settled = prepare.chosen.length >= prepare.need;
  const [picked, setPicked] = useState<string[]>(prepare.chosen);
  const busy = readOnly || pending !== null;
  const shown = settled ? prepare.chosen : picked;
  const flip = (key: string) =>
    setPicked((current) => (current.includes(key) ? current.filter((k) => k !== key) : current.length >= prepare.need ? current : [...current, key]));
  return (
    <>
      <div className="rv-body ct-body" data-step="prepare">
        <RomyLine line={PM_LINES.prepare_ask} props={props} past={settled} />
        <p className="ct-hint">{pm.prepare_task}</p>
        <section className="ct-frame rb-notes" aria-label={MICRO_FR.notes}>
          <p className="ct-frame__k" lang="fr">
            {MICRO_FR.notes}
          </p>
          <div className="ct-tiles" role="group" aria-label={pm.prepare_task}>
            {prepare.holes.map((hole) => (
              <button
                key={hole.key}
                type="button"
                className="ct-tile rb-hole"
                aria-pressed={shown.includes(hole.key)}
                disabled={busy || settled || (!shown.includes(hole.key) && shown.length >= prepare.need)}
                onClick={() => flip(hole.key)}
              >
                <span className="ct-tile__fr" lang="fr">
                  {`${hole.hole.fr}\u00a0`}
                  <span aria-hidden="true">___</span>
                </span>
                {hole.hole.tr && (
                  <span className="ct-tile__tr" lang={glossLanguage}>
                    {hole.hole.tr}
                  </span>
                )}
              </button>
            ))}
          </div>
        </section>
        {notice}
      </div>
      {!readOnly && (
        <div className="rv-foot ct-foot" ref={footRef}>
          {settled ? (
            <Continue props={props} />
          ) : (
            <>
              <p className="ct-foot__hint" aria-live="polite">
                {fill(pm.prepare_count, { n: String(picked.length), max: String(prepare.need) })}
              </p>
              <Action tone="primary" pending={pending === 'prepare'} pendingLabel={pm.prepare_send} disabled={busy || picked.length !== prepare.need} onClick={() => void onAct({ act: 'prepare', keys: picked }, 'prepare')}>
                {pm.prepare_send}
              </Action>
            </>
          )}
        </div>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// «L'interview»
// ---------------------------------------------------------------------------

export function RvMicroInterview(props: MicroStepProps) {
  const { view, chrome, glossLanguage, copy, pending, readOnly, onAct, notice, footRef } = props;
  const pm = photoMicroCopy(chrome);
  const px = photoMicroCopy(glossLanguage);
  const interview = view.interview!;
  const [text, setText] = useState('');
  const [tile, setTile] = useState<string | null>(null);
  useEffect(() => {
    setText('');
    setTile(null);
  }, [interview.turns.length]);
  const busy = readOnly || pending !== null;
  const witness = interview.witness;
  const holeOf = (key: string | null) => interview.holes.find((h) => h.key === key) ?? null;
  return (
    <>
      <div className="rv-body ct-body" data-step="interview" data-input={interview.input}>
        <RomyLine line={PM_LINES.interview_ask} props={props} past={interview.done} />
        <p className="ct-hint rb-by">
          <CastPortrait characterId={witness.id} name={witness.nameFr} size="xs" ring />
          <span lang="fr">
            {witness.nameFr}
            {witness.roleFr ? ` · ${witness.roleFr}` : ''}
          </span>
        </p>
        <section className="ct-frame rb-notes" aria-label={MICRO_FR.notes}>
          <p className="ct-frame__k" lang="fr">
            {MICRO_FR.notes}
          </p>
          <ul className="rb-notes__list">
            {interview.holes.map((hole) => (
              <li key={hole.key} className="rb-notes__hole" data-filled={hole.filled ? '' : undefined} lang="fr">
                {hole.hole.fr} {hole.filled ? '✓' : '___'}
              </li>
            ))}
          </ul>
        </section>
        <ol className="rb-exchange">
          {interview.turns.map((turn, index) => {
            const newest = index === interview.turns.length - 1;
            const hole = holeOf(turn.holeKey);
            return (
              <li key={index} className="rb-exchange__turn" data-kind={turn.kind} data-ct-anchor={newest ? 'nearest' : undefined}>
                <MineLine textFr={turn.questionFr} copy={copy} />
                <Witness props={props} id={witness.id} name={witness.nameFr} line={turn.answer} />
                {turn.kind === 'shrug' && (
                  <p className="ct-why" lang={glossLanguage}>
                    {turn.spent ? px.shrug_spent : px.shrug_free}
                  </p>
                )}
                {turn.kind === 'again' && (
                  <p className="ct-why" lang={glossLanguage}>
                    {px.again}
                  </p>
                )}
                {turn.kind === 'answer' && hole && (
                  <p className="ct-hint" lang="fr">
                    {fill(pm.hole_filled, { hole: hole.hole.fr })}
                  </p>
                )}
              </li>
            );
          })}
        </ol>
        {!interview.done && !readOnly && (
          <section className="ct-frame rb-ask" aria-label={pm.ask_label}>
            <p className="ct-frame__k">
              {fill(pm.turns_left, { n: String(turnNumber(view)), max: String(interview.total) })} ·{' '}
              <span lang="fr">{interview.phrase.fr}</span>
            </p>
            {interview.input === 'tiles' ? (
              <>
                <p className="ct-hint">{pm.interview_task_tiles}</p>
                <div className="ct-tiles" role="radiogroup" aria-label={pm.interview_task_tiles}>
                  {interview.tiles.map((row) => (
                    <button key={row.key} type="button" role="radio" className="ct-tile" aria-checked={tile === row.key} disabled={busy} onClick={() => setTile(row.key)}>
                      <span className="ct-tile__fr" lang="fr">
                        {row.text.fr}
                      </span>
                      {row.text.tr && (
                        <span className="ct-tile__tr" lang={glossLanguage}>
                          {row.text.tr}
                        </span>
                      )}
                    </button>
                  ))}
                </div>
              </>
            ) : (
              <>
                <p className="ct-hint">{interview.input === 'frame' ? pm.interview_task_frame : pm.interview_task_free}</p>
                {interview.input === 'frame' && interview.frames.length > 0 && (
                  <div className="ct-bank" role="group" aria-label={pm.frames_label}>
                    {interview.frames.map((frame) => (
                      <button key={frame.fr} type="button" className="ct-bank__b" lang="fr" disabled={busy} onClick={() => setText(`${frame.fr} `)}>
                        {frame.fr}…
                      </button>
                    ))}
                  </div>
                )}
                {textAnswerField({ label: pm.ask_label, value: text, rows: 2, disabled: busy, onChange: setText })}
              </>
            )}
          </section>
        )}
        {notice}
      </div>
      {!readOnly && (
        <div className="rv-foot ct-foot" ref={footRef}>
          {interview.done ? (
            <Continue props={props} />
          ) : interview.input === 'tiles' ? (
            <Action tone="primary" pending={pending === 'ask'} pendingLabel={pm.ask_send} disabled={busy || !tile} onClick={() => tile && void onAct({ act: 'ask', key: tile }, 'ask')}>
              {pm.ask_send}
            </Action>
          ) : (
            <Action tone="primary" pending={pending === 'ask'} pendingLabel={pm.ask_send} disabled={busy || !text.trim()} onClick={() => void onAct({ act: 'ask', text }, 'ask')}>
              {pm.ask_send}
            </Action>
          )}
        </div>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// «Tes notes»
// ---------------------------------------------------------------------------

function NoteItem({ item, props }: { item: NonNullable<RvMicroView['notes']>['items'][number]; props: MicroStepProps }) {
  const { view, chrome, glossLanguage, pending, readOnly, onAct, rcopy } = props;
  const pm = photoMicroCopy(chrome);
  const px = photoMicroCopy(glossLanguage);
  const notes = view.notes!;
  const witness = view.interview?.witness;
  const last = item.attempts[item.attempts.length - 1] ?? '';
  const [text, setText] = useState(last);
  useEffect(() => setText(item.attempts[item.attempts.length - 1] ?? ''), [item.tries, item.attempts]);
  const busy = readOnly || pending !== null;
  return (
    <section className="ct-frame rb-fix" data-key={item.key} data-resolved={item.resolved ? '' : undefined} aria-label={item.hole.fr}>
      <p className="ct-frame__k" lang="fr">
        {item.hole.fr} {item.resolved ? item.valueFr ?? '' : '___'}
      </p>
      {witness ? <Witness props={props} id={witness.id} name={witness.nameFr} line={item.answer} /> : <FrLine text={item.answer} props={props} />}
      {!item.resolved && notes.input === 'pick' && (
        <div className="ct-opts" role="group" aria-label={pm.notes_task_pick}>
          {item.options.map((option) => (
            <button
              key={option}
              type="button"
              className="ct-opt"
              lang="fr"
              data-state={item.attempts.includes(option) ? 'no' : undefined}
              aria-pressed={item.attempts.includes(option)}
              disabled={busy || item.attempts.includes(option)}
              onClick={() => void onAct({ act: 'note', key: item.key, value: option }, `note-${item.key}`)}
            >
              {option}
            </button>
          ))}
        </div>
      )}
      {!item.resolved && notes.input === 'write' && (
        <>
          {textAnswerField({ label: pm.note_label, value: text, rows: 1, disabled: busy, onChange: setText })}
          <Action tone="secondary" pending={pending === `note-${item.key}`} pendingLabel={rcopy.check} disabled={busy || !text.trim()} onClick={() => void onAct({ act: 'note', key: item.key, text }, `note-${item.key}`)}>
            {rcopy.check}
          </Action>
        </>
      )}
      {!item.resolved && item.tries > 0 && (
        <>
          <p className="ct-why" lang={glossLanguage} data-ct-anchor="nearest">
            {notes.input === 'write' && last ? <span lang="fr">« {last} » · </span> : null}
            {px.note_wrong}
          </p>
          <p className="ct-foot__hint">{fill(rcopy.try_n, { n: String(item.tries + 1), max: String(item.maxTries) })}</p>
        </>
      )}
      {item.resolved && (
        <p className="ct-fb__note" data-correct={item.correct ? '' : undefined} data-ct-anchor="nearest">
          {item.correct ? pm.note_right : fill(pm.note_shown, { value: item.valueFr ?? '' })}
        </p>
      )}
    </section>
  );
}

export function RvMicroNotes(props: MicroStepProps) {
  const { view, chrome, readOnly, notice, footRef } = props;
  const pm = photoMicroCopy(chrome);
  const notes = view.notes!;
  const done = notes.items.every((item) => item.resolved);
  return (
    <>
      <div className="rv-body ct-body" data-step="notes" data-input={notes.input}>
        <RomyLine line={PM_LINES.notes_ask} props={props} past={done} />
        <p className="ct-hint">{notes.input === 'pick' ? pm.notes_task_pick : pm.notes_task_write}</p>
        {notes.items.map((item) => (
          <NoteItem key={item.key} item={item} props={props} />
        ))}
        {notice}
      </div>
      {!readOnly && done && (
        <div className="rv-foot ct-foot" ref={footRef}>
          <Continue props={props} />
        </div>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// «Relis tes questions»
// ---------------------------------------------------------------------------

export function RvMicroReview(props: MicroStepProps) {
  const { view, chrome, glossLanguage, pending, readOnly, onAct, notice, footRef } = props;
  const pm = photoMicroCopy(chrome);
  const px = photoMicroCopy(glossLanguage);
  const review = view.review!;
  const sent = review.proof !== null;
  const busy = readOnly || pending !== null;
  return (
    <>
      <div className="rv-body ct-body" data-step="review" data-input={review.input}>
        <RomyLine line={PM_LINES.review_ask} props={props} past={sent} />
        {!sent && (
          <>
            <p className="ct-hint">{review.input === 'tiles' ? pm.review_tiles : pm.review_task}</p>
            <ol className="fl-wire rb-questions" lang="fr">
              {review.questions.map((question, index) => (
                <li key={index} className="fl-wire__row">
                  <span className="fl-wire__fr">{question}</span>
                </li>
              ))}
            </ol>
            {review.hints.length > 0 && (
              <div className="ct-why" lang={glossLanguage}>
                {review.hints.map((hint, index) => (
                  <p key={index}>{fill(hint.code === 'inversion' ? px.hint_inversion : px.hint_question_word, { n: String(hint.index + 1) })}</p>
                ))}
              </div>
            )}
          </>
        )}
        {sent && (
          <ProofBlock
            props={props}
            proof={review.proof}
            draftFr={review.draftFr ?? ''}
            printedFr={review.printedFr}
            marks={review.marks}
            tries={review.tries}
            notes={review.notes}
            tiles={review.input === 'tiles'}
          />
        )}
        {sent && review.proof === 'marked' && review.hints.length > 0 && (
          <div className="ct-why" lang={glossLanguage}>
            {review.hints.map((hint, index) => (
              <p key={index}>{fill(hint.code === 'inversion' ? px.hint_inversion : px.hint_question_word, { n: String(hint.index + 1) })}</p>
            ))}
          </div>
        )}
        {notice}
      </div>
      {!readOnly && (
        <div className="rv-foot ct-foot" ref={footRef}>
          {!sent ? (
            <Action tone="primary" pending={pending === 'review'} pendingLabel={pm.review_send} disabled={busy} onClick={() => void onAct({ act: 'review' }, 'review')}>
              {pm.review_send}
            </Action>
          ) : (
            <ProofFoot props={props} proof={review.proof} draftFr={review.draftFr ?? ''} tries={review.tries} maxTries={review.maxTries} fixAct="review_fix" />
          )}
        </div>
      )}
    </>
  );
}
