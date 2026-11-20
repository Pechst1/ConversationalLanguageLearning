/**
 * «Le titre» · «Trois titres», «Le piège», «À toi».
 *
 * «Trois titres»: Gus proposes three headlines (he exaggerates by character, so who says it
 * gives nothing away); the learner picks the honest one. A wrong pick shows that headline's
 * why in the learner's language with the claim that settles it, never the solution; the
 * second wrong pick shows the honest one. Two tries at most.
 *
 * «Le piège»: the exaggerated headline, each word a button; the learner taps the words that
 * say too much. A miss names the tapped words the article does say; the second shows them.
 *
 * «À toi»: A1 builds from a subject tile and a fact tile (correct by construction); A2
 * completes the frame; B1+ write freely (≤ 12 words). Never the words that said too much
 * (said before sending). From A2 Romy marks, the learner fixes, as in «Le fil» (with «Le
 * pourquoi» on, each mark opens its rule, never the answer, and the settled headline carries
 * its notes); then «Voir la page».
 */

import React, { useEffect, useState } from 'react';

import { Action, ArrowRightIcon, CastPortrait } from '@/components/atelier-v2/ui';
import { textAnswerField } from '@/components/atelier-v2/ui/Choice';

import { COMPTOIR_FR, COMPTOIR_LINES, inPaperLabel } from '../comptoir/comptoir-copy';
import { wordDiff } from '../comptoir/comptoir-model';
import { MineLine, RomyLine } from '../comptoir/RvComptoirParts';
import { RvProofMarks } from '../comptoir/RvProofMarks';
import { RvProofNotes } from '../comptoir/RvProofNotes';
import { papierCopy } from '../papier/papier-copy';
import { PpDeleatur, PpPencilLoop, PpStrike } from '../papier/PapierPrint';
import { fill } from '../revue-copy';
import { RvComposer } from '../RvComposer';
import { RvClaim, RvTranslate } from '../RvThread';
import { RUBRIQUE_LINES } from './rubriques-copy';
import { a1Headline, fineWords, saysTooMuch, toggle, wordCount } from './rubriques-model';
import { FrLine, type TitreStepProps } from './RvRubriqueParts';

function Continue({ props }: { props: TitreStepProps }) {
  const { copy, pending, onContinue } = props;
  return (
    <Action tone="primary" disabled={pending !== null} iconAfter={<ArrowRightIcon size={18} />} onClick={onContinue}>
      {copy.continue}
    </Action>
  );
}

// ---------------------------------------------------------------------------
// «Trois titres»
// ---------------------------------------------------------------------------

