/**
 * «Le fil» · «Raconter»: the story in two sentences, with the phrase of the day.
 *
 * A1: twice a sequence word and a moment (the dispatches' own fragments): the sentence
 * builds as the learner taps and is correct by construction (no model call); an
 * impossible order is refused with its reason. A2: the two frames, each with its field.
 * B1+: free text with at least two sequence words (the count shows as they type).
 *
 * From A2 Romy marks, the learner fixes, as at the counter: the marks sit on the
 * learner's own words with the kind of slip (never the answer), the field holds the
 * sentence to fix, «Corrige-le, Romy» after one try. With «Le pourquoi» on, the marks are
 * the counter's (`RvProofMarks`: each opens its rule, never the answer) and the settled
 * telling carries its notes (`RvProofNotes`). Once settled, what prints and how
 * it got there; then «Voir la page» (the close).
 */

import React, { useState } from 'react';

import { Action } from '@/components/atelier-v2/ui';
import { textAnswerField } from '@/components/atelier-v2/ui/Choice';

import { COMPTOIR_FR, COMPTOIR_LINES, inPaperLabel } from '../comptoir/comptoir-copy';
import { wordDiff } from '../comptoir/comptoir-model';
import { MineLine, RomyLine } from '../comptoir/RvComptoirParts';
import { RvProofMarks } from '../comptoir/RvProofMarks';
import { RvProofNotes } from '../comptoir/RvProofNotes';
import { fill } from '../revue-copy';
import { RvComposer } from '../RvComposer';
import { RvTranslate } from '../RvThread';
import { FIL_FR, FIL_LINES } from './fil-copy';
import { a1Telling, connectorsUsed, wordCount } from './fil-model';
import type { FilStepProps } from './RvFilSteps';

