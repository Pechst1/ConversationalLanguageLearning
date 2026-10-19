/**
 * «Au comptoir» · step 3, «L'intox» (§3 step 3; skipped when the band has none):
 * Romy «Attends… quelqu'un a dit un truc faux. Qui ?» over the three takes as
 * compact quotes to tap. A wrong guess: «Non, relis bien.» and the claim that
 * settles it, with its source; two tries, then she says who it was. Then her
 * question and the fix — two options at A1–A2, the prefilled «C'est faux, … !
 * C'est …, pas …» from B1 (in the foot's field). The result: the right sentence
 * as the learner's line (always, even after a wrong fix), the claim and its
 * source (unless a missed guess already showed it), the liar caught, and «C'est
 * faux, c'est…, pas…» as today's phrase.
 */

import React from 'react';

import { Action, CastPortrait } from '@/components/atelier-v2/ui';

import { fill } from '../revue-copy';
import { RvComposer } from '../RvComposer';
import { RvClaim } from '../RvThread';
import { COMPTOIR_LINES } from './comptoir-copy';
import { castName, hasBlank, quoteSegments } from './comptoir-model';
import { ComptoirBubble, RomyLine, type ComptoirStepProps } from './RvComptoirParts';

const fold = (text: string) =>
  text
    .normalize('NFC')
    .replace(/’/g, "'")
    .toLowerCase()
    .replace(/[\s.!]+$/, '')
    .trim();