export function RvTitreThree(props: TitreStepProps) {
  const { session, view, rcopy, xcopy, glossLanguage, glosses, copy, pending, readOnly, onAct, wordFor, notice, footRef } = props;
  const pcopy = papierCopy(props.chrome);
  const three = view.three!;
  const [chosen, setChosen] = useState<string | null>(null);
  useEffect(() => setChosen(null), [three.tries]);
  const busy = readOnly || pending !== null;
  const lastWrong = !three.resolved && three.picked.length ? three.headlines.find((h) => h.key === three.picked[three.picked.length - 1]) : null;
  return (
    <>
      <div className="rv-body ct-body" data-step="three">
        <RomyLine line={RUBRIQUE_LINES.three_ask} props={props} />
        <p className="ct-hint rb-by">
          <CastPortrait characterId={three.by.id} name={three.by.nameFr} size="xs" ring />
          <span>{fill(rcopy.three_proposes, { name: three.by.nameFr })}</span>
        </p>
        {!three.resolved && <p className="ct-hint">{rcopy.three_task}</p>}
        <ol className="fl-strips rb-heads" role="radiogroup" aria-label={rcopy.three_task}>
          {three.headlines.map((headline) => {
            const tried = three.picked.includes(headline.key);
            const honest = three.resolved && headline.key === three.solution;
            return (
              <li key={headline.key} className="fl-strip rb-head" data-role={headline.role ?? undefined} data-tried={tried && !honest ? '' : undefined} data-honest={honest ? '' : undefined}>
                <button
                  type="button"
                  role="radio"
                  className="fl-strip__n"
                  aria-checked={chosen === headline.key || honest}
                  aria-label={headline.text.fr}
                  disabled={busy || three.resolved || tried}
                  onClick={() => setChosen(headline.key)}
                >
                  {headline.key.toUpperCase()}
                </button>
                <div className="fl-strip__text">
                  <FrLine
                    text={headline.text}
                    props={props}
                    className="fl-strip__fr rb-headline"
                    overlay={
                      // The learner's grease pencil round the proof they pick (and round the honest one
                      // once the loop has settled it); a refused proof is struck. Never before the loop says so.
                      honest || (chosen === headline.key && !tried) ? (
                        <PpPencilLoop seed={`${session.id}:${headline.key}`} label={honest ? pcopy.kept : pcopy.your_pick} still={readOnly} />
                      ) : tried && !honest ? (
                        <PpStrike label={pcopy.refused} />
                      ) : null
                    }
                  />
                  {headline.role && <span className="rb-head__role">{rcopy.role[headline.role]}</span>}
                </div>
                {headline === lastWrong && (
                  <p className="ct-why" lang={glossLanguage}>
                    {xcopy.three_wrong}
                  </p>
                )}
                {headline.why && (tried || three.resolved) && (
                  <p className="ct-why" lang={headline.why.tr ? glossLanguage : 'fr'} data-ct-anchor={headline === lastWrong ? 'nearest' : undefined}>
                    {headline.why.tr ?? headline.why.fr}
                  </p>
                )}
                {headline.claim && headline === lastWrong && (
                  <RvClaim claim={headline.claim} support={session.plan.support} glosses={glosses} band={session.plan.band} glossLanguage={glossLanguage} copy={copy} onWord={wordFor(null)} />
                )}
              </li>
            );
          })}
        </ol>
        {three.resolved && (
          <p className="ct-why" data-ct-anchor="nearest">
            {three.correct ? rcopy.three_right : rcopy.three_shown}
          </p>
        )}
        {notice}
      </div>
      {!readOnly && (
        <div className="rv-foot ct-foot" ref={footRef}>
          {three.resolved ? (
            <Continue props={props} />
          ) : (
            <>
              <p className="ct-foot__hint">{fill(rcopy.try_n, { n: String(three.tries + 1), max: String(three.maxTries) })}</p>
              <Action tone="primary" pending={pending === 'pick'} pendingLabel={rcopy.check} disabled={busy || !chosen} onClick={() => chosen && void onAct({ act: 'pick', key: chosen }, 'pick')}>
                {rcopy.check}
              </Action>
            </>
          )}
        </div>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// «Le piège»
// ---------------------------------------------------------------------------

export function RvTitreTrap(props: TitreStepProps) {
  const { session, view, rcopy, xcopy, glossLanguage, glosses, copy, pending, readOnly, onAct, wordFor, notice, footRef } = props;
  const pcopy = papierCopy(props.chrome);
  const trap = view.trap!;
  const [picked, setPicked] = useState<number[]>([]);
  useEffect(() => setPicked([]), [trap.tries]);
  const busy = readOnly || pending !== null;
  const lit = trap.resolved ? trap.solution : picked;
  return (
    <>
      <div className="rv-body ct-body" data-step="trap">
        <RomyLine line={RUBRIQUE_LINES.trap_ask} props={props} />
        {!trap.resolved && <p className="ct-hint">{rcopy.trap_task}</p>}
        <p className="rb-trap" lang="fr" role="group" aria-label={rcopy.trap_task}>
          {trap.words.map((word) => (
            <button
              key={word.index}
              type="button"
              className="rb-trap__w"
              aria-pressed={lit.includes(word.index)}
              data-fine={!trap.resolved && trap.fine.includes(word.index) ? '' : undefined}
              data-wrong={trap.resolved && trap.solution.includes(word.index) ? '' : undefined}
              disabled={busy || trap.resolved}
              onClick={() => setPicked((current) => toggle(current, word.index))}
            >
              {word.fr}
              {/* The proofreader's delete mark on a word the learner strikes (the solution's only once settled); «stet» on one the article does say. */}
              {lit.includes(word.index) && <PpDeleatur />}
              {lit.includes(word.index) && <span className="av2-sr"> · {pcopy.deleatur}</span>}
              {!trap.resolved && trap.fine.includes(word.index) && <span className="av2-sr"> · {pcopy.stet}</span>}
            </button>
          ))}
        </p>
        <RvTranslate textFr={trap.headline.fr} translation={trap.headline.tr} glossLanguage={glossLanguage} copy={copy} />
        {!trap.resolved && trap.fine.length > 0 && (
          <p className="ct-why" lang={glossLanguage} data-ct-anchor="nearest">
            {fill(xcopy.trap_fine, { words: fineWords(view) })}
          </p>
        )}
        {trap.resolved && (
          <>
            <p className="ct-why" data-ct-anchor="nearest">
              {trap.correct ? rcopy.trap_right : rcopy.trap_shown}
            </p>
            {trap.why && (
              <p className="ct-why" lang={trap.why.tr ? glossLanguage : 'fr'}>
                {trap.why.tr ?? trap.why.fr}
              </p>
            )}
            {trap.claim && (
              <RvClaim claim={trap.claim} support={session.plan.support} glosses={glosses} band={session.plan.band} glossLanguage={glossLanguage} copy={copy} onWord={wordFor(null)} />
            )}
          </>
        )}
        {notice}
      </div>
      {!readOnly && (
        <div className="rv-foot ct-foot" ref={footRef}>
          {trap.resolved ? (
            <Continue props={props} />
          ) : (
            <>
              <p className="ct-foot__hint">{fill(rcopy.try_n, { n: String(trap.tries + 1), max: String(trap.maxTries) })}</p>
              <Action tone="primary" pending={pending === 'trap'} pendingLabel={rcopy.check} disabled={busy || picked.length === 0} onClick={() => void onAct({ act: 'trap', words: picked }, 'trap')}>
                {rcopy.check}
              </Action>
            </>
          )}
        </div>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// «À toi»
// ---------------------------------------------------------------------------

export function RvTitreBuild(props: TitreStepProps) {
  const { view, copy, ccopy, rcopy, xcopy, glossLanguage, pending, readOnly, onAct, onContinue, notice, footRef } = props;
  const build = view.build!;
  const [subject, setSubject] = useState<number | null>(null);
  const [fact, setFact] = useState<number | null>(null);
  const [text, setText] = useState('');
  const busy = readOnly || pending !== null;
  const told = build.proof !== null;
  const avoid = fill(rcopy.build_avoid, { avoid: build.avoidFr });

  let composer: React.ReactNode = null;
  let ready = false;
  let tooMuch = false;
  let send: () => void = () => undefined;
  if (!told && build.input === 'tiles') {
    const built = a1Headline(subject === null ? null : build.subjects[subject]?.fr ?? null, fact === null ? null : build.facts[fact]?.fr ?? null);
    ready = subject !== null && fact !== null;
    send = () => void onAct({ act: 'build', parts: [subject as number, fact as number] }, 'build');
    const tiles = (rows: typeof build.subjects, value: number | null, set: (n: number) => void, label: string) => (
      <div className="ct-tiles" role="radiogroup" aria-label={label}>
        {rows.map((tile, index) => (
          <button key={index} type="button" role="radio" className="ct-tile" aria-checked={value === index} disabled={busy} onClick={() => set(index)}>
            <span className="ct-tile__fr" lang="fr">
              {tile.fr}
            </span>
            {tile.tr && (
              <span className="ct-tile__tr" lang={glossLanguage}>
                {tile.tr}
              </span>
            )}
          </button>
        ))}
      </div>
    );
    composer = (
      <section className="ct-frame rb-build" aria-label={rcopy.build_label}>
        <p className="ct-frame__k">{rcopy.subject_label}</p>
        {tiles(build.subjects, subject, setSubject, rcopy.subject_label)}
        <p className="ct-frame__k">{rcopy.fact_label}</p>
        {tiles(build.facts, fact, setFact, rcopy.fact_label)}
        <p className="ct-frame__k">
          {ccopy.phrase_label} · <span lang="fr">{build.phrase.fr}</span>
        </p>
        <p className="ct-frame__fr rb-headline" lang="fr" aria-live="polite" data-built={built ? '' : undefined}>
          {built || '…'}
        </p>
      </section>
    );
  } else if (!told) {
    const full = build.input === 'frame' && build.frame ? `${build.frame.fr} ${text}` : text;
    const count = wordCount(full);
    tooMuch = saysTooMuch(full, build.avoidFr);
    ready = wordCount(text) >= 1 && count >= 3 && count <= build.maxWords && !tooMuch;
    send = () => void onAct({ act: 'build', text }, 'build');
    composer = (
      <div className="ct-frame" data-input={build.input}>
        <p className="ct-frame__k">
          {ccopy.phrase_label} · <span lang="fr">{build.phrase.fr}</span>
        </p>
        <p className="ct-hint">
          {build.input === 'frame' ? rcopy.build_task_frame : fill(rcopy.build_task_free, { n: String(build.maxWords) })} · <span lang="fr">{avoid}</span>
        </p>
        {build.input === 'frame' && build.frame && (
          <p className="ct-frame__fr" lang="fr">
            {build.frame.fr}…
          </p>
        )}
        {textAnswerField({ label: rcopy.build_label, value: text, rows: 2, disabled: busy, onChange: setText })}
        <p className="ct-foot__hint" aria-live="polite">
          {fill(rcopy.words_count, { n: String(count), max: String(build.maxWords) })}
        </p>
        {tooMuch && (
          <p className="ct-why" lang={glossLanguage}>
            {fill(xcopy.errors.says_too_much, { avoid: build.avoidFr })}
          </p>
        )}
      </div>
    );
  }

  let suite: React.ReactNode = null;
  const marked = build.proof === 'marked';
  const draft = build.draftFr ?? build.learnerFr ?? '';
  if (told && marked) {
    suite = (
      <>
        <RomyLine line={COMPTOIR_LINES.proof_marked} props={props} anchor="start" />
        <section className="ct-paper" data-proof="marked" aria-label={COMPTOIR_FR.proof_marked}>
          <p className="ct-paper__k" lang="fr">
            {COMPTOIR_FR.proof_marked}
          </p>
          <RvProofMarks
            key={`marks-${build.tries}`}
            draftFr={draft}
            marks={build.marks}
            kindLabels={ccopy.mark_kinds}
            copy={ccopy.pourquoi}
            whyLanguage={glossLanguage}
            idPrefix="rb"
          />
        </section>
      </>
    );
  } else if (told && build.proof) {
    const printed = build.printedFr ?? draft;
    const label = inPaperLabel(build.proof, build.input === 'tiles');
    suite = (
      <section className="ct-paper" data-ct-anchor="start" data-proof={build.proof} aria-label={label}>
        <p className="ct-paper__k" lang="fr">
          {label}
        </p>
        <p className="ct-paper__fr rb-headline" lang="fr">
          {build.proof === 'corrected'
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
        <RvProofNotes notes={build.notes} kindLabels={ccopy.mark_kinds} copy={ccopy.pourquoi} whyLanguage={glossLanguage} />
      </section>
    );
  }

  let foot: React.ReactNode;
  if (!told) {
    foot = (
      <>
        {!ready && build.input === 'tiles' && <p className="ct-foot__hint">{rcopy.build_task_tiles}</p>}
        <Action tone="primary" pending={pending === 'build'} pendingLabel={rcopy.build_send} disabled={!ready || busy} onClick={send}>
          {rcopy.build_send}
        </Action>
      </>
    );
  } else if (marked) {
    const tryNumber = Math.min(build.tries + 1, build.maxTries);
    foot = (
      <>
        <p className="ct-foot__hint">{fill(ccopy.fix_try, { n: String(tryNumber), max: String(build.maxTries) })}</p>
        <RvComposer
          key={`fix-${build.tries}`}
          initial={draft}
          label={ccopy.fix_label}
          placeholder={ccopy.fix_placeholder}
          disabled={busy}
          onSend={(value, how) => void onAct({ act: 'build_fix', text: value, mode: how }, 'fix')}
          copy={copy}
        />
        {build.tries >= 1 && (
          <Action tone="quiet" pending={pending === 'romy'} pendingLabel={ccopy.fix_romy} disabled={busy} onClick={() => void onAct({ act: 'build_fix', value: 'romy' }, 'romy')}>
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
      <div className="rv-body ct-body" data-step="build" data-input={build.input}>
        <RomyLine line={RUBRIQUE_LINES.build_ask} props={props} past={told} />
        {told && build.learnerFr && <MineLine textFr={build.learnerFr} copy={copy} />}
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