export function RvFilTell(props: FilStepProps) {
  const { view, copy, ccopy, fcopy, glossLanguage, pending, readOnly, onAct, onContinue, notice, footRef } = props;
  const tell = view.tell!;
  const [parts, setParts] = useState<Array<string | null>>([null, null, null, null]);
  const [texts, setTexts] = useState<string[]>(['', '']);
  const [text, setText] = useState('');
  const busy = readOnly || pending !== null;
  const told = tell.proof !== null;
  const byId = new Map(tell.connectors.map((connector) => [connector.id, connector]));
  const tileOf = (key: string | null) => tell.tiles.find((tile) => tile.key === key)?.text.fr ?? null;

  let composer: React.ReactNode = null;
  let ready = false;
  let send: () => void = () => undefined;
  if (!told && tell.input === 'tiles') {
    const built = a1Telling(byId.get(parts[0] ?? '') ?? null, tileOf(parts[1]), byId.get(parts[2] ?? '') ?? null, tileOf(parts[3]));
    ready = parts.every(Boolean);
    send = () => void onAct({ act: 'tell', parts: parts as string[] }, 'tell');
    const setPart = (at: number, value: string) => setParts((current) => current.map((row, index) => (index === at ? value : row)));
    composer = (
      <>
        {[0, 1].map((n) => (
          <section key={n} className="ct-frame fl-build" aria-label={fill(fcopy.sentence_n, { n: String(n + 1) })}>
            <p className="ct-frame__k">{fill(fcopy.sentence_n, { n: String(n + 1) })}</p>
            <div className="ct-bank" role="radiogroup" aria-label={fcopy.word_label}>
              {tell.connectors.map((connector) => (
                <button key={connector.id} type="button" role="radio" className="ct-bank__b" lang="fr" aria-checked={parts[n * 2] === connector.id} disabled={busy} onClick={() => setPart(n * 2, connector.id)}>
                  {connector.fr}
                </button>
              ))}
            </div>
            <div className="ct-tiles" role="radiogroup" aria-label={fcopy.event_label}>
              {tell.tiles.map((tile) => (
                <button key={tile.key} type="button" role="radio" className="ct-tile" aria-checked={parts[n * 2 + 1] === tile.key} disabled={busy} onClick={() => setPart(n * 2 + 1, tile.key)}>
                  <span className="ct-tile__fr" lang="fr">
                    {tile.text.fr}
                  </span>
                  {tile.text.tr && (
                    <span className="ct-tile__tr" lang={glossLanguage}>
                      {tile.text.tr}
                    </span>
                  )}
                </button>
              ))}
            </div>
          </section>
        ))}
        <div className="ct-frame" aria-live="polite">
          <p className="ct-frame__k">
            {ccopy.phrase_label} · <span lang="fr">{tell.phrase.fr}</span>
          </p>
          <p className="ct-frame__fr" lang="fr" data-built={built ? '' : undefined}>
            {built || '…'}
          </p>
        </div>
      </>
    );
  } else if (!told && tell.input === 'frames') {
    ready = texts.every((value) => wordCount(value) >= 2) && wordCount(texts.join(' ')) >= tell.minWords;
    send = () => void onAct({ act: 'tell', texts }, 'tell');
    composer = (
      <div className="ct-frame" data-input="frame">
        <p className="ct-frame__k">
          {ccopy.phrase_label} · <span lang="fr">{tell.phrase.fr}</span>
        </p>
        {tell.frames.map((frame, index) => (
          <React.Fragment key={index}>
            <p className="ct-frame__fr" lang="fr">
              {frame.fr}…
            </p>
            {textAnswerField({
              label: fill(fcopy.sentence_n, { n: String(index + 1) }),
              value: texts[index] ?? '',
              rows: 2,
              disabled: busy,
              onChange: (value) => setTexts((current) => current.map((row, at) => (at === index ? value : row))),
            })}
          </React.Fragment>
        ))}
      </div>
    );
  } else if (!told) {
    const used = connectorsUsed(text, tell.connectors);
    ready = wordCount(text) >= tell.minWords && used.length >= tell.minConnectors;
    send = () => void onAct({ act: 'tell', text }, 'tell');
    composer = (
      <div className="ct-frame" data-input="free">
        <p className="ct-frame__k">
          {ccopy.phrase_label} · <span lang="fr">{tell.phrase.fr}</span>
        </p>
        <p className="ct-hint">{fill(fcopy.tell_task_free, { n: String(tell.minConnectors) })}</p>
        <div className="ct-words" lang="fr">
          {tell.connectors.map((connector) => (
            <span key={connector.id} title={connector.tr ?? undefined}>
              {connector.fr}
            </span>
          ))}
        </div>
        {textAnswerField({ label: FIL_FR.tell_label, value: text, rows: 4, disabled: busy, placeholder: fcopy.tell_placeholder, onChange: setText })}
        <p className="ct-foot__hint" aria-live="polite">
          {fill(fcopy.connectors_count, { n: String(used.length), min: String(tell.minConnectors) })}
        </p>
      </div>
    );
  }

  // --- once told: Romy's marks, or what prints -------------------------------------
  let suite: React.ReactNode = null;
  const marked = tell.proof === 'marked';
  const draft = tell.draftFr ?? tell.learnerFr ?? '';
  if (told && marked) {
    suite = (
      <>
        <RomyLine line={COMPTOIR_LINES.proof_marked} props={props} anchor="start" />
        <section className="ct-paper" data-proof="marked" aria-label={COMPTOIR_FR.proof_marked}>
          <p className="ct-paper__k" lang="fr">
            {COMPTOIR_FR.proof_marked}
          </p>
          <RvProofMarks
            key={`marks-${tell.tries}`}
            draftFr={draft}
            marks={tell.marks}
            kindLabels={ccopy.mark_kinds}
            copy={ccopy.pourquoi}
            whyLanguage={glossLanguage}
            idPrefix="fl"
          />
        </section>
      </>
    );
  } else if (told && tell.proof) {
    const printed = tell.printedFr ?? draft;
    const label = inPaperLabel(tell.proof, tell.input === 'tiles');
    suite = (
      <section className="ct-paper" data-ct-anchor="start" data-proof={tell.proof} aria-label={label}>
        <p className="ct-paper__k" lang="fr">
          {label}
        </p>
        <p className="ct-paper__fr" lang="fr">
          {tell.proof === 'corrected'
            ? wordDiff(draft, printed).map((segment, index) =>
                segment.changed ? (
                  <mark key={index} className="ct-fix">
                    {segment.text}
                  </mark>
                ) : (
                  <React.Fragment key={index}>{segment.text}</React.Fragment>
                ),
              )
            : printed}
        </p>
        <RvTranslate textFr={printed} glossLanguage={glossLanguage} copy={copy} />
        <RvProofNotes notes={tell.notes} kindLabels={ccopy.mark_kinds} copy={ccopy.pourquoi} whyLanguage={glossLanguage} />
      </section>
    );
  }

  let foot: React.ReactNode;
  if (!told) {
    foot = (
      <>
        {!ready && tell.input !== 'free' && <p className="ct-foot__hint">{tell.input === 'tiles' ? fcopy.tell_task_tiles : fcopy.tell_task_frames}</p>}
        <Action tone="primary" pending={pending === 'tell'} pendingLabel={fcopy.tell_send} disabled={!ready || busy} onClick={send}>
          {fcopy.tell_send}
        </Action>
      </>
    );
  } else if (marked) {
    const tryNumber = Math.min(tell.tries + 1, tell.maxTries);
    foot = (
      <>
        <p className="ct-foot__hint">{fill(ccopy.fix_try, { n: String(tryNumber), max: String(tell.maxTries) })}</p>
        <RvComposer
          key={`fix-${tell.tries}`}
          initial={draft}
          label={ccopy.fix_label}
          placeholder={ccopy.fix_placeholder}
          disabled={busy}
          onSend={(value, how) => void onAct({ act: 'tell_fix', text: value, mode: how }, 'fix')}
          copy={copy}
        />
        {tell.tries >= 1 && (
          <Action tone="quiet" pending={pending === 'romy'} pendingLabel={ccopy.fix_romy} disabled={busy} onClick={() => void onAct({ act: 'tell_fix', value: 'romy' }, 'romy')}>
            {ccopy.fix_romy}
          </Action>
        )}
      </>
    );
  } else {
    foot = (
      <Action tone="primary" pending={pending === 'close'} pendingLabel={ccopy.see_page} disabled={busy} onClick={onContinue}>
        {ccopy.see_page}
      </Action>
    );
  }

  return (
    <>
      <div className="rv-body ct-body" data-step="tell" data-input={tell.input}>
        <RomyLine line={FIL_LINES.tell_ask} props={props} past={told} />
        {told && tell.learnerFr && <MineLine textFr={tell.learnerFr} copy={copy} />}
        {composer}
        {suite}
        {notice}
      </div>
      {!readOnly && (
        <div className="rv-foot ct-foot" ref={footRef}>
          {foot}
        </div>
      )}
    </>
  );
}

export default RvFilTell;