export function RvComptoirIntox(props: ComptoirStepProps) {
  const { session, view, copy, ccopy, glossLanguage, glosses, voice, pending, readOnly, onAct, onContinue, wordFor, notice, footRef } = props;
  const intox = view.intox;
  if (!intox) return null;
  const support = session.plan.support;
  const lower = view.band !== 'b1';
  const fix = intox.fix;
  const wrongTries = intox.tries.filter((id) => id !== intox.by);
  const liar = intox.by;
  const liarName = liar ? castName(view, liar) : '';
  // The claim that settles it, once a guess missed; the fix never repeats it.
  const hintShown = wrongTries.length > 0 && Boolean(intox.hintClaim);

  const pickQuote = (castId: string) => void onAct({ act: 'intox_who', guestId: castId }, 'who');

  let foot: React.ReactNode = null;
  if (fix) {
    foot = (
      <Action tone="primary" disabled={pending !== null} onClick={onContinue}>
        {copy.continue}
      </Action>
    );
  } else if (intox.resolved && !lower) {
    foot = (
      <RvComposer
        key="intox-fix"
        initial={intox.prefillFr ?? ''}
        label={ccopy.intox_fix_label}
        placeholder={ccopy.intox_fix_placeholder}
        disabled={pending !== null}
        onSend={(text, mode) => void onAct({ act: 'intox_fix', text, mode }, 'fix')}
        copy={copy}
      />
    );
  } else {
    foot = (
      <>
        {!intox.resolved && <p className="ct-foot__hint">{ccopy.intox_pick_hint}</p>}
        <Action tone="primary" disabled onClick={onContinue}>
          {copy.continue}
        </Action>
      </>
    );
  }

  return (
    <>
      <div className="rv-body ct-body" data-step="intox">
        <RomyLine line={COMPTOIR_LINES.intox_ask} props={props} />
        <ol className="ct-pick" aria-label={ccopy.intox_pick_hint}>
          {intox.quotes.map((quote) => {
            const tried = wrongTries.includes(quote.castId);
            const caught = intox.resolved && quote.castId === liar;
            const segments = quoteSegments(quote.quoteFr, caught && fix ? fix.wrongFr : null);
            return (
              <li key={quote.castId}>
                <button
                  type="button"
                  className="ct-pick__b"
                  data-char={quote.castId}
                  data-state={caught ? 'liar' : tried ? 'tried' : undefined}
                  disabled={readOnly || intox.resolved || tried || pending !== null}
                  aria-pressed={caught || tried}
                  onClick={() => pickQuote(quote.castId)}
                >
                  <CastPortrait characterId={quote.castId} name={quote.nameFr} size="xs" ring mood={caught ? 'surprised' : 'neutral'} />
                  <span className="ct-pick__fr" lang="fr">
                    <span className="av2-sr">{quote.nameFr} : </span>«&nbsp;
                    {segments.map((segment, index) =>
                      segment.wrong ? (
                        <s key={index} className="ct-strike">
                          {segment.text}
                        </s>
                      ) : (
                        <React.Fragment key={index}>{segment.text}</React.Fragment>
                      ),
                    )}
                    &nbsp;»
                  </span>
                  {tried && <span className="ct-pick__no">{ccopy.intox_not_this}</span>}
                </button>
              </li>
            );
          })}
        </ol>
        {wrongTries.length > 0 && (
          <>
            {!intox.resolved && <RomyLine line={COMPTOIR_LINES.intox_wrong} props={props} anchor="nearest" />}
            {hintShown && intox.hintClaim && (
              <RvClaim claim={intox.hintClaim} support={support} glosses={glosses} band={session.plan.band} glossLanguage={glossLanguage} copy={copy} onWord={wordFor(null)} />
            )}
          </>
        )}
        {intox.resolved && (
          <RomyLine
            line={intox.found ? COMPTOIR_LINES.intox_found : COMPTOIR_LINES.intox_reveal}
            vars={{ name: liarName }}
            extra={intox.ask}
            props={props}
            anchor={lower && intox.options.length > 0 ? undefined : 'nearest'}
          />
        )}
        {intox.resolved && lower && intox.options.length > 0 && (
          <div className="ct-opts" role="group" aria-label={intox.ask?.fr ?? ''} data-ct-anchor="nearest">
            {intox.options.map((option) => {
              const right = fix ? fold(option) === fold(fix.rightFr) : false;
              const chosen = fix ? fold(option) === fold(fix.answerFr) : false;
              return (
                <button
                  key={option}
                  type="button"
                  className="ct-opt"
                  lang="fr"
                  data-state={fix ? (right ? 'ok' : chosen ? 'no' : undefined) : undefined}
                  aria-pressed={chosen}
                  disabled={readOnly || Boolean(fix) || pending !== null}
                  onClick={() => void onAct({ act: 'intox_fix', value: option }, 'fix')}
                >
                  {option}
                </button>
              );
            })}
          </div>
        )}
        {fix && (
          <>
            {!lower && <p className="rv-thread__mine ct-mine" lang="fr">{fix.answerFr}</p>}
            {!fix.correct && (
              <p className="ct-hint" data-ct-anchor="start">
                {fill(ccopy.intox_wrong_answer, { right: fix.rightFr })}
              </p>
            )}
            <div className="ct-fb" data-correct={fix.correct ? '' : undefined} data-ct-anchor={fix.correct ? 'start' : undefined}>
              {/* A B1 line already word for word the right one is not printed twice. */}
              {(lower || fold(fix.answerFr) !== fold(fix.lineFr)) && (
                <p className="ct-fb__fr" lang="fr">
                  {fix.lineFr}
                </p>
              )}
              <p className="ct-fb__note">{ccopy.intox_your_line}</p>
            </div>
            {fix.claim && !(hintShown && intox.hintClaim?.id === fix.claim.id) && (
              <RvClaim claim={fix.claim} support={support} glosses={glosses} band={session.plan.band} glossLanguage={glossLanguage} copy={copy} onWord={wordFor(null)} />
            )}
            {liar && fix.caught.fr && (
              <ComptoirBubble
                castId={liar}
                name={liarName}
                textFr={fix.caught.fr}
                translation={fix.caught.tr}
                mood="surprised"
                glosses={glosses}
                glossLanguage={glossLanguage}
                voice={voice}
                voiceKey={`ct-caught-${liar}`}
                copy={copy}
                ccopy={ccopy}
                onWord={wordFor(liar, liarName)}
              />
            )}
          </>
        )}
        {notice}
      </div>
      {!readOnly && (
        <div className="rv-foot ct-foot" ref={footRef} data-blank={intox.resolved && !lower && !fix && hasBlank(intox.prefillFr ?? '') ? '' : undefined}>
          {foot}
        </div>
      )}
    </>
  );
}

export default RvComptoirIntox;
